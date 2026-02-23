#!/usr/bin/env python3
"""
Must-Know Today - Generate videos for ALL audiences (young, middle_age, old)
Dynamically determines story count based on major/hot topics present
"""

import argparse
from datetime import datetime
import os
import time
from news_fetcher import NewsFetcher
from content_generator import ContentGenerator
from image_generator import ImageGenerator
from tts_generator import TTSGenerator
from video_generator import VideoGenerator
from youtube_uploader import YouTubeUploader
from config import NEWS_API_KEY, YOUTUBE_AUTO_UPLOAD, YOUTUBE_PRIVACY_STATUS, YOUTUBE_CATEGORY_ID, CONTENT_STYLE

def generate_must_know_video_for_audience(target_age_group: str = "young", story_count: int = None, content_style: str = None, pre_fetched_articles: list = None):
    """
    Generate 'Must-Know Today' video focusing on practical, daily-life news
    
    Args:
        target_age_group: "young", "middle_age", or "old"
        story_count: Number of stories to cover (should be provided when called from all-audiences script)
        content_style: "newsy" (traditional news format) or "social" (social media native format). Defaults to config value.
        pre_fetched_articles: Optional pre-fetched articles (used when generating for all audiences)
    
    Returns:
        Path to generated video, or None if failed
    """
    # Use config default if not provided
    if content_style is None:
        content_style = CONTENT_STYLE
    
    print("=" * 60)
    print(f"Generating 'Must-Know Today' Video")
    print(f"Target Audience: {target_age_group.upper()}")
    print(f"Content Style: {content_style.upper()}")
    print(f"Stories: {story_count}")
    print("=" * 60)
    
    # Step 1: Use pre-fetched articles or fetch new ones
    if pre_fetched_articles:
        all_articles = pre_fetched_articles
        print(f"\n[1/6] Using pre-fetched articles ({len(all_articles)} articles)")
    else:
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
    
    # Step 2: Analyze and select must-know news
    print(f"\n[2/6] Analyzing news for practical relevance to {target_age_group}...")
    generator = ContentGenerator()
    articles = generator.analyze_and_select_must_know_news(
        all_articles, 
        select_count=story_count,  # Use provided count (determined once for all audiences)
        target_age_group=target_age_group,
        skip_deduplication=True  # Skip deduplication when using Gemini
    )
    actual_story_count = len(articles)  # Should match story_count
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

def generate_all_audiences(story_count: int = None, content_style: str = None, upload: bool = False, single_video: bool = False):
    """
    Generate 'Must-Know Today' videos for all age groups
    
    Args:
        story_count: Number of stories to cover. If None, dynamically determined ONCE for all audiences.
        content_style: "newsy" or "social". If None, uses config default.
        upload: Whether to upload to YouTube
        single_video: If True, generate ONE video with neutral language for all audiences. If False, generate separate videos for each age group.
    """
    if single_video:
        # Generate ONE video with neutral language for all audiences
        print("=" * 80)
        print("GENERATING SINGLE VIDEO FOR ALL AUDIENCES")
        print("=" * 80)
        print("Language: Neutral, professional (consumable by all age groups)")
        if story_count is None:
            print("Story Count: Auto-determined (based on major/hot topics)")
        else:
            print(f"Story Count: {story_count}")
        print(f"Content Style: {content_style or CONTENT_STYLE}")
        print("=" * 80)
        
        # Override auto-upload if upload flag is provided
        if upload:
            os.environ['YOUTUBE_AUTO_UPLOAD'] = 'true'
        
        # Step 1: Fetch news
        print("\n[1/6] Fetching today's news...")
        print("  🇮🇳 Using Gemini with Google Search for Indian news...")
        # Use Gemini with Google Search to get today's essential news
        fetcher = NewsFetcher(news_api_key=NEWS_API_KEY, country="in", use_gemini=True)
        all_articles = fetcher.fetch_today_news(limit=100)
        if all_articles is None:
            all_articles = []
        print(f"  ✅ Found {len(all_articles)} articles")
        
        if not all_articles:
            print("❌ No articles found. Exiting.")
            return {}
        
        # Step 2: Determine story count (if not provided)
        if story_count is None:
            # When using Gemini, use all articles it returned (already curated, max 10)
            story_count = len(all_articles)
            print(f"\n[2/6] Using all {story_count} articles from Gemini (already curated)")
            print(f"  ✅ Gemini already selected the most important news, using all {story_count} stories")
        
        # Step 3: Generate single video with neutral language
        print("\n[3/6] Generating video with neutral language for all audiences...")
        video_path = generate_must_know_video_for_audience(
            target_age_group="all_audiences",  # Special age group for neutral language
            story_count=story_count,
            content_style=content_style,
            pre_fetched_articles=all_articles
        )
        
        if video_path:
            print(f"\n✅ Success! Video saved to: {video_path}")
            return {"all_audiences": {"status": "success", "path": video_path}}
        else:
            print("\n❌ Failed to create video.")
            return {"all_audiences": {"status": "failed", "path": None}}
    
    # Original behavior: Generate separate videos for each age group
    age_groups = ["young", "middle_age", "old"]
    results = {}
    
    print("=" * 80)
    print("GENERATING SEPARATE VIDEOS FOR EACH AGE GROUP")
    print("=" * 80)
    print(f"Age Groups: {', '.join(age_groups)}")
    if story_count is None:
        print("Story Count: Auto-determined ONCE for all audiences (based on major/hot topics)")
    else:
        print(f"Story Count: {story_count} (same for all audiences)")
    print(f"Content Style: {content_style or CONTENT_STYLE}")
    print("=" * 80)
    
    # Override auto-upload if upload flag is provided
    if upload:
        os.environ['YOUTUBE_AUTO_UPLOAD'] = 'true'
    
    # Step 1: Fetch news once for all audiences
    print("\n[PRE-STEP] Fetching today's news for all audiences...")
    print("  🇮🇳 Using Gemini with Google Search for Indian news...")
    fetcher = NewsFetcher(news_api_key=NEWS_API_KEY, country="in", use_gemini=True)
    all_articles = fetcher.fetch_today_news(limit=100)
    if all_articles is None:
        all_articles = []
    print(f"  ✅ Found {len(all_articles)} articles")
    
    if not all_articles:
        print("❌ No articles found. Exiting.")
        return results
    
    # Step 2: Determine story count ONCE for all audiences (if not provided)
    if story_count is None:
        # When using Gemini, use all articles it returned (already curated, max 10)
        story_count = len(all_articles)
        print(f"\n[PRE-STEP] Using all {story_count} articles from Gemini (already curated)")
        print(f"  ✅ Gemini already selected the most important news, using all {story_count} stories for ALL audiences")
    
    # Step 3: Generate videos for each age group using the SAME story count
    for i, age_group in enumerate(age_groups, 1):
        print("\n" + "=" * 80)
        print(f"PROCESSING {i}/{len(age_groups)}: {age_group.upper()} (using {story_count} stories)")
        print("=" * 80)
        
        try:
            # Pass the pre-fetched articles and determined story count
            video_path = generate_must_know_video_for_audience(
                target_age_group=age_group,
                story_count=story_count,
                content_style=content_style,
                pre_fetched_articles=all_articles  # Use pre-fetched articles
            )
            
            if video_path:
                results[age_group] = {"status": "success", "path": video_path}
                print(f"\n✅ {age_group.upper()}: Success - {video_path}")
            else:
                results[age_group] = {"status": "failed", "path": None}
                print(f"\n❌ {age_group.upper()}: Failed")
        
        except Exception as e:
            results[age_group] = {"status": "error", "error": str(e)}
            print(f"\n❌ {age_group.upper()}: Error - {e}")
        
        # Add delay between generations to avoid rate limiting
        if i < len(age_groups):
            print("\n⏳ Waiting 5 seconds before next generation...")
            time.sleep(5)
    
    # Summary
    print("\n" + "=" * 80)
    print("GENERATION SUMMARY")
    print("=" * 80)
    for age_group, result in results.items():
        status = result.get("status", "unknown")
        if status == "success":
            print(f"✅ {age_group.upper()}: {result.get('path', 'N/A')}")
        elif status == "failed":
            print(f"❌ {age_group.upper()}: Generation failed")
        else:
            print(f"⚠️  {age_group.upper()}: {result.get('error', 'Unknown error')}")
    print("=" * 80)
    
    return results

def main():
    parser = argparse.ArgumentParser(
        description='Generate "Must-Know Today" videos for ALL audiences (young, middle_age, old)'
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
        help='Upload videos to YouTube after generation'
    )
    parser.add_argument(
        '--style',
        choices=['newsy', 'social'],
        default=None,
        help='Content style: newsy (traditional news format) or social (social media native format). Defaults to CONTENT_STYLE config value.'
    )
    parser.add_argument(
        '--single',
        action='store_true',
        help='Generate ONE video with neutral language for all audiences (instead of separate videos for each age group)'
    )
    
    args = parser.parse_args()
    
    generate_all_audiences(
        story_count=args.stories,
        content_style=args.style,
        upload=args.upload,
        single_video=args.single
    )

if __name__ == "__main__":
    main()

