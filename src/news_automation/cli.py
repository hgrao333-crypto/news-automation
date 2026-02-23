"""
CLI entrypoint. Use from project root:
  python -m news_automation --type today [--upload]
  python -m news_automation --type topic [--topic "AI"] [--upload]
"""

import argparse
import os
import sys
from pathlib import Path


def _ensure_project_root_on_path():
    """Ensure project root is on sys.path so config and legacy modules load."""
    root = Path(__file__).resolve().parents[2]  # src/news_automation/cli.py -> project root
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main() -> None:
    _ensure_project_root_on_path()
    from config import YOUTUBE_AUTO_UPLOAD, YOUTUBE_PRIVACY_STATUS, YOUTUBE_CATEGORY_ID
    from news_automation.application.pipeline import VideoPipeline
    from news_automation.adapters import default_adapters

    parser = argparse.ArgumentParser(
        description="Generate automated 60-second news shorts (SOLID pipeline)"
    )
    parser.add_argument(
        "--type",
        choices=["today", "topic"],
        default="today",
        help="Video type: 'today' (daily summary) or 'topic' (hot topic)",
    )
    parser.add_argument("--topic", type=str, help="Topic for hot-topic video (optional)")
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload video to YouTube after generation",
    )
    args = parser.parse_args()

    if args.upload:
        os.environ["YOUTUBE_AUTO_UPLOAD"] = "true"

    upload_after = (
        os.getenv("YOUTUBE_AUTO_UPLOAD", "false").lower() == "true"
        or args.upload
    )

    adapters = default_adapters()
    pipeline = VideoPipeline(
        **adapters,
        upload_after=upload_after,
        category_id=YOUTUBE_CATEGORY_ID,
        privacy_status=YOUTUBE_PRIVACY_STATUS,
    )

    if args.type == "today":
        pipeline.run_today_video()
    else:
        pipeline.run_topic_video(args.topic)


if __name__ == "__main__":
    main()
