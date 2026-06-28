# RepoVeritas v1 — Dataset Card

## Dataset summary

**RepoVeritas** is a code-grounding benchmark in the spirit of FEVER, but for source code and centered on **sufficiency**. Each item pairs a natural-language **claim** about a piece of code with the **visible code evidence**, and asks a model to assign one of three labels:

- **supported** — the visible code positively establishes that the claim is true;
- **contradicted** — the visible code positively establishes that the claim is false (it does the opposite, or something incompatible);
- **insufficient** — the visible code is on-topic but does not contain enough to decide whether the claim is true or false.

The **insufficient / abstention** class is the methodological contribution. Most code-understanding and fact-verification benchmarks are two-way (true/false) or treat "not enough information" as a noisy afterthought; RepoVeritas makes the question *"can the model recognize when the evidence does not settle the claim?"* a first-class, separately-scored target on real code. The headline metric is **insufficient-F1**, backed by macro-F1 and per-class confusion; accuracy is reported but de-emphasized (the supported-heavy class distribution makes it misleading — see *Considerations*).

v1 is deliberately narrow: **Python only**, two task families, English claims, claim-grounding sufficiency.

## Supported tasks

A single task — three-way claim-grounding classification — over two families:

- **`docstring_function`** — claim = the first sentence of a function's docstring; evidence = the function body (chunked). Tests whether the documented behavior is borne out by the implementation shown.
- **`commit_diff`** — claim = a commit subject line; evidence = the Python diff. Tests whether the described change is borne out by the diff shown.

## Languages

Code: Python. Claims and rationales: English.

## Dataset structure

### Two views (eval-hygiene wall)

The dataset ships in two strictly-separated views, enforced by the export harness:

- **Model-facing (`*_public.jsonl`)** — the *only* fields a model ever sees:
  `id`, `task_family`, `claim`, `evidence_spans`.
- **Private gold/audit (`*_gold.jsonl`)** — everything needed to score and study the data:
  `public_id`, `label`, `justifying_span_ids`, `rationale`, `claim_origin`, `mutation_type`, `original_claim`, `tier`, `sourcing_method`, `task_family`, `split`, `source_item_id`, and annotation metadata (`annotator`, `guide_version`, `label_tool`, `labeled_at_utc`).

The fields kept out of the public view are the ones that would leak the answer: `label` and `rationale` obviously, but also `mutation_type` / `original_claim` (which would flag a mutated → contradicted item), `sourcing_method` (gold-sourced items are nearly all supported), and `tier`. **Public IDs are neutral and shuffled** (`rv_{split}_NNNNNN`), assigned after a shuffle so that neither the field set nor the ID value betrays the label; the mapping to original IDs lives only in the private `id_map.json`.

### Data fields (model-facing)

- `id` *(string)* — neutral public identifier of the form `rv_{split}_NNNNNN`.
- `task_family` *(string)* — `docstring_function` or `commit_diff`.
- `claim` *(string)* — the natural-language claim.
- `evidence_spans` *(list of string)* — the visible code, as one or more spans. (Median: ~380 characters over 2 spans for docstring items; ~693 characters over 4 spans for commit items.)

### Data splits

Split **by repository** (commit family) and evidence-bound (see *Eval hygiene* below), ~30/70 dev/test. `dev` is for prompt/few-shot tuning; `test` is the leaderboard split.

| split | n | supported | insufficient | contradicted | docstring | commit |
|---|---|---|---|---|---|---|
| dev | 87 | 56 | 19 | 12 | 41 | 46 |
| test | 207 | 133 | 44 | 30 | 97 | 110 |
| **total** | **294** | **189** | **63** | **42** | **138** | **156** |

### Composition (family × label)

| family | supported | insufficient | contradicted | total |
|---|---|---|---|---|
| `docstring_function` | 81 | 40 | 17 | 138 |
| `commit_diff` | 108 | 23 | 25 | 156 |
| **total** | **189** | **63** | **42** | **294** |

Class proportions: **supported 64.3%, insufficient 21.4%, contradicted 14.3%.** This is *not* the original 40/30/30 target; the distribution drifted supported-heavy by deliberate choice (see *Curation rationale* and *Considerations*).

## Dataset creation

### Curation rationale

RepoVeritas exists to measure abstention on code grounding — the gap between a model's ability to *confirm* a claim and its ability to *recognize when it cannot*. Existing benchmarks largely test verification on text (FEVER and successors), or test code understanding without isolating sufficiency. By scoring the *insufficient* class separately on real Python, RepoVeritas turns "I don't have enough to tell" from a failure mode into a measurable capability.

Three labeling principles, fixed during construction, define the data's character:

- **Unrelated ≠ contradicted.** A claim whose evidence is about an entirely different function is a *retrieval failure*, not a contradiction. Such pairs are routed to `reject_out_of_scope` and excluded from the benchmark. Genuine *contradicted* requires the **same operation with an opposite specific behavior**. (During construction, an audit found that 48 of 54 originally-labeled docstring-contradicted items were actually unrelated distractor pairs and were reclassified out; only 6 genuine natural contradictions survived.)
- **The visible-evidence rule.** *Insufficient* means the shown evidence genuinely fails to confirm the claim — typically because the deciding logic lives in code not included in the span. It is *related but not enough*, never *unrelated*.
- **Lean over padded.** Where a cell could not be filled with clean, genuine examples, it was kept small rather than padded with borderline cases. This is why the class balance drifted from target.

### Source data

- **Docstring family:** functions and their docstrings from the **CodeSearchNet** Python corpus.
- **Commit family:** commit messages and Python diffs from **8 locked repositories** — `django`, `scikit-learn`, `pandas`, `numpy`, `ansible`, `requests`, `flask`, `scrapy` — via the GitHub API.

Roughly 70% of items are fully real (real code + real claim). The exception is the contradicted class (below).

### Annotations

All items were labeled against a written rubric (`RepoVeritas_labeling_guide.md`) using a dedicated labeling harness, with each label stamped with annotator, guide version, tool, and timestamp. The primary annotator is the dataset author.

### The contradicted class is mutation-based (disclosed)

Naturally-occurring, on-topic contradictions are rare, so most **contradicted** items are constructed by **adversarially editing the claim while leaving the code untouched** — manufacturing a same-operation opposite (e.g. flipping a verb or a target so the claim now asserts the opposite of what the code does). Every such item privately carries `claim_origin="mutated"`, `mutation_type`, the `original_claim`, and a `tier` (`code_grounded` for high-precision rule-confirmed flips, `review_only` otherwise). Of the 42 contradicted items, **36 are mutation-based and 6 are natural** (real documentation drift). By family, the 6 natural contradictions are all docstring items; all 25 commit-contradicted and 11 docstring-contradicted items are mutated.

A construction finding worth recording: **commit claims mutate cleanly far more often than docstring claims** (≈75% vs ≈25% acceptance of proposed flips), because commit subjects are natural prose whereas CodeSearchNet docstrings carry `:param:`/`:return:` scaffolding that makes many flips read as synthetic.

## Eval hygiene and contamination control

- **No source + mutation across splits.** Each mutated-contradicted item shares its *evidence* with the supported item it was derived from (linked by `source_item_id`). These pairs are bound to the **same split** so a model never sees one as training/dev context and the other as test. The export manifest records **36 source–mutation pairs, all same-split, and `cross_split_pairs = 0`.** (Boundary: contamination control is *lineage-based*; coincidental cross-split overlap of unrelated evidence is not auto-detected.)
- **Rejects are excluded, not deleted.** The 84 `reject_out_of_scope` items (unrelated claim/evidence) are kept in `rejects_audit.jsonl` for transparency but are not part of the benchmark.
- **Neutral, shuffled public IDs** prevent ID-order leakage of labels.

## Reliability

Reported in two parts: an instrument check on a clean constructed set, and the production figure on real data.

**Instrument check (kill-test).** A blind kill-test on a fresh 15-item constructed set returned **intra-rater κ = 1.00, inter-rater κ = 1.00, and insufficient-vs-rest κ = 1.00** — establishing that the labeling scheme is *applicable and self-consistent* under ideal conditions. This validates the instrument; it is not the production number.

**Production reliability (inter-rater, real data).** The citable figure comes from a **60-item validation slice** drawn from the released test split, stratified at 10 items per (family × label) cell and **deduplicated by evidence** so that no two items in the slice share the same code — preventing agreement from being inflated by a rater anchoring on a source/mutation contrast pair. An independent second rater labeled the slice **blind**: given only the claim, the visible code, and the labeling guide, with no access to the gold labels, the answer key, or any scoring logic. Agreement against the released gold:

| metric | κ |
|---|---|
| **Overall Cohen's κ** | **0.800** |
| insufficient (one-vs-rest) — *headline* | **0.775** |
| supported (one-vs-rest) | 0.741 |
| contradicted (one-vs-rest) | 0.886 |
| raw agreement | 0.867 (52 / 60) |

By the Landis–Koch convention this is **substantial-to-almost-perfect** agreement. The figure that matters most for this dataset is the **insufficient-vs-rest κ of 0.775**: the abstention class — the benchmark's core contribution — is *reliably annotatable*, not subjective noise.

The 8 disagreements are **concentrated on the insufficient↔supported boundary** (5 of the 8 involve that confusion); contradicted is the most-agreed class (κ 0.886, 18 of 20 matched). That the residual human disagreement falls on the sufficiency boundary — the same boundary models fail on (see `RepoVeritas_results.md`) — is consistent with that judgment being intrinsically subtle rather than the labels being arbitrary, and is itself a small corroboration of the benchmark's premise. The κ above is computed on the labels exactly as released.

## Considerations for using the data

- **`insufficient` is the contribution and the hardest class.** As in comparable benchmarks (e.g. AVeriTeC's NEI class), F1 on the abstention label sits well below the other classes; baseline models score 0.00–0.44 insufficient-F1 across the Qwen2.5 0.5B–7B range, and even Claude Opus 4.8 reaches only 0.657 (versus 0.923 supported-F1) — the gap is task-intrinsic, not a small-model artifact. Treat insufficient-F1 (and macro-F1), not accuracy, as the headline.
- **The class distribution is supported-heavy by construction (64/21/14).** A majority-class predictor scores ~64% accuracy. This is why accuracy is de-emphasized; on the baseline sweep, accuracy actively *inverts* the true competence ranking of models (see `RepoVeritas_results.md`).
- **The contradicted class is largely synthetic** (86% mutated claims over real, untouched code). It is transparently flagged in the private fields. Studies that need naturally-occurring contradictions should filter on `claim_origin`.
- **Contamination dedup is lineage-based**, not a full evidence-hash dedupe; coincidental cross-split evidence overlap is not automatically caught.
- **Scope is narrow:** Python only, two task families, single primary annotator. Generalization to other languages, task framings, or annotator pools is untested in v1.

## Files

**Public release:**

| file | contents |
|---|---|
| `test_public.jsonl` / `dev_public.jsonl` | model-facing inputs (id, task_family, claim, evidence_spans) |
| `test_gold_labels.jsonl` / `dev_gold_labels.jsonl` | answer labels only (public_id, task_family, label) |
| `rejects_audit.jsonl` | the 84 excluded `reject_out_of_scope` items (slimmed, neutral IDs) |
| `export_manifest.json` | input SHA256, shuffle seed, split/label counts |

**Withheld (private)** to keep the benchmark sound — full-provenance gold (`test_gold.jsonl` / `dev_gold.jsonl` with rationale, `mutation_type`, `original_claim`, `claim_origin`, `tier`, etc.) and the `id_map.json` public-ID→source mapping. Only the answer `label` is released; the provenance that would let a model game the contradicted class, or de-anonymize the items, is not.

Scoring uses `baseline_eval.py`: predict on a `*_public.jsonl` file, score against the matching `*_gold_labels.jsonl`. The harness reports per-class P/R/F1, macro-F1, insufficient-F1, a confusion matrix, and a per-family breakdown.

## Reproducibility

### From locked gold to released benchmark (the row-count chain)

The released benchmark is the result of two pruning stages applied to the locked gold file. The counts are easy to misread without the chain spelled out, so it is stated explicitly here:

```
389   labels_v1_locked.jsonl        full annotated pool (locked gold)
 −11   evidence-bound split pruning   6 failed-flip + 5 duplicate-evidence
 ───
378   labels_v1_split.jsonl          export-harness input  (manifest total_in)
 −84   reject_out_of_scope            unrelated claim/evidence (→ rejects_audit.jsonl)
 ───
294   released benchmark             dev (87) + test (207)
```

- The **locked gold** (`labels_v1_locked.jsonl`) holds **389 rows** — the complete annotated pool, including all mutation candidates.
- The evidence-bound splitter prunes **11 rows**: **6 failed-flip items** (mutation candidates whose claim could not be cleanly flipped, so they remained synthetic *supported* near-duplicates of a real item) and **5 duplicate-evidence items** (3 commits sharing an identical diff, plus the 2 mutations derived from those commits). These 11 are retained with a `_drop_reason` in `dropped_audit.jsonl`. The result is the **378-row** export input.
- The export harness then excludes the **84 `reject_out_of_scope`** items (retained in `rejects_audit.jsonl`), leaving the **294-item benchmark**.

So the manifest's `total_in = 378` is the **post-pruning** count, not the locked-file count; the 389 → 378 difference is the 11 deliberately-pruned rows above, not a discrepancy. Note these are two *distinct* exclusions in two files: the **11** are mechanical pruning (`dropped_audit.jsonl`), the **84** are semantic out-of-scope rejects (`rejects_audit.jsonl`).

### Manifest and lineage

The export manifest records the input file **SHA256 `c1b42db7f11f7a3c6c01e69ffab54099f30ee72d033c3242f5abfc11171b61a1`**, **shuffle seed 13**, pair-policy (`warn`), and full per-cell counts (`total_in = 378`, `rejects_dropped = 84`, `kept = 294`, `source_pairs_detected = 36`, `cross_split_pairs = 0`). Source-item lineage is preserved end-to-end via `source_item_id` and the per-item provenance fields.

## Baseline results

See `RepoVeritas_results.md`. In brief, on the 207-item test split: the majority floor reaches 0.643 accuracy with **0.000 insufficient-F1**; the Qwen2.5-Instruct family climbs from **0.000** (0.5B) to **0.438** (7B) insufficient-F1 while supported-F1 stays near ~0.78; and **Claude Opus 4.8**, the frontier ceiling, reaches **0.657** insufficient-F1 against **0.923** supported-F1. The abstention gap therefore **persists at the frontier** — Opus nearly solves the supported and contradicted classes but recovers only 52% of insufficient items, declaring a verdict on the rest. The gap is task-intrinsic, and at small scale it is invisible to accuracy (which collapses onto the majority class).

## Citation and contact

Author: dataset author (independent research). *Related work and citations — including the sufficiency-verification line this benchmark connects to — to be added by the author. [PLACEHOLDER]*

## Limitations recap (one line)

A narrow, honest, Python-only v1 whose value is a cleanly-measured *insufficient* class; its contradicted class is mostly synthetic-but-disclosed, its class balance is supported-heavy, and its inter-rater reliability is κ = 0.80 overall (0.775 on the insufficient class).
