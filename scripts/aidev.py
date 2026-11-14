"""Shared constants, loaders and statistics for the AIDev pilot scripts.

Every rule here is the one written down in ANALYSIS_PLAN.md.
"""
import os

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA_DIR = os.path.join(ROOT, "data", "aidev_v3")
RESULTS_DIR = os.path.join(ROOT, "results")
FIGURES_DIR = os.path.join(ROOT, "figures")

SEED = 2026
HORIZON_DAYS = 30        # outcome horizon: merged within 30 days of opening
WINDOW_DAYS = 30         # matched human PR opened within +/- 30 days
CAP_PER_REPO = 3         # at most 3 pairs from any one repository
N_PAIRS = 200
N_BOOT = 10_000

# Human-baseline cleaning rules (ANALYSIS_PLAN.md, "Cleaning the human baseline").
BOT_LOGIN_RE = r"(?i)(?:\[bot\]|bot)$"
AUTOMATION_LOGINS = {"Copilot", "airbyteio"}
AGENT_SIGNATURE_RE = (r"(?i)Generated with \[?Claude Code|Co-Authored-By: Claude|"
                      r"chatgpt\.com/codex|app\.devin\.ai|cursor\.com")

PR_COLS = ["id", "number", "user", "repo_url", "html_url", "created_at", "closed_at",
           "merged_at", "state"]


def path(table, data_dir=DATA_DIR):
    return os.path.join(data_dir, table + ".parquet")


def _with_times(df):
    for c in ("created_at", "closed_at", "merged_at"):
        df[c] = pd.to_datetime(df[c], utc=True)
    return df


def load_agent_prs(data_dir=DATA_DIR):
    df = pd.read_parquet(path("pull_request", data_dir), columns=PR_COLS + ["agent"])
    types = pd.read_parquet(path("pr_task_type", data_dir), columns=["id", "type"])
    return _with_times(df.merge(types, on="id", how="left"))


def load_human_prs(data_dir=DATA_DIR):
    df = pd.read_parquet(path("human_pull_request", data_dir), columns=PR_COLS + ["body"])
    types = pd.read_parquet(path("human_pr_task_type", data_dir), columns=["id", "type"])
    df = _with_times(df.merge(types, on="id", how="left"))
    df["agent"] = "Human"
    return df


def snapshot_lower_bound(df):
    """Latest timestamp of any kind in a PR table: the table was captured no earlier."""
    return max(df[c].max() for c in ("created_at", "closed_at", "merged_at"))


def human_exclusions(human, agent_urls):
    """One boolean column per cleaning rule; a PR is dropped if any is True."""
    flags = pd.DataFrame(index=human.index)
    flags["bot_or_automation_account"] = (
        human["user"].str.contains(BOT_LOGIN_RE, regex=True)
        | human["user"].isin(AUTOMATION_LOGINS))
    flags["agent_signature_in_body"] = human["body"].fillna("").str.contains(
        AGENT_SIGNATURE_RE, regex=True)
    flags["also_in_agent_table"] = human["html_url"].isin(agent_urls)
    return flags


def study_window_end(human):
    """Last creation time that still leaves 30 observed days in the human snapshot."""
    return snapshot_lower_bound(human) - pd.Timedelta(days=HORIZON_DAYS)


def add_outcomes(df):
    """30-day outcomes from PR-level fields only."""
    horizon = df["created_at"] + pd.Timedelta(days=HORIZON_DAYS)
    merged = df["merged_at"].notna() & (df["merged_at"] <= horizon)
    closed = df["merged_at"].isna() & df["closed_at"].notna() & (df["closed_at"] <= horizon)
    out = df.copy()
    out["merged_30d"] = merged
    out["closed_unmerged_30d"] = closed
    out["open_at_30d"] = ~(merged | closed)
    out["hours_to_merge"] = np.where(
        merged, (df["merged_at"] - df["created_at"]).dt.total_seconds() / 3600, np.nan)
    out["merged_at_snapshot"] = df["merged_at"].notna()
    return out


def is_bot(login, user_type=None):
    login = login.fillna("")
    bot = login.str.endswith("[bot]") | (login == "Copilot")
    if user_type is not None:
        bot = bot | (user_type == "Bot")
    return bot


def read_for_prs(table, pr_ids, columns, key="pr_id", data_dir=DATA_DIR):
    """Read only the rows of a sub-resource table that belong to the given PRs."""
    ids = [int(i) for i in pr_ids]
    return pq.read_table(path(table, data_dir), columns=columns,
                         filters=[(key, "in", ids)]).to_pandas()


# ---------------------------------------------------------------- statistics

def wilson(k, n, z=1.959964):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (centre - half, centre + half)


def cohen_h(p1, p2):
    return 2 * np.arcsin(np.sqrt(p1)) - 2 * np.arcsin(np.sqrt(p2))


def cliffs_delta(x, y):
    """P(x > y) - P(x < y) over all cross-group pairs."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) == 0 or len(y) == 0:
        return np.nan
    diff = x[:, None] - y[None, :]
    return (np.sum(diff > 0) - np.sum(diff < 0)) / diff.size


def repo_bootstrap_counts(n_repos, rng, n_boot=N_BOOT, chunk=1000):
    """Yield (chunk x n_repos) matrices: how often each repo is drawn per resample."""
    done = 0
    while done < n_boot:
        size = min(chunk, n_boot - done)
        yield rng.multinomial(n_repos, np.full(n_repos, 1.0 / n_repos), size=size)
        done += size


def proportion_gap(per_repo, rng):
    """Agent-minus-human rate gap with a repo-cluster bootstrap CI.

    per_repo has one row per repository and columns k_agent, n_agent, k_human, n_human.
    """
    k_a, n_a = per_repo["k_agent"].to_numpy(float), per_repo["n_agent"].to_numpy(float)
    k_h, n_h = per_repo["k_human"].to_numpy(float), per_repo["n_human"].to_numpy(float)
    p_a, p_h = k_a.sum() / n_a.sum(), k_h.sum() / n_h.sum()
    gaps, hs = [], []
    for w in repo_bootstrap_counts(len(per_repo), rng):
        with np.errstate(invalid="ignore", divide="ignore"):
            ba = (w @ k_a) / (w @ n_a)
            bh = (w @ k_h) / (w @ n_h)
        gaps.append(ba - bh)
        hs.append(cohen_h(ba, bh))
    gaps, hs = np.concatenate(gaps), np.concatenate(hs)
    ok = ~np.isnan(gaps)
    return {
        "n_agent": int(n_a.sum()), "n_human": int(n_h.sum()),
        "k_agent": int(k_a.sum()), "k_human": int(k_h.sum()),
        "n_repos": int(len(per_repo)),
        "rate_agent": p_a, "rate_human": p_h,
        "wilson_agent": wilson(k_a.sum(), n_a.sum()),
        "wilson_human": wilson(k_h.sum(), n_h.sum()),
        "gap": p_a - p_h,
        "gap_ci": tuple(np.percentile(gaps[ok], [2.5, 97.5])),
        "cohen_h": cohen_h(p_a, p_h),
        "cohen_h_ci": tuple(np.percentile(hs[ok], [2.5, 97.5])),
        "boot_valid": int(ok.sum()),
    }
