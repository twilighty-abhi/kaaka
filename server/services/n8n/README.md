# n8n Self-Hosted with PostgreSQL

Production-ready Docker deployment for [n8n](https://n8n.io/) using PostgreSQL backend, custom Dockerfile extension, health checks, and persistent volumes.

## Directory Structure

```text
n8n/
├── Dockerfile              # Extends n8nio/n8n:latest with extra system & Python tools
├── docker-compose.yml      # Service definitions for n8n & PostgreSQL
├── .env                    # Active environment variables and encryption key
├── .env.example            # Sample environment variables template
├── .gitignore              # Ignores sensitive .env file
└── local-files/            # (Optional) shared folder mounted to /files in container
```

## Quick Start

1. Start all services in detached mode:
   ```bash
   docker compose up -d --build
   ```

2. Check service status and health:
   ```bash
   docker compose ps
   ```

3. View live logs:
   ```bash
   docker compose logs -f n8n
   ```

4. Access the web interface at:
   [http://localhost:5678](http://localhost:5678)

## Management

- **Stop services**:
  ```bash
  docker compose down
  ```

- **Update n8n**:
  ```bash
  docker compose pull
  docker compose up -d --build
  ```

- **Backup PostgreSQL database**:
  ```bash
  docker compose exec -t postgres pg_dump -U n8n -d n8n > n8n_backup.sql
  ```

- **Restore database**:
  ```bash
  cat n8n_backup.sql | docker compose exec -T postgres psql -U n8n -d n8n
  ```
