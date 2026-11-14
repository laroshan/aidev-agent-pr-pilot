"""Draw figures/figure1.png from results/metrics.json.

Panel A: what happened to the matched agent and human PRs within 30 days.
Panel B: the agent-minus-human gap in merge rate at each comparison step.

Usage:
    python scripts/05_make_figure.py
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aidev  # noqa: E402

# Reference palette (dataviz skill): light surface, ink and the first three
# categorical slots, which pass the colour-blindness checks for all pairs.
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]

STEP_LABELS = {
    "0": "Raw tables, merged by each snapshot",
    "1a": "+ only PRs opened by 29 May 2025",
    "1": "+ merged within 30 days (equal follow-up)",
    "2": "+ bots and agents removed from human PRs",
    "3": "+ only repos with both kinds of PR",
    "4": "Matched pairs: repo, task type, ±30 days",
}
STEP_ORDER = ["0", "1a", "1", "2", "3", "4"]


def minus(text):
    return text.replace("-", "−")


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelcolor=INK2, length=0)


def outcomes_panel(ax, m):
    p, s = m["primary_merged_30d"], m["secondary"]
    rows = [
        ("Agent PRs", [p["rate_agent"], s["closed_unmerged_30d"]["rate_agent"],
                       s["open_at_30d"]["rate_agent"]]),
        ("Matched human PRs", [p["rate_human"], s["closed_unmerged_30d"]["rate_human"],
                               s["open_at_30d"]["rate_human"]]),
    ]
    names = ["Merged", "Closed without merge", "Still open"]
    for y, (label, shares) in zip((1, 0), rows):
        left = 0.0
        for share, colour in zip(shares, SERIES):
            ax.barh(y, 100 * share, left=left, height=0.5, color=colour,
                    edgecolor=SURFACE, linewidth=2)
            if share >= 0.07:
                ax.text(left + 50 * share, y, "%.1f%%" % (100 * share), ha="center",
                        va="center", color="white", fontsize=9.5, fontweight="semibold")
            left += 100 * share
    ax.set_yticks([1, 0])
    ax.set_yticklabels(["%s (n=%d)" % (r[0], p["n_agent"]) for r in rows], color=INK, fontsize=10)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, 1.6)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    style(ax)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in SERIES]
    ax.legend(handles, names, ncol=3, frameon=False, loc="lower left",
              bbox_to_anchor=(0, 1.0), fontsize=9.5, labelcolor=INK2, handlelength=1.0,
              borderaxespad=0.2)
    ax.set_title("A. What happened within 30 days of opening (%d matched pairs, %d repos)" % (
        p["n_agent"], p["n_repos"]), loc="left", color=INK, fontsize=11.5,
        fontweight="semibold", pad=26)


def ladder_panel(ax, m):
    steps = {s["step"]: s for s in m["comparison_steps"]}
    ys = list(range(len(STEP_ORDER)))[::-1]
    for y, key in zip(ys, STEP_ORDER):
        s = steps[key]
        lo, hi = (100 * v for v in s["gap_ci"])
        ax.plot([lo, hi], [y, y], color=SERIES[0], linewidth=2, solid_capstyle="round")
        ax.plot(100 * s["gap"], y, "o", markersize=8, color=SERIES[0],
                markeredgecolor=SURFACE, markeredgewidth=2)
        ax.text(1.02, y, minus("%+.1f  (%+.1f to %+.1f)" % (100 * s["gap"], lo, hi)),
                transform=ax.get_yaxis_transform(), va="center", ha="left",
                color=INK2 if key != "4" else INK, fontsize=9.5,
                fontweight="semibold" if key == "4" else "normal")
    ax.axvline(0, color=AXIS, linewidth=1)
    ax.set_yticks(ys)
    labels = ["%s  %s" % (k, STEP_LABELS[k]) for k in STEP_ORDER]
    ax.set_yticklabels(labels, fontsize=9.5, color=INK)
    ax.get_yticklabels()[-1].set_fontweight("semibold")
    ax.set_xlim(-45, 5)
    ax.set_ylim(-0.6, len(STEP_ORDER) - 0.4)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: minus("%+d" % v)
                                                                 if v else "0"))
    ax.set_xlabel("Agent minus human merge rate, percentage points "
                  "(95% CI, bootstrap over repositories)", color=INK2, fontsize=9.5)
    style(ax)
    ax.set_title("B. The gap widens once PRs come from the same months and repos",
                 loc="left", color=INK, fontsize=11.5, fontweight="semibold", pad=10)


def main():
    with open(os.path.join(aidev.RESULTS_DIR, "metrics.json"), encoding="utf-8") as f:
        m = json.load(f)
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    fig, (a, b) = plt.subplots(2, 1, figsize=(10, 6.6), dpi=200,
                               gridspec_kw={"height_ratios": [1, 1.9], "hspace": 0.55})
    fig.patch.set_facecolor(SURFACE)
    outcomes_panel(a, m)
    ladder_panel(b, m)
    fig.text(0.01, 0.005, "Data: AIDev v3 (MSR 2026 Mining Challenge release). "
             "Steps 0 and 1a count merges by each table's snapshot; steps 1 to 4 count "
             "merges within 30 days of opening.", color=MUTED, fontsize=8)
    os.makedirs(aidev.FIGURES_DIR, exist_ok=True)
    out = os.path.join(aidev.FIGURES_DIR, "figure1.png")
    fig.savefig(out, bbox_inches="tight", facecolor=SURFACE, pad_inches=0.25)
    print("wrote", out)


if __name__ == "__main__":
    main()
