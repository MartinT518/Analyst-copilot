# Configuration Guide

The Analyst Copilot system is configured using environment variables. You can set these variables in your shell or by creating a `.env` file in the root of the project.

## 📋 Configuration Categories

### 🔧 Core Configuration (Required for All Environments)

These variables are essential for basic system operation:

| Variable             | Required   | Description                               | Default                     | Example                                 |
| -------------------- | ---------- | ----------------------------------------- | --------------------------- | --------------------------------------- |
| `SECRET_KEY`         | ✅ **YES** | Secret key for JWT signing and encryption | _None_                      | `your-super-secure-secret-key-256-bits` |
| `OPENAI_API_KEY`     | ✅ **YES** | API key for LLM and embedding services    | _None_                      | `sk-...`                                |
| `LLM_ENDPOINT`       | ✅ **YES** | Endpoint URL for LLM service              | `http://localhost:11434/v1` | `https://ai.company.com/openai`         |
| `EMBEDDING_ENDPOINT` | ✅ **YES** | Endpoint URL for embedding service        | `http://localhost:11434/v1` | `http://embed.company.com/v1`           |

### 🗄️ Database Configuration (Optional - Uses Defaults)

| Variable       | Required | Description                 | Default                                          | Example                              |
| -------------- | -------- | --------------------------- | ------------------------------------------------ | ------------------------------------ |
| `DATABASE_URL` | ❌ No    | PostgreSQL connection URL   | `postgresql://acp:password@localhost/acp_ingest` | `postgresql://user:pass@db:5432/acp` |
| `REDIS_URL`    | ❌ No    | Redis connection URL        | `redis://localhost:6379/0`                       | `redis://redis:6379/0`               |
| `CHROMA_HOST`  | ❌ No    | Chroma vector database host | `localhost`                                      | `chroma`                             |
| `CHROMA_PORT`  | ❌ No    | Chroma vector database port | `8001`                                           | `8000`                               |

### 🔒 Production Security Configuration (Required for Production)

| Variable        | Required | Description                                       | Default      | Example           |
| --------------- | -------- | ------------------------------------------------- | ------------ | ----------------- |
| `ENVIRONMENT`   | ❌ No    | Environment mode (`production`, `development`)    | `production` | `production`      |
| `DEBUG`         | ❌ No    | Enable debug mode (must be `false` in production) | `false`      | `false`           |
| `SSL_ENABLED`   | ❌ No    | Enable SSL/TLS                                    | `false`      | `true`            |
| `SSL_CERT_FILE` | ❌ No    | Path to SSL certificate file                      | _None_       | `/certs/cert.pem` |
| `SSL_KEY_FILE`  | ❌ No    | Path to SSL private key file                      | _None_       | `/certs/key.pem`  |

### 🏦 Vault Integration (Optional)

| Variable            | Required | Description                   | Default  | Example                     |
| ------------------- | -------- | ----------------------------- | -------- | --------------------------- |
| `VAULT_URL`         | ❌ No    | HashiCorp Vault server URL    | _None_   | `https://vault.company.com` |
| `VAULT_TOKEN`       | ❌ No    | Vault authentication token    | _None_   | `hvs.abc123...`             |
| `VAULT_NAMESPACE`   | ❌ No    | Vault namespace               | _None_   | `acp-production`            |
| `VAULT_MOUNT_POINT` | ❌ No    | Vault mount point for secrets | `secret` | `secret`                    |

### 📊 Monitoring Configuration (Optional)

| Variable             | Required | Description               | Default | Example           |
| -------------------- | -------- | ------------------------- | ------- | ----------------- |
| `PROMETHEUS_ENABLED` | ❌ No    | Enable Prometheus metrics | `false` | `true`            |
| `PROMETHEUS_PORT`    | ❌ No    | Prometheus metrics port   | `9090`  | `9090`            |
| `GRAFANA_ENABLED`    | ❌ No    | Enable Grafana dashboards | `false` | `true`            |
| `GRAFANA_PASSWORD`   | ❌ No    | Grafana admin password    | `admin` | `secure-password` |

### 🔐 Authentication & Authorization (Optional)

| Variable                      | Required | Description                           | Default | Example |
| ----------------------------- | -------- | ------------------------------------- | ------- | ------- |
| `JWT_ALGORITHM`               | ❌ No    | JWT signing algorithm                 | `HS256` | `HS256` |
| `JWT_EXPIRE_MINUTES`          | ❌ No    | JWT token expiration (minutes)        | `1440`  | `60`    |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ❌ No    | Access token expiration (minutes)     | `1440`  | `60`    |
| `PASSWORD_MIN_LENGTH`         | ❌ No    | Minimum password length               | `8`     | `12`    |
| `MAX_LOGIN_ATTEMPTS`          | ❌ No    | Maximum login attempts before lockout | `5`     | `3`     |

### 📁 File Processing Configuration (Optional)

| Variable             | Required | Description                             | Default                                | Example           |
| -------------------- | -------- | --------------------------------------- | -------------------------------------- | ----------------- |
| `MAX_FILE_SIZE`      | ❌ No    | Maximum file size (bytes)               | `104857600` (100MB)                    | `52428800` (50MB) |
| `UPLOAD_DIR`         | ❌ No    | Directory for file uploads              | `/app/uploads`                         | `/data/uploads`   |
| `ALLOWED_EXTENSIONS` | ❌ No    | Comma-separated allowed file extensions | `csv,html,htm,xml,pdf,md,txt,zip,json` | `pdf,txt,md`      |
| `MAX_CHUNK_SIZE`     | ❌ No    | Maximum text chunk size                 | `1000`                                 | `2000`            |
| `CHUNK_OVERLAP`      | ❌ No    | Text chunk overlap                      | `200`                                  | `100`             |

### 🛡️ PII Detection Configuration (Optional)

| Variable                   | Required | Description                                      | Default  | Example   |
| -------------------------- | -------- | ------------------------------------------------ | -------- | --------- |
| `PII_DETECTION_ENABLED`    | ❌ No    | Enable PII detection                             | `true`   | `true`    |
| `PII_REDACTION_MODE`       | ❌ No    | PII redaction mode (`redact`, `replace`, `mask`) | `redact` | `replace` |
| `PII_CONFIDENCE_THRESHOLD` | ❌ No    | PII detection confidence threshold               | `0.8`    | `0.9`     |
| `PRESIDIO_ENABLED`         | ❌ No    | Enable Microsoft Presidio                        | `false`  | `true`    |

### 📝 Logging Configuration (Optional)

| Variable        | Required | Description                                         | Default                    | Example                |
| --------------- | -------- | --------------------------------------------------- | -------------------------- | ---------------------- |
| `LOG_LEVEL`     | ❌ No    | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO`                     | `DEBUG`                |
| `LOG_FORMAT`    | ❌ No    | Log format (`json`, `text`)                         | `json`                     | `text`                 |
| `LOG_FILE`      | ❌ No    | Log file path                                       | `/app/logs/acp-ingest.log` | `/var/log/acp/app.log` |
| `LOG_ROTATION`  | ❌ No    | Log rotation schedule                               | `1 day`                    | `1 week`               |
| `LOG_RETENTION` | ❌ No    | Log retention period                                | `30 days`                  | `90 days`              |

### ⚡ Performance Configuration (Optional)

| Variable                | Required | Description                           | Default | Example |
| ----------------------- | -------- | ------------------------------------- | ------- | ------- |
| `DATABASE_POOL_SIZE`    | ❌ No    | Database connection pool size         | `10`    | `20`    |
| `DATABASE_MAX_OVERFLOW` | ❌ No    | Database connection pool max overflow | `20`    | `30`    |
| `DATABASE_POOL_TIMEOUT` | ❌ No    | Database connection timeout (seconds) | `30`    | `60`    |
| `MAX_CONCURRENT_JOBS`   | ❌ No    | Maximum concurrent processing jobs    | `5`     | `10`    |
| `BATCH_SIZE`            | ❌ No    | Processing batch size                 | `10`    | `20`    |

### 🌐 CORS Configuration (Optional)

| Variable       | Required | Description                     | Default                                       | Example                      |
| -------------- | -------- | ------------------------------- | --------------------------------------------- | ---------------------------- |
| `CORS_ENABLED` | ❌ No    | Enable CORS                     | `true`                                        | `true`                       |
| `CORS_ORIGINS` | ❌ No    | Comma-separated allowed origins | `http://localhost:3000,http://localhost:5173` | `https://app.company.com`    |
| `CORS_METHODS` | ❌ No    | Allowed HTTP methods            | `GET,POST,PUT,DELETE,OPTIONS`                 | `GET,POST`                   |
| `CORS_HEADERS` | ❌ No    | Allowed headers                 | `*`                                           | `Content-Type,Authorization` |

## 🔧 Configuration Examples

### Development Environment

```bash
# .env for development
SECRET_KEY=dev-secret-key-not-for-production
OPENAI_API_KEY=your-dev-api-key
LLM_ENDPOINT=http://localhost:11434/v1
EMBEDDING_ENDPOINT=http://localhost:11434/v1
DEBUG=true
LOG_LEVEL=DEBUG
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### Production Environment

```bash
# .env for production
SECRET_KEY=your-super-secure-256-bit-secret-key
OPENAI_API_KEY=your-production-api-key
LLM_ENDPOINT=https://ai.company.com/openai
EMBEDDING_ENDPOINT=https://embed.company.com/v1
ENVIRONMENT=production
DEBUG=false
SSL_ENABLED=true
SSL_CERT_FILE=/certs/cert.pem
SSL_KEY_FILE=/certs/key.pem
CORS_ORIGINS=https://app.company.com
VAULT_URL=https://vault.company.com
VAULT_TOKEN=hvs.your-vault-token
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
```

### Docker Compose Override

```bash
# docker-compose.override.yml
version: '3.8'
services:
  acp-ingest:
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LLM_ENDPOINT=${LLM_ENDPOINT}
      - EMBEDDING_ENDPOINT=${EMBEDDING_ENDPOINT}
```

## 🔒 Security Best Practices

### Required Security Settings for Production

1. **SECRET_KEY**: Must be at least 256 bits (32 characters) of cryptographically secure random data
2. **DEBUG**: Must be `false` in production
3. **SSL_ENABLED**: Must be `true` for production deployments
4. **CORS_ORIGINS**: Must be restricted to specific domains (never use `*`)

### Secret Management

- Use environment variables or secret management systems (Vault, AWS Secrets Manager)
- Never commit secrets to version control
- Rotate secrets regularly
- Use different secrets for different environments

### Validation

The system automatically validates critical configuration on startup:

```python
# Configuration validation errors will prevent startup
if not settings.secret_key or settings.secret_key == "your-secret-key":
    raise ValueError("SECRET_KEY must be set to a secure value")
```

## 🚨 Common Configuration Issues

### 1. Missing Required Variables

**Error**: `SECRET_KEY must be set to a secure value`

**Solution**: Set a secure SECRET_KEY in your `.env` file:

```bash
SECRET_KEY=$(openssl rand -base64 32)
```

### 2. CORS Configuration Issues

**Error**: `CORS origins should be restricted in production`

**Solution**: Set specific CORS origins:

```bash
CORS_ORIGINS=https://your-frontend-domain.com
```

### 3. Database Connection Issues

**Error**: `Failed to connect to database`

**Solution**: Verify DATABASE_URL format:

```bash
DATABASE_URL=postgresql://username:password@host:port/database
```

### 4. SSL Certificate Issues

**Error**: `SSL certificate file not found`

**Solution**: Ensure certificate files exist and are readable:

```bash
SSL_CERT_FILE=/path/to/cert.pem
SSL_KEY_FILE=/path/to/key.pem
```

## 📋 Configuration Checklist

### Pre-Deployment Checklist

- [ ] `SECRET_KEY` is set to a secure value
- [ ] `OPENAI_API_KEY` is configured
- [ ] `LLM_ENDPOINT` points to your LLM service
- [ ] `EMBEDDING_ENDPOINT` points to your embedding service
- [ ] `DEBUG=false` for production
- [ ] `CORS_ORIGINS` is restricted to specific domains
- [ ] SSL certificates are configured (if using HTTPS)
- [ ] Database connection is tested
- [ ] Redis connection is tested
- [ ] Log levels are appropriate for environment

### Production Security Checklist

- [ ] All secrets are stored securely (Vault, environment variables)
- [ ] SSL/TLS is enabled
- [ ] CORS is properly configured
- [ ] Database credentials are secure
- [ ] Log files have appropriate permissions
- [ ] Monitoring is enabled
- [ ] Backup procedures are in place

## 🔄 Configuration Updates

### Hot Reloading

Some configuration changes require service restart:

```bash
# Restart specific service
docker-compose restart acp-ingest

# Restart all services
docker-compose restart
```

### Configuration Validation

The system validates configuration on startup. Check logs for validation errors:

```bash
docker-compose logs acp-ingest | grep -i "configuration\|validation\|error"
```

## 📞 Support

For configuration issues:

1. Check the [troubleshooting guide](troubleshooting.md)
2. Review service logs: `docker-compose logs <service-name>`
3. Validate configuration: `docker-compose config`
4. Open an issue with your configuration (redact secrets)
