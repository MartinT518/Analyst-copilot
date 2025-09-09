# Analyst Copilot

An on-premises AI-powered analyst automation system that transforms manual analysis workflows into intelligent, automated processes while maintaining complete data sovereignty and enterprise security.

## 🚀 Features

- **Document Ingestion**: Automated parsing and processing of Jira exports, Confluence pages, PDFs, and Markdown files
- **Semantic Search**: Vector-based search with PII detection and redaction
- **AI Agent Orchestration**: Multi-agent workflows for clarification, synthesis, task generation, and verification
- **Enterprise Security**: RBAC, audit trails, rate limiting, and comprehensive security scanning
- **Production Monitoring**: Structured logging, Prometheus metrics, distributed tracing, and Grafana dashboards
- **Modern CI/CD**: GitHub Actions with comprehensive testing, security scanning, and automated deployment

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   acp-ingest    │    │   acp-agents    │    │   acp-cli       │
│   (Port 8001)   │    │   (Port 8002)   │    │   (Local)       │
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
```

## 🛠️ Quick Start

### Prerequisites

- Python 3.10+ 
- Docker and Docker Compose
- Git

### Local Development

1. **Clone the repository**:
   ```bash
   git clone https://github.com/MartinT518/Analyst-copilot.git
   cd Analyst-copilot
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Install development dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Start services**:
   ```bash
   docker-compose -f docker-compose.local.yml up -d
   ```

5. **Install and configure CLI**:
   ```bash
   cd acp-cli
   pip install -e .
   acp init
   acp config set-service ingest --url http://localhost:8001
   acp config set-service agents --url http://localhost:8002
   ```

6. **Verify installation**:
   ```bash
   acp status
   ```

## 🧪 Testing

### Run All Tests
```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run unit tests with coverage
acp test run --coverage

# Run integration tests
acp test integration

# Run performance tests
acp test performance --duration 60 --users 10

# Run security scans
acp scan all
```

### CI/CD Pipeline

The project uses GitHub Actions for comprehensive CI/CD:

- **Code Quality**: Black, isort, flake8, mypy across Python 3.10-3.12
- **Security**: Bandit, pip-audit, TruffleHog, Trivy container scanning
- **Testing**: Unit tests, integration tests with real databases, performance testing
- **Coverage**: 80% minimum coverage requirement with Codecov integration
- **Deployment**: Automated staging and production deployment with rollback capabilities

### GitHub Actions Services

CI uses GitHub Actions services instead of docker-compose:
- **PostgreSQL 15**: For database testing
- **Redis 7**: For caching and job queue testing  
- **Chroma**: For vector database testing

## 📊 Monitoring & Observability

### Structured Logging
```bash
# View logs with filtering
acp monitor logs --service ingest --level ERROR

# Follow logs in real-time
acp monitor logs --follow

# Search logs
acp monitor logs --search "authentication"
```

### Metrics & Dashboards
```bash
# View service metrics
acp monitor metrics --service ingest

# Open monitoring dashboard
acp monitor dashboard

# Check service health
acp monitor health
```

### Distributed Tracing
```bash
# View traces
acp monitor traces --service ingest

# Filter by operation
acp monitor traces --operation document_upload
```

Access monitoring interfaces:
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Jaeger**: http://localhost:16686

## 🔒 Security

### Security Scanning
```bash
# Run all security scans
acp scan all

# Scan dependencies for vulnerabilities
acp scan dependencies --severity high

# Scan code for security issues
acp scan code --confidence medium

# Scan for exposed secrets
acp scan secrets

# Scan container images
acp scan containers --severity critical
```

### Security Features
- **Authentication**: API key-based authentication with JWT support
- **Authorization**: Role-based access control (RBAC)
- **Rate Limiting**: Configurable rate limits per endpoint
- **Security Headers**: HSTS, CSP, XSS protection
- **Input Validation**: Comprehensive input sanitization
- **PII Detection**: Automatic detection and redaction of sensitive data
- **Audit Logging**: Immutable audit trails with hash chain integrity

## 🚀 Deployment

### Staging Deployment
```bash
acp deploy staging
```

### Production Deployment
```bash
acp deploy production --backup
```

### Container Images
Images are automatically built and pushed to GitHub Container Registry:
- `ghcr.io/martint518/analyst-copilot/acp-ingest:latest`
- `ghcr.io/martint518/analyst-copilot/acp-agents:latest`

## 🛠️ CLI Commands

### Configuration
```bash
acp config show                    # Show current configuration
acp config set-service ingest --url http://localhost:8001
acp config validate               # Validate configuration
```

### Document Management
```bash
acp ingest upload document.pdf    # Upload document
acp ingest search "query text"    # Search documents
acp ingest status job-id          # Check job status
```

### Agent Workflows
```bash
acp agents clarify "Analyze authentication system"
acp agents workflow start --type synthesis
acp agents workflow status workflow-id
```

### Testing & Quality
```bash
acp test run --service ingest     # Run service tests
acp test lint                     # Run linting
acp test security                 # Run security tests
```

### Monitoring
```bash
acp monitor health                # Check service health
acp monitor logs --follow         # View logs
acp monitor metrics               # View metrics
acp monitor alerts                # View active alerts
```

### Security
```bash
acp scan dependencies             # Scan for vulnerabilities
acp scan code                     # Static code analysis
acp scan secrets                  # Scan for exposed secrets
```

## 📚 Documentation

- **[Infrastructure Guide](docs/infra.md)**: Comprehensive infrastructure documentation
- **[API Reference](docs/api-reference.md)**: Complete API documentation
- **[Architecture](docs/architecture.md)**: System architecture and design
- **[Deployment](docs/deployment.md)**: Deployment procedures and best practices
- **[Troubleshooting](docs/troubleshooting.md)**: Common issues and solutions

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Install pre-commit hooks**: `pre-commit install`
4. **Make your changes** and ensure tests pass: `acp test run`
5. **Run security scans**: `acp scan all`
6. **Commit your changes**: `git commit -m 'Add amazing feature'`
7. **Push to the branch**: `git push origin feature/amazing-feature`
8. **Open a Pull Request**

### Development Standards
- **Code Quality**: Black formatting, isort imports, flake8 linting
- **Type Safety**: mypy type checking required
- **Testing**: 80% minimum test coverage
- **Security**: All security scans must pass
- **Documentation**: Update docs for new features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the [docs/](docs/) directory
- **Issues**: Open an issue on GitHub
- **Discussions**: Use GitHub Discussions for questions

## 🎯 Roadmap

- [x] **Phase 1**: Core infrastructure and CLI tooling
- [x] **Phase 2**: Document ingestion and search
- [x] **Phase 3**: AI agent orchestration
- [x] **Phase 4**: Monitoring and security
- [x] **Phase 5**: CI/CD and deployment automation
- [ ] **Phase 6**: Advanced analytics and reporting
- [ ] **Phase 7**: Multi-tenant support
- [ ] **Phase 8**: Advanced AI capabilities

---

**Built with ❤️ for enterprise analyst teams who demand both automation and control.**

