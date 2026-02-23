"""Ports (interfaces) – depend on these, implement in adapters."""

from news_automation.ports.interfaces import (
    INewsSource,
    IContentGenerator,
    IImageGenerator,
    ITTSProvider,
    IVideoRenderer,
    IUploader,
)

__all__ = [
    "INewsSource",
    "IContentGenerator",
    "IImageGenerator",
    "ITTSProvider",
    "IVideoRenderer",
    "IUploader",
]
