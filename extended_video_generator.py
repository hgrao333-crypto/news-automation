"""
Extended Video Generator - Creates 10-minute deep-dive videos for very hot topics
This is a separate module that doesn't modify existing code
"""
import os
# Fix huggingface/tokenizers parallelism warning
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')

import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json
import re
import os
from news_fetcher import NewsFetcher
from content_generator import ContentGenerator
from image_generator import ImageGenerator
from tts_generator import TTSGenerator
from video_generator import VideoGenerator
from config import NEWS_API_KEY, TEMP_DIR, OUTPUT_DIR

# Date filtering: Only fetch articles from last 10 days
DAYS_BACK = 10

# Try to import sentence-transformers for semantic similarity
# Falls back to keyword-based method if not available
USE_SEMANTIC_EMBEDDINGS = False
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    USE_SEMANTIC_EMBEDDINGS = True
    print("  ✅ Using semantic embeddings for article grouping (better accuracy)")
except ImportError:
    print("  ⚠️  sentence-transformers not available, using keyword-based method")
    print("  💡 Install with: pip install sentence-transformers scikit-learn")
    print("  💡 This will provide better article grouping accuracy")

class HotTopicDetector:
    """Detects very hot topics that need extended coverage (10-minute videos) - GLOBAL NEWS"""
    
    def __init__(self, news_api_key: str = None):
        self.news_api_key = news_api_key
        
        # Initialize semantic embedding model if available
        self.embedding_model = None
        if USE_SEMANTIC_EMBEDDINGS:
            try:
                # Use a lightweight, fast model optimized for news/sentences
                # all-MiniLM-L6-v2 is small (80MB), fast, and works well for news
                print("  📦 Loading semantic embedding model...")
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                print("  ✅ Semantic embedding model loaded")
            except Exception as e:
                print(f"  ⚠️  Could not load embedding model: {e}")
                print("  🔄 Falling back to keyword-based method")
                self.embedding_model = None
        
        # Keywords that indicate very hot topics requiring extended coverage
        self.hot_topic_keywords = [
            # Market/Economic
            'market crash', 'stock market crash', 'economic crisis', 'recession', 'inflation surge',
            'currency crash', 'banking crisis', 'financial crisis', 'bear market', 'dow jones',
            'nasdaq crash', 'bitcoin crash', 'crypto crash',
            
            # Major disasters
            'earthquake', 'tsunami', 'hurricane', 'cyclone', 'flood', 'wildfire', 'pandemic',
            'outbreak', 'epidemic', 'natural disaster', 'volcano', 'tornado',
            
            # Major political events
            'election results', 'government collapse', 'coup', 'revolution', 'war', 'conflict',
            'military action', 'nuclear', 'sanctions', 'impeachment', 'resignation',
            
            # Major tech events
            'data breach', 'cyber attack', 'hack', 'outage', 'major launch', 'breakthrough',
            'ai breakthrough', 'quantum computing',
            
            # Major social events
            'protest', 'riot', 'strike', 'mass demonstration', 'civil unrest',
            
            # Breaking news indicators
            'breaking', 'urgent', 'alert', 'emergency', 'crisis', 'critical', 'developing'
        ]
        
        # Impact scoring keywords (higher weight)
        self.high_impact_keywords = {
            'crash': 10,
            'crisis': 9,
            'emergency': 8,
            'breaking': 7,
            'urgent': 7,
            'war': 9,
            'pandemic': 9,
            'earthquake': 8,
            'recession': 8,
            'collapse': 8,
            'nuclear': 10,
            'attack': 9,
            'outbreak': 8
        }
    
    def _is_within_days(self, published_date, days: int = DAYS_BACK) -> bool:
        """Check if article is within the last N days
        Handles various date formats: ISO strings, RFC 2822, feedparser time.struct_time
        """
        if not published_date:
            return False
        
        try:
            article_date = None
            
            # Handle feedparser's time.struct_time format (tuple-like object)
            import time
            if isinstance(published_date, time.struct_time):
                # feedparser returns time.struct_time
                article_date = datetime(*published_date[:6])
            elif hasattr(published_date, 'timetuple'):
                # Some datetime-like objects
                article_date = datetime(*published_date.timetuple()[:6])
            elif isinstance(published_date, str):
                # Try ISO format first (2024-11-30T12:00:00Z)
                if 'T' in published_date:
                    # ISO format
                    date_str = published_date.split('T')[0]  # Get date part
                    article_date = datetime.strptime(date_str, '%Y-%m-%d')
                else:
                    # Try RFC 2822 format (Mon, 30 Nov 2024 12:00:00 +0000)
                    try:
                        import email.utils
                        parsed = email.utils.parsedate_tz(published_date)
                        if parsed:
                            article_date = datetime.fromtimestamp(email.utils.mktime_tz(parsed))
                        else:
                            # Try simple date format
                            article_date = datetime.strptime(published_date[:10], '%Y-%m-%d')
                    except:
                        # Try simple date format
                        try:
                            article_date = datetime.strptime(published_date[:10], '%Y-%m-%d')
                        except:
                            return False
            else:
                return False
            
            if article_date is None:
                return False
            
            # Check if within last N days
            cutoff_date = datetime.now() - timedelta(days=days)
            return article_date >= cutoff_date
        except Exception as e:
            # If parsing fails, assume it's recent (don't filter out)
            return True
    
    def _clean_text(self, text: str) -> str:
        """Remove HTML tags, URLs, and clean text"""
        if not text:
            return ""
        # Remove HTML tags (including <p>, <div>, <span>, etc.)
        text = re.sub(r'<[^>]+>', '', text)
        # Remove URLs (http://, https://, www.)
        text = re.sub(r'https?://[^\s]+', '', text)  # Remove http:// and https:// URLs
        text = re.sub(r'www\.[^\s]+', '', text)  # Remove www. URLs
        # Decode HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&apos;', "'")
        text = text.replace('&mdash;', '—').replace('&ndash;', '–')
        # Clean up extra whitespace
        text = ' '.join(text.split())
        return text.strip()
    
    def detect_very_hot_topic(self, articles: List[Dict], min_score: int = 50) -> Optional[Dict]:
        """
        Detect if there's a very hot topic that warrants a 10-minute video
        Prioritizes engagement: multiple articles, trending topics, global reach
        
        Returns:
            Dict with topic info if detected, None otherwise
        """
        if not articles:
            return None
        
        # Group articles by topic/keyword clusters
        topic_clusters = {}
        
        # Score each article for "hotness" and group by topic
        scored_articles = []
        total_articles = len(articles)
        print(f"  📊 Analyzing {total_articles} articles for hot topics...")
        
        for idx, article in enumerate(articles):
            # Show progress every 5% or every 25 articles, whichever is more frequent
            if idx % max(1, total_articles // 20) == 0 or idx == total_articles - 1:
                progress = ((idx + 1) / total_articles) * 100
                print(f"  ⏳ Progress: {progress:.1f}% ({idx + 1}/{total_articles} articles analyzed)", end='\r')
            
            title = article.get('title', '').lower()
            description = article.get('description', '').lower()
            content = f"{title} {description}"
            
            score = 0
            matched_keywords = []
            
            # Check for hot topic keywords
            for keyword in self.hot_topic_keywords:
                if keyword.lower() in content:
                    base_keyword = keyword.split()[0]
                    keyword_score = self.high_impact_keywords.get(base_keyword, 5)
                    score += keyword_score
                    matched_keywords.append(keyword)
            
            # ENGAGEMENT SCORING - Multiple articles about SAME SPECIFIC STORY (not just same keyword)
            # Use semantic similarity if available, otherwise use keyword + context matching
            similar_articles = []
            article_title = title.lower()
            article_desc = description.lower()
            
            # Extract specific context from this article (locations, names, specific terms)
            article_context = self._extract_specific_context(title, description)
            
            for a in articles:
                a_title = a.get('title', '').lower()
                a_desc = a.get('description', '').lower()
                
                # Check if article shares keywords AND specific context (same story)
                shares_keyword = any(kw in a_title or kw in a_desc for kw in matched_keywords)
                if shares_keyword:
                    # Extract context from other article
                    other_context = self._extract_specific_context(a.get('title', ''), a.get('description', ''))
                    
                    # Check if they share specific context (locations, names, etc.) - same story
                    # Pass full text for semantic similarity if available
                    if self._are_articles_same_story(
                        article_context, other_context, matched_keywords,
                        title, description, a.get('title', ''), a.get('description', '')
                    ):
                        similar_articles.append(a)
            
            similar_count = len(similar_articles)
            
            # Engagement multiplier: More articles = higher engagement
            if similar_count >= 10:
                engagement_multiplier = 3.0  # Very high engagement
            elif similar_count >= 5:
                engagement_multiplier = 2.5  # High engagement
            elif similar_count >= 3:
                engagement_multiplier = 2.0  # Medium-high engagement
            else:
                engagement_multiplier = 1.5  # Low-medium engagement
            
            # Base score multiplied by engagement
            score = int(score * engagement_multiplier)
            
            # Additional engagement points based on article count
            engagement_points = min(similar_count * 3, 30)  # Max 30 points for engagement
            score += engagement_points
            
            # Recency bonus (recent articles = more engagement)
            published = article.get('published', '')
            if published:
                if '2025' in published or '2024' in published:
                    score += 10  # Recent article = more engagement
                if 'T' in published:  # ISO format with time
                    score += 5   # Very recent
            
            # Global reach bonus (articles from multiple sources = viral)
            source_diversity = len(set(a.get('link', '')[:30] for a in similar_articles))
            if source_diversity >= 5:
                score += 15  # High source diversity = global reach
            elif source_diversity >= 3:
                score += 10  # Medium source diversity
            
            if score > 0:
                scored_articles.append({
                    'article': article,
                    'score': score,
                    'keywords': matched_keywords,
                    'similar_count': similar_count,
                    'engagement_multiplier': engagement_multiplier
                })
                
                # Group by SPECIFIC topic (not just generic keyword) for clustering
                # Extract specific topic name first, then group by that
                if matched_keywords:
                    # Extract specific topic name (e.g., "Ukraine War" not just "War")
                    specific_topic = self._extract_topic_name(article, matched_keywords)
                    
                    # Use specific topic as cluster key
                    cluster_key = specific_topic.lower()
                    if cluster_key not in topic_clusters:
                        topic_clusters[cluster_key] = []
                    topic_clusters[cluster_key].append({
                        'article': article,
                        'score': score,
                        'similar_count': similar_count,
                        'topic': specific_topic,
                        'keywords': matched_keywords  # Store keywords for validation
                    })
        
        # Clear progress line
        print()  # New line after progress
        
        # Sort by score
        scored_articles.sort(key=lambda x: x['score'], reverse=True)
        
        # Find best topic cluster (highest aggregate engagement)
        print(f"\n  📊 Processing {len(topic_clusters)} topic clusters...")
        best_cluster = None
        best_cluster_score = 0
        
        cluster_items = list(topic_clusters.items())
        for cluster_idx, (topic_key, cluster_articles) in enumerate(cluster_items):
            # Show progress for cluster processing
            if len(cluster_items) > 5:  # Only show progress if there are many clusters
                progress = ((cluster_idx + 1) / len(cluster_items)) * 100
                print(f"  ⏳ Cluster analysis: {progress:.1f}% ({cluster_idx + 1}/{len(cluster_items)})", end='\r')
            
            cluster_score = sum(a['score'] for a in cluster_articles)
            cluster_engagement = sum(a['similar_count'] for a in cluster_articles)
            
            # Additional validation: ensure articles in cluster are actually about same story
            # Check that articles share specific context (not just generic keyword)
            validated_articles = []
            if cluster_articles:
                # Use first article as reference
                ref_article = cluster_articles[0]['article']
                ref_context = self._extract_specific_context(
                    ref_article.get('title', ''), 
                    ref_article.get('description', '')
                )
                # Get keywords from the cluster item
                ref_keywords = cluster_articles[0].get('keywords', [])
                
                for cluster_item in cluster_articles:
                    article = cluster_item['article']
                    article_context = self._extract_specific_context(
                        article.get('title', ''),
                        article.get('description', '')
                    )
                    # Only include if it's the same specific story
                    ref_article = cluster_articles[0]['article']
                    article = cluster_item['article']
                    if self._are_articles_same_story(
                        ref_context, article_context, ref_keywords,
                        ref_article.get('title', ''), ref_article.get('description', ''),
                        article.get('title', ''), article.get('description', '')
                    ):
                        validated_articles.append(cluster_item)
                    else:
                        # Article doesn't match - might be different war/conflict
                        print(f"  ⚠️  Excluding article from cluster: '{article.get('title', '')[:50]}...' (different story)")
            
            # Use validated articles only
            if not validated_articles:
                continue
                
            cluster_score = sum(a['score'] for a in validated_articles)
            cluster_engagement = sum(a['similar_count'] for a in validated_articles)
            # Weight cluster score by engagement
            weighted_score = cluster_score + (cluster_engagement * 2)
            
            if weighted_score > best_cluster_score:
                best_cluster_score = weighted_score
                best_cluster = {
                    'keyword': topic_key,
                    'articles': validated_articles,
                    'score': weighted_score,
                    'engagement': cluster_engagement
                }
        
        # Clear progress line if we showed progress
        if len(cluster_items) > 5:
            print()  # New line after progress
        
        # Only return the HOTTEST topic (top 1, must meet threshold)
        if not scored_articles:
            return None
        
        # Find the absolute hottest topic (highest score)
        hottest = scored_articles[0]
        
        if hottest['score'] < min_score:
            return None
        
        top_article = hottest['article']
        topic = self._extract_topic_name(top_article, hottest['keywords'])
        
        # Get ALL related articles for comprehensive coverage
        # CRITICAL: Only include articles about the SAME SPECIFIC STORY (not just same keyword)
        print(f"\n  📊 Collecting related articles...")
        related_articles = []
        seen_titles = set()
        
        # Extract specific context from the hottest article
        hottest_article = hottest['article']
        hottest_context = self._extract_specific_context(
            hottest_article.get('title', ''),
            hottest_article.get('description', '')
        )
        
        # Add articles that are about the SAME SPECIFIC STORY
        total_scored = len(scored_articles)
        for scored_idx, scored in enumerate(scored_articles):
            if total_scored > 10:  # Only show progress if there are many articles
                progress = ((scored_idx + 1) / total_scored) * 100
                print(f"  ⏳ Collecting articles: {progress:.1f}% ({scored_idx + 1}/{total_scored})", end='\r')
            
            article = scored['article']
            title = article.get('title', '').lower()
            
            # Check if article shares keywords AND is about same specific story
            shares_keyword = any(kw in title or kw in article.get('description', '').lower() 
                                 for kw in hottest['keywords'])
            if shares_keyword:
                article_context = self._extract_specific_context(
                    article.get('title', ''),
                    article.get('description', '')
                )
                # Only include if it's the same specific story
                if self._are_articles_same_story(
                    hottest_context, article_context, hottest['keywords'],
                    hottest_article.get('title', ''), hottest_article.get('description', ''),
                    article.get('title', ''), article.get('description', '')
                ):
                    if title not in seen_titles:
                        seen_titles.add(title)
                        related_articles.append(article)
        
        # Clear progress line if we showed progress
        if total_scored > 10:
            print()  # New line after progress
        
        # Also search original articles list for any related content
        print(f"\n  📊 Final validation pass...")
        for article_idx, article in enumerate(articles):
            if total_articles > 50:  # Only show progress if there are many articles
                progress = ((article_idx + 1) / total_articles) * 100
                print(f"  ⏳ Validation: {progress:.1f}% ({article_idx + 1}/{total_articles})", end='\r')
            title = article.get('title', '').lower()
            desc = article.get('description', '').lower()
            
            # Check if article mentions keywords AND is about same specific story
            shares_keyword = any(kw in title or kw in desc for kw in hottest['keywords'])
            if shares_keyword:
                article_context = self._extract_specific_context(
                    article.get('title', ''),
                    article.get('description', '')
                )
                if self._are_articles_same_story(
                    hottest_context, article_context, hottest['keywords'],
                    hottest_article.get('title', ''), hottest_article.get('description', ''),
                    article.get('title', ''), article.get('description', '')
                ):
                    if title not in seen_titles:
                        seen_titles.add(title)
                        related_articles.append(article)
        
        # Clear progress line and show completion
        if total_articles > 50:
            print()  # New line after progress
        
        # Sort by relevance (articles with more keyword matches first)
        def relevance_score(article):
            title = article.get('title', '').lower()
            desc = article.get('description', '').lower()
            content = f"{title} {desc}"
            matches = sum(1 for kw in hottest['keywords'] if kw in content)
            return matches
        
        related_articles.sort(key=relevance_score, reverse=True)
        
        # CRITICAL: Require minimum number of articles for extended videos
        # A 10-minute video needs substantial content - at least 5 articles minimum
        min_articles_required = 5
        
        if len(related_articles) < min_articles_required:
            print(f"  ⚠️  Topic '{topic}' has only {len(related_articles)} article(s), but extended videos require at least {min_articles_required} articles")
            print(f"     Score: {hottest['score']} (threshold: {min_score})")
            print(f"     Engagement: {hottest['similar_count']} related articles")
            print(f"     ❌ Not enough articles for extended video (need {min_articles_required}+)")
            return None
        
        print(f"  🔥 HOTTEST TOPIC: {topic}")
        print(f"     Score: {hottest['score']} (threshold: {min_score})")
        print(f"     Engagement: {hottest['similar_count']} related articles")
        print(f"     Total articles found: {len(related_articles)} (minimum: {min_articles_required})")
        
        # Debug: Show sample article titles to verify they're about the same story
        print(f"\n  📋 Sample articles in this topic (showing first 5):")
        for i, article in enumerate(related_articles[:5], 1):
            article_title = article.get('title', 'N/A')[:80]
            print(f"     {i}. {article_title}...")
        
        # Check if topic is too generic (just "War", "Conflict", etc. without location)
        if topic.lower() in ['war', 'conflict', 'crisis', 'attack', 'military action']:
            print(f"\n  ⚠️  WARNING: Topic '{topic}' is generic and may include different wars/conflicts!")
            print(f"     The system should extract specific names like 'Ukraine War' or 'Gaza Conflict'")
            print(f"     If articles are about different wars, they should be separated.")
            print(f"     Please verify the articles are actually about the same specific war/conflict.")
        
        return {
            'topic': topic,
            'article': top_article,
            'score': hottest['score'],
            'engagement_score': hottest['similar_count'],
            'related_articles': related_articles,  # ALL related articles
            'keywords': hottest['keywords'],
            'cluster_info': best_cluster
        }
    
    def _extract_specific_context(self, title: str, description: str) -> Dict:
        """Extract specific context from article (locations, names, specific terms) to identify same story"""
        content = f"{title} {description}".lower()
        
        # Extract locations
        locations = [
            'ukraine', 'russia', 'gaza', 'israel', 'palestine', 'syria', 'yemen', 
            'afghanistan', 'iraq', 'iran', 'china', 'taiwan', 'korea', 'north korea',
            'sudan', 'ethiopia', 'myanmar', 'libya', 'lebanon', 'jordan', 'egypt',
            'vietnam', 'cuba', 'venezuela', 'mexico', 'colombia', 'brazil',
            'india', 'pakistan', 'bangladesh', 'sri lanka', 'nepal'
        ]
        
        found_locations = []
        for location in locations:
            if location in content:
                found_locations.append(location)
        
        # Extract key names (capitalized words that might be people, organizations, etc.)
        # Look for capitalized words in title
        title_words = title.split()
        key_names = []
        for word in title_words:
            if word and word[0].isupper() and len(word) > 3:
                # Skip common words
                if word.lower() not in ['the', 'this', 'that', 'with', 'from', 'about', 'breaking', 'news', 'update', 'latest']:
                    key_names.append(word.lower())
        
        # Extract specific terms (dates, numbers, specific events)
        # Look for patterns like "2024", "2025", specific dates
        # Use module-level re (already imported at top)
        dates = re.findall(r'\b(20\d{2}|january|february|march|april|may|june|july|august|september|october|november|december)\b', content)
        
        return {
            'locations': found_locations,
            'key_names': key_names[:5],  # Limit to top 5
            'dates': dates[:3]  # Limit to top 3
        }
    
    def _are_articles_same_story(self, context1: Dict, context2: Dict, keywords: List[str], 
                                  title1: str = "", desc1: str = "", title2: str = "", desc2: str = "") -> bool:
        """Check if two articles are about the same specific story (not just same topic)
        
        Uses semantic embeddings if available, otherwise falls back to keyword-based matching
        """
        # Use semantic similarity if embedding model is available
        if self.embedding_model and title1 and title2:
            try:
                # Create text representation for each article
                text1 = f"{title1} {desc1}".strip()
                text2 = f"{title2} {desc2}".strip()
                
                if text1 and text2:
                    # Generate embeddings
                    embeddings = self.embedding_model.encode([text1, text2])
                    
                    # Calculate cosine similarity
                    similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
                    
                    # Threshold: 0.65+ = same story, 0.5-0.65 = possibly same, <0.5 = different
                    # For news articles, 0.65 is a good threshold (not too strict, not too loose)
                    if similarity >= 0.65:
                        return True
                    elif similarity < 0.5:
                        return False
                    # For 0.5-0.65, use context-based validation as tiebreaker
            except Exception as e:
                print(f"  ⚠️  Error in semantic similarity: {e}, falling back to keyword method")
        
        # Fallback to keyword-based method
        # If both have locations, they must share at least one location
        if context1.get('locations') and context2.get('locations'):
            shared_locations = set(context1['locations']) & set(context2['locations'])
            if not shared_locations:
                # Different locations = different stories (e.g., Ukraine War vs Gaza War)
                return False
        
        # If one has location and other doesn't, but keyword is generic (war, conflict), likely different
        if keywords:
            primary_keyword = keywords[0].lower()
            if primary_keyword in ['war', 'conflict', 'crisis', 'attack', 'military action']:
                # For generic keywords, require location match
                if context1.get('locations') and not context2.get('locations'):
                    return False
                if context2.get('locations') and not context1.get('locations'):
                    return False
                # Both must have same location
                if context1.get('locations') and context2.get('locations'):
                    if not (set(context1['locations']) & set(context2['locations'])):
                        return False
        
        # Check for shared key names (people, organizations) - strong indicator of same story
        if context1.get('key_names') and context2.get('key_names'):
            shared_names = set(context1['key_names']) & set(context2['key_names'])
            if shared_names:
                # Shared names = likely same story
                return True
        
        # If locations match, consider it same story
        if context1.get('locations') and context2.get('locations'):
            if set(context1['locations']) & set(context2['locations']):
                return True
        
        # If no specific context but keywords match, allow it (fallback)
        # But prefer stricter matching
        if not context1.get('locations') and not context2.get('locations'):
            # No location info - use keyword matching as fallback
            return True
        
        # Default: not same story if we can't confirm
        return False
    
    def _extract_topic_name(self, article: Dict, keywords: List[str]) -> str:
        """Extract a concise, specific topic name from article that distinguishes between different conflicts/wars"""
        title = article.get('title', '')
        description = article.get('description', '')
        content = f"{title} {description}".lower()
        
        # Try to extract more specific topic names for common generic keywords
        # This helps distinguish between different wars/conflicts
        
        # Common location/country names that appear in war/conflict news
        locations = [
            'ukraine', 'russia', 'gaza', 'israel', 'palestine', 'syria', 'yemen', 
            'afghanistan', 'iraq', 'iran', 'china', 'taiwan', 'korea', 'north korea',
            'sudan', 'ethiopia', 'myanmar', 'libya', 'lebanon', 'jordan', 'egypt',
            'vietnam', 'cuba', 'venezuela', 'mexico', 'colombia', 'brazil',
            'india', 'pakistan', 'bangladesh', 'sri lanka', 'nepal'
        ]
        
        # Check if article mentions a specific location
        found_location = None
        for location in locations:
            if location in content:
                found_location = location.title()
                break
        
        # If we found a location and the keyword is generic (war, conflict, etc.)
        if found_location and keywords:
            primary_keyword = keywords[0].lower()
            if primary_keyword in ['war', 'conflict', 'crisis', 'attack', 'military action']:
                # Create specific topic name: "Ukraine War", "Gaza Conflict", etc.
                return f"{found_location} {primary_keyword.title()}"
        
        # Try to extract from title - look for patterns like "Country War" or "Location Conflict"
        title_lower = title.lower()
        for location in locations:
            location_lower = location.lower()
            if location_lower in title_lower:
                # Check if there's a keyword nearby
                location_idx = title_lower.find(location_lower)
                # Look for keywords in the 20 characters before or after the location
                context_start = max(0, location_idx - 20)
                context_end = min(len(title_lower), location_idx + len(location_lower) + 20)
                context = title_lower[context_start:context_end]
                
                for keyword in ['war', 'conflict', 'crisis', 'attack', 'invasion', 'strike']:
                    if keyword in context:
                        return f"{location.title()} {keyword.title()}"
                
                # If no keyword found but location is there, use location + generic term
                if keywords:
                    return f"{location.title()} {keywords[0].title()}"
        
        # If we have keywords but no location, try to make it more specific
        if keywords:
            primary_keyword = keywords[0].lower()
            # Check if title has any specific context we can use
            # Look for capitalized words (likely proper nouns) near the keyword
            title_words = title.split()
            keyword_idx = -1
            for i, word in enumerate(title_words):
                if primary_keyword in word.lower():
                    keyword_idx = i
                    break
            
            if keyword_idx >= 0:
                # Look for capitalized words before the keyword (likely the subject)
                context_words = []
                for i in range(max(0, keyword_idx - 3), keyword_idx):
                    word = title_words[i]
                    # If word is capitalized and not a common word, include it
                    if word and word[0].isupper() and len(word) > 2:
                        # Skip common words
                        if word.lower() not in ['the', 'a', 'an', 'in', 'on', 'at', 'for', 'with', 'from', 'to', 'of', 'and', 'or', 'but']:
                            context_words.append(word)
                
                if context_words:
                    # Use the most relevant context word + keyword
                    return f"{' '.join(context_words[-2:])} {primary_keyword.title()}"
            
            # Fallback: just use keyword
            return keywords[0].title()
        
        # Last resort: use first few meaningful words of title
        words = title.split()[:5]
        # Filter out common words
        meaningful_words = [w for w in words if w.lower() not in ['the', 'a', 'an', 'in', 'on', 'at', 'for', 'with', 'from', 'to', 'of', 'and', 'or', 'but', 'breaking', 'news', 'update']]
        if meaningful_words:
            return ' '.join(meaningful_words[:4])
        
        return ' '.join(words[:5])
    
    def fetch_extended_news(self, topic: str, limit: int = 50) -> List[Dict]:
        """
        Fetch extended news coverage for a hot topic - GLOBAL NEWS
        Searches worldwide, not limited to India
        Only fetches articles from last 10 days
        """
        all_articles = []
        
        # Calculate date 10 days ago for filtering
        cutoff_date = datetime.now() - timedelta(days=DAYS_BACK)
        from_date = cutoff_date.strftime('%Y-%m-%d')
        
        # Search multiple sources with broader queries
        search_queries = [
            topic,
            topic.split()[0] if topic.split() else topic,  # First word
            ' '.join(topic.split()[:3]) if len(topic.split()) > 1 else topic  # First 3 words
        ]
        
        # Fetch from NewsAPI - GLOBAL SEARCH (no country restriction)
        # Filter to last 10 days only
        if self.news_api_key:
            for query in search_queries:
                try:
                    url = "https://newsapi.org/v2/everything"
                    params = {
                        "apiKey": self.news_api_key,
                        "q": query,
                        "language": "en",
                        "sortBy": "popularity",  # Sort by popularity for engagement
                        "pageSize": min(limit, 50),
                        "from": from_date,  # Only articles from last 10 days
                        # NO country parameter - global search
                    }
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        for article in data.get("articles", []):
                            published = article.get("publishedAt", "")
                            # Double-check date filter (in case API doesn't respect it)
                            if self._is_within_days(published, DAYS_BACK):
                                # Clean HTML and URLs from title and description
                                title = self._clean_text(article.get("title", ""))
                                description = self._clean_text(article.get("description", ""))
                                if title:  # Only add if title exists
                                    all_articles.append({
                                        "title": title,
                                        "description": description,
                                        "link": article.get("url", ""),
                                        "published": published,
                                        "source": article.get("source", {}).get("name", ""),
                                    })
                except Exception as e:
                    print(f"Error fetching global news: {e}")
        
        # Also fetch from global RSS feeds (not India-specific)
        # Use NewsFetcher but override country
        fetcher = NewsFetcher(news_api_key=self.news_api_key, country=None)  # Global
        
        # Fetch from multiple global sources
        try:
            # Top headlines globally
            url = "https://newsapi.org/v2/top-headlines"
            params = {
                "apiKey": self.news_api_key,
                "language": "en",
                "pageSize": 30,
                # NO country = global
            }
            # Add date filter for last 10 days
            cutoff_date = datetime.now() - timedelta(days=DAYS_BACK)
            from_date = cutoff_date.strftime('%Y-%m-%d')
            params["from"] = from_date
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for article in data.get("articles", []):
                    published = article.get("publishedAt", "")
                    # Check date filter
                    if self._is_within_days(published, DAYS_BACK):
                        # Check if article is related to topic
                        article_title = article.get("title") or ""
                        article_desc = article.get("description") or ""
                        title = article_title.lower() if article_title else ""
                        desc = article_desc.lower() if article_desc else ""
                        if topic and title and desc and any(word in title or word in desc for word in topic.lower().split()):
                            # Clean HTML and URLs
                            clean_title = self._clean_text(article_title)
                            clean_desc = self._clean_text(article_desc)
                            if clean_title:  # Only add if title exists
                                all_articles.append({
                                    "title": clean_title,
                                    "description": clean_desc,
                                    "link": article.get("url", ""),
                                    "published": published,
                                    "source": article.get("source", {}).get("name", ""),
                                })
        except Exception as e:
            print(f"Error fetching global headlines: {e}")
        
        # Fetch from RSS feeds globally - Expanded list for comprehensive coverage
        try:
            rss_feeds = [
                # Major International News
                "http://feeds.bbci.co.uk/news/rss.xml",
                "http://feeds.bbci.co.uk/news/world/rss.xml",
                "http://feeds.bbci.co.uk/news/business/rss.xml",
                "http://rss.cnn.com/rss/edition.rss",
                "http://rss.cnn.com/rss/edition_world.rss",
                "http://rss.cnn.com/rss/money_latest.rss",
                "http://feeds.reuters.com/reuters/topNews",
                "http://feeds.reuters.com/reuters/worldNews",
                "http://feeds.reuters.com/reuters/businessNews",
                "https://www.theguardian.com/world/rss",
                "https://www.theguardian.com/business/rss",
                "https://feeds.npr.org/1001/rss.xml",
                "https://feeds.npr.org/1004/rss.xml",
                "https://feeds.npr.org/1006/rss.xml",
                
                # US News Sources
                "https://feeds.foxnews.com/foxnews/latest",
                "https://feeds.foxnews.com/foxnews/world",
                "https://www.nbcnews.com/rss.xml",
                "https://www.nbcnews.com/world/rss.xml",
                "https://abcnews.go.com/abcnews/topstories",
                "https://abcnews.go.com/abcnews/internationalheadlines",
                "https://www.cbsnews.com/latest/rss/main",
                "https://www.cbsnews.com/latest/rss/world",
                
                # International Sources
                "https://www.aljazeera.com/xml/rss/all.xml",
                "https://www.aljazeera.com/xml/rss/world.xml",
                "https://www.dw.com/en/rss/rss-top/rss.xml",
                "https://www.dw.com/en/rss/rss-world/rss.xml",
                "https://www.france24.com/en/rss",
                "https://www.france24.com/en/world/rss",
                "https://www.euronews.com/rss?format=mrss",
                "https://www.euronews.com/rss?format=mrss&name=world",
                
                # Business & Finance
                "https://feeds.bloomberg.com/markets/news.rss",
                "https://www.ft.com/rss/home",
                "https://www.ft.com/rss/world",
                "https://feeds.washingtonpost.com/rss/world",
                "https://feeds.washingtonpost.com/rss/business",
            ]
            
            import feedparser
            import time
            for feed_url in rss_feeds:
                try:
                    feed = feedparser.parse(feed_url)
                    # Fetch more entries (30 instead of 10) for better topic coverage
                    for entry in feed.entries[:30]:
                        # feedparser provides both 'published' (string) and 'published_parsed' (time.struct_time)
                        # Use published_parsed if available (more reliable), otherwise use published string
                        published = entry.get('published_parsed') or entry.get('published', '')
                        # Filter by date: only last 10 days
                        if self._is_within_days(published, DAYS_BACK):
                            entry_title = entry.get('title') or ''
                            entry_desc = entry.get('description') or ''
                            title = entry_title.lower() if entry_title else ''
                            desc = entry_desc.lower() if entry_desc else ''
                            # Check if related to topic (handle None topic)
                            if topic and title and desc and any(word in title or word in desc for word in topic.lower().split()):
                                # Clean HTML and URLs
                                clean_title = self._clean_text(entry_title)
                                clean_desc = self._clean_text(entry_desc)
                                if clean_title:  # Only add if title exists
                                    # Convert time.struct_time to string for storage
                                    if isinstance(published, time.struct_time):
                                        # Convert to ISO format string
                                        published_str = datetime(*published[:6]).isoformat()
                                    else:
                                        published_str = str(published) if published else ''
                                    
                                    all_articles.append({
                                        "title": clean_title,
                                        "description": clean_desc,
                                        "link": entry.get('link', ''),
                                        "published": published_str,
                                        "source": feed.feed.get('title', 'RSS Feed'),
                                    })
                except Exception as e:
                    # Silently skip failed feeds
                    pass
        except Exception as e:
            print(f"Error fetching RSS feeds: {e}")
        
        # Remove duplicates
        seen_titles = set()
        unique_articles = []
        for article in all_articles:
            title = article.get('title', '').lower()
            if title not in seen_titles and article.get('title'):
                seen_titles.add(title)
                unique_articles.append(article)
        
        # Sort by recency (most recent first)
        unique_articles.sort(key=lambda x: x.get('published', ''), reverse=True)
        
        print(f"  🌍 Fetched {len(unique_articles)} global articles for topic: {topic}")
        
        return unique_articles[:limit]


class ExtendedContentGenerator:
    """Generates extended 10-minute scripts for hot topics"""
    
    def __init__(self):
        # Use existing ContentGenerator's LLM client setup
        self.base_generator = ContentGenerator()
        self.llm_client = self.base_generator.llm_client
        # Keep for backward compatibility
        self.client = self.base_generator.client
        self.model = self.base_generator.model
    
    def generate_extended_script(self, topic: str, articles: List[Dict], duration: int = 600, content_style: str = "newsy") -> Dict:
        """
        Generate an extended 10-minute script for a very hot topic
        Summarizes ALL relevant articles to create comprehensive story
        Structure: Introduction -> Multiple detailed sections -> Multiple detailed sections -> Conclusion
        
        Args:
            topic: The hot topic to cover
            articles: List of news articles about the topic
            duration: Video duration in seconds (default: 600 = 10 minutes)
            content_style: "newsy" (traditional news format) or "social" (social media native format)
        """
        print(f"\n  📝 Generating extended {duration//60}-minute script for HOTTEST topic: {topic}")
        print(f"  📰 Summarizing {len(articles)} relevant articles...")
        
        # Social media native format adjustments
        is_social_format = content_style.lower() == "social"
        
        # Prepare comprehensive news summary - USE ALL ARTICLES
        # Group articles by theme/subtopic for better organization
        news_summary = "COMPREHENSIVE NEWS COVERAGE - ALL RELEVANT ARTICLES:\n\n"
        
        # Include ALL articles, not just first 40
        for i, article in enumerate(articles, 1):
            title = article.get('title', '')
            desc = article.get('description', '') or ''
            # Include full description, not truncated
            news_summary += f"{i}. {title}\n   {desc}\n\n"
        
        print(f"  ✅ Prepared summary from {len(articles)} articles")
        
        # Generate title based on content style
        if is_social_format:
            title_prompt = f"""Create a VIRAL, social media-style title for a 10-minute deep-dive YouTube video about:

Topic: {topic}

Requirements:
- Social media native language
- Attention-grabbing and shareable
- Uses casual, relatable tone
- Creates FOMO and curiosity
- 8-12 words maximum
- Feels like a friend sharing news, not a news anchor

SOCIAL MEDIA TITLE PATTERNS:
- "POV: You're watching [topic] unfold and it's wild"
- "So [topic] just happened and honestly? You need to see this"
- "[Topic] - Here's everything that went down (no cap)"
- "The [topic] story is WILD - here's what you missed"

Return ONLY the title, nothing else."""
        else:
            title_prompt = f"""Create a compelling, clickbait-style title for a 10-minute deep-dive video about:

Topic: {topic}

Requirements:
- Attention-grabbing and engaging
- Suitable for YouTube (encourages clicks)
- Professional but exciting
- 8-12 words maximum

Return ONLY the title, nothing else."""
        
        try:
            # Use unified LLM client with fallback
            title_response = self.llm_client.generate(title_prompt, {"temperature": 0.8, "num_predict": 100})
            clickbait_title = title_response.get('response', f"Breaking: {topic}").strip().strip('"').strip("'")
            if len(clickbait_title) > 100:
                clickbait_title = clickbait_title[:100]
        except:
            clickbait_title = f"Breaking: {topic} - Complete Analysis"
        
        # Check if hook-based headlines are enabled (import from config)
        from config import USE_HOOK_BASED_HEADLINES
        use_hooks = USE_HOOK_BASED_HEADLINES
        
        # Generate structured script that summarizes ALL articles as ONE CONNECTED STORY
        style_note = ""
        if is_social_format:
            style_note = """
CRITICAL: This is SOCIAL MEDIA NATIVE FORMAT - use casual, relatable, viral-worthy language!
- Use casual, friend-to-friend tone (not news anchor style)
- Use social media patterns: "So", "Okay so", "Here's the thing", "Wait, what?", "This is wild"
- For YOUNG (18-30): Use Gen Z slang: "spicy", "wild", "crazy", "fire", "slaps", "vibes", "tea", "no cap"
- For MIDDLE_AGE (30-55): Use professional but relatable: "So this just happened", "Here's what's going on"
- For OLD (55+): Use clear, straightforward: "Here's what happened", "Important update"
- Make it feel like a friend explaining a story, not a formal news report
"""
        else:
            style_note = """
- Use natural, professional news anchor language
- Maintain authoritative but engaging tone
"""
        
        script_prompt = f"""You are creating a comprehensive {duration//60}-minute deep-dive video script about the HOTTEST trending topic.
{style_note}

Topic: {topic}

CRITICAL: This is ONE UNIFIED STORY, not separate segments. The entire script must flow as a single, connected narrative.
Think of it like a news anchor telling ONE complete story from beginning to end, where each part connects to the next.

IMPORTANT: You have access to ALL relevant articles about this topic. Your script must:
1. Synthesize ALL articles into ONE COHESIVE STORY
2. Connect all information together - show how events relate to each other
3. Flow naturally from one point to the next with smooth transitions
4. Build a complete narrative arc: setup → development → impact → implications
5. Make it feel like ONE story, not separate topics

Comprehensive News Coverage ({len(articles)} articles):
{news_summary[:8000]}  # Limit to avoid token limits, but use representative sample

Create a detailed, structured {duration//60}-minute script that tells ONE CONNECTED STORY:

1. INTRODUCTION (30-45 seconds)
   {"- POWERFUL HOOK that grabs attention immediately (use engagement techniques like 'Wait, this just happened...', 'Breaking right now...', 'You won't believe this...')" if use_hooks else "- Hook that grabs attention"}
   - Brief overview of why this topic matters
   - What viewers will learn

2. MAIN CONTENT (8-9 minutes total)
   Divide into 5-6 natural segments that flow smoothly, each covering:
   - Opening statement (20-30 seconds): Natural introduction to this aspect
   - Detailed explanation (40-60 seconds): Comprehensive coverage synthesizing multiple articles
   - Additional details (40-60 seconds): More depth from various sources
   - Further analysis (40-60 seconds): Additional angles and perspectives
   - Context and implications (30-40 seconds): Why this matters, what it means
   
   Cover ALL aspects from the articles naturally:
   - What happened (facts, timeline, key events from ALL sources - tell it as a story)
   - Why it happened (causes, background, context from multiple perspectives)
   - Who is affected (impact on people, businesses, countries - comprehensive coverage)
   - What happens next (implications, predictions, future outlook from all articles)
   - Broader context (synthesize information from all sources)
   
   CRITICAL: 
   - Each segment must draw from MULTIPLE articles, not just one
   - Write naturally as a news anchor would speak
   - Use smooth transitions between topics
   - Avoid repetitive phrases or numbered lists
   - Make it engaging and informative
   {"- STRATEGICALLY USE ENGAGEMENT HOOKS at key transition points (every 2-3 segments):" if use_hooks else ""}
   {"  * Use 'Wait, this just happened...' or 'Breaking right now...' at major developments" if use_hooks else ""}
   {"  * Use 'You won't believe this...' or 'This just changed everything...' at surprising revelations" if use_hooks else ""}
   {"  * Use 'Here's what you need to know...' or 'This is huge...' at critical moments" if use_hooks else ""}
   {"  * Weave hooks naturally into the narrative - don't just prefix them" if use_hooks else ""}

3. CONCLUSION (30-45 seconds)
   - Summary of key takeaways
   - Final thoughts
   - Call to action

CRITICAL REQUIREMENTS:
- Total duration: EXACTLY {duration} seconds ({duration//60} minutes) - MUST fill entire duration
- Average speaking rate: 2.5 words per second (calculate carefully: {duration} seconds = {int(duration * 2.5)} words total)
- Each segment should be 20-60 seconds
- Be detailed and informative (this is a deep-dive)
- Use natural, professional news anchor language
- Include specific facts, numbers, dates, and details from articles
- Make it ONE CONNECTED STORY - not separate topics
- Use smooth transitions: "As this developed...", "This led to...", "Meanwhile...", "In response..."
- Show connections: How does each event relate to others?
- Build narrative arc: Beginning → Development → Current State → Implications
- NO numbered lists, NO "key point 1/2/3", NO "section 1/2/3"
- Write as a professional news anchor telling ONE complete story
{"- NATURALLY incorporate engagement hooks throughout - make them feel conversational and part of the story, not forced" if use_hooks else ""}

Format your response as JSON:
{{
  "script": "[full script text - ONE CONNECTED STORY, approximately {int(duration * 2.5)} words to fill {duration} seconds. Tell it as ONE narrative, not separate topics]",
  "segments": [
    {{
      "text": "[segment text - part of ONE connected story, flows from previous segment, uses transitions like 'As this developed', 'This led to', 'Meanwhile', 'In response']",
      "duration": [duration in seconds, 20-60],
      "start_time": [start time in seconds],
      "type": "opening|story_part1|story_part2|story_part3|story_part4|closing",
      "section": [part number 1-4],
      "section_title": "[natural part name: 'The Beginning', 'The Escalation', 'Current Situation', 'Ripple Effects']"
    }},
    ...
  ],
  "image_prompts": [
    "[detailed visual description for each segment - 80-150 words, describe scene, composition, lighting, mood]",
    ...
  ]
}}

STORY STRUCTURE EXAMPLE:
{"- Segment 1: 'Wait, this just happened - [topic]. This story began when...' (powerful hook)" if use_hooks else "- Segment 1: 'Breaking news: [topic]. This story began when...'"}
- Segment 2: "As this developed, [what happened next]..."
- Segment 3: "This led to [consequence], affecting [who]..."
{"- Segment 4: 'You won't believe this - meanwhile, [related development]...' (engagement hook)" if use_hooks else "- Segment 4: 'Meanwhile, [related development]...'"}
- Segment 5: "The situation escalated when [next event]..."
{"- Segment 6: 'Breaking right now - this just changed everything...' (strategic hook)" if use_hooks else "- Segment 6: 'Further developments show...'"}
- Continue connecting events until conclusion...

VERIFY: Total words in script should be approximately {int(duration * 2.5)} words to fill {duration} seconds.

IMPORTANT for image_prompts:
- Each prompt should be 80-150 words
- Describe visual elements: people, objects, scenes, buildings, landscapes, actions
- Include composition, lighting, colors, mood, atmosphere
- ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO SIGNS, NO LABELS - purely visual imagery only
- AVOID any text elements: no headlines, no captions, no signs, no banners, no text overlays, no written words of any kind
- Focus on visual storytelling through imagery, symbols, colors, composition, and mood only
- Match the content of each segment

Return ONLY valid JSON, no markdown formatting."""

        try:
            # Use unified LLM client with fallback
            response = self.llm_client.generate(
                script_prompt,
                {
                    "temperature": 0.7,
                    "num_predict": 4000,  # More tokens for longer script
                }
            )
            
            content = response.get('response', '').strip()
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            # Try to parse JSON, handle errors gracefully
            try:
                # Try to repair JSON before parsing
                content = self._repair_json_string(content)
                result = json.loads(content.strip())
            except json.JSONDecodeError as e:
                print(f"  ⚠️  JSON parsing error: {e}")
                print(f"  📄 Response preview: {content[:500]}...")
                # Try to extract JSON from response
                if '{' in content and '}' in content:
                    # Try to find JSON object
                    start_idx = content.find('{')
                    end_idx = content.rfind('}') + 1
                    if start_idx < end_idx:
                        try:
                            json_str = content[start_idx:end_idx]
                            # Try to repair the extracted JSON
                            json_str = self._repair_json_string(json_str)
                            result = json.loads(json_str)
                            print(f"  ✅ Successfully repaired and parsed JSON after extraction")
                        except json.JSONDecodeError as e2:
                            print(f"  ⚠️  JSON repair failed: {e2}")
                            print(f"  📄 Attempting more aggressive repair...")
                            # Try one more time with more aggressive repair
                            try:
                                # Try to fix common issues more aggressively
                                # Remove any text before first { and after last }
                                json_str_clean = json_str.strip()
                                # Try to fix unescaped quotes in string values
                                # This is a last resort - try to fix obvious issues
                                # Fix trailing commas before closing braces/brackets
                                json_str_clean = re.sub(r',(\s*[}\]])', r'\1', json_str_clean)
                                # Try to close any unclosed strings at the end
                                if json_str_clean.count('"') % 2 != 0:
                                    # Odd number of quotes - try to close the last one
                                    last_quote_idx = json_str_clean.rfind('"')
                                    if last_quote_idx > 0:
                                        # Check if we're in a string value context
                                        before_quote = json_str_clean[:last_quote_idx]
                                        if ':' in before_quote:
                                            # Likely a string value, try to close it
                                            json_str_clean = json_str_clean[:last_quote_idx + 1] + '"' + json_str_clean[last_quote_idx + 1:]
                                
                                result = json.loads(json_str_clean)
                                print(f"  ✅ Successfully parsed JSON after aggressive repair")
                            except json.JSONDecodeError as e3:
                                print(f"  ⚠️  Aggressive repair also failed: {e3}")
                                print(f"  💡 Attempting to extract usable data from broken JSON...")
                                # Try to extract usable data from broken JSON
                                extracted_data = self._extract_data_from_broken_json(json_str_clean)
                                if extracted_data:
                                    print(f"  ✅ Successfully extracted usable data from broken JSON")
                                    result = extracted_data
                                else:
                                    print(f"  💡 Falling back to fallback script generation")
                                    raise ValueError("Could not parse JSON response even after repair attempts")
                    else:
                        raise ValueError("Invalid JSON structure")
                else:
                    raise ValueError("No JSON found in response")
            
            # Ensure segments have proper structure
            segments = result.get('segments', [])
            if not segments:
                raise ValueError("No segments generated")
            
            # Normalize durations to match target - ensure full duration is used
            total_duration = sum(s.get('duration', 0) for s in segments)
            
            # Check if script is long enough (should be ~2.5 words per second)
            script_text = result.get('script', '')
            word_count = len(script_text.split())
            expected_words = duration * 2.5
            
            print(f"  📊 Script word count: {word_count} (target: {expected_words:.0f})")
            print(f"  📊 Segment duration sum: {total_duration}s (target: {duration}s)")
            
            # If script is too short, extend segments to fill duration
            if word_count < expected_words * 0.7:
                print(f"  ⚠️  Warning: Script is too short ({word_count} words vs {expected_words:.0f} expected)")
                print(f"  💡 Script may not fill full {duration//60} minutes - will extend audio")
                
                # Extend each segment proportionally to fill the duration
                if total_duration > 0 and total_duration < duration:
                    scale_factor = duration / total_duration
                    current_time = 0
                    for segment in segments:
                        new_duration = max(20, round(segment.get('duration', 30) * scale_factor))
                        segment['duration'] = new_duration
                        segment['start_time'] = current_time
                        current_time += new_duration
                    
                    # Adjust last segment to match exact duration
                    total = sum(s['duration'] for s in segments)
                    if total != duration:
                        segments[-1]['duration'] += (duration - total)
                        segments[-1]['start_time'] = sum(s['duration'] for s in segments[:-1])
                elif total_duration == 0:
                    # If no durations, calculate from word count
                    seconds_per_segment = duration / len(segments) if segments else 0
                    current_time = 0
                    for segment in segments:
                        segment['duration'] = max(20, round(seconds_per_segment))
                        segment['start_time'] = current_time
                        current_time += segment['duration']
            elif total_duration != duration:
                # Script is long enough, just adjust durations
                scale_factor = duration / total_duration if total_duration > 0 else 1
                current_time = 0
                for segment in segments:
                    segment['duration'] = max(15, round(segment.get('duration', 30) * scale_factor))
                    segment['start_time'] = current_time
                    current_time += segment['duration']
                
                # Adjust last segment to match exact duration
                total = sum(s['duration'] for s in segments)
                if total != duration:
                    segments[-1]['duration'] += (duration - total)
                    segments[-1]['start_time'] = sum(s['duration'] for s in segments[:-1])
            
            # Generate image prompts if missing or incomplete
            image_prompts = result.get('image_prompts', [])
            if not image_prompts or len(image_prompts) < len(segments):
                print("  🖼️  Generating detailed image prompts for extended video...")
                image_prompts = self._generate_image_prompts(segments, articles, topic)
            
            # Clean image prompts
            cleaned_prompts = []
            for p in image_prompts:
                if isinstance(p, str):
                    cleaned = re.sub(r'<[^>]+>', '', p)
                    cleaned = cleaned.replace('&nbsp;', ' ').replace('&amp;', '&')
                    cleaned = ' '.join(cleaned.split())
                    if len(cleaned) < 20 or cleaned.startswith('<img'):
                        cleaned = f"Professional news broadcast scene depicting: {topic}. Detailed visual representation with appropriate lighting, composition, and atmosphere."
                    cleaned_prompts.append(cleaned)
                else:
                    cleaned_prompts.append(str(p))
            
            result['title'] = clickbait_title
            result['segments'] = segments
            result['image_prompts'] = cleaned_prompts
            
            print(f"  ✅ Generated extended script with {len(segments)} segments")
            print(f"  📋 Total duration: {sum(s['duration'] for s in segments)} seconds")
            print(f"  🖼️  Image prompts: {len(cleaned_prompts)}")
            
            return result
            
        except Exception as e:
            print(f"  ⚠️  Error generating extended script: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to simpler structure
            return self._create_fallback_script(topic, articles, duration)
    
    def _repair_json_string(self, json_str: str) -> str:
        """
        Attempt to repair common JSON issues like unterminated strings, unescaped quotes, etc.
        """
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
        # 1. Fix missing commas between JSON elements FIRST (before string processing)
        # Pattern: }" or ]" or }[ or ][ -> should have comma
        # But be careful not to add commas inside string values
        # Use a more sophisticated approach: track string state
        
        # First, fix obvious cases where we're outside strings
        # Look for patterns like: }"key": or ]"key": (missing comma before key)
        json_str = re.sub(r'}(\s*)"([^"]+)":', r'},\1"\2":', json_str)
        json_str = re.sub(r'](\s*)"([^"]+)":', r'],\1"\2":', json_str)
        json_str = re.sub(r'}(\s*)\[', r'},\1[', json_str)
        json_str = re.sub(r'](\s*)\[', r'],\1[', json_str)
        json_str = re.sub(r'}(\s*){', r'},\1{', json_str)
        json_str = re.sub(r'](\s*){', r'],\1{', json_str)
        
        # Fix missing commas after closing quotes (but before next key)
        # Pattern: "value""key": -> "value", "key":
        json_str = re.sub(r'"(\s*)"([^"]+)":', r'",\1"\2":', json_str)
        
        # 2. Fix trailing commas before closing braces/brackets (do this early)
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # 4. Unterminated strings - find strings that don't have closing quotes
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
            last_colon = repaired.rfind(':')
            last_comma = repaired.rfind(',')
            last_brace = repaired.rfind('}')
            last_bracket = repaired.rfind(']')
            
            # If we have a colon and we're in a value context, close the string
            if last_colon > 0:
                if last_comma > last_colon or (last_brace > last_colon and last_comma < last_colon) or (last_bracket > last_colon and last_comma < last_colon):
                    repaired += '"'
                    in_string = False
                else:
                    repaired += '"'
                    in_string = False
            else:
                repaired += '"'
                in_string = False
        
        # Close unclosed braces/brackets
        open_braces = repaired.count('{') - repaired.count('}')
        open_brackets = repaired.count('[') - repaired.count(']')
        
        if open_braces > 0:
            repaired += '}' * open_braces
        if open_brackets > 0:
            repaired += ']' * open_brackets
        
        # Fix trailing commas again (in case we added some)
        repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)
        
        # Fix double commas (comma after comma)
        repaired = re.sub(r',\s*,', r',', repaired)
        
        # Fix missing commas between array/object elements more aggressively
        # Look for patterns like: }"key" or ]"key" or }"value" (should have comma)
        repaired = re.sub(r'}(\s*)"([^"]+)":', r'},\1"\2":', repaired)
        repaired = re.sub(r'](\s*)"([^"]+)":', r'],\1"\2":', repaired)
        
        # More aggressive comma fixing using regex patterns
        # These patterns are safer because they work on the already-processed string
        
        # Pattern 1: "value" followed by "key": (missing comma between object properties)
        # Look for: "text" followed by whitespace then "key":
        # But be careful - only match when we're clearly between object properties
        # Pattern: "..." followed by whitespace and "key": where key doesn't start with special chars
        final_repaired = re.sub(r'"([^"]*)"\s+"([a-zA-Z_][^"]*)":', r'"\1", "\2":', repaired)
        
        # Pattern 2: } or ] followed by "key": (missing comma before next property)
        final_repaired = re.sub(r'([}\]])"([^"]+)":', r'\1, "\2":', final_repaired)
        
        # Pattern 3: "value" followed by { or [ (missing comma before object/array)
        final_repaired = re.sub(r'"([^"]*)"\s*([{\[])', r'"\1", \2', final_repaired)
        
        # Pattern 4: } or ] followed by { or [ (missing comma between objects/arrays)
        final_repaired = re.sub(r'([}\]])"([^"]+)":', r'\1, "\2":', final_repaired)
        final_repaired = re.sub(r'([}\]])"([^"]+)":', r'\1, "\2":', final_repaired)  # Run twice for nested cases
        
        # Pattern 5: Number or boolean followed by "key": (missing comma)
        final_repaired = re.sub(r'([0-9.]+|true|false|null)\s+"([^"]+)":', r'\1, "\2":', final_repaired)
        
        # Pattern 6: } or ] followed by "key": (missing comma - more aggressive)
        # This handles cases where a closing brace/bracket is immediately followed by a new key
        final_repaired = re.sub(r'([}\]])"([^"]+)":', r'\1, "\2":', final_repaired)
        
        # Pattern 7: Missing comma in arrays - "value" followed by "value" (array of strings)
        # But only when we're clearly in an array context (after [ or ,)
        final_repaired = re.sub(r'(\[|,)\s*"([^"]+)"\s+"([^"]+)"', r'\1 "\2", "\3"', final_repaired)
        
        # Pattern 8: Missing comma between object properties - more sophisticated
        # Look for: "key": "value" followed by "key": (missing comma)
        # This is tricky because we need to ensure we're not inside a string value
        # Use a state machine approach for this
        state_machine_repaired = ""
        in_string = False
        escape_next = False
        i = 0
        
        while i < len(final_repaired):
            char = final_repaired[i]
            
            if escape_next:
                state_machine_repaired += char
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                escape_next = True
                state_machine_repaired += char
                i += 1
                continue
            
            if char == '"':
                in_string = not in_string
                state_machine_repaired += char
            elif not in_string:
                # We're outside a string - check for missing comma patterns
                # Pattern: "value" followed by whitespace and "key":
                if (i + 1 < len(final_repaired) and 
                    char == '"' and 
                    i > 0 and final_repaired[i-1] in [':', ',', '[', '{']):
                    # Check if next is a quote (start of new key)
                    j = i + 1
                    while j < len(final_repaired) and final_repaired[j] in [' ', '\t', '\n']:
                        j += 1
                    if j < len(final_repaired) and final_repaired[j] == '"':
                        # Missing comma - add it
                        state_machine_repaired += '", "'
                        # Skip the quote we just added
                        i = j
                        continue
                state_machine_repaired += char
            else:
                state_machine_repaired += char
            
            i += 1
        
        final_repaired = state_machine_repaired
        
        # Fix any double commas we might have created
        final_repaired = re.sub(r',\s*,', r',', final_repaired)
        
        # Fix trailing commas before closing braces/brackets one more time
        final_repaired = re.sub(r',(\s*[}\]])', r'\1', final_repaired)
        
        return final_repaired
    
    def _extract_data_from_broken_json(self, json_str: str) -> Optional[Dict]:
        """
        Try to extract usable data from broken JSON by parsing it manually.
        This is a last resort before falling back to the fallback script generator.
        """
        try:
            result = {}
            
            # Try to extract script field
            script_match = re.search(r'"script"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', json_str, re.DOTALL)
            if not script_match:
                # Try with escaped quotes
                script_match = re.search(r'"script"\s*:\s*"((?:[^"\\]|\\.)*)"', json_str, re.DOTALL)
            if script_match:
                script_text = script_match.group(1)
                # Unescape JSON string
                script_text = script_text.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
                result['script'] = script_text
                print(f"    ✅ Extracted script text ({len(script_text)} chars)")
            
            # Try to extract segments array - look for segment objects
            segments = []
            # Pattern: find segment objects with text, duration, etc.
            segment_pattern = r'\{\s*"text"\s*:\s*"([^"]*(?:\\.[^"]*)*)"\s*,\s*"duration"\s*:\s*(\d+(?:\.\d+)?)'
            segment_matches = re.finditer(segment_pattern, json_str, re.DOTALL)
            
            current_time = 0
            for i, match in enumerate(segment_matches):
                try:
                    text = match.group(1)
                    duration = float(match.group(2))
                    # Unescape JSON string
                    text = text.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
                    
                    # Try to extract more fields if available
                    segment_obj = {
                        'text': text,
                        'duration': duration,
                        'start_time': current_time,
                        'type': 'content',
                        'section': (i // 3) + 1,
                        'section_title': f"Section {(i // 3) + 1}"
                    }
                    
                    # Try to extract type, section, etc. from surrounding context
                    segment_start = match.start()
                    segment_end = min(segment_start + 500, len(json_str))
                    segment_context = json_str[segment_start:segment_end]
                    
                    type_match = re.search(r'"type"\s*:\s*"([^"]+)"', segment_context)
                    if type_match:
                        segment_obj['type'] = type_match.group(1)
                    
                    section_match = re.search(r'"section"\s*:\s*(\d+)', segment_context)
                    if section_match:
                        segment_obj['section'] = int(section_match.group(1))
                    
                    section_title_match = re.search(r'"section_title"\s*:\s*"([^"]+)"', segment_context)
                    if section_title_match:
                        segment_obj['section_title'] = section_title_match.group(1)
                    
                    segments.append(segment_obj)
                    current_time += duration
                except Exception as e:
                    print(f"    ⚠️  Error extracting segment {i}: {e}")
                    continue
            
            if segments:
                result['segments'] = segments
                print(f"    ✅ Extracted {len(segments)} segments from broken JSON")
                
                # Normalize durations to match target if we have a target
                # For now, just return what we have
                return result
            elif 'script' in result:
                # If we have script but no segments, try to split script into segments
                print(f"    💡 Splitting script into segments...")
                script_text = result['script']
                words = script_text.split()
                words_per_segment = max(50, len(words) // 10)  # ~10 segments
                
                segments = []
                current_time = 0
                for i in range(0, len(words), words_per_segment):
                    segment_words = words[i:i + words_per_segment]
                    segment_text = ' '.join(segment_words)
                    duration = len(segment_words) / 2.5  # 2.5 words per second
                    
                    segments.append({
                        'text': segment_text,
                        'duration': max(20, round(duration)),
                        'start_time': current_time,
                        'type': 'content',
                        'section': (i // words_per_segment) + 1,
                        'section_title': f"Section {(i // words_per_segment) + 1}"
                    })
                    current_time += segments[-1]['duration']
                
                result['segments'] = segments
                print(f"    ✅ Created {len(segments)} segments from script text")
                return result
            
            return None
            
        except Exception as e:
            print(f"    ⚠️  Error extracting data from broken JSON: {e}")
            return None
    
    def _generate_image_prompts(self, segments: List[Dict], articles: List[Dict], topic: str) -> List[str]:
        """Generate detailed image prompts for each segment"""
        prompts = []
        
        for i, segment in enumerate(segments):
            segment_text = segment.get('text', '')
            segment_type = segment.get('type', 'key_point')
            section_title = segment.get('section_title', f"Section {segment.get('section', 1)}")
            
            prompt = f"""Create a detailed image generation prompt (80-150 words) for an editorial news video segment with dramatic, stylized visuals.

Topic: {topic}
Section: {section_title}
Segment Type: {segment_type}
Content: {segment_text[:200]}

Create a comprehensive visual description that:
- Uses CONCEPT ILLUSTRATION style - editorial, dramatic, stylized art (NOT photorealistic)
- Uses VISUAL METAPHORS and SYMBOLS instead of literal representations of people
- Uses SATIRICAL or EDITORIAL art styles (stylized, expressive, dramatic illustrations)
- AVOIDS photorealistic faces or actual people - use silhouettes, abstract figures, symbolic representations, or focus on objects/scenes
- Describes the scene, composition, lighting, colors, mood in editorial/artistic terms
- Makes it feel editorial and dramatic, not fake - audiences accept stylized illustrations for news
- Optimized for landscape video format (16:9 aspect ratio)
- ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO SIGNS, NO LABELS - purely visual imagery only
- AVOID any text elements: no headlines, no captions, no signs, no banners, no text overlays, no written words of any kind
- Focus on visual storytelling through imagery, symbols, colors, composition, and mood only

Focus on:
- CONCEPT ILLUSTRATIONS: Use symbolic, metaphorical, or abstract visual representations
- EDITORIAL ART STYLE: Stylized, dramatic, expressive illustrations
- VISUAL METAPHORS: Represent concepts through symbols, objects, scenes, compositions
- AVOID photorealistic people: Use silhouettes, abstract human forms, symbolic figures, or focus on objects/scenes
- PURELY VISUAL: Describe only visual elements - shapes, colors, lighting, composition, mood, atmosphere
- NO TEXT: Never mention text, words, letters, numbers, signs, labels, or any written elements in the image

Return ONLY the image prompt text, 80-150 words, nothing else."""
            
            try:
                # Use unified LLM client with fallback
                response = self.llm_client.generate(prompt, {"temperature": 0.7, "num_predict": 300})
                image_prompt = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
                image_prompt = re.sub(r'<[^>]+>', '', image_prompt)
                image_prompt = ' '.join(image_prompt.split())
                
                if len(image_prompt) < 50:
                    image_prompt = f"Professional news broadcast scene depicting: {segment_text[:100]}. Realistic, detailed visual representation with appropriate lighting, composition, and atmosphere."
                
                prompts.append(image_prompt)
            except:
                prompts.append(f"Professional news broadcast scene: {topic}. {section_title}.")
        
        return prompts
    
    def _create_fallback_script(self, topic: str, articles: List[Dict], duration: int) -> Dict:
        """Create fallback extended script if Ollama fails - generates proper 10-minute content"""
        segments = []
        image_prompts = []
        current_time = 0
        
        # Check if hooks are enabled
        from config import USE_HOOK_BASED_HEADLINES
        use_hooks = USE_HOOK_BASED_HEADLINES
        
        # Introduction (45 seconds) - Natural news anchor style with hooks if enabled
        if use_hooks:
            intro_text = f"Wait, this just happened - breaking news tonight: {topic}. This is a developing story that's captured global attention. Here's what we know so far, and why this matters."
        else:
            intro_text = f"Breaking news tonight: {topic}. This is a developing story that's captured global attention. Here's what we know so far, and why this matters."
        intro_duration = 45
        segments.append({
            'text': intro_text,
            'duration': intro_duration,
            'start_time': current_time,
            'type': 'introduction',
            'section': 1,
            'section_title': 'Introduction'
        })
        image_prompts.append(f"Breaking news scene about {topic}. Professional news broadcast setting with dramatic lighting")
        current_time += intro_duration
        
        # Main sections - divide remaining time properly
        remaining_time = duration - intro_duration - 45  # Reserve 45s for conclusion
        num_sections = min(8, len(articles))  # More sections for 10-minute video
        time_per_section = remaining_time // num_sections
        
        # Create ONE CONNECTED STORY from all articles
        # Combine all articles into a unified narrative
        all_text = []
        for article in articles[:num_sections]:
            title = article.get('title', '')
            desc = article.get('description', '') or ''
            if title and desc:
                all_text.append(f"{title}. {desc}")
        
        combined_content = ' '.join(all_text)
        
        # Divide into connected story parts
        part_names = ['The Beginning', 'The Escalation', 'Current Situation', 'Ripple Effects']
        num_parts = min(4, len(part_names))
        time_per_part = remaining_time // num_parts
        chars_per_part = len(combined_content) // num_parts
        
        for i in range(num_parts):
            part_start = i * chars_per_part
            part_end = (i + 1) * chars_per_part if i < num_parts - 1 else len(combined_content)
            part_content = combined_content[part_start:part_end]
            
            # Create connected narrative segments
            num_segments_per_part = 3
            segment_duration = time_per_part // num_segments_per_part
            
            for j in range(num_segments_per_part):
                seg_start = j * (len(part_content) // num_segments_per_part)
                seg_end = (j + 1) * (len(part_content) // num_segments_per_part) if j < num_segments_per_part - 1 else len(part_content)
                seg_content = part_content[seg_start:seg_end]
                
                # Add natural transitions with hooks if enabled
                if use_hooks:
                    if i == 0 and j == 0:
                        seg_text = f"Wait, this just happened - breaking news: {topic}. This story began when {seg_content[:250]}"
                    elif j == 0:
                        # Use hooks at section transitions (every 2-3 segments)
                        if i % 2 == 0:
                            hook_transitions = ["Breaking right now - as this developed,", "You won't believe this - this led to", "Wait, this just changed - meanwhile,", "This is huge - in response,"]
                            seg_text = f"{hook_transitions[i % len(hook_transitions)]} {seg_content[:250]}"
                        else:
                            transitions = ["As this developed,", "This led to", "Meanwhile,", "In response,"]
                            seg_text = f"{transitions[i % len(transitions)]} {seg_content[:250]}"
                    else:
                        # Use hooks occasionally in middle segments
                        if (i + j) % 3 == 0:
                            hook_transitions = ["The situation escalated when", "Breaking right now - further developments show", "This is huge - this has affected", "You need to know - looking at the broader impact,"]
                            seg_text = f"{hook_transitions[(i + j) % len(hook_transitions)]} {seg_content[:250]}"
                        else:
                            transitions = ["The situation escalated when", "Further developments show", "This has affected", "Looking at the broader impact,"]
                            seg_text = f"{transitions[j % len(transitions)]} {seg_content[:250]}"
                else:
                    # Original transitions without hooks
                    if i == 0 and j == 0:
                        seg_text = f"Breaking news: {topic}. This story began when {seg_content[:250]}"
                    elif j == 0:
                        transitions = ["As this developed,", "This led to", "Meanwhile,", "In response,"]
                        seg_text = f"{transitions[i % len(transitions)]} {seg_content[:250]}"
                    else:
                        transitions = ["The situation escalated when", "Further developments show", "This has affected", "Looking at the broader impact,"]
                        seg_text = f"{transitions[j % len(transitions)]} {seg_content[:250]}"
                
                actual_duration = max(segment_duration, 20)
                segments.append({
                    'text': seg_text,
                    'duration': actual_duration,
                    'start_time': current_time,
                    'type': 'content',
                    'section': i + 1,
                    'section_title': part_names[i] if i < len(part_names) else f"Part {i+1}"
                })
                image_prompts.append(f"Professional news broadcast scene depicting: {topic}. Detailed visual representation with appropriate lighting, composition, and atmosphere")
                current_time += actual_duration
        
        # Conclusion (45 seconds)
        conclusion_text = f"That's our comprehensive coverage of {topic}. We've examined the key developments, their implications, and what to expect next. Stay informed and stay safe."
        segments.append({
            'text': conclusion_text,
            'duration': 45,
            'start_time': current_time,
            'type': 'conclusion',
            'section': num_sections + 2,
            'section_title': 'Conclusion'
        })
        image_prompts.append("News broadcast closing scene. Professional news studio setting")
        
        # Normalize to exact duration
        total = sum(s['duration'] for s in segments)
        if total != duration:
            diff = duration - total
            segments[-1]['duration'] += diff
        
        # Recalculate start times
        current_time = 0
        for segment in segments:
            segment['start_time'] = current_time
            current_time += segment['duration']
        
        return {
            'title': f"Breaking: {topic} - Complete Analysis",
            'script': ' '.join([s['text'] for s in segments]),
            'segments': segments,
            'image_prompts': image_prompts
        }


def generate_extended_video(topic: str, articles: List[Dict], duration: int = 600, content_style: str = "newsy"):
    """
    Generate extended 10-minute video for a HOT TOPIC ONLY
    This function should only be called for topics that have been verified as hot
    This is a standalone function that doesn't modify existing code
    """
    print("=" * 60)
    print(f"Generating Extended {duration//60}-Minute Video")
    print(f"Topic: {topic}")
    print("=" * 60)
    
    # Step 1: Generate extended script
    print("\n[1/6] Generating extended script...")
    print(f"  📝 Content Style: {content_style.upper()}")
    ext_generator = ExtendedContentGenerator()
    script_data = ext_generator.generate_extended_script(topic, articles, duration, content_style=content_style)
    print(f"Title: {script_data.get('title', 'Untitled')}")
    print(f"Total segments: {len(script_data.get('segments', []))}")
    
    # Step 2: Generate images (16:9 landscape format for extended videos)
    print("\n[2/6] Generating images for extended video (16:9 landscape format)...")
    image_gen = ImageGenerator()
    image_prompts = script_data.get('image_prompts', [])
    
    print(f"  📸 Generating {len(image_prompts)} images in 16:9 format...")
    image_paths = image_gen.generate_images_for_segments(image_prompts, aspect_ratio="16:9")
    print(f"✅ Generated {len(image_paths)} images")
    
    # Step 3: Generate TTS audio
    print("\n[3/6] Generating text-to-speech audio...")
    tts = TTSGenerator()
    segments = script_data.get('segments', [])
    
    # Generate segmented audio with target duration
    audio_files = []
    segment_timings = []
    current_time = 0
    
    for i, segment in enumerate(segments):
        text = segment.get('text', '')
        expected_duration = segment.get('duration', 30)
        
        if text:
            segment_file = tts.generate_audio(text, f"extended_segment_{i}.mp3")
            if segment_file:
                from pydub import AudioSegment
                audio_seg = AudioSegment.from_mp3(segment_file)
                actual_duration_sec = len(audio_seg) / 1000.0
                
                # Use actual audio duration - don't slow down or stretch
                audio_files.append((segment_file, audio_seg))
                segment_timings.append({
                    'index': i,
                    'start_time': current_time,
                    'duration': actual_duration_sec,
                    'text': text
                })
                current_time += actual_duration_sec
                print(f"  Segment {i+1}: {actual_duration_sec:.1f}s (expected: {expected_duration:.1f}s)")
    
    # Combine audio
    if audio_files:
        from pydub import AudioSegment
        combined = AudioSegment.empty()
        for _, audio_seg in audio_files:
            combined += audio_seg
        
        # Normalize to target duration if needed
        actual_duration_ms = len(combined)
        target_duration_ms = duration * 1000
        
        print(f"  📊 Audio duration: {actual_duration_ms/1000:.1f}s, target: {target_duration_ms/1000:.1f}s")
        
        # Use actual audio duration - don't slow down, stretch, or add silence
        # It's okay if the video is shorter than the target duration
        if actual_duration_ms > target_duration_ms + 5000:
            # Only trim if significantly over (more than 5 seconds)
            print(f"  ⚠️  Audio is too long, trimming to {target_duration_ms/1000:.1f}s")
            combined = combined[:target_duration_ms]
            if segment_timings:
                actual_duration_s = len(combined) / 1000
                total_so_far = sum(s['duration'] for s in segment_timings[:-1])
                segment_timings[-1]['duration'] = max(15, actual_duration_s - total_so_far)
        else:
            # Use actual duration - it's okay if shorter than target
            print(f"  ✅ Using actual audio duration ({actual_duration_ms/1000:.1f}s) - video will match audio length")
            # Update target duration to match actual
            target_duration_ms = actual_duration_ms
        
        audio_path = os.path.join(TEMP_DIR, "extended_audio.mp3")
        combined.export(audio_path, format="mp3")
        print(f"Generated audio: {audio_path} ({len(combined)/1000:.1f}s)")
    else:
        print("Failed to generate audio")
        return None
    
    # Update script_data with actual timings
    for i, timing in enumerate(segment_timings):
        if i < len(script_data['segments']):
            script_data['segments'][i]['start_time'] = timing['start_time']
            script_data['segments'][i]['duration'] = timing['duration']
    
    # Step 4: Create video (16:9 landscape format for extended videos)
    print("\n[4/6] Creating extended video (16:9 landscape format)...")
    video_gen = VideoGenerator(is_extended=True)  # Use 16:9 format
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
    output_filename = f"extended_{safe_topic}_{timestamp}.mp4"
    video_path = video_gen.create_video(image_paths, audio_path, script_data, output_filename, segment_timings, is_extended=True)
    
    if video_path:
        print(f"\n✅ Success! Extended video saved to: {video_path}")
        return video_path
    else:
        print("\n❌ Failed to create video.")
        return None


def auto_detect_and_generate():
    """
    Automatically detect very hot topics and generate extended videos
    Searches GLOBALLY (not just India) and prioritizes engagement
    """
    print("=" * 60)
    print("Auto-Detecting Very Hot Topics (GLOBAL SEARCH)")
    print("=" * 60)
    
    # Step 1: Fetch GLOBAL news (not India-specific)
    print("\n[1/4] Fetching global news...")
    detector = HotTopicDetector(news_api_key=NEWS_API_KEY)
    
    all_articles = []
    
    # Fetch global headlines from NewsAPI - Multiple queries for more articles
    # Filter to last 10 days only
    cutoff_date = datetime.now() - timedelta(days=DAYS_BACK)
    from_date = cutoff_date.strftime('%Y-%m-%d')
    
    if NEWS_API_KEY:
        try:
            # Fetch from multiple categories to get more articles
            categories = ['general', 'world', 'business', 'technology']
            for category in categories:
                try:
                    url = "https://newsapi.org/v2/top-headlines"
                    params = {
                        "apiKey": NEWS_API_KEY,
                        "language": "en",
                        "pageSize": 50,
                        "category": category,
                        # Note: top-headlines doesn't support date filtering, but we'll filter manually
                        # NO country = global
                    }
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        for article in data.get("articles", []):
                            published = article.get("publishedAt", "")
                            # Filter by date: only last 10 days
                            if detector._is_within_days(published, DAYS_BACK):
                                # Clean HTML and URLs
                                clean_title = detector._clean_text(article.get("title", ""))
                                clean_desc = detector._clean_text(article.get("description", ""))
                                if clean_title:  # Only add if title exists
                                    all_articles.append({
                                        "title": clean_title,
                                        "description": clean_desc,
                                        "link": article.get("url", ""),
                                        "published": published,
                                        "source": article.get("source", {}).get("name", ""),
                                    })
                except Exception as e:
                    # Continue with other categories if one fails
                    pass
        except Exception as e:
            print(f"Error fetching global headlines: {e}")
    
    # Also fetch from global RSS feeds - Expanded list for 200-500 articles
    try:
        import feedparser
        rss_feeds = [
            # Major International News
            "http://feeds.bbci.co.uk/news/rss.xml",
            "http://feeds.bbci.co.uk/news/world/rss.xml",
            "http://feeds.bbci.co.uk/news/business/rss.xml",
            "http://feeds.bbci.co.uk/news/technology/rss.xml",
            "http://rss.cnn.com/rss/edition.rss",
            "http://rss.cnn.com/rss/edition_world.rss",
            "http://rss.cnn.com/rss/money_latest.rss",
            "http://rss.cnn.com/rss/edition_technology.rss",
            "http://feeds.reuters.com/reuters/topNews",
            "http://feeds.reuters.com/reuters/worldNews",
            "http://feeds.reuters.com/reuters/businessNews",
            "http://feeds.reuters.com/reuters/technologyNews",
            "https://www.theguardian.com/world/rss",
            "https://www.theguardian.com/business/rss",
            "https://www.theguardian.com/technology/rss",
            "https://www.theguardian.com/politics/rss",
            "https://feeds.npr.org/1001/rss.xml",
            "https://feeds.npr.org/1004/rss.xml",  # World
            "https://feeds.npr.org/1006/rss.xml",  # Business
            "https://feeds.npr.org/1019/rss.xml",  # Technology
            
            # US News Sources
            "https://feeds.foxnews.com/foxnews/latest",
            "https://feeds.foxnews.com/foxnews/world",
            "https://feeds.foxnews.com/foxnews/politics",
            "https://www.nbcnews.com/rss.xml",
            "https://www.nbcnews.com/world/rss.xml",
            "https://www.nbcnews.com/business/rss.xml",
            "https://abcnews.go.com/abcnews/topstories",
            "https://abcnews.go.com/abcnews/internationalheadlines",
            "https://abcnews.go.com/abcnews/usheadlines",
            "https://www.cbsnews.com/latest/rss/main",
            "https://www.cbsnews.com/latest/rss/world",
            "https://www.cbsnews.com/latest/rss/business",
            
            # International Sources
            "https://www.aljazeera.com/xml/rss/all.xml",
            "https://www.aljazeera.com/xml/rss/world.xml",
            "https://www.aljazeera.com/xml/rss/business.xml",
            "https://www.dw.com/en/rss/rss-top/rss.xml",
            "https://www.dw.com/en/rss/rss-world/rss.xml",
            "https://www.dw.com/en/rss/rss-business/rss.xml",
            "https://www.france24.com/en/rss",
            "https://www.france24.com/en/world/rss",
            "https://www.france24.com/en/business/rss",
            "https://www.euronews.com/rss?format=mrss",
            "https://www.euronews.com/rss?format=mrss&name=world",
            "https://www.euronews.com/rss?format=mrss&name=business",
            
            # Business & Finance
            "https://feeds.bloomberg.com/markets/news.rss",
            "https://feeds.bloomberg.com/politics/news.rss",
            "https://www.ft.com/rss/home",
            "https://www.ft.com/rss/world",
            "https://www.ft.com/rss/companies",
            "https://feeds.washingtonpost.com/rss/world",
            "https://feeds.washingtonpost.com/rss/business",
            "https://feeds.washingtonpost.com/rss/politics",
            
            # Technology
            "https://rss.cnn.com/rss/edition_technology.rss",
            "https://feeds.npr.org/1019/rss.xml",
            "https://www.theverge.com/rss/index.xml",
            "https://techcrunch.com/feed/",
            "https://www.wired.com/feed/rss",
            
            # Additional Major Sources
            "https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/section/world/rss.xml",
            "https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/section/business/rss.xml",
            "https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/section/technology/rss.xml",
            "https://www.latimes.com/world/rss2.0.xml",
            "https://www.latimes.com/business/rss2.0.xml",
            "https://www.usatoday.com/rss/",
            "https://www.usatoday.com/rss/world/",
            "https://www.usatoday.com/rss/money/",
            
            # Regional & Specialized
            "https://www.scmp.com/rss/3/feed",
            "https://www.scmp.com/rss/4/feed",
            "https://www.timesofisrael.com/feed/",
            "https://www.japantimes.co.jp/rss/news/",
            "https://www.japantimes.co.jp/rss/business/",
            "https://www.straitstimes.com/rss",
            "https://www.straitstimes.com/rss/world",
            "https://www.straitstimes.com/rss/business",
        ]
        
        print(f"  📡 Fetching from {len(rss_feeds)} RSS feeds...")
        successful_feeds = 0
        for feed_url in rss_feeds:
            try:
                feed = feedparser.parse(feed_url)
                # Fetch more entries per feed (50 instead of 20) to get 200-500 total articles
                # Filter to last 10 days only
                entries_fetched = 0
                import time
                for entry in feed.entries[:50]:
                    # feedparser provides both 'published' (string) and 'published_parsed' (time.struct_time)
                    # Use published_parsed if available (more reliable), otherwise use published string
                    published = entry.get('published_parsed') or entry.get('published', '')
                    # Filter by date: only last 10 days
                    if detector._is_within_days(published, DAYS_BACK):
                        # Clean HTML and URLs
                        clean_title = detector._clean_text(entry.get('title', ''))
                        clean_desc = detector._clean_text(entry.get('description', ''))
                        if clean_title:  # Only add if title exists
                            # Convert time.struct_time to string for storage
                            if isinstance(published, time.struct_time):
                                # Convert to ISO format string
                                published_str = datetime(*published[:6]).isoformat()
                            else:
                                published_str = str(published) if published else ''
                            
                            all_articles.append({
                                "title": clean_title,
                                "description": clean_desc,
                                "link": entry.get('link', ''),
                                "published": published_str,
                                "source": feed.feed.get('title', 'RSS Feed'),
                            })
                            entries_fetched += 1
                if entries_fetched > 0:
                    successful_feeds += 1
            except Exception as e:
                # Silently skip failed feeds to avoid spam
                pass
        
        print(f"  ✅ Successfully fetched from {successful_feeds}/{len(rss_feeds)} RSS feeds")
    except Exception as e:
        print(f"Error fetching RSS feeds: {e}")
    
    # Remove duplicates
    seen_titles = set()
    unique_articles = []
    for article in all_articles:
        title = article.get('title', '').lower()
        if title not in seen_titles and article.get('title'):
            seen_titles.add(title)
            unique_articles.append(article)
    
    print(f"  🌍 Found {len(unique_articles)} global articles")
    
    if not unique_articles:
        print("No articles found. Exiting.")
        return None
    
    # Step 2: Detect very hot topics (with engagement scoring)
    print("\n[2/4] Detecting very hot topics (prioritizing engagement)...")
    hot_topic = detector.detect_very_hot_topic(unique_articles, min_score=50)
    
    if not hot_topic:
        print("  ℹ️  No very hot topics detected. Score threshold not met.")
        print("  💡 Extended videos are ONLY generated for very hot topics (score ≥ 50)")
        print("  💡 Use regular 60-second video generation for normal news")
        return None
    
    print(f"\n🔥 VERY HOT TOPIC DETECTED - Generating Extended Video!")
    print(f"  Topic: {hot_topic['topic']}")
    print(f"  Hotness Score: {hot_topic['score']} (threshold: 50)")
    print(f"  Engagement Score: {hot_topic.get('engagement_score', 0)} related articles")
    print(f"  Keywords: {', '.join(hot_topic['keywords'])}")
    print(f"  Related articles: {len(hot_topic['related_articles'])}")
    print(f"  ✅ This topic qualifies for extended 10-minute deep-dive video")
    
    # Step 3: Fetch extended GLOBAL news coverage for HOTTEST topic
    print(f"\n[3/4] Fetching ALL relevant global news coverage...")
    extended_articles = detector.fetch_extended_news(hot_topic['topic'], limit=100)  # Fetch more
    print(f"  📰 Found {len(extended_articles)} additional global articles")
    
    # Combine ALL articles (related + extended)
    all_extended = hot_topic['related_articles'] + extended_articles
    seen_titles = set()
    unique_extended = []
    for article in all_extended:
        title = article.get('title', '').lower()
        if title not in seen_titles:
            seen_titles.add(title)
            unique_extended.append(article)
    
    print(f"  ✅ Total unique articles for comprehensive coverage: {len(unique_extended)}")
    print(f"  📊 Using ALL {len(unique_extended)} articles to generate comprehensive story")
    
    # Step 4: Generate extended video with ALL articles
    print(f"\n[4/4] Generating extended 10-minute video summarizing ALL articles...")
    # Get content style from config or default to newsy
    from config import CONTENT_STYLE
    content_style = CONTENT_STYLE
    return generate_extended_video(hot_topic['topic'], unique_extended, duration=600, content_style=content_style)  # Use ALL articles


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "auto":
            # Auto-detect and generate (ONLY for hot topics)
            auto_detect_and_generate()
        elif sys.argv[1] == "topic" and len(sys.argv) > 2:
            # Check if topic is actually hot before generating
            topic = sys.argv[2]
            print(f"Checking if '{topic}' is a hot topic...")
            
            detector = HotTopicDetector(news_api_key=NEWS_API_KEY)
            
            # Fetch global news to check topic hotness
            # Filter to last 10 days only
            cutoff_date = datetime.now() - timedelta(days=DAYS_BACK)
            from_date = cutoff_date.strftime('%Y-%m-%d')
            
            all_articles = []
            if NEWS_API_KEY:
                try:
                    url = "https://newsapi.org/v2/everything"
                    params = {
                        "apiKey": NEWS_API_KEY,
                        "q": topic,
                        "language": "en",
                        "sortBy": "popularity",
                        "pageSize": 50,
                        "from": from_date,  # Only articles from last 10 days
                    }
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        for article in data.get("articles", []):
                            published = article.get("publishedAt", "")
                            # Double-check date filter
                            if detector._is_within_days(published, DAYS_BACK):
                                all_articles.append({
                                    "title": article.get("title", ""),
                                    "description": article.get("description", ""),
                                    "link": article.get("url", ""),
                                    "published": published,
                                })
                except Exception as e:
                    print(f"Error fetching news: {e}")
            
            # Check if topic is hot
            hot_topic = detector.detect_very_hot_topic(all_articles, min_score=50)
            
            if hot_topic and hot_topic['score'] >= 50:
                print(f"✅ Topic '{topic}' is HOT (score: {hot_topic['score']})")
                print(f"   Engagement: {hot_topic.get('engagement_score', 0)} articles")
                # Fetch ALL relevant articles for comprehensive coverage
                extended_articles = detector.fetch_extended_news(topic, limit=100)
                all_articles = hot_topic['related_articles'] + extended_articles
                # Remove duplicates
                seen = set()
                unique_articles = []
                for a in all_articles:
                    title = a.get('title', '').lower()
                    if title not in seen:
                        seen.add(title)
                        unique_articles.append(a)
                print(f"   📊 Using {len(unique_articles)} articles for comprehensive story")
                from config import CONTENT_STYLE
                generate_extended_video(topic, unique_articles, duration=600, content_style=CONTENT_STYLE)
            else:
                print(f"❌ Topic '{topic}' is NOT hot enough for extended video")
                print(f"   Score: {hot_topic['score'] if hot_topic else 0} (minimum: 50)")
                print(f"   💡 Use regular 60-second video generation for this topic")
                print(f"   💡 Or wait for auto-detection to find hot topics")
        else:
            print("Usage:")
            print("  python extended_video_generator.py auto          # Auto-detect hot topics only")
            print("  python extended_video_generator.py topic <name> # Check if topic is hot, then generate")
            print("")
            print("Note: Extended videos are ONLY generated for very hot topics (score ≥ 50)")
    else:
        # Default: auto-detect
        print("Auto-detecting hot topics...")
        auto_detect_and_generate()

