# -*- coding=utf-8

import requests
import urllib
import logging
import hashlib
import base64
import os
import sys
import copy
import xml.dom.minidom
import xml.etree.ElementTree
from requests import Request, Session
from urllib import quote
from hashlib import md5
from streambody import StreamBody
from xml2dict import Xml2Dict
from dicttoxml import dicttoxml
from cos_auth import CosS3Auth
from cos_comm import *
from cos_threadpool import SimpleThreadPool
from cos_exception import CosClientError
from cos_exception import CosServiceError

logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                datefmt='%a, %d %b %Y %H:%M:%S',
                filename='cos_v5.log',
                filemode='w')
logger = logging.getLogger(__name__)
reload(sys)
sys.setdefaultencoding('utf-8')


class CosConfig(object):
    """config类，保存用户相关信息"""
    def __init__(self, Appid=None, Region=None, Secret_id=None, Secret_key=None, Token=None, Scheme=None, Timeout=None, Access_id=None, Access_key=None):
        """初始化，保存用户的信息

        :param Appid(string): 用户APPID.
        :param Region(string): 地域信息.
        :param Secret_id(string): 秘钥SecretId.
        :param Secret_key(string): 秘钥SecretKey.
        :param Token(string): 临时秘钥使用的token.
        :param Schema(string): http/https
        :param Timeout(int): http超时时间.
        :param Access_id(string): 秘钥AccessId(兼容).
        :param Access_key(string): 秘钥AccessKey(兼容).
        """
        self._appid = Appid
        self._region = format_region(Region)
        self._token = Token
        self._timeout = Timeout

        if Scheme is None:
            Scheme = 'http'
        if(Scheme != 'http' and Scheme != 'https'):
            raise CosClientError('Scheme can be only set to http/https')
        self._scheme = Scheme

        # 兼容(SecretId,SecretKey)以及(AccessId,AccessKey)
        if(Secret_id and Secret_key):
            self._secret_id = Secret_id
            self._secret_key = Secret_key
        elif(Access_id and Access_key):
            self._secret_id = Access_id
            self._secret_key = Access_key
        else:
            raise CosClientError('SecretId and SecretKey is Required!')

        logger.info("config parameter-> appid: {appid}, region: {region}".format(
                 appid=Appid,
                 region=Region))

    def uri(self, bucket, path=None, scheme=None, region=None):
        """拼接url

        :param bucket(string): 存储桶名称.
        :param path(string): 请求COS的路径.
        :return(string): 请求COS的URL地址.
        """
        bucket = format_bucket(bucket, self._appid)
        if scheme is None:
            scheme = self._scheme
        if region is None:
            region = self._region
        if path is not None:
            if path == "":
                raise CosClientError("Key can't be empty string")
            if path[0] == '/':
                path = path[1:]
            url = u"{scheme}://{bucket}.{region}.myqcloud.com/{path}".format(
                scheme=scheme,
                bucket=to_unicode(bucket),
                region=region,
                path=to_unicode(path)
            )
        else:
            url = u"{scheme}://{bucket}.{region}.myqcloud.com/".format(
                scheme=self._scheme,
                bucket=to_unicode(bucket),
                region=self._region
            )
        return url


class CosS3Client(object):
    """cos客户端类，封装相应请求"""
    def __init__(self, conf, retry=1, session=None):
        """初始化client对象

        :param conf(CosConfig): 用户的配置.
        :param retry(int): 失败重试的次数.
        :param session(object): http session.
        """
        self._conf = conf
        self._retry = retry  # 重试的次数，分片上传时可适当增大
        if session is None:
            self._session = requests.session()
        else:
            self._session = session

    def get_auth(self, Method, Bucket, Key='', Expired=300, Headers={}, Params={}):
        """获取签名

        :param Method(string): http method,如'PUT','GET'.
        :param Bucket(string): 存储桶名称.
        :param Key(string): 请求COS的路径.
        :param Expired(int): 签名有效时间,单位为s.
        :param headers(dict): 签名中的http headers.
        :param params(dict): 签名中的http params.
        :return (string): 计算出的V5签名.
        """
        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~'))
        r = Request(Method, url, headers=Headers, params=Params)
        auth = CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key, Params, Expired)
        return auth(r).headers['Authorization']

    def send_request(self, method, url, timeout=30, **kwargs):
        """封装request库发起http请求"""
        if self._conf._timeout is not None:  # 用户自定义超时时间
            timeout = self._conf._timeout
        if self._conf._token is not None:
            kwargs['headers']['x-cos-security-token'] = self._conf._token
        kwargs['headers']['User-Agent'] = 'cos-python-sdk-v5.3.2'
        try:
            for j in range(self._retry):
                if method == 'POST':
                    res = self._session.post(url, timeout=timeout, **kwargs)
                elif method == 'GET':
                    res = self._session.get(url, timeout=timeout, **kwargs)
                elif method == 'PUT':
                    res = self._session.put(url, timeout=timeout, **kwargs)
                elif method == 'DELETE':
                    res = self._session.delete(url, timeout=timeout, **kwargs)
                elif method == 'HEAD':
                    res = self._session.head(url, timeout=timeout, **kwargs)
                if res.status_code < 300:
                    return res
        except Exception as e:  # 捕获requests抛出的如timeout等客户端错误,转化为客户端错误
            logger.exception('url:%s, exception:%s' % (url, str(e)))
            raise CosClientError(str(e))

        if res.status_code >= 400:  # 所有的4XX,5XX都认为是COSServiceError
            if method == 'HEAD' and res.status_code == 404:   # Head 需要处理
                info = dict()
                info['code'] = 'NoSuchResource'
                info['message'] = 'The Resource You Head Not Exist'
                info['resource'] = url
                info['requestid'] = res.headers['x-cos-request-id']
                info['traceid'] = res.headers['x-cos-trace-id']
                logger.error(info)
                raise CosServiceError(method, info, res.status_code)
            else:
                msg = res.text
                if msg == '':  # 服务器没有返回Error Body时 给出头部的信息
                    msg = res.headers
                logger.error(msg)
                raise CosServiceError(method, msg, res.status_code)

    #  s3 object interface begin
    def put_object(self, Bucket, Body, Key, **kwargs):
        """单文件上传接口，适用于小文件，最大不得超过5GB

        :param Bucket(string): 存储桶名称.
        :param Body(file|string): 上传的文件内容，类型为文件流或字节流.
        :param Key(string): COS路径.
        :kwargs(dict): 设置上传的headers.
        :return(dict): 上传成功返回的结果，包含ETag等信息.
        """
        headers = mapped(kwargs)
        if 'Metadata' in headers.keys():
            for i in headers['Metadata'].keys():
                headers[i] = headers['Metadata'][i]
            headers.pop('Metadata')

        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~'))  # 提前对key做encode
        logger.info("put object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        Body = deal_with_empty_file_stream(Body)
        rt = self.send_request(
            method='PUT',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key),
            data=Body,
            headers=headers)

        response = rt.headers
        return response

    def get_object(self, Bucket, Key, **kwargs):
        """单文件下载接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置下载的headers.
        :return(dict): 下载成功返回的结果,包含Body对应的StreamBody,可以获取文件流或下载文件到本地.
        """
        headers = mapped(kwargs)
        params = {}
        for key in headers.keys():
            if key.startswith("response"):
                params[key] = headers[key]
                headers.pop(key)
        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~'))
        logger.info("get object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
                method='GET',
                url=url,
                stream=True,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key),
                params=params,
                headers=headers)

        response = rt.headers
        response['Body'] = StreamBody(rt)

        return response

    def get_presigned_download_url(self, Bucket, Key, Expired=300):
        """生成预签名的下载url

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Expired(int): 签名过期时间.
        :return(string): 预先签名的下载URL.
        """
        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~'))
        sign = self.get_auth(Method='GET', Bucket=Bucket, Key=Key, Expired=300)
        url = url + '?sign=' + urllib.quote(sign)
        return url

    def delete_object(self, Bucket, Key, **kwargs):
        """单文件删除接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~'))
        logger.info("delete object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
                method='DELETE',
                url=url,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key),
                headers=headers)
        return None

    def delete_objects(self, Bucket, Delete={}, **kwargs):
        """文件批量删除接口,单次最多支持1000个object

        :param Bucket(string): 存储桶名称.
        :param Delete(dict): 批量删除的object信息.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 批量删除的结果.
        """
        lst = ['<Object>', '</Object>']  # 类型为list的标签
        xml_config = format_xml(data=Delete, root='Delete', lst=lst)
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        url = self._conf.uri(bucket=Bucket, path="?delete")
        logger.info("put bucket replication, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='POST',
            url=url,
            data=xml_config,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        data = xml_to_dict(rt.text)
        if 'Deleted' in data.keys() and not isinstance(data['Deleted'], list):
            lst = []
            lst.append(data['Deleted'])
            data['Deleted'] = lst
        if 'Error' in data.keys() and not isinstance(data['Error'], list):
            lst = []
            lst.append(data['Error'])
            data['Error'] = lst
        return data

    def head_object(self, Bucket, Key, **kwargs):
        """获取文件信息

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 文件的metadata信息.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~'))
        logger.info("head object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='HEAD',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key),
            headers=headers)
        return rt.headers

    def copy_object(self, Bucket, Key, CopySource, CopyStatus='Copy', **kwargs):
        """文件拷贝，文件信息修改

        :param Bucket(string): 存储桶名称.
        :param Key(string): 上传COS路径.
        :param CopySource(dict): 拷贝源,包含Appid,Bucket,Region,Key.
        :param CopyStatus(string): 拷贝状态,可选值'Copy'|'Replaced'.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 拷贝成功的结果.
        """
        headers = mapped(kwargs)
        if 'Metadata' in headers.keys():
            for i in headers['Metadata'].keys():
                headers[i] = headers['Metadata'][i]
            headers.pop('Metadata')
        headers['x-cos-copy-source'] = gen_copy_source_url(CopySource)
        if CopyStatus != 'Copy' and CopyStatus != 'Replaced':
            raise CosClientError('CopyStatus must be Copy or Replaced')
        headers['x-cos-metadata-directive'] = CopyStatus
        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~'))
        logger.info("copy object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key),
            headers=headers)
        data = xml_to_dict(rt.text)
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
        """
        headers = mapped(kwargs)
        headers['x-cos-copy-source'] = gen_copy_source_url(CopySource)
        headers['x-cos-copy-source-range'] = CopySourceRange
        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~')+"?partNumber={PartNumber}&uploadId={UploadId}".format(
            PartNumber=PartNumber,
            UploadId=UploadId))
        logger.info("upload part copy, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
                method='PUT',
                url=url,
                headers=headers,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key))
        data = xml_to_dict(rt.text)
        return data

    def create_multipart_upload(self, Bucket, Key, **kwargs):
        """创建分片上传，适用于大文件上传

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 初始化分块上传返回的结果，包含UploadId等信息.
        """
        headers = mapped(kwargs)
        if 'Metadata' in headers.keys():
            for i in headers['Metadata'].keys():
                headers[i] = headers['Metadata'][i]
            headers.pop('Metadata')

        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~')+"?uploads")
        logger.info("create multipart upload, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
                method='POST',
                url=url,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key),
                headers=headers)

        data = xml_to_dict(rt.text)
        return data

    def upload_part(self, Bucket, Key, Body, PartNumber, UploadId, **kwargs):
        """上传分片，单个大小不得超过5GB

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param Body(file|string): 上传分块的内容,可以为文件流或者字节流.
        :param PartNumber(int): 上传分块的编号.
        :param UploadId(string): 分块上传创建的UploadId.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 上传成功返回的结果，包含单个分块ETag等信息.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~')+"?partNumber={PartNumber}&uploadId={UploadId}".format(
            PartNumber=PartNumber,
            UploadId=UploadId))
        logger.info("put object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        Body = deal_with_empty_file_stream(Body)
        rt = self.send_request(
                method='PUT',
                url=url,
                headers=headers,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key),
                data=Body)
        response = dict()
        logger.debug("local md5: {key}".format(key=rt.headers['ETag'][1:-1]))
        logger.debug("cos md5: {key}".format(key=md5(Body).hexdigest()))
        if md5(Body).hexdigest() != rt.headers['ETag'][1:-1]:
            raise CosClientError("MD5 inconsistencies")
        response['ETag'] = rt.headers['ETag']
        return response

    def complete_multipart_upload(self, Bucket, Key, UploadId, MultipartUpload={}, **kwargs):
        """完成分片上传,除最后一块分块块大小必须大于等于1MB,否则会返回错误.

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param UploadId(string): 分块上传创建的UploadId.
        :param MultipartUpload(dict): 所有分块的信息,包含Etag和PartNumber.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 上传成功返回的结果，包含整个文件的ETag等信息.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~')+"?uploadId={UploadId}".format(UploadId=UploadId))
        logger.info("complete multipart upload, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
                method='POST',
                url=url,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key),
                data=dict_to_xml(MultipartUpload),
                timeout=1200,  # 分片上传大文件的时间比较长，设置为20min
                headers=headers)
        data = xml_to_dict(rt.text)
        return data

    def abort_multipart_upload(self, Bucket, Key, UploadId, **kwargs):
        """放弃一个已经存在的分片上传任务，删除所有已经存在的分片.

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param UploadId(string): 分块上传创建的UploadId.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~')+"?uploadId={UploadId}".format(UploadId=UploadId))
        logger.info("abort multipart upload, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
                method='DELETE',
                url=url,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key),
                headers=headers)
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
        """
        headers = mapped(kwargs)
        params = {
            'uploadId': UploadId,
            'part-number-marker': PartNumberMarker,
            'max-parts': MaxParts}
        if EncodingType:
            if EncodingType != 'url':
                raise CosClientError('EncodingType must be url')
            params['encoding-type'] = EncodingType

        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~'))
        logger.info("list multipart upload, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
                method='GET',
                url=url,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key),
                headers=headers,
                params=params)
        data = xml_to_dict(rt.text)
        if 'Part' in data.keys() and isinstance(data['Part'], dict):  # 只有一个part，将dict转为list，保持一致
            lst = []
            lst.append(data['Part'])
            data['Part'] = lst
        return data

    def put_object_acl(self, Bucket, Key, AccessControlPolicy={}, **kwargs):
        """设置object ACL

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param AccessControlPolicy(dict): 设置object ACL规则.
        :param kwargs(dict): 通过headers来设置ACL.
        :return: None.
        """
        lst = [  # 类型为list的标签
            '<Grant>',
            '</Grant>']
        xml_config = ""
        if AccessControlPolicy:
            xml_config = format_xml(data=AccessControlPolicy, root='AccessControlPolicy', lst=lst)
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~')+"?acl")
        logger.info("put object acl, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            data=xml_config,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key),
            headers=headers)
        return None

    def get_object_acl(self, Bucket, Key, **kwargs):
        """获取object ACL

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Object对应的ACL信息.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~')+"?acl")
        logger.info("get object acl, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key),
            headers=headers)
        data = xml_to_dict(rt.text, "type", "Type")
        if data['AccessControlList'] is not None and isinstance(data['AccessControlList']['Grant'], dict):
            lst = []
            lst.append(data['AccessControlList']['Grant'])
            data['AccessControlList']['Grant'] = lst
        return data

    # s3 bucket interface begin
    def create_bucket(self, Bucket, **kwargs):
        """创建一个bucket

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket)
        logger.info("create bucket, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
                method='PUT',
                url=url,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
                headers=headers)
        return None

    def delete_bucket(self, Bucket, **kwargs):
        """删除一个bucket，bucket必须为空

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
                method='DELETE',
                url=url,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
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
        """
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
            params['encoding-type'] = EncodingType
        rt = self.send_request(
                method='GET',
                url=url,
                params=params,
                headers=headers,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key))

        data = xml_to_dict(rt.text)
        if 'Contents' in data.keys() and isinstance(data['Contents'], dict):  # 只有一个Contents，将dict转为list，保持一致
                lst = []
                lst.append(data['Contents'])
                data['Contents'] = lst
        return data

    def list_objects_versions(self, Bucket, Prefix="", Delimiter="", KeyMarker="", VersionIdMarker="", MaxKeys=1000, EncodingType="", **kwargs):
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
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path='?versions')
        logger.info("list objects versions, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        params = {
            'prefix': Prefix,
            'delimiter': Delimiter,
            'key-marker': KeyMarker,
            'version-id-marker': VersionIdMarker,
            'max-keys': MaxKeys
            }
        if EncodingType:
            if EncodingType != 'url':
                raise CosClientError('EncodingType must be url')
            params['encoding-type'] = EncodingType
        rt = self.send_request(
                method='GET',
                url=url,
                params=params,
                headers=headers,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key))

        data = xml_to_dict(rt.text)
        if 'Version' in data.keys() and isinstance(data['Version'], dict):  # 只有一个Version，将dict转为list，保持一致
                lst = []
                lst.append(data['Version'])
                data['Version'] = lst
        if 'DeleteMarker' in data.keys() and isinstance(data['DeleteMarker'], dict):
                lst = []
                lst.append(data['DeleteMarker'])
                data['DeleteMarker'] = lst
        return data

    def list_multipart_uploads(self, Bucket, Prefix="", Delimiter="", KeyMarker="", UploadIdMarker="", MaxUploads=1000, EncodingType="", **kwargs):
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
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path='?uploads')
        logger.info("get multipart uploads, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        params = {
            'prefix': Prefix,
            'delimiter': Delimiter,
            'key-marker': KeyMarker,
            'upload-id-marker': UploadIdMarker,
            'max-uploads': MaxUploads
            }
        if EncodingType:
            if EncodingType != 'url':
                raise CosClientError('EncodingType must be url')
            params['encoding-type'] = EncodingType
        rt = self.send_request(
                method='GET',
                url=url,
                params=params,
                headers=headers,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key))

        data = xml_to_dict(rt.text)
        if 'Upload' in data.keys() and isinstance(data['Upload'], dict):  # 只有一个Upload，将dict转为list，保持一致
                lst = []
                lst.append(data['Upload'])
                data['Upload'] = lst
        return data

    def head_bucket(self, Bucket, **kwargs):
        """确认bucket是否存在

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket)
        logger.info("head bucket, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='HEAD',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        return None

    def put_bucket_acl(self, Bucket, AccessControlPolicy={}, **kwargs):
        """设置bucket ACL

        :param Bucket(string): 存储桶名称.
        :param AccessControlPolicy(dict): 设置bucket ACL规则.
        :param kwargs(dict): 通过headers来设置ACL.
        :return: None.
        """
        lst = [  # 类型为list的标签
            '<Grant>',
            '</Grant>']
        xml_config = ""
        if AccessControlPolicy:
            xml_config = format_xml(data=AccessControlPolicy, root='AccessControlPolicy', lst=lst)
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path="?acl")
        logger.info("put bucket acl, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            data=xml_config,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        return None

    def get_bucket_acl(self, Bucket, **kwargs):
        """获取bucket ACL

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置headers.
        :return(dict): Bucket对应的ACL信息.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path="?acl")
        logger.info("get bucket acl, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        data = xml_to_dict(rt.text, "type", "Type")
        if data['AccessControlList'] is not None and not isinstance(data['AccessControlList']['Grant'], list):
            lst = []
            lst.append(data['AccessControlList']['Grant'])
            data['AccessControlList']['Grant'] = lst
        return data

    def put_bucket_cors(self, Bucket, CORSConfiguration={}, **kwargs):
        """设置bucket CORS

        :param Bucket(string): 存储桶名称.
        :param CORSConfiguration(dict): 设置Bucket跨域规则.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        lst = [  # 类型为list的标签
            '<CORSRule>',
            '<AllowedOrigin>',
            '<AllowedMethod>',
            '<AllowedHeader>',
            '<ExposeHeader>',
            '</CORSRule>',
            '</AllowedOrigin>',
            '</AllowedMethod>',
            '</AllowedHeader>',
            '</ExposeHeader>']
        xml_config = format_xml(data=CORSConfiguration, root='CORSConfiguration', lst=lst)
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        url = self._conf.uri(bucket=Bucket, path="?cors")
        logger.info("put bucket cors, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            data=xml_config,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        return None

    def get_bucket_cors(self, Bucket, **kwargs):
        """获取bucket CORS

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 获取Bucket对应的跨域配置.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path="?cors")
        logger.info("get bucket cors, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        data = xml_to_dict(rt.text)
        if 'CORSRule' in data.keys() and not isinstance(data['CORSRule'], list):
            lst = []
            lst.append(data['CORSRule'])
            data['CORSRule'] = lst
        if 'CORSRule' in data.keys():
            allow_lst = ['AllowedOrigin', 'AllowedMethod', 'AllowedHeader', 'ExposeHeader']
            for rule in data['CORSRule']:
                for text in allow_lst:
                    if text in rule.keys() and not isinstance(rule[text], list):
                        lst = []
                        lst.append(rule[text])
                        rule[text] = lst
        return data

    def delete_bucket_cors(self, Bucket, **kwargs):
        """删除bucket CORS

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path="?cors")
        logger.info("delete bucket cors, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        return None

    def put_bucket_lifecycle(self, Bucket, LifecycleConfiguration={}, **kwargs):
        """设置bucket LifeCycle

        :param Bucket(string): 存储桶名称.
        :param LifecycleConfiguration(dict): 设置Bucket的生命周期规则.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        lst = ['<Rule>', '<Tag>', '</Tag>', '</Rule>']  # 类型为list的标签
        xml_config = format_xml(data=LifecycleConfiguration, root='LifecycleConfiguration', lst=lst)
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        url = self._conf.uri(bucket=Bucket, path="?lifecycle")
        logger.info("put bucket lifecycle, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            data=xml_config,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        return None

    def get_bucket_lifecycle(self, Bucket, **kwargs):
        """获取bucket LifeCycle

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket对应的生命周期配置.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path="?lifecycle")
        logger.info("get bucket cors, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        data = xml_to_dict(rt.text)
        if 'Rule' in data.keys() and not isinstance(data['Rule'], list):
            lst = []
            lst.append(data['Rule'])
            data['Rule'] = lst
        return data

    def delete_bucket_lifecycle(self, Bucket, **kwargs):
        """删除bucket LifeCycle

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path="?lifecycle")
        logger.info("delete bucket cors, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        return None

    def put_bucket_versioning(self, Bucket, Status, **kwargs):
        """设置bucket版本控制

        :param Bucket(string): 存储桶名称.
        :param Status(string): 设置Bucket版本控制的状态，可选值为'Enabled'|'Suspended'.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path="?versioning")
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
            data=xml_config,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        return None

    def get_bucket_versioning(self, Bucket, **kwargs):
        """查询bucket版本控制

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 获取Bucket版本控制的配置.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path="?versioning")
        logger.info("get bucket versioning, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        data = xml_to_dict(rt.text)
        return data

    def get_bucket_location(self, Bucket, **kwargs):
        """查询bucket所属地域

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 存储桶的地域信息.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path="?location")
        logger.info("get bucket location, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        root = xml.etree.ElementTree.fromstring(rt.text)
        data = dict()
        data['LocationConstraint'] = root.text
        return data

    def put_bucket_replication(self, Bucket, ReplicationConfiguration={}, **kwargs):
        """设置bucket跨区域复制配置

        :param Bucket(string): 存储桶名称.
        :param ReplicationConfiguration(dict): 设置Bucket的跨区域复制规则.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        lst = ['<Rule>', '</Rule>']  # 类型为list的标签
        xml_config = format_xml(data=ReplicationConfiguration, root='ReplicationConfiguration', lst=lst)
        headers = mapped(kwargs)
        headers['Content-MD5'] = get_md5(xml_config)
        headers['Content-Type'] = 'application/xml'
        url = self._conf.uri(bucket=Bucket, path="?replication")
        logger.info("put bucket replication, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='PUT',
            url=url,
            data=xml_config,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        return None

    def get_bucket_replication(self, Bucket, **kwargs):
        """获取bucket 跨区域复制配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return(dict): Bucket对应的跨区域复制配置.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path="?replication")
        logger.info("get bucket replication, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='GET',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        data = xml_to_dict(rt.text)
        if 'Rule' in data.keys() and not isinstance(data['Rule'], list):
            lst = []
            lst.append(data['Rule'])
            data['Rule'] = lst
        return data

    def delete_bucket_replication(self, Bucket, **kwargs):
        """删除bucket 跨区域复制配置

        :param Bucket(string): 存储桶名称.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path="?replication")
        logger.info("delete bucket replication, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='DELETE',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
            headers=headers)
        return None

    # service interface begin
    def list_buckets(self, **kwargs):
        """列出所有bucket

        :return(dict): 账号下bucket相关信息.
        """
        headers = mapped(kwargs)
        url = 'http://service.cos.myqcloud.com/'
        rt = self.send_request(
                method='GET',
                url=url,
                headers=headers,
                auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key),
                )
        data = xml_to_dict(rt.text)
        if data['Buckets'] is not None and not isinstance(data['Buckets']['Bucket'], list):
            lst = []
            lst.append(data['Buckets']['Bucket'])
            data['Buckets']['Bucket'] = lst
        return data

    # Advanced interface
    def _upload_part(self, bucket, key, local_path, offset, size, part_num, uploadid, md5_lst):
        """从本地文件中读取分块, 上传单个分块,将结果记录在md5——list中

        :param bucket(string): 存储桶名称.
        :param key(string): 分块上传路径名.
        :param local_path(string): 本地文件路径名.
        :param offset(int): 读取本地文件的分块偏移量.
        :param size(int): 读取本地文件的分块大小.
        :param part_num(int): 上传分块的序号.
        :param uploadid(string): 分块上传的uploadid.
        :param md5_lst(list): 保存上传成功分块的MD5和序号.
        :return: None.
        """
        with open(local_path, 'rb') as fp:
            fp.seek(offset, 0)
            data = fp.read(size)
        rt = self.upload_part(bucket, key, data, part_num, uploadid)
        md5_lst.append({'PartNumber': part_num, 'ETag': rt['ETag']})
        return None

    def upload_file(self, Bucket, Key, LocalFilePath, PartSize=10, MAXThread=5, **kwargs):
        """小于等于100MB的文件简单上传，大于等于100MB的文件使用分块上传

        :param Bucket(string): 存储桶名称.
        :param key(string): 分块上传路径名.
        :param LocalFilePath(string): 本地文件路径名.
        :param PartSize(int): 分块的大小设置.
        :param MAXThread(int): 并发上传的最大线程数.
        :param kwargs(dict): 设置请求headers.
        :return: None.
        """
        file_size = os.path.getsize(LocalFilePath)
        if file_size <= 1024*1024*100:
            with open(LocalFilePath, 'rb') as fp:
                rt = self.put_object(Bucket=Bucket, Key=Key, Body=fp, **kwargs)
            return rt
        else:
            part_size = 1024*1024*PartSize  # 默认按照10MB分块,最大支持100G的文件，超过100G的分块数固定为10000
            last_size = 0  # 最后一块可以小于1MB
            parts_num = file_size / part_size
            last_size = file_size % part_size

            if last_size != 0:
                parts_num += 1
            if parts_num > 10000:
                parts_num = 10000
                part_size = file_size / parts_num
                last_size = file_size % parts_num
                last_size += part_size

            # 创建分块上传
            rt = self.create_multipart_upload(Bucket=Bucket, Key=Key, **kwargs)
            uploadid = rt['UploadId']

            # 上传分块
            offset = 0  # 记录文件偏移量
            lst = list()  # 记录分块信息
            pool = SimpleThreadPool(MAXThread)

            for i in range(1, parts_num+1):
                if i == parts_num:  # 最后一块
                    pool.add_task(self._upload_part, Bucket, Key, LocalFilePath, offset, file_size-offset, i, uploadid, lst)
                else:
                    pool.add_task(self._upload_part, Bucket, Key, LocalFilePath, offset, part_size, i, uploadid, lst)
                    offset += part_size

            pool.wait_completion()
            lst = sorted(lst, key=lambda x: x['PartNumber'])  # 按PartNumber升序排列

            # 完成分片上传
            try:
                rt = self.complete_multipart_upload(Bucket=Bucket, Key=Key, UploadId=uploadid, MultipartUpload={'Part': lst})
            except Exception as e:
                abort_response = self.abort_multipart_upload(Bucket=Bucket, Key=Key, UploadId=uploadid)
                raise e
            return rt

    def _inner_head_object(self, CopySource):
        """查询源文件的长度"""
        bucket, path, region = get_copy_source_info(CopySource)
        url = self._conf.uri(bucket=bucket, path=quote(path, '/-_.~'), scheme=self._conf._scheme, region=region)
        rt = self.send_request(
            method='HEAD',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, path),
            headers={})
        return int(rt.headers['Content-Length'])

    def _upload_part_copy(self, bucket, key, part_number, upload_id, copy_source, copy_source_range, md5_lst):
        """拷贝指定文件至分块上传,记录结果到lst中去

        :param bucket(string): 存储桶名称.
        :param key(string): 上传COS路径.
        :param part_number(int): 上传分块的编号.
        :param upload_id(string): 分块上传创建的UploadId.
        :param copy_source(dict): 拷贝源,包含Appid,Bucket,Region,Key.
        :param copy_source_range(string): 拷贝源的字节范围,bytes=first-last。
        :param md5_lst(list): 保存上传成功分块的MD5和序号.
        :return: None.
        """
        print part_number
        rt = self.upload_part_copy(bucket, key, part_number, upload_id, copy_source, copy_source_range)
        md5_lst.append({'PartNumber': part_number, 'ETag': rt['ETag']})
        return None

    def _check_same_region(self, dst_region, CopySource):
        if 'Region' in CopySource.keys():
            src_region = CopySource['Region']
            src_region = format_region(src_region)
        else:
            raise CosClientError('CopySource Need Parameter Region')
        if src_region == dst_region:
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
        """
        # 同园区直接走copy_object
        if self._check_same_region(self._conf._region, CopySource):
            response = self.copy_object(Bucket=Bucket, Key=Key, CopySource=CopySource, CopyStatus=CopyStatus, **kwargs)
            return response

        # 不同园区查询拷贝源object的content-length
        file_size = self._inner_head_object(CopySource)
        # 如果源文件大小小于5G，则直接调用copy_object接口
        if file_size < SINGLE_UPLOAD_LENGTH:
            response = self.copy_object(Bucket=Bucket, Key=Key, CopySource=CopySource, CopyStatus=CopyStatus, **kwargs)
            return response

        # 如果源文件大小大于等于5G，则先创建分块上传，在调用upload_part
        part_size = 1024*1024*PartSize  # 默认按照10MB分块
        last_size = 0  # 最后一块可以小于1MB
        parts_num = file_size / part_size
        last_size = file_size % part_size
        if last_size != 0:
            parts_num += 1
        if parts_num > 10000:
            parts_num = 10000
            part_size = file_size / parts_num
            last_size = file_size % parts_num
            last_size += part_size
        # 创建分块上传
        rt = self.create_multipart_upload(Bucket=Bucket, Key=Key, **kwargs)
        uploadid = rt['UploadId']

        # 上传分块拷贝
        offset = 0  # 记录文件偏移量
        lst = list()  # 记录分块信息
        pool = SimpleThreadPool(MAXThread)

        for i in range(1, parts_num+1):
            if i == parts_num:  # 最后一块
                copy_range = gen_copy_source_range(offset, file_size-1)
                pool.add_task(self._upload_part_copy, Bucket, Key, i, uploadid, CopySource, copy_range, lst)
            else:
                copy_range = gen_copy_source_range(offset, offset+part_size-1)
                pool.add_task(self._upload_part_copy, Bucket, Key, i, uploadid, CopySource, copy_range, lst)
                offset += part_size

        pool.wait_completion()
        lst = sorted(lst, key=lambda x: x['PartNumber'])  # 按PartNumber升序排列
        # 完成分片上传
        try:
            rt = self.complete_multipart_upload(Bucket=Bucket, Key=Key, UploadId=uploadid, MultipartUpload={'Part': lst})
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
        headers = mapped(kwargs)
        if 'Metadata' in headers.keys():
            for i in headers['Metadata'].keys():
                headers[i] = headers['Metadata'][i]
            headers.pop('Metadata')

        url = self._conf.uri(bucket=Bucket, path=quote(Key, '/-_.~')+"?append&position="+str(Position))
        logger.info("append object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        Body = deal_with_empty_file_stream(Data)
        rt = self.send_request(
            method='POST',
            url=url,
            auth=CosS3Auth(self._conf._secret_id, self._conf._secret_key, Key),
            data=Body,
            headers=headers)
        response = rt.headers
        return response


if __name__ == "__main__":
    pass
