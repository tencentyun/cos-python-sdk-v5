# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
from platform import python_version_tuple
import io
import sys


def requirements():
    with open('requirements.txt', 'r') as fileobj:
        requirements = []

        # certifi2021.10.8之后的版本不再支持python2和python3.6之前的版本
        if sys.version_info.major < 3 or \
                (sys.version_info.major == 3 and sys.version_info.minor < 6):
            requirements.append('certifi<=2021.10.8')

        # requests2.27.1之后的版本不再支持python2和python3.7之前的版本
        if sys.version_info.major < 3 or \
                (sys.version_info.major == 3 and sys.version_info.minor < 7):
            requirements.append('requests>=2.8,<=2.27.1')
        else:
            requirements.append('requests>=2.8')

        requirements.extend([line.strip() for line in fileobj])
        return requirements


def long_description():
    with io.open('README.rst', 'r', encoding='utf8') as fileobj:
        return fileobj.read()


setup(
    name='cos-python-sdk-v5',
    version='1.9.21',
    url='https://www.qcloud.com/',
    license='MIT',
    author='tiedu, lewzylu, channingliu',
    author_email='dutie123@qq.com',
    description='cos-python-sdk-v5',
    long_description=long_description(),
    packages=find_packages(),
    install_requires=requirements()
)
