# Age Groups Guide - Must-Know Today Format

## 🎯 Three Age Groups

### 1. **YOUNG** (18-30 years)
**Focus Areas:**
- Education policies, job market, internships, scholarships
- Exam updates, tech trends affecting careers
- Startup opportunities, career planning
- Social issues affecting youth
- Dating/relationships, housing/rent
- Skill development, social media trends
- Health for young adults

**Example Stories:**
- "New education loan policies - how this affects students planning higher studies"
- "Job market trends - what young professionals need to know"
- "Tech skills in demand - career opportunities for 2024"
- "Housing rent changes - how this affects young adults"

**Tone:** Energetic, forward-looking, opportunity-focused

---

### 2. **MIDDLE_AGE** (30-55 years)
**Focus Areas:**
- Job market, salary trends, tax changes
- Business news, economic policies
- Investment opportunities, industry changes
- Family finances, children's education
- Health insurance, retirement planning
- Property/real estate, career advancement
- Work-life balance

**Example Stories:**
- "New tax policy - how this affects your salary and investments"
- "Job market changes - what middle-aged professionals need to know"
- "Children's education policies - how this affects your family"
- "Retirement planning updates - what you need to know now"

**Tone:** Practical, family-focused, stability-oriented

---

### 3. **OLD** (55+ years)
**Focus Areas:**
- Pension updates, healthcare policies
- Senior citizen benefits, retirement schemes
- Health alerts, medical facilities
- Government schemes for elderly
- Property/legal matters, family matters
- Social security, inflation impact on savings
- Medical insurance, age-related health issues
- Senior citizen discounts/benefits

**Example Stories:**
- "Pension scheme updates - how this affects senior citizens"
- "Healthcare policy changes - what elderly need to know"
- "Senior citizen benefits - new schemes announced"
- "Medical insurance updates - coverage changes"

**Tone:** Respectful, health-focused, security-oriented

---

## 🚀 Usage

### Test Scripts (Text Only):
```bash
# Test one age group
python test_must_know_scripts.py --age-group young

# Test all age groups
python test_must_know_scripts.py --age-group all

# Customize story count
python test_must_know_scripts.py --age-group middle_age --stories 5
```

### Generate Videos:
```bash
# For young adults
python must_know_today.py --age-group young

# For middle-aged adults
python must_know_today.py --age-group middle_age

# For senior citizens
python must_know_today.py --age-group old

# Customize stories
python must_know_today.py --age-group young --stories 5
```

---

## 📊 Content Selection Differences

### YOUNG Audience:
- ✅ Education, career, opportunities
- ✅ Tech trends, startups, skills
- ✅ Social issues, relationships
- ❌ Retirement, pension (not relevant yet)

### MIDDLE_AGE Audience:
- ✅ Career advancement, family finances
- ✅ Children's education, investments
- ✅ Health insurance, retirement planning
- ❌ Student loans (already past that stage)

### OLD Audience:
- ✅ Healthcare, pension, benefits
- ✅ Medical facilities, senior schemes
- ✅ Legal matters, family security
- ❌ Career opportunities (retired)

---

## 🎬 Script Structure (Same for All)

```
[0-4s] Opening Hook
  "You need to know these 4 stories - they affect you today!"

[4-16s] Story 1
  - What happened (3-4s)
  - Why it matters to YOUR age group (4-6s)
  - How it affects daily life (3-5s)

[16-28s] Story 2
  - What happened (3-4s)
  - Why it matters to YOUR age group (4-6s)
  - How it affects daily life (3-5s)

[28-40s] Story 3
  - What happened (3-4s)
  - Why it matters to YOUR age group (4-6s)
  - How it affects daily life (3-5s)

[40-52s] Story 4
  - What happened (3-4s)
  - Why it matters to YOUR age group (4-6s)
  - How it affects daily life (3-5s)

[52-55s] Closing
  "Stay informed - these stories affect you. Follow for daily updates!"
```

---

## 💡 Engagement Techniques (All Age Groups)

1. **Urgency Hooks**: "Breaking:", "Important:", "You need to know:"
2. **Personal Language**: "This affects YOU because...", "For [age group], this means..."
3. **Curiosity**: "Here's why this matters...", "The impact is huge..."
4. **Specific Examples**: Use numbers, dates, concrete examples
5. **Emotional Connection**: "This could save you money", "This affects your future"

---

## 📈 Expected Results

### YOUNG:
- High engagement with career/education content
- Comments about opportunities, skills, jobs
- Shares with friends in similar life stage

### MIDDLE_AGE:
- High engagement with family/finance content
- Comments about taxes, investments, children
- Shares with family/colleagues

### OLD:
- High engagement with health/benefits content
- Comments about healthcare, pension, schemes
- Shares with family/peers

---

## 🧪 Testing Workflow

1. **Test Scripts First** (no video generation):
   ```bash
   python test_must_know_scripts.py --age-group young
   ```
   - Review the generated text
   - Check if stories are relevant
   - Verify tone and language
   - Adjust if needed

2. **Generate Video** (after script validation):
   ```bash
   python must_know_today.py --age-group young
   ```
   - Creates full video with images and audio
   - Saves to output/ directory

3. **Iterate**:
   - Test different age groups
   - Adjust story count
   - Refine prompts if needed

---

## 🎯 Quick Start

1. **Test one age group:**
   ```bash
   python test_must_know_scripts.py --age-group young
   ```

2. **Review the output JSON file** (saved automatically)

3. **If script looks good, generate video:**
   ```bash
   python must_know_today.py --age-group young
   ```

4. **Repeat for other age groups**

---

Ready to test? Start with:
```bash
python test_must_know_scripts.py --age-group young
```

