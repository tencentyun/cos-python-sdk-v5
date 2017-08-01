import xml.dom.minidom


class COSException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)


class COSBadResponseError(COSException):
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
        raise COSBadResponseError("Response Error Msg Is INVALID")


class ClientError(COSException):
    def __init__(self, message):
        COSException.__init__(self, message)


class COSServiceError(COSException):
    def __init__(self, message):
        COSException.__init__(self, message)
        self._msg = digest_xml(message)

    def get_full_msg(self):
        return self._msg

    def get_error_code(self):
        return self._msg['code']

    def get_error_msg(self):
        return self._msg['message']

    def get_resource_location(self):
        return self._msg['resource']

    def get_trace_id(self):
        return self._msg['requestid']

    def get_request_id(self):
        return self._msg['traceid']
