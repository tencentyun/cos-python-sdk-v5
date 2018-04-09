# qcloud_cos_py3

腾讯云COS 对象存储的python SDK 官方只支持python2.7。我自己修改了官方的代码，这个版本是支持python3.* 的版本。所有代码基本保持原样，只是做了python2 到python3 的兼容性处理。初步使用无bug。有bug欢迎提issue。
## 用法
所有方法和接口都没变，请参照官方教程
https://cloud.tencent.com/document/product/436/12270
https://github.com/tencentyun/cos-python-sdk-v5/blob/master/qcloud_cos/demo.py

用在自己的项目里面，将qcloud_cos3 放到项目根目录下，引用里面的方法的时候，将demo 里面的
from qcloud_cos import CosConfig
 换成
 from qcloud_cos3 import CosConfig
 
 以此类推

## Motivation
现在有很多包都依赖python3.* ，这个也是一个趋势。
最近在写一个qt的项目，用了pyqt5，就依赖python 3.5.
网上找的又觉得都有点小问题，所以就自己动手在官方的包上改动了一下，处理了所有不兼容的函数。
















Qcloud COSv5 SDK
#######################
    
介绍
_______

腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7。

安装指南
__________

使用pip安装 ::

    pip install -U cos-python-sdk-v5

手动安装::

    python setup.py install

使用方法
__________

使用python sdk，参照 https://github.com/tencentyun/cos-python-sdk-v5/blob/master/qcloud_cos/demo.py

cos最新可用地域，参照 https://cloud.tencent.com/document/product/436/6224

python sdk 快速入门，参照 https://cloud.tencent.com/document/product/436/12269

python sdk 接口文档，参照 https://cloud.tencent.com/document/product/436/12270
