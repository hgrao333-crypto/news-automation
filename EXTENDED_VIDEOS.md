# Extended Video Generator - 10-Minute Deep-Dive Videos

## Overview

This is a **separate module** (`extended_video_generator.py`) that creates 10-minute extended videos for very hot topics like market crashes, major disasters, breaking news, etc. It does NOT modify any existing code.

## Features

### 🔥 Automatic Hot Topic Detection
- Scans news articles for very hot topics
- Scores topics based on keywords (market crash, crisis, emergency, etc.)
- Detects trending topics with multiple related articles
- Threshold-based detection (default: score ≥ 50)

### 📝 Extended Script Generation
- 10-minute (600 seconds) comprehensive scripts
- Structured format:
  - Introduction (30-45s)
  - 5-6 Main Sections (8-9 minutes total)
    - Section Overview
    - Key Points (detailed)
    - Analysis/Context
  - Conclusion (30-45s)
- Detailed, informative content
- Step-by-step coverage

### 🖼️ Comprehensive Image Generation
- Detailed image prompts (80-150 words each)
- Visual descriptions with composition, lighting, mood
- One image per segment
- Professional news broadcast style

### 🎬 Video Generation
- Full 10-minute videos
- Uses existing video generator (no modifications)
- Same quality and features as regular videos

## Usage

### Auto-Detect Hot Topics
```bash
source venv/bin/activate
python extended_video_generator.py auto
```

This will:
1. Fetch today's news
2. Detect very hot topics automatically
3. Generate extended 10-minute video if hot topic found

### Manual Topic Selection
```bash
python extended_video_generator.py topic "Market Crash"
```

This will:
1. Fetch extended news coverage for the topic
2. Generate 10-minute video

## Hot Topic Keywords

The system detects topics with keywords like:
- **Market/Economic**: market crash, economic crisis, recession, inflation surge
- **Disasters**: earthquake, tsunami, hurricane, pandemic, wildfire
- **Political**: election results, government collapse, war, conflict
- **Tech**: data breach, cyber attack, major outage
- **Social**: protest, riot, mass demonstration
- **Breaking**: breaking, urgent, alert, emergency, crisis

## Scoring System

Topics are scored based on:
- Keyword matches (5-10 points per keyword)
- Multiple related articles (up to 20 points)
- Recency (5-10 points)
- **Minimum score**: 50 (configurable)

## Output

Extended videos are saved as:
```
output/extended_<topic>_<timestamp>.mp4
```

## Integration

This module:
- ✅ Uses existing modules (NewsFetcher, ImageGenerator, TTSGenerator, VideoGenerator)
- ✅ Does NOT modify existing code
- ✅ Can run independently
- ✅ Can be integrated into main.py later if needed

## Example Workflow

1. **Detection**: Scans 50+ articles for hot topics
2. **Scoring**: Scores each topic based on keywords and relevance
3. **Selection**: Picks topic with score ≥ 50
4. **Extended Fetch**: Fetches 50+ articles about the topic
5. **Script Generation**: Creates detailed 10-minute script
6. **Image Generation**: Generates detailed visual prompts
7. **Video Creation**: Compiles 10-minute video

## Notes

- Extended videos require more processing time
- More images need to be generated (one per segment)
- Scripts are more detailed and comprehensive
- Uses same video quality settings as regular videos

