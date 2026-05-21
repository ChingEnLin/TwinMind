# QueryPal — Personal Project

## Summary
QueryPal is a natural-language-to-SQL assistant that Ching-En built as a personal project. It targets read-only analytics queries against Postgres warehouses.

## Stack
The backend is FastAPI with a thin LLM adapter layer; the frontend is a small React widget. QueryPal uses retrieval-augmented prompting over the warehouse's information schema to keep the model grounded.

## Outcome
QueryPal was open-sourced on GitHub under the ChingEnLin account and demonstrates Ching-En's interest in grounded LLM tooling and developer ergonomics.
