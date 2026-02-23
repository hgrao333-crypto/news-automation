#!/usr/bin/env python3
"""
Simple test script to generate TTS audio with Indian names
Run this to test pronunciation: python3 test_tts_simple.py
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tts_generator import TTSGenerator
from config import TEMP_DIR

def main():
    print("=" * 60)
    print("Testing TTS with Indian Names")
    print("=" * 60)
    
    # Test text with Indian names
    test_text = """
    Breaking news from Karnataka. Chief Minister Siddaramaiah and Deputy Chief Minister Shivakumar 
    addressed the assembly in Bangalore. Prime Minister Narendra Modi visited Maharashtra and Tamil Nadu. 
    The meeting was attended by Rajesh Kumar from Delhi, Priya Sharma from Mumbai, and Deepak Patel from Chennai.
    """
    
    print("\n📝 Test Text:")
    print(test_text.strip())
    
    print("\n🎙️  Initializing TTS...")
    try:
        tts = TTSGenerator()
        
        if tts.use_elevenlabs:
            from config import ELEVENLABS_MODEL_ID
            print(f"✅ Using ElevenLabs")
            print(f"   Voice ID: {tts.elevenlabs_voice_id}")
            print(f"   Model: {ELEVENLABS_MODEL_ID}")
        else:
            print(f"✅ Using Edge-TTS")
            print(f"   Voice: {tts.edge_voice}")
        
        print("\n🔊 Generating audio...")
        output_file = "test_indian_names.mp3"
        audio_path = tts.generate_audio(test_text, output_file)
        
        if audio_path:
            print(f"\n✅ Success! Audio generated: {audio_path}")
            print(f"\n🎧 Please listen to the audio to verify Indian name pronunciation:")
            print(f"   - Siddaramaiah")
            print(f"   - Shivakumar")
            print(f"   - Narendra Modi")
            print(f"   - Karnataka")
            print(f"   - Bangalore")
            print(f"   - Maharashtra")
            print(f"   - Tamil Nadu")
            print(f"   - Rajesh Kumar")
            print(f"   - Priya Sharma")
            print(f"   - Deepak Patel")
            print(f"   - Chennai")
        else:
            print("\n❌ Failed to generate audio")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

