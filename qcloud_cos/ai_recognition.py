# -*- coding=utf-8
import json

from qcloud_cos import CosS3Auth
from qcloud_cos.cos_client import logger, CosS3Client
from .cos_comm import *


class AIRecognitionClient(CosS3Client):

    def cos_create_ai_object_detect_job(self, Bucket, ObjectKey="",
        DetectUrl=None, **kwargs):
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

    def cos_goods_matting(self, Bucket, ObjectKey="", DetectUrl=None,
        CenterLayout=0, PaddingLayout=None, Stream=True, **kwargs):
        """ 商品抠图 https://cloud.tencent.com/document/product/460/79735

        :param Bucket(string) 存储桶名称.
        :param ObjectKey(string) 设置 ObjectKey.
        :param DetectUrl(string) 您可以通过填写 detect-url 处理任意公网可访问的图片链接。不填写 detect-url 时，后台会默认处理 ObjectKey ，填写了 detect-url 时，后台会处理 detect-url 链接，无需再填写 ObjectKey.
        :param CenterLayout(int) 抠图商品居中显示； 值为1时居中显示，值为0时不作处理，默认为0.
        :param PaddingLayout(string) 将处理后的图片四边进行留白，形式为 padding-layout=<dx>x<dy>，左右两边各进行 dx 像素的留白，上下两边各进行 dy 像素的留白.
        :param kwargs:(dict) 设置上传的headers.
        :return(dict): response header.
        :return(dict): 请求成功返回的结果,dict类型.

        .. code-block:: python

            config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
            client = CosS3Client(config)
            #  商品抠图
            response, data = client.cos_goods_matting(
                Bucket='bucket',
                ObjectKey='',
                DetectUrl=''
            )
            print data
            print response
        """
        params = {}
        if DetectUrl is not None:
            params["detect-url"] = DetectUrl
        if CenterLayout != 0:
            params["center-layout"] = CenterLayout
        if PaddingLayout is not None:
            params["padding-layout"] = PaddingLayout
        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path,
                               CiProcess="GoodsMatting", Params=params,
                               NeedHeader=True, Stream=Stream, **kwargs)

    def cos_ai_body_recognition(self, Bucket, ObjectKey='', DetectUrl=None,
        **kwargs):
        """ 人体识别 https://cloud.tencent.com/document/product/460/83196

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param DetectUrl(string) 您可以通过填写 detect-url 处理任意公网可访问的图片链接。不填写 detect-url 时，后台会默认处理 ObjectKey ，填写了 detect-url 时，后台会处理 detect-url 链接，无需再填写 ObjectKey detect-url 示例：http://www.example.com/abc.jpg ，需要进行 UrlEncode，处理后为http%25253A%25252F%25252Fwww.example.com%25252Fabc.jpg.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  人体识别
                response, data = client.cos_ai_body_recognition(
                    Bucket='bucket',
                    ObjectKey='',
                    DetectUrl=''
                )
                print data
                print response
            """

        params = {}
        if DetectUrl is not None:
            params["detect-url"] = DetectUrl

        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path,
                               CiProcess="AIBodyRecognition", Params=params,
                               NeedHeader=True, **kwargs)

    def cos_ai_detect_face(self, Bucket, ObjectKey, MaxFaceNum=1, **kwargs):
        """ 人脸检测 https://cloud.tencent.com/document/product/460/63223

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param MaxFaceNum(int) 最多处理的人脸数目。默认值为1（仅检测图片中面积最大的那张人脸），最大���为120。此参数用于控制处理待检测图片中的人脸个数，值越小，处理速度越快。.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  人脸检测
                response, data = client.cos_ai_detect_face(
                    Bucket='bucket',
                    ObjectKey='',
                    MaxFaceNum=''
                )
                print data
                print response
            """

        params = {}
        params["max-face-num"] = MaxFaceNum

        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path, CiProcess="DetectFace",
                               Params=params, NeedHeader=True, **kwargs)

    def cos_ai_detect_pet(self, Bucket, ObjectKey, **kwargs):
        """ 宠物识别 https://cloud.tencent.com/document/product/460/95753

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  宠物识别
                response, data = client.cos_ai_detect_pet(
                    Bucket='bucket',
                    ObjectKey=''
                )
                print data
                print response
            """

        params = {}

        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path, CiProcess="detect-pet",
                               Params=params, NeedHeader=True, **kwargs)

    def cos_ai_enhance_image(self, Bucket, ObjectKey='', Denoise=3,
        Sharpen=3, DetectUrl=None, IgnoreError=None, Stream=True, **kwargs):
        """ 图像增强 https://cloud.tencent.com/document/product/460/83792

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param Denoise(int) 去噪强度值，取值范围为 0 - 5 之间的整数，值为 0 时不进行去噪操作，默认值为3。.
            :param Sharpen(int) 锐化强度值，取值范围为 0 - 5 之间的整数，值为 0 时不进行锐化操作，默认值为3。.
            :param DetectUrl(string) 您可以通过填写 detect-url 处理任意公网可访问的图片链接。不填写 detect-url  时，后台会默认处理 ObjectKey ，填写了detect-url 时，后台会处理 detect-url链接，无需再填写 ObjectKey ，detect-url 示例：http://www.example.com/abc.jpg ，需要进行 UrlEncode，处理后为  http%25253A%25252F%25252Fwww.example.com%25252Fabc.jpg.
            :param IgnoreError(int) .
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  图像增强
                response, data = client.cos_ai_enhance_image(
                    Bucket='bucket',
                    ObjectKey='',
                    Denoise='',
                    Sharpen='',
                    DetectUrl='',
                    IgnoreError=''
                )
                print data
                print response
            """

        params = {}
        if Denoise is not None:
            params["denoise"] = Denoise
        if Sharpen is not None:
            params["sharpen"] = Sharpen
        if DetectUrl is not None:
            params["detect-url"] = DetectUrl
        if IgnoreError is not None:
            params["ignore-error"] = IgnoreError

        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path,
                               CiProcess="AIEnhanceImage", Params=params,
                               NeedHeader=True, Stream=Stream, **kwargs)

    def cos_ai_face_effect(self, Bucket, Type, ObjectKey="", DetectUrl=None,
        Whitening=30, Smoothing=10, FaceLifting=70, EyeEnlarging=70,
        Gender=None, Age=None, **kwargs):
        """ 人脸特效 https://cloud.tencent.com/document/product/460/47197

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param DetectUrl(string) 您可以通过填写 detect-url 处理任意公网可访问的图片链接。不填写 detect-url 时，后台会默认处理 ObjectKey ，填写了 detect-url 时，后台会处理 detect-url 链接，无需再填写 ObjectKey detect-url 示例：http://www.example.com/abc.jpg ，需要进行 UrlEncode，处理后为http%25253A%25252F%25252Fwww.example.com%25252Fabc.jpg。.
            :param Type(string) 人脸特效类型，人脸美颜：face-beautify；人脸性别转换：face-gender-transformation；人脸年龄变化：face-age-transformation；人像分割：face-segmentation.
            :param Whitening(int) type为face-beautify时生效，美白程度，取值范围[0,100]。0不美白，100代表最高程度。默认值30.
            :param Smoothing(int) type为face-beautify时生效，磨皮程度，取值范围[0,100]。0不磨皮，100代表最高程度。默认值10.
            :param FaceLifting(int) type为face-beautify时生效，瘦脸程度，取值范围[0,100]。0不瘦脸，100代表最高程度。默认值70.
            :param EyeEnlarging(int) type为face-beautify时生效，大眼程度，取值范围[0,100]。0不大眼，100代表最高程度。默认值70.
            :param Gender(int) type为face-gender-transformation时生效，选择转换方向，0：男变女，1：女变男。无默认值，为必选项。限制：仅对图片中面积最大的人脸进行转换。.
            :param Age(int) type为face-age-transformation时生效，变化到的人脸年龄,[10,80]。无默认值，为必选项。限制：仅对图片中面积最大的人脸进行转换。.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  人脸特效
                response, data = client.cos_ai_face_effect(
                    Bucket='bucket',
                    ObjectKey='',
                    DetectUrl='',
                    Type='',
                    Whitening='',
                    Smoothing='',
                    FaceLifting='',
                    EyeEnlarging='',
                    Gender='',
                    Age=''
                )
                print data
                print response
            """

        params = {}
        params["type"] = Type
        if DetectUrl is not None:
            params["detect-url"] = DetectUrl
        if Whitening is not None:
            params["whitening"] = Whitening
        if Smoothing is not None:
            params["smoothing"] = Smoothing
        if FaceLifting is not None:
            params["faceLifting"] = FaceLifting
        if EyeEnlarging is not None:
            params["eyeEnlarging"] = EyeEnlarging
        if Gender is not None:
            params["gender"] = Gender
        if Age is not None:
            params["age"] = Age

        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path, CiProcess="face-effect",
                               Params=params, NeedHeader=True, **kwargs)

    def cos_ai_game_rec(self, Bucket, ObjectKey='', DetectUrl=None, **kwargs):
        """ 游戏场景识别 https://cloud.tencent.com/document/product/460/93153

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 图片地址.
            :param DetectUrl(string) 您可以通过填写 detect-url 对任意公网可访问的图片进行游戏场景识别。不填写 detect-url 时，后台会默认处理 objectkey ；填写了 detect-url 时，后台会处理 detect-url 链接，无需再填写 objectkey ， detect-url 示例：http://www.example.com/abc.jpg。.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  游戏场景识别
                response, data = client.cos_ai_game_rec(
                    Bucket='bucket',
                    ObjectKey='',
                    DetectUrl=''
                )
                print data
                print response
            """

        params = {}
        if DetectUrl is not None:
            params["detect-url"] = DetectUrl

        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path, CiProcess="AIGameRec",
                               Params=params, NeedHeader=True, **kwargs)

    def cos_ai_id_card_ocr(self, Bucket, ObjectKey, CardSide=None, Config=None,
        **kwargs):
        """ 身份证识别 https://cloud.tencent.com/document/product/460/48638

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param CardSide(string) FRONT：身份证有照片的一面（人像面）BACK：身份证有国徽的一面（国徽面）该参数如果不填，将为您自动判断身份证正反面.
            :param Config(string) 以下可选字段均为 bool 类型，默认 false：CropIdCard，身份证照片裁剪（去掉证件外多余的边缘、自动矫正拍摄角度）CropPortrait，人像照片裁剪（自动抠取身份证头像区域）CopyWarn，复印件告警BorderCheckWarn，边框和框内遮挡告警ReshootWarn，翻拍告警DetectPsWarn，PS 检测告警TempIdWarn，临时身份证告警InvalidDateWarn，身份证有效日期不合法告警Quality，图片质量分数（评价图片的模糊程度）MultiCardDetect，是否开启多卡证检测参数设置方式参考：Config = {"CropIdCard":true,"CropPortrait":true}.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  身份证识别
                response, data = client.cos_aiid_card_ocr(
                    Bucket='bucket',
                    ObjectKey='',
                    CardSide='',
                    Config=''
                )
                print data
                print response
            """

        params = {}
        if CardSide is not None:
            params["CardSide"] = CardSide
        if Config is not None:
            params["Config"] = Config

        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path, CiProcess="IDCardOCR",
                               Params=params, NeedHeader=True, **kwargs)

    def cos_ai_image_coloring(self, Bucket, ObjectKey="", DetectUrl=None,
        Stream=True, **kwargs):
        """ 图片上色 https://cloud.tencent.com/document/product/460/83794

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param DetectUrl(string) 待上色图片url，需要进行urlencode，与ObjectKey二选其一，如果同时存在，则默认以ObjectKey为准.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  图片上色
                response, data = client.cos_ai_image_coloring(
                    Bucket='bucket',
                    ObjectKey='',
                    DetectUrl=''
                )
                print data
                print response
            """

        params = {}
        if DetectUrl is not None:
            params["detect-url"] = DetectUrl

        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path,
                               CiProcess="AIImageColoring", Params=params,
                               Stream=Stream, NeedHeader=True, **kwargs)

    def cos_ai_image_crop(self, Bucket, Width, Height, ObjectKey="",
        DetectUrl=None, Fixed=0, IgnoreError=None, Stream=True, **kwargs):
        """ 图像智能裁剪 https://cloud.tencent.com/document/product/460/83791

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param DetectUrl(string) 您可以通过填写 detect-url 处理任意公网可访问的图片链接。不填写 detect-url 时，后台会默认处理 ObjectKey ，填写了 detect-url 时，后台会处理 detect-url 链接，无需再填写 ObjectKey detect-url 示例：http://www.example.com/abc.jpg ，需要进行 UrlEncode，处理后为http%25253A%25252F%25252Fwww.example.com%25252Fabc.jpg.
            :param Width(int) 需要裁剪区域的宽度，与height共同组成所需裁剪的图片宽高比例；输入数字请大于0、小于图片宽度的像素值.
            :param Height(int) 需要裁剪区域的高度，与width共同组成所需裁剪的图片宽高比例；输入数字请大于0、小于图片高度的像素值；width : height建议取值在[1, 2.5]之间，超过这个范围可能会影响效果.
            :param Fixed(int) 是否严格按照 width 和 height 的值进行输出。取值为0时，宽高比例（width : height）会简化为最简分数，即如果width输入10、height输入20，会简化为1：2；取值为1时，输出图片的宽度等于width，高度等于height；默认值为0.
            :param IgnoreError(int) 当此参数为1时，针对文件过大等导致处理失败的场景，会直接返回原图而不报错.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  图像智能裁剪
                response, data = client.cos_ai_image_crop(
                    Bucket='bucket',
                    ObjectKey='',
                    DetectUrl='',
                    Width='',
                    Height='',
                    Fixed='',
                    IgnoreError=''
                )
                print data
                print response
            """

        params = {}
        params["width"] = Width
        params["height"] = Height
        if DetectUrl is not None:
            params["detect-url"] = DetectUrl
        if Fixed is not None:
            params["fixed"] = Fixed
        if IgnoreError is not None:
            params["ignore-error"] = IgnoreError

        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path, CiProcess="AIImageCrop",
                               Params=params, NeedHeader=True, Stream=Stream,
                               **kwargs)

    def cos_ai_license_rec(self, Bucket, CardType, ObjectKey='', DetectUrl=None,
        **kwargs):
        """ 卡证识别 https://cloud.tencent.com/document/product/460/96767

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param DetectUrl(string) 您可以通过填写 detect-url 处理任意公网可访问的图片链接。不填写 detect-url 时，后台会默认处理 ObjectKey ，填写了 detect-url 时，后台会处理 detect-url 链接，无需再填写 ObjectKey detect-url 示例：http://www.example.com/abc.jpg ，需要进行 UrlEncode，处理后为http%25253A%25252F%25252Fwww.example.com%25252Fabc.jpg.
            :param CardType(string) 卡证识别类型，有效值为IDCard，DriverLicense。<br>IDCard表示身份证；DriverLicense表示驾驶证，默认：DriverLicense.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  卡证识别
                response, data = client.cos_ai_license_rec(
                    Bucket='bucket',
                    ObjectKey='',
                    DetectUrl='',
                    CardType=''
                )
                print data
                print response
            """

        params = {}
        params["ci-process"] = "AILicenseRec"
        params["CardType"] = CardType
        if DetectUrl is not None:
            params["detect-url"] = DetectUrl

        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path,
                               CiProcess="AILicenseRec", Params=params,
                               NeedHeader=True, **kwargs)

    def cos_ai_pic_matting(self, Bucket, ObjectKey='', DetectUrl=None,
        CenterLayout=0, PaddingLayout=None, Stream=True, **kwargs):
        """ 通用抠图 https://cloud.tencent.com/document/product/460/106750

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param DetectUrl(string) 您可以通过填写 detect-url 处理任意公网可访问的图片链接。不填写 detect-url 时，后台会默认处理 ObjectKey ，填写了 detect-url 时，后台会处理 detect-url 链接，无需再填写 ObjectKey detect-url 示例：http://www.example.com/abc.jpg ，需要进行 UrlEncode，处理后为http%25253A%25252F%25252Fwww.example.com%25252Fabc.jpg。.
            :param CenterLayout(int) 抠图主体居中显示；值为1时居中显示，值为0不做处理，默认为0.
            :param PaddingLayout(string) 将处理后的图片四边进行留白，形式为 padding-layout=<dx>x<dy>，左右两边各进行 dx 像素的留白，上下两边各进行 dy 像素的留白，例如：padding-layout=20x10默认不进行留白操作，dx、dy 最大值为1000像素。.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  通用抠图
                response, data = client.cos_ai_pic_matting(
                    Bucket='bucket',
                    ObjectKey='',
                    DetectUrl='',
                    CenterLayout='',
                    PaddingLayout=''
                )
                print data
                print response
            """

        params = {}
        if DetectUrl is not None:
            params["detect-url"] = DetectUrl
        if CenterLayout is not None:
            params["center-layout"] = CenterLayout
        if PaddingLayout is not None:
            params["padding-layout"] = PaddingLayout

        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path,
                               CiProcess="AIPicMatting", Params=params,
                               NeedHeader=True, Stream=Stream, **kwargs)

    def cos_ai_portrait_matting(self, Bucket, ObjectKey='', DetectUrl=None,
        CenterLayout=0, PaddingLayout=None, Stream=True, **kwargs):
        """ 人像抠图 https://cloud.tencent.com/document/product/460/106751

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param DetectUrl(string) 您可以通过填写 detect-url 处理任意公网可访问的图片链接。不填写 detect-url 时，后台会默认处理 ObjectKey ，填写了 detect-url 时，后台会处理 detect-url 链接，无需再填写 ObjectKey。 detect-url 示例：http://www.example.com/abc.jpg，需要进行 UrlEncode，处理后为http%25253A%25252F%25252Fwww.example.com%25252Fabc.jpg。.
            :param CenterLayout(int) 抠图主体居中显示；值为1时居中显示，值为0不做处理，默认为0.
            :param PaddingLayout(string) 将处理后的图片四边进行留白，形式为 padding-layout=x，左右两边各进行 dx 像素的留白，上下两边各进行 dy 像素的留白，例如：padding-layout=20x10默认不进行留白操作，dx、dy最大值为1000像素。.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  人像抠图
                response, data = client.cos_ai_portrait_matting(
                    Bucket='bucket',
                    ObjectKey='',
                    DetectUrl='',
                    CenterLayout='',
                    PaddingLayout=''
                )
                print data
                print response
            """

        params = {}
        if DetectUrl is not None:
            params["detect-url"] = DetectUrl
        if CenterLayout is not None:
            params["center-layout"] = CenterLayout
        if PaddingLayout is not None:
            params["padding-layout"] = PaddingLayout

        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path,
                               CiProcess="AIPortraitMatting", Params=params,
                               NeedHeader=True, Stream=Stream, **kwargs)

    def cos_auto_translation_block(self, Bucket, InputText, SourceLang,
        TargetLang, TextDomain='general', TextStyle='sentence', **kwargs):
        """ 实时文字翻译 https://cloud.tencent.com/document/product/460/83547

            :param Bucket(string) 存储桶名称.
            :param InputText(string) 待翻译的文本.
            :param SourceLang(string) 输入语言，如 "zh".
            :param TargetLang(string) 输出语言，如 "en".
            :param TextDomain(string) 文本所属业务领域，如: "ecommerce", //缺省值为 general.
            :param TextStyle(string) 文本类型，如: "title", //缺省值为 sentence.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  实时文字翻译
                response, data = client.cos_auto_translation_block(
                    Bucket='bucket',
                    InputText='',
                    SourceLang='',
                    TargetLang='',
                    TextDomain='',
                    TextStyle=''
                )
                print data
                print response
            """

        params = {}
        params["InputText"] = InputText
        params["SourceLang"] = SourceLang
        params["TargetLang"] = TargetLang
        if TextDomain is not None:
            params["TextDomain"] = TextDomain
        if TextStyle is not None:
            params["TextStyle"] = TextStyle

        path = "/"
        return self.ci_process(Bucket=Bucket, Key=path,
                               CiProcess="AutoTranslationBlock", Params=params,
                               NeedHeader=True, **kwargs)

    def cos_get_action_sequence(self, Bucket, **kwargs):
        """ 获取动作顺序 https://cloud.tencent.com/document/product/460/48648

            :param Bucket(string) 存储桶名称.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  获取动作顺序
                response, data = client.cos_get_action_sequence(
                    Bucket='bucket'
                )
                print data
                print response
            """

        params = {}

        path = "/"
        return self.ci_process(Bucket=Bucket, Key=path,
                               CiProcess="GetActionSequence", Params=params,
                               NeedHeader=True, **kwargs)

    def cos_get_live_code(self, Bucket, **kwargs):
        """ 获取数字验证码 https://cloud.tencent.com/document/product/460/48647

            :param Bucket(string) 存储桶名称.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  获取数字验证码
                response, data = client.cos_get_live_code(
                    Bucket='bucket'
                )
                print data
                print response
            """

        params = {}
        path = "/"
        return self.ci_process(Bucket=Bucket, Key=path, CiProcess="GetLiveCode",
                               Params=params, NeedHeader=True, **kwargs)

    def cos_image_repair(self, Bucket, ObjectKey="", DetectUrl=None,
        MaskPic=None, MaskPoly=None, Stream=True, **kwargs):
        """ 图像修复 https://cloud.tencent.com/document/product/460/79042

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  图像修复
                response, data = client.cos_image_repair(
                    Bucket='bucket',
                    ObjectKey=''
                )
                print data
                print response
            """

        params = {}
        if DetectUrl is not None:
            params['detect-url'] = DetectUrl
        if MaskPic is not None:
            params['MaskPic'] = MaskPic
        if MaskPoly is not None:
            params['MaskPoly'] = MaskPoly
        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path, CiProcess="ImageRepair",
                               Params=params, NeedHeader=True, Stream=Stream,
                               **kwargs)

    def cos_liveness_recognition(self, Bucket, ObjectKey, IdCard, Name,
        LivenessType, ValidateData=None, BestFrameNum=None, **kwargs):
        """ 活体人脸核身 https://cloud.tencent.com/document/product/460/48641

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param IdCard(string) 身份证号.
            :param Name(string) 姓名。中文请使用 UTF-8编码.
            :param LivenessType(string) 活体检测类型，取值：LIP/ACTION/SILENTLIP 为数字模式，ACTION 为动作模式，SILENT 为静默模式，三种模式选择一种传入.
            :param ValidateData(string) 数字模式传参：数字验证码（1234），需先调用接口获取数字验证码动作模式传参：传动作顺序（2，1 or 1，2），需先调用接口获取动作顺序静默模式传参：空.
            :param BestFrameNum(int) 需要返回多张最佳截图，取值范围1 - 10，不设置默认返回一张最佳截图.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  活体人脸核身
                response, data = client.cos_liveness_recognition(
                    Bucket='bucket',
                    ObjectKey='',
                    CiProcess='',
                    IdCard='',
                    Name='',
                    LivenessType='',
                    ValidateData='',
                    BestFrameNum=''
                )
                print data
                print response
            """

        params = {}
        params["IdCard"] = IdCard
        params["Name"] = Name
        params["LivenessType"] = LivenessType
        if ValidateData is not None:
            params["ValidateData"] = ValidateData
        if BestFrameNum is not None:
            params["BestFrameNum"] = BestFrameNum

        path = "/" + ObjectKey
        return self.ci_process(Bucket=Bucket, Key=path,
                               CiProcess="LivenessRecognition",
                               Params=params, NeedHeader=True, **kwargs)

    def ci_image_search_bucket(self, Bucket, Body, **kwargs):
        """ 开通以图搜图 https://cloud.tencent.com/document/product/460/63899

            :param Bucket(string) 存储桶名称.
            :param Body:(dict) 开通以图搜图配置信息.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  开通以图搜图
                response, data = client.ci_image_search_bucket(
                    Bucket='bucket',
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
        xml_config = format_xml(data=Body, root='Request')
        path = "/" + "ImageSearchBucket"
        url = self._conf.uri(bucket=Bucket, path=path,
                             endpoint=self._conf._endpoint_ci)

        logger.info(
            "ci_image_search_bucket result, url=:{url} ,headers=:{headers}, params=:{params},xml_config=:{xml_config}".format(
                url=url,
                headers=headers,
                params=params,
                xml_config=xml_config))
        rt = self.send_request(
            method='POST',
            url=url,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=True)

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response:
            if response[
                'Content-Type'] == 'application/xml' and 'Content-Length' in response and \
                response['Content-Length'] != 0:
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data

    def cos_add_image_search(self, Bucket, ObjectKey, Body, **kwargs):
        """ 添加图库图片 https://cloud.tencent.com/document/product/460/63900

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param Body:(dict) 添加图库图片配置信息.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  添加图库图片
                response, data = client.cos_add_image_search(
                    Bucket='bucket',
                    ObjectKey='',
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
        params["ci-process"] = "ImageSearch"
        params["action"] = "AddImage"
        params = format_values(params)

        xml_config = format_xml(data=Body, root='Request')

        path = "/" + ObjectKey
        url = self._conf.uri(bucket=Bucket, path=path)

        logger.info(
            "cos_add_image_search result, url=:{url} ,headers=:{headers}, params=:{params},xml_config=:{xml_config}".format(
                url=url,
                headers=headers,
                params=params,
                xml_config=xml_config))
        rt = self.send_request(
            method='POST',
            url=url,
            data=xml_config,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=False)

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response:
            if response[
                'Content-Type'] == 'application/xml' and 'Content-Length' in response and \
                response['Content-Length'] != 0:
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data

    def cos_get_search_image(self, Bucket, ObjectKey, MatchThreshold=0,
        Offset=0, Limit=10, Filter=None, **kwargs):
        """ 图片搜索接口 https://cloud.tencent.com/document/product/460/63901

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param MatchThreshold(int) 出参 Score 中，只有超过 MatchThreshold 值的结果才会返回。默认为0.
            :param Offset(int) 起始序号，默认值为0.
            :param Limit(int) 返回数量，默认值为10，最大值为100.
            :param Filter(string) 针对入库时提交的 Tags 信息进行条件过滤。支持>、>=、<、<=、=、!=，多个条件之间支持 AND 和 OR 进行连接.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  图片搜索接口
                response, data = client.cos_get_search_image(
                    Bucket='bucket',
                    ObjectKey='',
                    MatchThreshold='',
                    Offset='',
                    Limit='',
                    Filter=''
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
        params["ci-process"] = "ImageSearch"
        params["action"] = "SearchImage"
        if MatchThreshold is not None:
            params["MatchThreshold"] = MatchThreshold
        if Offset is not None:
            params["Offset"] = Offset
        if Limit is not None:
            params["Limit"] = Limit
        if Filter is not None:
            params["Filter"] = Filter

        params = format_values(params)

        path = "/" + ObjectKey
        url = self._conf.uri(bucket=Bucket, path=path)

        logger.info(
            "cos_get_search_image result, url=:{url} ,headers=:{headers}, params=:{params}".format(
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
            if response[
                'Content-Type'] == 'application/xml' and 'Content-Length' in response and \
                response['Content-Length'] != 0:
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data

    def cos_delete_image_search(self, Bucket, ObjectKey, Body, **kwargs):
        """ 删除图库图片 https://cloud.tencent.com/document/product/460/63902

            :param Bucket(string) 存储桶名称.
            :param ObjectKey(string) 设置 ObjectKey.
            :param Body:(dict) 删除图库图片配置信息.
            :param kwargs:(dict) 设置上传的headers.
            :return(dict): response header.
            :return(dict): 请求成功返回的结果,dict类型.

            .. code-block:: python

                config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token)  # 获取配置对象
                client = CosS3Client(config)
                #  删除图库图片
                response, data = client.cos_delete_image_search(
                    Bucket='bucket',
                    ObjectKey='',
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

        params["ci-process"] = "ImageSearch"
        params["action"] = "DeleteImage"
        params = format_values(params)
        body = format_xml(data=Body, root='Request')
        path = "/" + ObjectKey
        url = self._conf.uri(bucket=Bucket, path=path)

        logger.info(
            "cos_delete_image_search result, url=:{url} ,headers=:{headers}, params=:{params},body=:{body}".format(
                url=url,
                headers=headers,
                params=params,
                body=body))
        rt = self.send_request(
            method='POST',
            url=url,
            data=body,
            auth=CosS3Auth(self._conf, path, params=params),
            params=params,
            headers=headers,
            ci_request=False)

        data = rt.content
        response = dict(**rt.headers)
        if 'Content-Type' in response:
            if response['Content-Type'] == 'application/xml' and 'Content-Length' in response and \
                response['Content-Length'] != 0:
                data = xml_to_dict(rt.content)
                format_dict(data, ['Response'])
            elif response['Content-Type'].startswith('application/json'):
                data = rt.json()

        return response, data
