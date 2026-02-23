"""IContentGenerator adapter using existing ContentGenerator."""

from typing import Any, Dict, List, Optional

from news_automation.ports.interfaces import IContentGenerator


class ContentGeneratorAdapter(IContentGenerator):
    """Wraps root-level ContentGenerator."""

    def __init__(self):
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from content_generator import ContentGenerator
        self._gen = ContentGenerator()

    def analyze_and_select_important_news(
        self,
        articles: List[Dict[str, Any]],
        select_count: int = 5,
        ensure_diversity: bool = True,
    ) -> List[Dict[str, Any]]:
        return self._gen.analyze_and_select_important_news(
            articles, select_count=select_count, ensure_diversity=ensure_diversity
        )

    def generate_today_in_60_seconds(
        self,
        articles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return self._gen.generate_today_in_60_seconds(articles)

    def generate_hot_topic_script(
        self,
        topic: str,
        articles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return self._gen.generate_hot_topic_script(topic, articles)

    def generate_image_prompts(
        self,
        segments: List[Dict[str, Any]],
        articles: List[Dict[str, Any]],
        topic: Optional[str] = None,
    ) -> List[str]:
        return self._gen._generate_image_prompts_with_ollama(segments, articles, topic)
