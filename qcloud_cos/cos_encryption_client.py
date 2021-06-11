# -*- coding=utf-8

import logging
from qcloud_cos import CosS3Client
from qcloud_cos.crypto import RSAProvider
from qcloud_cos.crypto import MetaHandle
from qcloud_cos.crypto import DataDecryptAdapter
from .cos_exception import CosClientError
from .cos_comm import *
from .cos_auth import CosS3Auth

logger = logging.getLogger(__name__)


class CosEncryptionClient(CosS3Client):
    """cos支持加密的客户端，封装相应请求"""

    def __init__(self, conf, provider, retry=1, session=None):
        """初始化client对象

        :param conf(CosConfig): 用户的配置.
        :param provider(BaseProvider): 客户端主密钥加密类
        :param retry(int): 失败重试的次数.
        :param session(object): http session.
        """
        super(CosEncryptionClient, self).__init__(conf, retry, session)
        self.provider = provider

    def put_object(self, Bucket, Body, Key, EnableMD5=False, **kwargs):
        """单文件加密上传接口，适用于小文件，最大不得超过5GB

        :param Bucket(string): 存储桶名称.
        :param Body(file|string): 上传的文件内容，类型为文件流或字节流.
        :param Key(string): COS路径.
        :param EnableMD5(bool): 是否需要SDK计算Content-MD5，打开此开关会增加上传耗时.
        :kwargs(dict): 设置上传的headers.
        :return(dict): 上传成功返回的结果，包含ETag等信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            provider = RSAProvider()
            client = CosEncryptionClient(config, provider)
            # 上传本地文件到cos
            with open('test.txt', 'rb') as fp:
                response = client.put_object(
                    Bucket='bucket',
                    Body=fp,
                    Key='test.txt'
                )
                print (response['ETag'])
        """
        encrypt_key, encrypt_start = self.provider.init_data_cipher()
        meta_handle = MetaHandle(encrypt_key, encrypt_start)
        kwargs = meta_handle.set_object_meta(kwargs)
        data = self.provider.make_data_encrypt_adapter(Body)
        response = super(CosEncryptionClient, self).put_object(Bucket, data, Key, EnableMD5, **kwargs)
        return response

    def get_object(self, Bucket, Key, **kwargs):
        """单文件加密下载接口

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置下载的headers.
        :return(dict): 下载成功返回的结果,包含Body对应的StreamBody,可以获取文件流或下载文件到本地.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            provider = RSAProvider()
            client = CosEncryptionClient(config, provider)
            # 下载cos上的文件到本地
            response = client.get_object(
                Bucket='bucket',
                Key='test.txt'
            )
            response['Body'].get_stream_to_file('local_file.txt')
        """
        response = self.head_object(Bucket, Key, **kwargs)
        meta_handle = MetaHandle()
        encrypt_key, encrypt_start = meta_handle.get_object_meta(response)

        headers = mapped(kwargs)
        offset = 0
        real_start = 0
        if 'Range' in headers:
            read_range = headers['Range']
            read_range = read_range.replace('bytes=', '').strip().split('-')
            if len(read_range) != 2:
                raise CosClientError('key:Range is wrong format, except first-last')

            real_start = self.provider.adjust_read_offset(int(read_range[0]))
            headers['Range'] = 'bytes=' + str(real_start) + '-' + read_range[1]
            offset = int(read_range[0]) - real_start
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

        self.provider.init_data_cipter_by_user(encrypt_key, encrypt_start, real_start)
        response['Body'] = self.provider.make_data_decrypt_adapter(rt, offset)
        return response

    def create_multipart_upload(self, Bucket, Key, **kwargs):
        """创建分块上传，适用于大文件上传

        :param Bucket(string): 存储桶名称.
        :param Key(string): COS路径.
        :param kwargs(dict): 设置请求headers.
        :return(dict): 初始化分块上传返回的结果，包含UploadId等信息.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            provider = RSAProvider()
            client = CosEncryptionClient(config, provider)
            # 创建分块上传
            response = client.create_multipart_upload(
                Bucket='bucket',
                Key='test.txt'
            )
        """
        encrypt_key, encrypt_start = self.provider.init_data_cipher()
        meta_handle = MetaHandle(encrypt_key, encrypt_start)
        kwargs = meta_handle.set_object_meta(kwargs)
        response = super(CosEncryptionClient, self).create_multipart_upload(Bucket, Key, **kwargs)
        return response

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
            provider = RSAProvider()
            client = CosEncryptionClient(config, provider)
            # 分块上传
            with open('test.txt', 'rb') as fp:
                data = fp.read(1024*1024)
                response = client.upload_part(
                    Bucket='bucket',
                    Body=data,
                    Key='test.txt'
                )
        """
        data = self.provider.make_data_encrypt_adapter(Body)
        response = super(CosEncryptionClient, self).upload_part(Bucket, Key, data, PartNumber, UploadId,
                                                                EnableMD5=False, **kwargs)
        return response
