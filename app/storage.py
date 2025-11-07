"""In-memory storage utilities for simulation history and exports."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence, TYPE_CHECKING

from .config import Settings, get_settings
from .models import ExportResponse, HistoricalRecord, SimulationResult

if TYPE_CHECKING:  # pragma: no cover
    from .risk_engine import RiskEngine


class SimulationStorage:
    """Stateful helper that tracks simulation history and handles exports."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._history: List[HistoricalRecord] = []
        self._latest_result: Optional[SimulationResult] = None

    @property
    def history(self) -> List[HistoricalRecord]:
        """Return a copy of the stored simulation history."""
        return list(self._history)

    @property
    def latest_result(self) -> Optional[SimulationResult]:
        """Return the most recent simulation result, if available."""
        return self._latest_result

    def record(
        self, entry: HistoricalRecord, *, result: Optional[SimulationResult] = None
    ) -> None:
        """Persist a new history entry while observing the configured limit."""
        self._history.append(entry)
        if len(self._history) > self._settings.history_limit:
            self._history = self._history[-self._settings.history_limit :]
        if result is not None:
            self._latest_result = result

    def clear(self) -> None:
        """Erase all stored history."""
        self._history.clear()
        self._latest_result = None

    def snapshot(self) -> Sequence[HistoricalRecord]:
        """Obtain a read-only snapshot of the history."""
        return tuple(self._history)

    def export(self, engine: "RiskEngine", result: SimulationResult) -> ExportResponse:
        """Persist the provided result to a timestamped CSV file."""
        dataframe = engine.results_to_dataframe(result)

        timestamp = result.summary.timestamp_utc.strftime("%Y%m%dT%H%M%SZ")
        filename = f"risk_estimator_{timestamp}.csv"
        export_path = self._settings.export_directory / filename
        export_path.parent.mkdir(parents=True, exist_ok=True)

        dataframe.to_csv(export_path, index=False)

        return ExportResponse(
            export_path=str(export_path.resolve()),
            record_count=len(dataframe),
            generated_at_utc=datetime.now(timezone.utc),
        )


