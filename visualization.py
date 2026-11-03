"""
@file    visualization.py
@brief   Figures: what the history LOOKS like.
@author  Troy Celdran
@author  JARVIS (Claude Opus 5) — co-author
@date    2026-09-07

@details
Four figures, each answering one question. Like metrics.py these are pure
functions over a history list — no asset, no environment, no controller — so
a figure can be redrawn from an exported CSV with the simulation gone.

    1  Power balance      where the watts came from and went, hour by hour
    2  Reserves           the two-tier storage story, with the night shaded
    3  Shed timeline      which load was disconnected, and for how long
    4  The two signals    energy reserve against power headroom — the figure
                        this project exists to produce

Every figure renders in two themes. `make_all` writes both, and the README
serves them with <picture> + prefers-color-scheme, so a reader on a dark
GitHub never gets a white rectangle burned into the page.

@note DEFECT D-02 — the palette shipped through Step 12 failed the claim its
    own docstring made. It was described as a "validated categorical palette"
    with "adjacent slots guaranteed separable", but nothing measured it. When
    finally measured (2026-09-07, `tests/palette_check.py`):

        amber  #eda100  contrast 2.11:1 against the surface   (floor 3.0)
        green  #1baf7a  contrast 2.74:1                       (floor 3.0)
        orange vs amber  CIEDE2000 9.6 under deuteranopia     (floor 15)
        red    vs orange CIEDE2000 10.6 under tritanopia      (floor 15)

    Two defences in the old docstring did not survive contact with the code.
    "Adjacent slots" was irrelevant: shed_timeline put all four slots on one
    axis and two_signals put the reserved red directly against slot 1. And
    figure_reserves drew the 2.74:1 green as a 2 pt line — a thin graphical
    object, exactly what WCAG 1.4.11 is about.

    The root cause was not tuning but HUE CHOICE. Orange, amber and red are
    three warm hues; deuteranopia collapses them onto one axis, so no amount
    of lightness adjustment separates all three. A palette search over
    in-gamut CIELCh confirmed both that the old set was unfixable in place
    and that passing sets exist.

@note PALETTE. Colours are assigned by fixed slot order and the assignment is
    MEASURED, not asserted — `tests/palette_check.py` is the proof and
    `test_visualization.py` runs it. The floors are WCAG 2.2 SC 1.4.11
    (>= 3.0:1 for a meaningful graphical object) and CIEDE2000 >= 18 between
    every pair that shares an axis, evaluated under normal vision plus
    protanopia, deuteranopia and tritanopia simulated with Machado, Oliveira
    & Fernandes (2009) at severity 1.0.

    THREE categorical slots, not four. No figure ever identifies more than
    three series by colour. The old fourth slot existed only for
    shed_timeline, where the row labels already carry the identity — so
    colour there was redundant encoding that cost a palette constraint and
    bought nothing. Those bars are now one neutral tone.

    Series identity is never carried by colour alone: every figure legends
    and direct-labels its series.

@note ONE AXIS PER FIGURE, always. No figure here plots two different units
    against left and right scales. Where two quantities of different scale
    matter (reserve fraction and headroom watts) they get two stacked panels
    sharing a time axis, which lets them be compared without inviting a false
    reading of where the curves cross.

@note metrics.report() is the table view for these figures — the same numbers
    in text, for anyone who cannot use the colour.

@see metrics.py for the numbers these draw.
@see power_bus.py for the RECORD SCHEMA they read.
@see tests/palette_check.py for the measurement behind every colour here.


================================================================================
API
================================================================================

Theme                                                               [dataclass]
    One coherent set of colour tokens. Two are defined: LIGHT and DARK.

    @param  name       'light' or 'dark'; used in output filenames.
    @param  surface    Figure and axes background.
    @param  ink        Primary text and the demand line.
    @param  ink_soft   Secondary text, tick labels, threshold lines.
    @param  ink_faint  Grid lines and spines.
    @param  night      Lunar-night shading band.
    @param  muted      Large neutral fills (curtailment).
    @param  bar        Shed-timeline bars; one tone, identity is the row label.
    @param  series     Three categorical slots, in assignment order.
    @param  critical   RESERVED status colour. Never used as a series slot.

THEME                                                                [variable]
    The theme in force. Read at call time, so `use_theme` affects any figure
    drawn inside the block. Module-level state is the idiom matplotlib
    already uses; `use_theme` restores on exit, including on exception.

use_theme(theme)                                            [context manager]
    Draw inside this block with `theme` in force.

        with use_theme(DARK):
            figure_reserves(history, "reserves_dark.png")

figure_power_balance(history, path=None) -> Figure
    Stacked supply against demand, with curtailment and shortfall called out.

    @param  history  Per-tick records.
    @param  path     Save here if given; the figure is returned either way.

    @note Supply STACKS because the components sum to something meaningful —
        total power delivered to the bus. Demand is a line over the top, not
        a fourth stack layer: it is the target the stack is trying to reach,
        and drawing it as another band would imply it adds to supply.
    @note Curtailment is drawn BELOW the axis as a negative band. It is
        generated power that was thrown away, so showing it above zero would
        double-count it against the same watts already in the PV band.

figure_reserves(history, path=None) -> Figure
    Aggregate, battery and RFC state of charge, with the night shaded.

    @note The shed and restore thresholds are drawn as reference lines. The
        gap between them IS the hysteresis dead band, and seeing the
        aggregate trace sit inside it without acting is the clearest picture
        of why the band exists.
    @note Night shading comes from is_daylight rather than a computed clock,
        so it stays correct if the synodic period is ever revised.

figure_shed_timeline(history, path=None) -> Figure
    One row per load; a bar wherever that load was disconnected.

    @note Rows are ordered by LoadPriority, so the staircase reads top to
        bottom: the least important load sheds first and restores last. ECLSS
        occupies a row that should never contain a bar — an empty row is the
        result, not a missing series.
    @note ONE colour for every bar. The row label is the identity; colouring
        the bars differently would imply the colour encodes something it does
        not, and it used to cost the palette a fourth constraint for nothing.

figure_two_signals(history, path=None) -> Figure
    Two stacked panels: energy reserve above, power headroom below.

    @note THE figure. The upper panel is the signal a conventional controller
        watches; the lower is the one this project added. Every point where
        the lower panel crosses zero while the upper sits comfortably high is
        an hour a single-signal controller would have slept through.
    @note The lower panel plots headroom and the fleet discharge ceiling
        together because they are both watts on one axis. The ceiling
        collapsing to the RFC's rating while the battery sits at its floor is
        the mechanism behind every power-limited hour.

make_all(history, outdir="data/figures", themes=None) -> list[str]
    Render every figure in every theme and return the paths written.

    @note Dark files are suffixed `_dark`; light files keep the bare name, so
        existing README links and anything pointing at the old filenames
        continue to resolve.
"""

import contextlib
import dataclasses

import matplotlib
matplotlib.use("Agg")                    # no display needed; write files
import matplotlib.pyplot as plt          # noqa: E402

from config import SOC_SHED_THRESHOLD, SOC_RESTORE_THRESHOLD  # noqa: E402
from metrics import series_names, timestep_hours              # noqa: E402


@dataclasses.dataclass(frozen=True)
class Theme:
    """One coherent set of colour tokens; see the API note above."""
    name: str
    surface: str
    ink: str
    ink_soft: str
    ink_faint: str
    night: str
    muted: str
    bar: str
    series: tuple
    critical: str


# Both palettes are the output of a search over in-gamut CIELCh, satisficing
# at the CIEDE2000 floor and then optimising for a conventional appearance —
# which is why they look like an ordinary blue/orange/green/red chart despite
# being chosen by measurement. tests/palette_check.py re-derives the numbers.
LIGHT = Theme(
    name="light",
    surface="#fcfcfb",
    ink="#0b0b0b",
    ink_soft="#52514e",
    ink_faint="#c9c8c2",
    night="#eceae5",
    muted="#c9c8c2",
    bar="#5b6470",
    series=("#1963a4", "#d67510", "#2ba07e"),
    critical="#b13328",
)

DARK = Theme(
    name="dark",
    surface="#14161a",
    ink="#f2f3f5",
    ink_soft="#9aa2ad",
    ink_faint="#333944",
    night="#1c1f26",
    muted="#454c58",
    bar="#8892a0",
    series=("#207db6", "#fea12d", "#3ec69d"),
    critical="#e22e31",
)

THEMES = {"light": LIGHT, "dark": DARK}

THEME = LIGHT


@contextlib.contextmanager
def use_theme(theme):
    """Draw with `theme` in force; restore on exit, including on exception."""
    global THEME
    previous = THEME
    THEME = theme
    try:
        yield theme
    finally:
        THEME = previous


def _legend(ax, ncol):
    """Legend ABOVE the axes, never inside it.

    These are dense 1440-point series that fill their frame, so every in-axes
    position lands on data somewhere in the run — the first draft put one
    across the battery trace and another across the headroom curve. Above the
    frame is the only placement that cannot collide.
    """
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=ncol,
            frameon=False, fontsize=8, labelcolor=THEME.ink_soft,
            handlelength=1.6, columnspacing=1.6, borderaxespad=0.2)


SHORT_NAMES = {"Environmental Control and Life Support System": "ECLSS (life support)"}


def _short(name):
    """Axis-length label for a load; the official names do not fit."""
    return SHORT_NAMES.get(name, name)


def _style(ax, title, ylabel, xlabel="hours since lunar dawn", pad=26):
    """Recessive grid and axes; ink tokens for all text."""
    ax.set_facecolor(THEME.surface)
    ax.set_title(title, color=THEME.ink, fontsize=11, loc="left", pad=pad)
    ax.set_ylabel(ylabel, color=THEME.ink_soft, fontsize=9)
    if xlabel:
        ax.set_xlabel(xlabel, color=THEME.ink_soft, fontsize=9)
    ax.tick_params(colors=THEME.ink_soft, labelsize=8)
    ax.grid(True, color=THEME.ink_faint, linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(THEME.ink_faint)


def _shade_night(ax, history):
    """Shade the lunar night from is_daylight, not from a computed clock."""
    dt = timestep_hours(history)
    start = None
    for record in history:
        if not record["is_daylight"] and start is None:
            start = record["t_hours"]
        elif record["is_daylight"] and start is not None:
            ax.axvspan(start, record["t_hours"], color=THEME.night, zorder=0)
            start = None
    if start is not None:
        ax.axvspan(start, history[-1]["t_hours"] + dt, color=THEME.night, zorder=0)


def _figure(nrows=1, height=4.0):
    """A themed figure with the chart surface applied."""
    fig, axes = plt.subplots(nrows, 1, figsize=(11, height), sharex=(nrows > 1))
    fig.patch.set_facecolor(THEME.surface)
    return fig, axes


def _save(fig, path):
    """Write the figure if a path was given; return it either way."""
    if path:
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=THEME.surface)
    return fig


def figure_power_balance(history, path=None):
    """Stacked supply against demand; curtailment below the axis."""
    t = [r["t_hours"] for r in history]
    sources = series_names(history, "gen:")
    bands = [[r[f"gen:{n}"] / 1000 for r in history] for n in sources]
    bands.append([r["discharged_w"] / 1000 for r in history])
    labels = sources + ["Storage discharge"]

    fig, ax = _figure(height=4.2)
    _shade_night(ax, history)
    ax.stackplot(t, *bands, labels=labels,
                colors=THEME.series[:len(bands)],
                edgecolor=THEME.surface, linewidth=0.3)
    ax.plot(t, [r["demand_w"] / 1000 for r in history],
            color=THEME.ink, linewidth=1.6, label="Demand (after shedding)")
    ax.fill_between(t, 0, [-r["curtailed_w"] / 1000 for r in history],
                    color=THEME.muted, label="Curtailed")
    ax.axhline(0, color=THEME.ink_faint, linewidth=1.0)

    _style(ax, "Power balance — supply stacked against demand", "power  [kW]", pad=30)
    _legend(ax, 5)
    ax.set_xlim(t[0], t[-1])
    return _save(fig, path)


def figure_reserves(history, path=None):
    """Aggregate, battery and RFC state of charge, with the night shaded."""
    t = [r["t_hours"] for r in history]
    traces = [("Fleet aggregate", [r["aggregate_soc"] for r in history])]
    traces += [(n, [r[f"soc:{n}"] for r in history])
            for n in series_names(history, "soc:")]

    fig, ax = _figure(height=4.2)
    _shade_night(ax, history)
    ax.axhspan(SOC_SHED_THRESHOLD, SOC_RESTORE_THRESHOLD,
            color=THEME.ink_faint, alpha=0.45, zorder=1)
    ax.axhline(SOC_SHED_THRESHOLD, color=THEME.ink_soft, linewidth=1.0,
            linestyle=(0, (4, 3)), zorder=2)
    ax.axhline(SOC_RESTORE_THRESHOLD, color=THEME.ink_soft, linewidth=1.0,
            linestyle=(0, (4, 3)), zorder=2)
    ax.text(t[-1], (SOC_SHED_THRESHOLD + SOC_RESTORE_THRESHOLD) / 2,
            "  hysteresis\n  dead band", color=THEME.ink_soft, fontsize=8,
            va="center")

    for i, (label, values) in enumerate(traces):
        ax.plot(t, values, color=THEME.series[i % len(THEME.series)],
                linewidth=2.0, label=label, zorder=3)

    _style(ax, "Storage reserves — the two-tier split", "state of charge  [-]", pad=30)
    _legend(ax, 3)
    ax.set_xlim(t[0], t[-1] * 1.10)
    ax.set_ylim(0, 1.05)
    return _save(fig, path)


def figure_shed_timeline(history, path=None):
    """One row per load; a bar wherever that load was disconnected."""
    dt = timestep_hours(history)
    names = series_names(history, "shed:")
    fig, ax = _figure(height=2.8)
    _shade_night(ax, history)

    for row, name in enumerate(names):
        spans, start = [], None
        for record in history:
            if record[f"shed:{name}"] and start is None:
                start = record["t_hours"]
            elif not record[f"shed:{name}"] and start is not None:
                spans.append((start, record["t_hours"] - start))
                start = None
        if start is not None:
            spans.append((start, history[-1]["t_hours"] + dt - start))
        if spans:
            # One tone for every row: the label is the identity.
            ax.broken_barh(spans, (row - 0.32, 0.64),
                        facecolors=THEME.bar, zorder=3)

    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([_short(n) for n in names], fontsize=8)
    ax.invert_yaxis()
    ax.set_ylim(len(names) - 0.5, -0.5)
    _style(ax, "Load shedding — bars mark hours disconnected", "")
    ax.grid(True, axis="x", color=THEME.ink_faint, linewidth=0.6, alpha=0.6)
    ax.grid(False, axis="y")
    ax.set_xlim(history[0]["t_hours"], history[-1]["t_hours"])
    # No legend: the row labels ARE the identity. A colour key here would say
    # only "shed", which the title already says, while implying the colours
    # encode something they do not.
    return _save(fig, path)


def figure_two_signals(history, path=None):
    """Energy reserve above, power headroom below — two panels, one time axis."""
    t = [r["t_hours"] for r in history]
    fig, (top, bot) = _figure(nrows=2, height=6.0)

    for ax in (top, bot):
        _shade_night(ax, history)

    top.plot(t, [r["aggregate_soc"] for r in history],
            color=THEME.series[0], linewidth=2.0, label="Fleet aggregate SoC")
    top.axhline(SOC_SHED_THRESHOLD, color=THEME.ink_soft, linewidth=1.0,
                linestyle=(0, (4, 3)))
    _style(top, "The energy signal — what a conventional controller watches",
        "state of charge  [-]", xlabel="", pad=30)
    _legend(top, 2)
    top.set_ylim(0, 1.05)

    bot.plot(t, [r["storage_ceiling_w"] / 1000 for r in history],
            color=THEME.series[1], linewidth=2.0, label="Fleet discharge ceiling")
    bot.plot(t, [r["headroom_w"] / 1000 for r in history],
            color=THEME.series[0], linewidth=2.0, label="Power headroom")
    bot.axhline(0, color=THEME.ink, linewidth=1.2)

    brownouts = [r["t_hours"] for r in history if r["shortfall_w"] > 0]
    for i, t_bad in enumerate(brownouts):
        bot.axvline(t_bad, color=THEME.critical, linewidth=1.6, zorder=1,
                    label="Unserved power" if i == 0 else None)

    _style(bot, "The power signal — what this project added", "power  [kW]", pad=30)
    _legend(bot, 3)

    for ax in (top, bot):
        ax.set_xlim(t[0], t[-1])
    fig.tight_layout()
    return _save(fig, path)


def figure_estimator(history, path=None):
    """Truth against the estimate, and the drift the filter is beating.

    Returns None when the run carried no estimator, so make_all can skip it
    rather than draw an empty axis.
    """
    if not history or "est:soc" not in history[0]:
        return None

    t = [r["t_hours"] for r in history]
    truth = [r["est:true_battery_soc"] for r in history]
    est = [r["est:soc"] for r in history]
    counted = [r["est:counted"] for r in history]
    err = [(e - v) * 100.0 for e, v in zip(est, truth)]
    drift = [(c - v) * 100.0 for c, v in zip(counted, truth)]

    fig, (top, bot) = plt.subplots(
        2, 1, figsize=(10, 6.4), sharex=True,
        gridspec_kw={"height_ratios": [1.5, 1.0], "hspace": 0.18})
    fig.patch.set_facecolor(THEME.surface)

    for ax in (top, bot):
        _shade_night(ax, history)

    # Truth goes on TOP, dashed. The estimate tracks it so closely that drawing
    # truth underneath hides it completely — and a reader cannot tell a line
    # that agrees from a line that was never plotted.
    top.plot(t, counted, color=THEME.critical, linewidth=1.6,
             label="coulomb counting alone", zorder=3)
    top.plot(t, est, color=THEME.series[0], linewidth=2.4,
             label="EKF estimate", zorder=4)
    top.plot(t, truth, color=THEME.ink, linewidth=1.4,
             linestyle=(0, (3, 4)), label="truth (no sensor reads this)",
             zorder=5)
    _style(top, "What no instrument can measure",
           "battery state of charge  [-]", xlabel="", pad=30)
    _legend(top, 3)
    top.set_ylim(0, 1.05)

    bot.axhline(0, color=THEME.ink, linewidth=1.0, zorder=2)
    bot.plot(t, drift, color=THEME.critical, linewidth=1.6,
             label="counting error")
    bot.plot(t, err, color=THEME.series[0], linewidth=2.0,
             label="EKF error")
    _style(bot, "", "estimate - truth  [% SoC]", pad=18)
    _legend(bot, 2)
    bot.set_xlim(t[0], t[-1])
    return _save(fig, path)


FIGURES = [
    (figure_power_balance, "power_balance"),
    (figure_reserves, "reserves"),
    (figure_shed_timeline, "shed_timeline"),
    (figure_two_signals, "two_signals"),
    (figure_estimator, "estimator"),
]


def make_all(history, outdir="data/figures", themes=None):
    """Render every figure in every theme into outdir; returns paths written."""
    import os
    os.makedirs(outdir, exist_ok=True)
    themes = themes or (LIGHT, DARK)
    paths = []
    for theme in themes:
        suffix = "" if theme.name == "light" else f"_{theme.name}"
        with use_theme(theme):
            for fn, stem in FIGURES:
                path = os.path.join(outdir, f"{stem}{suffix}.png")
                fig = fn(history, path)
                if fig is None:      # the run carried no estimator
                    continue
                plt.close(fig)
                paths.append(path)
    return paths
