"""Run one paper-trading collection cycle without placing real bets."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(script):
    result = subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    # First refresh the public fixture snapshot.  The auditor then receives
    # today's actual page data instead of yesterday's stale snapshot.
    history = run("export_fixture_snapshot.py")
    # A network outage must not turn a healthy public dashboard into an empty
    # "no matches" screen.  The fixture exporter keeps the last good snapshot
    # and reports failure; leave the last full system status in place until a
    # source can provide a real schedule again.
    if history != 0:
        print("Системный статус не обновлён: сохранён последний полный отчёт до восстановления источника.")
        raise SystemExit(history)
    # The status exporter records forecasts before the next matches finish.
    status = run("export_system_status.py")
    raise SystemExit(0 if status == 0 and history == 0 else 1)
