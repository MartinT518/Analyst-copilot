"""Setup script for acp-shared-models package."""

from setuptools import find_packages, setup

setup(
    name="acp-shared-models",
    version="1.0.0",
    description="Shared Pydantic models for Analyst Copilot",
    author="Analyst Copilot Team",
    author_email="team@analyst-copilot.com",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "pydantic>=2.9.2",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "ruff>=0.1.6",
            "mypy>=1.7.1",
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
