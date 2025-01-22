# -*- coding: utf-8 -*-

from six.moves.urllib.parse import quote, unquote, urlparse, urlencode
import hmac
import time
import hashlib
import logging
from requests.auth import AuthBase
from .cos_comm import to_unicode, to_bytes, to_str

logger = logging.getLogger(__name__)


def filter_headers(data):
    """只设置host content-type 还有x开头的头部.

    :param data(dict): 所有的头部信息.
    :return(dict): 计算进签名的头部.
    """
    valid_headers = [
        "cache-control",
        "content-disposition",
        "content-encoding",
        "content-type",
        "content-md5",
        "content-length",
        "expect",
        "expires",
        "host",
        "if-match",
        "if-modified-since",
        "if-none-match",
        "if-unmodified-since",
        "origin",
        "range",
        "transfer-encoding",
        "pic-operations",
    ]
    headers = {}
    for i in data:
        if str.lower(i) in valid_headers or str.lower(i).startswith("x-cos-") or str.lower(i).startswith("x-ci-"):
            headers[i] = data[i]
    return headers


class CosS3Auth(AuthBase):

    def __init__(self, conf, key=None, params={}, expire=10000, sign_host=None):
        self._secret_id = conf._secret_id if conf._secret_id else \
            (conf._credential_inst.secret_id if conf._credential_inst else None)
        self._secret_key = conf._secret_key if conf._secret_key else \
            (conf._credential_inst.secret_key if conf._credential_inst else None)
        self._anonymous = conf._anonymous
        self._expire = expire
        self._params = params
        self._sign_params = conf._sign_params

        # 如果API指定了是否签名host，则以具体API为准，如果未指定则以配置为准
        if sign_host is not None:
            self._sign_host = bool(sign_host)
        else:
            self._sign_host = conf._sign_host

        if key:
            key = to_unicode(key)
            if key[0] == u'/':
                self._path = key
            else:
                self._path = u'/' + key
        else:
            self._path = u'/'

    def __call__(self, r):

        # 匿名请求直接返回
        if self._anonymous:
            r.headers['Authorization'] = ""
            logger.debug("anonymous reqeust")
            return r

        path = self._path
        uri_params = {}
        if self._sign_params:
            uri_params = self._params
        headers = filter_headers(r.headers)

        # 如果headers中不包含host头域，则从url中提取host，并且加入签名计算
        if self._sign_host:

            # 判断headers中是否包含host头域
            contain_host = False
            for i in headers:
                if str.lower(i) == "host":  # 兼容host/Host/HOST等
                    contain_host = True
                    break

            # 从url中提取host
            if not contain_host:
                url_parsed = urlparse(r.url)
                if url_parsed.hostname is not None:
                    headers["host"] = url_parsed.hostname

        # reserved keywords in headers urlencode are -_.~, notice that / should be encoded and space should not be encoded to plus sign(+)
        headers = dict([(quote(to_bytes(to_str(k)), '-_.~').lower(), quote(to_bytes(to_str(v)), '-_.~')) for k, v in
                        headers.items()])  # headers中的key转换为小写，value进行encode
        uri_params = dict([(quote(to_bytes(to_str(k)), '-_.~').lower(), quote(to_bytes(to_str(v)), '-_.~')) for k, v in
                           uri_params.items()])
        format_str = u"{method}\n{host}\n{params}\n{headers}\n".format(
            method=r.method.lower(),
            host=path,
            params='&'.join(map(lambda tupl: "%s=%s" %
                            (tupl[0], tupl[1]), sorted(uri_params.items()))),
            headers='&'.join(map(lambda tupl: "%s=%s" %
                             (tupl[0], tupl[1]), sorted(headers.items())))
        )
        logger.debug("format str: " + format_str)

        start_sign_time = int(time.time())
        sign_time = "{bg_time};{ed_time}".format(
            bg_time=start_sign_time - 60, ed_time=start_sign_time + self._expire)
        sha1 = hashlib.sha1()
        sha1.update(to_bytes(format_str))

        str_to_sign = "sha1\n{time}\n{sha1}\n".format(
            time=sign_time, sha1=sha1.hexdigest())
        logger.debug('str_to_sign: ' + str(str_to_sign))
        sign_key = hmac.new(to_bytes(self._secret_key), to_bytes(
            sign_time), hashlib.sha1).hexdigest()
        sign = hmac.new(to_bytes(sign_key), to_bytes(
            str_to_sign), hashlib.sha1).hexdigest()
        logger.debug('sign_key: ' + str(sign_key))
        logger.debug('sign: ' + str(sign))
        sign_tpl = "q-sign-algorithm=sha1&q-ak={ak}&q-sign-time={sign_time}&q-key-time={key_time}&q-header-list={headers}&q-url-param-list={params}&q-signature={sign}"

        r.headers['Authorization'] = sign_tpl.format(
            ak=self._secret_id,
            sign_time=sign_time,
            key_time=sign_time,
            params=';'.join(sorted(uri_params.keys())),
            headers=';'.join(sorted(headers.keys())),
            sign=sign
        )
        logger.debug("sign_key" + str(sign_key))
        logger.debug(r.headers['Authorization'])
        logger.debug("request headers: " + str(r.headers))
        return r


class CosRtmpAuth(AuthBase):

    def __init__(self, conf, bucket=None, channel=None, params={}, expire=3600, presign_expire=0):
        self._secret_id = conf._secret_id
        self._secret_key = conf._secret_key
        self._token = conf._token
        self._anonymous = conf._anonymous
        self._expire = expire
        self._presign_expire = presign_expire
        self._params = params
        if self._token:
            self._params['q-token'] = self._token
        self._path = u'/' + bucket + u'/' + channel

    def get_rtmp_sign(self):
        # get rtmp string
        canonicalized_param = ''
        for k, v in self._params.items():
            canonicalized_param += '{key}={value}&'.format(key=k, value=v)
        if self._presign_expire >= 60:
            canonicalized_param += 'presign={value}'.format(
                value=self._presign_expire)
        canonicalized_param = canonicalized_param.rstrip('&')
        rtmp_str = u"{path}\n{params}\n".format(
            path=self._path, params=canonicalized_param)
        logger.debug("rtmp str: " + rtmp_str)

        sha1 = hashlib.sha1()
        sha1.update(to_bytes(rtmp_str))
        # get time
        sign_time = int(time.time())
        sign_time_str = "{start_time};{end_time}".format(
            start_time=sign_time - 60, end_time=sign_time + self._expire)
        str_to_sign = "sha1\n{time}\n{sha1}\n".format(
            time=sign_time_str, sha1=sha1.hexdigest())
        logger.debug('str_to_sign: ' + str(str_to_sign))
        # get sinature
        signature = hmac.new(to_bytes(self._secret_key), to_bytes(
            str_to_sign), hashlib.sha1).hexdigest()
        logger.debug('signature: ' + str(signature))
        rtmp_sign = "q-sign-algorithm=sha1&q-ak={ak}&q-sign-time={sign_time}&q-key-time={key_time}&q-signature={sign}".format(
            ak=self._secret_id, sign_time=sign_time_str, key_time=sign_time_str, sign=signature)
        if canonicalized_param != '':
            return rtmp_sign + "&{params}".format(params=canonicalized_param)
        else:
            return rtmp_sign


if __name__ == "__main__":
    pass
