"""Patch docker-compose.yml with production settings."""
import re

p = r"D:\MyPrograms\rag-knowledge-platform\docker-compose.yml"
with open(p, "r", encoding="utf-8") as f:
    c = f.read()

# Lock ports to localhost
c = c.replace('"5432:5432"', '"127.0.0.1:5432:5432"')
c = c.replace('"8000:8000"', '"127.0.0.1:8000:8000"')

# Add postgres logging + stop_grace_period
c = c.replace(
    "    deploy:\n      resources:\n        limits:\n          memory: 512M",
    """    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    stop_grace_period: 60s
    deploy:
      resources:
        limits:
          memory: 512M""",
)

# Add API healthcheck, logging, stop_grace_period + migrate service
c = c.replace(
    "    deploy:\n      resources:\n        limits:\n          memory: 768M\n\nvolumes:",
    """    healthcheck:
      test: ["CMD", "python", "-c", "import httpx;r=httpx.get('http://localhost:8000/health');exit(0 if r.json().get('database')=='ok' else 1)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    stop_grace_period: 30s
    deploy:
      resources:
        limits:
          memory: 768M

  migrate:
    build:
      context: ./backend
      pull: false
    container_name: zhiku-migrate
    restart: "no"
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+asyncpg://zhiku:${POSTGRES_PASSWORD:-changeme}@postgres:5432/zhiku
    depends_on:
      postgres:
        condition: service_healthy
    command: ["alembic", "upgrade", "head"]
    logging:
      driver: "json-file"
      options:
        max-size: "5m"
        max-file: "1"

volumes:""",
)

c = c.replace(
    "  postgres:\n    build:\n      context: ./docker/postgres\n      pull: false\n    image: zhiku-postgres:16-pgvector\n    container_name: zhiku-postgres\n    restart: unless-stopped",
    """  postgres:
    build:
      context: ./docker/postgres
      pull: false
    image: zhiku-postgres:16-pgvector
    container_name: zhiku-postgres
    restart: unless-stopped""",
)

with open(p, "w", encoding="utf-8") as f:
    f.write(c)
print("OK")
