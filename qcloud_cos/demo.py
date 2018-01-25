# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos import CosServiceError
from qcloud_cos import CosClientError

import logging

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7

# pip安装指南:pip install -U cos-python-sdk-v5

# cos最新可用地域,参照https://www.qcloud.com/document/product/436/6224

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

# 设置用户属性, 包括secret_id, secret_key, region
secret_id = 'AKID15IsskiBQACGbAo6WhgcQbVls7HmuG00'     # 替换为用户的secret_id
secret_key = 'csivKvxxrMvSvQpMWHuIz12pThQQlWRW'     # 替换为用户的secret_key
region = 'ap-beijing-1'    # 替换为用户的region
token = ''                 # 使用临时秘钥需要传入Token，默认为空,可不填
config = CosConfig(Region=region, Secret_id=secret_id, Secret_key=secret_key, Token=token)  # 获取配置对象
client = CosS3Client(config)

# 文件流 简单上传
file_name = 'test.txt'
with open('test.txt', 'rb') as fp:
    response = client.put_object(
        Bucket='test04-123456789',
        Body=fp,
        Key=file_name,
        StorageClass='STANDARD',
        CacheControl='no-cache',
        ContentDisposition='download.txt'
    )
    print response['ETag']

# 字节流 简单上传
response = client.put_object(
    Bucket='test04-123456789',
    Body='abcdefg',
    Key=file_name,
    CacheControl='no-cache',
    ContentDisposition='download.txt'
)
print response['ETag']

# 文件下载 获取文件到本地
response = client.get_object(
    Bucket='test04-123456789',
    Key=file_name,
)
response['Body'].get_stream_to_file('output.txt')

# 文件下载 获取文件流
response = client.get_object(
    Bucket='test04-123456789',
    Key=file_name,
)
fp = response['Body'].get_raw_stream()
print fp.read(2)

# 文件下载 捕获异常
try:
    response = client.get_object(
        Bucket='test04-123456789',
        Key='not_exist.txt',
    )
    fp = response['Body'].get_raw_stream()
    print fp.read(2)
except CosServiceError as e:
    print e.get_origin_msg()
    print e.get_digest_msg()
    print e.get_status_code()
    print e.get_error_code()
    print e.get_error_msg()
    print e.get_resource_location()
    print e.get_trace_id()
    print e.get_request_id()
