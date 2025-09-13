# Architecture

The Analyst Copilot system is designed with a microservices architecture to ensure scalability, flexibility, and maintainability. Each component is responsible for a specific set of tasks and communicates with other components through well-defined APIs.

## System Components

The following diagram illustrates the high-level architecture of the Analyst Copilot system:

```mermaid
graph TD
    A[User] --> B{API Gateway}
    B --> C[Ingest Service]
    B --> D[Search Service]
    C --> E[Parsers]
    C --> F[PII Detector]
    C --> G[Text Chunker]
    C --> H[Vector Service]
    D --> H
    H --> I[Chroma DB]
    C --> J[PostgreSQL]
    D --> J
```

- **API Gateway**: The single entry point for all API requests. It handles authentication, rate limiting, and routing to the appropriate microservice.
- **Ingest Service**: Responsible for handling file uploads, text pastes, and orchestrating the ingestion workflow.
- **Search Service**: Provides a semantic search interface to query the ingested data.
- **Parsers**: A collection of modules that extract text and metadata from various file formats (e.g., Jira CSV, Confluence HTML, PDF).
- **PII Detector**: Identifies and redacts personally identifiable information (PII) from the extracted text.
- **Text Chunker**: Splits the processed text into smaller, semantically meaningful chunks for embedding.
- **Vector Service**: Manages the interaction with the vector database, including storing and retrieving vector embeddings.
- **Chroma DB**: The vector database used to store and search for similar vector embeddings.
- **PostgreSQL**: The relational database used to store metadata about ingest jobs, knowledge chunks, and other system information.

## Ingestion Workflow

The following sequence diagram illustrates the data ingestion workflow:

```mermaid
sequenceDiagram
    participant User
    participant Ingest Service
    participant Parser
    participant PII Detector
    participant Text Chunker
    participant Vector Service

    User->>Ingest Service: Upload file
    Ingest Service->>Parser: Parse file
    Parser-->>Ingest Service: Return documents
    Ingest Service->>PII Detector: Process documents
    PII Detector-->>Ingest Service: Return redacted documents
    Ingest Service->>Text Chunker: Chunk documents
    Text Chunker-->>Ingest Service: Return chunks
    Ingest Service->>Vector Service: Embed and store chunks
    Vector Service-->>Ingest Service: Confirm storage
    Ingest Service-->>User: Confirm ingestion
```

## Technology Stack

- **Backend**: Python, FastAPI
- **Database**: PostgreSQL, Chroma DB
- **Messaging**: Redis, Celery
- **Frontend**: (To be determined)
- **Deployment**: Docker, Docker, Docker, Docker, Docker, Docker, Docker, Docker, Docker, Docker, Docker, Docker, Docker, Docker, Docker, Docker, Docker, Docker, Docker Compose
