# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client

import sys
import logging
import os

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

# https://cloud.tencent.com/document/product/436/48987

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 设置用户属性, 包括secret_id, secret_key, region
# appid已在配置中移除,请在参数Bucket中带上appid。Bucket由bucketname-appid组成
secret_id = ''  # 替换为用户的secret_id
secret_key = ''  # 替换为用户的secret_key
region = 'ap-guangzhou'  # 替换为用户的region
token = None  # 使用临时密钥需要传入Token，默认为空,可不填
config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
client = CosS3Client(config)

bucket_name = 'examplebucket-1250000000'

# TPG 压缩
response = client.ci_download_compress_image(
    Bucket=bucket_name,
    Key='sample.png',
    DestImagePath='sample.tpg',
    CompressType='tpg'
)
print(response['x-cos-request-id'])
assert os.path.exists('sample.tpg')

# HEIF 压缩
response = client.ci_download_compress_image(
    Bucket=bucket_name,
    Key='sample.png',
    DestImagePath='sample.heif',
    CompressType='heif'
)
print(response['x-cos-request-id'])
assert os.path.exists('sample.heif')
