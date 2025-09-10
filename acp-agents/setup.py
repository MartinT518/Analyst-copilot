"""Setup script for ACP Agents service."""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="acp-agents",
    version="1.0.0",
    author="Analyst Copilot Team",
    author_email="team@analystcopilot.com",
    description="Multi-agent orchestration system for AI-powered analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/analystcopilot/acp-agents",
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
        "langgraph==0.2.16",
        "langchain==0.2.11",
        "langchain-core==0.2.38",
        "langchain-community==0.2.10",
    ],
    entry_points={
        "console_scripts": [
            "acp-agents=app.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "app": ["*.py"],
    },
)

