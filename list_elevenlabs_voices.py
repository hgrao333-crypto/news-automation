#!/usr/bin/env python3
"""
Script to list available ElevenLabs voices and help choose the best one for Indian names
"""

import os
from dotenv import load_dotenv
load_dotenv()

from tts_generator import TTSGenerator

def main():
    print("=" * 60)
    print("ElevenLabs Voice List - Finding Best Voice for Indian Names")
    print("=" * 60)
    
    # List ElevenLabs voices
    print("\n📢 Available ElevenLabs Voices:")
    print("-" * 60)
    
    voices = TTSGenerator.list_elevenlabs_voices()
    
    if not voices:
        print("❌ Could not fetch voices. Check your ELEVENLABS_API_KEY in .env file")
        return
    
    print(f"\n✅ Found {len(voices)} voices\n")
    
    # Group voices by category/description
    news_voices = []
    professional_voices = []
    other_voices = []
    
    for voice in voices:
        name = voice.get('name', 'Unknown')
        description = voice.get('description', '').lower()
        category = voice.get('category', '').lower()
        voice_id = voice.get('voice_id', '')
        labels = voice.get('labels', {})
        
        # Check if it's a news/professional voice
        is_news = any(keyword in description for keyword in ['news', 'professional', 'anchor', 'broadcast', 'clear', 'authoritative'])
        is_professional = any(keyword in description for keyword in ['professional', 'business', 'formal', 'clear'])
        
        voice_info = {
            'name': name,
            'voice_id': voice_id,
            'description': voice.get('description', ''),
            'category': category,
            'labels': labels
        }
        
        if is_news:
            news_voices.append(voice_info)
        elif is_professional:
            professional_voices.append(voice_info)
        else:
            other_voices.append(voice_info)
    
    # Display news voices first (best for news content)
    if news_voices:
        print("🎙️  NEWS/PROFESSIONAL VOICES (Best for News):")
        print("-" * 60)
        for voice in news_voices:
            print(f"  Name: {voice['name']}")
            print(f"  ID: {voice['voice_id']}")
            print(f"  Description: {voice['description']}")
            print(f"  Category: {voice['category']}")
            print()
    
    # Display professional voices
    if professional_voices:
        print("💼 PROFESSIONAL VOICES:")
        print("-" * 60)
        for voice in professional_voices[:10]:  # Limit to first 10
            print(f"  Name: {voice['name']}")
            print(f"  ID: {voice['voice_id']}")
            print(f"  Description: {voice['description']}")
            print()
    
    # Recommendations for Indian names
    print("\n" + "=" * 60)
    print("🇮🇳 RECOMMENDATIONS FOR INDIAN NAMES:")
    print("=" * 60)
    print("""
For best Indian name pronunciation with ElevenLabs:

1. **Use Multilingual Model**: The 'eleven_multilingual_v2' model (already configured)
   handles multiple languages and should handle Indian names better.

2. **Best Voices for Indian Names** (based on clarity and multilingual support):
   - Rachel (21m00Tcm4TlvDq8ikWAM) - Current default, good clarity
   - Adam (pNInz6obpgDQGcFmaJgB) - Deep, clear, handles names well
   - Antoni (ErXwobaYiN019PkySvjV) - Clear, professional
   - Domi (ThT5KcBeYPX3keUQqHPh) - Energetic, clear pronunciation

3. **Alternative: Use Edge-TTS with Indian English**:
   - en-IN-NeerjaNeural (Female) - Specifically trained for Indian English
   - en-IN-PrabhatNeural (Male) - Specifically trained for Indian English
   - These are FREE and handle Indian names excellently

4. **Pronunciation Hints**: The code already includes a pronunciation dictionary
   for common Indian names, cities, and states.

To test a voice, update ELEVENLABS_VOICE_ID in config.py or .env file.
""")
    
    # Show current configuration
    print("\n" + "=" * 60)
    print("⚙️  CURRENT CONFIGURATION:")
    print("=" * 60)
    current_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    current_voice = next((v for v in voices if v.get('voice_id') == current_voice_id), None)
    if current_voice:
        print(f"Current Voice: {current_voice.get('name')}")
        print(f"Voice ID: {current_voice_id}")
        print(f"Description: {current_voice.get('description', 'N/A')}")
    else:
        print(f"Current Voice ID: {current_voice_id} (not found in list)")

if __name__ == "__main__":
    main()

