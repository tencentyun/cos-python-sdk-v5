# -*- coding=utf-8
"""高性能桶（COS Rapid Bucket / fusion-io）session 鉴权。

对照 cos-go-sdk-v5 session_auth，并按 2026-08-18 review 修复：
- C1: CreateSession 契约为 AWS 兼容 XML；历史 proxy JSON 仅作过渡兼容
- H1: 数据面 403 按桶 evict 后强制刷新，带防抖
- M1: 支持 x-cos-create-session-mode
- L1: CreateSession 独立超时
"""

import json
import logging
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from six import text_type, binary_type

from .cos_comm import to_unicode, format_bucket
from .cos_exception import CosClientError

logger = logging.getLogger(__name__)

RAPID_BUCKET_RE = re.compile(r'^[a-z0-9][a-z0-9-]*-x--[0-9]+$')
RAPID_HOST_SUFFIX = (u'myqcloud', u'com')
RAPID_REGIONS = frozenset((
    u'ap-guangzhou', u'ap-shanghai', u'ap-hongkong', u'ap-beijing',
    u'ap-singapore', u'na-siliconvalley', u'ap-chengdu', u'eu-frankfurt',
    u'ap-seoul', u'ap-chongqing', u'na-ashburn', u'ap-bangkok',
    u'ap-tokyo', u'ap-nanjing', u'ap-tianjin', u'ap-shenzhen',
    u'ap-taipei', u'sl-saopaulo', u'ap-others', u'ap-qingyuan',
    u'ap-jakarta', u'sa-saopaulo', u'ap-guiyang', u'me-saudi-arabia',
    u'ap-zhongwei', u'na-queretaro', u'ap-johorbahru', u'ap-osaka',
))
_RAPID_REGION_ALIASES = {
    u'cosgz': u'ap-guangzhou',
    u'cossh': u'ap-shanghai',
    u'cosbj': u'ap-beijing',
    u'coscd': u'ap-chengdu',
    u'cossgp': u'ap-singapore',
    u'coshk': u'ap-hongkong',
    u'cosger': u'eu-frankfurt',
}
DEFAULT_SESSION_REFRESH_BEFORE = 60
DEFAULT_CREATE_SESSION_TIMEOUT = 30
DEFAULT_EVICT_DEBOUNCE = 1
SESSION_MODE_READ_WRITE = u'ReadWrite'
SESSION_MODE_READ_ONLY = u'ReadOnly'
VALID_SESSION_MODES = (SESSION_MODE_READ_WRITE, SESSION_MODE_READ_ONLY)


def is_rapid_bucket(bucket_name):
    """判断桶名是否为高性能桶 <short>-x--<appId>。"""
    if bucket_name is None:
        return False
    name = to_unicode(bucket_name).strip()
    if name != name.lower():
        return False
    if len(name) < 3 or len(name) > 63:
        return False
    return RAPID_BUCKET_RE.match(name) is not None


def normalize_rapid_region(region):
    if not region:
        return u''
    region = to_unicode(region).strip().lower()
    region = _RAPID_REGION_ALIASES.get(region, region)
    return region if region in RAPID_REGIONS else u''


def rapid_endpoint_for_region(region):
    raw_region = region
    region = normalize_rapid_region(raw_region)
    if not region:
        raise CosClientError(
            'rapid bucket domain does not support region %r' % raw_region)
    return u'cosrapid.%s.myqcloud.com' % region


def rapid_service_domain_for_region(region):
    raw_region = region
    region = normalize_rapid_region(raw_region)
    if not region:
        raise CosClientError(
            'rapid service domain does not support region %r' % raw_region)
    return u'service.cosrapid.%s.myqcloud.com' % region


def _normalized_host(host):
    if not host:
        return u''
    host = to_unicode(host).strip()
    if host != host.lower() or host.endswith(u'.'):
        return u''
    if host.startswith(u'[') or u':' in host:
        return u''
    return host


def parse_bucket_name_from_host(host):
    """从 <bucket>.cosrapid.<ap-code>.myqcloud.com 解析桶名。"""
    labels = _normalized_host(host).split(u'.')
    if (len(labels) != 5 or labels[1] != u'cosrapid'
            or tuple(labels[3:]) != RAPID_HOST_SUFFIX):
        return u''
    if labels[2] not in RAPID_REGIONS:
        return u''
    return labels[0] if is_rapid_bucket(labels[0]) else u''


def rapid_region_from_host(host):
    labels = _normalized_host(host).split(u'.')
    if (len(labels) == 4 and labels[0] == u'cosrapid'
            and tuple(labels[2:]) == RAPID_HOST_SUFFIX):
        host_region = labels[1]
    elif (len(labels) == 5 and labels[1] == u'cosrapid'
          and tuple(labels[3:]) == RAPID_HOST_SUFFIX
          and (labels[0] == u'service' or is_rapid_bucket(labels[0]))):
        host_region = labels[2]
    else:
        return u''
    if host_region not in RAPID_REGIONS:
        return u''
    return host_region


def host_looks_rapid(host, region=None):
    host_region = rapid_region_from_host(host)
    if not host_region:
        return False
    if region:
        expected = normalize_rapid_region(region)
        return bool(expected) and host_region == expected
    return True


def endpoint_looks_rapid(host, region=None):
    labels = _normalized_host(host).split(u'.')
    if (len(labels) != 4 or labels[0] != u'cosrapid'
            or tuple(labels[2:]) != RAPID_HOST_SUFFIX):
        return False
    return host_looks_rapid(host, region)


def normalize_session_mode(mode, default=SESSION_MODE_READ_WRITE):
    if mode is None or mode == u'':
        return default
    mode = to_unicode(mode)
    if mode not in VALID_SESSION_MODES:
        raise CosClientError(
            'x-cos-create-session-mode must be ReadWrite or ReadOnly, got %r' % mode)
    return mode


def _mode_covers(cached_mode, requested):
    """ReadWrite 覆盖 ReadOnly；ReadOnly 不能用于写请求。"""
    cached_mode = cached_mode or SESSION_MODE_READ_WRITE
    requested = requested or SESSION_MODE_READ_WRITE
    if requested == SESSION_MODE_READ_WRITE:
        return cached_mode == SESSION_MODE_READ_WRITE
    return cached_mode in VALID_SESSION_MODES


def _first_text(*values):
    for value in values:
        if value is None:
            continue
        text = _to_text(value).strip()
        if text:
            return text
    return u''


def _to_text(value):
    if value is None:
        return u''
    if isinstance(value, binary_type):
        return value.decode('utf-8')
    return to_unicode(value)


def parse_expiration(expiration, expired_time=None):
    """解析 RFC3339 Expiration 或 unix ExpiredTime，返回 naive UTC datetime。"""
    if expiration:
        text = _to_text(expiration).strip()
        if text:
            match = re.match(
                r'^(.*?)(Z|([+-])(\d{2}):(\d{2}))$', text)
            if match:
                value = match.group(1)
                parsed = None
                for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f'):
                    try:
                        parsed = datetime.strptime(value, fmt)
                        break
                    except ValueError:
                        continue
                if parsed is not None:
                    if match.group(2) == u'Z':
                        return parsed
                    hours = int(match.group(4))
                    minutes = int(match.group(5))
                    if hours <= 23 and minutes <= 59:
                        offset = timedelta(hours=hours, minutes=minutes)
                        return (parsed - offset if match.group(3) == u'+'
                                else parsed + offset)
            else:
                # 兼容旧版曾接受的无时区 ISO 时间；按既有语义视为 UTC。
                for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f'):
                    try:
                        return datetime.strptime(text, fmt)
                    except ValueError:
                        continue
    if expired_time not in (None, u'', 0, '0'):
        try:
            return datetime.utcfromtimestamp(int(expired_time))
        except (TypeError, ValueError, OverflowError):
            pass
    return None


class SessionCredential(object):
    def __init__(self, secret_id, secret_key, session_token, expiration, mode=None):
        self.secret_id = _to_text(secret_id)
        self.secret_key = _to_text(secret_key)
        self.session_token = _to_text(session_token)
        self.expiration = expiration
        self.mode = mode or SESSION_MODE_READ_WRITE

    def remaining(self, now=None):
        if self.expiration is None:
            return None
        if now is None:
            now = datetime.utcnow()
        return (self.expiration - now).total_seconds()

    def covers(self, min_remaining, now=None):
        left = self.remaining(now)
        if left is None:
            return False
        return left > min_remaining


def _xml_local(tag):
    if tag is None:
        return u''
    if u'}' in tag:
        return tag.rsplit(u'}', 1)[-1]
    return tag


def _xml_child_text(parent, name):
    if parent is None:
        return u''
    for child in list(parent):
        if _xml_local(child.tag) == name:
            return _to_text(child.text).strip() if child.text else u''
    return u''


def parse_create_session_result(body):
    """解析 CreateSession 响应。契约为 AWS 兼容 XML；JSON 仅兼容历史 proxy。"""
    if body is None:
        raise CosClientError('CreateSession response is empty')
    raw = body
    if isinstance(body, binary_type):
        text = body.decode('utf-8')
    else:
        text = to_unicode(body)
    stripped = text.strip()
    if not stripped:
        raise CosClientError('CreateSession response is empty')

    cred = None
    extra = {}
    if stripped[0] == u'<':
        cred, extra = _parse_xml_session(stripped)
    elif stripped[0] == u'{':
        cred, extra = _parse_json_session(stripped)
    else:
        raise CosClientError(
            'CreateSession response is neither XML nor JSON: %r' % stripped[:80])

    if not cred.secret_id or not cred.secret_key or not cred.session_token:
        raise CosClientError('CreateSession response credentials are incomplete')
    if cred.expiration is None:
        raise CosClientError('session credential expiration is missing')
    extra['credential'] = cred
    extra['raw'] = raw
    return extra


def _parse_json_session(text):
    try:
        data = json.loads(text)
    except ValueError as e:
        raise CosClientError('CreateSession JSON decode failed: %s' % e)
    credentials = data.get('Credentials') or {}
    if not isinstance(credentials, dict):
        credentials = {}
    secret_id = _first_text(
        credentials.get('TmpSecretId'), credentials.get('AccessKeyId'),
        credentials.get('SecretId'), data.get('TmpSecretId'), data.get('AccessKeyId'))
    secret_key = _first_text(
        credentials.get('TmpSecretKey'), credentials.get('SecretAccessKey'),
        credentials.get('SecretKey'), data.get('TmpSecretKey'), data.get('SecretAccessKey'))
    token = _first_text(
        credentials.get('Token'), credentials.get('SessionToken'),
        data.get('Token'), data.get('SessionToken'))
    expiration = parse_expiration(
        data.get('Expiration') or credentials.get('Expiration'),
        data.get('ExpiredTime') if data.get('ExpiredTime') is not None else credentials.get('ExpiredTime'))
    cred = SessionCredential(secret_id, secret_key, token, expiration)
    return cred, {
        'ExpiredTime': data.get('ExpiredTime'),
        'Expiration': data.get('Expiration'),
        'RequestId': data.get('RequestId') or data.get('RequestID'),
    }


def _parse_xml_session(text):
    try:
        root = ET.fromstring(text.encode('utf-8') if isinstance(text, text_type) else text)
    except ET.ParseError as e:
        raise CosClientError('CreateSession XML decode failed: %s' % e)
    cred_node = None
    if _xml_local(root.tag) == u'Credentials':
        cred_node = root
    else:
        for child in list(root):
            if _xml_local(child.tag) == u'Credentials':
                cred_node = child
                break
    secret_id = _xml_child_text(cred_node, u'AccessKeyId') or _xml_child_text(cred_node, u'TmpSecretId')
    secret_key = _xml_child_text(cred_node, u'SecretAccessKey') or _xml_child_text(cred_node, u'TmpSecretKey')
    token = _xml_child_text(cred_node, u'SessionToken') or _xml_child_text(cred_node, u'Token')
    expiration_text = _xml_child_text(cred_node, u'Expiration') or _xml_child_text(root, u'Expiration')
    expired_time = _xml_child_text(root, u'ExpiredTime')
    expiration = parse_expiration(expiration_text, expired_time or None)
    cred = SessionCredential(secret_id, secret_key, token, expiration)
    return cred, {
        'ExpiredTime': expired_time,
        'Expiration': expiration_text,
        'RequestId': _xml_child_text(root, u'RequestId') or _xml_child_text(root, u'RequestID'),
    }


class _BucketSession(object):
    def __init__(self):
        self.lock = threading.Lock()
        self.cred = None
        self.base_ak = u''
        # GET/HEAD 预签名专用 ReadOnly 槽，不复用数据面 ReadWrite。
        self.presign_ro_cred = None
        self.presign_ro_base_ak = u''
        self.last_evict = 0.0


class CreateSessionProvider(object):
    """按桶缓存 session 凭证：单飞刷新、baseAK 指纹、刷新失败降级、403 evict 防抖。"""

    def __init__(self, create_fn, base_secret_id_fn,
                 refresh_before=DEFAULT_SESSION_REFRESH_BEFORE,
                 evict_debounce=DEFAULT_EVICT_DEBOUNCE):
        self._create_fn = create_fn
        self._base_secret_id_fn = base_secret_id_fn
        self.refresh_before = refresh_before
        self.evict_debounce = evict_debounce
        self._lock = threading.Lock()
        self._buckets = {}
        self._pid = os.getpid()
        self._pid_locks = {}

    def _reset_after_fork(self):
        """新 PID 使用新锁和缓存，不能接触父进程可能处于 locked 的锁。"""
        pid = os.getpid()
        if pid == self._pid:
            return
        lock = self._pid_locks.get(pid)
        if lock is None:
            lock = self._pid_locks.setdefault(pid, threading.Lock())
        with lock:
            if pid != self._pid:
                self._lock = threading.Lock()
                self._buckets = {}
                self._pid = pid
                self._pid_locks = {pid: lock}

    def _bucket(self, bucket_name):
        self._reset_after_fork()
        with self._lock:
            session = self._buckets.get(bucket_name)
            if session is None:
                session = _BucketSession()
                self._buckets[bucket_name] = session
            return session

    def evict(self, bucket_name, now=None, force=False):
        """淘汰缓存。防抖成功返回 True，应随后强制 CreateSession。"""
        if now is None:
            now = time.time()
        session = self._bucket(bucket_name)
        with session.lock:
            if not force and (now - session.last_evict) < self.evict_debounce:
                return False
            session.cred = None
            session.base_ak = u''
            session.presign_ro_cred = None
            session.presign_ro_base_ak = u''
            session.last_evict = now
            return True

    def get_credential(self, bucket_name, mode=None, reuse_window=None, force_refresh=False):
        if reuse_window is None:
            reuse_window = self.refresh_before
        session = self._bucket(bucket_name)
        with session.lock:
            base_ak = _to_text(self._base_secret_id_fn() or u'')
            requested = normalize_session_mode(mode, default=SESSION_MODE_READ_WRITE)
            if (not force_refresh and session.cred is not None
                    and session.base_ak == base_ak
                    and session.cred.covers(reuse_window)
                    and _mode_covers(session.cred.mode, requested)):
                return session.cred
            try:
                result = self._create_fn(bucket_name, requested)
                cred = result['credential'] if isinstance(result, dict) and 'credential' in result else result
                cred.mode = requested
                session.cred = cred
                session.base_ak = base_ak
                return cred
            except Exception:
                if (session.cred is not None and session.base_ak == base_ak
                        and session.cred.covers(0)):
                    logger.warning('CreateSession failed, reuse unexpired cached credential for %s',
                                   bucket_name)
                    return session.cred
                raise

    def _get_presign_readonly(self, bucket_name, reuse_window):
        """只读写 ReadOnly 预签名槽，不命中数据面的 ReadWrite 缓存。"""
        session = self._bucket(bucket_name)
        with session.lock:
            base_ak = _to_text(self._base_secret_id_fn() or u'')
            if (session.presign_ro_cred is not None
                    and session.presign_ro_base_ak == base_ak
                    and session.presign_ro_cred.covers(reuse_window)
                    and session.presign_ro_cred.mode == SESSION_MODE_READ_ONLY):
                return session.presign_ro_cred
            try:
                result = self._create_fn(bucket_name, SESSION_MODE_READ_ONLY)
                cred = result['credential'] if isinstance(result, dict) and 'credential' in result else result
                cred.mode = SESSION_MODE_READ_ONLY
                session.presign_ro_cred = cred
                session.presign_ro_base_ak = base_ak
                return cred
            except Exception:
                if (session.presign_ro_cred is not None
                        and session.presign_ro_base_ak == base_ak
                        and session.presign_ro_cred.covers(0)
                        and session.presign_ro_cred.mode == SESSION_MODE_READ_ONLY):
                    logger.warning(
                        'CreateSession failed, reuse unexpired ReadOnly presign credential for %s',
                        bucket_name)
                    return session.presign_ro_cred
                raise

    def fresh_credential(self, bucket_name, min_remaining, mode=None, isolated_readonly=False):
        if min_remaining is None:
            raise CosClientError('session presign required lifetime is missing')
        if min_remaining <= 0:
            raise CosClientError('session presign expired time must be positive')
        requested = normalize_session_mode(mode, default=SESSION_MODE_READ_WRITE)
        if isolated_readonly and requested == SESSION_MODE_READ_ONLY:
            cred = self._get_presign_readonly(bucket_name, reuse_window=min_remaining)
        else:
            cred = self.get_credential(bucket_name, mode=requested, reuse_window=min_remaining)
        if cred.expiration is None:
            raise CosClientError('session credential expiration is missing')
        if not cred.covers(min_remaining):
            raise CosClientError(
                'session credential lifetime (until %s) is shorter than required %ss' % (
                    cred.expiration.strftime('%Y-%m-%dT%H:%M:%SZ'), int(min_remaining)))
        return cred


def resolve_session_bucket(conf, bucket):
    """规范化桶名并判断是否应对该桶启用 session。"""
    appid = getattr(conf, '_appid', None)
    name = format_bucket(bucket, appid) if bucket else u''
    return name, is_rapid_bucket(name)


def conf_rapid_host(conf):
    region = getattr(conf, '_region', None)
    endpoint = getattr(conf, '_endpoint', None)
    if endpoint_looks_rapid(endpoint, region):
        return True
    domain = getattr(conf, '_domain', None)
    return bool(parse_bucket_name_from_host(domain)) and host_looks_rapid(
        domain, region)


def should_use_session_auth(conf, bucket):
    """auto：rapid 桶且 endpoint/domain 符合 Rapid 域名，或显式开启。"""
    flag = getattr(conf, '_enable_session_auth', None)
    _name, rapid = resolve_session_bucket(conf, bucket)
    if not rapid:
        return False
    if flag is False:
        return False
    if flag is True:
        return True
    return conf_rapid_host(conf) or bool(getattr(conf, '_enable_rapid_domain', False))


def require_session_ready(conf, bucket):
    """L3：高性能桶数据面必须启用 session，否则本地 fail-fast。"""
    name, rapid = resolve_session_bucket(conf, bucket)
    if not rapid:
        return False
    if should_use_session_auth(conf, bucket):
        return True
    raise CosClientError(
        'rapid bucket %s requires session auth: set EnableSessionAuth=True, '
        'EnableRapidDomain=True, or use an Endpoint/Domain such as '
        '<bucket>.cosrapid.<region>.myqcloud.com. '
        '(COS Rapid Bucket / fusion-io)' % name)
