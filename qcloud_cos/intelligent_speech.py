# -*- coding=utf-8

from qcloud_cos import CosS3Auth
from qcloud_cos.cos_client import logger, CosS3Client
from .cos_comm import *


class IntelligentSpeechClient(CosS3Client):

    def _asr_hot_vocabulary_table(self, Bucket, Body=None, Params={}, Path="/asrhotvocabtable", Method="POST", **kwargs):
        headers = mapped(kwargs)
        final_headers = {}
        params = Params
        for key in headers:
            if key.startswith("response"):
                params[key] = headers[key]
            else:
                final_headers[key] = headers[key]
        headers = final_headers
        params = format_values(params)

        xml_config = None
        if Body is not None:
            xml_config = format_xml(data=Body, root='Request')
        path = Path
        url = self._conf.uri(bucket=Bucket, path=path, endpoint=self._conf._endpoint_ci)
        logger.info("_asr_hot_vocabulary_table result, url=:{url} ,headers=:{headers}, params=:{params}, xml_config=:{xml_config}".format(
            url=url,
            headers=headers,
            params=params,
            xml_config=xml_config))
        rt = self.send_request(
            method=Method,
            url=url,
            bucket=Bucket,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True,
            cos_request=False)

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response and len(data) != 0:
            if response['Content-Type'] == 'application/xml':
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data

    def ci_create_asr_hot_vocabulary_table(self, Bucket, Body, **kwargs):
        """

        :param Bucket(string): 存储桶名称
        :param Body(dict): 创建热词表body
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 创建成功返回的结果, dict类型.

        . code-block:: python

            body = {
                "TableName": "test",
                "TableDescription": "test",
                "VocabularyWeights": {
                    "Vocabulary": "abc",
                    "Weight": "10"
                },
                # "VocabularyWeightStr": ""
            }
            response, data = client.ci_create_asr_hot_vocabulary_table(
                Bucket=bucket_name,
                Body=body,
                ContentType='application/xml'
            )
            print(response)
            print(data)
            return response, data
        """
        return self._asr_hot_vocabulary_table(Bucket, Body, **kwargs)

    def ci_update_asr_hot_vocabulary_table(self, Bucket, Body, **kwargs):
        """

        :param Bucket(string): 存储桶名称
        :param Body(dict): 更新热词表body
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 更新成功返回的结果, dict类型.

        . code-block:: python

            body = {
                "TableId": "08417b95c91xxxxxxxxxxxxx",
                "TableName": "test1",
                "TableDescription": "test1",
                "VocabularyWeights": {
                    "Vocabulary": "abc",
                    "Weight": "8"
                },
                # "VocabularyWeightStr": ""
            }
            response, data = client.ci_update_asr_hot_vocabulary_table(
                Bucket=bucket_name,
                Body=body,
                ContentType='application/xml'
            )
            print(response)
            print(data)
            return response, data
        """
        return self._asr_hot_vocabulary_table(Bucket=Bucket, Body=Body, Method="PUT", **kwargs)

    def ci_get_asr_hot_vocabulary_table(self, Bucket, TableId, **kwargs):
        """

        :param Bucket(string): 存储桶名称
        :param TableId(string): 热词表ID
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果, dict类型.

        . code-block:: python

            response, data = client.ci_get_asr_hot_vocabulary_table(
                Bucket=bucket_name,
                TableId='08417b95c91xxxxxxxxxxxxx',
            )
            print(response)
            print(data)
            return response, data
        """
        return self._asr_hot_vocabulary_table(Bucket=Bucket, Method="GET", Path="/asrhotvocabtable/" + TableId, **kwargs)

    def ci_list_asr_hot_vocabulary_table(self, Bucket, Offset=0, Limit=10, **kwargs):
        """

        :param Bucket(string): 存储桶名称
        :param Offset(string): 热词表ID
        :param Limit(string): 热词表ID
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果, dict类型.

        . code-block:: python

            response, data = client.ci_list_asr_hot_vocabulary_table(
                Bucket=bucket_name,
            )
            print(response)
            print(data)
            return response, data
        """
        param = {}
        param["offset"] = Offset
        param["limit"] = Limit
        return self._asr_hot_vocabulary_table(Bucket=Bucket, Method="GET", Params=param, **kwargs)

    def ci_delete_asr_hot_vocabulary_table(self, Bucket, TableId, **kwargs):
        """

        :param Bucket(string): 存储桶名称
        :param TableId(string): 热词表ID
        :param kwargs(dict): 设置请求的headers.
        :return(dict): 查询成功返回的结果, dict类型.

        . code-block:: python

            response, data = client.ci_delete_asr_hot_vocabulary_table(
                Bucket=bucket_name,
                TableId='08417b95c91xxxxxxxxxxxxx',
            )
            print(response)
            print(data)
            return response, data
        """
        return self._asr_hot_vocabulary_table(Bucket=Bucket, Method="DELETE", Path="/asrhotvocabtable/" + TableId, **kwargs)
