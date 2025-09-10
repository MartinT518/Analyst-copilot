"""Setup script for ACP Code Analyzer service."""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="acp-code-analyzer",
    version="1.0.0",
    author="Analyst Copilot Team",
    author_email="team@analystcopilot.com",
    description="AI-powered code analysis and understanding service",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/analystcopilot/acp-code-analyzer",
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
        "ast-tools==0.1.8",
        "tree-sitter==0.20.4",
        "tree-sitter-python==0.21.0",
    ],
    entry_points={
        "console_scripts": [
            "acp-code-analyzer=app.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "app": ["*.py"],
    },
)
