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
- Imagine Art API token (see `.env.example`)

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
   Copy `.env.example` to `.env` and fill in your keys (no secrets are committed).
   Required for full features: `IMAGINE_TOKEN`, and optionally `NEWS_API_KEY`, `GEMINI_API_KEY` or `OPENROUTER_API_KEY`, `ELEVENLABS_API_KEY`. Ollama works without keys.

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

## Project Structure (SOLID)

The codebase follows SOLID principles and a ports-and-adapters layout so you can plug in different news sources (e.g. real-time feed or an openclaw agent) without changing the core pipeline.

```
news-automation/
├── main.py                    # Entrypoint (delegates to pipeline)
├── config.py                  # Env-based configuration (no secrets in code)
├── requirements.txt
├── pyproject.toml             # Package metadata
├── .env.example               # Template for .env (copy to .env)
├── src/news_automation/       # Main package
│   ├── domain/               # Models (Article, ScriptData, Segment)
│   ├── ports/                # Interfaces (INewsSource, IContentGenerator, …)
│   ├── adapters/             # Implementations wrapping existing modules
│   ├── application/          # VideoPipeline (orchestration, dependency injection)
│   └── cli.py                # CLI (python -m news_automation)
├── news_fetcher.py           # News (RSS/NewsAPI/Gemini) – used by adapter
├── content_generator.py      # Script/selection – used by adapter
├── image_generator.py
├── tts_generator.py
├── video_generator.py
├── youtube_uploader.py
├── output/                   # Generated videos
└── temp/                     # Temporary files
```

### Using a real-time feed or openclaw agent

The pipeline depends on **interfaces** (ports), not concrete classes. To drive videos from a real-time feed or another agent (e.g. openclaw):

1. Implement the `INewsSource` port: provide `fetch_today_news(limit, test_articles)` and `fetch_hot_topic(topic, limit)` returning the same article dict shape (e.g. `title`, `description`, `link`, `published`).
2. Build the pipeline with your adapter:  
   `pipeline = VideoPipeline(news_source=YourRealtimeNewsAdapter(), **default_adapters())`  
   (or use `default_adapters(news_source=YourRealtimeNewsAdapter())` and pass the rest as-is).

Other entry points (same pipeline, different formats): `single_story_viral.py`, `must_know_today.py`, `must_know_all_audiences.py`, `afternoon.py`, `extended_video_generator.py`. See **ARCHITECTURE.md** for the SOLID layout and how to plug in a custom news source.

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

- Indian RSS feeds are used by default; set `country` in the news adapter for others
- NewsAPI key is optional but recommended for better results
- Generated videos are saved in the `output/` directory
- Temporary files are stored in `temp/` directory

## Troubleshooting

- **Ollama connection error**: Make sure Ollama is running (`ollama serve`)
- **Image generation fails**: Check your Imagine Art API token
- **TTS errors**: Ensure internet connection for gTTS
- **Video generation issues**: Install ffmpeg (`brew install ffmpeg` on macOS)

