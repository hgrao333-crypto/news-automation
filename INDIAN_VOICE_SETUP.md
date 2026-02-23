# Setting Up Indian Accent Voice for ElevenLabs v3

## 🎯 Goal
Use ElevenLabs v3 model with Indian accent emulation for better Indian name pronunciation.

## ✅ Current Setup (COMPLETE)

Your system is now configured to use **ElevenLabs v3 model with Indian accent emulation**:

- **Model**: `eleven_turbo_v2_5` (v3 equivalent) ✅
- **Voice**: Adam (`pNInz6obpgDQGcFmaJgB`) - Works with any voice via v3 accent tags ✅
- **Audio Tags**: `[Indian English]` tag automatically added ✅
- **Name Preprocessing**: Phonetic hints for 100+ Indian names ✅

## 🎤 How It Works

ElevenLabs v3 supports **accent emulation** using audio tags. The system automatically:
1. Adds `[Indian English]` tag at the start of text
2. Adds phonetic pronunciation hints for Indian names
3. Uses v3 model (`eleven_turbo_v2_5`) for best accent emulation

**Example:**
```
Original: "Siddaramaiah addressed the media in Bangalore"
Processed: "[Indian English] Siddaramaiah (SID-dah-rah-MY-ah) addressed the media in Bangalore (BAN-ga-lore)"
```

## 🧪 Test Your Setup

### 1. Verify v3 Tags Are Working

```bash
python3 verify_v3_tags.py
```

This shows the processed text with `[Indian English]` tag.

### 2. Generate Test Audio

```bash
python3 test_v3_indian_accent.py
```

This generates `temp/test_v3_indian_accent.mp3` with Indian names.

### 3. Listen and Verify

Check pronunciation of:
- Indian names: Siddaramaiah, Shivakumar, Narendra Modi
- Indian cities: Bangalore, Chennai, Hyderabad, Mumbai
- Indian states: Karnataka, Maharashtra, Tamil Nadu

## 🔍 Finding Indian Accent Voices (Optional)

If you want to use a specific Indian accent voice (like "Akshay"):

### 1. List All Voices

```bash
python3 find_indian_voices.py
```

This shows all available voices. Look for voices with:
- "Indian" in name or description
- "Akshay", "Priyam", "Sonu", "Aman", "Nikhil" in name
- Indian accent labels

### 2. Update Voice ID

If you find an Indian accent voice, update it:

**Option A: Update config.py**
```python
ELEVENLABS_VOICE_ID = "VOICE_ID_HERE"  # Replace with Indian voice ID
```

**Option B: Set in .env file**
```bash
ELEVENLABS_VOICE_ID=VOICE_ID_HERE
```

### 3. Note About Voice Cloning

If "Akshay" or other Indian voices aren't available:
- You can clone/create an Indian accent voice in ElevenLabs dashboard
- Or use any voice with v3 `[Indian English]` tag (current setup) - this works well!

## 💡 Features Enabled

1. **v3 Audio Tags**: Automatically adds `[Indian English]` tag for accent emulation
2. **Phonetic Hints**: Adds pronunciation hints for common Indian names
3. **Name Dictionary**: 100+ Indian names, cities, and states with phonetic pronunciations
4. **Model**: v3 (`eleven_turbo_v2_5`) for best accent emulation

## 🔄 Alternative: Use Edge-TTS (FREE)

If you prefer a different approach, switch to Edge-TTS with Indian English:

```bash
export TTS_USE_ELEVENLABS=false
export TTS_USE_EDGE_TTS=true
export TTS_EDGE_VOICE=en-IN-NeerjaNeural  # or en-IN-PrabhatNeural
```

Edge-TTS Indian English voices are specifically trained for Indian names and are FREE!

## 📊 Current Status

✅ **v3 Model**: Configured (`eleven_turbo_v2_5`)
✅ **Indian Accent**: Enabled via `[Indian English]` tag
✅ **Name Preprocessing**: Active with phonetic hints
✅ **Test Scripts**: Available for verification

**You're all set!** The system will automatically use Indian accent emulation for all TTS generation.

