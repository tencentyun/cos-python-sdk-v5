from setuptools import setup, find_packages
from platform import python_version_tuple


def requirements():

    with open('requirements.txt', 'r') as fileobj:
        requirements = [line.strip() for line in fileobj]
        return requirements


def long_description():
    with open('README.rst', 'r') as fileobj:
        return fileobj.read()


setup(
    name='cos-python-sdk-v5-python3',
    version='1.4.0',
    url='https://wyue.name',
    license='MIT',
    author='YueWang',
    author_email='15118421@bjtu.edu.cn',
    description='cos-python-sdk-v5-python3',
    long_description=long_description(),
    packages=find_packages(),
    install_requires=requirements()
)
