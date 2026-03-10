# Man vs. MAChine — Comparison Report
**Task:** Multi-criterion galaxy cluster relaxation study, Frontier-E HACC simulation, ~10,000 halos at z=0
**Three paradigms:** Expert human scientist · AI single-step (prescriptive 7-step prompt) · AI multi-step (2-sentence vague prompt)
**All numbers in this document are auto-computed from the repository filesystem via `compare.py`.**

---

## 1. Output at a Glance

| Metric | Human | AI Single-step | AI Multi-step |
|---|---|---|---|
| Python scripts | 1 | 0 (no saved scripts) | 31 |
| Lines of code (LOC) | 312 | — | 8,089 |
| Defined functions | 7 | — | 142 |
| Total PNG plots | 5 | 52 | 55 |
| **Pub-ready plots** | **5 (100%)** | **32 (62%)** | **24 (44%)** |
| Data files (JSON+CSV) | 0 | **29** | 8 |
| Structured report pages | 0 | 0 | **~42 (LaTeX)** |
| Agent execution log | — | ~519 pp (Md) | ~1 pp |

**The Human produced the smallest but cleanest output: every plot was analysis-grade.**
**The AI teams traded yield ratio for breadth.**

---

## 2. Scientific Scope Coverage

Scored against the 7 canonical tasks defined in the experiment prompt (0 = not done, 0.5 = partial, 1 = complete). Evidence for every score is documented in `compare.py::RUBRIC`.

| Task | Human | AI Single-step | AI Multi-step |
|---|---|---|---|
| T1 Profile exploration | ✗ | ✓ | ✓ |
| T2 Reference model fits (NFW, β, UPP) | ✗ | ✓ | ✓ |
| T3 Relaxation criteria (all 4 δ) | ½ | ✓ | ✓ |
| T4 Stacked profiles by class | ✗ | ✓ | ✓ |
| T5 Scaling relations (L_X–T, Y_SZ–M) | ½ | ✓ | ✓ |
| T6 Extreme / discordant objects | ✗ | ✓ | ✓ |
| T7 Core thermodynamics (TPI, BH) | ½ | ✓ | ✓ |
| **Total** | **1.5 / 7** | **7.0 / 7** | **7.0 / 7** |

**Both AI paradigms achieved complete scope coverage. The human addressed ~21% of the prescribed task space.**
However, this comparison is incomplete without the next section.

---

## 3. What the Scope Score Misses: Human Novelty

The human scientist did not simply under-perform — they pursued a **completely different scientific hypothesis**. The human's `relaxed_classify.py` introduces a novel relaxation indicator:

> **Δ_Mgal = (M₁ − M₂) / M₁** (stellar mass gap between the two brightest cluster galaxies, binned by halo mass)

This criterion does not appear in the prompt, nor in either AI team's work. It leverages the idea that dynamically disturbed clusters host a more even distribution of massive satellite galaxies (smaller gap), as opposed to relaxed clusters dominated by a single BCG. The code is MPI-parallelised (mpi4py), targeting HPC execution from day one — a design choice neither AI team made.

**Novelty score: Human 5/5, AI Single-step 2/5, AI Multi-step 3/5.**
The creative gap remains the most important unresolved difference between human and AI science.

---

## 4. Holistic Quality (Scored 1–5)

| Dimension | Human | AI Single-step | AI Multi-step |
|---|---|---|---|
| Physics insight | 4 | 4 | 4 |
| Statistical rigor | 3 | **5** | 4 |
| Reproducibility | 4 | 2 | **5** |
| Novelty | **5** | 2 | 3 |

- **Rigor:** Single-step produced percentile bands on all 20 stacked profile plots, concordance statistics across all 4 criteria, and quantified scaling-relation scatter. No other team matched this level of systematic statistical treatment.
- **Reproducibility:** Multi-step wins by a large margin — 31 saved Python scripts, phased JSON outputs, and a LaTeX-formatted paper. Single-step generated zero reusable code; the pipeline cannot be re-run independently.
- **Human trade-off:** High novelty and domain-appropriate HPC design, at the cost of statistical completeness and narrow scope.

---

## 5. Multi-step Phase Convergence

The multi-step agent refined its outputs across 7 phases. Phase-by-phase LOC and pub-ready plot accumulation (from `compare.py::collect_phase_data`):

| Phase | LOC written | New pub-ready plots | Cumulative pub plots |
|---|---|---|---|
| 1 – Profile exploration | 156 | 1 | 1 |
| 2 – Model fits | 349 | 2 | 3 |
| 3 – Profile quality | 270 | 1 | 4 |
| 4 – Criteria & distributions | 285 | 3 | 7 |
| 5 – Scaling / stacked / extreme | 467 | 5 | 12 |
| 6 – Comprehensive stacked + TPI | **737** | 4 | 16 |
| 7 – Particle gallery | 130 | 1 | **17** |

**~70% of the final pub-ready output came from phases 5–7, with phase 6 being the single most productive.** Phase 1–4 were largely scaffolding. This is consistent with the multi-step paradigm: early phases build infrastructure; scientific value concentrates in later phases. A reviewer of the multi-step work should focus on phase 5+ outputs.

---

## 6. Code Quality Analysis (Auto-measured via AST)

All scores 1–5, derived from AST parsing + regex. Raw measurements are logged in `metrics_data.json`.

| Dimension | Human | AI Multi-step | Winner |
|---|---|---|---|
| **Readability** (docstrings, comment density, function length) | 2.7 | **4.3** | AI Multi-step |
| **Portability** (hardcoded HPC paths penalty) | **4.0** | 1.0 | Human |
| **Robustness** (try/except coverage) | 1.0 | **2.6** | AI Multi-step |
| **Extendability** (config constants, parameterisation, magic numbers) | 2.5 | **3.8** | AI Multi-step |

**Raw measurements driving the scores:**

| Measurement | Human | AI Multi-step |
|---|---|---|
| Docstring coverage | 0% | **76%** |
| Comment density | 8.1% | 6.8% |
| Hardcoded absolute paths | **2** | 41 |
| try/except blocks | 0 | **23** |
| Config constants (UPPER_CASE) | 0 | **213** |
| Magic numbers | 53 | 2 123 |
| Avg function length (lines) | 45 | **37** |

**Key code quality finding:** The AI multi-step code is significantly more structured and self-documenting (76% docstring coverage, 108 of 142 functions have docstrings vs 0 for human). However, it pays a severe portability penalty: each of 16 phase files hardcodes three absolute cluster paths (`PROJECT_ROOT`, `EXPERIMENT_DIR`, `CATALOG`), making the pipeline non-portable without manual path editing. The human's single script is tightly coupled to Frontier-E HPC storage but has only 2 such paths. Neither team wrote assertions; the multi-step agent does include 23 try/except guards, mostly around data-loading.

---

## 7. Key Findings

### Where AI clearly wins

1. **Breadth and systematic coverage.** Both AI approaches completed every prescribed task. Neither would have missed an entire analysis step (e.g., model fits, TPI diagnostic, concordance tables). A human working alone on a complex multi-step task is far more likely to deprioritize certain analyses.

2. **Statistical rigour at scale.** The single-step agent applied error bands, scatter statistics, and cross-classification concordance to all 10,000 halos systematically. This level of statistical completeness is difficult to achieve in a human-driven exploratory session of equivalent duration.

3. **Documentation volume.** The multi-step agent produced a ~42-page LaTeX report without being explicitly asked to format it. The single-step agent produced ~519 pages of detailed execution logs that serve as a comprehensive lab notebook.

### Where human clearly wins

4. **Scientific creativity.** The Δ_Mgal criterion is a genuinely novel relaxation indicator that neither AI team considered. Humans generate hypotheses from physical intuition; AI (given a detailed prompt) executes a prescribed roadmap. Even the multi-step agent, given only a vague prompt, converged on the same analysis structure rather than inventing new science.

5. **Computational design awareness.** The human wrote MPI-parallel code targeting real HPC constraints from the outset. Neither AI team considered parallel execution.

### Structural asymmetry that limits direct comparison

6. **The prompt is part of the experiment.** Single-step AI received a 7-step detailed roadmap (high input cost from a domain expert). Multi-step received a 2-sentence vague prompt. Human had no prompt at all. Any ROI comparison must account for the human effort spent writing the single-step prompt — which itself encodes significant scientific design.

7. **Reproducibility asymmetry.** Single-step AI left no reusable code. Evaluating it as a production science pipeline requires either accepting black-box outputs or rebuilding the pipeline. Multi-step and human outputs are fully re-runnable.

---

## 8. Summary Assessment

| Question | Answer |
|---|---|
| Which paradigm covered the most science? | AI (both, equally) |
| Which produced the cleanest, most pub-ready output per plot? | Human (100% yield) |
| Which is most statistically rigorous? | AI Single-step |
| Which is most reproducible? | AI Multi-step |
| Which produced genuinely new scientific ideas? | Human |
| Which delivers the best ROI for well-scoped, known problems? | AI Single-step |
| Which is best for open-ended exploration with re-runnable code? | AI Multi-step |
| Which writes more self-documenting code? | AI Multi-step (76% docstring coverage vs 0%) |
| Which writes more portable code? | Human (2 hardcoded paths vs 41) |
| Which is more robust to runtime errors? | AI Multi-step (23 try/except blocks vs 0) |

---

*Report auto-generated from filesystem metrics. Rubric scores are manually curated with evidence in `compare.py`. Re-run `compare.py` to update after adding new outputs.*
