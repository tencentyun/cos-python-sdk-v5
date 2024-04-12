# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client

import sys
import logging
import os

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

# 高级图片压缩 TPG压缩相关API请参考 https://cloud.tencent.com/document/product/460/60526
# 高级图片压缩 HEIF压缩相关API请参考 https://cloud.tencent.com/document/product/460/60525

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 设置用户属性, 包括 secret_id, secret_key, region等。Appid 已在CosConfig中移除，请在参数 Bucket 中带上 Appid。Bucket 由 BucketName-Appid 组成
secret_id = 'SecretId'     # 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_key = 'SecretKey'   # 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
region = 'ap-beijing'      # 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
                           # COS支持的所有region列表参见https://www.qcloud.com/document/product/436/6224
token = None               # 如果使用永久密钥不需要填入token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见https://cloud.tencent.com/document/product/436/14048

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
