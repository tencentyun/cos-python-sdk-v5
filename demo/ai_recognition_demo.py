# -*- coding=utf-8
import base64

from qcloud_cos import CosConfig
from qcloud_cos import AIRecognitionClient

import os
import sys
import logging

from qcloud_cos.streambody import StreamBody

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
#
# 设置用户属性, 包括 secret_id, secret_key, region等。Appid 已在CosConfig中移除，请在参数 Bucket 中带上 Appid。Bucket 由 BucketName-Appid 组成
# 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_id = os.environ["SECRETID"]
# 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_key = os.environ["SECRETKEY"]
# 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
region = 'ap-chongqing'
# COS支持的所有region列表参见https://www.qcloud.com/document/product/436/6224
token = None  # 如果使用永久密钥不需要填入token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见https://cloud.tencent.com/document/product/436/14048

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key,
                   Token=token)  # 获取配置对象
client = AIRecognitionClient(config)

bucket_name = 'examplebucket-1250000000'


def ai_process_when_put_object(local_file, key, pic_operations):
    response, data = client.ci_put_object_from_local_file(
        Bucket=bucket_name,
        LocalFilePath=local_file,
        Key=key,
        # pic operation json struct
        PicOperations=pic_operations
    )
    print(response['x-cos-request-id'])
    print(data)


def ai_process_on_cloud(key, pic_operations):
    response, data = client.ci_image_process(
        Bucket=bucket_name,
        Key=key,
        # pic operation json struct
        PicOperations=pic_operations
    )
    print(response['x-cos-request-id'])
    print(data)


def cos_create_ai_object_detect_job():
    # 图像主体检测
    response, data = client.cos_create_ai_object_detect_job(
        Bucket=bucket_name,
        ObjectKey="AIObjectDetect.jpeg",
        # DetectUrl="https://test-125000000.cos.ap-chongqing.myqcloud.com/test.jpeg"
    )
    print(response)
    print(data)
    return response, data


def goods_matting():
    # 商品抠图下载时处理
    response, data = client.cos_goods_matting(
        Bucket=bucket_name,
        ObjectKey="GoodsMatting.jpg",
        DetectUrl="https://test-125000000.cos.ap-chongqing.myqcloud.com/test.jpeg",
        CenterLayout=1,
        PaddingLayout='300x300',
        Stream=True
    )
    data.get_stream_to_file('test.jpg')
    print(response)
    return response, data


def goods_matting_when_put_object():
    # 商品抠图上传时处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "test.png",' \
                 '"rule": "ci-process=GoodsMatting&center-layout=1&padding-layout=20x10" }]}'
    return ai_process_when_put_object("GoodsMatting.jpg", "result.jpg",
                                      operations)


def goods_matting_on_cloud():
    # 商品抠图云上处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "format.png",' \
                 '"rule": "ci-process=GoodsMatting&center-layout=1&padding-layout=20x10" }]}'
    return ai_process_on_cloud("GoodsMatting.jpg", operations)


def cos_ai_body_recognition():
    # 人体识别
    response, data = client.cos_ai_body_recognition(
        Bucket=bucket_name,
        ObjectKey="test.jpg",
        DetectUrl="https://test-125000000.cos.ap-chongqing.myqcloud.com/test.jpeg"
    )
    print(response)
    print(data)
    return response, data


def cos_ai_detect_face():
    # 人脸检测
    response, data = client.cos_ai_detect_face(
        Bucket=bucket_name,
        ObjectKey="test.jpg",
        MaxFaceNum=3
    )
    print(response)
    print(data)
    return response, data


def cos_ai_detect_pet():
    # 宠物识别
    response, data = client.cos_ai_detect_pet(
        Bucket=bucket_name,
        ObjectKey="test.jpg",
    )
    print(response)
    print(data)
    return response, data


def cos_ai_enhance_image():
    # 图像增强
    response, data = client.cos_ai_enhance_image(
        Bucket=bucket_name,
        ObjectKey="test.jpg",
        Denoise=3,
        Sharpen=3,
        # DetectUrl="https://test-125000000.cos.ap-chongqing.myqcloud.com/test.jpeg",
        IgnoreError=0,
        Stream=True
    )
    data.get_stream_to_file('result.jpg')
    print(response)
    return response, data


def ai_enhance_image_when_put_object():
    # 图像增强上传时处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "result2.png",' \
                 '"rule": "ci-process=AIEnhanceImage&denoise=4&sharpen=4" }]}'
    return ai_process_when_put_object("result.jpg", "result1.jpg", operations)


def ai_enhance_image_on_cloud():
    # 图像增强云上处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "result.png",' \
                 '"rule": "ci-process=AIEnhanceImage&denoise=2&sharpen=2" }]}'
    return ai_process_on_cloud("test.jpg", operations)


def cos_ai_face_effect():
    # 人脸特效
    response, data = client.cos_ai_face_effect(
        Bucket=bucket_name,
        ObjectKey="test.jpeg",
        # DetectUrl="https://test-125000000.cos.ap-chongqing.myqcloud.com/test.jpeg",
        Type="face-beautify",
        Whitening=30,
        Smoothing=10,
        FaceLifting=70,
        EyeEnlarging=70,
    )
    print(response)
    print(data)
    return response, data


def cos_ai_game_rec():
    # 游戏场景识别
    response, data = client.cos_ai_game_rec(
        Bucket=bucket_name,
        ObjectKey="test.png",
        # DetectUrl="https://test-125000000.cos.ap-chongqing.myqcloud.com/test.jpeg"
    )
    print(response)
    print(data)
    return response, data


def cos_ai_id_card_ocr():
    # 身份证识别
    response, data = client.cos_ai_id_card_ocr(
        Bucket=bucket_name,
        ObjectKey="test.jpeg",
        # CardSide="FRONT",
        Config='{"CropIdCard":true,"CropPortrait":true}'
    )
    print(response)
    print(data)
    return response, data


def cos_ai_image_coloring():
    # 图片上色
    response, data = client.cos_ai_image_coloring(
        Bucket=bucket_name,
        ObjectKey="test.jpeg",
        # DetectUrl="https://test-125000000.cos.ap-chongqing.myqcloud.com/test.jpeg"
        Stream=True
    )
    data.get_stream_to_file('result.jpg')
    print(response)
    return response, data


def ai_image_coloring_when_put_object():
    # 图像增强上传时处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "result2.png",' \
                 '"rule": "ci-process=AIImageColoring" }]}'
    return ai_process_when_put_object("test.jpeg", "result.jpg", operations)


def ai_image_coloring_on_cloud():
    # 图像增强云上处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "result.png",' \
                 '"rule": "ci-process=AIImageColoring" }]}'
    return ai_process_on_cloud("test.jpeg", operations)


def cos_ai_image_crop():
    # 图像智能裁剪
    response, data = client.cos_ai_image_crop(
        Bucket=bucket_name,
        ObjectKey="test.jpg",
        # DetectUrl="https://test-125000000.cos.ap-chongqing.myqcloud.com/test.jpeg"
        Width=100,
        Height=100,
        Fixed=1,
        IgnoreError=0
    )
    data.get_stream_to_file('result.jpg')
    print(response)
    return response, data


def ai_image_crop_when_put_object():
    # 图像增强上传时处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "result2.png",' \
                 '"rule": "ci-process=AIImageCrop&width=50&height=100&fixed=1" }]}'
    return ai_process_when_put_object("result.jpg", "result.jpg", operations)


def ai_image_crop_on_cloud():
    # 图像增强云上处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "result.png",' \
                 '"rule": "ci-process=AIImageCrop&width=50&height=100&fixed=1" }]}'
    return ai_process_on_cloud("test.jpg", operations)


def cos_ai_license_rec():
    # 卡证识别
    response, data = client.cos_ai_license_rec(
        Bucket=bucket_name,
        ObjectKey="test.jpeg",
        # DetectUrl="https://test-125000000.cos.ap-chongqing.myqcloud.com/test.jpeg"
        CardType="IDCard"
    )
    print(response)
    print(data)
    return response, data


def cos_ai_pic_matting():
    # 通用抠图
    response, data = client.cos_ai_pic_matting(
        Bucket=bucket_name,
        ObjectKey="test.jpeg",
        # DetectUrl="https://test-125000000.cos.ap-chongqing.myqcloud.com/test.jpeg"
        CenterLayout=1,
        PaddingLayout="10x10",
        Stream=True
    )
    data.get_stream_to_file('result.jpg')
    print(response)
    return response, data


def ai_pic_matting_when_put_object():
    # 通用抠图上传时处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "result2.png",' \
                 '"rule": "ci-process=AIPicMatting&center-layout=1&padding-layout=10x10" }]}'
    return ai_process_when_put_object("result.jpg", "result.jpg", operations)


def ai_pic_matting_on_cloud():
    # 通用抠图云上处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "result.png",' \
                 '"rule": "ci-process=AIPicMatting&center-layout=1&padding-layout=10x10" }]}'
    return ai_process_on_cloud("test.jpg", operations)


def cos_ai_portrait_matting():
    # 人像抠图
    response, data = client.cos_ai_portrait_matting(
        Bucket=bucket_name,
        ObjectKey="test.jpeg",
        # DetectUrl="https://test-125000000.cos.ap-chongqing.myqcloud.com/test.jpeg"
        CenterLayout=1,
        PaddingLayout="10x10",
        Stream=True
    )
    data.get_stream_to_file('result.jpg')
    print(response)
    return response, data


def ai_portrait_matting_when_put_object():
    # 人像抠图上传时处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "result2.png",' \
                 '"rule": "ci-process=AIPortraitMatting&center-layout=1&padding-layout=10x10" }]}'
    return ai_process_when_put_object("result.jpg", "result.jpg", operations)


def ai_portrait_matting_on_cloud():
    # 人像抠图云上处理
    operations = '{"is_pic_info":1,"rules":[{"fileid": "result.png",' \
                 '"rule": "ci-process=AIPortraitMatting&center-layout=1&padding-layout=10x10" }]}'
    return ai_process_on_cloud("test.jpg", operations)


def cos_auto_translation_block():
    # 实时文字翻译
    response, data = client.cos_auto_translation_block(
        Bucket=bucket_name,
        InputText="测试",
        SourceLang="zh",
        TargetLang="en",
        TextDomain="general",
        TextStyle="sentence"
    )
    print(response)
    print(data)
    return response, data


def cos_get_action_sequence():
    # 获取动作顺序
    response, data = client.cos_get_action_sequence(
        Bucket=bucket_name,
    )
    print(response)
    print(data)
    return response, data


def cos_get_live_code():
    # 获取数字验证码
    response, data = client.cos_get_live_code(
        Bucket=bucket_name,
    )
    print(response)
    print(data)
    return response, data


def cos_image_repair():
    # 图像修复下载时处理
    mask_pic = 'https://ci-qta-cq-1251704708.cos.ap-chongqing.myqcloud.com/data/pic/identification/ImageRepair/mask.jpg'
    mask_poly = '[[[100, 200], [1000, 200], [1000, 400], [100, 400]]]'
    if len(mask_pic) != 0:
        mask_pic = base64.b64encode(mask_pic.encode('utf-8')).decode('utf-8')
    if len(mask_poly) != 0:
        mask_poly = base64.b64encode(mask_poly.encode('utf-8')).decode('utf-8')
    response, data = client.cos_image_repair(
        Bucket=bucket_name,
        ObjectKey="test.jpg",
        # MaskPic=mask_pic,
        MaskPoly=mask_poly
    )
    data.get_stream_to_file('result.jpg')
    print(response)
    return response, data


def image_repair_when_put_object():
    # 图像修复上传时处理
    mask_pic = 'https://test-1250000000.cos.ap-chongqing.myqcloud.com/mask.jpg'
    mask_poly = '[[[100, 200], [1000, 200], [1000, 400], [100, 400]]]'
    rule = "ci-process=ImageRepair"
    if len(mask_pic) != 0:
        rule += "&MaskPic=" + base64.b64encode(mask_pic.encode('utf-8')).decode(
            'utf-8')
    if len(mask_poly) != 0:
        rule += "&MaskPoly=" + base64.b64encode(
            mask_poly.encode('utf-8')).decode('utf-8')
    operations = '{"is_pic_info":1,"rules":[{"fileid": "result.png",' \
                 '"rule": "' + rule + '" }]}'
    return ai_process_when_put_object("test.jpg", "result.jpg", operations)


def image_repair_on_cloud():
    # 图像修复云上处理
    mask_pic = 'https://test-1250000000.cos.ap-chongqing.myqcloud.com/mask.jpg'
    mask_poly = '[[[100, 200], [1000, 200], [1000, 400], [100, 400]]]'
    rule = "ci-process=ImageRepair"
    if len(mask_pic) != 0:
        rule += "&MaskPic=" + base64.b64encode(mask_pic.encode('utf-8')).decode(
            'utf-8')
    if len(mask_poly) != 0:
        rule += "&MaskPoly=" + base64.b64encode(
            mask_poly.encode('utf-8')).decode('utf-8')
    operations = '{"is_pic_info":1,"rules":[{"fileid": "result.png",' \
                 '"rule": "' + rule + '" }]}'
    return ai_process_on_cloud("test.jpg", operations)


def cos_liveness_recognition():
    # 活体人脸核身
    response, data = client.cos_liveness_recognition(
        Bucket=bucket_name,
        ObjectKey="test.mp4",
        IdCard="123456",
        Name="测试",
        LivenessType="SILENT",
        ValidateData="",
        BestFrameNum=5
    )
    print(response)
    print(data)
    return response, data


def ci_image_search_bucket():
    # 开通以图搜图
    body = {
        # 图库容量限制
        # 是否必传：是
        'MaxCapacity': 10,
        # 图库访问限制，默认10
        # 是否必传：否
        'MaxQps': 10,
    }
    response, data = client.ci_image_search_bucket(
        Bucket=bucket_name,
        Body=body,
        ContentType="application/xml"
    )
    print(response)
    print(data)
    return response, data


def cos_add_image_search():
    # 添加图库图片
    body = {
        # 物品 ID，最多支持64个字符。若 EntityId 已存在，则对其追加图片
        # 是否必传：是
        'EntityId': "test",
        # 用户自定义的内容，最多支持4096个字符，查询时原样带回
        # 是否必传：否
        'CustomContent': "custom test",
        # 图片自定义标签，最多不超过10个，json 字符串，格式为 key:value （例 key1>=1 key1>='aa' ）对
        # 是否必传：否
        'Tags': '{"key1":"val1","key2":"val2"}',
    }
    response, data = client.cos_add_image_search(
        Bucket=bucket_name,
        ObjectKey="result.png",
        Body=body,
        ContentType="application/xml"
    )
    print(response)
    print(data)
    return response, data


def cos_get_search_image():
    # 图片搜索接口
    response, data = client.cos_get_search_image(
        Bucket=bucket_name,
        ObjectKey="result.png",
        MatchThreshold=1,
        Offset=0,
        Limit=10,
        # Filter="key1=val1"
    )
    print(response)
    print(data)
    return response, data


def cos_delete_image_search():
    # 删除图库图片
    body = {
        # 物品 ID
        # 是否必传：是
        'EntityId': "test",
    }
    response, data = client.cos_delete_image_search(
        Bucket=bucket_name,
        ObjectKey="result.png",
        Body=body,
        ContentType="application/xml"
    )
    print(response)
    print(data)
    return response, data


def ci_get_ai_bucket():
    # 查询ai处理异步服务开通状态
    response = client.ci_get_ai_bucket(
        Regions=region,
        # BucketName='demo',
        BucketNames=bucket_name,
        PageSize="1",
        PageNumber="1"
    )
    print(response)
    return response


def ci_close_ai_bucket():
    # 关闭AI内容识别服务
    response, data = client.ci_close_ai_bucket(
        Bucket=bucket_name
    )
    print(response)
    print(data)
    return response, data


def ci_open_ai_bucket():
    # 开通AI内容识别服务
    response, data = client.ci_open_ai_bucket(
        Bucket=bucket_name
    )
    print(response)
    print(data)
    return response, data


def ci_get_ai_queue():
    # 查询ai处理队列信息
    response = client.ci_get_ai_queue(
        Bucket=bucket_name,
        QueueIds='',
        State='All',
        PageNumber='',
        PageSize=''
    )
    print(response)
    return response


def ci_put_ai_queue():
    # 更新ai队列信息
    body = {
        'Name': 'ai-queue',
        'QueueID': 'pa2c2afbe68xxxxxxxxxxxxxxxxxxxxxx',
        'State': 'Active',
        'NotifyConfig': {
            'Type': 'Url',
            'Url': 'http://www.demo.callback.com',
            'Event': 'TaskFinish',
            'State': 'On',
            'ResultFormat': 'JSON',
        }
    }
    response = client.ci_update_ai_queue(
        Bucket=bucket_name,
        QueueId='pa2c2afbe68c44xxxxxxxxxxxxxxxxxxxx',
        Request=body,
        ContentType='application/xml'
    )
    print(response)
    return response


if __name__ == '__main__':
    pass
