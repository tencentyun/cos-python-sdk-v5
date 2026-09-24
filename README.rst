Qcloud COSv5 SDK
#######################

.. image:: https://img.shields.io/pypi/v/cos-python-sdk-v5.svg
   :target: https://pypi.org/search/?q=cos-python-sdk-v5
   :alt: Pypi
.. image:: https://api.travis-ci.com/tencentyun/cos-python-sdk-v5.svg?branch=master
   :target: https://app.travis-ci.com/github/tencentyun/cos-python-sdk-v5
   :alt: Travis CI 

介绍
_______

腾讯云COSV5Python SDK, 目前可以支持Python2.6与Python2.7以及Python3.x。

安装指南
__________

使用pip安装 ::

    pip install -U cos-python-sdk-v5

手动安装::

    python setup.py install

使用方法
__________

使用python sdk，参照 https://github.com/tencentyun/cos-python-sdk-v5/blob/master/demo/demo.py

cos最新可用地域，参照 https://cloud.tencent.com/document/product/436/6224

python sdk 快速入门，参照 https://cloud.tencent.com/document/product/436/12269

python sdk 接口文档，参照 https://cloud.tencent.com/document/product/436/12270

高性能桶（COS Rapid Bucket）
____________________________

高性能桶（fusion-io）的数据面请求必须先 ``CreateSession`` 换临时凭证再签名。
``CreateSession`` 响应契约为 AWS 兼容 XML；历史 proxy 的 JSON 响应仍可过渡解析。
``CosS3Client`` 在识别到桶名 ``<short>-x--<appid>`` 且 Endpoint/Domain 符合
``<bucket>.cosrapid.<region>.myqcloud.com`` 域名（或显式配置开关）时
自动完成签发、按桶缓存与重签。不要用基础永久密钥直接打数据面；未启用 session
时 SDK 会本地报错，而不是把请求发出去后等网关 403。

使用示例见 `demo/rapid_bucket.py <demo/rapid_bucket.py>`_。

配置要点：

* ``EnableRapidDomain=True``：Bucket Endpoint 使用
  ``cosrapid.<region>.myqcloud.com``，ServiceDomain 使用
  ``service.cosrapid.<region>.myqcloud.com``。例如对象 Host 为
  ``<bucket>.cosrapid.ap-nanjing.myqcloud.com``。
* ``EnableSessionAuth=True``：本地 IP:Port / 自定义 Domain 联调时强制对 rapid 桶开 session。
* ``SessionMode``：``ReadWrite``（默认）或 ``ReadOnly``。
* ``CreateSessionTimeout``：CreateSession 独立超时，默认 30 秒。

Rapid Gateway DNS 负载均衡
~~~~~~~~~~~~~~~~~~~~~~~~~~

SDK 对满足条件的 HTTP Rapid Gateway Bucket Host 请求默认启用进程内 DNS 负载均衡：连接目标从
``<bucket>.cosrapid.<region>.myqcloud.com`` 的 A/AAAA 结果中选择，但 HTTP ``Host``
和 COS 签名仍使用该逻辑桶域名。
普通桶和 HTTPS 请求保持原路径。

Rapid Bucket 控制面（Create/Delete/Head Bucket、BucketPolicy、CreateSession）连接
``service.cosrapid.<region>.myqcloud.com`` 的 Proxy 入口，但 HTTP ``Host`` 和签名 Host
仍使用 Bucket Host；``list_buckets`` 没有具体 Bucket，连接、Host 和签名均使用 service 域名。

配置要点：

* ``EnableGatewayDnsLb=None``（默认）：仅合格的 HTTP rapid 请求自动启用；``True`` 在
  rapid 请求不满足约束时本地报错；``False`` 关闭。
* ``GatewayDnsRefreshInterval=5``：DNS 刷新间隔秒数，最小 1 秒。
* 设置 ``CosConfig.IP``、显式 ``Proxies``、自定义 ``session=``，或启用
  ``trust_env`` 且进程存在 HTTP/ALL 环境代理时，不启用 DNS LB。
* Bucket Host 不得携带显式端口；生产 HTTP 入口使用默认 80 端口。

连接异常、超时、响应截断和 HTTP 500/502/503/504 会在 body 可回退时换节点，并使用
full-jitter 指数退避。``retry=N`` 最多执行 ``N+1`` 次 IP 尝试；IP 路径用尽后当前请求
最多再按逻辑域名发送一次。冷启动没有 DNS 快照时直接走逻辑域名并使用原 retry 预算。
生成器或无法 seek 的 body 不会自动重发。

``rename_object`` 例外：Rename 没有请求级幂等凭据，响应丢失时无法区分“未执行”和
“已提交但响应未到达”。SDK 因此不对它的连接异常、超时、响应截断或 5xx 自动重发；
调用方收到此类错误时必须按结果不确定处理。

支持的接口：

* 对象：``put_object`` / ``get_object`` / ``head_object`` / ``delete_object`` / ``delete_objects``
* 对象：``copy_object`` / ``upload_part_copy`` / 高级 ``copy``（Rapid 仅同桶同地域）/
  ``upload_file`` / ``download_file``
* 对象：``rename_object``（高性能桶专用，同桶原子重命名）
* 预签名：``get_session_presigned_url``；rapid 桶上 ``get_presigned_url`` 会转到该方法
* 分块上传全流程、``list_objects``
* 控制面（使用基础凭证，不走 session）：``create_bucket`` / ``delete_bucket`` /
  ``head_bucket`` / bucket policy / ``create_session``

创建高性能桶时，使用 ``create_bucket`` 的四个可选命名参数；它们合并后的有效值
必须齐全且非空。以下变量应使用实际桶名、VPC、CIDR、子网和可用区配置::

    client.create_bucket(
        Bucket=bucket, VpcId=vpc_id, CidrBlock=cidr_block,
        SubnetId=subnet_id, Zone=zone,
    )

旧 ``Metadata`` 用法仍然支持，可与命名参数混合使用::

    client.create_bucket(
        Bucket=bucket,
        Metadata={
            'x-cos-vpc-id': vpc_id,
            'x-cos-cidr-block': cidr_block,
            'x-cos-subnet-id': subnet_id,
            'x-cos-zone': zone,
        },
    )

``Metadata`` 的键是完整 HTTP 头名，不会自动添加 ``x-cos-meta-`` 前缀。四个字段按
头名大小写不敏感合并；同值接受（含等价的 text/bytes），冲突在本地报错，不静默覆盖。
命名参数的 ``None`` 表示未提供，允许由 ``Metadata`` 补齐；缺失、空字符串或纯空白值
在发送请求前拒绝。SDK 不推导 Zone/CIDR，不代替服务端校验云资源配置。
命名参数仅用于 Rapid ``create_bucket``，普通桶误用非 ``None`` 值会被拒绝；普通桶
原有 ``Metadata`` 行为不变，其它 API 也不新增这些参数。

创建请求使用基础凭证，不依赖 Rapid session。方法成功返回 ``None`` 表示创建请求
已受理，不代表资源编排完成；使用 ``head_bucket`` 查询 ``x-cos-bucket-status``，
待服务端报告 ``Available`` 后再进行对象操作。
独立建桶示例见 `demo/rapid_create_bucket.py <demo/rapid_create_bucket.py>`_。

Rapid ``upload_file`` 会在不携带 Prefix 的情况下分页列举未完成 MPU，再按完整 Key
在客户端过滤，因此兼容 Gateway 的 ListMultipartUploads 参数限制并保留断点续传。
``upload_file`` / ``download_file`` 继续使用现有 ``MAXThread`` 并发与下载记录文件。
可分别通过 ``EnableMD5=True`` 和 ``EnableCRC=True`` 开启上传 Content-MD5 与
下载 CRC64 完整性校验。

名单外接口（例如 object/bucket ACL、Tagging、Versioning、Website、Inventory、
Symlink、Append、Select/Restore）不属于 Rapid Gateway 当前契约，SDK 会在
``CreateSession`` 和网络调用前本地拒绝；普通 bucket 不受该限制。

Rapid Gateway 的 ``list_objects`` 使用目录语义，``Delimiter`` 为空时 SDK 仅对
rapid bucket 规范化为 ``/``；普通 bucket 仍保留原来的空 delimiter 行为。
非空 ``Prefix`` 必须以 ``/`` 结尾；不支持按任意字符串前缀递归列举。
分页时保持 ``Prefix`` 不变，把返回的 ``NextMarker`` 直接作为下一次 ``Marker``。
Rapid 的游标是当前目录内的相对名字，不要从 ``Contents.Key`` 推导或额外拼接 Prefix。

Rapid ``list_objects``、``list_multipart_uploads``、``list_parts`` 的响应声明
``EncodingType=url`` 时，SDK 默认按 query 编码解码名称与游标：``+`` 还原为空格，
``%2B`` 还原为字面加号，百分号只解码一次；multipart 的 UploadId 游标保持原样。
普通 Bucket 和未声明编码的旧 Rapid 响应保持既有解码行为。显式传入
``EncodingType='url'`` 时仍返回编码后的字段，调用方应自行使用 ``unquote_plus``
解码 Rapid 名称及 Key/Marker 后再使用；不要解码 UploadId。

Rapid 参数边界
~~~~~~~~~~~~~~

* Rapid 不支持对象版本。显式传入 ``VersionId``（包括空值或 ``"null"``）、
  ``CopySource.VersionId``、批量删除对象的 ``VersionId`` 或预签名
  ``Params['versionId']`` 时，SDK 本地报错，避免对当前对象执行错误操作。
* Rapid 不支持服务端 ``Callback`` / ``CallbackVar``。显式设置时本地报错；
  ``upload_file`` 的本地 ``progress_callback`` 继续支持。
* Rapid Copy 仅支持同桶；高层 ``copy`` 在读取源对象和创建分块上传前检查。
* 对象 Key、CopySource.Key 和 RenameSource 不能含独立的 ``.`` / ``..`` 路径段。
  SDK 本地拒绝，防止 HTTP 库在请求到达 Gateway 前归并路径；不会把用户 Key 改写成其它对象。
* ``ForbidOverwrite`` 只接受字符串 ``"true"`` / ``"false"``。
  ``put_object``、``complete_multipart_upload`` 可通过同名 kwargs 设置；
  ``upload_file``、``upload_file_from_buffer`` 和高层 ``copy`` 的分块路径
  会在最终 Complete 时传入该参数，断点续传也保持本次调用的防覆盖要求。
  ``rename_object`` 使用同名参数，省略时保持服务端默认行为。

这些限制只作用于 Rapid 桶，普通 COS 桶保持原有行为。

预签名注意：

* token 放在 query 的 ``x-cos-security-token`` 并参与签名；网关只接受拆开的
  ``q-sign-algorithm`` / ``q-ak`` / ... 形态，``SignMerged=True`` 会被拒绝。
* ``GET`` / ``HEAD`` 默认申请独立的 ReadOnly session，不复用数据面已缓存的 ReadWrite。
* 实际可用窗口是 ``min(签名窗口, token 剩余寿命, 网关种子剩余寿命)``。
  种子寿命通常不低于 token。

Rapid 响应元数据
~~~~~~~~~~~~~~~~

Rapid 返回响应头的接口（含 ``head_bucket``）继续返回普通 ``dict``，保留服务端原始头名和值，同时提供全部头名的小写别名，以及 SDK 常用的
``ETag``、``Content-Length``、``Last-Modified``、``Content-Type``、``Content-Range`` 等固定键。
例如 ``X-Cos-Request-Id`` 可通过 ``response['x-cos-request-id']`` 读取；``Etag``、``etag``、``ETAG`` 均可通过
``response['ETag']`` 读取。普通 Bucket 的成功响应字典保持原有行为。

HTTP 头部规范化不修改 XML 字段：列表中的 ``LastModified`` 与 HTTP ``Last-Modified`` 分别保留其 ISO 时间和
GMT 时间字符串。SDK 不生成独立的 ``Mtime`` 头，也不把时间或 Content-Length 字符串自动转换成其它类型。
仅解析 XML 或返回 None 的接口保持现有返回契约。

``CosServiceError.get_request_id()`` 和 ``get_trace_id()`` 优先读取已解析的错误信息；缺失时从响应头按不区分
大小写的方式读取，仍缺失则返回 ``Unknown``。空响应体或 XML 解析失败时也能保留响应头中的诊断 ID。

错误 XML 中 ``Resource``、``RequestId`` 或 ``TraceId`` 为空或缺失时，SDK 保留已解析的 ``Code`` 和
``Message``；缺失的 request/trace ID 仍按上述规则从响应头读取。该错误解析行为同时适用于普通 Bucket。
