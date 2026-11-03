# The estimator

Project B, merged into Project A rather than kept beside it: an Extended Kalman
Filter in C++ that estimates battery state of charge from terminal measurements,
eventually running on an ESP32 with the physics on the host.

---

## Why this is not a bolt-on

`BatteryBank.state_of_charge` is `energy_wh / capacity_wh`. Exact. Noiseless.
Known instantly, every tick, for free.

**No real battery can tell you that.** There is no state-of-charge sensor. You
can measure terminal voltage and current, and from those you must *infer* the
charge — which is precisely why Kalman filters exist in battery management.

So the controller in this simulation has been acting on ground truth it could
never have had. That is a cheat, and it is the interesting kind: it does not
make the model wrong so much as make it *optimistic in a way nobody measured*.

Replacing truth with an estimate turns the merge into a question:

> **How much does outpost reliability degrade when the controller acts on an
> estimate rather than on truth?**

The project already reports unserved kWh, LOLP and failure mode, so the answer
is a table rather than an opinion. And it aims straight at the headline finding:
if the estimator lags during a fast discharge, the power-limited hours should get
**worse**, by an amount we can state.

---

## Toolchain, re-measured 2026-09-15 — **B03 is unblocked**

| | |
|---|---|
| `clang++` | ✅ Apple clang 21.0.0 |
| `g++`, `make`, `cmake` | ✅ present |
| PlatformIO | ✅ 6.2.0, in the project venv (`.venv/bin/pio`) |
| ESP32 board | ✅ **ESP32-D0WD-V3 rev 3.1**, 4 MB flash |
| serial bridge | ✅ CP2102, `/dev/cu.usbserial-0001` |
| `pyserial` | ✅ 3.5 |
| `esptool` | ✅ in the venv |

Board ID for `platformio.ini` is **`esp32dev`** — it matches the attached part
exactly on MCU, clock, flash and RAM. PlatformIO is installed into the venv
rather than system-wide, for the same reason the venv itself lives outside
iCloud Drive: this project has already lost eleven minutes a test run to an
environment nobody was watching.

The Xtensa compiler itself is not downloaded until the first build, so the
install above is small; expect the first `pio run` to fetch a few hundred MB
into `~/.platformio`.

**One measured fact that reaches back into the code.** The LX6 core has a
SINGLE-precision FPU. `double` is emulated in software and markedly slower,
which is exactly what CPP_NOTES.md warned about from general knowledge and is
now confirmed against this silicon. The filter is `double` throughout, so B03
must either accept the cost or measure what single precision does to the
variance `P` — which moves across orders of magnitude and has roughly seven
decimal digits to spend in `float`.

**This sets the order of work, and the order is the right one anyway.**

The EKF gets written and proven **natively**, on the host, where a test can run
in milliseconds and a failure points at a line. Only then does it go near a
board. An estimator that is wrong on a laptop is wrong on an ESP32, and far
harder to see there.

That constraint also improves the code: the filter must be **portable C++ with
no framework dependencies** — no `Arduino.h`, no ESP-IDF headers, no dynamic
allocation. Which is what you want in an estimator regardless, and what makes it
flashable later without a rewrite.

---

## The sequence

### B01 — a battery the EKF can observe  ·  *user, physics*  ·  **blocks everything**

The filter needs something to measure. Today `BatteryBank` exposes state and no
terminals, so there is nothing to observe.

This adds an **open-circuit-voltage curve** and an **internal resistance**, so
the pack has a terminal voltage that depends on charge and on the current being
drawn:

```
V_terminal = OCV(soc) − I · R_internal
```

That single equation is what makes estimation possible *and* difficult: the
`I·R` term means a heavy discharge looks like a low state of charge, and
untangling the two is the filter's whole job.

Lives in the main simulation (`assets/storage.py`), not here — it is battery
physics, not estimator code.

### B02 — the EKF  ·  *user, algorithm*  ·  **DONE 2026-09-15**

**14 passed, 0 failed, 0 skipped.** `include/ekf.hpp` carries the interface,
the six equations and four traps; `src/ekf.cpp` is the filter. Two functions:

  * `docv_dsoc(soc)` — the measurement Jacobian, the analytic derivative of
    `params::ocv_v`. The trap is the **chain rule**: the polynomial is in
    `x = 2*soc - 1`, so differentiating the coefficients gives `dOCV/dx` and
    you still owe a factor of 2. Forget it and every gain is half what it
    should be — the filter still runs, still converges, just slower, which is
    exactly the kind of wrong that survives a demo.
  * `Ekf::update(...)` — the six lines.

`include/battery_params.hpp` is **generated** from `config.py` by
`tools/export_params.py`, so the filter and the simulation cannot disagree
about the battery. `ocv_v` is generated too — a direct port of
`BatteryBank.open_circuit_voltage_v` — but its derivative deliberately is not,
because that is the heart of the filter.

**What a Kalman filter is**, if it is new: a weighted average between something
you predicted and something you measured, weighted by how much you trust each.
You are walking a corridor with your eyes shut, counting paces — smooth, but
your error grows without bound. Occasionally you glimpse a doorway through fog
— blurry, but it does not drift. Coulomb counting is the paces; terminal
voltage is the doorway.

With one state there are **no matrices**. All six equations are scalar:

```
predict:   z <- z - eta*I*dt/(3600*Q)
           P <- P + Q_proc

correct:   H <- dOCV/dz                  at the PREDICTED state
           K <- P*H / (H*H*P + R_meas)
           z <- z + K*(V_meas - V_pred)
           P <- (1 - K*H)*P
```

`K` is the only interesting quantity: near 0 means ignore the voltmeter, near 1
means trust it completely. And note where `H` sits — a flat OCV curve drives
`H` to zero, which drives `K` to zero, and the filter stops listening however
good the voltmeter is. That is why LFP estimators diverge, and it is chemistry
rather than tuning.

**Expect a residual offset.** The bias is not in the state vector, so this
filter cannot estimate it and will not remove it. It should settle where the
voltage correction balances the coulomb drift. That is the result, not a bug:
the filter converts UNBOUNDED drift into BOUNDED error. Pure coulomb counting
runs to 42 % across one lunar night and keeps going.

The maths in full: `docs/estimator_formulas.pdf` for the plant,
`docs/ekf_formulas.pdf` for the filter.

**If C++ is the unfamiliar part rather than the filter**, read
`CPP_NOTES.md` first. It is not a tutorial — it is the specific subset these
two functions need, built around a line-for-line translation of the B01
`open_circuit_voltage_v` you already wrote, plus the five things that will
actually bite (`params::` prefixes, integer division, `-Werror`, missing
headers, and how to read a C++ error message).

### B03 — the HIL bridge  ·  *Claude, plumbing*

Controller on the ESP32, physics on the host, serial between them. The
controller was written numpy-free at Step 7 precisely so it could port to an
MCU; this is that decision being cashed in.

Needs hardware and a toolchain, so it comes last.

### B04 — the measurement  ·  *together*  ·  **DONE 2026-09-15**

Truth versus estimate across the scenarios. The deliverable was a table, and
the table says the outpost does not care.

| bias [A] | battery error | unserved kWh | min agg SoC | actions |
|---|---|---|---|---|
| truth | — | 0.00 | 0.2955 | 9 |
| 2 | 1.33 % | 0.00 | 0.2955 | 9 |
| 10 | 5.96 % | 0.00 | 0.2955 | 9 |
| 25 | 14.60 % | 0.00 | 0.2955 | 9 |
| 50 | 30.05 % | 0.00 | 0.2955 | 9 |
| 100 | 60.73 % | 0.00 | 0.2955 | 9 |

Six identical rows is what a broken experiment looks like, so the wiring was
checked directly rather than assumed: instrumenting `controller.update` shows
it genuinely receives a fleet figure up to **5.08 points** from truth at a
100 A bias. The estimate reaches the controller. The controller does not care.

**Why, in two numbers.** The battery holds **7.95 %** of the fleet reserve, so
a 60 % battery error becomes ~4.4 points of fleet error. The controller's
hysteresis is **15 points** wide (shed 0.30, restore 0.45), and the worst
perturbation near the threshold was 4.375 points. Nothing flips.

This section predicted the opposite — that the power-limited hours would get
worse by an amount we could state. The amount is zero, and the reason is
architectural rather than numerical: **reliability here is protected by the
RFC's dominance of stored energy, not by the quality of the estimate.**

It is a LOWER BOUND, and deliberately reported as one. Only the battery is
estimated; the RFC has no OCV curve and no terminals in this model, so its
share stays ground truth. Giving the RFC an estimator, or measuring a
battery-dominant outpost, is the next experiment.

### B04.5 — the estimator, visible

`web/src/ekf.js` puts the filter in the browser so the page shows it working
tick by tick. It is held to a golden trace from the compiled C++ — 1992 checks
across the OCV curve, its derivative and 600 ticks, agreeing to **3.87e-15**
relative — because a port nobody checks is a second source of truth that
drifts silently.

On the page: a live estimator tile, a truth-versus-estimate chart and a
Kalman-gain chart. Over one lunar cycle (708.7 h), six seeds,
matched-model simulation: EKF max error 1.14-1.33 points of SOC; the same
biased current reading integrated alone is off by 83.0-85.0 points
(unclamped; a real counter saturates at 0 %).

---

## Layout

```
estimator/
  include/ekf.hpp        the interface and the spec
  src/ekf.cpp            the filter                      [B02, user]
  test/
    harness.hpp          a tiny PASS/FAIL/SKIP reporter, no dependencies
    test_ekf.cpp         tests written FROM the spec
  tools/
    export_profile.py    dump (t, current, voltage, true SoC) from the sim
  data/                  exported profiles the tests read
  CMakeLists.txt         native build; no board required
```

## Building and testing

```bash
cmake -S estimator -B estimator/build
cmake --build estimator/build
./estimator/build/test_ekf
```

Tests whose method is not written yet report **SKIP** rather than fail, exactly
as the Python suite does — so the build stays green while the filter is being
written, and the skip list doubles as the to-do list.

---

## What this deliberately is not

- **Not a cell model.** One equivalent-circuit pack, not 100 series cells with
  individual balancing. The question is what the *controller* sees, not what a
  BMS engineer would need.
- **Not thermally coupled.** Real internal resistance is strongly temperature
  dependent, and the lunar swing is severe. Declared, not modelled — yet.
- **Not an ageing model.** Capacity fade and resistance growth are the other
  half of a real BMS and are out of scope here.
