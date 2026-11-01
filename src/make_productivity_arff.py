#!/usr/bin/env python3
"""Build the five-attribute productivity ARFF file used in Question 4.

productivity = 1 if actual_productivity >= targeted_productivity, else 0.
Numeric fields keep the original CSV tokens so Weka sees the same values.
"""

import csv
from pathlib import Path

SRC = Path("/workspace/data/garments_worker_productivity.csv")
DST = Path("/workspace/solution/productivity.arff")

NUMERIC = ["team", "smv", "over_time", "incentive", "no_of_workers"]


def main():
    rows_out = []
    n1 = n0 = 0
    missing = 0
    with SRC.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if any(row[c] is None or row[c].strip() == "" for c in NUMERIC + ["actual_productivity", "targeted_productivity"]):
                missing += 1
                continue
            actual = float(row["actual_productivity"])
            target = float(row["targeted_productivity"])
            label = "1" if actual >= target else "0"
            if label == "1":
                n1 += 1
            else:
                n0 += 1
            values = [row[c].strip() for c in NUMERIC] + [label]
            rows_out.append(values)

    lines = [
        "@relation productivity",
        "",
        "@attribute team numeric",
        "@attribute smv numeric",
        "@attribute over_time numeric",
        "@attribute incentive numeric",
        "@attribute no_of_workers numeric",
        "@attribute productivity {0,1}",
        "",
        "@data",
    ]
    for values in rows_out:
        lines.append(",".join(values))
    DST.write_text("\n".join(lines) + "\n")
    print(f"wrote {DST} instances={len(rows_out)} productivity1={n1} productivity0={n0} skipped_missing={missing}")


if __name__ == "__main__":
    main()
