"""Setup script for ACP Ingest CLI."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="acp-ingest",
    version="1.0.0",
    author="Analyst Copilot Team",
    author_email="team@analystcopilot.com",
    description="On-premises AI-powered analysis system for processing exported data",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/analystcopilot/acp-ingest",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.11",
    install_requires=[
        "fastapi==0.104.1",
        "uvicorn[standard]==0.24.0",
        "click==8.1.7",
        "rich==13.7.0",
        "httpx==0.25.2",
        "pydantic==2.5.0",
    ],
    entry_points={
        "console_scripts": [
            "acp=app.cli:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "app": ["*.py"],
    },
)

