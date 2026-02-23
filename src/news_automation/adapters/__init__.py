"""
Adapters – concrete implementations of ports.
Uses existing root-level modules (news_fetcher, content_generator, etc.)
so current behavior is unchanged. For real-time/openclaw, add a new
INewsSource implementation and inject it into the pipeline.
"""

from news_automation.adapters.news import NewsFetcherAdapter
from news_automation.adapters.content import ContentGeneratorAdapter
from news_automation.adapters.image import ImageGeneratorAdapter
from news_automation.adapters.tts import TTSGeneratorAdapter
from news_automation.adapters.video import VideoGeneratorAdapter
from news_automation.adapters.upload import YouTubeUploaderAdapter


def default_adapters(**overrides):
    """
    Build default adapter instances (use root config).
    Overrides: news_source=..., content_generator=..., etc. for testing or real-time feed.
    """
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]  # project root (src/news_automation/adapters -> 3 up)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from news_automation.ports.interfaces import (
        INewsSource,
        IContentGenerator,
        IImageGenerator,
        ITTSProvider,
        IVideoRenderer,
        IUploader,
    )

    defaults = {
        "news_source": NewsFetcherAdapter(),
        "content_generator": ContentGeneratorAdapter(),
        "image_generator": ImageGeneratorAdapter(),
        "tts_provider": TTSGeneratorAdapter(),
        "video_renderer": VideoGeneratorAdapter(),
        "uploader": YouTubeUploaderAdapter(),
    }
    defaults.update(overrides)
    return defaults
