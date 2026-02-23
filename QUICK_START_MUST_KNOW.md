# Quick Start: Must-Know Today Format

## ✅ What's Been Created

1. **3 Age Groups**: `young` (18-30), `middle_age` (30-55), `old` (55+)
2. **Test Script**: `test_must_know_scripts.py` - Generates text scripts only (no video)
3. **Video Generator**: `must_know_today.py` - Creates full videos with images/audio
4. **Engaging Format**: Content designed to keep viewers hooked with urgency, personal relevance, and actionable insights

---

## 🧪 Step 1: Test Scripts First (Recommended)

### Test One Age Group:
```bash
python test_must_know_scripts.py --age-group young
```

This will:
- ✅ Fetch today's news
- ✅ Select relevant stories for the age group
- ✅ Generate engaging script with hooks
- ✅ Display full script and segments
- ✅ Save output to JSON file

### Test All Age Groups:
```bash
python test_must_know_scripts.py --age-group all
```

### Test with Custom Story Count:
```bash
python test_must_know_scripts.py --age-group middle_age --stories 5
```

---

## 📺 Step 2: Generate Videos (After Testing)

Once you're happy with the scripts:

```bash
# For young adults
python must_know_today.py --age-group young

# For middle-aged adults  
python must_know_today.py --age-group middle_age

# For senior citizens
python must_know_today.py --age-group old
```

---

## 🎯 Age Group Options

| Age Group | Age Range | Focus Areas |
|-----------|-----------|------------|
| `young` | 18-30 | Education, career, startups, skills, relationships |
| `middle_age` | 30-55 | Family finances, investments, children's education, retirement planning |
| `old` | 55+ | Healthcare, pension, senior benefits, medical facilities |

---

## 📋 What the Scripts Include

### Each Story Has:
1. **What Happened** (3-4 seconds)
   - Starts with urgency: "Breaking:", "Important:", "You need to know:"

2. **Why It Matters** (4-6 seconds)
   - Personal connection: "This affects YOU because..."
   - Age-group specific relevance
   - Emotional connection

3. **How It Affects Daily Life** (3-5 seconds)
   - Specific, actionable information
   - Concrete examples
   - Practical impact

### Full Video Structure:
- **Opening Hook** (3-4s): Attention-grabbing intro
- **4 Stories** (12-15s each): What + Why + How
- **Closing** (3-4s): Call-to-action

**Total: ~60 seconds**

---

## 📊 Example Output (Test Script)

When you run the test script, you'll see:

```
================================================================================
TESTING: Must-Know Today Script Generator
Age Group: YOUNG
Stories: 4
================================================================================

[1/3] Fetching today's news...
✅ Found 30 articles

[2/3] Analyzing news for young audience...
✅ Selected 4 must-know stories:
  1. RBI announces new education loan policies...
  2. Tech job market sees 20% growth...
  3. New startup funding opportunities...
  4. Housing rent changes in major cities...

[3/3] Generating engaging script for young...

================================================================================
GENERATED SCRIPT
================================================================================

📺 TITLE:
   You Need to Know These 4 Stories - Young Adults Edition

📝 FULL SCRIPT:
   [Full script text here...]

🎬 SEGMENTS BREAKDOWN:
   Segment 1 (OPENING): 0.0s - 4.0s (4s)
   Segment 2 (STORY): 4.0s - 16.0s (12s)
   ...

💾 Saved to: test_output_must_know_young_20241130_120000.json
```

---

## 🎨 Engagement Features

The format includes:

1. **Urgency Hooks**: "Breaking:", "Important:", "Alert:"
2. **Personal Language**: "This affects YOU", "For young adults, this means..."
3. **Curiosity**: "Here's why this matters...", "The impact is huge..."
4. **Specific Examples**: Numbers, dates, concrete details
5. **Emotional Connection**: "This could save you money", "This affects your future"
6. **Call-to-Action**: Encourages comments, shares, subscribe

---

## 🔧 Troubleshooting

### If test script fails:
- Check your `NEWS_API_KEY` in config
- Ensure Ollama/LLM is running
- Check internet connection

### If stories aren't relevant:
- The system analyzes news for age-group relevance
- Try running again (news changes daily)
- Adjust `--stories` count if needed

### If script is too long/short:
- Default is 4 stories (~60 seconds)
- Adjust with `--stories` parameter
- System automatically calculates timing

---

## 📁 Output Files

### Test Script Output:
- `test_output_must_know_{age_group}_{timestamp}.json`
- Contains: title, script, segments, image prompts, selected articles

### Video Output:
- `must_know_{age_group}_{timestamp}.mp4`
- Saved to `output/` directory

---

## 🚀 Next Steps

1. **Test scripts** for all 3 age groups
2. **Review output** - check if stories are relevant
3. **Generate videos** for the best-performing age group
4. **Iterate** - adjust based on engagement metrics

---

## 💡 Pro Tips

1. **Test first**: Always test scripts before generating videos
2. **Start with one**: Test one age group first, then expand
3. **Review JSON**: Check the saved JSON file for full details
4. **Customize**: Adjust story count based on your needs
5. **Time it right**: Post at times when your target age group is active

---

Ready to start? Run:

```bash
python test_must_know_scripts.py --age-group young
```

Then review the output and generate videos when ready!

