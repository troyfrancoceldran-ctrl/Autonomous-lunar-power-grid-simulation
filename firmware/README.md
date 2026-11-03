# B03 — the controller, on hardware

The physics stays on the host. The **decisions** move to an ESP32.

```
  Python                          serial, 115200                  ESP32
  ──────                          ─────────────                   ─────
  environment, assets,     T <t> <soc> <headroom> <loads…>   ►    policy:
  topology, converters,                                           thresholds,
  dispatch, metrics        ◄   A <index> <shed>                   priority order,
                                                                  dwell timers
```

That split is the whole point. The controller was written **numpy-free at
Step 7** specifically so it could port to a microcontroller; this is that
decision being cashed in.

---

## Why the controller compiles on a laptop

`src/controller.cpp` includes **no** `Arduino.h`, no vendor SDK, no dynamic
allocation and no `<string>`. `src/main.cpp` — the only file that knows it is
on an ESP32 — owns the serial link and calls into it.

Keeping that boundary is not tidiness. It is what allows the port to be held to
the Python original's decisions **on the host, before anything is flashed**:

```bash
.venv/bin/python firmware/tools/export_controller_golden.py
cmake -S firmware -B firmware/build && cmake --build firmware/build
./firmware/build/test_controller
```

The golden records what the real `AutonomousController` was **shown** and what
it **did** at all 1440 ticks of 1440 h (60 days), captured by wrapping
`controller.update` inside the running simulation — not by reconstructing its
inputs afterwards, which would be a second implementation of the thing under
test and would agree with the port for the same wrong reasons.

All 1440 must match, including the 1429 where the answer was *do nothing*. A
port that acts when the original stayed idle is just as wrong as one that
misses an action, and far easier to overlook.

---

## The protocol

Line-based ASCII, host-initiated, one exchange per tick. Text rather than
packed binary on purpose: it can be read in a serial monitor with no tooling,
which is worth more than the bandwidth over a 1440-tick run.

| direction | line |
|---|---|
| host → board | `I` |
| board → host | `LUNAR B03 <proto> <max_loads>` |
| host → board | `R` — reset the dwell timers |
| board → host | `OK` |
| host → board | `T <t_h> <soc> <headroom_w> <n> <p s d> <p s d> …` |
| board → host | `A <index> <shed>` — index `-1` means no action |

Every reply is exactly one line, so the host reads to a newline and never has
to guess how much is coming.

**Loads are positional.** The board has no heap and no strings, so a load is
its index in the list the bus passed. A reply naming an out-of-range index
raises rather than being clamped — a clamped index would shed a load nobody
chose.

---

## What is, and is not, on the board

| on it | not on it |
|---|---|
| the thresholds | the physics |
| the priority ordering | the assets and topology |
| the dwell timers, held in RAM between ticks | dispatch and metrics |

The dwell state living in the ESP32's RAM is what makes this a **controller**
rather than a lookup table with extra steps.

---

## Running it

```bash
.venv/bin/pio run -d firmware --target upload
.venv/bin/python firmware/tools/run_hil.py
```

`run_hil.py` runs the month **twice** — once in Python, once with the board —
and compares **every tick**, not just the summary. Two runs can reach the same
unserved total by shedding different loads at different times, and that is
exactly the failure this is meant to catch.

---

## The board

Identified with `esptool` on 2026-09-15:

| | |
|---|---|
| chip | ESP32-D0WD-V3 rev 3.1, dual-core LX6 @ 240 MHz |
| flash | 4 MB |
| bridge | CP2102, `/dev/cu.usbserial-0001` |
| PlatformIO board ID | `esp32dev` — exact match on MCU, clock, flash, RAM |

**The LX6 has a single-precision FPU.** `double` is emulated in software. The
controller uses `double` throughout and is comfortable at ~1440 ticks, but the
estimator is a different matter — see `estimator/CPP_NOTES.md`.

---

## What this deliberately is not

- **Not the estimator on hardware.** B02's EKF stays on the host for now. The
  controller was the numpy-free one; porting the filter is a separate question
  with a real answer needed about `float` and the variance `P`.
- **Not real-time.** The host drives the clock. The board answers as fast as it
  is asked, which is not the same as meeting a deadline.
- **Not fault-tolerant.** A dropped line raises. A flight controller would
  retry, checksum and fail safe; this is a bench bridge and says so.
