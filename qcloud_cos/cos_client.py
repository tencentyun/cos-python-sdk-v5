# -*- coding=utf-8

import requests
import logging
import hashlib
import base64
import os
import sys
import time
import copy
import json
import threading
import xml.dom.minidom
import xml.etree.ElementTree
from requests import Request, Session, ConnectionError, Timeout
from datetime import datetime
from six.moves.urllib.parse import quote, unquote, urlencode, urlparse
from six import text_type, binary_type
from hashlib import md5
from .streambody import StreamBody
from .xml2dict import Xml2Dict
from .cos_auth import CosS3Auth
from .cos_auth import CosRtmpAuth
from .cos_comm import *
from .cos_threadpool import SimpleThreadPool
from .cos_exception import CosClientError
from .cos_exception import CosServiceError
from .version import __version__
from .select_event_stream import EventStream
from .resumable_downloader import ResumableDownLoader

# python 3.10报错"module 'collections' has no attribute 'Iterable'"，这里先规避
if sys.version_info.major >= 3 and sys.version_info.minor >= 10:
    import collections.abc
    collections.Iterable = collections.abc.Iterable

logger = logging.getLogger(__name__)


class CosConfig(object):
    """config类，保存用户相关信息"""

    def __init__(self, Appid=None, Region=None, SecretId=None, SecretKey=None, Token=None, CredentialInstance=None, Scheme=None, Timeout=None,
                 Access_id=None, Access_key=None, Secret_id=None, Secret_key=None, Endpoint=None, IP=None, Port=None,
                 Anonymous=None, UA=None, Proxies=None, Domain=None, ServiceDomain=None, KeepAlive=True, PoolConnections=10,
                 PoolMaxSize=10, AllowRedirects=False, SignHost=True, EndpointCi=None, EndpointPic=None, EnableOldDomain=True, EnableInternalDomain=True, SignParams=True,
                 AutoSwitchDomainOnRetry=False, VerifySSL=None, SSLCert=None):
        """初始化，保存用户的信息

        :param Appid(string): 用户APPID.
        :param Region(string): 地域信息.
        :param SecretId(string): 秘钥SecretId.
        :param SecretKey(string): 秘钥SecretKey.
        :param Token(string): 临时秘钥使用的token.
        :param Scheme(string): http/https
        :param Timeout(int): http超时时间.
        :param Access_id(string): 秘钥AccessId(兼容).
        :param Access_key(string): 秘钥AccessKey(兼容).
        :param Secret_id(string): 秘钥SecretId(兼容).
        :param Secret_key(string): 秘钥SecretKey(兼容).
        :param Endpoint(string): endpoint.
        :param IP(string): 访问COS的ip
        :param Port(int):  访问COS的port
        :param Anonymous(bool):  是否使用匿名访问COS
        :param UA(string):  使用自定义的UA来访问COS
        :param Proxies(dict):  使用代理来访问COS
        :param Domain(string):  使用自定义的域名来访问COS
        :param ServiceDomain(string):  使用自定义的域名来访问cos service
        :param KeepAlive(bool):       是否使用长连接
        :param PoolConnections(int):  连接池个数
        :param PoolMaxSize(int):      连接池中最大连接数
        :param AllowRedirects(bool):  是否重定向
        :param SignHost(bool):  是否将host算入签名
        :param EndpointCi(string):  ci的endpoint
        :param EnableOldDomain(bool):  是否使用旧的myqcloud.com域名访问COS
        :param EnableInternalDomain(bool):  是否使用内网域名访问COS
        :param SignParams(bool): 是否将请求参数算入签名
        :param AutoSwitchDomainOnRetry(bool): 重试请求时是否将myqcloud.com域名切换为tencentcos.cn
        :param VerifySSL(bool or string): 是否开启SSL证书校验, 或客户端CA bundle证书文件路径. 示例: True/False 或 '/path/certfile'
        :param SSLCert(string or tuple): 客户端SSL证书路径. 示例: '/path/client.pem' 或 ('/path/client.cert', '/path/client.key')
        """
        self._appid = to_unicode(Appid)
        self._token = to_unicode(Token)
        self._timeout = Timeout
        self._region = Region
        self._endpoint = Endpoint
        self._endpoint_ci = EndpointCi
        self._endpoint_pic = EndpointPic
        self._ip = to_unicode(IP)
        self._port = Port
        self._anonymous = Anonymous
        self._ua = UA
        self._proxies = Proxies
        self._domain = Domain
        self._service_domain = ServiceDomain
        self._keep_alive = KeepAlive
        self._pool_connections = PoolConnections
        self._pool_maxsize = PoolMaxSize
        self._allow_redirects = AllowRedirects
        self._sign_host = SignHost
        self._copy_part_threshold_size = SINGLE_UPLOAD_LENGTH
        self._enable_old_domain = EnableOldDomain
        self._enable_internal_domain = EnableInternalDomain
        self._sign_params = SignParams
        self._auto_switch_domain_on_retry = AutoSwitchDomainOnRetry
        self._verify_ssl = VerifySSL
        self._ssl_cert = SSLCert

        if self._domain is None:
            self._endpoint = format_endpoint(Endpoint, Region, u'cos.', EnableOldDomain, EnableInternalDomain)
        if Scheme is None:
            Scheme = u'https'
        Scheme = to_unicode(Scheme)
        if (Scheme != u'http' and Scheme != u'https'):
            raise CosClientError('Scheme can be only set to http/https')
        self._scheme = Scheme

        # 格式化ci的endpoint 不支持自定义域名的
        # ci暂不支持新域名
        self._endpoint_ci = format_endpoint(EndpointCi, Region, u'ci.', True, False)
        self._endpoint_pic = format_endpoint(EndpointCi, Region, u'pic.', True, False)

        # 兼容(SecretId,SecretKey)以及(AccessId,AccessKey)
        if (SecretId and SecretKey):
            self._secret_id = self.convert_secret_value(SecretId)
            self._secret_key = self.convert_secret_value(SecretKey)
        elif (Secret_id and Secret_key):
            self._secret_id = self.convert_secret_value(Secret_id)
            self._secret_key = self.convert_secret_value(Secret_key)
        elif (Access_id and Access_key):
            self._secret_id = self.convert_secret_value(Access_id)
            self._secret_key = self.convert_secret_value(Access_key)
        elif (CredentialInstance and hasattr(CredentialInstance, "secret_id") and hasattr(CredentialInstance, "secret_key") and hasattr(CredentialInstance, "token")):
            self._secret_id = None
            self._secret_key = None
            self._credential_inst = CredentialInstance
        elif self._anonymous:
            self._secret_id = None
            self._secret_key = None
            self._credential_inst = None
        else:
            raise CosClientError('SecretId and SecretKey is Required!')

    def uri(self, bucket=None, path=None, endpoint=None, domain=None, useAppid=False):
        """拼接url

        :param bucket(string): 存储桶名称.
        :param path(string): 请求COS的路径.
        :return(string): 请求COS的URL地址.
        """
        scheme = self._scheme
        # 拼接请求的url,默认使用bucket和endpoint拼接请求域名
        # 使用自定义域名时则使用自定义域名访问
        # 指定ip和port时,则使用ip:port方式访问,优先级最高
        if domain is None:
            domain = self._domain
        if domain is not None:
            url = domain
        else:
            if endpoint is None:
                endpoint = self._endpoint

            if bucket is not None:
                bucket = format_bucket(bucket, self._appid)
                url = u"{bucket}.{endpoint}".format(bucket=bucket, endpoint=endpoint)
            else:
                if useAppid:
                    url = u"{appid}.{endpoint}".format(appid=self._appid, endpoint=endpoint)
                else:
                    url = u"{endpoint}".format(endpoint=endpoint)
        if self._ip is not None:
            url = self._ip
            if self._port is not None:
                url = u"{ip}:{port}".format(ip=self._ip, port=self._port)

        if path is not None:
            if not path:
                raise CosClientError("Key is required not empty")
            path = to_unicode(path)
            if path[0] == u'/':
                path = path[1:]
            path = quote(to_bytes(path), '/-_.~')
            path = path.replace('./', '.%2F')
            request_url = u"{scheme}://{url}/{path}".format(
                scheme=to_unicode(scheme),
                url=to_unicode(url),
                path=to_unicode(path)
            )
        else:
            request_url = u"{scheme}://{url}/".format(
                scheme=to_unicode(scheme),
                url=to_unicode(url)
            )
        return request_url

    def get_host(self, Bucket=None, Appid=None):
        """传入bucket名称,根据endpoint获取Host名称
        :param Bucket(string): bucket名称
        :return (string): Host名称
        """
        if Bucket is not None:
            return u"{bucket}.{endpoint}".format(bucket=format_bucket(Bucket, self._appid), endpoint=self._endpoint)
        if Appid is not None:
            return u"{appid}.{endpoint}".format(appid=Appid, endpoint=self._endpoint)

    def set_ip_port(self, IP, Port=None):
        """设置直接访问的ip:port,可以不指定Port,http默认为80,https默认为443
        :param IP(string): 访问COS的ip
        :param Port(int):  访问COS的port
        :return None
        """
        self._ip = to_unicode(IP)
        self._port = Port

    def set_credential(self, SecretId, SecretKey, Token=None):
        """设置访问的身份,包括secret_id,secret_key,临时秘钥token默认为空
        :param SecretId(string): 秘钥SecretId.
        :param SecretKey(string): 秘钥SecretKey.
        :param Token(string): 临时秘钥使用的token.
        """
        self._secret_id = self.convert_secret_value(SecretId)
        self._secret_key = self.convert_secret_value(SecretKey)
        self._token = self.convert_secret_value(Token)

    def set_copy_part_threshold_size(self, size):
        if size > 0:
            self._copy_part_threshold_size = size

    def convert_secret_value(self, value):
        value = to_unicode(value)

        if value.endswith(' ') or value.startswith(' '):
            raise CosClientError('secret_id and secret_key cannot contain spaces at the beginning and end')

        return value


class CosS3Client(object):
    """cos客户端类，封装相应请求"""

    __built_in_sessions = None  # 内置的静态连接池，多个Client间共享使用
    __built_in_pid = 0

    def __init__(self, conf, retry=3, session=None):
        """初始化client对象

        :param conf(CosConfig): 用户的配置.
        :param retry(int): 失败重试的次数.
        :param session(object): http session.
        """
        self._conf = conf
        self._retry = retry  # 重试的次数，分片上传时可适当增大
        self._retry_exe_times = 0 # 重试已执行次数

        if session is None:
            if not CosS3Client.__built_in_sessions:
                with threading.Lock():
                    if not CosS3Client.__built_in_sessions:  # 加锁后double check
                        CosS3Client.__built_in_sessions = self.generate_built_in_connection_pool(self._conf._pool_connections, self._conf._pool_maxsize)
                        CosS3Client.__built_in_pid = os.getpid()

            self._session = CosS3Client.__built_in_sessions
            self._use_built_in_pool = True
            logger.info("bound built-in connection pool when new client. maxsize=%d,%d" % (self._conf._pool_connections, self._conf._pool_maxsize))
        else:
            self._session = session
            self._use_built_in_pool = False

    def generate_built_in_connection_pool(self, PoolConnections, PoolMaxSize):
        """生成SDK内置的连接池，此连接池是client间共用的"""
        built_in_sessions = requests.session()
        built_in_sessions.mount('http://', requests.adapters.HTTPAdapter(pool_connections=PoolConnections, pool_maxsize=PoolMaxSize))
        built_in_sessions.mount('https://', requests.adapters.HTTPAdapter(pool_connections=PoolConnections, pool_maxsize=PoolMaxSize))
        logger.info("generate built-in connection pool success. maxsize=%d,%d" % (PoolConnections, PoolMaxSize))
        return built_in_sessions

    def handle_built_in_connection_pool_by_pid(self):
        if not CosS3Client.__built_in_sessions:
            return

        if not self._use_built_in_pool:
            return

        if CosS3Client.__built_in_pid == os.getpid():
            return

        with threading.Lock():
            if CosS3Client.__built_in_pid == os.getpid(): # 加锁后double check
                return

            # 重新生成内置连接池
            CosS3Client.__built_in_sessions.close()
            CosS3Client.__built_in_sessions = self.generate_built_in_connection_pool(self._conf._pool_connections, self._conf._pool_maxsize)
            CosS3Client.__built_in_pid = os.getpid()

            # 重新绑定到内置连接池
            self._session = CosS3Client.__built_in_sessions
            logger.info("bound built-in connection pool when new processor. maxsize=%d,%d" % (self._conf._pool_connections, self._conf._pool_maxsize))

    def get_conf(self):
        """获取配置"""
        return self._conf
    
    def get_retry_exe_times(self):
        """获取重试已执行次数"""
        return self._retry_exe_times
    
    def inc_retry_exe_times(self):
        """重试执行次数递增"""
        self._retry_exe_times += 1

    def get_auth(self, Method, Bucket, Key, Expired=300, Headers={}, Params={}, SignHost=None, UseCiEndPoint=False):
        """获取签名

        :param Method(string): http method,如'PUT','GET'.
        :param Bucket(string): 存储桶名称.
        :param Key(string): 请求COS的路径.
        :param Expired(int): 签名有效时间,单位为s.
        :param headers(dict): 签名中的http headers.
        :param params(dict): 签名中的http params.
        :param SignHost(bool): 是否将host算入签名.
        :return (string): 计算出的V5签名.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取上传请求的签名
            auth_string = client.get_auth(
                    Method='PUT',
                    Bucket='bucket',
                    Key='test.txt',
                    Expired=600,
                    Headers={'header1': 'value1'},
                    Params={'param1': 'value1'}
                )
            print (auth_string)
        """

        # python中默认参数只会初始化一次，这里重新生成可变对象实例避免多线程访问问题
        if not Headers:
            Headers = dict()
        if not Params:
            Params = dict()

        endpoint = None
        if UseCiEndPoint:
            endpoint = self._conf._endpoint_ci
        url = self._conf.uri(bucket=Bucket, path=Key, endpoint=endpoint)
        r = Request(Method, url, headers=Headers, params=Params)
        auth = CosS3Auth(self._conf, Key, Params, Expired, SignHost)
        return auth(r).headers['Authorization']

    def should_switch_domain(self, url, headers={}):
        host = urlparse(url).hostname
        if not 'x-cos-request-id' in headers and \
            self._conf._auto_switch_domain_on_retry and \
            re.match(r'^([a-z0-9-]+-[0-9]+\.)(cos\.[a-z]+-[a-z]+(-[a-z]+)?(-1)?)\.(myqcloud\.com)$', host):
            return True
        return False

    def send_request(self, method, url, bucket=None, timeout=30, cos_request=True, ci_request=False, appid=None, **kwargs):
        """封装request库发起http请求"""
        if self._conf._timeout is not None:  # 用户自定义超时时间
            timeout = self._conf._timeout
        if self._conf._ua is not None:
            kwargs['headers']['User-Agent'] = self._conf._ua
        else:
            kwargs['headers']['User-Agent'] = 'cos-python-sdk-v' + __version__
        if self._conf._token is not None:
            if ci_request:
                kwargs['headers']['x-ci-security-token'] = self._conf._token
            else:
                kwargs['headers']['x-cos-security-token'] = self._conf._token
        if self._conf._ip is not None:  # 使用IP访问时需要设置请求host
            if self._conf._domain is not None:
                kwargs['headers']['Host'] = self._conf._domain
            elif bucket is not None:
                kwargs['headers']['Host'] = self._conf.get_host(Bucket=bucket)
            elif appid is not None:
                kwargs['headers']['Host'] = self._conf.get_host(Appid=appid)
        if self._conf._keep_alive == False:
            kwargs['headers']['Connection'] = 'close'
        kwargs['headers'] = format_values(kwargs['headers'])

        file_position = None
        if 'data' in kwargs:
            body = kwargs['data']
            if hasattr(body, 'tell') and hasattr(body, 'seek') and hasattr(body, 'read'):
                try:
                    file_position = body.tell()  # 记录文件当前位置
                except Exception as ioe:
                    file_position = None
            kwargs['data'] = to_bytes(kwargs['data'])
        # 使用https访问时可设置ssl证书校验相关参数
        if self._conf._scheme == 'https':
            if self._conf._verify_ssl is not None:
                kwargs['verify'] = self._conf._verify_ssl
            if self._conf._ssl_cert is not None:
                kwargs['cert'] = self._conf._ssl_cert
        if self._conf._allow_redirects is not None:
            kwargs['allow_redirects'] = self._conf._allow_redirects
        exception_logbuf = list() # 记录每次重试的错误日志

        # 切换了进程需要重新生成连接池
        self.handle_built_in_connection_pool_by_pid()

        for j in range(self._retry + 1):
            try:
                if j != 0:
                    if client_can_retry(file_position, **kwargs):
                        kwargs['headers']['x-cos-sdk-retry'] = 'true' # SDK重试标记
                        self.inc_retry_exe_times()
                        time.sleep(j)
                    else:
                        break
                logger.debug("send request: url: {}, headers: {}".format(url, kwargs['headers']))
                if method == 'POST':
                    res = self._session.post(url, timeout=timeout, proxies=self._conf._proxies, **kwargs)
                elif method == 'GET':
                    res = self._session.get(url, timeout=timeout, proxies=self._conf._proxies, **kwargs)
                elif method == 'PUT':
                    res = self._session.put(url, timeout=timeout, proxies=self._conf._proxies, **kwargs)
                elif method == 'DELETE':
                    res = self._session.delete(url, timeout=timeout, proxies=self._conf._proxies, **kwargs)
                elif method == 'HEAD':
                    res = self._session.head(url, timeout=timeout, proxies=self._conf._proxies, **kwargs)
                logger.debug("recv response: status_code: {}, headers: {}".format(res.status_code, res.headers))
                if res.status_code < 400:  # 2xx和3xx都认为是成功的
                    if res.status_code == 301 or res.status_code == 302 or res.status_code == 307:
                        if j < self._retry and self.should_switch_domain(url, res.headers):
                            url = switch_hostname_for_url(url)
                            continue
                    return res
                elif res.status_code < 500:  # 4xx 不重试
                    break
                else:
                    if j == (self._retry - 1) and self.should_switch_domain(url, res.headers):
                        url = switch_hostname_for_url(url)
                    continue
            except Exception as e:  # 捕获requests抛出的如timeout等客户端错误,转化为客户端错误
                logger.debug("recv exception: {}".format(e))
                # 记录每次请求的exception
                exception_log = 'url:%s, retry_time:%d exception:%s' % (url, j, str(e))
                exception_logbuf.append(exception_log)
                if j < self._retry and (isinstance(e, ConnectionError) or isinstance(e, Timeout)):  # 只重试网络错误
                    if j == (self._retry - 1) and self.should_switch_domain(url):
                        url = switch_hostname_for_url(url)
                    continue
                logger.exception(exception_logbuf) # 最终重试失败, 输出前几次重试失败的exception
                raise CosClientError(str(e))

        if not cos_request:
            return res
        if res.status_code >= 400:  # 所有的4XX,5XX都认为是COSServiceError
            if method == 'HEAD' and res.status_code == 404:  # Head 需要处理
                info = dict()
                info['code'] = 'NoSuchResource'
                info['message'] = 'The Resource You Head Not Exist'
                info['resource'] = url
                if 'x-cos-request-id' in res.headers:
                    info['requestid'] = res.headers['x-cos-request-id']
                if 'x-cos-trace-id' in res.headers:
                    info['traceid'] = res.headers['x-cos-trace-id']
                logger.warning(info)
                if len(exception_logbuf) > 0:
                    logger.exception(exception_logbuf) # 最终重试失败, 输出前几次重试失败的exception
                raise CosServiceError(method, info, res.status_code)
            else:
                msg = res.text
                if msg == u'':  # 服务器没有返回Error Body时 给出头部的信息
                    msg = res.headers
                logger.error(msg)
                if len(exception_logbuf) > 0:
                    logger.exception(exception_logbuf) # 最终重试失败, 输出前几次重试失败的exception
                raise CosServiceError(method, msg, res.status_code)

        return None

    #  s3 object interface begin
    def put_object(self, Bucket, Body, Key, EnableMD5=False, **kwargs):
        """单文件上传接口，适用于小文件，最大不得超过5GB

        :param Bucket(string): 存储桶名称.
        :param Body(file|string): 上传的文件内容，类型为文件流或字节流.
        :param Key(string): COS路径.
        :param EnableMD5(bool): 是否需要SDK计算Content-MD5，打开此开关会增加上传耗时.
        :kwargs(dict): 设置上传的headers.
        :return(dict): 上传成功返回的结果，包含ETag等信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 上传本地文件到cos
            with open('test.txt', 'rb') as fp:
                response = client.put_object(
                    Bucket='bucket',
                    Body=fp,
                    Key='test.txt'
                )
                print (response['ETag'])
        """
        check_object_content_length(Body)
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("put object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        if EnableMD5:
            md5_str = get_content_md5(Body)
            if md5_str:
                headers['Content-MD5'] = md5_str
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key),
            data=Body,
            headers=headers)

        response = dict(**rt.headers)
        return response

    def get_object(self, Bucket, Key, KeySimplifyCheck=True, **kwargs):
        """单文件下载接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param KeySimplifyCheck(bool): 是否对Key进行posix路径语义归并检查
        :param kwargs(dict): 设置下载的headers.
        :return(dict): 下载成功返回的结果,包含Body对应的StreamBody,可以获取文件流或下载文件到本地.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 下载cos上的文件到本地
            response = client.get_object(
                Bucket='bucket',
                Key='test.txt'
            )
            response['Body'].get_stream_to_file('local_file.txt')
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        if 'versionId' in headers:
            params['versionId'] = headers['versionId']
            del headers['versionId']
        params = format_values(params)

        # 检查key: 按照posix路径语义合并后如果是'/'则抛异常(因为这导致GetObject请求变成GetBucket)
        if KeySimplifyCheck:
            path_simplify_check(path=Key)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("get object, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        response = dict(**rt.headers)
        response['Body'] = StreamBody(rt)

        return response

    def get_object_sensitive_content_recognition(self, Bucket, Key=None, DetectType=None, Interval=None, MaxFrames=None, BizType=None, DetectUrl=None, LargeImageDetect=None,
                                                 DataId=None, Async=0, CallBack=None, **kwargs):
        """文件内容识别接口 https://cloud.tencent.com/document/product/460/37318

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param DetectType(int): 内容识别标志,位计算 1:porn,8:ads
        :param Interval(int): 截帧频率，GIF图/长图检测专用，默认值为0，表示只会检测GIF图/长图的第一帧.
        :param MaxFrames(int): 最大截帧数量，GIF图/长图检测专用，默认值为1，表示只取GIF的第1帧图片进行审核，或长图不做切分识别.
        :param BizType(string): 审核策略的唯一标识，由后台自动生成，在控制台中对应为Biztype值.
        :param DetectUrl(string): 您可以通过填写detect-url审核任意公网可访问的图片链接。不填写detect-url时，后台会默认审核ObjectKey
            填写了detect-url时，后台会审核detect-url链接，无需再填写ObjectKey。 detect-url示例：http://www.example.com/abc.jpg.
        :param LargeImageDetect(int): 对于超过大小限制的图片是否进行压缩后再审核，取值为： 0（不压缩），1（压缩）。默认为0。
            注：压缩最大支持32M的图片，且会收取压缩费用。
        :param DataId(string): 图片标识，该字段在结果中返回原始内容，长度限制为512字节.
        :param Async(int): 是否异步进行审核，取值 0：同步返回结果，1：异步进行审核，默认为0。
        :param Callback(string): 审核结果（Detail版本）以回调形式发送至您的回调地址，异步审核时生效，支持以 http:// 或者 https:// 开头的地址，例如： http://www.callback.com。
        :param kwargs(dict): 设置下载的headers.
        :return(dict): 下载成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 识别cos上的图片
            response = client.get_object_sensitive_content_recognition(
                Bucket='bucket',
                DetectType=CiDetectType.PORN | CiDetectType.POLITICS,
                Key='test.png'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        if 'versionId' in headers:
            params['versionId'] = headers['versionId']
            del headers['versionId']
        params['ci-process'] = 'sensitive-content-recognition'
        if DetectType is not None:
            detect_type = ''
            if DetectType & CiDetectType.PORN > 0:
                detect_type += 'porn'
            if DetectType & CiDetectType.TERRORIST > 0:
                if len(detect_type) > 0:
                    detect_type += ','
                detect_type += 'terrorist'
            if DetectType & CiDetectType.POLITICS > 0:
                if len(detect_type) > 0:
                    detect_type += ','
                detect_type += 'politics'
            if DetectType & CiDetectType.ADS > 0:
                if len(detect_type) > 0:
                    detect_type += ','
                detect_type += 'ads'
            if DetectType & CiDetectType.TEENAGER > 0:
                if len(detect_type) > 0:
                    detect_type += ','
                detect_type += 'teenager'

            params['detect-type'] = detect_type
        if Interval:
            params['interval'] = Interval
        if MaxFrames:
            params['max-frames'] = MaxFrames
        if BizType:
            params['biz-type'] = BizType
        if DetectUrl:
            params['detect-url'] = DetectUrl
        if LargeImageDetect:
            params['large-image-detect'] = LargeImageDetect
        if DataId:
            params['dataid'] = DataId
        if Async != 0:
            params['async'] = Async
        if CallBack:
            params['callback'] = CallBack
        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("get object sensitive content recognition, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        logger.debug("get object sensitive content recognition rsp:%s", rt.content)
        data = xml_to_dict(rt.content)
        # format res
        if 'PornInfo' in data:
            if 'OcrResults' in data['PornInfo']:
                format_dict_or_list(data['PornInfo']['OcrResults'], ['Keywords'])
            format_dict(data['PornInfo'], ['OcrResults'])
        if 'TerroristInfo' in data:
            if 'OcrResults' in data['TerroristInfo']:
                format_dict_or_list(data['TerroristInfo']['OcrResults'], ['Keywords'])
            format_dict(data['TerroristInfo'], ['OcrResults'])
        if 'PoliticsInfo' in data:
            if 'OcrResults' in data['PoliticsInfo']:
                format_dict_or_list(data['PoliticsInfo']['OcrResults'], ['Keywords'])
            format_dict(data['PoliticsInfo'], ['OcrResults', 'ObjectResults'])
        if 'AdsInfo' in data:
            if 'OcrResults' in data['AdsInfo']:
                format_dict_or_list(data['AdsInfo']['OcrResults'], ['Keywords'])
            format_dict(data['AdsInfo'], ['OcrResults'])

        return data

    def get_presigned_url(self, Bucket, Key, Method, Expired=300, Params={}, Headers={}, UseCiEndPoint=False, SignHost=None):
        """生成预签名的url

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Method(string): HTTP请求的方法, 'PUT'|'POST'|'GET'|'DELETE'|'HEAD'
        :param Expired(int): 签名过期时间.
        :param Params(dict): 签入签名的参数
        :param Headers(dict): 签入签名的头部
        :param SignHost(bool): 是否将host算入签名.
        :return(string): 预先签名的URL.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取预签名链接
            response = client.get_presigned_url(
                Bucket='bucket',
                Key='test.txt',
                Method='PUT'
            )
        """
        endpoint = None
        if UseCiEndPoint:
            endpoint = self._conf._endpoint_ci
        url = self._conf.uri(bucket=Bucket, path=Key, endpoint=endpoint)
        sign = self.get_auth(Method=Method, Bucket=Bucket, Key=Key, Expired=Expired, Headers=Headers, Params=Params, SignHost=SignHost, UseCiEndPoint=UseCiEndPoint)
        sign = urlencode(dict([item.split('=', 1) for item in sign.split('&')]))
        url = url + '?' + sign
        if Params:
            url = url + '&' + urlencode(Params)
        return url

    def get_presigned_download_url(self, Bucket, Key, Expired=300, Params={}, Headers={}, UseCiEndPoint=False, SignHost=None):
        """生成预签名的下载url

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Expired(int): 签名过期时间.
        :param Params(dict): 签入签名的参数
        :param Headers(dict): 签入签名的头部
        :param SignHost(bool): 是否将host算入签名.
        :return(string): 预先签名的下载URL.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取预签名文件下载链接
            response = client.get_presigned_download_url(
                Bucket='bucket',
                Key='test.txt'
            )
        """
        return self.get_presigned_url(Bucket, Key, 'GET', Expired, Params, Headers, UseCiEndPoint, SignHost)

    def get_object_url(self, Bucket, Key):
        """生成对象访问的url

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :return(string): 对象访问的URL.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取预签名链接
            response = client.get_object_url(
                Bucket='bucket',
                Key='test.txt'
            )
        """
        url = self._conf.uri(bucket=Bucket, path=Key)
        return url

    def delete_object(self, Bucket, Key, **kwargs):
        """单文件删除接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置请求headers.
        :return: dict.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除一个文件
            response = client.delete_object(
                Bucket='bucket',
                Key='test.txt'
            )
        """
        headers = mapped(kwargs)
        params = {}
        if 'versionId' in headers:
            params['versionId'] = headers['versionId']
            del headers['versionId']
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("delete object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key, params),
            headers=headers,
            params=params)
        data = dict(**rt.headers)
        return data

    def delete_objects(self, Bucket, Delete={}, **kwargs):
        """文件批量删除接口,单次最多支持1000个object

        :param Bucket(string): 存储桶名称.
        :param Delete(dict): 批量删除的object信息.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 批量删除的结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 批量删除文件
            objects = {
                "Quiet": "true",
                "Object": [
                    {
                        "Key": "file_name1"
                    },
                    {
                        "Key": "file_name2"
                    }
                ]
            }
            response = client.delete_objects(
                Bucket='bucket',
                Delete=objects
            )
        """
        xml_config = format_xml(data=Delete, root='Delete')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'delete': ''}
        params = format_values(params)
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete objects, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        format_dict(data, ['Deleted', 'Error'])
        return data

    def head_object(self, Bucket, Key, **kwargs):
        """获取文件信息

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 文件的metadata信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询文件属性
            response = client.head_object(
                Bucket='bucket',
                Key='test.txt'
            )
        """
        headers = mapped(kwargs)
        params = {}
        if 'versionId' in headers:
            params['versionId'] = headers['versionId']
            del headers['versionId']
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("head object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='HEAD',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key, params=params),
            headers=headers,
            params=params)
        return dict(**rt.headers)

    def copy_object(self, Bucket, Key, CopySource, CopyStatus='Copy', **kwargs):
        """文件拷贝，文件信息修改

        :param Bucket(string): 存储桶名称.
        :param Key(string): 上传COS路径.
        :param CopySource(dict): 拷贝源,包含Appid,Bucket,Region,Key.
        :param CopyStatus(string): 拷贝状态,可选值'Copy'|'Replaced'.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 拷贝成功的结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 文件拷贝
            copy_source = {'Bucket': 'test04-1252448703', 'Key': '/test.txt', 'Region': 'ap-beijing-1'}
            response = client.copy_object(
                Bucket='bucket',
                Key='test.txt',
                CopySource=copy_source
            )
        """
        headers = mapped(kwargs)
        headers['x-cos-copy-source'] = gen_copy_source_url(CopySource, self._conf._enable_old_domain, self._conf._enable_internal_domain)
        if CopyStatus != 'Copy' and CopyStatus != 'Replaced':
            raise CosClientError('CopyStatus must be Copy or Replaced')
        headers['x-cos-metadata-directive'] = CopyStatus
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("copy object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key),
            headers=headers)
        body = xml_to_dict(rt.content)
        if 'ETag' not in body:
            logger.error(rt.content)
            raise CosServiceError('PUT', rt.content, 200)
        data = dict(**rt.headers)
        data.update(body)
        return data

    def upload_part_copy(self, Bucket, Key, PartNumber, UploadId, CopySource, CopySourceRange='', **kwargs):
        """拷贝指定文件至分块上传

        :param Bucket(string): 存储桶名称.
        :param Key(string): 上传COS路径.
        :param PartNumber(int): 上传分块的编号.
        :param UploadId(string): 分块上传创建的UploadId.
        :param CopySource(dict): 拷贝源,包含Appid,Bucket,Region,Key.
        :param CopySourceRange(string): 拷贝源的字节范围,bytes=first-last。
        :param kwargs(dict): 设置请求headers.
        :return(dict): 拷贝成功的结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 分块上传拷贝分块
            copy_source = {'Bucket': 'test04-1252448703', 'Key': '/test.txt', 'Region': 'ap-beijing-1'}
            response = client.upload_part_copy(
                Bucket='bucket',
                Key='test.txt',
                PartNumber=1,
                UploadId='your uploadid',
                CopySource=copy_source
            )
        """
        headers = mapped(kwargs)
        headers['x-cos-copy-source'] = gen_copy_source_url(CopySource, self._conf._enable_old_domain, self._conf._enable_internal_domain)
        headers['x-cos-copy-source-range'] = CopySourceRange
        params = {'partNumber': PartNumber, 'uploadId': UploadId}
        params = format_values(params)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.debug("upload part copy, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            headers=headers,
            params=params,
            auth=CosS3Auth(self._conf, Key, params=params))
        body = xml_to_dict(rt.content)
        data = dict(**rt.headers)
        data.update(body)
        return data

    def create_multipart_upload(self, Bucket, Key, **kwargs):
        """创建分块上传，适用于大文件上传

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 初始化分块上传返回的结果，包含UploadId等信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建分块上传
            response = client.create_multipart_upload(
                Bucket='bucket',
                Key='test.txt'
            )
        """
        headers = mapped(kwargs)
        params = {'uploads': ''}
        params = format_values(params)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("create multipart upload, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key, params=params),
            headers=headers,
            params=params)

        data = xml_to_dict(rt.content)
        return data

    def upload_part(self, Bucket, Key, Body, PartNumber, UploadId, EnableMD5=False, **kwargs):
        """上传分块，单个大小不得超过5GB

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Body(file|string): 上传分块的内容,可以为文件流或者字节流.
        :param PartNumber(int): 上传分块的编号.
        :param UploadId(string): 分块上传创建的UploadId.
        :param kwargs(dict): 设置请求headers.
        :param EnableMD5(bool): 是否需要SDK计算Content-MD5，打开此开关会增加上传耗时.
        :return(dict): 上传成功返回的结果，包含单个分块ETag等信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 分块上传
            with open('test.txt', 'rb') as fp:
                data = fp.read(1024*1024)
                response = client.upload_part(
                    Bucket='bucket',
                    Body=data,
                    Key='test.txt'
                )
        """
        check_object_content_length(Body)
        headers = mapped(kwargs)
        params = {'partNumber': PartNumber, 'uploadId': UploadId}
        params = format_values(params)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.debug("upload part, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        if EnableMD5:
            md5_str = get_content_md5(Body)
            if md5_str:
                headers['Content-MD5'] = md5_str
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            headers=headers,
            params=params,
            auth=CosS3Auth(self._conf, Key, params=params),
            data=Body)
        response = dict(**rt.headers)
        return response

    def complete_multipart_upload(self, Bucket, Key, UploadId, MultipartUpload={}, **kwargs):
        """完成分片上传,除最后一块分块块大小必须大于等于1MB,否则会返回错误.

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param UploadId(string): 分块上传创建的UploadId.
        :param MultipartUpload(dict): 所有分块的信息,包含Etag和PartNumber.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 上传成功返回的结果，包含整个文件的ETag等信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 分块上传
            response = client.complete_multipart_upload(
                Bucket='bucket',
                Key='multipartfile.txt',
                UploadId='uploadid',
                MultipartUpload={'Part': lst}
            )
        """
        headers = mapped(kwargs)
        params = {'uploadId': UploadId}
        params = format_values(params)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("complete multipart upload, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key, params=params),
            data=dict_to_xml(MultipartUpload),
            timeout=1200,  # 分片上传大文件的时间比较长，设置为20min
            headers=headers,
            params=params)
        body = xml_to_dict(rt.content)
        # 分块上传文件返回200OK并不能代表文件上传成功,返回的body里面如果没有ETag则认为上传失败
        if 'ETag' not in body:
            logger.error(rt.content)
            raise CosServiceError('POST', rt.content, 200)
        data = dict(**rt.headers)
        data.update(body)
        return data

    def abort_multipart_upload(self, Bucket, Key, UploadId, **kwargs):
        """放弃一个已经存在的分片上传任务，删除所有已经存在的分片.

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param UploadId(string): 分块上传创建的UploadId.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 分块上传
            response = client.abort_multipart_upload(
                Bucket='bucket',
                Key='multipartfile.txt',
                UploadId='uploadid'
            )
        """
        headers = mapped(kwargs)
        params = {'uploadId': UploadId}
        params = format_values(params)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("abort multipart upload, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key, params=params),
            headers=headers,
            params=params)
        return None

    def list_parts(self, Bucket, Key, UploadId, EncodingType='', MaxParts=1000, PartNumberMarker=0, **kwargs):
        """列出已上传的分片.

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param UploadId(string): 分块上传创建的UploadId.
        :param EncodingType(string): 设置返回结果编码方式,只能设置为url.
        :param MaxParts(int): 设置单次返回最大的分块数量,最大为1000.
        :param PartNumberMarker(int): 设置返回的开始处,从PartNumberMarker下一个分块开始列出.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 分块的相关信息，包括Etag和PartNumber等信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 列出分块
            response = client.list_parts(
                Bucket='bucket',
                Key='multipartfile.txt',
                UploadId='uploadid'
            )
        """
        headers = mapped(kwargs)
        decodeflag = True
        params = {
            'uploadId': UploadId,
            'part-number-marker': PartNumberMarker,
            'max-parts': MaxParts}
        if EncodingType:
            if EncodingType != 'url':
                raise CosClientError('EncodingType must be url')
            params['encoding-type'] = EncodingType
            decodeflag = False
        else:
            params['encoding-type'] = 'url'
        params = format_values(params)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("list multipart upload parts, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        format_dict(data, ['Part'])
        if decodeflag:
            decode_result(data, ['Key'], [])
        return data

    def put_object_acl(self, Bucket, Key, AccessControlPolicy={}, **kwargs):
        """设置object ACL

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param AccessControlPolicy(dict): 设置object ACL规则.
        :param kwargs(dict): 通过headers来设置ACL.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置 object ACL
            response = client.put_object_acl(
                Bucket='bucket',
                Key='multipartfile.txt',
                ACL='public-read',
                GrantRead='id="qcs::cam::uin/123:uin/456",id="qcs::cam::uin/123:uin/123"'
            )
        """
        xml_config = ""
        if AccessControlPolicy:
            xml_config = format_xml(data=AccessControlPolicy, root='AccessControlPolicy')
        headers = mapped(kwargs)
        params = {'acl': ''}
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("put object acl, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, Key, params=params),
            headers=headers,
            params=params)
        return None

    def get_object_acl(self, Bucket, Key, **kwargs):
        """获取object ACL

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Object对应的ACL信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取object ACL
            response = client.get_object_acl(
                Bucket='bucket',
                Key='multipartfile.txt'
            )
        """
        headers = mapped(kwargs)
        params = {'acl': ''}
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("get object acl, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content, "type", "Type")
        if data['AccessControlList'] is not None and isinstance(data['AccessControlList']['Grant'], dict):
            lst = []
            lst.append(data['AccessControlList']['Grant'])
            data['AccessControlList']['Grant'] = lst
        data['CannedACL'] = parse_object_canned_acl(data, rt.headers)
        return data

    def restore_object(self, Bucket, Key, RestoreRequest={}, **kwargs):
        """取回沉降到CAS中的object到COS

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param RestoreRequest(dict): 取回object的属性设置
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        params = {'restore': ''}
        headers = mapped(kwargs)
        if 'versionId' in headers:
            params['versionId'] = headers['versionId']
            headers.pop('versionId')
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("restore_object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        xml_config = format_xml(data=RestoreRequest, root='RestoreRequest')
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, Key, params=params),
            headers=headers,
            params=params)
        return None

    def select_object_content(self, Bucket, Key, Expression, ExpressionType, InputSerialization, OutputSerialization,
                              RequestProgress=None, **kwargs):
        """从指定文对象中检索内容

        :param Bucket(string): 存储桶名称.
        :param Key(string): 检索的路径.
        :param Expression(string): 查询语句
        :param ExpressionType(string): 查询语句的类型
        :param RequestProgress(dict): 查询进度设置
        :param InputSerialization(dict): 输入格式设置
        :param OutputSerialization(dict): 输出格式设置
        :param kwargs(dict): 设置请求headers.
        :return(dict): 检索内容.
        """
        params = {'select': '', 'select-type': 2}
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("select object content, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        SelectRequest = {
            'Expression': Expression,
            'ExpressionType': ExpressionType,
            'InputSerialization': InputSerialization,
            'OutputSerialization': OutputSerialization
        }
        if RequestProgress is not None:
            SelectRequest['RequestProgress'] = RequestProgress
        xml_config = format_xml(data=SelectRequest, root='SelectRequest')
        rt = self.send_request(
            method='POST',
            url=url,
            stream=True,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, Key, params=params),
            headers=headers,
            params=params)
        data = {'Payload': EventStream(rt)}
        return data

    # s3 bucket interface begin
    def create_bucket(self, Bucket, BucketAZConfig=None, BucketArchConfig=None, **kwargs):
        """创建一个bucket

        :param Bucket(string): 存储桶名称. 存储桶名称不支持大写字母，COS 后端会将用户传入的大写字母自动转换为小写字母用于创建存储桶.
        :param BucketAZConfig(string): 存储桶的多AZ配置
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建单AZ bucket
            response = client.create_bucket(
                Bucket='bucket'
            )
            # 创建多AZ bucket
            response = client.create_bucket(
                Bucket='bucket',
                BucketAZConfig='MAZ'
            )
        """
        headers = mapped(kwargs)
        xml_config = None
        bucket_config = dict()
        if BucketAZConfig == 'MAZ':
            bucket_config.update({'BucketAZConfig': 'MAZ'})
        if BucketArchConfig == 'OFS':
            bucket_config.update({'BucketArchConfig': 'OFS'})
        if len(bucket_config) != 0:
            xml_config = format_xml(data=bucket_config, root='CreateBucketConfiguration')
            headers['Content-MD5'] = get_md5(xml_config)
            headers['Content-Type'] = 'application/xml'

        url = self._conf.uri(bucket=Bucket)
        logger.info("create bucket, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf),
            headers=headers)
        return None

    def delete_bucket(self, Bucket, **kwargs):
        """删除一个bucket，bucket必须为空

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除bucket
            response = client.delete_bucket(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf),
            headers=headers)
        return None

    def list_objects(self, Bucket, Prefix="", Delimiter="", Marker="", MaxKeys=1000, EncodingType="", **kwargs):
        """获取文件列表

        :param Bucket(string): 存储桶名称.
        :param Prefix(string): 设置匹配文件的前缀.
        :param Delimiter(string): 分隔符.
        :param Marker(string): 从marker开始列出条目.
        :param MaxKeys(int): 设置单次返回最大的数量,最大为1000.
        :param EncodingType(string): 设置返回结果编码方式,只能设置为url.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 文件的相关信息，包括Etag等信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 列出bucket
            response = client.list_objects(
                Bucket='bucket',
                MaxKeys=100,
                Prefix='中文',
                Delimiter='/'
            )
        """
        decodeflag = True  # 是否需要对结果进行decode
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket)
        logger.info("list objects, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        params = {
            'prefix': Prefix,
            'delimiter': Delimiter,
            'marker': Marker,
            'max-keys': MaxKeys
        }
        if EncodingType:
            if EncodingType != 'url':
                raise CosClientError('EncodingType must be url')
            decodeflag = False  # 用户自己设置了EncodingType不需要去decode
            params['encoding-type'] = EncodingType
        else:
            params['encoding-type'] = 'url'
        params = format_values(params)
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            params=params,
            headers=headers,
            auth=CosS3Auth(self._conf, params=params))
        data = xml_to_dict(rt.content)
        format_dict(data, ['Contents', 'CommonPrefixes'])
        if decodeflag:
            decode_result(
                data,
                [
                    'Prefix',
                    'Marker',
                    'NextMarker'
                ],
                [
                    ['Contents', 'Key'],
                    ['CommonPrefixes', 'Prefix']
                ]
            )
        return data

    def list_objects_versions(self, Bucket, Prefix="", Delimiter="", KeyMarker="", VersionIdMarker="", MaxKeys=1000,
                              EncodingType="", **kwargs):
        """获取文件列表

        :param Bucket(string): 存储桶名称.
        :param Prefix(string): 设置匹配文件的前缀.
        :param Delimiter(string): 分隔符.
        :param KeyMarker(string): 从KeyMarker指定的Key开始列出条目.
        :param VersionIdMarker(string): 从VersionIdMarker指定的版本开始列出条目.
        :param MaxKeys(int): 设置单次返回最大的数量,最大为1000.
        :param EncodingType(string): 设置返回结果编码方式,只能设置为url.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 文件的相关信息，包括Etag等信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 列出bucket带版本
            response = client.list_objects_versions(
                Bucket='bucket',
                MaxKeys=100,
                Prefix='中文',
                Delimiter='/'
            )
        """
        headers = mapped(kwargs)
        decodeflag = True
        url = self._conf.uri(bucket=Bucket)
        logger.info("list objects versions, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        params = {
            'versions': '',
            'prefix': Prefix,
            'delimiter': Delimiter,
            'key-marker': KeyMarker,
            'version-id-marker': VersionIdMarker,
            'max-keys': MaxKeys
        }
        if EncodingType:
            if EncodingType != 'url':
                raise CosClientError('EncodingType must be url')
            decodeflag = False
            params['encoding-type'] = EncodingType
        else:
            params['encoding-type'] = 'url'
        params = format_values(params)
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            params=params,
            headers=headers,
            auth=CosS3Auth(self._conf, params=params))
        data = xml_to_dict(rt.content)
        format_dict(data, ['Version', 'DeleteMarker', 'CommonPrefixes'])
        if decodeflag:
            decode_result(
                data,
                [
                    'Prefix',
                    'KeyMarker',
                    'NextKeyMarker',
                    'VersionIdMarker',
                    'NextVersionIdMarker'
                ],
                [
                    ['Version', 'Key'],
                    ['CommonPrefixes', 'Prefix'],
                    ['DeleteMarker', 'Key']
                ]
            )
        return data

    def list_multipart_uploads(self, Bucket, Prefix="", Delimiter="", KeyMarker="", UploadIdMarker="", MaxUploads=1000,
                               EncodingType="", **kwargs):
        """获取Bucket中正在进行的分块上传

        :param Bucket(string): 存储桶名称.
        :param Prefix(string): 设置匹配文件的前缀.
        :param Delimiter(string): 分隔符.
        :param KeyMarker(string): 从KeyMarker指定的Key开始列出条目.
        :param UploadIdMarker(string): 从UploadIdMarker指定的UploadID开始列出条目.
        :param MaxUploads(int): 设置单次返回最大的数量,最大为1000.
        :param EncodingType(string): 设置返回结果编码方式,只能设置为url.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 文件的相关信息，包括Etag等信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 列出所有分块上传
            response = client.list_multipart_uploads(
                Bucket='bucket',
                MaxUploads=100,
                Prefix='中文',
                Delimiter='/'
            )
        """
        headers = mapped(kwargs)
        decodeflag = True
        url = self._conf.uri(bucket=Bucket)
        logger.info("get multipart uploads, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        params = {
            'uploads': '',
            'prefix': Prefix,
            'delimiter': Delimiter,
            'key-marker': KeyMarker,
            'upload-id-marker': UploadIdMarker,
            'max-uploads': MaxUploads
        }
        if EncodingType:
            if EncodingType != 'url':
                raise CosClientError('EncodingType must be url')
            decodeflag = False
            params['encoding-type'] = EncodingType
        else:
            params['encoding-type'] = 'url'
        params = format_values(params)
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            params=params,
            headers=headers,
            auth=CosS3Auth(self._conf, params=params))

        data = xml_to_dict(rt.content)
        format_dict(data, ['Upload', 'CommonPrefixes'])
        if decodeflag:
            decode_result(
                data,
                [
                    'Prefix',
                    'KeyMarker',
                    'NextKeyMarker',
                    'UploadIdMarker',
                    'NextUploadIdMarker'
                ],
                [
                    ['Upload', 'Key'],
                    ['CommonPrefixes', 'Prefix']
                ]
            )
        return data

    def head_bucket(self, Bucket, **kwargs):
        """确认bucket是否存在

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return: HEAD Bucket响应头域.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 确认bucket是否存在
            response = client.head_bucket(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket)
        logger.info("head bucket, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='HEAD',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf),
            headers=headers)

        response = dict(**rt.headers)
        return response

    def put_bucket_acl(self, Bucket, AccessControlPolicy={}, **kwargs):
        """设置bucket ACL

        :param Bucket(string): 存储桶名称.
        :param AccessControlPolicy(dict): 设置bucket ACL规则.
        :param kwargs(dict): 通过headers来设置ACL.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置 object ACL
            response = client.put_bucket_acl(
                Bucket='bucket',
                ACL='private',
                GrantRead='id="qcs::cam::uin/123:uin/456",id="qcs::cam::uin/123:uin/123"'
            )
        """
        xml_config = ""
        if AccessControlPolicy:
            xml_config = format_xml(data=AccessControlPolicy, root='AccessControlPolicy')
        headers = mapped(kwargs)
        params = {'acl': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket acl, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_acl(self, Bucket, **kwargs):
        """获取bucket ACL

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置headers.
        :return(dict): Bucket对应的ACL信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置 object ACL
            response = client.get_bucket_acl(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'acl': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket acl, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content, "type", "Type")
        if data['AccessControlList'] is not None and not isinstance(data['AccessControlList']['Grant'], list):
            lst = []
            lst.append(data['AccessControlList']['Grant'])
            data['AccessControlList']['Grant'] = lst
        data['CannedACL'] = parse_bucket_canned_acl(data)
        return data

    def put_bucket_cors(self, Bucket, CORSConfiguration={}, **kwargs):
        """设置bucket CORS

        :param Bucket(string): 存储桶名称.
        :param CORSConfiguration(dict): 设置Bucket跨域规则.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket跨域配置
            cors_config = {
                'CORSRule': [
                    {
                        'ID': '1234',
                        'AllowedOrigin': ['http://www.qq.com'],
                        'AllowedMethod': ['GET', 'PUT'],
                        'AllowedHeader': ['x-cos-meta-test'],
                        'ExposeHeader': ['x-cos-meta-test1'],
                        'MaxAgeSeconds': 500
                    }
                ]
            }
            response = client.put_bucket_cors(
                Bucket='bucket',
                CORSConfiguration=cors_config
            )
        """
        xml_config = format_xml(data=CORSConfiguration, root='CORSConfiguration')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'cors': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket cors, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_cors(self, Bucket, **kwargs):
        """获取bucket CORS

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 获取Bucket对应的跨域配置.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket跨域配置
            response = client.get_bucket_cors(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'cors': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket cors, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        if 'CORSRule' in data and not isinstance(data['CORSRule'], list):
            lst = []
            lst.append(data['CORSRule'])
            data['CORSRule'] = lst
        if 'CORSRule' in data:
            allow_lst = ['AllowedOrigin', 'AllowedMethod', 'AllowedHeader', 'ExposeHeader']
            for rule in data['CORSRule']:
                for text in allow_lst:
                    if text in rule and not isinstance(rule[text], list):
                        lst = []
                        lst.append(rule[text])
                        rule[text] = lst
        return data

    def delete_bucket_cors(self, Bucket, **kwargs):
        """删除bucket CORS

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除bucket跨域配置
            response = client.delete_bucket_cors(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'cors': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket cors, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def put_bucket_lifecycle(self, Bucket, LifecycleConfiguration={}, **kwargs):
        """设置bucket LifeCycle

        :param Bucket(string): 存储桶名称.
        :param LifecycleConfiguration(dict): 设置Bucket的生命周期规则.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket生命周期配置
            lifecycle_config = {
                'Rule': [
                    {
                        'Expiration': {'Date': get_date(2018, 4, 24)},
                        'ID': '123',
                        'Filter': {'Prefix': ''},
                        'Status': 'Enabled',
                    }
                ]
            }
            response = client.put_bucket_lifecycle(
                Bucket='bucket',
                LifecycleConfiguration=lifecycle_config
            )
        """
        # 类型为list的标签
        xml_config = format_xml(data=LifecycleConfiguration, root='LifecycleConfiguration')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'lifecycle': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket lifecycle, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_lifecycle(self, Bucket, **kwargs):
        """获取bucket LifeCycle

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket对应的生命周期配置.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket生命周期配置
            response = client.get_bucket_lifecycle(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'lifecycle': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket lifecycle, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        format_dict(data, ['Rule'])
        if 'Rule' in data:
            for rule in data['Rule']:
                format_dict(rule, ['Transition', 'NoncurrentVersionTransition'])
                if 'Filter' in rule:
                    format_dict(rule['Filter'], ['Tag'])
        return data

    def delete_bucket_lifecycle(self, Bucket, **kwargs):
        """删除bucket LifeCycle

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除bucket生命周期配置
            response = client.delete_bucket_lifecycle(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'lifecycle': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket lifecycle, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def put_bucket_versioning(self, Bucket, Status, **kwargs):
        """设置bucket版本控制

        :param Bucket(string): 存储桶名称.
        :param Status(string): 设置Bucket版本控制的状态，可选值为'Enabled'|'Suspended'.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 打开多版本配置
            response = client.put_bucket_versioning(
                Bucket='bucket',
                Status='Enabled'
            )
        """
        headers = mapped(kwargs)
        params = {'versioning': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket versioning, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        if Status != 'Enabled' and Status != 'Suspended':
            raise CosClientError('versioning status must be set to Enabled or Suspended!')
        config = dict()
        config['Status'] = Status
        xml_config = format_xml(data=config, root='VersioningConfiguration')
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_versioning(self, Bucket, **kwargs):
        """查询bucket版本控制

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 获取Bucket版本控制的配置.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取多版本配置
            response = client.get_bucket_versioning(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'versioning': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket versioning, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        return data

    def get_bucket_location(self, Bucket, **kwargs):
        """查询bucket所属地域

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 存储桶的地域信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket所在地域信息
            response = client.get_bucket_location(
                Bucket='bucket'
            )
            print (response['LocationConstraint'])
        """
        headers = mapped(kwargs)
        params = {'location': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket location, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        root = xml.etree.ElementTree.fromstring(rt.content)
        data = dict()
        data['LocationConstraint'] = root.text
        return data

    def put_bucket_replication(self, Bucket, ReplicationConfiguration={}, **kwargs):
        """设置bucket跨区域复制配置

        :param Bucket(string): 存储桶名称.
        :param ReplicationConfiguration(dict): 设置Bucket的跨区域复制规则.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket跨区域复制配置
            replication_config = {
                'Role': 'qcs::cam::uin/735905558:uin/735905558',
                'Rule': [
                    {
                        'ID': '123',
                        'Status': 'Enabled',
                        'Prefix': 'replication',
                        'Destination': {
                            'Bucket': 'qcs:id/0:cos:cn-south:appid/1252448703:replicationsouth'
                        }
                    }
                ]
            }
            response = client.put_bucket_replication(
                Bucket='bucket',
                ReplicationConfiguration=replication_config
            )
        """
        xml_config = format_xml(data=ReplicationConfiguration, root='ReplicationConfiguration')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'replication': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket replication, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_replication(self, Bucket, **kwargs):
        """获取bucket 跨区域复制配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket对应的跨区域复制配置.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket跨区域复制配置
            response = client.get_bucket_replication(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'replication': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket replication, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        format_dict(data, ['Rule'])
        return data

    def delete_bucket_replication(self, Bucket, **kwargs):
        """删除bucket 跨区域复制配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除bucket跨区域复制配置
            response = client.delete_bucket_replication(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'replication': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket replication, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def put_bucket_website(self, Bucket, WebsiteConfiguration={}, **kwargs):
        """设置bucket静态网站配置

        :param Bucket(string): 存储桶名称.
        :param ReplicationConfiguration(dict): 设置Bucket的静态网站规则.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket跨区域复制配置
            website_config = {
                'IndexDocument': {
                    'Suffix': 'string'
                },
                'ErrorDocument': {
                    'Key': 'string'
                },
                'RedirectAllRequestsTo': {
                    'HostName': 'string',
                    'Protocol': 'http'|'https'
                },
                'RoutingRules': [
                    {
                        'Condition': {
                            'HttpErrorCodeReturnedEquals': 'string',
                            'KeyPrefixEquals': 'string'
                        },
                        'Redirect': {
                            'HostName': 'string',
                            'HttpRedirectCode': 'string',
                            'Protocol': 'http'|'https',
                            'ReplaceKeyPrefixWith': 'string',
                            'ReplaceKeyWith': 'string'
                        }
                    }
                ]
            }
            response = client.put_bucket_website(
                Bucket='bucket',
                WebsiteConfiguration=website_config
            )
        """
        # 重构 WebsiteConfiguration['RoutingRules']
        WebsiteConfigurationCpy = copy.deepcopy(WebsiteConfiguration)
        if 'RoutingRules' in WebsiteConfigurationCpy.keys():
            WebsiteConfigurationCpy['RoutingRules'] = {'RoutingRule': WebsiteConfigurationCpy['RoutingRules']}

        xml_config = format_xml(data=WebsiteConfigurationCpy, root='WebsiteConfiguration')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'website': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket website, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_website(self, Bucket, **kwargs):
        """获取bucket 静态网站配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket对应的静态网站配置.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket静态网站配置
            response = client.get_bucket_website(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'website': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket website, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        if 'RoutingRules' in data and not isinstance(data['RoutingRules']['RoutingRule'], list):
            lst = []
            lst.append(data['RoutingRules']['RoutingRule'])
            data['RoutingRules']['RoutingRule'] = lst
        if 'RoutingRules' in data:
            data['RoutingRules'] = data['RoutingRules']['RoutingRule']
        return data

    def delete_bucket_website(self, Bucket, **kwargs):
        """删除bucket 静态网站配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除bucket静态网站配置
            response = client.delete_bucket_website(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'website': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket website, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def put_bucket_logging(self, Bucket, BucketLoggingStatus={}, **kwargs):
        """设置bucket logging

        :param Bucket(string): 存储桶名称.
        :param BucketLoggingStatus(dict): 设置Bucket的日志配置.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket logging服务
            logging_bucket = 'logging-beijing-1250000000'
            logging_config = {
                'LoggingEnabled': {
                    'TargetBucket': logging_bucket,
                    'TargetPrefix': 'test'
                }
            }
            response = logging_client.put_bucket_logging(
                Bucket=logging_bucket,
                BucketLoggingStatus=logging_config
            )
        """
        xml_config = format_xml(data=BucketLoggingStatus, root='BucketLoggingStatus')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'logging': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket logging, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        logging_rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_logging(self, Bucket, **kwargs):
        """获取bucket logging

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket对应的logging配置.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket logging服务配置
            response = logging_client.get_bucket_logging(
                Bucket=logging_bucket
            )
        """
        headers = mapped(kwargs)
        params = {'logging': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket logging, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        return data

    def put_bucket_policy(self, Bucket, Policy, **kwargs):
        """设置bucket policy

        :param Bucket(string): 存储桶名称.
        :param Policy(dict): 设置Bucket的Policy配置.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket policy服务
            bucket = 'test-1252448703'
            response = client.put_bucket_policy(
                Bucket=bucket,
                Policy=policy
            )
        """
        # Policy必须是一个json字符串(str)或者json对象(dict)
        body = Policy
        policy_type = type(body)
        if policy_type != str and policy_type != dict:
            raise CosClientError("Policy must be a json format string or json format dict")
        if policy_type == dict:
            body = json.dumps(body)

        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/json'
        params = {'policy': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket policy, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=body,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_policy(self, Bucket, **kwargs):
        """获取bucket policy

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket对应的policy配置.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket policy服务配置
            response = client.get_bucket_policy(
                Bucket=bucket
            )
        """
        headers = mapped(kwargs)
        params = {'policy': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket policy, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = {'Policy': json.dumps(rt.json())}
        return data

    def delete_bucket_policy(self, Bucket, **kwargs):
        """删除bucket policy

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除bucket policy服务配置
            response = client.delete_bucket_policy(
                Bucket=bucket
            )
        """
        headers = mapped(kwargs)
        params = {'policy': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket policy, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def put_bucket_domain(self, Bucket, DomainConfiguration={}, **kwargs):
        """设置bucket的自定义域名

        :param Bucket(string): 存储桶名称.
        :param DomainConfiguration(dict): 设置Bucket的自定义域名规则.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket自定义域名配置
            domain_config = {
                'DomainRule': [
                    {
                        'Name': 'www.abc.com',
                        'Type': 'REST',
                        'Status': 'ENABLED',
                        'ForcedReplacement': 'CNAME'
                    },
                ]
            }
            response = client.put_bucket_domain(
                Bucket='bucket',
                DomainConfiguration=domain_config
            )
        """
        xml_config = format_xml(data=DomainConfiguration, root='DomainConfiguration')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'domain': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket domain, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_domain(self, Bucket, **kwargs):
        """获取bucket 自定义域名配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket对应的自定义域名配置.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket自定义域名配置
            response = client.get_bucket_domain(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'domain': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket domain, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        format_dict(data, ['DomainRule'])
        if 'x-cos-domain-txt-verification' in rt.headers:
            data['x-cos-domain-txt-verification'] = rt.headers['x-cos-domain-txt-verification']
        return data

    def delete_bucket_domain(self, Bucket, **kwargs):
        """删除bucket 自定义域名配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除ucket自定义域名配置
            response = client.delete_bucket_domain(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'domain': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket domain, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def put_bucket_domain_certificate(self, Bucket, DomainCertificateConfiguration, **kwargs):
        """设置bucket的自定义域名证书配置规则

        :param Bucket(string): 存储桶名称.
        :param DomainCertificateConfiguration(dict): 设置Bucket的自定义域名证书配置规则.
        :param kwargs(dict): 设置请求headers.
        :return: None

        .. code-block:: python
            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket自定义域名证书配置规则
            domain_cert_config = {}
            response = client.put_bucket_domain_certificate(
                Bucket='bucket',
                DomainCertificateConfiguration=domain_cert_config
            )
        """
        xml_config = format_xml(data=DomainCertificateConfiguration, root='DomainCertificate')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'domaincertificate': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket domain certificate, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_domain_certificate(self, Bucket, DomainName, **kwargs):
        """获取bucket的自定义域名证书配置规则

        :param Bucket(string): 存储桶名称.
        :param DomainName(string): Bucket的自定义域名.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket的自定义域名证书配置规则.

        .. code-block:: python
            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket自定义域名证书配置规则
            response = client.get_bucket_domain_certificate(
                Bucket='bucket',
                DomainName='domain-name'
            )
        """
        headers = mapped(kwargs)
        params = {'domaincertificate': '', 'domainname': DomainName}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket domain certificate, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        return data

    def delete_bucket_domain_certificate(self, Bucket, DomainName, **kwargs):
        """删除bucket的自定义域名证书配置规则

        :param Bucket(string): 存储桶名称.
        :param DomainName(string): Bucket的自定义域名.
        :param kwargs(dict): 设置请求headers.
        :return: None

        .. code-block:: python
            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除bucket自定义域名证书配置规则
            response = client.delete_bucket_domain_certificate(
                Bucket='bucket',
                DomainName='domain-name'
            )
        """
        headers = mapped(kwargs)
        params = {'domaincertificate': '', 'domainname': DomainName}
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket domain certificate, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def put_bucket_origin(self, Bucket, OriginConfiguration={}, **kwargs):
        """设置bucket的回源规则

        :param Bucket(string): 存储桶名称.
        :param OriginConfiguration(dict): 设置Bucket的回源规则.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket回源规则
            origin_config = {}
            response = client.put_bucket_origin(
                Bucket='bucket',
                OriginConfiguration=origin_config
            )
        """
        xml_config = format_xml(data=OriginConfiguration, root='OriginConfiguration')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'origin': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket origin, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_origin(self, Bucket, **kwargs):
        """获取bucket 回源配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket对应的回源规则.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket回源规则
            response = client.get_bucket_origin(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'origin': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket origin, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        format_dict(data, ['OriginRule'])
        return data

    def delete_bucket_origin(self, Bucket, **kwargs):
        """删除bucket 回源配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除bucket回源规则
            response = client.delete_bucket_origin(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'origin': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket origin, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def put_bucket_inventory(self, Bucket, Id, InventoryConfiguration={}, **kwargs):
        """设置bucket的清单规则

        :param Bucket(string): 存储桶名称.
        :param Id(string): 清单规则名称.
        :param InventoryConfiguration(dict): Bucket的清单规则.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket清单规则
            inventory_config = {
                'Destination': {
                    'COSBucketDestination': {
                        'AccountId': '100000000001',
                        'Bucket': 'qcs::cos:ap-guangzhou::examplebucket-1250000000',
                        'Format': 'CSV',
                        'Prefix': 'list1',
                        'Encryption': {
                            'SSECOS': {}
                        }
                    },
                'IsEnabled': 'True',
                'Filter': {
                    'Prefix': 'filterPrefix'
                },
                'IncludedObjectVersions':'All',
                'OptionalFields': {
                    'Field': [
                        'Size',
                        'LastModifiedDate',
                        'ETag',
                        'StorageClass',
                        'IsMultipartUploaded',
                        'ReplicationStatus'
                    ]
                },
                'Schedule': {
                    'Frequency': 'Daily'
                }
            }
            response = client.put_bucket_inventory(
                Bucket='bucket',
                Id='list1',
                InventoryConfiguration=inventory_config
            )
        """
        InventoryConfiguration['Id'] = Id
        xml_config = format_xml(data=InventoryConfiguration, root='InventoryConfiguration')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'inventory': '', 'id': Id}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket inventory, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_inventory(self, Bucket, Id, **kwargs):
        """获取bucket清单规则

        :param Bucket(string): 存储桶名称.
        :param Id(string): 清单规则名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket对应的清单规则.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket清单规则
            response = client.get_bucket_inventory(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'inventory': '', 'id': Id}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket inventory, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        format_dict(data['OptionalFields'], ['Field'])
        return data

    def delete_bucket_inventory(self, Bucket, Id, **kwargs):
        """删除bucket清单规则

        :param Bucket(string): 存储桶名称.
        :param Id(string): 清单规则名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除bucket清单规则
            response = client.delete_bucket_origin(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'inventory': '', 'id': Id}
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket inventory, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def list_bucket_inventory_configurations(self, Bucket, ContinuationToken=None, **kwargs):
        """列举存储桶清单规则

        :param Bucket(string): 存储桶名称
        :param ContinuationToken(string): 分页参数, 用以获取下一页信息
        :param kwargs(dict): 设置请求headers.
        :return(dict): 存储桶清单规则列表

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 分页列举bucket清单规则
            continuation_token = ''
            while True:
                resp = client.list_bucket_inventory_configurations(
                    Bucket=bucket,
                    ContinuationToken=continuation_token,
                )
                if 'InventoryConfiguration' in resp:
                    for conf in resp['InventoryConfiguration']:
                        print(conf)
                if resp['IsTruncated'] == 'true':
                    continuation_token = resp['NextContinuationToken']
                else:
                    break
        """
        headers = mapped(kwargs)
        params = {'inventory': ''}
        if ContinuationToken is not None:
            params['continuation-token'] = ContinuationToken
        url = self._conf.uri(bucket=Bucket)
        logger.info("list bucket inventory configurations, url={url}, headers={headers}".format(
            url=url,
            headers=headers,
        ))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        return data

    def post_bucket_inventory(self, Bucket, Id, InventoryConfiguration={}, **kwargs):
        """设置bucket的清单规则(一次性清单/即时清单)

        :param Bucket(string): 存储桶名称.
        :param Id(string): 清单规则名称.
        :param InventoryConfiguration(dict): Bucket的清单规则.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket清单规则
            inventory_config = {
                'Destination': {
                    'COSBucketDestination': {
                        'AccountId': '100000000001',
                        'Bucket': 'qcs::cos:ap-guangzhou::examplebucket-1250000000',
                        'Format': 'CSV',
                        'Prefix': 'list1',
                        'Encryption': {
                            'SSECOS': {}
                        }
                    },
                'Filter': {
                    'Prefix': 'filterPrefix'
                },
                'IncludedObjectVersions':'All',
                'OptionalFields': {
                    'Field': [
                        'Size',
                        'LastModifiedDate',
                        'ETag',
                        'StorageClass',
                        'IsMultipartUploaded',
                        'ReplicationStatus'
                    ]
                },
            }
            response = client.put_bucket_inventory(
                Bucket='bucket',
                Id='list1',
                InventoryConfiguration=inventory_config
            )
        """
        InventoryConfiguration['Id'] = Id
        xml_config = format_xml(data=InventoryConfiguration, root='InventoryConfiguration')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'inventory': '', 'id': Id}
        url = self._conf.uri(bucket=Bucket)
        logger.info("post bucket inventory, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def put_object_tagging(self, Bucket, Key, Tagging={}, **kwargs):
        """设置object的标签

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Tagging(dict): Object的标签集合
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket标签
            tagging_set = {
                'TagSet': {
                    'Tag': [
                        {
                            'Key': 'string',
                            'Value': 'string'
                        }
                    ]
                }
            }
            response = client.put_object_tagging(
                Bucket='bucket',
                Key='test.txt',
                Tagging=tagging_set
            )
        """
        xml_config = format_xml(data=Tagging, root='Tagging')
        headers = mapped(kwargs)
        params = {'tagging': ''}
        if 'versionId' in headers:
            params['versionId'] = headers['versionId']
            del headers['versionId']
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("put object tagging, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, Key, params=params),
            headers=headers,
            params=params)
        return None

    def get_object_tagging(self, Bucket, Key, **kwargs):
        """获取object标签

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket对应的标签.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket标签
            response = client.get_object_tagging(
                Bucket='bucket',
                Key='test.txt'
            )
        """
        headers = mapped(kwargs)
        params = {'tagging': ''}
        if 'versionId' in headers:
            params['versionId'] = headers['versionId']
            del headers['versionId']
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("get object tagging, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        if 'TagSet' in data:
            format_dict(data['TagSet'], ['Tag'])
        return data

    def delete_object_tagging(self, Bucket, Key, **kwargs):
        """删除object标签

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置请求headers.
        :return(dict): None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除bucket标签
            response = client.delete_object_tagging(
                Bucket='bucket',
                Key='test.txt'
            )
        """
        headers = mapped(kwargs)
        params = {'tagging': ''}
        if 'versionId' in headers:
            params['versionId'] = headers['versionId']
            del headers['versionId']
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("delete object tagging, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key, params=params),
            headers=headers,
            params=params)
        return None

    def put_bucket_tagging(self, Bucket, Tagging={}, **kwargs):
        """设置bucket的标签

        :param Bucket(string): 存储桶名称.
        :param Tagging(dict): Bucket的标签集合
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket标签
            tagging_set = {
                'TagSet': {
                    'Tag': [
                        {
                            'Key': 'string',
                            'Value': 'string'
                        }
                    ]
                }
            }
            response = client.put_bucket_tagging(
                Bucket='bucket',
                Tagging=tagging_set
            )
        """
        xml_config = format_xml(data=Tagging, root='Tagging')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'tagging': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket tagging, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_tagging(self, Bucket, **kwargs):
        """获取bucket标签

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket对应的标签.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket标签
            response = client.get_bucket_tagging(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'tagging': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket tagging, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        if 'TagSet' in data:
            format_dict(data['TagSet'], ['Tag'])
        return data

    def delete_bucket_tagging(self, Bucket, **kwargs):
        """删除bucket 回源配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除bucket标签
            response = client.delete_bucket_tagging(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'tagging': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket tagging, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def put_bucket_referer(self, Bucket, RefererConfiguration={}, **kwargs):
        """设置bucket的防盗链规则

        :param Bucket(string): 存储桶名称.
        :param RefererConfiguration(dict): Bucket的防盗链规则
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置bucket标签
            referer_config = {
                'Status': 'Enabled',
                'RefererType': 'White-List',
                'EmptyReferConfiguration': 'Allow',
                'DomainList': {
                    'Domain': [
                        '*.qq.com',
                        '*.qcloud.com'
                    ]
                }
            }
            response = client.put_bucket_referer(
                Bucket='bucket',
                RefererConfiguration=referer_config
            )
        """
        xml_config = format_xml(data=RefererConfiguration, root='RefererConfiguration')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'referer': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket referer, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_referer(self, Bucket, **kwargs):
        """获取bucket防盗链规则

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket对应的防盗链规则.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket标签
            response = client.get_bucket_referer(
                Bucket='bucket'
            )
        """
        headers = mapped(kwargs)
        params = {'referer': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket referer, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        if 'DomainList' in data:
            format_dict(data['DomainList'], ['Domain'])
        return data

    def delete_bucket_referer(self, Bucket, **kwargs):
        """删除bucket防盗链规则

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取bucket标签
            response = client.delete_bucket_referer(
                Bucket='bucket'
            )
        """

        xml_config = ''
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'referer': ''}
        url = self._conf.uri(bucket=Bucket)
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def put_bucket_intelligenttiering_v2(self, Bucket, IntelligentTieringConfiguration=None, Id=None, **kwargs):
        """设置存储桶智能分层配置

        :param Bucket(string): 存储桶名称.
        :param IntelligentTieringConfiguration(dict): 智能分层配置
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)

            intelligent_tiering_conf = {
                'Status': 'Enable',
                'Transition': {
                    'Days': '30|60|90',
                    'RequestFrequent': '1'
                }
            }
            client.put_bucket_intelligenttiering(Bucket="bucket", IntelligentTieringConfiguration=intelligent_tiering_conf)
        """

        if IntelligentTieringConfiguration is None:
            IntelligentTieringConfiguration = {}
        xml_config = format_xml(data=IntelligentTieringConfiguration, root='IntelligentTieringConfiguration')
        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/xml'
        params = {'id': Id}
        url = self._conf.uri(bucket=Bucket) + '?intelligent-tiering'
        logger.info("put bucket intelligenttiering, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def put_bucket_intelligenttiering(self, Bucket, IntelligentTieringConfiguration=None, **kwargs):
        """设置存储桶智能分层配置

        :param Bucket(string): 存储桶名称.
        :param IntelligentTieringConfiguration(dict): 智能分层配置
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)

            intelligent_tiering_conf = {
                'Status': 'Enable',
                'Transition': {
                    'Days': '30|60|90',
                    'RequestFrequent': '1'
                }
            }
            client.put_bucket_intelligenttiering(Bucket="bucket", IntelligentTieringConfiguration=intelligent_tiering_conf)
        """

        if IntelligentTieringConfiguration is None:
            IntelligentTieringConfiguration = {}
        xml_config = format_xml(data=IntelligentTieringConfiguration, root='IntelligentTieringConfiguration')
        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/xml'
        params = {'intelligenttiering': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket intelligenttiering, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return None

    def get_bucket_intelligenttiering(self, Bucket, **kwargs):
        """获取存储桶智能分层配置
        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 智能分层配置.

        .. code-block:: python
            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            client.get_bucket_intelligenttiering(Bucket='bucket')
        """

        headers = mapped(kwargs)
        params = {'intelligenttiering': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket intelligenttiering, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        return data

    def get_bucket_intelligenttiering_v2(self, Bucket, Id, **kwargs):
        """获取存储桶智能分层配置

        :param Bucket(string): 存储桶名称.
        :param Id(string) 智能分层规则Id.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 智能分层配置.

        .. code-block:: python
            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            client.get_bucket_intelligenttiering_v2(Bucket='bucket', Id='id')
        """

        headers = mapped(kwargs)
        params = {'id': Id}
        url = self._conf.uri(bucket=Bucket) + '?intelligent-tiering'
        logger.info("get bucket intelligenttiering, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        return data

    def list_bucket_intelligenttiering_configurations(self, Bucket, **kwargs):
        """列举存储桶中的所有智能分层配置
        
        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 所有的智能分层配置.

        .. code-block:: python
            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            client.list_bucket_intelligenttiering_configurations(Bucket='bucket')
        """

        headers = mapped(kwargs)
        params = {}
        url = self._conf.uri(bucket=Bucket) + "?intelligent-tiering"
        logger.info("list bucket intelligenttiering configurations, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        return data
    
    def put_bucket_object_lock(self, Bucket, ObjectLockConfiguration={}, **kwargs):
        """设置存储桶对象锁定配置

        :param Bucket(string): 存储桶名称.
        :param ObjectLockConfiguration(dict): 对象锁定配置.
        :param kwargs(dict): 设置请求headers.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)

            object_lock_conf = {
                'ObjectLockEnabled': 'Enabled',
            }
            client.put_bucket_object_lock(Bucket="bucket", ObjectLockConfiguration=objeck_lock_conf)
        """

        xml_config = format_xml(data=ObjectLockConfiguration, root='ObjectLockConfiguration')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'object-lock': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket object-lock, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        return rt.headers
    
    def get_bucket_object_lock(self, Bucket, **kwargs):
        """获取存储桶对象锁定配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 对象锁定配置.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            client.get_bucket_object_lock(Bucket="bucket")
        """
        headers = mapped(kwargs)
        params = {'object-lock': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket object-lock, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        return data
    
    def get_bucket_meta(self, Bucket, **kwargs):
        """获取存储桶各项配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 存储桶各项配置.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            client.get_bucket_meta(Bucket="bucket")
        """
        data = {
            'BucketUrl': None,
            'OFS': False,
            'MAZ': False,
            'Encryption': None,
            'ACL': None,
            'Website': None,
            'Logging': None,
            'CORS': None,
            'Versioning': None,
            'IntelligentTiering': None,
            'Lifecycle': None,
            'Tagging': None,
            'ObjectLock': None,
            'Replication': None,
        }
        pool = SimpleThreadPool(num_threads=10)

        # HeadBucket
        def _head_bucket_wrapper(Bucket, **kwargs):
            resp = self.head_bucket(Bucket, **kwargs)
            # x-cos-bucket-arch: 'OFS'
            # x-cos-bucket-az-type: 'MAZ'
            # x-cos-bucket-region: 'ap-beijing'
            if 'x-cos-bucket-arch' in resp and resp['x-cos-bucket-arch'] == 'OFS':
                data.update({'OFS': True})
            else:
                data.update({'OFS': False})
            if 'x-cos-bucket-az-type' in resp and resp['x-cos-bucket-az-type'] == 'MAZ':
                data.update({'MAZ': True})
            else:
                data.update({'MAZ': False})
            data.update({"Location": resp['x-cos-bucket-region']})
            url = self._conf.uri(bucket=Bucket).strip('/')
            data.update({'BucketUrl': url})
        pool.add_task(_head_bucket_wrapper, Bucket, **kwargs)

        # Website
        def _get_bucket_website_wrapper(Bucket, **kwargs):
            try:
                resp = self.get_bucket_website(Bucket, **kwargs)
                data.update({'Website': resp})
            except CosServiceError as e:
                logger.debug("get_bucket_meta failed to get website conf:{}".format(e))
        pool.add_task(_get_bucket_website_wrapper, Bucket, **kwargs)

        # ObjectLock
        def _get_bucket_object_lock_wrapper(Bucket, **kwargs):
            try:
                resp = self.get_bucket_object_lock(Bucket, **kwargs)
                data.update({'ObjectLock': resp})
            except CosServiceError as e:
                logger.debug("get_bucket_meta failed to get object_lock conf:{}".format(e))
        pool.add_task(_get_bucket_object_lock_wrapper, Bucket, **kwargs)

        # ACL
        def _get_bucket_acl_wrapper(Bucket, **kwargs):
            try:
                resp = self.get_bucket_acl(Bucket, **kwargs)
                data.update({'ACL': resp})
            except CosServiceError as e:
                logger.debug("get_bucket_meta failed to get acl conf:{}".format(e))
        pool.add_task(_get_bucket_acl_wrapper, Bucket, **kwargs)

        # Logging
        def _get_bucket_logging_wrapper(Bucket, **kwargs):
            try:
                resp = self.get_bucket_logging(Bucket, **kwargs)
                data.update({'Logging': resp})
            except CosServiceError as e:
                logger.debug("get_bucket_meta failed to get logging conf:{}".format(e))
        pool.add_task(_get_bucket_logging_wrapper, Bucket, **kwargs)

        # Lifecycle
        def _get_bucket_lifecycle_wrapper(Bucket, **kwargs):
            try:
                resp = self.get_bucket_lifecycle(Bucket, **kwargs)
                data.update({'Lifecycle': resp})
            except CosServiceError as e:
                logger.debug("get_bucket_meta failed to get lifecycle conf:{}".format(e))
        pool.add_task(_get_bucket_lifecycle_wrapper, Bucket, **kwargs)

        # Replication
        def _get_bucket_replication_wrapper(Bucket, **kwargs):
            try:
                resp = self.get_bucket_replication(Bucket, **kwargs)
                data.update({'Replication': resp})
            except CosServiceError as e:
                logger.debug("get_bucket_meta failed to get replication conf:{}".format(e))
        pool.add_task(_get_bucket_replication_wrapper, Bucket, **kwargs)

        # Encryption
        def _get_bucket_encryption_wrapper(Bucket, **kwargs):
            try:
                resp = self.get_bucket_encryption(Bucket, **kwargs)
                data.update({'Encryption': resp})
            except CosServiceError as e:
                logger.debug("get_bucket_meta failed to get encryption conf:{}".format(e))
        pool.add_task(_get_bucket_encryption_wrapper, Bucket, **kwargs)

        # CORS
        def _get_bucket_cors_wrapper(Bucket, **kwargs):
            try:
                resp = self.get_bucket_cors(Bucket, **kwargs)
                data.update({'CORS': resp})
            except CosServiceError as e:
                logger.debug("get_bucket_meta failed to get cors conf:{}".format(e))
        pool.add_task(_get_bucket_cors_wrapper, Bucket, **kwargs)

        # Versioning
        def _get_bucket_versioning_wrapper(Bucket, **kwargs):
            try:
                resp = self.get_bucket_versioning(Bucket, **kwargs)
                data.update({'Versioning': resp})
            except CosServiceError as e:
                logger.debug("get_bucket_meta failed to get versioning conf:{}".format(e))
        pool.add_task(_get_bucket_versioning_wrapper, Bucket, **kwargs)

        # IntelligentTiering
        def _list_bucket_intelligenttiering_conf_wrapper(Bucket, **kwargs):
            try:
                resp = self.list_bucket_intelligenttiering_configurations(Bucket, **kwargs)
                data.update({'IntelligentTiering': resp})
            except CosServiceError as e:
                logger.debug("get_bucket_meta failed to get intelligenttiering conf:{}".format(e))
        pool.add_task(_list_bucket_intelligenttiering_conf_wrapper, Bucket, **kwargs)

        # Tagging
        def _get_bucket_tagging_wrapper(Bucket, **kwargs):
            try:
                resp = self.get_bucket_tagging(Bucket, **kwargs)
                data.update({'Tagging': resp})
            except CosServiceError as e:
                logger.debug("get_bucket_meta failed to get tagging conf:{}".format(e))
        pool.add_task(_get_bucket_tagging_wrapper, Bucket, **kwargs)

        pool.wait_completion()
        return data

    # service interface begin
    def list_buckets(self, TagKey=None, TagValue=None, Region=None, CreateTime=None, Range=None, Marker="", MaxKeys=2000, **kwargs):
        """列出符合条件的bucket
        :param Bucket(string): 存储桶名称
        :param TagKey(string): 标签键
        :param TagValue(string): 标签值
        :param Region(string): 地域名称
        :param CreateTime(Timestamp): GMT时间戳, 和 Range 参数一起使用, 支持根据创建时间过滤存储桶
        :param Range(string): 和 CreateTime 参数一起使用, 支持根据创建时间过滤存储桶，支持枚举值 lt（创建时间早于 create-time）、gt（创建时间晚于 create-time）、lte（创建时间早于或等于 create-time）、gte（创建时间晚于或等于create-time）
        :param Marker(string): 起始标记, 从该标记之后（不含）按照 UTF-8 字典序返回存储桶条目
        :param MaxKeys(int): 单次返回最大的条目数量，默认值为2000，最大为2000

        :return(dict): 账号下bucket相关信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取账户下所有存储桶信息
            response = client.list_buckets()
        """
        headers = mapped(kwargs)

        if self._conf._enable_old_domain:
            url = '{scheme}://service.cos.myqcloud.com/'.format(scheme=self._conf._scheme)
        else:
            url = '{scheme}://service.cos.tencentcos.cn/'.format(scheme=self._conf._scheme)

        if self._conf._service_domain is not None:
            url = '{scheme}://{domain}/'.format(scheme=self._conf._scheme, domain=self._conf._service_domain)

        params = {
            'marker': Marker,
            'max-keys': MaxKeys,
        }
        if TagKey and TagValue:
            params['tagkey'] = TagKey
            params['tagvalue'] = TagValue
        if Region:
            params['region'] = Region
        if CreateTime and Range:
            params['create-time'] = CreateTime
            params['range'] = Range

        rt = self.send_request(
            method='GET',
            url=url,
            bucket=None,
            headers=headers,
            params=params,
            auth=CosS3Auth(self._conf),
        )
        data = xml_to_dict(rt.content)
        if data['Buckets'] is not None and not isinstance(data['Buckets']['Bucket'], list):
            lst = []
            lst.append(data['Buckets']['Bucket'])
            data['Buckets']['Bucket'] = lst
        return data

    # Advanced interface
    def _upload_part(self, bucket, key, local_path, offset, size, part_num, uploadid, md5_lst, resumable_flag,
                     already_exist_parts, enable_md5, progress_callback=None, **kwargs):
        """从本地文件中读取分块, 上传单个分块,将结果记录在md5——list中

        :param bucket(string): 存储桶名称.
        :param key(string): 分块上传路径名.
        :param local_path(string): 本地文件路径名.
        :param offset(int): 读取本地文件的分块偏移量.
        :param size(int): 读取本地文件的分块大小.
        :param part_num(int): 上传分块的序号.
        :param uploadid(string): 分块上传的uploadid.
        :param md5_lst(list): 保存上传成功分块的MD5和序号.
        :param resumable_flag(bool): 是否为断点续传.
        :param already_exist_parts(dict): 断点续传情况下,保存已经上传的块的序号和Etag.
        :param enable_md5(bool): 是否开启md5校验.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        # 如果是断点续传且该分块已经上传了则不用实际上传
        if resumable_flag and part_num in already_exist_parts:
            md5_lst.append({'PartNumber': part_num, 'ETag': already_exist_parts[part_num]})
        else:
            with open(local_path, 'rb') as fp:
                fp.seek(offset, 0)
                data = fp.read(size)
            rt = self.upload_part(bucket, key, data, part_num, uploadid, enable_md5, **kwargs)
            lower_rt = dict([(k.lower(), v) for k, v in rt.items()])
            md5_lst.append({'PartNumber': part_num, 'ETag': lower_rt['etag']})
        if progress_callback:
            progress_callback.report(size)
        return None

    def _get_resumable_uploadid(self, bucket, key):
        """从服务端获取未完成的分块上传任务,获取断点续传的uploadid

        :param bucket(string): 存储桶名称.
        :param key(string): 分块上传路径名.
        :return(string): 断点续传的uploadid,如果不存在则返回None.
        """
        if key and key[0] == '/':
            key = key[1:]
        multipart_response = self.list_multipart_uploads(
            Bucket=bucket,
            Prefix=key
        )
        if 'Upload' in multipart_response:
            # 取最后一个(最新的)uploadid
            index = len(multipart_response['Upload']) - 1
            while index >= 0:
                if multipart_response['Upload'][index]['Key'] == key:
                    return multipart_response['Upload'][index]['UploadId']
                index -= 1
        return None

    def _check_single_upload_part(self, local_path, offset, local_part_size, remote_part_size, remote_etag):
        """从本地文件中读取分块, 校验本地分块和服务端的分块信息

        :param local_path(string): 本地文件路径名.
        :param offset(int): 读取本地文件的分块偏移量.
        :param local_part_size(int): 读取本地文件的分块大小.
        :param remote_part_size(int): 服务端的文件的分块大小.
        :param remote_etag(string): 服务端的文件Etag.
        :return(bool): 本地单个分块的信息是否和服务端的分块信息一致
        """
        if local_part_size != remote_part_size:
            return False
        with open(local_path, 'rb') as fp:
            fp.seek(offset, 0)
            local_etag = get_raw_md5(fp.read(local_part_size))
            if local_etag == remote_etag:
                return True
        return False

    def _check_all_upload_parts(self, bucket, key, uploadid, local_path, parts_num, part_size, last_size,
                                already_exist_parts):
        """获取所有已经上传的分块的信息,和本地的文件进行对比

        :param bucket(string): 存储桶名称.
        :param key(string): 分块上传路径名.
        :param uploadid(string): 分块上传的uploadid
        :param local_path(string): 本地文件的大小
        :param parts_num(int): 本地文件的分块数
        :param part_size(int): 本地文件的分块大小
        :param last_size(int): 本地文件的最后一块分块大小
        :param already_exist_parts(dict): 保存已经上传的分块的part_num和Etag
        :return(bool): 本地文件是否通过校验,True为可以进行断点续传,False为不能进行断点续传
        """
        parts_info = []
        part_number_marker = 0
        list_over_status = False
        while list_over_status is False:
            response = self.list_parts(
                Bucket=bucket,
                Key=key,
                UploadId=uploadid,
                PartNumberMarker=part_number_marker
            )
            # 已经存在的分块上传,有可能一个分块都没有上传,判断一下
            if 'Part' in response:
                parts_info.extend(response['Part'])
            if response['IsTruncated'] == 'false':
                list_over_status = True
            else:
                part_number_marker = int(response['NextPartNumberMarker'])
        for part in parts_info:
            part_num = int(part['PartNumber'])
            # 如果分块数量大于本地计算出的最大数量,校验失败
            if part_num > parts_num:
                return False
            offset = (part_num - 1) * part_size
            local_part_size = part_size
            if part_num == parts_num:
                local_part_size = last_size
            # 有任何一块没有通过校验，则校验失败
            if not self._check_single_upload_part(local_path, offset, local_part_size, int(part['Size']), part['ETag']):
                return False
            already_exist_parts[part_num] = part['ETag']
        return True

    def download_file(self, Bucket, Key, DestFilePath, PartSize=20, MAXThread=5, EnableCRC=False, progress_callback=None, DumpRecordDir=None, KeySimplifyCheck=True, DisableTempDestFilePath=False, **Kwargs):
        """小于等于20MB的文件简单下载，大于20MB的文件使用续传下载

        :param Bucket(string): 存储桶名称.
        :param key(string): COS文件的路径名.
        :param DestFilePath(string): 下载文件的目的路径.
        :param PartSize(int): 分块下载的大小设置,单位为MB.
        :param MAXThread(int): 并发下载的最大线程数.
        :param EnableCRC(bool): 校验下载文件与源文件是否一致
        :param DumpRecordDir(string): 指定保存断点信息的文件路径
        :param KeySimplifyCheck(bool): 是否对Key进行posix路径语义归并检查
        :param DisableTempDestFilePath(bool): 简单下载写入目标文件时,不使用临时文件
        :param kwargs(dict): 设置请求headers.
        """
        logger.debug("Start to download file, bucket: {0}, key: {1}, dest_filename: {2}, part_size: {3}MB,\
                     max_thread: {4}".format(Bucket, Key, DestFilePath, PartSize, MAXThread))

        head_headers = dict()
        # SSE-C对象在head时也要求传入加密头域
        if 'SSECustomerAlgorithm' in Kwargs:
            head_headers['SSECustomerAlgorithm'] = Kwargs['SSECustomerAlgorithm']
            head_headers['SSECustomerKey'] = Kwargs['SSECustomerKey']
            head_headers['SSECustomerKeyMD5'] = Kwargs['SSECustomerKeyMD5']
        # head时需要携带版本ID
        if 'VersionId' in Kwargs:
            head_headers['VersionId'] = Kwargs['VersionId']
        object_info = self.head_object(Bucket, Key, **head_headers)
        file_size = int(object_info['Content-Length'])
        if file_size <= 1024 * 1024 * PartSize:
            response = self.get_object(Bucket, Key, KeySimplifyCheck, **Kwargs)
            response['Body'].get_stream_to_file(DestFilePath, DisableTempDestFilePath)
            return

        # 支持回调查看进度
        callback = None
        if progress_callback:
            callback = ProgressCallback(file_size, progress_callback)

        downloader = ResumableDownLoader(self, Bucket, Key, DestFilePath, object_info, PartSize, MAXThread, EnableCRC,
                                         callback, DumpRecordDir, KeySimplifyCheck, **Kwargs)
        downloader.start()

    def upload_file(self, Bucket, Key, LocalFilePath, PartSize=1, MAXThread=5, EnableMD5=False, progress_callback=None,
                    **kwargs):

        """
        :param Bucket(string): 存储桶名称.
        :param key(string): 分块上传路径名.
        :param LocalFilePath(string): 本地文件路径名.
        :param PartSize(int): 分块的大小设置,单位为MB.
        :param MAXThread(int): 并发上传的最大线程数.
        :param EnableMD5(bool): 是否打开MD5校验.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 成功上传文件的元信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 根据文件大小自动选择分块大小,多线程并发上传提高上传速度
            file_name = 'thread_1GB_test'
            response = client.upload_file(
                Bucket='bucket',
                Key=file_name,
                LocalFilePath=file_name,
                PartSize=10,
                MAXThread=10,
            )
        """
        file_size = os.path.getsize(LocalFilePath)
        if file_size <= 1024 * 1024 * PartSize:
            with open(LocalFilePath, 'rb') as fp:
                rt = self.put_object(Bucket=Bucket, Key=Key, Body=fp, EnableMD5=EnableMD5, **kwargs)
            return rt
        else:
            part_size = 1024 * 1024 * PartSize  # 默认按照1MB分块,最大支持10G的文件，超过10G的分块数固定为10000
            last_size = 0  # 最后一块可以小于1MB
            parts_num = file_size // part_size
            last_size = file_size % part_size

            if last_size != 0:
                parts_num += 1
            else:  # 如果刚好整除,最后一块的大小等于分块大小
                last_size = part_size
            if parts_num > 10000:
                parts_num = 10000
                part_size = file_size // parts_num
                last_size = file_size % parts_num
                last_size += part_size

            # 创建分块上传
            # 判断是否可以断点续传
            resumable_flag = False
            already_exist_parts = {}
            uploadid = self._get_resumable_uploadid(Bucket, Key)
            if uploadid is not None:
                logger.info("fetch an existed uploadid in remote cos, uploadid={uploadid}".format(uploadid=uploadid))
                # 校验服务端返回的每个块的信息是否和本地的每个块的信息相同,只有校验通过的情况下才可以进行断点续传
                resumable_flag = self._check_all_upload_parts(Bucket, Key, uploadid, LocalFilePath, parts_num,
                                                              part_size, last_size, already_exist_parts)
            # 如果不能断点续传,则创建一个新的分块上传
            if not resumable_flag:
                rt = self.create_multipart_upload(Bucket=Bucket, Key=Key, **kwargs)
                uploadid = rt['UploadId']
                logger.info("create a new uploadid in upload_file, uploadid={uploadid}".format(uploadid=uploadid))

            # 增加限速功能
            part_headers = dict()
            if 'TrafficLimit' in kwargs:
                part_headers['TrafficLimit'] = kwargs['TrafficLimit']
            # SSE-C对象在上传段时也要求传入加密头域
            if 'SSECustomerAlgorithm' in kwargs:
                part_headers['SSECustomerAlgorithm'] = kwargs['SSECustomerAlgorithm']
                part_headers['SSECustomerKey'] = kwargs['SSECustomerKey']
                part_headers['SSECustomerKeyMD5'] = kwargs['SSECustomerKeyMD5']

            offset = 0  # 记录文件偏移量
            lst = list()  # 记录分块信息
            pool = SimpleThreadPool(MAXThread)
            callback = None
            if progress_callback:
                callback = ProgressCallback(file_size, progress_callback)
            for i in range(1, parts_num + 1):
                if i == parts_num:  # 最后一块
                    pool.add_task(self._upload_part, Bucket, Key, LocalFilePath, offset, file_size - offset, i,
                                  uploadid, lst, resumable_flag, already_exist_parts, EnableMD5, callback, **part_headers)
                else:
                    pool.add_task(self._upload_part, Bucket, Key, LocalFilePath, offset, part_size, i, uploadid, lst,
                                  resumable_flag, already_exist_parts, EnableMD5, callback, **part_headers)
                    offset += part_size

            pool.wait_completion()
            result = pool.get_result()
            if not result['success_all'] or len(lst) != parts_num:
                raise CosClientError('some upload_part fail after max_retry, please upload_file again')
            lst = sorted(lst, key=lambda x: x['PartNumber'])  # 按PartNumber升序排列

            # 完成分块上传
            rt = self.complete_multipart_upload(Bucket=Bucket, Key=Key, UploadId=uploadid,
                                                MultipartUpload={'Part': lst})
            return rt

    def _head_object_when_copy(self, CopySource, **kwargs):
        """查询源文件的长度"""
        bucket, path, endpoint, versionid = get_copy_source_info(CopySource, self._conf._enable_old_domain, self._conf._enable_internal_domain)
        params = {}
        if versionid != '':
            params['versionId'] = versionid
        url = u"{scheme}://{bucket}.{endpoint}/{path}".format(scheme=self._conf._scheme, bucket=bucket,
                                                              endpoint=endpoint, path=quote(to_bytes(path), '/-_.~'))

        headers = dict()
        # SSE-C对象在head源对象时也要求传入加密头域
        if 'CopySourceSSECustomerAlgorithm' in kwargs:
            headers['SSECustomerAlgorithm'] = kwargs['CopySourceSSECustomerAlgorithm']
            headers['SSECustomerKey'] = kwargs['CopySourceSSECustomerKey']
            headers['SSECustomerKeyMD5'] = kwargs['CopySourceSSECustomerKeyMD5']
        headers = mapped(headers)

        rt = self.send_request(
            method='HEAD',
            url=url,
            bucket=bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            headers=headers,
            params=params)
        storage_class = 'standard'
        if 'x-cos-storage-class' in rt.headers:
            storage_class = rt.headers['x-cos-storage-class'].lower()
        return int(rt.headers['Content-Length']), storage_class

    def _upload_part_copy(self, bucket, key, part_number, upload_id, copy_source, copy_source_range, md5_lst, **kwargs):
        """拷贝指定文件至分块上传,记录结果到lst中去

        :param bucket(string): 存储桶名称.
        :param key(string): 上传COS路径.
        :param part_number(int): 上传分块的编号.
        :param upload_id(string): 分块上传创建的UploadId.
        :param copy_source(dict): 拷贝源,包含Appid,Bucket,Region,Key.
        :param copy_source_range(string): 拷贝源的字节范围,bytes=first-last。
        :param md5_lst(list): 保存上传成功分块的MD5和序号.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        rt = self.upload_part_copy(bucket, key, part_number, upload_id, copy_source, copy_source_range, **kwargs)
        md5_lst.append({'PartNumber': part_number, 'ETag': rt['ETag']})
        return None

    def _check_same_region(self, dst_endpoint, CopySource):
        src_endpoint = get_copy_source_info(CopySource, self._conf._enable_old_domain, self._conf._enable_internal_domain)[2]
        if src_endpoint == dst_endpoint:
            return True
        return False

    def copy(self, Bucket, Key, CopySource, CopyStatus='Copy', PartSize=10, MAXThread=5, **kwargs):
        """文件拷贝，小于5G的文件调用copy_object，大于等于5G的文件调用分块上传的upload_part_copy

        :param Bucket(string): 存储桶名称.
        :param Key(string): 上传COS路径.
        :param CopySource(dict): 拷贝源,包含Appid,Bucket,Region,Key.
        :param CopyStatus(string): 拷贝状态,可选值'Copy'|'Replaced'.
        :param PartSize(int): 分块的大小设置.
        :param MAXThread(int): 并发上传的最大线程数.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 拷贝成功的结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 根据拷贝源文件的大小自动选择拷贝策略
            copy_source = {'Bucket': 'testcopt-1252468703', 'Key': '/thread_1MB', 'Region': 'ap-guangzhou'}
            response = client.copy(
                Bucket='test',
                Key='copy_10G.txt',
                CopySource=copy_source,
                MAXThread=10
            )
        """
        # 先查询下拷贝源object的content-length
        file_size, src_storage_class = self._head_object_when_copy(CopySource, **kwargs)

        dst_storage_class = 'standard'
        if 'StorageClass' in kwargs:
            dst_storage_class = kwargs['StorageClass'].lower()

        # 同园区且不改存储类型的情况下直接走copy_object
        if self._check_same_region(self._conf._endpoint, CopySource) and src_storage_class == dst_storage_class:
            response = self.copy_object(Bucket=Bucket, Key=Key, CopySource=CopySource, CopyStatus=CopyStatus, **kwargs)
            return response

        # 如果源文件大小小于5G，则直接调用copy_object接口
        if file_size < self._conf._copy_part_threshold_size:
            response = self.copy_object(Bucket=Bucket, Key=Key, CopySource=CopySource, CopyStatus=CopyStatus, **kwargs)
            return response

        # 如果源文件大小大于等于5G，则先创建分块上传，在调用upload_part
        part_size = 1024 * 1024 * PartSize  # 默认按照10MB分块
        last_size = 0  # 最后一块可以小于1MB
        parts_num = file_size // part_size
        last_size = file_size % part_size
        if last_size != 0:
            parts_num += 1
        if parts_num > 10000:
            parts_num = 10000
            part_size = file_size // parts_num
            last_size = file_size % parts_num
            last_size += part_size
        # 创建分块上传
        rt = self.create_multipart_upload(Bucket=Bucket, Key=Key, **kwargs)
        uploadid = rt['UploadId']

        # 上传分块拷贝
        offset = 0  # 记录文件偏移量
        lst = list()  # 记录分块信息
        pool = SimpleThreadPool(MAXThread)

        part_headers = dict()
        # 目标对象是SSE-C需要增加加密头域
        if 'SSECustomerAlgorithm' in kwargs:
            part_headers['SSECustomerAlgorithm'] = kwargs['SSECustomerAlgorithm']
            part_headers['SSECustomerKey'] = kwargs['SSECustomerKey']
            part_headers['SSECustomerKeyMD5'] = kwargs['SSECustomerKeyMD5']
        # 源对象是SSE-C需要增加加密头域
        if 'CopySourceSSECustomerAlgorithm' in kwargs:
            part_headers['CopySourceSSECustomerAlgorithm'] = kwargs['CopySourceSSECustomerAlgorithm']
            part_headers['CopySourceSSECustomerKey'] = kwargs['CopySourceSSECustomerKey']
            part_headers['CopySourceSSECustomerKeyMD5'] = kwargs['CopySourceSSECustomerKeyMD5']

        for i in range(1, parts_num + 1):
            if i == parts_num:  # 最后一块
                copy_range = gen_copy_source_range(offset, file_size - 1)
                pool.add_task(self._upload_part_copy, Bucket, Key, i, uploadid, CopySource, copy_range, lst, **part_headers)
            else:
                copy_range = gen_copy_source_range(offset, offset + part_size - 1)
                pool.add_task(self._upload_part_copy, Bucket, Key, i, uploadid, CopySource, copy_range, lst, **part_headers)
                offset += part_size

        pool.wait_completion()
        result = pool.get_result()
        if not result['success_all']:
            raise CosClientError('some upload_part_copy fail after max_retry')

        lst = sorted(lst, key=lambda x: x['PartNumber'])  # 按PartNumber升序排列
        # 完成分片上传
        try:
            rt = self.complete_multipart_upload(Bucket=Bucket, Key=Key, UploadId=uploadid,
                                                MultipartUpload={'Part': lst})
        except Exception as e:
            abort_response = self.abort_multipart_upload(Bucket=Bucket, Key=Key, UploadId=uploadid)
            raise e
        return rt

    def _upload_part_from_buffer(self, bucket, key, data, part_num, uploadid, md5_lst):
        """从内存中读取分块, 上传单个分块,将结果记录在md5——list中

        :param bucket(string): 存储桶名称.
        :param key(string): 分块上传路径名.
        :param data(string): 数据块.
        :param part_num(int): 上传分块的序号.
        :param uploadid(string): 分块上传的uploadid.
        :param md5_lst(list): 保存上传成功分块的MD5和序号.
        :return: None.
        """

        rt = self.upload_part(bucket, key, data, part_num, uploadid)
        md5_lst.append({'PartNumber': part_num, 'ETag': rt['ETag']})
        return None

    def upload_file_from_buffer(self, Bucket, Key, Body, MaxBufferSize=100, PartSize=10, MAXThread=5, **kwargs):
        """小于分块大小的的文件简单上传，大于等于分块大小的文件使用分块上传

        :param Bucket(string): 存储桶名称.
        :param key(string): 分块上传路径名.
        :param Body(fp): 文件流,必须实现了read方法.
        :param MaxBufferSize(int): 缓存文件的大小,单位为MB,MaxBufferSize/PartSize决定线程池中最大等待调度的任务数量
        :param PartSize(int): 分块的大小设置,单位为MB
        :param MAXThread(int): 并发上传的最大线程数.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 成功上传的文件的结果.
        """
        if not hasattr(Body, 'read'):
            raise CosClientError("Body must have attr read")

        part_size = 1024 * 1024 * PartSize

        # 先读一个块,如果直接EOF了就调用简单文件上传
        part_num = 1
        data = Body.read(part_size)

        if len(data) < part_size:
            rt = self.put_object(Bucket=Bucket, Key=Key, Body=data, **kwargs)
            return rt

        # 创建分块上传
        rt = self.create_multipart_upload(Bucket=Bucket, Key=Key, **kwargs)
        uploadid = rt['UploadId']

        lst = list()  # 记录分块信息
        MAXQueue = MaxBufferSize // PartSize
        if MAXQueue == 0:
            MAXQueue = 1
        pool = SimpleThreadPool(MAXThread, MAXQueue)
        while True:
            if not data:
                break
            pool.add_task(self._upload_part_from_buffer, Bucket, Key, data, part_num, uploadid, lst)
            part_num += 1
            data = Body.read(part_size)

        pool.wait_completion()
        result = pool.get_result()
        if not result['success_all']:
            raise CosClientError('some upload_part fail after max_retry')
        lst = sorted(lst, key=lambda x: x['PartNumber'])  # 按PartNumber升序排列

        # 完成分片上传
        try:
            rt = self.complete_multipart_upload(Bucket=Bucket, Key=Key, UploadId=uploadid,
                                                MultipartUpload={'Part': lst})
        except Exception as e:
            abort_response = self.abort_multipart_upload(Bucket=Bucket, Key=Key, UploadId=uploadid)
            raise e
        return rt

    def append_object(self, Bucket, Key, Position, Data, **kwargs):
        """文件块追加接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Position(int): 追加内容的起始位置.
        :param Data(string): 追加的内容
        :kwargs(dict): 设置上传的headers.
        :return(dict): 上传成功返回的结果，包含ETag等信息.
        """
        check_object_content_length(Data)
        headers = mapped(kwargs)
        params = {'append': '', 'position': Position}
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("append object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key, params=params),
            data=Data,
            headers=headers,
            params=params)
        response = dict(**rt.headers)
        return response

    def put_object_from_local_file(self, Bucket, LocalFilePath, Key, EnableMD5=False, **kwargs):
        """本地文件上传接口，适用于小文件，最大不得超过5GB

        :param Bucket(string): 存储桶名称.
        :param LocalFilePath(string): 上传文件的本地路径.
        :param Key(string): COS路径.
        :param EnableMD5(bool): 是否需要SDK计算Content-MD5，打开此开关会增加上传耗时.
        :kwargs(dict): 设置上传的headers.
        :return(dict): 上传成功返回的结果，包含ETag等信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 上传本地文件到cos
            response = client.put_object_from_local_file(
                Bucket='bucket',
                LocalFilePath='local.txt',
                Key='test.txt'
            )
            print (response['ETag'])
        """
        with open(LocalFilePath, 'rb') as fp:
            return self.put_object(Bucket, fp, Key, EnableMD5, **kwargs)

    def object_exists(self, Bucket, Key):
        """判断一个文件是否存在

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :return(bool): 文件是否存在,返回True为存在,返回False为不存在

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 上传本地文件到cos
            status = client.object_exists(
                Bucket='bucket',
                Key='test.txt'
            )
        """
        try:
            self.head_object(Bucket, Key)
            return True
        except CosServiceError as e:
            if e.get_status_code() == 404:
                return False
            else:
                raise e

    def bucket_exists(self, Bucket):
        """判断一个存储桶是否存在

        :param Bucket(string): 存储桶名称.
        :return(bool): 存储桶是否存在,返回True为存在,返回False为不存在.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 上传本地文件到cos
            status = client.bucket_exists(
                Bucket='bucket'
            )
        """
        try:
            self.head_bucket(Bucket)
            return True
        except CosServiceError as e:
            if e.get_status_code() == 404:
                return False
            else:
                raise e

    def change_object_storage_class(self, Bucket, Key, StorageClass):
        """改变文件的存储类型

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param StorageClass(bool): 是否需要SDK计算Content-MD5，打开此开关会增加上传耗时.
        :kwargs(dict): 设置上传的headers.
        :return(dict): 上传成功返回的结果，包含ETag等信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 上传本地文件到cos
            response = client.change_object_storage_class(
                Bucket='bucket',
                Key='test.txt',
                StorageClass='STANDARD'
            )
        """
        copy_source = {
            'Bucket': Bucket,
            'Key': Key,
            'Endpoint': self._conf._endpoint,
            'Appid': self._conf._appid
        }
        response = self.copy_object(
            Bucket=Bucket,
            Key=Key,
            CopySource=copy_source,
            CopyStatus='Replaced',
            StorageClass=StorageClass
        )
        return response

    def update_object_meta(self, Bucket, Key, **kwargs):
        """改变文件的存储类型

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :kwargs(dict): 设置文件的元属性.
        :return: None.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 上传本地文件到cos
            response = client.update_object_meta(
                Bucket='bucket',
                Key='test.txt',
                ContentType='text/html'
            )
        """
        copy_source = {
            'Bucket': Bucket,
            'Key': Key,
            'Endpoint': self._conf._endpoint,
            'Appid': self._conf._appid
        }
        response = self.copy_object(
            Bucket=Bucket,
            Key=Key,
            CopySource=copy_source,
            CopyStatus='Replaced',
            **kwargs
        )
        return response

    def put_bucket_encryption(self, Bucket, ServerSideEncryptionConfiguration={}, **kwargs):
        """设置执行存储桶下的默认加密配置

        :param Bucket(string): 存储桶名称.
        :param ServerSideEncryptionConfiguration(dict): 设置Bucket的加密规则
        :param kwargs(dict): 设置请求的headers.
        :return: None.
        """
        xml_config = format_xml(data=ServerSideEncryptionConfiguration, root='ServerSideEncryptionConfiguration')
        headers = mapped(kwargs)
        params = {'encryption': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("put bucket encryption, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            data=xml_config,
            headers=headers,
            params=params)

        return None

    def get_bucket_encryption(self, Bucket, **kwargs):
        """获取存储桶下的默认加密配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 返回bucket的加密规则.
        """
        headers = mapped(kwargs)
        params = {'encryption': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("get bucket encryption, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Rule'])
        return data

    def delete_bucket_encryption(self, Bucket, **kwargs):
        """用于删除指定存储桶下的默认加密配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求的headers.
        :return: None.
        """
        headers = mapped(kwargs)
        params = {'encryption': ''}
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket encryption, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)

        return None

    def put_async_fetch_task(self, Bucket, FetchTaskConfiguration={}, **kwargs):
        """发起异步拉取对象到COS的任务

        :param Bucket(string): 存储桶名称.
        :param FetchTaskConfiguration(dict): 异步拉取任务的配置.
        :kwargs(dict): 扩展参数.
        :return(dict): 异步任务成功返回的结果，包含Taskid等信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 发起异步拉取任务
            response = client.put_async_fetch_task(
                Bucket='bucket',
                FetchTaskConfiguration={
                    'Url':
                    'Key':
                    'MD5':
                    'SuccessCallbackUrl':
                    'FailureCallbackUrl':
                }
            )
        """
        url = '{scheme}://{region}.migration.myqcloud.com/{bucket}/'.format(scheme=self._conf._scheme,
                                                                            region=self._conf._region, bucket=Bucket)
        if self._conf._domain is not None:
            url = '{scheme}://{domain}/{bucket}/'.format(scheme=self._conf._scheme, domain=self._conf._domain,
                                                         bucket=Bucket)
        headers = {'Content-Type': 'application/json'}
        signed_key = Bucket + '/'
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=None,
            data=json.dumps(FetchTaskConfiguration),
            headers=headers,
            auth=CosS3Auth(self._conf, signed_key),
            cos_request=False
        )
        data = rt.json()
        return data

    def get_async_fetch_task(self, Bucket, TaskId, **kwargs):
        """获取异步拉取对象到COS的任务状态

        :param Bucket(string): 存储桶名称.
        :param TaskId(string): 异步拉取任务查询的唯一标识.
        :kwargs(dict): 扩展参数.
        :return(dict): 异步任务的状态

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取异步拉取任务
            response = client.get_async_fetch_task(
                Bucket='bucket',
                TaskId='string'
            )
        """
        url = '{scheme}://{region}.migration.myqcloud.com/{bucket}/{task_id}'.format(scheme=self._conf._scheme,
                                                                                     region=self._conf._region,
                                                                                     bucket=Bucket, task_id=TaskId)
        if self._conf._domain is not None:
            url = '{scheme}://{domain}/{bucket}/{task_id}'.format(scheme=self._conf._scheme, domain=self._conf._domain,
                                                                  bucket=Bucket, task_id=TaskId)
        headers = {'Content-Type': 'application/json'}
        signed_key = '{bucket}/{task_id}'.format(bucket=Bucket, task_id=TaskId)
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=None,
            headers=headers,
            auth=CosS3Auth(self._conf, signed_key),
            cos_request=False
        )
        data = rt.json()
        return data

    def put_live_channel(self, Bucket, ChannelName, Expire=3600, PreSignExpire=0, LiveChannelConfiguration={}, **kwargs):
        """创建直播通道

        :param Bucket(string): 存储桶名称.
        :param ChannelName(string): 直播通道名称.
        :param Expire(int): 推流url签名过期时间.
        :param PreSignExpire(int): playlist中ts分片签名的过期时间,合法值[60,43200],默认为0,不开启该签名.
        :param LiveChannelConfiguration(dict): 直播通道配置.
        :param kwargs(dict): 设置请求headers.
        :return(dict): publish url and playurl.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 设置直播通道配置
            livechannel_config = {
                'Description': 'channel description',
                'Switch': 'Enabled',
                'Target': {
                    'Type': 'HLS',
                    'FragDuration': '3',
                    'FragCount': '5',
                 }
            }
            response = client.put_live_channel(Bucket='bucket', ChannelName='ch1', LiveChannelConfiguration=livechannel_config)
        """
        xml_config = format_xml(data=LiveChannelConfiguration, root='LiveChannelConfiguration')
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        params = {'live': ''}
        url = self._conf.uri(bucket=Bucket, path=ChannelName)
        logger.info("put live channel, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params, key=ChannelName),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        if data['PublishUrls']['Url'] is not None:
            rtmpSign = CosRtmpAuth(self._conf, bucket=Bucket, channel=ChannelName, expire=Expire, presign_expire=PreSignExpire)
            url = data['PublishUrls']['Url']
            url += '?' + rtmpSign.get_rtmp_sign()
            data['PublishUrls']['Url'] = url
        return data

    def get_rtmp_signed_url(self, Bucket, ChannelName, Expire=3600, Params={}):
        """获取直播通道带签名的推流url
        :param Bucket(string): 存储桶名称.
        :param ChannelName(string): 直播通道名称.
        :return: dict.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            resp = client.get_rtmp_signed_url(Bucket='bucket', ChannelName='ch1')
        """
        rtmp_signed_url = 'rtmp://{bucket}.cos.{region}.myqcloud.com/live/{channel}'.format(bucket=Bucket,
                                                                                            region=self._conf._region,
                                                                                            channel=ChannelName)
        rtmpAuth = CosRtmpAuth(self._conf, bucket=Bucket, channel=ChannelName, params=Params, expire=Expire)
        return rtmp_signed_url + '?' + rtmpAuth.get_rtmp_sign()

    def get_live_channel_info(self, Bucket, ChannelName, **kwargs):
        """获取直播通道配置信息

        :param Bucket(string): 存储桶名称.
        :param ChannelName(string): 直播通道名称.
        :param kwargs(dict): 设置请求headers.
        :return: dict.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            resp = client.get_live_channel_info(Bucket='bucket', ChannelName='ch1')
        """
        params = {'live': ''}
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=ChannelName)
        logger.info("get live channel info, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params, key=ChannelName),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        return data

    def put_live_channel_switch(self, Bucket, ChannelName, Switch, **kwargs):
        """禁用或者开启直播通道

        :param Bucket(string): 存储桶名称.
        :param ChannelName(string): 直播通道名称.
        :param Switch(string): 'enabled'或'disabled'.
        :param kwargs(dict): 设置请求headers.
        :return(None).

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            client.put_live_channel_switch(Bucket='bucket', ChannelName='ch1', Switch='enabled')
        """
        params = {'live': ''}
        if Switch in ['enabled', 'disabled']:
            params['switch'] = Switch
        else:
            raise CosClientError('switch must be enabled or disabled')

        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=ChannelName)
        logger.info("put live channel switch, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))
        self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params, key=ChannelName),
            headers=headers,
            params=params)
        return None

    def get_live_channel_history(self, Bucket, ChannelName, **kwargs):
        """获取直播通道推流历史

        :param Bucket(string): 存储桶名称.
        :param ChannelName(string): 直播通道名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict).

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            resp = client.get_live_channel_history(Bucket='bucket', ChannelName='ch1')
        """
        params = {'live': '', 'comp': 'history'}
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=ChannelName)
        logger.info("get live channel history, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params, key=ChannelName),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        format_dict(data, ['LiveRecord'])
        return data

    def get_live_channel_status(self, Bucket, ChannelName, **kwargs):
        """获取直播通道推流状态

        :param Bucket(string): 存储桶名称.
        :param ChannelName(string): 直播通道名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict).

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            resp = client.get_live_channel_status(Bucket='bucket', ChannelName='ch1')
        """
        params = {'live': '', 'comp': 'status'}
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=ChannelName)
        logger.info("get live channel status, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params, key=ChannelName),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        return data

    def delete_live_channel(self, Bucket, ChannelName, **kwargs):
        """删除直播通道

        :param Bucket(string): 存储桶名称.
        :param ChannelName(string): 直播通道名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict).

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            client.delete_live_channel(Bucket='bucket', ChannelName='ch1')
        """
        params = {'live': ''}
        url = self._conf.uri(bucket=Bucket, path=ChannelName)
        headers = mapped(kwargs)
        logger.info("delete live channel, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params, key=ChannelName),
            headers=headers,
            params=params)
        data = dict(**rt.headers)
        return data

    def get_vod_playlist(self, Bucket, ChannelName, StartTime=0, EndTime=0, **kwargs):
        """查询指定时间段播放列表文件

        :param Bucket(string): 存储桶名称.
        :param ChannelName(string): 直播通道名称.
        :param StartTime(int): 播放列表ts文件的起始时间，格式为unix时间戳.
        :param EndTime(int): 播放列表ts文件的结束时间，格式为unix时间戳.
        :param kwargs(dict): 设置请求headers.
        :return(string).

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            resp = client.get_vod_playlist(Bucket='bucket', ChannelName='ch1', StartTime=1611218201, EndTime=1611218300)
        """
        if StartTime <= 0 or EndTime <= 0:
            raise CosClientError('invalid timestamp')
        if StartTime >= EndTime:
            raise CosClientError('StartTime must be less than EndTime')

        params = {'vod': '', 'starttime': StartTime, 'endtime': EndTime}
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=ChannelName)
        logger.info("get vod playlist, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params, key=ChannelName),
            headers=headers,
            params=params)
        return rt.content

    def post_vod_playlist(self, Bucket, ChannelName, PlaylistName, StartTime=0, EndTime=0, **kwargs):
        """生成点播播放列表文件

        :param Bucket(string): 存储桶名称.
        :param ChannelName(string): 直播通道名称.
        :param PlaylistName(string): 播放列表文件名称.
        :param StartTime(int): 播放列表ts文件的起始时间，格式为unix时间戳.
        :param EndTime(int): 播放列表ts文件的结束时间，格式为unix时间戳.
        :param kwargs(dict): 设置请求headers.
        :return(None).

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            resp = client.post_vod_playlist(Bucket='bucket', ChannelName='ch1', PlaylistName='test.m3u8', StartTime=1611218201, EndTime=1611218300)
        """
        if StartTime <= 0 or EndTime <= 0:
            raise CosClientError('invalid timestamp')
        if StartTime >= EndTime:
            raise CosClientError('StartTime must be less than EndTime')
        if not PlaylistName.endswith('.m3u8'):
            raise CosClientError('PlaylistName must be end with .m3u8')

        params = {'vod': '', 'starttime': StartTime, 'endtime': EndTime}
        headers = mapped(kwargs)
        file_path = ChannelName + '/' + PlaylistName
        url = self._conf.uri(bucket=Bucket, path=file_path)
        logger.info("post vod playlist, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params, key=file_path),
            headers=headers,
            params=params)
        return None

    def list_live_channel(self, Bucket, MaxKeys=100, Prefix='', Marker='', **kwargs):
        """获取直播通道列表

        :param Bucket(string): 存储桶名称.
        :param MaxKeys(int): 每页可以列出通道数量的最大值，有效值范围为[1, 1000]，默认值：100.
        :param Prefix(string): 限定返回的 LiveChannel 必须以 prefix 作为前缀.
        :param Marker(string): 从 marker 之后按字母排序的第一个开始返回.
        :param kwargs(dict): 设置请求headers.
        :return: string.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            resp = client.list_channel(Bucket='bucket', MaxKeys=100)
        """
        params = {'live': ''}
        if MaxKeys >= 1:
            params['max-keys'] = MaxKeys
        if Prefix != '':
            params['prefix'] = Prefix
        if Marker != '':
            params['marker'] = Marker
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket)
        logger.info("list live channel, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)
        data = xml_to_dict(rt.content)
        format_dict(data, ['LiveChannel'])
        decode_result(
            data,
            [
                'Prefix',
                'Marker',
                'MaxKeys',
                'IsTruncated',
                'NextMarker'
            ],
            [
                ['LiveChannel', 'Name'],
            ])
        return data

    def ci_put_object_from_local_file(self, Bucket, LocalFilePath, Key, EnableMD5=False, **kwargs):
        """本地CI文件上传接口，适用于小文件，最大不得超过5GB

        :param Bucket(string): 存储桶名称.
        :param LocalFilePath(string): 上传文件的本地路径.
        :param Key(string): COS路径.
        :param EnableMD5(bool): 是否需要SDK计算Content-MD5，打开此开关会增加上传耗时.
        :kwargs(dict): 设置上传的headers.
        :return(dict): 上传成功UploadResult结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 上传本地文件到CI
            response = client.ci_put_object_from_local_file(
                Bucket='bucket-appid',
                LocalFilePath='local.jpg',
                Key='local.jpg'
                PicOperations='{"is_pic_info":1,"rules":[{"fileid":"format.png","rule":"imageView2/format/png"}]}'
            )
            print(response['ProcessResults']['Object']['ETag'])
        """
        with open(LocalFilePath, 'rb') as fp:
            return self.ci_put_object(Bucket, fp, Key, EnableMD5, **kwargs)

    def ci_put_object(self, Bucket, Body, Key, EnableMD5=False, **kwargs):
        """单文件CI上传接口，适用于小文件，最大不得超过5GB

        :param Bucket(string): 存储桶名称.
        :param Body(file|string): 上传的文件内容，类型为文件流或字节流.
        :param Key(string): COS路径.
        :param EnableMD5(bool): 是否需要SDK计算Content-MD5，打开此开关会增加上传耗时.
        :kwargs(dict): 设置上传的headers.
        :return(dict): 上传成功UploadResult结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 上传本地文件到cos
            with open('local.jpg', 'rb') as fp:
                response = client.ci_put_object(
                    Bucket='bucket',
                    Body=fp,
                    Key='local.jpg'
                    PicOperations='{"is_pic_info":1,"rules":[{"fileid":"format.jpg","rule":"imageView2/format/png"}]}'
                )
                print(response['ProcessResults']['Object']['ETag'])
        """
        check_object_content_length(Body)
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("ci_put_object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        if EnableMD5:
            md5_str = get_content_md5(Body)
            if md5_str:
                headers['Content-MD5'] = md5_str
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key),
            data=Body,
            headers=headers)

        response = dict(**rt.headers)
        data = xml_to_dict(rt.content)
        return response, data

    def ci_put_image_style(self, Bucket, Request, **kwargs):
        """CI增加图片样式接口

        :param Bucket(string): 存储桶名称.
        :param Request(dict): 图片样式请求体.
        :kwargs(dict): 设置上传的headers.
        :return(dict): 添加图片样式返回结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            body = {
                'StyleName': 'style_name',
                'StyleBody': 'imageMogr2/thumbnail/!50px',
            }
            response = client.ci_put_image_style(
                Bucket=bucket_name,
                Request=body,
            )
        """
        headers = mapped(kwargs)
        params = {'style': ''}
        xml_config = format_xml(data=Request, root='AddStyle')
        url = self._conf.uri(bucket=Bucket, endpoint=self._conf._endpoint_pic)
        logger.info("ci_put_image_style, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)

        response = dict(**rt.headers)
        return response

    def ci_get_image_style(self, Bucket, Request, **kwargs):
        """CI获取图片样式接口

        :param Bucket(string): 存储桶名称.
        :param Request(dict): 图片样式请求体.
        :kwargs(dict): 设置上传的headers.
        :return(dict): 获取图片样式结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
                body = {
                    'StyleName': 'style_name',
                }
                response, data = client.ci_get_image_style(
                    Bucket=bucket_name,
                    Request=body,
                )
                print(response['x-cos-request-id'])
                print(data)
        """
        headers = mapped(kwargs)
        params = {'style': ''}
        url = self._conf.uri(bucket=Bucket, endpoint=self._conf._endpoint_pic)
        xml_config = format_xml(data=Request, root='GetStyle')
        logger.info("ci_get_image_style, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)

        response = dict(**rt.headers)
        data = xml_to_dict(rt.content)
        return response, data

    def ci_delete_image_style(self, Bucket, Request, **kwargs):
        """CI删除图片样式接口

        :param Bucket(string): 存储桶名称.
        :param Request(dict): 图片样式请求体.
        :kwargs(dict): 设置上传的headers.
        :return(dict): 获取图片样式response header.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            body = {
                'StyleName': 'style_name',
            }
            response = client.ci_delete_image_style(
                Bucket=bucket_name,
                Request=body,
            )
            print(response['x-cos-request-id'])
        """
        headers = mapped(kwargs)
        params = {'style': ''}
        xml_config = format_xml(data=Request, root='DeleteStyle')
        url = self._conf.uri(bucket=Bucket, endpoint=self._conf._endpoint_pic)
        logger.info("ci_delete_image_style, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, params=params),
            headers=headers,
            params=params)

        response = dict(**rt.headers)
        return response

    def ci_get_object(self, Bucket, Key, DestImagePath, Rule, **kwargs):
        """单文件CI下载对象到文件接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param DestImagePath(string): 下载图片的目的路径.
        :param Rule(string): 图片处理规则.
        :kwargs(dict): 设置上传的headers.
        :return(dict): 下载后response header.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response = client.ci_get_object(
                    Bucket='bucket',
                    Key='local.jpg',
                    DestImagePath='download.png'
                    Rule='imageView2/format/png'
                )
                print(response['x-cos-request-id'])

        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {Rule: ''}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        if 'versionId' in headers:
            params['versionId'] = headers['versionId']
            del headers['versionId']
        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("ci_get_object, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        StreamBody(rt).get_stream_to_file(DestImagePath)
        response = dict(**rt.headers)
        return response

    def ci_get_image_info(self, Bucket, Key, Param='imageInfo', **kwargs):
        """ci获取图片基本信息接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Param(string): 请求参数，一般情况下不进行赋值操作.
        :kwargs(dict): 设置获取图片信息的headers.
        :return(dict): response header.
        :return(dict): 图片信息结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response, data = client.ci_get_image_info(
                Bucket=bucket_name,
                 Key='format.png',
            )
            print(response['x-cos-request-id'])
            print(data)

        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {Param: ''}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        if 'versionId' in headers:
            params['versionId'] = headers['versionId']
            del headers['versionId']
        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("ci_get_image_info, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        response = dict(**rt.headers)
        data = rt.content
        return response, data

    def ci_get_image_exif_info(self, Bucket, Key, **kwargs):
        """ci获取图片exif信息接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :kwargs(dict): 设置获取图片exif信息的headers.
        :return(dict): response header.
        :return(dict): 图片exif信息结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response, data = client.ci_get_image_exif_info(
                Bucket=bucket_name,
                Key='format.png',
            )
            print(response['x-cos-request-id'])
            print(data)

        """
        return self.ci_get_image_info(Bucket, Key, 'exif', **kwargs)

    def ci_get_image_ave_info(self, Bucket, Key, **kwargs):
        """ci获取图片主色调接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :kwargs(dict): 设置获取图片主色调的headers.
        :return(dict): response header.
        :return(dict): 图片主色调结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response, data = client.ci_get_image_exif_info(
                Bucket=bucket_name,
                Key='format.png',
            )
            print(response['x-cos-request-id'])
            print(data)

        """
        return self.ci_get_image_info(Bucket, Key, 'imageAve', **kwargs)

    def ci_process(self, Bucket, Key, CiProcess, Params={}, NeedHeader=False, Stream=False, **kwargs):
        """ci_process基本信息的接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param CiProcess(string): ci process处理参数.
        :param kwargs(dict): 设置下载的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response = client.ci_process(
                Bucket='bucket',
                Key='test.mp4',
                CiProcess='AssessQuality',
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {'ci-process': CiProcess}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if Params is not None:
            for key in Params:
                params[key] = Params[key]

        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("ci_process=:{ci_process}, url=:{url} ,headers=:{headers}, params=:{params}".format(
            ci_process=CiProcess,
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key, params=params),
            stream=Stream,
            params=params,
            headers=headers)

        data = ''
        response = dict(**rt.headers)
        if 'Content-Type' in response:
            if response['Content-Type'] == 'application/xml' and 'Content-Length' in response and response['Content-Length'] != 0:
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()
            else:
                if Stream:
                    data = StreamBody(rt)
                else:
                    data = rt.content

        if NeedHeader:
            return response, data
        return data

    def ci_image_assess_quality(self, Bucket, Key, **kwargs):
        """ci_image_assess_quality图片质量评估接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置下载的headers.
        :return(dict): 图片质量评估返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response = client.ci_image_assess_quality(
                Bucket='bucket',
                Key='test.mp4',
            )
            print response
        """
        return self.ci_process(Bucket, Key, "AssessQuality", **kwargs)

    def ci_image_detect_car(self, Bucket, Key, **kwargs):
        """ci_image_detect_car车辆车牌检测接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置下载的headers.
        :return(dict): 车辆车牌检测返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response = client.ci_image_detect_car(
                Bucket='bucket',
                Key='test.mp4',
            )
            print response
        """
        return self.ci_process(Bucket, Key, "DetectCar", **kwargs)

    def ci_image_detect_label(self, Bucket, Key='', Scenes=None, DetectUrl=None, **kwargs):
        """ci_image_detect_label图片标签接口 https://cloud.tencent.com/document/product/460/39082

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Scenes(string): 本次调用支持的识别场景，可选值如下：
                                    web，针对网络图片优化；
                                    camera，针对手机摄像头拍摄图片优化；
                                    album，针对手机相册、网盘产品优化；
                                    news，针对新闻、资讯、广电等行业优化；
                                    如果不传此参数，则默认为camera。
                                    支持多场景（scenes）一起检测，以，分隔。例如，使用 scenes=web，camera 即对一张图片使用两个模型同时检测，输出两套识别结果.
        :param DetectUrl(string): 您可以通过填写 detect-url 处理任意公网可访问的图片链接。不填写 detect-url 时，后台会默认处理 ObjectKey ，填写了 detect-url 时，后台会处理 detect-url 链接.
        :param kwargs(dict): 设置下载的headers.
        :return(dict): 图片质量评估返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response = client.ci_image_detect_label(
                Bucket='bucket',
                Key='test.mp4',
            )
            print response
        """
        params = {}
        if Scenes is not None:
            params['scenes'] = Scenes
        if DetectUrl is not None:
            params['detect-url'] = DetectUrl
        path = "/" + Key
        return self.ci_process(Bucket=Bucket, Key=path, CiProcess="detect-label", Params=params, **kwargs)

    def ci_qrcode_generate(self, Bucket, QrcodeContent, Width, Mode=0, **kwargs):
        """二维码生成接口

        :param Bucket(string): 存储桶名称.
        :param QrcodeContent(string): 可识别的二维码文本信息.
        :param Width(string):  指定生成的二维码或条形码的宽度，高度会进行等比压缩.
        :param Mode(int): 生成的二维码类型，可选值：0或1。0为二维码，1为条形码，默认值为0.
        :return(dict): 二维码生成结果

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response = client.ci_qrcode_generate(
                Bucket=bucket_name,
                QrcodeContent='https://www.example.com',
                Width=200
            )
            qrCodeImage = base64.b64decode(response['ResultImage'])
            with open('/result.png', 'wb') as f:
                f.write(qrCodeImage)
            print(response)
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {'ci-process': 'qrcode-generate'}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['qrcode-content'] = QrcodeContent
        params['width'] = Width
        params['mode'] = Mode
        params = format_values(params)

        url = self._conf.uri(bucket=Bucket)
        logger.info("ci_qrcode_generate, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, params=params),
            params=params,
            headers=headers)

        data = xml_to_dict(rt.content)
        return data

    def ci_ocr_process(self, Bucket, Key, Type='general', LanguageType='zh', Ispdf=False, PdfPagenumber=1, Isword=False, EnableWordPolygon=False, **kwargs):
        """通用文字识别

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Type(string): OCR 的识别类型，有效值为 general，accurate，efficient，fast，handwriting。general 表示通用印刷体识别；accurate 表示印刷体高精度版；efficient 表示印刷体精简版；fast 表示印刷体高速版；handwriting 表示手写体识别。默认值为 general。
        :param LanguageType(string):  type 值为 general 时有效，表示识别语言类型。支持自动识别语言类型，同时支持自选语言种类，默认中英文混合(zh)，各种语言均支持与英文混合的文字识别。可选值请参见 可识别的语言类型。
        :param Ispdf(bool): type 值为 general、fast 时有效，表示是否开启 PDF 识别，有效值为 true 和 false，默认值为 false，开启后可同时支持图片和 PDF 的识别。
        :param PdfPagenumber(int): type 值为 general、fast 时有效，表示需要识别的 PDF 页面的对应页码，仅支持 PDF 单页识别，当上传文件为 PDF 且 ispdf 参数值为 true 时有效，默认值为1。
        :param Isword(bool): type 值为 general、accurate 时有效，表示识别后是否需要返回单字信息，有效值为 true 和 false，默认为 false。
        :param EnableWordPolygon(bool): type 值为 handwriting 时有效，表示是否开启单字的四点定位坐标输出，有效值为 true 和 false，默认值为 false。
        :return(dict): 下载成功返回的结果,包含Body对应的StreamBody,可以获取文件流或下载文件到本地.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            def ci_ocr_process():
                # 通用文字识别
                response = client.ci_ocr_process(
                    Bucket=bucket_name,
                    Key='ocr.jpeg',
                )
                print(response)
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {'ci-process': 'OCR'}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['type'] = Type
        params['language-type'] = LanguageType
        params['ispdf'] = str(Ispdf).lower()
        params['pdf-pagenumber'] = PdfPagenumber
        params['isword'] = str(Isword).lower()
        params['enable-word-polygon'] = str(EnableWordPolygon).lower()
        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("ci_ocr_process, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        data = xml_to_dict(rt.content)

        return data

    def ci_image_process(self, Bucket, Key, **kwargs):
        """查询CI image process

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 上传成功UploadResult结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建分块上传
            response = client.ci_image_process(
                Bucket='bucket',
                Key='local.jpg'
                PicOperations='{"is_pic_info":1,"rules":[{"fileid":"format.png","rule":"imageView2/format/png"}]}'
            )
            print(response['ProcessResults']['Object']['ETag'])
        """
        headers = mapped(kwargs)
        params = {'image_process': ''}
        params = format_values(params)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("ci_image_process, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key, params=params),
            headers=headers,
            params=params)
        response = dict(**rt.headers)
        data = xml_to_dict(rt.content)
        return response, data

    def ci_download_compress_image(self, Bucket, Key, DestImagePath, CompressType, **kwargs):
        """图片压缩接口
        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param DestImagePath(string): 下载图片的目的路径.
        :param CompressType(string): 压缩格式，目标缩略图的图片格式为 TPG 或 HEIF.
        :param kwargs(dict): 设置下载的headers.
        :return response(dict): 请求成功返回的header.
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {'imageMogr2/format/' + CompressType: ''}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        if 'versionId' in headers:
            params['versionId'] = headers['versionId']
            del headers['versionId']
        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("ci_download_compress_image, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        StreamBody(rt).get_stream_to_file(DestImagePath)
        response = dict(**rt.headers)
        return response

    def ci_image_inspect(self, Bucket, Key, **kwargs):
        """ci异常图片检测同步请求 https://cloud.tencent.com/document/product/460/75997

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置获取图片信息的headers.
        :return(dict): response header.
        :return(dict): 检测结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response, data = client.ci_image_inspect(
                Bucket=bucket_name,
                 Key='format.png',
            )
            print(response['x-cos-request-id'])
            print(data)

        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {'imageInspect': ''}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        if 'versionId' in headers:
            params['versionId'] = headers['versionId']
            del headers['versionId']
        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("ci_image_inspect, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        response = dict(**rt.headers)
        data = rt.content
        return response, data

    def ci_get_image_aigc_metadata(self, Bucket, Key, **kwargs):
        """ci_get_image_aigc_metadata查询图片中保存的AIGC元数据标识信息接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置下载的headers.
        :return(dict): response header.
        :return(dict): AIGC元数据标识信息结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response, data = client.ci_get_image_aigc_metadata(
                    Bucket='bucket',
                    ObjectKey=''
                )
            print data
            print response
        """

        path = "/" + Key
        return self.ci_process(Bucket, path, "ImageAIGCMetadata", NeedHeader=True, **kwargs)

    def ci_put_object_from_local_file_and_get_qrcode(self, Bucket, LocalFilePath, Key, EnableMD5=False, **kwargs):
        """本地CI文件上传接口并返回二维码，适用于小文件，最大不得超过5GB

        :param Bucket(string): 存储桶名称.
        :param LocalFilePath(string): 上传文件的本地路径.
        :param Key(string): COS路径.
        :param EnableMD5(bool): 是否需要SDK计算Content-MD5，打开此开关会增加上传耗时.
        :kwargs(dict): 设置上传的headers.
        :return(dict,dict): 上传成功UploadResult结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 上传本地文件到CI
            response, data = client.ci_put_object_qrcode_from_local_file(
                Bucket='bucket-appid',
                LocalFilePath='local.jpg',
                Key='local.jpg'
                PicOperations='{"is_pic_info":1,"rules":[{"fileid":"format.jpg","rule":"QRcode/cover/0"}]}'
            )
            print(response,data)
        """
        with open(LocalFilePath, 'rb') as fp:
            return self.ci_put_object(Bucket, fp, Key, EnableMD5, **kwargs)

    def ci_get_object_qrcode(self, Bucket, Key, Cover, BarType=0, **kwargs):
        """单文件CI下载接口，返回文件二维码信息

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Cover(int): 二维码覆盖功能.
        :param BarType(int): 二维码/条形码识别功能，将对识别出的二维码/条形码 覆盖马赛克. 取值为0,1,2:
                            0表示都识别
                            1表示识别二维码
                            2表示识别条形码
                            默认值0
        :param kwargs(dict): 设置下载的headers.
        :return(dict,dict): 操作返回的结果.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response, data = client.ci_get_object_qrcode(
                Bucket='bucket',
                Key='test.txt',
                Cover=0
            )
            print(response,data)
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        if 'versionId' in headers:
            params['versionId'] = headers['versionId']
            del headers['versionId']

        params['ci-process'] = 'QRcode'
        params['cover'] = Cover
        params['bar-type'] = BarType
        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)

        logger.info("get object, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        response = dict(**rt.headers)
        data = xml_to_dict(rt.content)
        return response, data

    def ci_auditing_submit_common(self, Bucket, Key, DetectType, Type, Url=None, BizType=None, Conf={}, Input=None, UserInfo=None, DataId=None, RequestType=None, StorageConf=None, Encryption=None, **kwargs):
        """通用提交审核任务接口 https://cloud.tencent.com/document/product/460/46427

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param DetectType(int): 内容识别标志,位计算 1:porn, 2:terrorist, 4:politics, 8:ads, 16: Illegal, 32:Abuse
        :param Type(string): 审核类型，video:视频，text：文本，audio：音频，docment：文档。
        :param Url(string): Url, 支持非cos上的文件
        :param Conf(dic): 审核的个性化配置
        :param Input(dic): Input的个性化配置，dict类型，可跟restful api对应查询
        :param BizType(string): 审核策略的唯一标识，由后台自动生成，在控制台中对应为Biztype值.
        :param UserInfo(dict): 用户业务字段.
        :param DataId(string): 该字段在审核结果中会返回原始内容，长度限制为512字节。您可以使用该字段对待审核的数据进行唯一业务标识。
        :param StorageConf(dict): 包含直播流转存的配置信息。
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 下载成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 识别cos上的视频
            response = client.ci_auditing_submit_common(
                Bucket='bucket',
                DetectType=CiDetectType.PORN | CiDetectType.POLITICS,
                Key='test.mp4',
                Type='video'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        if DetectType is not None:
            detect_type = CiDetectType.get_detect_type_str(DetectType)
            Conf['DetectType'] = detect_type
        request = {
            'Input': {},
            'Conf': Conf
        }
        if BizType:
            request['Conf']['BizType'] = BizType

        if Key:
            request['Input']['Object'] = Key
        if Url:
            request['Input']['Url'] = Url

        if Input:
            request['Input'] = Input
        if UserInfo:
            request['Input']['UserInfo'] = UserInfo
        if DataId:
            request['Input']['DataId'] = DataId
        if Encryption:
            request['Input']['Encryption'] = Encryption
        if RequestType:
            request['Type'] = RequestType
        if StorageConf:
            request['StorageConf'] = StorageConf
        xml_request = format_xml(data=request, root='Request')
        headers['Content-Type'] = 'application/xml'

        path = Type + '/auditing'
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.debug("ci auditing {type} job submit, url=:{url} ,headers=:{headers}, params=:{params}, request=:{request}, ci_endpoint=:{ci_endpoint}".format(
            type=Type,
            url=url,
            headers=headers,
            params=params,
            request=request,
            ci_endpoint=self._conf._endpoint_ci))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_request,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        logger.debug("ci auditing rsp:%s", rt.content)
        data = xml_to_dict(rt.content)

        return data

    def ci_auditing_query_common(self, Bucket, Type, JobID, **kwargs):
        """通用查询审核任务接口 https://cloud.tencent.com/document/product/460/46926

        :param Bucket(string): 存储桶名称.
        :param Type(string): 审核类型，video:视频，text：文本，audio：音频，docment：文档。
        :param JobID(string): 任务id.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 下载成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询视频审核返回的结果
            response = client.ci_auditing_video_query(
                Bucket='bucket',
                JobID='v11122zxxxazzz',
                Type='video'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = Type + '/auditing/' + JobID
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("query ci auditing {type} result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            type=Type,
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        logger.debug("query ci auditing:%s", rt.content)
        data = xml_to_dict(rt.content)

        return data

    def ci_auditing_video_submit(self, Bucket, Key, DetectType=None, Url=None, Callback=None, CallbackVersion='Simple',
                                 CallbackType=None, DetectContent=0, Mode='Interval', Count=100, TimeInterval=1.0,
                                 BizType=None, DataId=None, UserInfo=None, Freeze=None, Encryption=None, **kwargs):
        """提交video审核任务接口 https://cloud.tencent.com/document/product/460/46427

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Url(string): 支持直接传非cos上url过来审核
        :param DetectType(int): 内容识别标志,位计算 1:porn, 8:ads
        :param Callback(string): 回调地址，以http://或者https://开头的地址。
        :param CallbackVersion(string): 回调内容的结构，有效值：Simple（回调内容包含基本信息）、Detail（回调内容包含详细信息）。默认为 Simple。
        :param CallbackType(int): 回调片段类型，有效值：1（回调全部截帧和音频片段）、2（回调违规截帧和音频片段）。默认为 1。
        :param DetectContent(int): 用于指定是否审核视频声音，当值为0时：表示只审核视频画面截图；值为1时：表示同时审核视频画面截图和视频声音。默认值为0。
        :param Mode(string): 截帧模式。Interval 表示间隔模式；Average 表示平均模式；Fps 表示固定帧率模式。
                            Interval 模式：TimeInterval，Count 参数生效。当设置 Count，未设置 TimeInterval 时，表示截取所有帧，共 Count 张图片。
                            Average 模式：Count 参数生效。表示整个视频，按平均间隔截取共 Count 张图片。
                            Fps 模式：TimeInterval 表示每秒截取多少帧，Count 表示共截取多少帧。
        :param Count(int): 视频截帧数量，范围为(0, 10000]。
        :param TimeInterval(float): 视频截帧频率，范围为(0, 60]，单位为秒，支持 float 格式，执行精度精确到毫秒。
        :param BizType(string): 审核策略的唯一标识，由后台自动生成，在控制台中对应为Biztype值.
        :param UserInfo(dict): 用户业务字段.
        :param DataId(string): 该字段在审核结果中会返回原始内容，长度限制为512字节。您可以使用该字段对待审核的数据进行唯一业务标识。
        :param Freeze(dict): 自动冻结配置项，可配置指定审核分数的结果进行自动冻结。
                            PornScore(int): 取值为[0,100]，表示当色情审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
                            AdsScore(int): 取值为[0,100]，表示当广告审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
        :param Encryption(dict):
                            Algorithm(string): 当前支持`aes-256-ctr、aes-256-cfb、aes-256-ofb、aes-192-ctr、aes-192-cfb、aes-192-ofb、aes-128-ctr、aes-128-cfb、aes-128-ofb`，不区分大小写。以`aes-256-ctr`为例，`aes`代表加密算法，`256`代表密钥长度，`ctr`代表加密模式。
                            Key(string): 文件加密使用的密钥的值，需进行 Base64 编码。当KeyType值为1时，需要将Key进行指定的加密后再做Base64 编码。Key的长度与使用的算法有关，详见`Algorithm`介绍，如：使用`aes-256-ctr`算法时，需要使用256位密钥，即32个字节。
                            IV(string): 初始化向量，需进行 Base64 编码。AES算法要求IV长度为128位，即16字节。
                            KeyId(string): 当KeyType值为1时，该字段表示RSA加密密钥的版本号，当前支持`1.0`。默认值为`1.0`。
                            KeyType(int): 指定加密算法的密钥（参数Key）的传输模式，有效值：0（明文传输）、1（RSA密文传输，使用OAEP填充模式），默认值为0。
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 任务提交成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 识别cos上的视频
            response = client.ci_auditing_video_submit(
                Bucket='bucket',
                DetectType=CiDetectType.PORN,
                BizType='xxxxx',
                Key='test.mp4'
            )
            print response
        """

        conf = {
            'Snapshot': {
                'Mode': Mode,
                'TimeInterval': TimeInterval,
                'Count': Count,
            },
            'DetectContent': DetectContent
        }

        if Callback:
            conf['Callback'] = Callback

        if CallbackVersion:
            conf['CallbackVersion'] = CallbackVersion

        if CallbackType:
            conf['CallbackType'] = CallbackType

        if Freeze:
            conf['Freeze'] = Freeze
        return self.ci_auditing_submit_common(
            Bucket=Bucket,
            Key=Key,
            Type='video',
            BizType=BizType,
            Conf=conf,
            Url=Url,
            DetectType=DetectType,
            UserInfo=UserInfo,
            DataId=DataId,
            Encryption=Encryption,
            **kwargs
        )

    def ci_auditing_video_query(self, Bucket, JobID, **kwargs):
        """查询video审核任务接口 https://cloud.tencent.com/document/product/460/46926

        :param Bucket(string): 存储桶名称.
        :param JobID(string): 任务id.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询视频审核返回的结果
            response = client.ci_auditing_video_query(
                Bucket='bucket',
                JobID='v11122zxxxazzz'
            )
            print response
        """

        data = self.ci_auditing_query_common(
            Bucket=Bucket,
            JobID=JobID,
            Type='video',
            **kwargs
        )

        if 'JobsDetail' in data:
            format_dict(data['JobsDetail'], ['Snapshot', 'AudioSection'])
            if 'Snapshot' in data['JobsDetail']:
                for snapshot in data['JobsDetail']['Snapshot']:
                    if 'PornInfo' in snapshot:
                        format_dict(snapshot['PornInfo'], ['OcrResults', 'ObjectResults'])
                        if 'OcrResults' in snapshot['PornInfo']:
                            for ocrResult in snapshot['PornInfo']['OcrResults']:
                                format_dict(ocrResult, ['Keywords'])
                    if 'TerrorismInfo' in snapshot:
                        format_dict(snapshot['TerrorismInfo'], ['OcrResults', 'ObjectResults'])
                        if 'OcrResults' in snapshot['TerrorismInfo']:
                            for ocrResult in snapshot['TerrorismInfo']['OcrResults']:
                                format_dict(ocrResult, ['Keywords'])
                    if 'PoliticsInfo' in snapshot:
                        format_dict(snapshot['PoliticsInfo'], ['OcrResults', 'ObjectResults'])
                        if 'OcrResults' in snapshot['PoliticsInfo']:
                            for ocrResult in snapshot['PoliticsInfo']['OcrResults']:
                                format_dict(ocrResult, ['Keywords'])
                    if 'AdsInfo' in snapshot:
                        format_dict(snapshot['AdsInfo'], ['OcrResults', 'ObjectResults'])
                        if 'OcrResults' in snapshot['AdsInfo']:
                            for ocrResult in snapshot['AdsInfo']['OcrResults']:
                                format_dict(ocrResult, ['Keywords'])
            if 'AudioSection' in data['JobsDetail']:
                for audioSection in data['JobsDetail']['AudioSection']:
                    if 'PornInfo' in audioSection:
                        format_dict(audioSection['PornInfo'], ['Keywords'])
                    if 'TerrorismInfo' in audioSection:
                        format_dict(audioSection['TerrorismInfo'], ['Keywords'])
                    if 'PoliticsInfo' in audioSection:
                        format_dict(audioSection['PoliticsInfo'], ['Keywords'])
                    if 'AdsInfo' in audioSection:
                        format_dict(audioSection['AdsInfo'], ['Keywords'])

        return data

    def ci_auditing_audio_submit(self, Bucket, Key, DetectType=None, Url=None, Callback=None, CallbackVersion='Simple', BizType=None, UserInfo=None,
                                 DataId=None, CallbackType=None, Freeze=None, **kwargs):
        """提交音频审核任务接口 https://cloud.tencent.com/document/product/460/53395

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Url(string): 支持直接传非cos上url过来审核
        :param DetectType(int): 内容识别标志,位计算 1:porn, 8:ads
        :param Callback(string): 回调地址，以http://或者https://开头的地址。
        :param CallbackVersion(string): 回调内容的结构，有效值：Simple（回调内容包含基本信息）、Detail（回调内容包含详细信息）。默认为 Simple。
        :param BizType(string): 审核策略的唯一标识，由后台自动生成，在控制台中对应为Biztype值.
        :param UserInfo(dict): 用户业务字段.
        :param DataId(string): 该字段在审核结果中会返回原始内容，长度限制为512字节。您可以使用该字段对待审核的数据进行唯一业务标识。
        :param CallbackType(int): 回调片段类型，有效值：1（回调全部音频片段）、2（回调违规音频片段）。默认为 1。
        :param Freeze(dict): 可通过该字段，设置根据审核结果给出的不同分值，对音频文件进行自动冻结，仅当input中审核的音频为object时有效。
                             PornScore(int): 取值为[0,100]，表示当色情审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
                             AdsScore(int): 取值为[0,100]，表示当广告审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 任务提交成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 识别cos上的音频
            response = client.ci_auditing_audio_submit(
                Bucket='bucket',
                DetectType=CiDetectType.PORN | CiDetectType.POLITICS,
                Key='test.mp3'
            )
            print response
        """

        conf = {
        }

        if Callback:
            conf['Callback'] = Callback

        if CallbackVersion:
            conf['CallbackVersion'] = CallbackVersion

        if CallbackType:
            conf['CallbackType'] = CallbackType

        if Freeze:
            conf['Freeze'] = Freeze
        return self.ci_auditing_submit_common(
            Bucket=Bucket,
            Key=Key,
            Type='audio',
            BizType=BizType,
            Conf=conf,
            Url=Url,
            DetectType=DetectType,
            UserInfo=UserInfo,
            DataId=DataId,
            **kwargs
        )

    def ci_auditing_audio_query(self, Bucket, JobID, **kwargs):
        """查询音频审核任务接口 https://cloud.tencent.com/document/product/460/53396

        :param Bucket(string): 存储桶名称.
        :param JobID(string): 任务id.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询视频审核返回的结果
            response = client.ci_auditing_audio_query(
                Bucket='bucket',
                JobID='v11122zxxxazzz'
            )
            print response
        """

        data = self.ci_auditing_query_common(
            Bucket=Bucket,
            JobID=JobID,
            Type='audio',
            **kwargs
        )
        if 'JobsDetail' in data:
            format_dict(data['JobsDetail'], ['Section'])
            if 'Section' in data['JobsDetail']:
                for section in data['JobsDetail']['Section']:
                    if 'PornInfo' in section:
                        format_dict(section['PornInfo'], ['Keywords'])
                    if 'TerrorismInfo' in section:
                        format_dict(section['TerrorismInfo'], ['Keywords'])
                    if 'PoliticsInfo' in section:
                        format_dict(section['PoliticsInfo'], ['Keywords'])
                    if 'AdsInfo' in section:
                        format_dict(section['AdsInfo'], ['Keywords'])

        return data

    def ci_auditing_text_submit(self, Bucket, Key=None, DetectType=None, Content=None,
        Callback=None,  BizType=None, Url=None, UserInfo=None, DataId=None, CallbackVersion=None, CallbackType=None, Freeze=None, **kwargs):
        """提交文本审核任务接口 https://cloud.tencent.com/document/product/460/56285

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Url(string): 支持直接传非cos上url过来审核
        :param Content(string): 当传入的内容为纯文本信息，原文长度不能超过10000个 utf8 编码字符。若超出长度限制，接口将会报错。
        :param DetectType(int): 内容识别标志,位计算 1:porn, 8:ads
        :param Callback(string): 回调地址，以http://或者https://开头的地址。
        :param BizType(string): 审核策略的唯一标识，由后台自动生成，在控制台中对应为Biztype值.
        :param UserInfo(dict): 用户业务字段.
        :param DataId(string): 该字段在审核结果中会返回原始内容，长度限制为512字节。您可以使用该字段对待审核的数据进行唯一业务标识。
        :param CallbackVersion(string): 回调内容的结构，有效值：Simple（回调内容包含基本信息）、Detail（回调内容包含详细信息）。默认为 Simple。
        :param CallbackType(int): 回调片段类型，有效值：1（回调全部文本片段）、2（回调违规文本片段）。默认为 1。
        :param Freeze(dict): 可通过该字段，设置根据审核结果给出的不同分值，对文本文件进行自动冻结，仅当 input 中审核的文本为 object 时有效。
                            PornScore(int): 取值为[0,100]，表示当色情审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
                            AdsScore(int): 取值为[0,100]，表示当广告审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
                            IllegalScore(int): 取值为[0,100]，表示当违法审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
                            AbuseScore(int): 取值为[0,100]，表示当谩骂审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 任务提交成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 识别cos上的文本
            response = client.ci_auditing_text_submit(
                Bucket='bucket',
                DetectType=CiDetectType.PORN,
                BizType='xxxx',
                Key='test.txt'
            )
            print response
        """

        Input = {}
        if Key:
            Input['Object'] = Key
        if Url:
            Input['Url'] = Url
        if Content:
            Input['Content'] = base64.b64encode(Content).decode('UTF-8')

        conf = {
        }

        if Callback:
            conf['Callback'] = Callback
        if CallbackVersion:
            conf['CallbackVersion'] = CallbackVersion
        if CallbackType:
            conf['CallbackType'] = CallbackType
        if Freeze:
            conf['Freeze'] = Freeze
        data = self.ci_auditing_submit_common(
            Bucket=Bucket,
            Key=Key,
            Type='text',
            BizType=BizType,
            Conf=conf,
            DetectType=DetectType,
            Input=Input,
            UserInfo=UserInfo,
            DataId=DataId,
            **kwargs
        )

        if 'JobsDetail' in data:
            format_dict(data['JobsDetail'], ['Section'])

        return data

    def ci_auditing_text_query(self, Bucket, JobID, **kwargs):
        """查询文本审核任务接口 https://cloud.tencent.com/document/product/460/56284

        :param Bucket(string): 存储桶名称.
        :param JobID(string): 任务id.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询文本审核返回的结果
            response = client.ci_auditing_text_query(
                Bucket='bucket',
                JobID='v11122zxxxazzz'
            )
            print response
        """

        data = self.ci_auditing_query_common(
            Bucket=Bucket,
            JobID=JobID,
            Type='text',
            **kwargs
        )
        if 'JobsDetail' in data:
            format_dict(data['JobsDetail'], ['Section'])
        return data

    def ci_auditing_document_submit(self, Bucket, Url=None, DetectType=None, Key=None, Type=None,
        Callback=None,  BizType=None, UserInfo=None, DataId=None, CallbackType=None, Freeze=None, **kwargs):
        """提交文档审核任务接口 https://cloud.tencent.com/document/product/460/59380

        :param Bucket(string): 存储桶名称.
        :param Url(string): 文档文件的链接地址，例如 http://www.example.com/doctest.doc
        :param DetectType(int): 内容识别标志,位计算 1:porn, 8:ads
        :param Key(string): 存储在 COS 存储桶中的文件名称，例如在目录 test 中的文件test.doc，则文件名称为 test/test. Key 和 Url 只能选择其中一种。
        :param Type(string): 指定文档文件的类型，如未指定则默认以文件的后缀为类型。
                             如果文件没有后缀，该字段必须指定，否则会审核失败。例如：doc、docx、ppt、pptx 等
        :param Callback(string): 回调地址，以http://或者https://开头的地址。
        :param CallbackType(int): 回调片段类型，有效值：1（回调全部音频片段）、2（回调违规音频片段）。默认为1。
        :param BizType(string): 审核策略的唯一标识，由后台自动生成，在控制台中对应为Biztype值.
        :param UserInfo(dict): 用户业务字段.
        :param DataId(string): 该字段在审核结果中会返回原始内容，长度限制为512字节。您可以使用该字段对待审核的数据进行唯一业务标识。
        :param Freeze(dict): 可通过该字段，设置根据审核结果给出的不同分值，对文档进行自动冻结。仅当 input 中审核的文档为 object 时有效。
                               PornScore(int): 取值为[0,100]，表示当色情审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
                               AdsScore(int): 取值为[0,100]，表示当广告审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
        :param kwargs(dict): 设置请求的headers.
        :return(dict):任务提交成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 识别cos上的文本
            response = client.ci_auditing_document_submit(
                Bucket='bucket',
                DetectType=CiDetectType.PORN,
                Url='http://www.example.com/doctest.doc'
            )
            print response
        """

        Input = {}
        if Url is not None:
            Input['Url'] = Url
        if Key is not None:
            Input['Object'] = Key
        if Type:
            Input['Type'] = Type

        conf = {
        }

        if Callback:
            conf['Callback'] = Callback
        if CallbackType:
            conf['CallbackType'] = CallbackType
        if Freeze:
            conf['Freeze'] = Freeze

        return self.ci_auditing_submit_common(
            Bucket=Bucket,
            Key='',
            Type='document',
            BizType=BizType,
            Conf=conf,
            DetectType=DetectType,
            Input=Input,
            UserInfo=UserInfo,
            DataId=DataId,
            **kwargs
        )

    def ci_auditing_document_query(self, Bucket, JobID, **kwargs):
        """查询文档审核任务接口 https://cloud.tencent.com/document/product/460/59383

        :param Bucket(string): 存储桶名称.
        :param JobID(string): 任务id.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询文本审核返回的结果
            response = client.ci_auditing_document_query(
                Bucket='bucket',
                JobID='v11122zxxxazzz'
            )
            print response
        """

        data = self.ci_auditing_query_common(
            Bucket=Bucket,
            JobID=JobID,
            Type='document',
            **kwargs
        )

        if 'JobsDetail' in data and 'PageSegment' in data['JobsDetail'] and 'Results' in data['JobsDetail']['PageSegment']:
            format_dict(data['JobsDetail']['PageSegment'], ['Results'])
            for resultsItem in data['JobsDetail']['PageSegment']['Results']:
                if 'PornInfo' in resultsItem:
                    format_dict(resultsItem['PornInfo'], ['OcrResults', 'ObjectResults'])
                    if 'OcrResults' in resultsItem['PornInfo']:
                        format_dict_or_list(resultsItem['PornInfo']['OcrResults'], ['Keywords'])
                if 'TerrorismInfo' in resultsItem:
                    format_dict(resultsItem['TerrorismInfo'], ['OcrResults', 'ObjectResults'])
                    if 'OcrResults' in resultsItem['TerrorismInfo']:
                        format_dict_or_list(resultsItem['TerrorismInfo']['OcrResults'], ['Keywords'])
                if 'PoliticsInfo' in resultsItem:
                    format_dict(resultsItem['PoliticsInfo'], ['OcrResults', 'ObjectResults'])
                    if 'OcrResults' in resultsItem['PoliticsInfo']:
                        format_dict_or_list(resultsItem['PoliticsInfo']['OcrResults'], ['Keywords'])
                if 'AdsInfo' in resultsItem:
                    format_dict(resultsItem['AdsInfo'], ['OcrResults', 'ObjectResults'])
                    if 'OcrResults' in resultsItem['AdsInfo']:
                        format_dict_or_list(resultsItem['AdsInfo']['OcrResults'], ['Keywords'])

        return data

    def ci_auditing_html_submit(self, Bucket, Url, DetectType=None, ReturnHighlightHtml=False, Callback=None,  BizType=None, UserInfo=None, DataId=None, **kwargs):
        """提交网页审核任务接口 https://cloud.tencent.com/document/product/436/63958

        :param Bucket(string): 存储桶名称.
        :param Url(string): 文档文件的链接地址，例如 http://www.example.com/doctest.doc
        :param DetectType(int): 内容识别标志,位计算 1:porn, 8:ads
        :param ReturnHighlightHtml(bool): 指定是否需要高亮展示网页内的违规文本，查询及回调结果时会根据此参数决定是否返回高亮展示的
                                            html 内容。取值为 true 或者 false，默认为 false。
        :param Callback(string): 回调地址，以http://或者https://开头的地址。
        :param BizType(string): 审核策略的唯一标识，由后台自动生成，在控制台中对应为Biztype值.
        :param UserInfo(dict): 用户业务字段.
        :param DataId(string): 该字段在审核结果中会返回原始内容，长度限制为512字节。您可以使用该字段对待审核的数据进行唯一业务标识。
        :param kwargs(dict): 设置请求的headers.
        :return(dict):任务提交成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 识别网页
            response = client.ci_auditing_html_submit(
                Bucket='bucket',
                DetectType=CiDetectType.PORN,
                Url='http://www.example.com/index.html'
            )
            print response
        """

        Input = {}
        if Url is not None:
            Input['Url'] = Url

        conf = {
        }

        if Callback:
            conf['Callback'] = Callback
        if ReturnHighlightHtml:
            conf['ReturnHighlightHtml'] = ReturnHighlightHtml

        return self.ci_auditing_submit_common(
            Bucket=Bucket,
            Key='',
            Type='webpage',
            BizType=BizType,
            Conf=conf,
            DetectType=DetectType,
            Input=Input,
            UserInfo=UserInfo,
            DataId=DataId,
            **kwargs
        )

    def ci_auditing_html_query(self, Bucket, JobID, **kwargs):
        """查询网页审核任务接口 https://cloud.tencent.com/document/product/436/63959

        :param Bucket(string): 存储桶名称.
        :param JobID(string): 任务id.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询网页审核返回的结果
            response = client.ci_auditing_html_query(
                Bucket='bucket',
                JobID='v11122zxxxazzz'
            )
            print response
        """

        data = self.ci_auditing_query_common(
            Bucket=Bucket,
            JobID=JobID,
            Type='webpage',
            **kwargs
        )

        if 'JobsDetail' in data and 'ImageResults' in data['JobsDetail'] and 'Results' in data['JobsDetail']['ImageResults']:
            format_dict(data['JobsDetail']['ImageResults'], ['Results'])
            for resultsItem in data['JobsDetail']['ImageResults']['Results']:
                if 'PornInfo' in resultsItem:
                    format_dict(resultsItem['PornInfo'], ['OcrResults'])
                    if 'OcrResults' in resultsItem['PornInfo']:
                        format_dict_or_list(resultsItem['PornInfo']['OcrResults'], ['Keywords'])
                if 'TerrorismInfo' in resultsItem:
                    format_dict(resultsItem['TerrorismInfo'], ['OcrResults'])
                    if 'OcrResults' in resultsItem['TerrorismInfo']:
                        format_dict_or_list(resultsItem['TerrorismInfo']['OcrResults'], ['Keywords'])
                if 'PoliticsInfo' in resultsItem:
                    format_dict(resultsItem['PoliticsInfo'], ['OcrResults', 'ObjectResults'])
                    if 'OcrResults' in resultsItem['PoliticsInfo']:
                        format_dict_or_list(resultsItem['PoliticsInfo']['OcrResults'], ['Keywords'])
                if 'AdsInfo' in resultsItem:
                    format_dict(resultsItem['AdsInfo'], ['OcrResults'])
                    if 'OcrResults' in resultsItem['AdsInfo']:
                        format_dict_or_list(resultsItem['AdsInfo']['OcrResults'], ['Keywords'])

        if 'JobsDetail' in data and 'TextResults' in data['JobsDetail'] and 'Results' in data['JobsDetail']['TextResults']:
            format_dict(data['JobsDetail']['TextResults'], ['Results'])

        return data

    def ci_auditing_image_batch(self, Bucket, Input, DetectType=None, BizType=None, Async=0, Callback=None, Freeze=None, **kwargs):
        """图片同步批量审核接口 https://cloud.tencent.com/document/product/436/63593

        :param Bucket(string): 存储桶名称.
        :param Input(dict array): 需要审核的图片信息,每个array元素为dict类型，支持的参数如下:
                            Object: 存储在 COS 存储桶中的图片文件名称，例如在目录 test 中的文件 image.jpg，则文件名称为 test/image.jpg。
                                传入多个时仅一个生效，按 Content，Object， Url 顺序。
                            Url: 图片文件的链接地址，例如 http://a-1250000.cos.ap-shanghai.tencentcos.cn/image.jpg。
                                传入多个时仅一个生效，按 Content，Object， Url 顺序。
                            Content: 图片文件的内容，需要先经过 base64 编码。Content，Object 和 Url 只能选择其中一种，传入多个时仅一个生效，按 Content，Object， Url 顺序。
                            Interval: 截帧频率，GIF 图检测专用，默认值为5，表示从第一帧（包含）开始每隔5帧截取一帧
                            MaxFrames: 最大截帧数量，GIF 图检测专用，默认值为5，表示只截取 GIF 的5帧图片进行审核，必须大于0
                            DataId: 图片标识，该字段在结果中返回原始内容，长度限制为512字节
                            LargeImageDetect: 对于超过大小限制的图片是否进行压缩后再审核，取值为： 0（不压缩），1（压缩）。默认为0。
                                注：压缩最大支持32M的图片，且会收取压缩费用。
                            DataId: 图片标识，该字段在结果中返回原始内容，长度限制为512字节
                            UserInfo: 用户业务字段。
                            Encryption(dict): 文件加密信息。如果图片未做加密则不需要使用该字段，如果设置了该字段，则会按设置的信息解密后再做审核。
                                            Algorithm(string): 当前支持`aes-256-ctr、aes-256-cfb、aes-256-ofb、aes-192-ctr、aes-192-cfb、aes-192-ofb、aes-128-ctr、aes-128-cfb、aes-128-ofb`，不区分大小写。以`aes-256-ctr`为例，`aes`代表加密算法，`256`代表密钥长度，`ctr`代表加密模式。
                                            Key(string): 文件加密使用的密钥的值，需进行 Base64 编码。当KeyType值为1时，需要将Key进行指定的加密后再做Base64 编码。Key的长度与使用的算法有关，详见`Algorithm`介绍，如：使用`aes-256-ctr`算法时，需要使用256位密钥，即32个字节。
                                            IV(string): 初始化向量，需进行 Base64 编码。AES算法要求IV长度为128位，即16字节。
                                            KeyId(string): 当KeyType值为1时，该字段表示RSA加密密钥的版本号，当前支持`1.0`。默认值为`1.0`。
                                            KeyType(int): 指定加密算法的密钥（参数Key）的传输模式，有效值：0（明文传输）、1（RSA密文传输，使用OAEP填充模式），默认值为0。
        :param DetectType(int): 内容识别标志,位计算 1:porn, 8:ads
        :param BizType(string): 审核策略的唯一标识，由后台自动生成，在控制台中对应为Biztype值.
        :param Async(string): 是否异步进行审核，0：同步返回结果，1：异步进行审核。默认值为 0。
        :param Callback(string): 审核结果（Detail版本）以回调形式发送至您的回调地址，异步审核时生效，支持以 http:// 或者 https:// 开头的地址，例如：http://www.callback.com。
        :param Freeze(dict): 可通过该字段，设置根据审核结果给出的不同分值，对图片进行自动冻结，仅当 input 中审核的图片为 object 时有效。
                            PornScore: 取值为[0,100]，表示当色情审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
                            AdsScore: 取值为[0,100]，表示当广告审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
        :param kwargs(dict): 设置请求的headers.
        :return(dict):任务提交成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 识别网页
            response = client.ci_auditing_image_batch(
                Bucket='bucket',
                DetectType=CiDetectType.PORN,
                Input=[{
                    Url='http://www.example.com/test.jpg',
                }]
            )
            print response
        """
        conf = {
        }

        if BizType:
            conf['BizType'] = BizType
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        params = format_values(params)

        if DetectType is not None:
            detect_type = CiDetectType.get_detect_type_str(DetectType)
            conf['DetectType'] = detect_type
        if Async == 0:
            conf['Async'] = Async
        if Callback is not None:
            conf["Callback"] = Callback
        if Freeze is not None:
            conf["Freeze"] = Freeze
        request = {
            'Input': Input,
            'Conf': conf
        }

        xml_request = format_xml(data=request, root='Request')
        headers['Content-Type'] = 'application/xml'

        path = 'image/auditing'
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci auditing {type} job submit, url=:{url} ,headers=:{headers}, params=:{params}, ci_endpoint=:{ci_endpoint}, xml_request=:{data}".format(
            type='image',
            url=url,
            headers=headers,
            params=params,
            ci_endpoint=self._conf._endpoint_ci,
            data=xml_request))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_request,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        logger.debug("ci auditing rsp:%s", rt.content)
        data = xml_to_dict(rt.content)

        if 'JobsDetail' in data:
            format_dict(data, ['JobsDetail'])
            for jobsDetail in data['JobsDetail']:
                if 'PornInfo' in jobsDetail:
                    format_dict(jobsDetail['PornInfo'], ['OcrResults'])
                    if 'OcrResults' in jobsDetail['PornInfo']:
                        format_dict_or_list(jobsDetail['PornInfo']['OcrResults'], ['Keywords'])
                if 'TerrorismInfo' in jobsDetail:
                    format_dict(jobsDetail['TerrorismInfo'], ['OcrResults'])
                    if 'OcrResults' in jobsDetail['TerrorismInfo']:
                        format_dict_or_list(jobsDetail['TerrorismInfo']['OcrResults'], ['Keywords'])
                if 'PoliticsInfo' in jobsDetail:
                    format_dict(jobsDetail['PoliticsInfo'], ['OcrResults', 'ObjectResults'])
                    if 'OcrResults' in jobsDetail['PoliticsInfo']:
                        format_dict_or_list(jobsDetail['PoliticsInfo']['OcrResults'], ['Keywords'])
                if 'AdsInfo' in jobsDetail:
                    format_dict(jobsDetail['AdsInfo'], ['OcrResults'])
                    if 'OcrResults' in jobsDetail['AdsInfo']:
                        format_dict_or_list(jobsDetail['AdsInfo']['OcrResults'], ['Keywords'])

        return data

    def ci_auditing_image_query(self, Bucket, JobID, **kwargs):
        """查询图片审核任务接口

        :param Bucket(string): 存储桶名称.
        :param JobID(string): 任务id.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询文本审核返回的结果
            response = client.ci_auditing_image_query(
                Bucket='bucket',
                JobID='v11122zxxxazzz'
            )
            print response
        """

        data = self.ci_auditing_query_common(
            Bucket=Bucket,
            JobID=JobID,
            Type='image',
            **kwargs
        )

        if 'JobsDetail' in data:
            jobsDetail = data['JobsDetail']
            if 'PornInfo' in jobsDetail:
                format_dict(jobsDetail['PornInfo'], ['OcrResults'])
                if 'OcrResults' in jobsDetail['PornInfo']:
                    format_dict_or_list(jobsDetail['PornInfo']['OcrResults'], ['Keywords'])
            if 'TerrorismInfo' in jobsDetail:
                format_dict(jobsDetail['TerrorismInfo'], ['OcrResults'])
                if 'OcrResults' in jobsDetail['TerrorismInfo']:
                    format_dict_or_list(jobsDetail['TerrorismInfo']['OcrResults'], ['Keywords'])
            if 'PoliticsInfo' in jobsDetail:
                format_dict(jobsDetail['PoliticsInfo'], ['OcrResults', 'ObjectResults'])
                if 'OcrResults' in jobsDetail['PoliticsInfo']:
                    format_dict_or_list(jobsDetail['PoliticsInfo']['OcrResults'], ['Keywords'])
            if 'AdsInfo' in jobsDetail:
                format_dict(jobsDetail['AdsInfo'], ['OcrResults'])
                if 'OcrResults' in jobsDetail['AdsInfo']:
                    format_dict_or_list(jobsDetail['AdsInfo']['OcrResults'], ['Keywords'])

        return data

    def ci_auditing_live_video_submit(self, Bucket, BizType, DetectType=None, Url=None, DataId=None, Callback=None, CallbackType=None,
                                      UserInfo=None, StorageConf=None, **kwargs):
        """提交直播流审核任务接口 https://cloud.tencent.com/document/product/460/46427

        :param Bucket(string): 存储桶名称.
        :param Url(string): 支持直接传非cos上url过来审核
        :param DetectType(int): 内容识别标志,位计算 1:porn, 8:ads
        :param DataId(string): 该字段在审核结果中会返回原始内容，长度限制为512字节。您可以使用该字段对待审核的数据进行唯一业务标识。
        :param Callback(string): 回调地址，以http://或者https://开头的地址。
        :param CallbackType(int): 回调片段类型，有效值：1（回调全部截帧和音频片段）、2（回调违规截帧和音频片段）。默认为 1。
        :param BizType(string): 审核策略的唯一标识，由后台自动生成，在控制台中对应为Biztype值.
        :param UserInfo(dict): 用户业务字段.
        :param StorageConf(dict): 包含直播流转存的配置信息。
                                Path(string): 表示直播流所要转存的路径，直播流的 ts 文件和 m3u8 文件将保存在本桶该目录下。
                                              m3u8 文件保存文件名为 Path/{$JobId}.m3u8，ts 文件的保存文件名为
                                              Path/{$JobId}-{$Realtime}.ts，其中 Realtime 为17位年月日时分秒毫秒时间。
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 任务提交成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 识别cos上的视频
            response = client.ci_auditing_live_video_submit(
                Bucket='bucket',
                DetectType=CiDetectType.PORN,
                BizType='xxxxx',
                Url='test.mp4'
            )
            print response
        """

        conf = {
        }

        if Callback:
            conf['Callback'] = Callback

        if CallbackType:
            conf['CallbackType'] = CallbackType

        return self.ci_auditing_submit_common(
            Bucket=Bucket,
            Type='video',
            Key=None,
            BizType=BizType,
            Conf=conf,
            Url=Url,
            DetectType=DetectType,
            RequestType='live_video',
            DataId=DataId,
            UserInfo=UserInfo,
            StorageConf=StorageConf,
            **kwargs
        )

    def ci_auditing_live_video_cancle(self, Bucket, JobID, **kwargs):
        """取消直播流审核任务接口 https://cloud.tencent.com/document/product/460/46926

        :param Bucket(string): 存储桶名称.
        :param JobID(string): 任务id.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 下载成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 取消直播流
            response = client.ci_auditing_live_video_cancle(
                Bucket='bucket',
                JobID='v11122zxxxazzz',
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = '/video/cancel_auditing/' + JobID
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("live video canlce result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        logger.debug("live video canlce:%s", rt.content)
        data = xml_to_dict(rt.content)

        return data

    def ci_auditing_virus_submit(self, Bucket, Key=None, Url=None, Callback=None, **kwargs):
        """提交病毒审核任务接口 https://cloud.tencent.com/document/product/460/63964

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Url(string): Url, 支持非cos上的文件
        :param Callback(string): 	检测结果回调通知到您设置的地址，支持以 http:// 或者 https:// 开头的地址，例如：http://www.callback.com。
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 下载成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 识别cos上的视频
            response = client.ci_auditing_virus_submit(
                Bucket='bucket',
                Key='test.mp4',
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        Conf = {
            'DetectType': 'Virus',
        }
        if Callback:
            Conf['Callback'] = Callback
        request = {
            'Input': {},
            'Conf': Conf
        }

        if Key:
            request['Input']['Object'] = Key
        if Url:
            request['Input']['Url'] = Url

        xml_request = format_xml(data=request, root='Request')
        headers['Content-Type'] = 'application/xml'

        path = '/virus/detect'
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci auditing Virus submit, url=:{url} ,headers=:{headers}, params=:{params}, ci_endpoint=:{ci_endpoint}".format(
            url=url,
            headers=headers,
            params=params,
            ci_endpoint=self._conf._endpoint_ci))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_request,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        logger.debug("ci auditing rsp:%s", rt.content)
        data = xml_to_dict(rt.content)

        return data

    def ci_auditing_virus_query(self, Bucket, JobID, **kwargs):
        """查询病毒审核任务接口 https://cloud.tencent.com/document/product/460/63965

        :param Bucket(string): 存储桶名称.
        :param JobID(string): 任务id.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 下载成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询视频审核返回的结果
            response = client.ci_auditing_video_query(
                Bucket='bucket',
                JobID='v11122zxxxazzz',
                Type='video'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = '/virus/detect/' + JobID
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("query ci auditing virus result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        logger.debug("query ci auditing:%s", rt.content)
        data = xml_to_dict(rt.content)

        # 格式化array的输出
        if 'JobsDetail' in data and 'DetectDetail' in data['JobsDetail']:
            format_dict(data['JobsDetail'], ['DetectDetail'])
            for detectItem in data['JobsDetail']['DetectDetail']:
                if 'Result' in detectItem:
                    format_dict(detectItem, ['Result'])

        return data

    def ci_auditing_report_badcase(self, Bucket, ContentType, Label, SuggestedLabel, Text=None, Url=None, JobId=None, ModerationTime=None, **kwargs):
        """审核结果反馈

        :param Bucket(string): 存储桶名称.
        :param ContentType(int): 需要反馈的数据类型，取值为：1-文本，2-图片。
        :param Label(string): 审核给出的有问题的结果标签。
        :param SuggestedLabel(string): 期望的正确处置标签，正常则填Normal。
        :param Text(dic): 文本的Badcase，需要填写base64的文本内容，ContentType为1时必填。
        :param Url(dic): 图片的Badcase，需要填写图片的url链接，ContentType为2时必填。
        :param JobId(string): 该Case对应的审核任务ID，有助于定位审核记录。
        :param ModerationTime(dict): 该Case的审核时间，有助于定位审核记录。格式为 2021-08-07T12:12:12+08:00
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 下载成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 识别cos上的视频
            response = client.ci_auditing_report_badcase(
                Bucket='bucket',
                ContentType=1,
                Label='test.mp4',
                SuggestedLabel='Normal'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        request = {
            'ContentType': ContentType,
            'Label': Label,
            'SuggestedLabel': SuggestedLabel
        }
        if Text:
            request['Text'] = Text
        if Url:
            request['Url'] = Url
        if JobId:
            request['JobId'] = JobId
        if ModerationTime:
            request['ModerationTime'] = ModerationTime

        xml_request = format_xml(data=request, root='Request')
        headers['Content-Type'] = 'application/xml'

        path = '/report/badcase'
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.debug("ci_auditing_report_badcase, url=:{url} ,headers=:{headers}, params=:{params}, request=:{request}, ci_endpoint=:{ci_endpoint}".format(
            url=url,
            headers=headers,
            params=params,
            request=request,
            ci_endpoint=self._conf._endpoint_ci))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_request,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        logger.debug("ci auditing rsp:%s", rt.content)
        data = xml_to_dict(rt.content)

        return data

    def ci_get_media_bucket(self, Regions='', BucketName='', BucketNames='', PageNumber='', PageSize='', **kwargs):
        """查询媒体处理开通状态接口 https://cloud.tencent.com/document/product/436/48988

        :param Regions(string): 地域信息，例如 ap-shanghai、ap-beijing，若查询多个地域以“,”分隔字符串
        :param BucketName(string): 存储桶名称前缀，前缀搜索
        :param BucketNames(string): 存储桶名称，以“,”分隔，支持多个存储桶，精确搜索
        :param PageNumber(string): 第几页
        :param PageSize(string): 每页个数
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询媒体处理队列接口
            response = client.ci_get_media_bucket(
                Regions='ap-chongqing,ap-shanghai',
                BucketName='demo',
                BucketNames='demo-1253960454,demo1-1253960454',
                PageNumber='2'，
                PageSize='3',
            )
            print response
        """
        return self.ci_get_bucket(Regions=Regions, BucketName=BucketName,
                                  BucketNames=BucketNames, PageNumber=PageNumber,
                                  PageSize=PageSize, **kwargs)

    def ci_get_bucket(self, Regions='', BucketName='', BucketNames='', PageNumber='', PageSize='', Path = '/mediabucket', **kwargs):
        """查询服务开通状态接口

        :param Regions(string): 地域信息，例如 ap-shanghai、ap-beijing，若查询多个地域以“,”分隔字符串
        :param BucketName(string): 存储桶名称前缀，前缀搜索
        :param BucketNames(string): 存储桶名称，以“,”分隔，支持多个存储桶，精确搜索
        :param PageNumber(string): 第几页
        :param PageSize(string): 每页个数
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询媒体处理队列接口
            response = client.ci_get_bucket(
                Regions='ap-chongqing,ap-shanghai',
                BucketName='demo',
                BucketNames='demo-1253960454,demo1-1253960454',
                PageNumber='2'，
                PageSize='3',
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['regions'] = Regions
        params['bucketNames'] = BucketNames
        params['bucketName'] = BucketName
        params['pageNumber'] = PageNumber
        params['pageSize'] = PageSize

        params = format_values(params)

        path = Path
        url = self._conf.uri(bucket=None, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_get_bucket result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=None,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        if path == '/picbucket':
            format_dict(data, ['PicBucketList'])
        else:
            format_dict(data, ['MediaBucketList'])
        return data

    def ci_get_media_queue(self, Bucket, State='All', QueueIds='', PageNumber='', PageSize='', UrlPath='/queue', **kwargs):
        """查询媒体处理队列接口 https://cloud.tencent.com/document/product/436/54045

        :param Bucket(string): 存储桶名称.
        :param QueueIds(string): 队列 ID，以“,”符号分割字符串.
        :param State(string): 队列状态
        :param PageNumber(string): 第几页
        :param PageSize(string): 每页个数
        :param UrlPath(string): 请求URL路径，无需主动设置
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询媒体处理队列接口
            response = client.ci_get_media_queue(
                Bucket='bucket'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['queueIds'] = QueueIds
        params['state'] = State
        params['pageNumber'] = PageNumber
        params['pageSize'] = PageSize

        params = format_values(params)

        path = UrlPath
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("get_media_queue result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['QueueList'])
        return data

    def ci_update_media_queue(self, Bucket, QueueId, Request={}, UrlPath="/queue/", **kwargs):
        """ 更新媒体处理队列接口 https://cloud.tencent.com/document/product/436/54046

        :param Bucket(string): 存储桶名称.
        :param QueueId(string): 队列ID.
        :param Request(dict): 更新队列配置请求体.
        :param UrlPath(string): 请求URL路径，无需主动设置
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_update_media_queue(
                Bucket='bucket',
                QueueId='',
                Request={},
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        xml_config = format_xml(data=Request, root='Request')
        path = UrlPath + QueueId
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("update_media_queue result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['Queue'])
        return data

    def ci_open_pic_bucket(self, Bucket, **kwargs):
        """ 开通图片处理异步服务 https://cloud.tencent.com/document/product/460/95749

        :param Bucket(string) 存储桶名称.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果, dict类型.

        . code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token) # 获取配置对象
            client = CosS3Client(config)
            # 开通图片处理异步服务
            response, data = client.ci_open_pic_bucket(
                Bucket='bucket')
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = "/" + "picbucket"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)

        logger.info("ci_open_pic_bucket result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='POST',
            url=url,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response:
            if response['Content-Type'] == 'application/xml' and 'Content-Length' in response and \
                response['Content-Length'] != 0:
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data

    def ci_get_pic_bucket(self, Regions='', BucketName='', BucketNames='', PageNumber='', PageSize='', **kwargs):
        """查询图片异步处理开通状态接口

        :param Regions(string): 地域信息，例如 ap-shanghai、ap-beijing，若查询多个地域以“,”分隔字符串
        :param BucketName(string): 存储桶名称前缀，前缀搜索
        :param BucketNames(string): 存储桶名称，以“,”分隔，支持多个存储桶，精确搜索
        :param PageNumber(string): 第几页
        :param PageSize(string): 每页个数
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询媒体处理队列接口
            response = client.ci_get_pic_bucket(
                Regions='ap-chongqing,ap-shanghai',
                BucketName='demo',
                BucketNames='demo-1253960454,demo1-1253960454',
                PageNumber='2'，
                PageSize='3',
            )
            print response
        """
        return self.ci_get_bucket(Regions=Regions, BucketName=BucketName,
                                  BucketNames=BucketNames, PageNumber=PageNumber,
                                  PageSize=PageSize, Path='/picbucket', **kwargs)

    def ci_close_pic_bucket(self, Bucket, **kwargs):
        """ 关闭图片处理异步服务 https://cloud.tencent.com/document/product/460/95751

        :param Bucket(string) 存储桶名称.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果, dict类型.

        . code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token) # 获取配置对象
            client = CosS3Client(config)
            # 关闭图片处理异步服务
            response, data = client.ci_close_pic_bucket(
                Bucket='bucket')
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = "/" + "picbucket"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)

        logger.info("ci_close_pic_bucket result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='DELETE',
            url=url,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response:
            if response['Content-Type'] == 'application/xml' and 'Content-Length' in response and \
                response['Content-Length'] != 0:
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data

    def ci_update_media_pic_queue(self, Bucket, QueueId, Request={}, **kwargs):
        """ 更新图片处理队列接口

        :param Bucket(string): 存储桶名称.
        :param QueueId(string): 队列ID.
        :param Request(dict): 更新队列配置请求体.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_update_media_pic_queue(
                Bucket='bucket',
                QueueId='',
                Request={},
            )
            print response
        """
        return self.ci_update_media_queue(Bucket=Bucket, QueueId=QueueId,
                                          Request=Request, UrlPath="/picqueue/", **kwargs)

    def ci_get_media_pic_queue(self, Bucket, State='All', QueueIds='', PageNumber='', PageSize='', **kwargs):
        """查询图片处理队列接口

        :param Bucket(string): 存储桶名称.
        :param QueueIds(string): 队列 ID，以“,”符号分割字符串.
        :param State(string): 队列状态
        :param PageNumber(string): 第几页
        :param PageSize(string): 每页个数
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询媒体处理队列接口
            response = client.ci_get_media_pic_queue(
                Bucket='bucket'
            )
            print response
        """
        return self.ci_get_media_queue(Bucket=Bucket, State=State, QueueIds=QueueIds,
                                       PageNumber=PageNumber, PageSize=PageSize,
                                       UrlPath="/picqueue", **kwargs)

    def ci_create_media_jobs(self, Bucket, Jobs={}, Lst={}, **kwargs):
        """ 创建任务接口 https://cloud.tencent.com/document/product/436/54013

        :param Bucket(string): 存储桶名称.
        :param Jobs(dict): 创建任务的配置.
        :param Lst(dict): 创建任务dict转xml时去除Key数组. TODO 替换成 xmltodict 库后可以将 Lst 参数去掉
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_create_media_jobs(
                Bucket='bucket'
                Jobs={},
                Lst={}
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        xml_config = format_xml(data=Jobs, root='Request')
        path = "/jobs"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("create_media_jobs result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['JobsDetail'])
        return data

    def ci_create_media_pic_jobs(self, Bucket, Jobs={}, Lst={}, **kwargs):
        """ 创建图片处理任务接口 https://cloud.tencent.com/document/product/436/67194

        :param Bucket(string): 存储桶名称.
        :param Jobs(dict): 创建任务的配置.
        :param Lst(dict): 创建任务dict转xml时去除Key数组. TODO 替换为 xmltodict 库后可以将 Lst 参数去掉
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_create_media_pic_jobs(
                Bucket='bucket'
                Jobs={},
                Lst={}
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        xml_config = format_xml(data=Jobs, root='Request')
        path = "/pic_jobs"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("create_media_pic_jobs result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['JobsDetail'])
        return data

    def ci_get_media_jobs(self, Bucket, JobIDs, **kwargs):
        """ 查询任务接口 https://cloud.tencent.com/document/product/436/54010

        :param Bucket(string): 存储桶名称.
        :param JobIDs(string): 任务ID，以,分割多个任务ID.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_get_media_jobs(
                Bucket='bucket'
                JobIDs={}
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        path = "/jobs/" + JobIDs
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("get_media_jobs result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        logger.debug("ci_get_media_jobs result, url=:{url} ,content=:{content}".format(
            url=url,
            content=rt.content))

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['JobsDetail'])
        return data

    def ci_get_media_pic_jobs(self, Bucket, JobIDs, **kwargs):
        """ 查询图片处理任务接口 https://cloud.tencent.com/document/product/436/67197

        :param Bucket(string): 存储桶名称.
        :param JobIDs(string): 任务ID，以,分割多个任务ID.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_get_media_pic_jobs(
                Bucket='bucket'
                JobIDs={}
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        path = "/pic_jobs/" + JobIDs
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("get_media_jobs result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        logger.debug("ci_get_media_pic_jobs result, url=:{url} ,content=:{content}".format(
            url=url,
            content=rt.content))

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['JobsDetail'])
        return data

    def ci_list_media_pic_jobs(self, Bucket, Tag, QueueId=None, StartCreationTime=None, EndCreationTime=None, OrderByTime='Desc', States='All', Size=10, NextToken='', **kwargs):
        """ 查询图片处理任务列表接口 https://cloud.tencent.com/document/product/436/67198

        :param Bucket(string): 存储桶名称.
        :param QueueId(string): 队列ID.
        :param Tag(string): 任务类型.
        :param StartCreationTime(string): 开始时间.
        :param EndCreationTime(string): 结束时间.
        :param OrderByTime(string): 排序方式.
        :param States(string): 任务状态.
        :param Size(string): 任务个数.
        :param NextToken(string): 请求的上下文，用于翻页.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_get_media_pic_jobs(
                Bucket='bucket'
                QueueId='',
                Tag='PicProcess'
            )
            print response
        """
        return self.ci_list_media_jobs(Bucket=Bucket, QueueId=QueueId, Tag=Tag,
                                       StartCreationTime=StartCreationTime,
                                       EndCreationTime=EndCreationTime,
                                       OrderByTime=OrderByTime, States=States,
                                       Size=Size, NextToken=NextToken, Path='/pic_jobs', **kwargs)

    def ci_list_media_jobs(self, Bucket, Tag, QueueId=None, StartCreationTime=None, EndCreationTime=None, OrderByTime='Desc', States='All', Size=10, NextToken='', Path='/jobs', **kwargs):
        """ 查询任务接口 https://cloud.tencent.com/document/product/436/54011

        :param Bucket(string): 存储桶名称.
        :param QueueId(string): 队列ID.
        :param Tag(string): 任务类型.
        :param StartCreationTime(string): 开始时间.
        :param EndCreationTime(string): 结束时间.
        :param OrderByTime(string): 排序方式.
        :param States(string): 任务状态.
        :param Size(string): 任务个数.
        :param NextToken(string): 请求的上下文，用于翻页.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_get_media_jobs(
                Bucket='bucket'
                QueueId='',
                Tag='Transcode'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['tag'] = Tag
        params['orderByTime'] = OrderByTime
        params['states'] = States
        params['size'] = str(Size)
        params['nextToken'] = NextToken
        if QueueId is not None:
            params['queueId'] = QueueId
        if StartCreationTime is not None:
            params['startCreationTime'] = StartCreationTime
        if EndCreationTime is not None:
            params['endCreationTime'] = EndCreationTime

        params = format_values(params)
        path = Path
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("list_media_jobs result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        logger.debug("list_media_jobs result, url=:{url} ,content=:{content}".format(
            url=url,
            content=rt.content))
        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['JobsDetail'])
        return data

    def ci_create_workflow(self, Bucket, Body, **kwargs):
        """ 创建工作流接口 https://cloud.tencent.com/document/product/460/76856

        :param Bucket(string): 存储桶名称.
        :param Body(dict): 创建工作流的配置信息.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建工作流接口
            response = client.ci_create_workflow(
                Bucket='bucket'
                Body={},
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        xml_config = format_xml(data=Body, root='Request')
        path = "/workflow"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_create_workflow result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        return data

    def ci_update_workflow_state(self, Bucket, WorkflowId, UpdateState, **kwargs):
        """ 更新工作流接口 https://cloud.tencent.com/document/product/460/76861

        :param Bucket(string): 存储桶名称.
        :param WorkflowId(string): 需要更新状态的工作流ID.
        :param UpdateState(string): 更新工作流的状态,有效值为active、paused
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 更新工作流状态接口
            response = client.ci_update_workflow_state(
                Bucket='bucket'
                WorkflowId='',
                UpdateState='active'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params[UpdateState] = ''

        params = format_values(params)

        path = "/workflow/" + WorkflowId
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_update_workflow_state result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        return data

    def ci_update_workflow(self, Bucket, WorkflowId, Body, **kwargs):
        """ 更新工作流接口 https://cloud.tencent.com/document/product/460/76861

        :param Bucket(string): 存储桶名称.
        :param WorkflowId(string): 需要更新状态的工作流ID.
        :param Body(dict): 更新工作流的配置信息.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_update_workflow(
                Bucket='bucket'
                Body={},
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        xml_config = format_xml(data=Body, root='Request')
        path = "/workflow/" + WorkflowId
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_update_workflow result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        return data

    def ci_get_workflow(self, Bucket, Ids='', Name='', PageNumber='', PageSize='', **kwargs):
        """ 获取工作流详情接口 https://cloud.tencent.com/document/product/460/76857

        :param Bucket(string): 存储桶名称.
        :param Ids(string): 需要查询的工作流 ID，可传入多个，以,符号分割字符串.
        :param Name(string): 需要查询的工作流名称.
        :param PageNumber(string): 第几页.
        :param PageSize(string): 每页个数.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_get_workflow(
                Bucket='bucket'
                Body={},
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['ids'] = Ids
        params['name'] = Name
        params['pageNumber'] = str(PageNumber)
        params['pageSize'] = str(PageSize)

        params = format_values(params)

        path = "/workflow"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_get_workflow result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['MediaWorkflowList'])
        return data

    def ci_delete_workflow(self, Bucket, WorkflowId, **kwargs):
        """ 删除工作流接口 https://cloud.tencent.com/document/product/460/76860

        :param Bucket(string): 存储桶名称.
        :param WorkflowId(string): 需要删除的工作流ID.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除指定工作流
            response = client.ci_delete_workflow(
                Bucket=bucket_name,
                WorkflowId='w1bdxxxxxxxxxxxxxxxxx94a9',
            )
            print(response)
            return response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = "/workflow/" + WorkflowId
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)

        logger.info("ci_delete_workflow result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        return data

    def ci_trigger_workflow(self, Bucket, WorkflowId, Key, **kwargs):
        """ 触发工作流接口 https://cloud.tencent.com/document/product/436/54641

        :param Bucket(string): 存储桶名称.
        :param WorkflowId(string):工作流ID.
        :param Key(string): 对象key.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 触发工作流接口
            response = client.ci_trigger_workflow(
                Bucket='bucket'
                WorkflowId='',
                Key='a.mp4'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['workflowId'] = WorkflowId
        params['object'] = Key

        params = format_values(params)
        path = "/triggerworkflow"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_trigger_workflow result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        logger.debug("ci_trigger_workflow result, url=:{url} ,content=:{content}".format(
            url=url,
            content=rt.content))
        data = xml_to_dict(rt.content)
        return data

    def ci_get_workflowexecution(self, Bucket, RunId, **kwargs):
        """ 获取工作流实例详情 https://cloud.tencent.com/document/product/436/53992

        :param Bucket(string): 存储桶名称.
        :param RunId(string): 工作流实例ID.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 获取工作流实例详情
            response = client.ci_get_workflowexecution(
                Bucket='bucket'
                RunId=''
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        path = "/workflowexecution/" + RunId
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_get_workflowexecution result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        logger.debug("ci_get_workflowexecution result, url=:{url} ,content=:{content}".format(
            url=url,
            content=rt.content))

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['WorkflowExecution'])
        return data

    def ci_list_workflowexecution(self, Bucket, WorkflowId, Name='', StartCreationTime=None, EndCreationTime=None, OrderByTime='Desc', States='All', Size=10, NextToken='', BatchJobId=None, **kwargs):
        """ 获取工作流实例列表 https://cloud.tencent.com/document/product/436/80048

        :param Bucket(string): 存储桶名称.
        :param WorkflowId(string): 工作流实例ID.
        :param Name(string): 触发对象.
        :param StartCreationTime(string): 开始时间.
        :param EndCreationTime(string): 结束时间.
        :param OrderByTime(string): 排序方式.
        :param States(string): 任务状态.
        :param Size(string): 任务个数.
        :param NextToken(string): 请求的上下文，用于翻页.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_list_workflowexecution(
                Bucket='bucket'
                WorkflowId='',
                Name='a.mp4'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['workflowId'] = WorkflowId
        params['name'] = Name
        params['orderByTime'] = OrderByTime
        params['states'] = States
        params['size'] = str(Size)
        params['nextToken'] = NextToken
        if StartCreationTime is not None:
            params['startCreationTime'] = StartCreationTime
        if EndCreationTime is not None:
            params['endCreationTime'] = EndCreationTime
        if BatchJobId is not None:
            params['jobId'] = BatchJobId

        params = format_values(params)
        path = "/workflowexecution"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_list_workflowexecution result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        logger.debug("ci_list_workflowexecution result, url=:{url} ,content=:{content}".format(
            url=url,
            content=rt.content))
        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['WorkflowExecution'])
        return data

    def get_media_info(self, Bucket, Key, **kwargs):
        """用于查询媒体文件的信息 https://cloud.tencent.com/document/product/436/55672

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置下载的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 用于查询COS上媒体文件的信息
            response = client.get_media_info(
                Bucket='bucket',
                Key='test.mp4'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {'ci-process': 'videoinfo'}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("get_media_info, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        data = xml_to_dict(rt.content)
        format_dict(data, ['MediaInfo'])
        return data

    def get_snapshot(self, Bucket, Key, Time, Width=None, Height=None, Format='jpg', Rotate='auto', Mode='exactframe', **kwargs):
        """获取媒体文件某个时间的截图 https://cloud.tencent.com/document/product/436/55671

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Time(string): 截图时间点.
        :param Width(string):  截图宽.
        :param Height(string): 截图高.
        :param Format(string): jpg, png.
        :param Rotate(string): auto 自动根据媒体信息旋转, off 不旋转.
        :param Mode(string): 截帧方式 keyframe：截取指定时间点之前的最近的一个关键帧 exactframe：截取指定时间点的帧.
        :return(dict): 下载成功返回的结果,包含Body对应的StreamBody,可以获取文件流或下载文件到本地.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 用于获取COS文件某个时间的截图
            response = client.get_snapshot(
                Bucket='bucket',
                Key='test.mp4',
                Time='1.5',
                Witdh='480',
                Format='jpg',
                Rotate='auto',
                Mode='exactframe'
            )
            response['Body'].get_stream_to_file('snapshot.jpg')
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {'ci-process': 'snapshot'}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['time'] = Time
        if Width is not None:
            params['width'] = Width
        if Height is not None:
            params['height'] = Height
        params['format'] = Format
        params['rotate'] = Rotate
        params['mode'] = Mode
        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("get_snapshot, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        response = dict(**rt.headers)
        response['Body'] = StreamBody(rt)

        return response

    def get_pm3u8(self, Bucket, Key, Expires, **kwargs):
        """获取私有 M3U8 ts 资源的下载授权 https://cloud.tencent.com/document/product/436/63740

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Expires(string): 私有 ts 资源 url 下载凭证的相对有效期.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 下载成功返回的结果,包含Body对应的StreamBody,可以获取文件流或下载文件到本地.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 用于获取COS文件某个时间的截图
            response = client.get_snapshot(
                Bucket='bucket',
                Key='test.mp4',
                Expires='3600',
            )
            response['Body'].get_stream_to_file('pm3u8.m3u8')
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {'ci-process': 'pm3u8'}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['expires'] = Expires
        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("get_pm3u8, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        response = dict(**rt.headers)
        response['Body'] = StreamBody(rt)

        return response

    def ci_get_media_aigc_metadata(self, Bucket, Key, **kwargs):
        """ci_get_media_aigc_metadata查询音视频中保存的AIGC元数据标识信息接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置下载的headers.
        :return(dict): response header.
        :return(dict): AIGC元数据标识信息结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response, data = client.ci_get_media_aigc_metadata(
                    Bucket='bucket',
                    ObjectKey='',
                )
            print data
            print response
        """

        path = "/" + Key
        return self.ci_process(Bucket, path, "MediaAIGCMetadata", NeedHeader=True, **kwargs)

    def ci_get_doc_queue(self, Bucket, State='All', QueueIds='', PageNumber=1, PageSize=10, **kwargs):
        """查询文档转码处理队列接口 https://cloud.tencent.com/document/product/460/46946

        :param Bucket(string): 存储桶名称.
        :param QueueIds(string): 队列 ID，以“,”符号分割字符串.
        :param State(string): 队列状态
        :param PageNumber(int): 第几页
        :param PageSize(int): 每页个数
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询文档转码处理队列接口
            response = client.ci_get_doc_queue(
                Bucket='bucket'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['queueIds'] = QueueIds
        params['state'] = State
        params['pageNumber'] = str(PageNumber)
        params['pageSize'] = str(PageSize)

        params = format_values(params)

        path = "/docqueue"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("get_doc_queue result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['QueueList'])
        return data

    def ci_update_doc_queue(self, Bucket, QueueId, Request={}, **kwargs):
        """ 更新文档预览队列接口

        :param Bucket(string): 存储桶名称.
        :param QueueId(string): 队列ID.
        :param Request(dict): 更新队列配置请求体.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 更新文档预览队列接口
            response = client.ci_update_doc_queue(
                Bucket='bucket',
                QueueId='',
                Request={},
            )
            print response
        """
        return self.ci_update_media_queue(Bucket=Bucket, QueueId=QueueId,
                                          Request=Request, UrlPath="/docqueue/", **kwargs)

    def ci_create_doc_job(self, Bucket, InputObject, OutputBucket, OutputRegion, OutputObject, QueueId=None, SrcType=None, TgtType=None,
                          StartPage=None, EndPage=-1, SheetId=0, PaperDirection=0, PaperSize=0, DocPassword=None, Comments=None, PageRanges=None,
                          ImageParams=None, Quality=100, Zoom=100, ImageDpi=96, PicPagination=0, **kwargs):
        """ 创建任务接口 https://cloud.tencent.com/document/product/460/46942

        :param Bucket(string): 存储桶名称.
        :param QueueId(string): 任务所在的队列 ID.
        :param InputObject(string): 文件在 COS 上的文件路径，Bucket 由 Host 指定.
        :param OutputBucket(string): 存储结果的存储桶.
        :param OutputRegion(string): 存储结果的存储桶的地域.
        :param OutputObject(string): 输出文件路径。
            非表格文件输出文件名需包含 ${Number} 或 ${Page} 参数。多个输出文件，${Number} 表示序号从1开始，${Page} 表示序号与预览页码一致。
            ${Number} 表示多个输出文件，序号从1开始，例如输入 abc_${Number}.jpg，预览某文件5 - 6页，则输出文件名为 abc_1.jpg，abc_2.jpg
            ${Page} 表示多个输出文件，序号与预览页码一致，例如输入 abc_${Page}.jpg，预览某文件5-6页，则输出文件名为 abc_5.jpg，abc_6.jpg
            表格文件输出路径需包含 ${SheetID} 占位符，输出文件名必须包含 ${Number} 参数。
            例如 /${SheetID}/abc_${Number}.jpg，先根据 excel 转换的表格数，生成对应数量的文件夹，再在对应的文件夹下，生成对应数量的图片文件.
        :param SrcType(string): 源数据的后缀类型，当前文档转换根据 cos 对象的后缀名来确定源数据类型，当 cos 对象没有后缀名时，可以设置该值.
        :param TgtType(string): 	转换输出目标文件类型：
            jpg，转成 jpg 格式的图片文件；如果传入的格式未能识别，默认使用 jpg 格式
            png，转成 png 格式的图片文件
            pdf，转成 pdf 格式文件（暂不支持指定页数）.
        :param StartPage(int): 从第 X 页开始转换；在表格文件中，一张表可能分割为多页转换，生成多张图片。StartPage 表示从指定 SheetId 的第 X 页开始转换。默认为1.
        :param EndPage(int): 转换至第 X 页；在表格文件中，一张表可能分割为多页转换，生成多张图片。EndPage 表示转换至指定 SheetId 的第 X 页。默认为-1，即转换全部页
        :param SheetId(int): 表格文件参数，转换第 X 个表，默认为0；设置 SheetId 为0，即转换文档中全部表
        :param PaperDirection(int): 表格文件转换纸张方向，0代表垂直方向，非0代表水平方向，默认为0
        :param PaperSize(int): 设置纸张（画布）大小，对应信息为： 0 → A4 、 1 → A2 、 2 → A0 ，默认 A4 纸张
        :param DocPassword(string): Office 文档的打开密码，如果需要转换有密码的文档，请设置该字段
        :param Comments(int): 是否隐藏批注和应用修订，默认为 0；0：隐藏批注，应用修订；1：显示批注和修订
        :param ImageParams(string): 转换后的图片处理参数，支持 基础图片处理 所有处理参数，多个处理参数可通过 管道操作符 分隔，从而实现在一次访问中按顺序对图片进行不同处理
        :param Quality(int): 生成预览图的图片质量，取值范围 [1-100]，默认值100。 例：值为100，代表生成图片质量为100%
        :param Zoom(int): 预览图片的缩放参数，取值范围[10-200]， 默认值100。 例：值为200，代表图片缩放比例为200% 即放大两倍
        :param ImageDpi(int): 按指定 dpi 渲染图片，该参数与 Zoom 共同作用，取值范围 96-600 ，默认值为 96 。转码后的图片单边宽度需小于65500像素
        :param PicPagination(int): 是否转换成单张长图，设置为 1 时，最多仅支持将 20 标准页面合成单张长图，超过可能会报错，分页范围可以通过 StartPage、EndPage 控制。默认值为 0 ，按页导出图片，TgtType="png"/"jpg" 时生效
        :param PageRanges(string): 自定义需要转换的分页范围，例如： "1,2-4,7" ，则表示转换文档的 1、2、3、4、7 页面
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_create_doc_job(
                Bucket='bucket'
                QueueId='p532fdead78444e649e1a4467c1cd19d3',
                InputObject='test.doc',
                OutputBucket='outputbucket',
                OutputRegion='outputregion',
                OutputObject='/${SheetID}/abc_${Number}.jpg',
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/xml'

        params = format_values(params)
        body = {
            'Input': {
                'Object': InputObject,
            },
            'Tag': 'DocProcess',
            'Operation': {
                'Output': {'Bucket': OutputBucket, 'Region': OutputRegion, 'Object': OutputObject},
                'DocProcess': {
                }
            }
        }
        if QueueId:
            body['QueueId'] = QueueId
        if SrcType:
            body['Operation']['DocProcess']['SrcType'] = SrcType
        if TgtType:
            body['Operation']['DocProcess']['TgtType'] = TgtType
        if ImageParams:
            body['Operation']['DocProcess']['ImageParams'] = ImageParams
        if DocPassword:
            body['Operation']['DocProcess']['DocPassword'] = DocPassword
        if PageRanges:
            body['Operation']['DocProcess']['PageRanges'] = PageRanges
        if StartPage:
            body['Operation']['DocProcess']['StartPage'] = StartPage
        if EndPage:
            body['Operation']['DocProcess']['EndPage'] = EndPage
        if SheetId:
            body['Operation']['DocProcess']['SheetId'] = SheetId
        if PaperDirection:
            body['Operation']['DocProcess']['PaperDirection'] = PaperDirection
        if PaperSize:
            body['Operation']['DocProcess']['PaperSize'] = PaperSize
        if Quality:
            body['Operation']['DocProcess']['Quality'] = Quality
        if Zoom:
            body['Operation']['DocProcess']['Zoom'] = Zoom
        if PicPagination:
            body['Operation']['DocProcess']['PicPagination'] = PicPagination
        if ImageDpi:
            body['Operation']['DocProcess']['ImageDpi'] = ImageDpi
        if Comments:
            body['Operation']['DocProcess']['Comments'] = Comments

        xml_config = format_xml(data=body, root='Request')
        path = "/doc_jobs"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("create_doc_jobs result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        return data

    def ci_get_doc_job(self, Bucket, JobID, **kwargs):
        """ 查询任务接口 https://cloud.tencent.com/document/product/460/46943

        :param Bucket(string): 存储桶名称.
        :param JobID(string): 任务ID.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询任务接口
            response = client.ci_get_doc_job(
                Bucket='bucket'
                JobID='jobid'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/xml'

        params = format_values(params)
        path = "/doc_jobs/" + JobID
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("get_doc_jobs result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        logger.debug("ci_get_doc_jobs result, url=:{url} ,content=:{content}".format(
            url=url,
            content=rt.content))

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['JobsDetail'])
        return data

    def ci_list_doc_jobs(self, Bucket, QueueId=None, StartCreationTime=None, EndCreationTime=None, OrderByTime='Desc', States='All', Size=10, NextToken='', **kwargs):
        """ 拉取文档预览任务列表接口 https://cloud.tencent.com/document/product/460/46944

        :param Bucket(string): 存储桶名称.
        :param QueueId(string): 队列ID.
        :param StartCreationTime(string): 开始时间.
        :param EndCreationTime(string): 结束时间.
        :param OrderByTime(string): 排序方式.Desc 或者 Asc。默认为 Desc
        :param States(string): 拉取该状态的任务，以,分割，支持多状态：All、Submitted、Running、Success、Failed、Pause、Cancel。默认为 All
        :param Size(string): 拉取的最大任务数。默认为10。最大为100.
        :param NextToken(string): 请求的上下文，用于翻页.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_list_doc_jobs(
                Bucket='bucket'
                QueueId='',
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/xml'

        params['tag'] = 'DocProcess'
        params['orderByTime'] = OrderByTime
        params['states'] = States
        params['size'] = str(Size)
        params['nextToken'] = NextToken
        if QueueId is not None:
            params['queueId'] = QueueId
        if StartCreationTime is not None:
            params['startCreationTime'] = StartCreationTime
        if EndCreationTime is not None:
            params['endCreationTime'] = EndCreationTime

        params = format_values(params)
        path = "/doc_jobs"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("list_doc_jobs result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        logger.debug("list_doc_jobs result, url=:{url} ,content=:{content}".format(
            url=url,
            content=rt.content))
        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['JobsDetail'])
        return data

    def ci_doc_preview_process(self, Bucket, Key, SrcType=None, Page=None, DstType=None, PassWord=None, Comment=0, Sheet=1,
                               ExcelPaperDirection=0, ExcelRow=0, ExcelCol=0, ExcelPaperSize=None, TxtPagination=False,
                               ImageParams=None, Quality=100, Scale=100, ImageDpi=96, **kwargs):
        """文档预览同步接口 https://cloud.tencent.com/document/product/460/47074

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param SrcType(string): 源数据的后缀类型，当前文档转换根据 COS 对象的后缀名来确定源数据类型。当 COS 对象没有后缀名时，可以设置该值。
        :param Page(int):  需转换的文档页码，默认从1开始计数；表格文件中 page 表示转换的第 X 个 sheet 的第 X 张图。
        :param DstType(string): 转换输出目标文件类型：
                                                png，转成 png 格式的图片文件
                                                jpg，转成 jpg 格式的图片文件
                                                pdf，转成 pdf 格式文件。 无法选择页码，page 参数不生效
                                                txt，转成 txt 格式文件
                                                如果传入的格式未能识别，默认使用 jpg 格式。
        :param PassWord(string): Office 文档的打开密码，如果需要转换有密码的文档，请设置该字段。
        :param Comment(int): 是否隐藏批注和应用修订，默认为0。0：隐藏批注，应用修订；1：显示批注和修订。
        :param Sheet(int): 表格文件参数，转换第 X 个表，默认为1。
        :param ExcelPaperDirection(int): 表格文件转换纸张方向，0代表垂直方向，非0代表水平方向，默认为0。
        :param ExcelRow(int): 值为1表示将所有列放到1页进行排版，默认值为0。
        :param ExcelCol(int): 值为1表示将所有行放到1页进行排版，默认值为0。
        :param ExcelPaperSize(int): 设置纸张（画布）大小，对应信息为： 0 → A4 、 1 → A2 、 2 → A0 ，默认 A4 纸张 （需配合 excelRow 或 excelCol 一起使用）。
        :param TxtPagination(bool): 是否转换成长文本，设置为 true 时，可以将需要导出的页中的文字合并导出，分页范围可以通过 Ranges 控制。默认值为 false ，按页导出 txt。（ ExportType="txt" 时生效)。
        :param ImageParams(string): 转换后的图片处理参数，支持 基础图片处理 所有处理参数，多个处理参数可通过 管道操作符 分隔，从而实现在一次访问中按顺序对图片进行不同处理。
        :param Quality(int): 生成预览图的图片质量，取值范围为 [1, 100]，默认值100。 例如取值为100，代表生成图片质量为100%。
        :param Scale(int): 预览图片的缩放参数，取值范围为 [10, 200]， 默认值100。 例如取值为200，代表图片缩放比例为200% 即放大两倍。
        :param ImageDpi(int): 按指定 dpi 渲染图片，该参数与 scale 共同作用，取值范围 96-600 ，默认值为 96 。转码后的图片单边宽度需小于65500像素。
        :return(dict): 下载成功返回的结果,包含Body对应的StreamBody,可以获取文件流或下载文件到本地.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            def ci_doc_preview_process():
                # 文档预览同步接口
                response = client.ci_doc_preview_process(
                    Bucket=bucket_name,
                    Key='1.txt',
                )
                print(response)
                response['Body'].get_stream_to_file('result.png')
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {'ci-process': 'doc-preview'}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        if SrcType:
            params['srcType'] = SrcType
        if Page:
            params['page'] = Page
        if DstType:
            params['dstType'] = DstType
        if PassWord:
            params['password'] = PassWord
        params['comment'] = Comment
        params['sheet'] = Sheet
        params['excelPaperDirection'] = ExcelPaperDirection
        params['excelRow'] = ExcelRow
        params['excelCol'] = ExcelCol
        if ExcelPaperSize:
            params['excelPaperSize'] = ExcelPaperSize
        params['txtPagination'] = str(TxtPagination).lower()
        if ImageParams:
            params['ImageParams'] = ImageParams
        params['quality'] = Quality
        params['scale'] = Scale
        params['imageDpi'] = ImageDpi

        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("ci_doc_preview_process, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        response = dict(**rt.headers)
        response['Body'] = StreamBody(rt)

        return response

    def ci_doc_preview_html_process(self, Bucket, Key, SrcType=None, Copyable='1', DstType='html', HtmlParams=None, HtmlWaterword=None, HtmlFillStyle=None,
                                    HtmlFront=None, HtmlRotate=None, HtmlHorizontal=None, HtmlVertical=None, HtmlTitle=None, **kwargs):
        """文档转 HTML https://cloud.tencent.com/document/product/460/52518

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param SrcType(string): 源数据的后缀类型，当前文档转换根据 COS 对象的后缀名来确定源数据类型。当 COS 对象没有后缀名时，可以设置该值。
        :param Copyable(string):  是否可复制。默认为可复制，填入值为1；不可复制，填入值为0。
        :param DstType(string): 转换输出目标文件类型，文档 HTML 预览固定为 html（需为小写字母）.
        :param HtmlParams(string): 自定义配置参数，json结构，需要经过 URL 安全 的 Base64 编码，默认配置为：{ commonOptions: { isShowTopArea: true, isShowHeader: true } }。
        :param HtmlWaterword(string): 水印文字，需要经过 URL 安全 的 Base64 编码，默认为空。
        :param Htmlfillstyle(string): 水印 RGBA（颜色和透明度），需要经过 URL 安全 的 Base64 编码，默认为：rgba(192,192,192,0.6)。
        :param HtmlFront(string): 水印文字样式，需要经过 URL 安全 的 Base64 编码，默认为：bold 20px Serif。
        :param HtmlRotate(string): 水印文字旋转角度，0 - 360，默认315度。
        :param HtmlHorizontal(string): 水印文字水平间距，单位 px，默认为50。
        :param HtmlVertical(string): 水印文字垂直间距，单位 px，默认为100。
        :param HtmlTitle(string): 自定义返回html的title信息，默认为“腾讯云-数据万象”，可输入自定义字符串并配合通配符使用，需要经过 URL安全的Base64 编码。
        :return(dict): 获取成功返回的结果,包含Body对应的StreamBody,可以获取文件流或下载文件到本地.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response = client.ci_doc_preview_html_process(
                Bucket=bucket_name,
                Key='1.txt',
            )
            print(response)
            response['Body'].get_stream_to_file('result.html')
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {'ci-process': 'doc-preview'}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        if SrcType:
            params['srcType'] = SrcType
        params['copyable'] = Copyable
        params['dstType'] = DstType
        if HtmlParams:
            params['htmlParams'] = HtmlParams
        if HtmlWaterword:
            params['htmlwaterword'] = HtmlWaterword
        if HtmlFillStyle:
            params['htmlfillstyle'] = HtmlFillStyle
        if HtmlFront:
            params['htmlfront'] = HtmlFront
        if HtmlRotate:
            params['htmlrotate'] = HtmlRotate
        if HtmlHorizontal:
            params['htmlhorizontal'] = HtmlHorizontal
        if HtmlVertical:
            params['htmlvertical'] = HtmlVertical
        if HtmlTitle:
            params['htmltitle'] = HtmlTitle

        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("ci_doc_preview_html_process, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        response = dict(**rt.headers)
        response['Body'] = StreamBody(rt)

        return response

    def ci_get_doc_bucket(self, Regions='', BucketName='', BucketNames='', PageNumber=1, PageSize=10, **kwargs):
        """查询文档预览开通状态接口 https://cloud.tencent.com/document/product/460/46945

        :param Regions(string): 地域信息，例如 ap-shanghai、ap-beijing，若查询多个地域以“,”分隔字符串
        :param BucketName(string): 存储桶名称前缀，前缀搜索
        :param BucketNames(string): 存储桶名称，以“,”分隔，支持多个存储桶，精确搜索
        :param PageNumber(string): 第几页
        :param PageSize(string): 每页个数
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询文档预览开通状态接口
            response = client.ci_get_doc_bucket(
                Regions='ap-chongqing,ap-shanghai',
                BucketName='demo',
                BucketNames='demo-1253960454,demo1-1253960454',
                PageNumber='2'，
                PageSize='3',
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['regions'] = Regions
        params['bucketNames'] = BucketNames
        params['bucketName'] = BucketName
        params['pageNumber'] = str(PageNumber)
        params['pageSize'] = str(PageSize)

        params = format_values(params)

        path = "/docbucket"
        url = self._conf.uri(bucket=None, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_get_doc_bucket result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=None,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['DocBucketList'])
        return data

    def ci_open_asr_bucket(self, Bucket, **kwargs):
        """ 开通智能语音服务 https://cloud.tencent.com/document/product/460/95754

        :param Bucket(string) 存储桶名称.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  开通智能语音服务
            response, data = client.ci_open_asr_bucket(
                Bucket='bucket'
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = "/" + "asrbucket"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)

        logger.info("ci_open_asr_bucket result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='POST',
            url=url,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response:
            if response['Content-Type'] == 'application/xml' and 'Content-Length' in response and \
                response['Content-Length'] != 0:
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data

    def ci_get_asr_bucket(self, Regions='', BucketName='', BucketNames='', PageNumber='', PageSize='', **kwargs):
        """查询语音识别开通状态接口 https://cloud.tencent.com/document/product/460/46232

        :param Regions(string): 地域信息，例如 ap-shanghai、ap-beijing，若查询多个地域以“,”分隔字符串
        :param BucketName(string): 存储桶名称前缀，前缀搜索
        :param BucketNames(string): 存储桶名称，以“,”分隔，支持多个存储桶，精确搜索
        :param PageNumber(string): 第几页
        :param PageSize(string): 每页个数
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询语音识别开通状态接口
            response = client.ci_get_asr_bucket(
                Regions='ap-chongqing,ap-shanghai',
                BucketName='demo',
                BucketNames='demo-1253960454,demo1-1253960454',
                PageNumber='2'，
                PageSize='3',
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['regions'] = Regions
        params['bucketNames'] = BucketNames
        params['bucketName'] = BucketName
        params['pageNumber'] = PageNumber
        params['pageSize'] = PageSize

        params = format_values(params)

        path = "/asrbucket"
        url = self._conf.uri(bucket=None, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_get_asr_bucket result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=None,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['AsrBucketList'])
        return data

    def ci_close_asr_bucket(self, Bucket, **kwargs):
        """ 关闭智能语音服务 https://cloud.tencent.com/document/product/460/95755

        :param Bucket(string) 存储桶名称.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  关闭智能语音服务
            response, data = client.ci_close_asr_bucket(
                Bucket='bucket'
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = "/" + "asrbucket"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)

        logger.info("ci_close_asr_bucket result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='DELETE',
            url=url,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response:
            if response['Content-Type'] == 'application/xml' and 'Content-Length' in response and \
                response['Content-Length'] != 0:
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data

    def ci_get_asr_queue(self, Bucket, State='All', QueueIds='', PageNumber=1, PageSize=10, **kwargs):
        """查询语音识别队列接口 https://cloud.tencent.com/document/product/460/46234

        :param Bucket(string): 存储桶名称.
        :param QueueIds(string): 队列 ID，以“,”符号分割字符串.
        :param State(string): 队列状态
        :param PageNumber(int): 第几页
        :param PageSize(int): 每页个数
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询语音识别队列接口
            response = client.ci_get_asr_queue(
                Bucket='bucket'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['queueIds'] = QueueIds
        params['state'] = State
        params['pageNumber'] = str(PageNumber)
        params['pageSize'] = str(PageSize)

        params = format_values(params)

        path = "/asrqueue"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("get_asr_queue result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['QueueList'])
        return data

    def ci_update_asr_queue(self, Bucket, QueueId, Request={}, **kwargs):
        """ 更新语音识别队列接口 https://cloud.tencent.com/document/product/460/46235

        :param Bucket(string): 存储桶名称.
        :param QueueId(string): 队列ID.
        :param Request(dict): 更新队列配置请求体.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 更新语音识别队列接口
            response = client.ci_update_asr_queue(
                Bucket='bucket',
                QueueId='',
                Request={},
            )
            print response
        """
        return self.ci_update_media_queue(Bucket=Bucket, QueueId=QueueId,
                                          Request=Request, UrlPath="/asrqueue/", **kwargs)

    def ci_create_asr_job(self, Bucket, OutputBucket, OutputRegion, OutputObject, QueueId=None, InputObject=None, Url=None, TemplateId=None,
                          SpeechRecognition=None, CallBack=None, CallBackFormat=None, CallBackType=None, CallBackMqConfig=None, **kwargs):
        """ 创建语音识别任务接口 https://cloud.tencent.com/document/product/460/78951

        :param Bucket(string): 存储桶名称.
        :param QueueId(string): 任务所在的队列 ID.
        :param InputObject(string): 文件在 COS 上的文件路径，Bucket 由 Host 指定.
        :param Url(string): 外网可下载的Url.
        :param OutputBucket(string): 存储结果的存储桶.
        :param OutputRegion(string): 存储结果的存储桶的地域.
        :param OutputObject(string): 输出文件路径。
        :param TemplateId(string): 对应语音识别模板ID.
        :param SpeechRecognition(dict): 语音识别参数信息，当参数TemplateId 不为空时，此参数无效
        :param CallBack(string): 任务结束回调，回调Url
        :param CallBackFormat(string): 任务回调格式，JSON 或 XML，默认 XML，优先级高于队列的回调格式
        :param CallBackType(string): 任务回调类型，Url 或 TDMQ，默认 Url，优先级高于队列的回调类型
        :param CallBackMqConfig(dict): 任务回调TDMQ配置，当 CallBackType 为 TDMQ 时必填，详见 https://cloud.tencent.com/document/product/460/78927#CallBackMqConfig
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            body = {
                'EngineModelType': '16k_zh',
                'ChannelNum': '1',
                'ResTextFormat': '1',
            }
            response = client.ci_create_asr_job(
                Bucket=bucket_name,
                QueueId='s0980xxxxxxxxxxxxxxxxff12',
                # TemplateId='t1ada6f282d29742db83244e085e920b08',
                InputObject='normal.mp4',
                OutputBucket=bucket_name,
                OutputRegion='ap-chongqing',
                OutputObject='result.txt',
                SpeechRecognition=body
            )
            print(response)
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/xml'

        params = format_values(params)
        body = {
            'Input': {
            },
            'Tag': 'SpeechRecognition',
            'Operation': {
                'Output': {
                    'Bucket': OutputBucket,
                    'Region': OutputRegion,
                    'Object': OutputObject
                },
            }
        }
        if QueueId:
            body['QueueId'] = QueueId
        if InputObject:
            body['Input']['Object'] = InputObject
        if Url:
            body['Input']['Url'] = Url
        if TemplateId:
            body['Operation']['TemplateId'] = TemplateId
        if SpeechRecognition:
            body['Operation']['SpeechRecognition'] = SpeechRecognition
        if CallBack:
            body['CallBack'] = CallBack
        if CallBackFormat:
            body['CallBackFormat'] = CallBackFormat
        if CallBackMqConfig:
            body['CallBackMqConfig'] = CallBackMqConfig
        xml_config = format_xml(data=body, root='Request')
        path = "/asr_jobs"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("create_asr_jobs result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        return data

    def ci_get_asr_job(self, Bucket, JobID, **kwargs):
        """ 查询语音识别任务接口 https://cloud.tencent.com/document/product/460/46229

        :param Bucket(string): 存储桶名称.
        :param JobID(string): 任务ID.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询任务接口
            response = client.ci_get_asr_job(
                Bucket='bucket'
                JobID='jobid'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/xml'

        params = format_values(params)
        path = "/asr_jobs/" + JobID
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("get_asr_jobs result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        logger.debug("ci_get_asr_jobs result, url=:{url} ,content=:{content}".format(
            url=url,
            content=rt.content))

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['JobsDetail'])
        return data

    def ci_list_asr_jobs(self, Bucket, QueueId=None, StartCreationTime=None, EndCreationTime=None, OrderByTime='Desc', States='All', Size=10, NextToken='', **kwargs):
        """ 拉取语音识别任务列表接口 https://cloud.tencent.com/document/product/460/46230

        :param Bucket(string): 存储桶名称.
        :param QueueId(string): 队列ID.
        :param StartCreationTime(string): 开始时间.
        :param EndCreationTime(string): 结束时间.
        :param OrderByTime(string): 排序方式.Desc 或者 Asc。默认为 Desc
        :param States(string): 拉取该状态的任务，以,分割，支持多状态：All、Submitted、Running、Success、Failed、Pause、Cancel。默认为 All
        :param Size(string): 拉取的最大任务数。默认为10。最大为100.
        :param NextToken(string): 请求的上下文，用于翻页.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 拉取语音识别任务列表接口
            response = client.ci_list_asr_jobs(
                Bucket='bucket'
                QueueId='',
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/xml'

        params['tag'] = 'SpeechRecognition'
        params['orderByTime'] = OrderByTime
        params['states'] = States
        params['size'] = str(Size)
        params['nextToken'] = NextToken
        if QueueId is not None:
            params['queueId'] = QueueId
        if StartCreationTime is not None:
            params['startCreationTime'] = StartCreationTime
        if EndCreationTime is not None:
            params['endCreationTime'] = EndCreationTime

        params = format_values(params)
        path = "/asr_jobs"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("list_asr_jobs result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        logger.debug("list_asr_jobs result, url=:{url} ,content=:{content}".format(
            url=url,
            content=rt.content))
        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['JobsDetail'])
        return data

    def ci_create_asr_template(self, Bucket, Name, EngineModelType, ChannelNum=None,
                               ResTextFormat=None, FilterDirty=0, FilterModal=0, ConvertNumMode=0, SpeakerDiarization=0,
                               SpeakerNumber=0, FilterPunc=0, OutputFileType='txt', FlashAsr=False, Format=None, FirstChannelOnly=1, WordInfo=0, **kwargs):
        """ 创建语音识别模板接口 https://cloud.tencent.com/document/product/460/78939

        :param Bucket(string): 存储桶名称.
        :param Name(string): 模板名称.
        :param EngineModelType(string): 引擎模型类型，分为电话场景和非电话场景
                                        电话场景：
                                            8k_zh：电话 8k 中文普通话通用（可用于双声道音频）。
                                            8k_zh_s：电话 8k 中文普通话话者分离（仅适用于单声道音频）。
                                            8k_en：电话 8k 英语。
                                        非电话场景：
                                            16k_zh：16k 中文普通话通用。
                                            16k_zh_video：16k 音视频领域。
                                            16k_en：16k 英语。
                                            16k_ca：16k 粤语。
                                            16k_ja：16k 日语。
                                            16k_zh_edu：中文教育。
                                            16k_en_edu：英文教育。
                                            16k_zh_medical：医疗。
                                            16k_th：泰语。
                                            16k_zh_dialect：多方言，支持23种方言。
        :param ChannelNum(int): 语音声道数：1 表示单声道.EngineModelType为非电话场景仅支持单声道。2 表示双声道（仅支持 8k_zh 引擎模型双声道应分别对应通话双方）。
        :param ResTextFormat(int): 识别结果返回形式：0 表示识别结果文本（含分段时间戳）。1 词级别粒度的详细识别结果，不含标点，含语速值（词时间戳列表，一般用于生成字幕场景）。2 词级别粒度的详细识别结果（包含标点、语速值）。
        :param FilterDirty(int): 是否过滤脏词（目前支持中文普通话引擎）：0 表示不过滤脏词。1 表示过滤脏词。2 表示将脏词替换为 *。默认值为0。
        :param FilterModal(int): 是否过语气词（目前支持中文普通话引擎）：0 表示不过滤语气词。1 表示部分过滤。2 表示严格过滤 。默认值为0。
        :param ConvertNumMode(int): 是否进行阿拉伯数字智能转换（目前支持中文普通话引擎）：0 表示不转换，直接输出中文数字。1 表示根据场景智能转换为阿拉伯数字。3 表示打开数学相关数字转换。默认值为0。
        :param SpeakerDiarization(int): 是否开启说话人分离：0 表示不开启。1 表示开启(仅支持8k_zh，16k_zh，16k_zh_video，单声道音频)。默认值为0。注意：8k电话场景建议使用双声道来区分通话双方，设置ChannelNum=2即可，不用开启说话人分离。
        :param SpeakerNumber(int): 说话人分离人数（需配合开启说话人分离使用），取值范围：0-10。0 代表自动分离（目前仅支持≤6个人），1-10代表指定说话人数分离。默认值为 0。
        :param FilterPunc(int): 是否过滤标点符号（目前支持中文普通话引擎）：0 表示不过滤。1 表示过滤句末标点。2 表示过滤所有标点。默认值为 0 。
        :param OutputFileType(string): 输出文件类型，可选 txt、srt。默认为 txt。
        :param FlashAsr(bool): 是否开启极速ASR，可选true、false。默认为false.
        :param Format(string): 极速ASR音频格式。支持 wav、pcm、ogg-opus、speex、silk、mp3、m4a、aac 。
        :param FirstChannelOnly(int): 极速ASR参数。表示是否只识别首个声道，默认为1。0：识别所有声道；1：识别首个声道。
        :param WordInfo(int): 极速ASR参数。表示是否显示词级别时间戳，默认为0。0：不显示；1：显示，不包含标点时间戳，2：显示，包含标点时间戳。
        :return(dict): 创建成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建语音识别模板接口
            response = client.ci_create_asr_template(
                Bucket=bucket_name,
                Name='templateName',
                EngineModelType='16k_zh',
                ChannelNum=1,
                ResTextFormat=2,
            )
            print(response)
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/xml'

        params = format_values(params)
        body = {
            'Name': Name,
            'Tag': 'SpeechRecognition',
            'SpeechRecognition': {
                'EngineModelType': EngineModelType,
            }
        }
        if ChannelNum:
            body['SpeechRecognition']['ChannelNum'] = ChannelNum
        if ResTextFormat:
            body['SpeechRecognition']['ResTextFormat'] = ResTextFormat
        body['SpeechRecognition']['FilterDirty'] = FilterDirty
        body['SpeechRecognition']['FilterModal'] = FilterModal
        body['SpeechRecognition']['ConvertNumMode'] = ConvertNumMode
        body['SpeechRecognition']['SpeakerDiarization'] = SpeakerDiarization
        body['SpeechRecognition']['SpeakerNumber'] = SpeakerNumber
        body['SpeechRecognition']['FilterPunc'] = FilterPunc
        body['SpeechRecognition']['OutputFileType'] = OutputFileType
        body['SpeechRecognition']['FlashAsr'] = str(FlashAsr).lower()
        if Format:
            body['SpeechRecognition']['Format'] = Format
        body['SpeechRecognition']['FirstChannelOnly'] = FirstChannelOnly
        body['SpeechRecognition']['WordInfo'] = WordInfo

        xml_config = format_xml(data=body, root='Request')
        path = "/template"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_create_asr_template result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        return data

    def ci_update_asr_template(self, Bucket, TemplateId, Name, EngineModelType, ChannelNum,
                               ResTextFormat, FilterDirty=0, FilterModal=0, ConvertNumMode=0, SpeakerDiarization=0,
                               SpeakerNumber=0, FilterPunc=0, OutputFileType='txt', FlashAsr=False, Format=None, FirstChannelOnly=1, WordInfo=0, **kwargs):
        """ 更新语音识别模板接口 https://cloud.tencent.com/document/product/460/78942

        :param Bucket(string): 存储桶名称.
        :param TemplateId(string): 需要更新的模板ID。
        :param Name(string): 存储桶名称.
        :param EngineModelType(string): 引擎模型类型，分为电话场景和非电话场景
                                        电话场景：
                                            8k_zh：电话 8k 中文普通话通用（可用于双声道音频）。
                                            8k_zh_s：电话 8k 中文普通话话者分离（仅适用于单声道音频）。
                                            8k_en：电话 8k 英语。
                                        非电话场景：
                                            16k_zh：16k 中文普通话通用。
                                            16k_zh_video：16k 音视频领域。
                                            16k_en：16k 英语。
                                            16k_ca：16k 粤语。
                                            16k_ja：16k 日语。
                                            16k_zh_edu：中文教育。
                                            16k_en_edu：英文教育。
                                            16k_zh_medical：医疗。
                                            16k_th：泰语。
                                            16k_zh_dialect：多方言，支持23种方言。
        :param ChannelNum(int): 语音声道数：1 表示单声道.EngineModelType为非电话场景仅支持单声道。2 表示双声道（仅支持 8k_zh 引擎模型双声道应分别对应通话双方）。
        :param ResTextFormat(int): 识别结果返回形式：0 表示识别结果文本（含分段时间戳）。1 词级别粒度的详细识别结果，不含标点，含语速值（词时间戳列表，一般用于生成字幕场景）。2 词级别粒度的详细识别结果（包含标点、语速值）。
        :param FilterDirty(int): 是否过滤脏词（目前支持中文普通话引擎）：0 表示不过滤脏词。1 表示过滤脏词。2 表示将脏词替换为 *。默认值为0。
        :param FilterModal(int): 是否过语气词（目前支持中文普通话引擎）：0 表示不过滤语气词。1 表示部分过滤。2 表示严格过滤 。默认值为0。
        :param ConvertNumMode(int): 是否进行阿拉伯数字智能转换（目前支持中文普通话引擎）：0 表示不转换，直接输出中文数字。1 表示根据场景智能转换为阿拉伯数字。3 表示打开数学相关数字转换。默认值为0。
        :param SpeakerDiarization(int): 是否开启说话人分离：0 表示不开启。1 表示开启(仅支持8k_zh，16k_zh，16k_zh_video，单声道音频)。默认值为0。注意：8k电话场景建议使用双声道来区分通话双方，设置ChannelNum=2即可，不用开启说话人分离。
        :param SpeakerNumber(int): 说话人分离人数（需配合开启说话人分离使用），取值范围：0-10。0 代表自动分离（目前仅支持≤6个人），1-10代表指定说话人数分离。默认值为 0。
        :param FilterPunc(int): 是否过滤标点符号（目前支持中文普通话引擎）：0 表示不过滤。1 表示过滤句末标点。2 表示过滤所有标点。默认值为 0。
        :param OutputFileType(string): 输出文件类型，可选 txt、srt。默认为 txt。
        :param FlashAsr(bool): 是否开启极速ASR，可选true、false。默认为false.
        :param Format(string): 极速ASR音频格式。支持 wav、pcm、ogg-opus、speex、silk、mp3、m4a、aac 。
        :param FirstChannelOnly(int): 极速ASR参数。表示是否只识别首个声道，默认为1。0：识别所有声道；1：识别首个声道。
        :param WordInfo(int): 极速ASR参数。表示是否显示词级别时间戳，默认为0。0：不显示；1：显示，不包含标点时间戳，2：显示，包含标点时间戳。
        :return(dict): 更新成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 更新语音识别模板接口
            response = client.ci_update_asr_template(
                Bucket=bucket_name,
                TemplateId='t1bdxxxxxxxxxxxxxxxxx94a9',
                Name='updateAsr',
                EngineModelType='16k_zh',
                ChannelNum=1,
                ResTextFormat=1,
            )
            print(response)
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/xml'

        params = format_values(params)
        body = {
            'Name': Name,
            'Tag': 'SpeechRecognition',
            'SpeechRecognition': {
                'EngineModelType': EngineModelType,
            }
        }
        if ChannelNum:
            body['SpeechRecognition']['ChannelNum'] = ChannelNum
        if ResTextFormat:
            body['SpeechRecognition']['ResTextFormat'] = ResTextFormat
        body['SpeechRecognition']['FilterDirty'] = FilterDirty
        body['SpeechRecognition']['FilterModal'] = FilterModal
        body['SpeechRecognition']['ConvertNumMode'] = ConvertNumMode
        body['SpeechRecognition']['SpeakerDiarization'] = SpeakerDiarization
        body['SpeechRecognition']['SpeakerNumber'] = SpeakerNumber
        body['SpeechRecognition']['FilterPunc'] = FilterPunc
        body['SpeechRecognition']['OutputFileType'] = OutputFileType
        body['SpeechRecognition']['FlashAsr'] = str(FlashAsr).lower()
        if Format:
            body['SpeechRecognition']['Format'] = Format
        body['SpeechRecognition']['FirstChannelOnly'] = FirstChannelOnly
        body['SpeechRecognition']['WordInfo'] = WordInfo
        xml_config = format_xml(data=body, root='Request')
        path = "/template/" + TemplateId
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_update_asr_template result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        return data

    def ci_get_asr_template(self, Bucket, Category='Custom', Ids='', Name='', PageNumber=1, PageSize=10, **kwargs):
        """ 查询语音识别模板接口 https://cloud.tencent.com/document/product/460/46943

        :param Bucket(string): 存储桶名称.
        :param Category(string): Official（系统预设模板），Custom（自定义模板），默认值：Custom.
        :param Ids(string): 模板 ID，以,符号分割字符串.
        :param Name(string): 模板名称前缀.
        :param PageNumber(string): 第几页，默认值：1.
        :param PageSize(string): 每页个数，默认值：10.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询语音识别模板接口
            response = client.ci_get_asr_template(
                Bucket=bucket_name,
            )
            print(response)
            return response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['category'] = Category
        params['ids'] = Ids
        params['name'] = Name
        params['pageNumber'] = str(PageNumber)
        params['pageSize'] = str(PageSize)

        params = format_values(params)

        path = "/template"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_get_asr_template result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['TemplateList'])
        return data

    def ci_delete_asr_template(self, Bucket, TemplateId, **kwargs):
        """ 删除语音识别模板接口 https://cloud.tencent.com/document/product/460/46943

        :param Bucket(string): 存储桶名称.
        :param TemplateId(string): 需要删除的语音识别模板ID.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除指定语音识别模板
            response = client.ci_delete_asr_template(
                Bucket=bucket_name,
                TemplateId='t1bdxxxxxxxxxxxxxxxxx94a9',
            )
            print(response)
            return response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = "/template/" + TemplateId
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)

        logger.info("ci_delete_asr_template result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        return data

    def file_hash(self, Bucket, Key, Type, AddToHeader=False, **kwargs):
        """以同步请求的方式进行文件哈希值计算，实时返回计算得到的哈希值 https://cloud.tencent.com/document/product/436/83107

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Type(string): 支持的哈希算法类型，有效值：md5、sha1、sha256.
        :param AddToHeader(bool): 是否将计算得到的哈希值，自动添加至文件的自定义header，格式为：x-cos-meta-md5/sha1/sha256; 有效值： True、False，不填则默认为False.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 下载成功返回的结果,包含Body对应的StreamBody,可以获取文件流或下载文件到本地.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 用于获取COS文件某个时间的截图
            response = client.file_hash(Bucket=bucket_name, Key="mytest.mp4", Type='md5')
            print(response)
            return response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {'ci-process': 'filehash'}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['type'] = Type
        params['addtoheader'] = str(AddToHeader).lower()
        params = format_values(params)

        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("file_hash, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=CosS3Auth(self._conf, Key, params=params),
            params=params,
            headers=headers)

        data = xml_to_dict(rt.content)
        return data

    def _ci_create_file_process_job(self, Bucket, Body=None, **kwargs):
        """ 创建文件处理公共接口
        :param Bucket(string): 存储桶名称.
        :param Body(dict): 文件处理参数信息.
        :return(dict): 查询成功返回的结果,dict类型.
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/xml'

        params = format_values(params)
        xml_config = format_xml(data=Body, root='Request')
        path = "/file_jobs"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("_ci_create_file_job result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        return data

    def ci_create_file_hash_job(self, Bucket, InputObject,
        FileHashCodeConfig, QueueId=None, CallBack=None, CallBackFormat=None,
        CallBackType=None, CallBackMqConfig=None, UserData=None, **kwargs):
        """ 创建哈希值计算任务接口 https://cloud.tencent.com/document/product/436/83108

        :param Bucket(string): 存储桶名称.
        :param QueueId(string): 任务所在的队列 ID.
        :param InputObject(string): 文件在 COS 上的文件路径，Bucket 由 Host 指定.
        :param FileHashCodeConfig(dict): 指定哈希值计算的处理规则.
        :param CallBack(string): 任务结束回调，回调Url
        :param CallBackFormat(string): 任务回调格式，JSON 或 XML，默认 XML，优先级高于队列的回调格式
        :param CallBackType(string): 任务回调类型，Url 或 TDMQ，默认 Url，优先级高于队列的回调类型
        :param CallBackMqConfig(dict): 任务回调TDMQ配置，当 CallBackType 为 TDMQ 时必填，详见 https://cloud.tencent.com/document/product/460/78927#CallBackMqConfig
        :param UserData(string): 透传用户信息, 可打印的 ASCII 码, 长度不超过1024.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            body = {
                    'Type': 'MD5',
            }
            response = client.ci_create_file_hash_job(
                Bucket=bucket_name,
                InputObject="mytest.mp4",
                FileHashCodeConfig=body
            )
            print(response)
            return response
        """
        body = {
            'Input': {
                'Object': InputObject
            },
            'Tag': 'FileHashCode',
            'Operation': {
                'FileHashCodeConfig': FileHashCodeConfig,
            }
        }
        if QueueId:
            body['QueueId'] = QueueId
        if CallBack:
            body['CallBack'] = CallBack
        if CallBackFormat:
            body['CallBackFormat'] = CallBackFormat
        if CallBackMqConfig:
            body['CallBackMqConfig'] = CallBackMqConfig
        if CallBackType:
            body['CallBackType'] = CallBackType
        if UserData:
            body['Operation']['UserData'] = UserData

        return self._ci_create_file_process_job(Bucket, Body=body, **kwargs)

    def ci_create_file_uncompress_job(self, Bucket, InputObject, OutputBucket,
        OutputRegion, FileUncompressConfig, QueueId=None, CallBack=None,
        CallBackFormat=None, CallBackType=None, CallBackMqConfig=None,
        UserData=None, **kwargs):
        """ 创建文件解压任务接口 https://cloud.tencent.com/document/product/436/83110

        :param Bucket(string): 存储桶名称.
        :param QueueId(string): 任务所在的队列 ID.
        :param InputObject(string): 文件在 COS 上的文件路径，Bucket 由 Host 指定.
        :param OutputBucket(string): 存储结果的存储桶.
        :param OutputRegion(string): 存储结果的存储桶的地域.
        :param FileUncompressConfig(dict): 指定文件解压的处理规则.
        :param CallBack(string): 任务结束回调，回调Url
        :param CallBackFormat(string): 任务回调格式，JSON 或 XML，默认 XML，优先级高于队列的回调格式
        :param CallBackType(string): 任务回调类型，Url 或 TDMQ，默认 Url，优先级高于队列的回调类型
        :param CallBackMqConfig(dict): 任务回调TDMQ配置，当 CallBackType 为 TDMQ 时必填，详见 https://cloud.tencent.com/document/product/460/78927#CallBackMqConfig
        :param UserData(string): 透传用户信息, 可打印的 ASCII 码, 长度不超过1024.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            body = {
                'Prefix': 'output/',
            }
            response = client.ci_create_file_uncompress_job(
                Bucket=bucket_name,
                InputObject='test.zip',
                FileUncompressConfig=body
            )
            print(response)
            return response
        """
        body = {
            'Input': {
                'Object': InputObject
            },
            'Tag': 'FileUncompress',
            'Operation': {
                'FileUncompressConfig': FileUncompressConfig,
                'Output': {
                    'Bucket': OutputBucket,
                    'Region': OutputRegion,
                }
            }
        }
        if QueueId:
            body['QueueId'] = QueueId
        if CallBack:
            body['CallBack'] = CallBack
        if CallBackFormat:
            body['CallBackFormat'] = CallBackFormat
        if CallBackMqConfig:
            body['CallBackMqConfig'] = CallBackMqConfig
        if CallBackType:
            body['CallBackType'] = CallBackType
        if UserData:
            body['Operation']['UserData'] = UserData

        return self._ci_create_file_process_job(Bucket, Body=body, **kwargs)

    def ci_create_file_compress_job(self, Bucket, OutputBucket, OutputRegion, OutputObject,
        FileCompressConfig, QueueId=None, CallBack=None, CallBackFormat=None,
        CallBackType=None, CallBackMqConfig=None, UserData=None, **kwargs):
        """ 创建多文件打包压缩任务接口 https://cloud.tencent.com/document/product/436/83112

        :param Bucket(string): 存储桶名称.
        :param OutputBucket(string): 存储结果的存储桶.
        :param OutputRegion(string): 存储结果的存储桶的地域.
        :param OutputObject(string): 输出文件路径。
        :param QueueId(string): 任务所在的队列 ID.
        :param FileCompressConfig(dict): 指定文件打包的处理规则.
        :param CallBack(string): 任务结束回调，回调Url
        :param CallBackFormat(string): 任务回调格式，JSON 或 XML，默认 XML，优先级高于队列的回调格式
        :param CallBackType(string): 任务回调类型，Url 或 TDMQ，默认 Url，优先级高于队列的回调类型
        :param CallBackMqConfig(dict): 任务回调TDMQ配置，当 CallBackType 为 TDMQ 时必填，详见 https://cloud.tencent.com/document/product/460/78927#CallBackMqConfig
        :param UserData(string): 透传用户信息, 可打印的 ASCII 码, 长度不超过1024.
        :return(dict): 任务返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            body = {
                'Flatten': '0',
                'Format': 'zip',
                'Prefix': '/',
            }
            response = client.ci_create_file_compress_job(
                Bucket=bucket_name,
                OutputBucket=bucket_name,
                OutputRegion='ap-guangzhou',
                OutputObject='result.zip',
                FileCompressConfig=body
            )
            print(response)
            return response
        """
        body = {
            'Tag': 'FileCompress',
            'Operation': {
                'FileCompressConfig': FileCompressConfig,
                'Output': {
                    'Bucket': OutputBucket,
                    'Region': OutputRegion,
                    'Object': OutputObject
                },
            }
        }
        if QueueId:
            body['QueueId'] = QueueId
        if CallBack:
            body['CallBack'] = CallBack
        if CallBackFormat:
            body['CallBackFormat'] = CallBackFormat
        if CallBackMqConfig:
            body['CallBackMqConfig'] = CallBackMqConfig
        if CallBackType:
            body['CallBackType'] = CallBackType
        if UserData:
            body['Operation']['UserData'] = UserData

        return self._ci_create_file_process_job(Bucket, Body=body, **kwargs)

    def ci_get_file_process_jobs(self, Bucket, JobIDs, **kwargs):
        """ 查询文件处理任务接口

        :param Bucket(string): 存储桶名称.
        :param JobIDs(string): 任务ID，以,分割多个任务ID.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_get_file_process_jobs(
                Bucket='bucket'
                JobIDs={}
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        path = "/file_jobs/" + JobIDs
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_get_file_process_jobs result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        logger.debug("ci_get_file_process_jobs result, url=:{url} ,content=:{content}".format(
            url=url,
            content=rt.content))

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['JobsDetail'])
        return data

    def ci_file_zip_preview(self, Bucket, Key, **kwargs):
        """ci_file_zip_preview 压缩文件预览接口 https://cloud.tencent.com/document/product/436/93032

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置下载的headers.
        :return(dict): 预览结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            response = client.ci_file_zip_preview(
                Bucket='bucket',
                Key='test.zip',
            )
            print response
        """
        return self.ci_process(Bucket, Key, "zippreview", **kwargs)

    def ci_recognize_logo_process(self, Bucket, Key=None, Url=None, **kwargs):
        """Logo 识别

        :param Bucket(string): 存储桶名称.
        :param Key(string): 对象文件名，例如：folder/document.jpg.
        :param Url(string): 公网可访问的图片链接. Key与Url参数不可同时传入，根据需求选择其中一个
        :return(dict): 下载成功返回的结果,包含Body对应的StreamBody,可以获取文件流或下载文件到本地.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            def ci_recognize_logo_process():
                # 通用文字识别
                response = client.ci_recognize_logo_process(
                    Bucket=bucket_name,
                    Key='demo.jpeg',
                )
                print(response)
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {'ci-process': 'RecognizeLogo'}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if Url:
            params['detect-url'] = Url
        params = format_values(params)
        url = self._conf.uri(bucket=Bucket)
        cos_s3_auth = CosS3Auth(self._conf, params=params)
        if Key:
            url = self._conf.uri(bucket=Bucket, path=Key)
            cos_s3_auth = CosS3Auth(self._conf, Key, params=params)
        logger.info("ci_recognize_logo_process, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=cos_s3_auth,
            params=params,
            headers=headers)

        data = xml_to_dict(rt.content)

        return data

    def ci_super_resolution_process(self, Bucket, Key=None, Url=None, **kwargs):
        """图像超分 https://cloud.tencent.com/document/product/460/83793#1.-.E4.B8.8B.E8.BD.BD.E6.97.B6.E5.A4.84.E7.90.86

        :param Bucket(string): 存储桶名称.
        :param Key(string): 对象文件名，例如：folder/document.jpg.
        :param Url(string): 您可以通过填写 Url 处理任意公网可访问的图片链接。不填写 detect-url 时，后台会默认处理 ObjectKey ，填写了 detect-url 时，后台会处理 detect-url 链接，无需再填写 ObjectKey，detect-url 示例：http://www.example.com/abc.jpg ，需要进行 UrlEncode，处理后为http%25253A%25252F%25252Fwww.example.com%25252Fabc.jpg。
        :return(dict): 下载成功返回的结果,包含Body对应的StreamBody,可以获取文件流或下载文件到本地.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            def ci_super_resolution_process():
                # 图像超分
                response = client.ci_super_resolution_process(
                    Bucket=bucket_name,
                    Key='demo.jpeg',
                )
                print(response)
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {'ci-process': 'AISuperResolution'}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if Url:
            params['detect-url'] = Url
        params = format_values(params)
        url = self._conf.uri(bucket=Bucket)
        cos_s3_auth = CosS3Auth(self._conf, params=params)
        if Key:
            url = self._conf.uri(bucket=Bucket, path=Key)
            cos_s3_auth = CosS3Auth(self._conf, Key, params=params)
        logger.info("ci_super_resolution_process, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            stream=True,
            auth=cos_s3_auth,
            params=params,
            headers=headers)

        response = dict(**rt.headers)
        response['Body'] = StreamBody(rt)

        return response

    def ci_cancel_jobs(self, Bucket, JobID, **kwargs):
        """取消媒体处理任务接口 https://cloud.tencent.com/document/product/436/85082

        :param Bucket(string): 存储桶名称.
        :param JobID(string): 任务id.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 下载成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 取消任务
            response = client.ci_cancel_jobs(
                Bucket='bucket',
                JobID='v11122zxxxazzz',
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = '/jobs/' + JobID
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        url += "?cancel"
        logger.info("ci_cancel_jobs result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        logger.debug("ci_cancel_jobs:%s", rt.content)
        return ''

    def ci_create_inventory_trigger_jobs(self, Bucket, JobBody, **kwargs):
        """ 创建批量处理任务接口 https://cloud.tencent.com/document/product/460/80155
        :param Bucket(string): 存储桶名称.
        :param JobBody(dict): 创建批量处理任务的配置.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.
        .. code-block:: python
            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_create_inventory_trigger_jobs(
                Bucket='bucket'
                JobBody={},
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        xml_config = format_xml(data=JobBody, root='Request')
        path = "/inventorytriggerjob"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_create_inventory_trigger_jobs result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['JobsDetail'])
        return data

    def ci_delete_inventory_trigger_jobs(self, Bucket, JobId, **kwargs):
        """ 取消指定批量任务接口 https://cloud.tencent.com/document/product/460/76892

        :param Bucket(string): 存储桶名称.
        :param JobId(string): 需要取消的批量任务ID.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 更新工作流状态接口
            response = client.ci_delete_inventory_trigger_jobs(
                Bucket='bucket'
                JobId='',
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = "/inventorytriggerjob/" + JobId
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        url = url + '?cancel'
        logger.info("ci_delete_inventory_trigger_jobs result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        return rt

    def ci_list_inventory_trigger_jobs(self, Bucket, StartCreationTime=None,
        EndCreationTime=None, OrderByTime='Desc', States='All', Size=10,
        NextToken='', Type='Workflow', WorkflowId='', JobId='', Name=None, **kwargs):
        """ 查询批量任务列表接口 https://cloud.tencent.com/document/product/460/76894

        :param Bucket(string): 存储桶名称.
        :param StartCreationTime(string): 开始时间.
        :param EndCreationTime(string): 结束时间.
        :param OrderByTime(string): 排序方式.
        :param States(string): 任务状态.
        :param Size(string): 任务个数.
        :param NextToken(string): 请求的上下文，用于翻页.
        :param Type(string): 拉取批量任务类型，工作流类型 Workflow 、任务类型 Job.
        :param WorkflowId(string): 工作流 ID.
        :param JobId(string): 批量触发任务 ID.
        :param Name(string): 批量触发任务名称.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_list_inventory_trigger_jobs(
                Bucket='bucket'
                QueueId='',
                Tag='Transcode'
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['type'] = Type
        params['orderByTime'] = OrderByTime
        params['states'] = States
        params['size'] = str(Size)
        params['nextToken'] = NextToken
        params['workflowId'] = WorkflowId
        params['jobId'] = JobId
        if Name is not None:
            params['name'] = Name
        if StartCreationTime is not None:
            params['startCreationTime'] = StartCreationTime
        if EndCreationTime is not None:
            params['endCreationTime'] = EndCreationTime

        params = format_values(params)
        path = 'inventorytriggerjob'
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_list_inventory_trigger_jobs result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        logger.debug("ci_list_inventory_trigger_jobs result, url=:{url} ,content=:{content}".format(
            url=url,
            content=rt.content))
        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['JobsDetail'])
        return data

    def ci_get_inventory_trigger_jobs(self, Bucket, JobID, **kwargs):
        """ 查询批量任务接口 https://cloud.tencent.com/document/product/460/76893

        :param Bucket(string): 存储桶名称.
        :param JobID(string): 任务ID
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_get_inventory_trigger_jobs(
                Bucket='bucket'
                JobIDs={}
            )
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        path = "/inventorytriggerjob/" + JobID
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_get_inventory_trigger_jobs result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)
        logger.debug("ci_get_inventory_trigger_jobs result, url=:{url} ,content=:{content}".format(
            url=url,
            content=rt.content))

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['JobsDetail'])
        return data

    def ci_create_template(self, Bucket, Template, **kwargs):
        """ 创建模板接口 https://cloud.tencent.com/document/product/460/78939

        :param Bucket(string): 存储桶名称.
        :param Name(string): 模板名称.
        :param Template(dict): 模板详细配置
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 创建成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建语音识别模板接口
            response = client.ci_create_template(
                Bucket=bucket_name,
                Name='templateName',
                Template='16k_zh',
            )
            print(response)
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/xml'

        params = format_values(params)

        xml_config = format_xml(data=Template, root='Request')
        path = "/template"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_create_template result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method='POST',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        return data

    def ci_update_template(self, Bucket, TemplateId, Template, **kwargs):
        """ 更新模板接口 https://cloud.tencent.com/document/product/460/78942

        :param Bucket(string): 存储桶名称.
        :param TemplateId(string): 需要更新的模板ID。
        :param Template(dict): 模板配置.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 更新成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 更新模板接口
            response = client.ci_update_template(
                Bucket=bucket_name,
                TemplateId='t1bdxxxxxxxxxxxxxxxxx94a9',
                Template={},
            )
            print(response)
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/xml'

        params = format_values(params)
        xml_config = format_xml(data=Template, root='Request')
        path = "/template/" + TemplateId
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_update_asr_template result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        return data

    def ci_get_template(self, Bucket, Category='Custom', Ids='', Name='', PageNumber=1, PageSize=10, **kwargs):
        """ 查询模板接口 https://cloud.tencent.com/document/product/460/46943

        :param Bucket(string): 存储桶名称.
        :param Category(string): Official（系统预设模板），Custom（自定义模板），默认值：Custom.
        :param Ids(string): 模板 ID，以,符号分割字符串.
        :param Name(string): 模板名称前缀.
        :param PageNumber(string): 第几页，默认值：1.
        :param PageSize(string): 每页个数，默认值：10.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询语音识别模板接口
            response = client.ci_get_template(
                Bucket=bucket_name,
            )
            print(response)
            return response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params['category'] = Category
        params['ids'] = Ids
        params['name'] = Name
        params['pageNumber'] = str(PageNumber)
        params['pageSize'] = str(PageSize)

        params = format_values(params)

        path = "/template"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_get_template result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        # 单个元素时将dict转为list
        format_dict(data, ['TemplateList'])
        return data

    def ci_delete_template(self, Bucket, TemplateId, **kwargs):
        """ 删除模板接口 https://cloud.tencent.com/document/product/460/46943

        :param Bucket(string): 存储桶名称.
        :param TemplateId(string): 需要删除的模板ID.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 删除指定语音识别模板
            response = client.ci_delete_template(
                Bucket=bucket_name,
                TemplateId='t1bdxxxxxxxxxxxxxxxxx94a9',
            )
            print(response)
            return response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = "/template/" + TemplateId
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)

        logger.info("ci_delete_template result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='DELETE',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        return data

    def ci_open_ai_bucket(self, Bucket, **kwargs):
        """ 开通AI内容识别服务 https://cloud.tencent.com/document/product/460/79593

        :param Bucket(string) 存储桶名称.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  开通AI内容识别服务
            response, data = client.ci_open_ai_bucket(
                Bucket='bucket'
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = "/" + "ai_bucket"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)

        logger.info("ci_open_ai_bucket result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='POST',
            url=url,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response:
            if response['Content-Type'] == 'application/xml':
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data

    def ci_get_ai_bucket(self, Regions='', BucketName='', BucketNames='', PageNumber='', PageSize='', **kwargs):
        """查询ai处理开通状态接口 https://cloud.tencent.com/document/product/460/79594

        :param Regions(string): 地域信息，例如 ap-shanghai、ap-beijing，若查询多个地域以“,”分隔字符串
        :param BucketName(string): 存储桶名称前缀，前缀搜索
        :param BucketNames(string): 存储桶名称，以“,”分隔，支持多个存储桶，精确搜索
        :param PageNumber(string): 第几页
        :param PageSize(string): 每页个数
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询媒体处理队列接口
            response = client.ci_get_ai_bucket(
                Regions='ap-chongqing,ap-shanghai',
                BucketName='demo',
                BucketNames='demo-1253960454,demo1-1253960454',
                PageNumber='2'，
                PageSize='3',
            )
            print response
        """
        return self.ci_get_bucket(Regions=Regions, BucketName=BucketName,
                                  BucketNames=BucketNames, PageNumber=PageNumber,
                                  PageSize=PageSize, Path='/ai_bucket', **kwargs)

    def ci_close_ai_bucket(self, Bucket, **kwargs):
        """ 关闭AI内容识别服务 https://cloud.tencent.com/document/product/460/95752

        :param Bucket(string) 存储桶名称.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  关闭AI内容识别服务
            response, data = client.ci_close_ai_bucket(
                Bucket='bucket'
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)

        path = "/" + "ai_bucket"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)

        logger.info("ci_close_ai_bucket result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='DELETE',
            url=url,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response:
            if response['Content-Type'] == 'application/xml' and 'Content-Length' in response and \
                response['Content-Length'] != 0:
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data

    def ci_update_ai_queue(self, Bucket, QueueId, Request={}, **kwargs):
        """ 更新图片处理队列接口

        :param Bucket(string): 存储桶名称.
        :param QueueId(string): 队列ID.
        :param Request(dict): 更新队列配置请求体.
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 创建任务接口
            response = client.ci_update_ai_queue(
                Bucket='bucket',
                QueueId='',
                Request={},
            )
            print response
        """
        return self.ci_update_media_queue(Bucket=Bucket, QueueId=QueueId,
                                          Request=Request, UrlPath="/ai_queue/", **kwargs)

    def ci_get_ai_queue(self, Bucket, State='All', QueueIds='', PageNumber='', PageSize='', **kwargs):
        """查询ai队列接口 https://cloud.tencent.com/document/product/460/79394

        :param Bucket(string): 存储桶名称.
        :param QueueIds(string): 队列 ID，以“,”符号分割字符串.
        :param State(string): 队列状态
        :param PageNumber(string): 第几页
        :param PageSize(string): 每页个数
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            # 查询媒体处理队列接口
            response = client.ci_get_ai_queue(
                Bucket='bucket'
            )
            print response
        """
        return self.ci_get_media_queue(Bucket=Bucket, State=State, QueueIds=QueueIds,
                                       PageNumber=PageNumber, PageSize=PageSize,
                                       UrlPath="/ai_queue", **kwargs)

    def ci_get_hls_play_key(self, Bucket, **kwargs):
        """ 获取 HLS 播放密钥 https://cloud.tencent.com/document/product/436/104292

            :param Bucket(string) 存储桶名称.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  获取 HLS 播放密钥
                response, data = client.ci_get_hls_play_key(
                    Bucket='bucket',
                    ObjectKey='',
                    Body={}
                )
                print data
                print response
            """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        path = "/playKey"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)

        logger.info(
            "ci_get_hls_play_key result, url=:{url} ,headers=:{headers}, params=:{params}".format(
                url=url,
                headers=headers,
                params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response:
            if response['Content-Type'] == 'application/xml' and 'Content-Length' in response and \
                response['Content-Length'] != 0:
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data

    def ci_update_hls_play_key(self, Bucket, MasterPlayKey=None, BackupPlayKey=None, **kwargs):
        """ 更新 HLS 播放密钥 https://cloud.tencent.com/document/product/436/104291

            :param Bucket(string) 存储桶名称.
            :param MasterPlayKey(string) 主播放密钥.
            :param BackupPlayKey(string) 备播放密钥.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  获取 HLS 播放密钥
                response, data = client.ci_get_hls_play_key(
                    Bucket='bucket',
                    ObjectKey='',
                    Body={}
                )
                print data
                print response
            """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        if MasterPlayKey is not None:
            params['masterPlayKey'] = MasterPlayKey
        if BackupPlayKey is not None:
            params['backupPlayKey'] = BackupPlayKey
        params = format_values(params)
        path = "/playKey"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("ci_update_hls_play_key result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='PUT',
            url=url,
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response:
            if response['Content-Type'] == 'application/xml' and 'Content-Length' in response and \
                response['Content-Length'] != 0:
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data


if __name__ == "__main__":
    pass
