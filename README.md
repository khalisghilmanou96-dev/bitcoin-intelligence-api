# Bitcoin Intelligence API

A self-hosted Bitcoin intelligence API powered by continuous data ingestion, hybrid retrieval, vector search, and a local large language model.

Bitcoin Intelligence API is designed as an API-first knowledge system for developers who want to integrate Bitcoin-focused search and question answering into their own applications.

The system continuously collects public Bitcoin information, indexes it into a PostgreSQL/pgvector knowledge base, retrieves relevant evidence using hybrid search, and generates grounded answers through a configurable LLM.

> This project is specialized exclusively in Bitcoin.

> The current release is V2.1 and represents the foundation of a continuously updated Bitcoin intelligence engine.

## Features

- FastAPI REST API
- Bitcoin-only question filtering
- Hourly web crawling
- Content extraction and relevance filtering
- SHA-256 content deduplication
- Document versioning
- PostgreSQL knowledge base
- pgvector semantic search
- Local embeddings with Ollama
- Hybrid vector + PostgreSQL full-text retrieval
- Chunk-based RAG
- Evidence sufficiency checks
- Source citations
- Citation validation
- Local LLM generation with Ollama
- Background indexing worker
- Docker Compose deployment
- Automatic OpenAPI documentation
- Source-available licensing

## Architecture

```text
Public Bitcoin Sources
        |
        v
Crawler / Ingestion
        |
        v
Extraction + Bitcoin Relevance Filtering
        |
        v
PostgreSQL + pgvector
        |
        v
Chunking + Embeddings
        |
        v
Hybrid Retrieval
(Vector + Full-Text Search)
        |
        v
Evidence Guard
        |
        v
RAG Context
        |
        v
Local / Configurable LLM
        |
        v
Citation Validation
        |
        v
FastAPI
        |
        +--> Applications
        +--> Services
        +--> Research Tools
        +--> Optional Frontends
```

## Current Stack

- Python 3.12
- FastAPI
- PostgreSQL 17
- pgvector
- SQLAlchemy
- Ollama
- Qwen3 8B
- nomic-embed-text
- Docker Compose

The default local configuration uses:

```text
LLM:       qwen3:8b
Embeddings: nomic-embed-text
```

Other providers can be supported through configuration as the project evolves.

## Knowledge Pipeline

The system maintains its knowledge base independently from the LLM.

New information does not require retraining the language model.

Instead, the pipeline works as follows:

```text
Discover
   |
Fetch
   |
Extract
   |
Filter
   |
Deduplicate
   |
Store
   |
Chunk
   |
Embed
   |
Retrieve
   |
Generate
```

This allows the knowledge base to be updated frequently while keeping model inference independent from ingestion.

## Initial Sources

Seed sources are configured in:

```text
config/seed_sources.yaml
```

The initial source set focuses on public Bitcoin technical and educational resources.

The crawler is intentionally bounded and configurable. The project does not claim to crawl the entire Internet.

## Requirements

For the default fully local configuration:

- Docker
- Docker Compose
- Ollama
- PostgreSQL/pgvector through Docker
- Enough memory to run the selected LLM

The default Qwen3 8B model requires several gigabytes of memory. Hardware requirements depend on the selected model and inference backend.

## Installation

Clone the repository and enter the project directory.

Create the local environment file:

```bash
cp .env.example .env
```

Change the example database password in `.env`.

The PostgreSQL password used in `POSTGRES_PASSWORD` must match the password contained in `DATABASE_URL`.

Example:

```env
POSTGRES_PASSWORD=replace-with-a-secure-password
DATABASE_URL=postgresql+psycopg://bitcoin:replace-with-a-secure-password@db:5432/bitcoin
```

Do not commit `.env`.

## Local LLM Setup

Install Ollama and pull the default models:

```bash
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

Make sure Ollama is running.

Example local configuration:

```env
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen3:8b
LLM_TIMEOUT_SECONDS=300

EMBEDDING_BASE_URL=http://host.docker.internal:11434/v1
EMBEDDING_API_KEY=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_TIMEOUT_SECONDS=90
```

## Start the Stack

```bash
docker compose up --build
```

Or start it in the background:

```bash
docker compose up -d --build
```

Check the services:

```bash
docker compose ps
```

## API

By default:

```text
API:     http://localhost:8000
Swagger: http://localhost:8000/docs
Health:  http://localhost:8000/v1/health
```

### Health

```bash
curl http://localhost:8000/v1/health
```

### Ask a Bitcoin Question

```bash
curl -X POST http://localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is a UTXO?",
    "max_sources": 4
  }'
```

The API currently accepts questions in English.

A successful generated response includes:

- the generated answer;
- whether LLM generation succeeded;
- supporting documents and chunks;
- source URLs;
- retrieval scores;
- the latest knowledge-base update timestamp.

### Search the Knowledge Base

```bash
curl "http://localhost:8000/v1/search?q=Taproot&limit=10"
```

This endpoint exposes hybrid retrieval results directly and is useful for search applications and retrieval diagnostics.

### Latest Documents

```bash
curl http://localhost:8000/v1/latest
```

### Sources

```bash
curl http://localhost:8000/v1/sources
```

### Model Information

```bash
curl http://localhost:8000/v1/model/info
```

## RAG Safety and Grounding

The `/v1/ask` pipeline includes multiple deterministic safeguards.

```text
Question
   |
Bitcoin Domain Guard
   |
Hybrid Retrieval
   |
Evidence Guard
   |
Relevance Reranking
   |
Document Deduplication
   |
LLM Generation
   |
Citation Validation
   |
Response
```

### Domain Guard

Questions without a recognized Bitcoin signal are rejected before expensive LLM generation.

Bitcoin comparisons with other systems can still be accepted when Bitcoin is explicitly part of the question.

### Evidence Guard

Retrieval alone does not guarantee that the knowledge base contains enough information to answer a question.

The evidence guard checks whether retrieved documents contain sufficient question-specific evidence before generation is allowed.

### Citation Validation

Generated answers must contain citations referring to sources actually supplied to the model.

Invalid or missing citations cause the generated response to be rejected.

Citation validation currently verifies citation references. It does not yet prove that every individual claim is semantically entailed by its cited excerpt.

## Retrieval

V2.1 uses hybrid retrieval combining:

- pgvector cosine similarity;
- PostgreSQL full-text search;
- lexical fallback search.

Documents are divided into overlapping chunks before embedding.

Default chunk configuration:

```env
CHUNK_SIZE_CHARS=1800
CHUNK_OVERLAP_CHARS=250
```

The indexer hashes chunks and avoids re-indexing unchanged content.

## Continuous Updates

The crawler periodically searches configured sources for new or changed Bitcoin content.

Default interval:

```env
CRAWL_INTERVAL_SECONDS=3600
```

This corresponds to one crawl cycle per hour.

The indexer runs independently and processes new or changed documents.

Default interval:

```env
INDEX_INTERVAL_SECONDS=300
```

The system therefore updates its external knowledge without retraining the LLM.

## Running Tests

```bash
docker compose exec api pytest -q
```

The test suite currently covers core crawler relevance and RAG safeguards including:

- Bitcoin domain detection;
- unrelated-query rejection;
- evidence sufficiency;
- citation extraction;
- citation validation.

## Security

The current project is intended as a self-hosted foundation.

Before exposing an instance directly to the public Internet, production deployments should add or verify:

- API authentication
- rate limiting
- request quotas
- HTTPS
- restrictive CORS
- crawler SSRF protection
- domain-level crawl rate limits
- secure secret management
- structured logging
- monitoring
- resource limits

Never commit `.env`, API credentials, private keys, or production database passwords.

## Current Limitations

V2.1 is an engineering foundation rather than a claim of complete Bitcoin knowledge.

Current limitations include:

- bounded source discovery;
- English-only questions;
- lexical components in evidence validation;
- local LLM latency depends heavily on hardware;
- citation validation does not yet perform claim-level entailment;
- crawler politeness and discovery mechanisms require further expansion;
- no distributed crawling or indexing queue yet.

## Roadmap

Potential future improvements include:

- robots.txt support
- sitemap discovery
- RSS/Atom ingestion
- native Git and GitHub ingestion
- deeper BIP ingestion
- per-domain rate limiting
- Redis-backed queues
- source trust scoring
- semantic reranking
- stronger claim-level grounding
- configurable LLM providers
- streaming generation
- on-chain data
- mempool intelligence
- Lightning Network data
- market and macroeconomic context
- historical event correlation
- anomaly detection
- uncertainty estimation
- distributed crawling

## API-First Design

Bitcoin Intelligence API is designed so that other software can use the intelligence layer without depending on a bundled frontend.

Potential integrations include:

- Bitcoin applications
- research platforms
- developer tools
- dashboards
- monitoring systems
- educational applications
- AI agents
- internal knowledge systems

A frontend can be built separately on top of the REST API.

## License

See `LICENSE`.

The repository uses a source-available licensing approach. Review the license terms before commercial redistribution, hosted resale, SaaS use, or other commercial deployment.

The included license text is not legal advice.