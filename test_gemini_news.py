#!/usr/bin/env python3
"""
Test script to verify Gemini API with Google Search is working
"""
import sys
from news_fetcher import NewsFetcher
from config import NEWS_API_KEY

def test_gemini_news():
    """Test Gemini news fetching"""
    print("=" * 60)
    print("Testing Gemini API with Google Search")
    print("=" * 60)
    
    print("\n[1/2] Initializing NewsFetcher with Gemini...")
    fetcher = NewsFetcher(news_api_key=NEWS_API_KEY, country="in", use_gemini=True)
    
    print("\n[2/2] Fetching 5 news articles (this may take 30-90 seconds)...")
    print("      If it hangs, press Ctrl+C to cancel and check the error messages")
    print()
    
    try:
        articles = fetcher.fetch_today_news(limit=5)
        
        if articles:
            print(f"\n✅ SUCCESS! Got {len(articles)} articles:")
            print()
            for i, article in enumerate(articles, 1):
                print(f"{i}. {article.get('title', 'No title')[:80]}")
                print(f"   {article.get('description', 'No description')[:100]}...")
                print(f"   Link: {article.get('link', 'No link')[:80]}")
                print()
        else:
            print("\n❌ No articles returned. Check error messages above.")
            print("\n💡 Troubleshooting:")
            print("   1. Check if Gemini API key is valid")
            print("   2. Google Search grounding may require paid API")
            print("   3. Try without Google Search (set use_gemini=False)")
            return False
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelled by user")
        print("💡 If it was hanging, Gemini API might be:")
        print("   - Rate limited (free tier)")
        print("   - Requiring paid API for Google Search")
        print("   - Timing out (try increasing timeout)")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        print(f"\n📋 Full error:")
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_gemini_news()
    sys.exit(0 if success else 1)

