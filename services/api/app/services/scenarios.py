import json
from pathlib import Path

from pydantic import ValidationError

from app.api.schemas import ScenarioLoad, ScenarioSummary


class ScenarioStore:
    """Reads the demo scenario fixtures. They hold inputs only; nothing here computes or stores a verdict."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _load_all(self) -> dict[str, ScenarioLoad]:
        out: dict[str, ScenarioLoad] = {}
        for path in sorted(self.directory.glob("*.json")):
            try:
                scenario = ScenarioLoad.model_validate(json.loads(path.read_text()))
            except (OSError, ValueError, ValidationError) as exc:
                raise ValueError(f"scenario fixture {path.name} is invalid: {exc}") from exc
            out[scenario.id] = scenario
        return out

    def list(self) -> list[ScenarioSummary]:
        return [ScenarioSummary(id=s.id, title=s.title, description=s.description) for s in self._load_all().values()]

    def get(self, scenario_id: str) -> ScenarioLoad | None:
        return self._load_all().get(scenario_id)
