#!/usr/bin/env python3
"""Write the Question 3 working, using the same induction procedure as the analysis."""

import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/workspace/src")
import q1_q3_analysis as A


def r6(x: float) -> str:
    return f"{x:.6f}"


def counts(labels):
    c = Counter(labels)
    return ", ".join(str(c[name]) for name in A.CLASS_ORDER)


def count_words(labels):
    c = Counter(labels)
    parts = [f"{name} {c[name]}" for name in A.CLASS_ORDER if c[name]]
    return ", ".join(parts)


def entropy_formula(labels):
    n = len(labels)
    c = Counter(labels)
    bits = []
    for name in A.CLASS_ORDER:
        v = c[name]
        if v == 0:
            continue
        bits.append(rf"\frac{{{v}}}{{{n}}}\log_2\frac{{{v}}}{{{n}}}")
    return r"-\left(" + "+".join(bits) + r"\right)"


def latex_desc(desc: str) -> str:
    return (
        desc.replace("≤", r" $\le$ ")
        .replace("∈", r" $\in$ ")
        .replace(">", r" $>$ ")
        .replace("  ", " ")
    )


def candidate_table(node) -> str:
    rows = []
    best = node.split.gain if node.split else None
    for cand in node.candidates:
        left = [r[3] for r, m in zip(node.records, cand.mask) if m]
        right = [r[3] for r, m in zip(node.records, cand.mask) if not m]
        mark = r" \textbf{" + r6(cand.gain) + "}" if best is not None and abs(cand.gain - best) < 1e-12 else r6(cand.gain)
        # if stopped because best < 0.15, still bold the best (first, highest)
        rows.append(
            f"{latex_desc(cand.description)} & {cand.n_left} & {counts(left)} & {r6(cand.h_left)} "
            f"& {cand.n_right} & {counts(right)} & {r6(cand.h_right)} & {mark} \\\\"
        )
    # bold the top row always, since candidates are sorted by gain
    # The mark above only bolds when a split was chosen. Also bold when we stopped on the threshold.
    if node.split is None and node.candidates:
        first = rows[0]
        # replace the last numeric gain (already plain) — easier to rebuild
        rows = []
        top = node.candidates[0].gain
        for cand in node.candidates:
            left = [r[3] for r, m in zip(node.records, cand.mask) if m]
            right = [r[3] for r, m in zip(node.records, cand.mask) if not m]
            gain = r6(cand.gain)
            if abs(cand.gain - top) < 1e-12:
                gain = r"\textbf{" + gain + "}"
            rows.append(
                f"{latex_desc(cand.description)} & {cand.n_left} & {counts(left)} & {r6(cand.h_left)} "
                f"& {cand.n_right} & {counts(right)} & {r6(cand.h_right)} & {gain} \\\\"
            )
    body = "\n".join(rows)
    return rf"""
\begin{{center}}
\scriptsize
\begin{{tabular}}{{lrrrrrrr}}
\toprule
Split & $|L|$ & $L$ counts & $H(L)$ & $|R|$ & $R$ counts & $H(R)$ & Gain \\
\midrule
{body}
\bottomrule
\end{{tabular}}
\end{{center}}
Counts are ordered (HC, Infected, Asthma, COPD). The largest gain is in bold.
"""


def node_block(node, heading: str) -> str:
    labels = [r[3] for r in node.records]
    ids = ", ".join(str(r[0]) for r in node.records)
    h = A.entropy(labels)
    parts = [heading, ""]
    parts.append(
        f"Records {ids} ($n={len(labels)}$). Class counts: {count_words(labels)}."
    )
    parts.append(
        rf"\[ H = {entropy_formula(labels)} = {r6(h)}. \]"
    )
    if node.candidates:
        parts.append(
            "Every binary split is evaluated below. For a numeric attribute the threshold is the midpoint between successive distinct values, which puts every instance of one value entirely on one side. For nominal Smoking, each binary split is one partition of the values that actually occur in the node."
        )
        parts.append(candidate_table(node))
        if node.split is not None:
            n = len(labels)
            parts.append(
                f"The best gain is {r6(node.split.gain)}, which is at least $0.15$, and the node has at least 8 instances, so the node is split on {latex_desc(node.split.description)}."
            )
            parts.append(
                rf"\[ \mathrm{{Gain}} = H - \frac{{{node.split.n_left}}}{{{n}}}H(L) - \frac{{{node.split.n_right}}}{{{n}}}H(R) = {r6(node.split.gain)}. \]"
            )
            parts.append(
                "This gain is computed from the unrounded entropies and is the value compared with $0.15$. The entropies in the table are those same quantities rounded to 6 decimal places."
            )
        else:
            parts.append(
                f"The best gain is {r6(node.candidates[0].gain)}, which is less than $0.15$. Pre-pruning stops the split. The leaf label is the majority class {node.prediction}."
            )
    else:
        if "|D|" in node.reason:
            parts.append(
                f"This node has $n={len(labels)}<8$, so it is not split. The leaf label is the majority class {node.prediction}."
            )
        else:
            parts.append(f"{node.reason}. The leaf label is the majority class {node.prediction}.")
    parts.append("")
    return "\n".join(parts)


def main() -> None:
    tree = A.build(A.RAW)
    labels = [r[3] for r in A.RAW]
    # multi-way gain ratio
    groups = {}
    for rec in A.RAW:
        groups.setdefault(rec[2], []).append(rec[3])
    n = len(A.RAW)
    h = A.entropy(labels)
    remainder = 0.0
    split_info = 0.0
    group_lines = []
    for s in sorted(groups):
        labs = groups[s]
        hs = A.entropy(labs)
        remainder += len(labs) / n * hs
        p = len(labs) / n
        split_info -= p * math.log2(p)
        group_lines.append(
            f"Smoking $= {s}$ ($n={len(labs)}$): {count_words(labs)}."
        )
        group_lines.append(
            rf"\[ H = {entropy_formula(labs)} = {r6(hs)}. \]"
        )
    ig = h - remainder
    gr = ig / split_info

    text = []
    text.append(r"\subsection*{Training distribution}")
    text.append(
        f"The training set has 18 instances. Class counts: {count_words(labels)}."
    )
    text.append(node_block(tree, r"\subsection*{Root}"))
    text.append(node_block(tree.left, r"\subsection*{Left child: Smoking $\in \{1,3\}$}"))
    text.append(node_block(tree.left.left, r"\subsection*{Left-left child: Smoking $\in \{1,3\}$ and Age $\le 62.5$}"))
    text.append(node_block(tree.left.right, r"\subsection*{Left-right child: Smoking $\in \{1,3\}$ and Age $> 62.5$}"))
    text.append(node_block(tree.right, r"\subsection*{Right child: Smoking $= 2$}"))
    text.append(r"\subsection*{Gain ratio of the multi-way Smoking split}")
    text.append(
        "This calculation is separate from the tree. It uses one branch for each value of Smoking on the full training set."
    )
    text.append(
        rf"The parent entropy is the root entropy above, $H(D)={r6(h)}$."
    )
    for line in group_lines:
        text.append(line)
        text.append("")
    text.append(
        rf"\[ \mathrm{{Remainder}} = \frac{{7}}{{18}}\times {r6(A.entropy(groups[1]))} + \frac{{7}}{{18}}\times {r6(A.entropy(groups[2]))} + \frac{{4}}{{18}}\times {r6(A.entropy(groups[3]))} = {r6(remainder)}. \]"
    )
    text.append(
        rf"\[ \mathrm{{Gain}} = {r6(h)} - {r6(remainder)} = {r6(ig)}. \]"
    )
    text.append(
        rf"\[ \mathrm{{SplitInfo}} = -\left(\frac{{7}}{{18}}\log_2\frac{{7}}{{18}}+\frac{{7}}{{18}}\log_2\frac{{7}}{{18}}+\frac{{4}}{{18}}\log_2\frac{{4}}{{18}}\right) = {r6(split_info)}. \]"
    )
    text.append(
        rf"\[ \mathrm{{GainRatio}} = \frac{{{r6(ig)}}}{{{r6(split_info)}}} = {r6(gr)}. \]"
    )
    out_dir = Path("/workspace/solution/generated")
    out_dir.mkdir(parents=True, exist_ok=True)
    joined = "\n".join(text)
    marker = r"\subsection*{Gain ratio of the multi-way Smoking split}"
    tree_part, gain_part = joined.split(marker, 1)
    (out_dir / "q3_tree.tex").write_text(tree_part.strip() + "\n")
    (out_dir / "q3_gain.tex").write_text(marker + "\n\n" + gain_part.strip() + "\n")
    print("wrote q3 parts, gainratio", r6(gr))


if __name__ == "__main__":
    main()
