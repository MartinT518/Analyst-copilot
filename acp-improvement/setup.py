"""Setup script for ACP Improvement service."""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="acp-improvement",
    version="1.0.0",
    author="Analyst Copilot Team",
    author_email="team@analystcopilot.com",
    description="AI-powered improvement and optimization service",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/analystcopilot/acp-improvement",
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
        "pydantic==2.9.2",
        "pydantic-settings==2.1.0",
        "tensorflow==2.15.0",
        "keras-tuner==1.4.6",
        "scikit-learn==1.3.2",
    ],
    entry_points={
        "console_scripts": [
            "acp-improvement=app.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "app": ["*.py"],
    },
)
