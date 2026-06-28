#!/usr/bin/env python3
"""
rater_label.py -- blind labeling for the RepoVeritas reliability slice.

This is the ONLY script a second rater runs. It shows each item (claim + visible
code) and you type one of s / c / i. It contains no gold labels, no answer key,
and no scoring logic -- there is nothing here that reveals the "correct" answer.

Usage:
    python rater_label.py --sheet slice_blind.jsonl --out yourname_labels.jsonl

Controls: s = supported, c = contradicted, i = insufficient, q = save & quit.
Quitting is safe -- re-run the same command to resume where you left off.
"""
import json, argparse, os

SHORT = {"s": "supported", "c": "contradicted", "i": "insufficient"}


def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True, help="the blind slice (slice_blind.jsonl)")
    ap.add_argument("--out", required=True, help="your labels output (appended; resumable)")
    a = ap.parse_args()

    sheet = load_jsonl(a.sheet)
    done = {}
    if os.path.exists(a.out):
        for r in load_jsonl(a.out):
            done[r["id"]] = r["label"]
        print(f"resuming: {len(done)} already labeled")
    todo = [r for r in sheet if r["id"] not in done]
    print(f"{len(todo)} items to label.   s=supported  c=contradicted  i=insufficient  q=quit&save\n")

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
                fout.close()
                print(f"\nsaved {len(done)} labels -> {a.out}  (re-run to resume)")
                return
            if ans in SHORT:
                lab = SHORT[ans]
                fout.write(json.dumps({"id": it["id"], "label": lab}) + "\n")
                fout.flush()
                done[it["id"]] = lab
                break
            print("  please enter s, c, i, or q")
    fout.close()
    print(f"\ndone -- {len(done)} labels written to {a.out}")
    print("Send that file back to whoever gave you this task.")


if __name__ == "__main__":
    main()
