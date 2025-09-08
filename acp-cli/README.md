# ACP CLI - Analyst Copilot Command Line Interface

A powerful command-line interface for interacting with Analyst Copilot services.

## Installation

### From Source

```bash
cd acp-cli
pip install -e .
```

### Development Installation

```bash
cd acp-cli
pip install -e ".[dev]"
```

## Quick Start

1. **Initialize the CLI**:
   ```bash
   acp init
   ```

2. **Configure services**:
   ```bash
   acp config set-service ingest --url http://localhost:8000
   acp config set-service agents --url http://localhost:8001
   ```

3. **Check service status**:
   ```bash
   acp status
   ```

4. **Upload a document**:
   ```bash
   acp ingest upload document.pdf
   ```

5. **Search the knowledge base**:
   ```bash
   acp ingest search "user authentication"
   ```

6. **Start an agent workflow**:
   ```bash
   acp agents clarify "Analyze the login process"
   ```

## Commands

### Global Commands

- `acp init` - Initialize CLI configuration
- `acp status` - Check status of all services
- `acp version` - Show version information

### Ingest Service Commands

- `acp ingest upload <file>` - Upload a document
- `acp ingest paste <content>` - Paste content for ingestion
- `acp ingest search <query>` - Search the knowledge base
- `acp ingest jobs` - List ingestion jobs
- `acp ingest status <job-id>` - Get job status
- `acp ingest health` - Check ingest service health

### Agents Service Commands

- `acp agents start <workflow-type>` - Start a workflow
- `acp agents status <workflow-id>` - Get workflow status
- `acp agents workflows` - List workflows
- `acp agents clarify <request>` - Generate clarifying questions
- `acp agents synthesize <requirements>` - Generate AS-IS to TO-BE docs
- `acp agents tasks <requirements>` - Generate developer tasks
- `acp agents verify <output>` - Verify output against KB
- `acp agents health` - Check agents service health

### Configuration Commands

- `acp config show` - Show current configuration
- `acp config set-service <service>` - Set service configuration
- `acp config set-output <format>` - Set output format
- `acp config set-verbose <true|false>` - Set verbose mode
- `acp config set-debug <true|false>` - Set debug mode
- `acp config reset` - Reset to defaults
- `acp config validate` - Validate configuration

## Configuration

The CLI stores configuration in `~/.acp/config.yaml`. You can also use environment variables:

### Environment Variables

- `ACP_INGEST_URL` - Ingest service URL
- `ACP_AGENTS_URL` - Agents service URL
- `ACP_CODE_ANALYZER_URL` - Code analyzer service URL
- `ACP_INGEST_API_KEY` - Ingest service API key
- `ACP_AGENTS_API_KEY` - Agents service API key
- `ACP_CODE_ANALYZER_API_KEY` - Code analyzer service API key
- `ACP_OUTPUT_FORMAT` - Default output format (table, json, yaml)
- `ACP_VERBOSE` - Enable verbose output (true/false)
- `ACP_DEBUG` - Enable debug mode (true/false)
- `ACP_LOG_FILE` - Log file path

### Configuration File Example

```yaml
ingest_service:
  url: http://localhost:8000
  api_key: your-api-key
  timeout: 30

agents_service:
  url: http://localhost:8001
  api_key: your-api-key
  timeout: 30

code_analyzer_service:
  url: http://localhost:8002
  api_key: your-api-key
  timeout: 30

output_format: table
verbose: false
debug: false
config_dir: /home/user/.acp
```

## Output Formats

The CLI supports multiple output formats:

- **table** (default) - Human-readable tables
- **json** - JSON format
- **yaml** - YAML format

Set the default format:
```bash
acp config set-output json
```

Or use the `--format` option:
```bash
acp ingest jobs --format json
```

## Examples

### Document Ingestion

```bash
# Upload a PDF document
acp ingest upload document.pdf

# Upload with metadata
acp ingest upload document.pdf --metadata source=confluence --metadata team=engineering

# Paste text content
acp ingest paste "This is some content to analyze" --type text

# Check ingestion job status
acp ingest status job-123
```

### Knowledge Base Search

```bash
# Basic search
acp ingest search "user authentication"

# Search with filters
acp ingest search "API endpoints" --filter source=confluence --filter team=backend

# Limit results
acp ingest search "database schema" --limit 5
```

### Agent Workflows

```bash
# Generate clarifying questions
acp agents clarify "Improve the user onboarding process"

# Synthesize documentation
acp agents synthesize "User registration system" --current "Manual email verification"

# Generate developer tasks
acp agents tasks "Implement OAuth2 authentication" --priority high

# Verify output
acp agents verify "The system should use JWT tokens for authentication"
```

### Advanced Usage

```bash
# Start workflow with JSON input file
acp agents start clarifier --input workflow-input.json

# Start workflow with inline data
acp agents start synthesizer --data requirements="New API" --data priority="high"

# Monitor workflow progress
acp agents status workflow-456

# List recent workflows
acp agents workflows --limit 20
```

## Error Handling

The CLI provides clear error messages and exit codes:

- Exit code 0: Success
- Exit code 1: General error
- Exit code 2: Configuration error

Use verbose mode for detailed error information:
```bash
acp --verbose ingest upload document.pdf
```

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black acp_cli/
isort acp_cli/
```

### Type Checking

```bash
mypy acp_cli/
```

### Linting

```bash
flake8 acp_cli/
```

## Support

For issues and questions:
1. Check the troubleshooting guide in the main documentation
2. Validate your configuration: `acp config validate`
3. Check service status: `acp status`
4. Enable debug mode: `acp --debug <command>`

