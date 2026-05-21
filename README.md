# TwinMind

Digital Twin RAG chatbot backend. See `docs/` for architecture, API contract, and token budget.

## Quickstart

```bash
cp .env.example .env  # set ANTHROPIC_API_KEY
make install
make ingest
make query Q="What did Ching-En do at Virtonomy?"
make serve       # FastAPI on :8000
make e2e         # smoke eval against real Anthropic
```

Phase 1: in-memory vector store, stub embedder, Anthropic Haiku 4.5 with prompt caching.
