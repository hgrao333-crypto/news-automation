#!/usr/bin/env python3
"""
Main script to generate automated 60-second news shorts for YouTube.
Uses the SOLID pipeline in src/news_automation; run from project root.
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure project root and src are on path (config + legacy modules at root, package in src)
_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
for p in (_ROOT, _SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _run_pipeline(video_type: str, topic: str = None, upload: bool = False) -> None:
    """Run the SOLID pipeline (today or topic)."""
    from news_automation.application.pipeline import VideoPipeline
    from news_automation.adapters import default_adapters
    from config import YOUTUBE_AUTO_UPLOAD, YOUTUBE_PRIVACY_STATUS, YOUTUBE_CATEGORY_ID

    if upload:
        os.environ["YOUTUBE_AUTO_UPLOAD"] = "true"
    upload_after = os.getenv("YOUTUBE_AUTO_UPLOAD", "false").lower() == "true" or upload

    adapters = default_adapters()
    pipeline = VideoPipeline(
        **adapters,
        upload_after=upload_after,
        category_id=YOUTUBE_CATEGORY_ID,
        privacy_status=YOUTUBE_PRIVACY_STATUS,
    )

    if video_type == "today":
        pipeline.run_today_video()
    else:
        pipeline.run_topic_video(topic)


def main():
    parser = argparse.ArgumentParser(description="Generate automated 60-second news shorts")
    parser.add_argument(
        "--type",
        choices=["today", "topic"],
        default="today",
        help='Type of video: "today" (daily summary) or "topic" (hot topic)',
    )
    parser.add_argument("--topic", type=str, help="Topic for hot-topic video (optional)")
    parser.add_argument("--upload", action="store_true", help="Upload to YouTube after generation")
    args = parser.parse_args()

    _run_pipeline(args.type, args.topic, args.upload)


if __name__ == "__main__":
    main()
