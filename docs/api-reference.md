# API Reference

This document provides a detailed reference for the Analyst Copilot API. The API is organized around REST principles and uses JSON for all requests and responses.

## Authentication

All API requests must be authenticated using a bearer token. The token should be included in the `Authorization` header of your requests:

```
Authorization: Bearer <your-api-key>
```

## Endpoints

### Ingest API

- **POST /api/v1/ingest/upload**: Upload a file for ingestion.
- **POST /api/v1/ingest/paste**: Paste text content for ingestion.
- **GET /api/v1/ingest/status/{job_id}**: Get the status of an ingest job.
- **GET /api/v1/ingest/jobs**: List all ingest jobs.

### Search API

- **POST /api/v1/search**: Search for knowledge chunks.
- **GET /api/v1/search/similar/{chunk_id}**: Find chunks similar to a specific chunk.

### Health API

- **GET /health**: Check the health of the system and its components.
- **GET /health/live**: Kubernetes liveness probe.
- **GET /health/ready**: Kubernetes readiness probe.

For detailed information about the request and response formats for each endpoint, please refer to the OpenAPI documentation at `http://localhost:8000/docs`.
