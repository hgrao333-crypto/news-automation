#!/usr/bin/env python3
"""
Test script to generate "Must-Know Today" content scripts (text only, no video)
Tests all 3 age groups: young, middle_age, old
"""

import argparse
import json
from datetime import datetime
from news_fetcher import NewsFetcher
from content_generator import ContentGenerator
from config import NEWS_API_KEY

def test_age_group(target_age_group: str, story_count: int = 4):
    """
    Test script generation for a specific age group
    
    Args:
        target_age_group: "young", "middle_age", or "old"
        story_count: Number of stories to cover
    """
    print("=" * 80)
    print(f"TESTING: Must-Know Today Script Generator")
    print(f"Age Group: {target_age_group.upper()}")
    print(f"Stories: {story_count}")
    print("=" * 80)
    
    # Step 1: Fetch news
    print("\n[1/3] Fetching today's news...")
    print("  🇮🇳 Using Indian news sources...")
    fetcher = NewsFetcher(news_api_key=NEWS_API_KEY, country="in")
    
    all_articles = fetcher.fetch_today_news(limit=100)  # Fetch more for better selection
    print(f"✅ Found {len(all_articles)} articles")
    
    if not all_articles:
        print("❌ No articles found. Exiting.")
        return None
    
    # Step 2: Analyze and select must-know news
    print(f"\n[2/3] Analyzing news for {target_age_group} audience...")
    generator = ContentGenerator()
    articles = generator.analyze_and_select_must_know_news(
        all_articles, 
        select_count=story_count, 
        target_age_group=target_age_group
    )
    print(f"✅ Selected {len(articles)} must-know stories:")
    for i, article in enumerate(articles, 1):
        print(f"  {i}. {article['title'][:70]}")
    
    # Step 3: Generate content script
    print(f"\n[3/3] Generating engaging script for {target_age_group}...")
    script_data = generator.generate_must_know_today(
        articles, 
        target_age_group=target_age_group,
        story_count=story_count
    )
    
    # Display results
    print("\n" + "=" * 80)
    print("GENERATED SCRIPT")
    print("=" * 80)
    
    print(f"\n📺 TITLE:")
    print(f"   {script_data.get('title', 'Untitled')}")
    
    print(f"\n📝 FULL SCRIPT ({len(script_data.get('script', ''))} characters):")
    print("-" * 80)
    print(script_data.get('script', ''))
    print("-" * 80)
    
    print(f"\n🎬 SEGMENTS BREAKDOWN:")
    segments = script_data.get('segments', [])
    total_duration = 0
    for i, segment in enumerate(segments, 1):
        seg_type = segment.get('type', 'unknown')
        text = segment.get('text', '')
        duration = segment.get('duration', 0)
        start_time = segment.get('start_time', 0)
        total_duration += duration
        
        print(f"\n  Segment {i} ({seg_type.upper()}):")
        print(f"    Time: {start_time:.1f}s - {start_time + duration:.1f}s ({duration}s)")
        print(f"    Text: {text}")
        print(f"    Word count: {len(text.split())} words")
    
    print(f"\n⏱️  TOTAL DURATION: {total_duration:.1f} seconds")
    
    print(f"\n🖼️  IMAGE PROMPTS ({len(script_data.get('image_prompts', []))} prompts):")
    for i, prompt in enumerate(script_data.get('image_prompts', []), 1):
        print(f"  {i}. {prompt[:100]}...")
    
    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"test_output_must_know_{target_age_group}_{timestamp}.json"
    
    output_data = {
        "age_group": target_age_group,
        "story_count": story_count,
        "generated_at": datetime.now().isoformat(),
        "title": script_data.get('title'),
        "full_script": script_data.get('script'),
        "segments": segments,
        "image_prompts": script_data.get('image_prompts', []),
        "selected_articles": [
            {
                "title": a.get('title'),
                "description": a.get('description', '')[:200]
            }
            for a in articles
        ]
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Saved to: {output_file}")
    
    return script_data

def test_all_age_groups(story_count: int = 4):
    """Test all 3 age groups"""
    print("\n" + "=" * 80)
    print("TESTING ALL AGE GROUPS")
    print("=" * 80)
    
    age_groups = ["young", "middle_age", "old"]
    results = {}
    
    for age_group in age_groups:
        print(f"\n\n{'='*80}")
        print(f"TESTING: {age_group.upper()}")
        print(f"{'='*80}\n")
        
        try:
            result = test_age_group(age_group, story_count)
            results[age_group] = result
        except Exception as e:
            print(f"❌ Error testing {age_group}: {e}")
            results[age_group] = None
        
        print("\n" + "-" * 80)
        print("Press Enter to continue to next age group...")
        input()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for age_group, result in results.items():
        if result:
            title = result.get('title', 'N/A')
            segments = len(result.get('segments', []))
            print(f"✅ {age_group.upper()}: {title} ({segments} segments)")
        else:
            print(f"❌ {age_group.upper()}: Failed")
    
    return results

def main():
    parser = argparse.ArgumentParser(
        description='Test "Must-Know Today" script generation (text only, no video)'
    )
    parser.add_argument(
        '--age-group',
        choices=['young', 'middle_age', 'old', 'all'],
        default='all',
        help='Age group to test: young (18-30), middle_age (30-55), old (55+), or all'
    )
    parser.add_argument(
        '--stories',
        type=int,
        default=4,
        help='Number of stories to cover (default: 4)'
    )
    
    args = parser.parse_args()
    
    if args.age_group == 'all':
        test_all_age_groups(args.stories)
    else:
        test_age_group(args.age_group, args.stories)

if __name__ == "__main__":
    main()

