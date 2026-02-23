# YouTube Shorts Engagement Techniques - Prompt Comparison

This document shows how the prompts would change to add cliffhangers, hooks, and other engagement techniques to your news videos.

---

## 1. TITLE PROMPT - Current vs Enhanced

### CURRENT PROMPT (Lines 1603-1614)
```python
title_prompt = f"""Generate a viral, clickbait-style YouTube Shorts title for a 60-second news video.

Today's top news stories:
{news_summary}

Create a catchy, attention-grabbing title that:
- Is under 60 characters
- Uses power words like "SHOCKING", "BREAKING", "YOU WON'T BELIEVE"
- Creates curiosity and urgency
- Is suitable for YouTube Shorts

Return ONLY the title text, nothing else."""
```

### ENHANCED PROMPT (with engagement hooks)
```python
title_prompt = f"""Generate a viral, clickbait-style YouTube Shorts title for a 60-second news video.

Today's top news stories:
{news_summary}

Create a catchy, attention-grabbing title that:
- Is under 60 characters
- Uses power words like "SHOCKING", "BREAKING", "YOU WON'T BELIEVE"
- Creates curiosity and urgency
- Is suitable for YouTube Shorts
- Uses cliffhanger patterns: "Wait until you see #3", "Story #5 will shock you", "You won't believe what happened next"
- Includes countdown hooks: "8 Stories That Changed Everything Today", "Top 8 Breaking News Stories"
- Creates FOMO (Fear of Missing Out): "This Just Happened", "Breaking Right Now", "You Need to See This"

ENGAGEMENT TECHNIQUES TO USE:
1. Question hooks: "Did You Know This Happened Today?"
2. Pattern interrupts: "This Changed Everything..."
3. Number hooks: "8 Stories in 60 Seconds"
4. Urgency: "BREAKING NOW", "JUST IN"
5. Cliffhanger teasers: "Wait for Story #5..."

Return ONLY the title text, nothing else."""
```

**Example Output:**
- Current: "BREAKING: Today's Top Stories in 60 Seconds"
- Enhanced: "8 Stories That Will SHOCK You - Wait for #5! 🔥"

---

## 2. STORY SCRIPT PROMPT - Current vs Enhanced

### CURRENT PROMPT (Lines 1289-1339)
```python
story_prompt = f"""You are a news anchor creating a script segment for ONE news story.

News Story:
Title: {article_title}
Description: {article_desc}

Create TWO segments for this story:
1. HEADLINE segment (EXACTLY {target_headline_duration} seconds): A detailed, informative headline that helps users understand the news
2. SUMMARY segment (EXACTLY {target_summary_duration} seconds): A concise explanation

CRITICAL TIME CONSTRAINTS:
- Average speaking rate: 2.5 words per second
- Headline MUST be {headline_words_max} words or LESS (for {target_headline_duration} seconds)
- Summary MUST be {summary_words_max} words or LESS (for {target_summary_duration} seconds)
- Count your words carefully - exceeding these limits will cause timing issues
- Use clear, engaging language suitable for YouTube Shorts

IMPORTANT FOR HEADLINE:
- Make the headline DETAILED and INFORMATIVE - include key names, places, and what happened
- Use the full {headline_words_max} words to provide context and help users understand the news
- Don't be too brief - include enough information so users can understand the story from the headline alone
- Example: Instead of "Breaking: Karnataka crisis", use "Karnataka Congress leadership crisis deepens as Siddaramaiah and Shivakumar clash publicly over Chief Minister seat"
```

### ENHANCED PROMPT (with cliffhangers and hooks)
```python
story_prompt = f"""You are a news anchor creating a script segment for ONE news story in a YouTube Shorts video.

News Story:
Title: {article_title}
Description: {article_desc}

Story Position: Story {story_number} of {total_stories}

Create TWO segments for this story with MAXIMUM ENGAGEMENT:
1. HEADLINE segment (EXACTLY {target_headline_duration} seconds): A hook-driven, attention-grabbing headline
2. SUMMARY segment (EXACTLY {target_summary_duration} seconds): A concise explanation with a cliffhanger ending

CRITICAL TIME CONSTRAINTS:
- Average speaking rate: 2.5 words per second
- Headline MUST be {headline_words_max} words or LESS (for {target_headline_duration} seconds)
- Summary MUST be {summary_words_max} words or LESS (for {target_summary_duration} seconds)
- Count your words carefully - exceeding these limits will cause timing issues
- Use clear, engaging language suitable for YouTube Shorts

ENGAGEMENT TECHNIQUES FOR HEADLINE:
- Start with a hook: "Wait, this just happened...", "You won't believe this...", "Breaking right now..."
- Use pattern interrupts: "This changes everything...", "This is huge...", "This is shocking..."
- Include urgency: "BREAKING:", "JUST IN:", "URGENT:"
- Make it DETAILED and INFORMATIVE - include key names, places, and what happened
- Use the full {headline_words_max} words to provide context
- Example: Instead of "Breaking: Karnataka crisis", use "BREAKING: Karnataka Congress leadership crisis deepens as Siddaramaiah and Shivakumar clash publicly - this changes everything!"

ENGAGEMENT TECHNIQUES FOR SUMMARY:
- End with a cliffhanger that teases the next story or creates curiosity
- Use phrases like: "But here's what you need to know...", "The shocking detail is...", "Wait until you hear what happened next..."
- If this is NOT the last story, end with: "Up next: [tease next story topic] - you won't believe this!"
- If this IS the last story, end with: "This is developing - stay tuned for updates!"
- Keep viewers engaged and wanting to watch until the end

STORY POSITION AWARENESS:
- If story_number is 1-3: Use strong opening hooks ("BREAKING:", "SHOCKING:", "URGENT:")
- If story_number is 4-6: Use curiosity hooks ("Wait until you see this...", "This just changed...")
- If story_number is 7-8: Use urgency hooks ("FINAL UPDATE:", "LAST STORY:", "You need to see this...")

Format your response as JSON:
{{
  "headline": {{
    "text": "[Hook-driven headline with urgency - MAX {headline_words_max} words]",
    "duration": {target_headline_duration},
    "type": "headline"
  }},
  "summary": {{
    "text": "[Concise explanation with cliffhanger ending - MAX {summary_words_max} words]",
    "duration": {target_summary_duration},
    "type": "summary"
  }},
  "image_prompt": "A detailed, visually striking image representing: [describe the news story visually - ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO SIGNS, NO BANNERS, purely visual elements like people, objects, scenes, landscapes, actions, emotions, atmosphere only]"
}}
```

**Example Output:**

**Current:**
- Headline: "Breaking: Karnataka Congress leadership crisis deepens as Siddaramaiah and Shivakumar clash publicly over Chief Minister seat"
- Summary: "The political crisis in Karnataka has escalated with public disagreements between senior leaders."

**Enhanced:**
- Headline: "BREAKING: Karnataka Congress leadership crisis deepens as Siddaramaiah and Shivakumar clash publicly - this changes everything!"
- Summary: "The political crisis in Karnataka has escalated with public disagreements. But here's what you need to know - this could reshape Indian politics. Up next: You won't believe what happened in Delhi!"

---

## 3. TRANSITION PROMPTS - New Addition

### NEW: TRANSITION GENERATION PROMPT
```python
transition_prompt = f"""Generate a smooth, engaging transition between two news stories in a YouTube Shorts video.

Current Story: {current_story_title}
Next Story: {next_story_title}
Story Position: Moving from story {current_number} to story {next_number} of {total_stories}

Create a transition that:
1. Ends the current story with a cliffhanger or hook
2. Smoothly introduces the next story
3. Creates curiosity and keeps viewers watching
4. Is 2-3 seconds maximum (5-7 words)

TRANSITION PATTERNS TO USE:
- "But wait, there's more... [next story]"
- "Up next: [tease next story] - you won't believe this!"
- "Speaking of [topic], this just happened: [next story]"
- "That's not all - [next story] is breaking right now!"
- "Hold on, this is huge: [next story]"

Return ONLY the transition text, nothing else."""
```

**Example Output:**
- "But wait, there's more... Delhi just made a shocking announcement!"
- "Up next: You won't believe what happened in Mumbai - this is breaking right now!"

---

## 4. CLOSING PROMPT - Current vs Enhanced

### CURRENT CLOSING (Line 1679)
```python
closing_text = "That's today's news. Stay informed!"
```

### ENHANCED CLOSING
```python
closing_prompt = f"""Generate an engaging closing for a YouTube Shorts news video.

Total stories covered: {total_stories}
Last story topic: {last_story_title}

Create a closing that:
1. Summarizes the video briefly (2-3 seconds)
2. Includes a call-to-action (1-2 seconds)
3. Creates urgency for future videos
4. Is 4-5 seconds total (10-12 words)

CLOSING PATTERNS:
- "That's today's top {total_stories} stories. Follow for breaking news updates!"
- "Stay tuned - more breaking news coming tomorrow!"
- "Which story shocked you most? Comment below!"
- "That's today's news. Hit subscribe for daily updates!"
- "Follow for more - breaking news happens every day!"

Return ONLY the closing text, nothing else."""
```

**Example Output:**
- Current: "That's today's news. Stay informed!"
- Enhanced: "That's today's top 8 stories. Which one shocked you most? Comment below and follow for more breaking news!"

---

## 5. VISUAL TEXT OVERLAYS - New Addition

### NEW: ON-SCREEN TEXT GENERATION PROMPT
```python
overlay_prompt = f"""Generate engaging on-screen text overlays for a news story in a YouTube Shorts video.

Story: {story_title}
Story Number: {story_number} of {total_stories}
Story Type: {story_type}  # 'headline' or 'summary'

Create 1-2 short text overlays (2-4 words each) that:
1. Appear at key moments during the story
2. Add visual interest and emphasis
3. Create urgency or curiosity
4. Are suitable for YouTube Shorts

OVERLAY PATTERNS:
- Urgency: "BREAKING NOW", "JUST IN", "URGENT"
- Curiosity: "WAIT FOR IT...", "YOU WON'T BELIEVE", "SHOCKING"
- Progress: "STORY 3 OF 8", "MORE COMING..."
- Emphasis: "THIS IS HUGE", "MAJOR UPDATE", "DEVELOPING"

Return as JSON array:
{{
  "overlays": [
    {{
      "text": "[2-4 word overlay]",
      "start_time": 0.5,  // seconds into segment
      "duration": 1.5,     // seconds to display
      "position": "top"    // "top", "center", or "bottom"
    }}
  ]
}}"""
```

**Example Output:**
```json
{
  "overlays": [
    {
      "text": "BREAKING NOW",
      "start_time": 0.5,
      "duration": 2.0,
      "position": "top"
    },
    {
      "text": "STORY 3 OF 8",
      "start_time": 1.0,
      "duration": 1.5,
      "position": "bottom"
    }
  ]
}
```

---

## 6. HOOK OPENING - New Addition

### NEW: OPENING HOOK PROMPT
```python
opening_hook_prompt = f"""Generate a powerful opening hook for a YouTube Shorts news video.

Total stories: {total_stories}
Top story: {top_story_title}

Create a 3-4 second opening hook (8-10 words) that:
1. Grabs attention immediately
2. Creates curiosity
3. Sets up the video structure
4. Uses engagement techniques

HOOK PATTERNS:
- Countdown: "{total_stories} stories that will shock you in 60 seconds!"
- Question: "Did you know this happened today? Here's what you missed..."
- Pattern interrupt: "This just changed everything. Here's what happened..."
- Urgency: "BREAKING: {total_stories} major stories you need to see right now!"
- Cliffhanger: "Wait until you see story #{total_stories} - it will blow your mind!"

Return ONLY the hook text, nothing else."""
```

**Example Output:**
- "8 stories that will shock you in 60 seconds!"
- "Did you know this happened today? Here's what you missed..."
- "BREAKING: 8 major stories you need to see right now!"

---

## SUMMARY OF CHANGES

### What Gets Added:
1. ✅ **Cliffhanger endings** to each story summary
2. ✅ **Hook-driven headlines** with urgency and pattern interrupts
3. ✅ **Transition phrases** between stories
4. ✅ **Engaging closing** with call-to-action
5. ✅ **On-screen text overlays** for visual emphasis
6. ✅ **Powerful opening hook** to grab attention
7. ✅ **Story position awareness** (different hooks for different positions)

### Expected Impact:
- **Higher watch time**: Cliffhangers keep viewers watching until the end
- **Better engagement**: Hooks grab attention in first 3 seconds
- **More shares**: Engaging content gets shared more
- **Better retention**: Transitions maintain flow and interest

### Implementation Notes:
- All changes maintain the same word count limits
- Timing constraints remain the same
- Can be toggled on/off with a config flag
- Works with existing video generation pipeline

