# -*- coding: utf-8 -*-
"""进程内 HTTP Rapid Gateway DNS 快照。仅供 SDK 内部使用。"""

import logging
import os
import random
import socket
import threading
import time


logger = logging.getLogger(__name__)

_IDLE_TTL = 10 * 60
_COLD_WAIT_TIMEOUT = 10.0
_monotonic = getattr(time, 'monotonic', time.time)
_condition = threading.Condition()
_states = {}
_pid = os.getpid()
_thread = None
_pid_locks = {}


def _reset_after_fork():
    """PID 变化时不能接触父进程继承的锁。"""
    global _condition, _states, _pid, _thread, _pid_locks
    pid = os.getpid()
    if pid == _pid:
        return
    lock = _pid_locks.get(pid)
    if lock is None:
        lock = _pid_locks.setdefault(pid, threading.Lock())
    with lock:
        if pid != _pid:
            _condition = threading.Condition()
            _states = {}
            _thread = None
            _pid = pid
            _pid_locks = {pid: lock}


def _resolve_nodes(host, port):
    try:
        infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    except Exception as error:
        logger.warning('Gateway DNS resolve failed for %s:%s: %s', host, port, error)
        return ()

    nodes = []
    seen = set()
    for info in infos:
        address = info[4]
        if not address:
            continue
        node = (address[0], address[1])
        if node not in seen:
            seen.add(node)
            nodes.append(node)
    if not nodes:
        logger.warning('Gateway DNS resolve returned no nodes for %s:%s', host, port)
    return tuple(nodes)


def _start_thread_locked():
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(target=_refresh_loop, name='cos-gateway-dns-lb')
    _thread.daemon = True
    _thread.start()


def _publish_locked(key, state, nodes, now):
    old_nodes = state['nodes']
    if nodes:
        state['nodes'] = nodes
        if nodes != old_nodes:
            logger.info('Gateway DNS snapshot changed for %s:%s: %s',
                        key[0], key[1], nodes)
    state['next_refresh'] = now + state['interval']
    state['resolving'] = False
    _condition.notify_all()


def ensure_snapshot(host, port, interval):
    """注册 key；冷启动按 key 同步单飞解析，返回不可变节点快照。"""
    _reset_after_fork()
    interval = max(1.0, float(interval))
    key = (host, port)
    state = None
    should_resolve = False

    with _condition:
        now = _monotonic()
        state = _states.get(key)
        if state is None:
            state = {
                'nodes': (),
                'next_refresh': now,
                'last_seen': now,
                'interval': interval,
                'resolving': True,
            }
            _states[key] = state
            should_resolve = True
            _start_thread_locked()
            _condition.notify_all()
        else:
            state['last_seen'] = now
            if interval < state['interval']:
                state['interval'] = interval
                state['next_refresh'] = min(state['next_refresh'], now + interval)
                _condition.notify_all()
            if state['nodes']:
                return state['nodes']
            if not state['resolving'] and now >= state['next_refresh']:
                state['resolving'] = True
                should_resolve = True
            elif state['resolving']:
                deadline = _monotonic() + _COLD_WAIT_TIMEOUT
                while state['resolving'] and not state['nodes']:
                    remaining = deadline - _monotonic()
                    if remaining <= 0:
                        logger.warning(
                            'Gateway DNS cold resolve wait timed out for %s:%s',
                            host, port)
                        break
                    _condition.wait(remaining)
                return state['nodes']
            else:
                return state['nodes']

    if should_resolve:
        nodes = _resolve_nodes(host, port)
        with _condition:
            current = _states.get(key)
            if current is state:
                _publish_locked(key, state, nodes, _monotonic())
                return state['nodes']
    return ()


def pick_node(nodes, excluded=None):
    """从请求提供的不可变快照中均匀随机选一个尚未失败的节点。"""
    if excluded:
        nodes = tuple(node for node in nodes if node not in excluded)
    if not nodes:
        return None
    return random.choice(nodes)


def _evict_idle_locked(now):
    for key, state in list(_states.items()):
        if not state['resolving'] and now - state['last_seen'] >= _IDLE_TTL:
            del _states[key]


def _refresh_loop():
    while True:
        _reset_after_fork()
        key = None
        state = None
        with _condition:
            while key is None:
                now = _monotonic()
                _evict_idle_locked(now)
                if not _states:
                    _condition.wait()
                    continue

                wake_at = None
                for candidate_key, candidate in _states.items():
                    if candidate['resolving']:
                        continue
                    if candidate['next_refresh'] <= now:
                        candidate['resolving'] = True
                        key = candidate_key
                        state = candidate
                        break
                    candidate_wake = min(
                        candidate['next_refresh'],
                        candidate['last_seen'] + _IDLE_TTL)
                    if wake_at is None or candidate_wake < wake_at:
                        wake_at = candidate_wake
                if key is None:
                    if wake_at is None:
                        _condition.wait()
                    else:
                        _condition.wait(max(0.0, wake_at - now))

        nodes = _resolve_nodes(key[0], key[1])
        with _condition:
            current = _states.get(key)
            if current is state:
                _publish_locked(key, state, nodes, _monotonic())
