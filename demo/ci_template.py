# -*- coding=utf-8
import time

import xmltodict

from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client

import sys
import logging
import os

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

# 媒体处理模板相关API 请参考 https://cloud.tencent.com/document/product/460/84733
# 媒体处理对不同类型的任务有不同的模板，此处指向转码模板

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 设置用户属性, 包括secret_id, secret_key, region
# appid已在配置中移除,请在参数Bucket中带上appid。Bucket由bucketname-appid组成
# 这里秘钥是从环境变量取得，如自己测试可改成自己对应的秘钥
secret_id = os.environ["SECRETID"] # 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_key = os.environ["SECRETKEY"] # 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
region = 'ap-chongqing' # 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
# COS支持的所有region列表参见https://www.qcloud.com/document/product/436/6224
token = None # 如果使用永久密钥不需要填入token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见https://cloud.tencent.com/document/product/436/14048

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme='https') # 获取配置对象
client = CosS3Client(config)


bucket_name = 'demo-1250000000'

snapshot_template_config = {
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64
    # 必选
    'Name': 'snapshot_template',
    # 模板类型：截图模板固定值为 Snapshot
    # 必选
    'Tag': 'Snapshot',
    # 截图参数
    # 必选
    'Snapshot': {
        # 截图模式
        # 值范围：{Interval, Average, KeyFrame}
        # Interval 表示间隔模式，Start，TimeInterval，Count参数生效。当设置 Count，未设置 TimeInterval 时，表示截取所有帧，共Count张图片
        # Average 表示平均模式，Start，Count参数生效。表示从Start开始到视频结束，按平均间隔截取共Count张图片
        # KeyFrame 表示关键帧模式
        # 非必选，默认为 Interval
        'Mode': 'Interval',
        # 生成截图宽度
        # 值范围：[128，4096] 单位：px
        # 若只设置 Width 时，按照视频原始比例计算 Height
        # 非必选，默认视频原始宽度
        'Width': '128',
        # 生成截图高度
        # 值范围：[128，4096] 单位：px
        # 若只设置 Height 时，按照视频原始比例计算 Width
        # 非必选，默认视频原始高度
        'Height': '128',
        # 截图开始时间
        # [0 视频时长] 单位为秒；支持 float 格式，执行精度精确到毫秒
        # 非必选，默认值为0
        'Start': '0',
        # 截图时间间隔
        # (0 3600] 单位为秒
        # 支持 float 格式，执行精度精确到毫秒
        # 非必选
        'TimeInterval': '10',
        # 截图数量，取值范围 (0，10000]
        # 必选
        'Count': '1',
        # 截图后图片处理参数
        # 详见图片处理：https://cloud.tencent.com/document/product/460/53505
        # 非必选
        'CIParam': '',
        # 是否强制检查截图个数。使用自定义间隔模式截图时，视频时长不够截取 Count 个截图，可以转为平均截图模式截取 Count 个截图
        # 取值 true、false
        # 非必选，默认false
        'IsCheckCount': 'false',
        # 是否开启黑屏检测，
        # 取值 true、false
        # 非必选，默认false
        'IsCheckBlack': 'false',
        # 截图黑屏检测参数，当 IsCheckBlack=true 时有效
        # 值参考范围[30，100]，表示黑色像素的占比值，值越小，黑色占比越小
        # Start > 0，参数设置无效，不做过滤黑屏
        # Start =0 参数有效，截帧的开始时间为第一帧非黑屏开始
        # 非必选
        'BlackLevel': '',
        # 截图黑屏检测参数，当 IsCheckBlack=true 时有效
        # 判断像素点是否为黑色点的阈值，取值范围：[0，255]
        # 非必选
        'PixelBlackThreshold': '',
        # 截图输出模式参数
        # OnlySnapshot：仅输出截图模式
        # OnlySprite：仅输出雪碧图模式
        # SnapshotAndSprite：输出截图与雪碧图模式
        # 非必选，默认OnlySnapshot
        'SnapshotOutMode': 'SnapshotAndSprite',
        # 雪碧图输出配置
        # 非必选
        'SpriteSnapshotConfig': {
            # 单图宽度
            # 值范围：[8，4096]，单位：px
            # 非必选
            'CellWidth': '128',
            # 单图高度
            # 值范围：[8，4096]，单位：px
            # 非必选
            'CellHeight': '128',
            # 雪碧图内边距大小
            # 值范围：[0，1024]，单位：px
            # 非必选，默认为0
            'Padding': '0',
            # 雪碧图外边距大小
            # 值范围：[0，1024]，单位：px
            # 非必选，默认为0
            'Margin': '1',
            # 背景颜色
            # 支持颜色详见 FFmpeg：https://www.ffmpeg.org/ffmpeg-utils.html#color-syntax
            # 必选
            'Color': "AliceBlue",
            # 雪碧图列数
            # 值范围：[1，10000]
            # 必选
            'Columns': '10',
            # 雪碧图行数
            # 值范围：[1，10000]
            # 必选
            'Lines': '20',
            # 雪碧图缩放模式
            # DirectScale: 指定宽高缩放
            # MaxWHScaleAndPad: 指定最大宽高缩放填充
            # MaxWHScale: 指定最大宽高缩放
            # 主动设置 CellWidth 和CellHeight 时生效
            # 非必选，默认 DirectScale
            'ScaleMethod': 'DirectScale'
        },
    },
}


def ci_create_snapshot_template():
    # 创建截图模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=snapshot_template_config,
    )
    print(response)
    return response


def ci_update_snapshot_template():
    # 创建截图模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t17f3ab93bf575xxxxxxxxxxxxxxxxxxx',
        Template=snapshot_template_config,
    )
    print(response)
    return response


transcode_template_config = {
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64
    # 必选
    'Name': 'transcode_template',
    # 模板类型：转码模板固定值为 Transcode
    # 必选
    'Tag': 'Transcode',
    # 容器格式
    # 必选
    'Container': {
        # 封装格式
        # 必选
        'Format': 'mp4',
        # 分片配置，当 format 为 hls 和 dash 时有效
        # 非必选
        'ClipConfig': {
            # 分片时长
            # 非必选，默认5s
            'Duration': '5'
        }
    },
    # 转码视频流配置信息
    # 非必选
    'Video': {
        # 编解码格式
        # H.264 H.265 VP8 VP9 AV1
        # 非必选，H.264，当 Format 为 WebM 时，为 VP8
        'Codec': 'H.264',
        # 转码后的视频宽度
        # 值范围：[128, 4096]，必须为偶数，单位：px
        # 若只设置 Width 时，按照视频原始比例计算 Height
        # 非必选，默认值为视频原始宽度
        'Width': '',
        # 转码后的视频高度
        # 值范围：[128, 4096]，必须为偶数，单位：px
        # 若只设置 Height 时，按照视频原始比例计算 Width
        # 非必选，默认值为视频原始高度
        'Height': '',
        # 转码后的视频帧率
        # 值范围：(0, 60]，单位：fps
        # 非必选
        'Fps': '',
        # 是否删除视频流
        # 取值 true 或 false
        # 非必选，默认false
        'Remove': 'false',
        # 编码级别，仅H.264支持此参数
        # 支持 baseline、main、high、auto
        # 当 视频颜色格式Pixfmt参数为 auto 时，参数值将被设置为 auto
        # baseline：适合移动设备
        # main：适合标准分辨率设备
        # high：适合高分辨率设备
        # 非必选，默认为high
        'Profile': 'high',
        # 转码后的视频码率
        # 值范围：[10, 50000], 单位：Kbps
        # 设置为 auto 表示自适应码率
        # 非必选
        'Bitrate': '',
        # 码率-质量控制因子
        # 值范围：(0, 51]
        # 如果设置了 Crf，则 Bitrate 的设置失效
        # 当 Bitrate 为空时，默认为25
        'Crf': '',
        # 关键帧间最大帧数
        # 值范围：[1, 100000]
        # 非必选
        'Gop': '',
        # 视频算法器预置
        # H.264 支持该参数，取值 veryfast、fast、medium、slow、slower
        # VP8 支持该参数，取值 good、realtime
        # AV1 支持该参数，取值 universal、medium
        # H.265 和 VP9 不支持该参数
        # 非必选，当 Codec 为 H.264 时，为 medium；当 Codec 为 VP8 时，为 good
        'Preset': '',
        # 缓冲区大小
        # 值范围：[1000, 128000]，单位：Kb。Codec 为 VP8/VP9时不支持此参数
        # 非必选
        'Bufsize': '',
        # 视频码率峰值
        # 值范围：[10, 50000]，单位：Kbps，Codec 为 VP8/VP9 时不支持此参数
        # 非必选
        'Maxrate': '',
        # 视频颜色格式
        # H.264支持：yuv420p、yuv422p、yuv444p、yuvj420p、yuvj422p、yuvj444p、auto
        # H.265支持：yuv420p、yuv420p10le、auto
        # Codec 为 VP8/VP9/AV1 时不支持此参数
        # 非必选
        'Pixfmt': '',
        # 长短边自适应，
        # 取值 true 或 false。Codec 为 VP8/VP9/AV1 时不支持此参数。
        # 非必选，默认false
        'LongShortMode': '',
        # 旋转角度
        # 值范围：[0, 360)，单位：度
        # 非必选
        'Rotate': '',
        # Roi 强度
        # 取值为 none、low、medium、high，Codec 为 VP8/VP9 时不支持此参数
        # 非必选，默认为none
        'Roi': 'none',
        # 自由裁剪
        # 自定义裁切: width:height:left:top。示例:1280:800:0:140
        # width和height的值需要大于0，left和top的值需要大于等于0
        # Codec 为 H.265/AV1 时不支持此参数。
        # 开启自适应编码时, 不支持此参数。
        # 开启roi时, 不支持此参数。
        # 非必选
        'Crop': '',
        # 开启隔行扫描
        # false/true
        # Codec 为 H.265/AV1 时不支持此参数。
        # 开启自适应码率时, 不支持此参数。
        # 开启roi时, 不支持此参数。
        # 非必选，默认false
        'Interlaced': 'false',
    },
    # 转码音频信息
    # 非必选
    'Audio': {
        # 编解码格式
        # 取值 aac、mp3、flac、amr、Vorbis、opus、pcm_s16le
        # 非必选 aac；当 format 为 WebM 时，为 Vorbis；当 format 为 wav 时，为 pcm_s16le
        'Codec': '',
        # 采样率
        # 单位：Hz
        # 可选 8000、11025、12000、16000、22050、24000、32000、44100、48000、88200、96000
        # 不同的封装，mp3 支持不同的采样率
        # 当 Codec 设置为 amr 时，只支持8000
        # 当 Codec 设置为 opus 时，支持8000，16000，24000，48000
        # 非必选 默认值44100，当 Codec 为 opus 时，默认值为48000
        'Samplerate': '',
        # 原始音频码率
        # 值范围：[8，1000] 单位：Kbps
        # 非必选
        'Bitrate': '',
        # 声道数
        # 当 Codec 设置为 aac/flac，支持1、2、4、5、6、8
        # 当 Codec 设置为 mp3/opus 时，支持1、2
        # 当 Codec 设置为 Vorbis 时，只支持2
        # 当 Codec 设置为 amr，只支持1
        # 当 Codec 设置为 pcm_s16le 时，只支持1、2
        # 当封装格式为 dash 时，不支持8
        # 非必选
        'Channels': '',
        # 是否删除源音频流
        # 取值 true、false
        # 非必选，默认false
        'Remove': '',
        # 采样位宽
        # 当 Codec 设置为 aac，支持 fltp
        # 当 Codec 设置为 mp3，支持 fltp、s16p、s32p
        # 当 Codec 设置为 flac，支持s16、s32、s16p、s32p
        # 当 Codec 设置为 amr，支持s16、s16p
        # 当 Codec 设置为 opus，支持s16
        # 当 Codec 设置为 pcm_s16le，支持s16
        # 当 Codec 设置为 Vorbis，支持 fltp
        # 当 Video.Codec 为 H.265 时，此参数无效
        'SampleFormat': '',
    },
    'TimeInterval': {
        # 转码开始时间
        # [0 视频时长] 单位为秒，支持 float 格式，执行精度精确到毫秒
        # 非必选，默认为0
        'Start': '',
        # 持续时间
        # 非必选 默认视频源时长
        'Duration': '',
    },
    'TransConfig': {
        # 分辨率调整方式
        # 取值 scale、crop、pad、none
        # 当输出视频的宽高比与原视频不等时，根据此参数做分辨率的相应调整
        # 非必选，默认为none
        'AdjDarMethod': '',
        # 是否检查分辨率，取值 true、false
        # 当为 false 时，按照配置参数转码
        # 非必选，默认false
        'IsCheckReso': '',
        # 分辨率调整方式
        # 当 IsCheckReso 为 true 时生效，取值0、1；
        # 0 表示使用原视频分辨率；
        # 1 表示返回转码失败
        # 非必选 默认为0
        'ResoAdjMethod': '',
        # 是否检查视频码率，取值 true、false
        # 当为 false 时，按照配置参数转码
        # 非必选 默认为false
        'IsCheckVideoBitrate': '',
        # 视频码率调整方式
        # IsCheckVideoBitrate 为 true 时生效，取值0、1；
        # 当输出视频码率大于原视频码率时，0表示使用原视频码率；1表示返回转码失败
        # 非必选 默认为0
        'VideoBitrateAdjMethod': '',
        # 是否检查音频码率，取值 true、false
        # 当为 false 时，按照配置参数转码
        # 非必选 默认为false
        'IsCheckAudioBitrate': '',
        # 音频码率调整方式
        # IsCheckAudioBitrate 为 true 时生效，取值0、1；
        # 当输出音频码率大于原音频码率时，0表示使用原音频码率；1表示返回转码失败
        # 非必选 默认为0
        'AudioBitrateAdjMethod': '',
        # 是否检查视频帧率，取值 true、false
        # 当为 false 时，按照配置参数转码
        # 非必选 默认false
        'IsCheckVideoFps': '',
        # 视频帧率调整方式
        # IsCheckVideoFps 为 true 时生效，取值0、1；
        # 当输出视频帧率大于原视频帧率时，0表示使用原视频帧率；1表示返回转码失败
        # 非必选 默认为0
        'VideoFpsAdjMethod': '',
        # 是否删除文件中的 MetaData 信息
        # 取值 true、false
        # 非必选 默认为false
        'DeleteMetadata': '',
        # 是否开启 HDR 转 SDR
        # 取值 true、false
        # 非必选 默认为false
        'IsHdr2Sdr': '',
        # 指定处理的流编号
        # 非必选
        'TranscodeIndex': '',
        # hls 加密配置
        # 非必选
        'HlsEncrypt': {
            # 是否开启 HLS 加密，取值 true、false
            # 当 Container.Format 为 hls 时支持加密
            # 非必选 默认false
            'IsHlsEncrypt': 'false',
            # HLS 加密的 key
            # 当 IsHlsEncrypt 为 true 时，该参数才有意义
            # 非必选
            'UriKey': ''
        },
        # dash 加密配置
        # 非必选
        'DashEncrypt': {
            # 是否开启 DASH 加密，取值 true、false
            # 当 Container.Format 为 dash 时支持加密
            # 非必选 默认false
            'IsEncrypt': 'false',
            # DASH 加密的 key
            # 当 IsEncrypt 为 true 时，该参数才有意义
            # 非必选
            'UriKey': ''
        },
    },
    # 混音参数
    # 非必选
    'AudioMix': {
        # 需要被混音的音轨媒体地址, 需要做 URLEncode
        # 必选
        'AudioSource': 'http://bucket-1250000000.cos.ap-beijing.myqcloud.com/audioMix.mp3',
        # 混音模式
        # Repeat: 混音循环
        # Once: 混音一次播放
        # 非必选 默认Repeat
        'MixMode': 'Repeat',
        # 是否用混音音轨媒体替换Input媒体文件的原音频
        # true/false
        # 非必选 默认false
        'Replace': '',
        # 混音淡入淡出配置
        # 非必选
        'EffectConfig': {
            # 开启淡入
            # true/false
            # 非必选 默认false
            'EnableStartFadein': '',
            # 淡入时长
            # 大于0, 支持浮点数
            # 非必选
            'StartFadeinTime': '',
            # 开启淡出
            # true/false
            # 非必选 默认false
            'EnableEndFadeout': '',
            # 淡出时长
            # 大于0, 支持浮点数
            # 非必选
            'EndFadeoutTime': '',
            # 开启 bgm 转换淡入
            # true/false
            # 非必选 默认false
            'EnableBgmFade': '',
            # bgm 转换淡入时长
            # 大于0, 支持浮点数
            # 非必选
            'BgmFadeTime': '',
        },
    },
    # 'AudioMixArray': [{
    #     'AudioSource': 'http://bucket-1250000000.cos.ap-beijing.myqcloud.com/audioMix.mp3',
    #     'MixMode': 'Repeat',
    #     'Replace': '',
    #     'EffectConfig': {
    #         'EnableStartFadein': '',
    #         'StartFadeinTime': '',
    #         'EnableEndFadeout': '',
    #         'EndFadeoutTime': '',
    #         'EnableBgmFade': '',
    #         'BgmFadeTime': '',
    #     },
    # },
    #     {
    #         'AudioSource': 'http://bucket-1250000000.cos.ap-beijing.myqcloud.com/audioMix1.mp3',
    #         'MixMode': 'Repeat',
    #         'Replace': '',
    #         'EffectConfig': {
    #             'EnableStartFadein': '',
    #             'StartFadeinTime': '',
    #             'EnableEndFadeout': '',
    #             'EndFadeoutTime': '',
    #             'EnableBgmFade': '',
    #             'BgmFadeTime': '',
    #         },
    #     }],
}


def ci_create_transcode_template():
    # 创建截图模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=transcode_template_config,
    )
    print(response)
    return response


def ci_update_transcode_template():
    # 创建截图模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t16fcd827edf6344xxxxxxxxxxxxxxxxx',
        Template=transcode_template_config,
    )
    print(response)
    return response



high_speed_hd_template_config = {
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64
    # 必选
    'Name': 'high_speed_hd_template',
    # 模板类型：转码模板固定值为 Transcode
    # 必选
    'Tag': 'HighSpeedHd',
    # 容器格式
    # 必选
    'Container': {
        # 封装格式
        # 支持mp4，flv，hls，mkv
        # 必选
        'Format': 'mp4',
        # 分片配置，当 format 为 hls 和 dash 时有效
        # 非必选
        'ClipConfig': {
            # 分片时长
            # 非必选，默认5s
            'Duration': '5'
        }
    },
    # 转码视频流配置信息
    # 非必选
    'Video': {
        # 编解码格式
        # H.264 H.265
        # 非必选，默认值为H.264
        'Codec': 'H.264',
        # 转码后的视频宽度
        # 值范围：[128, 4096]，必须为偶数，单位：px
        # 若只设置 Width 时，按照视频原始比例计算 Height
        # 非必选，默认值为视频原始宽度
        'Width': '',
        # 转码后的视频高度
        # 值范围：[128, 4096]，必须为偶数，单位：px
        # 若只设置 Height 时，按照视频原始比例计算 Width
        # 非必选，默认值为视频原始高度
        'Height': '',
        # 转码后的视频帧率
        # 值范围：(0, 60]，单位：fps
        # 非必选
        'Fps': '',
        # 是否删除视频流
        # 取值 true 或 false
        # 非必选，默认false
        'Remove': 'false',
        # 编码级别，仅H.264支持此参数
        # 支持 baseline、main、high
        # baseline：适合移动设备
        # main：适合标准分辨率设备
        # high：适合高分辨率设备
        # 非必选，默认为high
        'Profile': 'high',
        # 转码后的视频码率
        # 值范围：[10, 50000], 单位：Kbps
        # 设置为 auto 表示自适应码率
        # 非必选
        'Bitrate': '',
        # 码率-质量控制因子
        # 值范围：(0, 51]
        # 如果设置了 Crf，则 Bitrate 的设置失效
        # 当 Bitrate 为空时，默认为25
        'Crf': '',
        # 关键帧间最大帧数
        # 值范围：[1, 100000]
        # 非必选
        'Gop': '',
        # 视频算法器预置
        # H.264 支持该参数，取值 veryfast、fast、medium、slow、slower
        # 非必选，默认值为medium
        'Preset': '',
        # 缓冲区大小
        # 值范围：[1000, 128000]，单位：Kb。Codec 为 VP8/VP9时不支持此参数
        # 非必选
        'Bufsize': '',
        # 视频码率峰值
        # 值范围：[10, 50000]，单位：Kbps，Codec 为 VP8/VP9 时不支持此参数
        # 非必选
        'Maxrate': '',
        # 视频颜色格式
        # H.264支持：yuv420p、auto
        # H.265支持：yuv420p、yuv420p10le、auto
        # 非必选
        'Pixfmt': '',
        # 旋转角度
        # 值范围：[0, 360)，单位：度
        # 非必选
        'Rotate': '',
        # Roi 强度
        # 取值为 none、low、medium、high，Codec 为 VP8/VP9 时不支持此参数
        # 非必选，默认为none
        'Roi': 'none',
    },
    # 转码音频信息
    # 非必选
    'Audio': {
        # 编解码格式
        # 取值 aac、mp3、flac、amr、Vorbis、opus、pcm_s16le
        # 非必选 aac；当 format 为 WebM 时，为 Vorbis；当 format 为 wav 时，为 pcm_s16le
        'Codec': '',
        # 采样率
        # 单位：Hz
        # 可选 8000、11025、12000、16000、22050、24000、32000、44100、48000、88200、96000
        # 不同的封装，mp3 支持不同的采样率
        # 当 Codec 设置为 amr 时，只支持8000
        # 当 Codec 设置为 opus 时，支持8000，16000，24000，48000
        # 非必选 默认值44100，当 Codec 为 opus 时，默认值为48000
        'Samplerate': '',
        # 原始音频码率
        # 值范围：[8，1000] 单位：Kbps
        # 非必选
        'Bitrate': '',
        # 声道数
        # 当 Codec 设置为 aac，支持1、2、4、5、6、8
        # 当 Codec 设置为 mp3，支持1、2
        # 非必选
        'Channels': '',
        # 是否删除源音频流
        # 取值 true、false
        # 非必选，默认false
        'Remove': 'false',
    },
    'TimeInterval': {
        # 转码开始时间
        # [0 视频时长] 单位为秒，支持 float 格式，执行精度精确到毫秒
        # 非必选，默认为0
        'Start': '',
        # 持续时间
        # 非必选 默认视频源时长
        'Duration': '',
    },
    'TransConfig': {
        # 分辨率调整方式
        # 取值 scale、crop、pad、none
        # 当输出视频的宽高比与原视频不等时，根据此参数做分辨率的相应调整
        # 非必选，默认为none
        'AdjDarMethod': '',
        # 是否检查分辨率，取值 true、false
        # 当为 false 时，按照配置参数转码
        # 非必选，默认false
        'IsCheckReso': '',
        # 分辨率调整方式
        # 当 IsCheckReso 为 true 时生效，取值0、1；
        # 0 表示使用原视频分辨率；
        # 1 表示返回转码失败
        # 非必选 默认为0
        'ResoAdjMethod': '',
        # 是否检查视频码率，取值 true、false
        # 当为 false 时，按照配置参数转码
        # 非必选 默认为false
        'IsCheckVideoBitrate': '',
        # 视频码率调整方式
        # IsCheckVideoBitrate 为 true 时生效，取值0、1；
        # 当输出视频码率大于原视频码率时，0表示使用原视频码率；1表示返回转码失败
        # 非必选 默认为0
        'VideoBitrateAdjMethod': '',
        # 是否检查音频码率，取值 true、false
        # 当为 false 时，按照配置参数转码
        # 非必选 默认为false
        'IsCheckAudioBitrate': '',
        # 音频码率调整方式
        # IsCheckAudioBitrate 为 true 时生效，取值0、1；
        # 当输出音频码率大于原音频码率时，0表示使用原音频码率；1表示返回转码失败
        # 非必选 默认为0
        'AudioBitrateAdjMethod': '',
        # 是否检查视频帧率，取值 true、false
        # 当为 false 时，按照配置参数转码
        # 非必选 默认false
        'IsCheckVideoFps': '',
        # 视频帧率调整方式
        # IsCheckVideoFps 为 true 时生效，取值0、1；
        # 当输出视频帧率大于原视频帧率时，0表示使用原视频帧率；1表示返回转码失败
        # 非必选 默认为0
        'VideoFpsAdjMethod': '',
        # 是否删除文件中的 MetaData 信息
        # 取值 true、false
        # 非必选 默认为false
        'DeleteMetadata': '',
        # 是否开启 HDR 转 SDR
        # 取值 true、false
        # 非必选 默认为false
        'IsHdr2Sdr': '',
        # 指定处理的流编号
        # 非必选
        'TranscodeIndex': '',
        # hls 加密配置
        # 非必选
        'HlsEncrypt': {
            # 是否开启 HLS 加密，取值 true、false
            # 当 Container.Format 为 hls 时支持加密
            # 非必选 默认false
            'IsHlsEncrypt': 'false',
            # HLS 加密的 key
            # 当 IsHlsEncrypt 为 true 时，该参数才有意义
            # 非必选
            'UriKey': ''
        },
    },
}


def ci_create_high_speed_hd_template():
    # 创建截图模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=high_speed_hd_template_config,
    )
    print(response)
    return response


def ci_update_high_speed_hd_template():
    # 创建截图模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t1e801dd4a9fcxxxxxxxxxxxxxxx',
        Template=high_speed_hd_template_config,
    )
    print(response)
    return response


animation_template_config = {
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64
    # 必选
    'Name': 'animation_template',
    # 模板类型：转码模板固定值为 Transcode
    # 必选
    'Tag': 'Animation',
    # 容器格式
    # 必选
    'Container': {
        # 封装格式
        # 支持gif，hgif，webp
        # 必选
        'Format': 'gif',
    },
    # 转码视频流配置信息
    # 非必选
    'Video': {
        # 编解码格式
        # gif, webp
        # 必选
        'Codec': 'gif',
        # 转码后的视频宽度
        # 值范围：[128, 4096]，必须为偶数，单位：px
        # 若只设置 Width 时，按照视频原始比例计算 Height
        # 非必选，默认值为视频原始宽度
        'Width': '',
        # 转码后的视频高度
        # 值范围：[128, 4096]，必须为偶数，单位：px
        # 若只设置 Height 时，按照视频原始比例计算 Width
        # 非必选，默认值为视频原始高度
        'Height': '',
        # 转码后的视频帧率
        # 值范围：(0, 60]，单位：fps
        # 如果不设置，那么播放速度按照原来的时间戳。这里设置 fps 为动图的播放帧率
        # 非必选，默认值为视频原始帧率
        'Fps': '',
        # 动图只保留关键帧
        # true ：AnimateTimeIntervalOfFrame 和 AnimateFramesPerSecond 无效
        # false：AnimateTimeIntervalOfFrame  和 AnimateFramesPerSecond 必填
        # 非必选 默认false
        'AnimateOnlyKeepKeyFrame': 'false',
        # 动图抽帧间隔时间
        # 取值范围：（0，视频时长 ]
        # 若设置 TimeInterval.Duration，则小于该值
        # 非必选
        'AnimateTimeIntervalOfFrame': '1',
        # 每秒抽帧帧数，
        # 取值范围：（0，视频帧率）
        # 非必选
        'AnimateFramesPerSecond': '2',
        # 相对质量
        # 取值范围： [1, 100)
        # webp 图像质量设定生效，gif 没有质量参数
        # 非必选
        'Quality': '',
    },
    'TimeInterval': {
        # 转码开始时间
        # [0 视频时长] 单位为秒，支持 float 格式，执行精度精确到毫秒
        # 非必选，默认为0
        'Start': '',
        # 持续时间
        # 非必选 默认视频源时长
        'Duration': '',
    },
}


def ci_create_animation_template():
    # 创建截图模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=animation_template_config,
    )
    print(response)
    return response


def ci_update_animation_template():
    # 创建截图模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t1c0dfe4730b734xxxxxxxxxxxxxxx',
        Template=animation_template_config,
    )
    print(response)
    return response


concat_template_config = {
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64
    # 必选
    'Name': 'concat_template',
    # 模板类型：拼接模板固定值为 Concat
    # 必选
    'Tag': 'Concat',
    # 转码视频流配置信息
    # 非必选
    'ConcatTemplate': {
        'ConcatFragment': [{
            # 拼接对象地址
            # 必选
            'Url': 'http://bucket-1250000000.cos.ap-beijing.myqcloud.com/start.mp4',
            # 节点类型
            # Start：开头，End：结尾
            # 必选
            'Mode': 'Start',
            # 开始时间
            # 单位为秒, 支持float格式，执行精度精确到毫秒
            # 当Request.ConcatTemplate.DirectConcat 为 true 时不生效
            # 非必选
            'StartTime': '0',
            # 结束时间
            # 单位为秒, 支持float格式，执行精度精确到毫秒
            # 当 Request.ConcatTemplate.DirectConcat 为 true 时不生效
            # 非必选
            'EndTime': '2',

        },
        {
            'Url': 'http://bucket-1250000000.cos.ap-beijing.myqcloud.com/end.mp4',
            'Mode': 'End',
        }],
        # 容器格式
        # 必选
        'Container': {
            # 封装格式
            # mp4，flv，hls，ts, mp3, aac
            # 必选
            'Format': 'mp4',
        },
        # 拼接后的视频流配置信息
        # 非必选
        'Video': {
            # 编解码格式
            # H.264
            # 必选，默认值为H.264
            'Codec': 'H.264',
            # 转码后的视频宽度
            # 值范围：[128, 4096]，必须为偶数，单位：px
            # 若只设置 Width 时，按照视频原始比例计算 Height
            # 非必选，默认值为视频原始宽度
            'Width': '',
            # 转码后的视频高度
            # 值范围：[128, 4096]，必须为偶数，单位：px
            # 若只设置 Height 时，按照视频原始比例计算 Width
            # 非必选，默认值为视频原始高度
            'Height': '',
            # 转码后的视频帧率
            # 值范围：(0, 60]，单位：fps
            # 非必选
            'Fps': '',
            # 是否删除视频流
            # 取值 true 或 false
            # 非必选，默认false
            'Remove': 'false',
            # 编码级别，仅H.264支持此参数
            # 支持 baseline、main、high
            # baseline：适合移动设备
            # main：适合标准分辨率设备
            # high：适合高分辨率设备
            # 非必选，默认为high
            'Profile': 'high',
            # 转码后的视频码率
            # 值范围：[10, 50000], 单位：Kbps
            # 设置为 auto 表示自适应码率
            # 非必选
            'Bitrate': '',
            # 码率-质量控制因子
            # 值范围：(0, 51]
            # 如果设置了 Crf，则 Bitrate 的设置失效
            # 当 Bitrate 为空时，默认为25
            'Crf': '',
            # 旋转角度
            # 值范围：[0, 360)，单位：度
            # 非必选
            'Rotate': '',
        },
        # 转码音频信息
        # 非必选
        'Audio': {
            # 编解码格式
            # 取值 aac、mp3
            # 必选
            'Codec': 'mp3',
            # 采样率
            # 单位：Hz
            # 可选 11025、22050、32000、44100、48000、96000
            # 不同的封装，mp3 支持不同的采样率
            # 非必选 默认值文件原采样率
            'Samplerate': '',
            # 原始音频码率
            # 值范围：[8，1000] 单位：Kbps
            # 非必选 默认文件原音频码率
            'Bitrate': '',
            # 声道数
            # 当 Codec 设置为 aac，支持1、2、4、5、6、8
            # 当 Codec 设置为 mp3，支持1、2
            # 非必选 默认文件原声道数
            'Channels': '',
        },
        # 混音参数
        # 非必选
        'AudioMix': {
            # 需要被混音的音轨媒体地址, 需要做 URLEncode
            # 必选
            'AudioSource': 'http://bucket-1250000000.cos.ap-beijing.myqcloud.com/audioMix.mp3',
            # 混音模式
            # Repeat: 混音循环
            # Once: 混音一次播放
            # 非必选 默认Repeat
            'MixMode': 'Repeat',
            # 是否用混音音轨媒体替换Input媒体文件的原音频
            # true/false
            # 非必选 默认false
            'Replace': '',
            # 混音淡入淡出配置
            # 非必选
            'EffectConfig': {
                # 开启淡入
                # true/false
                # 非必选 默认false
                'EnableStartFadein': '',
                # 淡入时长
                # 大于0, 支持浮点数
                # 非必选
                'StartFadeinTime': '',
                # 开启淡出
                # true/false
                # 非必选 默认false
                'EnableEndFadeout': '',
                # 淡出时长
                # 大于0, 支持浮点数
                # 非必选
                'EndFadeoutTime': '',
                # 开启 bgm 转换淡入
                # true/false
                # 非必选 默认false
                'EnableBgmFade': '',
                # bgm 转换淡入时长
                # 大于0, 支持浮点数
                # 非必选
                'BgmFadeTime': '',
            },
        },
        # 'AudioMixArray': [{
        #     'AudioSource': 'http://bucket-1250000000.cos.ap-beijing.myqcloud.com/audioMix.mp3',
        #     'MixMode': 'Repeat',
        #     'Replace': '',
        #     'EffectConfig': {
        #         'EnableStartFadein': '',
        #         'StartFadeinTime': '',
        #         'EnableEndFadeout': '',
        #         'EndFadeoutTime': '',
        #         'EnableBgmFade': '',
        #         'BgmFadeTime': '',
        #     },
        # },
        #     {
        #         'AudioSource': 'http://bucket-1250000000.cos.ap-beijing.myqcloud.com/audioMix1.mp3',
        #         'MixMode': 'Repeat',
        #         'Replace': '',
        #         'EffectConfig': {
        #             'EnableStartFadein': '',
        #             'StartFadeinTime': '',
        #             'EnableEndFadeout': '',
        #             'EndFadeoutTime': '',
        #             'EnableBgmFade': '',
        #             'BgmFadeTime': '',
        #         },
        #     }],
        # 只拼接不转码，
        # 取值 true/ false
        # 非必选 默认false
        'DirectConcat': 'false',
        # 转场参数
        # 非必选
        'SceneChangeInfo': {
            # 转场模式
            # Default：不添加转场特效
            # FADE：淡入淡出
            # GRADIENT：渐变
            # 必选
            'Mode': 'Default',
            # 转场时长
            # 单位：秒(s)
            # 取值范围：(0, 5]，支持小数
            # 非必选 默认值为3
            'Time': '3'
        },
    },
}


def ci_create_contact_template():
    # 创建拼接模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=concat_template_config,
    )
    print(response)
    return response


def ci_update_contact_template():
    # 更新拼接模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t1a0d176b5489xxxxxxxxxxxxxxxxxxx',
        Template=concat_template_config,
    )
    print(response)
    return response


montage_template_config = {
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64
    # 必选
    'Name': 'video_montage_template',
    # 模板类型：精彩集锦模板固定值为 VideoMontage
    # 必选
    'Tag': 'VideoMontage',
    # 集锦时长
    # 单位为秒 支持 float 格式，执行精度精确到毫秒
    # 非必选 默认自动分析时长
    'Duration': '',
    # 精彩集锦场景
    # Video：普通视频
    # Soccer： 足球
    # 非必选 默认为Video
    'Scene': 'Video',
    # 容器格式
    # 必选
    'Container': {
        # 封装格式
        # mp4、flv、hls、ts、mkv
        # 必选
        'Format': 'mp4',
    },
    # 拼接后的视频流配置信息
    # 非必选
    'Video': {
        # 编解码格式
        # H.264、H.265
        # 非必选，默认值为H.264
        'Codec': 'H.264',
        # 转码后的视频宽度
        # 值范围：[128, 4096]，必须为偶数，单位：px
        # 若只设置 Width 时，按照视频原始比例计算 Height
        # 非必选，默认值为视频原始宽度
        'Width': '',
        # 转码后的视频高度
        # 值范围：[128, 4096]，必须为偶数，单位：px
        # 若只设置 Height 时，按照视频原始比例计算 Width
        # 非必选，默认值为视频原始高度
        'Height': '',
        # 转码后的视频帧率
        # 值范围：(0, 60]，单位：fps
        # 非必选
        'Fps': '',
        # 转码后的视频码率
        # 值范围：[10, 50000], 单位：Kbps
        # 非必选
        'Bitrate': '',
        # 码率-质量控制因子
        # 值范围：(0, 51]
        # 如果设置了 Crf，则 Bitrate 的设置失效
        # 当 Bitrate 为空时，默认为25
        'Crf': '',
        # 旋转角度
        # 值范围：[0, 360)，单位：度
        # 非必选
        'Rotate': '',
    },
    # 转码音频信息
    # 非必选
    'Audio': {
        # 编解码格式
        # 取值 aac、mp3
        # 必选
        'Codec': 'mp3',
        # 采样率
        # 单位：Hz
        # 可选 11025、22050、32000、44100、48000、96000
        # 不同的封装，mp3 支持不同的采样率
        # 非必选 默认值文件原采样率
        'Samplerate': '',
        # 原始音频码率
        # 值范围：[8，1000] 单位：Kbps
        # 非必选 默认文件原音频码率
        'Bitrate': '',
        # 声道数
        # 当 Codec 设置为 aac，支持1、2、4、5、6、8
        # 当 Codec 设置为 mp3，支持1、2
        # 非必选 默认文件原声道数
        'Channels': '',
        # 是否删除音频流
        # 取值 true、false
        # 非必选 默认false
        'Remove': 'false'
    },
    # 混音参数
    # 非必选
    'AudioMix': {
        # 需要被混音的音轨媒体地址, 需要做 URLEncode
        # 必选
        'AudioSource': 'http://bucket-1250000000.cos.ap-beijing.myqcloud.com/audioMix.mp3',
        # 混音模式
        # Repeat: 混音循环
        # Once: 混音一次播放
        # 非必选 默认Repeat
        'MixMode': 'Repeat',
        # 是否用混音音轨媒体替换Input媒体文件的原音频
        # true/false
        # 非必选 默认false
        'Replace': '',
        # 混音淡入淡出配置
        # 非必选
        'EffectConfig': {
            # 开启淡入
            # true/false
            # 非必选 默认false
            'EnableStartFadein': '',
            # 淡入时长
            # 大于0, 支持浮点数
            # 非必选
            'StartFadeinTime': '',
            # 开启淡出
            # true/false
            # 非必选 默认false
            'EnableEndFadeout': '',
            # 淡出时长
            # 大于0, 支持浮点数
            # 非必选
            'EndFadeoutTime': '',
            # 开启 bgm 转换淡入
            # true/false
            # 非必选 默认false
            'EnableBgmFade': '',
            # bgm 转换淡入时长
            # 大于0, 支持浮点数
            # 非必选
            'BgmFadeTime': '',
        },
    },
    # 'AudioMixArray': [{
    #     'AudioSource': 'http://bucket-1250000000.cos.ap-beijing.myqcloud.com/audioMix.mp3',
    #     'MixMode': 'Repeat',
    #     'Replace': '',
    #     'EffectConfig': {
    #         'EnableStartFadein': '',
    #         'StartFadeinTime': '',
    #         'EnableEndFadeout': '',
    #         'EndFadeoutTime': '',
    #         'EnableBgmFade': '',
    #         'BgmFadeTime': '',
    #     },
    # },
    #     {
    #         'AudioSource': 'http://bucket-1250000000.cos.ap-beijing.myqcloud.com/audioMix1.mp3',
    #         'MixMode': 'Repeat',
    #         'Replace': '',
    #         'EffectConfig': {
    #             'EnableStartFadein': '',
    #             'StartFadeinTime': '',
    #             'EnableEndFadeout': '',
    #             'EndFadeoutTime': '',
    #             'EnableBgmFade': '',
    #             'BgmFadeTime': '',
    #         },
    #     }],
}


def ci_create_video_montage_template():
    # 创建精彩集锦模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=montage_template_config,
    )
    print(response)
    return response


def ci_update_video_montage_template():
    # 更新精彩集锦模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t1381a5708bfdxxxxxxxxxxxxxxxxx',
        Template=montage_template_config,
    )
    print(response)
    return response


voice_separate_template_config = {
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64
    # 必选
    'Name': 'voice_separate_template',
    # 模板类型：人声分离模板固定值为 VoiceSeparate
    # 必选
    'Tag': 'VoiceSeparate',
    # 输出音频
    # IsAudio：输出人声
    # IsBackground：输出背景声
    # AudioAndBackground：输出人声和背景声
    # MusicMode：输出人声、背景声、Bass声、鼓声
    # 必选
    'AudioMode': 'IsAudio',
    # 转码音频信息
    # 非必选
    'AudioConfig': {
        # 编解码格式
        # 取值 aac、mp3、flac、amr。当 Request.AudioMode 为 MusicMode 时，仅支持 mp3、wav、aac
        # 非必选，默认aac
        'Codec': 'aac',
        # 采样率
        # 单位：Hz
        # 可选 8000、11025、22050、32000、44100、48000、96000
        # 当 Codec 设置为 aac/flac 时，不支持 8000
        # 当 Codec 设置为 mp3 时，不支持 8000 和 96000
        # 当 Codec 设置为 amr 时，只支持 8000
        # 当 Request.AudioMode 为 MusicMode 时，该参数无效
        # 非必选 默认值为44100
        'Samplerate': '44100',
        # 原始音频码率
        # 值范围：[8，1000] 单位：Kbps
        # 当 Request.AudioMode 为 MusicMode 时，该参数无效
        # 非必选 默认文件原音频码率
        'Bitrate': '',
        # 声道数
        # 当 Codec 设置为 aac/flac，支持1、2、4、5、6、8
        # 当 Codec 设置为 mp3，支持1、2
        # 当 Codec 设置为 amr，只支持1
        # 当 Request.AudioMode 为 MusicMode 时，该参数无效
        # 非必选 默认原始音频声道数
        'Channels': '',
    },
}


def ci_create_voice_separate_template():
    # 创建人声分离模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=voice_separate_template_config,
    )
    print(response)
    return response


def ci_update_voice_separate_template():
    # 更新人声分离模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t1381a5708bfd74xxxxxxxxxxxxxxxxxx',
        Template=voice_separate_template_config,
    )
    print(response)
    return response


pic_process_template_config = {
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64
    # 必选
    'Name': 'pic_process_template',
    # 模板类型：图片处理模板固定值为 PicProcess
    # 必选
    'Tag': 'PicProcess',
    # 图片处理信息
    # 必选
    'PicProcess': {
        # 是否返回原图信息
        # 取值 true/false
        # 非必选 默认 false
        'IsPicInfo': 'false',
        # 图片处理规则
        # 详见 https://cloud.tencent.com/document/product/436/44879
        # 必选
        'ProcessRule': 'imageMogr2/rotate/90',
    },
}


def ci_create_pic_process_template():
    # 创建人声分离模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=pic_process_template_config,
    )
    print(response)
    return response


def ci_update_pic_process_template():
    # 更新人声分离模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t1fdb441f4967xxxxxxxxxxxxxxxx',
        Template=pic_process_template_config,
    )
    print(response)
    return response


watermark_template_config = {
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64
    # 必选
    'Name': 'watermark_template',
    # 模板类型：水印模板固定值为 Watermark
    # 必选
    'Tag': 'Watermark',
    # 水印信息
    # 必选
    'Watermark': {
        # 水印类型
        # Text：文字水印
        # Image：图片水印
        # 必选
        'Type': 'Image',
        # 偏移方式
        # Relativity：按比例
        # Absolute：固定位置
        # 必选
        'LocMode': 'Absolute',
        # 水平偏移
        # 在图片水印中，如果 Background 为 true，当 locMode 为 Relativity 时，为%，值范围：[-300 0]；当 locMode 为 Absolute 时，为 px，值范围：[-4096 0]。
        # 在图片水印中，如果 Background 为 false，当 locMode 为 Relativity 时，为%，值范围：[0 100]；当 locMode 为 Absolute 时，为 px，值范围：[0 4096]。
        # 在文字水印中，当 locMode 为 Relativity 时，为%，值范围：[0 100]；当 locMode 为 Absolute 时，为 px，值范围：[0 4096]。
        # 当Pos为Top、Bottom和Center时，该参数无效。
        #'Dx': '128',

        # 垂直偏移
        # 在图片水印中，如果 Background 为 true，当 locMode 为 Relativity 时，为%，值范围：[-300 0]；当 locMode 为 Absolute 时，为 px，值范围：[-4096 0]。
        # 在图片水印中，如果 Background 为 false，当 locMode 为 Relativity 时，为%，值范围：[0 100]；当 locMode 为 Absolute 时，为 px，值范围：[0 4096]。
        # 在文字水印中，当 locMode 为 Relativity 时，为%，值范围：[0 100]；当 locMode 为 Absolute 时，为 px，值范围：[0 4096]。
        # 当Pos为Left、Right和Center时，该参数无效。
        #'Dy': '128',
        # 基准位置
        # TopRight TopLeft
        # BottomRight BottomLeft
        # Right Left
        # Top Bottom Center
        # 必选
        'Pos': 'TopLeft',
        # 水印开始时间
        # [0，视频时长]
        #  单位为秒
        # 支持 float 格式，执行精度精确到毫秒
        # 非必选 默认为0
        'StartTime': '',
        # 水印结束时间
        # [0，视频时长]
        # 单位为秒
        # 支持 float 格式，执行精度精确到毫秒
        # 非必选 默认视频时长
        'EndTime': '',
        # 水印滑动配置，配置该参数后水印位移设置不生效，极速高清/H265转码暂时不支持该参数
        # 非必选
        'SlideConfig': {
            # 滑动模式
            # Default: 默认不开启
            # ScrollFromLeft: 从左到右滚动
            # 若设置了ScrollFromLeft模式，则Watermark.Pos参数不生效
            # 必选
            'SlideMode': 'Default',
            # 横向滑动速度，取值范围：[0,10]内的整数
            # 非必选 默认为0
            'XSlideSpeed': '0',
            # 纵向滑动速度，取值范围：[0,10]内的整数
            # 非必选 默认为0
            'YSlideSpeed': '0'
        },
        # 图片水印节点
        # 非必选
        'Image': {
            # 水印图地址(需要 Urlencode 后传入)
            # 必选
            'Url': 'http://bucket-1250000000.cos.ap-beijing.myqcloud.com/watermark.png',
            # 尺寸模式
            # Original：原有尺寸
            # Proportion：按比例
            # Fixed：固定大小
            # 必选
            'Mode': 'Original',
            # 宽
            # 当 Mode 为 Original 时，不支持设置水印图宽度
            # 当 Mode 为 Proportion，单位为%，背景图值范围：[100 300]；前景图值范围：[1 100]，相对于视频宽，最大不超过4096px
            # 当 Mode 为 Fixed，单位为 px，值范围：[8，4096]
            # 若只设置 Width 时，按照水印图比例计算 Height
            # 非必选
            'Width': '',
            # 高
            # 当 Mode 为 Original 时，不支持设置水印图高度
            # 当 Mode 为 Proportion，单位为%，背景图值范围：[100 300]；前景图值范围：[1 100]，相对于视频高，最大不超过4096px
            # 当 Mode 为 Fixed，单位为 px，值范围：[8，4096]
            # 若只设置 Height 时，按照水印图比例计算 Width
            # 非必选
            'Height': '',
            # 透明度，值范围：[1 100]，单位%
            # 必选
            'Transparency': '30',
            # 是否背景图，取值 true、false
            # 非必选 默认false
            'Background': 'false',
        },
        # 文本水印节点
        # 非必选
        'Text': {
            # 水印内容，长度不超过64个字符，仅支持中文、英文、数字、_、-和*
            # 必选
            'Text': "test",
            # 字体大小，值范围：[5 100]，单位 px
            # 必选
            'FontSize': '40',
            # 字体类型
            # 必选
            'FontType': 'simfang.ttf',
            # 字体颜色，格式：0xRRGGBB
            # 必选
            'FontColor': '0x123456',
            # 透明度，值范围：[1 100]，单位%
            # 必选
            'Transparency': '30'
        }
    }
}


def ci_create_watermark_template():
    # 创建人声分离模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=watermark_template_config,
    )
    print(response)
    return response


def ci_update_watermark_template():
    # 更新人声分离模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t151d54442e1514ccea5fe031431dc5929',
        Template=watermark_template_config,
    )
    print(response)
    return response


def ci_get_template():
    # 更新人声分离模板
    response = client.ci_get_template(
        Bucket=bucket_name,
    )
    print(response)
    return response


transcode_pro_template_config = {
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64
    # 必选
    'Name': 'transcode_pro_template',
    # 模板类型：转码模板固定值为 Transcode
    # 必选
    'Tag': 'TranscodePro',
    # 容器格式
    # 必选
    'Container': {
        # 封装格式：mxf、mov、mkv
        # 必选
        'Format': 'mxf',
    },
    # 转码视频流配置信息
    # 非必选
    'Video': {
        # 编解码格式
        # xavc、apple_prores
        # 必选
        'Codec': 'xavc',
        # 转码后的视频宽度
        'Width': '1440',
        # 转码后的视频高度
        'Height': '1080',
        # 转码后的视频帧率
        'Fps': '25',
        # 视频算法器预置
        'Profile': 'XAVC-HD_intra_420_10bit_class50',
        # 场模式
        'Interlaced': 'true',
        # 视频输出文件的码率
        'Bitrate': '',
        # 旋转角度
        'Rotate': '1'
    },
    # 转码音频信息
    # 非必选
    'Audio': {
        # 编解码格式
        # pcm_s24le、aac、mp3
        # 必选
        'Codec': 'pcm_s24le',
        # 是否删除源音频流
        # 取值 true、false
        # 非必选，默认false
        'Remove': '',
    },
    'TimeInterval': {
        # 转码开始时间
        # [0 视频时长] 单位为秒，支持 float 格式，执行精度精确到毫秒
        # 非必选，默认为0
        'Start': '',
        # 持续时间
        # 非必选 默认视频源时长
        'Duration': '',
    },
    'TransConfig': {
        # 分辨率调整方式
        # 取值 scale、crop、pad、none
        # 当输出视频的宽高比与原视频不等时，根据此参数做分辨率的相应调整
        # 非必选，默认为none
        'AdjDarMethod': '',
        # 是否检查分辨率，取值 true、false
        # 当为 false 时，按照配置参数转码
        # 非必选，默认false
        'IsCheckReso': '',
        # 分辨率调整方式
        # 当 IsCheckReso 为 true 时生效，取值0、1；
        # 0 表示使用原视频分辨率；
        # 1 表示返回转码失败
        # 非必选 默认为0
        'ResoAdjMethod': '',
        # 是否检查视频码率，取值 true、false
        # 当为 false 时，按照配置参数转码
        # 非必选 默认为false
        'IsCheckVideoBitrate': '',
        # 视频码率调整方式
        # IsCheckVideoBitrate 为 true 时生效，取值0、1；
        # 当输出视频码率大于原视频码率时，0表示使用原视频码率；1表示返回转码失败
        # 非必选 默认为0
        'VideoBitrateAdjMethod': '',
        # 是否检查音频码率，取值 true、false
        # 当为 false 时，按照配置参数转码
        # 非必选 默认为false
        'IsCheckAudioBitrate': '',
        # 音频码率调整方式
        # IsCheckAudioBitrate 为 true 时生效，取值0、1；
        # 当输出音频码率大于原音频码率时，0表示使用原音频码率；1表示返回转码失败
        # 非必选 默认为0
        'AudioBitrateAdjMethod': '',
        # 是否检查视频帧率，取值 true、false
        # 当为 false 时，按照配置参数转码
        # 非必选 默认false
        'IsCheckVideoFps': '',
        # 视频帧率调整方式
        # IsCheckVideoFps 为 true 时生效，取值0、1；
        # 当输出视频帧率大于原视频帧率时，0表示使用原视频帧率；1表示返回转码失败
        # 非必选 默认为0
        'VideoFpsAdjMethod': '',
        # 是否删除文件中的 MetaData 信息
        # 取值 true、false
        # 非必选 默认为false
        'DeleteMetadata': '',
        # 是否开启 HDR 转 SDR
        # 取值 true、false
        # 非必选 默认为false
        'IsHdr2Sdr': '',
    },
}


def ci_create_transcode_pro_template():
    # 创建截图模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=transcode_pro_template_config,
    )
    print(response)
    return response


def ci_update_transcode_pro_template():
    # 更新人声分离模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t16b96b496527b4xxxxxxxxxxxxxxxxxx',
        Template=transcode_pro_template_config,
    )
    print(response)
    return response


tts_template_config = {
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64
    # 必选
    'Name': 'tts_template',
    # 模板类型：图片处理模板固定值为 PicProcess
    # 必选
    'Tag': 'Tts',
    # 处理模式，Asyc（异步合成）、Sync（同步合成）
    # 当选择 Asyc 时，codec 只支持 pcm
    # 默认值 Asyc
    'Mode': '',
    # 音频格式，wav、mp3、pcm
    # 默认值 wav（同步）/pcm（异步）
    'Codec': '',
    # 音色
    # 默认值 ruxue
    'VoiceType': '',
    # 音量
    # 取值范围：[-10,10]
    # 默认值0
    'Volume': '',
    # 语速
    # 取值范围：[50,200]
    # 默认值100
    'Speed': '',
}


def ci_create_tts_template():
    # 创建人声分离模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=tts_template_config,
    )
    print(response)
    return response


def ci_update_tts_template():
    # 更新人声分离模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t1f926a582106340xxxxxxxxxxxxxxxxx',
        Template=tts_template_config,
    )
    print(response)
    return response


smart_cover_template_config = {
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64
    # 必选
    'Name': 'smart_cover_template',
    # 模板类型：水印模板固定值为 Watermark
    # 必选
    'Tag': 'SmartCover',
    # 水印信息
    # 必选
    'SmartCover': {
        # 图片格式
        # jpg、png、webp
        # 非必选 默认值为jpg
        'Format': '',
        # 宽
        # 值范围：[128，4096]
        # 单位：px
        # 若只设置 Width 时，按照视频原始比例计算 Height
        # 非必选 默认视频原始宽度
        'Width': '',
        # 高
        # 值范围：[128，4096]
        # 单位：px
        # 若只设置 Height 时，按照视频原始比例计算 Width
        # 非必选 默认视频原始高度
        'Height': '',
        # 截图数量
        # 取值范围：[1,10]
        # 非必选 默认为3
        'Count': '',
        # 封面去重
        # 取值范围：true false
        # 非必选 默认为false
        'DeleteDuplicates': 'false',
    }
}


def ci_create_smart_cover_template():
    # 创建人声分离模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=smart_cover_template_config,
    )
    print(response)
    return response


def ci_update_smart_cover_template():
    # 更新人声分离模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t13eb9cabe8xxxxxxxxxxxxxxxxxxxx',
        Template=smart_cover_template_config,
    )
    print(response)
    return response


noise_reduction_template_config = {
    # 固定值：NoiseReduction
    # 是否必传：是
    'Tag': "NoiseReduction",
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64。
    # 是否必传：是
    'Name': "noise_reduction_test",
    # 降噪参数
    # 是否必传：是
    'NoiseReduction': {
        # 封装格式，支持 mp3、m4a、wav
        # 是否必传：否
        'Format': "wav",
        # 采样率单位：Hz可选 8000、12000、16000、24000、32000、44100、48000
        # 是否必传：否
        'Samplerate': "8000",
    },
}


def ci_create_noise_reduction_template():
    # 创建音频降噪模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=noise_reduction_template_config,
    )
    print(response)
    return response


def ci_update_noise_reduction_template():
    # 更新音频降噪模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t1ec6c1xxxxxxxxxxxxxxxxxxxxxx',
        Template=noise_reduction_template_config,
    )
    print(response)
    return response


video_target_rec_template_config = {
    # 模板类型：VideoTargetRec
    # 是否必传：是
    'Tag': "VideoTargetRec",
    # 模板名称，仅支持中文、英文、数字、_、-和*，长度不超过 64
    # 是否必传：是
    'Name': "video_target_rec_test",
    # 视频目标检测 参数
    # 是否必传：是
    'VideoTargetRec': {
        # 是否开启人体检测，取值 true/false
        # 是否必传：否
        'Body': "true",
        # 是否开启宠物检测，取值 true/false
        # 是否必传：否
        'Pet': "true",
        # 是否开启车辆检测，取值 true/false
        # 是否必传：否
        'Car': "false",
    },
}


def ci_create_video_target_template():
    # 创建视频目标检测模板
    response = client.ci_create_template(
        Bucket=bucket_name,
        Template=video_target_rec_template_config,
    )
    print(response)
    return response


def ci_update_video_target_template():
    # 更新视频目标检测模板
    response = client.ci_update_template(
        Bucket=bucket_name,
        TemplateId='t17de5xxxxxxxxxxxxxxxxxxxxxxx',
        Template=video_target_rec_template_config,
    )
    print(response)
    return response


if __name__ == "__main__":
    # ci_create_snapshot_template()
    # ci_update_snapshot_template()
    # ci_create_transcode_template()
    # ci_update_transcode_template()
    # ci_create_high_speed_hd_template()
    # ci_update_high_speed_hd_template()
    # ci_create_animation_template()
    # ci_update_animation_template()
    # ci_create_contact_template()
    # ci_update_contact_template()
    # ci_create_video_montage_template()
    # ci_update_video_montage_template()
    # ci_create_voice_separate_template()
    # ci_update_voice_separate_template()
    # ci_create_pic_process_template()
    # ci_update_pic_process_template()
    # ci_create_watermark_template()
    # ci_update_watermark_template()
    # ci_get_template()
    # ci_create_transcode_pro_template()
    # ci_update_transcode_pro_template()
    # ci_create_tts_template()
    # ci_update_tts_template()
    # ci_create_smart_cover_template()
    # ci_update_smart_cover_template()
    # ci_create_noise_reduction_template()
    # ci_update_noise_reduction_template()
    # ci_create_video_target_template()
    ci_update_video_target_template()

