"""
@file    firmware/tools/run_hil.py
@brief   Run the outpost twice — controller in Python, controller on the ESP32.
@author  Troy Celdran
@author  JARVIS (Claude Opus 5) — co-author
@date    2026-09-15

@details
B03's deliverable. The same outpost, the same environment, the same seed; the
only difference is WHERE the decisions are made. If the two runs differ by
anything, the port is wrong or the link is lossy, and either way the number to
report is the divergence.

    .venv/bin/pio run -d firmware --target upload
    .venv/bin/python firmware/tools/run_hil.py

@note The software run goes FIRST and its history is kept. Running hardware
    first and comparing against a remembered summary would hide a divergence
    that cancels out by the end of the month.
@note Every tick is compared, not just the summary. Two runs can reach the
    same unserved total by shedding different loads at different times, and
    that is precisely the failure this is meant to catch.
"""

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from environment import LunarEnvironment          # noqa: E402
from simulation_engine import SimulationEngine    # noqa: E402
import main                                       # noqa: E402
from hil_controller import HardwareController, DEFAULT_PORT  # noqa: E402

COMPARE_FIELDS = ["aggregate_soc", "headroom_w", "served_w", "unserved_w",
                  "demand_w", "generation_w", "charged_w", "discharged_w"]


def run(controller=None):
    """1440 h (60 days). Returns (history, summary, seconds)."""
    bus = main.build_outpost(LunarEnvironment(), topology=True, converters=True)
    if controller is not None:
        bus.controller = controller
    started = time.time()
    engine = SimulationEngine(bus)
    engine.run()
    return engine.history, engine.summary(), time.time() - started


def compare(soft, hard):
    """Every tick, every field. Returns a list of human-readable divergences."""
    out = []
    if len(soft) != len(hard):
        return [f"tick count differs: {len(soft)} vs {len(hard)}"]
    for i, (a, b) in enumerate(zip(soft, hard)):
        for field in COMPARE_FIELDS:
            if field not in a:
                continue
            x, y = a[field], b[field]
            if abs(x - y) > 1e-9 * max(1.0, abs(x)):
                out.append(f"tick {i} {field}: {x!r} vs {y!r}")
        for key in a:
            if key.startswith("shed:") and a[key] != b.get(key):
                out.append(f"tick {i} {key}: {a[key]} vs {b.get(key)}")
        if len(out) > 20:
            out.append("... truncated")
            return out
    return out


def main_():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default=DEFAULT_PORT)
    args = ap.parse_args()

    print("  software controller ...")
    soft_hist, soft_sum, soft_s = run()
    print(f"    {len(soft_hist)} ticks in {soft_s:.2f} s, "
          f"{soft_sum['actions']} actions")

    print(f"  hardware controller on {args.port} ...")
    with HardwareController(args.port) as board:
        print(f"    {board.identify()}")
        board.reset()
        hard_hist, hard_sum, hard_s = run(board)
        print(f"    {len(hard_hist)} ticks in {hard_s:.2f} s, "
              f"{hard_sum['actions']} actions, "
              f"{hard_s / max(len(hard_hist), 1) * 1000:.1f} ms per tick")

    print()
    print(f"  {'':<22}{'software':>14}{'hardware':>14}")
    for key in ("served_kwh", "unserved_kwh", "curtailed_kwh",
                "min_aggregate_soc", "actions"):
        a, b = soft_sum[key], hard_sum[key]
        fmt = "{:>14.4f}" if isinstance(a, float) else "{:>14}"
        print(f"  {key:<22}" + fmt.format(a) + fmt.format(b))

    problems = compare(soft_hist, hard_hist)
    print()
    if not problems:
        print("  HIL CONFORMANCE PASS — the outpost behaved identically with "
              "its controller on hardware.")
        return 0
    print(f"  HIL CONFORMANCE FAIL — {len(problems)} divergences:")
    for line in problems:
        print(f"    {line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_())
