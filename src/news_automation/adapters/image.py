"""IImageGenerator adapter using existing ImageGenerator."""

from typing import List

from news_automation.ports.interfaces import IImageGenerator


class ImageGeneratorAdapter(IImageGenerator):
    """Wraps root-level ImageGenerator."""

    def __init__(self):
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from image_generator import ImageGenerator
        self._gen = ImageGenerator()

    def generate_images_for_segments(self, prompts: List[str]) -> List[str]:
        return self._gen.generate_images_for_segments(prompts)
