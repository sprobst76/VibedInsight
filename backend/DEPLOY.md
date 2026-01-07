# VibedInsight Deployment

Für VPS mit bestehendem ai-lab Setup (Traefik + Ollama).

## Voraussetzungen

- Bestehendes ai-lab Setup unter `/srv/ai-lab`
- Docker Netzwerk `ai-lab` existiert
- Ollama + Traefik laufen bereits

## Quick Install (mit Deploy-Script)

```bash
cd /srv
git clone https://github.com/sprobst76/VibedInsight.git vibedinsight
cd vibedinsight
./deploy.sh install
```

Das Script fragt nach der Domain und generiert automatisch ein sicheres Passwort.

## Deploy-Script Befehle

| Befehl | Beschreibung |
|--------|--------------|
| `./deploy.sh install` | Erstinstallation |
| `./deploy.sh update` | Aktualisieren (git pull + rebuild) |
| `./deploy.sh status` | Status + Health Check |
| `./deploy.sh logs` | API Logs anzeigen |
| `./deploy.sh logs postgres` | DB Logs anzeigen |
| `./deploy.sh backup` | Datenbank-Backup erstellen |
| `./deploy.sh restart` | Services neu starten |
| `./deploy.sh stop` | Services stoppen |

## Manuelle Installation

### 1. Repository klonen

```bash
cd /srv
git clone https://github.com/sprobst76/VibedInsight.git vibedinsight
```

### 2. Konfiguration

```bash
cd vibedinsight/backend
cp .env.example .env
nano .env
```

Setze:
```bash
DOMAIN=deine-domain.com
POSTGRES_PASSWORD=$(openssl rand -base64 24)
```

### 3. Starten

```bash
docker compose up -d
```

### 4. Prüfen

```bash
curl https://insight.lab.DEINE_DOMAIN/health
```

## Struktur auf VPS

```
/srv/vibedinsight/
├── docker-compose.yml
├── .env
├── Dockerfile
├── app/
│   ├── main.py
│   ├── models/
│   ├── routers/
│   └── services/
└── data/
    └── postgres/        # Automatisch erstellt
```

## Ressourcen

| Service    | RAM Limit | RAM Reserved |
|------------|-----------|--------------|
| PostgreSQL | 256 MB    | 128 MB       |
| API        | 256 MB    | 64 MB        |
| **Gesamt** | 512 MB    | 192 MB       |

Ollama wird aus ai-lab mitgenutzt.

## Updates

```bash
cd /srv/vibedinsight
git pull
docker compose build --no-cache api
docker compose up -d api
```

## Backup

```bash
# Backup
docker exec vibedinsight-postgres pg_dump -U vibedinsight vibedinsight > backup_$(date +%Y%m%d).sql

# Restore
cat backup.sql | docker exec -i vibedinsight-postgres psql -U vibedinsight vibedinsight
```

## Flutter App

Vor dem Release-Build:

```dart
// lib/config/api_config.dart
static const String productionUrl = 'https://insight.lab.DEINE_DOMAIN';
static const bool isProduction = true;
```

```bash
cd app
flutter build apk --release
```
