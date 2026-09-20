# ClearanceOS / TowFit

Pitch prototype for a Georgia mobility competition. A rig mounted on a patrol car moves a disabled vehicle out of a live lane when the vehicle can be put into neutral. **TowFit** is the rule engine that says GREEN / YELLOW / RED before anyone deploys it.

TowFit does not replace operator judgment or authorize a move. It provides a documented safety recommendation based on vehicle, rig, and scene constraints.

> Status: **Phase 0** (scaffold, schemas, config). The rule engine, API endpoint and console UI come in later phases. Full setup steps are written in Phase 7.

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
