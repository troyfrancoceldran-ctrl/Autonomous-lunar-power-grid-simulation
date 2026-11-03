# Build Progress

> **COMPLETE — 2026-09-15.** Every step ticked: Steps 0-12, the electrical
> topology T01-T05, and Project B end to end (B00-B04.5). The two projects are
> merged and the question they were built to ask has an answer.
>
> | suite | result |
> |---|---|
> | Python | 312 passed |
> | C++ estimator | 14 passed, 0 skipped |
> | C++ controller vs Python | 1440/1440 ticks identical |
> | Browser vs Python | 198,720 comparisons + 1992 EKF checks, PASS |
> | Hardware in the loop | 1440/1440 ticks identical on an ESP32 |
>
> Further work is recorded as **recommendations** in `README.md`, not as
> unfinished tasks: an estimator for the fuel cell, the filter on the ESP32
> with the `float`-versus-`double` question measured, and thermal coupling.


Working agreement: hybrid pace. Boilerplate/plumbing steps are written by
Claude; physics- and algorithm-heavy steps (environment model, generation,
storage/SoC math, RFC mass balance, the controller) are written by the user
with Claude giving the spec/pseudocode first and reviewing the result after.

Documentation convention (applied on completion of every step, from Step 5 on):
each module carries a Doxygen-style header — `@file` / `@brief` / `@author` /
`@date` / `@details` — followed by an `API` section holding the full
`@param` / `@return` / `@note` detail for every class and method. The code
below carries only a single-phrase docstring per definition, so the
implementation stays readable without scrolling past its own documentation.
Authors are Troy Celdran with JARVIS (Claude Opus 5) as co-author.

- [x] Step 0 — Repo scaffold, config constants, `.gitignore`, `requirements.txt` (Claude)
- [x] Step 1 — `assets/base_asset.py` abstract interfaces (Claude)
- [x] Step 2 — `environment.py`: LunarEnvironment day/night + solar flux model (user)
- [x] Step 3 — `assets/generation.py`: PVArray, FissionSurfacePower (user)
- [x] Step 4 — `assets/storage.py`: BatteryBank SoC model (user, with Claude debugging)
- [x] Step 5 — `assets/storage.py`: RegenerativeFuelCell H2/O2 mass model (user)
- [x] Step 6 — `assets/loads.py`: ECLSS, ThermalControl, CommsArray, SciencePayload (user)
- [x] Step 7 — `controller.py`: AutonomousController (priority shed/restore + hysteresis) (user, ControlStrategy interface by Claude)
- [x] Compliance inspection of Steps 0–7 against NASA FSP / NASA Glenn RFC / IEEE 2030.7. Six findings; audit record in `docs/compliance_inspection.html`.
- [x] W01–W04 remediation — all six findings closed:
      - F-01/F-05/F-06 fixed in the inspection itself (708.7 h synodic period, 60-day run, declared simplifications)
      - F-02 `solar_elevation_fraction()` — fixed arrays follow the sine of solar elevation
      - F-04 PV dust derate and an explicit tracking flag
      - F-03 scripted reactor outage window
      - the two-signal control contract: capacity-weighted `aggregate_soc` + `shortfall_w`
- [x] Step 8 — `power_bus.py`: per-tick measure/decide/dispatch/record (Claude). Exposed defect D-01 in the W04 control contract — the shortfall signal was stale by construction; replaced with a signed `headroom_w` measured at the start of each tick. `MIN_ACTION_DWELL_HOURS` 1.0 -> 3.0, which had been a no-op since Step 7.
- [x] Step 9 — `simulation_engine.py`: fixed-timestep loop + CSV/JSON history export; `main.py` now runnable (Claude)
- [x] Step 10 — `metrics.py` + `visualization.py`: KPIs and plots (Claude). Headline result: on the t=500 h outage, **100 % of shortfall hours were power-limited at aggregate_soc 0.6159** — the two-signal design measured rather than asserted. Also: 27.3 % of generation curtailed, battery at its floor for 554 of 708 night hours.
- [x] Step 11 — `tests/`: 188 tests in 0.4 s, organised by failure mode rather than by module (Claude — reassigned mid-session at the user's request). Plus `tests/mutation_check.py`, which reintroduces nine shipped bugs and confirms 8 are caught; the 9th is a verified equivalent mutant. Seven measurement errors were made writing it, against zero code defects found.
- [x] Step 12 (part 1) — README rewritten around the result, `--report`/`--figures` flags wired into `main.py`, MIT LICENSE, figures committed to `docs/figures/`, pre-publication audit run (Claude)
- [x] Step 12 (part 2) — published. Public repo `Autonomous-lunar-power-grid-simulation`
      at github.com/troyfrancoceldran-ctrl, 40 commits, MIT. All commits
      rewritten to a GitHub noreply author before the first push, so the
      university address never left the machine. Roadmap added in `1c82dbf`.

- [x] Dual-theme figures + defect D-02 (Claude, 2026-09-07). The palette that
      shipped through Step 12 called itself "validated" and was not: amber at
      2.11:1 and green at 2.74:1 against the surface (floor 3.0), orange vs
      amber ΔE 9.6 under deuteranopia and red vs orange ΔE 10.6 under
      tritanopia (floor 18). Root cause was HUE CHOICE — three warm hues
      collapse onto one axis under deuteranopia, so no tuning fixes it.
      `tests/palette_check.py` now measures both themes; it is itself verified
      against the CIEDE2000 standard's published test data. The palette needs
      only THREE slots: no figure identified more than three series by colour.
      218 tests.

## Week of 2026-09-08 — DONE
All four topology work orders, the client-side model and the operable SLD.
The repo is also a live website now: GitHub Pages serves the landing page, the
diagram and the conformance check at
https://troyfrancoceldran-ctrl.github.io/Autonomous-lunar-power-grid-simulation/
The conformance page only became runnable once it was served over HTTPS —
file:// blocks the fetch it needs — so "run it yourself" is now literal.

## Next cycle — PROJECT B, and the merge into this one
From the user's career roadmap: **Project B — Real-Time HIL Battery Management
State Estimator**, an Extended Kalman Filter written from scratch in Modern
C++, flashed onto an ESP32, tracking Li-ion state of charge under noisy
high-stress current profiles. The user intends to merge it into this project
(Project A) rather than keep them separate.

WHY IT IS NOT A BOLT-ON. `BatteryBank.state_of_charge` is `energy_wh /
capacity_wh` — exact, noiseless, known instantly. No real system can measure
SoC at all; that is precisely why an EKF exists. So the controller currently
acts on ground truth it could never have. Swapping that input for an ESTIMATE
turns the merge into a measurable question:

    How much does outpost reliability degrade when the controller acts on an
    estimate rather than on truth?

The project already measures unserved kWh, LOLP and failure mode, so the answer
is a table. It attacks the headline finding directly: if the estimator lags
during a fast discharge, the power-limited hours should get WORSE, and by a
number we can state.

- [x] **B00** `estimator/` scaffolded 2026-09-14 (Claude). Native CMake build,
      a dependency-free test harness that reports SKIP for unwritten methods
      exactly as the Python suite does, and a placeholder interface. 5 passed,
      1 skipped, exit 0.
      TOOLCHAIN, MEASURED: clang 21 / g++ / cmake / make all present; NO
      PlatformIO, ESP-IDF or arduino-cli; no board attached; no pyserial. So
      the filter is written and proven NATIVELY first and the board comes
      later — which is the right order anyway, and forces the filter to be
      portable C++ with no framework dependencies.
- [x] **B01** `assets/storage.py` — DONE 2026-09-14. Physics by the user:
      a degree-7 NMC OCV fit (monotonic, min step +4288 uV), terminal voltage
      with a 5.96 V droop at the 417 A rating, and an instrument model whose
      BIAS is fixed and deliberate rather than drawn. Internal resistance is
      DERIVED from BATTERY_DISCHARGE_EFFICIENCY (14.3 mohm; I^2R = 2487 W
      against the 2500 W that 5 % of 50 kW implies), not chosen, so the same
      loss is not counted twice. Two review defects: efficiency used where
      resistance belonged (-392 V under load), and cell volts where pack volts
      were promised. 300 tests still pass — nothing here touches the energy
      books.
- [x] **B00.5** Environment: the venv was inside iCloud Drive with 8120 of its
      8167 files evicted to the cloud. `import matplotlib` cost 229.9 s cold
      against 0.22 s warm. Rebuilt at ~/.venvs/lunar with .venv as a symlink;
      the full suite went from 704.96 s to 2.47 s.
- [x] **B01 (superseded line — see the entry above for the result)** A battery
      terminal model the EKF can observe: OCV curve plus internal resistance,
      so there is a voltage to measure rather than a state to read.
      (USER — physics)
- [x] **B02** `estimator/src/ekf.cpp` — DONE 2026-09-15. Algorithm by the
      user; spec, generated params, plumbing and 14 tests by Claude.
      **14 passed, 0 failed, 0 skipped.** Two functions:
      `docv_dsoc` (the measurement Jacobian) and `Ekf::update` (the six
      scalar lines). ONE STATE, so no matrices and no loops in the filter.
      `docv_dsoc` verified against a central finite difference at five points
      across the usable range, agreeing to every digit checked — the chain
      rule's factor of 2, the pack scale and the index weighting all correct
      at once. `battery_params.hpp` is generated from config.py so the filter
      and the simulation cannot disagree about the battery; its derivative is
      deliberately NOT generated.
      The predicted result held: the bias is not in the state vector, so the
      filter cannot remove it, and the error settles at a bounded offset
      instead of growing. Closed form checked against simulation —
      +0.127 % predicted, +0.129 % observed, against -42 % and still falling
      for coulomb counting alone. Converting UNBOUNDED drift into BOUNDED
      error IS the finding.
      Written in C++ as a first encounter with the language: the mathematics
      was right on the first attempt at each function, and every correction
      after that was syntax. `estimator/CPP_NOTES.md` records the subset and
      the traps.
- [x] **B03** The HIL bridge — DONE 2026-09-15. Controller on an ESP32,
      physics on the host, serial between them. **HIL CONFORMANCE PASS**:
      1440 ticks, every field of every tick identical to the software run,
      repeated three times. 12.8 ms per tick.
      The controller was written numpy-free at Step 7 precisely so it could
      port to an MCU; this is that decision being cashed in.
      `firmware/src/controller.cpp` includes no Arduino.h and no vendor SDK,
      so it also builds natively and is held to a 1440-tick golden trace of
      the PYTHON controller's decisions — captured by wrapping
      `controller.update` inside the running simulation, not by reconstructing
      its inputs, which would be a second implementation of the thing under
      test. All 1440 match, including the 1429 where the answer was "do
      nothing".
      Board: ESP32-D0WD-V3 rev 3.1, 22.6 kB RAM (6.9 %), 275 kB flash (21 %).
      Three defects found and fixed on the way, all environmental rather than
      logical: the ESP32 Arduino core compiles as gnu++11 where a struct with
      default member initialisers is not an aggregate (forced to C++17 so the
      firmware and the native test share one standard); opening the port
      toggles DTR/RTS, which on a CP2102 resets the board into its ROM
      bootloader at 74880 baud and produces endless plausible garbage; and a
      strict request/response protocol must drain stale input BEFORE sending,
      or every exchange lags by one and the symptom is a perfectly valid
      answer to the previous question.
- [x] **B04** Truth vs estimate — MEASURED 2026-09-15, and the answer is not
      the one that was predicted. (together)
      The controller's only view of stored energy is one float at
      `power_bus.py:427`. B04 swaps it for an EKF inference and reports the
      cost. `soc_estimator.py` calls the REAL C++ filter through ctypes —
      stdlib only, no port to drift — and `estimated=` defaults to False, so
      all 300 pre-B04 tests still pass and the comparison changes one
      variable rather than the model.
      **The outpost does not notice.** Unserved kWh, min aggregate SoC and
      controller actions are identical to truth at every sensor bias from
      2 A to 100 A, even where the battery estimate is 60.7 % wrong. That is
      not broken wiring: instrumenting `controller.update` directly confirms
      it receives a fleet figure up to 5.08 points from truth.
      WHY, in two numbers. The battery is 7.95 % of the fleet reserve, so
      even a 60 % battery error becomes ~4.4 points of fleet error; and the
      controller's hysteresis is 15 points wide, so nothing flips. The
      reliability is protected by the RFC's dominance of stored energy, not
      by the quality of the estimate.
      estimator/README.md predicted the power-limited hours would get WORSE
      by a statable amount. The amount is zero, and the reason is
      architectural. This is a LOWER BOUND: only the battery is estimated,
      because the RFC has no OCV curve or terminals in this model. Giving the
      RFC an estimator, or measuring a battery-dominant outpost, is the next
      experiment rather than a correction to this one.
- [x] **B04.5** The estimator, visible. 2026-09-15.
      `web/src/ekf.js` ports the filter to the browser so the page shows it
      WORKING tick by tick rather than replaying a chart computed elsewhere.
      Held to a golden trace generated from the compiled C++ through ctypes:
      1992 checks over the OCV curve, its derivative and 600 filter ticks,
      agreeing to 3.87e-15 relative. A port nobody checks is a second source
      of truth.
      Adds a live signal tile, a truth-vs-estimate chart and a Kalman-gain
      chart to the page, plus `visualization.figure_estimator` in both
      themes. In the browser run the EKF stays within 1.29 % while pure
      coulomb counting reaches 62.45 % — a 48x difference, which is the
      finding stated as a picture.
      2026-11-03: the 1.29 % / 62.45 % / 48x figures above came from a browser run and did not reproduce; see results/measure_ekf_vs_counting.py for the six-seed measurement.
      (B03 was numbered before B04 but sequenced after it, because it needed
      hardware that was not attached and produced no finding of its own. The
      board arrived 2026-09-15 and B03 is recorded above, complete.)

NOTE ON THE "HARDWARE RENDER". It was a placeholder and the user was never
sure of it either (said so 2026-09-08). Hardware-in-the-loop supersedes it: a
render produces a picture, HIL produces a measurement, and this project has
consistently preferred measurements.

## Agreed sequence from here (2026-09-04)
1. **User** writes Step 11 against `tests/INVARIANTS.md`.
2. **Together** — full test run and review before anything is published.
3. **Claude** does Step 12: README with the figures and the headline result,
   docstring consistency sweep, LICENSE, `.gitignore` check for anything that
   should not be public.
4. **Push to a NEW public GitHub repo.** Outward-facing, so it needs explicit
   go-ahead at the time, not this note. Two things to settle first: the repo
   name, and the git author identity (see tasks.md — currently the repo-local
   "TroyJan_ EE").
5. **LinkedIn post** — DRAFTED 2026-09-15 at `docs/linkedin_post.md`. Two
   variants, a first comment with the links, and what to attach. Posting is
   the user's to do. Every figure in it was checked against the repository
   before it was written down.

Each step should be its own git commit, so the repo history itself tells
the build story — useful when this becomes a portfolio piece.
- [x] **T05** What actually limits a fault — DONE 2026-09-15 (Claude, at the
      user's request; the spec was written for the user but handed back).
      `prospective_fault_current_a` treated the source as ideal, I = V/R_cable,
      and its own @note already called that an upper bound. The bound was
      loose: on the battery feeder it overstates by nearly 5x.
      Three limits replace it, and only ONE is an impedance —
      battery `OCV(soc)/(R_internal + R_cable)`, PV `Isc` which a cell cannot
      exceed, converter `limit x rated`. The battery's 14.3 mohm is 0.7x the
      cable's own so impedance is a real correction, but CONTROL is the larger
      one: adding impedance to converter-fed sources while ignoring their
      current limits would be more detail and less truth.
      **The finding: a PV array cannot trip its own protection.** Isc is 1.15x
      rated against a 10x instantaneous threshold, so it simply feeds the
      fault indefinitely. That is a real property of PV systems and the reason
      they need a different protection philosophy from a battery.
      Fault-to-rating ratios fall across the board — the battery feeder from
      88x ideal to 21.5x with every source summed. Busbar impedance is
      declared rather than modelled: under 1 % of the answer for a whole model
      layer. 12 new tests, 312 passing.
