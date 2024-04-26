# -*- coding=utf-8
import time

from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client

import sys
import logging
import os

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

# 媒体处理相关API请参考 https://cloud.tencent.com/document/product/460/84790

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


def ci_get_media_bucket():
    # 查询媒体处理开通状态
    response = client.ci_get_media_bucket(
        Regions=region,
        BucketName='demo',
        BucketNames=bucket_name,
        PageSize="1",
        PageNumber="1"
    )
    print(response)
    return response


def ci_get_media_queue():
    # 查询媒体队列信息
    response = client.ci_get_media_queue(
                    Bucket=bucket_name,
                )
    print(response)
    return response


def ci_get_pic_bucket():
    # 查询图片处理异步服务开通状态
    response = client.ci_get_pic_bucket(
        Regions=region,
        BucketName='demo',
        BucketNames=bucket_name,
        PageSize="1",
        PageNumber="1"
    )
    print(response)
    return response


def ci_get_ai_bucket():
    # 查询ai处理异步服务开通状态
    response = client.ci_get_ai_bucket(
        Regions=region,
        BucketName='demo',
        BucketNames=bucket_name,
        PageSize="1",
        PageNumber="1"
    )
    print(response)
    return response


def ci_get_ai_queue():
    # 查询ai处理队列信息
    response = client.ci_get_ai_queue(
        Bucket=bucket_name,
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


def ci_get_media_pic_queue():
    # 查询图片处理队列信息
    response = client.ci_get_media_pic_queue(
        Bucket=bucket_name,
    )
    print(response)
    return response


def ci_put_media_queue():
    # 更新媒体队列信息
    body = {
        'Name': 'media-queue',
        'QueueID': 'p5135bc6xxxxxxxxxxxxxxxxf047454',
        'State': 'Active',
        'NotifyConfig': {
            'Type': 'Url',
            'Url': 'http://www.demo.callback.com',
            'Event': 'TaskFinish',
            'State': 'On',
            'ResultFormat': 'JSON',
            # TDMQ回调信息配置
            # 消息队列所属园区
            # 必选。目前支持园区 sh（上海）、bj（北京）、gz（广州）、cd（成都）、hk（中国香港）
            # 'MqRegion': 'bj',
            # # 消息队列使用模式
            # # 必选。主题订阅：Topic 队列服务: Queue
            # 'MqMode': 'Queue',
            # # TDMQ 主题名称 必选。
            # 'MqName': 'queueName'
        }
    }
    response = client.ci_update_media_queue(
        Bucket=bucket_name,
        QueueId='p5135bcxxxxxxxxxxxxxxxxf047454',
        Request=body,
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_put_media_pic_queue():
    # 更新图片处理队列信息
    body = {
        'Name': 'media-pic-queue',
        'QueueID': 'peb83bdxxxxxxxxxxxxxxxxa21c7d68',
        'State': 'Active',
        'NotifyConfig': {
            'Type': 'Url',
            'Url': 'http://www.demo.callback.com',
            'Event': 'TaskFinish',
            'State': 'On',
            'ResultFormat': 'JSON'
        }
    }
    response = client.ci_update_media_pic_queue(
        Bucket=bucket_name,
        QueueId='peb83bdxxxxxxxxxxxxxxxxxx4a21c7d68',
        Request=body,
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_media_transcode_with_digital_watermark_jobs():
    # 创建带数字水印的转码任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'Transcode',
        'Operation': {
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'transcode_with_digital_watermark_output.mp4'
            },
            'TemplateId': 't04e1ab86554984f1aa17c062fbf6c007c',
            'DigitalWatermark': {
                'Type': 'Text',
                'Message': '123456789ab',
                'Version': 'V1',
                'IgnoreError': 'false',
            },
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


def ci_create_media_transcode_with_watermark_jobs():
    # 创建带水印的转码任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'Transcode',
        'Operation': {
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'transcode_with_watermark_output.mp4'
            },
            'TemplateId': 't04e1ab86554984f1aa17c062fbf6c007c',
            # "WatermarkTemplateId": ["", ""],
            'Watermark': [
                {
                    'Type': 'Text',
                    'Pos': 'TopRight',
                    'LocMode': 'Absolute',
                    'Dx': '64',
                    'Dy': '64',
                    'StartTime': '0',
                    'EndTime': '1000.5',
                    'Text': {
                        'Text': '水印内容',
                        'FontSize': '90',
                        'FontType': 'simfang.ttf',
                        'FontColor': '0xFFEEFF',
                        'Transparency': '100',
                    },
                },
                {
                    'Type': 'Image',
                    'Pos': 'TopLeft',
                    'LocMode': 'Absolute',
                    'Dx': '100',
                    'Dy': '100',
                    'StartTime': '0',
                    'EndTime': '1000.5',
                    'Image': {
                        'Url': 'http://' + bucket_name + ".cos." + region + ".myqcloud.com/watermark.png",
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


def ci_create_media_hls_transcode_jobs():
    # 创建hls转码任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'Transcode',
        'Operation': {
            "Transcode": {
                "Container": {
                    "Format": "hls"
                },
                "Video": {
                    "Codec": "H.264",
                    "Profile": "high",
                    "Bitrate": "1000",
                    "Width": "1280",
                    "Fps": "30",
                    "Preset": "medium",
                    "Bufsize": "1000",
                    "Maxrate": "10"
                },
                "Audio": {
                    "Codec": "aac",
                    "Samplerate": "44100",
                    "Bitrate": "128",
                    "Channels": "4"
                },
                "TransConfig": {
                    'HlsEncrypt': {
                        'IsHlsEncrypt': 'true',
                        'UriKey': 'http://www.demo.com'
                    }
                },
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'transcode_output.mp4'
            },
            # 'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5'
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


def ci_create_media_transcode_jobs():
    # 创建转码任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'Transcode',
        'Operation': {
            "Transcode": {
                "Container": {
                    "Format": "mp4"
                },
                "Video": {
                    "Codec": "H.264",
                    "Profile": "high",
                    "Bitrate": "1000",
                    "Width": "1280",
                    "Fps": "30",
                    "Preset": "medium",
                    "Bufsize": "1000",
                    "Maxrate": "10"
                },
                "Audio": {
                    "Codec": "aac",
                    "Samplerate": "44100",
                    "Bitrate": "128",
                    "Channels": "4"
                },
                "TransConfig": {
                    "AdjDarMethod": "scale",
                    "IsCheckReso": "false",
                    "ResoAdjMethod": "1"
                },
                "TimeInterval": {
                    "Start": "0",
                    "Duration": "60"
                }
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'transcode_output.mp4'
            },
            # 'FreeTranscode': 'true',
            # 'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5'
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


def ci_create_media_snapshot_jobs():
    # 创建截图任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'Snapshot',
        'Operation': {
            'Snapshot': {
                'Mode': 'Interval',
                'Width': '1280',
                'Height': '1280',
                'Start': '0',
                'TimeInterval': '',
                'Count': '1',
                'SnapshotOutMode': 'SnapshotAndSprite',
                'SpriteSnapshotConfig': {
                    "CellHeight": "128",
                    "CellWidth": "128",
                    "Color": "White",
                    "Columns": "10",
                    "Lines": "10",
                    "Margin": "0",
                    "Padding": "0"
                }
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'snapshot-${Number}.jpg',
                'SpriteObject': 'sprite-snapshot-${Number}.jpg'
            },
            # 'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5'
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


def ci_create_media_animation_jobs():
    # 创建转动图任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'Animation',
        'Operation': {
            "Animation": {
                "Container": {
                    "Format": "gif"
                },
                "Video": {
                    "Codec": "gif",
                    "Width": "1280",
                    "Fps": "15",
                    "AnimateOnlyKeepKeyFrame": "true"
                },
                "TimeInterval": {
                    "Start": "0",
                    "Duration": "60"
                }
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'snapshot.gif'
            },
            # 'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5'
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


def ci_create_media_concat_jobs():
    # 创建拼接任务，以下示例仅展示部分参数，更详细参数详见API文档
    # API文档：https://cloud.tencent.com/document/product/460/84788
    body = {
        # 任务类型，拼接任务为Concat
        'Tag': 'Concat',
        'Operation': {
            # 拼接参数
            "ConcatTemplate": {
                # 拼接节点
                "ConcatFragment": [
                    {
                        # 拼接对象地址
                        "Url": "http://demo-1xxxxxxxxx.cos.ap-chongqing.myqcloud.com/1.mp4",
                        # 拼接对象的索引位置, 非必传参数，默认为0
                        "FragmentIndex": "0",
                        # 开始/结束时间,表示截取 StartTime - EndTime的视频段进行拼接，非必传参数，
                        # Request.Operation.ConcatTemplate.DirectConcat 为 true 时不生效
                        # 此示例表示截取1.mp4的0-1s的视频段进行拼接
                        "StartTime": "0",
                        "EndTime": "1"
                    },
                    {
                        "Url": "http://demo-1xxxxxxxxx.cos.ap-chongqing.myqcloud.com/2.mp4",
                        "FragmentIndex": "1",
                    }
                ],
                # 目标文件的音频配置，非必传参数
                "Audio": {
                    "Codec": "mp3"
                },
                # 目标文件的视频配置，非必传参数
                "Video": {
                    "Codec": "H.264",
                    "Bitrate": "1000",
                    "Width": "1280",
                    "Fps": "30"
                },
                # 目标文件的封装格式
                "Container": {
                    # 封装格式：mp4，flv，hls，ts, mp3, aac
                    "Format": "mp4"
                },
                # 转场参数
                "SceneChangeInfo": {
                    # 转场模式
                    # Default：不添加转场特效
                    # FADE：淡入淡出
                    # GRADIENT：渐变
                    "Mode": "Default",
                    # 转场时长 非必传参数，单位秒， 默认为3秒
                    # 取值范围：(0, 5], 支持小数
                    "Time": "3",
                },
                # 简单拼接方式（不转码直接拼接），若值为true，以上视频和音频参数失效
                "DirectConcat": "false",
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'concat-result.mp4'
            },
        }
    }
    lst = ['<ConcatFragment>', '</ConcatFragment>']
    response = client.ci_create_media_jobs(
        Bucket=bucket_name,
        Jobs=body,
        Lst=lst,
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_media_smart_cover_jobs():
    # 创建智能封面任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'SmartCover',
        'Operation': {
            'SmartCover': {
                'Format': 'jpg',
                'Width': '128',
                'Height': '128',
                'Count': '3',
                'DeleteDuplicates': 'true'
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'smart-cover-${Number}.jpg'
            },
            # 'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5'
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


def ci_create_media_video_process_jobs():
    # 创建视频增强任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'VideoProcess',
        'Operation': {
            "VideoProcess": {
                "ColorEnhance": {
                    "Enable": "true",
                    "Contrast": "10",
                    "Correction": "10",
                    "Saturation": "10"
                },
                "MsSharpen": {
                    "Enable": "true",
                    "SharpenLevel": "1"
                }
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'video-process.mp4'
            },
            # 'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5',
            'TranscodeTemplateId': 't04e1ab86554984f1aa17c062fbf6c007c'
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


def ci_create_media_video_montage_jobs():
    # 创建精彩集锦任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'VideoMontage',
        'Operation': {
            "VideoMontage": {
                "Container": {
                    "Format": "mp4"
                },
                "Video": {
                    "Codec": "H.264",
                    "Bitrate": "1000",
                    "Width": "1280",
                    "Height": "1280"
                },
                "Audio": {
                    "Codec": "aac",
                    "Samplerate": "44100",
                    "Bitrate": "128",
                    "Channels": "4"
                },
                "AudioMix": {
                    "AudioSource": "https://demo-xxxxxxxxxxxx.cos.ap-chongqing.myqcloud.com/1.mp4",
                    "MixMode": "Once",
                    "Replace": "true"
                },
                "Duration": "1"
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'video-montage.mp4'
            },
            # 'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5',
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


def ci_create_media_voice_separate_jobs():
    # 创建人声分离任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'VoiceSeparate',
        'Operation': {
            "VoiceSeparate": {
                "AudioMode": "IsAudio",
                "AudioConfig": {
                    "Codec": "mp3",
                    "Samplerate": "44100",
                    "Bitrate": "12",
                    "Channels": "2"
                }
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'voice-separate.mp3',
                'AuObject': 'voice-separate-audio.mp3'
            },
            # 'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5',
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


def ci_create_media_sdr2hdr_jobs():
    # 创建sdr2hdr任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'SDRtoHDR',
        'Operation': {
            "SDRtoHDR": {
                "HdrMode": "HLG",
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'sdr2hdr.mp4'
            },
            'TranscodeTemplateId': 't04e1ab86554984f1aa17c062fbf6c007c'
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


def ci_create_media_digital_watermark_jobs():
    # 创建嵌入数字水印任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'DigitalWatermark',
        'Operation': {
            "DigitalWatermark": {
                "Type": "Text",
                "Message": "123456789ab",
                "Version": "V1"
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'digital.mp4'
            },
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


def ci_create_media_extract_digital_watermark_jobs():
    # 创建提取数字水印任务
    body = {
        'Input': {
            'Object': 'digital.mp4'
        },
        'Tag': 'ExtractDigitalWatermark',
        'Operation': {
            "ExtractDigitalWatermark": {
                "Type": "Text",
                "Version": "V1"
            },
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


def ci_create_media_super_resolution_jobs():
    # 创建超分任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'SuperResolution',
        'Operation': {
            "SuperResolution": {
                "Resolution": "sdtohd",
                "EnableScaleUp": "true"
            },
            'TranscodeTemplateId': 't04e1ab86554984f1aa17c062fbf6c007c',
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'super.mp4'
            },
        },
    }
    response = client.ci_create_media_jobs(
        Bucket=bucket_name,
        Jobs=body,
        Lst={},
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_media_video_tag_jobs():
    # 创建视频标签任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'VideoTag',
        'Operation': {
            "VideoTag": {
                "Scenario": "Stream"
            },
        },
    }
    response = client.ci_create_media_jobs(
        Bucket=bucket_name,
        Jobs=body,
        Lst={},
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_media_segment_jobs():
    # 创建转封装任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'Segment',
        'Operation': {
            "Segment": {
                "Format": "mp4",
                "Duration": "5",
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'segment-${Number}.mp4'
            },
        },
    }
    response = client.ci_create_media_jobs(
        Bucket=bucket_name,
        Jobs=body,
        Lst={},
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_multi_jobs():
    # 创建多任务
    body = {
        'Input': {
            'Object': '117374C.mp4'
        },
        'Operation': [
            {
                'Tag': 'Segment',
                "Segment": {
                    "Format": "mp4",
                    "Duration": "50",
                },
                'Output': {
                    'Bucket': bucket_name,
                    'Region': region,
                    'Object': 'multi-segment-${Number}.mp4'
                },
            },
            {
                'Tag': 'SDRtoHDR',
                "SDRtoHDR": {
                    "HdrMode": "HLG",
                },
                'Output': {
                    'Bucket': bucket_name,
                    'Region': region,
                    'Object': 'multi-sdr2hdr.mp4'
                },
                'TranscodeTemplateId': 't04e1ab86554984f1aa17c062fbf6c007c'
            }
        ],
    }
    lst = ['<Operation>', '</Operation>']
    response = client.ci_create_media_jobs(
        Bucket=bucket_name,
        Jobs=body,
        Lst=lst,
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_get_media_info_jobs():
    # 创建获取媒体信息任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'MediaInfo',
    }
    response = client.ci_create_media_jobs(
        Bucket=bucket_name,
        Jobs=body,
        Lst={},
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_media_pic_jobs():
    # 创建图片处理任务
    body = {
        'Input': {
            'Object': '1.png'
        },
        'Tag': 'PicProcess',
        'Operation': {
            "PicProcess": {
                "IsPicInfo": "true",
                "ProcessRule": "imageMogr2/rotate/90",
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'pic-process-result.png'
            },
        }
    }
    response = client.ci_create_media_pic_jobs(
        Bucket=bucket_name,
        Jobs=body,
        Lst={},
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_list_media_transcode_jobs():
    # 转码任务列表
    response = client.ci_list_media_jobs(
                    Bucket=bucket_name,
                    Tag='DigitalWatermark',
                    ContentType='application/xml',
                    StartCreationTime='2022-05-27T00:00:00+0800',
                    EndCreationTime='2022-05-31T00:00:00+0800',
                    States='Success'
                )
    print(response)
    return response


def ci_get_media_jobs():
    # 查询任务详情
    response = client.ci_get_media_jobs(
                    Bucket=bucket_name,
                    JobIDs='jc46435e40bcc11ed83d6e19dd89b02cc',
                    ContentType='application/xml'
                )
    print(response)
    return response


def ci_list_media_pic_jobs():
    # 图片处理任务列表
    response = client.ci_list_media_pic_jobs(
        Bucket=bucket_name,
        Tag='PicProcess',
        ContentType='application/xml',
        StartCreationTime='2022-05-30T23:30:00+0800',
        EndCreationTime='2022-05-31T01:00:00+0800',
        States='Success'
    )
    print(response)
    return response


def ci_get_media_pic_jobs():
    # 图片处理任务详情
    response = client.ci_get_media_pic_jobs(
        Bucket=bucket_name,
        JobIDs='c01742xxxxxxxxxxxxxxxxxx7438e39',
        ContentType='application/xml'
    )
    print(response)
    return response


def get_media_info():
    # 获取媒体信息
    response = client.get_media_info(
        Bucket=bucket_name,
        Key='demo.mp4'
    )
    print(response)


def get_snapshot():
    # 产生同步截图
    response = client.get_snapshot(
        Bucket=bucket_name,
        Key='demo.mp4',
        Time='1.5',
        Width='480',
        Format='png'
    )
    print(response)
    response['Body'].get_stream_to_file('snapshot.jpg')


def get_pm3u8():
    # 获取私有 M3U8 ts 资源的下载授权
    response = client.get_pm3u8(
        Bucket=bucket_name,
        Key='demo.m3u8',
        Expires='3600',
    )
    print(response)
    response['Body'].get_stream_to_file('pm3u8.m3u8')


def ci_trigger_workflow():
    # 触发工作流接口
    response = client.ci_trigger_workflow(
                    Bucket=bucket_name,
                    WorkflowId='w1b4ffd6900a343c3a2fe5b92b1fb7ff6',
                    Key='test.mp4'
                )
    print(response)
    return response


def ci_get_workflowexecution():
    # 查询工作流实例接口
    response = client.ci_get_workflowexecution(
                    Bucket=bucket_name,
                    RunId='id1f94868688111eca793525400ca1839'
                )
    print(response)
    return response


def ci_list_workflowexecution():
    # 查询工作流实例接口
    response = client.ci_list_workflowexecution(
                    Bucket=bucket_name,
                    WorkflowId='w1b4ffd6900a343c3a2fe5b92b1fb7ff6'
                )
    print(response)
    return response


def ci_create_quality_estimate_jobs():
    # 创建视频质量评分任务
    body = {
        'Input': {
            'Object': 'gaobai.mp4'
        },
        'Tag': 'QualityEstimate',
        'Operation': {
            # 非必选
            "UserData": "This is my data",
        },
        # 非必选
        'CallBack': 'http://callback.demo.com',
        # 非必选
        'CallBackFormat': 'JSON'
    }
    response = client.ci_create_media_jobs(
        Bucket=bucket_name,
        Jobs=body,
        Lst={},
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_segment_video_body_jobs():
    # 创建视频人像抠图任务
    body = {
        # 待操作的对象信息
        'Input': {
            # 输入文件路径
            'Object': 'gaobai.mp4'
        },
        # 任务类型，固定值 SegmentVideoBody
        'Tag': 'SegmentVideoBody',
        # 操作规则
        'Operation': {
            # 视频人像抠图配置
            'SegmentVideoBody': {
                # 抠图模式 当前只支持
                # Mask (输出alpha通道结果) 、
                # Foreground（输出前景视频）、
                # Combination（输出抠图后的前景与自定义背景合成后的视频）
                'Mode': 'Mask',
                # 非必选 抠图模式，当前支持 HumanSeg（人像抠图）、GreenScreenSeg（绿幕抠图）、SolidColorSeg（纯色背景抠图）。 默认值 HumanSeg
                # 'SegmentType': 'GreenScreenSeg',
                # 非必选 mode为Foreground时可指定此参数，背景颜色为蓝色，取值范围为0-255, 默认值为0
                # 'BackgroundBlue': '255',
                # 非必选 mode为Foreground时可指定此参数，背景颜色为红色，取值范围为0-255, 默认值为0
                # 'BackgroundRed': '255',
                # 非必选 mode为Foreground时可指定此参数，背景颜色为绿色，取值范围为0-255, 默认值为0
                # 'BackgroundGreen': '255',
                # 非必选 mode为Combination时，必需指定此参数，传入背景文件，背景文件需与object在同存储桶下
                # 'BackgroundLogoUrl': 'http://testpic-1253960454.cos.ap-chongqing.myqcloud.com'
                # 非必选 阈值 可以调整alpha通道的边缘，调整抠图的边缘位置 取值范围为0-255, 默认值为0
                # 'BinaryThreshold': '200',
                # 非必选 纯色背景抠图的背景色（红）, 当 SegmentType 为 SolidColorSeg 生效，取值范围为0-255，默认值为 0
                # 'RemoveRed': '200',
                # 非必选 纯色背景抠图的背景色（绿）, 当 SegmentType 为 SolidColorSeg 生效，取值范围为0-255，默认值为 0
                # 'RemoveGreen': '200',
                # 非必选 纯色背景抠图的背景色（蓝）, 当 SegmentType 为 SolidColorSeg 生效，取值范围为0-255，默认值为 0
                # 'RemoveBlue': '200'
            },
            # 输出配置
            'Output': {
                # 输出桶信息
                'Bucket': bucket_name,
                # 输出地域信息
                'Region': region,
                # 输出文件路径信息
                'Object': 'result.mp4'
            },
            # 非必选
            "UserData": "This is my data",
        },
        # 非必选 回调URL
        # 'CallBack': 'http://callback.demo.com',
        # 非必选 回调信息格式 支持JSON/XML
        # 'CallBackFormat': 'JSON'
    }
    response = client.ci_create_media_jobs(
        Bucket=bucket_name,
        Jobs=body,
        Lst={},
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_and_get_live_recognition_jobs():
    # 创建直播流识别任务
    body = {
        # 待操作的直播流信息
        'Input': {
            # 直播流拉流地址
            'Url': 'http://demo.liveplay.com/demo.m3u8',
            # 输入类型，直播流固定为LiveStream
            'SourceType': 'LiveStream'
        },
        # 任务类型，固定值 VideoTargetRec
        'Tag': 'VideoTargetRec',
        # 操作规则
        'Operation': {
            # 识别配置
            'VideoTargetRec': {
                # 直播流识别任务必选且值设置为true
                'CarPlate': 'true',
                # 截图时间间隔，单位为秒，非必选，默认为1，取值范围：[1, 300]
                'SnapshotTimeInterval': '1',
            },
            # 输出配置，直播流转存至cos的配置信息，转存为hls格式，ts分片时长为3s
            'Output': {
                # 输出桶信息
                'Bucket': bucket_name,
                # 输出地域信息
                'Region': region,
                # 输出文件路径信息
                'Object': 'result.m3u8'
            },
            # 非必选
            "UserData": "This is my data",
        },
        # 非必选 回调URL
        'CallBack': 'https://www.callback.com',
        # 非必选 回调信息格式 支持JSON/XML
        # 'CallBackFormat': 'JSON'
    }
    response = client.ci_create_media_jobs(
        Bucket=bucket_name,
        Jobs=body,
        Lst={},
        ContentType='application/xml'
    )
    print(response)
    print("create job success")
    job_id = response['JobsDetail'][0]['JobId']
    while True:
        time.sleep(5)
        response = client.ci_get_media_jobs(
            Bucket=bucket_name,
            JobIDs=job_id,
            ContentType='application/xml'
        )
        if 'VideoTargetRecResult' in response['JobsDetail'][0]["Operation"]:
            if 'CarPlateRecognition' in response['JobsDetail'][0]["Operation"][
                "VideoTargetRecResult"] and response['JobsDetail'][0]["Operation"]["VideoTargetRecResult"][
                "CarPlateRecognition"] is not None \
                and \
                response['JobsDetail'][0]["Operation"]["VideoTargetRecResult"][
                    "CarPlateRecognition"]['CarPlateInfo'] is not None:
                print("result:" + str(response['JobsDetail'][0]["Operation"]["VideoTargetRecResult"]["CarPlateRecognition"]))
            else:
                print("don't have result: " + str(response['JobsDetail'][0]["Operation"]["VideoTargetRecResult"]))
        state = response['JobsDetail'][0]['State']
        if state == 'Success' or state == 'Failed' or state == 'Cancel':
            print(response)
            break


def ci_cancel_jobs():
    # 转码任务详情
    response = client.ci_cancel_jobs(
        Bucket=bucket_name,
        JobID='a65xxxxxxxxxxxxxxxx1f213dcd0151',
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_workflow_image_inspect():
    # 创建异常图片检测工作流

    # 工作流配置详情
    body = {
        # 工作流节点 固定值传入即可
        'MediaWorkflow': {
            # 创建的工作流名称，可自定义输入名称
            # 支持中文、英文、数字、—和_，长度限制128字符
            # 必传参数
            'Name': 'image-inspect',
            # 工作流状态，表示创建时是否开启COS上传对象事件通知
            # 支持 Active / Paused
            # 非必选，默认Paused 不开启
            'State': 'Active',
            # 工作流拓扑结构
            # 必传参数
            'Topology': {
                # 工作流节点依赖关系
                # 必传参数
                'Dependencies': {
                    # Start 工作流开始节点，用于存储工作流回调，前缀，后缀等配置信息，只有一个开始节点
                    # End 工作流结束节点
                    # ImageInspectNode 异常图片检测节点信息
                    # 此示例表示 Start -> ImageInspectNode -> End 的依赖关系
                    'Start': 'ImageInspectNode',
                    'ImageInspectNode': 'End',
                },
                # 工作流各节点的详细配置信息
                # 必传参数
                'Nodes': {
                    # 工作流开始节点配置信息
                    'Start': {
                        # 节点类型，开始节点固定为 Start
                        # 必传参数
                        'Type': 'Start',
                        # 工作流的输入信息
                        # 必传参数
                        'Input': {
                            # Object 前缀，COS上传对象的前缀，只有当前缀匹配时，才会触发该工作流
                            # 如该示例，会触发以test为前缀的对象
                            # 必传参数
                            'ObjectPrefix': 'test',
                            # 工作流自定义回调配置信息，当配置了该项后，当工作流执行完成或工作流中的子节点中的任务执行完成，会发送回调给指定Url或tdmq
                            # 非必传配置
                            'NotifyConfig': {
                                # 回调类型，支持Url TDMQ两种类型
                                'Type': 'Url',
                                # 回调地址，当回调类型为Url时有效
                                'Url': 'http://www.callback.com',
                                # 回调事件 支持多种事件，以逗号分割
                                'Event': 'WorkflowFinish,TaskFinish',
                                # 回调信息格式，支持XML JSON两种格式，非必传，默认为XML
                                'ResultFormat': '',
                                # TDMQ 所属园区，当回调类型为TDMQ时有效，支持园区详见https://cloud.tencent.com/document/product/406/12667
                                'MqRegion': '',
                                # TDMQ 使用模式，当回调类型为TDMQ时有效
                                # Topic：主题订阅
                                # Queue：队列服务
                                'MqMode': '',
                                # TDMQ 主题名称，当回调类型为TDMQ时有效
                                'MqName': '',
                            },
                            # 文件后缀过滤器，当需要只处理部分后缀文件时，可配置此项
                            # 非必传配置
                            'ExtFilter': {
                                # 是否开始后缀过滤，On/Off，非必选，默认为Off
                                'State': '',
                                # 打开视频后缀限制，false/true，非必选，默认为false
                                'Video': '',
                                # 打开音频后缀限制，false/true，非必选，默认为false
                                'Audio': '',
                                # 打开图片后缀限制，false/true，非必选，默认为false
                                'Image': '',
                                # 打开 ContentType 限制，false/true，非必选，默认为false
                                'ContentType': '',
                                # 打开自定义后缀限制，false/true，非必选，默认为false
                                'Custom': '',
                                # 自定义后缀，当Custom为true时有效，多种文件后缀以/分隔，后缀个数不超过10个
                                'CustomExts': 'jpg/png',
                                # 所有文件，false/true，非必选，默认为false
                                'AllFile': '',
                            }
                        }
                    },
                    # 异常图片检测节点配置信息
                    'ImageInspectNode': {
                        # 节点类型，异常图片检测固定为ImageInspect
                        'Type': 'ImageInspect',
                        # 节点执行操作集合
                        # 非必选配置
                        'Operation': {
                            # 异常图片检测配置详情
                            'ImageInspect': {
                                # 是否开启检测到异常图片检测后自动对图片进行处理的动作，false/true，非必选，默认false
                                'AutoProcess': 'true',
                                # 在检测到为异常图片后的处理动作，有效值为：
                                # BackupObject：移动图片到固定目录下，目录名为abnormal_images_backup/，由后台自动创建
                                # SwitchObjectToPrivate：将图片权限设置为私有
                                # DeleteObject：删除图片
                                # 非必选参数，默认值为BackupObject
                                'ProcessType': 'BackupObject'
                            }
                        }
                    },
                },
            },
        },
    }
    response = client.ci_create_workflow(
        Bucket=bucket_name,  # 桶名称
        Body=body,  # 工作流配置信息
        ContentType='application/xml'
    )
    print(response)
    print("workflowId is: " + response['MediaWorkflow']['WorkflowId'])
    return response


def ci_update_workflow():
    # 更新工作流配置信息，仅当工作流状态为Paused时支持更新配置信息，故在更新信息前，需要将工作流状态为Paused

    # 工作流配置详情
    body = {
        # 工作流节点 固定值传入即可
        'MediaWorkflow': {
            # 工作流名称，可自定义输入名称
            # 支持中文、英文、数字、—和_，长度限制128字符
            # 必传参数
            'Name': 'image-inspect',
            # 工作流状态，表示创建时是否开启COS上传对象事件通知
            # 支持 Active / Paused
            # 非必选，默认Paused 不开启
            'State': 'Active',
            # 工作流拓扑结构
            # 必传参数
            'Topology': {
                # 工作流节点依赖关系
                # 必传参数
                'Dependencies': {
                    # Start 工作流开始节点，用于存储工作流回调，前缀，后缀等配置信息，只有一个开始节点
                    # End 工作流结束节点
                    # ImageInspectNode 异常图片检测节点信息
                    # 此示例表示 Start -> ImageInspectNode -> End 的依赖关系
                    'Start': 'ImageInspectNode',
                    'ImageInspectNode': 'End',
                },
                # 工作流各节点的详细配置信息
                # 必传参数
                'Nodes': {
                    # 工作流开始节点配置信息
                    'Start': {
                        # 节点类型，开始节点固定为 Start
                        # 必传参数
                        'Type': 'Start',
                        # 工作流的输入信息
                        # 必传参数
                        'Input': {
                            # Object 前缀，COS上传对象的前缀，只有当前缀匹配时，才会触发该工作流
                            # 如该示例，会触发以test为前缀的对象
                            # 必传参数
                            'ObjectPrefix': 'test',
                            # 工作流自定义回调配置信息，当配置了该项后，当工作流执行完成或工作流中的子节点中的任务执行完成，会发送回调给指定Url或tdmq
                            # 非必传配置
                            'NotifyConfig': {
                                # 回调类型，支持Url TDMQ两种类型
                                'Type': 'Url',
                                # 回调地址，当回调类型为Url时有效
                                'Url': 'http://www.callback.com',
                                # 回调事件 支持多种事件，以逗号分割
                                'Event': 'WorkflowFinish,TaskFinish',
                                # 回调信息格式，支持XML JSON两种格式，非必传，默认为XML
                                'ResultFormat': '',
                                # TDMQ 所属园区，当回调类型为TDMQ时有效，支持园区详见https://cloud.tencent.com/document/product/406/12667
                                'MqRegion': '',
                                # TDMQ 使用模式，当回调类型为TDMQ时有效
                                # Topic：主题订阅
                                # Queue：队列服务
                                'MqMode': '',
                                # TDMQ 主题名称，当回调类型为TDMQ时有效
                                'MqName': '',
                            },
                            # 文件后缀过滤器，当需要只处理部分后缀文件时，可配置此项
                            # 非必传配置
                            'ExtFilter': {
                                # 是否开始后缀过滤，On/Off，非必选，默认为Off
                                'State': 'On',
                                # 打开视频后缀限制，false/true，非必选，默认为false
                                'Video': '',
                                # 打开音频后缀限制，false/true，非必选，默认为false
                                'Audio': '',
                                # 打开图片后缀限制，false/true，非必选，默认为false
                                'Image': 'true',
                                # 打开 ContentType 限制，false/true，非必选，默认为false
                                'ContentType': '',
                                # 打开自定义后缀限制，false/true，非必选，默认为false
                                'Custom': '',
                                # 自定义后缀，当Custom为true时有效，多种文件后缀以/分隔，后缀个数不超过10个
                                'CustomExts': 'jpg/png',
                                # 所有文件，false/true，非必选，默认为false
                                'AllFile': '',
                            }
                        }
                    },
                    # 异常图片检测节点配置信息
                    'ImageInspectNode': {
                        # 节点类型，异常图片检测固定为ImageInspect
                        'Type': 'ImageInspect',
                        # 节点执行操作集合
                        # 非必选配置
                        'Operation': {
                            # 异常图片检测配置详情
                            'ImageInspect': {
                                # 是否开启检测到异常图片检测后自动对图片进行处理的动作，false/true，非必选，默认false
                                'AutoProcess': 'true',
                                # 在检测到为异常图片后的处理动作，有效值为：
                                # BackupObject：移动图片到固定目录下，目录名为abnormal_images_backup/，由后台自动创建
                                # SwitchObjectToPrivate：将图片权限设置为私有
                                # DeleteObject：删除图片
                                # 非必选参数，默认值为BackupObject
                                'ProcessType': 'SwitchObjectToPrivate'
                            }
                        }
                    },
                },
            },
        },
    }
    response = client.ci_update_workflow(
        Bucket=bucket_name,  # 桶名称
        WorkflowId='wd34ca394909xxxxxxxxxxxx4d',  # 需要更新的工作流ID
        Body=body,  # 工作流配置详情
        ContentType='application/xml'
    )
    print(response)
    print("workflowId is: " + response['MediaWorkflow']['WorkflowId'])
    return response


def ci_update_workflow_state():
    # 更新工作流状态

    response = client.ci_update_workflow_state(
        Bucket=bucket_name,  # 桶名称
        WorkflowId='wd34ca3949090xxxxxxxxxx44d',  # 需要更新的工作流ID
        UpdateState='paused',  # 需要更新至的工作流状态，支持 active 开启 / paused 关闭
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_get_workflow():
    # 获取工作流配置详情

    response = client.ci_get_workflow(
        Bucket=bucket_name,  # 桶名称
        Ids='wd34ca394909xxxxxxxxxxxx4d',  # 需要查询的工作流ID，支持传入多个，以","分隔
        Name='image-inspect',  # 需要查询的工作流名称
        # PageNumber='6',  # 分页查询使用，第几页
        # PageSize='3', # 分页查询使用，每页个数
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_delete_workflow():
    # 删除指定的工作流

    response = client.ci_delete_workflow(
        Bucket=bucket_name,  # 桶名称
        WorkflowId='wd34ca39490904xxxxxxxxxx744d',  # 需要删除的工作流ID
    )
    print(response)
    return response


def ci_create_image_inspect_jobs():
    # 创建异常图片检测任务

    body = {
        # 待操作的对象信息
        'Input': {
            # 输入文件路径
            'Object': 'heichan.png'
        },
        # 任务类型，固定值 ImageInspect
        'Tag': 'ImageInspect',
        # 操作规则
        # 非必选
        'Operation': {
            # 异常图片检测配置
            # 非必选
            'ImageInspect': {
                # 是否开启检测到异常图片检测后自动对图片进行处理的动作，false/true，非必选，默认false
                'AutoProcess': 'true',
                # 在检测到为异常图片后的处理动作，有效值为：
                # BackupObject：移动图片到固定目录下，目录名为abnormal_images_backup/，由后台自动创建
                # SwitchObjectToPrivate：将图片权限设置为私有
                # DeleteObject：删除图片
                # 非必选参数，默认值为BackupObject
                'ProcessType': 'SwitchObjectToPrivate'
            },
            # 非必选
            "UserData": "This is my data",
        },
        # 非必选 回调URL
        # 'CallBack': 'http://callback.demo.com',
        # 非必选 回调信息格式 支持JSON/XML
        # 'CallBackFormat': 'JSON'
    }
    response = client.ci_create_media_jobs(
        Bucket=bucket_name,
        Jobs=body,
        Lst={},
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_image_inspect_batch_jobs():
    # 创建异常图片检测批量处理任务
    body = {
        # 批量任务名称
        # 存量触发任务名称，支持中文、英文、数字、—和_，长度限制128字符
        # 必选
        'Name': 'image-inspect-auto-move-batch-process',
        # 批量处理任务类型：
        # 支持 Job（独立异步任务） Workflow（工作流）
        'Type': 'Job',
        # 待操作的对象信息
        # 必传参数
        'Input': {
            # 'UrlFile': 'https://ziroom-tech-1255976291.cos.ap-beijing.myqcloud.com/ci_ziroom-tech_scankey_url.txt',
            # Object 前缀
            'Prefix': '/',
        },
        # 操作规则
        # 必传参数
        'Operation': {
            # 按对象的last modify时间过滤的触发范围，若传入此参数，则当前任务仅处理指定事件范围内的对象
            # 非必传
            # 创建的任务类型，此处固定值为ImageInspect
            # 必传参数
            'Tag': 'ImageInspect',
            # 任务参数集合
            # 必传参数
            'JobParam': {
                # 异常图片检测配置
                # 非必选
                'ImageInspect': {
                    # 是否开启检测到异常图片检测后自动对图片进行处理的动作，false/true，非必选，默认false
                    'AutoProcess': 'true',
                    # 在检测到为异常图片后的处理动作，有效值为：
                    # BackupObject：移动图片到固定目录下，目录名为abnormal_images_backup/，由后台自动创建
                    # SwitchObjectToPrivate：将图片权限设置为私有
                    # DeleteObject：删除图片
                    # 非必选参数，默认值为BackupObject
                    'ProcessType': 'BackupObject'
                },
            },

        },

    }
    response = client.ci_create_inventory_trigger_jobs(
        Bucket=bucket_name,
        JobBody=body,
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_image_inspect_workflow_batch_jobs():
    # 创建异常图片检测工作流批量处理任务

    body = {
        # 批量任务名称
        # 存量触发任务名称，支持中文、英文、数字、—和_，长度限制128字符
        # 必选
        'Name': 'image-inspect-auto-move-batch-process',
        # 批量处理任务类型：
        # 支持 Job（独立异步任务） Workflow（工作流）
        'Type': 'Workflow',
        # 待操作的对象信息
        # 必传参数
        'Input': {
            # 'UrlFile': 'https://ziroom-tech-1255976291.cos.ap-beijing.myqcloud.com/ci_ziroom-tech_scankey_url.txt',
            # Object 前缀
            'Prefix': '/',
        },
        # 操作规则
        # 必传参数
        'Operation': {
            # 按对象的last modify时间过滤的触发范围，若传入此参数，则当前任务仅处理指定事件范围内的对象
            # 非必传
            'TimeInterval': {
                'Start': '2023-05-01T00:00:00+0800',
                'End': '2023-06-01T00:00:00+0800'
            },
            # 创建的任务类型，此处固定值为ImageInspect
            # 必传参数
            'WorkflowIds': 'w2504f47ad46exxxxxxxxxxxxxx',
        },

    }
    response = client.ci_create_inventory_trigger_jobs(
        Bucket=bucket_name,
        JobBody=body,
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_list_inventory_trigger_jobs():
    # 查询批量处理任务列表
    response = client.ci_list_inventory_trigger_jobs(
        Bucket=bucket_name,  # 桶名称
    )
    print(response)
    return response


def ci_get_inventory_trigger_jobs():
    # 查询指定批量处理任务
    response = client.ci_get_inventory_trigger_jobs(
        Bucket=bucket_name,  # 桶名称
        JobID='bb16331089f7c11ecb10252540019ee59',
    )
    print(response)
    return response


def ci_delete_inventory_trigger_jobs():
    # 删除指定的批量处理任务
    response = client.ci_delete_inventory_trigger_jobs(
        Bucket=bucket_name,  # 桶名称
        JobId='b97c37f492adf11xxxxxxxxxxxx',  # 需要删除的工作流ID
    )
    print(response)
    return response


def ci_create_sound_hound_jobs():
    # 创建听歌识曲任务
    
    body = {
        # 待操作的对象信息
        'Input': {
            # 输入文件路径
            'Object': '1.mp3'
        },
        # 任务类型，固定值 SoundHound
        'Tag': 'SoundHound',
        # 操作规则
        # 非必选
        'Operation': {
            # 非必选 透传用户信息, 可打印的 ASCII 码, 长度不超过1024
            "UserData": "This is my data",
        },
        # 非必选 回调URL
        # 'CallBack': 'http://callback.demo.com',
        # 非必选 回调信息格式 支持JSON/XML
        # 'CallBackFormat': 'JSON'
        # 非必选 任务回调类型，Url 或 TDMQ，默认 Url，优先级高于队列的回调类型
        # 'CallBackType': 'Url',
        # 任务回调TDMQ配置，当 CallBackType 为 TDMQ 时必填
        # 'CallBackMqConfig': {
        #     # TDMQ回调信息配置
        #     
        #     # 消息队列所属园区
        #     # 必选。目前支持园区 sh（上海）、bj（北京）、gz（广州）、cd（成都）、hk（中国香港）
        #     'MqRegion': 'bj',
        #     # 消息队列使用模式
        #     # 必选。主题订阅：Topic 队列服务: Queue
        #     'MqMode': 'Queue',
        #     # TDMQ 主题名称 必选。
        #     'MqName': 'queueName'
        # },
    }
    response = client.ci_create_media_jobs(
        Bucket=bucket_name,
        Jobs=body,
        ContentType='application/xml'
    )
    print(response)
    return response


def ci_create_noise_reduction_jobs():
    # 创建音频降噪任务
    body = {
        'Input': {
            'Object': 'demo.mp3'
        },
        'Tag': 'NoiseReduction',
        'Operation': {
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'noise_reduction_result.mp3',
            },
            # 'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5'
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


def ci_create_stream_extract_jobs():
    # 创建流分离任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'Tag': 'StreamExtract',
        'Operation': {
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'StreamExtract': [
                    {
                        'Index': '0',
                        'Object': 'stream-1.mp4'
                    },
                    {
                        'Index': '1',
                        'Object': 'stream-2.mp4'
                    }
                ]
            },
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


def ci_create_tts_jobs():
    # 创建语音合成任务
    body = {
        'Tag': 'Tts',
        'Input': {
            'Object': 'demo.mp4'
        },
        'Operation': {
            'TtsTpl': {
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
            },
            'TemplateId': '',
            'TtsConfig': {
                'InputType': 'Text',
                'Input': '床前明月光，疑是地上霜',
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'result.mp3'
            },
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


def ci_create_translation_jobs():
    # 创建翻译任务
    body = {
        'Tag': 'Translation',
        'Input': {
            'Object': 'demo.txt',
            'Lang': 'en',
            'Type': 'txt',
            #   'BasicType': ''
        },
        'Operation': {
            'Translation': {
                'Lang': 'zh',
                'Type': 'txt',
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'result.txt'
            },
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


def ci_create_words_generalize_jobs():
    # 创建分词任务
    body = {
        'Tag': 'WordsGeneralize',
        'Input': {
            'Object': 'demo.txt',
        },
        'Operation': {
            'WordsGeneralize': {
                'NerMethod': 'DL',
                'SegMethod': 'MIX',
            },
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


def ci_get_presigned_download_url():
    param = {
        # 想要处理的文件路径
        # 支持cos对象的绝对路径
        # 必选参数
        "object": "test1026.gif",
        # 转码后的视频流格式
        # 当前仅支持mp4
        # 必选参数
        "format": "mp4",
        # 转码后视频的宽
        # 取值范围：(0,4096]。默认为0
        # 非必传参数
        # "width": "200",
        # 转码后视频的高
        # 取值范围：(0,4096]。默认为0
        # 非必传参数
        # 当 width 和 height 都为0时，表示使用视频的宽高。如果单个为0，则以另外一个值按视频宽高比例自动适应
        # "heigth": "200"
    }
    url = client.get_presigned_download_url(
        Bucket=bucket_name,  # 存储桶名称
        Key="/convert",  # 请求uri 同步转码固定为/convert
        Expired=3600,    # 预签名超时时间
        Params=param,    # 请求处理参数
        UseCiEndPoint=True,  # 是否使用数据万象的请求域名
    )
    if token is not None:
        url = url + "&x-cos-security-token=" + token
    print(url)


if __name__ == "__main__":
    # ci_get_media_queue()
    # ci_get_media_jobs()
    # ci_create_media_transcode_jobs()
    # get_media_info()
    # get_snapshot()
    # ci_trigger_workflow()
    # ci_list_workflowexecution()
    # ci_get_workflowexecution()
    # ci_get_media_bucket()
    # get_pm3u8()
    # ci_create_media_snapshot_jobs()
    # ci_create_media_animation_jobs()
    # ci_create_media_smart_cover_jobs()
    # ci_create_media_video_process_jobs()
    # ci_create_media_video_montage_jobs()
    # ci_create_media_voice_separate_jobs()
    # ci_create_media_sdr2hdr_jobs()
    # ci_create_media_super_resolution_jobs()
    # ci_create_media_concat_jobs()
    # ci_create_media_digital_watermark_jobs()
    # ci_create_media_extract_digital_watermark_jobs()
    # ci_create_media_video_tag_jobs()
    # ci_create_media_segment_jobs()
    # ci_create_multi_jobs()
    # ci_create_media_pic_jobs()
    # ci_get_media_pic_jobs()
    # ci_create_get_media_info_jobs()
    # ci_put_media_queue()
    # ci_create_media_transcode_with_watermark_jobs()
    # ci_create_media_transcode_with_digital_watermark_jobs()
    # ci_create_media_hls_transcode_jobs()
    # ci_list_media_transcode_jobs()
    # ci_list_media_pic_jobs()
    # ci_get_media_pic_queue()
    # ci_put_media_pic_queue()
    # ci_create_quality_estimate_jobs()
    # ci_create_segment_video_body_jobs()
    # ci_create_and_get_live_recognition_jobs()
    # ci_cancel_jobs()
    # ci_create_workflow_image_inspect()
    # ci_get_workflow()
    # ci_update_workflow()
    # ci_update_workflow_state()
    # ci_delete_workflow()
    # ci_create_image_inspect_jobs()
    # ci_create_sound_hound_jobs()
    # ci_list_inventory_trigger_jobs()
    # ci_get_pic_bucket()
    # ci_get_inventory_trigger_jobs()
    # ci_get_ai_bucket()
    # ci_get_ai_queue()
    # ci_put_ai_queue()
    # ci_create_noise_reduction_jobs()
    # ci_create_stream_extract_jobs()
    # ci_create_tts_jobs()
    # ci_create_translation_jobs()
    # ci_create_words_generalize_jobs()
    ci_get_presigned_download_url()
