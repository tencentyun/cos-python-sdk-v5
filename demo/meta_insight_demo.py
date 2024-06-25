# -*- coding=utf-8

from qcloud_cos import CosConfig
from qcloud_cos import MetaInsightClient

import os
import sys
import logging

# 腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# 设置用户属性, 包括 secret_id, secret_key, region等。Appid 已在CosConfig中移除，请在参数 Bucket 中带上 Appid。Bucket 由 BucketName-Appid 组成
# 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_id = os.environ["SECRETID"]
# 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_key = os.environ["SECRETKEY"]
# 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
region = 'ap-chongqing'
# COS支持的所有region列表参见https://www.qcloud.com/document/product/436/6224
token = None  # 如果使用永久密钥不需要填入token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见https://cloud.tencent.com/document/product/436/14048

appid = '1250000000'

config = CosConfig(Appid=appid, Region=region, SecretId=secret_id,
                   SecretKey=secret_key,
                   Token=token)  # 获取配置对象
client = MetaInsightClient(config)

bucket_name = 'examplebucket-1250000000'


def ci_create_dataset():
    # 创建数据集
    body = {
        # 数据集名称，同一个账户下唯一。命名规则如下： 长度为1~32字符。 只能包含小写英文字母，数字，短划线（-）。 必须以英文字母和数字开头。
        # 是否必传：是
        'DatasetName': "test",
        # 数据集描述信息。长度为1~256个英文或中文字符，默认值为空。
        # 是否必传：否
        'Description': "test",
        #  与数据集关联的检索模板，在建立元数据索引时，后端将根据检索模板来决定采集文件的哪些元数据。每个检索模板都包含若干个算子，不同的算子表示不同的处理能力，更多信息请参见 [检索模板与算子](https://cloud.tencent.com/document/product/460/106018)。 默认值为空，即不关联检索模板，不进行任何元数据的采集。
        # 是否必传：否
        'TemplateId': "Official:COSBasicMeta",
    }
    response, data = client.ci_create_dataset(
        Body=body,
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_create_dataset_binding():
    # 绑定存储桶与数据集
    body = {
        # 数据集名称，同一个账户下唯一
        # 是否必传：是
        'DatasetName': "test",
        # 资源标识字段，表示需要与数据集绑定的资源，当前仅支持COS存储桶，字段规则：cos://<BucketName>，其中BucketName表示COS存储桶名称，例如：cos://examplebucket-1250000000
        # 是否必传：是
        'URI': "cos://examplebucket-1250000000",
    }
    response, data = client.ci_create_dataset_binding(
        Body=body,
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_create_file_meta_index():
    # 创建元数据索引
    body = {
        # 数据集名称，同一个账户下唯一。
        # 是否必传：是
        'DatasetName': "test001",
        # 用于建立索引的文件信息。
        # 是否必传：是
        'File': {
            # 自定义ID。该文件索引到数据集后，作为该行元数据的属性存储，用于和您的业务系统进行关联、对应。您可以根据业务需求传入该值，例如将某个URI关联到您系统内的某个ID。推荐传入全局唯一的值。在查询时，该字段支持前缀查询和排序，详情请见[字段和操作符的支持列表](https://cloud.tencent.com/document/product/460/106154)。
            # 是否必传：否
            'CustomId': "001",
            # 自定义标签。您可以根据业务需要自定义添加标签键值对信息，用于在查询时可以据此为筛选项进行检索，详情请见[字段和操作符的支持列表](https://cloud.tencent.com/document/product/460/106154)。
            # 是否必传：否
            'CustomLabels': {"age": "18", "level": "18"},
            # 可选项，文件媒体类型，枚举值： image：图片。  other：其他。 document：文档。 archive：压缩包。 video：视频。  audio：音频。
            # 是否必传：否
            'MediaType': "image",
            # 可选项，文件内容类型（MIME Type），如image/jpeg。
            # 是否必传：否
            'ContentType': "image/jpeg",
            # 资源标识字段，表示需要建立索引的文件地址，当前仅支持COS上的文件，字段规则：cos:///，其中BucketName表示COS存储桶名称，ObjectKey表示文件完整路径，例如：cos://examplebucket-1250000000/test1/img.jpg。 注意： 1、仅支持本账号内的COS文件 2、不支持HTTP开头的地址
            # 是否必传：是
            'URI': "cos://examplebucket-1250000000/test.jpg",
            # 输入图片中检索的人脸数量，默认值为20，最大值为20。(仅当数据集模板 ID 为 Official:FaceSearch 有效)。
            # 是否必传：否
            'MaxFaceNum': 20,
            # 自定义人物属性(仅当数据集模板 ID 为 Official:FaceSearch 有效)。
            # 是否必传：否
            'Persons': [{
                # 自定义人物 ID。
                # 是否必传：否
                'PersonId': "xxxxx",
            }],
        },
    }
    response, data = client.ci_create_file_meta_index(
        Body=body,
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_dataset_face_search():
    # 人脸搜索
    body = {
        # 数据集名称，同一个账户下唯一。
        # 是否必传：是
        'DatasetName': "test",
        # 资源标识字段，表示需要建立索引的文件地址。
        # 是否必传：是
        'URI': "cos://examplebucket-1250000000/test.jpg",
        # 输入图片中检索的人脸数量，默认值为1(传0或不传采用默认值)，最大值为10。
        # 是否必传：否
        'MaxFaceNum': 1,
        # 检索的每张人脸返回相关人脸数量，默认值为10，最大值为100。
        # 是否必传：否
        'Limit': 10,
        # 限制返回人脸的最低相关度分数，只有超过 MatchThreshold 值的人脸才会返回。默认值为0，推荐值为80。 例如：设置 MatchThreshold 的值为80，则检索结果中仅会返回相关度分数大于等于80分的人脸。
        # 是否必传：否
        'MatchThreshold': 10,
    }
    response, data = client.ci_dataset_face_search(
        Body=body,
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_dataset_simple_query():
    # 简单查询
    body = {
        # 数据集名称，同一个账户下唯一。
        # 是否必传：是
        'DatasetName': "test",
        # 简单查询参数条件，可自嵌套。
        # 是否必传：否
        'Query': {
            # 操作运算符。枚举值： not：逻辑非。 or：逻辑或。 and：逻辑与。 lt：小于。 lte：小于等于。 gt：大于。 gte：大于等于。 eq：等于。 exist：存在性查询。 prefix：前缀查询。 match-phrase：字符串匹配查询。 nested：字段为数组时，其中同一对象内逻辑条件查询。
            # 是否必传：是
            'Operation': "and",
            # 子查询的结构体。 只有当Operations为逻辑运算符（and、or、not或nested）时，才能设置子查询条件。 在逻辑运算符为and/or/not时，其SubQueries内描述的所有条件需符合父级设置的and/or/not逻辑关系。 在逻辑运算符为nested时，其父级的Field必须为一个数组类的字段（如：Labels）。 子查询条件SubQueries组的Operation必须为and/or/not中的一个或多个，其Field必须为父级Field的子属性。
            # 是否必传：否
            'SubQueries': [{
                # 查询的字段值。当Operations为逻辑运算符（and、or、not或nested）时，该字段无效。
                # 是否必传：否
                'Value': "image/jpeg",
                #  操作运算符。枚举值：not：逻辑非。or：逻辑或。and：逻辑与。lt：小于。lte：小于等于。gt：大于。gte：大于等于。eq：等于。exist：存在性查询。prefix：前缀查询。match-phrase：字符串匹配查询。nested：字段为数组时，其中同一对象内逻辑条件查询。
                # 是否必传：是
                'Operation': "eq",
                # 字段名称。关于支持的字段，请参考字段和操作符的支持列表。
                # 是否必传：否
                'Field': "ContentType",
            }],
        },
        # 返回文件元数据的最大个数，取值范围为0200。 使用聚合参数时，该值表示返回分组的最大个数，取值范围为02000。 不设置此参数或者设置为0时，则取默认值100。
        # 是否必传：否
        'MaxResults': 100,
        # 排序字段列表。请参考[字段和操作符的支持列表](https://cloud.tencent.com/document/product/460/106154)。 多个排序字段可使用半角逗号（,）分隔，例如：Size,Filename。 最多可设置5个排序字段。 排序字段顺序即为排序优先级顺序。
        # 是否必传：否
        'Sort': "CustomId",
        # 排序字段的排序方式。取值如下： asc：升序； desc（默认）：降序。 多个排序方式可使用半角逗号（,）分隔，例如：asc,desc。 排序方式不可多于排序字段，即参数Order的元素数量需小于等于参数Sort的元素数量。例如Sort取值为Size,Filename时，Order可取值为asc,desc或asc。 排序方式少于排序字段时，未排序的字段默认取值asc。例如Sort取值为Size,Filename，Order取值为asc时，Filename默认排序方式为asc，即升序排列
        # 是否必传：否
        'Order': "desc",
    }
    response, data = client.ci_dataset_simple_query(
        Body=body,
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_delete_dataset():
    # 删除数据集
    body = {
        # 数据集名称，同一个账户下唯一。
        # 是否必传：是
        'DatasetName': "test",
    }
    response, data = client.ci_delete_dataset(
        Body=body,
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_delete_dataset_binding():
    # 解绑存储桶与数据集
    body = {
        # 数据集名称，同一个账户下唯一。
        # 是否必传：是
        'DatasetName': "test",
        # 资源标识字段，表示需要与数据集绑定的资源，当前仅支持COS存储桶，字段规则：cos://<BucketName>，其中BucketName表示COS存储桶名称，例如：cos://examplebucket-1250000000
        # 是否必传：是
        'URI': "cos://examplebucket-1250000000",
    }
    response, data = client.ci_delete_dataset_binding(
        Body=body,
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_delete_file_meta_index():
    # 删除元数据索引
    body = {
        # 数据集名称，同一个账户下唯一。
        # 是否必传：是
        'DatasetName': "test",
        # 资源标识字段，表示需要建立索引的文件地址。
        # 是否必传：是
        'URI': "cos://examplebucket-1250000000/test.jpg",
    }
    response, data = client.ci_delete_file_meta_index(
        Body=body,
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_describe_dataset():
    # 查询数据集

    response, data = client.ci_describe_dataset(
        Datasetname="数据集名称",
        Statistics="",
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_describe_dataset_binding():
    # 查询数据集与存储桶的绑定关系

    response, data = client.ci_describe_dataset_binding(
        Datasetname="数据集名称",
        Uri="uri",
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_describe_dataset_bindings():
    # 查询绑定关系列表

    response, data = client.ci_describe_dataset_bindings(
        Datasetname="数据集名称",
        Maxresults=100,
        Nexttoken="下一页",
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_describe_datasets():
    # 列出数据集

    response, data = client.ci_describe_datasets(
        Maxresults=100,
        Nexttoken="下一页",
        Prefix="数据集前缀",
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_describe_file_meta_index():
    # 查询元数据索引

    response, data = client.ci_describe_file_meta_index(
        Datasetname="数据集名称",
        Uri="cos://facesearch-12500000000",
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_search_image():
    # 图像检索
    body = {
        # 数据集名称，同一个账户下唯一。
        # 是否必传：是
        'DatasetName': "ImageSearch001",
        # 指定检索方式为图片或文本，pic 为图片检索，text 为文本检索，默认为 pic。
        # 是否必传：否
        'Mode': "pic",
        # 资源标识字段，表示需要建立索引的文件地址(Mode 为 pic 时必选)。
        # 是否必传：否
        'URI': "cos://facesearch-1258726280/huge_base.jpg",
        # 返回相关图片的数量，默认值为10，最大值为100。
        # 是否必传：否
        'Limit': 10,
        # 出参 Score（相关图片匹配得分） 中，只有超过 MatchThreshold 值的结果才会返回。默认值为0，推荐值为80。
        # 是否必传：否
        'MatchThreshold': 1,
    }
    response, data = client.ci_search_image(
        Body=body,
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_update_dataset():
    # 更新数据集
    body = {
        # 数据集名称，同一个账户下唯一。
        # 是否必传：是
        'DatasetName': "test",
        # 数据集描述信息。长度为1~256个英文或中文字符，默认值为空。
        # 是否必传：否
        'Description': "test",
        #  检与数据集关联的检索模板，在建立元数据索引时，后端将根据检索模板来决定采集文件的哪些元数据。 每个检索模板都包含若干个算子，不同的算子表示不同的处理能力，更多信息请参见 [检索模板与算子](https://cloud.tencent.com/document/product/460/106018)。 默认值为空，即不关联检索模板，不进行任何元数据的采集。
        # 是否必传：否
        'TemplateId': "Official:COSBasicMeta",
    }
    response, data = client.ci_update_dataset(
        Body=body,
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


def ci_update_file_meta_index():
    # 更新元数据索引
    body = {
        # 数据集名称，同一个账户下唯一。
        # 是否必传：是
        'DatasetName': "test001",
        # 用于建立索引的文件信息。
        # 是否必传：是
        'UpdateMetaFile': {
            # 自定义ID。该文件索引到数据集后，作为该行元数据的属性存储，用于和您的业务系统进行关联、对应。您可以根据业务需求传入该值，例如将某个URI关联到您系统内的某个ID。推荐传入全局唯一的值。在查询时，该字段支持前缀查询和排序，详情请见[字段和操作符的支持列表](https://cloud.tencent.com/document/product/460/106154)。
            # 是否必传：否
            'CustomId': "001",
            # 自定义标签。您可以根据业务需要自定义添加标签键值对信息，用于在查询时可以据此为筛选项进行检索，详情请见[字段和操作符的支持列表](https://cloud.tencent.com/document/product/460/106154)。
            # 是否必传：否
            'CustomLabels': {"age": "18", "level": "18"},
            # 可选项，文件媒体类型，枚举值： image：图片。  other：其他。 document：文档。 archive：压缩包。 video：视频。  audio：音频。
            # 是否必传：否
            'MediaType': "image",
            # 可选项，文件内容类型（MIME Type），如image/jpeg。
            # 是否必传：否
            'ContentType': "image/jpeg",
            # 资源标识字段，表示需要建立索引的文件地址，当前仅支持COS上的文件，字段规则：cos:///，其中BucketName表示COS存储桶名称，ObjectKey表示文件完整路径，例如：cos://examplebucket-1250000000/test1/img.jpg。 注意： 1、仅支持本账号内的COS文件 2、不支持HTTP开头的地址
            # 是否必传：是
            'URI': "cos://examplebucket-1250000000/test1/img.jpg",
        },
    }
    response, data = client.ci_update_file_meta_index(
        Body=body,
        ContentType="application/json"
    )
    print(response)
    print(data)
    return response, data


if __name__ == '__main__':
    pass
