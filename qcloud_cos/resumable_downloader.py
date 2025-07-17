# -*- coding: utf-8 -*-

import json
import os
import sys
import errno
import threading
import logging
import uuid
import hashlib
import crcmod
from .cos_comm import *
from .streambody import StreamBody
from .cos_threadpool import SimpleThreadPool

logger = logging.getLogger(__name__)


class ResumableDownLoader(object):
    def __init__(self, cos_client, bucket, key, dest_filename, object_info, part_size=20, max_thread=5,
                 enable_crc=False, progress_callback=None, dump_record_dir=None, key_simplify_check=True, **kwargs):
        self.__cos_client = cos_client
        self.__bucket = bucket
        self.__key = key
        self.__dest_file_path = os.path.abspath(dest_filename)
        self.__object_info = object_info
        self.__max_thread = max_thread
        self.__enable_crc = enable_crc
        self.__progress_callback = progress_callback
        self.__headers = kwargs
        self.__key_simplify_check = key_simplify_check

        self.__max_part_count = 100  # 取决于服务端是否对并发有限制
        self.__min_part_size = 1024 * 1024  # 1M
        self.__part_size = self.__determine_part_size_internal(int(object_info['Content-Length']), part_size)
        self.__finished_parts = []
        self.__lock = threading.Lock()
        self.__record = None  # 记录当前的上下文
        if not dump_record_dir:
            self.__dump_record_dir = os.path.join(os.path.expanduser('~'), '.cos_download_tmp_file')
        else:
            self.__dump_record_dir = dump_record_dir

        record_filename = self.__get_record_filename(bucket, key, self.__dest_file_path)
        self.__record_filepath = os.path.join(self.__dump_record_dir, record_filename)
        self.__tmp_file = None

        if not os.path.exists(self.__dump_record_dir):
            # 多进程并发情况下makedirs会出现冲突, 需要进行异常捕获
            try:
                os.makedirs(self.__dump_record_dir)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    logger.error('os makedir error: dir: {0}, errno {1}'.format(self.__dump_record_dir, e.errno))
                    raise
                pass
        logger.debug('resumale downloader init finish, bucket: {0}, key: {1}'.format(bucket, key))

    def start(self):
        logger.debug('start resumable download, bucket: {0}, key: {1}'.format(self.__bucket, self.__key))
        self.__load_record()  # 从record文件中恢复读取上下文

        assert self.__tmp_file
        open(self.__tmp_file, 'a').close()

        # 已完成分块先设置下载进度
        if self.__progress_callback:
            for finished_part in self.__finished_parts:
                self.__progress_callback.report(finished_part.length)

        parts_need_to_download = self.__get_parts_need_to_download()
        logger.debug('parts_need_to_download: {0}'.format(parts_need_to_download))
        pool = SimpleThreadPool(self.__max_thread)
        for part in parts_need_to_download:
            part_range = "bytes=" + str(part.start) + "-" + str(part.start + part.length - 1)
            headers = dict.copy(self.__headers)
            headers["Range"] = part_range
            pool.add_task(self.__download_part, part, headers)

        pool.wait_completion()
        result = pool.get_result()
        if not result['success_all']:
            raise CosClientError('some download_part fail after max_retry, please download_file again')

        if os.path.exists(self.__dest_file_path):
            os.remove(self.__dest_file_path)
        os.rename(self.__tmp_file, self.__dest_file_path)

        if self.__enable_crc:
            self.__check_crc()

        self.__del_record()
        logger.debug('download success, bucket: {0}, key: {1}'.format(self.__bucket, self.__key))

    def __get_record_filename(self, bucket, key, dest_file_path):
        dest_file_path_md5 = hashlib.md5(dest_file_path.encode("utf-8")).hexdigest()
        key_md5 = hashlib.md5(key.encode("utf-8")).hexdigest()
        return '{0}_{1}.{2}'.format(bucket, key_md5, dest_file_path_md5)

    def __determine_part_size_internal(self, file_size, part_size):
        real_part_size = part_size * 1024 * 1024  # MB
        if real_part_size < self.__min_part_size:
            real_part_size = self.__min_part_size

        while real_part_size * self.__max_part_count < file_size:
            real_part_size = real_part_size * 2
        logger.debug('finish to determine part size, file_size: {0}, part_size: {1}'.format(file_size, real_part_size))
        return real_part_size

    def __splite_to_parts(self):
        parts = []
        file_size = int(self.__object_info['Content-Length'])
        num_parts = int((file_size + self.__part_size - 1) / self.__part_size)
        for i in range(num_parts):
            start = i * self.__part_size
            if i == num_parts - 1:
                length = file_size - start
            else:
                length = self.__part_size

            parts.append(PartInfo(i + 1, start, length))
        return parts

    def __get_parts_need_to_download(self):
        all_set = set(self.__splite_to_parts())
        logger.debug('all_set: {0}'.format(len(all_set)))
        finished_set = set(self.__finished_parts)
        logger.debug('finished_set: {0}'.format(len(finished_set)))
        return list(all_set - finished_set)

    def __download_part(self, part, headers):
        with open(self.__tmp_file, 'rb+') as f:
            f.seek(part.start, 0)
            range = None
            traffic_limit = None
            if 'Range' in headers:
                range = headers['Range']

            if 'TrafficLimit' in headers:
                traffic_limit = headers['TrafficLimit']
            logger.debug("part_id: {0}, part_range: {1}, traffic_limit:{2}".format(part.part_id, range, traffic_limit))
            result = self.__cos_client.get_object(Bucket=self.__bucket, Key=self.__key, KeySimplifyCheck=self.__key_simplify_check, **headers)
            result["Body"].pget_stream_to_file(f, part.start, part.length)

        self.__finish_part(part)

        if self.__progress_callback:
            self.__progress_callback.report(part.length)

    def __finish_part(self, part):
        logger.debug('download part finished,bucket: {0}, key: {1}, part_id: {2}'.
                     format(self.__bucket, self.__key, part.part_id))
        with self.__lock:
            self.__finished_parts.append(part)
            self.__record['parts'].append({'part_id': part.part_id, 'start': part.start, 'length': part.length})
            self.__dump_record(self.__record)

    def __dump_record(self, record):
        record_filepath = self.__record_filepath
        if os.path.exists(self.__record_filepath):
            record_filepath += '.tmp'
        with open(record_filepath, 'w') as f:
            json.dump(record, f)
            logger.debug(
                'dump record to {0}, bucket: {1}, key: {2}'.format(record_filepath, self.__bucket, self.__key))
        if record_filepath != self.__record_filepath:
            os.remove(self.__record_filepath)
            os.rename(record_filepath, self.__record_filepath)

    def __load_record(self):
        record = None

        if os.path.exists(self.__record_filepath):
            with open(self.__record_filepath, 'r') as f:
                record = json.load(f)
            ret = self.__check_record(record)
            # record记录是否跟head object的一致，不一致则删除
            if not ret:
                self.__del_record()
                record = None
            else:
                self.__part_size = record['part_size']
                self.__tmp_file = record['tmp_filename']
                if not os.path.exists(self.__tmp_file):
                    record = None
                    self.__tmp_file = None
                    self.__del_record()
                else:
                    self.__finished_parts = list(
                        PartInfo(p['part_id'], p['start'], p['length']) for p in record['parts'])
                    logger.debug('load record: finished parts nums: {0}'.format(len(self.__finished_parts)))
                    self.__record = record

        if not record:
            self.__tmp_file = "{file_name}_{uuid}".format(file_name=self.__dest_file_path, uuid=uuid.uuid4().hex)
            record = {'bucket': self.__bucket, 'key': self.__key, 'tmp_filename': self.__tmp_file,
                      'mtime': self.__object_info['Last-Modified'], 'etag': self.__object_info['ETag'],
                      'file_size': self.__object_info['Content-Length'], 'part_size': self.__part_size, 'parts': []}
            self.__record = record
            self.__dump_record(record)

    def __check_record(self, record):
        return record['etag'] == self.__object_info['ETag'] and \
               record['mtime'] == self.__object_info['Last-Modified'] and \
               record['file_size'] == self.__object_info['Content-Length']

    def __del_record(self):
        os.remove(self.__record_filepath)
        logger.debug('ResumableDownLoader delete record_file, path: {0}'.format(self.__record_filepath))

    def __check_crc(self):
        logger.debug('start to check crc')
        c64 = crcmod.mkCrcFun(0x142F0E1EBA9EA3693, initCrc=0, xorOut=0xffffffffffffffff, rev=True)
        with open(self.__dest_file_path, 'rb') as f:
            local_crc64 = str(c64(f.read()))
        object_crc64 = self.__object_info['x-cos-hash-crc64ecma']
        if local_crc64 is not None and object_crc64 is not None and local_crc64 != object_crc64:
            raise CosClientError('crc of client: {0} is mismatch with cos: {1}'.format(local_crc64, object_crc64))


class PartInfo(object):
    def __init__(self, part_id, start, length):
        self.part_id = part_id
        self.start = start
        self.length = length

    def __eq__(self, other):
        return self.__key() == other.__key()

    def __hash__(self):
        return hash(self.__key())

    def __key(self):
        return self.part_id, self.start, self.length
