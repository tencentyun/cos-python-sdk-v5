# -*- coding=utf-8
import json

from six.moves.urllib.parse import quote

from qcloud_cos.cos_auth import CosS3Auth
from qcloud_cos.cos_client import logger, CosS3Client, CosConfig
from .cos_comm import *
from .cos_comm import format_bucket, mapped, to_bytes, to_unicode
from .cos_exception import CosClientError


def _dumps_json(data):
    """将请求体序列化为紧凑JSON, 无法序列化或包含NaN/Infinity时抛出CosClientError"""
    try:
        return json.dumps(data, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as e:
        raise CosClientError('request body is not valid JSON: {err}'.format(err=e))


def _without_none(pairs):
    """丢弃值为None的字段"""
    return dict((key, value) for key, value in pairs if value is not None)


class CosVectorsClient(CosS3Client):

    def _vectors_request(self, action, data, kwargs, path, bucket=None, retry_ambiguous=True):
        """发送COS Vectors协议或Native协议请求.

        :param action(string): 日志中的接口描述.
        :param data(dict): 请求体.
        :param kwargs(dict): 用户设置的headers.
        :param path(string): 已编码的请求路径, 同时用于签名.
        :param bucket(string): Native接口的存储桶名称, Host为<bucket>.<服务域名>; COS Vectors协议接口为None.
        :param retry_ambiguous(bool): 5xx与网络错误是否重试.
        :return(Response): 请求响应.
        """
        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/json'
        body = _dumps_json(data)
        url, host = self._conf.cos_vectors_url(path, bucket=bucket)
        # Host一律显式设置, 保证IP直连与带端口域名时签名的host与实际Host一致
        headers['Host'] = host

        logger.debug("{action}, url=:{url} ,headers=:{headers}".format(action=action, url=url, headers=headers))
        return self.send_request(
            method='POST',
            url=url,
            data=body,
            auth=CosS3Auth(self._conf, path),
            headers=headers,
            _retry_ambiguous=retry_ambiguous)

    @staticmethod
    def _vectors_response(rt):
        """返回 (response header, 结果), 结果为JSON时解析为dict"""
        data = rt.content
        response = dict(**rt.headers)
        content_type = rt.headers.get('Content-Type', '')
        if data and content_type.startswith('application/json'):
            data = rt.json()
        return response, data

    def _native_request(self, action, Bucket, path, data, kwargs, retry_ambiguous=True):
        """发送Native协议请求, Bucket必填且用于构造Host"""
        format_bucket(Bucket, self._conf._appid)
        return self._vectors_request(action, data, kwargs, path, bucket=Bucket, retry_ambiguous=retry_ambiguous)

    @staticmethod
    def _native_namespace_path(Namespace, action):
        """构造namespace级Native接口路径, namespace按单个路径段编码"""
        if not isinstance(Namespace, string_types) or not Namespace:
            raise CosClientError("Namespace is required not empty")
        namespace = to_unicode(Namespace)
        if u'/' in namespace or namespace in (u'.', u'..'):
            raise CosClientError("Namespace must not contain '/' or be '.' or '..'")
        return u"/_native/{namespace}/_{action}".format(
            namespace=to_unicode(quote(to_bytes(namespace), safe='')), action=action)

    def create_vector_bucket(self, Bucket, SseType=None, Mode=None, **kwargs):
        """ 创建向量存储桶

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param SseType: 存储桶加密类型.
            :type SseType: string
            :param Mode: 桶类型, 取值CLASSIC(经典向量索引)或ENHANCED(增强型namespace), 不填时由服务端按默认策略决定
                (当前服务端默认CLASSIC), SDK不发送mode字段. 创建后不可修改: Native API(namespace/文档接口)只能在ENHANCED桶上使用.
            :type Mode: string
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和请求成功返回的结果.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 创建向量桶
                resp, data = client.create_vector_bucket(Bucket="examplevectorbucket-1250000000", SseType="AES256")
                # 创建用于Native API的增强型桶
                resp, data = client.create_vector_bucket(Bucket="examplevectorbucket-1250000000", Mode="ENHANCED")
                print(resp)
                print(data)
        """
        data = dict()
        data['vectorBucketName'] = Bucket
        if SseType is not None:
            data['encryptionConfiguration'] = {'sseType': SseType}
        if Mode is not None:
            data['mode'] = Mode
        rt = self._vectors_request("create vector bucket", data, kwargs, "/CreateVectorBucket")
        return self._vectors_response(rt)

    def get_vector_bucket(self, Bucket, **kwargs):
        """ 获取向量存储桶信息

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和请求成功返回的结果.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 获取向量桶信息
                resp, data = client.get_vector_bucket(Bucket="examplevectorbucket-1250000000")
                print(resp)
                print(data)

        """
        data = dict()
        data['vectorBucketName'] = Bucket
        rt = self._vectors_request("get vector bucket", data, kwargs, "/GetVectorBucket")
        return self._vectors_response(rt)

    def list_vector_buckets(self, MaxResults=None, NextToken=None, Prefix=None, Mode=None, **kwargs):
        """ 获取向量存储桶列表

            :param MaxResults: 最大返回结果数.
            :type MaxResults: int
            :param NextToken: 下一页的token.
            :type NextToken: string
            :param Prefix: 向量存储桶名称前缀.
            :type Prefix: string
            :param Mode: 按桶类型过滤, 取值CLASSIC或ENHANCED; 不填时不过滤, 返回全部类型.
            :type Mode: string
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和请求成功返回的结果.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 获取向量桶列表
                resp, data = client.list_vector_buckets(
                    MaxResults=10,
                    Prefix="example")
                # 只列举增强型桶
                resp, data = client.list_vector_buckets(Mode="ENHANCED")
                print(resp)
                print(data)

        """
        data = _without_none([
            ('maxResults', MaxResults),
            ('nextToken', NextToken),
            ('prefix', Prefix),
            ('mode', Mode),
        ])
        rt = self._vectors_request("list vector buckets", data, kwargs, "/ListVectorBuckets")
        return self._vectors_response(rt)

    def delete_vector_bucket(self, Bucket, **kwargs):
        """ 删除向量存储桶
            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header.
            :rtype: dict

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 删除向量桶
                resp = client.delete_vector_bucket(Bucket="examplevectorbucket-1250000000")
                print(resp)

        """
        data = dict()
        data['vectorBucketName'] = Bucket
        rt = self._vectors_request("delete vector bucket", data, kwargs, "/DeleteVectorBucket")
        return dict(**rt.headers)

    def create_index(self, Bucket, Index, DataType, Dimension, DistanceMetric, NonFilterableMetadataKeys=None, **kwargs):
        """ 创建向量索引

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Index: 向量索引名称.
            :type Index: string
            :param DataType: 向量数据类型, 支持float32.
            :type DataType: string
            :param Dimension: 向量维度, 范围1-4096.
            :type Dimension: int
            :param DistanceMetric: 距离度量, 支持cosine, euclidean.
            :type DistanceMetric: string
            :param NonFilterableMetadataKeys: 非过滤元数据键列表.
            :type NonFilterableMetadataKeys: list
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和请求成功返回的结果.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 创建向量索引
                resp, data = client.create_index(
                    Bucket="examplevectorbucket-1250000000",
                    Index="example-index",
                    DataType="float32",
                    Dimension=128,
                    DistanceMetric="cosine")
                print(resp)
                print(data)
        """
        data = dict()
        data["dataType"] = DataType
        data["dimension"] = Dimension
        data["distanceMetric"] = DistanceMetric
        if NonFilterableMetadataKeys is not None:
            data["metadataConfiguration"] = {"nonFilterableMetadataKeys": NonFilterableMetadataKeys}
        data["indexName"] = Index
        data["vectorBucketName"] = Bucket
        rt = self._vectors_request("create index", data, kwargs, "/CreateIndex")
        return self._vectors_response(rt)

    def get_index(self, Bucket, Index, **kwargs):
        """ 获取向量桶的索引信息
            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Index: 向量索引名称.
            :type Index: string
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和请求成功返回的结果.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 获取向量桶的索引信息
                resp, data = client.get_index(Bucket="examplevectorbucket-1250000000", Index="exampleindex")
                print(resp)
                print(data)
        """
        data = dict()
        data["indexName"] = Index
        data["vectorBucketName"] = Bucket
        rt = self._vectors_request("get index", data, kwargs, "/GetIndex")
        return self._vectors_response(rt)

    def list_indexes(self, Bucket, MaxResults=None, NextToken=None, Prefix=None, **kwargs):
        """ 获取向量桶的索引列表
            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param MaxResults: 最大返回结果数.
            :type MaxResults: int
            :param NextToken: 下一页的token.
            :type NextToken: string
            :param Prefix: 索引名称前缀.
            :type Prefix: string
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和请求成功返回的结果.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 获取向量桶的索引列表
                resp, data = client.list_indexes(
                    Bucket="examplevectorbucket-1250000000",
                    MaxResults=10,
                    Prefix="example")
                print(resp)
                print(data)

        """
        data = _without_none([
            ("maxResults", MaxResults),
            ("nextToken", NextToken),
            ("prefix", Prefix),
        ])
        data["vectorBucketName"] = Bucket
        rt = self._vectors_request("list indexes", data, kwargs, "/ListIndexes")
        return self._vectors_response(rt)

    def delete_index(self, Bucket, Index, **kwargs):
        """ 删除向量桶的索引
            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Index: 向量索引名称.
            :type Index: string
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header.
            :rtype: dict

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 删除向量桶的索引
                resp = client.delete_index(
                    Bucket="examplevectorbucket-1250000000",
                    Index="example-index")
                print(resp)
        """
        data = dict()
        data["indexName"] = Index
        data["vectorBucketName"] = Bucket
        rt = self._vectors_request("delete index", data, kwargs, "/DeleteIndex")
        return dict(**rt.headers)

    def put_vectors(self, Bucket, Index, Vectors, **kwargs):
        """ 在向量桶的索引中添加或更新向量

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Index: 索引名称.
            :type Index: string
            :param Vectors: 向量列表, 例如[{"key": "key1", "data": {"float32": [0.1] * 128}, "metadata": {"d1": "value1"}}].
            :type Vectors: list
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header.
            :rtype: dict

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 向量
                vectors = [
                    {
                        "data": {"float32":  [0.1] * 128},
                        "key": "key1",
                        "metadata": {"metadata1": "value1", "metadata2": "value2"}
                    },
                    {
                        "data": {"float32":  [0.1] * 128},
                        "key": "key2",
                        "metadata": {"metadata1": "value3", "metadata2": "value4"}
                    },
                ]
                # 添加或更新向量
                resp = client.put_vectors(
                    Bucket="examplevectorbucket-1250000000",
                    Index="example-index",
                    Vectors=vectors)
                print(resp)
        """
        data = dict()
        data['indexName'] = Index
        data['vectorBucketName'] = Bucket
        data['vectors'] = Vectors
        rt = self._vectors_request("put vectors", data, kwargs, "/PutVectors")
        return rt.headers

    def get_vectors(self, Bucket, Index, Keys, ReturnData=None, ReturnMetaData=None, **kwargs):
        """ 获取向量桶的索引中的向量
            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Index: 向量索引名称.
            :type Index: string
            :param Keys: 向量键列表.
            :type Keys: list
            :param ReturnData: 是否返回向量数据.
            :type ReturnData: bool
            :param ReturnMetaData: 是否返回向量元数据.
            :type ReturnMetaData: bool
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和请求成功返回的结果.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 获取向量
                resp, data = client.get_vectors(
                    Bucket="examplevectorbucket-1250000000",
                    Index="example-index",
                    Keys=["key1", "key2"])
                print(resp)
                print(data)

        """
        data = _without_none([
            ("returnData", ReturnData),
            ("returnMetaData", ReturnMetaData),
        ])
        data["indexName"] = Index
        data["vectorBucketName"] = Bucket
        data["keys"] = Keys
        rt = self._vectors_request("get vectors", data, kwargs, "/GetVectors")
        return self._vectors_response(rt)

    def list_vectors(self, Bucket, Index, MaxResults=None, NextToken=None,
                     ReturnData=None, ReturnMetaData=None, SegmentCount=None, SegmentIndex=None,
                     Filter=None, **kwargs):
        """ 获取向量桶的索引中的向量列表
            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Index: 向量索引名称.
            :type Index: string
            :param MaxResults: 最大返回结果数.
            :type MaxResults: int
            :param NextToken: 下一次请求的token.
            :type NextToken: string
            :param ReturnData: 是否返回向量数据.
            :type ReturnData: bool
            :param ReturnMetaData: 是否返回向量元数据.
            :type ReturnMetaData: bool
            :param SegmentCount: 分段数.
            :type SegmentCount: int
            :param SegmentIndex: 分段索引, 从0开始.
            :type SegmentIndex: int
            :param Filter: 过滤条件, 例如{"metadata": {"$eq": "value1"}}, 语法详见接口文档.
            :type Filter: dict
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和请求成功返回的结果.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 获取向量列表
                resp, data = client.list_vectors(
                    Bucket="examplevectorbucket-1250000000",
                    Index="example-index")
                print(resp)
                print(data)
        """
        data = _without_none([
            ("maxResults", MaxResults),
            ("nextToken", NextToken),
            ("returnData", ReturnData),
            ("returnMetaData", ReturnMetaData),
            ("segmentCount", SegmentCount),
            ("segmentIndex", SegmentIndex),
            ("filter", Filter),
        ])
        data["indexName"] = Index
        data["vectorBucketName"] = Bucket
        rt = self._vectors_request("list vectors", data, kwargs, "/ListVectors")
        return self._vectors_response(rt)

    def delete_vectors(self, Bucket, Index, Keys, **kwargs):
        """ 删除向量桶的索引中的向量
            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Index: 向量索引名称.
            :type Index: string
            :param Keys: 向量键列表.
            :type Keys: list
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header.
            :rtype: dict

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 删除向量
                resp = client.delete_vectors(
                    Bucket="examplevectorbucket-1250000000",
                    Index="example-index",
                    Keys=["key1", "key2"])
                print(resp)
        """
        data = dict()
        data["indexName"] = Index
        data["vectorBucketName"] = Bucket
        data["keys"] = Keys
        rt = self._vectors_request("delete vectors", data, kwargs, "/DeleteVectors")
        return dict(**rt.headers)

    def query_vectors(self, Bucket, Index, QueryVector, TopK, Filter=None,
                      ReturnDistance=None, ReturnMetaData=None, ReturnData=None, **kwargs):
        """ 查询向量桶的索引中的向量
            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Index: 向量索引名称.
            :type Index: string
            :param QueryVector: 查询向量的表示, 如{"float32":[1.0, 2.0, 3.0]}.
            :type QueryVector: dict
            :param TopK: 返回结果数.
            :type TopK: int
            :param Filter: 过滤条件, {"metadata": {"$eq": "value1"}}, 语法详见接口文档.
            :type Filter: dict
            :param ReturnDistance: 是否返回距离.
            :type ReturnDistance: bool
            :param ReturnMetaData: 是否返回元数据.
            :type ReturnMetaData: bool
            :param ReturnData: 是否返回向量数据.
            :type ReturnData: bool
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和请求成功返回的结果.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 查询向量
                resp, data = client.query_vectors(
                    Bucket="examplevectorbucket-1250000000",
                    Index="example-index",
                    QueryVector={"float32":[1.0, 2.0, 3.0]},
                    TopK=10)
                print(resp)
                print(data)
        """
        data = _without_none([
            ("filter", Filter),
            ("returnDistance", ReturnDistance),
            ("returnMetaData", ReturnMetaData),
            ("returnData", ReturnData),
        ])
        data["indexName"] = Index
        data["vectorBucketName"] = Bucket
        data["queryVector"] = QueryVector
        data["topK"] = TopK
        rt = self._vectors_request("query vectors", data, kwargs, "/QueryVectors")
        return self._vectors_response(rt)

    def put_vector_bucket_policy(self, Bucket, Policy, **kwargs):
        """ 设置向量桶的策略
            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Policy: 策略内容.
            :type Policy: string or dict
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header.
            :rtype: dict

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 设置向量桶的策略
                resp = client.put_vector_bucket_policy(
                    Bucket="examplevectorbucket-1250000000",
                    Policy="{\"Statement\":[{\"Action\":[\"name/cos:DeleteVectorBucket\",\"name/cos:GetVectorBucket\",\"name/cos:PutVectorIndex\",\"name/cos:ListVectorIndexes\",\"name/cos:PutVectorBucketPolicy\",\"name/cos:GetVectorBucketPolicy\",\"name/cos:DeleteVectorBucketPolicy\"],\"Effect\":\"Allow\",\"Principal\":{\"qcs\":[\"qcs::cam::uin/700000000000:uin/700001234567\"]},\"Resource\":[\"qcs::cosvector:ap-guangzhou:uid/125000000:bucket/example-bucket-125000000/*\"],\"Sid\":\"bucket_action\"},{\"Action\":[\"name/cos:DeleteVectorIndex\",\"name/cos:GetVectorIndex\",\"name/cos:PutVectors\",\"name/cos:GetVectors\",\"name/cos:DeleteVectors\",\"name/cos:ListVectors\",\"name/cos:QueryVectors\"],\"Effect\":\"Allow\",\"Principal\":{\"qcs\":[\"qcs::cam::uin/700000000000:uin/700001234567\"]},\"Resource\":[\"qcs::cosvector:ap-guangzhou:uid/125000000:bucket/example-bucket-125000000/index/idx-dim3/*\"],\"Sid\":\"index_idx_dim3_action\"}],\"version\":\"2.0\"}")
                print(resp)
        """
        policy_str = Policy  # 策略内容, 可以是json格式字符串或者json格式字典
        if not isinstance(policy_str, string_types) and not isinstance(policy_str, dict):
            raise CosClientError("Policy must be a json format string or json format dict")
        if isinstance(policy_str, dict):
            policy_str = _dumps_json(policy_str)

        data = dict()
        data["policy"] = policy_str
        data["vectorBucketName"] = Bucket
        rt = self._vectors_request("put vector bucket policy", data, kwargs, "/PutVectorBucketPolicy")
        return dict(**rt.headers)

    def get_vector_bucket_policy(self, Bucket, **kwargs):
        """ 获取向量桶的策略
            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和请求成功返回的结果, policy字段为字符串, 可解析为dict.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 获取向量桶的策略
                resp, data = client.get_vector_bucket_policy(
                    Bucket="examplevectorbucket-1250000000")
                print(resp)
                print(data)
        """
        data = dict()
        data["vectorBucketName"] = Bucket
        rt = self._vectors_request("get vector bucket policy", data, kwargs, "/GetVectorBucketPolicy")
        return self._vectors_response(rt)

    def delete_vector_bucket_policy(self, Bucket, **kwargs):
        """ 删除向量桶的策略
            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header.
            :rtype: dict

            .. code-block:: python

                domain = "vectors.ap-guangzhou.coslake.com" # 设置访问向量桶的domain, 默认为vectors.<Region>.coslake.com
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Domain=domain)
                client = CosVectorsClient(config)
                # 删除向量桶的策略
                resp = client.delete_vector_bucket_policy(
                    Bucket="examplevectorbucket-1250000000")
                print(resp)
        """
        data = dict()
        data["vectorBucketName"] = Bucket
        rt = self._vectors_request("delete vector bucket policy", data, kwargs, "/DeleteVectorBucketPolicy")
        return dict(**rt.headers)

    # Native API begin
    #
    # Native接口通过Host定位存储桶: Domain > <bucket>.<EndpointCosVectors> > <bucket>.vectors.<Region>.coslake.com.
    # 配置Domain时, Domain必须为<bucket>.vectors.<region>.coslake.com形式且与Bucket参数一致.
    # 请求字段的取值、互斥与范围约束由服务端校验, 详见Native API文档.

    def create_namespace(self, Bucket, Namespace, Schema, Metadata=None, **kwargs):
        """ 创建namespace(Native API)

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Namespace: namespace名称.
            :type Namespace: string
            :param Schema: namespace schema, 包含fields与可选的primary_key, 详见Native API Schema定义.
            :type Schema: dict
            :param Metadata: 自定义元数据, 键与值均为字符串.
            :type Metadata: dict
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header.
            :rtype: dict

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)  # Native接口访问<bucket>.vectors.<Region>.coslake.com
                client = CosVectorsClient(config)
                # 创建namespace
                resp = client.create_namespace(
                    Bucket="examplevectorbucket-1250000000",
                    Namespace="products",
                    Schema={
                        "primary_key": "id",
                        "fields": {
                            "id": {"type": "string"},
                            "title": {"type": "text", "full_text_search": {"enabled": True}},
                            "price": {"type": "float64"},
                            "embedding": {"type": "vector", "dimension": 4, "distance_metric": "cosine"}
                        }
                    })
                print(resp)
        """
        data = _without_none([
            ('metadata', Metadata),
        ])
        data['schema'] = Schema
        path = self._native_namespace_path(Namespace, 'create_namespace')
        rt = self._native_request("create namespace", Bucket, path, data, kwargs)
        return dict(**rt.headers)

    def get_namespace(self, Bucket, Namespace, **kwargs):
        """ 获取namespace详情(Native API)

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Namespace: namespace名称.
            :type Namespace: string
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和请求成功返回的结果, 详情位于namespace字段.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
                client = CosVectorsClient(config)
                # 获取namespace详情
                resp, data = client.get_namespace(
                    Bucket="examplevectorbucket-1250000000",
                    Namespace="products")
                print(data['namespace'])
        """
        path = self._native_namespace_path(Namespace, 'get_namespace')
        rt = self._native_request("get namespace", Bucket, path, dict(), kwargs)
        return self._vectors_response(rt)

    def list_namespaces(self, Bucket, MaxResults=None, NextToken=None, Prefix=None, **kwargs):
        """ 列举存储桶下的namespace(Native API)

            结果不按kind过滤, 可能同时包含Native namespace(kind=namespace)与COS Vectors索引(kind=index).

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param MaxResults: 单页数量.
            :type MaxResults: int
            :param NextToken: 上一页返回的游标.
            :type NextToken: string
            :param Prefix: namespace名称前缀.
            :type Prefix: string
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和请求成功返回的结果, 列表位于namespaces字段, 没有更多结果时不返回nextToken.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
                client = CosVectorsClient(config)
                # 列举namespace
                resp, data = client.list_namespaces(
                    Bucket="examplevectorbucket-1250000000",
                    MaxResults=100,
                    Prefix="prod")
                print(data['namespaces'])
        """
        data = _without_none([
            ('maxResults', MaxResults),
            ('nextToken', NextToken),
            ('prefix', Prefix),
        ])
        rt = self._native_request("list namespaces", Bucket, u"/_native/_list_namespaces", data, kwargs)
        return self._vectors_response(rt)

    def modify_namespace(self, Bucket, Namespace, AddColumns=None, DropColumns=None, **kwargs):
        """ 修改namespace字段结构(Native API)

            AddColumns与DropColumns必须且只能提供一个非空列表.

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Namespace: namespace名称.
            :type Namespace: string
            :param AddColumns: 新增字段列表, 每个元素为平铺的字段定义, 如{"name": "category", "type": "string"}.
            :type AddColumns: list
            :param DropColumns: 待删除的字段名列表, 不能删除主键字段.
            :type DropColumns: list
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和修改后的namespace详情, 详情位于namespace字段.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
                client = CosVectorsClient(config)
                # 新增字段
                resp, data = client.modify_namespace(
                    Bucket="examplevectorbucket-1250000000",
                    Namespace="products",
                    AddColumns=[{"name": "category", "type": "string", "filterable": True}])
                print(data['namespace'])
        """
        data = _without_none([
            ('addColumns', AddColumns),
            ('dropColumns', DropColumns),
        ])
        path = self._native_namespace_path(Namespace, 'modify_namespace')
        rt = self._native_request("modify namespace", Bucket, path, data, kwargs)
        return self._vectors_response(rt)

    def delete_namespace(self, Bucket, Namespace, **kwargs):
        """ 删除namespace及其全部数据(Native API)

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Namespace: namespace名称.
            :type Namespace: string
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header.
            :rtype: dict

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
                client = CosVectorsClient(config)
                # 删除namespace
                resp = client.delete_namespace(
                    Bucket="examplevectorbucket-1250000000",
                    Namespace="products")
                print(resp)
        """
        path = self._native_namespace_path(Namespace, 'delete_namespace')
        rt = self._native_request("delete namespace", Bucket, path, dict(), kwargs)
        return dict(**rt.headers)

    def upsert_documents(self, Bucket, Namespace, Rows=None, Columns=None, PrimaryKeySpecified=False, **kwargs):
        """ 按主键整行插入或覆写文档(Native API)

            Rows与Columns必须且只能提供一个; 未在负载中出现的字段会被置为null, 只更新部分字段请使用patch_documents.

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Namespace: namespace名称.
            :type Namespace: string
            :param Rows: 行式负载, 每个元素为一个文档, 如[{"id": "p1", "title": "...", "embedding": [0.1, 0.2, 0.3, 0.4]}].
            :type Rows: list
            :param Columns: 列式负载, 字段名到取值数组的映射, 各列长度必须一致.
            :type Columns: dict
            :param PrimaryKeySpecified: 是否保证本次请求的每一行都携带主键(用户主键或显式的_id), 默认False.
                为False时5xx与网络错误不自动重试: 系统自动主键的namespace中未携带_id的行在重试时会重复写入.
                为True时按client的retry配置自动重试; schema指定了primary_key的namespace每行必然携带主键, 可设为True.
                SDK不校验该声明.
            :type PrimaryKeySpecified: bool
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header, 成功响应无body.
            :rtype: dict

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
                client = CosVectorsClient(config)
                # 行式写入, 每行都携带主键, 允许自动重试
                resp = client.upsert_documents(
                    Bucket="examplevectorbucket-1250000000",
                    Namespace="products",
                    Rows=[
                        {"id": "product-1", "title": "Vector database", "price": 12.5, "embedding": [0.1, 0.2, 0.3, 0.4]},
                        {"id": "product-2", "title": "Object storage", "price": 9.9, "embedding": [0.4, 0.3, 0.2, 0.1]}
                    ],
                    PrimaryKeySpecified=True)
                print(resp)
        """
        data = _without_none([
            ('rows', Rows),
            ('columns', Columns),
        ])
        path = self._native_namespace_path(Namespace, 'upsert')
        rt = self._native_request("upsert documents", Bucket, path, data, kwargs,
                                  retry_ambiguous=bool(PrimaryKeySpecified))
        return dict(**rt.headers)

    def patch_documents(self, Bucket, Namespace, Rows=None, Columns=None, **kwargs):
        """ 按主键部分更新文档(Native API)

            Rows与Columns必须且只能提供一个; 每行必须携带主键; 字段未出现保持原值, 显式null置为null, 有值则覆写.

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Namespace: namespace名称.
            :type Namespace: string
            :param Rows: 行式负载.
            :type Rows: list
            :param Columns: 列式负载, 各列长度必须一致.
            :type Columns: dict
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header, 成功响应无body.
            :rtype: dict

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
                client = CosVectorsClient(config)
                # 更新单个文档的价格
                resp = client.patch_documents(
                    Bucket="examplevectorbucket-1250000000",
                    Namespace="products",
                    Rows=[{"id": "product-1", "price": 10.0}])
                print(resp)
        """
        data = _without_none([
            ('rows', Rows),
            ('columns', Columns),
        ])
        path = self._native_namespace_path(Namespace, 'patch')
        rt = self._native_request("patch documents", Bucket, path, data, kwargs)
        return dict(**rt.headers)

    def delete_documents(self, Bucket, Namespace, Ids, **kwargs):
        """ 按主键删除文档(Native API)

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Namespace: namespace名称.
            :type Namespace: string
            :param Ids: 主键值列表, 必须非空, 删除不存在的主键不会报错.
            :type Ids: list
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header, 成功响应无body.
            :rtype: dict

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
                client = CosVectorsClient(config)
                # 按主键删除
                resp = client.delete_documents(
                    Bucket="examplevectorbucket-1250000000",
                    Namespace="products",
                    Ids=["product-1", "product-2"])
                print(resp)
        """
        data = dict()
        data['ids'] = Ids
        path = self._native_namespace_path(Namespace, 'delete')
        rt = self._native_request("delete documents", Bucket, path, data, kwargs)
        return dict(**rt.headers)

    def query_documents(self, Bucket, Namespace, Query=None, Queries=None, Filter=None, Fusion=None,
                        Sort=None, Limit=None, Offset=None, Projection=None, **kwargs):
        """ 检索文档(Native API), 支持BM25全文评分、向量ANN召回与多路召回融合

            Query、Queries、Filter至少提供一个; Query与Queries互斥; Fusion仅可与Queries同时提供. DSL语法详见Native API文档.

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Namespace: namespace名称.
            :type Namespace: string
            :param Query: 单路召回表达式, 如["title", "BM25", "vector database"].
            :type Query: list
            :param Queries: 多路召回表达式列表, 路数[1, 10].
            :type Queries: list
            :param Filter: 过滤表达式, 如["price", "Lt", 100].
            :type Filter: list
            :param Fusion: 多路召回融合配置, 如{"kind": "rrf", "rrf_k": 60}.
            :type Fusion: dict
            :param Sort: 排序项列表, 如[["price", "asc"]].
            :type Sort: list
            :param Limit: 返回条数.
            :type Limit: int
            :param Offset: 结果偏移量.
            :type Offset: int
            :param Projection: 返回字段投影, 如{"includes": ["title"]}或{"excludes": ["embedding"]}.
            :type Projection: dict
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和检索结果; 结果位于hits字段, 多路并行召回(Queries不带Fusion)时位于multiHits字段.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
                client = CosVectorsClient(config)
                # BM25与向量两路召回, RRF融合
                resp, data = client.query_documents(
                    Bucket="examplevectorbucket-1250000000",
                    Namespace="products",
                    Queries=[
                        ["title", "BM25", "vector database"],
                        ["embedding", "Ann", {"vector": [0.1, 0.2, 0.3, 0.4], "topk": 10}]
                    ],
                    Fusion={"kind": "rrf"},
                    Filter=["price", "Lt", 100],
                    Limit=10)
                print(data['hits'])
        """
        data = _without_none([
            ('query', Query),
            ('queries', Queries),
            ('filter', Filter),
            ('fusion', Fusion),
            ('sort', Sort),
            ('limit', Limit),
            ('offset', Offset),
            ('projection', Projection),
        ])
        path = self._native_namespace_path(Namespace, 'query')
        rt = self._native_request("query documents", Bucket, path, data, kwargs)
        return self._vectors_response(rt)

    def list_documents(self, Bucket, Namespace, Filter=None, MaxResults=None, NextToken=None,
                       Projection=None, SegmentCount=None, SegmentIndex=None, **kwargs):
        """ 枚举namespace内的文档(Native API), 不保证返回顺序

            SegmentCount与SegmentIndex必须同时提供或同时省略; 分页时nextToken须与首次请求的Filter与分段参数一致.

            :param Bucket: 向量存储桶名称.
            :type Bucket: string
            :param Namespace: namespace名称.
            :type Namespace: string
            :param Filter: 过滤表达式, 如["status", "Eq", "published"].
            :type Filter: list
            :param MaxResults: 单页条数.
            :type MaxResults: int
            :param NextToken: 上一页返回的游标.
            :type NextToken: string
            :param Projection: 返回字段投影, 规则同query_documents.
            :type Projection: dict
            :param SegmentCount: 并行枚举的总分段数.
            :type SegmentCount: int
            :param SegmentIndex: 当前分段下标, 从0开始.
            :type SegmentIndex: int
            :param kwargs: 设置上传的headers.
            :type kwargs: dict
            :return: response header 和枚举结果, 文档位于documents字段, 没有更多结果时不返回nextToken.
            :rtype: tuple(dict, dict)

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
                client = CosVectorsClient(config)
                # 分页枚举全部文档
                next_token = None
                while True:
                    resp, data = client.list_documents(
                        Bucket="examplevectorbucket-1250000000",
                        Namespace="products",
                        MaxResults=100,
                        NextToken=next_token)
                    print(data['documents'])
                    next_token = data.get('nextToken')
                    if not next_token:
                        break
        """
        data = _without_none([
            ('filter', Filter),
            ('maxResults', MaxResults),
            ('nextToken', NextToken),
            ('projection', Projection),
            ('segmentCount', SegmentCount),
            ('segmentIndex', SegmentIndex),
        ])
        path = self._native_namespace_path(Namespace, 'list')
        rt = self._native_request("list documents", Bucket, path, data, kwargs)
        return self._vectors_response(rt)
