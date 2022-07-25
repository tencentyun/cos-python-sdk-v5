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
secret_id = os.environ["SECRETID"] # 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_key = os.environ["SECRETKEY"] # 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
region = 'ap-chongqing' # 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
# COS支持的所有region列表参见https://www.qcloud.com/document/product/436/6224
token = None # 如果使用永久密钥不需要填入token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见https://cloud.tencent.com/document/product/436/14048

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme='https') # 获取配置对象
client = CosS3Client(config)


bucket_name = 'demo-1253960454'


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
            'ResultFormat': 'JSON'
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
        'QueueId': 'p5135bcxxxxxxxxxxxxxxxx047454',
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
        'QueueId': 'p5135bc6xxxxxxxxxxxxxxxxxxbf047454',
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
                        'Url': 'http://'+bucket_name+".cos."+region+".myqcloud.com/watermark.png",
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
        'QueueId': 'p5135xxxxxxxxxxxxxxxxxxxxx047454',
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
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxx8bf047454',
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
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
    # 创建拼接任务
    body = {
        'Input': {
            'Object': 'demo.mp4'
        },
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
        'Tag': 'Concat',
        'Operation': {
            "ConcatTemplate": {
                "ConcatFragment": [
                    {
                        "Url": "http://demo-1xxxxxxxxx.cos.ap-chongqing.myqcloud.com/1.mp4"
                    },
                    {
                        "Url": "http://demo-1xxxxxxxxx.cos.ap-chongqing.myqcloud.com/2.mp4"
                    }
                ],
                "Audio": {
                    "Codec": "mp3"
                },
                "Video": {
                    "Codec": "H.264",
                    "Bitrate": "1000",
                    "Width": "1280",
                    "Fps": "30"
                },
                "Container": {
                    "Format": "mp4"
                }
            },
            'Output': {
                'Bucket': bucket_name,
                'Region': region,
                'Object': 'concat-result.mp4'
            },
            # 'TemplateId': 't02db40900dc1c43ad9bdbd8acec6075c5'
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
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
        'Input':{
            'Object': 'demo.mp4'
        },
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
        'Input':{
            'Object': 'demo.mp4'
        },
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
        'QueueId': 'p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
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
        'QueueId': 'peb83bdbxxxxxxxxxxxxxxxxxxxa21c7d68',
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
                    QueueId='p5135bxxxxxxxxxxxxxxxxxxxc8bf047454',
                    Tag='DigitalWatermark',
                    ContentType='application/xml',
                    StartCreationTime='2022-05-27T00:00:00+0800',
                    EndCreationTime='2022-05-31T00:00:00+0800',
                    States='Success'
                )
    print(response)
    return response


def ci_get_media_transcode_jobs():
    # 转码任务详情
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
        QueueId='peb83bdbxxxxxxxxxxxxxxxxxxxa21c7d68',
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
    response = client.ci_get_media_jobs(
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
                    Key='117374C.mp4'
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
        'QueueId': 'peb83bdbxxxxxxxxxxxxxxxxxxxa21c7d68',
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


if __name__ == "__main__":
    # ci_get_media_queue()
    # ci_get_media_transcode_jobs()
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
    ci_create_quality_estimate_jobs()
