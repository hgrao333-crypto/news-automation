"""
News Automation – SOLID-structured pipeline for automated news shorts.

Use from project root (so root `config` is on path):
  from news_automation.application.pipeline import VideoPipeline
  from news_automation.adapters import default_adapters
  pipeline = VideoPipeline(**default_adapters())
  pipeline.run_today_video()

For real-time / openclaw agent: implement ports (e.g. INewsSource) and inject.
"""

__version__ = "0.2.0"
