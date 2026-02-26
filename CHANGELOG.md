# Changelog

## v0.3.7-admin-surface

- Usage tracking (`usage_events` table + RLS tenant isolation)
- Admin endpoints: `GET /admin/usage`, `GET /admin/api-keys`, `POST /admin/api-keys/revoke/{key_id}`
- Soft billing guard: `POST /cases` returns 402 after 1000 free-tier `usage_events`
- API key auth dependency instruments every authenticated request with a `usage_events` row (fire-and-forget)
- `api_keys` table extended: `revoked_at TIMESTAMPTZ`, `role TEXT DEFAULT 'user'`
- 40 tests passing
- Alembic head: `b1c2d3e4f505`

## v0.3.6-mvp-surface

- API key authentication (`X-API-Key` header, SHA-256 hash lookup)
- Bootstrap endpoint: `POST /bootstrap` provisions tenant + admin API key (requires `BOOTSTRAP_TOKEN`)
- v1 Case API: `POST /cases`, `GET /cases/{id}`, `POST /cases/{id}/finalize`, `POST /cases/{id}/verify-replay`
- Billing skeleton: `billing_status TEXT DEFAULT 'free'`, `api_client_id TEXT NULL` added to `cases`
- `api_keys` table created
- 33 tests passing
- Alembic head: `a96162dee369`

## v0.3.5-access-audit

- Enterprise access audit logging (`access_logs` table)
- RLS policy on `access_logs` enforcing tenant isolation
- `GET /cases/{id}` and `POST /cases/{id}/verify-replay` write `VIEW` / `VERIFY` audit entries
- Alembic head: `0e397e47435e`

## v0.3.4-replay-verified

- Replay verification endpoint: `POST /cases/{id}/verify-replay`
- Deterministic result signature validated on replay
- Immutable finalize: re-finalization of already-finalized case is rejected
- Alembic head: `7ad8653` (tag ref)

## v0.3.3-finalize-hardened

- Cryptographic result signature (SHA-256 of canonical JSON ranking snapshot)
- Finalization hardening: concurrent finalize race prevented via `WHERE status = 'draft'`
- `result_signature` and `ranking_snapshot` columns added to `cases`
