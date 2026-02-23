#!/usr/bin/env python3
"""
Test ElevenLabs v3 model with [Indian English] accent tag
This uses v3's accent emulation feature to get Indian accent pronunciation
"""

import os
import sys

# Ensure temp directory exists
if not os.path.exists("temp"):
    os.makedirs("temp")

from tts_generator import TTSGenerator
from config import ELEVENLABS_MODEL_ID, ELEVENLABS_VOICE_ID

print("=" * 70)
print("Testing ElevenLabs v3 with Indian English Accent Emulation")
print("=" * 70)
print(f"\n📋 Current Configuration:")
print(f"   Model: {ELEVENLABS_MODEL_ID}")
print(f"   Voice ID: {ELEVENLABS_VOICE_ID}")
print(f"\n💡 Note: v3 model automatically adds [Indian English] tag")
print("   This emulates Indian accent pronunciation with any voice!")
print("\n" + "=" * 70)

# Test text with Indian names
test_text = """
Today, Chief Minister Siddaramaiah and Deputy Chief Minister Shivakumar 
addressed the media in Bangalore, Karnataka.

Prime Minister Narendra Modi is expected to visit Karnataka next week. 
The latest tech breakthrough from Chennai is making waves across India.

Priya Sharma, a scientist from Hyderabad, received a prestigious award. 
Deepak Patel, a prominent businessman from Mumbai, announced new investments 
in Maharashtra.

The festival of Diwali was celebrated with great fervor across Delhi, 
Pune, and other major cities. Rajesh Kumar from Tamil Nadu shared his 
thoughts on the economic developments.
"""

print("\n🎤 Generating audio with Indian names...")
print("   This will use v3 model with [Indian English] accent tag")
print("   to improve pronunciation of Indian names and places.\n")

tts = TTSGenerator()

output_path = tts.generate_audio(test_text, "test_v3_indian_accent.mp3")

if output_path:
    print(f"\n✅ Audio generated successfully!")
    print(f"   File: {output_path}")
    print(f"\n🎧 Please listen to verify:")
    print(f"   - Indian names (Siddaramaiah, Shivakumar, Narendra Modi)")
    print(f"   - Indian cities (Bangalore, Chennai, Hyderabad, Mumbai)")
    print(f"   - Indian states (Karnataka, Maharashtra, Tamil Nadu)")
    print(f"   - Indian accent pronunciation")
    print(f"\n💡 If pronunciation is good, you're all set!")
    print(f"   If not, try:")
    print(f"   1. Use a different voice (run: python3 find_indian_voices.py)")
    print(f"   2. Switch to Edge-TTS with Indian English voices (FREE)")
else:
    print("\n❌ Failed to generate audio. Check your ELEVENLABS_API_KEY")

