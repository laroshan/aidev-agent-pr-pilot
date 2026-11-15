"""Draw the teaching figures used in STATISTICS.md, from the pilot's own data.

Writes figures/concepts/*.png and results/concepts.md (every number shown).

Usage:
    python scripts/06_concept_figures.py
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aidev  # noqa: E402

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
OUT = os.path.join(aidev.FIGURES_DIR, "concepts")
N_SIM = 5000


def style(ax, title):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelcolor=INK2, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", color=INK, fontsize=11.5, fontweight="semibold", pad=10)


def save(fig, name):
    fig.patch.set_facecolor(SURFACE)
    fig.savefig(os.path.join(OUT, name), dpi=170, bbox_inches="tight", facecolor=SURFACE,
                pad_inches=0.2)
    plt.close(fig)


def step3_data():
    agent = aidev.add_outcomes(aidev.load_agent_prs())
    human = aidev.add_outcomes(aidev.load_human_prs())
    flags = aidev.human_exclusions(human, set(agent["html_url"]))
    end = aidev.study_window_end(human)
    h = human[~flags.any(axis=1) & (human["created_at"] <= end)]
    a = agent[agent["created_at"] <= end]
    shared = set(a["repo_url"]) & set(h["repo_url"])
    return a[a["repo_url"].isin(shared)], h[h["repo_url"].isin(shared)]


def fig_naive_vs_cluster(a, h, rng, notes):
    """Same data, two ways to resample: single PRs vs whole repositories."""
    xa, xh = a["merged_30d"].to_numpy(float), a.shape[0]
    ya, yh = h["merged_30d"].to_numpy(float), h.shape[0]
    naive = np.empty(N_SIM)
    for i in range(N_SIM):
        naive[i] = (xa[rng.integers(0, xh, xh)].mean() - ya[rng.integers(0, yh, yh)].mean())
    counts = pd.DataFrame({
        "ka": a.groupby("repo_url")["merged_30d"].sum(), "na": a.groupby("repo_url").size(),
        "kh": h.groupby("repo_url")["merged_30d"].sum(), "nh": h.groupby("repo_url").size(),
    }).fillna(0)
    ka, na, kh, nh = (counts[c].to_numpy(float) for c in ("ka", "na", "kh", "nh"))
    cluster = np.concatenate([(w @ ka) / (w @ na) - (w @ kh) / (w @ nh)
                              for w in aidev.repo_bootstrap_counts(len(counts), rng, N_SIM)])
    gap = xa.mean() - ya.mean()
    n_ci, c_ci = np.percentile(naive, [2.5, 97.5]), np.percentile(cluster, [2.5, 97.5])

    fig, ax = plt.subplots(figsize=(9, 3.8))
    bins = np.linspace(-0.45, -0.15, 70)
    ax.hist(100 * cluster, bins=100 * bins, color=BLUE, alpha=0.55, label="Resample whole repositories (cluster)")
    ax.hist(100 * naive, bins=100 * bins, color=ORANGE, alpha=0.75, label="Resample single PRs (naive)")
    for ci, colour, y in ((n_ci, ORANGE, 0.93), (c_ci, BLUE, 0.83)):
        ax.annotate("", xy=(100 * ci[1], y), xytext=(100 * ci[0], y), xycoords=("data", "axes fraction"),
                    arrowprops=dict(arrowstyle="<->", color=colour, lw=2))
    ax.axvline(100 * gap, color=INK2, lw=1)
    ax.set_xlabel("Agent minus human merge rate, points (step 3: %s agent and %s human PRs in %d repos)" % (
        format(len(a), ","), format(len(h), ","), len(counts)), color=INK2, fontsize=9)
    ax.set_yticks([])
    ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc="upper left")
    style(ax, "Naive vs cluster bootstrap: same data, very different certainty")
    save(fig, "naive_vs_cluster.png")
    notes += [
        "## Naive vs cluster bootstrap (step 3 data, %d resamples, seed %d)" % (N_SIM, aidev.SEED), "",
        "| Method | 95% interval (points) | Width |", "| --- | --- | ---: |",
        "| Naive: resample single PRs | %.1f to %.1f | %.1f |" % (100 * n_ci[0], 100 * n_ci[1], 100 * (n_ci[1] - n_ci[0])),
        "| Cluster: resample repositories | %.1f to %.1f | %.1f |" % (100 * c_ci[0], 100 * c_ci[1], 100 * (c_ci[1] - c_ci[0])),
        "", "Observed gap: %.1f points." % (100 * gap), ""]


def fig_confounding(a, notes):
    """Merge rate of agent PRs depends heavily on the repository they land in."""
    rates = a.groupby("repo_url")["merged_30d"].agg(["mean", "size"])
    rates = rates[rates["size"] >= 10].sort_values("mean")
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.bar(range(len(rates)), 100 * rates["mean"], color=BLUE, width=0.8)
    ax.set_xticks([])
    ax.set_ylabel("% merged within 30 days", color=INK2, fontsize=9)
    ax.set_xlabel("Each bar is one repository with at least 10 agent PRs (step 3), sorted", color=INK2, fontsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    style(ax, "Why the repository matters: agent PR merge rates by repository")
    save(fig, "confounding_by_repo.png")
    notes += ["## Agent merge rate by repository (step 3, repos with >= 10 agent PRs)", "",
              "Repositories: %d. Merge rate ranges from %.0f%% to %.0f%%; median %.0f%%." % (
                  len(rates), 100 * rates["mean"].min(), 100 * rates["mean"].max(), 100 * rates["mean"].median()), ""]


def fig_intervals(po, notes):
    """Rates with Wilson intervals, and the gap with its bootstrap interval."""
    fig, ax = plt.subplots(figsize=(9, 2.6))
    for y, k, label, colour in ((1, int(po["agent_merged_30d"].sum()), "Agent PRs", BLUE),
                                (0, int(po["human_merged_30d"].sum()), "Human PRs", ORANGE)):
        lo, hi = aidev.wilson(k, len(po))
        ax.plot([100 * lo, 100 * hi], [y, y], color=colour, lw=6, solid_capstyle="round", alpha=0.35)
        ax.plot(100 * k / len(po), y, "o", color=colour, ms=9, mec=SURFACE, mew=2)
        ax.text(100 * hi + 1.5, y, "%d/%d = %.1f%%  (95%% CI %.1f to %.1f)" % (
            k, len(po), 100 * k / len(po), 100 * lo, 100 * hi), va="center", color=INK2, fontsize=9)
        notes.append("- %s: %d/%d, Wilson 95%% CI %.1f to %.1f" % (label, k, len(po), 100 * lo, 100 * hi))
    ax.set_yticks([1, 0])
    ax.set_yticklabels(["Agent PRs", "Human PRs"], color=INK, fontsize=10)
    ax.set_xlim(30, 110)
    ax.set_ylim(-0.6, 1.6)
    ax.set_xlabel("% merged within 30 days (matched sample)", color=INK2, fontsize=9)
    style(ax, "A confidence interval: the range of plausible true values")
    save(fig, "confidence_intervals.png")
    notes.append("")


def fig_cliffs(po, notes):
    """Hours to merge for merged PRs: the two groups overlap almost completely."""
    xa = po.loc[po["agent_merged_30d"], "agent_hours_to_merge"].to_numpy()
    xh = po.loc[po["human_merged_30d"], "human_hours_to_merge"].to_numpy()
    rng = np.random.default_rng(aidev.SEED)
    fig, ax = plt.subplots(figsize=(9, 2.8))
    for y, x, colour in ((1, xa, BLUE), (0, xh, ORANGE)):
        ax.scatter(np.maximum(x, 0.01), y + rng.uniform(-0.18, 0.18, len(x)), s=14, color=colour, alpha=0.6, lw=0)
        ax.plot([np.median(x)] * 2, [y - 0.3, y + 0.3], color=INK, lw=2)
    ax.set_xscale("log")
    ax.set_yticks([1, 0])
    ax.set_yticklabels(["Agent (n=%d)" % len(xa), "Human (n=%d)" % len(xh)], color=INK, fontsize=10)
    ax.set_xlabel("Hours from open to merge (log scale); black line = median", color=INK2, fontsize=9)
    style(ax, "Cliff's delta = %.2f: neither group is reliably faster" % aidev.cliffs_delta(xa, xh))
    save(fig, "cliffs_delta.png")
    notes += ["## Hours to merge", "",
              "Agent median %.1f h (n=%d); human median %.1f h (n=%d); Cliff's delta %.2f." % (
                  np.median(xa), len(xa), np.median(xh), len(xh), aidev.cliffs_delta(xa, xh)), ""]


def worked_examples(po, notes):
    """Step-by-step numbers for the hand calculations in STATISTICS.md."""
    z = 1.959964
    k, n = int(po["agent_merged_30d"].sum()), len(po)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    wald = z * np.sqrt(p * (1 - p) / n)
    notes += ["## Worked: Wilson interval for %d/%d" % (k, n), "",
              "p = %.3f; centre = %.4f; half-width = %.4f; interval %.3f to %.3f." % (
                  p, centre, half, centre - half, centre + half),
              "Wald on the same data: %.3f +/- %.4f = %.3f to %.3f." % (p, wald, p - wald, p + wald), ""]
    lo, hi = aidev.wilson(2, 20)
    w2 = z * np.sqrt(0.1 * 0.9 / 20)
    notes += ["## Worked: small sample, 2/20", "",
              "Wald: %.3f to %.3f. Wilson: %.3f to %.3f." % (0.1 - w2, 0.1 + w2, lo, hi), ""]

    pa, ph = po["agent_merged_30d"].mean(), po["human_merged_30d"].mean()
    aa, ah = 2 * np.arcsin(np.sqrt(pa)), 2 * np.arcsin(np.sqrt(ph))
    notes += ["## Worked: gap and Cohen's h", "",
              "Gap = %.3f - %.3f = %.3f (%.1f points)." % (pa, ph, pa - ph, 100 * (pa - ph)),
              "2*asin(sqrt(%.3f)) = %.4f; 2*asin(sqrt(%.3f)) = %.4f; h = %.4f." % (pa, aa, ph, ah, aa - ah), ""]

    xa = po.loc[po["agent_merged_30d"], "agent_hours_to_merge"].to_numpy()
    xh = po.loc[po["human_merged_30d"], "human_hours_to_merge"].to_numpy()
    diff = xa[:, None] - xh[None, :]
    slower, faster, ties = int((diff > 0).sum()), int((diff < 0).sum()), int((diff == 0).sum())
    notes += ["## Worked: median vs mean, and Cliff's delta", "",
              "Agent hours: median %.1f, mean %.1f, max %.1f. Human hours: median %.1f, mean %.1f, max %.1f." % (
                  np.median(xa), xa.mean(), xa.max(), np.median(xh), xh.mean(), xh.max()),
              "Comparisons: %d x %d = %d. Agent slower in %d, faster in %d, ties %d." % (
                  len(xa), len(xh), diff.size, slower, faster, ties),
              "Cliff's delta = (%d - %d) / %d = %.3f." % (slower, faster, diff.size, (slower - faster) / diff.size), ""]


def main():
    os.makedirs(OUT, exist_ok=True)
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    notes = ["# Numbers behind the teaching figures", "",
             "Generated by `scripts/06_concept_figures.py`. Used by STATISTICS.md.", ""]
    po = pd.read_csv(os.path.join(aidev.RESULTS_DIR, "pair_outcomes.csv"))
    notes += ["## Confidence intervals (matched sample)", ""]
    fig_intervals(po, notes)
    fig_cliffs(po, notes)
    worked_examples(po, notes)
    a, h = step3_data()
    fig_naive_vs_cluster(a, h, np.random.default_rng([aidev.SEED, 60]), notes)
    fig_confounding(a, notes)
    with open(os.path.join(aidev.RESULTS_DIR, "concepts.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(notes))
    print("\n".join(notes))


if __name__ == "__main__":
    main()
