from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize("module", ["leaderboard", "leaderboard.boards", "leaderboard.adapters", "leaderboard.cli"])
def test_package_imports(module: str) -> None:
    importlib.import_module(module)


def test_cli_main_returns_zero() -> None:
    from leaderboard.cli import main

    assert main([]) == 0
