"""Compute every number reported in README.md, writeup.md and the email draft.

Reads the matched pairs from 03_build_sample.py and the AIDev v3 tables.

Writes:
    results/metrics.json      all numbers, machine-readable
    results/results.md        the same numbers as tables
    results/pair_outcomes.csv per-pair outcomes (used by the figure)

Usage:
    python scripts/04_analyze.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aidev  # noqa: E402


def rng_for(step):
    return np.random.default_rng([aidev.SEED, step])


def per_repo_counts(agent, human, outcome):
    a = agent.groupby("repo_url")[outcome].agg(k_agent="sum", n_agent="size")
    h = human.groupby("repo_url")[outcome].agg(k_human="sum", n_human="size")
    return a.join(h, how="outer").fillna(0)


# ------------------------------------------------------------ comparison steps

def comparison_steps(agent, human, flags, window_end, pairs_out):
    in_window_a = agent[agent["created_at"] <= window_end]
    in_window_h = human[human["created_at"] <= window_end]
    clean_h = in_window_h[~flags.loc[in_window_h.index].any(axis=1)]
    shared = set(in_window_a["repo_url"]) & set(clean_h["repo_url"])
    # Step 1a was added after outcomes were computed (see ANALYSIS_PLAN.md), so seeds
    # are fixed per step rather than by position, leaving the planned steps unchanged.
    steps = [
        ("0", "Raw tables; merged at each table's snapshot",
         per_repo_counts(agent, human, "merged_at_snapshot")),
        ("1a", "Raw tables; merged at each table's snapshot; created by the window end",
         per_repo_counts(in_window_a, in_window_h, "merged_at_snapshot")),
        ("1", "Raw tables; merged within 30 days; created by the window end",
         per_repo_counts(in_window_a, in_window_h, "merged_30d")),
        ("2", "Step 1 with bots, automation and agent PRs removed from the human table",
         per_repo_counts(in_window_a, clean_h, "merged_30d")),
        ("3", "Step 2, only repositories that have both kinds of PR",
         per_repo_counts(in_window_a[in_window_a["repo_url"].isin(shared)],
                         clean_h[clean_h["repo_url"].isin(shared)], "merged_30d")),
        ("4", "Matched pairs: same repo, same task type, opened <=30 days apart",
         pairs_out.groupby("repo_url").agg(
             k_agent=("agent_merged_30d", "sum"), n_agent=("agent_merged_30d", "size"),
             k_human=("human_merged_30d", "sum"), n_human=("human_merged_30d", "size"))),
    ]
    seeds = {"0": 10, "1": 11, "2": 12, "3": 13, "4": 14, "1a": 15}
    results = []
    for key, label, counts in steps:
        r = aidev.proportion_gap(counts, rng_for(seeds[key]))
        r.update(step=key, label=label)
        results.append(r)
    return results


# ------------------------------------------------------------ matched sample

def time_to_merge(pairs_out, rng):
    """Medians and Cliff's delta for hours to merge, with a repo-cluster bootstrap."""
    repos = np.array(sorted(pairs_out["repo_url"].unique()))
    idx = {r: i for i, r in enumerate(repos)}
    a = pairs_out[pairs_out["agent_merged_30d"]][["repo_url", "agent_hours_to_merge"]]
    h = pairs_out[pairs_out["human_merged_30d"]][["repo_url", "human_hours_to_merge"]]
    xa, ra = a["agent_hours_to_merge"].to_numpy(), a["repo_url"].map(idx).to_numpy()
    xh, rh = h["human_hours_to_merge"].to_numpy(), h["repo_url"].map(idx).to_numpy()

    # G[r, s] = #(agent in r slower than human in s) - #(faster).
    sign = np.sign(xa[:, None] - xh[None, :])
    G = np.zeros((len(repos), len(repos)))
    np.add.at(G, (ra[:, None].repeat(len(xh), 1), rh[None, :].repeat(len(xa), 0)), sign)
    na = np.bincount(ra, minlength=len(repos)).astype(float)
    nh = np.bincount(rh, minlength=len(repos)).astype(float)

    def wmedian(values, groups, W):
        order = np.argsort(values)
        v, w = values[order], W[:, groups[order]].astype(float)
        cw = np.cumsum(w, axis=1)
        half = cw[:, -1:] / 2
        pos = (cw >= half).argmax(axis=1)
        out = v[pos]
        out[cw[:, -1] == 0] = np.nan
        return out

    deltas, med_a, med_h = [], [], []
    for W in aidev.repo_bootstrap_counts(len(repos), rng):
        with np.errstate(invalid="ignore", divide="ignore"):
            deltas.append(np.einsum("br,rs,bs->b", W, G, W) / ((W @ na) * (W @ nh)))
        med_a.append(wmedian(xa, ra, W))
        med_h.append(wmedian(xh, rh, W))
    deltas, med_a, med_h = map(np.concatenate, (deltas, med_a, med_h))
    ci = lambda v: tuple(np.nanpercentile(v, [2.5, 97.5]))
    q = lambda v: tuple(np.percentile(v, [25, 50, 75]))
    return {
        "n_agent": int(len(xa)), "n_human": int(len(xh)),
        "agent_quartiles": q(xa), "human_quartiles": q(xh),
        "agent_median_ci": ci(med_a), "human_median_ci": ci(med_h),
        "cliffs_delta": aidev.cliffs_delta(xa, xh), "cliffs_delta_ci": ci(deltas),
    }


def pair_outcomes(pairs, agent, human):
    cols = ["merged_30d", "closed_unmerged_30d", "open_at_30d", "hours_to_merge"]
    a = agent.set_index("id")[cols].add_prefix("agent_")
    h = human.set_index("id")[cols].add_prefix("human_")
    return pairs.join(a, on="agent_pr_id").join(h, on="human_pr_id")


# ------------------------------------------------------------ agent-only review activity

def review_activity(pairs, agent):
    ids = pairs["agent_pr_id"].tolist()
    pr = agent.set_index("id").loc[ids].copy()
    horizon = pr["created_at"] + pd.Timedelta(days=aidev.HORIZON_DAYS)
    pr["window_end"] = (horizon.mask(pr["closed_unmerged_30d"], pr["closed_at"])
                        .mask(pr["merged_30d"], pr["merged_at"]))

    reviews = aidev.read_for_prs("pr_reviews", ids, ["id", "pr_id", "user", "user_type", "state",
                                                     "submitted_at"])
    reviews["at"] = pd.to_datetime(reviews["submitted_at"], utc=True)
    comments = aidev.read_for_prs("pr_comments", ids, ["pr_id", "user", "user_type", "created_at"])
    comments["at"] = pd.to_datetime(comments["created_at"], utc=True)
    # Inline comments carry no pr_id; every one of them joins to a review (see schema.md).
    inline = pd.read_parquet(aidev.path("pr_review_comments_v2"),
                             columns=["pull_request_review_id", "user", "user_type", "created_at"])
    inline = inline.merge(reviews[["id", "pr_id"]], left_on="pull_request_review_id", right_on="id")
    inline["at"] = pd.to_datetime(inline["created_at"], utc=True)

    def human_before_decision(df):
        df = df.join(pr[["user", "window_end"]].rename(columns={"user": "author"}), on="pr_id")
        keep = (~aidev.is_bot(df["user"], df["user_type"]) & (df["user"] != df["author"])
                & (df["at"] <= df["window_end"]))
        return df[keep].groupby("pr_id").size().reindex(pr.index, fill_value=0)

    pr["review_rounds"] = human_before_decision(reviews)
    pr["inline_comments"] = human_before_decision(inline)
    pr["conversation_comments"] = human_before_decision(comments)
    pr["review_comments"] = pr["inline_comments"] + pr["conversation_comments"]
    touched = (pr["review_rounds"] + pr["review_comments"]) > 0
    pr["path"] = np.select(
        [pr["merged_30d"] & ~touched, pr["merged_30d"] & touched, pr["closed_unmerged_30d"]],
        ["merged, no human review", "merged after human review", "closed without merge"],
        default="open at day 30")

    truncated = {
        "pr_reviews_at_30_rows": int((reviews.groupby("pr_id").size() >= 30).sum()),
        "pr_comments_at_30_rows": int((comments.groupby("pr_id").size() >= 30).sum()),
    }
    return pr, truncated


def who_closed(pr):
    """Post-hoc (not in the plan): which account closed the agent PRs closed without merge."""
    closed = pr[pr["closed_unmerged_30d"]]
    tl = aidev.read_for_prs("pr_timeline", closed.index.tolist(),
                            ["pr_id", "event", "actor", "created_at"])
    last = tl[tl["event"] == "closed"].sort_values("created_at").groupby("pr_id")["actor"].last()
    actor = last.reindex(closed.index)
    author = closed["user"]
    who = np.select(
        [actor.isna(), actor == author, aidev.is_bot(actor) & actor.notna()],
        ["no closed event in timeline", "the PR's author account", "a bot"],
        default="another human")
    return pd.crosstab(closed["agent"], pd.Series(who, index=closed.index, name="closed by"))


def describe_counts(s):
    q = s.quantile([0.25, 0.5, 0.75])
    return {"median": float(q[0.5]), "q1": float(q[0.25]), "q3": float(q[0.75]),
            "mean": float(s.mean()), "share_zero": float((s == 0).mean()),
            "share_zero_ci": aidev.wilson(int((s == 0).sum()), len(s))}


# ------------------------------------------------------------ report

def pct(x):
    return "%.1f%%" % (100 * x)


def ci_pct(ci):
    return "%.1f to %.1f" % (100 * ci[0], 100 * ci[1])


def pp(x):
    return "%+.1f pp" % (100 * x)


def ci_pp(ci):
    return "%+.1f to %+.1f pp" % (100 * ci[0], 100 * ci[1])


def main():
    agent = aidev.add_outcomes(aidev.load_agent_prs())
    human = aidev.add_outcomes(aidev.load_human_prs())
    flags = aidev.human_exclusions(human, set(agent["html_url"]))
    window_end = aidev.study_window_end(human)
    pairs = pd.read_csv(os.path.join(aidev.RESULTS_DIR, "matched_pairs.csv"))

    po = pair_outcomes(pairs, agent, human)
    po.to_csv(os.path.join(aidev.RESULTS_DIR, "pair_outcomes.csv"), index=False)

    steps = comparison_steps(agent, human, flags, window_end, po)
    primary = steps[-1]

    # Which agents' PRs each step compares (composition only, no outcomes).
    in_window = agent[agent["created_at"] <= window_end]
    clean_h = human[~flags.any(axis=1) & (human["created_at"] <= window_end)]
    mix = pd.DataFrame({
        "Step 0": agent["agent"].value_counts(),
        "Steps 1a-2": in_window["agent"].value_counts(),
        "Step 3": in_window[in_window["repo_url"].isin(set(clean_h["repo_url"]))]["agent"].value_counts(),
        "Step 4": po["agent"].value_counts(),
    }).fillna(0).astype(int)
    mix = mix.loc[mix["Step 0"].sort_values(ascending=False).index]
    secondary = {}
    for i, name in enumerate(("closed_unmerged_30d", "open_at_30d")):
        counts = po.groupby("repo_url").agg(
            k_agent=("agent_" + name, "sum"), n_agent=("agent_" + name, "size"),
            k_human=("human_" + name, "sum"), n_human=("human_" + name, "size"))
        secondary[name] = aidev.proportion_gap(counts, rng_for(20 + i))
    ttm = time_to_merge(po, rng_for(30))

    by_agent = po.groupby("agent").agg(
        pairs=("pair", "size"), agent_merged_30d=("agent_merged_30d", "sum"),
        human_merged_30d=("human_merged_30d", "sum")).sort_values("pairs", ascending=False)

    pr, truncated = review_activity(pairs, agent)
    paths = pr["path"].value_counts().reindex(
        ["merged, no human review", "merged after human review", "closed without merge",
         "open at day 30"], fill_value=0)
    merged = pr[pr["merged_30d"]]
    merged_no_review = int((merged["path"] == "merged, no human review").sum())
    activity = {
        "review_comments": describe_counts(pr["review_comments"]),
        "review_rounds": describe_counts(pr["review_rounds"]),
        "paths": {k: {"n": int(v), "share": v / len(pr), "ci": aidev.wilson(int(v), len(pr))}
                  for k, v in paths.items()},
        "merged_without_human_review_share_of_merged": {
            "k": merged_no_review, "n": int(len(merged)),
            "share": merged_no_review / len(merged),
            "ci": aidev.wilson(merged_no_review, len(merged))},
        "paths_by_agent": pd.crosstab(pr["agent"], pr["path"]).to_dict(orient="index"),
        "truncation": truncated,
    }
    closers = who_closed(pr)
    activity["closed_by_post_hoc"] = closers.to_dict(orient="index")

    metrics = {
        "window_end": str(window_end),
        "human_snapshot": str(aidev.snapshot_lower_bound(human)),
        "agent_snapshot": str(aidev.snapshot_lower_bound(agent)),
        "comparison_steps": steps,
        "agent_mix_by_step": mix.to_dict(orient="index"),
        "primary_merged_30d": primary,
        "secondary": secondary,
        "time_to_merge_hours": ttm,
        "by_agent": by_agent.to_dict(orient="index"),
        "agent_review_activity": activity,
    }
    with open(os.path.join(aidev.RESULTS_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))

    L = ["# Results", "", "Generated by `scripts/04_analyze.py`. Bootstrap: %s resamples of "
         "repositories, seed %d." % (format(aidev.N_BOOT, ","), aidev.SEED), "",
         "## 1. Agent-minus-human gap in merge rate, as the comparison gets fairer", "",
         "| Step | Comparison | Agent PRs | Human PRs | Repos | Agent merged | Human merged | "
         "Gap (95% CI) | Cohen's h (95% CI) |",
         "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |"]
    for s in steps:
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s (%s) | %.2f (%.2f to %.2f) |" % (
            s["step"], s["label"], format(s["n_agent"], ","), format(s["n_human"], ","),
            format(s["n_repos"], ","), pct(s["rate_agent"]), pct(s["rate_human"]),
            pp(s["gap"]), ci_pp(s["gap_ci"]), s["cohen_h"], *s["cohen_h_ci"]))
    L += ["", "### Agent PRs compared at each step, by agent", "",
          "| Agent | " + " | ".join(mix.columns) + " |", "| --- |" + " ---: |" * len(mix.columns)]
    for name, r in mix.iterrows():
        L.append("| %s | %s |" % (name, " | ".join(
            "%s (%.0f%%)" % (format(v, ","), 100 * v / mix[c].sum()) for c, v in r.items())))
    L += ["", "## 2. Matched sample: %d pairs in %d repositories" % (
        primary["n_agent"], primary["n_repos"]), "",
          "| Outcome (within 30 days of opening) | Agent | Human | Gap (95% CI) | Cohen's h (95% CI) |",
          "| --- | --- | --- | --- | --- |"]
    for name, r in (("Merged (primary)", primary),
                    ("Closed without merge", secondary["closed_unmerged_30d"]),
                    ("Still open at day 30", secondary["open_at_30d"])):
        L.append("| %s | %d/%d = %s (%s) | %d/%d = %s (%s) | %s (%s) | %.2f (%.2f to %.2f) |" % (
            name, r["k_agent"], r["n_agent"], pct(r["rate_agent"]), ci_pct(r["wilson_agent"]),
            r["k_human"], r["n_human"], pct(r["rate_human"]), ci_pct(r["wilson_human"]),
            pp(r["gap"]), ci_pp(r["gap_ci"]), r["cohen_h"], *r["cohen_h_ci"]))
    L += ["", "Group CIs are Wilson intervals; gap and h CIs are repo-cluster bootstrap.", "",
          "### Hours from open to merge (PRs merged within 30 days)", "",
          "| | Merged PRs | Median (95% CI) | IQR |", "| --- | ---: | --- | --- |",
          "| Agent | %d | %.1f (%.1f to %.1f) | %.1f to %.1f |" % (
              ttm["n_agent"], ttm["agent_quartiles"][1], *ttm["agent_median_ci"],
              ttm["agent_quartiles"][0], ttm["agent_quartiles"][2]),
          "| Human | %d | %.1f (%.1f to %.1f) | %.1f to %.1f |" % (
              ttm["n_human"], ttm["human_quartiles"][1], *ttm["human_median_ci"],
              ttm["human_quartiles"][0], ttm["human_quartiles"][2]),
          "", "Cliff's delta (agent vs. human; negative = agent PRs merge faster): "
          "%.2f (95%% CI %.2f to %.2f)." % (ttm["cliffs_delta"], *ttm["cliffs_delta_ci"]), "",
          "### By agent (counts only; too few for inference)", "",
          "| Agent | Pairs | Agent PRs merged within 30 days | Matched human PRs merged within 30 days |",
          "| --- | ---: | ---: | ---: |"]
    for name, r in by_agent.iterrows():
        L.append("| %s | %d | %d | %d |" % (name, r["pairs"], r["agent_merged_30d"], r["human_merged_30d"]))
    rc, rr = activity["review_comments"], activity["review_rounds"]
    L += ["", "## 3. Review activity on the %d sampled agent PRs (no human comparator in the data)" % len(pr),
          "", "Counts only humans other than the PR author, before the merge or close "
          "(or day 30 if still open).", "",
          "| Measure | Median | IQR | Mean | PRs with none (95% CI) |", "| --- | ---: | --- | ---: | --- |",
          "| Review comments (inline + conversation) | %.0f | %.0f to %.0f | %.2f | %s (%s) |" % (
              rc["median"], rc["q1"], rc["q3"], rc["mean"], pct(rc["share_zero"]), ci_pct(rc["share_zero_ci"])),
          "| Review rounds (submitted reviews) | %.0f | %.0f to %.0f | %.2f | %s (%s) |" % (
              rr["median"], rr["q1"], rr["q3"], rr["mean"], pct(rr["share_zero"]), ci_pct(rr["share_zero_ci"])),
          "", "### Decision path within 30 days", "",
          "| Path | PRs | Share (95% CI) |", "| --- | ---: | --- |"]
    for k, v in activity["paths"].items():
        L.append("| %s | %d | %s (%s) |" % (k, v["n"], pct(v["share"]), ci_pct(v["ci"])))
    m = activity["merged_without_human_review_share_of_merged"]
    L += ["", "Of the %d agent PRs merged within 30 days, %d (%s, 95%% CI %s) had no review or "
          "comment from a human other than the author before merge." % (
              m["n"], m["k"], pct(m["share"]), ci_pct(m["ci"])), "",
          "### Decision path by agent (counts)", ""]
    ct = pd.crosstab(pr["agent"], pr["path"])
    L.append("| Agent | " + " | ".join(ct.columns) + " |")
    L.append("| --- |" + " ---: |" * len(ct.columns))
    for name, r in ct.iterrows():
        L.append("| %s | %s |" % (name, " | ".join(str(int(v)) for v in r)))
    L += ["", "### Post-hoc check (not in the plan): who closed the agent PRs closed without merge",
          "", "From the last `closed` event in `pr_timeline`. For Devin and Copilot the PR's "
          "author account is the agent; for Codex, Claude Code and Cursor it is the person who "
          "ran the agent. Human PRs have no timeline, so this can't be compared.", "",
          "| Agent | " + " | ".join(closers.columns) + " | Total |",
          "| --- |" + " ---: |" * (len(closers.columns) + 1)]
    for name, r in closers.iterrows():
        L.append("| %s | %s | %d |" % (name, " | ".join(str(int(v)) for v in r), r.sum()))
    L.append("| **All** | %s | **%d** |" % (
        " | ".join("**%d**" % v for v in closers.sum()), closers.values.sum()))
    L += ["", "Sampled agent PRs whose `pr_reviews` rows hit the 30-row cap: %d; "
          "`pr_comments` rows at the cap: %d." % (
              truncated["pr_reviews_at_30_rows"], truncated["pr_comments_at_30_rows"]), "",
          "## 4. Not computable from the dataset", "",
          "- CI / check results: no table or timeline event carries them, and the GitHub "
          "API was not used.",
          "- Follow-up fix or revert commits within 30 days of merge: human PRs have no "
          "timeline, and agent timelines have no cross-references and no message on "
          "`referenced` events.", ""]
    with open(os.path.join(aidev.RESULTS_DIR, "results.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
