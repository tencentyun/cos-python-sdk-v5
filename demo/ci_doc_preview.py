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
secret_id = os.environ["SECRETID"] # 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_key = os.environ["SECRETKEY"]   # 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
region = 'ap-chongqing'  # 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
# COS支持的所有region列表参见https://www.qcloud.com/document/product/436/6224
token = None  # 如果使用永久密钥不需要填入token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见https://cloud.tencent.com/document/product/436/14048

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key,
                   Token=token)  # 获取配置对象
client = CosS3Client(config)

bucket_name = 'examplebucket-1250000000'


def ci_get_doc_bucket():
    # 查询文档预览开通状态
    response = client.ci_get_doc_bucket(
        Regions=region,
        # BucketName='demo',
        BucketNames=bucket_name,
        PageSize=1,
        PageNumber=1
    )
    print(response)
    return response


def ci_get_doc_queue():
    # 查询文档预览队列信息
    response = client.ci_get_doc_queue(
        Bucket=bucket_name,
        # QueueIds='p4bdf22xxxxxxxxxxxxxxxxxxxxxxxxxf1',
        PageNumber=1,
        PageSize=1,
    )
    print(response)
    return response


def ci_put_doc_queue():
    # 更新文档预览队列信息
    body = {
        'Name': 'doc-queue',
        'QueueID': 'p4bdf22xxxxxxxxxxxxxxxxxxxxxxxxxf1',
        'State': 'Active',
        'NotifyConfig': {
            'Type': 'Url',
            'Url': 'http://www.demo.callback.com',
            'Event': 'TaskFinish',
            'State': 'On',
            'ResultFormat': 'JSON'
        }
    }
    response = client.ci_update_doc_queue(
        Bucket=bucket_name,
        QueueId='p4bdf22xxxxxxxxxxxxxxxxxxxxxxxxxf1',
        Request=body,
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_doc_jobs():
    # 创建文档预览异步任务
    response = client.ci_create_doc_job(
        Bucket=bucket_name,
        QueueId='p4bdf22xxxxxxxxxxxxxxxxxxxxxxxxxf1',
        InputObject='normal.pptx',
        OutputBucket=bucket_name,
        OutputRegion='ap-chongqing',
        OutputObject='/test_doc/normal/abc_${Number}.jpg',
        # DocPassword='123',
        Quality=109,
        PageRanges='1,3',
    )
    print(response)
    return response


def ci_get_doc_jobs():
    # 获取文档预览异步任务信息
    response = client.ci_get_doc_job(
        Bucket=bucket_name,
        JobID='d18a9xxxxxxxxxxxxxxxxxxxxff1aa',
    )
    print(response)
    return response


def ci_list_doc_jobs():
    # 获取文档预览异步任务信息列表
    response = client.ci_list_doc_jobs(
        Bucket=bucket_name,
        QueueId='p4bdxxxxxxxxxxxxxxxxxxxx57f1',
        Size=10,
    )
    print(response)
    return response


def ci_doc_preview_process():
    # 文档预览同步接口
    response = client.ci_doc_preview_process(
        Bucket=bucket_name,
        Key='1.txt',
    )
    print(response)
    response['Body'].get_stream_to_file('result.png')


def ci_doc_preview_to_html_process():
    # 文档预览同步接口（生成html）
    response = client.ci_doc_preview_html_process(
        Bucket=bucket_name,
        Key='1.txt',
    )
    print(response)
    response['Body'].get_stream_to_file('result.html')


def ci_get_doc_preview_process_url():
    # 获取文档预览同步URL
    params = {
        'ci-process': 'doc-preview',
        'DstType': 'pdf',
    }
    response = client.get_presigned_download_url(
        Bucket=bucket_name,
        Key='1.txt',
        Params=params,
    )
    print(response)


def ci_get_doc_preview_to_html_process_url():
    # 获取文档预览同步URL（生成html）
    params = {
        'ci-process': 'doc-preview',
        'DstType': 'html',
        'Copyable': '0',
    }
    response = client.get_presigned_download_url(
        Bucket=bucket_name,
        Key='1.txt',
        Params=params,
    )
    print(response)


if __name__ == '__main__':
    # ci_get_doc_bucket()
    # ci_get_doc_queue()
    # ci_put_doc_queue()
    # ci_create_doc_jobs()
    # ci_get_doc_jobs()
    # ci_list_doc_jobs()
    # ci_doc_preview_process()
    # ci_get_doc_preview_process_url()
    # ci_doc_preview_to_html_process()
    ci_get_doc_preview_to_html_process_url()
