# -*- coding=utf-8
"""高性能桶（COS Rapid Bucket / fusion-io）session 鉴权示例。

与普通桶不同，高性能桶的数据面请求需要先通过 CreateSession 换取临时 session
凭证再签名。CosS3Client 在识别到 rapid 桶后会自动完成这一步：按桶缓存 session、
基础 AK 变化后重签、数据面 403 时淘汰缓存并重试一次。

运行前请设置环境变量 COS_SECRET_ID / COS_SECRET_KEY，并把 Bucket 换成你自己的
高性能桶名（形如 <short>-x--<appid>）。

预签名 URL 的实际可用窗口是 min(签名窗口, token 剩余寿命, 网关种子剩余寿命)。
种子寿命通常不低于 token。
"""
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos.cos_exception import CosClientError, CosServiceError

import sys
import os
import logging
import requests

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

secret_id = os.environ['COS_SECRET_ID']
secret_key = os.environ['COS_SECRET_KEY']
region = 'ap-guangzhou'
bucket = 'example-x--1250000000'
token = None
scheme = 'http'

# EnableRapidDomain 会把 Bucket Endpoint 设为
# cosrapid.<region>.myqcloud.com，并把 ServiceDomain 设为
# service.cosrapid.<region>.myqcloud.com。
# 本地 IP:Port 联调可改用 EnableSessionAuth=True，并设置 IP/Port 或 Domain。
config = CosConfig(
    Region=region,
    SecretId=secret_id,
    SecretKey=secret_key,
    Token=token,
    Scheme=scheme,
    EnableRapidDomain=True)
client = CosS3Client(config)

key = 'rapid-example/hello.txt'
payload = b'hello rapid bucket'

try:
    client.put_object(Bucket=bucket, Key=key, Body=payload)
    print('PutObject OK (session 自动创建并签名)')

    resp = client.get_object(Bucket=bucket, Key=key)
    body = resp['Body'].get_raw_stream().read()
    print('GetObject OK: %s' % body)

    dst_key = 'rapid-example/hello-renamed.txt'
    client.rename_object(Bucket=bucket, Key=dst_key, RenameSource=key)
    print('RenameObject OK: %s -> %s' % (key, dst_key))
    # 防覆盖: client.rename_object(..., ForbidOverwrite='true')

    presigned = client.get_session_presigned_url(
        Bucket=bucket, Key=dst_key, Method='GET', Expired=600)
    print('Presigned URL: %s' % presigned)
    # GET/HEAD 默认申请 ReadOnly session；token 在 query 的 x-cos-security-token。
    # 不支持 SignMerged（网关只接受拆开的 q-sign-* 参数）。

    pr = requests.get(presigned, timeout=30)
    print('GET via presigned URL: status=%s body=%s' % (pr.status_code, pr.content))

    # 高级大文件上传/下载沿用普通 COS SDK 接口，支持并发和断点续传：
    # client.upload_file(
    #     Bucket=bucket, Key='rapid-example/large.bin',
    #     LocalFilePath='/path/to/large.bin', PartSize=16, MAXThread=8,
    #     EnableMD5=True)
    # client.download_file(
    #     Bucket=bucket, Key='rapid-example/large.bin',
    #     DestFilePath='/path/to/download.bin', PartSize=16, MAXThread=8,
    #     EnableCRC=True, DumpRecordDir='/path/to/download-records')
except CosClientError as e:
    print('Client error: %s' % e)
except CosServiceError as e:
    print('Service error: %s' % e)
