# CLI Reference

The Analyst Copilot comes with a command-line interface (CLI) that allows you to interact with the system from your terminal. The CLI is built using `click` and provides a user-friendly way to manage your data and perform common tasks.

## Installation

The CLI is automatically installed when you install the `acp-ingest` package. If you haven't already, you can install it with pip:

```bash
pip install -e acp-ingest
```

## Commands

### `acp auth`

- **`acp auth login`**: Authenticate with the Analyst Copilot API.
- **`acp auth logout`**: Log out from the Analyst Copilot API.

### `acp ingest`

- **`acp ingest upload`**: Upload a file for ingestion.
- **`acp ingest paste`**: Paste text content for ingestion.
- **`acp ingest status`**: Get the status of an ingest job.
- **`acp ingest list`**: List all ingest jobs.

### `acp search`

- **`acp search query`**: Search for knowledge chunks.
- **`acp search similar`**: Find chunks similar to a specific chunk.

For more information about the available options for each command, you can use the `--help` flag:

```bash
acp ingest upload --help
```


