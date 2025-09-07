# Analyst Copilot - Complete Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Analyst Copilot system in your on-premises environment. The system is designed to work with your existing OpenWebUI/vLLM infrastructure while maintaining strict security and compliance requirements.

## Prerequisites

### System Requirements
- **Operating System**: Ubuntu 22.04 LTS or CentOS 8+
- **CPU**: 8+ cores recommended
- **RAM**: 32GB+ recommended
- **Storage**: 500GB+ SSD recommended
- **Network**: Access to internal LLM endpoints

### Required Software
- Docker 24.0+ and Docker Compose 2.0+
- PostgreSQL 15+ (or use containerized version)
- Redis 7.0+ (or use containerized version)
- Python 3.11+ (for development)
- Git

### External Dependencies
- **LLM Endpoint**: Your existing OpenWebUI/vLLM setup
- **Embedding Endpoint**: Your internal embedding service
- **HashiCorp Vault** (optional, for secrets management)
- **Prometheus/Grafana** (optional, for monitoring)

## Quick Start (Docker Compose)

### 1. Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url> analyst-copilot
cd analyst-copilot

# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### 2. Configure Environment Variables

Edit `.env` file with your specific settings:

```bash
# Database Configuration
DATABASE_URL=postgresql://acp_user:secure_password@postgres:5432/acp_db

# LLM Configuration
LLM_ENDPOINT=https://ai.int.cyber.ee/openai
EMBEDDING_ENDPOINT=http://ai.int.cyber.ee:8083/v1
EMBEDDING_MODEL=BGE-M3
API_KEY=your-api-key-here

# Security Configuration
SECRET_KEY=your-super-secure-secret-key-change-this
JWT_EXPIRE_MINUTES=1440

# Vault Configuration (Optional)
VAULT_URL=https://vault.your-domain.com
VAULT_TOKEN=your-vault-token

# Monitoring Configuration (Optional)
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
```

### 3. Deploy with Docker Compose

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f acp-ingest
```

### 4. Initialize Database

```bash
# Run database migrations
docker-compose exec acp-ingest alembic upgrade head

# Create initial admin user
docker-compose exec acp-ingest python -m app.cli create-admin \
  --username admin \
  --email admin@your-domain.com \
  --password secure-admin-password
```

### 5. Verify Installation

```bash
# Check health endpoint
curl http://localhost:8000/health

# Check API documentation
open http://localhost:8000/docs

# Check Prometheus metrics (if enabled)
curl http://localhost:9090/metrics
```

## Manual Installation

### 1. Database Setup

```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE acp_db;
CREATE USER acp_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE acp_db TO acp_user;
\q
```

### 2. Redis Setup

```bash
# Install Redis
sudo apt install redis-server

# Configure Redis
sudo nano /etc/redis/redis.conf
# Set: bind 127.0.0.1
# Set: requirepass your-redis-password

# Restart Redis
sudo systemctl restart redis-server
```

### 3. Application Setup

```bash
# Create application user
sudo useradd -m -s /bin/bash acp
sudo su - acp

# Clone repository
git clone <your-repo-url> analyst-copilot
cd analyst-copilot

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r acp-ingest/requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
cd acp-ingest
alembic upgrade head

# Create admin user
python -m app.cli create-admin \
  --username admin \
  --email admin@your-domain.com \
  --password secure-admin-password
```

### 4. Service Configuration

Create systemd service files:

```bash
# Create service file
sudo nano /etc/systemd/system/acp-ingest.service
```

```ini
[Unit]
Description=ACP Ingest Service
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=acp
Group=acp
WorkingDirectory=/home/acp/analyst-copilot/acp-ingest
Environment=PATH=/home/acp/analyst-copilot/venv/bin
ExecStart=/home/acp/analyst-copilot/venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
# Create Celery worker service
sudo nano /etc/systemd/system/acp-worker.service
```

```ini
[Unit]
Description=ACP Celery Worker
After=network.target redis.service

[Service]
Type=exec
User=acp
Group=acp
WorkingDirectory=/home/acp/analyst-copilot/acp-ingest
Environment=PATH=/home/acp/analyst-copilot/venv/bin
ExecStart=/home/acp/analyst-copilot/venv/bin/celery -A app.worker worker --loglevel=info
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable acp-ingest acp-worker
sudo systemctl start acp-ingest acp-worker

# Check status
sudo systemctl status acp-ingest acp-worker
```

## Security Configuration

### 1. Vault Integration

If using HashiCorp Vault for secrets management:

```bash
# Install Vault CLI
wget https://releases.hashicorp.com/vault/1.15.2/vault_1.15.2_linux_amd64.zip
unzip vault_1.15.2_linux_amd64.zip
sudo mv vault /usr/local/bin/

# Configure Vault authentication
export VAULT_ADDR=https://vault.your-domain.com
export VAULT_TOKEN=your-vault-token

# Store secrets
vault kv put secret/acp/database password=secure_password
vault kv put secret/acp/jwt secret_key=your-super-secure-secret-key
vault kv put secret/acp/llm api_key=your-api-key
```

### 2. SSL/TLS Configuration

```bash
# Generate SSL certificates (or use existing ones)
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/acp.key \
  -out /etc/ssl/certs/acp.crt

# Configure nginx reverse proxy
sudo nano /etc/nginx/sites-available/acp
```

```nginx
server {
    listen 443 ssl;
    server_name acp.your-domain.com;

    ssl_certificate /etc/ssl/certs/acp.crt;
    ssl_certificate_key /etc/ssl/private/acp.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Firewall Configuration

```bash
# Configure UFW firewall
sudo ufw allow ssh
sudo ufw allow 443/tcp
sudo ufw allow from 10.0.0.0/8 to any port 8000  # Internal network only
sudo ufw enable
```

## Monitoring Setup

### 1. Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'acp-ingest'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### 2. Grafana Dashboard

Import the provided Grafana dashboard configuration from `monitoring/grafana-dashboard.json`.

## CLI Usage

### Installation

```bash
# Install CLI globally
pip install -e acp-ingest/

# Or use directly
cd acp-ingest
python -m app.cli --help
```

### Basic Commands

```bash
# Ingest a file
acp ingest upload --file document.pdf --origin customer-a --sensitivity confidential

# Paste text content
acp ingest paste --text "Your text content here" --origin customer-b --sensitivity internal

# Check job status
acp status --job-id <job-uuid>

# Search knowledge base
acp search --query "your search query" --limit 10

# Export results
acp export --format csv --output results.csv
```

## API Usage Examples

### Authentication

```bash
# Get access token
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=your-password"

# Use token in subsequent requests
export TOKEN="your-jwt-token"
```

### File Upload

```bash
# Upload file
curl -X POST "http://localhost:8000/api/v1/ingest/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@document.pdf" \
  -F "origin=customer-a" \
  -F "sensitivity=confidential"
```

### Search

```bash
# Search knowledge base
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "your search query",
    "limit": 10,
    "filters": {
      "sensitivity": ["internal", "public"]
    }
  }'
```

## Backup and Recovery

### Database Backup

```bash
# Create backup script
cat > /home/acp/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/acp/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
pg_dump -h localhost -U acp_user acp_db > $BACKUP_DIR/acp_db_$DATE.sql

# Backup Chroma data
tar -czf $BACKUP_DIR/chroma_data_$DATE.tar.gz /path/to/chroma/data

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
EOF

chmod +x /home/acp/backup.sh

# Add to crontab
crontab -e
# Add: 0 2 * * * /home/acp/backup.sh
```

### Recovery

```bash
# Restore database
psql -h localhost -U acp_user -d acp_db < backup_file.sql

# Restore Chroma data
tar -xzf chroma_data_backup.tar.gz -C /
```

## Troubleshooting

### Common Issues

1. **Database Connection Issues**
   ```bash
   # Check PostgreSQL status
   sudo systemctl status postgresql

   # Check connection
   psql -h localhost -U acp_user -d acp_db -c "SELECT 1;"
   ```

2. **Redis Connection Issues**
   ```bash
   # Check Redis status
   sudo systemctl status redis-server

   # Test connection
   redis-cli ping
   ```

3. **LLM Endpoint Issues**
   ```bash
   # Test LLM endpoint
   curl -X POST "https://ai.int.cyber.ee/openai/v1/chat/completions" \
     -H "Authorization: Bearer $API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model": "llama2", "messages": [{"role": "user", "content": "test"}]}'
   ```

4. **Permission Issues**
   ```bash
   # Fix file permissions
   sudo chown -R acp:acp /home/acp/analyst-copilot
   sudo chmod -R 755 /home/acp/analyst-copilot
   ```

### Log Locations

- Application logs: `/home/acp/analyst-copilot/logs/`
- System logs: `journalctl -u acp-ingest -f`
- Docker logs: `docker-compose logs -f`

### Performance Tuning

1. **Database Optimization**
   ```sql
   -- Add indexes for better performance
   CREATE INDEX CONCURRENTLY idx_knowledge_chunks_embedding_model ON knowledge_chunks(embedding_model);
   CREATE INDEX CONCURRENTLY idx_ingest_jobs_created_status ON ingest_jobs(created_at, status);
   ```

2. **Application Tuning**
   ```bash
   # Adjust worker processes
   export WORKERS=8
   export MAX_CONCURRENT_JOBS=10
   ```

## Security Checklist

- [ ] Change all default passwords
- [ ] Configure SSL/TLS certificates
- [ ] Set up firewall rules
- [ ] Configure Vault for secrets management
- [ ] Enable audit logging
- [ ] Set up monitoring and alerting
- [ ] Configure backup procedures
- [ ] Review and restrict API access
- [ ] Enable rate limiting
- [ ] Configure CORS properly

## Support and Maintenance

### Regular Maintenance Tasks

1. **Weekly**
   - Review audit logs
   - Check system performance metrics
   - Verify backup integrity

2. **Monthly**
   - Update dependencies
   - Review security configurations
   - Clean up old files and logs

3. **Quarterly**
   - Security assessment
   - Performance optimization
   - Documentation updates

### Getting Help

- Check the troubleshooting guide
- Review application logs
- Consult the API documentation at `/docs`
- Check system metrics in Grafana (if configured)

## Next Steps

After successful deployment:

1. **Configure User Roles**: Set up appropriate RBAC roles for your team
2. **Data Ingestion**: Start ingesting your knowledge base
3. **Integration**: Integrate with your existing workflows
4. **Monitoring**: Set up alerts and monitoring dashboards
5. **Training**: Train your team on the CLI and API usage

For advanced configuration and customization, refer to the detailed documentation in the `docs/` directory.
