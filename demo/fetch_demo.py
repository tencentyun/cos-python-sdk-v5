# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos import CosServiceError
from qcloud_cos import CosClientError

import sys
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 设置用户属性, 包括secret_id, secret_key, region
# appid已在配置中移除,请在参数Bucket中带上appid。Bucket由bucketname-appid组成
secret_id = ''  # 替换为用户的secret_id
secret_key = ''  # 替换为用户的secret_key
region = 'ap-beijing'  # 替换为用户的region
token = None  # 使用临时密钥需要传入Token，默认为空,可不填
scheme = 'http'
config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme=scheme)  # 获取配置对象
client = CosS3Client(config)

test_bucket = 'examplebucket-1250000000'
# 发起拉取任务
response = client.put_async_fetch_task(
    Bucket=test_bucket,
    FetchTaskConfiguration={
        'Url': 'http://examplebucket-1250000000.cos.ap-beijing.myqcloud.com/exampleobject',
        'Key': 'exampleobject'
    }
)

# 查询拉取任务
response = client.get_async_fetch_task(
    Bucket=test_bucket,
    TaskId=response['data']['taskid']
)
