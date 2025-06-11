import os
from setuptools import setup


def read(file_name):
    return open(os.path.join(os.path.dirname(__file__), file_name)).read()

# Function to read dependencies from requirements.txt
def read_requirements():
    with open('requirements.txt', 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    version=read("version"),
    name="podcast_downloader",
    author="Dawid Plocki",
    author_email="dawid.plocki@gmail.com",
    description="The script for downloading recent media files from given RSS channels",
    long_description_content_type="text/markdown",
    long_description=read("README.md"),
    packages=["podcast_downloader"],
    install_requires=read_requirements(), # Use the new function to read requirements
    url="https://github.com/dplocki/podcast-downloader",
    classifiers=[
        "Environment :: Console",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.12",
)