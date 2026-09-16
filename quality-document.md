# Project Quality Standard

## Product boundary

The assessment release provides role-aware schedule viewing and receptionist lesson creation, editing, and soft deletion with revision history. Unsafe writes are rejected immediately. Billing, payroll, curriculum, messaging integration, schedule-analysis pages, and two-way spreadsheet synchronization are excluded.

## Required qualities

- Deterministic and explainable scheduling behavior.
- Clear ownership across domain, services, storage, API, and UI.
- No secret or personal data exposure.
- Visible and recoverable failures.
- Repeatable verification for every passing feature.
- Supplied operational history remains preserved rather than silently repaired.

## Evidence standard

A feature is passing only when automated tests and a documented rehearsal demonstrate its behavior.

## Completion standard

Run verification, update feature state and progress, record evidence, and leave a concrete handoff. Unknown safety behavior remains disabled and explicitly blocked.
