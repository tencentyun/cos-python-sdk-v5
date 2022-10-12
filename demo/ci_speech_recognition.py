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


def ci_get_asr_bucket():
    # 查询语音识别开通状态
    response = client.ci_get_asr_bucket(
        Regions=region,
        BucketName=bucket_name,
        PageSize="10",
        PageNumber="1"
    )
    print(response)
    return response


def ci_get_asr_queue():
    # 查询语音识别队列信息
    response = client.ci_get_asr_queue(
        Bucket=bucket_name,
    )
    print(response)
    return response


def ci_put_asr_queue():
    # 更新语音识别队列信息
    body = {
        'Name': 'asr-queue',
        'QueueID': 'p7369xxxxxxxxxxxxxxxxxdff5a',
        'State': 'Active',
        'NotifyConfig': {
            'Type': 'Url',
            'Url': 'http://www.demo.callback.com',
            'Event': 'TaskFinish',
            'State': 'On',
            'ResultFormat': 'JSON'
        }
    }
    response = client.ci_update_asr_queue(
        Bucket=bucket_name,
        QueueId='p7369xxxxxxxxxxxxxxxxxdff5a',
        Request=body,
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_asr_jobs():
    # 创建语音识别异步任务
    body = {
        'EngineModelType': '16k_zh',
        'ChannelNum': '1',
        'ResTextFormat': '1',
        # 'FlashAsr': 'true',
        # 'Format': 'mp3'
    }
    response = client.ci_create_asr_job(
        Bucket=bucket_name,
        QueueId='s0980xxxxxxxxxxxxxxxxff12',
        # TemplateId='t1ada6f282d29742db83244e085e920b08',
        InputObject='normal.mp4',
        OutputBucket=bucket_name,
        OutputRegion='ap-chongqing',
        OutputObject='result.txt',
        SpeechRecognition=body
    )
    print(response)
    return response


def ci_get_asr_jobs():
    # 获取语音识别任务信息
    response = client.ci_get_asr_job(
        Bucket=bucket_name,
        JobID='s0980xxxxxxxxxxxxxxxxff12',
    )
    print(response)
    return response


def ci_list_asr_jobs():
    # 获取语音识别任务信息列表
    response = client.ci_list_asr_jobs(
        Bucket=bucket_name,
        QueueId='p7369exxxxxxxxxxxxxxxxf5a',
        Size=10,
    )
    print(response)
    return response


def ci_create_asr_template():
    # 创建语音识别模板
    response = client.ci_create_asr_template(
        Bucket=bucket_name,
        Name='templateName',
        EngineModelType='16k_zh',
        ChannelNum=1,
        ResTextFormat=2,
        FlashAsr=True,
        Format='mp3',
    )
    print(response)
    return response


def ci_get_asr_template():
    # 获取语音识别模板
    response = client.ci_get_asr_template(
        Bucket=bucket_name,
    )
    print(response)
    return response


def ci_update_asr_template():
    # 修改语音识别模板
    response = client.ci_update_asr_template(
        Bucket=bucket_name,
        TemplateId='t1bdxxxxxxxxxxxxxxxxx94a9',
        Name='QueueId1',
        EngineModelType='16k_zh',
        ChannelNum=1,
        ResTextFormat=1,
    )
    print(response)
    return response


def ci_delete_asr_template():
    # 删除指定语音识别模板
    response = client.ci_delete_asr_template(
        Bucket=bucket_name,
        TemplateId='t1bdxxxxxxxxxxxxxxxxx94a9',
    )
    print(response)
    return response


if __name__ == '__main__':
    # ci_get_asr_bucket()
    # ci_get_asr_queue()
    # ci_put_asr_queue()
    # ci_create_asr_template()
    # ci_get_asr_template()
    # ci_update_asr_template()
    # ci_delete_asr_template()
    ci_create_asr_jobs()
    # ci_get_asr_jobs()
    # ci_list_asr_jobs()
