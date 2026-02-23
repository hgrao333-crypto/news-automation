# API Keys Guide

This document explains which APIs require keys and how to obtain them.

## ✅ APIs That Require Keys

### 1. **NewsAPI** (Optional but Recommended)
- **Website**: https://newsapi.org
- **Free Tier**: Yes, 100 requests/day
- **Login Required**: Yes, you need to create a free account
- **How to Get**:
  1. Go to https://newsapi.org/register
  2. Sign up with email (free)
  3. Get your API key from the dashboard
  4. Add to `.env` file: `NEWS_API_KEY=your_key_here`
- **What it does**: Provides access to news articles from major sources
- **Note**: Without this key, the system will only use RSS feeds (which is still fine, but you'll get fewer articles)

### 2. **ElevenLabs** (Optional - for TTS)
- **Website**: https://elevenlabs.io
- **Free Tier**: Yes, limited characters/month
- **Login Required**: Yes, you need to create an account
- **How to Get**:
  1. Go to https://elevenlabs.io
  2. Sign up (free tier available)
  3. Get API key from your account settings
  4. Add to `.env` file: `ELEVENLABS_API_KEY=your_key_here`
- **What it does**: High-quality text-to-speech (better than free alternatives)
- **Note**: The system falls back to Edge-TTS (free, no key needed) if ElevenLabs is not available

### 3. **Imagine Art API** (Already Configured)
- **Status**: Already has a token in the code
- **No action needed**: The token is already set in `config.py`

## ❌ APIs That DON'T Require Keys

### RSS Feeds (60+ sources)
- **No login required**: All RSS feeds are public
- **No API keys needed**: These are free public feeds
- **Sources include**: BBC, CNN, Reuters, NPR, Guardian, Al Jazeera, and 50+ more

## Summary

**Minimum Setup** (works without any keys):
- ✅ RSS feeds work without any keys
- ✅ Edge-TTS works without any keys
- ✅ Ollama works locally without any keys

**Recommended Setup** (better results):
- ✅ **NewsAPI key** (free): Get 200-500 articles instead of just RSS feeds
  - Sign up at: https://newsapi.org/register
  - Free tier: 100 requests/day (plenty for daily use)
- ✅ **ElevenLabs key** (optional): Better TTS quality
  - Sign up at: https://elevenlabs.io
  - Free tier available

## Current Status

Based on your `config.py`:
- ✅ Imagine Art API: Already configured
- ⚠️ NewsAPI: Check if `NEWS_API_KEY` is set in `.env`
- ⚠️ ElevenLabs: Check if `ELEVENLABS_API_KEY` is set in `.env`

**The system will work without NewsAPI and ElevenLabs keys**, but you'll get:
- Fewer articles (RSS only, but we have 60+ feeds now)
- Lower quality TTS (Edge-TTS instead of ElevenLabs)

