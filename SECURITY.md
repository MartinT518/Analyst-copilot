# Security Policy

## Overview

This document outlines the security practices, policies, and procedures for the Analyst Copilot project. It covers security scanning, vulnerability management, and secure coding practices.

## Security Scanning

### Bandit Security Scanner

We use [Bandit](https://bandit.readthedocs.io/) to perform static security analysis on our Python codebase. Bandit is integrated into our CI/CD pipeline and runs on every pull request.

#### Bandit Configuration

- **Configuration File**: `.bandit` in the `acp-ingest/` directory
- **Excluded Directories**: `tests`, `venv`, `env`, `.venv`, `.env`
- **Skipped Rules**: `B105`, `B106` (hardcoded password false positives for metrics and audit events)

#### Security Rules Enforcement

| Rule ID | Description | Status | Justification |
|---------|-------------|--------|---------------|
| B104 | Hardcoded bind all interfaces | ✅ Enforced | Use `127.0.0.1` by default, configurable via `SERVER_HOST` |
| B105 | Hardcoded password string | ✅ Enforced | All secrets must come from environment variables or Vault |
| B106 | Hardcoded password funcarg | ✅ Enforced | Exception: Metric labels like "prompt", "completion" |
| B108 | Hardcoded tmp directory | ✅ Enforced | Use `tempfile.gettempdir()` instead of `/tmp` |
| B110 | Try except pass | ✅ Enforced | All exceptions must be properly handled and logged |
| B311 | Standard pseudo-random generators | ✅ Enforced | Use `secrets` module for cryptographic operations |
| B314 | XML parsing vulnerabilities | ✅ Enforced | Use `defusedxml` instead of `xml.etree.ElementTree` |
| B404 | Subprocess module usage | ✅ Enforced | Validate and sanitize all subprocess inputs |
| B405 | XML parsing vulnerabilities | ✅ Enforced | Use `defusedxml` instead of `xml.etree.ElementTree` |

#### Suppressed Rules with #nosec

The following rules are intentionally suppressed with `#nosec` comments:

1. **B105** - Hardcoded password strings in configuration validation
   - **Location**: `app/config.py:352`
   - **Justification**: String comparison for validation, not actual password storage

2. **B106** - Hardcoded password funcargs in metrics
   - **Location**: `app/observability/metrics.py:362,369`
   - **Justification**: Metric labels "prompt" and "completion" are not passwords

3. **B105** - Audit event names
   - **Location**: `app/services/audit_service.py:23,24`
   - **Justification**: Event names like "auth.token.refresh" are not passwords

4. **B404** - Subprocess usage in code parser
   - **Location**: `app/parsers/code_parser.py:4`
   - **Justification**: Controlled execution of IntelliJ inspect.sh tool

## Security Practices

### 1. Secrets Management

#### Environment Variables
All sensitive configuration must be provided via environment variables:

```bash
# Required secrets (system will fail to start if not provided)
SECRET_KEY=your-secure-secret-key-change-this-in-production
JWT_SECRET_KEY=your-jwt-secret-key-change-this-in-production
ENCRYPTION_KEY=your-encryption-key-change-this-in-production

# OAuth2 configuration
OAUTH2_CLIENT_ID=your-oauth2-client-id
OAUTH2_CLIENT_SECRET=your-oauth2-client-secret
OAUTH2_AUTHORIZATION_URL=https://your-auth-provider.com/oauth/authorize
OAUTH2_TOKEN_URL=https://your-auth-provider.com/oauth/token
OAUTH2_USERINFO_URL=https://your-auth-provider.com/oauth/userinfo
OAUTH2_REDIRECT_URI=http://localhost:3000/auth/callback
```

#### Vault Integration
For production environments, use HashiCorp Vault for secrets management:

```bash
VAULT_URL=https://vault.example.com
VAULT_TOKEN=your-vault-token
VAULT_NAMESPACE=acp
VAULT_MOUNT_POINT=secret
VAULT_AUTH_METHOD=token
```

### 2. Network Security

#### Bind Address Configuration
- **Development**: Default to `127.0.0.1` (localhost only)
- **Production**: Configurable via `SERVER_HOST` environment variable
- **Docker**: Use `0.0.0.0` only within containerized environments

#### CORS Configuration
- **Development**: Allow `http://localhost:3000`, `http://localhost:5173`
- **Production**: Restrict to specific domains only
- **Never use**: `"*"` wildcard in production

### 3. Data Security

#### XML Processing
- **Use**: `defusedxml.ElementTree` instead of `xml.etree.ElementTree`
- **Reason**: Prevents XML bomb and external entity attacks
- **Implementation**: All XML parsing uses defusedxml

#### Temporary Files
- **Use**: `tempfile.gettempdir()` instead of hardcoded `/tmp`
- **Cleanup**: Automatic cleanup after use
- **Permissions**: Secure file permissions

### 4. Authentication & Authorization

#### OAuth2/OIDC
- **Provider**: Compatible with Keycloak, Auth0, etc.
- **Flow**: Authorization Code flow with PKCE
- **Tokens**: JWT with proper expiration and refresh

#### Default Admin User
- **Creation**: Via bootstrap script, not hardcoded
- **Password**: Strong random password generated
- **Documentation**: Bootstrap process documented in README

### 5. Error Handling

#### Exception Management
- **No bare `except:`**: All exceptions must be caught and handled
- **Logging**: All errors must be logged with context
- **User-facing**: Generic error messages, detailed logs for debugging

## Vulnerability Management

### Reporting Security Issues

If you discover a security vulnerability, please report it responsibly:

1. **Do not** create a public GitHub issue
2. **Email**: security@analyst-copilot.com (if available)
3. **Include**: Detailed description, steps to reproduce, potential impact

### Security Updates

- **Dependencies**: Regular updates via Dependabot
- **Security Patches**: Applied within 48 hours of release
- **Critical Vulnerabilities**: Immediate attention and patching

### Security Testing

#### Automated Testing
- **Bandit**: Static analysis on every commit
- **Safety**: Dependency vulnerability scanning
- **Semgrep**: Additional security pattern detection

#### Manual Testing
- **Penetration Testing**: Quarterly security assessments
- **Code Review**: All security-related changes require review
- **Access Control**: Regular access audits

## Compliance

### Security Standards
- **OWASP Top 10**: Protection against common vulnerabilities
- **CWE**: Common Weakness Enumeration compliance
- **NIST**: Cybersecurity Framework alignment

### Data Protection
- **PII Detection**: Automatic detection and masking
- **Encryption**: Data encrypted in transit and at rest
- **Access Logs**: Comprehensive audit logging

## Incident Response

### Security Incident Process
1. **Detection**: Automated monitoring and alerting
2. **Assessment**: Impact and severity evaluation
3. **Containment**: Immediate threat isolation
4. **Eradication**: Root cause removal
5. **Recovery**: System restoration
6. **Lessons Learned**: Process improvement

### Contact Information
- **Security Team**: security@analyst-copilot.com
- **Emergency**: +1-XXX-XXX-XXXX (if available)
- **Status Page**: https://status.analyst-copilot.com (if available)

## Security Checklist

### Development
- [ ] No hardcoded secrets in code
- [ ] All inputs validated and sanitized
- [ ] Error handling implemented
- [ ] Security tests written
- [ ] Bandit scan passes

### Deployment
- [ ] Secrets configured via environment variables
- [ ] SSL/TLS enabled
- [ ] CORS properly configured
- [ ] Security headers set
- [ ] Monitoring enabled

### Maintenance
- [ ] Dependencies updated
- [ ] Security patches applied
- [ ] Logs reviewed
- [ ] Access audited
- [ ] Backup verified

---

**Last Updated**: 2025-09-06
**Version**: 1.0
**Next Review**: 2025-12-06
