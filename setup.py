import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="django-qns",
    version="0.0.1",
    author="Yuan",
    author_email="",
    description="add qiniuyun storage support for Django",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/YuanBLQ/django-qns",
    packages=setuptools.find_packages(),
    install_requires=['request>=2.5.0', 'qiniu>=7.2.6'],
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)
