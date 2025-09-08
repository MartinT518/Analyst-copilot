# Configuration

The Analyst Copilot system is configured using environment variables. You can set these variables in your shell or by creating a `.env` file in the root of the project.

## Environment Variables

The following table lists all the available environment variables and their default values:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | The connection URL for the PostgreSQL database. | `postgresql://user:password@localhost/acp` |
| `REDIS_URL` | The connection URL for the Redis server. | `redis://localhost:6379/0` |
| `CHROMA_HOST` | The hostname of the Chroma DB server. | `localhost` |
| `CHROMA_PORT` | The port of the Chroma DB server. | `8001` |
| `LLM_ENDPOINT` | The endpoint of the large language model (LLM). | `https://api.openai.com/v1` |
| `EMBEDDING_ENDPOINT` | The endpoint of the embedding model. | `https://api.openai.com/v1` |
| `OPENAI_API_KEY` | Your API key for the OpenAI API. | `your-api-key` |
| `SECRET_KEY` | A secret key for signing JWTs. | `your-secret-key` |
| `JWT_ALGORITHM` | The algorithm to use for JWTs. | `HS256` |
| `JWT_EXPIRE_MINUTES` | The expiration time for JWTs in minutes. | `1440` |
| `DEBUG` | Enable or disable debug mode. | `false` |
| `LOG_LEVEL` | The logging level. | `INFO` |
| `LOG_FORMAT` | The logging format. | `json` |
| `LOG_FILE` | The path to the log file. | `/app/logs/acp-ingest.log` |
| `MAX_FILE_SIZE` | The maximum file size for uploads in bytes. | `104857600` (100MB) |
| `UPLOAD_DIR` | The directory to store uploaded files. | `/app/uploads` |
| `ALLOWED_EXTENSIONS` | A comma-separated list of allowed file extensions. | `csv,html,htm,xml,pdf,md,txt,zip,json` |
| `MAX_CHUNK_SIZE` | The maximum size of text chunks. | `1000` |
| `CHUNK_OVERLAP` | The overlap between text chunks. | `200` |
| `BATCH_SIZE` | The batch size for processing embeddings. | `10` |
| `MAX_CONCURRENT_JOBS` | The maximum number of concurrent ingest jobs. | `5` |
| `PII_DETECTION_ENABLED` | Enable or disable PII detection. | `true` |
| `PII_REDACTION_MODE` | The PII redaction mode (`redact` or `replace`). | `redact` |
| `PRESIDIO_ENABLED` | Enable or disable Presidio for PII detection. | `false` |
| `PROMETHEUS_ENABLED` | Enable or disable Prometheus metrics. | `false` |
| `GRAFANA_PASSWORD` | The password for the Grafana admin user. | `admin` |
| `ACP_BASE_URL` | The base URL of the Analyst Copilot API. | `http://localhost:8000` |
| `ACP_API_KEY` | The API key for the Analyst Copilot CLI. | `your-api-key` |
| `RELOAD` | Enable or disable auto-reloading for development. | `false` |
| `WORKERS` | The number of Uvicorn workers. | `1` |
| `COMPOSE_PROJECT_NAME` | The name of the Docker Compose project. | `acp` |
| `COMPOSE_FILE` | The path to the Docker Compose file. | `docker-compose.yml` |


