# Architecture (SOLID)

This repo is structured so the **application layer** depends only on **abstractions (ports)**; **adapters** provide concrete implementations. That keeps the pipeline testable and lets you plug in new sources (e.g. real-time feed, openclaw agent) without changing core logic.

## Principles

- **Single Responsibility**: Each module has one reason to change (e.g. `NewsFetcher` only fetches; `VideoPipeline` only orchestrates).
- **Open/Closed**: Extend by new adapters (e.g. new `INewsSource`), not by editing pipeline or existing fetchers.
- **Liskov Substitution**: Any implementation of a port can replace another (e.g. RSS vs real-time `INewsSource`).
- **Interface Segregation**: Ports are small and focused (`INewsSource`, `IImageGenerator`, etc.).
- **Dependency Inversion**: `VideoPipeline` depends on `INewsSource`, `IContentGenerator`, …; it does not import `news_fetcher` or `content_generator` directly.

## Layers

| Layer        | Role |
|-------------|------|
| **Domain**  | Data shapes (e.g. `Article`, `ScriptData`, `Segment`) – dict-compatible. |
| **Ports**   | Abstract interfaces in `src/news_automation/ports/`. |
| **Adapters**| Implementations in `src/news_automation/adapters/` that wrap existing root-level modules. |
| **Application** | `VideoPipeline` in `src/news_automation/application/` – runs fetch → select → script → images → TTS → video → optional upload. |
| **CLI**     | `main.py` and `python -m news_automation` – parse args and run pipeline with default adapters. |

## Real-time feed / openclaw agent

To drive videos from a **real-time feed** or another agent (e.g. **openclaw**):

1. Implement **`INewsSource`** (see `src/news_automation/ports/interfaces.py`):
   - `fetch_today_news(limit, test_articles)` → list of article dicts (`title`, `description`, `link`, `published`).
   - `fetch_hot_topic(topic, limit)` → same shape.
2. Construct the pipeline with your adapter:

   ```python
   from news_automation.application.pipeline import VideoPipeline
   from news_automation.adapters import default_adapters

   adapters = default_adapters(news_source=YourRealtimeNewsAdapter())
   pipeline = VideoPipeline(**adapters, upload_after=False)
   pipeline.run_today_video()  # or run_topic_video(topic)
   ```

No changes to `VideoPipeline` or other adapters are required.

## Configuration

All secrets and environment-specific values come from **environment variables** (and optionally a `.env` file). See `.env.example` and `config.py`. No API keys or tokens are hardcoded.
