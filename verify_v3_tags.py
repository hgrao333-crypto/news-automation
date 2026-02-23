#!/usr/bin/env python3
"""
Verify that [Indian English] tag is being added for v3 model
"""

from tts_generator import TTSGenerator
from config import ELEVENLABS_MODEL_ID

print("=" * 70)
print("Verifying v3 [Indian English] Tag")
print("=" * 70)

tts = TTSGenerator()

# Test text
test_text = "Today, Chief Minister Siddaramaiah addressed the media in Bangalore."

print(f"\n📝 Original text:")
print(f"   {test_text}")

# Check if preprocessing adds the tag
processed = tts._preprocess_text_for_indian_names(test_text, use_ssml=False)

print(f"\n📝 Processed text:")
print(f"   {processed}")

# Check if tag is present
if "[Indian English]" in processed:
    print(f"\n✅ [Indian English] tag is being added!")
    print(f"   Model: {ELEVENLABS_MODEL_ID}")
    print(f"   This enables Indian accent emulation with v3 model.")
else:
    print(f"\n⚠️  [Indian English] tag NOT found in processed text.")
    print(f"   Model: {ELEVENLABS_MODEL_ID}")
    print(f"   Check if model supports v3 audio tags.")

print("\n" + "=" * 70)

