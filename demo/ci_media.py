# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos.cos_comm import CiDetectType

import sys
import logging
import os
import time

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

# https://cloud.tencent.com/document/product/436/48987

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 设置用户属性, 包括secret_id, secret_key, region
# appid已在配置中移除,请在参数Bucket中带上appid。Bucket由bucketname-appid组成
# 这里秘钥是从环境变量取得，如自己测试可改成自己对应的秘钥
SECRET_ID = os.environ["SECRETID"]
SECRET_KEY = os.environ["SECRETKEY"]

region = 'ap-chongqing'  # 替换为用户的region
token = None  # 使用临时密钥需要传入Token，默认为空,可不填
config = CosConfig(Region=region, SecretId=SECRET_ID, SecretKey=SECRET_KEY, Token=token, Scheme='https')  # 获取配置对象
client = CosS3Client(config)


bucket_name = 'demo-1253960454'


def ci_get_media_queue():
    # 查询媒体队列信息
    response = client.ci_get_media_queue(
                    Bucket=bucket_name
                )
    print(response)
    return response

def ci_create_media_transcode_watermark_jobs():
    # 创建转码任务
    body = {
        'Input':{
            'Object':'117374C.mp4'
        },
        'QueueId': 'pe943803693bd42d1a3105804ddaee525',
        'Tag': 'Transcode',
        'Operation': {
        'Output':{'Bucket':bucket_name, 'Region':region, 'Object':'117374C_output.mp4'},
        'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5',
        # "WatermarkTemplateId": ["", ""],
        'Watermark': [
            {
                'Type':'Text',
                'Pos':'TopRight',
                'LocMode':'Absolute',
                'Dx':'64',
                'Dy': '64',
                'StartTime':'0',
                'EndTime':'1000.5',
                'Text': {
                    'Text': '水印内容',
                    'FontSize': '90',
                    'FontType': 'simfang.ttf',
                    'FontColor': '0xFFEEFF',
                    'Transparency': '100',
                },
            },
            {
                'Type':'Image',
                'Pos':'TopLeft',
                'LocMode':'Absolute',
                'Dx':'100',
                'Dy': '100',
                'StartTime':'0',
                'EndTime':'1000.5',
                'Image': {
                    'Url': 'http://'+bucket_name+".cos."+region+".myqcloud.com/1215shuiyin.jpg",
                    'Mode': 'Fixed',
                    'Width': '128',
                    'Height': '128',
                    'Transparency': '100',
                },
            }
        ]
        }
    }
    # dict中数组类型的标签，都需要特殊处理
    lst = [
        '<Watermark>',
        '<WatermarkTemplateId>',
        '</WatermarkTemplateId>',
        '</Watermark>'
    ]
    response = client.ci_create_media_jobs(
                    Bucket=bucket_name,
                    Jobs=body,
                    Lst=lst,
                    ContentType='application/xml'
                )
    print(response)
    return response    

def ci_create_media_transcode_jobs():
    # 创建转码任务
    body = {
        'Input':{
            'Object':'117374C.mp4'
        },
        'QueueId': 'pe943803693bd42d1a3105804ddaee525',
        'Tag': 'Transcode',
        'Operation': {
        'Output':{'Bucket':bucket_name, 'Region':region, 'Object':'117374C_output.mp4'},
        'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5'
        }
    }
    response = client.ci_create_media_jobs(
                    Bucket=bucket_name,
                    Jobs=body,
                    Lst={},
                    ContentType='application/xml'
                )
    print(response)
    return response   

def ci_list_media_transcode_jobs():
    # 转码任务
    response = client.ci_list_media_jobs(
                    Bucket=bucket_name,
                    QueueId='pe943803693bd42d1a3105804ddaee525',
                    Tag='Transcode',
                    ContentType='application/xml'
                )
    print(response)
    return response 

def ci_get_media_transcode_jobs():
    # 转码任务
    response = client.ci_get_media_jobs(
                    Bucket=bucket_name,
                    JobIDs='j3feb7ccc28fc11eca50b6f68c211dc6c,jb83bcc5a28fb11ecae48a1f29371c5f8',
                    ContentType='application/xml'
                )
    print(response)
    return response 

if __name__ == "__main__":
    ci_get_media_transcode_jobs()