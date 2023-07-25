# -*- coding=utf-8
import base64

from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client

import os
import sys
import logging

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

# https://cloud.tencent.com/document/product/436/46782

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

secret_id = os.environ["SECRETID"] # 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_key = os.environ["SECRETKEY"] # 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
region = 'ap-chongqing' # 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
# COS支持的所有region列表参见https://www.qcloud.com/document/product/436/6224
token = None # 如果使用永久密钥不需要填入token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见https://cloud.tencent.com/document/product/436/14048

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme='https') # 获取配置对象
client = CosS3Client(config)


bucket_name = 'demo-1253960454'


def ci_get_file_hash():
    # 同步获取文件哈希值
    response = client.file_hash(
        Bucket=bucket_name,  # 文件所在的桶名称
        Key="mytest.mp4",  # 需要获取哈希值的文件名
        Type='md5',  # 哈希算法类型，有效值：md5、sha1、sha256.
        AddToHeader=True  # 是否将计算得到的哈希值，自动添加至文件的自定义header. 格式为：x-cos-meta-md5/sha1/sha256; 有效值： True、False，不填则默认为False.
    )
    print(response)
    return response


def ci_create_file_hash_job():
    # 创建获取文件哈希值异步任务
    body = {
        # 获取文件哈希值配置详情

        # 哈希值的算法类型
        # 必选，有效值：MD5、SHA1、SHA256。
        'Type': 'MD5',
        # 是否将计算得到的哈希值添加至文件自定义header，自定义header根据Type的值变化，例如Type值为MD5时，自定义header为 x-cos-meta-md5。
        # 非必选，有效值：true、false，默认值为 false。
        'AddToHeader': 'true'
    }
    mq_config = {
        # 消息队列所属园区
        # 必选。目前支持园区 sh（上海）、bj（北京）、gz（广州）、cd（成都）、hk（中国香港）
        'MqRegion': 'bj',
        # 消息队列使用模式
        # 必选。主题订阅：Topic 队列服务: Queue
        'MqMode': 'Queue',
        # TDMQ 主题名称 必选。
        'MqName': 'queueName'
    }
    response = client.ci_create_file_hash_job(
        Bucket=bucket_name,  # 文件所在的桶名称
        InputObject="mytest.mp4",  # 需要获取哈希值的文件名
        FileHashCodeConfig=body,  # 获取文件哈希值配置详情
        CallBack="http://www.callback.com",  # 回调url地址,当 CallBackType 参数值为 Url 时有效
        CallBackFormat="JSON",  # 回调信息格式 JSON 或 XML，默认 XML
        CallBackType="Url",  # 回调类型，Url 或 TDMQ，默认 Url
        CallBackMqConfig=mq_config,  # 任务回调TDMQ配置，当 CallBackType 为 TDMQ 时必填
        UserData="this is my user data"  # 透传用户信息, 可打印的 ASCII 码, 长度不超过1024
    )
    print(response)
    return response


def ci_create_file_uncompress_job():
    # 创建获取文件解压异步任务
    body = {
        # 文件解压配置详情

        # 指定解压后输出文件的前缀，不填则默认保存在存储桶根路径，非必选
        'Prefix': 'zip/',
        # 解压密钥，传入时需先经过 base64 编码。非必选
        'UnCompressKey': base64.b64encode("123456".encode("utf-8")).decode('utf-8'),
        # 指定解压后的文件路径是否需要替换前缀，有效值：
        # - 0：不添加额外的前缀，解压缩将保存在Prefix指定的路径下（不会保留压缩包的名称，仅将压缩包内的文件保存至指定的路径）。
        # - 1：以压缩包本身的名称作为前缀，解压缩将保存在Prefix指定的路径下。
        # - 2：以压缩包完整路径作为前缀，此时如果不指定Prefix，就是解压到压缩包所在的当前路径（包含压缩包本身名称）。
        # - 非必选，默认值为0
        'PrefixReplaced': '0'
    }
    mq_config = {
        # 消息队列所属园区
        # 必选。目前支持园区 sh（上海）、bj（北京）、gz（广州）、cd（成都）、hk（中国香港）
        'MqRegion': 'bj',
        # 消息队列使用模式
        # 必选。主题订阅：Topic 队列服务: Queue
        'MqMode': 'Queue',
        # TDMQ 主题名称 必选。
        'MqName': 'queueName'
    }
    response = client.ci_create_file_uncompress_job(
        Bucket=bucket_name,  # 文件所在的桶名称
        InputObject='zip/testmi.zip',  # 需要解压的文件名
        OutputBucket=bucket_name,  # 指定输出文件所在的桶名称
        OutputRegion=region,  # 指定输出文件所在的地域
        FileUncompressConfig=body,  # 文件解压配置详情
        CallBack="http://www.callback.com",  # 回调url地址,当 CallBackType 参数值为 Url 时有效
        CallBackFormat="JSON",  # 回调信息格式 JSON 或 XML，默认 XML
        CallBackType="Url",  # 回调类型，Url 或 TDMQ，默认 Url
        CallBackMqConfig=mq_config,  # 任务回调TDMQ配置，当 CallBackType 为 TDMQ 时必填
        UserData="this is my user data"  # 透传用户信息, 可打印的 ASCII 码, 长度不超过1024
    )
    print(response)
    return response


def ci_create_file_compress_job():
    # 创建获取文件压缩异步任务
    body = {
        # 文件打包时，是否需要去除源文件已有的目录结构
        # 必选，有效值：
        # 0：不需要去除目录结构，打包后压缩包中的文件会保留原有的目录结构
        # 1：需要，打包后压缩包内的文件会去除原有的目录结构，所有文件都在同一层级
        # 例如：源文件 URL 为 https://domain/source/test.mp4, 则源文件路径为 source/test.mp4
        # 如果为 1，则 ZIP 包中该文件路径为 test.mp4
        # 如果为 0，ZIP 包中该文件路径为 source/test.mp4
        'Flatten': '0',
        # 打包压缩的类型
        # 必选，有效值：zip、tar、tar.gz。
        'Format': 'zip',
        # 压缩类型，仅在Format为tar.gz或zip时有效。
        # faster：压缩速度较快
        # better：压缩质量较高，体积较小
        # default：适中的压缩方式
        # 非必选，默认值为default
        'Type': 'faster',
        # 压缩包密钥，传入时需先经过 base64 编码, 编码后长度不能超过128。当 Format 为 zip 时生效
        # 非必选
        'CompressKey': base64.b64encode("123456".encode("utf-8")).decode('utf-8'),

        # 下列参数UrlList、Prefix、Key 三者仅能选择一个，不能都为空，也不会同时生效。如果填了多个，会按优先级 UrlList > Prefix > Key 取最高优先级执行。

        # UrlList 支持将需要打包的文件整理成索引文件，后台将根据索引文件内提供的文件 url，打包为一个压缩包文件。
        # 索引文件需要保存在当前存储桶中，本字段需要提供索引文件的对象地址，例如：/test/index.csv。
        # 索引文件格式：仅支持 CSV 文件，一行一条 URL（仅支持本存储桶文件），如有多列字段，默认取第一列作为URL。最多不超过10000个文件，总大小不超过50G
        # 非必选
        'UrlList': '',
        # 支持对存储桶中的某个前缀进行打包，如果需要对某个目录进行打包，需要加/，
        # 例如test目录打包，则值为：test/。最多不超过10000个文件，总大小不超过50G，否则会导致任务失败。
        # 非必选
        'Prefix': 'zip/',
        # 支持对存储桶中的多个文件进行打包，个数不能超过 1000。
        # 非必选
        'Key': ['zip/1.png', 'zip/2.png', 'zip/3.png']
    }
    mq_config = {
        # 消息队列所属园区
        # 必选。目前支持园区 sh（上海）、bj（北京）、gz（广州）、cd（成都）、hk（中国香港）
        'MqRegion': 'bj',
        # 消息队列使用模式
        # 必选。主题订阅：Topic 队列服务: Queue
        'MqMode': 'Queue',
        # TDMQ 主题名称 必选。
        'MqName': 'queueName'
    }
    response = client.ci_create_file_compress_job(
        Bucket=bucket_name,  # 文件所在的桶名称
        OutputBucket=bucket_name,  # 指定输出文件所在的桶名称
        OutputRegion=region,  # 指定输出文件所在的地域
        OutputObject='zip/result.zip',  # 指定输出文件名
        FileCompressConfig=body,  # 指定压缩配置
        CallBack="http://www.callback.com",  # 回调url地址,当 CallBackType 参数值为 Url 时有效
        CallBackFormat="JSON",  # 回调信息格式 JSON 或 XML，默认 XML
        CallBackType="Url",  # 回调类型，Url 或 TDMQ，默认 Url
        CallBackMqConfig=mq_config,  # 任务回调TDMQ配置，当 CallBackType 为 TDMQ 时必填
        UserData="this is my user data"  # 透传用户信息, 可打印的 ASCII 码, 长度不超过1024
    )
    print(response)
    return response


def ci_get_file_process_jobs():
    # 获取文件处理异步任务结果详情
    response = client.ci_get_file_process_jobs(
        Bucket=bucket_name,  # 任务所在桶名称
        JobIDs='f7325938a256611xxxxxxxxxxx',  # 文件处理异步任务ID
    )
    print(response)
    return response


def ci_get_zip_preview():
    # 压缩包预览同步请求
    response = client.ci_file_zip_preview(
        Bucket=bucket_name,   # 压缩文件所在桶名称
        Key="zip/test.zip"  # 需要预览的压缩文件名
    )
    print(response)
    return response


if __name__ == '__main__':
    # ci_get_file_hash()
    # ci_create_file_hash_job()
    # ci_create_file_uncompress_job()
    # ci_create_file_compress_job()
    ci_get_zip_preview()
    # ci_get_file_process_jobs()
