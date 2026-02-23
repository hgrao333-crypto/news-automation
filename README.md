# News Automation - AI-Generated YouTube Shorts

Automated system for generating 60-second news shorts for YouTube using AI-generated images, Ollama for content generation, and TTS for narration.

## Features

- **Two Niches:**
  1. **Today in 60 Seconds** - Daily news summary
  2. **Hot Topic** - Focused coverage on trending topics

- **AI-Powered Components:**
  - Text-to-Image generation via Imagine Art API
  - Content generation using local Ollama
  - Text-to-Speech narration
  - Automated video compilation

## Setup

### Prerequisites

- Python 3.8+
- Ollama installed and running locally (default: http://localhost:11434)
- Imagine Art API token (already configured)

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables (optional):
Create a `.env` file with:
```
IMAGINE_TOKEN=Bearer vk-KocZ3f3P1qy2Z02tpH2Dn8ZTFHCDJJfCQGp8LPijSSta5a
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
NEWS_API_KEY=your_newsapi_key_here  # Optional, for better news fetching
```

3. Make sure Ollama is running:
```bash
ollama serve
```

4. Pull the Ollama model (if not already done):
```bash
ollama pull llama3.2
```

## Usage

### Generate "Today in 60 Seconds" video:
```bash
python main.py --type today
```

### Generate "Hot Topic" video:
```bash
python main.py --type topic --topic "artificial intelligence"
```

Or let it auto-detect a trending topic:
```bash
python main.py --type topic
```

## Project Structure

```
news-automation/
├── main.py                 # Main orchestration script
├── config.py              # Configuration settings
├── news_fetcher.py        # News fetching from RSS/NewsAPI
├── content_generator.py   # Ollama integration for script generation
├── image_generator.py     # Imagine Art API integration
├── tts_generator.py       # Text-to-speech generation
├── video_generator.py     # Video compilation
├── requirements.txt       # Python dependencies
├── output/                # Generated videos (created automatically)
└── temp/                  # Temporary files (created automatically)
```

## Workflow

1. **News Fetching**: Retrieves news from RSS feeds and NewsAPI
2. **Content Generation**: Uses Ollama to create engaging 60-second scripts
3. **Image Generation**: Creates visuals using Imagine Art API for each segment
4. **Audio Generation**: Converts script to speech using gTTS
5. **Video Compilation**: Combines images, audio, and text overlays into final video

## Configuration

Edit `config.py` to customize:
- Video dimensions (default: 1080x1920 for YouTube Shorts)
- Video duration (default: 60 seconds)
- FPS (default: 30)
- Ollama model and URL
- Output directories

## Notes

- The system uses RSS feeds by default (BBC, CNN, Reuters)
- NewsAPI key is optional but recommended for better results
- Generated videos are saved in the `output/` directory
- Temporary files are stored in `temp/` directory

## Troubleshooting

- **Ollama connection error**: Make sure Ollama is running (`ollama serve`)
- **Image generation fails**: Check your Imagine Art API token
- **TTS errors**: Ensure internet connection for gTTS
- **Video generation issues**: Install ffmpeg (`brew install ffmpeg` on macOS)

