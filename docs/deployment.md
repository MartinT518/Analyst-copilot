# Deployment

This guide provides instructions for deploying the Analyst Copilot system in a production environment.

## Docker Compose

The easiest way to deploy the Analyst Copilot is by using the provided Docker Compose configuration. This will start all the required services in a containerized environment.

1. **Prerequisites**:
   - Docker
   - Docker Compose

2. **Configuration**:
   - Create a `.env` file from the `.env.example` template and customize it with your production settings.
   - Pay special attention to the `SECRET_KEY`, database credentials, and other security-related settings.

3. **Deployment**:
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

   This will start the application in detached mode. You can view the logs using:

   ```bash
   docker-compose logs -f
   ```

## Kubernetes

For more advanced deployments, you can use the provided Kubernetes manifests to deploy the Analyst Copilot to a Kubernetes cluster.

(This section is a work in progress and will be updated with detailed instructions and manifests in a future release.)

## Manual Deployment

While not recommended for production, you can also deploy the Analyst Copilot manually by following these steps:

1. **Set up the database**: Install and configure PostgreSQL and Chroma DB.
2. **Set up the message broker**: Install and configure Redis.
3. **Configure the application**: Set the environment variables in your shell or using a `.env` file.
4. **Run the application**: Use a production-grade ASGI server like Uvicorn with Gunicorn to run the FastAPI application:

   ```bash
   gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
   ```

5. **Run the Celery worker**:

   ```bash
   celery -A app.worker.celery_app worker -l info
   ```


