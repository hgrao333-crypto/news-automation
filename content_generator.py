import ollama
from typing import Dict, List, Optional
import json
import os
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, USE_HOOK_BASED_HEADLINES, USE_CONTEXT_AWARE_OVERLAYS, TEMP_DIR
from llm_client import LLMClient

# Fix huggingface/tokenizers parallelism warning
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')

# Try to import sentence-transformers for semantic similarity
# Falls back to keyword-based method if not available
USE_SEMANTIC_EMBEDDINGS = False
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    USE_SEMANTIC_EMBEDDINGS = True
except ImportError:
    USE_SEMANTIC_EMBEDDINGS = False

class ContentGenerator:
    """Uses LLM (Gemini/OpenRouter/Ollama) to generate news scripts and content"""
    
    def __init__(self):
        self.model = OLLAMA_MODEL
        # Use unified LLM client with fallback support
        self.llm_client = LLMClient()
        # Keep Ollama client for backward compatibility
        try:
            self.client = ollama.Client(host=OLLAMA_BASE_URL)
        except:
            self.client = None
        # Check if model exists, try alternatives if not
        self._ensure_model_available()
        
        # Initialize semantic embedding model for duplicate detection
        self.embedding_model = None
        if USE_SEMANTIC_EMBEDDINGS:
            try:
                # Use a lightweight, fast model optimized for news/sentences
                # all-MiniLM-L6-v2 is small (80MB), fast, and works well for news
                print("  📦 Loading semantic embedding model for duplicate detection...")
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                print("  ✅ Semantic embedding model loaded")
            except Exception as e:
                print(f"  ⚠️  Could not load embedding model: {e}")
                print("  🔄 Falling back to title-based duplicate detection")
                self.embedding_model = None
        else:
            print("  ⚠️  sentence-transformers not available, using title-based duplicate detection")
            print("  💡 Install with: pip install sentence-transformers scikit-learn for better duplicate detection")
    
    def _categorize_article(self, article: Dict) -> str:
        """
        Categorize an article into a news category
        Returns: category name (politics, tech, business, sports, entertainment, health, etc.)
        """
        title = article.get('title', '').lower()
        description = article.get('description', '').lower()
        text = f"{title} {description}"
        
        # Category keywords
        categories = {
            'politics': ['election', 'modi', 'bjp', 'congress', 'government', 'minister', 'parliament', 'political', 'party', 'vote', 'campaign', 'policy', 'law', 'bill', 'assembly', 'cm', 'pm', 'ruling', 'opposition'],
            'tech': ['tech', 'technology', 'ai', 'artificial intelligence', 'startup', 'app', 'software', 'digital', 'internet', 'cyber', 'data', 'innovation', 'it', 'computer', 'mobile', 'phone', 'social media', 'platform'],
            'business': ['business', 'economy', 'market', 'stock', 'rupee', 'rbi', 'bank', 'company', 'corporate', 'trade', 'export', 'import', 'gdp', 'inflation', 'revenue', 'profit', 'investment', 'finance', 'financial'],
            'sports': ['cricket', 'ipl', 'match', 'sport', 'player', 'team', 'tournament', 'championship', 'football', 'hockey', 'olympics', 'athlete', 'game', 'win', 'defeat', 'victory'],
            'entertainment': ['movie', 'film', 'actor', 'actress', 'bollywood', 'celebrity', 'music', 'song', 'award', 'show', 'tv', 'series', 'entertainment'],
            'health': ['health', 'medical', 'hospital', 'doctor', 'disease', 'covid', 'vaccine', 'treatment', 'patient', 'healthcare', 'medicine', 'surgery'],
            'crime': ['crime', 'police', 'arrest', 'murder', 'theft', 'robbery', 'case', 'court', 'judge', 'lawyer', 'trial', 'jail', 'prison'],
            'education': ['education', 'school', 'college', 'university', 'student', 'exam', 'result', 'degree', 'academic'],
            'environment': ['climate', 'environment', 'pollution', 'green', 'solar', 'renewable', 'carbon', 'emission', 'weather', 'flood', 'drought'],
        }
        
        # Score each category
        category_scores = {}
        for category, keywords in categories.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                category_scores[category] = score
        
        # Return category with highest score, or 'general' if no match
        if category_scores:
            return max(category_scores.items(), key=lambda x: x[1])[0]
        return 'general'
    
    def analyze_and_select_important_news(self, articles: List[Dict], select_count: int = 5, ensure_diversity: bool = True) -> List[Dict]:
        """
        Use Ollama to analyze news articles and select the most important ones with diversity
        Returns: List of selected articles sorted by importance, ensuring diverse topics
        """
        if len(articles) <= select_count:
            return articles
        
        # Categorize all articles first
        if ensure_diversity:
            categorized_articles = {}
            for i, article in enumerate(articles):
                category = self._categorize_article(article)
                if category not in categorized_articles:
                    categorized_articles[category] = []
                categorized_articles[category].append((i, article))
            
            print(f"  📊 Categorized articles:")
            for category, items in categorized_articles.items():
                print(f"     {category}: {len(items)} articles")
        
        # Prepare news list for analysis
        news_list = "\n".join([
            f"{i+1}. {article['title']}\n   {article.get('description', '')[:150]}"
            for i, article in enumerate(articles)
        ])
        
        prompt = f"""You are a news editor analyzing today's top news stories. Your task is to identify the MOST IMPORTANT and NEWSWORTHY stories with DIVERSITY.

Here are {len(articles)} news articles:

{news_list}

Analyze these articles and select the top {select_count} MOST IMPORTANT stories that are RELATED TO INDIA.

CRITICAL REQUIREMENT: Only select news stories that are:
- About India, Indian states, Indian cities, Indian people, Indian government, Indian economy
- Indian politics, Indian elections, Indian policies, Indian businesses
- India's international relations, India's role in global events
- Events happening IN India or affecting India directly
- Indian technology, Indian startups, Indian sports (cricket, etc.)
- Indian culture, Indian festivals (if major national significance)

DIVERSITY REQUIREMENT (CRITICAL):
Select stories from DIFFERENT categories to ensure variety:
- Politics (government, elections, policies)
- Technology (tech news, startups, innovation)
- Business (economy, markets, companies)
- Sports (cricket, tournaments, matches)
- Entertainment (movies, celebrities, awards)
- Health (medical news, healthcare)
- Crime (major cases, legal news)
- Education (schools, exams, academic)
- Environment (climate, pollution, weather)
- General (other important news)

AIM FOR: MAXIMUM DIVERSITY - Select {select_count} stories from {select_count} DIFFERENT categories if possible.
Example for 8 stories: 1 politics + 1 sports + 1 tech + 1 business + 1 entertainment + 1 health + 1 crime + 1 education = diverse mix
PRIORITIZE: Getting one story from each category over multiple stories from the same category.

PRIORITY SCORING CRITERIA (weighted):
1. India Relevance Score (40%): MUST be about India or directly affecting India
   - High priority keywords: "India", "Indian", "Delhi", "Mumbai", "Bangalore", "Chennai", "Kolkata", "Hyderabad", "Pune", "Modi", "BJP", "Congress", "RBI", "Indian government", "Indian economy", "Indian rupee", "Indian stock market", "Indian cricket", "Indian tech", "Indian startup"
   - Indian states: "Maharashtra", "Karnataka", "Tamil Nadu", "Gujarat", "Rajasthan", "Uttar Pradesh", "West Bengal", "Punjab", "Haryana", "Kerala", "Telangana", "Andhra Pradesh", "Bihar", "Madhya Pradesh", "Odisha", "Assam", "Jammu and Kashmir"
   - Indian cities: "Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata", "Hyderabad", "Pune", "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Kanpur", "Nagpur", "Indore", "Thane", "Bhopal", "Visakhapatnam", "Patna", "Vadodara", "Ghaziabad"
   - Major events, policy changes, elections IN INDIA, disasters IN INDIA
   
2. Impact Score (25%): National or major regional importance IN INDIA
   - Indian politics, Indian economy, Indian policy changes
   - Major Indian events, Indian elections, Indian government decisions
   
3. Category Diversity (30%): STRONGLY prefer different categories
   - AVOID selecting multiple stories from the same category
   - PRIORITIZE variety: politics, tech, business, sports, entertainment, health, crime, education, environment
   - For {select_count} stories, aim for {select_count} different categories if available
   - Only select a second story from the same category if absolutely necessary
   
4. Recency Score (10%): Breaking news, recent developments (last 24 hours)
   - Prefer fresh news over older stories
   
5. Engagement Potential (5%): Viral-worthy, trending topics
   - Avoid soft news like "Rain expected in Noida tomorrow" (unless major flooding/disaster)
   - Prefer stories with controversy, major announcements, breaking developments

AVOID selecting:
- News NOT about India (international news unless it directly affects India)
- Soft news (weather forecasts, local events unless major)
- Entertainment/celebrity news (unless major Indian celebrity scandal)
- Redundant stories (same event covered multiple times)
- Low-impact regional news (unless it's a major development)
- Multiple stories from the same category (prioritize diversity)

Return your response as a JSON array with the article numbers (1-indexed) of the selected stories, ordered by importance (most important first).
Ensure the selection includes diverse categories if possible.

Example format:
[3, 1, 7, 2, 5]

Return ONLY the JSON array, no explanation or markdown formatting."""

        try:
            # Use unified LLM client with fallback
            response = self.llm_client.generate(prompt, {
                "temperature": 0.3,  # Lower temperature for more consistent analysis
                "num_predict": 200,
            })
            
            content = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            # Extract JSON array
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            # Clean up content
            content = content.strip().strip('[').strip(']')
            # Extract numbers
            import re
            numbers = [int(x.strip()) for x in re.findall(r'\d+', content)]
            
            # Select articles based on indices (convert to 0-indexed)
            selected_articles = []
            seen_indices = set()
            for num in numbers:
                idx = num - 1  # Convert to 0-indexed
                if 0 <= idx < len(articles) and idx not in seen_indices:
                    selected_articles.append(articles[idx])
                    seen_indices.add(idx)
                    if len(selected_articles) >= select_count:
                        break
            
            # If we didn't get enough, fill with remaining articles
            if len(selected_articles) < select_count:
                for i, article in enumerate(articles):
                    if i not in seen_indices:
                        selected_articles.append(article)
                        if len(selected_articles) >= select_count:
                            break
            
            # Post-process to ensure diversity if enabled
            if ensure_diversity and len(selected_articles) >= 3:
                selected_articles = self._ensure_diversity(selected_articles, articles, select_count)
            
            # Print selected categories for verification
            if ensure_diversity:
                print(f"  📊 Selected articles by category:")
                for i, article in enumerate(selected_articles[:select_count], 1):
                    category = self._categorize_article(article)
                    print(f"     {i}. [{category.upper()}] {article['title'][:60]}")
            
            print(f"📊 Analyzed {len(articles)} articles, selected top {len(selected_articles)} most important stories")
            return selected_articles[:select_count]
            
        except Exception as e:
            print(f"⚠️  Error analyzing news with Ollama: {e}")
            print(f"   Falling back to diverse selection from first {select_count * 2} articles")
            # Fallback: try to ensure diversity from available articles
            if ensure_diversity:
                return self._ensure_diversity([], articles[:select_count * 2], select_count)
            return articles[:select_count]
    
    def _ensure_diversity(self, selected_articles: List[Dict], all_articles: List[Dict], target_count: int) -> List[Dict]:
        """
        Ensure selected articles represent diverse news categories
        For 8 stories, prioritize getting 8 different categories (politics, sports, tech, business, etc.)
        """
        # Categorize all articles first
        all_categorized = {}
        for i, article in enumerate(all_articles):
            category = self._categorize_article(article)
            if category not in all_categorized:
                all_categorized[category] = []
            all_categorized[category].append((i, article))
        
        print(f"  📊 Available categories: {', '.join(all_categorized.keys())}")
        
        # Build diverse selection prioritizing unique categories
        diverse_selection = []
        used_indices = set()
        used_categories = set()
        
        # Priority order for categories (to ensure we get diverse types)
        priority_categories = ['politics', 'sports', 'tech', 'business', 'entertainment', 
                               'health', 'crime', 'education', 'environment', 'general']
        
        # First pass: Try to get one article from each category (prioritize important categories)
        for category in priority_categories:
            if len(diverse_selection) >= target_count:
                break
            if category not in all_categorized:
                continue
            if category in used_categories:
                continue
            
            # Get the first article from this category (prefer from selected_articles if available)
            found = False
            for article in selected_articles:
                if self._categorize_article(article) == category:
                    diverse_selection.append(article)
                    used_categories.add(category)
                    # Find index in all_articles
                    for i, a in enumerate(all_articles):
                        if a.get('title') == article.get('title'):
                            used_indices.add(i)
                            found = True
                            break
                    if found:
                        break
            
            # If not found in selected_articles, get from all_articles
            if not found and category in all_categorized:
                for i, article in all_categorized[category]:
                    if i not in used_indices:
                        diverse_selection.append(article)
                        used_categories.add(category)
                        used_indices.add(i)
                        break
        
        # Second pass: Add remaining articles from selected_articles (if they're from new categories)
        for article in selected_articles:
            if len(diverse_selection) >= target_count:
                break
            # Check if already added
            already_added = any(
                a.get('title') == article.get('title') for a in diverse_selection
            )
            if already_added:
                continue
            
            category = self._categorize_article(article)
            # Prefer articles from categories we haven't used yet
            if category not in used_categories:
                diverse_selection.append(article)
                used_categories.add(category)
                # Find index in all_articles
                for i, a in enumerate(all_articles):
                    if a.get('title') == article.get('title'):
                        used_indices.add(i)
                        break
        
        # Third pass: Fill remaining slots from any category
        if len(diverse_selection) < target_count:
            for article in selected_articles:
                if len(diverse_selection) >= target_count:
                    break
                # Check if already added
                already_added = any(
                    a.get('title') == article.get('title') for a in diverse_selection
                )
                if not already_added:
                    diverse_selection.append(article)
                    # Find index in all_articles
                    for i, a in enumerate(all_articles):
                        if a.get('title') == article.get('title'):
                            used_indices.add(i)
                            break
        
        # Fourth pass: Fill any remaining slots from all_articles
        if len(diverse_selection) < target_count:
            for i, article in enumerate(all_articles):
                if len(diverse_selection) >= target_count:
                    break
                if i not in used_indices:
                    diverse_selection.append(article)
                    used_indices.add(i)
        
        # Print diversity summary
        final_categories = [self._categorize_article(a) for a in diverse_selection]
        unique_categories = len(set(final_categories))
        print(f"  ✅ Selected {len(diverse_selection)} stories from {unique_categories} different categories:")
        for i, article in enumerate(diverse_selection, 1):
            category = self._categorize_article(article)
            print(f"     {i}. [{category.upper()}] {article.get('title', '')[:60]}")
        
        return diverse_selection[:target_count]
    
    def _review_content_accuracy(self, article: Dict, headline_text: str, summary_text: str, 
                                 headline_words_max: int, summary_words_max: int, 
                                 is_second_review: bool = False) -> Dict:
        """
        Review headline and summary for accuracy against the original article.
        This is called twice to ensure correctness.
        """
        article_title = article.get('title', '')
        article_desc = article.get('description', '')[:300]
        
        review_prompt = f"""You are a fact-checker reviewing news content for accuracy.

ORIGINAL ARTICLE:
Title: {article_title}
Description: {article_desc}

GENERATED CONTENT TO REVIEW:
Headline: {headline_text}
Summary: {summary_text}

Your task:
1. Check if the headline accurately represents the main point of the article
2. Check if the summary correctly explains what happened based on the article
3. Ensure no false information, exaggeration, or misinterpretation
4. Verify facts match the original article
5. Headline word count: Accept headlines between 10-25 words (ideal range). Only flag if less than 10 or more than 25 words.
6. Summary word count: Must be {summary_words_max} words or less

If the content is ACCURATE and CORRECT, return it as-is.
If there are ERRORS or INACCURACIES, provide CORRECTED versions.

Return your response as JSON:
{{
  "is_accurate": true/false,
  "headline": {{
    "text": "[corrected headline if needed, or original if accurate]",
    "duration": [duration],
    "type": "headline"
  }},
  "summary": {{
    "text": "[corrected summary if needed, or original if accurate]",
    "duration": [duration],
    "type": "summary"
  }},
  "image_prompt": "[keep original image prompt]",
  "issues_found": ["list any issues found, or empty array if none"]
}}

CRITICAL:
- If content is accurate, return it unchanged
- If inaccurate, provide corrected version
- Headline word count: Accept 10-25 words (this is the acceptable range). Do NOT flag headlines in this range as issues.
- Summary word count: Must be {summary_words_max} words or less
- Ensure facts match the original article exactly
- Do not add information not in the original article
- Do not remove important facts from the original article
- IMPORTANT: Do NOT flag headlines that are between 10-25 words as having word count issues

Return ONLY valid JSON, no markdown formatting."""

        try:
            # Use unified LLM client with fallback
            # Increase num_predict to ensure complete JSON responses
            response = self.llm_client.generate(review_prompt, {
                "temperature": 0.2,  # Lower temperature for more accurate review
                "num_predict": 600,  # Increased to ensure complete JSON responses
            })
            
            content = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            
            # Handle empty or invalid responses
            if not content or len(content) < 10:
                raise ValueError("Empty or too short response from LLM")
            
            # Extract JSON from markdown code blocks if present
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            # Try to repair JSON before parsing
            content = self._repair_json_string(content)
            
            # Try to parse JSON with better error handling
            try:
                reviewed = json.loads(content.strip())
            except json.JSONDecodeError as e:
                # Try to extract JSON object from response
                print(f"    ⚠️  JSON parsing error: {e}")
                print(f"    📄 Response preview: {content[:300]}...")
                
                # Try to find JSON object boundaries
                if '{' in content and '}' in content:
                    start_idx = content.find('{')
                    end_idx = content.rfind('}') + 1
                    if start_idx < end_idx:
                        try:
                            json_str = content[start_idx:end_idx]
                            # Try to repair the extracted JSON
                            json_str = self._repair_json_string(json_str)
                            reviewed = json.loads(json_str)
                            print(f"    ✅ Extracted and repaired JSON from response")
                        except json.JSONDecodeError as e2:
                            print(f"    ⚠️  Could not parse even after repair: {e2}")
                            raise ValueError(f"Could not parse JSON even after extraction and repair: {e}")
                    else:
                        raise ValueError(f"Invalid JSON structure: {e}")
                else:
                    raise ValueError(f"No JSON found in response: {e}")
            
            # Check if corrections were made
            is_accurate = reviewed.get('is_accurate', True)
            issues = reviewed.get('issues_found', [])
            
            if issues:
                review_num = "Second" if is_second_review else "First"
                print(f"    ⚠️  {review_num} review found issues: {', '.join(issues)}")
                if not is_accurate:
                    print(f"    ✅ Corrected content provided")
            else:
                review_num = "Second" if is_second_review else "First"
                print(f"    ✅ {review_num} review: Content is accurate")
            
            # Get reviewed content
            reviewed_headline = reviewed.get('headline', {})
            reviewed_summary = reviewed.get('summary', {})
            # Don't use image_prompt from review - it might be generic
            # We'll generate proper image prompts separately
            image_prompt = None  # Will be generated separately with detailed prompts
            
            # Ensure word counts are still within limits
            headline_text = reviewed_headline.get('text', headline_text)
            summary_text = reviewed_summary.get('text', summary_text)
            headline_words = len(headline_text.split())
            summary_words = len(summary_text.split())
            
            # Headline validation: Accept 10-25 words, only trim if >25 words
            if headline_words > 25:
                # More than 25 words - trim to 25 words max
                words = headline_text.split()
                headline_text = ' '.join(words[:25])
                headline_words = len(headline_text.split())
                print(f"    ⚠️  Trimmed headline from {len(words)} to {headline_words} words (exceeded 25-word limit)")
            elif headline_words < 10:
                # Less than 10 words - this is okay, but log it
                print(f"    ℹ️  Headline has {headline_words} words (less than 10, but acceptable)")
            # If 10-25 words, keep as-is (no trimming needed)
            
            if summary_words > summary_words_max:
                words = summary_text.split()
                summary_text = ' '.join(words[:summary_words_max])
                summary_words = len(summary_text.split())
            
            # Calculate durations
            headline_duration = headline_words / 2.5
            summary_duration = summary_words / 2.5
            
            return {
                'headline': {
                    'text': headline_text,
                    'duration': round(headline_duration, 1),
                    'type': 'headline'
                },
                'summary': {
                    'text': summary_text,
                    'duration': round(summary_duration, 1),
                    'type': 'summary'
                },
                'image_prompt': image_prompt
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"    ⚠️  Review failed: {error_msg}")
            print(f"    🔄 Regenerating content with feedback about the failure...")
            
            # Regenerate content with feedback about the failure
            regenerated = self._regenerate_content_with_feedback(
                article, headline_text, summary_text, headline_words_max, summary_words_max, error_msg
            )
            
            if regenerated:
                return regenerated
            else:
                # Fallback to original if regeneration also fails
                print(f"    ⚠️  Regeneration also failed, using original content")
                return {
                    'headline': {
                        'text': headline_text,
                        'duration': len(headline_text.split()) / 2.5,
                        'type': 'headline'
                    },
                    'summary': {
                        'text': summary_text,
                        'duration': len(summary_text.split()) / 2.5,
                        'type': 'summary'
                    },
                'image_prompt': f"Breaking news: {article_title[:50]}"
            }
    
    def _regenerate_content_with_feedback(
        self, article: Dict, headline_text: str, summary_text: str,
        headline_words_max: int, summary_words_max: int, error_message: str
    ) -> Optional[Dict]:
        """
        Regenerate headline and summary with feedback about the review failure
        """
        article_title = article.get('title', '')
        article_desc = article.get('description', '')[:300]
        
        regenerate_prompt = f"""You are a news anchor creating content for a news video. The previous review attempt failed with this error: "{error_message}"

ORIGINAL ARTICLE:
Title: {article_title}
Description: {article_desc}

PREVIOUS ATTEMPT (that failed review):
Headline: {headline_text}
Summary: {summary_text}

IMPORTANT: The review process failed because: {error_message}

Your task:
1. Generate a NEW headline and summary based on the original article
2. Ensure accuracy - facts must match the original article exactly
3. Respect word limits: Headline MAX {headline_words_max} words, Summary MAX {summary_words_max} words
4. Make it engaging and suitable for YouTube Shorts
5. Ensure the content is factually correct and matches the article

Return your response as JSON:
{{
  "headline": {{
    "text": "[new headline text - MAX {headline_words_max} words, accurate and engaging]",
    "duration": [calculated duration],
    "type": "headline"
  }},
  "summary": {{
    "text": "[new summary text - MAX {summary_words_max} words, accurate and informative]",
    "duration": [calculated duration],
    "type": "summary"
  }}
}}

CRITICAL REQUIREMENTS:
- Headline: EXACTLY {headline_words_max} words or less
- Summary: EXACTLY {summary_words_max} words or less
- All facts must match the original article
- No false information or exaggeration
- Use clear, engaging language

Return ONLY valid JSON, no markdown formatting."""
        
        try:
            # Use unified LLM client with fallback
            response = self.llm_client.generate(regenerate_prompt, {
                "temperature": 0.3,  # Lower temperature for more reliable JSON
                "num_predict": 600,  # Increased to ensure complete JSON responses
            })
            
            content = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            
            # Handle empty or invalid responses
            if not content or len(content) < 10:
                print(f"    ⚠️  Regeneration also returned empty response")
                return None
            
            # Extract JSON from markdown code blocks if present
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            # Try to repair JSON before parsing
            content = self._repair_json_string(content)
            
            # Try to parse JSON
            try:
                regenerated = json.loads(content.strip())
            except json.JSONDecodeError as e:
                # Try to extract JSON object from response
                print(f"    ⚠️  Could not parse regenerated JSON: {e}")
                if '{' in content and '}' in content:
                    start_idx = content.find('{')
                    end_idx = content.rfind('}') + 1
                    if start_idx < end_idx:
                        try:
                            json_str = content[start_idx:end_idx]
                            # Try to repair the extracted JSON
                            json_str = self._repair_json_string(json_str)
                            regenerated = json.loads(json_str)
                            print(f"    ✅ Extracted and repaired JSON from regenerated response")
                        except json.JSONDecodeError as e2:
                            print(f"    ⚠️  Could not parse even after repair: {e2}")
                            return None
                    else:
                        return None
                else:
                    return None
            
            # Extract regenerated content
            regenerated_headline = regenerated.get('headline', {})
            regenerated_summary = regenerated.get('summary', {})
            
            new_headline_text = regenerated_headline.get('text', headline_text)
            new_summary_text = regenerated_summary.get('text', summary_text)
            
            # Validate word counts
            headline_words = len(new_headline_text.split())
            summary_words = len(new_summary_text.split())
            
            # Trim if needed
            if headline_words > headline_words_max:
                words = new_headline_text.split()
                new_headline_text = ' '.join(words[:headline_words_max])
                headline_words = len(new_headline_text.split())
            
            if summary_words > summary_words_max:
                words = new_summary_text.split()
                new_summary_text = ' '.join(words[:summary_words_max])
                summary_words = len(new_summary_text.split())
            
            # Calculate durations
            headline_duration = headline_words / 2.5
            summary_duration = summary_words / 2.5
            
            print(f"    ✅ Regenerated content successfully")
            print(f"       New headline ({headline_words} words): {new_headline_text[:60]}...")
            print(f"       New summary ({summary_words} words): {new_summary_text[:60]}...")
            
            return {
                'headline': {
                    'text': new_headline_text,
                    'duration': round(headline_duration, 1),
                    'type': 'headline'
                },
                'summary': {
                    'text': new_summary_text,
                    'duration': round(summary_duration, 1),
                    'type': 'summary'
                },
                'image_prompt': None  # Will be generated separately
            }
            
        except Exception as e:
            print(f"    ⚠️  Error during regeneration: {e}")
            return None
    
    def _repair_json_string(self, json_str: str) -> str:
        """
        Attempt to repair common JSON issues like unterminated strings, unescaped quotes, etc.
        """
        import re
        
        if not json_str or len(json_str.strip()) < 2:
            return json_str
        
        # Remove leading/trailing whitespace
        json_str = json_str.strip()
        
        # Remove markdown code blocks if present
        if '```json' in json_str:
            json_str = json_str.split('```json')[1].split('```')[0].strip()
        elif '```' in json_str:
            json_str = json_str.split('```')[1].split('```')[0].strip()
        
        # Try to find JSON object boundaries
        if '{' not in json_str:
            return json_str
        
        start_idx = json_str.find('{')
        # Find matching closing brace
        brace_count = 0
        end_idx = start_idx
        for i in range(start_idx, len(json_str)):
            if json_str[i] == '{':
                brace_count += 1
            elif json_str[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        # Extract JSON object
        if end_idx > start_idx:
            json_str = json_str[start_idx:end_idx]
        
        # Fix common issues:
        # 1. Unescaped quotes in strings
        # Pattern: find strings and escape quotes inside them
        # This is complex, so we'll use a simpler approach
        
        # 2. Unterminated strings - find strings that don't have closing quotes
        # Process character by character to track string state properly
        repaired = ""
        in_string = False
        escape_next = False
        i = 0
        
        while i < len(json_str):
            char = json_str[i]
            
            if escape_next:
                repaired += char
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                escape_next = True
                repaired += char
                i += 1
                continue
            
            if char == '"':
                in_string = not in_string
                repaired += char
            else:
                repaired += char
            
            i += 1
        
        # If we're still in a string at the end, try to close it intelligently
        if in_string:
            # Look for context clues - if we're in a value field, close the string
            # Check if we're after a colon (likely a value) or after a comma (next field)
            last_colon = repaired.rfind(':')
            last_comma = repaired.rfind(',')
            last_brace = repaired.rfind('}')
            
            # If we have a colon and we're in a value context, close the string
            if last_colon > 0:
                # Find the position where we should close
                # Look backwards from end to find where the string value should end
                # Usually before a comma, closing brace, or newline
                # Try to find a reasonable place to close
                if last_comma > last_colon or (last_brace > last_colon and last_comma < last_colon):
                    # We're likely in a value field, close it
                    repaired += '"'
                    in_string = False
                else:
                    # Just close it at the end
                    repaired += '"'
                    in_string = False
            else:
                # No clear context, just close it
                repaired += '"'
                in_string = False
        
        # 3. Handle truncation - remove incomplete field at the end if JSON was cut off
        # Look for patterns like: "key": "incomplete value... (truncated)
        # Remove the last incomplete field if it looks truncated
        if repaired.rstrip().endswith(','):
            # Remove trailing comma
            repaired = repaired.rstrip().rstrip(',')
        
        # Check if the last field looks incomplete (ends with colon but no value, or incomplete string)
        # Pattern: "key": "incomplete... (no closing quote)
        # We'll try to remove incomplete fields at the end
        last_colon_idx = repaired.rfind(':')
        if last_colon_idx > 0:
            # Check if there's a value after the colon
            after_colon = repaired[last_colon_idx + 1:].strip()
            # If after colon is empty or just whitespace, or starts with quote but doesn't end with quote
            if not after_colon or (after_colon.startswith('"') and not after_colon.rstrip().endswith('"')):
                # This field is incomplete, try to remove it
                # Find the start of this field (look for the key)
                before_colon = repaired[:last_colon_idx]
                # Find the start of the key (look backwards for quote and comma or opening brace)
                key_start = before_colon.rfind('"')
                if key_start > 0:
                    # Check if there's a comma before the key
                    before_key = repaired[:key_start].rstrip()
                    if before_key.endswith(','):
                        # Remove the incomplete field including the comma
                        repaired = before_key.rstrip(',').rstrip()
                    elif before_key.endswith('{'):
                        # This is the first field, just remove it
                        repaired = before_key + '{'
        
        # 4. Close unclosed braces/brackets
        open_braces = repaired.count('{') - repaired.count('}')
        open_brackets = repaired.count('[') - repaired.count(']')
        
        if open_braces > 0:
            repaired += '}' * open_braces
        if open_brackets > 0:
            repaired += ']' * open_brackets
        
        # 5. Fix trailing commas before closing braces/brackets
        repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)
        
        # 5. Ensure proper escaping of quotes in string values
        # This is tricky - we'll try to fix obvious cases
        # Pattern: "text"text" -> "text\"text"
        # But this is complex, so we'll leave it for now
        
        return repaired
    
    def _regenerate_shorter_headline(
        self, article: Dict, headline_words_max: int, target_headline_duration: int, original_headline: str
    ) -> Optional[str]:
        """
        Regenerate a shorter headline (10-25 words) when the original is too long (>25 words)
        """
        article_title = article.get('title', '')
        article_desc = article.get('description', '')[:200]
        
        regenerate_prompt = f"""You are a news anchor creating a headline for a news story. The previous headline was too long ({len(original_headline.split())} words).

ORIGINAL ARTICLE:
Title: {article_title}
Description: {article_desc}

ORIGINAL HEADLINE (too long):
"{original_headline}"

Your task:
1. Create a NEW, SHORTER headline that is between 10-25 words
2. Keep all the key information: names, places, what happened
3. Make it detailed and informative - use the full 10-25 word range to provide context
4. Ensure accuracy - facts must match the original article exactly
5. Make it engaging and suitable for YouTube Shorts

IMPORTANT:
- Headline MUST be between 10-25 words (preferably 15-20 words)
- Include key names, places, and what happened
- Don't be too brief - provide enough context for users to understand
- Example: "Karnataka Congress leadership crisis deepens as Siddaramaiah and Shivakumar clash publicly over Chief Minister seat" (18 words)

Return ONLY the headline text, nothing else. No prefixes like "Breaking:" or "News:"."""

        try:
            response = self.llm_client.generate(regenerate_prompt, {
                "temperature": 0.7,
                "num_predict": 200,
            })
            
            new_headline = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            
            # Clean up
            new_headline = new_headline.strip('"').strip("'")
            if '```' in new_headline:
                new_headline = new_headline.split('```')[0].strip()
            
            # Remove common prefixes
            for prefix in ["Breaking:", "Breaking", "Next:", "Also:", "News:", "Update:"]:
                if new_headline.startswith(prefix):
                    new_headline = new_headline[len(prefix):].strip()
            
            # Validate word count
            word_count = len(new_headline.split())
            if 10 <= word_count <= 25:
                print(f"    ✅ Regenerated headline: {word_count} words")
                return new_headline
            elif word_count < 10:
                # Too short, try to expand it
                print(f"    ⚠️  Regenerated headline too short ({word_count} words), keeping original logic")
                return None
            else:
                # Still too long, return None to trigger fallback
                print(f"    ⚠️  Regenerated headline still too long ({word_count} words), will use fallback")
                return None
                
        except Exception as e:
            print(f"    ⚠️  Error regenerating shorter headline: {e}")
            return None
    
    def _regenerate_story_script_with_feedback(
        self, article: Dict, headline_words_max: int, summary_words_max: int,
        target_headline_duration: int, target_summary_duration: int,
        error_message: str, partial_response: str = ""
    ) -> Optional[Dict]:
        """
        Regenerate story script (headline + summary) with feedback about JSON parsing failure
        """
        article_title = article.get('title', '')
        article_desc = article.get('description', '')[:200]
        
        regenerate_prompt = f"""You are a news anchor creating a script segment for ONE news story. The previous generation attempt failed with this error: "{error_message}"

ORIGINAL ARTICLE:
Title: {article_title}
Description: {article_desc}

PREVIOUS ATTEMPT (that failed):
{f"Partial response received: {partial_response[:300]}..." if partial_response else "No valid response was received"}

IMPORTANT: The script generation failed because: {error_message}
Common causes:
- Malformed JSON (unterminated strings, unescaped quotes, missing brackets)
- Response was cut off mid-generation
- Invalid JSON structure

Your task:
1. Generate a NEW headline and summary based on the original article
2. Ensure accuracy - facts must match the original article exactly
3. Respect word limits: Headline MAX {headline_words_max} words, Summary MAX {summary_words_max} words
4. Make it engaging and suitable for YouTube Shorts
5. CRITICAL: Return ONLY valid, properly formatted JSON

Return your response as JSON:
{{
  "headline": {{
    "text": "[new headline text - MAX {headline_words_max} words, accurate and engaging]",
    "duration": {target_headline_duration},
    "type": "headline"
  }},
  "summary": {{
    "text": "[new summary text - MAX {summary_words_max} words, accurate and informative]",
    "duration": {target_summary_duration},
    "type": "summary"
  }},
  "image_prompt": "[detailed visual description - NO TEXT, NO WORDS, purely visual elements]"
}}

CRITICAL JSON REQUIREMENTS:
- Headline: EXACTLY {headline_words_max} words or less
- Summary: EXACTLY {summary_words_max} words or less
- All strings must be properly escaped (use \\" for quotes inside strings)
- Ensure all brackets and braces are properly closed
- No unterminated strings
- No trailing commas before closing braces
- Return ONLY valid JSON, no markdown formatting, no code blocks
- Start with {{ and end with }}
- Test your JSON before returning it - it must be parseable

EXAMPLE OF VALID JSON:
{{
  "headline": {{
    "text": "Breaking: Major development announced",
    "duration": {target_headline_duration},
    "type": "headline"
  }},
  "summary": {{
    "text": "Officials confirmed the news today after weeks of speculation.",
    "duration": {target_summary_duration},
    "type": "summary"
  }},
  "image_prompt": "Editorial illustration showing dramatic scene"
}}

Return ONLY valid JSON matching this exact structure, no markdown formatting."""
        
        try:
            # Use unified LLM client with fallback
            response = self.llm_client.generate(regenerate_prompt, {
                "temperature": 0.3,  # Lower temperature for more reliable JSON
                "num_predict": 500,  # Increased to ensure complete response
            })
            
            content = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            
            # Handle empty or invalid responses
            if not content or len(content) < 10:
                print(f"    ⚠️  Regeneration also returned empty response (length: {len(content) if content else 0})")
                print(f"    📄 Response preview: {content[:200] if content else 'None'}...")
                # Try one more time with even more explicit instructions
                retry_prompt = f"""CRITICAL: You MUST return valid JSON. The previous attempt returned an empty response.

{regenerate_prompt}

IMPORTANT: Return ONLY valid JSON. Start with {{ and end with }}. Ensure all strings are properly closed with quotes."""
                
                retry_response = self.llm_client.generate(retry_prompt, {
                    "temperature": 0.2,
                    "num_predict": 600,
                })
                content = retry_response.get('response', '').strip() if isinstance(retry_response, dict) else str(retry_response).strip()
                
                if not content or len(content) < 10:
                    print(f"    ⚠️  Retry also returned empty response")
                    return None
            
            # Extract JSON from markdown code blocks if present
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            # Try to parse JSON
            try:
                regenerated = json.loads(content.strip())
            except json.JSONDecodeError as e:
                # Try to repair JSON first
                repaired_content = self._repair_json_string(content)
                if repaired_content != content:
                    try:
                        regenerated = json.loads(repaired_content.strip())
                        print(f"    ✅ Repaired regenerated JSON and parsed successfully")
                    except json.JSONDecodeError as e2:
                        print(f"    ⚠️  Repair attempt failed: {e2}")
                        # Continue to extraction logic
                
                # If repair didn't work, try to extract JSON object from response
                if 'regenerated' not in locals():
                    print(f"    ⚠️  Regenerated JSON also has parsing error: {e}")
                    print(f"    📄 Regenerated response preview: {content[:300]}...")
                    if '{' in content and '}' in content:
                        start_idx = content.find('{')
                        end_idx = content.rfind('}') + 1
                        if start_idx < end_idx:
                            try:
                                json_str = content[start_idx:end_idx]
                                # Try to repair the extracted JSON
                                json_str = self._repair_json_string(json_str)
                                regenerated = json.loads(json_str)
                                print(f"    ✅ Extracted and repaired JSON from regenerated response")
                            except json.JSONDecodeError as e2:
                                print(f"    ⚠️  Could not parse regenerated JSON even after extraction and repair: {e2}")
                                return None
                        else:
                            return None
                    else:
                        return None
            
            # Extract regenerated content
            regenerated_headline = regenerated.get('headline', {})
            regenerated_summary = regenerated.get('summary', {})
            image_prompt = regenerated.get('image_prompt', f"Breaking news: {article_title[:50]}")
            
            headline_text = regenerated_headline.get('text', '')
            summary_text = regenerated_summary.get('text', '')
            
            # Validate word counts
            headline_words = len(headline_text.split())
            summary_words = len(summary_text.split())
            
            # Trim if needed
            if headline_words > headline_words_max:
                words = headline_text.split()
                headline_text = ' '.join(words[:headline_words_max])
                headline_words = len(headline_text.split())
            
            if summary_words > summary_words_max:
                words = summary_text.split()
                summary_text = ' '.join(words[:summary_words_max])
                summary_words = len(summary_text.split())
            
            # Calculate durations
            headline_duration = headline_words / 2.5
            summary_duration = summary_words / 2.5
            
            print(f"    ✅ Regenerated script successfully")
            print(f"       New headline ({headline_words} words): {headline_text[:60]}...")
            print(f"       New summary ({summary_words} words): {summary_text[:60]}...")
            
            return {
                'headline': {
                    'text': headline_text,
                    'duration': round(headline_duration, 1),
                    'type': 'headline'
                },
                'summary': {
                    'text': summary_text,
                    'duration': round(summary_duration, 1),
                    'type': 'summary'
                },
                'image_prompt': image_prompt
            }
            
        except Exception as e:
            print(f"    ⚠️  Error during script regeneration: {e}")
            return None
    
    def _combine_headline_summary(self, headline_text: str, summary_text: str, article: Dict) -> str:
        """
        Combine headline and summary into one concise, punchy segment without repetition.
        Example: "Civil war in Karnataka Congress? Siddaramaiah and Shivakumar are publicly clashing over the CM seat, forcing the High Command to step in."
        """
        # Remove common prefixes from headline
        headline_clean = headline_text
        for prefix in ["Breaking:", "Breaking", "Next:", "Also:", "News:", "Update:"]:
            if headline_clean.startswith(prefix):
                headline_clean = headline_clean[len(prefix):].strip()
        
        # Use LLM to intelligently combine without repetition
        combine_prompt = f"""You are a news anchor creating ONE concise, punchy news segment.

Article Title: {article.get('title', '')}
Article Description: {article.get('description', '')[:200]}

Headline: {headline_clean}
Summary: {summary_text}

Combine these into ONE concise, engaging news segment that:
1. Starts immediately with the key information (no "Here's what's happening" or passive language)
2. Combines headline and summary into ONE flowing narrative
3. Eliminates repetition - don't say the same thing twice
4. Uses active, urgent language (e.g., "Civil war in Karnataka Congress?" instead of "Here is what is happening")
5. Includes specific names, places, and details from the summary
6. Is punchy and attention-grabbing (suitable for YouTube Shorts)
7. Maximum 25-30 words total

Example format:
"Civil war in Karnataka Congress? Siddaramaiah and Shivakumar are publicly clashing over the CM seat, forcing the High Command to step in."

Return ONLY the combined text, nothing else. Start immediately with the story - no intro phrases."""

        try:
            response = self.llm_client.generate(combine_prompt, {
                "temperature": 0.7,
                "num_predict": 150,
            })
            
            combined = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            
            # Clean up
            combined = combined.strip('"').strip("'")
            if '```' in combined:
                combined = combined.split('```')[0].strip()
            
            # Fallback if LLM fails
            if not combined or len(combined) < 10:
                # Simple fallback: combine intelligently
                if headline_clean.lower() in summary_text.lower():
                    # Headline is already in summary, just use summary
                    combined = summary_text
                else:
                    # Combine: headline + summary (remove redundant words)
                    combined = f"{headline_clean}. {summary_text}"
                    # Remove obvious repetition
                    words = combined.split()
                    seen = set()
                    unique_words = []
                    for word in words:
                        word_lower = word.lower().strip('.,!?')
                        if word_lower not in seen or len(word_lower) <= 3:  # Keep short words
                            unique_words.append(word)
                            seen.add(word_lower)
                    combined = ' '.join(unique_words)
            
            return combined[:200]  # Limit length
            
        except Exception as e:
            print(f"  ⚠️  Error combining headline+summary: {e}, using simple combination")
            # Simple fallback
            headline_clean = headline_text.replace("Breaking:", "").replace("Next:", "").replace("Also:", "").strip()
            if headline_clean.lower() in summary_text.lower():
                return summary_text[:200]
            else:
                return f"{headline_clean}. {summary_text}"[:200]
    
    def _generate_detailed_image_prompt(self, article: Dict, headline_text: str, summary_text: str) -> str:
        """
        Generate a detailed, comprehensive image prompt (80-150 words) for a news story
        """
        article_title = article.get('title', '')
        article_desc = article.get('description', '')[:300]
        
        prompt = f"""You are creating a detailed image generation prompt for an editorial news video with dramatic, stylized visuals.

News Article:
Title: {article_title}
Description: {article_desc}

Headline: {headline_text}
Summary: {summary_text}

Create a comprehensive, detailed image generation prompt (80-150 words) that:
1. Uses CONCEPT ILLUSTRATION style - editorial, dramatic, stylized art (NOT photorealistic)
2. Uses VISUAL METAPHORS and SYMBOLS instead of literal representations
3. Uses SATIRICAL or EDITORIAL art styles (stylized, expressive, dramatic)
4. AVOIDS photorealistic faces or actual people - use silhouettes, abstract figures, symbolic representations
5. Describes composition, lighting, colors, mood, and visual style in editorial/artistic terms
6. Optimized for vertical video format (9:16 aspect ratio)
7. CRITICAL: ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO SIGNS, NO BANNERS, NO HEADLINES - purely visual elements only

Focus on:
- CONCEPT ILLUSTRATIONS: Use symbolic, metaphorical, or abstract visual representations
- EDITORIAL ART STYLE: Stylized, dramatic, expressive illustrations (like editorial cartoons or magazine illustrations)
- VISUAL METAPHORS: Represent concepts through symbols, objects, scenes, compositions
- AVOID photorealistic people: Use silhouettes, abstract human forms, symbolic figures, or focus on objects/scenes
- SATIRICAL ELEMENTS: When appropriate, use exaggerated, stylized, or satirical visual elements
- Composition, lighting, colors, mood, atmosphere in editorial/artistic style
- Make it feel editorial and dramatic, not fake - audiences accept stylized illustrations for news

IMPORTANT: 
- Be highly descriptive (80-150 words)
- Use CONCEPT ILLUSTRATION style, NOT photorealistic photography
- Use VISUAL METAPHORS and SYMBOLS instead of literal people/faces
- Use EDITORIAL/SATIRICAL art styles (stylized, dramatic, expressive)
- AVOID generating actual faces or photorealistic people - use silhouettes, abstract forms, or focus on objects/scenes
- ABSOLUTELY DO NOT mention or describe any text, words, letters, numbers, signs, banners, headlines, written content
- Focus on visual metaphors, symbols, abstract representations, stylized illustrations
- Describe what you SEE in editorial/artistic terms, not photorealistic terms

Return ONLY the image prompt text, nothing else. Be thorough and descriptive."""

        try:
            # Use unified LLM client with fallback
            response = self.llm_client.generate(prompt, {
                "temperature": 0.7,
                "num_predict": 300,
            })
            
            image_prompt = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            
            # Clean up the prompt
            import re
            # Remove HTML tags
            image_prompt = re.sub(r'<[^>]+>', '', image_prompt)
            # Remove HTML entities
            image_prompt = image_prompt.replace('&nbsp;', ' ').replace('&amp;', '&')
            image_prompt = image_prompt.replace('&lt;', '<').replace('&gt;', '>')
            image_prompt = image_prompt.replace('&quot;', '"').replace('&#39;', "'")
            # Clean up quotes and markdown
            image_prompt = image_prompt.strip('"').strip("'")
            if '```' in image_prompt:
                image_prompt = image_prompt.split('```')[0].strip()
            # Clean up extra whitespace
            image_prompt = ' '.join(image_prompt.split())
            
            # Remove any text-related words from the prompt itself
            text_keywords = ['text', 'word', 'letter', 'headline', 'title', 'caption', 'sign', 'banner', 'newspaper', 'magazine', 'screen with text', 'monitor with text']
            prompt_words = image_prompt.split()
            filtered_words = [w for w in prompt_words if not any(keyword in w.lower() for keyword in text_keywords)]
            image_prompt = ' '.join(filtered_words)
            
            # Validate prompt quality
            if len(image_prompt) < 50 or image_prompt.startswith('<img') or 'src=' in image_prompt.lower():
                # Fallback to detailed description based on article
                image_prompt = f"Professional news broadcast scene depicting: {article_title}. Realistic, detailed visual representation with appropriate lighting, composition, and atmosphere. Vertical format, absolutely no text elements."
            
            print(f"    ✅ Generated detailed prompt ({len(image_prompt)} chars)")
            return image_prompt
            
        except Exception as e:
            print(f"    ⚠️  Error generating detailed prompt: {e}, using fallback")
            # Fallback to article-based prompt
            return f"Professional news broadcast scene depicting: {article_title}. Realistic, detailed visual representation with appropriate lighting, composition, and atmosphere. Vertical format, no text elements."
    
    def _ensure_model_available(self):
        """Check if model is available, try alternatives if not"""
        try:
            # Try to list models to see what's available (only if Ollama client exists)
            if self.client is None:
                return
            models = self.client.list()
            available_models = [m['name'] for m in models.get('models', [])]
            
            if self.model not in available_models:
                # Try common alternatives (check both exact match and partial match)
                alternatives = ['llama3.1', 'llama3', 'llama2', 'mistral', 'phi3', 'gemma', 'gpt-oss']
                for alt in alternatives:
                    # Check if any available model contains this alternative
                    for model_name in available_models:
                        if alt.lower() in model_name.lower():
                            print(f"⚠️  Model '{self.model}' not found. Using '{model_name}' instead.")
                            self.model = model_name
                            return
                
                # If no alternative found, print available models
                print(f"⚠️  Model '{self.model}' not found.")
                print(f"Available models: {', '.join(available_models) if available_models else 'None'}")
                print("Please install a model with: ollama pull llama3.2")
        except Exception as e:
            print(f"⚠️  Could not check Ollama models: {e}")
            print("Make sure Ollama is running: ollama serve")
    
    def _generate_single_story_script(self, article: Dict, story_number: int, total_stories: int) -> Dict:
        """Generate script for a single news story (headline + summary pair)"""
        
        article_title = article.get('title', '')
        article_desc = article.get('description', '')[:200]
        
        # Calculate exact time constraints based on number of stories
        # For headline-only segments, allow more words for better understanding
        if total_stories <= 3:
            target_headline_duration = 6
            target_summary_duration = 12
            headline_words_max = 25  # Increased from 15 - allow more detailed headlines
            summary_words_max = 30   # 12 seconds * 2.5 words/sec
        elif total_stories == 4:
            target_headline_duration = 5
            target_summary_duration = 8
            headline_words_max = 20  # Increased from 12 - allow more detailed headlines
            summary_words_max = 20   # 8 seconds * 2.5 words/sec
        elif total_stories <= 7:
            target_headline_duration = 7  # Increased duration for more words
            target_summary_duration = 7
            headline_words_max = 18  # Increased from 10 - allow more detailed headlines (7 seconds * 2.5 words/sec)
            summary_words_max = 17   # 7 seconds * 2.5 words/sec
        else:  # 8-10 stories
            target_headline_duration = 6  # Allow 6 seconds for headline
            target_summary_duration = 7
            headline_words_max = 18  # Increased from 10 - allow more detailed headlines (6 seconds * 2.5 words/sec = 15, but allow up to 18)
            summary_words_max = 17   # 7 seconds * 2.5 words/sec
        
        # Check if hook-based headlines are enabled
        use_hooks = USE_HOOK_BASED_HEADLINES
        
        # Determine hook style based on story position
        # Use "wait" hooks only for 1st and 5th stories
        hook_style = "standard"
        if use_hooks:
            if story_number == 1:
                hook_style = "strong_opening"  # First story: use "wait" hook
            elif story_number == 5:
                hook_style = "wait_mid"  # 5th story: use "wait" hook
            elif story_number <= 3:
                hook_style = "strong_opening_no_wait"  # Stories 2-3: strong hooks but NO "wait"
            elif story_number <= 6:
                hook_style = "curiosity"  # Middle stories: curiosity hooks
            else:
                hook_style = "urgency"  # Last stories: urgency hooks
        
        story_prompt = f"""You are a news anchor creating a script segment for ONE news story in a YouTube Shorts video.

News Story:
Title: {article_title}
Description: {article_desc}

Story Position: Story {story_number} of {total_stories}

Create TWO segments for this story:
1. HEADLINE segment (EXACTLY {target_headline_duration} seconds): A hook-driven, attention-grabbing headline
2. SUMMARY segment (EXACTLY {target_summary_duration} seconds): A concise explanation

CRITICAL TIME CONSTRAINTS:
- Average speaking rate: 2.5 words per second
- Headline MUST be {headline_words_max} words or LESS (for {target_headline_duration} seconds)
- Summary MUST be {summary_words_max} words or LESS (for {target_summary_duration} seconds)
- Count your words carefully - exceeding these limits will cause timing issues
- Use clear, engaging language suitable for YouTube Shorts

{"ENGAGEMENT TECHNIQUES FOR HEADLINE (CRITICAL):" if use_hooks else "IMPORTANT FOR HEADLINE:"}
{"- Create a NATURAL, CONVERSATIONAL headline that naturally incorporates engagement hooks into the FULL text" if use_hooks else "- Make the headline DETAILED and INFORMATIVE - include key names, places, and what happened"}
{"- DO NOT just prefix with 'Breaking:' or 'Urgent:' - instead, weave the hook naturally into the complete headline text" if use_hooks else ""}
{"- Based on story position, naturally incorporate these hook styles into your full headline:" if use_hooks else ""}
{"  * If story 1: Use 'Wait, this just happened - [full story details with names, places, context]' or 'Wait, breaking right now: [complete headline with all context]'" if use_hooks and hook_style == "strong_opening" else ""}
{"  * If story 5: Use 'Wait, you need to see this - [full story details]' or 'Wait until you hear this - [complete headline with context]'" if use_hooks and hook_style == "wait_mid" else ""}
{"  * If story 2-3: Use strong opening hooks WITHOUT 'wait' like 'Breaking right now: [full story details]' or 'This just happened: [complete headline]' or 'You won't believe this: [full story]'" if use_hooks and hook_style == "strong_opening_no_wait" else ""}
{"  * If story 4, 6: Naturally incorporate curiosity like 'You won't believe what just happened - [full story details]' or 'This just changed everything - [complete headline with context]'" if use_hooks and hook_style == "curiosity" else ""}
{"  * If story 7-8: Naturally include urgency like 'Final update: [full story details]' or 'Last story - this is huge: [complete headline]'" if use_hooks and hook_style == "urgency" else ""}
{"- The hook should feel natural and conversational, not forced or prefixed" if use_hooks else ""}
{"- Make the headline DETAILED and INFORMATIVE - include key names, places, and what happened" if use_hooks else ""}
- Use the full {headline_words_max} words to provide context and help users understand the news
- Don't be too brief - include enough information so users can understand the story from the headline alone
{"- Example with natural hook: Instead of 'Breaking: Karnataka crisis', write the FULL headline naturally: 'Wait, this just happened - Karnataka Congress leadership crisis deepens as Siddaramaiah and Shivakumar clash publicly over Chief Minister seat'" if use_hooks else "- Example: Instead of 'Breaking: Karnataka crisis', use 'Karnataka Congress leadership crisis deepens as Siddaramaiah and Shivakumar clash publicly over Chief Minister seat'"}
{"- Another example: Instead of 'Urgent: Delhi metro', write: 'Breaking right now: Delhi Metro announces major expansion plan connecting five new districts to the network'" if use_hooks else ""}

Format your response as JSON:
{{
  "headline": {{
    "text": "{'[Hook-driven headline with urgency - MAX ' + str(headline_words_max) + ' words]' if use_hooks else '[short headline text - MAX ' + str(headline_words_max) + ' words]'}",
    "duration": {target_headline_duration},
    "type": "headline"
  }},
  "summary": {{
    "text": "[concise explanation - MAX {summary_words_max} words]",
    "duration": {target_summary_duration},
    "type": "summary"
  }},
  "image_prompt": "A detailed, visually striking image representing: [describe the news story visually - ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO SIGNS, NO BANNERS, purely visual elements like people, objects, scenes, landscapes, actions, emotions, atmosphere only]"
}}

REMEMBER: 
- Headline: EXACTLY {headline_words_max} words or less
- Summary: EXACTLY {summary_words_max} words or less
- Count words before submitting!

IMPORTANT for image_prompt:
- Describe visual elements only: people, objects, scenes, buildings, landscapes, actions, emotions, atmosphere
- ABSOLUTELY DO NOT mention or describe any text, words, letters, numbers, signs, banners, headlines, written content, newspapers, magazines, screens with text, or any text-based elements
- Focus on symbolic or representational imagery
- The image should be purely visual with absolutely no text elements whatsoever
- Describe what you SEE, not what you READ

Return ONLY valid JSON, no markdown formatting."""

        try:
            # Use unified LLM client with fallback
            response = self.llm_client.generate(story_prompt, {
                "temperature": 0.7,
                "num_predict": 300,
            })
            
            content = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            
            # Handle empty or invalid responses
            if not content or len(content) < 10:
                raise ValueError("Empty or too short response from LLM")
            
            # Extract JSON from markdown code blocks if present
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            # Try to parse JSON with better error handling
            try:
                result = json.loads(content.strip())
            except json.JSONDecodeError as e:
                # Try to extract JSON object from response
                print(f"  ⚠️  JSON parsing error: {e}")
                print(f"  📄 Response preview: {content[:300]}...")
                
                # Try to repair unterminated strings
                repaired_content = self._repair_json_string(content)
                if repaired_content != content:
                    try:
                        result = json.loads(repaired_content.strip())
                        print(f"  ✅ Repaired JSON string and parsed successfully")
                    except json.JSONDecodeError:
                        pass  # Continue to extraction/regeneration logic
                
                # If repair didn't work, try to extract JSON object boundaries
                if 'result' not in locals():
                    if '{' in content and '}' in content:
                        start_idx = content.find('{')
                        end_idx = content.rfind('}') + 1
                        if start_idx < end_idx:
                            try:
                                json_str = content[start_idx:end_idx]
                                # Try to repair the extracted JSON
                                json_str = self._repair_json_string(json_str)
                                result = json.loads(json_str)
                                print(f"  ✅ Extracted and repaired JSON from response")
                            except json.JSONDecodeError as e2:
                                # JSON extraction failed, regenerate with feedback
                                error_msg = f"JSON parsing failed: {e}. The response had malformed JSON (possibly unterminated string or unescaped quotes). Attempted repair but still failed: {e2}"
                                print(f"  🔄 Regenerating script with feedback about JSON parsing failure...")
                                regenerated = self._regenerate_story_script_with_feedback(
                                    article, headline_words_max, summary_words_max, target_headline_duration, 
                                    target_summary_duration, error_msg, content[:800]  # Include more context
                                )
                                if regenerated:
                                    result = regenerated
                                else:
                                    raise ValueError(f"Could not parse JSON even after extraction and regeneration: {e}")
                        else:
                            error_msg = f"Invalid JSON structure: {e}"
                            print(f"  🔄 Regenerating script with feedback...")
                            regenerated = self._regenerate_story_script_with_feedback(
                                article, headline_words_max, summary_words_max, target_headline_duration,
                                target_summary_duration, error_msg, content[:800]
                            )
                            if regenerated:
                                result = regenerated
                            else:
                                raise ValueError(error_msg)
                    else:
                        error_msg = f"No JSON found in response: {e}"
                        print(f"  🔄 Regenerating script with feedback...")
                        regenerated = self._regenerate_story_script_with_feedback(
                            article, headline_words_max, summary_words_max, target_headline_duration,
                            target_summary_duration, error_msg, content[:800]
                        )
                        if regenerated:
                            result = regenerated
                        else:
                            raise ValueError(error_msg)
            
            # Ensure proper structure
            headline = result.get('headline', {})
            summary = result.get('summary', {})
            image_prompt = result.get('image_prompt', f"Breaking news: {article_title[:50]}")
            
            # Get word counts
            headline_text = headline.get('text', '')
            summary_text = summary.get('text', '')
            headline_words = len(headline_text.split())
            summary_words = len(summary_text.split())
            
            # Calculate durations based on actual word count
            headline_duration = headline_words / 2.5
            summary_duration = summary_words / 2.5
            
            # Enforce maximum durations based on number of stories
            if total_stories <= 3:
                max_headline_duration = 6
                max_summary_duration = 12
            elif total_stories == 4:
                max_headline_duration = 5
                max_summary_duration = 8
            elif total_stories <= 7:
                max_headline_duration = 7  # Increased for more words
                max_summary_duration = 7
            else:  # 8-10 stories
                max_headline_duration = 6  # Allow 6 seconds for headline
                max_summary_duration = 7
            
            # Handle headlines that exceed time limits
            words = headline_text.split()
            word_count = len(words)
            
            if headline_duration > max_headline_duration:
                # Check word count to decide action
                if 10 <= word_count <= 25:
                    # Keep full headline (10-25 words) - don't trim
                    print(f"  ✅ Keeping full headline ({word_count} words) - within acceptable range")
                    # Adjust duration to fit the full headline
                    headline_duration = word_count / 2.5
                    # If it still exceeds max, we'll adjust timing later
                elif word_count > 25:
                    # More than 25 words - regenerate a shorter headline instead of truncating
                    print(f"  🔄 Headline too long ({word_count} words > 25), regenerating shorter headline...")
                    regenerated = self._regenerate_shorter_headline(
                        article, headline_words_max, target_headline_duration, headline_text
                    )
                    if regenerated:
                        headline_text = regenerated
                        headline_words = len(headline_text.split())
                        headline_duration = headline_words / 2.5
                        print(f"  ✅ Regenerated headline: {headline_words} words")
                    else:
                        # Fallback: trim to max words if regeneration fails
                        max_headline_words = int(max_headline_duration * 2.5)
                        headline_text = ' '.join(words[:max_headline_words])
                        headline_words = len(headline_text.split())
                        headline_duration = headline_words / 2.5
                        print(f"  ⚠️  Regeneration failed, trimmed headline from {word_count} to {headline_words} words")
                else:
                    # Less than 10 words - trim if needed
                    max_headline_words = int(max_headline_duration * 2.5)
                    headline_text = ' '.join(words[:max_headline_words])
                    headline_words = len(headline_text.split())
                    headline_duration = headline_words / 2.5
                    print(f"  ⚠️  Trimmed headline from {word_count} to {headline_words} words")
            
            if summary_duration > max_summary_duration:
                max_summary_words = int(max_summary_duration * 2.5)
                words = summary_text.split()
                summary_text = ' '.join(words[:max_summary_words])
                summary_words = len(summary_text.split())
                summary_duration = summary_words / 2.5
                print(f"  ⚠️  Trimmed summary from {len(words)} to {summary_words} words")
            
            # Update with trimmed text and calculated durations
            headline['text'] = headline_text
            headline['duration'] = round(headline_duration, 1)
            summary['text'] = summary_text
            summary['duration'] = round(summary_duration, 1)
            
            # First review: Validate accuracy against original article
            print(f"  🔍 First review: Validating headline and summary accuracy...")
            reviewed_result = self._review_content_accuracy(
                article, headline_text, summary_text, headline_words_max, summary_words_max
            )
            
            # Second review: Double-check the reviewed content
            print(f"  🔍 Second review: Double-checking reviewed content...")
            final_result = self._review_content_accuracy(
                article, reviewed_result['headline']['text'], reviewed_result['summary']['text'], 
                headline_words_max, summary_words_max, is_second_review=True
            )
            
            # Generate proper detailed image prompt using Ollama (not just article title)
            print(f"  🖼️  Generating detailed image prompt for story {story_number}...")
            detailed_image_prompt = self._generate_detailed_image_prompt(article, headline_text, summary_text)
            
            return {
                'headline': final_result['headline'],
                'summary': final_result['summary'],
                'image_prompt': detailed_image_prompt,
                'article': article
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"  ⚠️  Error generating script for story {story_number}: {error_msg}")
            
            # Try to regenerate with feedback about the error
            print(f"  🔄 Attempting to regenerate script with feedback about the error...")
            regenerated = self._regenerate_story_script_with_feedback(
                article, headline_words_max, summary_words_max, target_headline_duration,
                target_summary_duration, error_msg, ""
            )
            
            if regenerated:
                # Use regenerated content
                headline_text = regenerated.get('headline', {}).get('text', '')
                summary_text = regenerated.get('summary', {}).get('text', '')
                
                # Run reviews on regenerated content
                print(f"  🔍 First review: Validating regenerated headline and summary accuracy...")
                reviewed_result = self._review_content_accuracy(
                    article, headline_text, summary_text, headline_words_max, summary_words_max
                )
                
                print(f"  🔍 Second review: Double-checking reviewed content...")
                final_result = self._review_content_accuracy(
                    article, reviewed_result['headline']['text'], reviewed_result['summary']['text'], 
                    headline_words_max, summary_words_max, is_second_review=True
                )
                
                # Generate image prompt
                print(f"  🖼️  Generating detailed image prompt for story {story_number}...")
                detailed_image_prompt = self._generate_detailed_image_prompt(article, headline_text, summary_text)
                
                return {
                    'headline': final_result['headline'],
                    'summary': final_result['summary'],
                    'image_prompt': detailed_image_prompt,
                    'article': article
                }
            else:
                # Final fallback if regeneration also fails
                print(f"  ⚠️  Regeneration also failed, using simple fallback")
                return {
                    'headline': {
                        'text': f"Wait, this just happened: {article_title[:50]}",
                        'duration': 7,
                        'type': 'headline'
                    },
                    'summary': {
                        'text': article_desc[:100] if article_desc else "Important news story developing.",
                        'duration': 11,
                        'type': 'summary'
                    },
                    'image_prompt': f"Professional news broadcast image: {article_title[:50]}",
                    'article': article
                }
    
    def generate_today_in_60_seconds(self, news_articles: List[Dict]) -> Dict:
        """Generate a 60-second news script for 'Today in 60 seconds'"""
        
        # Select stories to cover - HEADLINE + SUMMARY segments (multiple segments per story)
        # Each story needs ~7-8 seconds (headline ~4s + summary ~3-4s)
        # So: 8 stories = 56-64s + 2s closing = 58-66s (will normalize to 60s)
        # We'll use exactly 8 stories with headline + summary segments
        max_stories = min(len(news_articles), 8)  # Use exactly 8 stories
        selected_articles = news_articles[:max_stories]
        
        print(f"  📰 Using {len(selected_articles)} stories for 60-second video (headline + summary segments)")
        
        # Initialize overlay_suggestions dictionary
        overlay_suggestions = {}  # story_index -> overlay_data
        
        # Step 1: Generate clickbait title
        news_summary = "\n".join([
            f"- {article['title']}: {article.get('description', '')[:100]}"
            for article in selected_articles
        ])
        
        # Enhanced title prompt with engagement hooks if enabled
        if USE_HOOK_BASED_HEADLINES:
            title_prompt = f"""Generate a viral, clickbait-style YouTube Shorts title for a 60-second news video.

Today's top news stories:
{news_summary}

Create a catchy, attention-grabbing title that:
- Is under 60 characters
- Uses power words like "SHOCKING", "BREAKING", "YOU WON'T BELIEVE"
- Creates curiosity and urgency
- Is suitable for YouTube Shorts
- Uses cliffhanger patterns: "Wait until you see #5", "Story #5 will shock you", "You won't believe what happened next"
- Includes countdown hooks: "{len(selected_articles)} Stories That Changed Everything Today", "Top {len(selected_articles)} Breaking News Stories"
- Creates FOMO (Fear of Missing Out): "This Just Happened", "Breaking Right Now", "You Need to See This"

ENGAGEMENT TECHNIQUES TO USE:
1. Question hooks: "Did You Know This Happened Today?"
2. Pattern interrupts: "This Changed Everything..."
3. Number hooks: "{len(selected_articles)} Stories in 60 Seconds"
4. Urgency: "BREAKING NOW", "JUST IN"
5. Cliffhanger teasers: "Wait for Story #{len(selected_articles)}..."

Return ONLY the title text, nothing else."""
        else:
            title_prompt = f"""Generate a viral, clickbait-style YouTube Shorts title for a 60-second news video.

Today's top news stories:
{news_summary}

Create a catchy, attention-grabbing title that:
- Is under 60 characters
- Uses power words like "SHOCKING", "BREAKING", "YOU WON'T BELIEVE"
- Creates curiosity and urgency
- Is suitable for YouTube Shorts

Return ONLY the title text, nothing else."""

        try:
            # Use unified LLM client with fallback
            title_response = self.llm_client.generate(title_prompt, {"temperature": 0.9, "num_predict": 100})
            clickbait_title = title_response.get('response', '').strip().strip('"').strip("'") if isinstance(title_response, dict) else str(title_response).strip().strip('"').strip("'")
            if '```' in clickbait_title:
                clickbait_title = clickbait_title.split('```')[0].strip()
            clickbait_title = clickbait_title[:60]
        except:
            clickbait_title = "BREAKING: Today's Top Stories in 60 Seconds"
        
        # Step 2: Generate script for EACH story separately (HEADLINE ONLY - NO SUMMARIES)
        print("\n  📝 Generating headlines for each news story (no summaries)...")
        story_scripts = []
        previous_overlays_list = []  # Track previous overlays to avoid repetition
        for i, article in enumerate(selected_articles, 1):
            print(f"  [{i}/{len(selected_articles)}] Generating headline for: {article.get('title', '')[:60]}...")
            story_script = self._generate_single_story_script(article, i, len(selected_articles))
            story_scripts.append(story_script)
            
            # Generate context-aware overlay suggestions for this story
            # Pass previous overlays to avoid repetition
            if USE_CONTEXT_AWARE_OVERLAYS:
                headline_text = story_script.get('headline', {}).get('text', '')
                # Get last 2 overlays to check for repetition (especially consecutive stories)
                recent_overlays = previous_overlays_list[-2:] if len(previous_overlays_list) >= 2 else previous_overlays_list
                overlay_data = self.generate_context_aware_overlays(
                    article=article,
                    headline_text=headline_text,
                    story_index=i,
                    total_stories=len(selected_articles),
                    previous_overlays=recent_overlays
                )
                if overlay_data:
                    overlay_suggestions[i] = overlay_data
                    previous_overlays_list.append(overlay_data)  # Track for next iteration
                    primary_text = overlay_data.get('primary_overlay', {}).get('text', 'N/A')
                    secondary_text = overlay_data.get('optional_secondary', {}).get('text', '')
                    if secondary_text:
                        print(f"    🎨 Generated overlays: {primary_text} | Curiosity: {secondary_text}")
                    else:
                        print(f"    🎨 Generated overlays: {primary_text}")
        
        # Step 3: Create segments - HEADLINE ONLY (no summaries)
        print("\n  🔗 Creating headline-only segments for 60-second script...")
        segments = []
        image_prompts = []
        current_time = 0
        
        # Calculate available time for stories
        closing_duration = 2  # Short closing
        available_time = 60 - closing_duration  # 58 seconds for stories
        
        num_stories = len(story_scripts)
        
        # Calculate target duration per story (headline only, ~7 seconds each)
        # Each story has only 1 segment: headline (~7s)
        # Reserve time for opening hook if enabled
        opening_hook_duration = 0
        if USE_HOOK_BASED_HEADLINES:
            opening_hook_duration = 3  # 3 seconds for opening hook
            available_time -= opening_hook_duration
        
        target_story_duration = available_time // num_stories  # ~7 seconds per story
        
        # Add opening hook if enabled
        if USE_HOOK_BASED_HEADLINES:
            opening_hook_prompt = f"""Generate a powerful opening hook for a YouTube Shorts news video.

Total stories: {num_stories}
Top story: {selected_articles[0].get('title', '')[:50] if selected_articles else 'breaking news'}

Create a 3-4 second opening hook (8-10 words) that:
1. Grabs attention immediately
2. Creates curiosity
3. Sets up the video structure
4. Uses engagement techniques

HOOK PATTERNS:
- Countdown: "{num_stories} stories that will shock you in 60 seconds!"
- Question: "Did you know this happened today? Here's what you missed..."
- Pattern interrupt: "This just changed everything. Here's what happened..."
- Urgency: "BREAKING: {num_stories} major stories you need to see right now!"
- Cliffhanger: "Wait until you see story #{num_stories} - it will blow your mind!"

Return ONLY the hook text, nothing else."""
            
            try:
                hook_response = self.llm_client.generate(opening_hook_prompt, {"temperature": 0.9, "num_predict": 60})
                opening_text = hook_response.get('response', '').strip().strip('"').strip("'") if isinstance(hook_response, dict) else str(hook_response).strip().strip('"').strip("'")
                if '```' in opening_text:
                    opening_text = opening_text.split('```')[0].strip()
                # Fallback if too long or empty
                if not opening_text or len(opening_text) > 60:
                    opening_text = f"{num_stories} stories that will shock you in 60 seconds!"
            except:
                opening_text = f"{num_stories} stories that will shock you in 60 seconds!"
            
            # Calculate duration for opening hook
            opening_words = len(opening_text.split())
            opening_duration = max(3, min(int(opening_words / 2.5), 4))  # 3-4 seconds
            
            segments.append({
                'text': opening_text,
                'duration': opening_duration,
                'start_time': current_time,
                'type': 'headline'
            })
            image_prompts.insert(0, "News broadcast opening scene")  # Add opening image prompt
            current_time += opening_duration
            available_time -= opening_duration  # Adjust available time
            print(f"  🎣 Opening hook: {opening_text}")
        
        # Add all stories (headline segments only)
        for i, story_script in enumerate(story_scripts, 1):
            headline = story_script['headline']
            headline_text = headline.get('text', '')
            
            # Clean up headline (remove prefixes like "Breaking:", "Next:", etc.)
            for prefix in ["Breaking:", "Breaking", "Next:", "Also:", "News:", "Update:"]:
                if headline_text.startswith(prefix):
                    headline_text = headline_text[len(prefix):].strip()
            
            # Calculate duration based on word count
            headline_word_count = len(headline_text.split())
            
            # Use target duration, but ensure minimum 5 seconds and maximum 8 seconds
            headline_duration = max(5, min(int(headline_word_count / 2.5), target_story_duration, 8))
            
            # Add headline segment only (no summary)
            headline_seg = {
                'text': headline_text,
                'duration': headline_duration,
                'start_time': current_time,
                'type': 'headline',
                'story_index': i
            }
            segments.append(headline_seg)
            image_prompts.append(story_script['image_prompt'])  # One image per story
            current_time += headline_duration
        
        # Add closing with engagement hooks if enabled
        if USE_HOOK_BASED_HEADLINES:
            # Generate engaging closing with call-to-action
            closing_prompt = f"""Generate an engaging closing for a YouTube Shorts news video.

Total stories covered: {num_stories}
Last story topic: {selected_articles[-1].get('title', 'news')[:50] if selected_articles else 'news'}

Create a closing that:
1. Summarizes the video briefly (2-3 seconds)
2. Includes a call-to-action (1-2 seconds)
3. Creates urgency for future videos
4. Is 4-5 seconds total (10-12 words)

CLOSING PATTERNS:
- "That's today's top {num_stories} stories. Follow for breaking news updates!"
- "Stay tuned - more breaking news coming tomorrow!"
- "Which story shocked you most? Comment below!"
- "That's today's news. Hit subscribe for daily updates!"
- "Follow for more - breaking news happens every day!"

CRITICAL INSTRUCTIONS:
- Return ONLY the closing text itself
- DO NOT include any explanations, options, or examples
- DO NOT say "Okay, here are a few options" or similar
- DO NOT include phrases like "keeping in mind" or "for [demographic]"
- DO NOT list multiple options - return ONLY ONE closing text
- Return the closing text directly, as if you're speaking it

Example of CORRECT response:
"That's what you need to know today. Follow for more updates!"

Example of WRONG response (DO NOT DO THIS):
"Okay, here are a few options, keeping in mind the middle-age demographic:
Option 1: That's what you need to know today. Follow for more updates!
Option 2: Stay informed - these stories matter. Subscribe for daily news!"

Return ONLY the closing text, nothing else. No explanations, no options, no examples."""
            
            try:
                closing_response = self.llm_client.generate(closing_prompt, {"temperature": 0.8, "num_predict": 80})
                closing_text = closing_response.get('response', '').strip().strip('"').strip("'") if isinstance(closing_response, dict) else str(closing_response).strip().strip('"').strip("'")
                if '```' in closing_text:
                    closing_text = closing_text.split('```')[0].strip()
                # Fallback if too long or empty
                if not closing_text or len(closing_text) > 80:
                    closing_text = f"That's today's top {num_stories} stories. Which one shocked you most? Comment below!"
            except:
                closing_text = f"That's today's top {num_stories} stories. Which one shocked you most? Comment below!"
            print(f"  🎬 Engaging closing: {closing_text}")
        else:
            closing_text = "That's today's news. Stay informed!"
        
        # Calculate minimum duration needed for closing text
        closing_words = len(closing_text.split())
        closing_duration_min = max(closing_duration, int(closing_words / 2.5) + 1)  # At least 4 seconds
        
        segments.append({
            'text': closing_text,
            'duration': closing_duration_min,
            'start_time': current_time,
            'type': 'headline'
        })
        image_prompts.append("News broadcast closing scene")
        current_time += closing_duration_min
        
        # Normalize to exactly 60 seconds
        total_duration = sum(s['duration'] for s in segments)
        if total_duration != 60:
            if total_duration > 60:
                # Need to reduce - reduce from non-closing segments first, preserve closing minimum
                excess = total_duration - 60
                for segment in segments[:-1]:  # All except closing
                    if excess > 0:
                        reduction = min(excess, max(1, int(segment['duration'] * 0.1)))  # Reduce up to 10%
                        segment['duration'] = max(3, int(segment['duration'] - reduction))
                        excess -= reduction
                
                # If still excess, reduce closing slightly but keep minimum
                if excess > 0:
                    segments[-1]['duration'] = max(closing_duration_min - 1, int(segments[-1]['duration'] - excess))
            else:
                # Need to add time - add to closing segment
                segments[-1]['duration'] = segments[-1]['duration'] + (60 - total_duration)
            
            # Recalculate start times
            current_time = 0
            for segment in segments:
                segment['start_time'] = current_time
                current_time += segment['duration']
            
            # Final check - ensure exactly 60 seconds
            total = sum(s['duration'] for s in segments)
            if total != 60:
                diff = 60 - total
                segments[-1]['duration'] = max(closing_duration_min - 1, segments[-1]['duration'] + diff)
                segments[-1]['start_time'] = sum(s['duration'] for s in segments[:-1])
        
        # No facts generation needed for headline-only segments
        
        # Combine full script text
        full_script = " ".join([s['text'] for s in segments])
        
        result = {
            'title': clickbait_title,
            'script': full_script,
            'segments': segments,
            'image_prompts': image_prompts,
            'overlay_suggestions': overlay_suggestions if USE_CONTEXT_AWARE_OVERLAYS else {}  # Add overlay suggestions
        }
        
        print(f"\n  ✅ Generated script with {len(segments)} segments")
        print(f"  📋 Stories covered: {len(story_scripts)}")
        print(f"  🖼️  Image prompts: {len(image_prompts)}")
        if USE_CONTEXT_AWARE_OVERLAYS:
            print(f"  🎨 Overlay suggestions: {len(overlay_suggestions)} stories")
        
        return result
        
        # OLD CODE BELOW - keeping for reference but not used
        # Step 2: Generate timed script segments
        script_prompt = f"""You are a news anchor creating a 60-second YouTube Shorts video script.

Today's top news stories:
{news_summary}

Create a concise, engaging 60-second news script with these EXACT requirements:
1. Total duration: EXACTLY 60 seconds
2. Average speaking rate: 2.5 words per second (150 words per minute)
3. Structure: Present EACH news story in TWO segments (headline THEN summary):
   - First segment: News headline/announcement (6-8 seconds) - announces the story
   - Second segment: Summary/explanation of that SAME story (10-12 seconds) - explains what happened
   - Then move to the next story
4. Cover 3 complete news stories (each story MUST have both headline + summary)
5. Start with a brief hook (first 3-5 seconds)
6. End with a call to action (last 3-5 seconds)
7. Use simple, clear language suitable for YouTube Shorts

CRITICAL STRUCTURE - Follow this EXACT pattern:
- Hook: "Here's what's happening today." (3-5 seconds)
- Story 1 HEADLINE: "Breaking: [Story 1 headline]" (6-8 seconds) - announces Story 1
- Story 1 SUMMARY: "[Detailed explanation of Story 1 - what happened, why it matters]" (10-12 seconds) - explains Story 1
- Story 2 HEADLINE: "Next: [Story 2 headline]" (6-8 seconds) - announces Story 2
- Story 2 SUMMARY: "[Detailed explanation of Story 2 - what happened, why it matters]" (10-12 seconds) - explains Story 2
- Story 3 HEADLINE: "Also: [Story 3 headline]" (6-8 seconds) - announces Story 3
- Story 3 SUMMARY: "[Detailed explanation of Story 3 - what happened, why it matters]" (10-12 seconds) - explains Story 3
- Closing: "That's today's news. Stay informed!" (3-5 seconds)

IMPORTANT: Calculate duration for each segment based on word count:
- Duration in seconds = (word count / 2.5)
- Round to nearest second
- Ensure all segments add up to exactly 60 seconds

Format your response as JSON with:
- "script": The full script text
- "segments": Array of objects, each with:
  - "text": The script portion for this segment (exact words)
  - "duration": Duration in seconds (calculated from word count, must be accurate)
  - "start_time": Start time in seconds (cumulative)
  - "type": Either "headline" or "summary" to indicate segment type
- "image_prompts": Array of image generation prompts for each segment (be descriptive and visual, matching the news story)

Example segment format (showing Story 1):
{{
  "text": "Here's what's happening today.",
  "duration": 4,
  "start_time": 0,
  "type": "headline"
}},
{{
  "text": "Breaking: Major AI breakthrough announced by scientists.",
  "duration": 7,
  "start_time": 4,
  "type": "headline"
}},
{{
  "text": "Researchers have developed revolutionary computing technology that processes data ten times faster. This breakthrough could transform everything from smartphones to supercomputers, making AI more powerful and accessible.",
  "duration": 12,
  "start_time": 11,
  "type": "summary"
}},
{{
  "text": "Next: Global climate summit reaches historic agreement.",
  "duration": 6,
  "start_time": 23,
  "type": "headline"
}},
{{
  "text": "World leaders agreed on new carbon reduction targets, committing to cut emissions by 50 percent by 2030. This marks the most ambitious climate deal in history and could significantly slow global warming.",
  "duration": 12,
  "start_time": 29,
  "type": "summary"
}}

IMPORTANT: 
- Headline segments should be SHORT and punchy (announce the story)
- Summary segments should be DETAILED (explain what happened and why it matters)
- Each story MUST have both headline AND summary
- Segments MUST alternate: headline, summary, headline, summary...

Return ONLY valid JSON, no markdown formatting."""

        try:
            # Use unified LLM client with fallback
            response = self.llm_client.generate(script_prompt, {
                "temperature": 0.7,
                "num_predict": 1000,
            })
            
            # Extract JSON from response
            content = response.get('response', '') if isinstance(response, dict) else str(response)
            # Try to extract JSON if wrapped in markdown
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            result = json.loads(content.strip())
            # Add clickbait title
            result['title'] = clickbait_title
            # Ensure segments have proper timing
            result['segments'] = self._normalize_segments(result.get('segments', []))
            # Validate and fix segment types to ensure headline → summary pairs
            result['segments'] = self._ensure_headline_summary_pairs(result['segments'])
            
            # Always generate image prompts with Ollama to ensure they're news-specific
            # Check if prompts are generic/fallback prompts
            image_prompts = result.get('image_prompts', [])
            generic_keywords = ['professional news broadcast studio', 'breaking news headline', 'news anchor presenting', 
                              'world map', 'newsroom', 'generic', 'placeholder', 'news anchor', 'broadcast studio']
            
            is_generic = False
            if not image_prompts or len(image_prompts) < len(result.get('segments', [])):
                is_generic = True
                print(f"  ⚠️  Image prompts missing or incomplete ({len(image_prompts)} prompts for {len(result.get('segments', []))} segments)")
            else:
                # Check if prompts contain generic keywords
                for i, prompt in enumerate(image_prompts[:3]):  # Check first 3 prompts
                    prompt_lower = prompt.lower()
                    if any(keyword.lower() in prompt_lower for keyword in generic_keywords):
                        print(f"  ⚠️  Detected generic prompt {i+1}: '{prompt[:60]}...'")
                        is_generic = True
                        break
            
            # Always regenerate to ensure news-specific prompts
            if is_generic or True:  # Force regeneration for now to ensure quality
                print("\n  ✅ Generating news-specific image prompts with Ollama...")
                print("  " + "="*50)
                result['image_prompts'] = self._generate_image_prompts_with_ollama(
                    result.get('segments', []), 
                    news_articles,
                    None  # No specific topic for "today" videos
                )
                print("  " + "="*50)
                print(f"\n  ✅ Generated {len(result['image_prompts'])} news-specific prompts")
                print("\n  📋 Final image prompts:")
                for i, prompt in enumerate(result['image_prompts'], 1):
                    print(f"     {i}. {prompt[:100]}...")
                print()
            
            return result
            
        except Exception as e:
            print(f"Error generating content: {e}")
            import traceback
            traceback.print_exc()
            # Fallback script
            fallback = self._create_fallback_script(selected_articles, "today")
            fallback['title'] = clickbait_title
            return fallback
    
    def generate_hot_topic_script(self, topic: str, articles: List[Dict]) -> Dict:
        """Generate a 60-second script about a hot topic - HEADLINE ONLY (same optimizations as today_in_60_seconds)"""
        
        # Select up to 8 articles for the hot topic
        max_stories = min(len(articles), 8)
        selected_articles = articles[:max_stories]
        
        print(f"  📰 Using {len(selected_articles)} stories for 60-second hot topic video (headline-only)")
        
        news_summary = "\n".join([
            f"- {article['title']}: {article.get('description', '')[:100]}"
            for article in selected_articles
        ])
        
        # Step 1: Generate clickbait title
        title_prompt = f"""Generate a viral, clickbait-style YouTube Shorts title about this topic.

Topic: {topic}

Related news:
{news_summary}

Create a catchy, attention-grabbing title that:
- Is under 60 characters
- Uses power words like "SHOCKING", "BREAKING", "YOU NEED TO KNOW"
- Creates curiosity about the topic
- Is suitable for YouTube Shorts

Return ONLY the title text, nothing else."""

        try:
            # Use unified LLM client with fallback
            title_response = self.llm_client.generate(title_prompt, {"temperature": 0.9, "num_predict": 100})
            clickbait_title = title_response.get('response', '').strip().strip('"').strip("'") if isinstance(title_response, dict) else str(title_response).strip().strip('"').strip("'")
            if '```' in clickbait_title:
                clickbait_title = clickbait_title.split('```')[0].strip()
            clickbait_title = clickbait_title[:60]
        except:
            clickbait_title = f"BREAKING: {topic} - What You Need to Know"
        
        # Step 2: Generate script for EACH story separately (HEADLINE ONLY - NO SUMMARIES)
        print("\n  📝 Generating headlines for each news story (no summaries)...")
        story_scripts = []
        for i, article in enumerate(selected_articles, 1):
            print(f"  [{i}/{len(selected_articles)}] Generating headline for: {article.get('title', '')[:60]}...")
            story_script = self._generate_single_story_script(article, i, len(selected_articles))
            story_scripts.append(story_script)
        
        # Step 3: Create segments - HEADLINE ONLY (no summaries)
        print("\n  🔗 Creating headline-only segments for 60-second script...")
        segments = []
        image_prompts = []
        current_time = 0
        
        # Calculate available time for stories
        closing_duration = 2  # Short closing
        available_time = 60 - closing_duration  # 58 seconds for stories
        
        num_stories = len(story_scripts)
        
        # Calculate target duration per story (headline only, ~7 seconds each)
        target_story_duration = available_time // num_stories  # ~7 seconds per story
        
        # Add all stories (headline segments only)
        for i, story_script in enumerate(story_scripts, 1):
            headline = story_script['headline']
            headline_text = headline.get('text', '')
            
            # Clean up headline (remove prefixes like "Breaking:", "Next:", etc.)
            for prefix in ["Breaking:", "Breaking", "Next:", "Also:", "News:", "Update:"]:
                if headline_text.startswith(prefix):
                    headline_text = headline_text[len(prefix):].strip()
            
            # Calculate duration based on word count
            headline_word_count = len(headline_text.split())
            
            # Use target duration, but ensure minimum 5 seconds and maximum 8 seconds
            headline_duration = max(5, min(int(headline_word_count / 2.5), target_story_duration, 8))
            
            # Add headline segment only (no summary)
            headline_seg = {
                'text': headline_text,
                'duration': headline_duration,
                'start_time': current_time,
                'type': 'headline',
                'story_index': i
            }
            segments.append(headline_seg)
            image_prompts.append(story_script['image_prompt'])  # One image per story
            current_time += headline_duration
        
        # Add closing
        closing_text = "That's today's news. Stay informed!"
        closing_words = len(closing_text.split())
        closing_duration_min = max(closing_duration, int(closing_words / 2.5) + 1)  # At least 4 seconds
        
        segments.append({
            'text': closing_text,
            'duration': closing_duration_min,
            'start_time': current_time,
            'type': 'headline'
        })
        image_prompts.append("News broadcast closing scene")
        current_time += closing_duration_min
        
        # Normalize to exactly 60 seconds
        total_duration = sum(s['duration'] for s in segments)
        if total_duration != 60:
            if total_duration > 60:
                # Need to reduce - reduce from non-closing segments first
                excess = total_duration - 60
                for segment in segments[:-1]:  # All except closing
                    if excess > 0:
                        reduction = min(excess, max(1, int(segment['duration'] * 0.1)))  # Reduce up to 10%
                        segment['duration'] = max(3, int(segment['duration'] - reduction))
                        excess -= reduction
                
                # If still excess, reduce closing slightly but keep minimum
                if excess > 0:
                    segments[-1]['duration'] = max(closing_duration_min - 1, int(segments[-1]['duration'] - excess))
            else:
                # Need to add time - add to closing segment
                segments[-1]['duration'] = segments[-1]['duration'] + (60 - total_duration)
            
            # Recalculate start times
            current_time = 0
            for segment in segments:
                segment['start_time'] = current_time
                current_time += segment['duration']
            
            # Final check - ensure exactly 60 seconds
            total = sum(s['duration'] for s in segments)
            if total != 60:
                diff = 60 - total
                segments[-1]['duration'] = max(closing_duration_min - 1, segments[-1]['duration'] + diff)
                segments[-1]['start_time'] = sum(s['duration'] for s in segments[:-1])
        
        # Combine full script text
        full_script = " ".join([s['text'] for s in segments])
        
        result = {
            'title': clickbait_title,
            'script': full_script,
            'segments': segments,
            'image_prompts': image_prompts
        }
        
        print(f"\n  ✅ Generated script with {len(segments)} segments")
        print(f"  📋 Stories covered: {len(story_scripts)}")
        print(f"  🖼️  Image prompts: {len(image_prompts)}")
        
        return result
    
    def generate_context_aware_overlays(self, article: Dict, headline_text: str, story_index: int, total_stories: int, previous_overlays: List[Dict] = None) -> Dict:
        """
        Generate context-aware overlay suggestions using LLM based on the news story
        previous_overlays: List of overlay data from previous stories to avoid repetition
        Returns dict with overlay text, style, and position suggestions
        """
        if not USE_CONTEXT_AWARE_OVERLAYS:
            return None
        
        article_title = article.get('title', '')
        article_desc = article.get('description', '')[:200]
        
        # Extract previous curiosity hooks to avoid repetition
        previous_curiosity_hooks = []
        if previous_overlays:
            for prev_overlay in previous_overlays:
                if prev_overlay and prev_overlay.get('optional_secondary'):
                    prev_hook = prev_overlay.get('optional_secondary', {}).get('text', '')
                    if prev_hook:
                        previous_curiosity_hooks.append(prev_hook)
        
        # Determine overlay style based on story position (matching hook-based headlines)
        if story_index <= 3:
            urgency_level = "high"
            style_hint = "BREAKING, URGENT, SHOCKING"
        elif story_index <= 6:
            urgency_level = "medium"
            style_hint = "URGENT, DEVELOPING, IMPORTANT"
        else:
            urgency_level = "final"
            style_hint = "FINAL UPDATE, LAST STORY, DEVELOPING"
        
        # Build previous hooks context for LLM
        previous_hooks_context = ""
        if previous_curiosity_hooks:
            previous_hooks_context = f"\n\nIMPORTANT - AVOID REPETITION:\nPrevious curiosity hooks used: {', '.join(previous_curiosity_hooks)}\nDO NOT use the same curiosity hook text in consecutive stories. Use different variations or skip curiosity hook if similar one was just used."
        else:
            previous_hooks_context = ""
        
        prompt = f"""You are creating visual text overlays for a YouTube Shorts news video.

News Story:
Title: {article_title}
Description: {article_desc}
Headline: {headline_text}
Story Position: Story {story_index} of {total_stories}
Urgency Level: {urgency_level}

Generate 1-2 context-aware text overlays that:
1. Are directly relevant to THIS specific news story (not generic)
2. Match the urgency level ({urgency_level})
3. Are short and punchy (2-5 words max)
4. Create engagement and urgency
5. Are suitable for visual overlay on news images

OVERLAY TYPES:
- Urgency badge: "BREAKING NOW", "JUST IN", "URGENT", "LIVE"
- Story-specific: Based on the actual news content (e.g., "CRISIS", "BREAKTHROUGH", "DEAL SIGNED", "PROTEST", "ELECTION")
- Progress: "STORY {story_index} OF {total_stories}"
- Curiosity: "WAIT FOR IT", "YOU WON'T BELIEVE", "THIS IS HUGE"

STYLE GUIDELINES:
- For high urgency (stories 1-3): Use "BREAKING NOW", "SHOCKING", "URGENT", or story-specific urgent terms
- For medium urgency (stories 4-6): Use "URGENT", "DEVELOPING", "IMPORTANT", or story-specific terms
- For final stories (7-8): Use "FINAL UPDATE", "LAST STORY", "DEVELOPING", or story-specific terms

IMPORTANT:
- Make overlays CONTEXT-AWARE - relate to the actual news story
- Example: If story is about election, use "ELECTION UPDATE" not just "BREAKING"
- Example: If story is about crisis, use "CRISIS ALERT" not just "URGENT"
- Example: If story is about breakthrough, use "BREAKTHROUGH" not just "NEWS"
- But still maintain urgency and engagement
- AVOID REPETITION: Do not use the same curiosity hook text ("YOU WON'T BELIEVE", "WAIT FOR IT", etc.) in consecutive stories
- If previous story used a curiosity hook, use a different variation or skip it for this story
{previous_hooks_context}

Return as JSON:
{{
  "primary_overlay": {{
    "text": "[2-5 word context-aware overlay text]",
    "style": "breaking|urgent|developing|final",
    "position": "top_center|top_left|top_right"
  }},
  "progress_overlay": {{
    "text": "STORY {story_index} OF {total_stories}",
    "position": "top_right"
  }},
  "optional_secondary": {{
    "text": "[Optional 2-4 word curiosity hook if story 4-6]",
    "position": "center_top"
  }}
}}

Return ONLY valid JSON, no markdown formatting."""
        
        try:
            response = self.llm_client.generate(prompt, {
                "temperature": 0.7,
                "num_predict": 200,
            })
            
            content = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            
            # Extract JSON from markdown code blocks if present
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            # Parse JSON
            try:
                overlays = json.loads(content.strip())
                return overlays
            except json.JSONDecodeError as e:
                print(f"  ⚠️  JSON parsing error for overlays: {e}")
                # Fallback: create context-aware overlay based on story position
                return self._create_fallback_overlays(story_index, total_stories, article_title)
                
        except Exception as e:
            print(f"  ⚠️  Error generating context-aware overlays: {e}")
            # Fallback: create overlay based on story position
            return self._create_fallback_overlays(story_index, total_stories, article_title)
    
    def _create_fallback_overlays(self, story_index: int, total_stories: int, article_title: str) -> Dict:
        """Create fallback overlays when LLM generation fails"""
        if story_index <= 3:
            primary_text = "BREAKING NOW"
            style = "breaking"
        elif story_index <= 6:
            primary_text = "URGENT"
            style = "urgent"
        else:
            primary_text = "FINAL UPDATE"
            style = "final"
        
        return {
            "primary_overlay": {
                "text": primary_text,
                "style": style,
                "position": "top_center"
            },
            "progress_overlay": {
                "text": f"STORY {story_index} OF {total_stories}",
                "position": "top_right"
            }
        }
    
    def _generate_facts_for_segment(self, segment_text: str, articles: List[Dict], segment_type: str) -> List[str]:
        """
        Generate key facts/data points for a segment using Ollama
        Returns list of 2-4 key facts to display
        """
        # Prepare news context
        news_context = "\n".join([
            f"- {article['title']}: {article.get('description', '')[:100]}"
            for article in articles[:3]
        ])
        
        prompt = f"""You are creating key facts/data points for a news video segment.

News Context:
{news_context}

Segment ({segment_type}):
"{segment_text}"

Generate 2-4 key facts, statistics, or data points related to this news segment. These will be displayed as text overlays in a news video.

Requirements:
- Each fact should be concise (5-15 words)
- Include specific numbers, percentages, or concrete details when possible
- Make facts informative and engaging
- Use bullet-point format
- Focus on the most important/interesting information

Examples:
- "Stock market up 3.2% today"
- "Over 1 million people affected"
- "Temperature reached record 45°C"
- "Agreement signed by 50 countries"

Return ONLY a JSON array of facts, like:
["Fact 1", "Fact 2", "Fact 3"]

Return ONLY the JSON array, no explanation."""

        try:
            # Use unified LLM client with fallback
            response = self.llm_client.generate(prompt, {
                "temperature": 0.6,
                "num_predict": 150,
            })
            
            content = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            
            # Handle empty or invalid responses
            if not content or len(content) < 5:
                return []
            
            # Extract JSON array from markdown code blocks if present
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            # Try to parse JSON array with better error handling
            try:
                facts = json.loads(content.strip())
            except json.JSONDecodeError as e:
                # Try to extract JSON array from response
                print(f"  ⚠️  JSON parsing error for facts: {e}")
                
                # Try to find array boundaries
                if '[' in content and ']' in content:
                    start_idx = content.find('[')
                    end_idx = content.rfind(']') + 1
                    if start_idx < end_idx:
                        try:
                            json_str = content[start_idx:end_idx]
                            facts = json.loads(json_str)
                        except json.JSONDecodeError:
                            # If still fails, try to extract strings manually
                            import re
                            # Try to find quoted strings
                            matches = re.findall(r'"([^"]+)"', content)
                            if matches:
                                facts = matches[:4]
                            else:
                                return []
                    else:
                        return []
                else:
                    return []
            
            if isinstance(facts, list) and len(facts) > 0:
                return facts[:4]  # Limit to 4 facts max
            else:
                return []
        except Exception as e:
            print(f"  Warning: Could not generate facts: {e}")
            return []
    
    def _generate_image_prompts_with_ollama(self, segments: List[Dict], articles: List[Dict], topic: str = None) -> List[str]:
        """
        Use Ollama to generate detailed, news-specific image prompts based on segments and news content
        Generate ONE prompt per story (not per segment) - group segments by story_index
        """
        prompts = []
        
        # Prepare news context
        news_context = "\n".join([
            f"- {article['title']}: {article.get('description', '')[:100]}"
            for article in articles[:5]
        ])
        
        # Group segments by story_index to generate one prompt per story
        stories_dict = {}  # story_index -> {headline_text}
        closing_segment = None
        
        for segment in segments:
            story_index = segment.get('story_index')
            segment_type = segment.get('type', 'headline')
            segment_text = segment.get('text', '')
            
            if story_index is not None:
                # This is a story segment (headline only, no summaries)
                if story_index not in stories_dict:
                    stories_dict[story_index] = {'headline': ''}
                
                if segment_type == 'headline':
                    stories_dict[story_index]['headline'] = segment_text
            else:
                # This might be a closing segment
                closing_segment = segment
        
        # Generate one prompt per story
        for story_index in sorted(stories_dict.keys()):
            story_data = stories_dict[story_index]
            headline_text = story_data.get('headline', '')
            
            # Use the headline text as primary (no summaries)
            primary_text = headline_text
            
            # Create a comprehensive image that represents the entire story
            style_note = "Create a dramatic, attention-grabbing image that represents this news story. Use bold visuals, strong composition, and impactful imagery that captures the essence of the story."
            
            prompt = f"""You are creating image prompts for an editorial news video with dramatic, stylized visuals.

News Context:
{news_context}

Story {story_index}:
Headline: "{headline_text}"

{style_note}

Create a detailed, comprehensive image generation prompt for this news story. The prompt should:
1. Be highly specific and descriptive (80-150 words - be thorough and detailed)
2. Use CONCEPT ILLUSTRATION style - editorial, dramatic, stylized art (NOT photorealistic)
3. Use VISUAL METAPHORS and SYMBOLS instead of literal representations of people
4. Use SATIRICAL or EDITORIAL art styles (stylized, expressive, dramatic illustrations)
5. AVOID photorealistic faces or actual people - use silhouettes, abstract figures, symbolic representations, or focus on objects/scenes
6. Describe composition, lighting, colors, mood, and visual style in editorial/artistic terms
7. Be optimized for vertical video format (9:16 aspect ratio)
8. Make it feel editorial and dramatic, not fake - audiences accept stylized illustrations for news
9. CRITICAL: NO TEXT, NO WORDS, NO LETTERS - The image must be purely visual with no text elements whatsoever
10. CRITICAL FOR INDIAN LOCATIONS: If the story mentions Indian locations (Delhi, Chennai, Mumbai, Bangalore, Parliament, Sansad Bhavan, etc.), you MUST specify "Indian [location/building]" in the prompt. For example:
    - "Indian Parliament building (Sansad Bhavan)" NOT "US Capitol Building" or "Parliament building"
    - "Indian city of Delhi" NOT just "Delhi" or "city"
    - "Indian government building" NOT "government building"
    - For Indian cities, always specify "Indian city of [name]" to ensure visual accuracy

Focus on:
- CONCEPT ILLUSTRATIONS: Use symbolic, metaphorical, or abstract visual representations
- EDITORIAL ART STYLE: Stylized, dramatic, expressive illustrations (like editorial cartoons or magazine illustrations)
- VISUAL METAPHORS: Represent concepts through symbols, objects, scenes, compositions
- AVOID photorealistic people: Use silhouettes, abstract human forms, symbolic figures, or focus on objects/scenes
- SATIRICAL ELEMENTS: When appropriate, use exaggerated, stylized, or satirical visual elements
- For headlines: Dramatic, attention-grabbing concept illustrations
- For summaries: Detailed, explanatory concept illustrations with visual metaphors
- Visual symbols, scenes, or compositions that represent the story WITHOUT any text

IMPORTANT RESTRICTIONS:
- Do NOT include any text, words, letters, signs, banners, headlines, or written content in the image
- Use CONCEPT ILLUSTRATION style, NOT photorealistic photography
- Use VISUAL METAPHORS and SYMBOLS instead of literal people/faces
- AVOID generating actual faces or photorealistic people - use silhouettes, abstract forms, or focus on objects/scenes
- Focus on visual metaphors, symbols, abstract representations, stylized illustrations

Return ONLY the image prompt text, nothing else. Be specific and descriptive."""

            try:
                # Use unified LLM client with fallback
                response = self.llm_client.generate(
                    prompt,
                    {
                        "temperature": 0.7,
                        "num_predict": 200,
                    }
                )
                
                image_prompt = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
                
                # Clean up the prompt - remove HTML tags and clean text
                import re
                # Remove HTML tags
                image_prompt = re.sub(r'<[^>]+>', '', image_prompt)
                # Remove HTML entities
                image_prompt = image_prompt.replace('&nbsp;', ' ').replace('&amp;', '&')
                image_prompt = image_prompt.replace('&lt;', '<').replace('&gt;', '>')
                image_prompt = image_prompt.replace('&quot;', '"').replace('&#39;', "'")
                # Clean up quotes and markdown
                image_prompt = image_prompt.strip('"').strip("'")
                if '```' in image_prompt:
                    image_prompt = image_prompt.split('```')[0].strip()
                # Clean up extra whitespace
                image_prompt = ' '.join(image_prompt.split())
                
                # Validate prompt quality - ensure it's not HTML or too short
                if len(image_prompt) < 20 or image_prompt.startswith('<img') or 'src=' in image_prompt.lower():
                    # Too short or contains HTML, use fallback
                    image_prompt = f"Professional news broadcast image representing: {primary_text[:50]}"
                    # Clean the fallback too
                    image_prompt = re.sub(r'<[^>]+>', '', image_prompt)
                    image_prompt = ' '.join(image_prompt.split())
                
                prompts.append(image_prompt)
                print(f"\n  📸 Generated image prompt {story_index}/{len(stories_dict)} (Story {story_index}):")
                print(f"     Headline: {headline_text[:60]}...")
                print(f"     Image prompt: {image_prompt[:100]}...")
                print()
                
            except Exception as e:
                print(f"  Warning: Could not generate image prompt for story {story_index}: {e}")
                # Fallback prompt
                fallback = f"Professional news broadcast image representing: {primary_text[:50]}"
                prompts.append(fallback)
        
        # Add closing image prompt if there's a closing segment
        if closing_segment:
            prompts.append("News broadcast closing scene")
        
        return prompts if prompts else [
            "Professional news broadcast studio",
            "Breaking news headline displayed",
            "News anchor presenting",
        ]
    
    def _ensure_headline_summary_pairs(self, segments: List[Dict]) -> List[Dict]:
        """
        Ensure segments alternate between headline and summary pairs
        Each story should have: headline → summary → headline → summary...
        """
        if not segments:
            return segments
        
        # Fix segment types to ensure proper alternation
        for i, segment in enumerate(segments):
            # Skip hook/opening segments
            if i == 0 and len(segment.get('text', '')) < 30:
                # Likely a hook, keep as is
                continue
            
            # Determine expected type based on position
            # After hook, should alternate: headline, summary, headline, summary...
            # Count non-hook segments
            non_hook_count = sum(1 for j, s in enumerate(segments[:i+1]) 
                                if j == 0 or len(s.get('text', '')) >= 30)
            
            # Even positions (0, 2, 4...) should be headlines
            # Odd positions (1, 3, 5...) should be summaries
            # But account for hook at position 0
            if i == 0:
                # First segment after hook - should be headline
                expected_type = 'headline'
            else:
                # Check previous segment
                prev_segment = segments[i-1]
                prev_type = prev_segment.get('type', '')
                
                if prev_type == 'headline':
                    expected_type = 'summary'
                elif prev_type == 'summary':
                    expected_type = 'headline'
                else:
                    # If no type set, alternate based on index
                    expected_type = 'headline' if (i % 2 == 0) else 'summary'
            
            # Set the type if not already set or if wrong
            current_type = segment.get('type', '')
            if not current_type or current_type not in ['headline', 'summary']:
                segment['type'] = expected_type
            elif current_type != expected_type and i > 0:
                # Only fix if it's clearly wrong (not the hook)
                segment['type'] = expected_type
        
        return segments
    
    def _normalize_segments(self, segments: List[Dict]) -> List[Dict]:
        """Normalize segment durations to ensure they add up to 60 seconds"""
        if not segments:
            return segments
        
        total_duration = sum(s.get('duration', 0) for s in segments)
        if total_duration == 0:
            # Calculate durations from word count
            for segment in segments:
                word_count = len(segment.get('text', '').split())
                segment['duration'] = max(3, round(word_count / 2.5))
            total_duration = sum(s.get('duration', 0) for s in segments)
        
        # Normalize to 60 seconds
        if total_duration != 60:
            scale_factor = 60 / total_duration if total_duration > 0 else 1
            for segment in segments:
                segment['duration'] = max(3, round(segment.get('duration', 10) * scale_factor))
        
        # Recalculate start times
        current_time = 0
        for segment in segments:
            segment['start_time'] = current_time
            current_time += segment.get('duration', 10)
        
        # Ensure total is exactly 60
        total = sum(s.get('duration', 0) for s in segments)
        if total != 60 and segments:
            diff = 60 - total
            segments[-1]['duration'] += diff
        
        return segments
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for better comparison"""
        import re
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Remove special characters that don't affect meaning
        text = re.sub(r'[^\w\s]', '', text.lower())
        return text.strip()
    
    def _are_titles_similar(self, title1: str, title2: str, threshold: float = 0.85) -> bool:
        """Check if two titles are very similar using simple string matching"""
        if not title1 or not title2:
            return False
        
        # Normalize titles
        norm1 = self._normalize_text(title1)
        norm2 = self._normalize_text(title2)
        
        # Exact match after normalization
        if norm1 == norm2:
            return True
        
        # Check if one title contains most of the other
        if len(norm1) > 0 and len(norm2) > 0:
            # Calculate word overlap
            words1 = set(norm1.split())
            words2 = set(norm2.split())
            if len(words1) > 0 and len(words2) > 0:
                overlap = len(words1 & words2) / max(len(words1), len(words2))
                if overlap >= threshold:
                    return True
        
        return False
    
    def _are_urls_similar(self, url1: str, url2: str) -> bool:
        """Check if two URLs point to the same article"""
        if not url1 or not url2:
            return False
        
        # Normalize URLs (remove query params, fragments, trailing slashes)
        import re
        from urllib.parse import urlparse, parse_qs
        
        try:
            parsed1 = urlparse(url1.lower().rstrip('/'))
            parsed2 = urlparse(url2.lower().rstrip('/'))
            
            # Compare domain and path
            if parsed1.netloc == parsed2.netloc and parsed1.path == parsed2.path:
                return True
            
            # Check if paths are very similar (e.g., different query params)
            if parsed1.netloc == parsed2.netloc:
                path1 = re.sub(r'/\d+$', '', parsed1.path)  # Remove trailing numbers
                path2 = re.sub(r'/\d+$', '', parsed2.path)
                if path1 == path2 and len(path1) > 10:  # Only if path is substantial
                    return True
        except:
            pass
        
        return False
    
    def _remove_duplicate_articles(self, articles: List[Dict], similarity_threshold: float = 0.60) -> List[Dict]:
        """
        Remove duplicate articles using multi-stage deduplication:
        1. URL-based (exact match)
        2. Title-based (similar titles)
        3. Semantic similarity (embedding-based)
        
        Args:
            articles: List of news articles
            similarity_threshold: Cosine similarity threshold (0.60 = more aggressive, catches more duplicates)
        
        Returns: List of unique articles (no duplicates)
        """
        if not articles:
            return articles
        
        # Stage 1: Quick URL-based deduplication
        seen_urls = {}
        url_filtered = []
        for article in articles:
            url = article.get('link', '').strip()
            if url:
                # Normalize URL
                url_normalized = url.lower().rstrip('/')
                if url_normalized not in seen_urls:
                    seen_urls[url_normalized] = article
                    url_filtered.append(article)
                else:
                    # URL already seen - keep the one with more complete info
                    existing = seen_urls[url_normalized]
                    if len(article.get('description', '')) > len(existing.get('description', '')):
                        # Replace with better version
                        idx = url_filtered.index(existing)
                        url_filtered[idx] = article
                        seen_urls[url_normalized] = article
            else:
                # No URL, keep it for further processing
                url_filtered.append(article)
        
        url_removed = len(articles) - len(url_filtered)
        if url_removed > 0:
            print(f"  🔗 Removed {url_removed} duplicates by URL matching")
        
        # Stage 2: Title-based deduplication (for articles without URLs or with different URLs)
        title_filtered = []
        seen_titles = {}
        for article in url_filtered:
            title = article.get('title', '').strip()
            if not title:
                title_filtered.append(article)
                continue
            
            title_normalized = self._normalize_text(title)
            
            # Check if we've seen a very similar title
            is_duplicate = False
            for seen_title_norm, seen_article in seen_titles.items():
                if self._are_titles_similar(title, seen_title_norm):
                    # Similar title found - keep the one with more complete info
                    if len(article.get('description', '')) > len(seen_article.get('description', '')):
                        # Replace existing
                        idx = title_filtered.index(seen_article)
                        title_filtered[idx] = article
                        seen_titles[seen_title_norm] = article
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                seen_titles[title_normalized] = article
                title_filtered.append(article)
        
        title_removed = len(url_filtered) - len(title_filtered)
        if title_removed > 0:
            print(f"  📰 Removed {title_removed} duplicates by title similarity")
        
        # If no embedding model, return title-filtered results
        if not self.embedding_model:
            return title_filtered
        
        # Stage 3: Semantic similarity (embedding-based) for remaining articles
        unique_articles = []
        article_texts = []
        
        for article in title_filtered:
            title = article.get('title', '').strip()
            description = article.get('description', '').strip()
            # Create text representation for embedding (normalize for better matching)
            text = f"{title} {description}".strip()
            if not text:
                continue
            
            article_texts.append(text)
            unique_articles.append(article)
        
        if len(unique_articles) <= 1:
            return unique_articles
        
        # Generate embeddings for all articles
        try:
            embeddings = self.embedding_model.encode(article_texts, show_progress_bar=False)
            
            # Find duplicates using cosine similarity
            to_remove = set()
            for i in range(len(unique_articles)):
                if i in to_remove:
                    continue
                
                for j in range(i + 1, len(unique_articles)):
                    if j in to_remove:
                        continue
                    
                    # Also check URL similarity as additional filter
                    url_i = unique_articles[i].get('link', '').strip()
                    url_j = unique_articles[j].get('link', '').strip()
                    if url_i and url_j and self._are_urls_similar(url_i, url_j):
                        # URLs are similar - remove one
                        if len(article_texts[i]) >= len(article_texts[j]):
                            to_remove.add(j)
                        else:
                            to_remove.add(i)
                            break
                        continue
                    
                    # Calculate cosine similarity
                    similarity = cosine_similarity([embeddings[i]], [embeddings[j]])[0][0]
                    
                    # Extract key topic words to check if same story/topic
                    # Check for common key phrases/entities that indicate same story
                    title_i = unique_articles[i].get('title', '')
                    title_j = unique_articles[j].get('title', '')
                    
                    # Get first 30 words from each article text for topic extraction
                    words_i = article_texts[i].lower().split()[:30]
                    words_j = article_texts[j].lower().split()[:30]
                    
                    # Remove common stop words and short words
                    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how', 'not', 'no', 'yes', 'so', 'if', 'then', 'than', 'as', 'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'once', 'here', 'there', 'when', 'where', 'why', 'all', 'each', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'now'}
                    key_words_i = {w for w in words_i if w not in stop_words and len(w) > 3}
                    key_words_j = {w for w in words_j if w not in stop_words and len(w) > 3}
                    
                    # Calculate key word overlap (indicates same topic)
                    if len(key_words_i) > 0 and len(key_words_j) > 0:
                        key_overlap = len(key_words_i & key_words_j) / max(len(key_words_i), len(key_words_j))
                    else:
                        key_overlap = 0
                    
                    # Check title similarity
                    title_similar = self._are_titles_similar(title_i, title_j, threshold=0.75)  # Lower threshold for title similarity
                    
                    # Use lower threshold (0.60) to catch more duplicates
                    # Also check title similarity and key word overlap as tiebreakers
                    if similarity >= similarity_threshold:
                        # If both semantic and title are similar, definitely duplicate
                        # OR if key words overlap significantly (same topic) with decent semantic similarity
                        if title_similar or similarity >= 0.70 or (key_overlap >= 0.35 and similarity >= 0.60):
                            # Keep the one with longer/more complete text
                            if len(article_texts[i]) >= len(article_texts[j]):
                                to_remove.add(j)
                            else:
                                to_remove.add(i)
                                break
                        # If semantic similarity is high but titles differ, might be related but different angle
                        # Remove if similarity is high (0.70+) OR if key words overlap significantly
                        elif similarity >= 0.70 or (key_overlap >= 0.45 and similarity >= 0.65):
                            if len(article_texts[i]) >= len(article_texts[j]):
                                to_remove.add(j)
                            else:
                                to_remove.add(i)
                                break
            
            # Remove duplicates
            filtered_articles = [article for idx, article in enumerate(unique_articles) if idx not in to_remove]
            
            semantic_removed = len(to_remove)
            if semantic_removed > 0:
                print(f"  🧠 Removed {semantic_removed} duplicates using semantic similarity")
            
            total_removed = len(articles) - len(filtered_articles)
            if total_removed > 0:
                print(f"  ✅ Total duplicates removed: {total_removed} (kept {len(filtered_articles)} unique articles)")
            
            return filtered_articles
            
        except Exception as e:
            print(f"  ⚠️  Error in semantic duplicate detection: {e}, using title-filtered results")
            return title_filtered
    
    def _create_fallback_script(self, articles: List[Dict], script_type: str) -> Dict:
        """Create a simple fallback script if Ollama fails"""
        if script_type == "today":
            title = "Today in 60 Seconds"
            script_parts = []
            for i, article in enumerate(articles[:5], 1):
                script_parts.append(f"Story {i}: {article['title']}")
            script = "Welcome to Today in 60 Seconds. " + " ".join(script_parts)
        else:
            title = f"Breaking: {articles[0]['title'] if articles else 'Hot Topic'}"
            script = f"Here's what you need to know. {articles[0].get('description', '') if articles else 'Important news update.'}"
        
        return {
            "title": title,
            "script": script,
            "segments": [
                {"text": script[:100], "duration": 20, "start_time": 0},
                {"text": script[100:200] if len(script) > 100 else script, "duration": 20, "start_time": 20},
                {"text": script[200:] if len(script) > 200 else script, "duration": 20, "start_time": 40}
            ],
            "image_prompts": [
                "Professional news broadcast studio",
                "Breaking news headline on screen",
                "News anchor presenting",
            ]
        }
    
    def _determine_optimal_story_count(self, articles: List[Dict], target_age_group: str = "young") -> int:
        """
        Dynamically determine the optimal number of stories based on:
        1. People's interest (engagement, trending, viral potential)
        2. Severity (breaking news, urgent, high impact, critical)
        
        Args:
            articles: List of news articles (should be deduplicated)
            target_age_group: Target age group for relevance filtering
        
        Returns:
            Optimal number of stories (minimum 3, maximum 8)
        """
        if not articles:
            return 4  # Default
        
        if len(articles) <= 3:
            return len(articles)
        
        # Use LLM to identify distinct major/hot topics based on INTEREST and SEVERITY
        news_list = "\n".join([
            f"{i+1}. {article['title']}\n   {article.get('description', '')[:150]}"
            for i, article in enumerate(articles[:50])  # Analyze first 50 for better coverage
        ])
        
        # Define age-specific interest indicators
        interest_context = {
            "young": "trending topics, viral stories, social media buzz, pop culture, tech innovations, career/job market, education, youth issues, entertainment, gaming, social trends",
            "middle_age": "business news, economic policies, job market, investments, family finances, education for children, health/fitness, real estate, tax changes, career advancement, work-life balance",
            "old": "healthcare policies, pension/retirement, senior benefits, medical facilities, government schemes, property/legal matters, inflation impact, social security, community events",
            "all_audiences": "breaking news, major policy changes, economic updates, health alerts, education updates, technology news, business news, government announcements, public safety, infrastructure, transportation, financial news - topics that affect everyone",
            "general": "breaking news, major policy changes, economic updates, health alerts, education updates, technology news, business news, government announcements, public safety, infrastructure, transportation, financial news - topics that affect everyone"
        }
        
        # Use target_age_group directly (it's already set correctly)
        interest_indicators = interest_context.get(target_age_group, interest_context["young"])
        
        prompt = f"""You are analyzing today's news to determine how many DISTINCT stories should be covered based on TWO CRITICAL FACTORS:

1. **PEOPLE'S INTEREST** (How much do people care about this?)
   - Trending/viral topics that people are actively discussing
   - Stories with high engagement potential (social media buzz, shares, comments)
   - Topics relevant to {target_age_group} audience: {interest_indicators}
   - Breaking news that everyone is talking about
   - Controversial or attention-grabbing stories
   - Stories that affect daily life, work, finances, or future

2. **SEVERITY** (How serious/urgent is this news?)
   - Breaking news or urgent developments
   - Major policy changes or government announcements
   - Critical events affecting many people
   - High-impact incidents (disasters, major accidents, security issues)
   - Time-sensitive information requiring immediate awareness
   - Stories with significant consequences

Here are the news articles:
{news_list}

Your task: Count how many DISTINCT stories meet BOTH criteria (high interest AND high severity).

**COUNTING RULES:**
- Group articles about the SAME story/topic together (e.g., multiple articles about "Sanchar Saathi app" = 1 story)
- Count only DISTINCT stories (not number of articles)
- A story qualifies if it has:
  * HIGH INTEREST (people care about it, trending, relevant to audience) AND
  * HIGH SEVERITY (breaking, urgent, major impact, critical)
- Ignore:
  * Minor updates or follow-ups to previous stories
  * Soft news with low impact
  * Stories with low interest (nobody cares) OR low severity (not urgent/important)
  * Duplicate coverage of same event

**PRIORITIZE:**
- Stories that are BOTH highly interesting AND highly severe
- If many stories meet criteria, count all of them (up to 8 maximum)
- If few stories meet criteria, only count those that truly qualify

Return ONLY a number between 3 and 8 representing the count of distinct stories that are BOTH high-interest AND high-severity.
Examples:
- 3 highly interesting + severe stories → return 3
- 5 highly interesting + severe stories → return 5
- 7+ highly interesting + severe stories → return 8 (maximum)

Return format: Just the number, nothing else.
"""
        
        try:
            result = self.llm_client.generate(prompt, {"max_tokens": 10})
            if result and result.get("response"):
                response = result["response"]
                # Extract number from response
                import re
                numbers = re.findall(r'\d+', response.strip())
                if numbers:
                    count = int(numbers[0])
                    # Clamp between 3 and 8
                    count = max(3, min(8, count))
                    print(f"  🎯 Detected {count} distinct major/hot topics")
                    return count
        except Exception as e:
            print(f"  ⚠️  Error determining topic count: {e}, using default")
        
        # Fallback: Use heuristics based on article count and quality
        # With 100 articles fetched, we expect more diverse topics
        if len(articles) >= 50:
            return 7  # Many high-quality articles = likely many important topics
        elif len(articles) >= 30:
            return 6  # Good number of articles = several important topics
        elif len(articles) >= 15:
            return 5  # Moderate articles = moderate topics
        elif len(articles) >= 8:
            return 4  # Fewer articles = fewer topics
        else:
            return 3  # Very few articles = minimal topics
    
    def analyze_and_select_must_know_news(self, articles: List[Dict], select_count: int = None, target_age_group: str = "18-35", skip_deduplication: bool = False) -> List[Dict]:
        """
        Analyze news articles and select stories that users MUST KNOW because they affect daily life
        
        Args:
            articles: List of news articles
            select_count: Number of stories to select. If None, dynamically determined based on major/hot topics.
            target_age_group: Target age group - "young" (18-30), "middle_age" (30-55), "old" (55+)
            skip_deduplication: If True, skip deduplication (e.g., when using Gemini which already selects important news)
        
        Returns: List of selected articles that affect daily life
        """
        # Step 0: Remove duplicates first (before determining count) - unless skipped
        if skip_deduplication:
            print(f"  ⏭️  Skipping deduplication (articles already curated by Gemini)")
            unique_articles = articles
        else:
            print(f"  🔍 Removing duplicate articles using multi-stage detection...")
            unique_articles = self._remove_duplicate_articles(articles, similarity_threshold=0.60)
            print(f"  ✅ {len(unique_articles)} unique articles after duplicate removal (from {len(articles)} total)")
        
        # Determine optimal story count if not provided
        if select_count is None:
            print(f"  📊 Analyzing news to determine optimal story count...")
            select_count = self._determine_optimal_story_count(unique_articles, target_age_group)
            print(f"  ✅ Optimal story count determined: {select_count}")
        
        if len(unique_articles) <= select_count:
            return unique_articles[:select_count]
        
        # Prepare news list for analysis (use unique_articles after duplicate removal)
        news_list = "\n".join([
            f"{i+1}. {article['title']}\n   {article.get('description', '')[:150]}"
            for i, article in enumerate(unique_articles)
        ])
        
        # Define relevance criteria based on age group
        age_group_context = {
            "young": "young adults (18-30) who need to know about: education policies, job market, internships, scholarships, exam updates, tech trends affecting careers, startup opportunities, social issues affecting youth, dating/relationships, housing/rent, career planning, skill development, social media trends, health for young adults",
            "middle_age": "middle-aged adults (30-55) who need to know about: job market, salary trends, tax changes, business news, tech updates affecting work, economic policies, investment opportunities, industry changes, family finances, children's education, health insurance, retirement planning, property/real estate, career advancement, work-life balance",
            "old": "senior citizens (55+) who need to know about: pension updates, healthcare policies, senior citizen benefits, retirement schemes, health alerts, medical facilities, government schemes for elderly, property/legal matters, family matters, social security, inflation impact on savings, medical insurance, age-related health issues, senior citizen discounts/benefits",
            "all_audiences": "all audiences (all age groups) who need to know about: breaking news, major policy changes, economic updates, health alerts, education updates, technology news, business news, government announcements, public safety, infrastructure, transportation, financial news - stories that affect everyone regardless of age"
        }
        
        # Handle "all_audiences" as a special case for neutral language
        original_target_age_group = target_age_group
        if target_age_group == "all_audiences":
            target_age_group = "general"  # Use general for story selection
        
        context = age_group_context.get(original_target_age_group, age_group_context.get(target_age_group, age_group_context["young"]))
        
        # Define age-specific topic interests
        age_group_topics = {
            "general": {
                "high_interest": [
                    "Breaking News", "Major Policy Changes", "Economic Updates", 
                    "Health Alerts", "Education Updates", "Technology News",
                    "Business News", "Government Announcements", "Public Safety",
                    "Infrastructure", "Transportation", "Financial News"
                ],
                "low_interest": [
                    "Celebrity Gossip", "Entertainment News", "Sports Scores",
                    "Minor Local Events", "Weather Forecasts (unless major disaster)"
                ]
            },
            "all_audiences": {
                "high_interest": [
                    "Breaking News", "Major Policy Changes", "Economic Updates", 
                    "Health Alerts", "Education Updates", "Technology News",
                    "Business News", "Government Announcements", "Public Safety",
                    "Infrastructure", "Transportation", "Financial News"
                ],
                "low_interest": [
                    "Celebrity Gossip", "Entertainment News", "Sports Scores",
                    "Minor Local Events", "Weather Forecasts (unless major disaster)"
                ]
            },
            "young": {
                "high_interest": [
                    "Pop Culture", "Social Media Trends", "Gaming", "Affordable Travel", 
                    "Student Loans", "Entry-level Job Markets", "Tech Startups", "Skill Development",
                    "Internships", "Scholarships", "Exam Updates", "Housing/Rent", "Dating/Relationships",
                    "Social Issues", "Youth Policies", "Career Opportunities", "Online Trends"
                ],
                "low_interest": [
                    "Retirement Planning", "Medicare", "Large-scale Geopolitical Conflicts", 
                    "Local Zoning Boards", "Estate Planning", "Senior Benefits", "Pension Schemes"
                ]
            },
            "middle_age": {
                "high_interest": [
                    "Personal Finance", "Real Estate", "Childcare/Education", "Career Advancement",
                    "Health/Fitness", "Local Politics", "Tax Changes", "Investment Opportunities",
                    "Family Finances", "Children's Education", "Health Insurance", "Property/Real Estate",
                    "Work-Life Balance", "Salary Trends", "Business News", "Economic Policies"
                ],
                "low_interest": [
                    "Viral TikTok Dances", "Cryptocurrency (unless investment-focused)", "Extreme Sports",
                    "Pop Culture Trends", "Gaming", "Social Media Challenges", "Youth Slang"
                ]
            },
            "old": {
                "high_interest": [
                    "Healthcare/Medicare", "Retirement/Investment News", "Local Community Events",
                    "Social Security", "Nostalgia/History", "Gardening", "Pension Updates",
                    "Senior Citizen Benefits", "Medical Facilities", "Government Schemes for Elderly",
                    "Property/Legal Matters", "Inflation Impact on Savings", "Medical Insurance",
                    "Age-related Health Issues", "Senior Discounts/Benefits"
                ],
                "low_interest": [
                    "New Tech Gadget Reviews (unless accessibility-focused)", "Niche Internet Culture",
                    "Gaming", "Social Media Trends", "Pop Culture", "Youth Entertainment"
                ]
            }
        }
        
        topics = age_group_topics.get(target_age_group, age_group_topics["young"])
        
        prompt = f"""You are an expert news editor analyzing today's news using MULTI-DIMENSIONAL analysis to identify stories that people MUST KNOW.

Target Audience: {original_target_age_group if original_target_age_group == "all_audiences" else target_age_group} ({context})

Here are {len(unique_articles)} unique news articles (duplicates have been removed):

{news_list}

Your task: Select the top {select_count} stories using THREE types of analysis:

## A. SUBJECT MATTER ANALYSIS (Explicit Topics) 📰

Analyze the EXPLICIT topics and entities in each article:

HIGH-INTEREST TOPICS for {target_age_group}:
{', '.join(topics['high_interest'])}

LOW-INTEREST TOPICS for {target_age_group} (AVOID unless major impact):
{', '.join(topics['low_interest'])}

Use Named Entity Recognition (NER) to identify:
- People: "Taylor Swift" (young) vs "Federal Reserve Chairman" (middle_age/old)
- Organizations: "TikTok" (young) vs "Medicare" (old)
- Products: "New iPhone" (young/middle_age) vs "Hearing Aid" (old)
- Concepts: "Student Loans" (young) vs "Retirement Planning" (old)

PRIORITIZE articles with entities/topics from HIGH-INTEREST list.
PENALIZE articles with entities/topics from LOW-INTEREST list (unless major national impact).

## B. TONE AND LANGUAGE ANALYSIS (Implicit Cues) 📝

Analyze the WRITING STYLE and LANGUAGE:

For YOUNG (18-30):
- ✅ Modern slang, internet abbreviations ("rizz", "NFT", "vibe")
- ✅ Casual, energetic tone
- ✅ Lower reading level (simpler syntax, shorter sentences)
- ✅ Cynical or rebellious tone
- ✅ Cultural references (memes, trends, pop culture)
- ❌ Formal, authoritative tone
- ❌ Complex financial/political jargon
- ❌ Respectful, traditional language

For MIDDLE_AGE (30-55):
- ✅ Professional, balanced tone
- ✅ Moderate reading level
- ✅ Practical, informative language
- ✅ Family/career-focused vocabulary
- ✅ Business/finance terminology
- ❌ Gen Z slang or internet culture
- ❌ Extremely casual or rebellious tone
- ❌ Overly technical academic language

For OLD (55+):
- ✅ Respectful, authoritative tone
- ✅ Clear, straightforward language
- ✅ Traditional vocabulary
- ✅ Health/retirement terminology
- ✅ Community-focused language
- ❌ Modern slang or internet abbreviations
- ❌ Fast-paced, energetic tone
- ❌ Gaming or pop culture references

PRIORITIZE articles whose TONE matches the target age group.

## C. SOURCE AND FORMAT ANALYSIS 📱

Consider the SOURCE and FORMAT indicators:

For YOUNG:
- ✅ Short-form content (60-second videos, quick reads)
- ✅ Social media sources, gaming websites, pop culture sites
- ✅ Visual-heavy, fast-paced formats
- ❌ Long-form editorials (3000+ words)
- ❌ Specialized retirement/financial planning sites

For MIDDLE_AGE:
- ✅ Medium-length articles, professional sources
- ✅ Business/finance websites, news outlets
- ✅ Balanced format (not too short, not too long)
- ❌ Gaming websites, TikTok-style content
- ❌ Extremely technical academic sources

For OLD:
- ✅ Traditional news sources, community newspapers
- ✅ Long-form editorials, detailed analysis
- ✅ Print-style, comprehensive coverage
- ❌ Social media sources, gaming websites
- ❌ Fast-paced, visual-heavy formats

## SELECTION CRITERIA (Weighted):

1. **IMPORTANCE & NEWSWORTHINESS (30% weight) - HIGHEST PRIORITY**: 
   - Breaking news, major events, significant policy changes
   - National/regional impact (affects many people)
   - Urgent/time-sensitive information
   - High-profile events, major announcements
   - Stories that would be on front page of major news sites
   - CRITICAL: Prioritize IMPORTANT news even if slightly less relevant to age group

2. **Subject Matter Match (25% weight)**: 
   - Topics/entities match HIGH-INTEREST list
   - Avoid LOW-INTEREST topics (unless major impact)

3. **Daily Life Impact (20% weight)**:
   - Affects daily routines, finances, health, work, education
   - Immediate consequences for viewers
   - Changes that require action or awareness

4. **Tone/Language Match (15% weight)**:
   - Writing style matches target age group
   - Reading level appropriate
   - Vocabulary and tone suitable
   - NOTE: Less important than news value - important news can override tone mismatch

5. **Practical Value (10% weight)**:
   - Actionable information
   - Helps make decisions
   - Prevents problems

## PRIORITIZE stories that:
- Are IMPORTANT and NEWSWORTHY (breaking news, major events, significant impact)
- Match HIGH-INTEREST topics for {target_age_group}
- Affect daily life, work, finances, health, or future
- Have national/regional significance
- Are time-sensitive or urgent

## SELECTION STRATEGY:
1. FIRST: Identify the MOST IMPORTANT stories (regardless of age group relevance)
2. THEN: Among important stories, prioritize those relevant to {target_age_group}
3. BALANCE: If a story is VERY IMPORTANT but less age-relevant, still include it
4. AVOID: Only truly unimportant stories (minor local news, pure entertainment, etc.)

## AVOID stories that:
- Are trivial or unimportant (unless highly relevant to age group)
- Match LOW-INTEREST topics (unless major national impact)
- Pure entertainment (unless major event)
- Sports scores (unless policy/career-related or major tournament)
- International news (unless directly affects India/Indians)
- **DUPLICATE or SIMILAR stories about the SAME topic/event** (CRITICAL: Only select ONE story per topic/event)

## CRITICAL: NO DUPLICATE TOPICS
- If multiple articles cover the SAME story/topic/event, select ONLY THE MOST IMPORTANT ONE
- Examples of duplicates to avoid:
  - "Sanchar Saathi app launched" + "New Sanchar Saathi app features" = SAME TOPIC, pick one
  - "Delhi AQI 500" + "Delhi air quality alert" = SAME TOPIC, pick one
  - "RBI rate cut" + "RBI announces interest rate change" = SAME TOPIC, pick one
- Only select multiple articles if they cover DIFFERENT aspects or DIFFERENT events
- When in doubt, choose the article with the most complete information

Return your response as a JSON array with the article numbers (1-indexed) of the selected stories, ordered by IMPORTANCE first, then relevance (most important/relevant first).

Example format:
[3, 1, 7, 2, 5]

Return ONLY the JSON array, no explanation or markdown formatting."""

        try:
            response = self.llm_client.generate(prompt, {
                "temperature": 0.3,
                "num_predict": 200,
            })
            
            content = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            # Extract JSON array
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            # Clean up content
            content = content.strip().strip('[').strip(']')
            # Extract numbers
            import re
            numbers = [int(x.strip()) for x in re.findall(r'\d+', content)]
            
            # Select articles based on indices (convert to 0-indexed)
            # Use unique_articles (after duplicate removal) instead of original articles
            selected_articles = []
            seen_indices = set()
            for num in numbers:
                idx = num - 1  # Convert to 0-indexed
                if 0 <= idx < len(unique_articles) and idx not in seen_indices:
                    selected_articles.append(unique_articles[idx])
                    seen_indices.add(idx)
                    if len(selected_articles) >= select_count:
                        break
            
            # If we didn't get enough, fill with remaining articles
            if len(selected_articles) < select_count:
                for i, article in enumerate(unique_articles):
                    if i not in seen_indices:
                        selected_articles.append(article)
                        if len(selected_articles) >= select_count:
                            break
            
            # Final deduplication pass on selected articles (in case LLM selected duplicates)
            # Skip if articles came from Gemini (already curated)
            # Use MORE AGGRESSIVE threshold to catch similar stories about same topic
            # Check if articles likely came from Gemini (small count, already curated)
            if len(selected_articles) <= 10:
                print(f"📊 Using {len(selected_articles)} stories from Gemini (skipping final deduplication)")
                final_articles = selected_articles
            else:
                print(f"📊 LLM selected {len(selected_articles)} stories, performing final deduplication check...")
                final_articles = self._remove_duplicate_articles(selected_articles, similarity_threshold=0.55)  # Lower threshold = more aggressive (was 0.70)
            
            # If we lost articles due to final dedup, fill with remaining unique articles
            if len(final_articles) < select_count and len(final_articles) < len(unique_articles):
                seen_final_titles = {self._normalize_text(a.get('title', '')) for a in final_articles}
                for article in unique_articles:
                    if len(final_articles) >= select_count:
                        break
                    title_norm = self._normalize_text(article.get('title', ''))
                    if title_norm not in seen_final_titles:
                        final_articles.append(article)
                        seen_final_titles.add(title_norm)
            
            print(f"✅ Final selection: {len(final_articles)} unique must-know stories for {target_age_group} audience")
            return final_articles[:select_count]
            
        except Exception as e:
            print(f"⚠️  Error analyzing must-know news: {e}")
            print(f"   Falling back to first {select_count} unique articles")
            return unique_articles[:select_count]
    
    def _load_selected_stories(self) -> Dict:
        """
        Load previously selected stories from file
        
        Returns:
            Dict with dates as keys and lists of story titles as values
        """
        selected_file = os.path.join(TEMP_DIR, "selected_viral_stories.json")
        if os.path.exists(selected_file):
            try:
                with open(selected_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"  ⚠️  Could not load selected stories: {e}")
                return {}
        return {}
    
    def _save_selected_story(self, article: Dict):
        """
        Save selected story to file with today's date
        
        Args:
            article: Selected article dict
        """
        from datetime import datetime
        selected_file = os.path.join(TEMP_DIR, "selected_viral_stories.json")
        
        # Load existing data
        selected_stories = self._load_selected_stories()
        
        # Get today's date (YYYY-MM-DD format)
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Initialize today's list if not exists
        if today not in selected_stories:
            selected_stories[today] = []
        
        # Add story title (use first 100 chars as identifier)
        story_title = article.get('title', '')[:100]
        if story_title and story_title not in selected_stories[today]:
            selected_stories[today].append(story_title)
            
            # Save to file
            try:
                os.makedirs(TEMP_DIR, exist_ok=True)
                with open(selected_file, 'w', encoding='utf-8') as f:
                    json.dump(selected_stories, f, indent=2, ensure_ascii=False)
                print(f"  💾 Saved selected story to tracking file: {story_title[:50]}...")
            except Exception as e:
                print(f"  ⚠️  Could not save selected story: {e}")
    
    def _filter_already_selected(self, news_articles: List[Dict]) -> List[Dict]:
        """
        Filter out stories that were already selected today
        
        Args:
            news_articles: List of news articles
            
        Returns:
            Filtered list excluding already-selected stories
        """
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        selected_stories = self._load_selected_stories()
        
        if today not in selected_stories:
            return news_articles
        
        today_selected = selected_stories[today]
        if not today_selected:
            return news_articles
        
        filtered = []
        for article in news_articles:
            article_title = article.get('title', '')[:100]
            # Check if this story was already selected today
            if article_title not in today_selected:
                filtered.append(article)
            else:
                print(f"  ⏭️  Skipping already-selected story: {article_title[:50]}...")
        
        if len(filtered) < len(news_articles):
            print(f"  📋 Filtered out {len(news_articles) - len(filtered)} already-selected stories")
        
        return filtered
    
    def _is_today_news(self, article: Dict) -> bool:
        """
        Check if article is from today (IST)
        
        Args:
            article: News article dict
            
        Returns:
            True if article is from today, False otherwise
        """
        from datetime import datetime, timezone, timedelta
        
        published = article.get('published', '')
        if not published:
            # If no published date, assume it's recent (from Gemini's today search)
            return True
        
        try:
            # Get today's IST date
            ist = timezone(timedelta(hours=5, minutes=30))
            today_ist = datetime.now(ist).date()
            
            # Parse article date
            if isinstance(published, str):
                # Try to extract date from ISO format or other formats
                if 'T' in published:
                    date_str = published.split('T')[0]
                else:
                    date_str = published[:10]  # First 10 chars (YYYY-MM-DD)
                
                article_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                return article_date == today_ist
        except:
            # If parsing fails, assume it's recent (from Gemini's today search)
            return True
        
        return True
    
    def _fact_check_article(self, article: Dict) -> bool:
        """
        Basic fact-checking for article to catch obvious errors
        
        Args:
            article: Article dict
            
        Returns:
            True if article passes fact-check, False if likely incorrect
        """
        title = article.get('title', '').lower()
        description = article.get('description', '').lower()
        text = f"{title} {description}"
        
        # Check for known incorrect facts
        # GDP-related: If it mentions GDP with a specific wrong number
        if 'gdp' in text and '4.2%' in text:
            # This is likely incorrect - India's GDP is around 6.6%, not 4.2%
            print(f"  ⚠️  Fact-check warning: Article mentions GDP 4.2% which may be incorrect")
            return False
        
        # Check for suspicious future dates
        published = article.get('published', '')
        if published:
            try:
                from datetime import datetime
                if 'T' in published:
                    article_date_str = published.split('T')[0]
                else:
                    article_date_str = published[:10]
                
                article_date = datetime.strptime(article_date_str, '%Y-%m-%d')
                today = datetime.now()
                
                # If article is more than 1 day in the future, it's likely fabricated
                if article_date > today:
                    days_ahead = (article_date - today).days
                    if days_ahead > 1:
                        print(f"  ⚠️  Fact-check warning: Article dated {days_ahead} days in the future")
                        return False
            except:
                pass
        
        return True
    
    def select_most_viral_story(self, news_articles: List[Dict]) -> Optional[Dict]:
        """
        Select the SINGLE most viral, emotional, relatable, or rage-bait story from news articles
        Uses Gemini to analyze and select the story with highest viral potential
        Automatically filters out stories already selected today
        Verifies that selected story is from today
        
        Args:
            news_articles: List of news articles
            
        Returns:
            Single article dict with highest viral potential, or None if no articles
        """
        if not news_articles:
            return None
        
        # Filter out already-selected stories
        filtered_articles = self._filter_already_selected(news_articles)
        
        # Also filter to ensure we only consider today's news
        today_articles = [a for a in filtered_articles if self._is_today_news(a)]
        if today_articles:
            filtered_articles = today_articles
            if len(today_articles) < len(filtered_articles):
                print(f"  📅 Filtered to {len(today_articles)} articles from today (IST)")
        
        # Fact-check articles to filter out incorrect information
        fact_checked_articles = []
        for article in filtered_articles:
            if self._fact_check_article(article):
                fact_checked_articles.append(article)
            else:
                print(f"  ⚠️  Filtered out article due to fact-check failure: {article.get('title', '')[:50]}...")
        
        if fact_checked_articles:
            filtered_articles = fact_checked_articles
            if len(fact_checked_articles) < len(filtered_articles):
                print(f"  ✅ Fact-checked: {len(fact_checked_articles)} articles passed verification")
        
        if not filtered_articles:
            print(f"  ⚠️  All stories were already selected today. Using original list.")
            filtered_articles = news_articles
        
        if len(filtered_articles) == 1:
            selected = filtered_articles[0]
            self._save_selected_story(selected)
            return selected
        
        print(f"  🔥 Analyzing {len(filtered_articles)} stories for viral potential...")
        
        # Prepare news list for analysis
        news_list = "\n".join([
            f"{i+1}. {article['title']}\n   {article.get('description', '')[:200]}"
            for i, article in enumerate(filtered_articles)
        ])
        
        prompt = f"""You are a viral content strategist selecting the SINGLE most viral-worthy news story for a 20-30 second video.

Here are {len(filtered_articles)} news articles:

{news_list}

Your task: Select the ONE story with the HIGHEST viral potential based on these criteria (in order of importance):

1. EMOTIONAL IMPACT (40% weight):
   - Stories that trigger strong emotions: shock, anger, outrage, excitement, fear, surprise
   - Stories that make people feel something intensely
   - Examples: Controversial decisions, shocking revelations, dramatic changes, scandals

2. RELATABLE CHAOS (30% weight):
   - Stories that create relatable chaos or disruption in daily life
   - Stories that affect many people's daily routines, plans, or expectations
   - Examples: Policy changes affecting daily life, sudden disruptions, unexpected changes
   - Stories people can immediately relate to: "This affects MY life"

3. VISUAL POTENTIAL (20% weight):
   - Stories that can be exaggerated visually with dramatic images
   - Stories with clear visual metaphors or dramatic scenes
   - Stories that can be shown with multiple exaggerated images

4. RAGE BAIT POTENTIAL (10% weight):
   - Stories that trigger outrage, debate, or strong opinions
   - Controversial topics that people will argue about
   - Stories that make people want to share their opinion

PRIORITIZE stories that:
- Are about India, Indian people, Indian cities, Indian policies
- Affect large numbers of people (students, workers, families, etc.)
- Have immediate, tangible impact on daily life
- Are breaking/trending right now
- Create strong emotional reactions

AVOID:
- Celebrity gossip (unless major scandal)
- Sports news (unless major tournament/achievement)
- Soft news (weather forecasts, minor updates)
- International news (unless directly affecting India)

Return ONLY the article number (1-indexed) of the selected story.

Example response:
5

Return ONLY the number, nothing else."""
        
        try:
            response = self.llm_client.generate(prompt, {
                "temperature": 0.3,
                "num_predict": 50,
            })
            
            content = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            
            # Extract number
            import re
            numbers = re.findall(r'\d+', content)
            if numbers:
                selected_index = int(numbers[0]) - 1  # Convert to 0-based
                if 0 <= selected_index < len(filtered_articles):
                    selected = filtered_articles[selected_index]
                    print(f"  ✅ Selected viral story: {selected['title'][:60]}...")
                    # Save to tracking file
                    self._save_selected_story(selected)
                    return selected
            
            # Fallback: return first article
            print(f"  ⚠️  Could not parse selection, using first article")
            selected = filtered_articles[0]
            self._save_selected_story(selected)
            return selected
            
        except Exception as e:
            print(f"  ⚠️  Error selecting viral story: {e}")
            selected = filtered_articles[0] if filtered_articles else news_articles[0]
            if selected:
                self._save_selected_story(selected)
            return selected
    
    def generate_single_story_viral(self, article: Dict, duration: int = 25) -> Dict:
        """
        Generate a 20-30 second viral video script for a SINGLE story
        Focus: Emotional, visual, relatable chaos, rage bait with heavy exaggeration
        
        Args:
            article: Single news article dict
            duration: Target duration in seconds (20-30, default 25)
        
        Returns:
            Dict with title, script, segments, and multiple image prompts (3-5 images)
        """
        print(f"  🔥 Generating viral script for: {article.get('title', 'Untitled')[:60]}...")
        
        article_title = article.get('title', '')
        article_desc = article.get('description', '')
        
        # Calculate word limits based on duration
        words_per_second = 2.7  # Slightly faster for viral content
        total_words = int(duration * words_per_second)
        
        # Segment breakdown (30 seconds example with facts):
        # NO HOOK - Start directly with news
        # What happened: 8s (22 words)
        # Impact statement 1: 3-4s (10 words)
        # Facts 1: 5s (14 words) - NEW
        # Impact statement 2: 3-4s (10 words)
        # Facts 2: 5s (14 words) - NEW (optional)
        # Impact statement 3: 3-4s (10 words)
        # CTA: 3s (8 words)
        
        hook_words = 0  # No hook
        what_happened_words = 22
        impact_statement_words = 10  # Per impact statement
        facts_words = 14  # Per facts segment
        cta_words = 8
        total_impact_words = 30  # Total for all impact statements (3 statements × 10 words)
        
        # Create a concrete example based on the news story to guide Gemini
        # This helps Gemini understand the exact format we want
        example_news = "Flight delays and cancellations at major airports"
        
        prompt = f"""TASK: Create a viral news video script following the EXACT format below.

NEWS STORY TO USE:
Title: {article_title}
Description: {article_desc}

═══════════════════════════════════════════════════════════════
FORMAT TEMPLATE - FOLLOW THIS EXACT STRUCTURE:
═══════════════════════════════════════════════════════════════

EXAMPLE (for news about "{example_news}"):

{{
  "title": "Airport Chaos: Your Flight Plans Just Got Disrupted",
  "what_happened": "Major airports are experiencing widespread flight delays and cancellations, leaving thousands of passengers stranded.",
  "impact_statement_1": "Your vacation plans are ruined - flights are cancelled with no refunds!",
  "facts_1": "Over 200 flights cancelled today. Airlines are offering rebooking but no compensation.",
  "impact_statement_2": "Your business trip is at risk - you might miss that crucial meeting!",
  "facts_2": "Delays averaging 4-6 hours. Airport authorities are struggling to manage the chaos.",
  "impact_statement_3": "Your wallet is taking a hit - last-minute hotel bookings cost double!",
  "cta": "Like and subscribe for more viral news that affects you!",
  "full_script": "Major airports are experiencing widespread flight delays and cancellations, leaving thousands of passengers stranded. Your vacation plans are ruined - flights are cancelled with no refunds! Over 200 flights cancelled today. Airlines are offering rebooking but no compensation. Your business trip is at risk - you might miss that crucial meeting! Delays averaging 4-6 hours. Airport authorities are struggling to manage the chaos. Your wallet is taking a hit - last-minute hotel bookings cost double! Like and subscribe for more viral news that affects you!",
  "image_prompts": [
    "Chaotic airport terminal with frustrated passengers and cancelled flight boards",
    "Stressed traveler on phone trying to rebook cancelled flight",
    "Empty airport gate with delayed flight sign",
    "Angry passenger arguing with airline staff at counter",
    "Crowded airport lounge with exhausted travelers sleeping on floor"
  ]
}}

═══════════════════════════════════════════════════════════════
RULES FOR IMPACT STATEMENTS (CRITICAL - READ CAREFULLY):
═══════════════════════════════════════════════════════════════

✅ DO THIS (GOOD):
- Use "you", "your" to make it personal
- Explain SPECIFIC consequences: "Your [specific thing] will [specific action]"
- Be opinionated: "Your flight is cancelled - no refunds!"
- Connect to daily life: "Your morning commute just got 30 minutes longer!"
- Use concrete examples: "Your grocery bill is about to skyrocket!"

❌ DON'T DO THIS (BAD):
- "This story affects thousands of people!" ❌ (too generic)
- "The impact is massive and the chaos is real!" ❌ (vague, no specifics)
- "This could change everything for millions!" ❌ (not personal, no mechanism)

FORMULA FOR GOOD IMPACT STATEMENTS:
"Your [specific thing people care about] [specific consequence] [timeframe/context]!"

Examples:
- "Your flight is cancelled - no refunds available!"
- "Your electricity bill will double next month!"
- "Your kids' school fees are increasing by 20%!"
- "Your morning commute just got 30 minutes longer!"

═══════════════════════════════════════════════════════════════
YOUR TASK:
═══════════════════════════════════════════════════════════════

Based on the news story above, create a script following the EXACT format of the example.

REQUIREMENTS:
1. what_happened: {what_happened_words} words max, start DIRECTLY with the news (no hook)
2. impact_statement_1: {impact_statement_words} words max, use "your" format, be SPECIFIC
3. facts_1: {facts_words} words max, real facts from the story
4. impact_statement_2: {impact_statement_words} words max, use "your" format, be SPECIFIC
5. facts_2: {facts_words} words max, more real facts
6. impact_statement_3: {impact_statement_words} words max, use "your" format, be SPECIFIC
7. cta: {cta_words} words max

⚠️ TOKEN LIMIT: Keep response UNDER 2000 tokens. Be CONCISE.

Return ONLY this JSON format (no markdown, no explanations):
{{
  "title": "Your viral title here (under 60 chars)",
  "what_happened": "Start directly with the news - what happened? ({what_happened_words} words max)",
  "impact_statement_1": "Your [specific thing] [specific consequence]! ({impact_statement_words} words max, use 'your' format)",
  "facts_1": "Real facts from the story ({facts_words} words max)",
  "impact_statement_2": "Your [specific thing] [specific consequence]! ({impact_statement_words} words max, use 'your' format)",
  "facts_2": "More real facts ({facts_words} words max)",
  "impact_statement_3": "Your [specific thing] [specific consequence]! ({impact_statement_words} words max, use 'your' format)",
  "cta": "Like and subscribe message ({cta_words} words max)",
  "full_script": "Combine all segments above into one script ({total_words} words total)",
  "image_prompts": [
    "Dramatic visual of the event (max 20 words, ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO SIGNS, NO BANNERS - pure visual only)",
    "People affected by the chaos (max 20 words, ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO SIGNS, NO BANNERS - pure visual only)",
    "Visual metaphor of consequences (max 20 words, ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO SIGNS, NO BANNERS - pure visual only)",
    "Emotional reaction scene (max 20 words, ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO SIGNS, NO BANNERS - pure visual only)",
    "Creative dramatic visual (max 20 words, ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO SIGNS, NO BANNERS - pure visual only)"
  ]
}}"""
        
        try:
            response = self.llm_client.generate(prompt, {
                "temperature": 0.8,  # Higher temperature for creative/exaggerated content
                "num_predict": 3000,  # Increased from 800 to 3000 to prevent truncation
            })
            
            content = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            
            # Debug: Log response length and check for image_prompts in raw content
            print(f"    📄 Raw response length: {len(content)} characters")
            if '"image_prompts"' in content or "'image_prompts'" in content:
                print(f"    ✅ Found 'image_prompts' in raw response")
            else:
                print(f"    ⚠️  'image_prompts' NOT found in raw response")
                # Show last 500 chars to see what was cut off
                if len(content) > 500:
                    print(f"    📄 Last 500 chars of response: {content[-500:]}")
            
            # Extract JSON
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            # Try to parse JSON
            try:
                data = json.loads(content.strip())
                # Debug: Check if image_prompts are present
                if 'image_prompts' not in data:
                    print(f"    ⚠️  'image_prompts' key missing from parsed JSON")
                    print(f"    📋 Available keys: {list(data.keys())}")
                elif not data.get('image_prompts'):
                    print(f"    ⚠️  'image_prompts' is empty in parsed JSON")
                else:
                    print(f"    ✅ Found {len(data.get('image_prompts', []))} image_prompts in parsed JSON")
            except json.JSONDecodeError as e:
                print(f"    ⚠️  JSON parse error: {e}")
                print(f"    📄 Response length: {len(content)} characters")
                print(f"    📄 First 500 chars: {content[:500]}")
                print(f"    📄 Last 500 chars: {content[-500:]}")
                # Check if response was truncated (common when hitting token limit)
                if len(content) > 7000:  # Close to 8192 token limit
                    print(f"    ⚠️  Response appears truncated (likely hit token limit)")
                    print(f"    💡 Consider increasing max_output_tokens or simplifying prompt")
                
                # Try to repair
                content = self._repair_json_string(content)
                try:
                    data = json.loads(content)
                    print(f"    ✅ Successfully repaired truncated JSON")
                    # Check image_prompts after repair
                    if 'image_prompts' not in data:
                        print(f"    ⚠️  'image_prompts' still missing after repair")
                    elif not data.get('image_prompts'):
                        print(f"    ⚠️  'image_prompts' still empty after repair")
                except json.JSONDecodeError as e2:
                    print(f"    ⚠️  Could not repair JSON after truncation: {e2}")
                    print(f"    💡 Using fallback script")
                    return self._create_fallback_viral_script(article, duration)
            
            # Create segments
            segments = []
            current_time = 0
            
            # NO HOOK - Start directly with what happened
            # What happened segment
            what_duration = 8
            segments.append({
                "text": data.get('what_happened', ''),
                "type": "what_happened",
                "duration": what_duration,
                "start_time": current_time,
                "story_index": 1
            })
            current_time += what_duration
            
            # ALTERNATING IMPACT AND FACTS SEGMENTS
            # Impact Statement 1
            impact1_duration = 3.5
            segments.append({
                "text": data.get('impact_statement_1', ''),
                "type": "impact",
                "duration": impact1_duration,
                "start_time": current_time,
                "story_index": 1
            })
            current_time += impact1_duration
            
            # Facts Segment 1
            facts1_duration = 5
            segments.append({
                "text": data.get('facts_1', ''),
                "type": "facts",
                "duration": facts1_duration,
                "start_time": current_time,
                "story_index": 1
            })
            current_time += facts1_duration
            
            # Impact Statement 2
            impact2_duration = 3.5
            segments.append({
                "text": data.get('impact_statement_2', ''),
                "type": "impact",
                "duration": impact2_duration,
                "start_time": current_time,
                "story_index": 1
            })
            current_time += impact2_duration
            
            # Facts Segment 2 (optional - use if provided, otherwise skip)
            facts2_text = data.get('facts_2', '').strip()
            if facts2_text:
                facts2_duration = 5
                segments.append({
                    "text": facts2_text,
                    "type": "facts",
                    "duration": facts2_duration,
                    "start_time": current_time,
                    "story_index": 1
                })
                current_time += facts2_duration
            
            # Impact Statement 3
            impact3_duration = 3.5
            segments.append({
                "text": data.get('impact_statement_3', ''),
                "type": "impact",
                "duration": impact3_duration,
                "start_time": current_time,
                "story_index": 1
            })
            current_time += impact3_duration
            
            # CTA segment
            cta_duration = 3
            segments.append({
                "text": data.get('cta', 'Like and subscribe for more viral news!'),
                "type": "cta",
                "duration": cta_duration,
                "start_time": current_time,
                "story_index": None
            })
            
            # Extract image_prompts with better error handling
            image_prompts = data.get('image_prompts', [])
            if not image_prompts or len(image_prompts) == 0:
                print(f"    ⚠️  No image_prompts in response, generating fallback prompts...")
                # Generate fallback prompts based on article
                article_title = article.get('title', 'news story')
                image_prompts = [
                    f"Dramatic visual of {article_title} showing the event",
                    f"People affected by {article_title} showing chaos",
                    f"Visual metaphor of consequences of {article_title}",
                    f"Emotional reaction scene to {article_title}",
                    f"Creative dramatic visual of {article_title}"
                ]
            else:
                print(f"    ✅ Got {len(image_prompts)} image prompts from response")
            
            return {
                "title": data.get('title', article_title[:60]),
                "script": data.get('full_script', ''),
                "segments": segments,
                "image_prompts": image_prompts
            }
            
        except Exception as e:
            print(f"    ⚠️  Error generating viral script: {e}")
            return self._create_fallback_viral_script(article, duration)
    
    def _create_fallback_viral_script(self, article: Dict, duration: int = 30) -> Dict:
        """Fallback viral script if generation fails"""
        title = article.get('title', 'Breaking News')[:60]
        # NO HOOK - Start directly with news
        what_happened = f"{article.get('title', '')}. {article.get('description', '')[:100]}"
        impact1 = "This story affects thousands of people!"
        facts1 = f"According to reports, {article.get('description', 'Major development')[:80]}"
        impact2 = "The impact is massive and the chaos is real!"
        facts2 = "Authorities are responding to the situation."
        impact3 = "This could change everything for millions!"
        cta = "Like and subscribe for more viral news that affects you!"
        
        segments = [
            {"text": what_happened, "type": "what_happened", "duration": 8, "start_time": 0, "story_index": 1},
            {"text": impact1, "type": "impact", "duration": 3.5, "start_time": 8, "story_index": 1},
            {"text": facts1, "type": "facts", "duration": 5, "start_time": 11.5, "story_index": 1},
            {"text": impact2, "type": "impact", "duration": 3.5, "start_time": 16.5, "story_index": 1},
            {"text": facts2, "type": "facts", "duration": 5, "start_time": 20, "story_index": 1},
            {"text": impact3, "type": "impact", "duration": 3.5, "start_time": 25, "story_index": 1},
            {"text": cta, "type": "cta", "duration": 3, "start_time": 28.5, "story_index": None}
        ]
        
        image_prompts = [
            f"Dramatic visual representation of {article.get('title', 'news story')}",
            f"People affected by {article.get('title', 'news')} showing chaos and disruption",
            f"Visual metaphor showing the impact of {article.get('title', 'news')}",
            f"People showing emotional reactions to {article.get('title', 'news')}",
            f"Exaggerated visual representation of consequences of {article.get('title', 'news')}"
        ]
        
        full_script = f"{what_happened} {impact1} {facts1} {impact2} {facts2} {impact3} {cta}"
        
        return {
            "title": title,
            "script": full_script,
            "segments": segments,
            "image_prompts": image_prompts
        }
    
    def generate_must_know_today(self, news_articles: List[Dict], target_age_group: str = "young", story_count: int = 4, content_style: str = "newsy") -> Dict:
        """
        Generate a "Must-Know Today" video script that explains WHY each story matters
        
        Args:
            news_articles: List of news articles
            target_age_group: "young" (18-30), "middle_age" (30-55), or "old" (55+)
            story_count: Number of stories to cover (default: 4, allows ~12-15 seconds per story)
            content_style: "newsy" (traditional news format) or "social" (social media native format)
        
        Returns: Dict with title, script, segments, and image_prompts
        """
        # Select must-know stories
        # If articles are already selected (from previous analyze_and_select call), skip deduplication
        # Check if articles likely came from Gemini (small count, already curated)
        skip_dedup = len(news_articles) <= 10
        selected_articles = self.analyze_and_select_must_know_news(
            news_articles, 
            select_count=story_count, 
            target_age_group=target_age_group,
            skip_deduplication=skip_dedup
        )
        
        print(f"  📰 Using {len(selected_articles)} must-know stories for {target_age_group} audience")
        
        # Generate title
        news_summary = "\n".join([
            f"- {article['title']}: {article.get('description', '')[:100]}"
            for article in selected_articles
        ])
        
        age_group_label = {
            "young": "Young Adults",
            "middle_age": "Middle-Aged Adults",
            "old": "Senior Citizens",
            "all_audiences": "All Audiences"
        }.get(target_age_group, "Young Adults")
        
        # Social media native format adjustments
        is_social_format = content_style.lower() == "social"
        
        if is_social_format:
            # Social media native title prompt
            title_prompt = f"""Generate a VIRAL, social media-style title for a YouTube Shorts video targeting {age_group_label}.

Today's must-know stories:
{news_summary}

Create a title that's SOCIAL MEDIA NATIVE:
- Is under 60 characters
- Uses social media language patterns
- Creates FOMO and curiosity
- Uses emojis if appropriate (but don't overdo it)
- Feels like a friend sharing news, not a news anchor

SOCIAL MEDIA TITLE PATTERNS:
- "POV: You wake up and {len(selected_articles)} things just changed your day"
- "{len(selected_articles)} things that happened today and honestly? We're not okay"
- "So {len(selected_articles)} things just happened and you need to know"
- "POV: You're scrolling and find out {len(selected_articles)} things changed everything"
- "{len(selected_articles)} updates that will actually affect your life (no cap)"

For YOUNG (18-30): Use Gen Z slang, casual tone, "POV", "honestly?", "no cap", "the vibes"
For MIDDLE_AGE (30-55): Use professional but relatable tone, "Here's what happened", "You need to know"
For OLD (55+): Use clear, straightforward tone, "Important updates", "What you need to know"
For ALL_AUDIENCES: Use NEUTRAL, professional language - NO slang, NO "vibes", NO "no cap", NO Gen Z terms. Use: "Here's what happened", "Today's news", "Important updates", "You need to know"

CRITICAL FOR ALL_AUDIENCES - AVOID:
- ❌ "the vibes are OFF" (Gen Z slang)
- ❌ "no cap" (Gen Z slang)
- ❌ "honestly?" (casual)
- ❌ "POV:" (Gen Z pattern)
- ❌ Any age-specific slang
- ✅ USE: Neutral, professional, clear language accessible to all age groups
- ✅ Examples: "{len(selected_articles)} things happened today you need to know", "Today's news: {len(selected_articles)} important updates", "Here's what happened: {len(selected_articles)} stories affecting everyone"

Return ONLY the title text, nothing else."""
        else:
            # Traditional newsy title prompt
            title_prompt = f"""Generate a COMPELLING, hook-driven title for a "Must-Know Today" news video targeting {age_group_label}.

Today's must-know stories:
{news_summary}

Create a title that MAKES USERS CARE:
- Is under 60 characters
- Creates URGENCY and FOMO (fear of missing out)
- Makes users feel they NEED to watch this
- Uses emotional hooks: "Affects You", "Changes Everything", "You Need This", "Don't Miss"
- Mentions the target audience if it adds value
- Uses power words: "Breaking", "Urgent", "Critical", "Important", "Must See"

TITLE PATTERNS THAT MAKE USERS CARE:
- "This Will Affect You - {len(selected_articles)} Stories You Can't Miss"
- "Breaking: {len(selected_articles)} Things {age_group_label} Must Know Today"
- "Don't Miss This - {len(selected_articles)} Stories That Change Everything"
- "Urgent: What {age_group_label} Need to Know Right Now"
- "{len(selected_articles)} Stories That Will Impact Your Life Today"

CRITICAL: The title should make users feel they'll MISS OUT if they don't watch. Create urgency and relevance.

Return ONLY the title text, nothing else."""

        try:
            title_response = self.llm_client.generate(title_prompt, {"temperature": 0.7, "num_predict": 100})
            title = title_response.get('response', '').strip().strip('"').strip("'") if isinstance(title_response, dict) else str(title_response).strip().strip('"').strip("'")
            if '```' in title:
                title = title.split('```')[0].strip()
            title = title[:60]
        except:
            title = f"Must-Know News Today - {age_group_label}"
        
        # Generate script segments for each story
        segments = []
        image_prompts = []
        script_parts = []
        
        # Opening hook - Social media vs traditional format
        if is_social_format:
            opening_prompt = f"""Generate a 3-4 second SOCIAL MEDIA NATIVE opening for a YouTube Shorts video.

Target audience: {target_age_group} ({age_group_label})
Number of stories: {len(selected_articles)}

Create a SOCIAL MEDIA opening that:
- Uses age-appropriate language for {age_group_label}
- Feels like a friend sharing news, not a news anchor
- Is 8-10 words (3-4 seconds at 2.5 words/second)
- Creates curiosity and engagement
- Uses appropriate social media patterns for the age group

EXAMPLES FOR YOUNG (18-30):
- "POV: You wake up and {len(selected_articles)} things just changed your day"
- "So {len(selected_articles)} things happened today and honestly? You need to know"
- "Okay so {len(selected_articles)} updates that will actually affect you"

EXAMPLES FOR MIDDLE_AGE (30-55) - USE PROFESSIONAL, CLEAR LANGUAGE:
- "Here's what happened today: {len(selected_articles)} things you need to know"
- "{len(selected_articles)} updates that will impact your daily life"
- "Today's important news: {len(selected_articles)} stories affecting you"
- "Here are {len(selected_articles)} things that happened today you should know"

CRITICAL FOR MIDDLE_AGE - AVOID:
- ❌ "went DOWN" (too casual/slang)
- ❌ "let's get into it" (too casual)
- ❌ "Okay so" (too casual)
- ❌ "honestly?" (too casual)
- ❌ Slang or Gen Z language
- ✅ USE: Professional, clear, informative language
- ✅ USE: "Here's what happened", "Here are", "Today's news", "Important updates"

EXAMPLES FOR ALL_AUDIENCES - USE NEUTRAL, PROFESSIONAL LANGUAGE (CONSUMABLE BY ALL):
- "Today's news: {len(selected_articles)} important updates you should know"
- "Here are {len(selected_articles)} important stories from today"
- "Today's important news: {len(selected_articles)} updates affecting everyone"
- "{len(selected_articles)} important stories you need to be aware of"

CRITICAL FOR ALL_AUDIENCES - AVOID:
- ❌ Any age-specific slang (no Gen Z slang, no casual phrases)
- ❌ "went DOWN", "let's get into it", "Okay so", "honestly?"
- ❌ Any casual or informal language
- ✅ USE: Neutral, professional, clear, respectful language
- ✅ USE: "Today's news", "Here are", "Important updates", "You should know"
- ✅ Language should be professional and accessible to all age groups

EXAMPLES FOR OLD (55+) - USE FORMAL, RESPECTFUL LANGUAGE:
- "Here are {len(selected_articles)} important updates from today"
- "Today's news: {len(selected_articles)} things you should know"
- "Important updates: {len(selected_articles)} stories from today"
- "{len(selected_articles)} important stories you need to be aware of"

EXAMPLES FOR ALL_AUDIENCES - USE NEUTRAL, PROFESSIONAL LANGUAGE (CONSUMABLE BY ALL):
- "Today's news: {len(selected_articles)} important updates you should know"
- "Here are {len(selected_articles)} important stories from today"
- "Today's important news: {len(selected_articles)} updates affecting everyone"
- "{len(selected_articles)} important stories you need to be aware of"

CRITICAL FOR ALL_AUDIENCES - AVOID:
- ❌ Any age-specific slang or casual language
- ❌ "went DOWN", "let's get into it", "Okay so", "honestly?"
- ❌ Gen Z slang, casual phrases, or informal language
- ✅ USE: Neutral, professional, clear, respectful language accessible to all
- ✅ USE: "Today's news", "Here are", "Important updates", "You should know"

CRITICAL FOR OLD - AVOID:
- ❌ Any casual language or slang
- ❌ "went DOWN", "let's get into it", "Okay so"
- ❌ Social media slang or abbreviations
- ✅ USE: Formal, respectful, clear language
- ✅ USE: "Here are", "Today's news", "Important updates", "You should know"

CRITICAL INSTRUCTIONS:
- Match the language style EXACTLY to the age group
- For ALL_AUDIENCES: Use neutral, professional language that works for everyone (NO age-specific slang)
- For MIDDLE_AGE: Use professional, clear language (NOT casual slang)
- For OLD: Use formal, respectful language (NOT casual at all)
- Return ONLY the opening text itself
- DO NOT include any explanations, options, or examples
- DO NOT say "Okay, here are a few options" or similar
- DO NOT include phrases like "keeping in mind" or "for [demographic]"
- DO NOT list multiple options - return ONLY ONE opening text
- Return the opening text directly, as if you're speaking it

Return ONLY the opening text, nothing else. No explanations, no options, no examples."""
        else:
            opening_prompt = f"""Generate a 3-4 second natural opening for a "Must-Know Today" news video.

Target audience: {target_age_group} ({age_group_label})
Number of stories: {len(selected_articles)}

Create an opening that:
- Uses age-appropriate language for {age_group_label}
- Starts with "Today's news" or "Here's today's news"
- Transitions to news that affects daily life
- Is 8-10 words (3-4 seconds at 2.5 words/second)
- Natural and conversational, not repetitive with "you/your"
- Creates interest without being pushy

EXAMPLES FOR YOUNG (18-30):
- "Today's news: {len(selected_articles)} things that will affect your day"
- "Here's today's news: {len(selected_articles)} updates you need to know"

EXAMPLES FOR MIDDLE_AGE (30-55) - USE PROFESSIONAL, CLEAR LANGUAGE:
- "Today's news: {len(selected_articles)} important updates you should know"
- "Here's today's news: {len(selected_articles)} stories affecting your daily life"
- "Today's important news: {len(selected_articles)} updates you need to be aware of"

CRITICAL FOR MIDDLE_AGE - AVOID:
- ❌ "went DOWN" (too casual/slang)
- ❌ "let's get into it" (too casual)
- ❌ "Okay so" (too casual)
- ❌ Any slang or Gen Z language
- ✅ USE: Professional, clear, informative language

EXAMPLES FOR ALL_AUDIENCES - USE NEUTRAL, PROFESSIONAL LANGUAGE (CONSUMABLE BY ALL):
- "Today's news: {len(selected_articles)} important updates you should know"
- "Here are {len(selected_articles)} important stories from today"
- "Today's important news: {len(selected_articles)} updates affecting everyone"

CRITICAL FOR ALL_AUDIENCES - AVOID:
- ❌ Any age-specific slang or casual language
- ❌ "went DOWN", "let's get into it", "Okay so"
- ✅ USE: Neutral, professional, clear, respectful language accessible to all

EXAMPLES FOR OLD (55+) - USE FORMAL, RESPECTFUL LANGUAGE:
- "Today's news: {len(selected_articles)} important updates you should know"
- "Here are {len(selected_articles)} important stories from today"
- "Today's important news: {len(selected_articles)} updates you need to be aware of"

CRITICAL FOR OLD - AVOID:
- ❌ Any casual language or slang
- ❌ "went DOWN", "let's get into it", "Okay so"
- ✅ USE: Formal, respectful, clear language

CRITICAL INSTRUCTIONS:
- Match the language style EXACTLY to the age group
- For MIDDLE_AGE: Use professional, clear language (NOT casual slang)
- For OLD: Use formal, respectful language (NOT casual at all)

EXAMPLES:
- "Today's news: {len(selected_articles)} stories that will affect daily life"
- "Here's today's news - {len(selected_articles)} stories impacting daily routines"
- "Today's news brings {len(selected_articles)} stories that matter for daily life"
- "Today's news: {len(selected_articles)} stories affecting work, finances, and health"

AVOID:
- Repetitive use of "you", "your", "you need", "you should"
- Pushy phrases like "You must see this", "Don't miss this"
- Overuse of urgency words in opening

CRITICAL INSTRUCTIONS:
- Return ONLY the opening text itself
- DO NOT include any explanations, options, or examples
- DO NOT say "Okay, here are a few options" or similar
- DO NOT include phrases like "keeping in mind" or "for [demographic]"
- DO NOT list multiple options - return ONLY ONE opening text
- Return the opening text directly, as if you're speaking it

Return ONLY the opening text, nothing else. No explanations, no options, no examples."""

        try:
            opening_response = self.llm_client.generate(opening_prompt, {"temperature": 0.8, "num_predict": 50})
            opening = opening_response.get('response', '').strip().strip('"').strip("'") if isinstance(opening_response, dict) else str(opening_response).strip().strip('"').strip("'")
            
            # CRITICAL: Remove any prompt instructions that leaked through
            import re
            
            # Remove markdown code blocks
            if '```' in opening:
                opening = opening.split('```')[0].strip()
            
            # Remove prompt-like patterns
            prompt_patterns = [
                r'^.*?(?:okay|here are|keeping in mind|option \d+|examples? for|for \w+).*?:',
            ]
            
            for pattern in prompt_patterns:
                opening = re.sub(pattern, '', opening, flags=re.IGNORECASE | re.MULTILINE)
            
            # If we see "Option 1:" or similar, extract only the actual opening text
            if re.search(r'option\s*\d+', opening, re.IGNORECASE):
                match = re.search(r'option\s*\d+[:\-]\s*(.+?)(?:\n|option|$)', opening, re.IGNORECASE | re.DOTALL)
                if match:
                    opening = match.group(1).strip()
            
            # Final validation: if opening contains prompt-like text, use fallback
            if any(phrase in opening.lower() for phrase in ['keeping in mind', 'here are a few', 'option 1', 'option 2', 'examples for']):
                raise ValueError("Opening contains prompt instructions, using fallback")
                
        except Exception as e:
            print(f"    ⚠️  Error extracting opening (using fallback): {e}")
            if is_social_format:
                if target_age_group == "young":
                    opening = f"POV: You wake up and {len(selected_articles)} things just changed your day."
                elif target_age_group == "middle_age":
                    opening = f"So {len(selected_articles)} things happened today and you need to know."
                else:
                    opening = f"Here are {len(selected_articles)} important updates from today."
            else:
                opening = f"Today's news: {len(selected_articles)} stories that will affect daily life."
        
        segments.append({
            "text": opening,
            "type": "opening",
            "duration": 4,
            "start_time": 0
        })
        script_parts.append(opening)
        # Don't add image prompt for opening - it uses fixed opening image
        # image_prompts.append("Professional news broadcast opening")  # Removed - uses fixed image
        
        current_time = 4
        
        # Track previous stories' headings for context (to vary urgency words)
        previous_headings = []
        
        # Generate detailed segments for each story
        for i, article in enumerate(selected_articles, 1):
            article_title = article.get('title', '')
            article_desc = article.get('description', '')
            
            # Calculate duration per story (remaining time / remaining stories)
            remaining_stories = len(selected_articles) - i + 1
            remaining_time = 60 - current_time - 3  # Reserve 3 seconds for closing
            target_duration = max(10, min(15, remaining_time // remaining_stories))  # 10-15 seconds per story
            
            # Build history context for varying urgency words
            history_context = ""
            if previous_headings:
                history_context = f"""
PREVIOUS STORIES CONTEXT (to avoid repetition):
{chr(10).join([f"- Story {j}: {heading[:60]}..." for j, heading in enumerate(previous_headings, 1)])}

URGENCY WORD VARIATION:
- Previous stories used: {', '.join([h.split(':')[0] if ':' in h else h.split()[0] for h in previous_headings[:3]])}
- VARY the urgency word - use DIFFERENT words like:
  * "Breaking:" (for first/major story)
  * "Alert:" (for urgent updates)
  * "This just happened:" (for recent developments)
  * "Update:" (for follow-ups)
  * "News:" (for important but less urgent)
  * "Latest:" (for recent news)
  * "Report:" (for informational)
- DO NOT repeat the same urgency word used in previous stories
- Choose urgency word based on story importance and position
"""
            
            # Build story prompt based on content style
            if is_social_format:
                # Social media native format prompt
                story_prompt = f"""You are creating a SOCIAL MEDIA NATIVE news segment for a YouTube Shorts video targeting {target_age_group} ({age_group_label}).

News Story {i} of {len(selected_articles)}:
Title: {article_title}
Description: {article_desc}
{history_context}

Create a SOCIAL MEDIA NATIVE script segment that feels like a friend sharing news, not a news anchor:

CRITICAL: This is SOCIAL MEDIA FORMAT - use casual, relatable, viral-worthy language!

SOCIAL MEDIA LANGUAGE PATTERNS BY AGE GROUP:

For YOUNG (18-30):
- Use Gen Z slang: "POV", "honestly?", "no cap", "the vibes", "we're not okay", "that's the tea"
- Casual phrases: "So", "Okay so", "Here's the thing", "Wait, what?", "This is wild"
- Examples: "POV: You're in Chennai and your entire day just changed", "So schools shut and honestly? We're not okay", "The vibes? Ruined. Here's why..."

For MIDDLE_AGE (30-55):
- Professional but relatable: "Here's what happened", "So this just dropped", "Quick update", "You need to know"
- Casual but not slang-heavy: "Okay so", "Here's the deal", "This is important", "Listen up"
- Examples: "So this just happened and you need to know", "Here's what's going on", "Quick update that affects your daily life"

For OLD (55+):
- Clear and straightforward: "Here's what happened", "Important update", "You should know", "This affects you"
- Respectful but engaging: "Here's an update", "This is important", "Let me tell you"
- Examples: "Here's what happened today", "Important update that affects daily life", "You should know about this"

1. HEADING/WHAT happened (3-4 seconds) - SOCIAL MEDIA HOOK
   Use SOCIAL MEDIA patterns, not traditional news language:
   
   ❌ BAD (Newsy): "Breaking: Chennai schools shut due to cyclone"
   ✅ GOOD (Social - Young): "POV: You're in Chennai and your entire day just changed. Schools shut."
   ✅ GOOD (Social - Middle): "So this just happened in Chennai. Schools shut, online classes start."
   ✅ GOOD (Social - Old): "Here's what happened in Chennai today. Schools closed due to weather."
   
   Social Media Hook Patterns:
   - YOUNG: "POV: [scenario]", "So [thing] just happened and honestly?", "Wait, [thing]?"
   - MIDDLE: "So [thing] just happened", "Here's what's going on", "Quick update: [thing]"
   - OLD: "Here's what happened", "Important update", "You should know about [thing]"
   
2. WHY THIS MATTERS (4-6 seconds) - SOCIAL MEDIA STYLE
   CRITICAL: VARY your transition phrases! Do NOT use the same phrase for every story.
   
   Story {i} transition options (rotate through these):
   - Story 1: "Here's why this matters..." or "This matters because..."
   - Story 2: "The impact on you is..." or "What this means for you..."
   - Story 3: "What does this mean for your wallet?" or "The real impact is..."
   - Story 4: "Here's the bottom line..." or "The key takeaway is..." or skip transition
   
   Explain impact using SOCIAL MEDIA language:
   
   For YOUNG:
   - "The vibes? [description]", "Honestly? This is [impact]", "No cap, this affects [group]"
   - "This is wild because...", "The tea is...", "Here's why this matters..."
   - VARY: Use different phrases for each story
   
   For MIDDLE_AGE:
   - "Here's why this matters...", "The impact is...", "This affects [group] because..."
   - "So basically...", "Here's the deal...", "This is important because..."
   - "What this means for your finances...", "The bottom line is...", "Here's the real impact..."
   - VARY: Use different phrases for each story - avoid repeating "Here's why this matters"
   
   For OLD:
   - "This is important because...", "Here's why you should care...", "This affects [group]"
   - "The impact is...", "This matters because...", "What this means for you..."
   - VARY: Use different phrases for each story
   
3. HOW it affects (3-5 seconds) - ACTIONABLE IN SOCIAL STYLE
   Give actionable advice in SOCIAL MEDIA tone:
   
   For YOUNG:
   - "If you're [group], here's what to do: [action]", "Pro tip: [action]", "Here's the move: [action]"
   - "If this affects you, consider [alternative]", "The play? [action]"
   
   For MIDDLE_AGE:
   - "If you're [group], here's what to do: [action]", "Here's what this means for you: [action]"
   - "If this affects you, consider [alternative]", "Here's how to adapt: [action]"
   
   For OLD:
   - "If you're [group], here's what to do: [action]", "Here's what this means: [action]"
   - "If this affects you, consider [alternative]", "Here's how to handle this: [action]"
   
   Also include:
   - Concrete examples: "Interest rates drop by 2%", "Rent could increase by X%"
   - Real impact: "Monthly savings of Rs. X", "Affects X% of income"
   - Make it actionable: "Here's what this means...", "The changes include..."

CRITICAL TIME CONSTRAINTS:
- Total duration: EXACTLY {target_duration} seconds
- Average speaking rate: 2.5 words per second
- Maximum words: {int(target_duration * 2.5)} words
- Count your words carefully!

SOCIAL MEDIA ENGAGEMENT TECHNIQUES:
- Use casual, friend-to-friend language (not news anchor style)
- Create shareable moments: "The vibes? Ruined", "Honestly? We're not okay", "This is wild"
- Use social media patterns: "POV", "So", "Okay so", "Here's the tea"
- Make it feel like a friend sharing news, not a formal announcement
- End with engagement hooks: "Drop a [emoji] if this affects you", "Comment if you're [affected]"

Format your response as JSON:
{{
  "heading": "[SOCIAL MEDIA HOOK - 3-4 seconds, {int(3.5 * 2.5)} words max - Use social media patterns like 'POV:', 'So [thing] just happened', 'Here's what happened' based on age group. Examples for YOUNG: 'POV: You're in Chennai and your entire day just changed. Schools shut.' Examples for MIDDLE: 'So this just happened in Chennai. Schools shut, online classes start.' Examples for OLD: 'Here's what happened in Chennai today. Schools closed.']",
  "why_this_matters": "[WHY THIS MATTERS - 4-6 seconds, {int(5 * 2.5)} words max - CRITICAL: VARY transition phrase! Story {i} should use different phrase than previous stories. For YOUNG: Rotate between 'The vibes? [description]', 'Honestly? This is...', 'The tea is...'. For MIDDLE: Rotate between 'Here's why this matters...', 'The impact on you is...', 'What this means for your finances...', 'The bottom line is...'. For OLD: Rotate between 'This is important because...', 'Here's why you should care...', 'What this means for you...'. Then explain impact.]",
  "how_it_affects": "[ACTIONABLE GUIDANCE - 3-5 seconds, {int(4 * 2.5)} words max - Social media style actionable advice. For YOUNG: 'Pro tip: If you're affected, check [action]' For MIDDLE: 'If you're [group], here's what to do: [action]' For OLD: 'If this affects you, here's what to do: [action]']",
  "full_text": "[Combined text for {target_duration} seconds, {int(target_duration * 2.5)} words max - Flow naturally in SOCIAL MEDIA style, casual and relatable, not formal news]",
  "image_prompt": "A detailed, visually striking image representing: [describe the news story visually - ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, purely visual elements. CRITICAL: If story mentions Indian locations (Delhi, Chennai, Mumbai, Parliament, etc.), specify 'Indian [location/building]' - e.g., 'Indian Parliament building (Sansad Bhavan)' NOT 'US Capitol Building'. For Indian cities, specify 'Indian city of [name]'. For government buildings, specify 'Indian [building type]' to ensure accuracy.]"
}}

Return ONLY the JSON, no markdown formatting."""
            else:
                # Traditional newsy format prompt
                story_prompt = f"""You are creating an ENGAGING news segment for a "Must-Know Today" video targeting {target_age_group} ({age_group_label}).

News Story {i} of {len(selected_articles)}:
Title: {article_title}
Description: {article_desc}
{history_context}
Create a script segment that KEEPS VIEWERS HOOKED and MAKES THEM CARE:

1. HEADING/WHAT happened (3-4 seconds) - SHARP HOOK FIRST, THEN REVEAL
   CRITICAL: Use CURIOSITY-DRIVEN hooks that create immediate personal connection BEFORE revealing the news.
   
   ❌ BAD (Direct, no curiosity): "Alert. Chennai schools shut due to cyclone"
   ✅ GOOD (Curiosity hook first): "If you're in Chennai, your entire day just changed. Schools shut, online classes start."
   
   Hook Techniques:
   - Start with personal impact statement: "If you're in [location/group], your [day/week/month] just changed"
   - Create curiosity: "Something just happened that affects everyone in [location/industry]"
   - Use emotional triggers: "Your plans just got disrupted", "This changes everything for [group]"
   - THEN reveal the news: "Schools shut", "Policy changed", "Rates increased"
   
   Examples:
   - "If you're planning a US tech job, your path just got harder. H-1B visa changes announced."
   - "Chennai residents, your entire day just changed. Schools shut, online classes start."
   - "Anyone with a home loan, this affects your monthly payment. RBI rate cut announced."
   
   - VARY urgency words - use DIFFERENT words from previous stories
   - Options: "Breaking:", "Alert:", "This just happened:", "Update:", "News:", "Latest:", "Report:"
   - Choose based on story importance: Major = "Breaking", Urgent = "Alert", Recent = "This just happened", Info = "Update/News"
   - Avoid repetitive "you/your" - be natural and informative
   
2. WHY THIS MATTERS (4-6 seconds) - CRITICAL SECTION - Explain the impact
   CRITICAL: VARY your transition phrases! Do NOT use "Here's why this matters" for every story.
   
   Story 1: Use "Here's why this matters..." or "This matters because..."
   Story 2: Use "The impact on you is..." or "What this means for you..."
   Story 3: Use "What does this mean for your wallet?" or "The real impact is..."
   Story 4: Use "Here's the bottom line..." or "The key takeaway is..." or just jump straight to explanation
   
   - Explain WHY this matters to {target_age_group} SPECIFICALLY
   - Connect to daily life, work, finances, health, or future
   - VARY transition phrases - use different ones for each story
   - Make it relevant: "This affects education loans", "This impacts job market", "This changes retirement planning"
   - Use "this affects" or "this impacts" instead of repetitive "you/your"
   
   VARIATION EXAMPLES:
   - "The impact on your finances is..."
   - "What this means for your daily life..."
   - "Here's how this affects you..."
   - "The bottom line is..."
   - "What you need to understand..."
   - "The real-world impact..."
   - "This translates to..."
   
3. HOW it affects daily life/work/finances/health (3-5 seconds) - ACTIONABLE GUIDANCE
   CRITICAL: Add ACTIONABLE GUIDANCE that tells viewers what to DO, not just what happened.
   
   ❌ BAD (Just facts): "H-1B visa rules changed. Fewer visas available."
   ✅ GOOD (Actionable): "H-1B visa rules changed. If you want a US tech job, start building a Plan B in Canada, Europe, or remote roles."
   
   Actionable Guidance Techniques:
   - For policy/news: "If you're [affected group], here's what to do: [action]"
   - For opportunities: "If you want [goal], start [actionable step]"
   - For problems: "If this affects you, consider [alternative/action]"
   - For changes: "Here's how to adapt: [specific action]"
   
   Examples:
   - "If you want a US tech job, start building a Plan B in Canada, Europe, or remote roles"
   - "If you're affected, check eligibility for [alternative program/benefit]"
   - "If this impacts your plans, consider [alternative option]"
   - "Here's what to do: [specific actionable step]"
   
   Also include:
   - Give concrete examples: "Interest rates drop by 2%", "Rent could increase by X%"
   - Show real impact: "Monthly savings of Rs. X", "Affects X% of income"
   - Make it actionable: "Here's what this means...", "The changes include..."

CRITICAL TIME CONSTRAINTS:
- Total duration: EXACTLY {target_duration} seconds
- Average speaking rate: 2.5 words per second
- Maximum words: {int(target_duration * 2.5)} words
- Count your words carefully!

ENGAGEMENT TECHNIQUES TO USE:
- SHARP HOOKS FIRST: Start with curiosity-driven personal impact BEFORE revealing news
  * "If you're in [location/group], your [day/week] just changed" → THEN reveal what happened
  * Creates immediate connection and curiosity, increases retention
- ACTIONABLE GUIDANCE: Always include what viewers should DO, not just what happened
  * "If you want [goal], start [actionable step]"
  * "If this affects you, consider [alternative/action]"
  * Makes distant policy feel like personal guidance
- Use personal language: "This affects YOU because...", "For {age_group_label}, this means...", "You should know..."
- Create curiosity: "Here's why this matters...", "The impact is huge...", "This changes everything..."
- Be specific: Use numbers, dates, concrete examples
- End with a hook: If not last story, tease next one: "But wait, there's more..."

TONE CALIBRATION FOR {target_age_group}:
- For YOUNG (18-30): USE casual, Gen Z-appropriate language
  * ENCOURAGE casual/juvenile words: "spicy", "wild", "crazy", "insane", "fire", "slaps", "vibes", "tea", "no cap"
  * This demographic expects and appreciates casual, relatable language
  * Example: "Parliament got spicy" or "This is wild" or "That's fire" - all acceptable for young audience
  * Still maintain professionalism but with Gen Z slang and casual tone
- For MIDDLE_AGE (30-55): Use professional, respectful language
  * AVOID juvenile/casual words: "spicy", "wild", "crazy", "insane", "fire", "slaps"
  * USE professional alternatives: "Heated", "Intense", "Critical", "Significant", "Important", "Major"
  * Example: Instead of "Parliament got spicy", use "Parliament debate intensified" or "Critical Parliament discussion"
- For OLD (55+): Use clear, respectful, traditional language
  * AVOID all casual/juvenile words
  * USE formal, respectful language: "Significant", "Important", "Critical", "Notable", "Substantial"

WHY THIS MATTERS SECTION IS THE MOST CRITICAL:
- This section determines if users will keep watching
- CRITICAL: VARY your transition phrases! Do NOT repeat "Here's why this matters" for every story
- Story {i} transition options (rotate through these):
  * Story 1: "Here's why this matters..." or "This matters because..."
  * Story 2: "The impact on you is..." or "What this means for you..."
  * Story 3: "What does this mean for your wallet?" or "The real impact is..."
  * Story 4: "Here's the bottom line..." or "The key takeaway is..." or skip transition, go straight to explanation
- Explain WHY this matters to {target_age_group} SPECIFICALLY - be very specific
- Connect to their REAL concerns: money, job security, health, family, future plans
- Use emotional triggers: fear (missing out, losing money), hope (opportunities, savings), urgency (act now)
- Make it relevant: "This affects education loans", "This impacts job market", "This changes retirement planning"
- Use concrete impact: "This means savings of Rs. X", "This affects X% of income", "Interest rates change by X%"
- Address their pain points: "For those planning [relevant action], this changes everything"
- VARY transition phrases - use different ones for each story to avoid repetition
- Make them understand the consequences: "Not knowing this could mean...", "This affects decisions about..."
- AVOID repetitive "you/your" - use "this affects", "this impacts", "this means" instead

Format your response as JSON:
{{
  "heading": "[SHARP HOOK FIRST - 3-4 seconds, {int(3.5 * 2.5)} words max - Start with curiosity-driven personal impact like 'If you're in [location/group], your [day/week] just changed' THEN reveal the news. VARY urgency word from previous stories. Examples: 'If you're in Chennai, your entire day just changed. Schools shut, online classes start.' or 'If you want a US tech job, your path just got harder. H-1B visa changes announced.']",
  "why_this_matters": "[WHY THIS MATTERS - 4-6 seconds, {int(5 * 2.5)} words max - CRITICAL: VARY transition phrase! Story {i} should use different phrase than previous stories. Options: 'Here's why this matters...', 'The impact on you is...', 'What this means for you...', 'The real impact is...', 'Here's the bottom line...', 'The key takeaway is...'. Then explain why this matters to {target_age_group}, use 'this affects', 'this impacts', 'this means' - avoid repetitive 'you/your']",
  "how_it_affects": "[ACTIONABLE GUIDANCE - 3-5 seconds, {int(4 * 2.5)} words max - Include actionable guidance telling viewers what to DO. Examples: 'If you want a US tech job, start building a Plan B in Canada, Europe, or remote roles' or 'If this affects you, check eligibility for [alternative]'. Also include specific numbers/examples, use 'this means', 'this affects', 'the impact is']",
  "full_text": "[Combined text for {target_duration} seconds, {int(target_duration * 2.5)} words max - Flow naturally from heading to why to how, avoid repetitive 'you/your']",
  "image_prompt": "A detailed, visually striking image representing: [describe the news story visually - ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, purely visual elements. CRITICAL: If story mentions Indian locations (Delhi, Chennai, Mumbai, Parliament, etc.), specify 'Indian [location/building]' - e.g., 'Indian Parliament building (Sansad Bhavan)' NOT 'US Capitol Building'. For Indian cities, specify 'Indian city of [name]'. For government buildings, specify 'Indian [building type]' to ensure accuracy.]"
}}

Return ONLY the JSON, no markdown formatting.

CRITICAL: You MUST return valid JSON. Do not return empty responses. The JSON must include all required fields: heading, why_this_matters, how_it_affects, full_text, image_prompt."""

            import json
            story_data = {}
            max_retries = 2
            retry_count = 0
            
            while retry_count <= max_retries:
                try:
                    story_response = self.llm_client.generate(story_prompt, {"temperature": 0.7, "num_predict": 300})
                    story_content = story_response.get('response', '').strip() if isinstance(story_response, dict) else str(story_response).strip()
                    
                    # Check if response is empty
                    if not story_content or len(story_content.strip()) < 10:
                        if retry_count < max_retries:
                            print(f"    ⚠️  Empty response for story {i}, retrying ({retry_count + 1}/{max_retries})...")
                            retry_count += 1
                            continue
                        else:
                            print(f"    ⚠️  Empty response for story {i} after {max_retries} retries, using fallback")
                            story_data = {}
                            break
                    
                    # Extract JSON
                    if '```json' in story_content:
                        story_content = story_content.split('```json')[1].split('```')[0]
                    elif '```' in story_content:
                        story_content = story_content.split('```')[1].split('```')[0]
                    
                    # Try to repair JSON before parsing
                    story_content_repaired = self._repair_json_string(story_content)
                    story_data = json.loads(story_content_repaired.strip())
                    print(f"    ✅ Successfully parsed JSON for story {i}")
                    break  # Success, exit retry loop
                    
                except json.JSONDecodeError as e:
                    if retry_count < max_retries:
                        print(f"    ⚠️  JSON parsing error for story {i}: {e}")
                        print(f"    📄 Response preview: {story_content[:300] if 'story_content' in locals() else 'Empty'}...")
                        print(f"    🔄 Retrying ({retry_count + 1}/{max_retries})...")
                        retry_count += 1
                        continue
                    else:
                        print(f"    ⚠️  JSON parsing error for story {i} after {max_retries} retries: {e}")
                        print(f"    📄 Response preview: {story_content[:300] if 'story_content' in locals() else 'Empty'}...")
                        
                        # Try to extract JSON object from response
                        if 'story_content' in locals() and '{' in story_content and '}' in story_content:
                            start_idx = story_content.find('{')
                            end_idx = story_content.rfind('}') + 1
                            if start_idx < end_idx:
                                try:
                                    json_str = story_content[start_idx:end_idx]
                                    json_str = self._repair_json_string(json_str)
                                    story_data = json.loads(json_str.strip())
                                    print(f"    ✅ Successfully extracted and parsed JSON")
                                    break  # Success, exit retry loop
                                except json.JSONDecodeError as e2:
                                    # Fallback: create story data from article
                                    print(f"    🔄 Using fallback story data (JSON extraction failed: {e2})")
                                    story_data = {}
                                    break
                        else:
                            # No JSON found, use fallback
                            print(f"    🔄 No JSON found in response, using fallback")
                            story_data = {}
                            break
                except Exception as e:
                    if retry_count < max_retries:
                        print(f"    ⚠️  Error generating story {i}: {e}, retrying...")
                        retry_count += 1
                        continue
                    else:
                        print(f"    ⚠️  Error generating story {i} after {max_retries} retries: {e}")
                        story_data = {}
                        break
                
            # Use new field names, with fallback to old names for compatibility
            # If story_data is empty, use article info as fallback
            if not story_data:
                # Vary urgency word even in fallback based on story position
                urgency_words = ["Breaking", "Alert", "Update", "News", "Latest", "Report"]
                urgency_word = urgency_words[(i - 1) % len(urgency_words)]
                heading = f"{urgency_word}: {article_title}"
                why_matters = f"This matters to {target_age_group}."
                how_affects = f"This affects daily life."
                full_text = f"{heading}. {why_matters} {how_affects}"
                image_prompt = f"Visual representation of {article_title}"
            else:
                heading = story_data.get('heading') or story_data.get('what_happened', f"Breaking: {article_title}")
                why_matters = story_data.get('why_this_matters') or story_data.get('why_you_need_to_care') or story_data.get('why_it_matters', f"This matters to {target_age_group}.")
                how_affects = story_data.get('how_it_affects', f"This affects daily life.")
                full_text = story_data.get('full_text', f"{heading}. {why_matters} {how_affects}")
                image_prompt = story_data.get('image_prompt', f"Visual representation of {article_title}")
            
            # Track heading for history context (to vary urgency words in next stories)
            previous_headings.append(heading)
            
            segments.append({
                "text": full_text,
                "type": "story",
                "story_index": i,
                "duration": target_duration,
                "start_time": current_time
            })
            script_parts.append(full_text)
            image_prompts.append(image_prompt)
            
            current_time += target_duration
        
        # Closing - Social media vs traditional format
        if is_social_format:
            closing_prompt = f"""Generate a 3-4 second SOCIAL MEDIA NATIVE closing for a YouTube Shorts video.

Target audience: {target_age_group} ({age_group_label})
Stories covered: {len(selected_articles)}

Create a SOCIAL MEDIA closing that:
- Uses casual, engaging language
- Includes a call-to-action in social media style
- Encourages engagement (comments, shares, subscribe)
- Is 8-10 words (3-4 seconds)
- Feels like a friend signing off, not a news anchor

EXAMPLES FOR YOUNG (18-30):
- "That's the tea for today. Drop a 🔥 if this affects you!"
- "That's what happened today. Comment which story hit different!"
- "Stay tuned for more updates. Hit follow for daily news!"

EXAMPLES FOR MIDDLE_AGE (30-55):
- "That's what you need to know today. Follow for more updates!"
- "Stay informed - these stories matter. Subscribe for daily news!"
- "That's today's update. Comment which story affects you most!"

EXAMPLES FOR OLD (55+):
- "That's what you need to know today. Stay informed, subscribe for updates!"
- "Here are today's important updates. Follow for more news!"
- "That's today's news. Subscribe to stay informed!"

CRITICAL INSTRUCTIONS:
- Return ONLY the closing text itself
- DO NOT include any explanations, options, or examples
- DO NOT say "Okay, here are a few options" or similar
- DO NOT include phrases like "keeping in mind" or "for [demographic]"
- DO NOT list multiple options - return ONLY ONE closing text
- Return the closing text directly, as if you're speaking it

Example of CORRECT response:
"That's what you need to know today. Follow for more updates!"

Example of WRONG response (DO NOT DO THIS):
"Okay, here are a few options, keeping in mind the middle-age demographic:
Option 1: That's what you need to know today. Follow for more updates!
Option 2: Stay informed - these stories matter. Subscribe for daily news!"

Return ONLY the closing text, nothing else. No explanations, no options, no examples."""
        else:
            closing_prompt = f"""Generate a 3-4 second engaging closing for a "Must-Know Today" news video.

Target audience: {target_age_group} ({age_group_label})
Stories covered: {len(selected_articles)}

Create a closing that:
- Summarizes briefly (1-2 seconds)
- Includes a STRONG call-to-action (1-2 seconds)
- Encourages engagement (comments, shares, subscribe)
- Is 8-10 words (3-4 seconds)
- Creates urgency for future videos

EXAMPLES:
- "Stay informed - these stories affect you. Follow for daily updates!"
- "That's what you need to know today. Comment which story affects you most!"
- "Stay tuned for more must-know news tomorrow. Hit subscribe!"

CRITICAL INSTRUCTIONS:
- Return ONLY the closing text itself
- DO NOT include any explanations, options, or examples
- DO NOT say "Okay, here are a few options" or similar
- DO NOT include phrases like "keeping in mind" or "for [demographic]"
- DO NOT list multiple options - return ONLY ONE closing text
- Return the closing text directly, as if you're speaking it

Example of CORRECT response:
"That's what you need to know today. Follow for more updates!"

Example of WRONG response (DO NOT DO THIS):
"Okay, here are a few options, keeping in mind the middle-age demographic:
Option 1: That's what you need to know today. Follow for more updates!
Option 2: Stay informed - these stories matter. Subscribe for daily news!"

Return ONLY the closing text, nothing else. No explanations, no options, no examples."""

        try:
            closing_response = self.llm_client.generate(closing_prompt, {"temperature": 0.8, "num_predict": 50})
            closing = closing_response.get('response', '').strip().strip('"').strip("'") if isinstance(closing_response, dict) else str(closing_response).strip().strip('"').strip("'")
            
            # CRITICAL: Remove any prompt instructions that leaked through
            # Look for common prompt patterns and remove everything before/after
            import re
            
            # Remove markdown code blocks
            if '```' in closing:
                closing = closing.split('```')[0].strip()
            
            # Remove any text that looks like prompt instructions
            # Patterns to remove:
            # - "Okay, here are a few options"
            # - "keeping in mind"
            # - "Here are some options"
            # - "Option 1:", "Option 2:"
            # - Anything before the first quote or example
            
            # Remove prompt-like patterns
            prompt_patterns = [
                r'^.*?(?:okay|here are|keeping in mind|option \d+|examples? for|for \w+).*?:',
                r'^.*?(?:okay|here are|keeping in mind|option \d+|examples? for|for \w+).*?\n',
            ]
            
            for pattern in prompt_patterns:
                closing = re.sub(pattern, '', closing, flags=re.IGNORECASE | re.MULTILINE)
            
            # If we see "Option 1:" or similar, extract only the actual closing text
            if re.search(r'option\s*\d+', closing, re.IGNORECASE):
                # Extract text after "Option 1:" or similar
                match = re.search(r'option\s*\d+[:\-]\s*(.+?)(?:\n|option|$)', closing, re.IGNORECASE | re.DOTALL)
                if match:
                    closing = match.group(1).strip()
            
            # If we see multiple options, take the first one that looks like actual closing text
            if 'option' in closing.lower() or 'here are' in closing.lower():
                # Try to extract the first quoted text or first sentence after "Option 1:"
                lines = closing.split('\n')
                for line in lines:
                    line = line.strip()
                    # Skip lines that look like prompts
                    if any(word in line.lower() for word in ['option', 'example', 'for young', 'for middle', 'for old', 'keeping in mind']):
                        continue
                    # Take the first line that looks like actual closing text
                    if line and len(line) > 10 and not line.lower().startswith(('okay', 'here are', 'keeping')):
                        closing = line
                        break
            
            # Final cleanup: remove any remaining prompt-like text
            # Remove anything before the first actual closing text (look for quotes or actual content)
            if '"' in closing:
                # Extract text within quotes
                match = re.search(r'"([^"]+)"', closing)
                if match:
                    closing = match.group(1)
            elif closing.lower().startswith(('okay', 'here are', 'keeping in mind', 'option')):
                # If it still starts with prompt words, try to extract the actual closing
                # Look for the first sentence that doesn't start with prompt words
                sentences = re.split(r'[.!?]\s+', closing)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if sentence and not sentence.lower().startswith(('okay', 'here are', 'keeping', 'option', 'example')):
                        closing = sentence
                        break
            
            # Final validation: if closing still contains prompt-like text, use fallback
            prompt_indicators = [
                'keeping in mind', 'here are a few', 'option 1', 'option 2', 'examples for',
                'okay, here are', 'here are some', 'for the middle-age', 'for young',
                'for old', 'demographic', 'target audience'
            ]
            if any(phrase in closing.lower() for phrase in prompt_indicators):
                # Try one more aggressive extraction
                # Look for text after "Option 1:" or similar patterns
                option_match = re.search(r'(?:option\s*\d+|here are|okay)[:\-]\s*(.+?)(?:\.|$|\n)', closing, re.IGNORECASE | re.DOTALL)
                if option_match:
                    extracted = option_match.group(1).strip()
                    # Validate extracted text doesn't contain prompt indicators
                    if extracted and not any(phrase in extracted.lower() for phrase in prompt_indicators):
                        closing = extracted
                    else:
                        raise ValueError("Closing contains prompt instructions, using fallback")
                else:
                    raise ValueError("Closing contains prompt instructions, using fallback")
            
            # Ensure closing is reasonable length (not too long, not empty)
            if not closing or len(closing) < 5:
                raise ValueError("Closing too short, using fallback")
            if len(closing) > 200:
                # Too long, might contain instructions - take first sentence
                closing = closing.split('.')[0] + '.'
                
        except Exception as e:
            print(f"    ⚠️  Error extracting closing (using fallback): {e}")
            if is_social_format:
                if target_age_group == "young":
                    closing = "That's the tea for today. Drop a 🔥 if this affects you!"
                elif target_age_group == "middle_age":
                    closing = "That's what you need to know today. Follow for more updates!"
                else:
                    closing = "That's today's news. Subscribe to stay informed!"
            else:
                closing = "Stay informed - these stories affect your daily life. Follow for more updates!"
        
        segments.append({
            "text": closing,
            "type": "closing",
            "duration": 3,
            "start_time": current_time
        })
        script_parts.append(closing)
        image_prompts.append("Professional news broadcast closing scene")
        
        full_script = " ".join(script_parts)
        
        return {
            "title": title,
            "script": full_script,
            "segments": segments,
            "image_prompts": image_prompts
        }

