#!/usr/bin/env python3
"""
Generate script for Sri Lanka Tsunami video and suggest heading
"""
import sys
import os
from extended_video_generator import HotTopicDetector, ExtendedContentGenerator
from config import NEWS_API_KEY, CONTENT_STYLE

def get_tsunami_script():
    """Get script for Sri Lanka Tsunami topic"""
    print("=" * 60)
    print("Generating Script for Sri Lanka Tsunami Video")
    print("=" * 60)
    
    topic = "Sri Lanka Tsunami"
    
    # Fetch news about the topic
    detector = HotTopicDetector(news_api_key=NEWS_API_KEY)
    articles = detector.fetch_extended_news(topic, limit=50)
    
    if not articles:
        print("No articles found. Using sample data...")
        articles = [{
            "title": "Sri Lanka Tsunami Warning",
            "description": "Tsunami warning issued for Sri Lanka"
        }]
    
    print(f"\nFound {len(articles)} articles about {topic}")
    
    # Generate script
    ext_generator = ExtendedContentGenerator()
    script_data = ext_generator.generate_extended_script(
        topic=topic,
        articles=articles,
        duration=600,  # 10 minutes
        content_style=CONTENT_STYLE
    )
    
    # Print script
    print("\n" + "=" * 60)
    print("VIDEO SCRIPT")
    print("=" * 60)
    print(f"\nTitle: {script_data.get('title', 'Untitled')}")
    print(f"\nFull Script:\n")
    print(script_data.get('script', 'No script found'))
    
    print("\n" + "=" * 60)
    print("SEGMENTS")
    print("=" * 60)
    segments = script_data.get('segments', [])
    for i, segment in enumerate(segments, 1):
        print(f"\nSegment {i} ({segment.get('type', 'unknown')}):")
        print(f"  Duration: {segment.get('duration', 0):.1f}s")
        print(f"  Start: {segment.get('start_time', 0):.1f}s")
        print(f"  Text: {segment.get('text', '')[:200]}...")
    
    # Suggest headings
    print("\n" + "=" * 60)
    print("SUGGESTED HEADINGS")
    print("=" * 60)
    
    headings = [
        f"{script_data.get('title', 'Sri Lanka Tsunami - Complete Analysis')}",
        "Sri Lanka Tsunami: What You Need to Know - Complete 10-Minute Analysis",
        "Breaking: Sri Lanka Tsunami Warning - Full Coverage & Impact Analysis",
        "Sri Lanka Tsunami Alert: Complete Story, Impact, and What Happens Next",
        "The Sri Lanka Tsunami Story: From Warning to Impact - Full Deep Dive"
    ]
    
    for i, heading in enumerate(headings, 1):
        print(f"{i}. {heading}")
    
    # Save to file
    output_file = "temp/tsunami_script.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"Title: {script_data.get('title', 'Untitled')}\n\n")
        f.write("=" * 60 + "\n")
        f.write("FULL SCRIPT\n")
        f.write("=" * 60 + "\n\n")
        f.write(script_data.get('script', ''))
        f.write("\n\n" + "=" * 60 + "\n")
        f.write("SEGMENTS\n")
        f.write("=" * 60 + "\n\n")
        for i, segment in enumerate(segments, 1):
            f.write(f"Segment {i} ({segment.get('type', 'unknown')}):\n")
            f.write(f"  Duration: {segment.get('duration', 0):.1f}s\n")
            f.write(f"  Start: {segment.get('start_time', 0):.1f}s\n")
            f.write(f"  Text: {segment.get('text', '')}\n\n")
    
    print(f"\n✅ Script saved to: {output_file}")
    
    return script_data

if __name__ == "__main__":
    get_tsunami_script()

