# -*- coding=utf-8
import base64
import time

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

region = 'ap-chongqing' # 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
# COS支持的所有region列表参见https://www.qcloud.com/document/product/436/6224
token = None
config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme='https') # 获取配置对象
client = CosS3Client(config)


bucket_name = 'test-1250000000'


def ci_auditing_video_submit():
    response = client.ci_auditing_video_submit(Bucket=bucket_name,
                                               Key="test.mp4",
                                               Callback="http://www.demo.com",
                                               CallbackVersion='Simple',
                                               DetectContent=1,
                                               Mode='Interval',
                                               Count=1,
                                               TimeInterval=1)
    print(str(response))


def ci_auditing_video_query():
    response = client.ci_auditing_video_query(Bucket=bucket_name, JobID="jobId")
    print(response['JobsDetail']['State'])


def ci_auditing_image_batch():
    user_info = {
        'TokenId': '123456',  # 一般用于表示账号信息，长度不超过128字节
        'Nickname': '测试',  # 一般用于表示昵称信息，长度不超过128字节
        'DeviceId': '腾讯云',  # 一般用于表示设备信息，长度不超过128字节
        'AppId': '12500000',  # 一般用于表示 App 的唯一标识，长度不超过128字节
        'Room': '1',  # 一般用于表示房间号信息，长度不超过128字节
        'IP': '127.0.0.1',  # 一般用于表示 IP 地址信息，长度不超过128字节
        'Type': '测试',  # 一般用于表示业务类型，长度不超过128字节
        'ReceiveTokenId': '789123',  # 一般用于表示接收消息的用户账号，长度不超过128字节
        'Gender': '男',  # 一般用于表示性别信息，长度不超过128字节
        'Level': '100',  # 一般用于表示等级信息，长度不超过128字节
        'Role': '测试人员',  # 一般用于表示角色信息，长度不超过128字节
    }
    input_info = []
    input_info.append({
        'Object': 'test.png',  # 存储在 COS 存储桶中的图片文件名称
        # 'Url': 'http://a-1250000.cos.ap-shanghai.myqcloud.com/image.jpg',  # 图片文件的链接地址
        # 'Content': base64.b64encode('我是测试'.encode("utf-8")).decode('utf-8'),  # 图片文件的内容，需要先经过 base64 编码
        # 'Interval': '5',  # 截帧频率，GIF 图检测专用，默认值为5，表示从第一帧（包含）开始每隔5帧截取一帧。
        # 'MaxFrames': '5',  # 最大截帧数量，GIF 图检测专用，默认值为5，表示只截取 GIF 的5帧图片进行审核，必须大于0。
        'DataId': 'my data id',  # 图片标识，该字段在结果中返回原始内容，长度限制为512字节。
        # 'LargeImageDetect': '0',  # 对于超过大小限制的图片是否进行压缩后再审核，取值为： 0（不压缩），1（压缩）。默认为0。注：压缩最大支持32M的图片，且会收取压缩费用。
        'UserInfo': user_info,  # 用户业务字段。
    })
    input_info.append({
        'Object': 'test.png',  # 存储在 COS 存储桶中的图片文件名称
        # 'Url': 'http://a-1250000.cos.ap-shanghai.myqcloud.com/image.jpg',  # 图片文件的链接地址
        # 'Content': base64.b64encode('我是测试1'.encode("utf-8")).decode('utf-8'),  # 图片文件的内容，需要先经过 base64 编码
        # 'Interval': '5',  # 截帧频率，GIF 图检测专用，默认值为5，表示从第一帧（包含）开始每隔5帧截取一帧。
        # 'MaxFrames': '5',  # 最大截帧数量，GIF 图检测专用，默认值为5，表示只截取 GIF 的5帧图片进行审核，必须大于0。
        'DataId': 'my data id',  # 图片标识，该字段在结果中返回原始内容，长度限制为512字节。
        # 'LargeImageDetect': '0',  # 对于超过大小限制的图片是否进行压缩后再审核，取值为： 0（不压缩），1（压缩）。默认为0。注：压缩最大支持32M的图片，且会收取压缩费用。
        'UserInfo': user_info,  # 用户业务字段。
    })

    freeze = {
        'PornScore': '50',  # 取值为[0,100]，表示当色情审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
        'AdsScore': '50'  # 取值为[0,100]，表示当广告审核结果大于或等于该分数时，自动进行冻结操作。不填写则表示不自动冻结，默认值为空。
    }
    response = client.ci_auditing_image_batch(Bucket=bucket_name,
                                              Input=input_info,
                                              BizType='',  # 表示审核策略的唯一标识
                                              Async=0,  # 是否异步进行审核
                                              Callback="http://www.demo.com",
                                              Freeze=freeze
                                              )
    print(str(response))


def ci_live_video_auditing():
    # 提交视频流审核任务
    response = client.ci_auditing_live_video_submit(
        Bucket=bucket_name,
        Url='rtmp://example.com/live/123',
        Callback='http://callback.com/',
        DataId='testdataid-111111',
        UserInfo={
            'TokenId': 'token',
            'Nickname': 'test',
            'DeviceId': 'DeviceId-test',
            'AppId': 'AppId-test',
            'Room': 'Room-test',
            'IP': 'IP-test',
            'Type': 'Type-test',
        },
        BizType='d0292362d07428b4f6982a31bf97c246',
        CallbackType=1
    )
    assert (response['JobsDetail']['JobId'])
    jobId = response['JobsDetail']['JobId']
    time.sleep(5)
    kwargs = {"CacheControl": "no-cache", "ResponseCacheControl": "no-cache"}
    response = client.ci_auditing_live_video_cancle(
        Bucket=bucket_name,
        JobID=jobId,
        **kwargs
    )
    print(response)


def ci_auditing_virus_submit_and_query():
    kwargs = {"CacheControl": "no-cache", "ResponseCacheControl": "no-cache"}
    response = client.ci_auditing_virus_submit(Bucket=bucket_name,
                                               Key="test.png",
                                               Callback="http://www.demo.com",
                                               **kwargs)
    jobId = response['JobsDetail']['JobId']
    while True:
        time.sleep(5)
        kwargs = {"CacheControl": "no-cache", "ResponseCacheControl": "no-cache"}
        response = client.ci_auditing_virus_query(Bucket=bucket_name, JobID=jobId, **kwargs)
        print(response['JobsDetail']['State'])
        if response['JobsDetail']['State'] == 'Success':
            print(str(response))
            break
    print(response)


def ci_auditing_text_submit():
    user_info = {
        'TokenId': '123456',  # 一般用于表示账号信息，长度不超过128字节
        'Nickname': '测试',  # 一般用于表示昵称信息，长度不超过128字节
        'DeviceId': '腾讯云',  # 一般用于表示设备信息，长度不超过128字节
        'AppId': '12500000',  # 一般用于表示 App 的唯一标识，长度不超过128字节
        'Room': '1',  # 一般用于表示房间号信息，长度不超过128字节
        'IP': '127.0.0.1',  # 一般用于表示 IP 地址信息，长度不超过128字节
        'Type': '测试',  # 一般用于表示业务类型，长度不超过128字节
        'ReceiveTokenId': '789123',  # 一般用于表示接收消息的用户账号，长度不超过128字节
        'Gender': '男',  # 一般用于表示性别信息，长度不超过128字节
        'Level': '100',  # 一般用于表示等级信息，长度不超过128字节
        'Role': '测试人员',  # 一般用于表示角色信息，长度不超过128字节
    }
    response = client.ci_auditing_text_submit(
        Bucket=bucket_name,  # 桶名称
        Content='123456test'.encode("utf-8"),  # 需要审核的文本内容
        BizType='',  # 表示审核策略的唯一标识
        UserInfo=user_info,  # 用户业务字段
        DataId='456456456',  # 待审核的数据进行唯一业务标识
    )
    print(response)


def ci_auditing_text_txt_submit():
    user_info = {
        'TokenId': '123456',  # 一般用于表示账号信息，长度不超过128字节
        'Nickname': '测试',  # 一般用于表示昵称信息，长度不超过128字节
        'DeviceId': '腾讯云',  # 一般用于表示设备信息，长度不超过128字节
        'AppId': '12500000',  # 一般用于表示 App 的唯一标识，长度不超过128字节
        'Room': '1',  # 一般用于表示房间号信息，长度不超过128字节
        'IP': '127.0.0.1',  # 一般用于表示 IP 地址信息，长度不超过128字节
        'Type': '测试',  # 一般用于表示业务类型，长度不超过128字节
        'ReceiveTokenId': '789123',  # 一般用于表示接收消息的用户账号，长度不超过128字节
        'Gender': '男',  # 一般用于表示性别信息，长度不超过128字节
        'Level': '100',  # 一般用于表示等级信息，长度不超过128字节
        'Role': '测试人员',  # 一般用于表示角色信息，长度不超过128字节
    }
    response = client.ci_auditing_text_submit(
        Bucket=bucket_name,  # 桶名称
        # Content='123456test'.encode("utf-8"),  # 需要审核的文本内容
        Key='shenhe.txt',
        Url='https://test-1250000000.cos.ap-chongqing.myqcloud.com/shenhe.txt?q-sign-algorithm=sha1&q-ak=AKIDPdbIjuoRt40g5D4ex0nKaaJlvoRKzNVN&q-sign-time=1690968685;1690975885&q-key-time=1690968685;1690975885&q-header-list=&q-url-param-list=&q-signature=c93b2350e946ad1d5336286221edc66e53f18989',
        BizType='',  # 表示审核策略的唯一标识
        UserInfo=user_info,  # 用户业务字段
        DataId='456456456',  # 待审核的数据进行唯一业务标识
    )
    print(response)


def ci_auditing_text_txt_query():

    response = client.ci_auditing_text_query(
        Bucket=bucket_name,  # 桶名称
        JobID='st6a7d90fe311xxxxxxxxxxxxxxxxx',  # 需要查询的文本文件审核任务ID
    )
    print(response)


if __name__ == '__main__':
    # ci_auditing_video_submit()
    # ci_auditing_video_query()
    ci_auditing_image_batch()
    # ci_live_video_auditing()
    # ci_auditing_virus_submit_and_query()
    # ci_auditing_text_submit()
    # ci_auditing_text_txt_submit()
    # ci_auditing_text_txt_query()