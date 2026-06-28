#!/usr/bin/env python3
"""
baseline_eval.py -- RepoVeritas v1 baseline evaluation.

Runs a 3-way classifier (supported|contradicted|insufficient) over a *_public.jsonl split,
scores against the matching *_gold.jsonl, and reports the metrics that matter for this benchmark:
per-class P/R/F1, macro-F1, ACCURACY, the HEADLINE insufficient-F1 (the abstention class), a
confusion matrix (to show *where* models fail -- typically insufficient->supported), and a
docstring-vs-commit breakdown.

Model-agnostic: you supply a `model_fn(prompt:str) -> str` that returns raw model text. Built-in:
  majority  -- always "supported" (the majority class) -> the accuracy floor
  random    -- uniform 3-way (seeded)                  -> the chance floor
Adapters for real models (fill in your key / model id) are at the bottom: Anthropic, OpenAI, HF-local.

Usage:
  python baseline_eval.py --public release_v1/test_public.jsonl --gold release_v1/test_gold.jsonl --model majority
  python baseline_eval.py ... --model anthropic:claude-3-5-sonnet-latest
  python baseline_eval.py ... --model hf:Qwen/Qwen2.5-7B-Instruct
  optional few-shot:  --fewshot 4 --dev release_v1/dev_gold.jsonl
"""
import json, re, argparse, random, os
from collections import defaultdict, Counter

LABELS = ["supported", "contradicted", "insufficient"]

PROMPT = """You are checking whether a CLAIM about code is supported by the VISIBLE CODE shown below.

CLAIM:
{claim}

VISIBLE CODE:
{evidence}

Choose exactly one label, based ONLY on the visible code:
- supported: the visible code positively establishes that the claim is TRUE.
- contradicted: the visible code positively establishes that the claim is FALSE (it does the opposite, or something incompatible with the claim).
- insufficient: the visible code is on-topic but does NOT contain enough to decide whether the claim is true or false (for example, the deciding behaviour lives in code that is not shown here).

Reason briefly, then end with a final line in exactly this format:
Label: <supported|contradicted|insufficient>"""


def load_public(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def load_gold(p):
    g = {}
    for l in open(p):
        if not l.strip():
            continue
        r = json.loads(l)
        g[r["public_id"]] = {"label": r["label"], "task_family": r["task_family"]}
    return g


def build_prompt(item, shots=()):
    ev = "\n\n".join(item["evidence_spans"])
    pre = ""
    for s in shots:
        se = "\n\n".join(s["evidence_spans"])
        pre += PROMPT.format(claim=s["claim"], evidence=se) + f"\nLabel: {s['label']}\n\n---\n\n"
    return pre + PROMPT.format(claim=item["claim"], evidence=ev)


def parse_label(text):
    if not text:
        return None
    m = re.search(r"label\s*[:=]\s*\*{0,2}\s*(supported|contradicted|insufficient)", text, re.I)
    if m:
        return m.group(1).lower()
    # fallback: last standalone label word in the output
    hits = re.findall(r"\b(supported|contradicted|insufficient)\b", text, re.I)
    return hits[-1].lower() if hits else None


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def score(rows):
    """rows: list of (gold, pred, family). pred may be None (unparseable)."""
    cm = defaultdict(int)
    for g, pr, _ in rows:
        cm[(g, pr if pr in LABELS else "??")] += 1
    per = {}
    for c in LABELS:
        tp = cm[(c, c)]
        fp = sum(cm[(g, c)] for g in LABELS if g != c)
        fn = sum(cm[(c, p)] for p in LABELS + ["??"] if p != c)
        per[c] = prf(tp, fp, fn)
    n = len(rows)
    correct = sum(cm[(c, c)] for c in LABELS)
    acc = correct / n if n else 0.0
    macro = sum(per[c][2] for c in LABELS) / 3
    return cm, per, acc, macro


def fam_f1(rows, label, fam):
    sub = [(g, p) for g, p, f in rows if f == fam]
    tp = sum(1 for g, p in sub if g == label and p == label)
    fp = sum(1 for g, p in sub if g != label and p == label)
    fn = sum(1 for g, p in sub if g == label and p != label)
    return prf(tp, fp, fn)[2]


def report(name, rows):
    cm, per, acc, macro = score(rows)
    n = len(rows)
    unp = sum(1 for _, p, _ in rows if p not in LABELS)
    print(f"\n================  MODEL: {name}  ================")
    print(f"items: {n}   parsed: {n - unp}   unparseable: {unp}   accuracy: {acc:.3f}")
    print(f"{'':14}{'precision':>10}{'recall':>9}{'f1':>8}{'support':>9}")
    sup_ct = Counter(g for g, _, _ in rows)
    for c in LABELS:
        p, r, f = per[c]
        print(f"  {c:12}{p:>10.3f}{r:>9.3f}{f:>8.3f}{sup_ct[c]:>9}")
    print(f"  macro-F1: {macro:.3f}")
    print(f"  >>> HEADLINE insufficient-F1: {per['insufficient'][2]:.3f} <<<")
    print(f"\nconfusion (rows=gold, cols=pred):")
    cols = LABELS + ["??"]
    print(f"  {'':13}" + "".join(f"{c[:4]:>6}" for c in cols))
    for g in LABELS:
        print(f"  {g:13}" + "".join(f"{cm[(g, c)]:>6}" for c in cols))
    print("per-family insufficient-F1:  " +
          "  ".join(f"{fam.split('_')[0]}={fam_f1(rows, 'insufficient', fam):.3f}" for fam in
                    ("docstring_function", "commit_diff")))
    print("per-family contradicted-F1:  " +
          "  ".join(f"{fam.split('_')[0]}={fam_f1(rows, 'contradicted', fam):.3f}" for fam in
                    ("docstring_function", "commit_diff")))
    return {"model": name, "n": n, "accuracy": acc, "macro_f1": macro,
            "per_class": {c: dict(zip(("p", "r", "f1"), per[c])) for c in LABELS},
            "insufficient_f1": per["insufficient"][2], "unparseable": unp}


# ---------------- model functions ----------------
def make_model_fn(spec, seed=0):
    if spec == "majority":
        return lambda prompt: "Label: supported"
    if spec == "random":
        rng = random.Random(seed)
        return lambda prompt: f"Label: {rng.choice(LABELS)}"
    if spec.startswith("anthropic:"):
        import anthropic
        client = anthropic.Anthropic()  # needs ANTHROPIC_API_KEY
        model = spec.split(":", 1)[1]
        def fn(prompt):
            m = client.messages.create(model=model, max_tokens=512,
                                       messages=[{"role": "user", "content": prompt}])
            return "".join(b.text for b in m.content if getattr(b, "type", "") == "text")
        return fn
    if spec.startswith("openai:"):
        from openai import OpenAI
        client = OpenAI()  # needs OPENAI_API_KEY
        model = spec.split(":", 1)[1]
        def fn(prompt):
            r = client.chat.completions.create(model=model, max_tokens=512,
                                               messages=[{"role": "user", "content": prompt}])
            return r.choices[0].message.content
        return fn
    if spec.startswith("hf:"):
        from transformers import pipeline
        pipe = pipeline("text-generation", model=spec.split(":", 1)[1],
                        device_map="auto", max_new_tokens=512)
        def fn(prompt):
            out = pipe([{"role": "user", "content": prompt}])[0]["generated_text"]
            return out[-1]["content"] if isinstance(out, list) else str(out)
        return fn
    raise SystemExit(f"unknown --model {spec!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--public", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--model", required=True,
                    help="majority | random | anthropic:<id> | openai:<id> | hf:<path>")
    ap.add_argument("--fewshot", type=int, default=0)
    ap.add_argument("--dev", default=None, help="dev_gold.jsonl for few-shot examples")
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=0, help="evaluate only first N (smoke test)")
    a = ap.parse_args()

    pub = load_public(a.public)
    gold = load_gold(a.gold)
    if a.limit:
        pub = pub[:a.limit]
    shots = ()
    if a.fewshot and a.dev:
        dev = [json.loads(l) for l in open(a.dev) if l.strip()]
        rng = random.Random(0); rng.shuffle(dev)
        shots = dev[:a.fewshot]
    model_fn = make_model_fn(a.model)

    rows = []
    for i, item in enumerate(pub, 1):
        gl = gold[item["id"]]
        raw = model_fn(build_prompt(item, shots))
        rows.append((gl["label"], parse_label(raw), gl["task_family"]))
        if a.model in ("majority", "random") and False:
            pass
    res = report(a.model, rows)
    if a.out:
        json.dump(res, open(a.out, "w"), indent=2)
        print(f"\nsaved -> {a.out}")


if __name__ == "__main__":
    main()
