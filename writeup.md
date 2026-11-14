# Are AI agents' pull requests treated differently from people's? A one-page summary

**The question.** AI coding agents such as Devin, Codex and Copilot now open pull requests (PRs) on real open-source projects. Someone still has to decide whether to merge each one. I wanted to know how often maintainers merge agent PRs compared with ordinary human PRs, and how much of that decision is visible in public data.

**What I did.**
- **Data:** I used AIDev, a public dataset of agent PRs on GitHub. I used the release from the MSR 2026 Mining Challenge, because it is the only one that also includes human PRs from the same projects.
- **Cleaning:** first I removed the "human" PRs that weren't really human. That is 18% of them: Dependabot, Renovate, other automation, and PRs written by agents.
- **Matching:** I paired 200 agent PRs with 200 human PRs from 108 projects. In each pair both PRs come from the same project, do the same kind of task (feature, bug fix, docs and so on), and were opened within 30 days of each other.
- **Outcome:** for each PR I checked what had happened 30 days after it was opened. I wrote the analysis plan down before looking at any results; the few things added afterwards are marked as such. Every number comes from a script anyone can rerun.

**What I found.**
- **Agent PRs were merged much less often.** Within 30 days, 49.5% of the agent PRs were merged, against 81.0% of their human partners: a gap of about 32 percentage points (95% confidence interval 23 to 40).
- **The missing merges were mostly closures.** 41% of agent PRs were closed without being merged, against 9% of human PRs. About the same share of each (roughly 1 in 10) was still open.
- **Speed was the same.** Agent PRs that were merged went in about as fast as human ones: a median of 1.8 hours for agent PRs against 2.5 hours for human PRs, a difference too small to detect.
- **The fair comparison matters.** If you simply compare the two tables as published, the gap looks like only 5 points. It appears once you compare PRs from the same months and the same projects. In the popular projects that also have human PRs, only 48.7% of agent PRs were merged within 30 days, against 61.7% across all projects.
- **Many merges leave no trace of review.** Almost half (45 of 99) of the merged agent PRs had no review or comment from anyone other than their author.
- **"Closed" doesn't always mean "rejected".** 30 of the 82 closed agent PRs were closed by the agent's own account or by the person who ran the agent, rather than by someone reviewing it.

**What the data can't tell us.**
- It has no CI (automated test) results.
- It has no record of reviews, comments or commits for the human PRs.
- It has no reliable way to see whether a merged PR was later fixed or reverted.

So it shows *what* was decided, but not *why*, and not whether the decision was right.

**Why this matters, and what's next.** The interesting question is how developers decide when to trust an agent's PR, when to ask for changes, and when to reject it, and what checking they do that never shows up in the PR. A full study would:
1. collect CI results and review history for both agent and human PRs;
2. follow merged changes for 30 to 90 days to see which ones needed fixes;
3. interview maintainers about how they make these calls.

**Caveats.**
- **A narrow slice of time and agents.** This is a small pilot covering PRs opened between late December 2024 and May 2025, and half the agent PRs come from Devin. It says little about newer agents such as Claude Code.
- **No match on size or author.** I couldn't match PRs on size, or on how experienced the author was, because the dataset has no such data for human PRs.

The full details and every number are in README.md and the `results/` folder.
