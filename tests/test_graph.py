"""Tests for depagon.graph."""

import pytest

from depagon.graph import DependencyGraph


def test_cycle_two_nodes() -> None:
    g = DependencyGraph()
    g.add_edge("A", "B")
    g.add_edge("B", "A")
    cycles = g.find_cycles()
    assert len(cycles) >= 1
    flat = {n for c in cycles for n in c}
    assert "A" in flat and "B" in flat


def test_no_cycle_dag() -> None:
    g = DependencyGraph()
    g.add_edge("A", "B")
    g.add_edge("B", "C")
    assert g.find_cycles() == []


def test_fan_in_out() -> None:
    g = DependencyGraph()
    g.add_edge("A", "B")
    g.add_edge("C", "B")
    g.add_edge("A", "C")
    assert g.fan_in("B") == 2
    assert g.fan_out("A") == 2
    assert g.fan_out("B") == 0
    assert g.fan_in("A") == 0


def test_three_node_cycle() -> None:
    g = DependencyGraph()
    g.add_edge("A", "B")
    g.add_edge("B", "C")
    g.add_edge("C", "A")
    cycles = g.find_cycles()
    assert len(cycles) >= 1


def test_coupling_report() -> None:
    g = DependencyGraph()
    g.add_edge("X", "Y")
    report = g.coupling_report()
    assert report["X"] == (0, 1)
    assert report["Y"] == (1, 0)


def test_add_node_idempotent() -> None:
    g = DependencyGraph()
    g.add_node("A")
    g.add_node("A")
    assert g.nodes().count("A") == 1


def test_self_loop_is_cycle() -> None:
    g = DependencyGraph()
    g.add_edge("A", "A")
    cycles = g.find_cycles()
    assert len(cycles) >= 1
