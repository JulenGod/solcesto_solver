"""Tests for window-title matching in find_window.

`pygetwindow.getAllWindows` is monkeypatched with fake windows so the matching
logic is exercised without a real desktop.
"""
import types

import pytest

from sol_cesto_solver import capture
from sol_cesto_solver.capture import WindowNotFoundError, find_window


def _win(title: str, width: int = 800, height: int = 600, minimized: bool = False):
    return types.SimpleNamespace(
        title=title, width=width, height=height, isMinimized=minimized, left=0, top=0
    )


def _patch(monkeypatch, windows):
    monkeypatch.setattr(capture.gw, "getAllWindows", lambda: windows)


def test_matches_title_ignoring_spaces(monkeypatch):
    # Default hint "Sol Cesto" must find the real window titled "SolCesto".
    _patch(monkeypatch, [_win("SolCesto")])
    assert find_window("Sol Cesto").size == (800, 600)


def test_match_is_case_insensitive(monkeypatch):
    _patch(monkeypatch, [_win("solcesto")])
    assert find_window("Sol Cesto").size == (800, 600)


def test_picks_the_largest_matching_window(monkeypatch):
    _patch(monkeypatch, [_win("SolCesto", 800, 600), _win("SolCesto (beta)", 1920, 1080)])
    assert find_window("Sol Cesto").size == (1920, 1080)


def test_hyphenated_unrelated_window_does_not_match(monkeypatch):
    # The VS Code window "…sol-cesto-solver - …" must NOT match (hyphens kept).
    _patch(monkeypatch, [_win("demo.png - sol-cesto-solver - Visual Studio Code", 2000, 1200)])
    with pytest.raises(WindowNotFoundError):
        find_window("Sol Cesto")


def test_raises_when_match_is_minimized(monkeypatch):
    _patch(monkeypatch, [_win("SolCesto", minimized=True)])
    with pytest.raises(WindowNotFoundError):
        find_window("Sol Cesto")
