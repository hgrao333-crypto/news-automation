#!/usr/bin/env python3
"""
Single Story Viral - Generate 20-30 second viral videos for ONE high-impact story
Focus: Emotional, visual, relatable chaos, rage bait with heavy exaggeration
"""

# Import compatibility fix FIRST (before any packages that use importlib.metadata)
import compat_fix

import argparse
from datetime import datetime
import os
from news_fetcher import NewsFetcher
from content_generator import ContentGenerator
from image_generator import ImageGenerator
from tts_generator import TTSGenerator
from video_generator import VideoGenerator
from youtube_uploader import YouTubeUploader
from config import NEWS_API_KEY, YOUTUBE_AUTO_UPLOAD, YOUTUBE_PRIVACY_STATUS, YOUTUBE_CATEGORY_ID

def generate_single_story_viral(duration: int = 30, upload: bool = False):
    """
    Generate a 20-30 second viral video for ONE high-impact story
    
    Args:
        duration: Video duration in seconds (20-30, default 25)
        upload: Whether to upload to YouTube
    
    Returns:
        Path to generated video, or None if failed
    """
    print("=" * 80)
    print("GENERATING SINGLE-STORY VIRAL VIDEO")
    print("=" * 80)
    print(f"Duration: {duration} seconds")
    print(f"Style: Emotional, Visual, Relatable Chaos, Rage Bait")
    print("=" * 80)
    
    # Step 1: Fetch news using Gemini
    print("\n[1/6] Fetching today's news with Gemini...")
    print("  🇮🇳 Using Gemini with Google Search for Indian news...")
    fetcher = NewsFetcher(news_api_key=NEWS_API_KEY, country="in", use_gemini=True)
    all_articles = fetcher.fetch_today_news(limit=50)  # Fetch more for better selection
    if all_articles is None:
        all_articles = []
    print(f"  ✅ Found {len(all_articles)} articles")
    
    if not all_articles:
        print("❌ No articles found. Exiting.")
        return None
    
    # Step 2: Select the most viral story
    print("\n[2/6] Selecting most viral story (emotional, visual, relatable chaos, rage bait)...")
    generator = ContentGenerator()
    selected_article = generator.select_most_viral_story(all_articles)
    
    if not selected_article:
        print("❌ Could not select viral story. Exiting.")
        return None
    
    print(f"  ✅ Selected: {selected_article['title'][:70]}...")
    
    # Step 3: Generate exaggerated viral script
    print("\n[3/6] Generating exaggerated viral script...")
    script_data = generator.generate_single_story_viral(selected_article, duration=duration)
    
    print(f"  ✅ Title: {script_data.get('title', 'Untitled')}")
    print(f"  ✅ Segments: {len(script_data.get('segments', []))}")
    
    # Display script preview
    segments = script_data.get('segments', [])
    for i, segment in enumerate(segments):
        segment_type = segment.get('type', '')
        segment_text = segment.get('text', '')
        duration_sec = segment.get('duration', 0)
        print(f"    {i+1}. [{segment_type}, {duration_sec}s]: {segment_text[:60]}...")
    
    # Step 4: Generate multiple images (3-5 images for exaggeration)
    print("\n[4/6] Generating multiple exaggerated images...")
    image_gen = ImageGenerator()
    image_prompts = script_data.get('image_prompts', [])
    
    # Ensure we have at least 3 images
    if len(image_prompts) < 3:
        print(f"  ⚠️  Only {len(image_prompts)} image prompts, generating fallback prompts...")
        while len(image_prompts) < 3:
            image_prompts.append(f"Dramatic visual representation of {selected_article.get('title', 'news story')}")
    
    print(f"  📸 Generating {len(image_prompts)} images with exaggerated visuals...")
    image_paths = image_gen.generate_images_for_segments(image_prompts, aspect_ratio="9:16")
    print(f"  ✅ Generated {len(image_paths)} images")
    
    # Step 5: Generate TTS audio
    print("\n[5/6] Generating text-to-speech audio...")
    tts = TTSGenerator()
    
    if segments:
        audio_path, segment_timings = tts.generate_segmented_audio(segments, "viral_audio.mp3")
        # Update script_data with actual timings
        for i, timing in enumerate(segment_timings):
            if i < len(script_data['segments']):
                script_data['segments'][i]['start_time'] = timing['start_time']
                script_data['segments'][i]['duration'] = timing['duration']
    else:
        script_text = script_data.get('script', '')
        audio_path = tts.generate_audio(script_text, "viral_audio.mp3")
        segment_timings = None
    
    if not audio_path:
        print("❌ Failed to generate audio. Exiting.")
        return None
    
    # Step 6: Create video with heavy effects
    print("\n[6/6] Creating viral video with heavy effects and word-by-word subtitles...")
    video_gen = VideoGenerator()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"viral_story_{timestamp}.mp4"
    
    # For single story, we'll use multiple images and switch between them
    # Map images to segments: distribute images across story segments
    video_path = video_gen.create_video(
        image_paths, 
        audio_path, 
        script_data, 
        output_filename, 
        segment_timings,
        is_extended=False
    )
    
    if video_path:
        print(f"\n✅ Success! Viral video saved to: {video_path}")
        
        # Optional: Upload to YouTube
        if upload or YOUTUBE_AUTO_UPLOAD:
            upload_to_youtube(video_path, script_data.get('title', 'Viral News Story'))
        
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
            description = f"""🔥 {title}

This viral news story will shock you! Watch to see what happened and how it affects you.

Like and subscribe for more viral news that affects your daily life!

#ViralNews #BreakingNews #News #YouTubeShorts #IndiaNews #Trending

Generated automatically with AI news automation."""
        
        if not tags:
            tags = ["viral news", "breaking news", "trending", "youtube shorts", "india news", "viral", "shocking news"]
        
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
        description='Generate 20-30 second viral video for ONE high-impact news story'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=30,
        choices=[25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35],
        help='Video duration in seconds (25-35, default: 30) - includes facts segments'
    )
    parser.add_argument(
        '--upload',
        action='store_true',
        help='Upload video to YouTube after generation'
    )
    
    args = parser.parse_args()
    
    generate_single_story_viral(
        duration=args.duration,
        upload=args.upload
    )

if __name__ == "__main__":
    main()

