# -*- coding=utf-8

from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client

import os
import sys
import logging

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

# https://cloud.tencent.com/document/product/436/46782

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 设置用户属性, 包括 secret_id, secret_key, region等。Appid 已在CosConfig中移除，请在参数 Bucket 中带上 Appid。Bucket 由 BucketName-Appid 组成
# secret_id = os.environ["SECRETID"] # 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
# secret_key = os.environ["SECRETKEY"]   # 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi

secret_id = os.environ["SECRETID"] # 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_key = os.environ["SECRETKEY"] # 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
region = 'ap-chongqing' # 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
# COS支持的所有region列表参见https://www.qcloud.com/document/product/436/6224
token = None # 如果使用永久密钥不需要填入token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见https://cloud.tencent.com/document/product/436/14048

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme='https') # 获取配置对象
client = CosS3Client(config)


bucket_name = 'demo-1253960454'


def ci_get_file_hash():
    response = client.file_hash(Bucket=bucket_name, Key="mytest.mp4", Type='md5')
    print(response)
    return response


def ci_create_file_hash_job():
    body = {
        'Type': 'MD5',
    }
    response = client.ci_create_file_hash_job(
        Bucket=bucket_name,
        InputObject="mytest.mp4",
        FileHashCodeConfig=body
    )
    print(response)
    return response


def ci_create_file_uncompress_job():
    body = {
        'Prefix': 'output/',
    }
    response = client.ci_create_file_uncompress_job(
        Bucket=bucket_name,
        InputObject='test.zip',
        FileUncompressConfig=body
    )
    print(response)
    return response


def ci_create_file_compress_job():
    body = {
        'Flatten': '0',
        'Format': 'zip',
        'Prefix': '/',
    }
    response = client.ci_create_file_compress_job(
        Bucket=bucket_name,
        OutputBucket=bucket_name,
        OutputRegion='ap-guangzhou',
        OutputObject='result.zip',
        FileCompressConfig=body,
        CallBack="http://www.callback.com",
        CallBackType="Url",
        CallBackFormat="XML",
        UserData="my data"
    )
    print(response)
    return response


def ci_get_file_process_jobs():
    response = client.ci_get_file_process_jobs(
        Bucket=bucket_name,
        JobIDs='fcb9a9f90e57611ed9************',
    )
    print(response)
    return response


def ci_get_zip_preview():
    response = client.ci_file_zip_preview(Bucket=bucket_name, Key="result.zip")
    print(response)
    return response


if __name__ == '__main__':
    # ci_get_file_hash()
    # ci_create_file_hash_job()
    # ci_create_file_uncompress_job()
    # ci_create_file_compress_job()
    # ci_get_zip_preview()
    ci_get_file_process_jobs()
