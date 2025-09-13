# Production Operator Checklist - Analyst Copilot

**Version:** 1.0
**Date:** January 2025
**Target:** Human Operators (Non-Developers)
**Purpose:** Complete manual setup guide for production deployment

---

## 🎯 Overview

This checklist covers all manual tasks required to deploy and operate the Analyst Copilot system in production. These are **human operator tasks** that cannot be automated through code changes.

**⚠️ Important:** This checklist assumes you have administrative access to cloud providers, GitHub, and deployment infrastructure.

---

## 📋 Repository Setup

### GitHub Repository Configuration

- [ ] **Protect master branch**

  - Navigate to Settings → Branches → Add rule
  - Require pull request reviews (2 reviewers minimum)
  - Require status checks to pass before merging
  - Require branches to be up to date before merging
  - Restrict pushes to master branch

- [ ] **Configure PR reviews**

  - Set up CODEOWNERS file (if not exists)
  - Require review from code owners
  - Enable auto-merge for approved PRs

- [ ] **Setup GitHub Environments**

  - Create `staging` environment
  - Create `production` environment
  - Configure protection rules for production environment
  - Set required reviewers for production deployments

- [ ] **Configure branch protection**
  - Enable "Require linear history"
  - Enable "Include administrators"
  - Set up automatic deletion of head branches

### GitHub Actions Secrets & Tokens

- [ ] **Add GitHub Actions secrets** (Settings → Secrets and variables → Actions)

  - [ ] `GHCR_TOKEN` - GitHub Container Registry token
  - [ ] `DOCKER_USERNAME` - Docker registry username
  - [ ] `DOCKER_PASSWORD` - Docker registry password
  - [ ] `SLACK_WEBHOOK_URL` - For deployment notifications (optional)
  - [ ] `VAULT_TOKEN` - HashiCorp Vault authentication token

- [ ] **Create GitHub Personal Access Token**
  - Go to Settings → Developer settings → Personal access tokens
  - Generate token with `repo`, `write:packages`, `read:org` scopes
  - Add as `GITHUB_TOKEN` secret

---

## 🔐 Secrets and Environment Variables

### Database Secrets

- [ ] **PostgreSQL Connection**

  - [ ] Provision PostgreSQL 13+ instance in cloud provider
  - [ ] Create dedicated database: `analyst_copilot_prod`
  - [ ] Create database user: `acp_user`
  - [ ] Set strong password (32+ characters)
  - [ ] Copy connection string format: `postgresql://acp_user:password@host:5432/analyst_copilot_prod`
  - [ ] Add as `POSTGRES_URI` secret

- [ ] **Database SSL Configuration**
  - [ ] Download SSL certificate from cloud provider
  - [ ] Add as `POSTGRES_SSL_CERT` secret
  - [ ] Configure SSL mode: `require` or `verify-full`

### Cache & Vector Store Secrets

- [ ] **Redis Configuration**

  - [ ] Provision Redis 7+ instance (AWS ElastiCache, Azure Cache, GCP Memorystore)
  - [ ] Enable encryption in transit and at rest
  - [ ] Create Redis password (32+ characters)
  - [ ] Copy connection string: `redis://:password@host:6379/0`
  - [ ] Add as `REDIS_URL` secret

- [ ] **ChromaDB Configuration**
  - [ ] Deploy ChromaDB instance (Docker container or managed service)
  - [ ] Configure persistent volume for vector storage
  - [ ] Set ChromaDB admin password
  - [ ] Copy connection string: `http://username:password@host:8000`
  - [ ] Add as `CHROMA_URL` secret

### Application Secrets

- [ ] **Core Application Secrets**

  - [ ] Generate `SECRET_KEY` (64+ character random string)
  - [ ] Add as `SECRET_KEY` secret
  - [ ] Generate `JWT_SECRET` (64+ character random string)
  - [ ] Add as `JWT_SECRET` secret

- [ ] **LLM Service Configuration**

  - [ ] Obtain OpenAI API key or configure local LLM endpoint
  - [ ] Add as `OPENAI_API_KEY` secret
  - [ ] Configure `LLM_ENDPOINT` environment variable
  - [ ] Configure `EMBEDDING_ENDPOINT` environment variable

- [ ] **OAuth2/OIDC Configuration**
  - [ ] Register application with identity provider (Google, Microsoft, Okta)
  - [ ] Obtain `CLIENT_ID` and `CLIENT_SECRET`
  - [ ] Add as `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` secrets
  - [ ] Configure redirect URIs: `https://yourdomain.com/auth/callback`

### Vault Integration (Optional)

- [ ] **HashiCorp Vault Setup**
  - [ ] Deploy Vault instance (cloud or self-hosted)
  - [ ] Initialize Vault and unseal
  - [ ] Create authentication method (AppRole, Kubernetes, etc.)
  - [ ] Add as `VAULT_URL` secret
  - [ ] Add as `VAULT_TOKEN` secret

---

## 🗄️ Database Setup

### PostgreSQL Instance Creation

- [ ] **Staging Environment**

  - [ ] Provision PostgreSQL 13+ instance
  - [ ] Configure backup retention (7 days minimum)
  - [ ] Set up monitoring and alerting
  - [ ] Configure connection pooling (PgBouncer recommended)

- [ ] **Production Environment**
  - [ ] Provision PostgreSQL 13+ instance with high availability
  - [ ] Configure automated backups (30 days retention)
  - [ ] Set up read replicas for scaling
  - [ ] Configure connection pooling
  - [ ] Enable performance insights and monitoring

### Database Migration

- [ ] **Run Alembic Migrations**

  - [ ] Connect to staging database
  - [ ] Run: `alembic upgrade head`
  - [ ] Verify all tables created successfully
  - [ ] Connect to production database
  - [ ] Run: `alembic upgrade head`
  - [ ] Verify migration success

- [ ] **Configure Database Users and Permissions**
  - [ ] Create application user with limited permissions
  - [ ] Grant necessary table permissions
  - [ ] Configure row-level security (if needed)
  - [ ] Test connection with application credentials

### Database Monitoring

- [ ] **Set up Database Monitoring**
  - [ ] Configure slow query logging
  - [ ] Set up connection monitoring
  - [ ] Configure disk space alerts
  - [ ] Set up backup verification alerts

---

## 🚀 Cache & Vector Store Setup

### Redis Configuration

- [ ] **Staging Redis**

  - [ ] Provision Redis 7+ instance
  - [ ] Configure memory limits (2GB minimum)
  - [ ] Enable persistence (RDB + AOF)
  - [ ] Configure backup schedule

- [ ] **Production Redis**
  - [ ] Provision Redis 7+ with clustering
  - [ ] Configure memory limits (8GB+ recommended)
  - [ ] Enable persistence and backups
  - [ ] Set up Redis monitoring and alerting

### ChromaDB Configuration

- [ ] **ChromaDB Deployment**

  - [ ] Deploy ChromaDB container with persistent volume
  - [ ] Configure collection management
  - [ ] Set up backup strategy for vector data
  - [ ] Configure memory limits and resource allocation

- [ ] **Vector Store Monitoring**
  - [ ] Set up ChromaDB health checks
  - [ ] Monitor embedding storage usage
  - [ ] Configure performance metrics collection

---

## 📦 Container Registry Setup

### GitHub Container Registry (GHCR)

- [ ] **Enable GHCR**

  - [ ] Go to repository Settings → Packages
  - [ ] Enable GitHub Container Registry
  - [ ] Configure package visibility (private for production)

- [ ] **Configure Authentication**
  - [ ] Create Personal Access Token with `write:packages` scope
  - [ ] Add as `GHCR_TOKEN` secret
  - [ ] Configure GitHub Actions to authenticate with GHCR

### Alternative Container Registries

- [ ] **AWS ECR Setup** (if using AWS)

  - [ ] Create ECR repositories for each service
  - [ ] Configure IAM roles for GitHub Actions
  - [ ] Add AWS credentials as secrets

- [ ] **Azure Container Registry** (if using Azure)

  - [ ] Create ACR instance
  - [ ] Configure service principal
  - [ ] Add Azure credentials as secrets

- [ ] **Google Container Registry** (if using GCP)
  - [ ] Create GCR repositories
  - [ ] Configure service account
  - [ ] Add GCP credentials as secrets

---

## 🌐 Deployment Infrastructure

### Domain and DNS Configuration

- [ ] **Domain Setup**

  - [ ] Purchase domain name (e.g., `analyst-copilot.company.com`)
  - [ ] Configure DNS records
  - [ ] Set up subdomains: `staging.analyst-copilot.company.com`, `api.analyst-copilot.company.com`

- [ ] **SSL/TLS Configuration**
  - [ ] Obtain SSL certificates (Let's Encrypt, AWS ACM, or commercial)
  - [ ] Configure automatic certificate renewal
  - [ ] Set up certificate monitoring

### Load Balancer and Reverse Proxy

- [ ] **Load Balancer Setup**

  - [ ] Configure cloud load balancer (AWS ALB, Azure LB, GCP LB)
  - [ ] Set up health checks for all services
  - [ ] Configure SSL termination
  - [ ] Set up routing rules

- [ ] **NGINX Configuration** (if using NGINX)
  - [ ] Install and configure NGINX
  - [ ] Set up SSL certificates
  - [ ] Configure upstream servers
  - [ ] Set up rate limiting and security headers

### Container Orchestration

- [ ] **Docker Compose Production Setup**

  - [ ] Create production docker-compose.yml
  - [ ] Configure resource limits
  - [ ] Set up health checks
  - [ ] Configure restart policies

- [ ] **Kubernetes Setup** (if using K8s)
  - [ ] Create Kubernetes cluster
  - [ ] Configure namespaces (staging, production)
  - [ ] Set up ingress controllers
  - [ ] Configure persistent volumes

---

## 📊 Monitoring & Logging

### Prometheus and Grafana Setup

- [ ] **Prometheus Configuration**

  - [ ] Deploy Prometheus instance
  - [ ] Configure service discovery
  - [ ] Set up retention policies (30 days minimum)
  - [ ] Configure alerting rules

- [ ] **Grafana Setup**
  - [ ] Deploy Grafana instance
  - [ ] Configure Prometheus as data source
  - [ ] Import Analyst Copilot dashboards
  - [ ] Set up user authentication

### Alert Rules Configuration

- [ ] **Basic Health Alerts**

  - [ ] Service down alerts
  - [ ] High error rate alerts (>5%)
  - [ ] High response time alerts (>2 seconds)
  - [ ] Database connection failure alerts

- [ ] **Business Logic Alerts**
  - [ ] Workflow failure rate alerts
  - [ ] Agent execution time alerts
  - [ ] Vector store performance alerts
  - [ ] Authentication failure rate alerts

### Log Aggregation

- [ ] **ELK Stack Setup** (if using ELK)

  - [ ] Deploy Elasticsearch cluster
  - [ ] Configure Logstash for log processing
  - [ ] Set up Kibana for log visualization
  - [ ] Configure log retention policies

- [ ] **Cloud Logging** (if using cloud providers)
  - [ ] Enable cloud logging services
  - [ ] Configure log routing
  - [ ] Set up log-based alerts
  - [ ] Configure log retention

---

## 🔒 Security Configuration

### Secret Management

- [ ] **Secret Rotation**

  - [ ] Set up automated secret rotation schedule
  - [ ] Document secret rotation procedures
  - [ ] Test secret rotation process
  - [ ] Configure alerts for secret expiration

- [ ] **Access Control**
  - [ ] Implement least-privilege access
  - [ ] Set up multi-factor authentication
  - [ ] Configure session timeouts
  - [ ] Regular access review process

### CI/CD Security

- [ ] **GitHub Actions Security**

  - [ ] Use least-privilege tokens
  - [ ] Enable branch protection rules
  - [ ] Configure required status checks
  - [ ] Set up security scanning in CI/CD

- [ ] **Dependency Management**
  - [ ] Enable Dependabot for security updates
  - [ ] Configure Renovate for dependency updates
  - [ ] Set up automated security scanning
  - [ ] Regular dependency audit process

### Network Security

- [ ] **Firewall Configuration**

  - [ ] Configure ingress rules
  - [ ] Set up egress filtering
  - [ ] Enable DDoS protection
  - [ ] Configure VPN access (if needed)

- [ ] **SSL/TLS Security**
  - [ ] Use TLS 1.3 minimum
  - [ ] Configure HSTS headers
  - [ ] Set up certificate pinning
  - [ ] Regular security certificate audit

---

## 🧪 Testing & Validation

### Smoke Testing

- [ ] **Endpoint Testing**

  - [ ] Test health check endpoints
  - [ ] Verify API authentication
  - [ ] Test file upload functionality
  - [ ] Validate search functionality

- [ ] **Database Connectivity**
  - [ ] Test database connections
  - [ ] Verify migration status
  - [ ] Test backup and restore procedures
  - [ ] Validate data integrity

### Multi-Agent Orchestrator Testing

- [ ] **Workflow Testing**

  - [ ] Test complete agent workflow
  - [ ] Verify agent communication
  - [ ] Test error handling and recovery
  - [ ] Validate result generation

- [ ] **Integration Testing**
  - [ ] Test with connected databases
  - [ ] Verify cache functionality
  - [ ] Test vector store operations
  - [ ] Validate end-to-end data flow

### Performance Testing

- [ ] **Load Testing**

  - [ ] Test concurrent user scenarios
  - [ ] Verify response time requirements
  - [ ] Test database performance under load
  - [ ] Validate auto-scaling behavior

- [ ] **Stress Testing**
  - [ ] Test system limits
  - [ ] Verify graceful degradation
  - [ ] Test recovery procedures
  - [ ] Validate monitoring under stress

---

## 📚 Documentation & Training

### Operational Documentation

- [ ] **Runbook Creation**

  - [ ] Create incident response runbook
  - [ ] Document troubleshooting procedures
  - [ ] Create backup and recovery procedures
  - [ ] Document scaling procedures

- [ ] **Monitoring Documentation**
  - [ ] Document alert procedures
  - [ ] Create escalation procedures
  - [ ] Document maintenance windows
  - [ ] Create performance tuning guide

### Team Training

- [ ] **Operator Training**

  - [ ] Train operators on system architecture
  - [ ] Provide hands-on training sessions
  - [ ] Create training materials
  - [ ] Conduct knowledge transfer sessions

- [ ] **Emergency Procedures**
  - [ ] Train on incident response
  - [ ] Practice disaster recovery procedures
  - [ ] Conduct tabletop exercises
  - [ ] Document lessons learned

---

## 🔄 Automation Opportunities

### Infrastructure as Code (Future Automation)

- [ ] **Terraform Configuration**

  - [ ] Create Terraform modules for infrastructure
  - [ ] Automate database provisioning
  - [ ] Automate load balancer configuration
  - [ ] Automate monitoring setup

- [ ] **Kubernetes Manifests**
  - [ ] Create Helm charts for services
  - [ ] Automate namespace creation
  - [ ] Automate ingress configuration
  - [ ] Automate persistent volume setup

### CI/CD Automation

- [ ] **Deployment Automation**

  - [ ] Automate staging deployments
  - [ ] Automate production deployments
  - [ ] Automate rollback procedures
  - [ ] Automate health checks

- [ ] **Monitoring Automation**
  - [ ] Automate alert rule deployment
  - [ ] Automate dashboard creation
  - [ ] Automate log configuration
  - [ ] Automate backup scheduling

---

## ✅ Pre-Production Checklist

### Final Validation

- [ ] **Security Review**

  - [ ] Complete security audit
  - [ ] Penetration testing completed
  - [ ] Vulnerability assessment passed
  - [ ] Compliance requirements met

- [ ] **Performance Validation**

  - [ ] Load testing completed successfully
  - [ ] Response time requirements met
  - [ ] Throughput requirements met
  - [ ] Resource utilization optimized

- [ ] **Operational Readiness**
  - [ ] Monitoring fully configured
  - [ ] Alerting tested and working
  - [ ] Backup procedures validated
  - [ ] Recovery procedures tested

### Go-Live Preparation

- [ ] **Team Readiness**

  - [ ] Operations team trained
  - [ ] On-call procedures established
  - [ ] Escalation paths defined
  - [ ] Communication channels established

- [ ] **Documentation Complete**
  - [ ] All runbooks created
  - [ ] Troubleshooting guides complete
  - [ ] Architecture documentation updated
  - [ ] API documentation current

---

## 🚀 Quick Start (TL;DR)

### For Operators Who Need the High-Level Steps:

1. **🔧 Repository Setup** (30 minutes)

   - Protect master branch, set up environments, add GitHub secrets

2. **🔐 Secrets Configuration** (2 hours)

   - Provision databases, cache, vector store, add all secrets to GitHub

3. **🗄️ Database Setup** (1 hour)

   - Run migrations, configure users, set up monitoring

4. **📦 Container Registry** (30 minutes)

   - Enable GHCR, configure authentication

5. **🌐 Deployment Infrastructure** (2 hours)

   - Set up domain, SSL, load balancer, reverse proxy

6. **📊 Monitoring Setup** (2 hours)

   - Deploy Prometheus/Grafana, configure alerts, set up logging

7. **🧪 Testing & Validation** (1 hour)

   - Run smoke tests, validate multi-agent workflow

8. **🔒 Security Hardening** (1 hour)
   - Configure firewalls, enable security scanning, set up secret rotation

**Total Estimated Time: 8-10 hours for complete setup**

### Critical Path Items:

- Database provisioning and migration
- Secrets configuration
- SSL/TLS setup
- Basic monitoring configuration

### Post-Setup:

- Performance testing and optimization
- Security audit and penetration testing
- Team training and documentation
- Incident response procedures

---

**📞 Support:** For questions about this checklist, contact the development team or refer to the main documentation in `/docs/`.

**🔄 Updates:** This checklist should be reviewed and updated quarterly or when significant infrastructure changes are made.
