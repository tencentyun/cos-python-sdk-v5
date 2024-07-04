# -*- coding=utf-8
import json

from qcloud_cos import CosS3Auth
from qcloud_cos.cos_client import logger, CosS3Client
from .cos_comm import *


class AIRecognitionClient(CosS3Client):

    def cos_create_ai_object_detect_job(self, Bucket, ObjectKey="", DetectUrl=None, **kwargs):
        """ 图像主体检测 https://cloud.tencent.com/document/product/460/97979

        :param Bucket(string) 存储桶名称.
        :param ObjectKey(string) 设置 ObjectKey.
        :param DetectUrl(string) 您可以通过填写 detect-url 处理任意公网可访问的图片链接。不填写 detect-url 时，后台会默认处理 ObjectKey ，填写了 detect-url 时，后台会处理 detect-url 链接，无需再填写 ObjectKey。 detect-url 示例：http://www.example.com/abc.jpg ，需要进行 UrlEncode，处理后为http%25253A%25252F%25252Fwww.example.com%25252Fabc.jpg。.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  图像主体检测
            response, data = client.cos_create_ai_object_detect_job(
                Bucket='bucket',
                ObjectKey='',
                DetectUrl=''
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
        params["ci-process"] = "AIObjectDetect"
        if DetectUrl is not None:
            params["detect-url"] = DetectUrl

        params = format_values(params)

        path = "/" + ObjectKey
        url = self._conf.uri(bucket=Bucket, path=path)

        logger.info(
            "cos_create_ai_object_detect_job result, url=:{url} ,headers=:{headers}, params=:{params}".format(
                url=url,
                headers=headers,
                params=params))
        rt = self.send_request(
            method='GET',
            url=url,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=False)

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response:
            if response['Content-Type'] == 'application/xml':
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data
