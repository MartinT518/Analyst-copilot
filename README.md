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
cp config/env.example config/.env
# Edit config/.env with your local endpoints and credentials
```

3. Start the development environment:
```bash
docker-compose up -d
```

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

See [Development Guide](docs/development.md) for detailed development instructions.

## Deployment

See [Deployment Guide](docs/deployment.md) for production deployment instructions.

## License

[Your License Here]

