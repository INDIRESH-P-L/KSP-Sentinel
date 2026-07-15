# Zoho Catalyst migration

## What's scaffolded here vs. what needs your login

`catalyst login` is an interactive OAuth device-code flow — nothing in this repo can
complete it. Everything below is either (a) verified against current Catalyst docs and
ready to use, or (b) explicitly marked as needing the CLI wizard to fill in, because its
exact schema isn't published and guessing at it would just hand you a broken config.

| File | Status |
|---|---|
| `catalyst/catalyst.json` | Verified against [catalyst-json docs](https://docs.catalyst.zoho.com/en/cli/v1/project-directory-structure/catalyst-json/). Ready to use. |
| `catalyst/functions/ksp-copilot/main.py` | Real, working Advanced I/O Python function (Flask-based, per [Advanced I/O docs](https://docs.catalyst.zoho.com/en/serverless/help/functions/advanced-io/)). Wraps the existing chatbot engine. |
| `catalyst/functions/ksp-copilot/requirements.txt` | Ready to use. |
| `catalyst/functions/ksp-copilot/catalyst-config.json` | **Not generated.** This file's exact schema isn't in Catalyst's public docs — it's auto-written when you run `catalyst functions:setup` interactively. Don't hand-author it. |
| `.catalystrc` (project linkage) | **Not generated.** Only `catalyst init` (post-login) can create a valid one — it embeds your actual org/project ID. |
| `catalyst/datastore_schema.json` | Self-derived from `backend/app/database/models.py` (34 tables). A checklist for manually creating tables in the Data Store console — not an automated importer, since there's no verified bulk-import format for arbitrary JSON. |

## Manual steps, in order

1. **`catalyst login`** — opens a browser OAuth flow tied to your Zoho account.
2. **`catalyst init`** in the repo root — links this directory to a real Catalyst project (creates `.catalystrc`). Choose "Use existing project directory structure" so it picks up `catalyst/catalyst.json` rather than overwriting it.
3. **Primary backend → AppSail, not Functions.** This repo's FastAPI backend has ~10 routers and a stateful SQLAlchemy layer against SQLite/Postgres — per the roadmap's own service-mapping table, that's an AppSail lift-and-shift target, not something to rewrite endpoint-by-endpoint as Functions. Run `catalyst appsail:deploy` against the existing `backend/` app once `DATABASE_URL` points at your provisioned database. See [AppSail docs](https://docs.catalyst.zoho.com/en/appsail/help/getting-started/) for the exact deploy flow for your plan.
4. **`catalyst functions:setup`** for the `ksp-copilot` function (Python 3.9 runtime) — this generates the real `catalyst-config.json` and installs `zcatalyst-sdk`. Then drop in the `main.py` and `requirements.txt` already in this folder. Treat `catalyst/functions/ksp-copilot/main.py` as the example to follow for any other single-endpoint Function you split out later (item 6 in the roadmap: the chatbot's NL query interface is a natural first candidate).
5. **Data Store** — in the console, create the 34 tables listed in `catalyst/datastore_schema.json`, using it as a column/type/FK checklist (verify each `suggested_datastore_type` against the actual "Add Column" dropdown — that mapping is a best-effort guess, not sourced from Catalyst docs).
6. **Stratus** — create a bucket for FIR scan/photo/evidence uploads (none of this repo's current file-upload code exists yet; this is still a build item, not just a config item).
7. **Signals** — for live map-pulsing anomaly alerts (`/api/crimes/emerging-trends`, already computing real z-score spikes) to push instead of poll.
8. **Authentication** — replace the current demo JWT login (`backend/app/api/auth.py`, hardcoded passwords) with Catalyst Authentication + Data Store RBAC for real jurisdiction-scoped access control (roadmap §8 — this is a real security gap in the current app, not just a Catalyst-specific TODO).

## Regenerating the Data Store schema reference

```
python scripts/export_catalyst_datastore_schema.py > catalyst/datastore_schema.json
```

Re-run after any change to `backend/app/database/models.py`.
