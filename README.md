# ClearanceOS / TowFit

Pitch prototype for a Georgia mobility competition. A rig mounted on a patrol car moves a disabled vehicle out of a live lane when the vehicle can be put into neutral. **TowFit** is the rule engine that says GREEN / YELLOW / RED before anyone deploys it.

TowFit does not replace operator judgment or authorize a move. It provides a documented safety recommendation based on vehicle, rig, and scene constraints.

> Status: **Phase 2 done** (config, rule engine, API with Decision Records). The console UI is Phase 3. Full setup steps are written in Phase 7.

## The rule in one paragraph

The rig mounts on a patrol car. If the disabled vehicle can be put or forced into neutral and nothing hard rules it out, it is **GREEN**: move it to a safe place and clear the lane. Hard triggers (wrong class, over capacity, not upright, fire, axle damage, too few grippable tires, outside the rig's dimensions, or cannot go into neutral) are **RED**: send the right wrecker. **YELLOW** means a human must confirm first: neutral not yet confirmed, no safe place to move it, or reduced grip. Airbags, high severity, a heavy-but-legal weight and a grade with traffic risk are shown as advisories and never change the verdict.

## Layout

| Path | What |
|---|---|
| `config/` | `fleet.yaml`, `vehicle_specs.yaml`, `assumptions.yaml`. Every unvalidated number lives here. |
| `services/api/` | FastAPI + Pydantic v2 + SQLModel (SQLite). Rule engine and Decision Records. |
| `apps/web/` | Next.js (App Router, TypeScript). The TowFit Console. |
| `fixtures/` | `scenarios/` (inputs for the three demo cases) and `camera/` (canned frames, not a real model). |
| `docs/` | Generated assumptions doc (Phase 7). |

## Run the API tests

```bash
cd services/api
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Needs Python 3.12 or newer (developed on 3.14).

## Run the API

```bash
cd services/api
.venv/bin/uvicorn app.main:create_app --factory --reload --port 8000
```

Interactive docs are at https://clearanceos.vercel.app/docs for the live deployment, or `/docs` on the port you started it on. It runs fully offline. Everything is under `/v1`:

| Endpoint | What |
|---|---|
| `GET /v1/fleet` | Units and rig capacities, each with the status of the assumption behind it |
| `GET /v1/vehicle-specs` | Curb-weight and dimension lookup, every row with its source |
| `GET /v1/scenarios`, `POST /v1/scenarios/{id}/load` | The three demo cases as **inputs only** |
| `POST /v1/towfit/evaluate` | Compute the verdict from the submitted fields and log a Decision Record |
| `GET /v1/decisions`, `GET /v1/decisions/{id}` | The audit log, filterable by unit, verdict and date |
| `POST /v1/decisions/{id}/events` | Record what the operator actually did, and outcomes (append-only) |
| `GET` / `PUT /v1/assumptions` | Read and live-edit `config/assumptions.yaml`; the next evaluation uses the edit |

After changing the API, regenerate the schema the web client is built from (a test fails if it is stale):

```bash
cd services/api && .venv/bin/python scripts/export_openapi.py
```
