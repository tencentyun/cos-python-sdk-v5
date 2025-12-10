# -*- coding=utf-8
import json

from qcloud_cos import CosS3Auth
from qcloud_cos.cos_client import logger, CosS3Client
from .cos_comm import *


class CosVectorsClient(CosS3Client):

    def create_vector_bucket(self, Bucket, **kwargs):
        """ 创建向量存储桶

            :param Bucket(string) 向量存储桶名称.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.

            .. code-block:: python

                endpoint = "cos-vectors.ap-beijing.myqcloud.com" # 设置访问向量桶的endpoint
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Endpoint=endpoint)
                client = CosVectorsClient(config)
                # 创建向量桶
                resp, data = client.create_vector_bucket(Bucket="examplevectorbucket-1250000000")
                print(resp)
                print(data)
        """
        headers = mapped(kwargs)
        data = dict()
        data['vectorBucketName'] = Bucket
        headers['Content-Type'] = 'application/json'

        path = "/" + "CreateVectorBucket"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint)

        logger.debug("create vector bucket, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='POST',
            url=url,
            data=json.dumps(data),
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path),
            headers=headers)
        
        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response and response['Content-Type'].startswith('application/json'):
            data = rt.json()

        return response, data

    def get_vector_bucket(self, Bucket, **kwargs):
        """ 获取向量存储桶信息

            :param Bucket(string) 向量存储桶名称.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                endpoint = "cos-vectors.ap-beijing.myqcloud.com" # 设置访问向量桶的endpoint
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Endpoint=endpoint)
                client = CosVectorsClient(config)
                # 获取向量桶信息
                resp, data = client.get_vector_bucket(Bucket="examplevectorbucket-1250000000")
                print(resp)
                print(data)

        """
        headers = mapped(kwargs)
        data = dict()
        data['vectorBucketName'] = Bucket
        headers['Content-Type'] = 'application/json'

        path = "/" + "GetVectorBucket"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint)

        logger.debug("get vector bucket, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method = "POST",
            url = url,
            data = json.dumps(data),
            bucket = Bucket,
            auth = CosS3Auth(self._conf, path),
            headers = headers
        )

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response and response['Content-Type'].startswith('application/json'):
            data = rt.json()

        return response, data
    
    def list_vector_buckets(self, MaxResults=None, NextToken=None, Prefix=None, **kwargs):
        """ 获取向量存储桶列表

            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                endpoint = "cos-vectors.ap-beijing.myqcloud.com" # 设置访问向量桶的endpoint
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Endpoint=endpoint)
                client = CosVectorsClient(config)
                # 获取向量桶列表
                resp, data = client.list_vector_buckets()
                print(resp)
                print(data)

        """
        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/json'
        data = dict()
        if MaxResults is not None:
            data['maxResults'] = MaxResults
        if NextToken is not None:
            data['nextToken'] = NextToken
        if Prefix is not None:
            data['prefix'] = Prefix
        
        path = "/" + "ListVectorBuckets"
        url = self._conf.uri(bucket=None, path=path, endpoint=self._conf._endpoint)

        logger.debug("list vector buckets, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))

        rt = self.send_request(
            method="POST",
            url=url,
            data=json.dumps(data),
            bucket=None,
            auth=CosS3Auth(self._conf, path),
            headers=headers
        )

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response and response['Content-Type'].startswith('application/json'):
            data = rt.json()

        return response, data

    def delete_vector_bucket(self, Bucket, **kwargs):
        """ 删除向量存储桶
            :param Bucket(string) 向量存储桶名称.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.

            .. code-block:: python

                endpoint = "cos-vectors.ap-beijing.myqcloud.com" # 设置访问向量桶的endpoint
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Endpoint=endpoint)
                client = CosVectorsClient(config)
                # 删除向量桶
                resp = client.delete_vector_bucket(Bucket="examplevectorbucket-1250000000")
                print(resp)

        """
        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/json'
        data = dict()
        # 构造请求数据
        data['vectorBucketName'] = Bucket

        # 构造请求URL
        path = "/" + "DeleteVectorBucket"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint)

        logger.debug("delete vector bucket, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))

        rt = self.send_request(
            method="POST",
            url=url,
            data=json.dumps(data),
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path),
            headers=headers
        )

        response = dict(**rt.headers)

        return response
    
    def create_index(self, Bucket, Index, DataType, Dimension, DistanceMetric, NonFilterableMetadataKeys, **kwargs):
        """ 创建向量索引

            :param Bucket(string) 向量存储桶名称.
            :param Index(string) 向量索引名称.
            :param dataType(string) 向量数据类型, 支持float32.
            :param dimension(int) 向量维度, 范围1-4096.
            :distanceMetric(string) 距离度量, 支持cosine, euclidean.
            :param nonFilterableMetadataKeys(list) 非过滤元数据键列表.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                endpoint = "cos-vectors.ap-beijing.myqcloud.com" # 设置访问向量桶的endpoint
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Endpoint=endpoint)
                client = CosVectorsClient(config)
                # 创建向量桶
                resp, data = client.create_vector_bucket(Bucket="examplevectorbucket-1250000000")
                print(resp)
                print(data)
        """

        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/json'
        data = dict()
        # 构造请求数据
        data["dataType"] = DataType
        data["dimension"] = Dimension
        data["distanceMetric"] = DistanceMetric
        data["nonFilterableMetadataKeys"] = {}
        data["nonFilterableMetadataKeys"]["nonFilterableMetadataKeys"] = NonFilterableMetadataKeys
        data["indexName"] = Index
        data["vectorBucketName"] = Bucket

        # 构造请求URL
        path = "/" + "CreateIndex"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint)

        logger.debug("create index, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))

        rt = self.send_request(
            method="POST",
            url=url,
            data=json.dumps(data),
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path),
            headers=headers
        )

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response and response['Content-Type'].startswith('application/json'):
            data = rt.json()

        return response, data
    
    def get_index(self, Bucket, IndexName, **kwargs):
        """ 获取向量桶的索引信息
            :param Bucket(string) 向量存储桶名称.
            :param IndexName(string) 向量索引名称.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                endpoint = "cos-vectors.ap-beijing.myqcloud.com" # 设置访问向量桶的endpoint
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Endpoint=endpoint)
                client = CosVectorsClient(config)
                # 获取向量桶的索引信息
                resp, data = client.get_index(Bucket="examplevectorbucket-1250000000", IndexName="exampleindex")
                print(resp)
                print(data)
        """
        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/json'
        data = dict()
        # 构造请求数据
        data["indexName"] = IndexName
        data["vectorBucketName"] = Bucket

        # 构造请求URL
        path = "/" + "GetIndex"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint)

        logger.debug("get index, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))

        rt = self.send_request(
            method="POST",
            url=url,
            data=json.dumps(data),
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path),
            headers=headers
        )

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response and response['Content-Type'].startswith('application/json'):
            data = rt.json()

        return response, data
    
    def list_indexes(self, Bucket, MaxResults=None, NextToken=None, Prefix=None, **kwargs):
        """ 获取向量桶的索引列表
            :param Bucket(string) 向量存储桶名称.
            :param maxResults(int) 最大返回结果数.
            :param nextToken(string) 下一页的token.
            :param prefix(string) 索引名称前缀.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

        """
        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/json'
        data = dict()
        # 构造请求数据
        data["vectorBucketName"] = Bucket
        if MaxResults is not None:
            data["maxResults"] = MaxResults
        if NextToken is not None:
            data["nextToken"] = NextToken
        if Prefix is not None:
            data["prefix"] = Prefix

        # 构造请求URL
        path = "/" + "ListIndexes"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint)

        logger.debug("list indexes, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))

        rt = self.send_request(
            method="POST",
            url=url,
            data=json.dumps(data),
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path),
            headers=headers
        )

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response and response['Content-Type'].startswith('application/json'):
            data = rt.json()

        return response, data
    
    def delete_index(self, Bucket, IndexName, **kwargs):
        """ 删除向量桶的索引
            :param Bucket(string) 向量存储桶名称.
            :param IndexName(string) 向量索引名称.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
        """
        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/json'
        data = dict()
        # 构造请求数据
        data["indexName"] = IndexName
        data["vectorBucketName"] = Bucket

        # 构造请求URL
        path = "/" + "DeleteIndex"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint)

        logger.debug("delete index, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))

        rt = self.send_request(
            method="POST",
            url=url,
            data=json.dumps(data),
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path),
            headers=headers
        )

        response = dict(**rt.headers)

        return response
    
    def put_vectors(self, Bucket, IndexName, Vectors, **kwargs):
        """ 在向量桶的索引中添加或更新向量

            :param Bucket(string) 向量存储桶名称.
            :param IndexName(string) 索引名称.
            :param Vectors(list) 向量列表.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.

            .. code-block:: python

                endpoint = "cos-vectors.ap-beijing.myqcloud.com" # 设置访问向量桶的endpoint
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Endpoint=endpoint)
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
                    IndexName="example-index",
                    Vectors=vectors)
                print(resp)
        """
        headers = mapped(kwargs)
        data = dict()
        data['indexName'] = IndexName
        data['vectorBucketName'] = Bucket
        data['vectors'] = Vectors
        headers['Content-Type'] = 'application/json'

        path = "/" + "PutVectors"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint)

        logger.debug("put vectors, url=:{url} ,headers=:{headers}".format(
            url=url,
            headers=headers))
        rt = self.send_request(
            method='POST',
            url=url,
            data=json.dumps(data),
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path),
            headers=headers)
        return rt.headers
    
    def get_vectors(self, Bucket, IndexName, Keys, ReturnData=None, ReturnMetaData=None, **kwargs):
        """ 获取向量桶的索引中的向量
            :param Bucket(string) 向量存储桶名称.
            :param IndexName(string) 向量索引名称.
            :param Keys(list) 向量键列表.
            :param returnData(bool) 是否返回向量数据.
            :param returnMetaData(bool) 是否返回向量元数据.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                endpoint = "cos-vectors.ap-beijing.myqcloud.com" # 设置访问向量桶的endpoint
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Endpoint=endpoint)
                client = CosVectorsClient(config)
                # 获取向量
                resp, data = client.get_vectors(
                    Bucket="examplevectorbucket-1250000000",
                    IndexName="example-index",
                    Keys=["key1", "key2"])
                print(resp)
                print(data)

        """
        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/json'
        data = dict()
        # 构造请求数据
        data["indexName"] = IndexName
        data["vectorBucketName"] = Bucket
        data["keys"] = Keys
        if ReturnData is not None:
            data["returnData"] = ReturnData
        if ReturnMetaData is not None:
            data["returnMetaData"] = ReturnMetaData
        
        # 构造请求URL
        path = "/" + "GetVectors"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint)

        logger.debug("get vectors, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))

        rt = self.send_request(
            method="POST",
            url=url,
            data=json.dumps(data),
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path),
            headers=headers
        )

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response and response['Content-Type'].startswith('application/json'):
            data = rt.json()

        return response, data
    
    def list_vectors(self, Bucket, IndexName, MaxResults=None, NextToken=None, Prefix=None,
                     ReturnData=None, ReturnMetaData=None, SegmentCount=None, SegmentIndex=None, **kwargs):
        """ 获取向量桶的索引中的向量列表
            :param Bucket(string) 向量存储桶名称.
            :param IndexName(string) 向量索引名称.
            :param maxResults(int) 最大返回结果数.
            :param nextToken(string) 下一次请求的token.
            :param prefix(string) 向量键前缀.
            :param returnData(bool) 是否返回向量数据.
            :param returnMetaData(bool) 是否返回向量元数据.
            :param segmentCount(int) 分段数.
            :param segmentIndex(int) 分段索引, 从0开始.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                endpoint = "cos-vectors.ap-beijing.myqcloud.com" # 设置访问向量桶的endpoint
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Endpoint=endpoint)
                client = CosVectorsClient(config)
                # 获取向量列表
                resp, data = client.list_vectors(
                    Bucket="examplevectorbucket-1250000000",
                    IndexName="example-index")
                print(resp)
                print(data)
        """
        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/json'
        data = dict()
        # 构造请求数据
        data["indexName"] = IndexName
        data["vectorBucketName"] = Bucket
        if MaxResults is not None:
            data["maxResults"] = MaxResults
        if NextToken is not None:
            data["nextToken"] = NextToken
        if Prefix is not None:
            data["prefix"] = Prefix
        if ReturnData is not None:
            data["returnData"] = ReturnData
        if ReturnMetaData is not None:
            data["returnMetaData"] = ReturnMetaData
        if SegmentCount is not None and SegmentIndex is not None:
            data["segmentCount"] = SegmentCount
            data["segmentIndex"] = SegmentIndex
        
        # 构造请求URL
        path = "/" + "ListVectors"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint)

        logger.debug("list vector buckets, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))

        rt = self.send_request(
            method="POST",
            url=url,
            data=json.dumps(data),
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path),
            headers=headers
        )

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response and response['Content-Type'].startswith('application/json'):
            data = rt.json()

        return response, data
    
    def delete_vectors(self, Bucket, IndexName, Keys, **kwargs):
        """ 删除向量桶的索引中的向量
            :param Bucket(string) 向量存储桶名称.
            :param IndexName(string) 向量索引名称.
            :param Keys(list) 向量键列表.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.

            .. code-block:: python

                endpoint = "cos-vectors.ap-beijing.myqcloud.com" # 设置访问向量桶的endpoint
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Endpoint=endpoint)
                client = CosVectorsClient(config)
                # 删除向量
                resp = client.delete_vectors(
                    Bucket="examplevectorbucket-1250000000",
                    IndexName="example-index",
                    Keys=["key1", "key2"])
                print(resp)
        """
        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/json'
        data = dict()
        # 构造请求数据
        data["indexName"] = IndexName
        data["vectorBucketName"] = Bucket
        data["keys"] = Keys

        # 构造请求URL
        path = "/" + "DeleteVectors"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint)

        logger.debug("delete vectors, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))

        rt = self.send_request(
            method="POST",
            url=url,
            data=json.dumps(data),
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path),
            headers=headers
        )
        response = dict(**rt.headers)
        return response
    
    def query_vectors(self, Bucket, IndexName, QueryVectorDataType, QueryVector,TopK, Filter=None,
                      ReturnDistance=None, ReturnMetaData=None, **kwargs):
        """ 查询向量桶的索引中的向量
            :param Bucket(string) 向量存储桶名称.
            :param IndexName(string) 向量索引名称.
            :param QueryVectorDataType(string) 查询向量数据类型, 如float32.
            :param QueryVector(list) 查询向量的列表表示, 如[1.0, 2.0, 3.0].
            :param topK(int) 返回结果数.
            :param Filter(dict) 过滤条件, 语法详见接口文档.
            :param returnDistance(bool) 是否返回距离.
            :param returnMetaData(bool) 是否返回元数据.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                endpoint = "cos-vectors.ap-beijing.myqcloud.com" # 设置访问向量桶的endpoint
                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Endpoint=endpoint)
                client = CosVectorsClient(config)
                # 查询向量
                resp, data = client.query_vectors(
                    Bucket="examplevectorbucket-1250000000",
                    IndexName="example-index",
                    QueryVectorDataType="float32",
                    QueryVector=[1.0, 2.0, 3.0],
                    topK=10)
                print(resp)
                print(data)
        """
        headers = mapped(kwargs)
        headers['Content-Type'] = 'application/json'
        data = dict()
        # 构造请求数据
        data["indexName"] = IndexName
        data["vectorBucketName"] = Bucket
        data["queryVector"] = {}
        data["queryVector"][QueryVectorDataType] = QueryVector
        data["topK"] = TopK
        if Filter is not None:
            data["filter"] = Filter
        if ReturnDistance is not None:
            data["returnDistance"] = ReturnDistance
        if ReturnMetaData is not None:
            data["returnMetaData"] = ReturnMetaData

        # 构造请求URL
        path = "/" + "QueryVectors"
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint)

        logger.debug("query vectors, url=:{url} ,headers=:{headers}".format(url=url, headers=headers))

        rt = self.send_request(
            method="POST",
            url=url,
            data=json.dumps(data),
            bucket=Bucket,
            auth=CosS3Auth(self._conf, path),
            headers=headers
        )

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response and response['Content-Type'].startswith('application/json'):
            data = rt.json()

        return response, data



