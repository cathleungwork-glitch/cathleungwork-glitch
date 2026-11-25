"""One command to generate the 14 posts, one command to dry-run publish."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from ig_pipeline.generate import PIPELINE_ROOT, generate
from ig_pipeline.publish import find_manifest, format_dry_run, publish_live
from ig_pipeline.schedule import tomorrow_hk


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ig_pipeline",
        description="Generate the 14-day Cantonese text-card queue, then dry-run the official publish path.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Read content/14-day.md and write a dated output folder.")
    gen.add_argument("--start-date", help="First post date, YYYY-MM-DD, Hong Kong. Default: tomorrow.")
    gen.add_argument("--output", help="Output folder. Default: output/<start-date>.")
    gen.add_argument(
        "--voice",
        choices=("edge", "azure", "silent"),
        default="edge",
        help="edge is zh-HK-HiuMaanNeural with no key. azure uses AZURE_SPEECH_KEY. silent skips speech.",
    )
    gen.add_argument("--force", action="store_true", help="Overwrite a folder that already records a publish.")

    pub = sub.add_parser("publish", help="Dry-run the Graph API schedule. Pass --live to post one due item.")
    pub.add_argument("--manifest", help="Path to schedule.json. Default: the only output/*/schedule.json.")
    pub.add_argument("--live", action="store_true", help="Post the one due item. Default is dry-run.")

    args = parser.parse_args(argv)
    if args.command == "generate":
        start = date.fromisoformat(args.start_date) if args.start_date else tomorrow_hk()
        output = Path(args.output) if args.output else None
        return generate(start, output, args.voice, args.force)

    manifest = find_manifest(args.manifest, PIPELINE_ROOT)
    if args.live:
        return publish_live(manifest)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    print(format_dry_run(data, manifest), end="")
    return 0
