# -*- coding=utf-8
from qcloud_cos.streambody import StreamBody

from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client

import os
import sys
import logging
import base64

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

# https://cloud.tencent.com/document/product/436/46782

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 设置用户属性, 包括 secret_id, secret_key, region等。Appid 已在CosConfig中移除，请在参数 Bucket 中带上 Appid。Bucket 由 BucketName-Appid 组成
secret_id = os.environ["SECRETID"] # 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_key = os.environ["SECRETKEY"]   # 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
region = 'ap-beijing'  # 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
# COS支持的所有region列表参见https://www.qcloud.com/document/product/436/6224
token = None  # 如果使用永久密钥不需要填入token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见https://cloud.tencent.com/document/product/436/14048

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key,
                   Token=token)  # 获取配置对象
client = CosS3Client(config)

bucket_name = 'examplebucket-1250000000'
watermark_url = 'http://{bucket}.cos.{region}.tencentcos.cn/watermark.png'.format(bucket=bucket_name, region=region)
watermark_url_base64 = bytes.decode(base64.b64encode(str.encode(watermark_url)))


def when_put_object(local_file, key, pic_operations):
    response, data = client.ci_put_object_from_local_file(
        Bucket=bucket_name,
        LocalFilePath=local_file,
        Key=key,
        # pic operation json struct
        PicOperations=pic_operations
    )
    print(response['x-cos-request-id'])
    print(data)


def when_download_object(dest_file, key, rule):
    response = client.ci_get_object(
        Bucket=bucket_name,
        Key=key,
        DestImagePath=dest_file,
        # pic operation json struct
        Rule=rule
    )
    print(response['x-cos-request-id'])


def process_on_cloud(key, pic_operations):
    response, data = client.ci_image_process(
        Bucket=bucket_name,
        Key=key,
        # pic operation json struct
        PicOperations=pic_operations
    )
    print(response['x-cos-request-id'])
    print(data)


def add_blind_watermark_when_put_object():
    # 添加盲水印
    print(watermark_url_base64)
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "watermark/3/type/1/image/' \
                 + watermark_url_base64 + '" }]}'
    when_put_object('format.png', "format.png", operations)


def add_blind_watermark_when_download_object():
    # 添加盲水印
    print(watermark_url_base64)
    rule = 'watermark/3/type/1/image/' + watermark_url_base64
    when_download_object('local.png', 'format.png', rule)


def add_blind_watermark_process_on_cloud():
    # 添加盲水印
    print(watermark_url_base64)
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "watermark/3/type/1/image/' \
                 + watermark_url_base64 + '" }]}'
    process_on_cloud('format.png', operations)


sample_url = 'http://{bucket}.cos.{region}.tencentcos.cn/sample.png'.format(bucket=bucket_name, region=region)
sample_url_base64 = bytes.decode(base64.b64encode(str.encode(sample_url)))


def get_blind_watermark_when_put_object():
    # 提取盲水印
    print(sample_url_base64)
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "watermark/4/type/1/image/' \
                 + sample_url_base64 + '" }]}'
    when_put_object('local.png', "format.png", operations)


def get_blind_watermark_process_on_cloud():
    # 提取盲水印
    print(sample_url_base64)
    operations = '{"is_pic_info":1,"rules":[{"fileid": "sample.png",' \
                 '"rule": "watermark/4/type/1/image/' \
                 + sample_url_base64 + '" }]}'
    process_on_cloud('format.png', operations)


def thumbnail_when_put_object():
    # 图片缩放
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/thumbnail/!50p" }]}'
    when_put_object('format.png', "format.png", operations)


def thumbnail_when_download_object():
    # 图片缩放
    rule = 'imageMogr2/thumbnail/!50p'
    when_download_object('local.png', 'format.png', rule)


def thumbnail_process_on_cloud():
    # 图片缩放
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/thumbnail/!50p" }]}'
    process_on_cloud('format.png', operations)


def cut_when_put_object():
    # 图片裁剪
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/cut/600x600x100x10" }]}'
    when_put_object('format.png', "format.png", operations)


def cut_when_download_object():
    # 图片裁剪
    rule = 'imageMogr2/cut/600x600x100x10'
    when_download_object('local.png', 'format.png', rule)


def cut_process_on_cloud():
    # 图片裁剪
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/cut/600x600x100x10" }]}'
    process_on_cloud('format.png', operations)


def rotate_when_put_object():
    # 图片旋转
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/rotate/90" }]}'
    when_put_object('format.png', "format.png", operations)


def rotate_when_download_object():
    # 图片旋转
    rule = 'imageMogr2/rotate/90'
    when_download_object('local.png', 'format.png', rule)


def rotate_process_on_cloud():
    # 图片旋转
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/rotate/90" }]}'
    process_on_cloud('format.png', operations)


def format_when_put_object():
    # 图片格式转换
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/format/jpg/interlace/1" }]}'
    when_put_object('format.png', "format.png", operations)


def format_when_download_object():
    # 图片格式转换
    rule = 'imageMogr2/format/jpg/interlace/1'
    when_download_object('local.png', 'format.png', rule)


def format_process_on_cloud():
    # 图片格式转换
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/format/jpg/interlace/1" }]}'
    process_on_cloud('format.png', operations)


def quality_when_put_object():
    # 图片质量变换
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/quality/60" }]}'
    when_put_object('format.png', "format.png", operations)


def quality_when_download_object():
    # 图片质量变换
    rule = 'imageMogr2/quality/60'
    when_download_object('local.png', 'format.png', rule)


def quality_process_on_cloud():
    # 图片质量变换
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/quality/60" }]}'
    process_on_cloud('format.png', operations)


def blur_when_put_object():
    # 图片高斯模糊处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/blur/8x5" }]}'
    when_put_object('format.png', "format.png", operations)


def blur_when_download_object():
    # 图片高斯模糊处理
    rule = 'imageMogr2/blur/8x5'
    when_download_object('local.png', 'format.png', rule)


def blur_process_on_cloud():
    # 图片高斯模糊处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/blur/8x5" }]}'
    process_on_cloud('format.png', operations)


def bright_when_put_object():
    # 图片亮度调节
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/bright/30" }]}'
    when_put_object('format.png', "format.png", operations)


def bright_when_download_object():
    # 图片亮度调节
    rule = 'imageMogr2/bright/60'
    when_download_object('local.png', 'format.png', rule)


def bright_process_on_cloud():
    # 图片亮度调节
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/bright/30" }]}'
    process_on_cloud('format.png', operations)


def contrast_when_put_object():
    # 图片对比度调节
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/contrast/-50" }]}'
    when_put_object('format.png', "format.png", operations)


def contrast_when_download_object():
    # 图片对比度调节
    rule = 'imageMogr2/contrast/-50'
    when_download_object('local.png', 'format.png', rule)


def contrast_process_on_cloud():
    # 图片对比度调节
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/contrast/-50" }]}'
    process_on_cloud('format.png', operations)


def sharpen_when_put_object():
    # 图片锐化处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/sharpen/70" }]}'
    when_put_object('format.png', "format.png", operations)


def sharpen_when_download_object():
    # 图片锐化处理
    rule = 'imageMogr2/sharpen/70'
    when_download_object('local.png', 'format.png', rule)


def sharpen_process_on_cloud():
    # 图片锐化处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/sharpen/70" }]}'
    process_on_cloud('format.png', operations)


def grayscale_when_put_object():
    # 灰度图
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/grayscale/1" }]}'
    when_put_object('format.png', "format.png", operations)


def grayscale_when_download_object():
    # 灰度图
    rule = 'imageMogr2/grayscale/1'
    when_download_object('local.png', 'format.png', rule)


def grayscale_process_on_cloud():
    # 灰度图
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/grayscale/1" }]}'
    process_on_cloud('format.png', operations)


def image_watermark_when_put_object():
    # 图片水印
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "watermark/1/image/' + watermark_url_base64 \
                 + '/gravity/southeast" }]}'
    when_put_object('format.png', "format.png", operations)


def image_watermark_when_download_object():
    # 图片水印
    rule = 'watermark/1/image/' + watermark_url_base64 + '/gravity/southeast'
    when_download_object('local.png', 'format.png', rule)


def image_watermark_process_on_cloud():
    # 图片水印
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "watermark/1/image/' + watermark_url_base64 \
                 + '/gravity/southeast" }]}'
    process_on_cloud('format.png', operations)


text_watermark_base64 = bytes.decode(base64.b64encode(str.encode("testWaterMark")))
text_color_base64 = bytes.decode(base64.b64encode(str.encode("#3D3D3D")))


def text_watermark_when_put_object():
    # 文字水印
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "watermark/2/text/' + text_watermark_base64 \
                 + '/fill' + text_color_base64 \
                 + '/fontsize/20/dissolve/50/gravity/northeast/dx/20/dy/20' \
                   '/batch/1/degree/45" }]}'
    when_put_object('format.png', "format.png", operations)


def text_watermark_when_download_object():
    # 文字水印
    rule = 'watermark/2/text/' + text_watermark_base64 \
           + '/fill' + text_color_base64 \
           + '/fontsize/20/dissolve/50/gravity/northeast/dx/20/dy/20' \
             '/batch/1/degree/45'
    when_download_object('local.png', 'format.png', rule)


def text_watermark_process_on_cloud():
    # 文字水印
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "watermark/2/text/' + text_watermark_base64 \
                 + '/fill' + text_color_base64 \
                 + '/fontsize/20/dissolve/50/gravity/northeast/dx/20/dy/20' \
                   '/batch/1/degree/45" }]}'
    process_on_cloud('format.png', operations)


def pipeline_when_put_object():
    # 管道符操作
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/thumbnail/!50p|watermark/2/text/' \
                 + text_watermark_base64 + '/fill' + text_color_base64 \
                 + '/fontsize/30/dx/20/dy/20" }]}'
    when_put_object('format.png', "format.png", operations)


def pipeline_when_download_object():
    # 管道符操作
    rule = 'imageMogr2/thumbnail/!50p|watermark/2/text/' \
           + text_watermark_base64 + '/fill' + text_color_base64 \
           + '/fontsize/30/dx/20/dy/20'
    when_download_object('local.png', 'format.png', rule)


def pipeline_process_on_cloud():
    # 管道符操作
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/thumbnail/!50p|watermark/2/text/' \
                 + text_watermark_base64 + '/fill' + text_color_base64 \
                 + '/fontsize/30/dx/20/dy/20" }]}'
    process_on_cloud('format.png', operations)


def ci_get_image_info():
    # 查询图片基本信息
    response, data = client.ci_get_image_info(
        Bucket=bucket_name,
        Key='format.png',
    )
    print(response['x-cos-request-id'])
    print(data)


def ci_get_exif_info():
    # 获取 EXIF 信息
    response, data = client.ci_get_image_exif_info(
        Bucket=bucket_name,
        Key='format.png',
    )
    print(response['x-cos-request-id'])
    print(data)


def ci_get_image_ave_info():
    # 获取图片主色调信息
    response, data = client.ci_get_image_ave_info(
        Bucket=bucket_name,
        Key='format.png',
    )
    print(response['x-cos-request-id'])
    print(data)


def strip_when_put_object():
    # 去除图片元信息
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/strip" }]}'
    when_put_object('sample.jpeg', "format.png", operations)


def strip_when_download_object():
    # 去除图片元信息
    rule = 'imageMogr2/strip'
    when_download_object('local.png', 'format.png', rule)


def strip_process_on_cloud():
    # 去除图片元信息
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageMogr2/strip" }]}'
    process_on_cloud('format.png', operations)


def image_view2_when_put_object():
    # 快速缩略模板
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageView2/1/w/400/h/600/q/85" }]}'
    when_put_object('format.png', "format.png", operations)


def image_view2_when_download_object():
    # 快速缩略模板
    rule = 'imageView2/1/w/100/h/100/q/85'
    when_download_object('local.png', 'format.png', rule)


def image_view2_process_on_cloud():
    # 快速缩略模板
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "imageView2/1/w/300/h/500/q/85" }]}'
    process_on_cloud('format.png', operations)


def size_limit_when_download_object():
    # 限制图片大小
    rule = 'imageMogr2/strip/format/png/size-limit/10k!'
    when_download_object('local.png', 'format.png', rule)


def qr_code_identify_when_put_object():
    # 二维码识别
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "QRcode/cover/1" }]}'
    when_put_object('testqrcode.png', "format.png", operations)


def qr_code_identify_when_download_object():
    # 二维码识别
    response, data = client.ci_get_object_qrcode(
        Bucket=bucket_name,
        Key='format.png',
        Cover=0
    )
    print(response, data)


def ci_image_assess_quality():
    # 图片质量评估
    response = client.ci_image_assess_quality(
        Bucket=bucket_name,
        Key='format.png',
    )
    print(response)


def ci_image_detect_car():
    # 车辆车牌检测
    response = client.ci_image_detect_car(
        Bucket=bucket_name,
        Key='car.jpeg',
    )
    print(response)


def ci_qrcode_generate():
    # 二维码生成
    response = client.ci_qrcode_generate(
        Bucket=bucket_name,
        QrcodeContent='https://www.example.com',
        Width=200
    )
    qrCodeImage = base64.b64decode(response['ResultImage'])
    with open('/result.png', 'wb') as f:
        f.write(qrCodeImage)
    print(response)


def ci_ocr_process():
    # 通用文字识别
    response = client.ci_ocr_process(
        Bucket=bucket_name,
        Key='ocr.jpeg',
    )
    print(response)


def ci_add_image_style():
    # 增加图片样式
    body = {
        'StyleName': 'style_name',
        'StyleBody': 'imageMogr2/thumbnail/!50px',
    }
    response = client.ci_put_image_style(
        Bucket=bucket_name,
        Request=body,
    )
    print(response)


def ci_get_image_style():
    # 获取图片样式
    body = {
        'StyleName': 'style_name',
    }
    response, data = client.ci_get_image_style(
        Bucket=bucket_name,
        Request=body,
    )
    print(response['x-cos-request-id'])
    print(data)


def ci_delete_image_style():
    # 删除图片样式
    body = {
        'StyleName': 'style_name',
    }
    response = client.ci_delete_image_style(
        Bucket=bucket_name,
        Request=body,
    )
    print(response['x-cos-request-id'])


def ci_image_detect_label():
    # 图片标签
    response = client.ci_image_detect_label(
        Bucket=bucket_name,
        Key='format.png',
    )
    print(response)


if __name__ == '__main__':
    # format.png
    # thumbnail_when_put_object()
    # thumbnail_process_on_cloud()
    # thumbnail_when_download_object()
    # cut_when_put_object()
    # cut_process_on_cloud()
    # cut_when_download_object()
    # rotate_when_put_object()
    # rotate_process_on_cloud()
    # rotate_when_download_object()
    # format_when_put_object()
    # format_process_on_cloud()
    # format_when_download_object()
    # quality_when_put_object()
    # quality_process_on_cloud()
    # quality_when_download_object()
    # blur_when_put_object()
    # blur_process_on_cloud()
    # blur_when_download_object()
    # bright_when_put_object()
    # bright_process_on_cloud()
    # bright_when_download_object()
    # contrast_when_put_object()
    # contrast_process_on_cloud()
    # contrast_when_download_object()
    # sharpen_when_put_object()
    # sharpen_process_on_cloud()
    # sharpen_when_download_object()
    # grayscale_when_put_object()
    # grayscale_process_on_cloud()
    # grayscale_when_download_object()
    # text_watermark_when_put_object()
    # text_watermark_process_on_cloud()
    # text_watermark_when_download_object()
    # pipeline_when_put_object()
    # pipeline_process_on_cloud()
    # pipeline_when_download_object()
    # ci_get_exif_info()
    # ci_get_image_ave_info()
    # strip_when_put_object()
    # strip_process_on_cloud()
    # strip_when_download_object()
    # image_view2_when_put_object()
    # image_view2_process_on_cloud()
    # image_view2_when_download_object()
    # size_limit_when_download_object()
    # ci_image_assess_quality()
    # ci_qrcode_generate()
    # qr_code_identify_when_put_object()
    qr_code_identify_when_download_object()
    # ci_image_detect_car()
    # ci_ocr_process()
    # ci_get_image_info()
    # ci_get_exif_info()
    # ci_add_image_style()
    # image_watermark_when_put_object()
    # image_watermark_process_on_cloud()
    # image_watermark_when_download_object()
    # add_blind_watermark_when_put_object()
    # add_blind_watermark_process_on_cloud()
    # add_blind_watermark_when_download_object()
    # get_blind_watermark_process_on_cloud()
    # get_blind_watermark_when_put_object()
    # ci_get_image_style()
    # ci_delete_image_style()
    # ci_image_detect_label()

