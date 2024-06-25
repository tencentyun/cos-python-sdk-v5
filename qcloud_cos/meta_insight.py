# -*- coding=utf-8
import json

from qcloud_cos import CosS3Auth
from qcloud_cos.cos_client import logger, CosS3Client
from .cos_comm import *


class MetaInsightClient(CosS3Client):

    def ci_create_dataset(self, Body, **kwargs):
        """ 创建数据集 https://cloud.tencent.com/document/product/460/106020

        :param Body:(dict) 创建数据集配置信息.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  创建数据集
            response, data = client.ci_create_dataset(
                Body={}
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        body = json.dumps(Body)
        path = "/" + "dataset"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_create_dataset result, url=:{url} ,headers=:{headers}, params=:{params},body=:{body}".format(
            url=url,
            headers=headers,
            params=params,
            body=body))
        rt = self.send_request(
            method='POST',
            url=url,
            appid=self._conf._appid,
            data=body,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_create_dataset_binding(self, Body, **kwargs):
        """ 绑定存储桶与数据集 https://cloud.tencent.com/document/product/460/106159

        :param Body:(dict) 绑定存储桶与数据集配置信息.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  绑定存储桶与数据集
            response, data = client.ci_create_dataset_binding(
                Body={}
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        body = json.dumps(Body)
        path = "/" + "datasetbinding"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_create_dataset_binding result, url=:{url} ,headers=:{headers}, params=:{params},body=:{body}".format(
            url=url,
            headers=headers,
            params=params,
            body=body))
        rt = self.send_request(
            method='POST',
            url=url,
            appid=self._conf._appid,
            data=body,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_create_file_meta_index(self, Body, **kwargs):
        """ 创建元数据索引 https://cloud.tencent.com/document/product/460/106022

        :param Body:(dict) 创建元数据索引配置信息.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  创建元数据索引
            response, data = client.ci_create_file_meta_index(
                Body={}
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        body = json.dumps(Body)
        path = "/" + "filemeta"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_create_file_meta_index result, url=:{url} ,headers=:{headers}, params=:{params},body=:{body}".format(
            url=url,
            headers=headers,
            params=params,
            body=body))
        rt = self.send_request(
            method='POST',
            url=url,
            appid=self._conf._appid,
            data=body,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_dataset_face_search(self, Body, **kwargs):
        """ 人脸搜索 https://cloud.tencent.com/document/product/460/106166

        :param Body:(dict) 人脸搜索配置信息.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  人脸搜索
            response, data = client.ci_dataset_face_search(
                Body={}
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        body = json.dumps(Body)
        path = "/" + "datasetquery" + "/" + "facesearch"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_dataset_face_search result, url=:{url} ,headers=:{headers}, params=:{params},body=:{body}".format(
            url=url,
            headers=headers,
            params=params,
            body=body))
        rt = self.send_request(
            method='POST',
            url=url,
            appid=self._conf._appid,
            data=body,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_dataset_simple_query(self, Body, **kwargs):
        """ 简单查询 https://cloud.tencent.com/document/product/460/106375

        :param Body:(dict) 简单查询配置信息.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  简单查询
            response, data = client.ci_dataset_simple_query(
                Body={}
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        body = json.dumps(Body)
        path = "/" + "datasetquery" + "/" + "simple"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_dataset_simple_query result, url=:{url} ,headers=:{headers}, params=:{params},body=:{body}".format(
            url=url,
            headers=headers,
            params=params,
            body=body))
        rt = self.send_request(
            method='POST',
            url=url,
            appid=self._conf._appid,
            data=body,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_delete_dataset(self, Body, **kwargs):
        """ 删除数据集 https://cloud.tencent.com/document/product/460/106157

        :param Body:(dict) 删除数据集配置信息.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  删除数据集
            response, data = client.ci_delete_dataset(
                Body={}
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        body = json.dumps(Body)
        path = "/" + "dataset"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_delete_dataset result, url=:{url} ,headers=:{headers}, params=:{params},body=:{body}".format(
            url=url,
            headers=headers,
            params=params,
            body=body))
        rt = self.send_request(
            method='DELETE',
            url=url,
            appid=self._conf._appid,
            data=body,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_delete_dataset_binding(self, Body, **kwargs):
        """ 解绑存储桶与数据集 https://cloud.tencent.com/document/product/460/106160

        :param Body:(dict) 解绑存储桶与数据集配置信息.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  解绑存储桶与数据集
            response, data = client.ci_delete_dataset_binding(
                Body={}
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        body = json.dumps(Body)
        path = "/" + "datasetbinding"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_delete_dataset_binding result, url=:{url} ,headers=:{headers}, params=:{params},body=:{body}".format(
            url=url,
            headers=headers,
            params=params,
            body=body))
        rt = self.send_request(
            method='DELETE',
            url=url,
            appid=self._conf._appid,
            data=body,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_delete_file_meta_index(self, Body, **kwargs):
        """ 删除元数据索引 https://cloud.tencent.com/document/product/460/106163

        :param Body:(dict) 删除元数据索引配置信息.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  删除元数据索引
            response, data = client.ci_delete_file_meta_index(
                Body={}
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        body = json.dumps(Body)
        path = "/" + "filemeta"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_delete_file_meta_index result, url=:{url} ,headers=:{headers}, params=:{params},body=:{body}".format(
            url=url,
            headers=headers,
            params=params,
            body=body))
        rt = self.send_request(
            method='DELETE',
            url=url,
            appid=self._conf._appid,
            data=body,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_describe_dataset(self, DatasetName, Statistics=False, **kwargs):
        """ 查询数据集 https://cloud.tencent.com/document/product/460/106155

        :param DatasetName:(string) 数据集名称，同一个账户下唯一。.
        :param Statistics:(bool) 是否需要实时统计数据集中文件相关信息。有效值： false：不统计，返回的文件的总大小、数量信息可能不正确也可能都为0。 true：需要统计，返回数据集中当前的文件的总大小、数量信息。 默认值为false。.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  查询数据集
            response, data = client.ci_describe_dataset(
                Datasetname='',
                Statistics=''
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        params["datasetname"] = DatasetName
        params["statistics"] = Statistics

        params = format_values(params)

        path = "/" + "dataset"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_describe_dataset result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            appid=self._conf._appid,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_describe_dataset_binding(self, DatasetName, Uri, **kwargs):
        """ 查询数据集与存储桶的绑定关系 https://cloud.tencent.com/document/product/460/106485

        :param DatasetName:(string) 数据集名称，同一个账户下唯一。.
        :param Uri:(string) 资源标识字段，表示需要与数据集绑定的资源，当前仅支持COS存储桶，字段规则：cos://，其中BucketName表示COS存储桶名称，例如（需要进行urlencode）：cos%3A%2F%2Fexample-125000.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  查询数据集与存储桶的绑定关系
            response, data = client.ci_describe_dataset_binding(
                DatasetName='',
                Uri=''
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        params["datasetname"] = DatasetName
        params["uri"] = Uri

        params = format_values(params)

        path = "/" + "datasetbinding"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_describe_dataset_binding result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            appid=self._conf._appid,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_describe_dataset_bindings(self, DatasetName, NextToken=None, MaxResults=100, **kwargs):
        """ 查询绑定关系列表 https://cloud.tencent.com/document/product/460/106161

        :param DatasetName:(string) 数据集名称，同一个账户下唯一。.
        :param MaxResults:(int) 返回绑定关系的最大个数，取值范围为0~200。不设置此参数或者设置为0时，则默认值为100。.
        :param NextToken:(string) 当绑定关系总数大于设置的MaxResults时，用于翻页的token。从NextToken开始按字典序返回绑定关系信息列表。第一次调用此接口时，设置为空。.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  查询绑定关系列表
            response, data = client.ci_describe_dataset_bindings(
                DatasetName='',
                MaxResults='',
                NextToken=''
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        params["datasetname"] = DatasetName
        if NextToken is not None:
            params["nexttoken"] = NextToken
        params["maxresults"] = MaxResults

        params = format_values(params)

        path = "/" + "datasetbindings"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_describe_dataset_bindings result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            appid=self._conf._appid,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_describe_datasets(self, NextToken=None, Prefix=None, MaxResults=100, **kwargs):
        """ 列出数据集 https://cloud.tencent.com/document/product/460/106158

        :param MaxResults:(int) 本次返回数据集的最大个数，取值范围为0~200。不设置此参数或者设置为0时，则默认值为100。.
        :param NextToken:(string) 翻页标记。当文件总数大于设置的MaxResults时，用于翻页的Token。从NextToken开始按字典序返回文件信息列表。填写上次查询返回的值，首次使用时填写为空。.
        :param Prefix:(string) 数据集名称前缀。.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  列出数据集
            response, data = client.ci_describe_datasets(
                MaxResults='',
                NextToken='',
                Prefix=''
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        if NextToken is not None:
            params["nexttoken"] = NextToken
        if Prefix is not None:
            params["prefix"] = Prefix
        params["maxresults"] = MaxResults

        params = format_values(params)

        path = "/" + "datasets"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_describe_datasets result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            appid=self._conf._appid,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_describe_file_meta_index(self, DatasetName, Uri, **kwargs):
        """ 查询元数据索引 https://cloud.tencent.com/document/product/460/106164

        :param DatasetName:(string) 数据集名称，同一个账户下唯一。.
        :param Uri:(string) 资源标识字段，表示需要建立索引的文件地址，当前仅支持 COS 上的文件，字段规则：cos://<BucketName>/<ObjectKey>，其中BucketName表示 COS 存储桶名称，ObjectKey 表示文件完整路径，例如：cos://examplebucket-1250000000/test1/img.jpg。 注意： 仅支持本账号内的 COS 文件 不支持 HTTP 开头的地址 需 UrlEncode.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  查询元数据索引
            response, data = client.ci_describe_file_meta_index(
                Datasetname='',
                Uri=''
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        params["datasetname"] = DatasetName
        params["uri"] = Uri

        params = format_values(params)

        path = "/" + "filemeta"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_describe_file_meta_index result, url=:{url} ,headers=:{headers}, params=:{params}".format(
            url=url,
            headers=headers,
            params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            appid=self._conf._appid,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_search_image(self, Body, **kwargs):
        """ 图像检索 https://cloud.tencent.com/document/product/460/106376

        :param Body:(dict) 图像检索配置信息.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  图像检索
            response, data = client.ci_search_image(
                Body={}
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        body = json.dumps(Body)
        path = "/" + "datasetquery" + "/" + "imagesearch"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_search_image result, url=:{url} ,headers=:{headers}, params=:{params},body=:{body}".format(
            url=url,
            headers=headers,
            params=params,
            body=body))
        rt = self.send_request(
            method='POST',
            url=url,
            appid=self._conf._appid,
            data=body,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_update_dataset(self, Body, **kwargs):
        """ 更新数据集 https://cloud.tencent.com/document/product/460/106156

        :param Body:(dict) 更新数据集配置信息.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  更新数据集
            response, data = client.ci_update_dataset(
                Body={}
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        body = json.dumps(Body)
        path = "/" + "dataset"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_update_dataset result, url=:{url} ,headers=:{headers}, params=:{params},body=:{body}".format(
            url=url,
            headers=headers,
            params=params,
            body=body))
        rt = self.send_request(
            method='PUT',
            url=url,
            appid=self._conf._appid,
            data=body,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data

    def ci_update_file_meta_index(self, Body, **kwargs):
        """ 更新元数据索引 https://cloud.tencent.com/document/product/460/106162

        :param Body:(dict) 更新元数据索引配置信息.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  更新元数据索引
            response, data = client.ci_update_file_meta_index(
                Body={}
            )
            print data
            print response
        """
        headers = mapped(kwargs)
        final_headers = {}
        params = {}
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers

        params = format_values(params)
        body = json.dumps(Body)
        path = "/" + "filemeta"
        url = self._conf.uri(path=path, endpoint=self._conf._endpoint_ci, useAppid=True)

        logger.info("ci_update_file_meta_index result, url=:{url} ,headers=:{headers}, params=:{params},body=:{body}".format(
            url=url,
            headers=headers,
            params=params,
            body=body))
        rt = self.send_request(
            method='PUT',
            url=url,
            appid=self._conf._appid,
            data=body,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = xml_to_dict(rt.content)
        format_dict(data, ['Response'])

        response = dict(**rt.headers)
        return response, data
