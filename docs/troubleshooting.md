# Troubleshooting

This guide provides solutions to common problems you may encounter while using the Analyst Copilot system.

## Ingestion Failures

If an ingestion job fails, you can check the logs for more information. The logs are located in the `/app/logs` directory inside the `acp-ingest` container.

Common causes of ingestion failures include:

- **Invalid file format**: Ensure that the file you are uploading is in a supported format.
- **PII detection errors**: If you are using PII detection, make sure that the PII detection service is running and accessible.
- **Embedding errors**: If you are using embeddings, make sure that the embedding service is running and accessible.

## Search Failures

If a search query fails, you can check the logs for more information. The logs are located in the `/app/logs` directory inside the `acp-ingest` container.

Common causes of search failures include:

- **Vector database errors**: Make sure that the vector database is running and accessible.
- **Invalid query**: Ensure that your query is well-formed and does not contain any syntax errors.

## Service Unavailability

If you are unable to access the Analyst Copilot API, you can check the status of the services using the following command:

```bash
docker-compose ps
```

If any of the services are not running, you can try restarting them:

```bash
docker-compose restart <service-name>
```

If the problem persists, you can check the logs for the affected service to get more information.


