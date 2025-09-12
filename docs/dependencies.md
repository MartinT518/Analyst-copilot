# Dependency Management Guide

## Overview

The Analyst Copilot project uses a modern dependency management system based on `pip-tools` to ensure reproducible builds, security, and compatibility across Python versions 3.10-3.12.

## File Structure

```
├── requirements.in          # Unpinned production dependencies
├── requirements-dev.in      # Unpinned development dependencies
├── requirements.txt         # Pinned production dependencies (auto-generated)
├── requirements-dev.txt     # Pinned development dependencies (auto-generated)
├── scripts/
│   └── validate_dependencies.py  # Dependency validation script
└── docs/
    └── dependencies.md      # This documentation
```

## How It Works

### 1. Source Files (.in)

- **`requirements.in`**: Contains unpinned production dependencies with flexible version constraints
- **`requirements-dev.in`**: Contains development tools and includes production dependencies via `-r requirements.in`

### 2. Compiled Files (.txt)

- **`requirements.txt`**: Auto-generated with exact pinned versions for production
- **`requirements-dev.txt`**: Auto-generated with exact pinned versions for development

### 3. Compilation Process

```bash
# Install pip-tools
pip install pip-tools

# Compile production dependencies
pip-compile requirements.in

# Compile development dependencies
pip-compile requirements-dev.in
```

## Adding/Updating Dependencies

### ✅ Correct Workflow

1. **Edit source files**: Modify `requirements.in` or `requirements-dev.in`
2. **Validate dependencies**: Run `python scripts/validate_dependencies.py`
3. **Compile**: Run `pip-compile` to update `.txt` files
4. **Test**: Run `pip check` to verify no conflicts
5. **Commit**: Include both `.in` and `.txt` files in your commit

### ❌ What NOT to Do

- ❌ Never edit `requirements.txt` or `requirements-dev.txt` directly
- ❌ Never add unverified packages without checking PyPI
- ❌ Never commit only `.txt` files without corresponding `.in` files

## Validation System

### Automatic Validation

The project includes multiple validation layers:

1. **Pre-commit Hook**: Validates dependencies before each commit
2. **CI Pipeline**: Runs dependency validation in GitHub Actions
3. **Manual Script**: `python scripts/validate_dependencies.py`

### Validation Checks

- ✅ Package exists on PyPI
- ✅ Package has versions compatible with Python 3.10-3.12
- ✅ No circular dependencies
- ✅ No conflicting version constraints

## Security Features

### Dependency Scanning

- **`pip-audit`**: Scans for known security vulnerabilities
- **`safety`**: Additional security checks for dependencies
- **`bandit`**: Security linting for Python code

### Regular Updates

- Dependencies are regularly updated to latest secure versions
- Security vulnerabilities are addressed promptly
- Outdated packages are flagged and updated

## Python Version Compatibility

All dependencies are validated for compatibility with:

- Python 3.10
- Python 3.11
- Python 3.12

## Troubleshooting

### Common Issues

#### 1. Package Not Found on PyPI

```
ERROR: Could not find a version that satisfies the requirement package-name
```

**Solution**: Verify the package name and check if it exists on PyPI

#### 2. Version Conflicts

```
ERROR: Cannot install package-a and package-b because these package versions have conflicting dependencies
```

**Solution**: Update one or both packages to compatible versions

#### 3. Compilation Failures

```
ERROR: No matching distribution found for package
```

**Solution**: Check if the package supports your Python version

### Debugging Commands

```bash
# Check for dependency conflicts
pip check

# Validate all dependencies
python scripts/validate_dependencies.py

# Test compilation without installing
pip-compile --dry-run requirements.in

# Check package availability
pip index versions package-name
```

## Best Practices

### 1. Version Constraints

Use flexible constraints in `.in` files:

```python
# Good
requests>=2.25.0,<3.0.0
pydantic>=2.0.0

# Avoid
requests==2.28.1  # Too specific for .in files
```

### 2. Dependency Groups

- **Production**: Only essential runtime dependencies
- **Development**: Testing, linting, and development tools
- **Optional**: Features that can be disabled

### 3. Regular Maintenance

- Update dependencies monthly
- Review security advisories weekly
- Test compatibility with new Python versions

## CI/CD Integration

### GitHub Actions

The CI pipeline includes:

- Dependency validation job
- Security scanning with `pip-audit` and `safety`
- Compatibility testing across Python versions
- Automatic dependency conflict detection

### Pre-commit Hooks

Automatically runs:

- Dependency validation
- Code formatting (Black, isort)
- Linting (flake8, mypy)
- Security checks (bandit)

## Migration from Old System

If migrating from individual `requirements.txt` files:

1. **Collect dependencies**: Gather all dependencies from service-specific files
2. **Categorize**: Separate production vs development dependencies
3. **Create .in files**: Write flexible constraints
4. **Compile**: Generate new `.txt` files
5. **Validate**: Run validation script
6. **Test**: Verify everything works
7. **Update CI**: Modify GitHub Actions to use new files

## Support

For dependency-related issues:

1. Check this documentation
2. Run validation scripts
3. Review CI logs
4. Create an issue with validation output

## Changelog

- **2024-01-XX**: Implemented pip-tools based dependency management
- **2024-01-XX**: Added comprehensive validation system
- **2024-01-XX**: Integrated with CI/CD pipeline
