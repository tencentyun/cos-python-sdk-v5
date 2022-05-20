# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos import CosServiceError
from qcloud_cos import CosClientError

import sys
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 设置用户属性, 包括 secret_id, secret_key, region等。Appid 已在CosConfig中移除，请在参数 Bucket 中带上 Appid。Bucket 由 BucketName-Appid 组成
secret_id = 'SecretId'     # 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_key = 'SecretKey'   # 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
region = 'ap-beijing'      # 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
                           # COS支持的所有region列表参见https://www.qcloud.com/document/product/436/6224
token = None               # 如果使用永久密钥不需要填入token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见https://cloud.tencent.com/document/product/436/14048
scheme = 'http'            # 指定使用 http/https 协议来访问 COS，默认为 https，可不填

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme=scheme)  # 获取配置对象
client = CosS3Client(config)

test_bucket = 'examplebucket-1250000000'
# 发起拉取任务
response = client.put_async_fetch_task(
    Bucket=test_bucket,
    FetchTaskConfiguration={
        'Url': 'http://examplebucket-1250000000.cos.ap-beijing.tencentcos.cn/exampleobject',
        'Key': 'exampleobject'
    }
)

# 查询拉取任务
response = client.get_async_fetch_task(
    Bucket=test_bucket,
    TaskId=response['data']['taskid']
)
