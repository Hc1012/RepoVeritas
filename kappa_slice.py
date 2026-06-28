#!/usr/bin/env python3
"""
kappa_slice.py -- RepoVeritas Phase-3 reliability (production Cohen's kappa).

Produces the citable inter-rater (or intra-rater) kappa on a real-data slice. Three steps:

  1) sample  -- draw a stratified slice (even across family x label), write a BLIND sheet
                (id, task_family, claim, evidence_spans -- NO gold label) + a private answer key.
  2) label   -- a second rater (inter) or you-after-a-delay (intra) labels the blind sheet
                interactively; gold is never shown. Writes rater labels incrementally.
  3) score   -- Cohen's kappa between the rater's labels and the gold labels:
                overall, per-class (one-vs-rest), and the headline insufficient-vs-rest,
                with an agreement matrix and pass/fail vs the kill-test thresholds.

Why this exists: the kill-test kappa (=1.00 on a clean constructed set) shows the *instrument*
is sound. It is NOT the production number. The production kappa comes from this slice on real,
messy data and is the one the dataset card cites.

Usage:
  python kappa_slice.py sample --gold release_v1/test_gold.jsonl --per-cell 10 --out-sheet slice_blind.jsonl --out-key slice_key.jsonl
  python kappa_slice.py label  --sheet slice_blind.jsonl --out rater2_labels.jsonl
  python kappa_slice.py score  --rater rater2_labels.jsonl --gold release_v1/test_gold.jsonl --mode inter
"""
import json, argparse, random, os, sys, hashlib
from collections import Counter, defaultdict

LABELS = ["supported", "contradicted", "insufficient"]
SHORT = {"s": "supported", "c": "contradicted", "i": "insufficient"}

# kill-test thresholds, by protocol
THRESH = {
    "intra": {"overall": 0.70, "insuf": 0.50},
    "inter": {"overall": 0.60, "insuf": 0.50},
}


def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


# ---------------- 1) SAMPLE ----------------
def _ehash(r):
    return hashlib.md5(("\n\n".join(r["evidence_spans"])).encode()).hexdigest()


def cmd_sample(a):
    gold = load_jsonl(a.gold)
    # bucket by (family, label) using the PRIVATE gold label
    cells = defaultdict(list)
    for r in gold:
        cells[(r["task_family"], r["label"])].append(r)
    rng = random.Random(a.seed)
    # Fill the constrained classes first (contradicted, then insufficient, then
    # supported). This matters because contradicted items are mutations that share
    # evidence with a supported source item; sampling contradicted first reserves
    # that evidence so its supported twin is then skipped -> no duplicate evidence
    # (no anchoring) inside the reliability slice.
    order = {"contradicted": 0, "insufficient": 1, "supported": 2}
    cell_keys = sorted(cells, key=lambda k: (order.get(k[1], 9), k[0]))
    used_ev = set()
    sheet, key = [], []
    print(f"cell fill (per-cell = {a.per_cell}, dedup by evidence):")
    for (fam, lab) in cell_keys:
        rows = cells[(fam, lab)][:]
        rng.shuffle(rows)
        taken = 0
        for r in rows:
            if taken >= a.per_cell:
                break
            h = _ehash(r)
            if h in used_ev:
                continue  # evidence already represented in the slice -> skip
            used_ev.add(h)
            pid = r.get("public_id", r.get("id"))
            sheet.append({"id": pid, "task_family": r["task_family"],
                          "claim": r["claim"], "evidence_spans": r["evidence_spans"]})
            # key uses `label` (not `gold`) so it is a drop-in for `score --gold`
            key.append({"id": pid, "label": r["label"], "task_family": r["task_family"]})
            taken += 1
        flag = "" if taken == a.per_cell else f"   ! only {taken} after dedup"
        print(f"    {fam:18} {lab:12} {taken}{flag}")
    rng.shuffle(sheet)  # present in random order, not grouped by cell
    with open(a.out_sheet, "w") as f:
        for r in sheet:
            f.write(json.dumps(r) + "\n")
    with open(a.out_key, "w") as f:
        for r in key:
            f.write(json.dumps(r) + "\n")
    print(f"\nwrote {len(sheet)} items -> {a.out_sheet} (blind sheet) + {a.out_key} (private key)")
    print(f"distinct evidence in slice: {len(used_ev)}  (equal to item count = no duplicate evidence)")
    print("Give the blind sheet to the rater; keep the key private. Do NOT show the key to the rater.")


# ---------------- 2) LABEL ----------------
def cmd_label(a):
    sheet = load_jsonl(a.sheet)
    done = {}
    if os.path.exists(a.out):                       # resume support
        for r in load_jsonl(a.out):
            done[r["id"]] = r["label"]
        print(f"resuming: {len(done)} already labeled")
    todo = [r for r in sheet if r["id"] not in done]
    print(f"{len(todo)} items to label. Enter s=supported, c=contradicted, i=insufficient, q=quit&save.\n")
    fout = open(a.out, "a")
    for n, it in enumerate(todo, 1):
        print("\n" + "=" * 70)
        print(f"item {n}/{len(todo)}   [{it['task_family']}]")
        print("-" * 70)
        print("CLAIM:\n  " + it["claim"])
        print("\nVISIBLE CODE:")
        for span in it["evidence_spans"]:
            print("  " + span.replace("\n", "\n  "))
        print("-" * 70)
        while True:
            ans = input("label (s/c/i, q=quit): ").strip().lower()
            if ans == "q":
                fout.close(); print(f"\nsaved {len(done)} labels -> {a.out}"); return
            if ans in SHORT:
                lab = SHORT[ans]
                fout.write(json.dumps({"id": it["id"], "label": lab}) + "\n"); fout.flush()
                done[it["id"]] = lab
                break
            print("  enter s, c, i, or q")
    fout.close()
    print(f"\ndone -- {len(done)} labels -> {a.out}")


# ---------------- 3) SCORE ----------------
def cohen_kappa(a_lab, b_lab, classes):
    n = len(a_lab)
    if n == 0:
        return 0.0, 0.0, 0.0
    po = sum(1 for x, y in zip(a_lab, b_lab) if x == y) / n
    ca, cb = Counter(a_lab), Counter(b_lab)
    pe = sum((ca.get(c, 0) / n) * (cb.get(c, 0) / n) for c in classes)
    k = (po - pe) / (1 - pe) if (1 - pe) > 1e-12 else 1.0
    return k, po, pe


def cmd_score(a):
    rater = {r["id"]: r["label"] for r in load_jsonl(a.rater)}
    gold_rows = load_jsonl(a.gold)
    gold = {r.get("public_id", r.get("id")): r.get("label", r.get("gold")) for r in gold_rows}
    fam = {r.get("public_id", r.get("id")): r["task_family"] for r in gold_rows}
    ids = [i for i in rater if i in gold]
    miss = [i for i in rater if i not in gold]
    if miss:
        print(f"! {len(miss)} rater ids not found in gold (ignored)")
    g = [gold[i] for i in ids]
    r = [rater[i] for i in ids]
    n = len(ids)
    th = THRESH[a.mode]
    print(f"\n=== RepoVeritas reliability ({a.mode}-rater) ===")
    print(f"paired items: {n}")
    for lab in LABELS:
        print(f"  gold {lab:12} {sum(1 for x in g if x==lab):>3} | rater {sum(1 for x in r if x==lab):>3}")

    ok, po, pe = cohen_kappa(g, r, LABELS)
    flag = "PASS" if ok >= th["overall"] else "FAIL"
    print(f"\noverall Cohen's kappa: {ok:.3f}   (po={po:.3f}, pe={pe:.3f})   threshold {th['overall']:.2f} -> {flag}")

    print("\nper-class (one-vs-rest) kappa:")
    for lab in LABELS:
        gb = [lab if x == lab else "rest" for x in g]
        rb = [lab if x == lab else "rest" for x in r]
        k, _, _ = cohen_kappa(gb, rb, [lab, "rest"])
        print(f"  {lab:12} {k:.3f}")

    gi = ["insufficient" if x == "insufficient" else "rest" for x in g]
    ri = ["insufficient" if x == "insufficient" else "rest" for x in r]
    ki, _, _ = cohen_kappa(gi, ri, ["insufficient", "rest"])
    flag_i = "PASS" if ki >= th["insuf"] else "FAIL"
    print(f"\n>>> HEADLINE insufficient-vs-rest kappa: {ki:.3f}   threshold {th['insuf']:.2f} -> {flag_i} <<<")

    print("\nagreement matrix (rows=gold, cols=rater):")
    cm = defaultdict(int)
    for x, y in zip(g, r):
        cm[(x, y)] += 1
    print(f"  {'':13}" + "".join(f"{c[:4]:>6}" for c in LABELS))
    for x in LABELS:
        print(f"  {x:13}" + "".join(f"{cm[(x, c)]:>6}" for c in LABELS))

    disagreements = [(i, gold[i], rater[i], fam[i]) for i in ids if gold[i] != rater[i]]
    print(f"\n{len(disagreements)} disagreements (raw agreement {1 - len(disagreements)/n:.3f}):")
    for i, gl, rl, fm in disagreements[:25]:
        print(f"  {i}  gold={gl:12} rater={rl:12} [{fm}]")

    if a.out:
        json.dump({"mode": a.mode, "n": n, "overall_kappa": ok,
                   "insufficient_vs_rest_kappa": ki,
                   "per_class_kappa": {lab: cohen_kappa(
                       [lab if x == lab else "rest" for x in g],
                       [lab if x == lab else "rest" for x in r], [lab, "rest"])[0]
                       for lab in LABELS},
                   "raw_agreement": 1 - len(disagreements) / n,
                   "thresholds": th}, open(a.out, "w"), indent=2)
        print(f"\nsaved -> {a.out}")


def main():
    ap = argparse.ArgumentParser(description="RepoVeritas Phase-3 reliability kappa")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sample", help="draw a stratified blind slice + private key")
    s.add_argument("--gold", required=True, help="gold jsonl to sample from (e.g. test_gold.jsonl)")
    s.add_argument("--per-cell", type=int, default=10, help="items per (family,label) cell")
    s.add_argument("--seed", type=int, default=13)
    s.add_argument("--out-sheet", default="slice_blind.jsonl")
    s.add_argument("--out-key", default="slice_key.jsonl")
    s.set_defaults(fn=cmd_sample)

    l = sub.add_parser("label", help="interactively label the blind sheet (gold never shown)")
    l.add_argument("--sheet", required=True)
    l.add_argument("--out", required=True, help="rater labels jsonl (appended; resumable)")
    l.set_defaults(fn=cmd_label)

    c = sub.add_parser("score", help="Cohen's kappa: rater labels vs gold")
    c.add_argument("--rater", required=True, help="rater labels jsonl from `label`")
    c.add_argument("--gold", required=True, help="gold jsonl (or the private key from `sample`)")
    c.add_argument("--mode", choices=["intra", "inter"], default="inter")
    c.add_argument("--out", default=None)
    c.set_defaults(fn=cmd_score)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
