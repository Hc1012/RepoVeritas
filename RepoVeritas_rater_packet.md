# RepoVeritas — Second Rater Packet

Thanks for doing this. It takes about **45 minutes**: you'll label 60 short items. Read this once (~5 min), then label straight through.

**Label independently.** Don't discuss any item with anyone until you're done, don't look things up, don't run the code. Your labels are compared against the primary annotator's to measure agreement — the entire value is in *your own* application of these rules.

## What you're doing

Each item is a **claim** (one sentence) plus **visible code** — either a function body or a commit diff. You assign exactly **one label**: does the visible code *support* the claim, *contradict* it, or is it *insufficient* to tell?

## The one rule that overrides everything

**Judge ONLY what is in the visible code.** Not what you know the library probably does elsewhere, not what the function is "obviously" meant to do. A claim can be perfectly true in the real world and still be **insufficient** *here*, because these particular lines don't show it.

## The three labels

- **supported** — the visible code positively shows the claim is **true**; you can point to the line(s) that establish it.
- **contradicted** — the visible code gives positive reason the claim is **false** — it does the opposite, or something incompatible (same operation, opposite specific behaviour).
- **insufficient** — the claim is on-topic for this code, but you **cannot decide** it from what's shown; you'd need more. **Test: you must be able to name what's missing** (an unseen helper, the surrounding code, or a benchmark/measurement). If you can't say what would settle it, it isn't insufficient.

## The rules that decide most items

**1 — Outcome claims need the outcome shown, not just a plausible mechanism.** If the claim asserts a *result* — *faster, optimized, more efficient, reduces memory, fixes flakiness, improves throughput* — it is **supported only if the code establishes that result** (a clear complexity reduction like O(n²)→O(n), or removal of visibly dominant work). A change that merely *aims at* the result → **insufficient** (missing evidence = a benchmark, or proof it's a hot path).
- *"Optimize by caching parsed config" wrapped around a dict lookup → insufficient* (the cached thing isn't expensive).
- *"Removed redundant DB query inside the loop" + diff deletes a per-iteration query → supported* (dominant work visibly removed).

**2 — Evaluative words must be earned.** If the claim contains *unnecessary, redundant, cleaner, properly, correctly, safer, better* and the code does not visibly establish that judgement, the item is **insufficient** — even if the underlying action is shown.
- *"Remove unnecessary check X" + diff removes the check → insufficient* (the removal is shown; "unnecessary" is not).

**3 — Insufficient must name what's missing.** If the deciding logic lives in a helper or call you can't see, it's **insufficient**, no matter what the names suggest.
- *"Returns records sorted by date" + `return self._sorted(rows)` where `_sorted` isn't shown → insufficient* (missing = the helper's definition).
- A *missing* expected mechanism is not disproof: no visible lock doesn't mean a race isn't fixed → that's **insufficient**, not contradicted.

**4 — Contradiction = same operation, opposite specific behaviour.** A claim naming a specific behaviour that the code clearly does the opposite of is a real contradiction.
- *"Sorts ascending" + `sorted(xs, reverse=True)` (full body shown) → contradicted.*
- *"Raises ValueError on empty input" + body raises IndexError → contradicted.*
- **But:** if the body is cut off so the deciding logic *could* be in an unseen part → **insufficient**, not contradicted.

**5 — Multi-part claims: the worst part wins**, in this order: **contradicted > insufficient > supported.**
- *"Returns scores sorted ascending, then cached" + body sorts descending → contradicted* (the false part sinks it; the rest is moot).

**6 — Don't nitpick wording** unless the claim hinges on it.
- *"Set a property by name" + `self.values[name] = value` → supported* (don't litigate "property" vs a generic dict).

## Three worked examples

- **supported** — claim *"Returns the input list with duplicates removed"* + body `return list(set(items))`. The code does exactly that. → **supported**
- **insufficient** — claim *"Speeds up lookup by caching results"* + diff wraps an in-memory dict access in a cache. Caching a cheap operation; the net speedup is unproven. → **insufficient** (missing = evidence the operation is expensive, or a benchmark).
- **contradicted** — claim *"Disables logging by default"* + body sets `logging_enabled = True`. Opposite of the claim. → **contradicted**

## How to label

Run:
```
python rater_label.py --sheet slice_blind.jsonl --out yourname_labels.jsonl
```
It shows each item one at a time. Type **s** (supported), **c** (contradicted), or **i** (insufficient) and press Enter. Type **q** to save and stop — you can resume later by re-running the same command. That's all you enter; just the label.

## If a rule feels ambiguous

Apply your best reading and move on. Don't ask and don't look anything up — your independent judgement on the hard cases is exactly what's being measured. *(If you want the complete rules behind this summary, they're in `RepoVeritas_labeling_guide.md`, but this packet is sufficient.)*
