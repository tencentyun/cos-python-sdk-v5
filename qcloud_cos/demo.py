# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos import CosServiceError
from qcloud_cos import CosClientError

import sys
import logging

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

# pip安装指南:pip install -U cos-python-sdk-v5

# cos最新可用地域,参照https://www.qcloud.com/document/product/436/6224

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 设置用户属性, 包括secret_id, secret_key, region
# appid已在配置中移除,请在参数Bucket中带上appid。Bucket由bucketname-appid组成
secret_id = 'AKID15IsskiBQACGbAo6WhgcQbVls7HmuG00'     # 替换为用户的secret_id
secret_key = 'csivKvxxrMvSvQpMWHuIz12pThQQlWRW'     # 替换为用户的secret_key
region = 'ap-beijing-1'    # 替换为用户的region
token = None               # 使用临时密钥需要传入Token，默认为空,可不填
config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
client = CosS3Client(config)

# 文件流 简单上传
file_name = 'test.txt'
with open('test.txt', 'rb') as fp:
    response = client.put_object(
        Bucket='test04-123456789',  # Bucket由bucketname-appid组成
        Body=fp,
        Key=file_name,
        StorageClass='STANDARD',
        ContentType='text/html; charset=utf-8'
    )
    print(response['ETag'])

# 字节流 简单上传
response = client.put_object(
    Bucket='test04-123456789',
    Body=b'abcdefg',
    Key=file_name
)
print(response['ETag'])

# 本地路径 简单上传
response = client.put_object_from_local_file(
    Bucket='test04-123456789',
    LocalFilePath='local.txt',
    Key=file_name,
)
print(response['ETag'])

# 设置HTTP头部 简单上传
response = client.put_object(
    Bucket='test04-123456789',
    Body=b'test',
    Key=file_name,
    ContentType='text/html; charset=utf-8'
)
print(response['ETag'])

# 设置自定义头部 简单上传
response = client.put_object(
    Bucket='test04-123456789',
    Body=b'test',
    Key=file_name,
    Metadata={
        'x-cos-meta-key1': 'value1',
        'x-cos-meta-key2': 'value2'
    }
)
print(response['ETag'])

# 高级上传接口(推荐)
response = client.upload_file(
    Bucket='test04-123456789',
    LocalFilePath='local.txt',
    Key=file_name,
    PartSize=10,
    MAXThread=10
)
print(response['ETag'])

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
print(fp.read(2))

# 文件下载 设置Response HTTP 头部
response = client.get_object(
    Bucket='test04-123456789',
    Key=file_name,
    ResponseContentType='text/html; charset=utf-8'
)
print(response['Content-Type'])
fp = response['Body'].get_raw_stream()
print(fp.read(2))

# 文件下载 指定下载范围
response = client.get_object(
    Bucket='test04-123456789',
    Key=file_name,
    Range='bytes=0-10'
)
fp = response['Body'].get_raw_stream()
print(fp.read())

# 文件下载 捕获异常
try:
    response = client.get_object(
        Bucket='test04-123456789',
        Key='not_exist.txt',
    )
    fp = response['Body'].get_raw_stream()
    print(fp.read(2))
except CosServiceError as e:
    print(e.get_origin_msg())
    print(e.get_digest_msg())
    print(e.get_status_code())
    print(e.get_error_code())
    print(e.get_error_msg())
    print(e.get_resource_location())
    print(e.get_trace_id())
    print(e.get_request_id())
