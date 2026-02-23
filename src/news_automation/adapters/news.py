"""INewsSource adapter using existing NewsFetcher."""

from typing import Any, Dict, List, Optional

from news_automation.ports.interfaces import INewsSource


class NewsFetcherAdapter(INewsSource):
    """Wraps root-level NewsFetcher for today/topic news. Replace with real-time feed adapter if needed."""

    def __init__(
        self,
        news_api_key: Optional[str] = None,
        country: str = "in",
        use_gemini: bool = False,
    ):
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from news_fetcher import NewsFetcher
        from config import NEWS_API_KEY
        self._fetcher = NewsFetcher(
            news_api_key=news_api_key if news_api_key is not None else NEWS_API_KEY,
            country=country,
            use_gemini=use_gemini,
        )

    def fetch_today_news(
        self,
        limit: int = 10,
        test_articles: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        return self._fetcher.fetch_today_news(limit=limit, test_articles=test_articles)

    def fetch_hot_topic(
        self,
        topic: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        return self._fetcher.fetch_hot_topic(topic=topic, limit=limit)
