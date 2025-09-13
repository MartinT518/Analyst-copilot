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

### Health Probes

The services include Kubernetes-ready health probe endpoints:

#### Liveness Probe

- **Endpoint**: `/health/live`
- **Purpose**: Indicates if the process is running
- **Response**: `{"status": "alive", "timestamp": "..."}`
- **Use Case**: Kubernetes can restart the pod if the process is dead

#### Readiness Probe

- **Endpoint**: `/health/ready`
- **Purpose**: Indicates if the service is ready to accept traffic
- **Checks**: Database, Redis, and critical dependencies
- **Use Case**: Kubernetes can route traffic only to ready pods

#### Startup Probe

- **Endpoint**: `/health/startup`
- **Purpose**: Indicates if the application has finished starting up
- **Checks**: Database connectivity and basic initialization
- **Use Case**: Kubernetes waits for startup before running liveness/readiness probes

### Example Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: acp-ingest
spec:
  replicas: 2
  selector:
    matchLabels:
      app: acp-ingest
  template:
    metadata:
      labels:
        app: acp-ingest
    spec:
      containers:
        - name: acp-ingest
          image: acp-ingest:latest
          ports:
            - containerPort: 8000
          env:
            - name: SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: acp-secrets
                  key: secret-key
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: acp-secrets
                  key: database-url
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          startupProbe:
            httpGet:
              path: /health/startup
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 30
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "2Gi"
              cpu: "1000m"
```

### Production Docker Compose

Use the production-specific compose file for production deployments:

```bash
# Deploy with production configuration
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# With monitoring enabled
docker-compose -f docker-compose.yml -f docker-compose.prod.yml --profile monitoring up -d
```

The production compose file includes:

- Resource limits and reservations
- Health checks with proper timeouts
- Internal networking (no direct port exposure)
- Production-ready volume mounts
- Multiple replicas for high availability

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
