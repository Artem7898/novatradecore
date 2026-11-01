"""Run an authenticated Locust benchmark and preserve reproducible measurements."""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--users", type=int, default=5)
    parser.add_argument("--spawn-rate", type=float, default=5)
    parser.add_argument("--duration", default="30s")
    parser.add_argument("--token-client", default="local-ingestor")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--min-success-rps", type=float, default=0)
    parser.add_argument("--max-p95-ms", type=float)
    args = parser.parse_args()
    address = urlsplit(args.host)
    if (
        address.scheme not in {"http", "https"}
        or not address.netloc
        or address.username
        or address.password
        or address.query
        or address.fragment
        or address.path not in {"", "/"}
    ):
        parser.error("--host must be an HTTP(S) origin without credentials, path, query or fragment")
    if args.users < 1 or args.spawn_rate <= 0 or not re.fullmatch(r"[1-9][0-9]*[smh]", args.duration):
        parser.error("users/spawn-rate must be positive; duration must look like 30s, 2m or 1h")
    if not 0 <= args.max_error_rate <= 1 or args.min_success_rps < 0:
        parser.error("invalid error-rate or successful-RPS threshold")
    if args.max_p95_ms is not None and args.max_p95_ms <= 0:
        parser.error("--max-p95-ms must be positive")

    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", override=False)
    token = os.getenv("BENCHMARK_TOKEN", "")
    if not token:
        try:
            tokens = json.loads(os.getenv("INGEST_API_TOKENS", "{}"))
            token = tokens.get(args.token_client, "")
        except (ValueError, AttributeError):
            parser.error("INGEST_API_TOKENS must contain a JSON object")
    if not isinstance(token, str) or not token:
        parser.error("set BENCHMARK_TOKEN or configure --token-client in INGEST_API_TOKENS")
    output = args.output or root / "work" / "benchmarks" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    summary_path = output / "measurements.json"
    environment = os.environ.copy()
    environment["BENCHMARK_TOKEN"] = token
    environment["BENCHMARK_SUMMARY_PATH"] = str(summary_path)
    command = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        str(root / "locustfile.py"),
        "--headless",
        "--host",
        args.host.rstrip("/"),
        "--users",
        str(args.users),
        "--spawn-rate",
        str(args.spawn_rate),
        "--run-time",
        args.duration,
        "--stop-timeout",
        "5",
        "--only-summary",
        "--exit-code-on-error",
        "0",
        "--csv",
        str(output / "locust"),
        "--csv-full-history",
    ]
    started_at = datetime.now(UTC).isoformat()
    with (output / "locust.log").open("w", encoding="utf-8") as log:
        completed = subprocess.run(
            command, cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT, check=False
        )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, text=True, capture_output=True, check=False
    ).stdout.strip()
    measurements = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    passed = (
        completed.returncode == 0
        and measurements.get("successful_requests", 0) > 0
        and measurements.get("error_rate", 1) <= args.max_error_rate
        and measurements.get("successful_rps", 0) >= args.min_success_rps
        and (args.max_p95_ms is None or measurements.get("successful_p95_ms", float("inf")) <= args.max_p95_ms)
    )
    report = {
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "commit": commit or None,
        "working_tree_dirty": bool(dirty),
        "host": args.host,
        "users": args.users,
        "spawn_rate": args.spawn_rate,
        "requested_duration": args.duration,
        "measurement_window": "entire run including ramp-up; response percentiles include successful requests only",
        "client": {"python": platform.python_version(), "platform": platform.platform(), "locust": version("locust")},
        "thresholds": {
            "max_error_rate": args.max_error_rate,
            "min_success_rps": args.min_success_rps,
            "max_successful_p95_ms": args.max_p95_ms,
        },
        "measurements": measurements,
        "passed": passed,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output / "report.json"), "passed": passed, "measurements": measurements}, indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
