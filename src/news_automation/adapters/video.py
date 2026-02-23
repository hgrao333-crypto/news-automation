"""IVideoRenderer adapter using existing VideoGenerator."""

from typing import Any, Dict, List, Optional

from news_automation.ports.interfaces import IVideoRenderer


class VideoGeneratorAdapter(IVideoRenderer):
    """Wraps root-level VideoGenerator."""

    def __init__(self, is_extended: bool = False):
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from video_generator import VideoGenerator
        self._gen = VideoGenerator(is_extended=is_extended)

    def create_video(
        self,
        image_paths: List[str],
        audio_path: str,
        script_data: Dict[str, Any],
        output_filename: str,
        segment_timings: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[str]:
        return self._gen.create_video(
            image_paths,
            audio_path,
            script_data,
            output_filename,
            segment_timings,
        )
