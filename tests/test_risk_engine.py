"""Unit tests for the risk engine simulation logic."""

from __future__ import annotations

import pytest

from app.models import DeploymentDecision, SimulationResult
from app.risk_engine import RiskEngine


def _run_deterministic_simulation(seed: int) -> SimulationResult:
    engine = RiskEngine()
    return engine.run_simulation(history=[], seed=seed)


def test_risk_score_formula_consistency() -> None:
    """Ensure the published weighted formula matches computed risk scores."""
    result = _run_deterministic_simulation(seed=123)
    metric = result.services[0]

    expected = round(
        0.4 * metric.dependency_impact_score
        + 0.2 * metric.rollback_rate
        + 0.15 * metric.change_frequency
        + 0.15 * metric.error_spike_history
        + 0.1 * metric.latency_instability,
        2,
    )
    assert metric.risk_score == pytest.approx(expected, abs=0.01)


def test_dependency_graph_contains_edges() -> None:
    """The generated dependency graph should expose at least one edge."""
    result = _run_deterministic_simulation(seed=321)
    assert result.edges, "Expected at least one dependency edge in the graph."

    services = {metric.service_name for metric in result.services}
    edge_nodes = {edge.source for edge in result.edges} | {edge.target for edge in result.edges}
    assert edge_nodes.issubset(services), "Edges should reference known services."


def test_decision_thresholds_reflect_risk_score() -> None:
    """Validate that deployment decisions align with risk thresholds."""
    result = _run_deterministic_simulation(seed=777)
    for metric in result.services:
        if metric.risk_score < 40:
            assert metric.decision == DeploymentDecision.AUTO_APPROVE
        elif metric.risk_score < 70:
            assert metric.decision == DeploymentDecision.MANUAL_REVIEW
        else:
            assert metric.decision == DeploymentDecision.BLOCK_DEPLOYMENT


