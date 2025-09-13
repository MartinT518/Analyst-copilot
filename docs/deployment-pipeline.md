# Deployment Pipeline Documentation

## Overview

The Analyst Copilot deployment pipeline is a secure, reliable, and production-ready system that follows enterprise best practices for CI/CD.

## Key Features

### 🔒 Security First
- **No secrets in files**: All secrets passed via environment variables
- **Comprehensive scanning**: Both ingest and agents images scanned with Trivy
- **Manual approval**: Production deployments require manual approval
- **Secure registry**: Uses GitHub Container Registry (GHCR)

### 🚀 Reliability
- **Versioned deployments**: Uses specific image tags, not 'latest'
- **Real rollback**: Deploys previous stable version on failure
- **Health checks**: Comprehensive service health validation
- **Performance testing**: k6 load testing with realistic thresholds

### 🛠️ Modern Tooling
- **Docker Compose Action**: Official GitHub action for compose
- **Buildx caching**: Optimized Docker builds with layer caching
- **Multi-stage builds**: Efficient image creation
- **Environment-specific configs**: Separate staging/production settings

## Pipeline Jobs

### 1. Build and Push Images
- Builds both `acp-ingest` and `acp-agents` images
- Pushes to GitHub Container Registry
- Uses buildx for optimized builds
- Generates metadata and tags

### 2. Security Scan
- Scans both images with Trivy
- Uploads results to GitHub Security tab
- Blocks deployment on critical vulnerabilities

### 3. Deploy to Staging
- Deploys to staging environment
- Runs health checks and smoke tests
- Uses environment-specific configuration

### 4. Deploy to Production
- **Requires manual approval** via GitHub Environments
- Deploys to production environment
- Enhanced health checks and monitoring
- SSL-enabled configuration

### 5. Performance Tests
- k6 load testing with realistic scenarios
- Tests core APIs (ingest, search)
- Performance thresholds and metrics

### 6. Rollback
- Automatic rollback on deployment failure
- Uses previous stable image tags
- Maintains service availability

### 7. Update Documentation
- Updates deployment history
- Tracks deployment metadata
- Maintains audit trail

### 8. Notifications
- Success/failure notifications
- Ready for Slack/Teams integration
- Clear status reporting

## Usage

### Manual Deployment
```bash
# Deploy to staging
gh workflow run deploy.yml -f environment=staging

# Deploy to production (requires approval)
gh workflow run deploy.yml -f environment=production

# Deploy specific image tag
gh workflow run deploy.yml -f environment=staging -f image_tag=v1.2.3
```

### Environment Variables Required

#### Staging Secrets
- `STAGING_DATABASE_URL`
- `STAGING_REDIS_URL`
- `STAGING_SECRET_KEY`
- `STAGING_JWT_SECRET_KEY`
- `STAGING_ENCRYPTION_KEY`
- `STAGING_LLM_ENDPOINT`
- `STAGING_EMBEDDING_ENDPOINT`

#### Production Secrets
- `PRODUCTION_DATABASE_URL`
- `PRODUCTION_REDIS_URL`
- `PRODUCTION_SECRET_KEY`
- `PRODUCTION_JWT_SECRET_KEY`
- `PRODUCTION_ENCRYPTION_KEY`
- `PRODUCTION_LLM_ENDPOINT`
- `PRODUCTION_EMBEDDING_ENDPOINT`

#### Shared Secrets
- `OPENAI_API_KEY`
- `GITHUB_TOKEN` (automatically provided)

## Security Considerations

### Secrets Management
- ✅ Secrets passed via environment variables
- ✅ No .env files created on disk
- ✅ Secrets not logged or exposed
- ✅ GitHub Secrets for secure storage

### Image Security
- ✅ Trivy vulnerability scanning
- ✅ GitHub Security tab integration
- ✅ Blocking on critical vulnerabilities
- ✅ Regular security updates

### Access Control
- ✅ Manual approval for production
- ✅ Environment protection rules
- ✅ Audit trail for all deployments
- ✅ Role-based access control

## Monitoring and Observability

### Health Checks
- Service availability monitoring
- API endpoint validation
- Database connectivity checks
- External service integration tests

### Performance Monitoring
- Response time thresholds
- Error rate monitoring
- Load testing with k6
- Resource utilization tracking

### Deployment Tracking
- Deployment history documentation
- Version tracking and rollback capability
- Success/failure notifications
- Audit trail maintenance

## Troubleshooting

### Common Issues

1. **Deployment Failure**
   - Check GitHub Actions logs
   - Verify secrets are properly configured
   - Ensure target environment is accessible

2. **Health Check Failures**
   - Verify service configuration
   - Check database connectivity
   - Validate external service endpoints

3. **Security Scan Failures**
   - Review Trivy scan results
   - Update vulnerable dependencies
   - Consider security exceptions if needed

4. **Performance Test Failures**
   - Review k6 test results
   - Check service performance metrics
   - Optimize slow endpoints

### Rollback Procedure
1. Automatic rollback triggers on deployment failure
2. Manual rollback available via workflow dispatch
3. Previous stable version automatically deployed
4. Health checks validate rollback success

## Best Practices

### Before Deployment
- ✅ Run local tests
- ✅ Review security scan results
- ✅ Validate configuration changes
- ✅ Test in staging first

### During Deployment
- ✅ Monitor deployment logs
- ✅ Watch health check results
- ✅ Verify service availability
- ✅ Check performance metrics

### After Deployment
- ✅ Monitor application logs
- ✅ Validate functionality
- ✅ Check performance metrics
- ✅ Update documentation

## Future Enhancements

### Planned Improvements
- [ ] Blue-green deployments
- [ ] Canary releases
- [ ] Automated rollback triggers
- [ ] Enhanced monitoring integration
- [ ] Multi-region deployment support
- [ ] Infrastructure as Code (Terraform)

### Integration Opportunities
- [ ] Slack/Teams notifications
- [ ] PagerDuty integration
- [ ] Grafana dashboards
- [ ] Prometheus metrics
- [ ] ELK stack logging
