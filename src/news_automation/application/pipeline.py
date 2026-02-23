"""
Video pipeline – single responsibility: orchestrate fetch → select → script → images → TTS → video → optional upload.
Depends only on port interfaces (SOLID – Dependency Inversion).
"""

import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from news_automation.ports.interfaces import (
    INewsSource,
    IContentGenerator,
    IImageGenerator,
    ITTSProvider,
    IVideoRenderer,
    IUploader,
)


class VideoPipeline:
    """
    Orchestrates the full video generation pipeline.
    All dependencies are injected (ports); no concrete implementations here.
    """

    def __init__(
        self,
        *,
        news_source: INewsSource,
        content_generator: IContentGenerator,
        image_generator: IImageGenerator,
        tts_provider: ITTSProvider,
        video_renderer: IVideoRenderer,
        uploader: IUploader,
        upload_after: bool = False,
        category_id: str = "22",
        privacy_status: str = "public",
    ):
        self._news = news_source
        self._content = content_generator
        self._images = image_generator
        self._tts = tts_provider
        self._video = video_renderer
        self._uploader = uploader
        self._upload_after = upload_after
        self._category_id = category_id
        self._privacy_status = privacy_status

    def run_today_video(self) -> Optional[str]:
        """Generate 'Today in 60 Seconds' video. Returns output path or None."""
        print("=" * 60)
        print("Generating 'Today in 60 Seconds' video...")
        print("=" * 60)

        print("\n[1/6] Fetching today's top news...")
        print("  🇮🇳 Using Indian news sources...")
        all_articles = self._news.fetch_today_news(limit=25)
        print(f"Found {len(all_articles)} articles")

        if not all_articles:
            print("No articles found. Exiting.")
            return None

        print("\n[2/6] Analyzing news importance (ensuring diversity)...")
        articles = self._content.analyze_and_select_important_news(
            all_articles, select_count=8, ensure_diversity=True
        )
        print(f"Selected {len(articles)} most important stories:")
        for i, article in enumerate(articles, 1):
            print(f"  {i}. {article['title'][:60]}")

        print("\n[3/6] Generating content script...")
        script_data = self._content.generate_today_in_60_seconds(articles)
        print(f"Title: {script_data.get('title', 'Untitled')}")
        print(f"Script length: {len(script_data.get('script', ''))} characters")

        print("\n[3.5/6] Preparing segments for video display...")
        segments = script_data.get("segments", [])
        for i, segment in enumerate(segments):
            seg_type = segment.get("type", "summary")
            text = segment.get("text", "")
            print(f"  Segment {i+1} ({seg_type}): {text[:70]}...")

        image_prompts = self._normalize_and_ensure_prompts(
            script_data, articles, segments, None, "today"
        )
        if not image_prompts:
            return None

        print("\n[4/6] Generating images from prompts...")
        image_paths = self._images.generate_images_for_segments(image_prompts)
        print(f"\n✅ Generated {len(image_paths)} images")

        print("\n[5/6] Generating text-to-speech audio...")
        audio_path, segment_timings = self._generate_audio(script_data, "today_audio.mp3")
        if not audio_path:
            print("Failed to generate audio. Exiting.")
            return None
        self._apply_timings_to_segments(script_data, segment_timings)

        print("\n[6/6] Creating final video...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"today_in_60_seconds_{timestamp}.mp4"
        video_path = self._video.create_video(
            image_paths, audio_path, script_data, output_filename, segment_timings
        )

        if not video_path:
            print("\n❌ Failed to create video.")
            return None

        print(f"\n✅ Success! Video saved to: {video_path}")
        if self._upload_after:
            self._do_upload(video_path, script_data.get("title", "Today in 60 Seconds"))
        return video_path

    def run_topic_video(self, topic: Optional[str] = None) -> Optional[str]:
        """Generate hot-topic video. Returns output path or None."""
        print("=" * 60)
        print("Generating 'Hot Topic' video...")
        print("=" * 60)

        print(f"\n[1/6] Fetching news about topic: {topic or 'trending topic'}...")
        all_articles = self._news.fetch_hot_topic(topic=topic, limit=20)
        print(f"Found {len(all_articles)} articles")

        if not all_articles:
            print("No articles found. Exiting.")
            return None

        if not topic and all_articles:
            topic = " ".join(all_articles[0]["title"].split()[:3])

        print("\n[2/6] Analyzing news relevance and importance...")
        articles = self._content.analyze_and_select_important_news(
            all_articles, select_count=7
        )
        print(f"Selected {len(articles)} most important stories:")
        for i, article in enumerate(articles, 1):
            print(f"  {i}. {article['title'][:60]}")

        print("\n[3/6] Generating content script...")
        script_data = self._content.generate_hot_topic_script(topic, articles)
        print(f"Title: {script_data.get('title', 'Untitled')}")
        print(f"Script length: {len(script_data.get('script', ''))} characters")

        print("\n[3.5/6] Preparing segments...")
        segments = script_data.get("segments", [])
        for i, segment in enumerate(segments):
            seg_type = segment.get("type", "summary")
            text = segment.get("text", "")
            print(f"  Segment {i+1} ({seg_type}): {text[:70]}...")

        image_prompts = script_data.get("image_prompts", [])
        if not image_prompts or len(image_prompts) < len(segments):
            if hasattr(self._content, "generate_image_prompts"):
                image_prompts = self._content.generate_image_prompts(
                    segments, articles, topic
                )
        if not image_prompts:
            image_prompts = [
                f"Visual representation of {topic}",
                f"Breaking news about {topic}",
                f"News coverage of {topic}",
            ]
        image_prompts = [p if isinstance(p, str) else str(p) for p in image_prompts]

        print("\n[4/6] Generating images...")
        image_paths = self._images.generate_images_for_segments(image_prompts)
        print(f"\n✅ Generated {len(image_paths)} images")

        print("\n[5/6] Generating TTS audio...")
        audio_path, segment_timings = self._generate_audio(script_data, "topic_audio.mp3")
        if not audio_path:
            print("Failed to generate audio. Exiting.")
            return None
        self._apply_timings_to_segments(script_data, segment_timings)

        print("\n[6/6] Creating final video...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = "".join(c for c in topic if c.isalnum() or c in (" ", "-", "_")).strip()[:30]
        output_filename = f"hot_topic_{safe_topic}_{timestamp}.mp4"
        video_path = self._video.create_video(
            image_paths, audio_path, script_data, output_filename, segment_timings
        )

        if not video_path:
            print("\n❌ Failed to create video.")
            return None

        print(f"\n✅ Success! Video saved to: {video_path}")
        if self._upload_after:
            self._do_upload(video_path, script_data.get("title", "Hot Topic Video"))
        return video_path

    def _normalize_and_ensure_prompts(
        self,
        script_data: Dict[str, Any],
        articles: List[Dict[str, Any]],
        segments: List[Dict[str, Any]],
        topic: Optional[str],
        mode: str,
    ) -> List[str]:
        """Normalize image_prompts to list of strings; regenerate if missing/generic."""
        generic_keywords = [
            "professional news broadcast studio",
            "breaking news headline",
            "news anchor presenting",
        ]
        image_prompts = script_data.get("image_prompts", [])
        image_prompts = [
            p if isinstance(p, str) else (p.get("text", str(p)) if isinstance(p, dict) else str(p))
            for p in image_prompts
        ]
        story_indices = {s.get("story_index") for s in segments if s.get("story_index") is not None}
        num_stories = len(story_indices)
        expected_prompts = num_stories + 1

        needs_regeneration = False
        if not image_prompts or len(image_prompts) < expected_prompts:
            needs_regeneration = True
            print(f"⚠️  Image prompts missing or incomplete. Regenerating...")
        elif len(image_prompts) > 1 and isinstance(image_prompts[1], str):
            if any(kw.lower() in image_prompts[1].lower() for kw in generic_keywords):
                needs_regeneration = True
                print("⚠️  Detected generic prompts. Regenerating...")
        elif image_prompts and not isinstance(image_prompts[0], str):
            needs_regeneration = True
            print("⚠️  Image prompts wrong format. Regenerating...")

        if needs_regeneration and hasattr(self._content, "generate_image_prompts"):
            image_prompts = self._content.generate_image_prompts(
                segments, articles, topic
            )
            script_data["image_prompts"] = image_prompts

        if not image_prompts:
            image_prompts = [
                "News broadcast opening scene",
                f"Breaking news: {articles[0]['title'][:40]}" if articles else "Breaking news headline",
                f"News story: {articles[1]['title'][:40]}" if len(articles) > 1 else "Important news update",
                f"Latest: {articles[2]['title'][:40]}" if len(articles) > 2 else "News coverage",
                "News broadcast closing scene",
            ]

        cleaned = []
        for p in image_prompts:
            if isinstance(p, str):
                s = re.sub(r"<[^>]+>", "", p)
                s = s.replace("&nbsp;", " ").replace("&amp;", "&")
                s = " ".join(s.split())
                if s.startswith("<img") or "src=" in s.lower() or len(s) < 10:
                    idx = len(cleaned)
                    s = f"Breaking news: {articles[idx]['title'][:50]}" if idx < len(articles) else "News broadcast scene"
                cleaned.append(s)
            else:
                cleaned.append(str(p))

        print(f"\n✅ Using {len(cleaned)} image prompts")
        return cleaned

    def _generate_audio(
        self,
        script_data: Dict[str, Any],
        output_filename: str,
    ) -> tuple:
        segments = script_data.get("segments", [])
        if segments:
            return self._tts.generate_segmented_audio(segments, output_filename)
        text = script_data.get("script", "")
        path = self._tts.generate_audio(text, output_filename)
        return (path, None)

    def _apply_timings_to_segments(
        self,
        script_data: Dict[str, Any],
        segment_timings: Optional[List[Dict[str, Any]]],
    ) -> None:
        if not segment_timings or "segments" not in script_data:
            return
        for i, timing in enumerate(segment_timings):
            if i < len(script_data["segments"]):
                script_data["segments"][i]["start_time"] = timing["start_time"]
                script_data["segments"][i]["duration"] = timing["duration"]

    def _do_upload(self, video_path: str, title: str) -> None:
        try:
            print("\n" + "=" * 60)
            print("📤 Uploading to YouTube...")
            print("=" * 60)
            result = self._uploader.upload_video(
                video_path=video_path,
                title=title,
                description=f"📰 {title}\n\nStay informed with the latest news updates!\n\n#News #BreakingNews #NewsUpdate #YouTubeShorts\n\nGenerated automatically with AI news automation.",
                tags=["news", "breaking news", "news update", "youtube shorts", "ai news"],
                category_id=self._category_id,
                privacy_status=self._privacy_status,
            )
            if result:
                print(f"\n🎉 Video published successfully!\n   Watch it here: {result.get('url', '')}")
            else:
                print("\n⚠️  YouTube upload failed, but video is saved locally")
        except Exception as e:
            print(f"\n⚠️  Error uploading to YouTube: {e}\n   Video is saved locally")
