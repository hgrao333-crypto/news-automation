# Extended Video Style Support & Glitch Effects Fix

## ✅ Changes Made

### 1. Added Content Style Support to Extended Videos

Extended videos (10-minute deep-dives) now support the `content_style` parameter:

- **`content_style="newsy"`** (default): Traditional news anchor format
- **`content_style="social"`**: Social media native format with casual, viral-worthy language

**How it works:**
- Extended videos now use the same content style system as short videos
- Style is automatically read from `CONTENT_STYLE` config or can be passed as parameter
- Social format uses casual language, Gen Z slang (for young), and viral patterns
- Newsy format uses professional news anchor language

### 2. Fixed Glitch Effects

**Issues Fixed:**
- ✅ Improved glitch effect frame handling (better error handling)
- ✅ Increased glitch visibility (higher intensity, more frequent)
- ✅ Better frame format detection (handles grayscale, RGB, etc.)
- ✅ Added error handling to prevent crashes
- ✅ Improved debugging output

**Changes:**
- Glitch chance increased from 10% to 15% max per frame
- Shift amount increased from 5 to 8 pixels max
- Scan line probability increased from 30% to 40%
- Block corruption probability increased from 20% to 30%
- Better bounds checking to prevent array index errors
- Added try-catch around glitch application

### 3. Improved Effect Suggestions

- Added better error handling for effect suggestion generation
- Added debug output to show how many segments have effects
- Fallback to default effects if LLM suggestions fail

## 🚀 Usage

### Extended Videos with Style

Extended videos automatically use the `CONTENT_STYLE` from config:

```bash
# In .env or config.py
CONTENT_STYLE=social  # or "newsy"
```

Or when calling programmatically:
```python
generate_extended_video(topic, articles, duration=600, content_style="social")
```

### Testing Glitch Effects

Glitch effects should now be more visible and work correctly. Check the console output for:
- `✨ Applied glitch effect (intensity: X.XX)` - confirms glitch is applied
- `⚠️  Could not apply glitch effect: [error]` - shows if there's an issue

## 🔍 Debugging

If glitch effects still don't appear:

1. **Check console output** - Look for glitch effect messages
2. **Check effect suggestions** - Should see "Effect suggestions generated: X segments"
3. **Check segment_effects** - Should have entries for segments with `glitch.enabled: true`
4. **Verify intensity** - Glitch intensity should be > 0 (typically 0.2-0.5)

## 📝 Notes

- Glitch effects are more subtle at lower intensities (0.1-0.3)
- Higher intensities (0.4-0.6) create more dramatic effects
- Effects are applied per segment based on LLM suggestions
- Headlines get default subtle glitch (0.2) if no suggestion provided

