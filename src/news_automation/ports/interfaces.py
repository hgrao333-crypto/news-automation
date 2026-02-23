"""
Port interfaces (SOLID – Dependency Inversion).
Implement these in adapters; application layer depends only on these abstractions.
New sources (e.g. real-time feed / openclaw agent) implement INewsSource.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class INewsSource(ABC):
    """News source: today's top stories or topic-based. Real-time feed can implement this."""

    @abstractmethod
    def fetch_today_news(
        self,
        limit: int = 10,
        test_articles: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch today's top news articles."""
        pass

    @abstractmethod
    def fetch_hot_topic(
        self,
        topic: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fetch news about a hot topic."""
        pass


class IContentGenerator(ABC):
    """Content/script generation: select stories and produce script + segments + image prompts."""

    @abstractmethod
    def analyze_and_select_important_news(
        self,
        articles: List[Dict[str, Any]],
        select_count: int = 5,
        ensure_diversity: bool = True,
    ) -> List[Dict[str, Any]]:
        """Select the most important and diverse articles."""
        pass

    @abstractmethod
    def generate_today_in_60_seconds(
        self,
        articles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate script, segments, and image prompts for 'today in 60 seconds'."""
        pass

    @abstractmethod
    def generate_hot_topic_script(
        self,
        topic: str,
        articles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate script, segments, and image prompts for a hot topic video."""
        pass

    def generate_image_prompts(
        self,
        segments: List[Dict[str, Any]],
        articles: List[Dict[str, Any]],
        topic: Optional[str] = None,
    ) -> List[str]:
        """Generate image prompts (optional override; some adapters use internal method)."""
        raise NotImplementedError("Adapter should implement or use script_data image_prompts")


class IImageGenerator(ABC):
    """Image generation from text prompts."""

    @abstractmethod
    def generate_images_for_segments(self, prompts: List[str]) -> List[str]:
        """Generate one image per prompt; return list of file paths."""
        pass


class ITTSProvider(ABC):
    """Text-to-speech: full script or per-segment with timings."""

    @abstractmethod
    def generate_audio(self, text: str, output_filename: str) -> Optional[str]:
        """Generate audio for full text; return path or None."""
        pass

    @abstractmethod
    def generate_segmented_audio(
        self,
        segments: List[Dict[str, Any]],
        output_filename: str,
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Generate audio per segment; return (audio_path, segment_timings)."""
        pass


class IVideoRenderer(ABC):
    """Video assembly: images + audio + script data -> final video file."""

    @abstractmethod
    def create_video(
        self,
        image_paths: List[str],
        audio_path: str,
        script_data: Dict[str, Any],
        output_filename: str,
        segment_timings: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[str]:
        """Create video; return output path or None."""
        pass


class IUploader(ABC):
    """Publish video (e.g. YouTube)."""

    @abstractmethod
    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        category_id: str = "22",
        privacy_status: str = "public",
    ) -> Optional[Dict[str, Any]]:
        """Upload video; return result dict with e.g. 'url' or None."""
        pass
