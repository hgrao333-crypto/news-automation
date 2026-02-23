# Must-Know Today Format

## 🎯 Overview

The "Must-Know Today" format focuses on news that **directly affects daily life** - things users should know because they impact their work, finances, health, education, or future decisions.

Unlike generic news summaries, this format:
- ✅ Explains **WHY** each story matters
- ✅ Connects news to **daily life impact**
- ✅ Targets **specific age groups** with relevant context
- ✅ Provides **practical value** to viewers

---

## 👥 Target Age Groups

### 1. **Students (18-25)**
Focuses on:
- Education policies, exam updates, scholarships
- Job market trends, internships, career opportunities
- Tech trends affecting future careers
- Startup opportunities, entrepreneurship
- Social issues affecting youth

**Example Story:**
- "RBI announces new education loan policies - Here's how this affects students planning higher education..."

### 2. **Professionals (25-40)**
Focuses on:
- Job market, salary trends, industry changes
- Tax changes, financial policies
- Business news, economic updates
- Tech updates affecting work
- Investment opportunities

**Example Story:**
- "New tax policy announced - Here's how this affects your salary and investments..."

### 3. **General (18-35)**
Focuses on:
- Things affecting daily life (transport, utilities, services)
- Cost of living (prices, inflation, taxes)
- Health and safety alerts
- Government policies affecting daily routines
- Technology affecting daily life

**Example Story:**
- "Metro fare changes announced - Here's how this affects your daily commute and budget..."

---

## 📋 Format Structure

### Video Length: 60 seconds
### Stories: 4-5 stories (12-15 seconds each)

**Structure:**
```
[0-4s] Opening Hook
  "Here's what you need to know today - 4 stories that affect you."

[4-16s] Story 1
  - What happened (3-4s)
  - Why it matters (4-6s)
  - How it affects daily life (3-5s)

[16-28s] Story 2
  - What happened (3-4s)
  - Why it matters (4-6s)
  - How it affects daily life (3-5s)

[28-40s] Story 3
  - What happened (3-4s)
  - Why it matters (4-6s)
  - How it affects daily life (3-5s)

[40-52s] Story 4
  - What happened (3-4s)
  - Why it matters (4-6s)
  - How it affects daily life (3-5s)

[52-55s] Closing
  "Stay informed - these stories affect your daily life. Follow for more updates!"
```

---

## 🎬 Example Script

### Story Example (Students):

**What Happened:**
"RBI announces new education loan policies with lower interest rates for students."

**Why It Matters:**
"This matters to students because it makes higher education more affordable. If you're planning to study abroad or pursue higher studies, this directly affects your financial planning."

**How It Affects:**
"This means you can now get education loans at 2% lower interest rates, saving thousands of rupees over the loan period. This could be the difference between affording your dream course or not."

---

## 🚀 Usage

### Basic Usage:
```bash
# Generate for general audience (default)
python must_know_today.py

# Generate for students
python must_know_today.py --age-group students

# Generate for professionals
python must_know_today.py --age-group professionals

# Customize number of stories
python must_know_today.py --age-group students --stories 5

# Upload to YouTube
python must_know_today.py --age-group professionals --upload
```

### Command Line Options:
- `--age-group`: Choose `students`, `professionals`, or `general` (default: `general`)
- `--stories`: Number of stories to cover (default: 4)
- `--upload`: Upload to YouTube after generation

---

## 📊 Selection Criteria

The system analyzes news articles and selects stories based on:

1. **Daily Life Impact (40% weight)**
   - Affects daily routines, cost of living, health, education, work

2. **Practical Value (30% weight)**
   - Helps users make better decisions
   - Provides actionable information
   - Prevents problems or helps preparation

3. **Timeliness (20% weight)**
   - Happening now or soon
   - Requires immediate attention
   - Breaking news affecting daily life

4. **Relevance to Age Group (10% weight)**
   - Specifically matters to target audience
   - Addresses their concerns and interests

---

## 🎯 What Gets Selected

### ✅ PRIORITIZED:
- Government policies affecting daily life
- Economic changes (inflation, job market, salary trends)
- Health alerts (disease outbreaks, vaccination, health policies)
- Education updates (exams, admissions, scholarships)
- Technology affecting work/life
- Infrastructure changes (transport, utilities)
- Financial news (banking, investment, currency)
- Job market trends

### ❌ AVOIDED:
- Pure entertainment (celebrity gossip, movies)
- Sports scores (unless major policy/career-related)
- International news (unless directly affects India/Indians)
- Soft news (weather forecasts, local events)
- Historical/retrospective (unless relevant to current decisions)

---

## 💡 Key Differences from Regular News

| Aspect | Regular News | Must-Know Today |
|--------|-------------|-----------------|
| **Focus** | What happened | Why it matters to YOU |
| **Context** | Basic facts | Practical impact |
| **Target** | General audience | Specific age groups |
| **Value** | Information | Actionable insights |
| **Structure** | Headlines + summaries | What + Why + How it affects |

---

## 📈 Expected Engagement

### Why This Format Works:
1. **Practical Value**: Viewers get actionable information
2. **Personal Relevance**: Stories connect to their daily life
3. **Educational**: Explains context and implications
4. **Targeted**: Content matches audience needs
5. **Actionable**: Helps viewers make better decisions

### Expected Metrics:
- **Higher Watch Time**: 70-80% retention (vs 40-50% for generic news)
- **More Comments**: 15-30 comments (vs 2-5 for generic news)
- **More Shares**: 8-15 shares (vs 1-3 for generic news)
- **Better Completion**: 60-70% (vs 40% for generic news)

---

## 🔧 Implementation Details

### Files Modified:
- `content_generator.py`: Added `analyze_and_select_must_know_news()` and `generate_must_know_today()`

### Files Created:
- `must_know_today.py`: Main script to generate videos

### Dependencies:
- Uses existing `NewsFetcher`, `ImageGenerator`, `TTSGenerator`, `VideoGenerator`
- No new dependencies required

---

## 🎨 Visual Elements

The format uses:
- **"MUST KNOW"** badge overlay for urgency
- **Age group indicator** (e.g., "For Students", "For Professionals")
- **"Why This Matters"** text overlays
- **Progress indicators** ("Story 2 of 4")
- **Practical icons** (money, calendar, health, etc.)

---

## 📝 Example Titles

- "5 Things Students Must Know Today"
- "Today's Must-Know News for Professionals"
- "4 Stories That Affect Your Daily Life"
- "What You Need to Know Today - Students Edition"
- "Must-Know News That Affects Your Work & Finances"

---

## 🚀 Next Steps

1. **Test the format** with different age groups
2. **Analyze engagement metrics** to see which age group responds best
3. **Refine selection criteria** based on viewer feedback
4. **Create series** (e.g., "Must-Know Monday", "Student News Tuesday")
5. **Add interactive elements** (polls, questions) to increase engagement

---

## 💬 Tips for Best Results

1. **Choose the right age group** for your target audience
2. **Use 4-5 stories** for optimal watch time (not too many, not too few)
3. **Focus on practical impact** - always explain WHY it matters
4. **Keep it actionable** - help viewers understand what to do with the information
5. **Post consistently** - build audience expectation for daily must-know updates

---

Ready to create your first "Must-Know Today" video? Run:

```bash
python must_know_today.py --age-group students
```

