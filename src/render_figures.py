#!/usr/bin/env python3
"""Render the Weka and Python outputs as readable result-window figures."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/workspace/solution")
FIG = ROOT / "figures"
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 18)
FONT_SM = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 15)
TITLE_FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)


def window(text: str, path: Path, title: str, font=FONT) -> None:
    lines = text.replace("\t", "    ").split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    pad_x, pad_y = 18, 14
    line_h = font.size + 8
    title_h = 34
    text_w = max(int(font.getlength(line)) for line in lines) if lines else 100
    title_w = int(TITLE_FONT.getlength(title)) + 24
    width = max(text_w + pad_x * 2, title_w)
    height = title_h + pad_y * 2 + line_h * max(len(lines), 1)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width - 1, title_h), fill="#ececec")
    draw.text((12, 8), title, fill="#222222", font=TITLE_FONT)
    draw.rectangle((0, 0, width - 1, height - 1), outline="#7a7a7a")
    draw.line((0, title_h, width, title_h), fill="#7a7a7a")
    y = title_h + pad_y
    for line in lines:
        draw.text((pad_x, y), line, fill="#111111", font=font)
        y += line_h
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def take(text: str, start: str, n_lines: int, last: bool = False) -> str:
    index = text.rfind(start) if last else text.find(start)
    if index < 0:
        raise SystemExit(f"marker not found: {start}")
    return "\n".join(text[index:].splitlines()[:n_lines])


def break_scheme(block: str) -> str:
    lines = []
    for line in block.splitlines():
        if line.startswith("Scheme:") and len(line) > 88:
            cut = line.find(" -W ")
            lines.append(line[:cut])
            lines.append(" " * 14 + line[cut + 1 :])
        else:
            lines.append(line)
    return "\n".join(lines)


def main() -> None:
    zeror = (ROOT / "zeror-explorer.txt").read_text()
    j48 = (ROOT / "j48-explorer.txt").read_text()
    cvps = (ROOT / "cvps-explorer.txt").read_text()
    q5 = (ROOT / "q5_output.txt").read_text()

    window(
        take(zeror, "=== Run information ===", 13),
        FIG / "q4a-run-information.png",
        "Weka Explorer  —  ZeroR, 10-fold cross-validation",
    )
    window(
        take(zeror, "=== Confusion Matrix ===", 5, last=True),
        FIG / "q4a-confusion-matrix.png",
        "Weka Explorer  —  ZeroR confusion matrix (stratified cross-validation)",
    )
    window(
        take(j48, "=== Run information ===", 13),
        FIG / "q4b-run-information.png",
        "Weka Explorer  —  J48, confidence factor C = 0.1",
    )
    window(
        take(j48, "J48 pruned tree", 16),
        FIG / "q4b-tree.png",
        "Weka Explorer  —  J48 pruned tree (first lines)",
    )
    window(
        break_scheme(take(cvps, "=== Run information ===", 13)),
        FIG / "q4c-run-information.png",
        "Weka Explorer  —  CVParameterSelection + J48",
    )
    window(
        take(cvps, "Cross-validated Parameter selection.", 4),
        FIG / "q4c-selected-c.png",
        "Weka Explorer  —  C selected by CVParameterSelection",
    )

    step1, rest = q5.split("===== Step 2 and Step 3 output =====", 1)
    step23, rest = rest.split("===== Step 4 output =====", 1)
    step4, step5 = rest.split("===== Step 5 output =====", 1)
    window(step1.strip(), FIG / "q5-step1.png", "python3 src/q5_abalone.py    —  Step 1")
    window(
        "===== Step 2 and Step 3 output =====\n" + step23.strip(),
        FIG / "q5-step23.png",
        "python3 src/q5_abalone.py    —  Steps 2 and 3",
    )
    step4_lines = ("===== Step 4 output =====\n" + step4.strip()).splitlines()
    mid = 28
    window(
        "\n".join(step4_lines[:mid]),
        FIG / "q5-step4a.png",
        "python3 src/q5_abalone.py    —  Step 4 (text tree, part 1)",
        font=FONT_SM,
    )
    window(
        "\n".join(step4_lines[mid:]),
        FIG / "q5-step4b.png",
        "python3 src/q5_abalone.py    —  Step 4 (text tree, part 2)",
        font=FONT_SM,
    )
    window(
        "===== Step 5 output =====\n" + step5.strip(),
        FIG / "q5-step5.png",
        "python3 src/q5_abalone.py    —  Step 5",
    )
    print("figures written")


if __name__ == "__main__":
    main()
