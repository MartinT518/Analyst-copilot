# Infrastructure Documentation

This document provides comprehensive information about the Analyst Copilot infrastructure, including monitoring, security, deployment, and operational procedures.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Monitoring & Observability](#monitoring--observability)
4. [Security](#security)
5. [Deployment](#deployment)
6. [CLI Tools](#cli-tools)
7. [Troubleshooting](#troubleshooting)
8. [Operational Procedures](#operational-procedures)

## Overview

The Analyst Copilot infrastructure is designed for production-ready deployment with comprehensive monitoring, security, and operational capabilities. The system follows microservices architecture with clear separation of concerns.

### Key Components

- **acp-ingest**: Document ingestion and knowledge base management
- **acp-agents**: AI agent orchestration and workflow management
- **PostgreSQL**: Primary database for metadata and user data
- **Redis**: Caching and job queue management
- **Chroma**: Vector database for semantic search
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Monitoring dashboards and visualization
- **Jaeger**: Distributed tracing
- **Nginx**: Reverse proxy and load balancing

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   acp-ingest    │    │   acp-agents    │    │   acp-cli       │
│   (Port 8000)   │    │   (Port 8001)   │    │   (Local)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     Redis       │    │     Chroma      │
│   (Port 5432)   │    │   (Port 6379)   │    │   (Port 8000)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Prometheus    │    │    Grafana      │    │     Jaeger      │
│   (Port 9090)   │    │   (Port 3000)   │    │   (Port 16686)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Monitoring & Observability

### Structured Logging

All services implement structured logging with JSON format:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "acp-ingest",
  "request_id": "req-123456",
  "correlation_id": "corr-789012",
  "user_id": "user-345678",
  "trace_id": "trace-abc123",
  "span_id": "span-def456",
  "message": "Document ingested successfully",
  "file_type": "pdf",
  "file_size": 1024000,
  "processing_time": 2.5
}
```

#### Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General operational messages
- **WARNING**: Warning conditions that don't prevent operation
- **ERROR**: Error conditions that may affect functionality

#### Viewing Logs

```bash
# View all service logs
acp monitor logs

# View specific service logs
acp monitor logs --service ingest

# Follow logs in real-time
acp monitor logs --follow

# Filter by log level
acp monitor logs --level ERROR

# Search logs
acp monitor logs --search "authentication"
```

### Metrics Collection

Prometheus metrics are exposed at `/metrics` endpoint for each service:

#### Key Metrics

- **acp_requests_total**: Total number of requests
- **acp_request_duration_seconds**: Request duration histogram
- **acp_errors_total**: Total number of errors
- **acp_active_connections**: Current active connections
- **acp_processing_time_seconds**: Processing time histogram
- **acp_queue_size**: Current queue size
- **acp_ingestion_total**: Total documents ingested
- **acp_vector_operations_total**: Vector database operations

#### Viewing Metrics

```bash
# View all metrics for a service
acp monitor metrics --service ingest

# View specific metric
acp monitor metrics --service ingest --metric acp_requests_total

# View metrics over time range
acp monitor metrics --service ingest --duration 1h
```

### Distributed Tracing

OpenTelemetry integration provides distributed tracing across services:

#### Trace Context

- **Trace ID**: Unique identifier for entire request flow
- **Span ID**: Unique identifier for individual operation
- **Parent Span**: Hierarchical relationship between operations

#### Viewing Traces

```bash
# View recent traces
acp monitor traces

# Filter by service
acp monitor traces --service ingest

# Filter by operation
acp monitor traces --operation document_upload
```

Access Jaeger UI at: `http://localhost:16686`

### Dashboards

Grafana dashboards are available at: `http://localhost:3000`

#### Default Dashboards

1. **Service Overview**: High-level service health and performance
2. **Request Metrics**: Request rates, latency, and error rates
3. **Infrastructure**: System resources and database performance
4. **Security**: Authentication failures and rate limiting
5. **Business Metrics**: Document ingestion and processing statistics

### Alerting

Prometheus alerting rules are configured for:

#### Service Alerts

- **ServiceDown**: Service is unreachable
- **HighErrorRate**: Error rate exceeds threshold
- **HighLatency**: Response time exceeds threshold
- **HighCPUUsage**: CPU usage exceeds 80%
- **HighMemoryUsage**: Memory usage exceeds threshold

#### Infrastructure Alerts

- **DiskSpaceLow**: Disk space below 10%
- **DatabaseConnectionsHigh**: Too many database connections
- **QueueProcessingStalled**: Job queue not processing
- **HighFailedAuthAttempts**: Potential security issue

#### Viewing Alerts

```bash
# View active alerts
acp monitor alerts

# Filter by severity
acp monitor alerts --severity critical

# View alert history
acp monitor alerts --active-only false
```

## Security

### Authentication & Authorization

#### API Key Management

```bash
# Generate new API key
acp config set-service ingest --api-key <your-key>

# Validate API key
acp config validate
```

#### Role-Based Access Control (RBAC)

- **Admin**: Full system access
- **Analyst**: Read/write access to documents and workflows
- **Viewer**: Read-only access

### Rate Limiting

Rate limiting is implemented at multiple levels:

- **Global**: 100 requests per minute per IP
- **Authentication**: 10 requests per minute per IP
- **Upload**: 5 uploads per minute per user

### Security Headers

All HTTP responses include security headers:

- **X-Content-Type-Options**: nosniff
- **X-Frame-Options**: DENY
- **X-XSS-Protection**: 1; mode=block
- **Strict-Transport-Security**: HSTS enabled
- **Content-Security-Policy**: Restrictive CSP

### Input Validation

- **File Upload**: Type and size validation
- **HTML Content**: Sanitization with bleach
- **SQL Injection**: Parameterized queries
- **XSS Prevention**: Input escaping

### Security Scanning

```bash
# Run all security scans
acp scan all

# Scan dependencies for vulnerabilities
acp scan dependencies

# Scan code for security issues
acp scan code

# Scan for exposed secrets
acp scan secrets

# Scan container images
acp scan containers
```

### Secrets Management

#### Environment Variables

Never commit secrets to version control. Use environment variables:

```bash
# Copy example environment file
cp .env.example .env

# Edit with your values
nano .env
```

#### HashiCorp Vault Integration

For production deployments, integrate with Vault:

```python
from infra.vault.vault_client import VaultClient

vault = VaultClient()
secret = vault.get_secret("database/password")
```

## Deployment

### Local Development

```bash
# Start all services
docker-compose up -d

# Check service status
acp status

# View logs
acp monitor logs --follow
```

### Staging Deployment

```bash
# Deploy to staging
acp deploy staging

# Check deployment status
acp deploy status --env staging

# View staging logs
acp deploy logs --env staging
```

### Production Deployment

```bash
# Deploy to production (requires confirmation)
acp deploy production

# Check production status
acp deploy status --env production

# Create database backup before deployment
acp deploy production --backup
```

### Docker Configuration

#### Multi-stage Builds

Production Dockerfiles use multi-stage builds for optimization:

```dockerfile
# Build stage
FROM python:3.11-slim as builder
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Production stage
FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
```

#### Security Hardening

- Non-root user execution
- Minimal base images
- Security scanning with Trivy
- Regular dependency updates

## CLI Tools

### Installation

```bash
# Install CLI in development mode
cd acp-cli
pip install -e .

# Verify installation
acp --help
```

### Configuration

```bash
# Initialize configuration
acp init

# Set service endpoints
acp config set-service ingest --url http://localhost:8000
acp config set-service agents --url http://localhost:8001

# Validate configuration
acp config validate
```

### Testing

```bash
# Run all tests
acp test run

# Run tests with coverage
acp test run --coverage

# Run specific service tests
acp test run --service ingest

# Run integration tests
acp test integration

# Run performance tests
acp test performance --duration 60 --users 10
```

### Monitoring

```bash
# Real-time dashboard
acp monitor dashboard

# Service health check
acp monitor health

# View metrics
acp monitor metrics --service ingest

# View traces
acp monitor traces --service ingest
```

### Security

```bash
# Run all security scans
acp scan all

# Dependency vulnerability scan
acp scan dependencies --severity high

# Code security scan
acp scan code --confidence medium

# Container image scan
acp scan containers --severity critical
```

## Troubleshooting

### Common Issues

#### Service Not Starting

1. Check Docker containers:
   ```bash
   docker-compose ps
   ```

2. View service logs:
   ```bash
   acp monitor logs --service <service-name>
   ```

3. Check configuration:
   ```bash
   acp config validate
   ```

#### Database Connection Issues

1. Check PostgreSQL status:
   ```bash
   docker-compose exec postgres pg_isready
   ```

2. Verify connection string:
   ```bash
   acp config show
   ```

3. Check database logs:
   ```bash
   acp monitor logs --service postgres
   ```

#### High Memory Usage

1. Check metrics:
   ```bash
   acp monitor metrics --metric process_resident_memory_bytes
   ```

2. Restart services:
   ```bash
   docker-compose restart <service-name>
   ```

#### Queue Processing Stalled

1. Check queue size:
   ```bash
   acp monitor metrics --metric acp_queue_size
   ```

2. Check Celery workers:
   ```bash
   docker-compose logs celery-worker
   ```

3. Restart workers:
   ```bash
   docker-compose restart celery-worker
   ```

### Performance Optimization

#### Database Optimization

- Monitor slow queries
- Optimize indexes
- Configure connection pooling
- Regular VACUUM and ANALYZE

#### Vector Database Optimization

- Monitor embedding performance
- Optimize chunk sizes
- Configure batch processing
- Monitor memory usage

#### Caching Strategy

- Redis for session data
- Application-level caching
- CDN for static assets
- Database query caching

### Monitoring Best Practices

1. **Set up alerts** for critical metrics
2. **Monitor trends** over time
3. **Regular health checks** for all services
4. **Capacity planning** based on metrics
5. **Performance baselines** for comparison

## Operational Procedures

### Daily Operations

1. **Health Check**:
   ```bash
   acp monitor health
   acp monitor alerts
   ```

2. **Log Review**:
   ```bash
   acp monitor logs --level ERROR --tail 100
   ```

3. **Metrics Review**:
   ```bash
   acp monitor dashboard
   ```

### Weekly Operations

1. **Security Scan**:
   ```bash
   acp scan all
   ```

2. **Performance Review**:
   - Review Grafana dashboards
   - Check for performance degradation
   - Analyze resource usage trends

3. **Backup Verification**:
   - Verify database backups
   - Test restore procedures

### Monthly Operations

1. **Dependency Updates**:
   ```bash
   acp scan dependencies
   # Update dependencies if needed
   ```

2. **Security Review**:
   - Review access logs
   - Update security policies
   - Rotate API keys

3. **Capacity Planning**:
   - Review resource usage trends
   - Plan for scaling needs
   - Update infrastructure as needed

### Incident Response

1. **Detection**:
   - Monitor alerts
   - Check service health
   - Review error logs

2. **Assessment**:
   - Determine impact
   - Identify root cause
   - Estimate resolution time

3. **Response**:
   - Implement immediate fixes
   - Communicate status
   - Document incident

4. **Recovery**:
   - Restore normal operations
   - Verify system health
   - Update monitoring

5. **Post-Incident**:
   - Conduct post-mortem
   - Update procedures
   - Implement preventive measures

### Backup and Recovery

#### Database Backup

```bash
# Create backup
acp deploy production --backup

# Manual backup
docker-compose exec postgres pg_dump -U acp_user acp_db > backup.sql
```

#### Restore Procedures

```bash
# Restore from backup
docker-compose exec postgres psql -U acp_user acp_db < backup.sql
```

#### Disaster Recovery

1. **Data Recovery**: Restore from latest backup
2. **Service Recovery**: Redeploy services
3. **Verification**: Run health checks
4. **Communication**: Update stakeholders

### Scaling Procedures

#### Horizontal Scaling

1. **Load Balancer**: Configure Nginx for multiple instances
2. **Database**: Set up read replicas
3. **Cache**: Configure Redis cluster
4. **Monitoring**: Update Prometheus targets

#### Vertical Scaling

1. **Resource Limits**: Update Docker resource limits
2. **Database**: Increase PostgreSQL resources
3. **Monitoring**: Update alert thresholds

---

For additional support or questions, please refer to the project documentation or contact the development team.

