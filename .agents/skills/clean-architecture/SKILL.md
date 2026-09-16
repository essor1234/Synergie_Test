---
name: clean-architecture
description: Preserve the Bright Path dependency boundaries and simple scheduling architecture when adding or reorganizing application code.
---

# Bright Path clean architecture

Keep the application small and make dependencies point toward the scheduling rules.

## Boundaries

- `domain` contains plain Python models and must not import FastAPI, Streamlit, or SQLite.
- `services` owns lesson workflows and inline mutation validation.
- `storage` owns SQLite schema and queries.
- `api` converts HTTP input and output around the services.
- `ui` calls the public API and never reads SQLite directly.

Use simple data structures at boundaries. Do not pass HTTP requests, Streamlit state, or database rows into the domain.

## Scope control

- Prefer the existing layers over adding abstractions.
- Do not add repository interfaces, dependency-injection frameworks, unit-of-work classes, or ORM models unless an observed requirement cannot be handled safely without them.
- Keep one feature in progress and preserve unrelated work.
