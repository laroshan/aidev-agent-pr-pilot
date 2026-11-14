# Analysis plan (fixed before computing outcomes)

Written 2026-11-02. By then I had inspected the schema, the PR-to-table coverage, creation dates, task types and author logins. I had **not** computed any outcome (merge, close, time to merge, reviews) for the sample or for the comparison steps below. The only outcome figures I had seen were the dataset-wide merged counts printed by the schema check (24,014 of 33,596 agent PRs, 5,081 of 6,618 human PRs). Any change to this plan after outcomes were computed is listed at the end with its reason.

## Data

AIDev v3, the MSR 2026 Mining Challenge release, pinned to Hugging Face commit `3ca0045773097b138b064550dfd6e72229f40bee`.

- **Agent PRs:** `pull_request`, the AIDev-pop subset of repos with more than 100 stars.
- **Human PRs:** `human_pull_request`, which the dataset card says was sampled from the same repos but only those with more than 500 stars.

### What the schema check found
- Human PRs have **no rows** in `pr_reviews`, `pr_comments`, `pr_review_comments_v2`, `pr_commits`, `pr_commit_details` or `pr_timeline`.
- No table has CI or check results.
- `pr_timeline` has no `cross-referenced` events, and its `referenced` events carry a commit SHA but no message.

### What can and can't be compared
- **Agent vs. human:** only PR-level fields can be compared: state, `created_at`, `closed_at`, `merged_at` and the LLM task type.
- **Agent PRs only:** review comments and review rounds can be described, with no human comparator.
- **Not computed:** CI results and follow-up fixes or reverts.

## Cleaning the human baseline

Drop a human PR if any of these hold:
1. **Bot or automation account:** the author login ends in `[bot]` or `bot` (case-insensitive), or is `Copilot` or `airbyteio`. `airbyteio` opens templated "run up-to-date pipeline" PRs.
2. **Agent signature in the body:** the body contains one of `Generated with Claude Code`, `Co-Authored-By: Claude`, `chatgpt.com/codex`, `app.devin.ai` or `cursor.com`.
3. **Duplicate:** its `html_url` also appears in the agent table.

## Equal follow-up time

The two tables were captured at different times. The human table's latest timestamp of any kind is `T_h` = 2025-06-28 23:07:52 UTC, while the agent table runs to 2025-07-30. The code computes `T_h` from the data.

To give both groups the same follow-up:
- **Primary outcome:** "merged within 30 days of being opened".
- **Sample window:** only PRs created on or before `T_h − 30 days`.

## Matching (1:1, built only from fields that are not outcomes)

1. **Candidate pairs:** an agent PR and a cleaned human PR in the same repo (`repo_url`), with the same task type (`pr_task_type.type` / `human_pr_task_type.type`), created no more than 30 days apart, and both inside the window above.
2. **Order:** agent PRs that have at least one candidate are shuffled with `numpy.random.default_rng(2026)`.
3. **Greedy pass:** in that order, skip an agent PR if its repo already has 3 pairs. Otherwise pair it with the unused human candidate whose creation time is closest, breaking ties by the lower human id. Stop at 200 pairs.
4. **Size:** human PRs have no commit or diff data, so size can't be matched. Agent PR size is reported for description only.

## Outcomes

### Agent vs. matched human PRs
- **Primary:** merged within 30 days (binary).
- **Secondary:**
  - closed without merge within 30 days;
  - still open at day 30;
  - hours from open to merge, among PRs merged within 30 days.

### Agent PRs only (descriptive; the dataset has no human comparator)
"Human" means an account that is not a bot: `user_type` is not `Bot`, the login doesn't end in `[bot]`, and the login isn't `Copilot`. Only activity before the merge or close counts; for PRs still open, activity up to day 30.

- **Review comments:** inline review comments plus conversation comments by humans other than the PR author.
- **Review rounds:** submitted reviews (any state) by humans other than the PR author.
- **Decision path:**
  - merged with no review or comment from a non-author human;
  - merged after at least one;
  - closed without merge;
  - still open at day 30.

## Statistics

- **Proportions:** Wilson 95% CI for each group. Agent minus human difference in percentage points, with a 95% percentile CI from a cluster bootstrap that resamples repositories (10,000 resamples, seed 2026). Effect size: Cohen's h, with a bootstrap CI.
- **Time to merge:** medians and IQR. Effect size: Cliff's delta (agent vs. human), with a cluster-bootstrap CI.
- No p-values, and no subgroup tests. Per-agent rows are counts only.

## Comparison steps (reported in full, whatever they show)

The agent-minus-human gap in merge rate, as the comparison is made fairer one change at a time:

0. Raw tables; merged at each table's snapshot.
1. Raw tables; merged within 30 days; created on or before `T_h − 30 days`.
2. Step 1 with the cleaned human baseline.
3. Step 2 restricted to repos that have both kinds of PR.
4. The matched sample (primary).

Every step gets the same repo-cluster bootstrap CI.

## Changes after outcomes were computed

All three changes were made on 2026-11-02, after the first full run of `04_analyze.py`. None of them changes a planned number: every bootstrap seed is fixed per step, so steps 0–4 and the matched-sample results are identical to the first run.

1. **Added step 1a** (raw tables, merged at snapshot, created by the window end). **Why:** step 1 changed two things at once, the time window (which shifts the agent mix towards Devin) and the outcome horizon. Step 1a separates the two.
2. **Added a table of which agents' PRs each step compares.** It counts PRs only, with no outcomes. **Why:** to explain the jump between steps 0 and 1a.
3. **Added a descriptive check of who closed the agent PRs that were closed without merge** (the last `closed` event in `pr_timeline`). **Why:** a spot-check showed that some were closed by the agent's own account or by the person who ran the agent, rather than by a reviewer. That changes how "closed without merge" can be described. It's descriptive only and can't be compared with humans, who have no timeline.
