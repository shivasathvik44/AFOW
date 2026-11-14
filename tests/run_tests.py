#!/usr/bin/env python3
"""Zero-dependency test runner for AFOW using only Python standard library.

Enables instant test execution on minimal Linux / Fedora installations without
requiring pip, virtual environments, or external dependencies like pytest.
"""

from __future__ import annotations

import contextlib
import importlib
import inspect
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class MonkeyPatch:
    """Minimal monkeypatch fixture emulator."""

    def __init__(self):
        self._env_undo = {}

    def setenv(self, key: str, value: str):
        if key not in self._env_undo:
            self._env_undo[key] = os.environ.get(key)
        os.environ[key] = value

    def delenv(self, key: str, raising: bool = True):
        if key not in self._env_undo:
            self._env_undo[key] = os.environ.get(key)
        if key in os.environ:
            del os.environ[key]
        elif raising:
            raise KeyError(key)

    def undo(self):
        for k, v in self._env_undo.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._env_undo.clear()


def run_all_tests() -> int:
    tests_dir = PROJECT_ROOT / "tests"
    test_files = sorted(tests_dir.glob("test_*.py"))

    total = 0
    passed = 0
    failed = 0
    skipped = 0
    failures = []

    print(f"Running AFOW Multi-OS Test Suite (Python {sys.version.split()[0]} on {sys.platform})")
    print("=" * 70)

    start_suite = time.perf_counter()

    for file_path in test_files:
        mod_name = f"tests.{file_path.stem}"
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:
            print(f"\n[ERROR] Failed to import {mod_name}: {e}")
            failed += 1
            failures.append((f"{mod_name}:import", str(e)))
            continue

        test_funcs = [
            (name, func)
            for name, func in inspect.getmembers(mod, inspect.isfunction)
            if name.startswith("test_")
        ]

        # Preserve definition order if possible
        test_funcs.sort(key=lambda item: item[1].__code__.co_firstlineno)

        for name, func in test_funcs:
            total += 1
            test_id = f"{file_path.stem}.py::{name}"
            sig = inspect.signature(func)
            kwargs = {}
            temp_dir = tempfile.mkdtemp(prefix="afow_test_")
            tmp_path = Path(temp_dir)
            mp = MonkeyPatch()
            db_file = tmp_path / "test_history.db"
            mp.setenv("AFOW_DB_PATH", str(db_file))

            try:
                if "tmp_path" in sig.parameters:
                    kwargs["tmp_path"] = tmp_path
                if "monkeypatch" in sig.parameters:
                    kwargs["monkeypatch"] = mp

                t0 = time.perf_counter()
                func(**kwargs)
                dt = (time.perf_counter() - t0) * 1000
                print(f"  PASS  {test_id:<55} ({dt:.1f} ms)")
                passed += 1
            except AssertionError as e:
                failed += 1
                failures.append((test_id, f"AssertionError: {e}"))
                print(f"  FAIL  {test_id:<55}")
            except Exception as e:
                failed += 1
                failures.append((test_id, f"{type(e).__name__}: {e}"))
                print(f"  FAIL  {test_id:<55}")
            finally:
                mp.undo()
                shutil.rmtree(temp_dir, ignore_errors=True)

    elapsed = time.perf_counter() - start_suite
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed, {total} total in {elapsed * 1000:.1f} ms")

    if failures:
        print("\nFailures:")
        for fid, msg in failures:
            print(f"  - {fid}: {msg}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(run_all_tests())
