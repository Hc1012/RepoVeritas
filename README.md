# RepoVeritas

**A three-way code-grounding benchmark: can a model tell when the evidence isn't enough?**

RepoVeritas is "FEVER for code." Each item pairs a natural-language **claim** about a piece of code with the **visible code evidence**, and asks for one of three labels:

- **supported** — the visible code establishes the claim is true
- **contradicted** — the visible code establishes the claim is false
- **insufficient** — the visible code is on-topic but doesn't contain enough to decide

The **`insufficient` (abstention) class is the contribution.** Most code-understanding benchmarks are true/false; RepoVeritas makes *recognizing when the visible evidence does not settle the claim* a first-class, separately-scored capability — on real Python.

## Why it matters — the headline result

Models are far better at **confirming** claims than at **recognizing insufficient evidence**, and the gap is **task-intrinsic, not a small-model artifact.**

| model | accuracy | insufficient-F1 | supported-F1 |
|---|---|---|---|
| majority baseline | 0.643 | 0.000 | 0.782 |
| Qwen2.5-0.5B | 0.638 | 0.000 | 0.781 |
| Qwen2.5-7B | 0.647 | 0.438 | 0.783 |
| **Claude Opus 4.8** | 0.860 | **0.657** | 0.923 |

Two findings:

1. **Accuracy is a trap.** Qwen2.5-0.5B and Qwen2.5-7B post *the same accuracy* (~0.64), yet the 0.5B scores 0.000 insufficient-F1 (it's the majority-class baseline in disguise) and the 7B scores 0.438. Accuracy hides the abstention failure — and across the sweep it actually *inverts* the true ranking of the models.
2. **The gap survives at the frontier.** Claude Opus 4.8 nearly solves the supported (0.923) and contradicted (0.817) classes but reaches only **0.657** on insufficient, recovering just 52% of insufficient items — it issues a verdict on the rest. Recognizing when code evidence *doesn't decide* a claim is the capability that does not fall to scale.

Full analysis in [`RepoVeritas_results.md`](RepoVeritas_results.md).

## The dataset

294 human-labeled items across two task families:

- **`docstring_function`** — claim = a function's docstring first sentence; evidence = the function body
- **`commit_diff`** — claim = a commit subject line; evidence = the Python diff

| | supported | insufficient | contradicted | total |
|---|---|---|---|---|
| docstring_function | 81 | 40 | 17 | 138 |
| commit_diff | 108 | 23 | 25 | 156 |
| **total** | **189** | **63** | **42** | **294** |

Evidence-bound split into `dev` (87) and `test` (207). Sources: CodeSearchNet (docstrings) and eight major Python repositories — django, scikit-learn, pandas, numpy, ansible, requests, flask, scrapy (commits).

## Reliability

Inter-rater agreement on a 60-item blind, evidence-deduplicated slice labeled by an independent second rater:

- **Overall Cohen's κ = 0.800**
- **insufficient-vs-rest κ = 0.775** — the abstention class is *reliably annotatable*, not subjective noise
- raw agreement 0.867 (52/60)

## Evaluating a model

Inputs are in `test_public.jsonl` / `dev_public.jsonl` (`id`, `task_family`, `claim`, `evidence_spans`). Answer labels are in `test_gold_labels.jsonl` / `dev_gold_labels.jsonl` (`public_id`, `task_family`, `label`). The evaluation harness prompts the model with the claim + code and scores against the labels:

```bash
# open model
python baseline_eval.py \
  --public test_public.jsonl \
  --gold   test_gold_labels.jsonl \
  --model  hf:Qwen/Qwen2.5-7B-Instruct

# frontier model (needs an API key)
python baseline_eval.py \
  --public test_public.jsonl \
  --gold   test_gold_labels.jsonl \
  --model  anthropic:claude-opus-4-8
```

It reports per-class P/R/F1, macro-F1, the headline **insufficient-F1**, a confusion matrix, and a per-family breakdown. The two notebooks reproduce the open-model sweep and the frontier datapoint end-to-end.

**Report `insufficient-F1` (and macro-F1), not accuracy** — accuracy is dominated by the supported-heavy class balance and, as shown above, misranks models.

## Repository contents

| file | what it is |
|---|---|
| `test_public.jsonl`, `dev_public.jsonl` | benchmark inputs (no labels) |
| `test_gold_labels.jsonl`, `dev_gold_labels.jsonl` | answer labels (`label` only; provenance withheld) |
| `rejects_audit.jsonl` | 84 excluded out-of-scope items (transparency) |
| `export_manifest.json` | provenance: input SHA256, seed, split/label counts |
| `baseline_eval.py` | evaluation harness |
| `repoveritas_baseline_sweep.ipynb`, `repoveritas_frontier_eval.ipynb` | reproducibility notebooks |
| `kappa_slice.py`, `rater_label.py`, `RepoVeritas_rater_packet.md` | reliability + annotation methodology |
| `RepoVeritas_dataset_card.md` | full dataset card |
| `RepoVeritas_results.md` | full results write-up |

To keep the benchmark sound, item provenance (rationale, mutation metadata, and the public-ID→source map) is intentionally withheld; only the answer label is released.

## Limitations

Python-only; supported-heavy class balance (64/21/14, disclosed); the contradicted class is mostly mutation-constructed (disclosed); single primary annotator with independent inter-rater validation. See the dataset card for the complete list.

## Related work

RepoVeritas relates to recent work on sufficiency verification in LLM grounding (e.g. Chlon et al., arXiv:2509.11208).

## Citation

```bibtex
@misc{repoveritas2026,
  title  = {RepoVeritas: A Three-Way Code-Grounding Benchmark with an Abstention Class},
  author = {Hadi Chamas},
  year   = {2026},
  url    = {https://github.com/Hc1012/repoveritas}
}
```

## License

*Choose a license before publishing — e.g. CC BY 4.0 for the data and MIT for the code. Add a `LICENSE` file (GitHub can generate one for you).*
