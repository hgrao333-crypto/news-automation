"""Domain models – dict-compatible for existing pipeline."""

from typing import Any, List, TypedDict


class Article(TypedDict, total=False):
    """A news article. Compatible with existing dict-based flow."""
    title: str
    description: str
    link: str
    published: str


class Segment(TypedDict, total=False):
    """A single segment of the script (headline or summary)."""
    type: str  # 'headline' | 'summary' | 'hook' | 'closing'
    text: str
    story_index: int
    start_time: float
    duration: float


class ScriptData(TypedDict, total=False):
    """Full script and metadata for one video."""
    title: str
    script: str
    segments: List[Segment]
    image_prompts: List[str]
