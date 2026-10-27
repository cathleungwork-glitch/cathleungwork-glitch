#!/usr/bin/env python3
"""Exact working for COMP7103 Assignment 1, Questions 1 and 3.

Question 2 is proved by hand; this script only checks the numeric
counter-examples used in that proof.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field


TERMS = ["borrow", "film", "good", "great", "know", "movie", "part", "think"]
REVIEWS = {
    1: [0, 0, 2, 2, 1, 5, 0, 2],
    2: [0, 5, 0, 1, 3, 4, 2, 1],
    3: [3, 0, 2, 0, 0, 10, 2, 2],
    4: [0, 3, 0, 0, 1, 4, 0, 0],
    5: [0, 1, 2, 2, 0, 4, 0, 0],
}


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def cosine(a, b):
    return dot(a, b) / (norm(a) * norm(b))


def q1():
    print("=" * 72)
    print("QUESTION 1(a)  cosine on term frequency")
    print("=" * 72)
    ids = sorted(REVIEWS)
    pairs = []
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            va, vb = REVIEWS[a], REVIEWS[b]
            d = dot(va, vb)
            na, nb = norm(va), norm(vb)
            c = d / (na * nb)
            pairs.append((c, a, b, d, na, nb))
            print(
                f"cos(R{a},R{b}) = {d} / (sqrt({dot(va, va)}) * sqrt({dot(vb, vb)}))"
                f" = {d} / ({na:.10f} * {nb:.10f}) = {c:.10f}"
            )
    pairs.sort(reverse=True)
    print("RANKING:")
    for c, a, b, d, na, nb in pairs:
        print(f"  R{a}-R{b}: {c:.10f}")
    print("MOST SIMILAR TF:", pairs[0][1], pairs[0][2], f"{pairs[0][0]:.10f}")

    print()
    print("=" * 72)
    print("QUESTION 1(b)  TF-IDF, idf = log2(|D|/|Dt|), |D|=5")
    print("=" * 72)
    df = []
    for t in range(len(TERMS)):
        df.append(sum(1 for v in REVIEWS.values() if v[t] > 0))
    idf = [math.log2(5 / d) for d in df]
    for t, term in enumerate(TERMS):
        print(f"  {term:8s} df={df[t]}  idf=log2(5/{df[t]})={idf[t]:.10f}")

    tfidf = {}
    for i, v in REVIEWS.items():
        tfidf[i] = [v[t] * idf[t] for t in range(len(TERMS))]
        pretty = ", ".join(f"{x:.6f}" for x in tfidf[i])
        print(f"R{i} tfidf: [{pretty}]")

    print()
    pairs = []
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            va, vb = tfidf[a], tfidf[b]
            d = dot(va, vb)
            na, nb = norm(va), norm(vb)
            c = d / (na * nb)
            pairs.append((c, a, b, d, na, nb))
            print(
                f"cos(R{a},R{b}) = {d:.10f} / ({na:.10f} * {nb:.10f}) = {c:.10f}"
            )
    pairs.sort(reverse=True)
    print("RANKING:")
    for c, a, b, *_ in pairs:
        print(f"  R{a}-R{b}: {c:.10f}")
    print("MOST SIMILAR TFIDF:", pairs[0][1], pairs[0][2], f"{pairs[0][0]:.10f}")


def lp(v, p):
    if p == 1:
        return sum(abs(x) for x in v)
    if p == 2:
        return math.sqrt(sum(x * x for x in v))
    if p == math.inf:
        return max(abs(x) for x in v)
    raise ValueError(p)


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def q2_checks():
    print()
    print("=" * 72)
    print("QUESTION 2 counter-example checks")
    print("=" * 72)

    def d1(p, q):
        return min(lp(sub(p[0], q[0]), 1), lp(sub(p[1], q[1]), 1))

    def d2(p, q):
        return lp(sub(p[0], q[0]), 2) + lp(sub(p[1], q[1]), math.inf)

    def d3(p, q):
        e = lp(sub(p[0], q[0]), 2)
        return e * e + lp(sub(p[1], q[1]), 1)

    def d4(p, q):
        return (
            lp(p[0], 2)
            - lp(q[0], 2)
            + lp(p[1], 2)
            - lp(q[1], 2)
        )

    p = ((0, 0, 0), (0, 0, 0))
    q = ((0, 0, 0), (10, 0, 0))
    print("d1 positivity", d1(p, q), "expected 0 with p!=q")

    a = ((0, 0, 0), (0, 0, 0))
    b = ((5, 0, 0), (0, 0, 0))
    c = ((5, 0, 0), (5, 0, 0))
    print("d1 triangle", d1(a, b), d1(b, c), d1(a, c), "expected 0,0,5")

    a = ((0, 0, 0), (0, 0, 0))
    b = ((1, 0, 0), (0, 0, 0))
    c = ((2, 0, 0), (0, 0, 0))
    print("d3 triangle", d3(a, b), d3(b, c), d3(a, c), "expected 1,1,4")

    p = ((0, 0, 0), (0, 0, 0))
    q = ((3, 4, 0), (0, 0, 0))
    print("d4", d4(p, q), d4(q, p), "expected -5, 5")

    # d4 triangle equality
    r = ((0, 5, 0), (0, 0, 0))
    print(
        "d4 triangle equality",
        d4(p, r),
        d4(p, q) + d4(q, r),
    )


# ---------------------------------------------------------------------------
# Question 3
# ---------------------------------------------------------------------------

CLASS_ORDER = ["HC", "Infected", "Asthma", "COPD"]

# record, age, smoking, class
RAW = [
    (1, 58, 1, "HC"),
    (2, 59, 3, "HC"),
    (3, 59, 3, "Infected"),
    (4, 60, 1, "Asthma"),
    (5, 60, 2, "HC"),
    (6, 60, 2, "COPD"),
    (7, 61, 1, "HC"),
    (8, 61, 2, "Asthma"),
    (9, 61, 2, "Asthma"),
    (10, 62, 1, "HC"),
    (11, 62, 1, "HC"),
    (12, 62, 1, "Infected"),
    (13, 63, 1, "COPD"),
    (14, 63, 2, "Infected"),
    (15, 63, 2, "Asthma"),
    (16, 63, 2, "Asthma"),
    (17, 63, 3, "HC"),
    (18, 63, 3, "COPD"),
]

TEST = [
    (19, 58, 1, "Infected"),
    (20, 58, 3, "Asthma"),
    (21, 60, 2, "COPD"),
    (22, 62, 3, "COPD"),
    (23, 63, 1, "Asthma"),
    (24, 63, 2, "HC"),
]


def entropy(labels):
    n = len(labels)
    if n == 0:
        return 0.0
    h = 0.0
    for v in Counter(labels).values():
        p = v / n
        h -= p * math.log2(p)
    return h


def fmt_counts(labels):
    c = Counter(labels)
    parts = [f"{k}:{c[k]}" for k in CLASS_ORDER if c[k]]
    return "{" + ", ".join(parts) + "}"


def majority(labels):
    c = Counter(labels)
    best = max(c.values())
    tied = [k for k in CLASS_ORDER if c[k] == best]
    return tied[0], tied, c


@dataclass
class Split:
    description: str
    attr: str
    mask: list[bool]
    gain: float
    h_left: float
    h_right: float
    n_left: int
    n_right: int


@dataclass
class TreeNode:
    records: list
    prediction: str
    tied: list
    reason: str
    split: Split | None = None
    left: "TreeNode | None" = None
    right: "TreeNode | None" = None
    node_id: str = ""
    candidates: list = field(default_factory=list)
    parent_h: float = 0.0


def candidate_splits(records):
    splits = []
    ages = sorted({r[1] for r in records})
    for i in range(len(ages) - 1):
        lo, hi = ages[i], ages[i + 1]
        thr = (lo + hi) / 2.0
        mask = [r[1] <= thr for r in records]
        if any(mask) and not all(mask):
            splits.append((f"Age ≤ {thr:.1f}  vs  Age > {thr:.1f}", "Age", mask))
    smoking_vals = sorted({r[2] for r in records})
    # all non-empty proper subsets, represented by the left-hand set, canonicalised
    # so the subset containing the smallest smoking value is... we want each
    # partition once. Generate subsets of size 1 up to len//2, and if len even
    # size len/2 only those whose min element is the smallest smoking value
    # to avoid double counting. Cleaner: all subsets that contain the smallest
    # value? NO that misses partitions where the smallest is on the other side
    # but that's the same partition.
    #
    # For 3 values, partitions are exactly the singleton vs the rest.
    # For fewer values present in a node, same idea: every non-empty proper
    # subset S with min(S) == min(all values) would DROP partitions whose
    # left side doesn't include the global min. The complement would be stored
    # when we flip. So take every subset that does NOT contain the smallest
    # value? Let's just do: for every non-empty proper subset whose frozenset
    # is lexicographically <= its complement.
    from itertools import combinations

    seen = set()
    for k in range(1, len(smoking_vals)):
        for comb in combinations(smoking_vals, k):
            left = frozenset(comb)
            right = frozenset(smoking_vals) - left
            if not right:
                continue
            key = tuple(sorted((tuple(sorted(left)), tuple(sorted(right)))))
            if key in seen:
                continue
            seen.add(key)
            # orient the description with the side that contains the smaller min first
            if min(left) < min(right):
                L, R = left, right
            else:
                L, R = right, left
            desc = (
                "Smoking ∈ {"
                + ",".join(str(x) for x in sorted(L))
                + "}  vs  Smoking ∈ {"
                + ",".join(str(x) for x in sorted(R))
                + "}"
            )
            mask = [r[2] in L for r in records]
            splits.append((desc, "Smoking", mask))
    return splits


def evaluate_split(records, desc, attr, mask) -> Split:
    labels = [r[3] for r in records]
    left = [lab for lab, m in zip(labels, mask) if m]
    right = [lab for lab, m in zip(labels, mask) if not m]
    h = entropy(labels)
    hl, hr = entropy(left), entropy(right)
    n = len(labels)
    gain = h - (len(left) / n) * hl - (len(right) / n) * hr
    return Split(desc, attr, mask, gain, hl, hr, len(left), len(right))


def build(records, node_id="root") -> TreeNode:
    labels = [r[3] for r in records]
    pred, tied, _ = majority(labels)
    h = entropy(labels)
    node = TreeNode(
        records=records,
        prediction=pred,
        tied=tied,
        reason="",
        node_id=node_id,
        parent_h=h,
    )
    if len(records) < 8:
        node.reason = f"stop: |D|={len(records)} < 8"
        return node
    if h == 0.0:
        node.reason = "stop: pure node (entropy 0, information gain would be 0 < 0.15)"
        return node
    cands = []
    for desc, attr, mask in candidate_splits(records):
        cands.append(evaluate_split(records, desc, attr, mask))
    cands.sort(key=lambda s: (-s.gain, s.attr, s.description))
    node.candidates = cands
    if not cands:
        node.reason = "stop: no valid binary split"
        return node
    best = cands[0]
    if best.gain < 0.15 - 1e-12:
        node.reason = f"stop: best information gain {best.gain:.6f} < 0.15"
        return node
    # exact tie warning
    ties = [c for c in cands if abs(c.gain - best.gain) < 1e-12]
    node.reason = f"split: IG={best.gain:.6f} ≥ 0.15"
    if len(ties) > 1:
        node.reason += f" (exact tie among {len(ties)} splits; take the first after sorting by attribute name then description)"
    node.split = best
    left_recs = [r for r, m in zip(records, best.mask) if m]
    right_recs = [r for r, m in zip(records, best.mask) if not m]
    node.left = build(left_recs, node_id + ".L")
    node.right = build(right_recs, node_id + ".R")
    return node


def print_node(node: TreeNode, indent=0):
    rec_ids = [r[0] for r in node.records]
    labels = [r[3] for r in node.records]
    pad = "  " * indent
    print(f"{pad}NODE {node.node_id} n={len(node.records)} records={rec_ids}")
    print(f"{pad}  classes {fmt_counts(labels)}  H={node.parent_h:.6f}")
    print(f"{pad}  majority={node.prediction} tied={node.tied}")
    print(f"{pad}  decision: {node.reason}")
    if node.candidates:
        print(f"{pad}  candidates:")
        for c in node.candidates:
            left_labels = [r[3] for r, m in zip(node.records, c.mask) if m]
            right_labels = [r[3] for r, m in zip(node.records, c.mask) if not m]
            print(
                f"{pad}    IG={c.gain:.6f}  L n={c.n_left} H={c.h_left:.6f} {fmt_counts(left_labels)}"
                f"  |  R n={c.n_right} H={c.h_right:.6f} {fmt_counts(right_labels)}"
                f"  :: {c.description}"
            )
    if node.left:
        print(f"{pad}  LEFT ({node.split.description.split('vs')[0].strip()})")
        print_node(node.left, indent + 2)
        print(f"{pad}  RIGHT ({node.split.description.split('vs')[1].strip()})")
        print_node(node.right, indent + 2)


def predict(node: TreeNode, age, smoking, path):
    if node.split is None:
        path.append(f"leaf {node.node_id} -> {node.prediction} ({node.reason})")
        return node.prediction
    # evaluate membership of the left branch from the description via the same mask rule
    desc = node.split.description
    if desc.startswith("Age"):
        # "Age ≤ 60.5  vs  Age > 60.5"
        thr = float(desc.split("≤")[1].split()[0])
        go_left = age <= thr
    else:
        left_part = desc.split("vs")[0]
        inside = left_part.split("{")[1].split("}")[0]
        vals = {int(x) for x in inside.split(",")}
        go_left = smoking in vals
    if go_left:
        path.append(f"{node.node_id}: LEFT {desc.split('vs')[0].strip()}")
        return predict(node.left, age, smoking, path)
    path.append(f"{node.node_id}: RIGHT {desc.split('vs')[1].strip()}")
    return predict(node.right, age, smoking, path)


def gain_ratio_smoking(records):
    labels = [r[3] for r in records]
    h = entropy(labels)
    groups = {}
    for r in records:
        groups.setdefault(r[2], []).append(r[3])
    n = len(records)
    remainder = 0.0
    split_info = 0.0
    print()
    print("=" * 72)
    print("QUESTION 3(b) GainRatio multi-way Smoking")
    print("=" * 72)
    print(f"parent n={n} {fmt_counts(labels)} H={h:.10f}")
    for s in sorted(groups):
        labs = groups[s]
        hs = entropy(labs)
        remainder += (len(labs) / n) * hs
        p = len(labs) / n
        split_info -= p * math.log2(p)
        print(
            f"  Smoking={s} n={len(labs)} {fmt_counts(labs)} H={hs:.10f} "
            f"weight={len(labs)}/{n}"
        )
    ig = h - remainder
    gr = ig / split_info
    print(f"remainder={remainder:.10f}")
    print(f"IG={ig:.10f}")
    print(f"SplitInfo={split_info:.10f}")
    print(f"GainRatio={gr:.10f}")
    return ig, split_info, gr


def confusion(tree):
    print()
    print("=" * 72)
    print("QUESTION 3(a)(ii) test evaluation")
    print("=" * 72)
    labels = CLASS_ORDER
    matrix = {a: {p: 0 for p in labels} for a in labels}
    correct = 0
    for rec, age, smoking, actual in TEST:
        path = []
        pred = predict(tree, age, smoking, path)
        matrix[actual][pred] += 1
        ok = pred == actual
        correct += int(ok)
        print(f"Record {rec}: Age={age}, Smoking={smoking}, actual={actual}, predicted={pred}")
        for step in path:
            print(f"    {step}")
    print("Confusion matrix rows=actual, cols=predicted")
    header = "actual\\pred".ljust(14) + "".join(p.ljust(12) for p in labels)
    print(header)
    for a in labels:
        row = a.ljust(14) + "".join(str(matrix[a][p]).ljust(12) for p in labels)
        print(row)
    print(f"accuracy={correct}/6={correct/6:.6f}")


def main():
    q1()
    q2_checks()
    print()
    print("=" * 72)
    print("QUESTION 3(a) decision tree")
    print("=" * 72)
    # sanity on overall counts
    labels = [r[3] for r in RAW]
    print("training", fmt_counts(labels), "H", f"{entropy(labels):.10f}")
    tree = build(RAW)
    print_node(tree)
    confusion(tree)
    gain_ratio_smoking(RAW)


if __name__ == "__main__":
    main()
