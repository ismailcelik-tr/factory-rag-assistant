# Setup Guide

> This guide will be completed once the application layer is scaffolded. The sections below define the expected setup process.

---

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) installed and running
- Sufficient RAM for local inference (Gemma 4 requirements TBD)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd factory-rag-assistant

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies (once pyproject.toml exists)
pip install -e ".[dev]"
```

## Ollama Setup

```bash
# Start the Ollama service
ollama serve

# Pull required models
ollama pull gemma4:e4b
ollama pull nomic-embed-text
```

## Environment Variables

Copy `.env.example` to `.env` and fill in values. Required variables will be documented in `.env.example` once the application layer is created.

```bash
cp .env.example .env
```

## First Run

```bash
# 1. Add documents to data/raw/
# 2. Ingest
python scripts/ingest.py --input data/raw/

# 3. Generate embeddings
python scripts/embed.py

# 4. Test a query
python scripts/chat.py --role tech_service
```
