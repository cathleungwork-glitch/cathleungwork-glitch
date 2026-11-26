"""The 14-day file stays inside the playbook, and the publisher stays a dry run."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from ig_pipeline.captions import DISCLAIMER, build_caption
from ig_pipeline.cli import main
from ig_pipeline.guardrails import lint_post, lint_text
from ig_pipeline.playbook import load_playbook
from ig_pipeline.publish import format_dry_run, select_for_live
from ig_pipeline.render import allocate_durations, render_carousel, render_reel
from ig_pipeline.textfit import font_candidates, font_path, wrap_text
from ig_pipeline.schedule import HK, post_at

ROOT = Path(__file__).resolve().parent.parent


class PlaybookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.posts, cls.checks = load_playbook()

    def test_voice_checks_are_the_four_sentences(self) -> None:
        self.assertEqual(
            self.checks,
            [
                "冇人叫你買入，亦都冇人叫你賣出。",
                "年費七百二，回贈未計年費就唔算賺到。",
                "你張卡 claim 咗，唔代表批咗。",
                "出糧嗰晚先轉走，轉一餐午饭錢都得。",
            ],
        )

    def test_fourteen_posts_and_kinds(self) -> None:
        self.assertEqual([post.day for post in self.posts], list(range(1, 15)))
        kinds = [post.kind for post in self.posts]
        self.assertEqual(kinds.count("reel"), 10)
        self.assertEqual(kinds.count("carousel"), 4)
        self.assertEqual([post.day for post in self.posts if post.kind == "carousel"], [3, 7, 11, 14])

    def test_topics_stay_inside_the_niche(self) -> None:
        blob = "\n".join(post.source + post.spoken + post.hook for post in self.posts)
        self.assertEqual(lint_text(blob), [])
        for post in self.posts:
            self.assertEqual(lint_post(post), [], post.day)

    def test_day_nine_does_not_tell_anyone_to_buy(self) -> None:
        day = self.posts[8]
        self.assertIn("唔係叫你買", day.spoken)
        self.assertIn("呢個係機制，唔係時機。", day.spoken)
        self.assertIn("以比特幣做例子", day.spoken)

    def test_hooks_stay_short(self) -> None:
        for post in self.posts:
            compact = "".join(post.hook.split())
            self.assertLessEqual(len(compact), 12, post.hook)

    def test_cards(self) -> None:
        by_day = {post.day: post.cards for post in self.posts if post.kind == "reel"}
        self.assertEqual(
            by_day[1],
            [
                "出糧同扣數一戶",
                "唔轉走第二日當使",
                "午饭六十蚊係例子",
                "二十二日約一千三",
                "出糧嗰晚轉第二戶",
            ],
        )
        self.assertEqual(
            by_day[4],
            [
                "交保費唔等於保",
                "保費係你付嘅錢",
                "不保先至係唔賠",
                "搜不保，讀第一段",
                "簽名前搜不保",
            ],
        )
        self.assertEqual(by_day[8][1], "例子：單一千還五十")
        self.assertIn("九百五十", " ".join(by_day[8]))
        self.assertEqual(by_day[12][0], "月尾先儲就遲")
        self.assertEqual(by_day[2][0], "收據總數你對")
        self.assertIn("對到總數先貼", by_day[2])

    def test_day_eleven_cover_stays_eight_pages(self) -> None:
        day = self.posts[10]
        self.assertEqual(day.hook, "出糧只動兩桶")
        self.assertEqual(len(day.pages), 8)
        self.assertEqual(day.pages[0], day.hook)
        self.assertEqual(day.point, "第三桶未寫低每年費用之前，留喺現金")
        self.assertEqual(day.pages[1], "第一桶一定要交：租、家用、車錢。出糧嗰晚先留夠")

    def test_captions(self) -> None:
        tag_lines = []
        for post in self.posts:
            lines = build_caption(post).splitlines()
            self.assertEqual(lines[0], post.hook)
            self.assertEqual(lines[1], post.point)
            self.assertEqual(lines[2], DISCLAIMER)
            self.assertLessEqual(len(lines[3].split()), 5)
            tag_lines.append(lines[3])
        self.assertEqual(len(set(tag_lines)), 14)

    def test_schedule_clock(self) -> None:
        start = date(2026, 11, 26)
        self.assertEqual(post_at(start, 1).isoformat(), "2026-11-26T12:20:00+08:00")
        self.assertEqual(post_at(start, 2).isoformat(), "2026-11-27T21:00:00+08:00")
        self.assertEqual(post_at(start, 14).isoformat(), "2026-12-09T21:00:00+08:00")
        for day in range(1, 15):
            stamp = post_at(start, day)
            if day % 2 == 1:
                self.assertEqual((stamp.hour, stamp.minute), (12, 20))
            else:
                self.assertEqual((stamp.hour, stamp.minute), (21, 0))

    def test_guardrail_rejects_a_guarantee(self) -> None:
        self.assertIn("保證回報", lint_text("呢隻保證回報"))
        self.assertIn("強積金", lint_text("講強積金"))
        self.assertIn("稅", lint_text("報稅"))


class PublishTests(unittest.TestCase):
    def test_live_selection_posts_one_due_item(self) -> None:
        posts = [
            {"day": 1, "post_at": "2026-11-26T12:20:00+08:00", "status": "draft"},
            {"day": 2, "post_at": "2026-11-27T21:00:00+08:00", "status": "draft"},
        ]
        now = datetime(2026, 11, 27, 22, 0, tzinfo=HK)
        choice = select_for_live(posts, now)
        self.assertEqual(choice.post["day"], 1)

    def test_live_selection_waits_twelve_hours(self) -> None:
        last = datetime(2026, 11, 27, 12, 20, tzinfo=HK)
        posts = [
            {
                "day": 1,
                "post_at": "2026-11-26T12:20:00+08:00",
                "status": "published",
                "published_at": last.isoformat(),
            },
            {"day": 2, "post_at": "2026-11-27T21:00:00+08:00", "status": "draft"},
        ]
        now = last + timedelta(hours=6)
        choice = select_for_live(posts, now)
        self.assertIsNone(choice.post)
        self.assertIn("12 hours", choice.message)

    def test_future_post_is_not_due(self) -> None:
        posts = [{"day": 1, "post_at": "2026-11-26T12:20:00+08:00", "status": "draft"}]
        now = datetime(2026, 11, 26, 9, 0, tzinfo=HK)
        choice = select_for_live(posts, now)
        self.assertIsNone(choice.post)
        self.assertIn("Nothing is due", choice.message)

    def test_dry_run_hides_the_token(self) -> None:
        previous = os.environ.get("IG_ACCESS_TOKEN")
        os.environ["IG_ACCESS_TOKEN"] = "SECRETTOKENVALUE123"
        os.environ["IG_USER_ID"] = "17890000"
        try:
            data = {
                "voice": {"engine": "edge-tts", "name": "zh-HK-HiuMaanNeural", "fallback": False},
                "posts": [
                    {
                        "day": 1,
                        "post_at": "2026-11-20T12:20:00+08:00",
                        "kind": "reel",
                        "status": "draft",
                        "file": "day-01/reel.mp4",
                        "caption": "出糧 8 秒，錢行咗\n",
                        "ai_generated_voice": True,
                    }
                ],
            }
            text = format_dry_run(data, Path("/tmp/schedule.json"), datetime(2026, 11, 25, 18, 0, tzinfo=HK))
        finally:
            if previous is None:
                os.environ.pop("IG_ACCESS_TOKEN", None)
            else:
                os.environ["IG_ACCESS_TOKEN"] = previous
            os.environ.pop("IG_USER_ID", None)
        self.assertNotIn("SECRETTOKENVALUE123", text)
        self.assertIn("Nothing was sent to Instagram.", text)
        self.assertIn("[redacted]", text)


class LimitTests(unittest.TestCase):
    def test_limit_five_writes_days_one_to_five_only(self) -> None:
        posts, _ = load_playbook()
        start = date(2026, 11, 26)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            code = main(
                [
                    "generate",
                    "--limit",
                    "5",
                    "--voice",
                    "silent",
                    "--start-date",
                    start.isoformat(),
                    "--output",
                    tmp,
                ]
            )
            self.assertEqual(code, 0)
            day_dirs = sorted(path.name for path in folder.iterdir() if path.name.startswith("day-"))
            self.assertEqual(day_dirs, ["day-01", "day-02", "day-03", "day-04", "day-05"])
            for day in range(6, 15):
                self.assertFalse((folder / f"day-{day:02}").exists())
            self.assertGreater((folder / "day-01" / "reel.mp4").stat().st_size, 10_000)
            self.assertTrue((folder / "day-02" / "reel.mp4").exists())
            self.assertTrue((folder / "day-04" / "reel.mp4").exists())
            self.assertTrue((folder / "day-05" / "reel.mp4").exists())
            self.assertTrue((folder / "day-03" / "page-01.jpg").exists())
            self.assertFalse((folder / "day-03" / "reel.mp4").exists())
            manifest = json.loads((folder / "schedule.json").read_text(encoding="utf-8"))
            self.assertEqual([item["day"] for item in manifest["posts"]], [1, 2, 3, 4, 5])
            self.assertEqual(manifest["limit"], 5)
            for post, record in zip(posts[:5], manifest["posts"]):
                self.assertEqual(record["caption"], build_caption(post))
                self.assertEqual(record["post_at"], post_at(start, post.day).isoformat(timespec="seconds"))
                caption = (folder / f"day-{post.day:02}" / "caption.txt").read_text(encoding="utf-8")
                self.assertEqual(caption, build_caption(post))

    def test_limit_zero_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["generate", "--limit", "0", "--voice", "silent", "--output", tmp])
            self.assertEqual(code, 1)
            self.assertEqual(list(Path(tmp).iterdir()), [])


class FontTests(unittest.TestCase):
    def test_candidates_try_mac_then_linux(self) -> None:
        paths = [str(path) for path in font_candidates()]
        self.assertEqual(
            paths[:5],
            [
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Medium.ttc",
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            ],
        )

    def test_linux_font_still_wins_when_mac_fonts_are_absent(self) -> None:
        self.assertEqual(font_path(), "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc")

    def test_pingfang_is_preferred_when_it_exists(self) -> None:
        pingfang = "/System/Library/Fonts/PingFang.ttc"

        def is_file(self: Path) -> bool:
            return str(self) == pingfang

        with patch.object(Path, "is_file", is_file):
            self.assertEqual(font_path(), pingfang)

    def test_user_library_wqy_is_used_when_nothing_else_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fonts = Path(tmp) / "Library" / "Fonts"
            fonts.mkdir(parents=True)
            (fonts / "Arial.ttf").write_bytes(b"x")
            wqy = fonts / "wqy-microhei.ttc"
            wqy.write_bytes(b"x")

            def is_file(self: Path) -> bool:
                return self == wqy

            with patch("ig_pipeline.textfit.Path.home", return_value=Path(tmp)):
                with patch.object(Path, "is_file", is_file):
                    self.assertEqual(font_path(), str(wqy))


class RenderTests(unittest.TestCase):
    def test_one_reel_and_one_carousel_page(self) -> None:
        commands: list[list[str]] = []
        real_run = subprocess.run

        def spy(cmd, **kwargs):
            if isinstance(cmd, list):
                commands.append([str(part) for part in cmd])
            return real_run(cmd, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with patch("ig_pipeline.render.subprocess.run", spy):
                render_reel(
                    ["出糧 8 秒，錢行咗", "出糧嗰晚，先轉走"],
                    None,
                    folder / "reel.mp4",
                    6,
                    True,
                    "出糧 8 秒，錢行咗",
                )
            render_carousel(["回贈未計年費，就唔算賺到"], folder)
            reel = folder / "reel.mp4"
            image = folder / "page-01.jpg"
            self.assertGreater(reel.stat().st_size, 10_000)
            self.assertTrue(commands)
            for cmd in commands:
                self.assertNotIn("drawtext", " ".join(cmd))
                self.assertNotIn("-vf", cmd)
            probe = json.loads(
                subprocess.check_output(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-select_streams",
                        "v:0",
                        "-show_entries",
                        "stream=width,height,codec_name",
                        "-of",
                        "json",
                        str(reel),
                    ],
                    text=True,
                )
            )
            stream = probe["streams"][0]
            self.assertEqual(stream["codec_name"], "h264")
            self.assertEqual((stream["width"], stream["height"]), (1080, 1920))
            from PIL import Image

            with Image.open(image) as opened:
                opened.verify()
            with Image.open(image) as opened:
                self.assertEqual(opened.size, (1080, 1350))
            self.assertEqual(round(sum(allocate_durations(20, 8)), 5), 20)

    def test_wrap_breaks_after_the_comma(self) -> None:
        lines = wrap_text("股票有間公司，幣冇一張報表", 88, 840)
        self.assertEqual(lines, ["股票有間公司，", "幣冇一張報表"])
        packed = wrap_text("有人用五成、三成、兩成。呢個係佢哋嘅分類，唔係你要跟嘅比例", 72, 880)
        for line in packed[1:]:
            self.assertNotIn(line[0], "，、。")


if __name__ == "__main__":
    unittest.main()
