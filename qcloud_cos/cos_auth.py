# -*- coding: utf-8 -*-

import hmac
import time
import urllib
import hashlib
import logging
from urllib import quote_plus
from urlparse import urlparse
from requests.auth import AuthBase
logger = logging.getLogger(__name__)


def filter_headers(data):
    """只设置host content-type 还有x开头的头部"""
    headers = {}
    for i in data.keys():
        if i == 'Content-Type' or i == 'Host' or i[0] == 'x' or i[0] == 'X':
            headers[i] = data[i]
    return headers


def cos_quote(value):
    """对头部进行encode"""
    data = quote_plus(value, '-_.~')  # 保留字为-_.~,并且要对/进行Encode
    data = data.replace('+', '%20')  # 对于空格，需要Encode成%20,而不是+
    return data


class CosS3Auth(AuthBase):

    def __init__(self, access_id, secret_key, expire=10000):
        self._access_id = access_id
        self._secret_key = secret_key
        self._expire = expire

    def __call__(self, r):
        method = r.method.lower()  # 获取小写method
        uri = urllib.unquote(r.url)
        uri = uri.split('?')[0]
        rt = urlparse(uri)  # 解析host以及params
        logger.debug("url parse: " + str(rt))
        if rt.query != "" and ("&" in rt.query or '=' in rt.query):
            uri_params = dict(map(lambda s: s.lower().split('='), rt.query.split('&')))
        elif rt.query != "":
            uri_params = {rt.query: ""}
        else:
            uri_params = {}
        headers = filter_headers(r.headers)
        headers = dict([(k.lower(), cos_quote(v)) for k, v in headers.items()])  # headers中的key转换为小写，value进行encode
        format_str = "{method}\n{host}\n{params}\n{headers}\n".format(
            method=method.lower(),
            host=rt.path,
            params=urllib.urlencode(uri_params),
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
            ak=self._access_id,
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
