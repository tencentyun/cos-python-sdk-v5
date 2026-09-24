# -*- coding: utf-8 -*-
"""Run only credential-free Rapid tests with pinned, isolated dependencies."""
from __future__ import print_function

import io
import os
import re
import sys
import unittest


def canonical(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def main():
    deps_dir = os.path.realpath(sys.argv[1])
    lock_file = sys.argv[2]
    pins = {}
    with io.open(lock_file, encoding='utf-8') as stream:
        for line in stream:
            line = line.split('#', 1)[0].strip()
            if line:
                name, version = line.split('==')
                pins[canonical(name)] = version

    installed = {}
    for entry in os.listdir(deps_dir):
        if not entry.endswith(('.dist-info', '.egg-info')):
            continue
        for filename in ('METADATA', 'PKG-INFO'):
            path = os.path.join(deps_dir, entry, filename)
            if not os.path.isfile(path):
                continue
            name = version = None
            with io.open(path, encoding='utf-8') as stream:
                for line in stream:
                    if line.startswith('Name:'):
                        name = line.split(':', 1)[1].strip()
                    elif line.startswith('Version:'):
                        version = line.split(':', 1)[1].strip()
                    if name and version:
                        installed[canonical(name)] = version
                        break
            break
    for name, version in pins.items():
        if installed.get(name) != version:
            raise RuntimeError('Dependency version mismatch: %s' % name)

    for name in ('requests', 'urllib3', 'certifi', 'chardet', 'idna',
                 'xmltodict', 'six', 'crcmod', 'Crypto'):
        module = __import__(name)
        source = os.path.realpath(module.__file__)
        if not source.startswith(deps_dir + os.sep):
            raise RuntimeError('Dependency imported outside isolated directory: %s' % name)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    import qcloud_cos
    if not os.path.realpath(qcloud_cos.__file__).startswith(root + os.sep):
        raise RuntimeError('SDK imported outside this checkout')
    modules = ('test_session_auth', 'test_gateway_lb', 'test_gateway_lb_integration',
               'test_encryption_rapid', 'test_rapid_advanced')
    # Python 2.7 cannot load these package modules in the same way as Python 3.
    sys.path.insert(0, os.path.join(root, 'ut'))
    suite = unittest.TestSuite()
    for name in modules:
        path = os.path.join(root, 'ut', name + '.py')
        with open(path, 'rb') as stream:
            compile(stream.read(), path, 'exec')
        module = __import__(name)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    if not suite.countTestCases():
        raise RuntimeError('No Rapid tests were discovered')
    print('Python %s; locked dependencies and checkout imports verified' % sys.version.split()[0])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() and not result.skipped else 1


if __name__ == '__main__':
    collector = None
    data_file = os.environ.get('RAPID_COVERAGE_FILE')
    if data_file:
        # -S disables automatic coverage startup. Load only the supplied package,
        # not the parent's site-packages or its SDK dependency versions.
        import imp
        coverage = imp.load_module(
            'coverage', None, os.environ['RAPID_COVERAGE_PACKAGE'],
            ('', '', imp.PKG_DIRECTORY))
        collector = coverage.Coverage(
            data_file=data_file, config_file=False,
            source=[os.path.dirname(os.path.dirname(os.path.abspath(__file__)))],
            branch=os.environ.get('RAPID_COVERAGE_BRANCH') == '1')
        collector.start()
    try:
        sys.exit(main())
    finally:
        if collector is not None:
            collector.stop()
            collector.save()
