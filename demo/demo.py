# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos import CosServiceError
from qcloud_cos import CosClientError

import sys
import logging


def percentage(consumed_bytes, total_bytes):
    """进度条回调函数，计算当前上传的百分比

    :param consumed_bytes: 已经上传/下载的数据量
    :param total_bytes: 总数据量
    """
    if total_bytes:
        rate = int(100 * (float(consumed_bytes) / float(total_bytes)))
        print('\r{0}% '.format(rate))
        sys.stdout.flush()


if __name__ == "__main__":

    # 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

    # pip安装指南:pip install -U cos-python-sdk-v5

    # cos最新可用地域,参照https://www.qcloud.com/document/product/436/6224

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # 设置用户属性, 包括secret_id, secret_key, region
    # appid已在配置中移除,请在参数Bucket中带上appid。Bucket由bucketname-appid组成
    secret_id = 'secret_id'  # 替换为用户的secret_id
    secret_key = 'secret_key'  # 替换为用户的secret_key
    region = 'ap-beijing'  # 替换为用户的region
    token = None  # 使用临时密钥需要传入Token，默认为空,可不填

    # domain自定义域名, 通常不用设置, 如果使用全球加速域名, 则设置成对应的域名, 如mybucket-01234.cos.accelerate.myqcloud.com，
    # 开启全球加速请参考https://cloud.tencent.com/document/product/436/38864
    domain = None
    config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Domain=domain)  # 获取配置对象
    client = CosS3Client(config)

    # 文件流 简单上传
    file_name = 'test.txt'
    with open('test.txt', 'rb') as fp:
        response = client.put_object(
            Bucket='test04-123456789',  # Bucket由bucketname-appid组成
            Body=fp,
            Key=file_name,
            StorageClass='STANDARD',
            ContentType='text/html; charset=utf-8'
        )
        print(response['ETag'])

    # 字节流 简单上传
    response = client.put_object(
        Bucket='test04-123456789',
        Body=b'abcdefg',
        Key=file_name
    )
    print(response['ETag'])

    # 本地路径 简单上传
    response = client.put_object_from_local_file(
        Bucket='test04-123456789',
        LocalFilePath='local.txt',
        Key=file_name,
    )
    print(response['ETag'])

    # 设置HTTP头部 简单上传
    response = client.put_object(
        Bucket='test04-123456789',
        Body=b'test',
        Key=file_name,
        ContentType='text/html; charset=utf-8'
    )
    print(response['ETag'])

    # 设置自定义头部 简单上传
    response = client.put_object(
        Bucket='test04-123456789',
        Body=b'test',
        Key=file_name,
        Metadata={
            'x-cos-meta-key1': 'value1',
            'x-cos-meta-key2': 'value2'
        }
    )
    print(response['ETag'])

    # 高级上传接口(推荐)
    response = client.upload_file(
        Bucket='test04-123456789',
        LocalFilePath='local.txt',
        Key=file_name,
        PartSize=10,
        MAXThread=10,
        progress_callback=percentage
    )
    print(response['ETag'])

    # 文件下载 获取文件到本地
    response = client.get_object(
        Bucket='test04-123456789',
        Key=file_name,
    )
    response['Body'].get_stream_to_file('output.txt')

    # 文件下载 获取文件流
    response = client.get_object(
        Bucket='test04-123456789',
        Key=file_name,
    )
    fp = response['Body'].get_raw_stream()
    print(fp.read(2))

    # 文件下载 设置Response HTTP 头部
    response = client.get_object(
        Bucket='test04-123456789',
        Key=file_name,
        ResponseContentType='text/html; charset=utf-8'
    )
    print(response['Content-Type'])
    fp = response['Body'].get_raw_stream()
    print(fp.read(2))

    # 文件下载 指定下载范围
    response = client.get_object(
        Bucket='test04-123456789',
        Key=file_name,
        Range='bytes=0-10'
    )
    fp = response['Body'].get_raw_stream()
    print(fp.read())

    # ci interface 简单上传
    ci_file_name = 'local.jpg'
    response, data = client.ci_put_object_from_local_file(
        Bucket='test04-123456789',
        LocalFilePath='local.jpg',
        Key=ci_file_name,
        # pic operation json struct
        PicOperations='{"is_pic_info":1,"rules":[{"fileid":"format.png","rule":"imageView2/format/png"}]}'
    )
    print(response['x-cos-request-id'])
    print(data['ProcessResults']['Object']['ETag'])

    with open('local.jpg', 'rb') as fp:
        response, data = client.ci_put_object(
            Bucket='test04-123456789',
            Body=fp,
            Key=ci_file_name,
            # pic operation json struct
            PicOperations='{"is_pic_info":1,"rules":[{"fileid":"format.png","rule":"imageView2/format/png"}]}'
        )
        print(response['x-cos-request-id'])
        print(data['ProcessResults']['Object']['ETag'])

    # 查询 ci image process
    response, data = client.ci_image_process(
        Bucket='test04-123456789',
        Key=ci_file_name,
        # pic operation json struct
        PicOperations='{"is_pic_info":1,"rules":[{"fileid":"format.png","rule":"imageView2/format/png"}]}'
    )
    print(response['x-cos-request-id'])
    print(data['ProcessResults']['Object']['ETag'])

    # 二维码图片上传时识别
    qrcode_file_name = 'test_object_sdk_qrcode.file'
    with open(qrcode_file_name, 'rb') as fp:
        # fp验证
        opts = '{"is_pic_info":1,"rules":[{"fileid":"format.jpg","rule":"QRcode/cover/1"}]}'
        response = client.put_ci_object_from_local_file_and_get_qrcode(
            Bucket='test04-123456789',
            LocalFilePath=qrcode_file_name,
            Key=qrcode_file_name,
            EnableMD5=False,
            PicOperations=opts
        )
        print(response)

    # 二维码图片下载时识别
    response = client.get_ci_object_qrcode(
        Bucket='test04-123456789',
        Key=qrcode_file_name,
        Cover=0
    )
    print(response)

    # 文件下载 捕获异常
    try:
        response = client.get_object(
            Bucket='test04-123456789',
            Key='not_exist.txt',
        )
        fp = response['Body'].get_raw_stream()
        print(fp.read(2))
    except CosServiceError as e:
        print(e.get_origin_msg())
        print(e.get_digest_msg())
        print(e.get_status_code())
        print(e.get_error_code())
        print(e.get_error_msg())
        print(e.get_resource_location())
        print(e.get_trace_id())
        print(e.get_request_id())
