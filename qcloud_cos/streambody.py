# -*- coding=utf-8
import os
import uuid


class StreamBody(object):
    def __init__(self, rt):
        self._rt = rt
        self._read_len = 0
        self._content_len = 0
        self._use_chunked = False
        self._use_encoding = False
        if 'Content-Length' in self._rt.headers:
            self._content_len = int(self._rt.headers['Content-Length'])
        elif 'Transfer-Encoding' in self._rt.headers and self._rt.headers['Transfer-Encoding'] == "chunked":
            self._use_chunked = True
        else:
            raise IOError("create StreamBody failed without Content-Length header or Transfer-Encoding header")

        if 'Content-Encoding' in self._rt.headers:
            self._use_encoding = True

    def __iter__(self):
        """提供一个默认的迭代器"""
        return self._rt.iter_content(1024)

    def __len__(self):
        return self._content_len

    def get_raw_stream(self):
        """提供原始流"""
        return self._rt.raw

    def get_stream(self, chunk_size=1024):
        """提供一个chunk可变的迭代器"""
        return self._rt.iter_content(chunk_size=chunk_size)

    def read(self, chunk_size=1024, auto_decompress=False):
        chunk = None
        if self._use_encoding and not auto_decompress:
            chunk = self._rt.raw.read(chunk_size)
        else:
            try:
                chunk = next(self._rt.iter_content(chunk_size))
            except StopIteration:
                return ''
        return chunk

    def get_stream_to_file(self, file_name, disable_tmp_file=False, auto_decompress=False):
        """保存流到本地文件"""
        self._read_len = 0
        tmp_file_name = "{file_name}_{uuid}".format(file_name=file_name, uuid=uuid.uuid4().hex)
        if disable_tmp_file:
            tmp_file_name = file_name
        chunk_size = 1024 * 1024
        with open(tmp_file_name, 'wb') as fp:
            while True:
                chunk = self.read(chunk_size, auto_decompress)
                if not chunk:
                    break
                self._read_len += len(chunk)
                fp.write(chunk)

        if not self._use_chunked and not (
                self._use_encoding and auto_decompress) and self._read_len != self._content_len:
            if os.path.exists(tmp_file_name):
                os.remove(tmp_file_name)
            raise IOError("download failed with incomplete file")
        if file_name != tmp_file_name:
            if os.path.exists(file_name):
                os.remove(file_name)
            os.rename(tmp_file_name, file_name)

    def pget_stream_to_file(self, fdst, offset, expected_len, auto_decompress=False):
        """保存流到本地文件的offset偏移"""
        self._read_len = 0
        fdst.seek(offset, 0)
        chunk_size = 1024 * 1024
        while True:
            chunk = self.read(chunk_size, auto_decompress)
            if not chunk:
                break
            self._read_len += len(chunk)
            fdst.write(chunk)

        if not self._use_chunked and not (self._use_encoding and auto_decompress) and self._read_len != expected_len:
            raise IOError("download failed with incomplete file")
