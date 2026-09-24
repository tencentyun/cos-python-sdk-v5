# -*- coding: utf-8 -*-
"""Exercise the upstream coverage bridge without importing cloud integration tests.

Run with pytest-cov and RAPID_TEST_DEPS_DIR pointing at the locked dependencies.
The same test supports both --cov and --cov-branch.
"""
import ast
import os
import subprocess
import sys

import coverage


def test_rapid_child_coverage():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, 'ut', 'test.py')
    with open(path, 'rb') as stream:
        tree = ast.parse(stream.read(), filename=path)
    # Execute the actual upstream entry, excluding module-level cloud clients.
    tree.body = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name == 'test_rapid_regression']
    assert len(tree.body) == 1
    namespace = dict(os=os, sys=sys, subprocess=subprocess, __file__=path)
    eval(compile(tree, path, 'exec'), namespace)
    active = coverage.Coverage.current()
    assert active is not None, 'Run this test with pytest-cov enabled'
    before = set(active.get_data().lines(os.path.abspath(__file__)) or [])
    namespace['test_rapid_regression']()
    assert before.issubset(set(active.get_data().lines(os.path.abspath(__file__)) or []))
    data = active.get_data()
    # These modules execute only in the child. Imports alone cannot hit 100 lines.
    for name in ('session_auth.py', 'gateway_dns_lb.py'):
        filename = os.path.join(root, 'qcloud_cos', name)
        assert len(data.lines(filename) or []) > 100, name
        if active.get_option('run:branch'):
            assert data.arcs(filename), name
