"""IUploader adapter using existing YouTubeUploader."""

from typing import Any, Dict, List, Optional

from news_automation.ports.interfaces import IUploader


class YouTubeUploaderAdapter(IUploader):
    """Wraps root-level YouTubeUploader."""

    def __init__(
        self,
        credentials_file: Optional[str] = None,
        token_file: Optional[str] = None,
    ):
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from config import YOUTUBE_CREDENTIALS_FILE, YOUTUBE_TOKEN_FILE
        from youtube_uploader import YouTubeUploader
        self._uploader = YouTubeUploader(
            credentials_file=credentials_file or YOUTUBE_CREDENTIALS_FILE,
            token_file=token_file or YOUTUBE_TOKEN_FILE,
        )

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        category_id: str = "22",
        privacy_status: str = "public",
    ) -> Optional[Dict[str, Any]]:
        return self._uploader.upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags or ["news", "breaking news", "news update", "youtube shorts", "ai news"],
            category_id=category_id,
            privacy_status=privacy_status,
        )
