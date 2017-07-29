# -*- coding=utf-8
from cos_auth import CosS3Auth
import requests
import logging
import sys
import copy
import xml.dom.minidom


logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                datefmt='%a, %d %b %Y %H:%M:%S',
                filename='cos_s3.log',
                filemode='w')
logger = logging.getLogger(__name__)
fs_coding = sys.getfilesystemencoding()

maplist = {
           'ContentLength': 'Content-Length',
           'ContentType': 'Content-Type',
           'ContentMD5': 'Content-MD5',
           'CacheControl': 'Cache-Control',
           'ContentDisposition': 'Content-Disposition',
           'ContentEncoding': 'Content-Encoding',
           'Expires': 'Expires',
           'Metadata': 'x-cos-meta- *',
           'ACL': 'x-cos-acl',
           'GrantFullControl': 'x-cos-grant-full-control',
           'GrantWrite': 'x-cos-grant-write',
           'GrantRead': 'x-cos-grant-read',
           'StorageClass': 'x-cos-storage-class',
           'EncodingType': 'encoding-type'
           }


def to_unicode(s):
    if isinstance(s, unicode):
        return s
    else:
        return s.decode(fs_coding)


def dict_to_xml(data):
    """V5使用xml格式，将输入的dict转换为xml"""
    doc = xml.dom.minidom.Document()
    root = doc.createElement('CompleteMultipartUpload')
    doc.appendChild(root)

    if 'Parts' not in data.keys():
        logger.error("Invalid Parameter, Parts Is Required!")
        return ''

    for i in data['Parts']:
        nodePart = doc.createElement('Part')

        if 'PartNumber' not in i.keys():
            logger.error("Invalid Parameter, PartNumber Is Required!")
            return ''

        nodeNumber = doc.createElement('PartNumber')
        nodeNumber.appendChild(doc.createTextNode(str(i['PartNumber'])))

        if 'ETag' not in i.keys():
            logger.error("Invalid Parameter, ETag Is Required!")
            return ''

        nodeETag = doc.createElement('ETag')
        nodeETag.appendChild(doc.createTextNode(str(i['ETag'])))

        nodePart.appendChild(nodeNumber)
        nodePart.appendChild(nodeETag)
        root.appendChild(nodePart)
    return doc.toxml('utf-8')


def mapped(headers):
    """S3到COS参数的一个映射"""
    _headers = dict()
    for i in headers.keys():
        if i in maplist:
            _headers[maplist[i]] = headers[i]
    return _headers


class CosConfig(object):
    """config类，保存用户相关信息"""
    def __init__(self, Appid, Region, Access_id, Access_key):
        self._appid = Appid
        self._region = Region
        self._access_id = Access_id
        self._access_key = Access_key
        logger.info("config parameter-> appid: {appid}, region: {region}".format(
                 appid=Appid,
                 region=Region))

    def uri(self, bucket, path=None):
        """拼接url"""
        if path:
            url = u"http://{bucket}-{uid}.{region}.myqcloud.com/{path}".format(
                bucket=to_unicode(bucket),
                uid=self._appid,
                region=self._region,
                path=to_unicode(path)
            )
        else:
            url = u"http://{bucket}-{uid}.{region}.myqcloud.com".format(
                bucket=to_unicode(bucket),
                uid=self._appid,
                region=self._region
            )
        return url


class CosS3Client(object):
    """cos客户端类，封装相应请求"""
    def __init__(self, conf, retry=1, session=None):
        self._conf = conf
        self._retry = retry  # 重试的次数，分片上传时可适当增大
        if session is None:
            self._session = requests.session()
        else:
            self._session = session

    def put_object(self, Bucket, Body, Key, **kwargs):
        """单文件上传接口，适用于小文件，最大不得超过5GB"""
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("put object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        for j in range(self._retry):
            rt = self._session.put(
                url=url,
                auth=CosS3Auth(self._conf._access_id, self._conf._access_key),
                data=Body,
                headers=headers)
            if rt.status_code == 200:
                break
            logger.error(rt.text)
        return rt

    def get_object(self, Bucket, Key, **kwargs):
        """单文件下载接口"""
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("get object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        for j in range(self._retry):
            rt = self._session.get(
                url=url,
                auth=CosS3Auth(self._conf._access_id, self._conf._access_key),
                headers=headers)
            if rt.status_code == 200:
                break
            logger.error(rt.text)
        return rt

    def delete_object(self, Bucket, Key, **kwargs):
        """单文件删除接口"""
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("delete object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        for j in range(self._retry):
            rt = self._session.delete(
                url=url,
                auth=CosS3Auth(self._conf._access_id, self._conf._access_key),
                headers=headers)
            if rt.status_code == 204:
                break
            logger.error(rt.text)
        return rt

    def create_multipart_upload(self, Bucket, Key, **kwargs):
        """创建分片上传，适用于大文件上传"""
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=Key+"?uploads")
        logger.info("create multipart upload, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        for j in range(self._retry):
            rt = self._session.post(
                url=url,
                auth=CosS3Auth(self._conf._access_id, self._conf._access_key),
                headers=headers)
            if rt.status_code == 200:
                break
            logger.error(rt.text)
        return rt

    def upload_part(self, Bucket, Key, Body, PartNumber, UploadId, **kwargs):
        """上传分片，单个大小不得超过5GB"""
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=Key+"?partNumber={PartNumber}&uploadId={UploadId}".format(
            PartNumber=PartNumber,
            UploadId=UploadId))
        logger.info("put object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        for j in range(self._retry):
            rt = self._session.put(
                url=url,
                auth=CosS3Auth(self._conf._access_id, self._conf._access_key),
                data=Body)
            if rt.status_code == 200:
                break
            logger.error(rt.text)
        return rt

    def complete_multipart_upload(self, Bucket, Key, UploadId, MultipartUpload={}, **kwargs):
        """完成分片上传，组装后的文件不得小于1MB,否则会返回错误"""
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=Key+"?uploadId={UploadId}".format(UploadId=UploadId))
        logger.info("complete multipart upload, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        for j in range(self._retry):
            rt = self._session.post(
                url=url,
                auth=CosS3Auth(self._conf._access_id, self._conf._access_key),
                data=dict_to_xml(MultipartUpload),
                headers=headers)
            if rt.status_code == 200:
                break
            logger.error(rt.text)
        return rt

    def abort_multipart_upload(self, Bucket, Key, UploadId, **kwargs):
        """放弃一个已经存在的分片上传任务，删除所有已经存在的分片"""
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=Key+"?uploadId={UploadId}".format(UploadId=UploadId))
        logger.info("abort multipart upload, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        for j in range(self._retry):
            rt = self._session.delete(
                url=url,
                auth=CosS3Auth(self._conf._access_id, self._conf._access_key),
                headers=headers)
            if rt.status_code == 200:
                break
            logger.error(rt.text)
        return rt

    def list_parts(self, Bucket, Key, UploadId, **kwargs):
        """列出已上传的分片"""
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=Key+"?uploadId={UploadId}".format(UploadId=UploadId))
        logger.info("list multipart upload, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        for j in range(self._retry):
            rt = self._session.get(
                url=url,
                auth=CosS3Auth(self._conf._access_id, self._conf._access_key),
                headers=headers)
            if rt.status_code == 200:
                break
            logger.error(rt.text)
        return rt

    def create_bucket(self, Bucket, **kwargs):
        """创建一个bucket"""
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket)
        logger.info("create bucket, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        for j in range(self._retry):
            rt = self._session.put(
                url=url,
                auth=CosS3Auth(self._conf._access_id, self._conf._access_key),
                headers=headers)
            if rt.status_code == 200:
                break
            logger.error(rt.text)
        return rt

    def delete_bucket(self, Bucket, **kwargs):
        """删除一个bucket，bucket必须为空"""
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket)
        logger.info("delete bucket, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        for j in range(self._retry):
            rt = self._session.delete(
                url=url,
                auth=CosS3Auth(self._conf._access_id, self._conf._access_key),
                headers=headers)
            if rt.status_code == 204:
                break
            logger.error(rt.text)
        return rt

    def list_objects(self, Bucket, Delimiter="", EncodingType="url", Marker="", MaxKeys=100, Prefix="",  **kwargs):
        """获取文件列表"""
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket)
        logger.info("list objects, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        params = {
            'delimiter': Delimiter,
            'encoding-type': EncodingType,
            'marker': Marker,
            'max-keys': MaxKeys,
            'prefix': Prefix}
        for j in range(self._retry):
            rt = self._session.get(
                url=url,
                params=params,
                headers=headers,
                auth=CosS3Auth(self._conf._access_id, self._conf._access_key))
            if rt.status_code == 200:
                break
            logger.error(rt.text)
        return rt

    def head_object(self, Bucket, Key, **kwargs):
        """获取文件信息"""
        headers = mapped(kwargs)
        url = self._conf.uri(bucket=Bucket, path=Key)
        logger.info("head object, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        for j in range(self._retry):
            rt = self._session.head(
                url=url,
                auth=CosS3Auth(self._conf._access_id, self._conf._access_key),
                headers=headers)
            if rt.status_code == 200:
                break
            logger.error(rt.text)
        return rt


if __name__ == "__main__":
    pass
