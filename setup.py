from setuptools import setup, find_packages
from platform import python_version_tuple
import io

def requirements():

    with open('requirements.txt', 'r') as fileobj:
        requirements = [line.strip() for line in fileobj]
        return requirements


def long_description():
    with io.open('README.rst', 'r', encoding='utf8') as fileobj:
        return fileobj.read()


setup(
    name='cos-python-sdk-v5',
    version='1.9.3',
    url='https://www.qcloud.com/',
    license='MIT',
    author='tiedu, lewzylu, channingliu',
    author_email='dutie123@qq.com',
    description='cos-python-sdk-v5',
    long_description=long_description(),
    packages=find_packages(),
    install_requires=requirements()
)
