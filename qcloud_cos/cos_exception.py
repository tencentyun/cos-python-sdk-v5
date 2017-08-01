
class CosException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)


class UserDefinedError(CosException):
    def __init__(self, message):
        CosException.__init__(self, message)


class ServerError(CosException):
    def __init__(self, message):
        CosException.__init__(self, message)
