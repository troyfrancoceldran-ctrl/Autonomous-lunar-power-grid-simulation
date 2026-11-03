"""
Measure EKF vs coulomb counting on the existing Python + C++ (ctypes) path.

Measurement only. Calls the existing API and modifies nothing:
    main.build_outpost(environment, estimated=True)
    soc_estimator.FleetEstimator(battery, seed=s)     -- replaces the default
    simulation_engine.SimulationEngine(bus).run()

Scenario: nominal (no outage, no topology, no converters) -- the CLI default.
Tuning: FleetEstimator defaults, untouched (q_proc 1e-9, initial_var 1e-6,
r_meas = volt_sensor_noise**2, initial_soc = true start).

Error = (estimate - truth) * 100, percentage points of SOC, per tick, where
truth = record["est:true_battery_soc"]. Every metric is over the ticks in the
window:
    max_abs  max |error|
    final    error at the last tick in the window (signed)
    rmse     sqrt(mean(error^2))

Windows, by END-of-tick time (t_hours + dt_hours, the instant the record
describes, since the estimator observes after dispatch):
    708.7    ticks with t_hours + dt_hours <= 708.7
    1440     every tick

Counter, clamped:   the repo's own figure, record["est:counted"].
Counter, unclamped: the same update, counted -= reported_a*dt/capacity_ah,
                    rebuilt from FleetEstimator.history without the clamp.
                    The clamped series is rebuilt the same way and checked
                    against record["est:counted"] to prove the reconstruction.

    .venv/bin/python results/measure_ekf_vs_counting.py
"""

import csv
import hashlib
import math
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
os.chdir(REPO)

from environment import LunarEnvironment          # noqa: E402
from main import build_outpost                    # noqa: E402
from simulation_engine import SimulationEngine    # noqa: E402
import soc_estimator                              # noqa: E402
from soc_estimator import FleetEstimator          # noqa: E402

SEEDS = (12345, 1, 2, 3, 4, 5)
WINDOWS = (708.7, 1440.0)


def counters(est, start, dt_hours):
    """Rebuild the counter from the reported currents, clamped and not.

    `start` is est.counted read before the run: the filter's prior, which
    defaults to the battery's true charge before tick 0.
    """
    clamped, unclamped = [], []
    c = u = start
    for row in est.history:
        reported_a = row[1]
        c = min(max(c - reported_a * dt_hours / est.capacity_ah, 0.0), 1.0)
        u = u - reported_a * dt_hours / est.capacity_ah
        clamped.append(c)
        unclamped.append(u)
    return clamped, unclamped


def metrics(errors):
    if not errors:
        return (float("nan"),) * 3
    return (max(abs(e) for e in errors), errors[-1],
            math.sqrt(sum(e * e for e in errors) / len(errors)))


def main():
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lib = soc_estimator.build_library()
    with open(lib, "rb") as handle:
        lib_sha = hashlib.sha256(handle.read()).hexdigest()
    lines = []
    out = lines.append
    out(f"utc: {ts}")
    out(f"python: {sys.version.split()[0]}")
    out(f"library: {os.path.relpath(lib, REPO)}  sha256 {lib_sha}  "
        f"mtime {datetime.fromtimestamp(os.path.getmtime(lib)).isoformat()}")
    out("scenario: nominal; FleetEstimator defaults except seed")
    out("error unit: percentage points of SOC, (estimate - truth) * 100")
    out("")

    header = (f"{'seed':>6} {'window_h':>8} {'ticks':>5} {'series':<18}"
              f" {'max_abs':>10} {'final':>10} {'rmse':>10}")
    table = [header, "-" * len(header)]
    first_zero = {}
    checks = []
    csv_rows = []

    for seed in SEEDS:
        # The prior must be read before the run moves the battery.
        bus = build_outpost(LunarEnvironment(), estimated=True)
        bus.estimator = FleetEstimator(bus.storage[0], seed=seed)
        est = bus.estimator
        start = est.counted
        engine = SimulationEngine(bus)
        history = engine.run()
        dt = engine.dt_hours

        if len(est.history) != len(history):
            raise SystemExit(f"seed {seed}: {len(est.history)} observations "
                             f"for {len(history)} ticks; cannot align")

        clamped, unclamped = counters(est, start, dt)
        recon = max(abs(a - r["est:counted"])
                    for a, r in zip(clamped, history))
        checks.append((seed, recon))

        truth = [r["est:true_battery_soc"] for r in history]
        series = {
            "ekf": [(r["est:soc"] - v) * 100.0 for r, v in zip(history, truth)],
            "count_clamped": [(r["est:counted"] - v) * 100.0
                              for r, v in zip(history, truth)],
            "count_unclamped": [(u - v) * 100.0
                                for u, v in zip(unclamped, truth)],
        }

        hit = next((r["t_hours"] + dt for r in history
                    if r["est:counted"] == 0.0), None)
        first_zero[seed] = hit

        for window in WINDOWS:
            n = sum(1 for r in history if r["t_hours"] + dt <= window + 1e-9)
            for name, errs in series.items():
                mx, fin, rm = metrics(errs[:n])
                table.append(f"{seed:>6} {window:>8.1f} {n:>5} {name:<18}"
                             f" {mx:>10.4f} {fin:>10.4f} {rm:>10.4f}")
        table.append("")

        for i, r in enumerate(history):
            row = est.history[i]
            csv_rows.append({
                "seed": seed, "t_hours": r["t_hours"],
                "t_end_hours": r["t_hours"] + dt,
                "true_current_a": row[0], "reported_current_a": row[1],
                "reported_voltage_v": row[2],
                "truth_soc": truth[i], "ekf_soc": r["est:soc"],
                "counted_clamped": r["est:counted"],
                "counted_unclamped": unclamped[i],
                "ekf_err_pp": series["ekf"][i],
                "count_clamped_err_pp": series["count_clamped"][i],
                "count_unclamped_err_pp": series["count_unclamped"][i],
                "gain": r["est:gain"], "variance": r["est:variance"],
            })

    lines.extend(table)
    out("first hour the CLAMPED counter reads 0 (end-of-tick time):")
    for seed in SEEDS:
        hit = first_zero[seed]
        out(f"  seed {seed:>5}: " + ("never" if hit is None else f"{hit:.4f} h"))
    out("")
    out("reconstruction check, max |rebuilt clamped - est:counted|:")
    for seed, diff in checks:
        out(f"  seed {seed:>5}: {diff:.3e}")

    raw = os.path.join(HERE, f"raw_measure_ekf_vs_counting_{ts}.txt")
    per_tick = os.path.join(HERE, f"per_tick_ekf_vs_counting_{ts}.csv")
    with open(per_tick, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)
    out("")
    out(f"raw:      {os.path.relpath(raw, REPO)}")
    out(f"per-tick: {os.path.relpath(per_tick, REPO)}")
    text = "\n".join(lines)
    with open(raw, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
