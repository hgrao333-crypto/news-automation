# Import compatibility fix FIRST (before any packages that use importlib.metadata)
import compat_fix

import requests
import feedparser
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import json
import re
import time
import email.utils
import os
from llm_client import LLMClient

class NewsFetcher:
    """Fetches news from various sources for both niches"""
    
    def __init__(self, news_api_key: str = None, country: str = "in", use_gemini: bool = False):
        self.news_api_key = news_api_key
        self.country = country  # Default to India ('in')
        self.use_gemini = use_gemini  # Use Gemini with Google Search instead of RSS/NewsAPI
        if use_gemini:
            self.llm_client = LLMClient()
        
        # Indian news RSS feeds (prioritized: most reliable first)
        self.indian_rss_feeds = [
            "https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms",  # TOI Top Stories ✅
            "https://www.thehindu.com/news/national/feeder/default.rss",  # The Hindu National News ✅
            "https://feeds.feedburner.com/ndtvnews-top-stories",  # NDTV Top Stories ✅
            "https://indianexpress.com/section/india/feed/",  # Indian Express India News ✅
            "https://www.livemint.com/rss/news",  # Mint News ✅
            "https://zeenews.india.com/rss/india-national-news.xml",  # Zee News India ✅
            # Alternative feeds for problematic ones:
            "https://www.indiatoday.in/rss/1206578",  # India Today (alternative feed)
            "https://www.business-standard.com/rss/top-stories.rss",  # Business Standard (alternative)
            "https://www.firstpost.com/rss/feed",  # Firstpost (alternative)
            "https://www.news18.com/rss/india-news.xml",  # News18 (alternative)
            "https://www.deccanherald.com/rss/top-stories.rss",  # Deccan Herald (alternative)
            "https://www.outlookindia.com/rss/feed",  # Outlook (alternative)
            "https://www.thequint.com/rss/feed",  # The Quint (alternative)
            # Additional reliable sources:
            "https://www.hindustantimes.com/rss/topnews/rssfeed.xml",  # Hindustan Times
            "https://www.tribuneindia.com/rss/feed",  # Tribune India
        ]
        
        # International news RSS feeds (fallback)
        self.international_rss_feeds = [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://rss.cnn.com/rss/edition.rss",
            "https://feeds.reuters.com/reuters/topNews",
        ]
        
        # Use Indian feeds if country is India
        self.rss_feeds = self.indian_rss_feeds if country == "in" else self.international_rss_feeds
    
    def _is_likely_fabricated(self, article: Dict, today_date: str) -> bool:
        """
        Check if article is likely fabricated/hallucinated
        
        Args:
            article: Article dict
            today_date: Today's date in YYYY-MM-DD format
            
        Returns:
            True if article appears to be fabricated, False otherwise
        """
        # Check for suspicious URLs (fake URLs often have patterns like example.com, or very generic patterns)
        link = article.get('link', '')
        if link:
            suspicious_patterns = [
                'example.com',
                'test.com',
                'placeholder',
                'fake',
                # Check if URL looks like a real news site
            ]
            if any(pattern in link.lower() for pattern in suspicious_patterns):
                return True
            
            # Check if URL is from known Indian news sites (if not, might be fake)
            known_news_domains = [
                'ndtv.com', 'thehindu.com', 'indiatoday.in', 'hindustantimes.com',
                'timesofindia.indiatimes.com', 'indianexpress.com', 'livemint.com',
                'zeenews.india.com', 'business-standard.com', 'firstpost.com',
                'news18.com', 'deccanherald.com', 'outlookindia.com', 'thequint.com',
                'tribuneindia.com', 'barandbench.com', 'moneycontrol.com'
            ]
            if not any(domain in link.lower() for domain in known_news_domains):
                # Not from known news site - might be fabricated, but don't filter too aggressively
                # Just log a warning
                pass
        
        # Check for future dates (articles dated in the future are likely fabricated)
        published = article.get('published', '')
        if published:
            try:
                # Extract date from published string
                if 'T' in published:
                    article_date_str = published.split('T')[0]
                else:
                    article_date_str = published[:10]
                
                # Parse dates
                article_date = datetime.strptime(article_date_str, '%Y-%m-%d').date()
                today_date_obj = datetime.strptime(today_date, '%Y-%m-%d').date()
                
                # If article date is more than 1 day in the future, it's likely fabricated
                if article_date > today_date_obj:
                    days_ahead = (article_date - today_date_obj).days
                    if days_ahead > 1:
                        return True
            except:
                pass
        
        # Check for obviously incorrect statistics (like wrong GDP numbers)
        title = article.get('title', '').lower()
        description = article.get('description', '').lower()
        text = f"{title} {description}"
        
        # Known incorrect facts to filter out
        incorrect_facts = [
            # GDP-related - if it mentions a specific wrong GDP number
            # We'll be conservative and only filter if it's clearly wrong
        ]
        
        # Check for suspicious patterns that suggest fabrication
        # Very generic descriptions or titles
        if len(description) < 50 and 'announced' in description.lower():
            # Too generic, might be fabricated
            pass
        
        return False
    
    def _clean_html(self, text: str) -> str:
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
    
    def fetch_from_rss(self, feed_url: str, limit: int = 15, silent: bool = False) -> List[Dict]:
        """Fetch news from RSS feed with improved error handling
        
        Args:
            feed_url: URL of the RSS feed
            limit: Maximum number of articles to fetch
            silent: If True, suppress error messages (only show success)
        """
        try:
            # Feedparser can handle URLs directly
            feed = feedparser.parse(feed_url)
            articles = []
            
            # Check for feed errors - be more lenient with encoding issues
            if hasattr(feed, 'bozo') and feed.bozo:
                # Some feeds have minor encoding issues but still work
                # Only fail if there are no entries
                if not feed.entries:
                    if not silent:
                        feed_name = feed_url.split('/')[-1] if '/' in feed_url else feed_url
                        error_type = str(feed.bozo_exception) if hasattr(feed, 'bozo_exception') else 'parsing error'
                        # Only show critical errors, suppress minor encoding warnings
                        if 'not well-formed' not in error_type.lower() and 'mismatched tag' not in error_type.lower():
                            print(f"  ⚠️  RSS feed {feed_name}: {error_type[:60]}")
                    return []
            
            if not feed.entries:
                if not silent:
                    feed_name = feed_url.split('/')[-1] if '/' in feed_url else feed_url
                    print(f"  ⚠️  RSS feed {feed_name}: No entries found")
                return []
            
            for entry in feed.entries[:limit]:
                title = self._clean_html(entry.get("title", ""))
                description = self._clean_html(entry.get("summary", "") or entry.get("description", ""))
                if title:  # Only add if title exists
                    articles.append({
                        "title": title,
                        "description": description,
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                    })
            
            if articles:
                feed_name = feed_url.split('/')[-1] if '/' in feed_url else feed_url
                print(f"  ✅ Fetched {len(articles)} articles from {feed_name}")
            
            return articles
            
        except Exception as e:
            # Suppress verbose errors for common issues
            if not silent:
                feed_name = feed_url.split('/')[-1] if '/' in feed_url else feed_url
                error_msg = str(e)[:50]
                # Only show non-common errors
                if 'timeout' in error_msg.lower() or 'connection' in error_msg.lower():
                    print(f"  ⚠️  RSS feed {feed_name}: Connection error")
            return []
    
    def fetch_today_news(self, limit: int = 10, test_articles: List[Dict] = None) -> List[Dict]:
        """Fetch today's top news stories
        
        Args:
            limit: Maximum number of articles to return
            test_articles: Optional list of test articles to prepend (for testing)
        """
        # Use Gemini with Google Search if enabled
        if self.use_gemini:
            return self._fetch_news_with_gemini(limit=limit, test_articles=test_articles)
        
        all_articles = []
        
        # Add test articles first if provided (for testing)
        if test_articles:
            all_articles.extend(test_articles)
        
        # Fetch from RSS feeds
        # Calculate articles per feed: aim for 4x the limit to account for duplicates, filtering, and better selection
        # Distribute across all feeds, minimum 15 per feed to ensure good coverage and diversity
        articles_per_feed = max(15, (limit * 4) // len(self.rss_feeds) if self.rss_feeds else limit)
        print(f"  📡 Fetching from {len(self.rss_feeds)} RSS feeds ({articles_per_feed} articles per feed)...")
        
        successful_feeds = 0
        failed_feeds = 0
        
        for feed_url in self.rss_feeds:
            articles = self.fetch_from_rss(feed_url, limit=articles_per_feed, silent=True)
            if articles:
                all_articles.extend(articles)
                successful_feeds += 1
            else:
                failed_feeds += 1
        
        if failed_feeds > 0:
            print(f"  ⚠️  {failed_feeds} feed(s) failed or returned no articles (this is normal)")
        
        print(f"  📰 Total articles from RSS: {len(all_articles)}")
        
        # Fetch from NewsAPI if key is available
        if self.news_api_key:
            try:
                print(f"  🔑 Fetching from NewsAPI...")
                url = "https://newsapi.org/v2/top-headlines"
                params = {
                    "apiKey": self.news_api_key,
                    "language": "en",
                    "pageSize": limit,
                }
                # Add country parameter for Indian news
                if self.country == "in":
                    params["country"] = "in"  # India
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    newsapi_count = 0
                    for article in data.get("articles", []):
                        title = self._clean_html(article.get("title", ""))
                        if title:  # Only add if title exists
                            all_articles.append({
                                "title": title,
                                "description": self._clean_html(article.get("description", "")),
                                "link": article.get("url", ""),
                                "published": article.get("publishedAt", ""),
                            })
                            newsapi_count += 1
                    if newsapi_count > 0:
                        print(f"  ✅ Fetched {newsapi_count} articles from NewsAPI")
                    else:
                        print(f"  ⚠️  NewsAPI returned no articles with titles")
                else:
                    print(f"  ⚠️  NewsAPI returned status code {response.status_code}: {response.text[:200]}")
            except Exception as e:
                print(f"  ⚠️  Error fetching from NewsAPI: {e}")
        else:
            print(f"  ⚠️  No NewsAPI key provided, skipping NewsAPI")
        
        # Remove duplicates based on title
        seen_titles = set()
        unique_articles = []
        for article in all_articles:
            title = article.get("title", "").strip()
            if title and title.lower() not in seen_titles:
                seen_titles.add(title.lower())
                unique_articles.append(article)
        
        print(f"  📊 Total unique articles after deduplication: {len(unique_articles)}")
        
        # If no articles found, try international feeds as fallback
        if not unique_articles and self.country == "in":
            print(f"  🔄 No articles from Indian sources, trying international feeds as fallback...")
            articles_per_feed = max(15, (limit * 4) // len(self.international_rss_feeds) if self.international_rss_feeds else limit)
            for feed_url in self.international_rss_feeds:
                articles = self.fetch_from_rss(feed_url, limit=articles_per_feed)
                for article in articles:
                    title = article.get("title", "").strip()
                    if title and title.lower() not in seen_titles:
                        seen_titles.add(title.lower())
                        unique_articles.append(article)
            print(f"  📊 Total articles after fallback: {len(unique_articles)}")
        
        # Filter for India-related news if country is India
        if self.country == "in" and unique_articles:
            india_keywords = [
                'india', 'indian', 'delhi', 'mumbai', 'bangalore', 'chennai', 'kolkata', 'hyderabad', 'pune',
                'modi', 'bjp', 'congress', 'rbi', 'indian government', 'indian economy', 'indian rupee',
                'indian stock market', 'indian cricket', 'indian tech', 'indian startup',
                'maharashtra', 'karnataka', 'tamil nadu', 'gujarat', 'rajasthan', 'uttar pradesh',
                'west bengal', 'punjab', 'haryana', 'kerala', 'telangana', 'andhra pradesh',
                'bihar', 'madhya pradesh', 'odisha', 'assam', 'jammu', 'kashmir',
                'ahmedabad', 'jaipur', 'surat', 'lucknow', 'kanpur', 'nagpur', 'indore',
                'thane', 'bhopal', 'visakhapatnam', 'patna', 'vadodara', 'ghaziabad',
                'noida', 'gurgaon', 'faridabad', 'navi mumbai', 'greater noida'
            ]
            
            india_related = []
            for article in unique_articles:
                title = article.get('title', '').lower()
                description = article.get('description', '').lower()
                content = f"{title} {description}"
                
                # Check if article contains India-related keywords
                if any(keyword in content for keyword in india_keywords):
                    india_related.append(article)
            
            print(f"  🇮🇳 Filtered to {len(india_related)} India-related articles (from {len(unique_articles)} total)")
            
            # Return India-related articles, or all articles if none found (to avoid empty results)
            if india_related:
                return india_related[:limit]
            else:
                print("  ⚠️  No India-specific articles found, returning all articles")
                return unique_articles[:limit]
        
        return unique_articles[:limit] if unique_articles else []
    
    def fetch_hot_topic(self, topic: str = None, limit: int = 5) -> List[Dict]:
        """Fetch news about a specific hot topic"""
        if not topic:
            # Get trending topic from today's news
            today_news = self.fetch_today_news(limit=20)
            if today_news:
                # Simple heuristic: use the first article's main keywords
                topic = today_news[0]["title"].split()[0:3]  # First 3 words
                topic = " ".join(topic)
        
        all_articles = []
        
        # Search RSS feeds for topic-related articles
        for feed_url in self.rss_feeds:
            articles = self.fetch_from_rss(feed_url, limit=20)
            for article in articles:
                if topic.lower() in article["title"].lower() or topic.lower() in article["description"].lower():
                    all_articles.append(article)
        
        # Search NewsAPI if available
        if self.news_api_key:
            try:
                url = "https://newsapi.org/v2/everything"
                params = {
                    "apiKey": self.news_api_key,
                    "q": topic,
                    "language": "en",
                    "sortBy": "popularity",
                    "pageSize": limit,
                }
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    for article in data.get("articles", []):
                        all_articles.append({
                            "title": self._clean_html(article.get("title", "")),
                            "description": self._clean_html(article.get("description", "")),
                            "link": article.get("url", ""),
                            "published": article.get("publishedAt", ""),
                        })
            except Exception as e:
                print(f"Error fetching from NewsAPI: {e}")
        
        # Remove duplicates
        seen_titles = set()
        unique_articles = []
        for article in all_articles:
            title = article["title"].lower()
            if title not in seen_titles and article["title"]:
                seen_titles.add(title)
                unique_articles.append(article)
        
        return unique_articles[:limit]
    
    def _is_within_hours(self, published_date, hours: int = 12) -> bool:
        """Check if article is within the last N hours
        Handles various date formats: ISO strings, RFC 2822, feedparser time.struct_time
        """
        if not published_date:
            return False
        
        try:
            article_date = None
            
            # Handle feedparser's time.struct_time format (tuple-like object)
            if isinstance(published_date, time.struct_time):
                # feedparser returns time.struct_time
                article_date = datetime(*published_date[:6])
            elif hasattr(published_date, 'timetuple'):
                # Some datetime-like objects
                article_date = datetime(*published_date.timetuple()[:6])
            elif isinstance(published_date, str):
                # Try ISO format first (2024-11-30T12:00:00Z)
                if 'T' in published_date:
                    # ISO format - try to parse with timezone
                    try:
                        # Remove timezone info if present (Z or +00:00)
                        date_str = published_date.replace('Z', '').split('+')[0].split('-')[0]
                        if '.' in date_str:
                            date_str = date_str.split('.')[0]
                        article_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                    except:
                        # Fallback to date only
                        date_str = published_date.split('T')[0]
                        article_date = datetime.strptime(date_str, '%Y-%m-%d')
                else:
                    # Try RFC 2822 format (Mon, 30 Nov 2024 12:00:00 +0000)
                    try:
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
            
            # Check if within last N hours
            cutoff_time = datetime.now() - timedelta(hours=hours)
            return article_date >= cutoff_time
        except Exception as e:
            return False
    
    def fetch_last_12_hours_news(self, limit: int = 25, topic: str = None) -> List[Dict]:
        """Fetch news from the last 12 hours, optionally filtered by topic
        
        Args:
            limit: Maximum number of articles to return
            topic: Optional topic to filter articles by
        """
        all_articles = []
        
        # Fetch from RSS feeds
        print(f"  📡 Fetching from {len(self.rss_feeds)} RSS feeds (last 12 hours)...")
        for feed_url in self.rss_feeds:
            try:
                feed = feedparser.parse(feed_url)
                if hasattr(feed, 'bozo') and feed.bozo:
                    continue
                if not feed.entries:
                    continue
                
                for entry in feed.entries[:20]:  # Check more entries to find recent ones
                    published = entry.get("published", "") or entry.get("published_parsed")
                    if not published:
                        continue
                    
                    # Check if within last 12 hours
                    if not self._is_within_hours(published, hours=12):
                        continue
                    
                    title = self._clean_html(entry.get("title", ""))
                    description = self._clean_html(entry.get("summary", "") or entry.get("description", ""))
                    
                    if not title:
                        continue
                    
                    # Filter by topic if provided
                    if topic:
                        content = f"{title} {description}".lower()
                        if topic.lower() not in content:
                            continue
                    
                    all_articles.append({
                        "title": title,
                        "description": description,
                        "link": entry.get("link", ""),
                        "published": published,
                    })
            except Exception as e:
                continue
        
        print(f"  📰 Total articles from RSS (last 12 hours): {len(all_articles)}")
        
        # Fetch from NewsAPI if key is available
        if self.news_api_key:
            try:
                print(f"  🔑 Fetching from NewsAPI (last 12 hours)...")
                # Calculate time 12 hours ago
                from_time = (datetime.now() - timedelta(hours=12)).isoformat() + 'Z'
                
                if topic:
                    # Search for topic
                    url = "https://newsapi.org/v2/everything"
                    params = {
                        "apiKey": self.news_api_key,
                        "q": topic,
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": limit * 2,  # Fetch more to filter
                        "from": from_time,
                    }
                else:
                    # Get top headlines
                    url = "https://newsapi.org/v2/top-headlines"
                    params = {
                        "apiKey": self.news_api_key,
                        "language": "en",
                        "pageSize": limit * 2,
                    }
                    if self.country == "in":
                        params["country"] = "in"
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    newsapi_count = 0
                    for article in data.get("articles", []):
                        published = article.get("publishedAt", "")
                        if not published:
                            continue
                        
                        # Double-check date filter
                        if not self._is_within_hours(published, hours=12):
                            continue
                        
                        title = self._clean_html(article.get("title", ""))
                        if title:  # Only add if title exists
                            all_articles.append({
                                "title": title,
                                "description": self._clean_html(article.get("description", "")),
                                "link": article.get("url", ""),
                                "published": published,
                            })
                            newsapi_count += 1
                    if newsapi_count > 0:
                        print(f"  ✅ Fetched {newsapi_count} articles from NewsAPI (last 12 hours)")
            except Exception as e:
                print(f"  ⚠️  Error fetching from NewsAPI: {e}")
        
        # Remove duplicates based on title
        seen_titles = set()
        unique_articles = []
        for article in all_articles:
            title = article.get("title", "").strip()
            if title and title.lower() not in seen_titles:
                seen_titles.add(title.lower())
                unique_articles.append(article)
        
        print(f"  📊 Total unique articles (last 12 hours): {len(unique_articles)}")
        
        return unique_articles[:limit] if unique_articles else []
    
    def _fetch_news_with_gemini(self, limit: int = 10, test_articles: List[Dict] = None) -> List[Dict]:
        """Fetch today's news using Gemini with Google Search grounding
        
        This method uses Gemini to search the web for today's most important news
        and format it in the required structure.
        
        Args:
            limit: Maximum number of articles to return
            test_articles: Optional list of test articles to prepend (for testing)
        """
        all_articles = []
        
        # Add test articles first if provided (for testing)
        if test_articles:
            all_articles.extend(test_articles)
        
        print(f"  🤖 Using Gemini with Google Search to fetch today's news...")
        print(f"  ⏳ This may take 30-90 seconds (Google Search takes time)...")
        
        # Determine location context
        location_context = "India" if self.country == "in" else "worldwide"
        location_filter = "Indian news" if self.country == "in" else "international news"
        
        # Get current IST date/time
        from datetime import timezone, timedelta
        ist = timezone(timedelta(hours=5, minutes=30))
        ist_now = datetime.now(ist)
        today_ist = ist_now.strftime('%Y-%m-%d')
        current_time_ist = ist_now.strftime('%Y-%m-%d %H:%M IST')
        
        # Limit to maximum 10 articles - a normal person doesn't need more than 10 news per day
        max_articles = min(limit, 10)
        
        # Create prompt for Gemini
        # Gemini 2.5 Flash can automatically search the web when asked for current information
        prompt = f"""Use your web search capability to find REAL, VERIFIABLE news that happened TODAY ({today_ist}) in Indian Standard Time (IST) that an Indian needs to know to stay updated.

⚠️ CRITICAL: You MUST search the web for CURRENT, REAL-TIME information from REAL news sources.
⚠️ DO NOT use your training data, do not hallucinate, do not make up news.
⚠️ ONLY return news that you can VERIFY from actual news websites.
⚠️ If you cannot find real news from today, return FEWER stories (even 0) rather than making up news.

VERIFICATION REQUIREMENTS:
- All URLs must be from REAL, accessible news websites (NDTV, The Hindu, India Today, etc.)
- All dates must match TODAY ({today_ist}) - do not use future dates
- All numbers and statistics must be ACCURATE (e.g., if mentioning GDP, verify the actual current rate)
- Cross-reference facts with multiple sources when possible
- If a story cannot be verified, DO NOT include it

CRITICAL: A normal person in India doesn't need more than 10 news stories per day to stay updated. Return MAXIMUM {max_articles} stories (can be fewer if there aren't that many important stories today, but never more than {max_articles}).

🎯 YOUR TASK: Choose WISELY which news to report to keep everyone updated. Be SELECTIVE and PRIORITIZE quality over quantity.

Think like a news editor: What are the {max_articles} most important stories that someone MUST know today to be well-informed? Don't just list everything - be strategic and choose only what truly matters.

CRITICAL SELECTION CRITERIA - Only include news that meets BOTH conditions:

1. HIGH PEOPLE INTEREST (What Indians are actually talking about/searching for):
   - Trending topics on social media, news platforms, search engines
   - Stories that affect large numbers of people
   - Topics that generate public discussion and engagement
   - News that people actively want to know about

2. HIGH IMPORTANCE (What actually matters):
   - Breaking news with significant impact on daily life, economy, or society
   - Policy changes, government decisions, regulatory updates
   - Economic developments affecting jobs, prices, investments
   - Major events affecting health, education, infrastructure
   - Critical developments in technology, business, politics
   - Stories that will have lasting consequences

EXCLUDE:
- Minor updates or follow-ups to old stories
- Celebrity gossip or entertainment news (unless it's a major scandal)
- Sports news (unless it's a major tournament win or significant development)
- Opinion pieces or analysis (only factual news)
- Duplicate stories covering the same event
- Stories from previous days (only TODAY's news)

SELECTION STRATEGY:
1. First, identify ALL potential important news from today
2. Then, CAREFULLY EVALUATE each story against the criteria below
3. RANK them by: (a) How many people it affects, (b) How significant the impact is, (c) How urgent/breaking it is
4. Choose WISELY - select only the TOP {max_articles} stories that truly keep people updated
5. If a story doesn't help someone stay informed about what matters, EXCLUDE it

Return ONLY the BARE MINIMUM - MAXIMUM {max_articles} most essential stories that meet BOTH high interest AND high importance criteria. If there are fewer than {max_articles} important stories today, return only those (quality over quantity).

Remember: Your goal is to keep everyone UPDATED, not overwhelmed. Choose stories that people NEED to know, not just what's available.

For each story, provide:
1. A clear, concise title (headline)
2. A detailed description (2-3 sentences explaining what happened, why it matters, and its impact on Indians)
3. The source URL/link where this news was published
4. The publication date/time in IST

Format your response as a JSON array with this exact structure:
[
  {{
    "title": "Clear headline of the news story",
    "description": "Detailed 2-3 sentence description explaining what happened, why it matters to Indians, and its impact",
    "link": "Source URL where this news was published",
    "published": "Publication date in ISO format (YYYY-MM-DDTHH:MM:SS+05:30) or {today_ist}"
  }},
  ...
]

CRITICAL REQUIREMENTS - FACT-CHECKING AND ACCURACY:
- ⚠️  DO NOT HALLUCINATE OR MAKE UP NEWS! Only return news that you can VERIFY from real sources
- ⚠️  DO NOT use training data or generate fake news - ONLY use REAL news from web search
- ⚠️  VERIFY all numbers, statistics, and facts before including them
- ⚠️  If you cannot find real, verifiable news from today, return FEWER stories (even 0) rather than making up news
- ⚠️  URLs must be REAL, accessible news website URLs (not fake URLs)
- ⚠️  Dates must be REALISTIC - do not use future dates or made-up dates
- ⚠️  If India's GDP is mentioned, verify the actual current rate (do not use outdated or incorrect numbers)
- ⚠️  Cross-reference facts with multiple sources when possible
- ⚠️  If a story seems suspicious or you cannot verify it, EXCLUDE it

ACCURACY REQUIREMENTS:
- All numbers and statistics must be ACCURATE and CURRENT
- All URLs must be REAL news website URLs that actually exist
- All dates must be REALISTIC and match today's date ({today_ist})
- If you cannot verify a story, DO NOT include it
- Quality and accuracy over quantity - better to return 3 accurate stories than 10 fake ones

⚠️ TOKEN LIMIT WARNING:
- Keep your response UNDER 8000 tokens (approximately 6000 words)
- Be CONCISE - keep descriptions to 2-3 sentences maximum per story
- Do NOT add explanations, comments, or extra text outside the JSON
- Keep titles short (under 100 characters)
- Keep descriptions brief (2-3 sentences, under 200 words each)
- Return ONLY the JSON array, no markdown, no code blocks, no explanations

Return ONLY valid JSON, no markdown, no explanations, no text before or after
- Start your response with [ and end with ]
- Ensure ALL stories are from TODAY ({today_ist}) in IST
- Return MAXIMUM {max_articles} stories (can be fewer if there aren't enough important stories, but never more than {max_articles})
- Keep descriptions concise (2-3 sentences max per story, under 200 words each)
- A normal person only needs up to {max_articles} stories per day to stay updated - quality over quantity
- CHOOSE WISELY: Select only news that truly helps people stay informed and updated
- Be SELECTIVE: Don't include stories just to fill the quota - only include what matters
- Prioritize stories that have REAL impact on people's lives, decisions, or understanding of current events
- Each story must meet BOTH high interest AND high importance criteria
- Prioritize stories that affect daily life, economy, jobs, health, education
- Focus on breaking news and major developments
- Each story must have: title, description, link, published
- Make descriptions explain why this matters to Indians specifically
- Ensure links are valid URLs from reputable Indian news sources

EXAMPLE OF CORRECT FORMAT (return exactly like this, no other text):
[
  {{
    "title": "Breaking: Major Policy Change Announced",
    "description": "The government announced a major policy change that affects millions of Indians. This will impact daily life, economy, and jobs significantly.",
    "link": "https://example.com/news/article1",
    "published": "{today_ist}T12:00:00+05:30"
  }},
  {{
    "title": "Economic Update: New Regulations",
    "description": "New economic regulations were introduced today that will affect businesses and consumers across India.",
    "link": "https://example.com/news/article2",
    "published": "{today_ist}T14:30:00+05:30"
  }}
]

DO NOT include:
- Any text before the opening [
- Any text after the closing ]
- Markdown code blocks (```json or ```)
- Explanations or comments
- Any other formatting

Return ONLY the JSON array starting with [ and ending with ] with MAXIMUM {max_articles} stories.

REMEMBER: 
- Choose WISELY - select only news that keeps everyone UPDATED
- Quality over quantity - return only the most essential stories (up to {max_articles})
- If there are fewer important stories today, return only those
- Never return more than {max_articles} stories
- Think like an editor: What does someone NEED to know today to stay informed?
- Be SELECTIVE and STRATEGIC in your choices"""

        try:
            # Use Gemini with Google Search grounding
            # Increase token limit to ensure complete responses (especially for news articles)
            response = self.llm_client.generate(
                prompt, 
                {
                    "temperature": 0.3,
                    "num_predict": 16384,  # Increased to 16384 to prevent truncation
                    "use_google_search": True  # Enable Google Search grounding
                }
            )
            
            content = response.get('response', '').strip() if isinstance(response, dict) else str(response).strip()
            
            print(f"  📝 Raw response length: {len(content)} characters")
            
            # Save raw response to file for analysis
            debug_dir = os.path.join("temp", "gemini_debug")
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            raw_response_file = os.path.join(debug_dir, f"gemini_raw_response_{timestamp}.txt")
            with open(raw_response_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  💾 Saved raw response to: {raw_response_file}")
            
            # Extract JSON from response - try multiple methods
            json_str = None
            
            # Method 1: Check for markdown code blocks
            if '```json' in content:
                parts = content.split('```json')
                if len(parts) > 1:
                    # Extract content between ```json and ```
                    extracted = parts[1].split('```')[0].strip()
                    if extracted:
                        json_str = extracted
                        print(f"  ✅ Found JSON in markdown code block (length: {len(json_str)} chars)")
            elif '```' in content:
                parts = content.split('```')
                # Look for JSON array pattern in code blocks
                for i, part in enumerate(parts):
                    part_stripped = part.strip()
                    if part_stripped.startswith('['):
                        json_str = part_stripped
                        # Check if it's complete (has closing bracket)
                        if ']' in part_stripped:
                            print(f"  ✅ Found complete JSON in code block (length: {len(json_str)} chars)")
                        else:
                            print(f"  ✅ Found incomplete JSON in code block (may be cut off, length: {len(json_str)} chars)")
                        break
            
            # Method 2: Find JSON array boundaries directly
            if not json_str:
                if '[' in content:
                    start_idx = content.find('[')
                    # Try to find matching closing bracket
                    bracket_count = 0
                    end_idx = start_idx
                    for i in range(start_idx, len(content)):
                        if content[i] == '[':
                            bracket_count += 1
                        elif content[i] == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end_idx = i + 1
                                break
                    
                    if end_idx > start_idx and bracket_count == 0:
                        json_str = content[start_idx:end_idx]
                        print(f"  ✅ Extracted complete JSON array from response")
                    elif start_idx < len(content):
                        # JSON might be incomplete (cut off), extract what we have and try to repair
                        json_str = content[start_idx:]
                        print(f"  ✅ Extracted incomplete JSON array (may be cut off, will try to repair)")
            
            # Method 3: Try to find any JSON object/array pattern
            if not json_str:
                # Look for JSON array pattern
                json_pattern = r'\[\s*\{[^\]]+\}\s*(?:,\s*\{[^\]]+\}\s*)*\]'
                match = re.search(json_pattern, content, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    print(f"  ✅ Found JSON using regex pattern")
            
            # Try to parse the JSON
            articles_data = None  # Initialize to track if we successfully parsed
            if json_str:
                # Save extracted JSON to file for analysis
                debug_dir = os.path.join("temp", "gemini_debug")
                os.makedirs(debug_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                json_extracted_file = os.path.join(debug_dir, f"gemini_extracted_json_{timestamp}.json")
                with open(json_extracted_file, 'w', encoding='utf-8') as f:
                    f.write(json_str)
                print(f"  💾 Saved extracted JSON to: {json_extracted_file}")
                
                try:
                    # Clean up common JSON issues
                    json_str = json_str.strip()
                    # Remove any trailing commas before closing brackets
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    
                    # Try parsing
                    articles_data = json.loads(json_str)
                    
                    # Ensure it's a list
                    if isinstance(articles_data, list):
                        print(f"  ✅ Successfully parsed JSON array ({len(articles_data)} items)")
                    elif isinstance(articles_data, dict):
                        articles_data = [articles_data]
                        print(f"  ✅ Successfully parsed JSON object, wrapped in array (1 item)")
                    else:
                        print(f"  ⚠️  Parsed JSON is not a list or dict: {type(articles_data)}")
                        articles_data = []
                    
                    # If we successfully parsed, process and return immediately
                    if articles_data:
                        try:
                            print(f"  🔍 Processing {len(articles_data)} parsed articles...")
                            for i, article_data in enumerate(articles_data):
                                if not isinstance(article_data, dict):
                                    print(f"    ⚠️  Article {i+1} is not a dict: {type(article_data)}")
                                    continue
                                
                                title = article_data.get('title', '').strip() if article_data.get('title') else ''
                                if not title:
                                    print(f"    ⚠️  Article {i+1} has no title. Keys: {list(article_data.keys())}")
                                    continue
                                
                                all_articles.append({
                                    "title": self._clean_html(title),
                                    "description": self._clean_html(article_data.get('description', '')),
                                    "link": article_data.get('link', ''),
                                    "published": article_data.get('published', datetime.now(ist).isoformat())
                                })
                                print(f"    ✅ Added article {i+1}: {title[:60]}...")
                            
                            print(f"  ✅ Gemini returned {len(all_articles)} news stories")
                            
                            # Remove duplicates and validate articles
                            seen_titles = set()
                            unique_articles = []
                            filtered_count = 0
                            
                            for article in all_articles:
                                title = article.get("title", "").strip().lower()
                                if not title or title in seen_titles:
                                    continue
                                
                                # Validate article - check for fabricated/hallucinated content
                                if self._is_likely_fabricated(article, today_ist):
                                    filtered_count += 1
                                    print(f"    ⚠️  Filtered out potentially fabricated article: {article.get('title', '')[:50]}...")
                                    continue
                                
                                seen_titles.add(title)
                                unique_articles.append(article)
                            
                            if filtered_count > 0:
                                print(f"  ⚠️  Filtered out {filtered_count} potentially fabricated articles")
                            
                            print(f"  📊 After deduplication and validation: {len(unique_articles)} unique stories")
                            result = unique_articles[:limit]
                            print(f"  ✅ Returning {len(result)} articles from Gemini")
                            return result
                        except Exception as process_err:
                            print(f"  ⚠️  Error processing articles: {process_err}")
                            import traceback
                            print(f"  📋 Error details: {traceback.format_exc()[:300]}")
                            # Don't raise - try to continue with what we have
                            if all_articles:
                                print(f"  ✅ Returning {len(all_articles)} articles despite processing error")
                                return all_articles[:limit]
                            # If no articles, continue to exception handler
                            articles_data = None
                    
                except json.JSONDecodeError as json_err:
                    print(f"  ⚠️  JSON parsing error: {json_err}")
                    print(f"  🔄 Attempting to repair JSON...")
                    
                    # Try to repair unterminated strings and other issues
                    try:
                        # Use the repair function from content_generator
                        from content_generator import ContentGenerator
                        generator = ContentGenerator()
                        repaired_json = generator._repair_json_string(json_str)
                        
                        # Save repaired JSON to file for analysis
                        if repaired_json != json_str:
                            debug_dir = os.path.join("temp", "gemini_debug")
                            os.makedirs(debug_dir, exist_ok=True)
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            json_repaired_file = os.path.join(debug_dir, f"gemini_repaired_json_{timestamp}.json")
                            with open(json_repaired_file, 'w', encoding='utf-8') as f:
                                f.write(repaired_json)
                            print(f"  💾 Saved repaired JSON to: {json_repaired_file}")
                        
                        if repaired_json != json_str:
                            parsed = json.loads(repaired_json)
                            # Ensure it's a list
                            if isinstance(parsed, list):
                                articles_data = parsed
                            elif isinstance(parsed, dict):
                                # If it's a single object, wrap it in a list
                                articles_data = [parsed]
                            else:
                                articles_data = []
                            
                            print(f"  ✅ Successfully parsed repaired JSON ({len(articles_data)} items)")
                            # Debug: show what we got
                            if articles_data:
                                first_item = articles_data[0]
                                print(f"  🔍 First item type: {type(first_item)}")
                                if isinstance(first_item, dict):
                                    print(f"  🔍 First item keys: {list(first_item.keys())}")
                                    print(f"  🔍 First item title: {first_item.get('title', 'MISSING')[:60]}")
                                else:
                                    print(f"  🔍 First item value: {str(first_item)[:100]}")
                        else:
                            raise ValueError("Repair didn't change JSON")
                    except Exception as repair_err:
                        print(f"  ❌ Could not repair with content_generator method: {repair_err}")
                        # Try manual repair for common issues
                        try:
                            # First, try to extract all complete objects from the JSON string
                            # Even if the array is incomplete, we can extract valid objects
                            articles_data = []
                            
                            # Find all complete JSON objects in the string
                            brace_count = 0
                            obj_start = -1
                            for i, char in enumerate(json_str):
                                if char == '{':
                                    if brace_count == 0:
                                        obj_start = i
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0 and obj_start != -1:
                                        # Found a complete object
                                        obj_str = json_str[obj_start:i+1]
                                        try:
                                            obj = json.loads(obj_str)
                                            if isinstance(obj, dict) and obj.get('title'):
                                                articles_data.append(obj)
                                        except:
                                            pass
                                        obj_start = -1
                            
                            if articles_data:
                                print(f"  ✅ Extracted {len(articles_data)} complete objects from malformed JSON")
                                # Limit to max_articles (10 max for daily update)
                                if len(articles_data) > max_articles:
                                    articles_data = articles_data[:max_articles]
                                    print(f"  📊 Limited to {max_articles} articles (max for daily update)")
                            else:
                                raise repair_err
                            # Fix unterminated strings by finding and closing them
                            # Look for patterns like: "text... (without closing quote)
                            lines = json_str.split('\n')
                            repaired_lines = []
                            in_string = False
                            escape_next = False
                            
                            for line in lines:
                                for char in line:
                                    if escape_next:
                                        escape_next = False
                                        repaired_lines.append(char)
                                        continue
                                    if char == '\\':
                                        escape_next = True
                                        repaired_lines.append(char)
                                        continue
                                    if char == '"':
                                        in_string = not in_string
                                    repaired_lines.append(char)
                                
                                # If we're still in a string at end of line, close it
                                if in_string:
                                    repaired_lines.append('"')
                                    in_string = False
                                repaired_lines.append('\n')
                            
                            repaired_json = ''.join(repaired_lines)
                            # Remove trailing commas
                            repaired_json = re.sub(r',\s*}', '}', repaired_json)
                            repaired_json = re.sub(r',\s*]', ']', repaired_json)
                            
                            articles_data = json.loads(repaired_json)
                            print(f"  ✅ Successfully parsed manually repaired JSON ({len(articles_data)} items)")
                        except Exception as manual_repair_err:
                            print(f"  ❌ Manual repair also failed: {manual_repair_err}")
                            # Last resort: try to extract individual valid objects
                            try:
                                articles_data = []
                                # Find all objects that look like articles by finding "title" fields
                                # Look for pattern: "title": "..." 
                                title_pattern = r'"title"\s*:\s*"([^"]+)"'
                                matches = list(re.finditer(title_pattern, json_str))
                                for match in matches:
                                    # Try to extract the full object starting before "title"
                                    start = max(0, match.start() - 50)  # Go back a bit to find {
                                    # Find the opening brace
                                    brace_start = json_str.rfind('{', 0, match.start())
                                    if brace_start == -1:
                                        continue
                                    
                                    # Find the closing brace
                                    brace_count = 0
                                    brace_end = brace_start
                                    for i in range(brace_start, min(brace_start + 2000, len(json_str))):
                                        if json_str[i] == '{':
                                            brace_count += 1
                                        elif json_str[i] == '}':
                                            brace_count -= 1
                                            if brace_count == 0:
                                                brace_end = i + 1
                                                break
                                    
                                    if brace_end > brace_start:
                                        try:
                                            obj_str = json_str[brace_start:brace_end]
                                            # Fix common issues in this object
                                            obj_str = re.sub(r',\s*}', '}', obj_str)
                                            obj_str = re.sub(r',\s*]', ']', obj_str)
                                            # Close any unterminated strings
                                            quote_count = obj_str.count('"')
                                            if quote_count % 2 != 0:
                                                obj_str = obj_str.rstrip().rstrip(',') + '"'
                                            obj = json.loads(obj_str)
                                            if isinstance(obj, dict) and obj.get('title'):
                                                articles_data.append(obj)
                                        except:
                                            continue
                                
                                if articles_data:
                                    print(f"  ✅ Extracted {len(articles_data)} valid articles from partial JSON")
                                else:
                                    raise manual_repair_err
                            except Exception as extract_err:
                                print(f"  ❌ Could not extract articles: {extract_err}")
                                raise json_err  # Re-raise original error
                    
                    # This code should not be reached if parsing succeeded above
                    # But keeping it as fallback for the repair path
                    if articles_data:
                        print(f"  🔍 Processing {len(articles_data)} parsed articles (from repair path)...")
                        for i, article_data in enumerate(articles_data):
                            if not isinstance(article_data, dict):
                                print(f"    ⚠️  Article {i+1} is not a dict: {type(article_data)}")
                                continue
                            
                            title = article_data.get('title', '').strip() if article_data.get('title') else ''
                            if not title:
                                print(f"    ⚠️  Article {i+1} has no title. Keys: {list(article_data.keys())}")
                                continue
                            
                            all_articles.append({
                                "title": self._clean_html(title),
                                "description": self._clean_html(article_data.get('description', '')),
                                "link": article_data.get('link', ''),
                                "published": article_data.get('published', datetime.now(ist).isoformat())
                            })
                            print(f"    ✅ Added article {i+1}: {title[:60]}...")
                        
                        print(f"  ✅ Gemini returned {len(all_articles)} news stories")
                        
                        # Remove duplicates
                        seen_titles = set()
                        unique_articles = []
                        for article in all_articles:
                            title = article.get("title", "").strip().lower()
                            if title and title not in seen_titles:
                                seen_titles.add(title)
                                unique_articles.append(article)
                        
                        print(f"  📊 After deduplication: {len(unique_articles)} unique stories")
                        return unique_articles[:limit]
                    else:
                        print(f"  ⚠️  No articles data after parsing")
                        articles_data = None
                except json.JSONDecodeError as json_err:
                    # Mark that parsing failed
                    articles_data = None
                    print(f"  ⚠️  JSON parsing error: {json_err}")
                    print(f"  📄 JSON string preview: {json_str[:500]}...")
                    print(f"  🔄 Attempting to repair JSON...")
                    
                    # Try to repair common JSON issues
                    try:
                        # Remove any text before first [
                        if '[' in json_str:
                            json_str = json_str[json_str.find('['):]
                        # Remove any text after last ]
                        if ']' in json_str:
                            json_str = json_str[:json_str.rfind(']') + 1]
                        
                        articles_data = json.loads(json_str)
                        print(f"  ✅ Successfully parsed repaired JSON")
                        
                        # Convert to our article format
                        for article_data in articles_data:
                            if isinstance(article_data, dict) and article_data.get('title'):
                                all_articles.append({
                                    "title": self._clean_html(article_data.get('title', '')),
                                    "description": self._clean_html(article_data.get('description', '')),
                                    "link": article_data.get('link', ''),
                                    "published": article_data.get('published', datetime.now(ist).isoformat())
                                })
                        
                        print(f"  ✅ Gemini returned {len(all_articles)} news stories")
                        
                        # Remove duplicates
                        seen_titles = set()
                        unique_articles = []
                        for article in all_articles:
                            title = article.get("title", "").strip().lower()
                            if title and title not in seen_titles:
                                seen_titles.add(title)
                                unique_articles.append(article)
                        
                        print(f"  📊 After deduplication: {len(unique_articles)} unique stories")
                        return unique_articles[:limit]
                    except Exception as final_err:
                        print(f"  ❌ Could not repair JSON: {final_err}")
                        articles_data = None
            
            # Only show this error if we actually failed to parse JSON
            if json_str is None:
                print(f"  ⚠️  Could not extract JSON from Gemini response")
                print(f"  📄 Full response preview (first 1000 chars):")
                print(f"  {'='*60}")
                print(f"  {content[:1000]}")
                print(f"  {'='*60}")
                print(f"  💡 Gemini may not have returned JSON format. Trying to extract news from text...")
                
                # Fallback: return empty list and let the system use RSS/NewsAPI
                print(f"  🔄 Falling back to RSS/NewsAPI...")
                self.use_gemini = False  # Temporarily disable Gemini
                fallback_result = self.fetch_today_news(limit=limit, test_articles=test_articles)
                return fallback_result if fallback_result is not None else []
            elif articles_data is None or len(articles_data) == 0:
                print(f"  ⚠️  Could not parse JSON from Gemini response (extracted but invalid)")
                print(f"  📄 JSON preview (first 500 chars): {json_str[:500] if json_str else 'None'}...")
                print(f"  🔄 Falling back to RSS/NewsAPI...")
                self.use_gemini = False  # Temporarily disable Gemini
                fallback_result = self.fetch_today_news(limit=limit, test_articles=test_articles)
                return fallback_result if fallback_result is not None else []
            
        except json.JSONDecodeError as e:
            print(f"  ⚠️  JSON parsing error: {e}")
            print(f"  🔄 Falling back to RSS/NewsAPI...")
            self.use_gemini = False  # Temporarily disable Gemini
            fallback_result = self.fetch_today_news(limit=limit, test_articles=test_articles)
            return fallback_result if fallback_result is not None else []
        except Exception as e:
            print(f"  ⚠️  Error fetching news with Gemini: {e}")
            import traceback
            print(f"  📋 Error details: {traceback.format_exc()[:300]}")
            print(f"  🔄 Falling back to RSS/NewsAPI...")
            self.use_gemini = False  # Temporarily disable Gemini
            fallback_result = self.fetch_today_news(limit=limit, test_articles=test_articles)
            return fallback_result if fallback_result is not None else []
    
    def get_news_summary(self, articles: List[Dict]) -> str:
        """Create a simple summary of articles"""
        summary = []
        for i, article in enumerate(articles, 1):
            summary.append(f"{i}. {article['title']}")
            if article.get('description'):
                summary.append(f"   {article['description'][:150]}...")
        return "\n".join(summary)

