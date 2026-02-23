#!/usr/bin/env python3
"""
Script to find Indian accent voices in ElevenLabs
Run: python3 find_indian_voices.py
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tts_generator import TTSGenerator

def find_indian_voices():
    """Find Indian accent voices in ElevenLabs"""
    
    print("=" * 60)
    print("Finding Indian Accent Voices in ElevenLabs")
    print("=" * 60)
    
    voices = TTSGenerator.list_elevenlabs_voices()
    
    if not voices:
        print("❌ Could not fetch voices. Check your ELEVENLABS_API_KEY")
        return
    
    print(f"\n✅ Found {len(voices)} total voices\n")
    
    # Search for Indian accent voices
    indian_keywords = ['indian', 'india', 'akshay', 'priyam', 'sonu', 'hindi', 'tamil', 'bengali']
    indian_voices = []
    
    for voice in voices:
        name = voice.get('name', '').lower()
        description = voice.get('description', '').lower()
        category = voice.get('category', '').lower()
        labels = voice.get('labels', {})
        
        # Check if it's an Indian accent voice
        is_indian = any(keyword in name or keyword in description for keyword in indian_keywords)
        
        if is_indian:
            indian_voices.append(voice)
    
    if indian_voices:
        print("🇮🇳 INDIAN ACCENT VOICES FOUND:")
        print("-" * 60)
        for voice in indian_voices:
            print(f"\n  Name: {voice.get('name')}")
            print(f"  ID: {voice.get('voice_id')}")
            print(f"  Description: {voice.get('description', 'N/A')}")
            print(f"  Category: {voice.get('category', 'N/A')}")
            if voice.get('labels'):
                print(f"  Labels: {voice.get('labels')}")
    else:
        print("⚠️  No Indian accent voices found with keywords.")
        print("\n📋 Showing ALL available voices (look for 'Akshay', 'Priyam', 'Indian', etc.):")
        print("-" * 60)
        for i, voice in enumerate(voices, 1):
            name = voice.get('name', 'Unknown')
            voice_id = voice.get('voice_id', 'N/A')
            description = voice.get('description', 'N/A')
            category = voice.get('category', 'N/A')
            
            # Highlight potential Indian voices
            is_potential = any(kw in name.lower() or kw in description.lower() 
                             for kw in ['indian', 'india', 'akshay', 'priyam', 'sonu', 'aman', 'nikhil', 'hindi'])
            
            marker = "🇮🇳" if is_potential else "  "
            print(f"{marker} {i}. {name}")
            print(f"     ID: {voice_id}")
            if description != 'N/A':
                print(f"     Description: {description}")
            if category != 'N/A':
                print(f"     Category: {category}")
            print()
    
    # Also show recommended voices
    print("\n" + "=" * 60)
    print("💡 RECOMMENDATIONS:")
    print("=" * 60)
    print("""
If you can't find 'Akshay', try searching for:
- Indian accent voices
- Hindi/Tamil/Bengali voices
- Voices with 'Indian' in name or description

Common Indian accent voice names:
- Akshay
- Priyam
- Sonu
- Indian Male/Female
- Hindi Narrator

To use a voice, update ELEVENLABS_VOICE_ID in config.py or .env file.
""")

if __name__ == "__main__":
    find_indian_voices()

