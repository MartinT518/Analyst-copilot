# Analyst Copilot - On-Premises AI-Powered Analysis System

A secure, on-premises system for processing exported Jira/Confluence data and generating developer-ready artifacts using local LLMs and embeddings.

## 🏗️ Architecture Overview

The Analyst Copilot is built as a microservices architecture with the following components:

```mermaid
graph TB
    subgraph "Frontend Layer"
        FE[acp-frontend<br/>React + Vite]
    end

    subgraph "API Gateway Layer"
        NGINX[Nginx<br/>Reverse Proxy]
    end

    subgraph "Microservices Layer"
        INGEST[acp-ingest<br/>FastAPI Service<br/>Port 8000]
        AGENTS[acp-agents<br/>FastAPI Service<br/>Port 8001]
        ANALYZER[acp-code-analyzer<br/>FastAPI Service<br/>Port 8002]
    end

    subgraph "Data Layer"
        PG[(PostgreSQL<br/>Metadata & Audit)]
        REDIS[(Redis<br/>Cache & Sessions)]
        CHROMA[(Chroma<br/>Vector Database)]
    end

    subgraph "External Services"
        LLM[Local LLM<br/>OpenWebUI/vLLM]
        EMBED[Embedding Service<br/>BGE-M3]
        VAULT[HashiCorp Vault<br/>Secrets Management]
    end

    subgraph "Background Processing"
        CELERY[Celery Workers<br/>Background Jobs]
        FLOWER[Flower<br/>Task Monitor<br/>Port 5555]
    end

    subgraph "Monitoring & Observability"
        PROM[Prometheus<br/>Metrics<br/>Port 9090]
        GRAF[Grafana<br/>Dashboards<br/>Port 3000]
    end

    %% Frontend connections
    FE --> NGINX

    %% API Gateway routing
    NGINX --> INGEST
    NGINX --> AGENTS
    NGINX --> ANALYZER

    %% Service interconnections
    INGEST --> AGENTS
    AGENTS --> INGEST

    %% Database connections
    INGEST --> PG
    INGEST --> REDIS
    INGEST --> CHROMA
    AGENTS --> PG
    AGENTS --> REDIS
    ANALYZER --> PG

    %% External service connections
    INGEST --> LLM
    INGEST --> EMBED
    AGENTS --> LLM
    AGENTS --> EMBED
    ANALYZER --> LLM

    %% Vault connections
    INGEST --> VAULT
    AGENTS --> VAULT

    %% Background processing
    CELERY --> INGEST
    CELERY --> PG
    CELERY --> REDIS
    CELERY --> CHROMA

    %% Monitoring connections
    INGEST --> PROM
    AGENTS --> PROM
    ANALYZER --> PROM
    PROM --> GRAF

    %% Styling
    classDef frontend fill:#e1f5fe
    classDef api fill:#f3e5f5
    classDef service fill:#e8f5e8
    classDef data fill:#fff3e0
    classDef external fill:#fce4ec
    classDef background fill:#f1f8e9
    classDef monitoring fill:#e0f2f1

    class FE frontend
    class NGINX api
    class INGEST,AGENTS,ANALYZER service
    class PG,REDIS,CHROMA data
    class LLM,EMBED,VAULT external
    class CELERY,FLOWER background
    class PROM,GRAF monitoring
```

## 📊 Project Status

### ✅ Phase 0: Foundation Rebuild (COMPLETED)

- **Security Hardening**: Removed default SECRET_KEY fallbacks, implemented secure CORS
- **Testing Infrastructure**: Integrated Vitest framework for frontend testing
- **CI/CD Optimization**: Enhanced pipeline with dependency caching and consolidated workflows
- **Database Performance**: Fixed N+1 query problems and optimized connection pooling
- **Error Handling**: Implemented correlation IDs across all services
- **Security Enhancements**: Added HTML sanitization with bleach, JWT revocation lists

### 🚀 Phase 1: Production Readiness (IN PROGRESS)

- **Authentication**: JWT revocation system with Redis
- **Parser Security**: Enhanced XML/HTML parsing with defusedxml and bleach
- **Health Monitoring**: Kubernetes-ready health probes
- **Circuit Breakers**: Resilience patterns for service communication
- **Multi-stage Docker**: Optimized container builds
- **Production Config**: Separate compose files for production deployment

### 📋 Phase 2: Advanced Features (PLANNED)

- **Shared Models**: Consolidated Pydantic schemas across services
- **Streaming Processing**: Large file processing with streaming
- **Advanced Monitoring**: Comprehensive observability stack
- **Performance Optimization**: Database indexing and query optimization

## 🚀 Quick Start

### Prerequisites

- **Docker & Docker Compose**: Version 2.0+
- **Python**: 3.11+ (for development)
- **Local LLM Endpoint**: OpenWebUI/vLLM setup
- **Embedding Service**: BGE-M3 or compatible endpoint

### 1. Clone and Setup

```bash
git clone <repository-url> analyst-copilot
cd analyst-copilot
```

### 2. Environment Configuration

```bash
# Copy environment template
cp env.example .env

# Edit configuration
nano .env
```

**Required Configuration:**

```bash
# Security (REQUIRED - system will fail without these)
SECRET_KEY=your-super-secure-secret-key-change-this-in-production
OPENAI_API_KEY=your-api-key-here

# LLM Configuration (REQUIRED)
LLM_ENDPOINT=https://your-llm-endpoint/openai
EMBEDDING_ENDPOINT=http://your-embedding-endpoint/v1

# Database (Optional - uses defaults if not set)
DATABASE_URL=postgresql://acp_user:acp_password@postgres:5432/acp_db
REDIS_URL=redis://redis:6379/0
```

### 3. Deploy with Docker Compose

```bash
# Start all services
docker-compose up -d

# Check service health
docker-compose ps

# View logs
docker-compose logs -f acp-ingest
```

### 4. Verify Installation

```bash
# Check service health
curl http://localhost:8000/health
curl http://localhost:8001/health

# Access frontend
open http://localhost:3000
```

## 🏢 Production Deployment

### Using Production Compose File

```bash
# Deploy with production configuration
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Environment-Specific Configurations

- **Development**: `docker-compose.yml`
- **Production**: `docker-compose.yml` + `docker-compose.prod.yml`
- **Monitoring**: Add `--profile monitoring` to enable Prometheus/Grafana

## 🔧 Service Details

### Core Services

| Service             | Port | Description                       | Dependencies                      |
| ------------------- | ---- | --------------------------------- | --------------------------------- |
| `acp-ingest`        | 8000 | Document ingestion and processing | PostgreSQL, Redis, Chroma, LLM    |
| `acp-agents`        | 8001 | AI agent orchestration            | PostgreSQL, Redis, Ingest Service |
| `acp-code-analyzer` | 8002 | Code repository analysis          | PostgreSQL, LLM                   |
| `acp-frontend`      | 3000 | React-based web interface         | All backend services              |

### Supporting Services

| Service       | Port | Description                    |
| ------------- | ---- | ------------------------------ |
| PostgreSQL    | 5432 | Metadata and audit storage     |
| Redis         | 6379 | Caching and session storage    |
| Chroma        | 8001 | Vector database for embeddings |
| Celery Worker | -    | Background job processing      |
| Flower        | 5555 | Task monitoring dashboard      |

### Optional Services

| Service    | Port   | Description           | Profile      |
| ---------- | ------ | --------------------- | ------------ |
| Prometheus | 9090   | Metrics collection    | `monitoring` |
| Grafana    | 3000   | Monitoring dashboards | `monitoring` |
| Nginx      | 80/443 | Reverse proxy         | `production` |

## 📚 Key Features

### 🔒 Security

- **On-Premises Processing**: No external API calls
- **JWT Authentication**: With revocation lists
- **Input Sanitization**: HTML/XML parsing with bleach
- **Secure Configuration**: Vault integration support
- **Audit Logging**: Comprehensive activity tracking

### 🧠 AI-Powered Analysis

- **Multi-Format Ingestion**: Jira CSV, Confluence HTML/XML, PDFs, code
- **Semantic Search**: Vector-based knowledge retrieval
- **Agent Orchestration**: Automated workflow processing
- **PII Detection**: Automatic sensitive data handling

### 📊 Observability

- **Structured Logging**: Correlation IDs across services
- **Health Probes**: Kubernetes-ready endpoints
- **Metrics Collection**: Prometheus integration
- **Error Tracking**: Comprehensive exception handling

### 🚀 Performance

- **Optimized Queries**: N+1 query prevention
- **Connection Pooling**: Efficient database connections
- **Background Processing**: Async job handling
- **Circuit Breakers**: Resilience patterns

## 🛠️ Development

### Running Tests

```bash
# Backend tests
pytest

# Frontend tests
cd acp-frontend
npm test

# Full test suite
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

### Code Quality

```bash
# Linting and formatting
ruff format .
ruff check .

# Type checking
mypy acp-ingest/ acp-agents/

# Security scanning
bandit -r acp-ingest/ acp-agents/
```

## 📖 Documentation

- [**Configuration Guide**](docs/configuration.md) - Environment variables and settings
- [**Deployment Guide**](docs/deployment.md) - Production deployment instructions
- [**API Reference**](docs/api-reference.md) - REST API documentation
- [**Security Policy**](SECURITY.md) - Security practices and policies
- [**Contributing Guide**](docs/contributing.md) - Development guidelines

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/your-org/analyst-copilot/issues)
- **Documentation**: [Project Wiki](https://github.com/your-org/analyst-copilot/wiki)
- **Security**: Report security issues to security@your-domain.com

---

**Analyst Copilot** - Empowering analysts with AI-driven automation while maintaining complete data sovereignty and security.
