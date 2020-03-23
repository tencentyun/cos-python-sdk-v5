# -*- coding=utf-8
import os
import uuid
import struct
import logging
from .cos_comm import xml_to_dict
from .cos_comm import to_unicode
from .cos_exception import CosServiceError

logger = logging.getLogger(__name__)


class EventStream():
    def __init__(self, rt):
        self._rt = rt
        self._raw = self._rt.raw
        self._finish = False

    def __iter__(self):
        return self

    def __next__(self):
        return self.next_event()

    next = __next__

    def next_event(self):
        """获取下一个事件"""
        if self._finish:
            """要把剩下的内容读完丢弃或者自己关连接,否则不会自动关连接"""
            self._raw.read()
            raise StopIteration
        total_byte_length = struct.unpack('>I', bytes(self._raw.read(4)))[0]  # message总长度
        header_byte_length = struct.unpack('>I', bytes(self._raw.read(4)))[0]  # header总长度
        prelude_crc = struct.unpack('>I', bytes(self._raw.read(4)))[0]
        # 处理headers
        offset = 0
        msg_headers = {}
        while offset < header_byte_length:
            header_name_length = struct.unpack('>B', bytes(self._raw.read(1)))[0]
            header_name = to_unicode(self._raw.read(header_name_length))
            header_value_type = struct.unpack('>B', bytes(self._raw.read(1)))[0]
            header_value_length = struct.unpack('>H', bytes(self._raw.read(2)))[0]
            header_value = to_unicode(self._raw.read(header_value_length))
            msg_headers[header_name] = header_value
            offset += 4 + header_name_length + header_value_length
        # 处理payload(输出给用户的dict中也为bytes)
        payload_byte_length = total_byte_length - header_byte_length - 16  # payload总长度
        payload = self._raw.read(payload_byte_length)
        message_crc = struct.unpack('>I', bytes(self._raw.read(4)))[0]
        if ':message-type' in msg_headers and msg_headers[':message-type'] == 'event':
            if ':event-type' in msg_headers and msg_headers[':event-type'] == "Records":
                return {'Records': {'Payload': payload}}
            elif ':event-type' in msg_headers and msg_headers[':event-type'] == "Stats":
                return {'Stats': {'Details': xml_to_dict(payload)}}
            elif ':event-type' in msg_headers and msg_headers[':event-type'] == "Progress":
                return {'Progress': {'Details': xml_to_dict(payload)}}
            elif ':event-type' in msg_headers and msg_headers[':event-type'] == "Cont":
                return {'Cont': {}}
            elif ':event-type' in msg_headers and msg_headers[':event-type'] == "End":
                self._finish = True
                return {'End': {}}
        # 处理Error Message(抛出异常)
        if ':message-type' in msg_headers and msg_headers[':message-type'] == 'error':
            error_info = dict()
            error_info['code'] = msg_headers[':error-code']
            error_info['message'] = msg_headers[':error-message']
            error_info['resource'] = self._rt.request.url
            error_info['requestid'] = ''
            error_info['traceid'] = ''
            if 'x-cos-request-id' in self._rt.headers:
                error_info['requestid'] = self._rt.headers['x-cos-request-id']
            if 'x-cos-trace-id' in self._rt.headers:
                error_info['traceid'] = self._rt.headers['x-cos-trace-id']
            logger.error(error_info)
            e = CosServiceError('POST', error_info, self._rt.status_code)
            raise e

    def get_select_result(self):
        """获取查询结果"""
        data = b""
        for event in self:
            if 'Records' in event:
                data += event['Records']['Payload']
        return data

    def get_select_result_to_file(self, file_name):
        """保存查询结果到文件"""
        tmp_file_name = "{file_name}_{uuid}".format(file_name=file_name, uuid=uuid.uuid4().hex)
        with open(tmp_file_name, 'wb') as fp:
            for event in self:
                if 'Records' in event:
                    data = event['Records']['Payload']
                    fp.write(data)
        if os.path.exists(file_name):
            os.remove(file_name)
        os.rename(tmp_file_name, file_name)
