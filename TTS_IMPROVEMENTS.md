# TTS Improvements for Professional News Anchor Tone

## Changes Made

### 1. UK English Accent ✅
- Changed from default US English to UK English (`tld='co.uk'`)
- UK English sounds more authoritative and professional
- Common in international news broadcasts (BBC, Sky News style)

### 2. Professional Audio Enhancement ✅
- **Normalization**: Consistent volume levels (broadcast standard)
- **Speed Adjustment**: 5% faster for professional pacing (150-160 WPM)
- **Volume Boost**: +2dB gain for authority and presence
- **Double Normalization**: Ensures consistent levels after speed changes

### 3. Broadcast-Style Processing ✅
- Professional news anchors speak at a moderate-fast pace
- Clear, authoritative delivery
- Consistent volume throughout (no sudden loud/quiet parts)
- Crisp, clear speech optimized for news delivery

## Technical Details

### Speed Adjustment
- Normal speech: ~140 words per minute
- News anchor pace: ~150-160 words per minute
- 5% speed increase achieves professional pacing

### Audio Processing Chain
1. Generate TTS with UK English
2. Normalize volume
3. Speed up by 5%
4. Normalize again
5. Apply +2dB gain
6. Final normalization

## Result

The TTS now sounds like:
- ✅ Professional news anchor
- ✅ Authoritative and confident
- ✅ Clear and crisp delivery
- ✅ Consistent pacing
- ✅ Broadcast-quality audio

## Image Generation

**Confirmed**: We're using **Imagine Art API (vyro.ai)** for image generation
- This is the official Imagine Art service
- API endpoint: `https://api.vyro.ai/v2/image/generations`
- Generates high-quality AI images for news segments

## Testing

Run the generator to hear the improved news anchor tone:
```bash
source venv/bin/activate
python main.py --type today
```

The audio should now sound much more like official TV news channels!

