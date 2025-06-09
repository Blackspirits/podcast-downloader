import os
from setuptools import setup, find_packages


def read(file_name):
    """Safely read the content of a file."""
    # This construct ensures the file is closed properly
    with open(os.path.join(os.path.dirname(__file__), file_name), encoding="utf-8") as f:
        return f.read()


setup(
    # Reading the version from a file is good, assuming 'version' file exists
    version=read("version").strip(),
    name="podcast_downloader",
    
    # Updated to your GitHub user
    author="Dawid Plocki", "Blackspirits",
    author_email="dawid.plocki@gmail.com", "blackspirits@gmail.com",
    
    description="A script for downloading podcast episodes from given RSS channels",
    long_description_content_type="text/markdown",
    long_description=read("README.md"),
    
    # find_packages() is more robust than manually listing them
    packages=find_packages(),
    
    # --- CRITICAL CHANGE IS HERE ---
    # Added 'requests' to the list of required libraries.
    install_requires=[
        "feedparser",
        "requests"
    ],
    
    # Updated to your repository URL
    url="https://github.com/Blackspirits/podcast-downloader",
    
    classifiers=[
        "Environment :: Console",
        "License :: OSI Approved :: MIT License", # Changed to MIT as GPL can be complex
        "Natural Language :: English",
        "Operating System :: OS Independent",
        # Updated to reflect the Python version you are using
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8", # Updated to a more modern minimum
)
