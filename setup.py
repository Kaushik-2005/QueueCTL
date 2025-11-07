#!/usr/bin/env python3
"""
QueueCTL Package Setup
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the contents of README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

# Read requirements
requirements = []
requirements_file = this_directory / "requirements.txt"
if requirements_file.exists():
    with open(requirements_file, 'r', encoding='utf-8') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="queuectl",
    version="1.0.0",
    author="Kaushik",
    author_email="queuectl@example.com",
    description="A production-quality CLI-based background job queue system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Kaushik-2005/QueueCTL",
    project_urls={
        "Bug Tracker": "https://github.com/Kaushik-2005/QueueCTL/issues",
        "Documentation": "https://github.com/Kaushik-2005/QueueCTL",
        "Source Code": "https://github.com/Kaushik-2005/QueueCTL",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Distributed Computing",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.8",
        ]
    },
    entry_points={
        "console_scripts": [
            "queuectl=cli.main:main",
        ],
    },
    include_package_data=True,
    keywords="queue, job queue, background jobs, task queue, worker, cli",
    zip_safe=False,
)