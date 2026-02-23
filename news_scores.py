#!/usr/bin/env python3
"""
Script to fetch current news and show scores for different news types/categories
"""

import ollama
from typing import Dict, List
import json
from news_fetcher import NewsFetcher
from content_generator import ContentGenerator
from config import NEWS_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL
from datetime import datetime

class NewsScorer:
    """Analyzes and scores news articles by category"""
    
    def __init__(self):
        self.model = OLLAMA_MODEL
        self.client = ollama.Client(host=OLLAMA_BASE_URL)
        self._ensure_model_available()
    
    def _ensure_model_available(self):
        """Check if model is available, try alternatives if not"""
        try:
            models = self.client.list()
            available_models = [m['name'] for m in models.get('models', [])]
            
            if self.model not in available_models:
                alternatives = ['llama3.1', 'llama3', 'llama2', 'mistral', 'phi3', 'gemma']
                for alt in alternatives:
                    for model_name in available_models:
                        if alt.lower() in model_name.lower():
                            print(f"⚠️  Model '{self.model}' not found. Using '{model_name}' instead.")
                            self.model = model_name
                            return
                
                print(f"⚠️  Model '{self.model}' not found.")
                print(f"Available models: {', '.join(available_models) if available_models else 'None'}")
        except Exception as e:
            print(f"⚠️  Could not check Ollama models: {e}")
    
    def categorize_news(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize news articles by type"""
        if not articles:
            return {}
        
        # Prepare news list for categorization
        news_list = "\n".join([
            f"{i+1}. {article['title']}\n   {article.get('description', '')[:150]}"
            for i, article in enumerate(articles)
        ])
        
        prompt = f"""You are analyzing news articles and categorizing them by type.

Here are {len(articles)} news articles:

{news_list}

Categorize each article into ONE of these categories:
- Politics: Government, elections, political parties, policies, politicians
- Economy: Business, finance, stock market, economy, trade, economic policies
- Technology: Tech companies, startups, innovation, digital, AI, software
- Sports: Football, basketball, Olympics, sports events, athletes, matches
- Health: Healthcare, medical, diseases, public health, hospitals
- Education: Schools, universities, education policies, exams
- Entertainment: Movies, celebrities, entertainment industry
- Crime: Legal issues, court cases, crime, law enforcement
- International: Foreign relations, global events, diplomacy
- Environment: Climate, pollution, natural disasters, environmental policies
- Science: Scientific research, discoveries, space, research
- Other: Anything that doesn't fit the above categories

Return your response as JSON with article numbers (1-indexed) mapped to categories:
{{
  "1": "Politics",
  "2": "Economy",
  "3": "Technology",
  ...
}}

Return ONLY valid JSON, no explanation or markdown formatting."""

        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": 0.3,
                    "num_predict": 500,
                }
            )
            
            content = response.get('response', '').strip()
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            categorization = json.loads(content.strip())
            
            # Group articles by category
            categorized = {}
            for idx_str, category in categorization.items():
                try:
                    idx = int(idx_str) - 1  # Convert to 0-indexed
                    if 0 <= idx < len(articles):
                        if category not in categorized:
                            categorized[category] = []
                        categorized[category].append(articles[idx])
                except (ValueError, KeyError):
                    continue
            
            return categorized
            
        except Exception as e:
            print(f"⚠️  Error categorizing news: {e}")
            # Fallback: categorize based on keywords
            return self._fallback_categorize(articles)
    
    def _fallback_categorize(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """Fallback categorization using keyword matching"""
        categories = {
            'Politics': ['election', 'government', 'minister', 'parliament', 'political', 'president', 'prime minister', 'senate', 'congress'],
            'Economy': ['economy', 'stock', 'gdp', 'inflation', 'business', 'trade', 'market', 'finance', 'bank', 'currency'],
            'Technology': ['tech', 'startup', 'digital', 'ai', 'software', 'app', 'internet', 'cyber', 'computer', 'innovation'],
            'Sports': ['football', 'basketball', 'sports', 'match', 'player', 'team', 'olympics', 'championship', 'game'],
            'Health': ['health', 'hospital', 'medical', 'disease', 'covid', 'vaccine', 'doctor', 'healthcare', 'treatment'],
            'Education': ['education', 'school', 'university', 'student', 'exam', 'college', 'academic'],
            'Entertainment': ['movie', 'actor', 'celebrity', 'entertainment', 'film', 'hollywood', 'music', 'tv'],
            'Crime': ['crime', 'court', 'police', 'arrest', 'murder', 'legal', 'trial', 'judge'],
            'International': ['china', 'usa', 'russia', 'uk', 'foreign', 'diplomatic', 'global', 'international', 'war'],
            'Environment': ['climate', 'pollution', 'environment', 'disaster', 'flood', 'drought', 'weather', 'global warming'],
            'Science': ['science', 'research', 'space', 'nasa', 'discovery', 'study', 'scientific', 'experiment'],
        }
        
        categorized = {}
        for article in articles:
            title = article.get('title', '').lower()
            description = article.get('description', '').lower()
            content = f"{title} {description}"
            
            matched = False
            for category, keywords in categories.items():
                if any(keyword in content for keyword in keywords):
                    if category not in categorized:
                        categorized[category] = []
                    categorized[category].append(article)
                    matched = True
                    break
            
            if not matched:
                if 'Other' not in categorized:
                    categorized['Other'] = []
                categorized['Other'].append(article)
        
        return categorized
    
    def calculate_category_scores(self, categorized_articles: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """Calculate scores for each category"""
        category_scores = {}
        
        for category, articles in categorized_articles.items():
            if not articles:
                continue
            
            # Calculate scores based on global news scoring criteria
            total_score = 0
            scores = {
                'article_count': len(articles),
                'relevance': 0,
                'impact': 0,
                'recency': 0,
                'engagement': 0,
                'uniqueness': 0,
                'total_score': 0
            }
            
            # Relevance keywords (global importance indicators)
            relevance_keywords = [
                'global', 'world', 'international', 'major', 'significant', 'important',
                'breaking', 'crisis', 'emergency', 'historic', 'unprecedented'
            ]
            
            # Impact keywords (high impact indicators)
            impact_keywords = [
                'breaking', 'major', 'historic', 'significant', 'important', 'crisis',
                'emergency', 'announcement', 'decision', 'policy', 'election', 'war',
                'conflict', 'disaster', 'pandemic'
            ]
            
            # Engagement keywords (viral potential)
            engagement_keywords = [
                'shocking', 'controversial', 'scandal', 'breaking', 'exclusive',
                'trending', 'viral', 'outrage', 'protest', 'surprising'
            ]
            
            for article in articles:
                title = article.get('title', '').lower()
                description = article.get('description', '').lower()
                content = f"{title} {description}"
                
                # Relevance Score (10% weight) - how globally relevant/important
                relevance_score = 1.0 if any(kw in content for kw in relevance_keywords) else 0.6
                # Boost score if it's breaking news or major event
                if any(kw in content for kw in ['breaking', 'major', 'historic', 'crisis']):
                    relevance_score = 1.0
                scores['relevance'] += relevance_score
                
                # Impact Score (20% weight)
                impact_score = 1.0 if any(kw in content for kw in impact_keywords) else 0.6
                scores['impact'] += impact_score
                
                # Recency Score (10% weight) - assume all are recent if fetched today
                scores['recency'] += 0.8
                
                # Engagement Potential (50% weight)
                engagement_score = 1.0 if any(kw in content for kw in engagement_keywords) else 0.5
                scores['engagement'] += engagement_score
                
                # Uniqueness (10% weight) - assume unique if in different categories
                scores['uniqueness'] += 0.7
            
            # Average scores
            if len(articles) > 0:
                scores['relevance'] = round(scores['relevance'] / len(articles), 2)
                scores['impact'] = round(scores['impact'] / len(articles), 2)
                scores['recency'] = round(scores['recency'] / len(articles), 2)
                scores['engagement'] = round(scores['engagement'] / len(articles), 2)
                scores['uniqueness'] = round(scores['uniqueness'] / len(articles), 2)
                
                # Calculate weighted total score
                total_score = (
                    scores['engagement'] * 0.50 +
                    scores['relevance'] * 0.10 +
                    scores['recency'] * 0.10 +
                    scores['impact'] * 0.20 +
                    scores['uniqueness'] * 0.10
                )
                scores['total_score'] = round(total_score, 2)
            
            category_scores[category] = scores
        
        return category_scores
    
    def get_detailed_scores(self, articles: List[Dict]) -> Dict:
        """Get detailed scores for all news types"""
        print("\n📊 Categorizing news articles...")
        categorized = self.categorize_news(articles)
        
        print("\n📈 Calculating scores for each category...")
        scores = self.calculate_category_scores(categorized)
        
        return {
            'categorized_articles': categorized,
            'category_scores': scores,
            'total_articles': len(articles)
        }


def main():
    """Main function to fetch news and display scores"""
    print("=" * 70)
    print("📰 News Category Scores Analysis")
    print("=" * 70)
    print(f"\n⏰ Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Fetch news
    print("\n[1/3] Fetching today's news...")
    print("  🌍 Fetching global news from international sources...")
    # Use "us" or any non-"in" value to get global/international news
    fetcher = NewsFetcher(news_api_key=NEWS_API_KEY, country="us")  # Global news
    
    articles = fetcher.fetch_today_news(limit=30)
    print(f"✅ Found {len(articles)} articles")
    
    if not articles:
        print("❌ No articles found. Exiting.")
        return
    
    # Step 2: Categorize and score
    print("\n[2/3] Analyzing and categorizing news...")
    scorer = NewsScorer()
    results = scorer.get_detailed_scores(articles)
    
    categorized = results['categorized_articles']
    scores = results['category_scores']
    
    # Step 3: Display results
    print("\n[3/3] Displaying results...")
    print("\n" + "=" * 70)
    print("📊 NEWS CATEGORY SCORES")
    print("=" * 70)
    
    # Sort categories by total score
    sorted_categories = sorted(
        scores.items(),
        key=lambda x: x[1]['total_score'],
        reverse=True
    )
    
    print(f"\n📈 Summary:")
    print(f"   Total Articles Analyzed: {results['total_articles']}")
    print(f"   Categories Found: {len(sorted_categories)}")
    
    print("\n" + "-" * 70)
    print(f"{'Category':<20} {'Articles':<10} {'Total Score':<12} {'Engage':<10} {'Relevance':<10} {'Recency':<10} {'Impact':<10} {'Unique':<10}")
    print("-" * 70)
    
    for category, score_data in sorted_categories:
        article_count = score_data['article_count']
        total_score = score_data['total_score']
        
        print(f"{category:<20} {article_count:<10} {total_score:<12.2f} "
              f"{score_data['engagement']:<10.2f} {score_data['relevance']:<10.2f} "
              f"{score_data['recency']:<10.2f} {score_data['impact']:<10.2f} "
              f"{score_data['uniqueness']:<10.2f}")
    
    print("\n" + "-" * 70)
    print("Score Weights: Engagement (50%), Relevance (10%), Recency (10%), Impact (20%), Uniqueness (10%)")
    
    # Show top articles per category
    print("\n" + "=" * 70)
    print("📰 TOP ARTICLES BY CATEGORY")
    print("=" * 70)
    
    for category, score_data in sorted_categories[:5]:  # Top 5 categories
        if category in categorized:
            articles_in_category = categorized[category]
            print(f"\n🏷️  {category} ({score_data['article_count']} articles, Score: {score_data['total_score']:.2f})")
            print("-" * 70)
            for i, article in enumerate(articles_in_category[:3], 1):  # Top 3 per category
                title = article.get('title', 'No title')[:70]
                print(f"   {i}. {title}")
            if len(articles_in_category) > 3:
                print(f"   ... and {len(articles_in_category) - 3} more")
    
    print("\n" + "=" * 70)
    print("✅ Analysis Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()

