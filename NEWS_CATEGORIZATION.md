# News Categorization System

## 📊 How News is Categorized

The system uses **keyword-based categorization** to automatically classify news articles into categories. This helps ensure diverse content selection and better targeting.

---

## 🔍 Categorization Method

### Process:
1. **Extract Text**: Combines article title + description (lowercased)
2. **Keyword Matching**: Checks for category-specific keywords
3. **Scoring**: Counts how many keywords match per category
4. **Selection**: Returns category with highest score, or "general" if no match

### Code Location:
`content_generator.py` → `_categorize_article()` method (lines 22-54)

---

## 📋 Categories & Keywords

### 1. **POLITICS**
**Keywords:**
- election, modi, bjp, congress, government, minister, parliament
- political, party, vote, campaign, policy, law, bill
- assembly, cm, pm, ruling, opposition

**Examples:**
- "Modi announces new policy"
- "BJP wins election"
- "Congress leader resigns"

---

### 2. **TECH**
**Keywords:**
- tech, technology, ai, artificial intelligence, startup
- app, software, digital, internet, cyber, data
- innovation, it, computer, mobile, phone
- social media, platform

**Examples:**
- "New AI startup raises funding"
- "Tech company launches app"
- "Digital payment system updated"

---

### 3. **BUSINESS**
**Keywords:**
- business, economy, market, stock, rupee, rbi, bank
- company, corporate, trade, export, import
- gdp, inflation, revenue, profit
- investment, finance, financial

**Examples:**
- "Stock market crashes"
- "RBI announces new policy"
- "Company reports profit"

---

### 4. **SPORTS**
**Keywords:**
- cricket, ipl, match, sport, player, team
- tournament, championship, football, hockey
- olympics, athlete, game, win, defeat, victory

**Examples:**
- "India wins cricket match"
- "IPL tournament begins"
- "Olympic athlete breaks record"

---

### 5. **ENTERTAINMENT**
**Keywords:**
- movie, film, actor, actress, bollywood, celebrity
- music, song, award, show, tv, series, entertainment

**Examples:**
- "Bollywood actor wins award"
- "New movie releases"
- "Celebrity announces project"

---

### 6. **HEALTH**
**Keywords:**
- health, medical, hospital, doctor, disease
- covid, vaccine, treatment, patient
- healthcare, medicine, surgery

**Examples:**
- "New vaccine approved"
- "Hospital opens new wing"
- "Disease outbreak reported"

---

### 7. **CRIME**
**Keywords:**
- crime, police, arrest, murder, theft, robbery
- case, court, judge, lawyer, trial, jail, prison

**Examples:**
- "Police arrest suspect"
- "Court delivers verdict"
- "Crime rate decreases"

---

### 8. **EDUCATION**
**Keywords:**
- education, school, college, university, student
- exam, result, degree, academic

**Examples:**
- "Exam dates announced"
- "University opens admissions"
- "Student wins scholarship"

---

### 9. **ENVIRONMENT**
**Keywords:**
- climate, environment, pollution, green, solar
- renewable, carbon, emission, weather
- flood, drought

**Examples:**
- "Climate change summit"
- "Solar energy project launched"
- "Flood warning issued"

---

### 10. **GENERAL** (Default)
**When no category matches:**
- Articles that don't fit any specific category
- Mixed topics
- Unclear categorization

---

## 🎯 How It's Used

### 1. **Diversity Selection**
When selecting news for videos, the system:
- Categorizes all articles
- Ensures diverse mix (one story per category when possible)
- Avoids multiple stories from same category

### 2. **Age Group Targeting**
For "Must-Know Today" format:
- Categories are weighted based on age group relevance
- Young: Prioritizes education, tech, business
- Middle Age: Prioritizes business, health, politics
- Old: Prioritizes health, politics, general

### 3. **Selection Process**
```
1. Fetch 50 articles
2. Categorize each article
3. Score by relevance to age group
4. Select diverse mix (4-5 stories)
5. Ensure practical value
```

---

## 📈 Category Distribution Example

**Input:** 50 articles fetched

**Categorization:**
```
Politics: 12 articles
Tech: 8 articles
Business: 10 articles
Sports: 5 articles
Entertainment: 3 articles
Health: 4 articles
Crime: 2 articles
Education: 3 articles
Environment: 1 article
General: 0 articles
```

**Selected for "Young" audience (4 stories):**
- 1 Education (exam updates)
- 1 Tech (career opportunities)
- 1 Business (job market)
- 1 Politics (education policy)

---

## 🔧 How to Modify Categories

### Add New Category:
1. Open `content_generator.py`
2. Find `_categorize_article()` method
3. Add new category to `categories` dictionary:

```python
categories = {
    ...
    'new_category': ['keyword1', 'keyword2', 'keyword3'],
}
```

### Add More Keywords:
Simply add keywords to existing category list:

```python
'tech': ['tech', 'technology', 'ai', 'NEW_KEYWORD_HERE', ...],
```

### Change Priority:
Modify the `priority_categories` list in `_ensure_diversity()` method:

```python
priority_categories = ['politics', 'tech', 'business', 'YOUR_PRIORITY', ...]
```

---

## 🎯 Category Relevance by Age Group

### YOUNG (18-30):
**High Priority:**
- Education (exams, admissions, scholarships)
- Tech (career opportunities, skills)
- Business (job market, startups)

**Medium Priority:**
- Politics (education policies)
- Health (young adult health)
- Entertainment (if relevant)

**Low Priority:**
- Sports (unless career-related)
- Crime (unless major impact)

---

### MIDDLE_AGE (30-55):
**High Priority:**
- Business (investments, economy)
- Politics (tax policies, regulations)
- Health (family health, insurance)

**Medium Priority:**
- Education (children's education)
- Tech (work-related)
- Crime (safety concerns)

**Low Priority:**
- Sports (unless major)
- Entertainment (unless relevant)

---

### OLD (55+):
**High Priority:**
- Health (senior health, medical facilities)
- Politics (pension, benefits)
- Business (savings, inflation)

**Medium Priority:**
- General (senior citizen schemes)
- Crime (safety)

**Low Priority:**
- Tech (unless relevant)
- Sports (unless relevant)
- Entertainment (unless relevant)

---

## 📊 Categorization Accuracy

### Strengths:
✅ Fast and efficient
✅ Works well for clear categories
✅ Handles common news topics

### Limitations:
⚠️ May misclassify ambiguous articles
⚠️ Requires keyword maintenance
⚠️ Doesn't understand context

### Improvements Possible:
- Use AI/ML for better categorization
- Add semantic understanding
- Context-aware classification

---

## 🔍 Debugging Categorization

### Check Category of Article:
```python
from content_generator import ContentGenerator

generator = ContentGenerator()
article = {"title": "RBI announces new policy", "description": "..."}
category = generator._categorize_article(article)
print(category)  # Output: "business"
```

### See All Categories:
```python
articles = [...]  # Your articles
generator = ContentGenerator()

for article in articles:
    category = generator._categorize_article(article)
    print(f"{category}: {article['title']}")
```

---

## 💡 Tips

1. **Keyword Selection**: Use common terms people use when searching
2. **Multiple Keywords**: More keywords = better matching
3. **Update Regularly**: Add new keywords as trends change
4. **Test**: Check categorization on sample articles
5. **Balance**: Ensure categories have similar keyword counts

---

## 📝 Summary

- **Method**: Keyword-based matching
- **Categories**: 9 specific + 1 general
- **Purpose**: Ensure diverse, relevant news selection
- **Location**: `content_generator.py` → `_categorize_article()`
- **Customizable**: Easy to add/modify categories and keywords

The categorization system ensures you get a diverse mix of news that's relevant to your target age group!

