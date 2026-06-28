# RepoVeritas v1 — Baseline Results

## Evaluation protocol

Every model performs the same three-way classification: given a natural-language **claim** and the **visible code evidence**, decide whether the evidence *supports* the claim, *contradicts* it, or is *insufficient* to decide. Evaluation is on the held-out **test split (207 items)**; the **dev split (87 items)** is reserved for prompt and few-shot tuning and is never scored here.

We report per-class precision/recall/F1, macro-F1, and the headline **insufficient-F1** (the abstention class). Accuracy is reported for completeness but is explicitly de-emphasized; the first result below is the reason why. All models are run **zero-shot with one identical prompt** that defines the three labels and asks for brief reasoning followed by a parsed `Label:` line. Outputs that never emit a parseable label are counted as errors — a model that cannot follow the output format has failed the task, and hiding that behind a fallback would flatter it.

We evaluate the **Qwen2.5-Instruct** family at 0.5B, 1.5B, 3B, and 7B parameters (7B in 4-bit nf4 quantization), against two non-learned floors — **majority** (always predict the majority class, *supported*) and **uniform random** — and, as a frontier ceiling, **Claude Opus 4.8** run through the identical harness and prompt so the comparison is exact.

## Headline results (test split, n = 207)

| model | accuracy | macro-F1 | supported-F1 | contradicted-F1 | **insufficient-F1** | unparseable |
|---|---|---|---|---|---|---|
| *majority floor* | 0.643 | 0.261 | 0.782 | 0.000 | **0.000** | 0 |
| *random floor* | 0.357 | 0.316 | 0.490 | 0.270 | **0.188** | 0 |
| Qwen2.5-0.5B | 0.638 | 0.260 | 0.781 | 0.000 | **0.000** | 2 |
| Qwen2.5-1.5B | 0.609 | 0.337 | 0.762 | 0.128 | **0.120** | 2 |
| Qwen2.5-3B | 0.415 | 0.386 | 0.528 | 0.229 | **0.400** | 31 |
| Qwen2.5-7B | 0.647 | 0.523 | 0.783 | 0.348 | **0.438** | 0 |
| **Claude Opus 4.8** *(frontier)* | **0.860** | **0.799** | 0.923 | 0.817 | **0.657** | 0 |

Two figures accompany this section: **Figure 1** (`repoveritas_insufficient_f1_vs_scale.png`) plots insufficient-, macro-, and supported-F1 against model size across the Qwen2.5 sweep with the random floor drawn in; **Figure 2** (`repoveritas_confusion.png`) shows the four per-model Qwen confusion matrices. The Claude Opus 4.8 datapoint is reported in the table above and analyzed in Finding 3; it post-dates the figures and is not yet plotted on them (regenerating Figure 1 with the frontier point appended is a trivial follow-up).

## Finding 1 — Accuracy hides the abstention failure, and these models prove it directly

The clearest result in the table is what accuracy *fails* to show. Qwen2.5-0.5B and Qwen2.5-7B post nearly identical accuracy — **0.638 versus 0.647** — yet their macro-F1 differs by a factor of two (0.260 versus 0.523) and their insufficient-F1 by everything-versus-nothing (0.000 versus 0.438). By accuracy the two models look interchangeable; by any metric that credits the hard classes they are not remotely comparable.

The 0.5B model is, statistically, the **majority-class baseline wearing an LLM's clothes**: its macro-F1 (0.260) is indistinguishable from the majority floor (0.261) and its insufficient-F1 is exactly the floor (0.000). Figure 2 shows why — it routes 205 of 207 items into *supported* and never once predicts *insufficient* or *contradicted*. It scores 64% by exploiting the fact that the test set is 64% supported, not by judging evidence.

The misranking is sharper still when the whole sweep is considered. **Accuracy is non-monotonic in scale** (0.638 → 0.609 → 0.415 → 0.647) while macro-F1 (0.260 → 0.337 → 0.386 → 0.523) and insufficient-F1 (0.000 → 0.120 → 0.400 → 0.438) both rise monotonically. Ranked by accuracy, the 0.5B model (0.638) would sit *above* the 3B model (0.415); ranked by any grounding metric, the 3B is far the stronger of the two. Accuracy does not merely miss the abstention signal — on this benchmark it inverts the true competence order. This is the empirical case for centering evaluation on insufficient-F1 and macro-F1.

This trap is specifically a **small- and mid-model phenomenon**. At the frontier it closes: Claude Opus 4.8 posts both high accuracy (0.860) *and* high macro-F1 (0.799), so for that model accuracy is an honest summary. The lesson is not that accuracy is always wrong — it is that accuracy is *unreliable precisely in the regime where models cope with class imbalance by collapsing onto the majority class*, and it cannot be trusted to rank models that differ in how they handle the hard classes. Crucially, the abstention gap that accuracy hides at small scale does not disappear at the frontier (Finding 3); it merely stops contaminating the accuracy number.

## Finding 2 — Abstention skill scales; confirmation skill is already high, and the gap never closes

Across the Qwen sweep, **supported-F1 sits at roughly 0.78 regardless of size** — the smallest model already confirms true claims about as well as the 7B — rising only modestly, to 0.923, at the frontier. **Insufficient-F1 behaves completely differently**: it starts at the floor (0.000 at 0.5B) and climbs steeply with capability — 0.000 → 0.120 → 0.400 → 0.438 across Qwen, then 0.657 at Opus. Two facts matter. First, abstention is the capability that *moves* with scale while confirmation is largely flat — a benchmark whose headline metric tracks model strength while a control metric is near-saturated is measuring a real, separable axis rather than noise, which is exactly what the *insufficient* class was designed to isolate. Second, and decisively, **insufficient-F1 stays well below supported-F1 at every scale, including the frontier** (0.657 vs 0.923 at Opus). The gap narrows but never closes; recognizing insufficient evidence is harder than confirming claims for every model tested.

## Finding 3 — The abstention gap is task-intrinsic, not a small-model artifact

The most important single result is what the frontier does *not* fix. Claude Opus 4.8 — the strongest model available — still leaves a **27-point gap** between confirmation and abstention: supported-F1 0.923 versus insufficient-F1 0.657. This directly answers the obvious objection to the Qwen sweep ("maybe a capable model just solves this"): it does not. A frontier model exhibits the same deficit the small models do, so the gap is a property of **the task**, not of model size.

The *shape* of Opus's errors is cleaner than the small models' and locates the difficulty precisely. Its confusion matrix shows the gap is now **one-sided**: of 133 supported items it misclassifies only 3 as insufficient — over-abstention is essentially gone — but of 44 *insufficient* items it commits 21 to a definite verdict anyway (**13 called supported, 8 called contradicted**), recovering only 23. Its insufficient **recall is 0.523**: faced with evidence that does not actually settle the claim, the best available model declares a verdict more than half the time. When it does abstain it is well-calibrated (precision 0.885) — so the failure is not false abstention, it is **under-detection of insufficiency**: over-claiming, not over-caution.

That contrast with the 7B is the frontier's signature. The 7B was noisy in *both* directions (18 insufficient→supported *and* 25 supported→insufficient — an unstable approximation of "enough evidence"). Scaling to Opus cleans up the over-abstention almost entirely but leaves the over-claiming largely intact. Capability buys calibration on the easy side of the boundary and barely moves the hard side: **knowing when you cannot tell remains the unsolved part.**

For the scale dynamics below the frontier: the 0.5B model is a constant *supported* predictor; the 3B over-corrects, discovering the *insufficient* label and over-applying it (111 insufficient predictions, only 31 correct — recall 0.70, precision 0.28) at the cost of 57 supported items; only the 7B begins to balance the two, and Opus then tips decisively back toward issuing verdicts. Notably, **learning to engage with the hard class initially costs accuracy** — the 3B's accuracy collapse to 0.415 is the price of attempting abstention before it can do so precisely.

## Finding 4 — At the frontier, two of three classes are nearly solved; abstention is the lone holdout

Reading Opus's per-class scores together reframes the contribution. Opus reaches **supported-F1 0.923** and **contradicted-F1 0.817** (catching 29 of 30 contradictions, recall 0.967) — both classes are largely handled. **Insufficient-F1 lags at 0.657**, and it is the only class where recall is poor (0.523). The benchmark's three labels are therefore *not* uniformly difficult: confirming true claims and detecting outright contradictions are increasingly solved as models improve, while recognizing insufficient evidence is the capability that stays stubborn at the ceiling. RepoVeritas's value concentrates in exactly the class that does not fall to scale — the abstention judgment its design was built around.

## Finding 5 — Per-family: docstring-insufficient scales, commit-insufficient barely moves — even at the frontier

Splitting insufficient-F1 by task family tracks a structural property of the data:

| model | docstring insufficient-F1 | commit insufficient-F1 |
|---|---|---|
| Qwen2.5-0.5B | 0.000 | 0.000 |
| Qwen2.5-1.5B | 0.176 | 0.000 |
| Qwen2.5-3B | 0.535 | 0.232 |
| Qwen2.5-7B | 0.556 | 0.182 |
| **Claude Opus 4.8** | **0.760** | **0.400** |

Docstring-insufficient is where scale pays off; commit-insufficient stays near zero until 3B and never climbs to match it. The split **persists at the frontier**: even Opus scores 0.760 on docstring-insufficient but only 0.400 on commit-insufficient. This is consistent with the dataset-construction finding that **commit diffs structurally reveal their own change** — a diff almost always shows what it did, so genuinely-insufficient commit examples are both rarer in the wild and harder for any model to recognize as insufficient. The result validates the deliberate decision to lock the commit-insufficient cell lean (23 items) rather than pad it: the difficulty is intrinsic to the modality, not an artifact of small sample, and it does not wash out with capability.

## The contradicted class

Contradicted-F1 scales steeply (0.000 → 0.128 → 0.229 → 0.348 across Qwen) and is then **largely solved at the frontier** — Opus reaches 0.817 with recall 0.967, catching 29 of 30 contradictions (commit-contradicted F1 of 0.944). The small-model difficulty is instructive: the 7B catches only 8 of 30, and **13 of the ones it misses it labels *insufficient*** — it senses something is wrong but will not commit to declaring it false. That hesitation vanishes with capability. The contrast with the insufficient class is the whole point: contradiction-detection is a capability that scale delivers; insufficiency-detection is not (Finding 4).

(One caveat on this class: 36 of the 42 contradicted items are mutation-constructed same-operation opposites, so high contradicted scores partly reflect models detecting an introduced inconsistency. This is disclosed in the dataset card; it does not affect the insufficient findings, which use real, unmutated items.)

## Limitations of this evaluation

These numbers span floor baselines, a small-model sweep, and one frontier model, and three caveats bound them.

First, the **3B point is unstable**. Its 31 unparseable outputs (15% of the test set) and its accuracy collapse mean its insufficient-F1 of 0.400 is propped up by recall rather than precision, and is partly an artifact of the 200-token generation cap truncating its longer reasoning before the `Label:` line. The monotone scaling story rests on the clean 0.5B / 1.5B / 7B spine; the 3B is a noisy waypoint and would benefit from a rerun with a larger token budget before it appears in any final figure.

Second, this is **zero-shot with a single fixed prompt** — no few-shot tuning (the dev split exists for exactly this), no chain-of-thought-versus-direct ablation, no self-consistency. Each of these would likely lift the numbers; none would plausibly close the 27-point frontier gap.

Third, the frontier is represented by a **single model** (Claude Opus 4.8, 0 unparseable). One ceiling point is enough to establish that the gap is task-intrinsic rather than scale-limited, but a second frontier model (e.g. a GPT-class system) would test whether the *specific* error profile — clean on over-abstention, weak on under-detection of insufficiency — generalizes across model families or is Opus-specific.

## Takeaway

On a human-verified, evidence-grounded benchmark, models are substantially worse at recognizing *insufficient* evidence than at confirming claims — and this holds from a 0.5B open model all the way to Claude Opus 4.8. The deficit is **task-intrinsic**: scaling to the frontier nearly solves the supported and contradicted classes (Opus: 0.923 and 0.817) yet leaves insufficient lagging (0.657, recall 0.523), with the residual error being over-claiming rather than over-caution. At small scale the deficit is also **invisible to accuracy**, which collapses onto the majority class and inverts the true ranking of models; at the frontier accuracy becomes honest, but the gap remains underneath it. Recognizing when code evidence does not settle a claim is the capability RepoVeritas isolates — and it is the one that does not fall to scale.
