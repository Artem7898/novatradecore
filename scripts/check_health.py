"""Probe loopback using a configured allowed Host header."""

import os
import re
from urllib.request import Request, urlopen


def healthcheck_host(raw_allowed_hosts: str) -> str:
    for value in raw_allowed_hosts.split(","):
        host = value.strip().lstrip(".")
        if re.fullmatch(r"[A-Za-z0-9.-]+|\[[0-9A-Fa-f:]+\]", host):
            return host
    return "localhost"


def main() -> None:
    request = Request(
        "http://127.0.0.1:8000/health/live/",
        headers={"Host": healthcheck_host(os.getenv("ALLOWED_HOSTS", "localhost"))},
    )
    with urlopen(request, timeout=3) as response:
        if response.status != 200:
            raise SystemExit("Liveness probe did not return HTTP 200.")


if __name__ == "__main__":
    main()
