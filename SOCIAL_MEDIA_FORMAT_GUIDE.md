# Social Media Native Format Guide

## 🎯 Overview

You now have the option to generate content in **social media native format** instead of traditional news format. This makes your videos feel more like viral social media content rather than formal news broadcasts.

## 🚀 How to Use

### Command Line

```bash
# Generate with social media format for young adults
python must_know_today.py --age-group young --style social

# Generate with social media format for middle-aged adults
python must_know_today.py --age-group middle_age --style social

# Generate with social media format for seniors
python must_know_today.py --age-group old --style social

# Default (traditional newsy format)
python must_know_today.py --age-group young --style newsy
```

### Configuration File

Set default style in `.env` or `config.py`:

```bash
# In .env file
CONTENT_STYLE=social  # or "newsy" for traditional format
```

Or in `config.py`:
```python
CONTENT_STYLE = os.getenv("CONTENT_STYLE", "social").lower()
```

## 📊 Format Differences

### Traditional "Newsy" Format
- **Opening**: "Today's news: 4 stories that will affect daily life"
- **Story**: "Breaking: Chennai schools closed due to Cyclone! This affects students and young families..."
- **Closing**: "Stay informed - these stories affect you. Follow for daily updates!"

### Social Media Native Format

#### For YOUNG (18-30):
- **Opening**: "POV: You wake up and 4 things just changed your day"
- **Story**: "POV: You're in Chennai and your entire day just changed. Schools shut. The vibes? Ruined. Here's why this matters..."
- **Closing**: "That's the tea for today. Drop a 🔥 if this affects you!"

#### For MIDDLE_AGE (30-55):
- **Opening**: "So 4 things happened today and you need to know"
- **Story**: "So this just happened in Chennai. Schools shut, online classes start. Here's why this matters..."
- **Closing**: "That's what you need to know today. Follow for more updates!"

#### For OLD (55+):
- **Opening**: "Here are 4 important updates from today"
- **Story**: "Here's what happened in Chennai today. Schools closed due to weather. This is important because..."
- **Closing**: "That's today's news. Subscribe to stay informed!"

## 🎨 Language Patterns by Age Group

### YOUNG (18-30) - Gen Z Style
- Uses: "POV", "honestly?", "no cap", "the vibes", "we're not okay", "that's the tea"
- Casual: "So", "Okay so", "Here's the thing", "Wait, what?", "This is wild"
- Examples:
  - "POV: You're in Chennai and your entire day just changed"
  - "The vibes? Ruined. Here's why..."
  - "Honestly? This is wild because..."

### MIDDLE_AGE (30-55) - Professional but Relatable
- Uses: "Here's what happened", "So this just dropped", "Quick update", "You need to know"
- Casual but not slang-heavy: "Okay so", "Here's the deal", "This is important"
- Examples:
  - "So this just happened and you need to know"
  - "Here's what's going on"
  - "Quick update that affects your daily life"

### OLD (55+) - Clear and Respectful
- Uses: "Here's what happened", "Important update", "You should know", "This affects you"
- Respectful but engaging: "Here's an update", "This is important", "Let me tell you"
- Examples:
  - "Here's what happened today"
  - "Important update that affects daily life"
  - "You should know about this"

## 💡 When to Use Each Format

### Use Social Media Format When:
- ✅ Targeting younger audiences (18-30)
- ✅ Posting on YouTube Shorts, TikTok, Instagram Reels
- ✅ Wanting maximum engagement and shares
- ✅ Creating viral-worthy content
- ✅ Building a casual, relatable brand

### Use Traditional Newsy Format When:
- ✅ Targeting older audiences (55+)
- ✅ Wanting authoritative, professional tone
- ✅ Building a news brand
- ✅ Creating educational/informative content
- ✅ Professional or corporate contexts

## 🔄 Switching Between Formats

You can easily switch between formats:

```bash
# Test social format
python must_know_today.py --age-group young --style social --stories 4

# Test traditional format
python must_know_today.py --age-group young --style newsy --stories 4

# Compare and see which performs better!
```

## 📈 Expected Engagement Differences

### Social Media Format:
- **Higher engagement**: More comments, shares, likes
- **Better retention**: Feels more entertaining
- **Viral potential**: Shareable, relatable content
- **Younger audience**: Appeals to Gen Z and Millennials

### Traditional Newsy Format:
- **Professional**: Authoritative, trustworthy
- **Older audience**: Appeals to 55+ demographic
- **Educational**: Better for informative content
- **Brand building**: Establishes news authority

## 🎯 Recommendations

1. **Test both formats** with your audience
2. **Use social format for young/middle_age** groups
3. **Use traditional format for old** age group
4. **A/B test** to see which performs better
5. **Mix formats** - use social for some videos, traditional for others

## 🛠️ Technical Details

- Format is controlled by `content_style` parameter: `"newsy"` or `"social"`
- Default can be set in `config.py` via `CONTENT_STYLE` environment variable
- All prompts (title, opening, stories, closing) adapt based on format
- Language patterns automatically adjust for each age group

## 📝 Examples

See `TONE_TRANSFORMATION_EXAMPLES.md` for detailed side-by-side comparisons of how the same stories change in different formats.

---

**Ready to try it?** Run:
```bash
python must_know_today.py --age-group young --style social --stories 4
```

