# Contributing to VibedInsight

Thank you for your interest in contributing to VibedInsight! This document provides guidelines for contributing.

## Development Setup

### Prerequisites

- Python 3.12+
- Flutter 3.x / Dart 3.x
- Docker & Docker Compose
- PostgreSQL (or use Docker)
- Ollama with llama3.2 model

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"

# Start PostgreSQL (if not running)
docker run -d --name postgres-dev \
  -e POSTGRES_PASSWORD=devpass \
  -e POSTGRES_DB=vibedinsight \
  -p 5432:5432 \
  postgres:16-alpine

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run development server
uvicorn app.main:app --reload --port 8000
```

### Flutter App Setup

```bash
cd app

# Get dependencies
flutter pub get

# Run on connected device or emulator
flutter run

# Run tests
flutter test

# Build APK
flutter build apk --release
```

## Development Principles

These principles guide how we develop VibedInsight:

1. **Plan first** - Before coding, outline the approach (max 7 steps)
2. **Minimal diffs** - Small, reviewable changes per commit
3. **Verify locally** - Run lint/test/format before committing
4. **No premature optimization** - Build MVP first, optimize later
5. **Avoid unnecessary dependencies** - Keep the stack lean
6. **No large refactors** - Without explicit reason and approval

## Code Style

### Python (Backend)

We use **ruff** for linting and formatting:

```bash
# Check for issues
ruff check app/

# Auto-fix issues
ruff check --fix app/

# Format code
ruff format app/
```

Key conventions:
- Type hints for all function parameters and return values
- Async functions for database operations
- Pydantic models for request/response validation
- Docstrings for public functions

### Dart (Flutter)

We follow the official [Dart style guide](https://dart.dev/guides/language/effective-dart/style):

```bash
# Analyze code
flutter analyze

# Format code
dart format .
```

Key conventions:
- Use Riverpod for state management
- Prefer `const` constructors where possible
- Extract widgets into separate files when they grow large

## Git Workflow

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `refactor/description` - Code refactoring
- `docs/description` - Documentation updates

### Commit Messages

Follow conventional commits format:

```
type(scope): description

[optional body]
```

Types:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `refactor` - Code refactoring
- `test` - Adding tests
- `chore` - Maintenance tasks

Examples:
```
feat(api): add bulk delete endpoint
fix(app): handle empty summary state
docs(readme): update installation instructions
```

### Pull Request Process

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Run tests and linting
5. Commit with descriptive messages
6. Push to your fork
7. Open a Pull Request against `main`

### PR Requirements

- [ ] Code follows project style guidelines
- [ ] Tests pass (`flutter test`, `pytest`)
- [ ] Linting passes (`ruff check`, `flutter analyze`)
- [ ] Documentation updated if needed
- [ ] Commit messages follow conventions

## Testing

### Backend Tests

```bash
cd backend
pytest

# With coverage
pytest --cov=app --cov-report=html
```

### Flutter Tests

```bash
cd app

# Unit tests
flutter test

# With coverage
flutter test --coverage
```

## Architecture Guidelines

### Backend

- **Routers**: HTTP endpoint handlers in `app/routers/`
- **Models**: SQLAlchemy models in `app/models/`
- **Schemas**: Pydantic schemas in `app/schemas.py`
- **Services**: Business logic in `app/services/`
- **Database**: Async SQLAlchemy with asyncpg

### Flutter App

- **Screens**: Full-page widgets in `lib/screens/`
- **Widgets**: Reusable components in `lib/widgets/`
- **Providers**: Riverpod state management in `lib/providers/`
- **Models**: Data models in `lib/models/`
- **Services**: API clients in `lib/services/`

## Reporting Issues

When reporting bugs, please include:

1. Description of the issue
2. Steps to reproduce
3. Expected behavior
4. Actual behavior
5. Environment (OS, Flutter version, Python version)
6. Relevant logs or screenshots

## Feature Requests

For feature requests:

1. Check existing issues to avoid duplicates
2. Describe the use case
3. Explain the proposed solution
4. Consider alternatives

## Questions?

Open a GitHub Discussion or Issue for questions about contributing.

---

Thank you for contributing!
