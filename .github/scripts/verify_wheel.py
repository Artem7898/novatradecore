"""Verify that the distribution includes the runnable Django project."""

from pathlib import Path
from zipfile import ZipFile

wheels = list(Path("dist").glob("novatradecore-*.whl"))
if len(wheels) != 1:
    raise SystemExit(f"Expected one wheel, found {len(wheels)}")
with ZipFile(wheels[0]) as wheel:
    files = set(wheel.namelist())
required = {"config/asgi.py", "config/settings/production.py", "trades/models/trade.py"}
missing = required - files
if missing:
    raise SystemExit(f"Wheel is missing application files: {sorted(missing)}")
print("Wheel contains Django settings, ASGI entry point and trade models.")
