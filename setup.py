from setuptools import find_packages
from setuptools import setup


setup(
    name='dsdvr',
    version='0.1',
    description='DSDVR video server',
    author='Ben Timby',
    author_email='btimby@gmail.com',
    url='https://github.com/btimby/dsdvr/',
    packages=find_packages(),
    install_requires=[],
    include_package_data=True,
    scripts=['scripts/dsdvr'],
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
)
