"""Simulation engine for estimating microservice deployment risk."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence

import networkx as nx
import numpy as np
import pandas as pd

from .config import Settings, get_settings
from .models import (
    DeploymentDecision,
    GraphEdge,
    HistoricalRecord,
    ServiceMetrics,
    SimulationResult,
    SimulationSummary,
)


class RiskEngine:
    """Core risk engine responsible for graph simulation and scoring."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()

    def run_simulation(
        self,
        history: Sequence[HistoricalRecord] | None = None,
        seed: Optional[int] = None,
    ) -> SimulationResult:
        """Create a new simulation using optional history for adjustments."""
        history = list(history or [])
        rng = np.random.default_rng(seed)

        graph = self._generate_dependency_graph(rng)
        blocked_services = self._collect_blocked_services(history)
        services = self._generate_service_metrics(graph, blocked_services, rng)
        summary = self._summarise_services(services)
        edges = [GraphEdge(source=u, target=v) for u, v in graph.edges()]

        return SimulationResult(summary=summary, services=services, edges=edges)

    def build_history_entry(self, result: SimulationResult) -> HistoricalRecord:
        """Convert a simulation result into a persisted history record."""
        return HistoricalRecord(summary=result.summary, services=result.services)

    def update_history(
        self, history: Sequence[HistoricalRecord], new_entry: HistoricalRecord
    ) -> List[HistoricalRecord]:
        """Add a new entry to history whilst enforcing the configured limit."""
        new_history = list(history) + [new_entry]
        if len(new_history) > self._settings.history_limit:
            new_history = new_history[-self._settings.history_limit :]
        return new_history

    def results_to_dataframe(self, result: SimulationResult) -> pd.DataFrame:
        """Convert a simulation result into a pandas DataFrame for export."""
        records = [
            {
                "service_name": metrics.service_name,
                "dependency_impact_score": metrics.dependency_impact_score,
                "rollback_rate": metrics.rollback_rate,
                "change_frequency": metrics.change_frequency,
                "error_spike_history": metrics.error_spike_history,
                "latency_instability": metrics.latency_instability,
                "risk_score": metrics.risk_score,
                "decision": metrics.decision.value,
                "timestamp_utc": result.summary.timestamp_utc.isoformat(),
            }
            for metrics in result.services
        ]
        return pd.DataFrame.from_records(records)

    def _generate_dependency_graph(self, rng: np.random.Generator) -> nx.DiGraph:
        """Create a directed dependency graph with randomised edges."""
        graph = nx.DiGraph()
        service_names = self._settings.service_names
        graph.add_nodes_from(service_names)

        for service in service_names:
            candidates = self._settings.dependency_candidates.get(service, [])
            if not candidates:
                continue
            max_edges = max(1, len(candidates) // 2)
            edge_count = int(rng.integers(0, max_edges + 1))
            chosen = rng.choice(candidates, size=edge_count, replace=False) if edge_count else []
            for dependency in chosen:
                if dependency != service:
                    graph.add_edge(dependency, service)

        # Ensure the graph remains weakly connected by connecting isolated nodes.
        isolated_nodes = list(nx.isolates(graph))
        for node in isolated_nodes:
            other = rng.choice([n for n in service_names if n != node])
            graph.add_edge(other, node)

        return graph

    def _collect_blocked_services(
        self, history: Sequence[HistoricalRecord]
    ) -> set[str]:
        """Identify services that were blocked in the latest history entry."""
        if not history:
            return set()
        latest = history[-1]
        return {
            metrics.service_name
            for metrics in latest.services
            if metrics.decision == DeploymentDecision.BLOCK_DEPLOYMENT
        }

    def _generate_service_metrics(
        self,
        graph: nx.DiGraph,
        blocked_services: Iterable[str],
        rng: np.random.Generator,
    ) -> List[ServiceMetrics]:
        """Produce risk metrics for each service in the graph."""
        blocked_lookup = set(blocked_services)
        betweenness = nx.betweenness_centrality(graph, normalized=True, weight=None)
        in_degrees = dict(graph.in_degree())
        max_in_degree = max(in_degrees.values()) if in_degrees else 1

        services: List[ServiceMetrics] = []
        for service in graph.nodes():
            dependency_score = self._normalise_to_percentage(
                0.6 * betweenness.get(service, 0.0)
                + 0.4 * (in_degrees.get(service, 0) / max_in_degree if max_in_degree else 0)
            )

            rollback_rate = float(rng.uniform(0, 100))
            if service in blocked_lookup:
                rollback_rate *= 0.85

            metrics = {
                "dependency_impact_score": dependency_score,
                "rollback_rate": self._normalise_to_percentage(rollback_rate / 100),
                "change_frequency": float(rng.uniform(0, 100)),
                "error_spike_history": float(rng.uniform(0, 100)),
                "latency_instability": float(rng.uniform(0, 100)),
            }

            for key in ("change_frequency", "error_spike_history", "latency_instability"):
                metrics[key] = round(metrics[key], 2)

            final_metrics = self._build_service_metrics(service, metrics)
            services.append(final_metrics)

        return sorted(services, key=lambda item: item.service_name)

    def _build_service_metrics(
        self, service: str, metrics: dict[str, float]
    ) -> ServiceMetrics:
        """Calculate the final service metrics record."""
        dependency_score = metrics["dependency_impact_score"]
        rollback_rate = metrics["rollback_rate"]
        change_frequency = metrics["change_frequency"]
        error_spike_history = metrics["error_spike_history"]
        latency_instability = metrics["latency_instability"]

        risk_score = (
            0.4 * dependency_score
            + 0.2 * rollback_rate
            + 0.15 * change_frequency
            + 0.15 * error_spike_history
            + 0.1 * latency_instability
        )

        risk_score = round(min(max(risk_score, 0), 100), 2)
        decision = self._classify_risk(risk_score)

        return ServiceMetrics(
            service_name=service,
            dependency_impact_score=round(dependency_score, 2),
            rollback_rate=round(rollback_rate, 2),
            change_frequency=round(change_frequency, 2),
            error_spike_history=round(error_spike_history, 2),
            latency_instability=round(latency_instability, 2),
            risk_score=risk_score,
            decision=decision,
        )

    @staticmethod
    def _classify_risk(score: float) -> DeploymentDecision:
        """Translate a risk score into a deployment decision."""
        if score < 40:
            return DeploymentDecision.AUTO_APPROVE
        if score < 70:
            return DeploymentDecision.MANUAL_REVIEW
        return DeploymentDecision.BLOCK_DEPLOYMENT

    @staticmethod
    def _normalise_to_percentage(value: float) -> float:
        """Normalise a floating point number into the 0-100 range."""
        if value < 0:
            return 0.0
        if value > 1:
            return 100.0
        return value * 100

    def _summarise_services(self, services: Sequence[ServiceMetrics]) -> SimulationSummary:
        """Build a summary for the provided service metrics."""
        risks = [service.risk_score for service in services]
        average_risk = round(float(np.mean(risks)), 2) if risks else 0.0
        highest = max(services, key=lambda item: item.risk_score)
        blocked = [svc.service_name for svc in services if svc.decision == DeploymentDecision.BLOCK_DEPLOYMENT]

        return SimulationSummary(
            average_risk=average_risk,
            highest_risk_service=highest.service_name,
            highest_risk_score=highest.risk_score,
            blocked_services=blocked,
            blocked_count=len(blocked),
            timestamp_utc=datetime.now(timezone.utc),
        )


