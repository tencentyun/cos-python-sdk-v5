# -*- coding: utf-8 -*-

import hmac
import time
import urllib
import hashlib
import logging
from urllib import quote
from urlparse import urlparse
from requests.auth import AuthBase
logger = logging.getLogger(__name__)


def filter_headers(data):
    """只设置host content-type 还有x开头的头部.

    :param data(dict): 所有的头部信息.
    :return(dict): 计算进签名的头部.
    """
    headers = {}
    for i in data.keys():
        if i == 'Content-Type' or i == 'Host' or i[0] == 'x' or i[0] == 'X':
            headers[i] = data[i]
    return headers


def to_string(data):
    """转换unicode为string.

    :param data(unicode|string): 待转换的unicode|string.
    :return(string): 转换后的string.
    """
    if isinstance(data, unicode):
        return data.encode('utf8')
    return data


class CosS3Auth(AuthBase):

    def __init__(self, secret_id, secret_key, key='', params={}, expire=10000):
        self._secret_id = to_string(secret_id)
        self._secret_key = to_string(secret_key)
        self._expire = expire
        self._params = params
        if key:
            if key[0] == '/':
                self._path = key
            else:
                self._path = '/' + key
        else:
            self._path = '/'

    def __call__(self, r):
        path = self._path
        uri_params = self._params
        headers = filter_headers(r.headers)
        # reserved keywords in headers urlencode are -_.~, notice that / should be encoded and space should not be encoded to plus sign(+)
        headers = dict([(k.lower(), quote(v, '-_.~')) for k, v in headers.items()])  # headers中的key转换为小写，value进行encode
        format_str = "{method}\n{host}\n{params}\n{headers}\n".format(
            method=r.method.lower(),
            host=path,
            params=urllib.urlencode(sorted(uri_params.items())),
            headers='&'.join(map(lambda (x, y): "%s=%s" % (x, y), sorted(headers.items())))
        )
        logger.debug("format str: " + format_str)

        start_sign_time = int(time.time())
        sign_time = "{bg_time};{ed_time}".format(bg_time=start_sign_time-60, ed_time=start_sign_time+self._expire)
        sha1 = hashlib.sha1()
        sha1.update(format_str)

        str_to_sign = "sha1\n{time}\n{sha1}\n".format(time=sign_time, sha1=sha1.hexdigest())
        logger.debug('str_to_sign: ' + str(str_to_sign))
        sign_key = hmac.new(self._secret_key, sign_time, hashlib.sha1).hexdigest()
        sign = hmac.new(sign_key, str_to_sign, hashlib.sha1).hexdigest()
        logger.debug('sign_key: ' + str(sign_key))
        logger.debug('sign: ' + str(sign))
        sign_tpl = "q-sign-algorithm=sha1&q-ak={ak}&q-sign-time={sign_time}&q-key-time={key_time}&q-header-list={headers}&q-url-param-list={params}&q-signature={sign}"

        r.headers['Authorization'] = sign_tpl.format(
            ak=self._secret_id,
            sign_time=sign_time,
            key_time=sign_time,
            params=';'.join(sorted(map(lambda k: k.lower(), uri_params.keys()))),
            headers=';'.join(sorted(headers.keys())),
            sign=sign
        )
        logger.debug("sign_key" + str(sign_key))
        logger.debug(r.headers['Authorization'])
        logger.debug("request headers: " + str(r.headers))
        return r


if __name__ == "__main__":
    pass
