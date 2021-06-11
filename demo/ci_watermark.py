# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client

import sys
import logging
import base64

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

# https://cloud.tencent.com/document/product/436/46782

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
# 添加盲水印
watermark_url = 'http://{bucket}.cos.{region}.myqcloud.com/watermark.png'.format(bucket=bucket_name, region=region)
watermark_url_base64 = bytes.decode(base64.b64encode(str.encode(watermark_url)))
print(watermark_url_base64)
response, data = client.ci_put_object_from_local_file(
    Bucket=bucket_name,
    LocalFilePath='sample.png',
    Key="sample.png",
    # pic operation json struct
    PicOperations='{"is_pic_info":1,"rules":[{"fileid": "format.png","rule": "watermark/3/type/1/image/' +
                  watermark_url_base64 + '" }]}'
)
print(response['x-cos-request-id'])
print(data['ProcessResults']['Object']['ETag'])

# 下载时添加盲水印
# download_url = http://examplebucket-1250000000.cos.ap-shanghai.myqcloud.com/sample.jpeg?watermark/3/type/3/text/watermark_url_base64

# 提取盲水印
sample_url = 'http://{bucket}.cos.{region}.myqcloud.com/sample.png'.format(bucket=bucket_name, region=region)
sample_url_base64 = bytes.decode(base64.b64encode(str.encode(sample_url)))
response, data = client.ci_put_object_from_local_file(
    Bucket=bucket_name,
    LocalFilePath='format.png',
    Key="format.png",
    # pic operation json struct
    PicOperations='{"is_pic_info":1,"rules":[{"fileid": "watermark.png","rule": "watermark/4/type/1/image/' +
                  sample_url_base64 + '" }]}'
)
print(response['x-cos-request-id'])
print(data['ProcessResults']['Object']['ETag'])
