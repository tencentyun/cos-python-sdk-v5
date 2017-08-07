# -*- coding=utf-8

import xml.dom.minidom


class COSException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)


def digest_xml(data):
    msg = dict()
    try:
        tree = xml.dom.minidom.parseString(data)
        root = tree.documentElement

        result = root.getElementsByTagName('Code')
        msg['code'] = result[0].childNodes[0].nodeValue

        result = root.getElementsByTagName('Message')
        msg['message'] = result[0].childNodes[0].nodeValue

        result = root.getElementsByTagName('Resource')
        msg['resource'] = result[0].childNodes[0].nodeValue

        result = root.getElementsByTagName('RequestId')
        msg['requestid'] = result[0].childNodes[0].nodeValue

        result = root.getElementsByTagName('TraceId')
        msg['traceid'] = result[0].childNodes[0].nodeValue
        return msg
    except Exception as e:
        return "Response Error Msg Is INVALID"


class ClientError(COSException):
    """Client端错误，如timeout"""
    def __init__(self, message):
        COSException.__init__(self, message)


class COSServiceError(COSException):
    """COS Server端错误，可以获取特定的错误信息"""
    def __init__(self, message, status_code):
        COSException.__init__(self, message)
        self._origin_msg = message
        self._digest_msg = digest_xml(message)
        self._status_code = status_code

    def get_origin_msg(self):
        """获取原始的XML格式错误信息"""
        return self._origin_msg

    def get_digest_msg(self):
        """获取经过处理的dict格式的错误信息"""
        return self._digest_msg

    def get_status_code(self):
        """获取http error code"""
        return self._status_code

    def get_error_code(self):
        """获取COS定义的错误码描述,服务器返回错误信息格式出错时，返回空 """
        if isinstance(self._digest_msg, dict):
            return self._digest_msg['code']
        return ""

    def get_error_msg(self):
        if isinstance(self._digest_msg, dict):
            return self._digest_msg['message']
        return ""

    def get_resource_location(self):
        if isinstance(self._digest_msg, dict):
            return self._digest_msg['resource']
        return ""

    def get_trace_id(self):
        if isinstance(self._digest_msg, dict):
            return self._digest_msg['requestid']
        return ""

    def get_request_id(self):
        if isinstance(self._digest_msg, dict):
            return self._digest_msg['traceid']
        return ""
