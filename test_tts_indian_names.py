#!/usr/bin/env python3
"""
Test script to generate TTS audio with Indian names to verify pronunciation
"""

import os
from tts_generator import TTSGenerator
from config import TEMP_DIR

def test_indian_names_pronunciation():
    """Test TTS pronunciation of Indian names"""
    
    print("=" * 60)
    print("Testing TTS Pronunciation of Indian Names")
    print("=" * 60)
    
    # Test text with various Indian names
    test_texts = [
        {
            "name": "Politicians",
            "text": "Prime Minister Narendra Modi, Chief Minister Siddaramaiah, Deputy Chief Minister Shivakumar, and Congress leader Rahul Gandhi addressed the Karnataka assembly."
        },
        {
            "name": "Cities and States",
            "text": "Breaking news from Karnataka, Maharashtra, Tamil Nadu, Gujarat, Rajasthan, and Uttar Pradesh. Major developments in Delhi, Mumbai, Bangalore, Chennai, and Hyderabad."
        },
        {
            "name": "Common Names",
            "text": "The meeting was attended by Rajesh Kumar, Priya Sharma, Deepak Patel, Anjali Reddy, and Vikram Singh. Also present were Suresh Nair, Mahesh Iyer, and Kavita Menon."
        },
        {
            "name": "Complex Names",
            "text": "Venkatesh Srinivas from Andhra Pradesh, Sathish Prakash from Tamil Nadu, and Niranjan Narayan from Kerala discussed the proposal."
        }
    ]
    
    # Initialize TTS generator
    print("\n🎙️  Initializing TTS Generator...")
    tts = TTSGenerator()
    
    print(f"\n✅ Using: {tts.use_elevenlabs and 'ElevenLabs' or 'Edge-TTS'}")
    if tts.use_elevenlabs:
        print(f"   Voice ID: {tts.elevenlabs_voice_id}")
        from config import ELEVENLABS_MODEL_ID
        print(f"   Model: {ELEVENLABS_MODEL_ID}")
    else:
        print(f"   Voice: {tts.edge_voice}")
    
    print("\n" + "=" * 60)
    print("Generating Test Audio Files...")
    print("=" * 60)
    
    generated_files = []
    
    for i, test_case in enumerate(test_texts, 1):
        print(f"\n[{i}/{len(test_texts)}] Testing: {test_case['name']}")
        print(f"   Text: {test_case['text'][:80]}...")
        
        output_filename = f"test_indian_names_{i}_{test_case['name'].lower().replace(' ', '_')}.mp3"
        output_path = os.path.join(TEMP_DIR, output_filename)
        
        try:
            audio_path = tts.generate_audio(test_case['text'], output_filename)
            if audio_path:
                generated_files.append({
                    'name': test_case['name'],
                    'path': audio_path,
                    'text': test_case['text']
                })
                print(f"   ✅ Generated: {output_filename}")
            else:
                print(f"   ❌ Failed to generate audio")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    
    if generated_files:
        print(f"\n✅ Successfully generated {len(generated_files)} test audio files:")
        for file_info in generated_files:
            print(f"   📄 {file_info['name']}: {os.path.basename(file_info['path'])}")
        
        print(f"\n📁 All files saved in: {TEMP_DIR}")
        print("\n🎧 Please listen to the audio files to verify Indian name pronunciation.")
        print("   If pronunciation is incorrect, try:")
        print("   1. Different voice (update ELEVENLABS_VOICE_ID in config.py)")
        print("   2. Different model (update ELEVENLABS_MODEL_ID in config.py)")
        print("   3. Use Edge-TTS with Indian English (set TTS_USE_ELEVENLABS=false)")
    else:
        print("\n❌ No audio files were generated. Check the errors above.")
    
    return generated_files

if __name__ == "__main__":
    test_indian_names_pronunciation()

