import os
from dotenv import load_dotenv

# Fix huggingface/tokenizers parallelism warning (must be set before any tokenizer imports)
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')

load_dotenv()

# Imagine Art API Configuration
IMAGINE_TOKEN = os.getenv("IMAGINE_TOKEN", "Bearer vk-KocZ3f3P1qy2Z02tpH2Dn8ZTFHCDJJfCQGp8LPijSSta5a")
IMAGINE_API_URL = "https://api.vyro.ai/v2/image/generations"

# Ollama Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")  # Default to llama3.1:8b, will auto-detect if not available

# News API Configuration
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

# Video Configuration
VIDEO_DURATION = 60  # seconds
FPS = 30
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920  # Vertical format for YouTube Shorts (9:16)

# Extended Video Configuration (16:9 landscape)
EXTENDED_VIDEO_WIDTH = 1920
EXTENDED_VIDEO_HEIGHT = 1080  # Landscape format for long videos (16:9)

# YouTube Upload Configuration
YOUTUBE_CREDENTIALS_FILE = os.getenv("YOUTUBE_CREDENTIALS_FILE", "client_secret.json")
YOUTUBE_TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", "token.pickle")
YOUTUBE_AUTO_UPLOAD = os.getenv("YOUTUBE_AUTO_UPLOAD", "false").lower() == "true"
YOUTUBE_PRIVACY_STATUS = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")  # public, unlisted, private
YOUTUBE_CATEGORY_ID = os.getenv("YOUTUBE_CATEGORY_ID", "22")  # 22 = People & Blogs

# TTS Configuration
# Priority order: ElevenLabs > Edge-TTS > gTTS
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "sk_ccf16b88610c35baec3b2d48b401cc692292e5ca5f5e7f25")

# ElevenLabs Voice Selection for Indian Names
# RECOMMENDED for Indian names (best pronunciation):
# - "pNInz6obpgDQGcFmaJgB" (Adam) - Male, deep, clear, handles Indian names well - RECOMMENDED
# - "ErXwobaYiN019PkySvjV" (Antoni) - Male, clear, professional, good for names
# - "21m00Tcm4TlvDq8ikWAM" (Rachel) - Female, professional, clear - CURRENT DEFAULT
# - "ThT5KcBeYPX3keUQqHPh" (Domi) - Energetic, clear pronunciation
# 
# Other good ElevenLabs voices for news:
# - "EXAVITQu4vr4xnSDxMaL" (Bella) - Warm, professional
# - "VR6AewLTigWG4xSOukaG" (Arnold) - Male, professional
#
# NOTE: For BEST Indian name pronunciation, consider using Edge-TTS with Indian English:
# - en-IN-NeerjaNeural (Female) - Specifically trained for Indian English names
# - en-IN-PrabhatNeural (Male) - Specifically trained for Indian English names
# These are FREE and handle Indian names excellently!

ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "2zRM7PkgwBPiau2jvVXc")  # User-selected voice for Indian names

# ElevenLabs Model Selection
# Available models for best Indian name pronunciation:
# - "eleven_turbo_v2_5" - Latest model (v3 equivalent), fast, high quality, best for Indian names - RECOMMENDED
# - "eleven_multilingual_v2" - Multilingual model, good for Indian names
# - "eleven_turbo_v2" - Fast, high quality
# - "eleven_monolingual_v1" - English only, very high quality
# - "eleven_multilingual_v1" - Older multilingual model
# NOTE: ElevenLabs v3 is typically accessed via "eleven_turbo_v2_5" or check latest API docs
# For v3 specifically, the model might be named "eleven_turbo_v2_5" or similar
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")  # v3 model, best for Indian names

TTS_USE_ELEVENLABS = os.getenv("TTS_USE_ELEVENLABS", "true").lower() == "true"  # Use ElevenLabs (best quality) by default
TTS_USE_EDGE_TTS = os.getenv("TTS_USE_EDGE_TTS", "true").lower() == "true"  # Use Edge-TTS as fallback
TTS_EDGE_VOICE = os.getenv("TTS_EDGE_VOICE", "en-IN-NeerjaNeural")  # Indian English, Female, Professional news anchor voice (best for Indian names)
# Edge-TTS options for Indian English (best for pronouncing Indian names):
# - "en-IN-NeerjaNeural" (Indian English, Female) - Professional, best for Indian names - RECOMMENDED
# - "en-IN-PrabhatNeural" (Indian English, Male) - Professional, best for Indian names
# Other Edge-TTS options:
# - "en-GB-SoniaNeural" (UK English, Female) - Professional
# - "en-US-AriaNeural" (US English, Female) - Professional
# - "en-GB-RyanNeural" (UK English, Male) - Professional
# - "en-US-GuyNeural" (US English, Male) - Professional

# Engagement Features Configuration
USE_HOOK_BASED_HEADLINES = os.getenv("USE_HOOK_BASED_HEADLINES", "true").lower() == "true"  # Enable hook-based headlines for better engagement
USE_CONTEXT_AWARE_OVERLAYS = os.getenv("USE_CONTEXT_AWARE_OVERLAYS", "true").lower() == "true"  # Enable context-aware visual overlays on images

# Content Style Configuration
CONTENT_STYLE = os.getenv("CONTENT_STYLE", "newsy").lower()  # "newsy" (traditional news) or "social" (social media native format)

# Output directories
OUTPUT_DIR = "output"
TEMP_DIR = "temp"

# Create directories if they don't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(os.path.join(TEMP_DIR, "opening"), exist_ok=True)
os.makedirs(os.path.join(TEMP_DIR, "closing"), exist_ok=True)

