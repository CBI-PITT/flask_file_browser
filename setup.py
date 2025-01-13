from setuptools import setup, find_packages

setup(
    name='flask_file_browser',
    version='0.1.0',
    description='A Flask extended app blueprint',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Flask>=2.0.0',
        'natsort>=8.4.0'
    ],
)
