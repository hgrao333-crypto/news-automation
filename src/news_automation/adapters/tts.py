"""ITTSProvider adapter using existing TTSGenerator."""

from typing import Any, Dict, List, Optional, Tuple

from news_automation.ports.interfaces import ITTSProvider


class TTSGeneratorAdapter(ITTSProvider):
    """Wraps root-level TTSGenerator."""

    def __init__(self):
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from tts_generator import TTSGenerator
        self._tts = TTSGenerator()

    def generate_audio(self, text: str, output_filename: str) -> Optional[str]:
        return self._tts.generate_audio(text, output_filename)

    def generate_segmented_audio(
        self,
        segments: List[Dict[str, Any]],
        output_filename: str,
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        return self._tts.generate_segmented_audio(segments, output_filename)
