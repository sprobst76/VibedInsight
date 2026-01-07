# VibedInsight Backend Deployment Guide

This guide covers deploying VibedInsight on a VPS with existing Traefik and Ollama infrastructure.

## Prerequisites

- VPS running Linux (Ubuntu 22.04+ recommended)
- Docker & Docker Compose v2
- Existing setup with:
  - **Traefik** reverse proxy with HTTPS
  - **Ollama** running with llama3.2 model
  - Docker network for shared services (e.g., `ailab_ai-lab`)

## Quick Install

```bash
cd /srv
git clone https://github.com/sprobst76/VibedInsight.git vibedinsight
cd vibedinsight
./deploy.sh install
```

The script will prompt for your domain and generate a secure database password.

## Deploy Script Commands

| Command | Description |
|---------|-------------|
| `./deploy.sh install` | Initial installation |
| `./deploy.sh update` | Update (git pull + rebuild) |
| `./deploy.sh status` | Show status + health check |
| `./deploy.sh logs` | Show API logs |
| `./deploy.sh logs postgres` | Show database logs |
| `./deploy.sh backup` | Create database backup |
| `./deploy.sh restart` | Restart services |
| `./deploy.sh stop` | Stop services |

## Manual Installation

### 1. Clone Repository

```bash
cd /srv
git clone https://github.com/sprobst76/VibedInsight.git vibedinsight
cd vibedinsight/backend
```

### 2. Configure Environment

```bash
cp .env.example .env
nano .env
```

Set the required values:

```bash
# Your domain (matches your Traefik setup)
DOMAIN=your-domain.com

# Strong password for PostgreSQL
POSTGRES_PASSWORD=$(openssl rand -base64 24)

# Timezone (optional)
TZ=Europe/Berlin

# Ollama model (optional, default: llama3.2)
OLLAMA_MODEL=llama3.2
```

### 3. Verify Network Name

Check your existing Docker network:

```bash
docker network ls | grep ai-lab
```

The docker-compose.yml expects `ailab_ai-lab`. If your network has a different name, update the network section in docker-compose.yml accordingly.

### 4. Deploy

```bash
docker compose up -d
```

### 5. Verify

```bash
curl https://insight.lab.YOUR_DOMAIN/health
```

Expected response: `{"status": "healthy"}`

## VPS Directory Structure

```
/srv/vibedinsight/
├── deploy.sh
├── backend/
│   ├── docker-compose.yml
│   ├── .env
│   ├── Dockerfile
│   └── app/
│       ├── main.py
│       ├── models/
│       ├── routers/
│       └── services/
└── data/
    └── postgres/        # Created automatically
```

## Resource Limits

| Service | RAM Limit | RAM Reserved |
|---------|-----------|--------------|
| PostgreSQL | 256 MB | 128 MB |
| API | 256 MB | 64 MB |
| **Total** | 512 MB | 192 MB |

Ollama is shared from the existing ai-lab setup.

## Traefik Configuration

The docker-compose.yml includes Traefik labels for automatic routing:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.vibedinsight.rule=Host(`insight.lab.${DOMAIN}`)"
  - "traefik.http.routers.vibedinsight.entrypoints=websecure"
  - "traefik.http.routers.vibedinsight.tls.certresolver=cloudflare"
  - "traefik.http.services.vibedinsight.loadbalancer.server.port=8000"
```

Adjust to match your Traefik configuration.

## Updates

Using deploy script:

```bash
./deploy.sh update
```

Or manually:

```bash
cd /srv/vibedinsight
git pull
docker compose build --no-cache api
docker compose up -d api
```

## Database Management

### Backup

```bash
# Using deploy script
./deploy.sh backup

# Or manually
docker exec vibedinsight-postgres pg_dump -U vibedinsight vibedinsight > backup_$(date +%Y%m%d).sql
```

### Restore

```bash
cat backup.sql | docker exec -i vibedinsight-postgres psql -U vibedinsight vibedinsight
```

### Reset Database

```bash
docker compose down
rm -rf data/postgres
docker compose up -d
```

## Troubleshooting

### API won't start

```bash
# Check PostgreSQL status
docker compose ps
docker compose logs postgres

# Verify database is ready
docker exec vibedinsight-postgres pg_isready -U vibedinsight
```

### Cannot reach API externally

```bash
# Test locally first
docker exec vibedinsight-api curl -f http://localhost:8000/health

# Check Traefik logs
docker logs traefik 2>&1 | grep vibedinsight
```

### Ollama connection fails

```bash
# Verify Ollama is on the same network
docker network inspect ailab_ai-lab | grep ollama

# Test from API container
docker exec vibedinsight-api curl http://ollama:11434/api/tags
```

### Processing stuck in "pending"

```bash
# Check API logs for errors
docker compose logs api | grep -i error

# Verify Ollama model is available
docker exec ollama ollama list
```

## Flutter App Configuration

Before building the release APK, update the API URL:

```dart
// app/lib/config/api_config.dart
static const String productionUrl = 'https://insight.lab.YOUR_DOMAIN';
static const bool isProduction = true;
```

Then build:

```bash
cd app
flutter build apk --release
```

## Security Notes

1. **Change default passwords** - Never use example passwords
2. **Firewall** - Only expose ports 80/443 via Traefik
3. **Network isolation** - API only accessible via Traefik
4. **Database** - PostgreSQL not exposed externally
