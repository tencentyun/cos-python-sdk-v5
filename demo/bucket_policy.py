# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
import sys
import os
import logging
import json

# 正常情况日志级别使用 INFO，需要定位时可以修改为 DEBUG，此时 SDK 会打印和服务端的通信信息
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 1. 设置用户属性, 包括 secret_id, secret_key, region 等。Appid 已在 CosConfig 中移除，请在参数 Bucket 中带上 Appid。Bucket 由 BucketName-Appid 组成
secret_id = os.environ['COS_SECRET_ID']     # 用户的 SecretId，建议使用子账号密钥，授权遵循最小权限指引，降低使用风险。子账号密钥获取可参见 https://cloud.tencent.com/document/product/598/37140
secret_key = os.environ['COS_SECRET_KEY']   # 用户的 SecretKey，建议使用子账号密钥，授权遵循最小权限指引，降低使用风险。子账号密钥获取可参见 https://cloud.tencent.com/document/product/598/37140
region = 'ap-beijing'      # 替换为用户的 region，已创建桶归属的 region 可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
                           # COS 支持的所有 region 列表参见 https://cloud.tencent.com/document/product/436/6224
token = None               # 如果使用永久密钥不需要填入 token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见 https://cloud.tencent.com/document/product/436/14048
scheme = 'https'           # 指定使用 http/https 协议来访问 COS，默认为 https，可不填

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme=scheme)
client = CosS3Client(config)

# 设置存储桶策略
response = client.put_bucket_policy(
    Bucket='examplebucket-1250000000',
    Policy={
        "Statement": [
            {
                "Principal": {
                    "qcs": [
                    "qcs::cam::uin/100000000001:uin/100000000011"
                    ]
                },
                "Effect": "allow",
                "Action": [
                    "name/cos:GetBucket"
                ],
                "Resource": [
                    "qcs::cos:ap-guangzhou:uid/1250000000:examplebucket-1250000000/*"
                ],
                "condition": {
                    "ip_equal": {
                    "qcs:ip": "10.121.2.10/24"
                    }
                }
            }
        ],
        "version": "2.0"
    }
)

# 查询存储桶策略
response = client.get_bucket_policy(
    Bucket='examplebucket-1250000000',
)
policy = json.loads(response['Policy'])

# 删除存储桶策略
response = client.delete_bucket_policy(
    Bucket='examplebucket-1250000000',
)
