"""Visualisation helpers for the risk estimator service."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import networkx as nx

from .models import ServiceMetrics, SimulationResult


def render_dependency_graph(result: SimulationResult, output_path: Path) -> Path:
    """Render a dependency graph highlighting service risk scores."""
    _ensure_parent_directory(output_path)

    graph = nx.DiGraph()
    for service in result.services:
        graph.add_node(service.service_name, risk=service.risk_score)
    for edge in result.edges:
        graph.add_edge(edge.source, edge.target)

    risk_values = [metrics.risk_score for metrics in result.services]
    if not risk_values:
        raise ValueError("Cannot render graph without service metrics.")

    normalised_colors = _get_colour_gradient(risk_values)
    pos = nx.spring_layout(graph, seed=42, k=0.7)

    plt.figure(figsize=(10, 8))
    nx.draw_networkx_edges(graph, pos, edge_color="#cccccc", arrows=True, arrowstyle="-|>", arrowsize=12)
    nx.draw_networkx_nodes(
        graph,
        pos,
        node_color=normalised_colors,
        node_size=1200,
        cmap=plt.cm.get_cmap("RdYlGn_r"),
    )
    nx.draw_networkx_labels(graph, pos, font_size=9, font_weight="bold")

    sm = plt.cm.ScalarMappable(cmap=plt.cm.get_cmap("RdYlGn_r"))
    sm.set_array([])
    cbar = plt.colorbar(sm, shrink=0.75)
    cbar.ax.set_ylabel("Risk Score", rotation=270, labelpad=15)

    plt.title("Microservice Dependency Risk Map")
    plt.tight_layout()
    plt.savefig(output_path, format="png", dpi=220)
    plt.close()

    return output_path


def render_risk_barchart(result: SimulationResult, output_path: Path) -> Path:
    """Render a bar chart comparing risk scores across services."""
    _ensure_parent_directory(output_path)

    services = _sort_services_by_risk(result.services)
    names = [service.service_name for service in services]
    risks = [service.risk_score for service in services]
    colours = _get_colour_gradient(risks)

    plt.figure(figsize=(12, 6))
    bars = plt.bar(names, risks, color=colours)
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("Risk Score")
    plt.ylim(0, 100)
    plt.title("Service Risk Comparison")

    for bar, risk in zip(bars, risks, strict=False):
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, height + 1, f"{risk:.1f}", ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, format="png", dpi=220)
    plt.close()

    return output_path


def _ensure_parent_directory(path: Path) -> None:
    """Create the parent directory for the output file if necessary."""
    path.parent.mkdir(parents=True, exist_ok=True)


def _sort_services_by_risk(services: Sequence[ServiceMetrics]) -> list[ServiceMetrics]:
    """Return services ordered by risk score descending."""
    return sorted(services, key=lambda svc: svc.risk_score, reverse=True)


def _get_colour_gradient(values: Iterable[float]) -> list[float]:
    """Normalise values for use in colour gradients."""
    values_list = list(values)
    if not values_list:
        return []
    min_value, max_value = min(values_list), max(values_list)
    if max_value == min_value:
        return [0.5] * len(values_list)
    return [(value - min_value) / (max_value - min_value) for value in values_list]


