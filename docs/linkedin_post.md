# LinkedIn draft

Written 2026-09-15, on completion. Every figure below is checked against the
repository — nothing here is rounded up for effect, which matters more than
usual when the post is partly *about* not rounding things up.

Posting is yours to do. Two variants follow: the long one leads with the
negative result, the short one leads with the hardware.

---

## Variant A — the honest negative result *(recommended)*

> I spent six weeks building a simulation of a lunar outpost's power grid, and
> the most useful thing I got from it was a result I was hoping wouldn't happen.
>
> The setup: an autonomous microgrid — solar, a fission reactor, a battery, a
> regenerative fuel cell — surviving a 354-hour lunar night, hour by hour, with
> a controller deciding what to shed and when.
>
> Partway through I realised the controller was cheating. It read state of
> charge as `stored energy ÷ capacity`. Exact, noiseless, free, every tick.
>
> **No real battery can tell you that.** There is no state-of-charge sensor.
> You measure terminal voltage and current and you *infer* the charge — which is
> exactly why Kalman filters exist in battery management.
>
> So I wrote one. An Extended Kalman Filter in C++, estimating charge from a
> voltage and a current sensor that lies by 2 A. Over one lunar cycle (708.7 h),
> six seeds, matched-model simulation: EKF max error 1.14-1.33 points of SOC;
> the same biased current reading integrated alone is off by 83.0-85.0 points
> (unclamped; a real counter saturates at 0 %). Unbounded drift becomes bounded
> error.
> That's the whole point of the filter.
>
> Then I fed the estimate to the controller instead of the truth, expecting
> reliability to get worse. I could then say by how much.
>
> **It didn't get worse. At all.** Unserved energy, minimum reserve, controller
> actions — identical, at every sensor bias from 2 A to 100 A, even where the
> battery estimate was 60 % wrong.
>
> Six identical rows is also what a broken experiment looks like, so I
> instrumented the controller directly. The estimate was reaching it, up to 5
> percentage points away from the truth. It simply didn't matter:
>
> • the battery holds **7.95 %** of the fleet's stored energy — the fuel cell
> holds the rest, and it isn't estimated
> • the controller's hysteresis band is **15 points** wide
>
> A 60 % battery error became ~4 points of fleet error, inside a 15-point dead
> band. Nothing flipped.
>
> That's not a failed experiment. It's an architectural finding: **reliability
> here is protected by the fuel cell's dominance of stored energy, not by the
> quality of the estimate.** And it's a lower bound, because only the battery is
> estimated — which tells me exactly what the next experiment is.
>
> The controller now also runs on an actual ESP32, with the physics on my laptop
> and the decisions on the board over a serial link. 1440 ticks, every tick
> identical to the software run.
>
> Repo and a live interactive one-line diagram in the comments. Written in
> Python, C++, and JavaScript; the ports are held to each other by golden-file
> conformance tests rather than by hoping.
>
> #PowerSystems #ElectricalEngineering #ControlSystems #EmbeddedSystems #Python

---

## Variant B — shorter, leads with the hardware

> The controller for my lunar microgrid simulation now runs on a real ESP32.
> Physics on the laptop, decisions on the board, serial in between — 1440
> simulated hours, every tick identical to the pure-software run.
>
> What made that possible was a decision made weeks earlier for a different
> reason: I'd written the controller as plain arithmetic with no numpy, because
> I thought it might one day need to run on a microcontroller. It did, and it
> ported without a rewrite.
>
> The project simulates an autonomous outpost surviving a 354-hour lunar night —
> solar, a fission reactor, a battery, a regenerative fuel cell, and a controller
> shedding loads by priority. Along the way it grew an Extended Kalman Filter in
> C++ that infers battery charge from terminal voltage, because no real battery
> has a state-of-charge sensor and the controller had been reading one.
>
> Two findings I didn't expect:
>
> • **A PV array can't trip its own protection.** Short-circuit current is about
> 1.15× rated; the breaker's instantaneous threshold is 10×. It just feeds the
> fault. That's why PV needs a different protection philosophy from a battery.
>
> • **The outpost doesn't care how good the estimator is** — because the battery
> is only 7.95 % of stored energy and the controller's dead band is 15 points
> wide. Reliability is protected by the architecture, not the algorithm.
>
> Repo and a live interactive single-line diagram in the comments.
>
> #PowerSystems #ElectricalEngineering #EmbeddedSystems #ControlSystems

---

## First comment (either variant)

> Repo: https://github.com/troyfrancoceldran-ctrl/Autonomous-lunar-power-grid-simulation
> Live one-line diagram (runs the whole simulation in your browser):
> https://troyfrancoceldran-ctrl.github.io/Autonomous-lunar-power-grid-simulation/web/sld.html
>
> Constants are sourced from NASA and IEEE literature, and the simplifications
> are declared rather than hidden — there's a section in the README for exactly
> that.

---

## What to attach

Post one image. In order of preference:

1. **`docs/figures/estimator_dark.png`** — truth against the estimate, with
   coulomb counting drifting off the bottom. It shows the finding in one glance
   and needs no caption.
2. A screenshot of the live one-line diagram mid-run, with the bus tie animating.
3. **`docs/figures/two_signals.png`** — if you'd rather lead with the microgrid
   than the estimator.

## Notes before posting

- **Variant A is the stronger post.** "I expected X, got not-X, and here's why"
  reads as engineering maturity; a list of features reads as coursework. It is
  also longer than LinkedIn's fold — the first two lines have to earn the click,
  and they do.
- **On disclosure:** the repo's commits carry `Co-Authored-By: Claude Opus 5`,
  so the collaboration is already public. If you want it in the post, one line
  near the end is enough — something like *"Built with Claude as a pair
  programmer; the physics and the filter maths are mine, and the commit history
  shows who wrote what."* Your call entirely; it is accurate either way, and
  the honest framing tends to land well with engineers.
- **Do not claim it is validated against a real outpost.** It isn't, and the
  README says so. The credibility of everything above rests on that being true.
