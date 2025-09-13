# CI/CD Strategy and Local Development Guide

## Overview

This document outlines the CI/CD strategy for the Analyst Copilot project and provides instructions for running the development environment locally.

## CI Pipeline Strategy

### Hybrid Fix Approach

We've implemented a hybrid fix strategy that balances code quality, security, and development velocity:

1. **Ruff for Linting**: Replaced isort with Ruff for faster, more reliable import sorting and linting
2. **Non-blocking Security**: Bandit runs but doesn't block the pipeline (warnings only)
3. **Improved Testing**: Enhanced test fixtures with better mocking and database setup
4. **Database Migrations**: Automated database setup in CI environment

### Pipeline Jobs

1. **Validate Dependencies**: Ensures all packages exist on PyPI
2. **Lint and Format**: Uses Ruff for formatting and linting
3. **Security Scan**: Bandit runs with HIGH severity/confidence only
4. **Tests**: Runs with SQLite fallback and proper mocking
5. **Build**: Docker image building (when needed)

## Local Development Setup

### Prerequisites

- Python 3.11+
- pip-tools
- Git

### Setup Steps

1. **Clone and Install Dependencies**:
   ```bash
   git clone <repository-url>
   cd Analyst-copilot
   pip install -r requirements-dev.txt
   ```

2. **Run Code Quality Checks**:
   ```bash
   # Format code
   ruff format .
   
   # Check linting and imports
   ruff check --fix .
   
   # Run security scan (optional)
   bandit -r . --severity-level high
   ```

3. **Run Tests**:
   ```bash
   # Set test environment
   export TESTING=true
   export USE_SQLITE_FOR_TESTS=true
   
   # Run tests
   pytest acp-ingest/tests/ -v
   ```

4. **Run Services Locally**:
   ```bash
   # Start ingest service
   cd acp-ingest
   uvicorn app.main:app --reload --port 8000
   
   # Start agents service (if needed)
   cd ../acp-agents
   uvicorn app.main:app --reload --port 8001
   ```

## Configuration Files

### Ruff Configuration (pyproject.toml)
- Line length: 100
- Black-compatible formatting
- Comprehensive linting rules

### Bandit Configuration (.bandit)
- Excludes: tests/, migrations/, scripts/
- Severity: HIGH only
- Confidence: HIGH only
- Skips common false positives

### Test Configuration (conftest.py)
- Automatic auth mocking
- External service mocking
- SQLite fallback for tests
- Proper database setup

## Troubleshooting

### Common Issues

1. **Import Sorting Errors**: Run `ruff check --fix .`
2. **Test Failures**: Ensure `TESTING=true` and `USE_SQLITE_FOR_TESTS=true`
3. **Security Warnings**: Check `.bandit` exclusions if needed
4. **Database Issues**: Tests use SQLite by default, no external DB required

### CI Debugging

- Check GitHub Actions logs for specific job failures
- Use `gh run view <run-id> --log-failed` to see detailed error logs
- Security scans are non-blocking - check warnings in logs

## Best Practices

1. **Before Committing**:
   - Run `ruff format .` and `ruff check --fix .`
   - Run tests locally: `pytest acp-ingest/tests/ -v`
   - Check for security issues: `bandit -r . --severity-level high`

2. **Code Quality**:
   - Follow Black formatting (enforced by Ruff)
   - Use type hints where possible
   - Write tests for new functionality

3. **Security**:
   - Review Bandit warnings
   - Use environment variables for secrets
   - Follow secure coding practices

## Future Improvements

1. **Performance**: Consider parallel test execution
2. **Coverage**: Add coverage reporting and thresholds
3. **Integration**: Add integration tests with real services
4. **Monitoring**: Add performance monitoring to CI
