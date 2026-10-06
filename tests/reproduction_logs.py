"""Synthetic controller tests: complete logs and fail-fast exit propagation.

The child boundary is mocked, so these checks test evidence capture, not POSIX
resource enforcement. All generated outputs are retained under --output.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import patch


def run(output: Path) -> dict:
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("owned_reproduction_controller", root / "reproduce.py")
    controller = importlib.util.module_from_spec(spec)
    # An import-only substitute is needed on Windows; every used resource
    # attribute is explicitly supplied below as synthetic test accounting.
    with patch.dict(sys.modules, {"resource": types.ModuleType("resource")}):
        spec.loader.exec_module(controller)
    synthetic_usage = types.SimpleNamespace(ru_utime=0, ru_stime=0)
    synthetic_resource = types.SimpleNamespace(RUSAGE_CHILDREN=0,
                                               getrusage=lambda _: synthetic_usage)
    cases = (("success", 0, "arrangement"), ("nonzero", 7, "exact"),
             ("timeout", 124, "exact"))
    records = []
    for name, expected_exit, group in cases:
        target = output / name
        stdout = "complete stdout: \u03b1\n" + "s" * 6000
        stderr = "complete stderr: \u03b2\n" + "e" * 6000
        def child(*args, **kwargs):
            if name == "timeout":
                raise subprocess.TimeoutExpired(args[0], 35,
                                                output=stdout.encode("utf-8"),
                                                stderr=stderr.encode("utf-8"))
            return subprocess.CompletedProcess(args[0], expected_exit, stdout, stderr)
        console = io.StringIO()
        exit_code = 0
        with patch.object(controller, "resource", synthetic_resource), \
             patch.object(controller.os, "chdir"), \
             patch.object(controller.os, "sched_getaffinity", return_value={0}, create=True), \
             patch.object(controller.os, "sched_setaffinity", create=True), \
             patch.object(controller.subprocess, "run", side_effect=child) as invoked, \
             patch.object(sys, "argv", ["reproduce.py", "--group", group, "--output", str(target)]), \
             contextlib.redirect_stdout(console), contextlib.redirect_stderr(console):
            try:
                controller.main()
            except SystemExit as exc:
                exit_code = exc.code
        assert exit_code == expected_exit, (name, exit_code)
        assert invoked.call_count == 1, "failed child must stop subsequent chunks"
        account = json.loads((target / ("accounting_" + group + ".json")).read_text(encoding="utf-8"))
        assert len(account["records"]) == 1
        row = account["records"][0]
        full_stderr = stderr + ("\n35-second chunk timeout\n" if name == "timeout" else "")
        assert Path(row["stdout_log"]).read_text(encoding="utf-8") == stdout
        assert Path(row["stderr_log"]).read_text(encoding="utf-8") == full_stderr
        assert row["stderr"] == full_stderr[-4000:]
        assert row["exit_code"] == expected_exit
        (target / "controller-console.txt").write_text(console.getvalue(), encoding="utf-8")
        records.append({"case": name, "exit_code": exit_code,
                        "child_calls": invoked.call_count,
                        "stdout_characters": len(stdout),
                        "stderr_characters": len(full_stderr)})
    return {"synthetic_controller_cases": len(records), "records": records,
            "mismatches": 0,
            "scope": "Mocked child outcomes; no claim of resource-limit enforcement"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not __debug__:
        parser.error("assertions must remain enabled")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = run(output)
    (output / "checks.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
