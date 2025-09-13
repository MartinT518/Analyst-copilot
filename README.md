# Analyst Copilot - On-Premises AI-Powered Analysis System

A secure, on-premises system for processing exported Jira/Confluence data and generating developer-ready artifacts using local LLMs and embeddings.

## Architecture Overview

The Analyst Copilot is built as a microservices architecture with the following components:

- **acp-ingest**: Core ingestion service for processing exported data
- **Vector Database**: Chroma for semantic search and retrieval
- **Metadata Database**: PostgreSQL for structured data and audit logs
- **Local LLM Integration**: OpenWebUI/vLLM proxy integration
- **Embedding Service**: Local BGE-M3 endpoint integration

## Key Features

- **Secure On-Premises Processing**: No external API calls, all processing happens locally
- **Multi-Format Ingestion**: Supports Jira CSV, Confluence HTML/XML, PDFs, and manual paste
- **PII Detection & Redaction**: Automatic detection and redaction of sensitive information
- **Semantic Chunking**: Intelligent document chunking with metadata preservation
- **Audit Logging**: Comprehensive audit trail for all operations
- **Role-Based Access Control**: Analyst, Reviewer, and Admin roles

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Access to local OpenWebUI/vLLM endpoint
- Access to local embedding endpoint

### Development Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd analyst-copilot
```

2. Copy and configure environment variables:
```bash
cp env.example .env
# Edit .env with your local endpoints and credentials
```

3. **IMPORTANT**: Configure secure secrets in `.env`:
```bash
# These MUST be set - system will fail to start without them
SECRET_KEY=your-secure-secret-key-change-this-in-production
JWT_SECRET_KEY=your-jwt-secret-key-change-this-in-production
ENCRYPTION_KEY=your-encryption-key-change-this-in-production

# OAuth2 configuration (required for authentication)
OAUTH2_CLIENT_ID=your-oauth2-client-id
OAUTH2_CLIENT_SECRET=your-oauth2-client-secret
OAUTH2_AUTHORIZATION_URL=https://your-auth-provider.com/oauth/authorize
OAUTH2_TOKEN_URL=https://your-auth-provider.com/oauth/token
OAUTH2_USERINFO_URL=https://your-auth-provider.com/oauth/userinfo
OAUTH2_REDIRECT_URI=http://localhost:3000/auth/callback
```

4. Start the development environment:
```bash
docker-compose up -d
```

5. **Create initial admin user** (first time only):
```bash
cd acp-ingest
python scripts/bootstrap_admin.py
```

6. **Security Note**: Change the admin password immediately after first login!

4. Install CLI tool:
```bash
cd acp-ingest
pip install -e .
```

5. Test the installation:
```bash
acp ingest --help
```

### Basic Usage

#### Upload a Jira export:
```bash
acp ingest --source ./exports/jira_export.csv --origin customerX --sensitivity confidential
```

#### Paste a single ticket:
```bash
acp paste --text "Ticket content..." --customer customerX --ticket jira-1234
```

#### Check processing status:
```bash
acp status <job_id>
```

## API Documentation

Once running, visit `http://localhost:8000/docs` for interactive API documentation.

## Security Considerations

- All processing occurs on-premises with no external API calls
- PII is automatically detected and redacted before embedding
- Raw exports are stored encrypted
- Comprehensive audit logging for compliance
- Role-based access control

## Development

### Pre-commit Hooks Setup

To ensure consistent code quality and formatting, we use pre-commit hooks. Set them up once:

```bash
# Install pre-commit
pip install pre-commit

# Install the git hook scripts
pre-commit install

# Optional: Run against all files
pre-commit run --all-files
```

The pre-commit hooks will automatically:
- Format code with Black
- Sort imports with isort
- Lint with flake8
- Run security scans with Bandit
- Check for common issues (trailing whitespace, large files, etc.)

### Development Workflow

1. **Clone and setup**:
```bash
git clone <repository-url>
cd Analyst-copilot
pip install -r acp-ingest/requirements.txt
pre-commit install
```

2. **Make changes** and commit:
```bash
git add .
git commit -m "Your commit message"
# Pre-commit hooks run automatically
```

3. **If hooks fail**, fix the issues and commit again:
```bash
# Hooks will auto-fix formatting issues
git add .
git commit -m "Fix formatting issues"
```

See [Development Guide](docs/development.md) for detailed development instructions.

## Deployment

See [Deployment Guide](docs/deployment.md) for production deployment instructions.

## License

[Your License Here]
