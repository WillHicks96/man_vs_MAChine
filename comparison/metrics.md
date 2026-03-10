# Comparison Metrics: Human vs. Machine Science

**Context:** Galaxy cluster relaxation classification using the Frontier-E HACC simulation.
Three paradigms: (A) `team_human`, (B) `team_machine_singlestep`, (C) `team_machine_multistep`.
This framework is intended to be reusable for other A/B benchmark exercises.

---

## Framing Principle

The three paradigms differ not just in *who* did the work but in *how the task was specified*:

| Team | Input cost | Autonomy |
|------|-----------|----------|
| Human | Years of domain knowledge + hours of coding | Full |
| Machine single-step | High — detailed 7-step prescriptive prompt | Low |
| Machine multi-step | Low — vague 2-sentence prompt | High |

Any fair comparison must account for this asymmetry. A machine that received an expert-written roadmap should not be compared directly on "creativity" against one that had to discover the roadmap itself.

---

## Key Metrics

### 1. Yield Ratio (Quantitative)

**Definition:** Fraction of total outputs that are publication-ready.

- **For plots:** subjective but assessable — axis labels, units, legend, caption-worthy, physically meaningful comparison shown. Count manually.
- **For code:** functions/scripts that are self-contained, parameterized (no hardcoded paths), and could be dropped into a paper's supplementary without embarrassment.
- **For data products:** JSON/CSV files that are fully annotated and documented enough to be shared.

> *Why it matters:* Raw output volume is misleading. A team that produces 100 plots with 80 exploratory/debug ones is less efficient than one producing 20 all-publishable. This is especially important for the multi-step approach where early phases generate significant noise.

**Operationalization:** `N_pub-ready / N_total` per output type.

---

### 2. Phase Convergence / Iteration Efficiency (Quantitative, multi-step specific but generalizable)

**Definition:** For iterative approaches, at which phase/iteration do outputs stabilize into publication-ready form? What fraction of total effort (code, plots) was in pre-convergence exploration?

- Identify the "last substantive revision" of each analysis task (e.g., phase4 supersedes phase2 for the same task).
- Compute: `N_tasks_completed_in_final_phase / N_total_tasks_attempted`
- Also: `LOC_in_final_phase / LOC_total` — code signal-to-noise ratio.

> *Why it matters:* The multi-step agent may revisit a task 3 times before getting it right. The useful output is only the last version. This metric distinguishes efficient convergence from noisy wandering. For single-step or human work, this is trivially 1.0, which is itself informative.

---

### 3. Scientific Scope Coverage (Qualitative → Quantitative via rubric)

**Definition:** Against the full problem statement, how many distinct scientific tasks were (a) attempted and (b) successfully completed?

Define a canonical task list from the problem statement (e.g., for this experiment: profile exploration, reference model fits, criterion definitions, stacked profile analysis, scaling relations, extreme objects, core thermodynamics = 7 tasks). Score each team 0/0.5/1 per task:
- 0 = not attempted
- 0.5 = attempted but incomplete or incorrect
- 1 = completed with correct methodology

> *Why it matters:* This is the primary differentiator in *breadth*. It captures whether a paradigm systematically misses certain classes of tasks (e.g., humans may skip tedious bulk computation; machines may miss physically motivated edge cases).

**Operationalization:** Rubric score matrix (team × task), filled in by a domain expert.

---

### 4. Methodological Rigor (Qualitative → Semi-quantitative)

Four sub-criteria, each scored 0–2:

| Sub-criterion | What to look for |
|---------------|-----------------|
| **Statistical completeness** | Error bars, percentile bands, scatter quantification — not just medians |
| **Threshold justification** | Are criterion thresholds cited from literature or arbitrary? |
| **Reproducibility** | Can an outside reader reproduce results from provided code + data? No hardcoded absolute paths, random seeds set, data access documented. |
| **Self-consistency checks** | Do teams verify their own results (e.g., cross-check two criteria give consistent relaxed fractions)? |

> *Why it matters:* A machine can produce many plots quickly, but if thresholds are unjustified or results can't be reproduced, scientific value is low. Humans tend to justify choices from memory; machines may hallucinate or omit justification.

---

### 5. Physics Insight Depth (Qualitative, expert-scored)

**Definition:** Quality of interpretation beyond the numbers — does the team understand *why* results look the way they do?

Assess from reports/documentation:
- Are discordant objects (e.g., sloshing cool-cores) identified and physically explained?
- Do conclusions go beyond restating results to make predictive or interpretive claims?
- Is there any novel angle not explicitly requested in the prompt (e.g., a new diagnostic, a connection to observations)?
- Are known failure modes of criteria acknowledged (e.g., projection effects, resolution limits)?

**Operationalization:** Holistic rubric, 1–5 scale, scored independently by ≥2 domain experts. Note specific examples from each team's outputs.

> *Why it matters:* This is where human expertise most often dominates — not in doing the computation, but in recognizing what the results *mean* and what caveats apply.

---

### 6. Input Cost vs. Output Quality Efficiency

**Definition:** How much human effort was required to get the outputs?

| Team | Input cost proxy |
|------|-----------------|
| Human | Estimated person-hours of coding + analysis |
| Machine single-step | Hours of prompt engineering + review time |
| Machine multi-step | Minutes of prompting + hours of review/steering |

Pair with output quality scores from metrics 1–5. The key question: at equal output quality, which paradigm requires less human time?

> *Why it matters:* This is the core ROI question for the benchmarking exercise. A machine that produces slightly worse science at 10× less human time may still be the preferred paradigm for many use cases.

---

## What NOT to Use as a Primary Metric

- **Raw lines of code** — more code is not better; multi-step will trivially win this.
- **Total number of plots** — similarly, volume ≠ quality.
- **Whether the "right" answer was found** — there may be no single right answer for an exploratory science task; multiple valid approaches exist.
- **Execution time** — not directly comparable given different compute access and task specification.

---

## Generalization Notes (for future experiments)

To reuse this framework for a different A/B science benchmarking exercise:

1. **Replace the task rubric** (Metric 3) with a canonical task list derived from the new problem statement.
2. **Keep Metrics 1, 2, 4, 5** as-is — they are problem-agnostic.
3. **Adjust Metric 6** input cost proxies to match how the new experiment was set up.
4. For experiments with >3 paradigms, add a column per team to the rubric matrices.
5. If the experiment has a ground truth (e.g., a known classification), add a **predictive accuracy** metric using standard ML evaluation (precision/recall/F1 relative to ground truth), which is not applicable here due to the blind comparison setup.

---

## Suggested Presentation Format

For a paper or summary report, organize results as:
1. A **rubric score table** (teams × metrics) — gives a quick visual comparison.
2. **Yield ratio bar chart** by output type (plots / code / data).
3. **Phase convergence curve** for multi-step: cumulative publication-ready outputs vs. phase number.
4. **Qualitative narrative** for Metrics 4 and 5, with specific examples from each team's reports.

This avoids the trap of collapsing everything into a single number while still enabling structured comparison.
