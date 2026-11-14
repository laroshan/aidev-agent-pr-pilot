# The pilot in pictures

A visual walk through the ideas behind this pilot. Every number comes from [`results/results.md`](results/results.md). The diagrams render on GitHub.

## 1. What happens to a pull request

A coding agent (or a person) opens a pull request. Someone then decides what to do with it. This pilot is about that decision.

```mermaid
flowchart LR
    A["Agent or person<br/>opens a PR"] --> B{"Maintainer decides"}
    B -->|trust| C["Merged as it is"]
    B -->|revise| D["Review comments,<br/>more commits"]
    D --> B
    B -->|reject| E["Closed without merge"]
```

## 2. What public data can and can't see

The dataset records the outcome of the decision, not the thinking behind it.

```mermaid
flowchart TB
    subgraph seen["Visible in AIDev"]
        S1["Merged or closed, and when"]
        S2["Review comments and reviews<br/>(agent PRs only)"]
        S3["Who closed the PR<br/>(agent PRs only)"]
    end
    subgraph hidden["Not visible"]
        H1["Why the PR was merged or closed"]
        H2["Checking that left no trace"]
        H3["Whether CI checks passed"]
        H4["Fixes or reverts after the merge"]
    end
    seen --> Q["A full study needs both sides"]
    hidden --> Q
```

## 3. Why a simple comparison isn't fair

Agent PRs and human PRs come from different projects, months and kinds of task. Comparing all of them mixes those differences into the result.

```mermaid
flowchart LR
    subgraph raw["Raw comparison"]
        R1["All agent PRs<br/>many small, easy-merge repos<br/>mostly Codex, mid-2025"]
        R2["All 'human' PRs<br/>bigger repos, early 2025<br/>18% are bots or agents"]
    end
    subgraph fair["Matched comparison"]
        F1["Agent PR"]
        F2["Human PR"]
        F1 ---|"same repo<br/>same task type<br/>opened within 30 days"| F2
    end
    raw -->|"clean, align time,<br/>match"| fair
```

## 4. How the 200 pairs were built

```mermaid
flowchart TB
    A["33,596 agent PRs"] --> C
    B["6,618 'human' PRs"] --> B2["Drop 1,187 bot, automation<br/>and agent PRs"]
    B2 --> C["Keep PRs opened by 29 May 2025<br/>(30 days of follow-up for both)"]
    C --> D["Candidate pairs:<br/>same repo, same task type,<br/>opened within 30 days"]
    D --> E["2,662 agent PRs have a candidate"]
    E --> F["Shuffle with a fixed seed.<br/>Each takes the closest unused human PR.<br/>At most 3 pairs per repo."]
    F --> G["200 pairs from 108 repos"]
```

## 5. What happened within 30 days

```mermaid
pie showData title Agent PRs (200)
    "Merged" : 99
    "Closed without merge" : 82
    "Still open" : 19
```

```mermaid
pie showData title Matched human PRs (200)
    "Merged" : 162
    "Closed without merge" : 18
    "Still open" : 20
```

Merged: 49.5% of agent PRs against 81.0% of human PRs. The gap is −31.5 points (95% CI −40.1 to −23.0).

## 6. The gap depends on what you compare

Each step removes one unfair difference. Two steps move the gap: comparing the same months, and comparing the same repositories.

```mermaid
flowchart LR
    S0["Raw tables<br/>−5.3"] --> S1a["Same months<br/>−16.6"]
    S1a --> S1["Merged within 30 days<br/>−15.6"]
    S1 --> S2["Bots removed<br/>−16.9"]
    S2 --> S3["Same repos<br/>−30.3"]
    S3 --> S4["Matched pairs<br/>−31.5"]
```

## 7. Inside the agent PRs: three decision paths

Only agent PRs have review data, so this view has no human comparison.

```mermaid
pie showData title 200 agent PRs after 30 days
    "Merged, no human review or comment" : 45
    "Merged after human review" : 54
    "Closed without merge" : 82
    "Still open" : 19
```

Two cautions:
- **"No human review" means no visible review.** A person may have read the change and left no trace.
- **"Closed" isn't always "rejected".** 30 of the 82 closed PRs were closed by the PR's own account: the Devin bot (18), the person who ran Codex (11) or the person who ran Claude Code (1).

## 8. Why the uncertainty is computed per repository

PRs in one repository are judged by the same people, so they aren't independent. The pilot therefore resamples whole repositories.

```mermaid
flowchart TB
    A["108 repositories"] --> B["Draw 108 repositories at random,<br/>with repeats allowed"]
    B --> C["Recompute the gap"]
    C --> D{"Done 10,000 times?"}
    D -->|no| B
    D -->|yes| E["Middle 95% of the gaps<br/>= confidence interval<br/>−40.1 to −23.0"]
```

## 9. Where this leads

```mermaid
flowchart LR
    P["This pilot:<br/>outcomes only"] --> N1["Add CI results and<br/>human review data"]
    P --> N2["Follow merged PRs<br/>for fixes and reverts"]
    P --> N3["Interview maintainers:<br/>how do you decide to trust,<br/>revise or reject?"]
    N1 --> G["How developers decide<br/>on an agent's PR"]
    N2 --> G
    N3 --> G
```
