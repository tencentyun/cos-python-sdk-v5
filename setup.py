from setuptools import setup, find_packages
from platform import python_version_tuple


def requirements():
    """
    Parse the list of pip requirements file.

    Args:
    """

    with open('requirements.txt', 'r') as fileobj:
        requirements = [line.strip() for line in fileobj]
        return requirements


def long_description():
    """
    Return the long description of a string.

    Args:
    """
    with open('README.rst', 'r', encoding='utf8') as fileobj:
        return fileobj.read()


setup(
    name='cos-python-sdk-v5',
    version='1.8.9',
    url='https://www.qcloud.com/',
    license='MIT',
    author='tiedu, lewzylu, channingliu',
    author_email='dutie123@qq.com',
    description='cos-python-sdk-v5',
    long_description=long_description(),
    packages=find_packages(),
    install_requires=requirements()
)
