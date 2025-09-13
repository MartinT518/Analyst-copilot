# Getting Started

This guide will walk you through the process of setting up and running the Analyst Copilot system for the first time.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

- Docker
- Docker Compose
- Python 3.11+
- `pip` and `virtualenv`

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-repo/analyst-copilot.git
   cd analyst-copilot
   ```

2. **Set up the environment:**

   Create a virtual environment and install the required dependencies:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r acp-ingest/requirements.txt
   ```

3. **Configure the environment variables:**

   Copy the example environment file and customize it with your settings:

   ```bash
   cp .env.example .env
   ```

   Edit the `.env` file to provide your database credentials, API keys, and other configuration options.

4. **Start the services:**

   Use Docker Compose to start all the required services:

   ```bash
   docker-compose up -d
   ```

## First Ingestion

Once the services are running, you can perform your first data ingestion using the command-line interface (CLI).

1. **Authenticate with the CLI:**

   ```bash
   acp auth login --username your-username --password your-password
   ```

2. **Ingest a file:**

   ```bash
   acp ingest upload --file /path/to/your/data.csv --origin "My Test Data" --sensitivity "low"
   ```

3. **Check the ingestion status:**

   ```bash
   acp ingest status <job-id>
   ```

## Next Steps

Now that you have successfully set up the Analyst Copilot and performed your first ingestion, you can explore the other features of the system:

- **Search your data:** Use the `/api/v1/search` endpoint to perform semantic searches on your ingested data.
- **Explore the API:** Check out the API documentation at `http://localhost:8000/docs` for a complete list of available endpoints.
- **Customize the system:** Learn how to extend the system with your own parsers and services in the [Architecture](./architecture.md) documentation.
