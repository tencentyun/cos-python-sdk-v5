# -*- coding=utf-8
import os
import uuid
import struct
from .cos_comm import xml_to_dict


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
            raise StopIteration
        total_byte_length = struct.unpack('>I', bytes(self._raw.read(4)))[0]  # message总长度
        header_byte_length = struct.unpack('>I', bytes(self._raw.read(4)))[0]  # header总长度
        prelude_crc = struct.unpack('>I', bytes(self._raw.read(4)))[0]
        # 处理headers
        offset = 0
        msg_headers = {}
        while offset < header_byte_length:
            header_name_length = struct.unpack('>B', bytes(self._raw.read(1)))[0]
            header_name = self._raw.read(header_name_length)
            header_value_type = struct.unpack('>B', bytes(self._raw.read(1)))[0]
            header_value_length = struct.unpack('>H', bytes(self._raw.read(2)))[0]
            header_value = self._raw.read(header_value_length)
            msg_headers[header_name] = header_value
            offset += 4 + header_name_length + header_value_length
        # 处理payload
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
