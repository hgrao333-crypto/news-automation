#!/usr/bin/env python3
"""
Must-Know Today - Generate videos focusing on news that affects daily life
Targets specific age groups: students, professionals, or general audience
"""

import argparse
from datetime import datetime
import os
from news_fetcher import NewsFetcher
from content_generator import ContentGenerator
from image_generator import ImageGenerator
from tts_generator import TTSGenerator
from video_generator import VideoGenerator
from youtube_uploader import YouTubeUploader
from config import NEWS_API_KEY, YOUTUBE_AUTO_UPLOAD, YOUTUBE_PRIVACY_STATUS, YOUTUBE_CATEGORY_ID, CONTENT_STYLE

def generate_must_know_video(target_age_group: str = "young", story_count: int = None, content_style: str = None):
    """
    Generate 'Must-Know Today' video focusing on practical, daily-life news
    
    Args:
        target_age_group: "young", "middle_age", or "old"
        story_count: Number of stories to cover. If None, dynamically determined based on major/hot topics.
        content_style: "newsy" (traditional news format) or "social" (social media native format). Defaults to config value.
    """
    # Use config default if not provided
    if content_style is None:
        content_style = CONTENT_STYLE
    
    print("=" * 60)
    print(f"Generating 'Must-Know Today' Video")
    print(f"Target Audience: {target_age_group.upper()}")
    print(f"Content Style: {content_style.upper()}")
    if story_count is None:
        print(f"Stories: Auto-determined (based on major/hot topics)")
    else:
        print(f"Stories: {story_count}")
    print("=" * 60)
    
    # Step 1: Fetch news
    print("\n[1/6] Fetching today's news...")
    print("  🇮🇳 Using Gemini with Google Search for Indian news...")
    # Use Gemini with Google Search to get today's essential news
    fetcher = NewsFetcher(news_api_key=NEWS_API_KEY, country="in", use_gemini=True)  # India, with Gemini
    
    all_articles = fetcher.fetch_today_news(limit=100)  # Fetch more for better selection
    if all_articles is None:
        all_articles = []
    print(f"Found {len(all_articles)} articles")
    
    if not all_articles:
        print("No articles found. Exiting.")
        return None
    
    # When using Gemini, use all articles it returned (already curated, max 10)
    if story_count is None:
        story_count = len(all_articles)
        print(f"  ✅ Using all {story_count} articles from Gemini (already curated)")
    
    # Step 2: Analyze and select must-know news
    print(f"\n[2/6] Analyzing news for practical relevance to {target_age_group}...")
    generator = ContentGenerator()
    articles = generator.analyze_and_select_must_know_news(
        all_articles, 
        select_count=story_count,  # Use all Gemini articles
        target_age_group=target_age_group,
        skip_deduplication=True  # Skip deduplication when using Gemini
    )
    actual_story_count = len(articles)  # Use actual count determined
    print(f"Selected {actual_story_count} must-know stories:")
    for i, article in enumerate(articles, 1):
        print(f"  {i}. {article['title'][:60]}")
    
    # Step 3: Generate content script
    print("\n[3/6] Generating content script with practical context...")
    script_data = generator.generate_must_know_today(
        articles, 
        target_age_group=target_age_group,
        story_count=actual_story_count,  # Use actual count
        content_style=content_style
    )
    print(f"Title: {script_data.get('title', 'Untitled')}")
    print(f"Total segments: {len(script_data.get('segments', []))}")
    
    # Display segments
    segments = script_data.get('segments', [])
    for i, segment in enumerate(segments):
        segment_type = segment.get('type', 'story')
        segment_text = segment.get('text', '')
        duration = segment.get('duration', 0)
        print(f"  Segment {i+1} ({segment_type}, {duration}s): {segment_text[:70]}...")
    
    # Step 4: Generate images
    print("\n[4/6] Generating images...")
    image_gen = ImageGenerator()
    image_prompts = script_data.get('image_prompts', [])
    
    # Filter out opening segment from image prompts (it uses fixed opening image)
    # Opening is typically first segment with type="opening" and no story_index
    filtered_prompts = []
    for i, prompt in enumerate(image_prompts):
        # Skip opening prompt (first one, or if it mentions opening)
        if i == 0 and any(word in str(prompt).lower() for word in ['opening', 'must know today']):
            print(f"  ⏭️  Skipping opening image prompt (uses fixed opening image)")
            continue
        filtered_prompts.append(prompt)
    
    # Clean prompts
    import re
    cleaned_prompts = []
    for p in filtered_prompts:
        if isinstance(p, str):
            cleaned = re.sub(r'<[^>]+>', '', p)
            cleaned = cleaned.replace('&nbsp;', ' ').replace('&amp;', '&')
            cleaned = cleaned.replace('&lt;', '<').replace('&gt;', '>')
            cleaned = cleaned.replace('&quot;', '"').replace('&#39;', "'")
            cleaned = ' '.join(cleaned.split())
            if not cleaned.startswith('<img') and 'src=' not in cleaned.lower() and len(cleaned) >= 10:
                cleaned_prompts.append(cleaned)
            else:
                # Fallback
                cleaned_prompts.append(f"Visual representation of important news story")
        else:
            cleaned_prompts.append(str(p))
    
    # We need images for: stories only (not opening, not closing)
    # Count story segments (segments with story_index)
    story_segments = [s for s in segments if s.get('story_index') is not None]
    expected_images = len(story_segments)
    
    # Ensure we have enough prompts for story segments
    if len(cleaned_prompts) < expected_images:
        print(f"  ⚠️  Only {len(cleaned_prompts)} prompts for {expected_images} story segments, filling missing...")
        while len(cleaned_prompts) < expected_images:
            cleaned_prompts.append("Visual representation of important news story")
    
    # Only generate images for story segments (not opening/closing)
    print(f"\n✅ Generating {len(cleaned_prompts)} images for {expected_images} story segments")
    image_paths = image_gen.generate_images_for_segments(cleaned_prompts[:expected_images])
    print(f"✅ Generated {len(image_paths)} images")
    
    # Step 5: Generate TTS audio
    print("\n[5/6] Generating text-to-speech audio...")
    tts = TTSGenerator()
    segments = script_data.get('segments', [])
    
    if segments:
        audio_path, segment_timings = tts.generate_segmented_audio(segments, "must_know_audio.mp3")
        # Update script_data with actual timings
        for i, timing in enumerate(segment_timings):
            if i < len(script_data['segments']):
                script_data['segments'][i]['start_time'] = timing['start_time']
                script_data['segments'][i]['duration'] = timing['duration']
    else:
        script_text = script_data.get('script', '')
        audio_path = tts.generate_audio(script_text, "must_know_audio.mp3")
        segment_timings = None
    
    if not audio_path:
        print("Failed to generate audio. Exiting.")
        return None
    
    # Step 6: Create video
    print("\n[6/6] Creating final video...")
    video_gen = VideoGenerator()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_group = target_age_group.replace(' ', '_')
    output_filename = f"must_know_{safe_group}_{timestamp}.mp4"
    video_path = video_gen.create_video(image_paths, audio_path, script_data, output_filename, segment_timings)
    
    if video_path:
        print(f"\n✅ Success! Video saved to: {video_path}")
        
        # Optional: Upload to YouTube
        upload_enabled = YOUTUBE_AUTO_UPLOAD or os.getenv('YOUTUBE_AUTO_UPLOAD', 'false').lower() == 'true'
        if upload_enabled:
            upload_to_youtube(video_path, script_data.get('title', 'Must-Know Today'))
        
        return video_path
    else:
        print("\n❌ Failed to create video.")
        return None

def upload_to_youtube(video_path: str, title: str, description: str = "", tags: list = None):
    """Upload video to YouTube"""
    try:
        print("\n" + "=" * 60)
        print("📤 Uploading to YouTube...")
        print("=" * 60)
        
        uploader = YouTubeUploader()
        
        if not description:
            description = f"""📰 {title}

Stay informed with news that affects your daily life, work, and future!

#News #MustKnow #DailyNews #NewsUpdate #YouTubeShorts #IndiaNews

Generated automatically with AI news automation."""
        
        if not tags:
            tags = ["news", "must know", "daily news", "news update", "youtube shorts", "india news", "practical news"]
        
        result = uploader.upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            category_id=YOUTUBE_CATEGORY_ID,
            privacy_status=YOUTUBE_PRIVACY_STATUS
        )
        
        if result:
            print(f"\n🎉 Video published successfully!")
            print(f"   Watch it here: {result['url']}")
            return result
        else:
            print("\n⚠️  YouTube upload failed, but video is saved locally")
            return None
            
    except Exception as e:
        print(f"\n⚠️  Error uploading to YouTube: {e}")
        print("   Video is saved locally and can be uploaded manually")
        return None

def main():
    parser = argparse.ArgumentParser(
        description='Generate "Must-Know Today" videos focusing on practical, daily-life news'
    )
    parser.add_argument(
        '--age-group',
        choices=['young', 'middle_age', 'old'],
        default='young',
        help='Target age group: young (18-30), middle_age (30-55), or old (55+)'
    )
    parser.add_argument(
        '--stories',
        type=int,
        default=None,
        help='Number of stories to cover. If not specified, automatically determined based on major/hot topics present (3-8 stories).'
    )
    parser.add_argument(
        '--upload',
        action='store_true',
        help='Upload video to YouTube after generation'
    )
    parser.add_argument(
        '--style',
        choices=['newsy', 'social'],
        default=None,
        help='Content style: newsy (traditional news format) or social (social media native format). Defaults to CONTENT_STYLE config value.'
    )
    
    args = parser.parse_args()
    
    # Override auto-upload if --upload flag is provided
    if args.upload:
        os.environ['YOUTUBE_AUTO_UPLOAD'] = 'true'
    
    generate_must_know_video(
        target_age_group=args.age_group,
        story_count=args.stories,
        content_style=args.style if args.style else None  # None will use config default
    )

if __name__ == "__main__":
    main()

