# RSS Feeds Setup Guide

This guide explains how to add and configure RSS feeds for the news automation system.

## Current RSS Feeds

The system currently uses **14 Indian news RSS feeds**:

1. **Times of India** - Top Stories
2. **The Hindu** - National News
3. **NDTV** - Top Stories
4. **India Today** - Top Stories
5. **Indian Express** - India News
6. **Business Standard** - Top Stories
7. **Mint** - News
8. **Firstpost** - India News
9. **News18** - India News
10. **Zee News** - India National News
11. **ABP News** - India News
12. **Outlook India** - India News
13. **Deccan Herald** - National News
14. **The Quint** - India News

## How to Add More RSS Feeds

### Step 1: Find RSS Feed URLs

Most news websites provide RSS feeds. Common patterns:
- `https://website.com/rss/feed.xml`
- `https://website.com/feed/`
- `https://feeds.feedburner.com/feedname`
- `https://website.com/rssfeeds/category.cms`

**How to find RSS feeds:**
1. Visit the news website
2. Look for an RSS icon (usually orange) or "RSS" link
3. Right-click and copy the link address
4. Or search for "site:website.com RSS" on Google

### Step 2: Test the RSS Feed

Before adding, test if the feed works:
```bash
# Using curl (if installed)
curl "https://example.com/rss/feed.xml" | head -20

# Or open in browser
# Most browsers will display RSS feeds in a readable format
```

### Step 3: Add to Code

Edit `news_fetcher.py` and add your feed to the `indian_rss_feeds` list:

```python
self.indian_rss_feeds = [
    # ... existing feeds ...
    "https://your-new-feed-url.com/rss/feed.xml",  # Your Feed Name
]
```

### Step 4: Test the Feed

Run the news fetcher to test:
```bash
python main.py
```

Check the output for:
- ✅ `Fetched X articles from feedname` - Feed is working
- ⚠️ `RSS feed returned no entries` - Feed might be empty or broken
- ⚠️ `Error fetching RSS feed` - Feed URL is invalid or inaccessible

## Popular Indian News RSS Feeds

Here are some additional RSS feeds you can add:

### National News
- **Scroll.in**: `https://scroll.in/rss`
- **The Wire**: `https://thewire.in/feed`
- **The Print**: `https://theprint.in/feed/`
- **Swarajya**: `https://swarajyamag.com/feed`

### Regional News
- **Times of India - Mumbai**: `https://timesofindia.indiatimes.com/rssfeeds/-2128833038.cms`
- **Times of India - Delhi**: `https://timesofindia.indiatimes.com/rssfeeds/-2128839597.cms`
- **Times of India - Bangalore**: `https://timesofindia.indiatimes.com/rssfeeds/-2128832078.cms`

### Business News
- **Economic Times**: `https://economictimes.indiatimes.com/rssfeedsdefault.cms`
- **Business Today**: `https://www.businesstoday.in/rss/feed`

### Sports News
- **ESPN Cricinfo**: `https://www.espncricinfo.com/rss/content/story/feeds/0.xml`
- **Sportskeeda**: `https://www.sportskeeda.com/feed`

### Technology News
- **Gadgets 360**: `https://gadgets.ndtv.com/rss/feeds/all`
- **TechCrunch India**: `https://techcrunch.com/tag/india/feed/`

## International RSS Feeds (Fallback)

The system also includes international feeds as fallback:
- **BBC News**: `https://feeds.bbci.co.uk/news/rss.xml`
- **CNN**: `https://rss.cnn.com/rss/edition.rss`
- **Reuters**: `https://feeds.reuters.com/reuters/topNews`

## Troubleshooting

### Feed Returns No Entries
- The feed might be temporarily down
- The feed URL might have changed
- The feed might require authentication (not supported)

### Feed Returns Errors
- Check if the URL is correct
- Verify the feed is publicly accessible
- Some feeds might block automated access

### Too Many Feeds
- The system fetches 5 articles per feed
- With 14 feeds, you'll get ~70 articles (before deduplication)
- Too many feeds might slow down fetching
- Consider removing feeds that consistently fail

## Best Practices

1. **Test feeds regularly** - RSS feeds can change or break
2. **Use reliable sources** - Major news outlets are more stable
3. **Monitor feed health** - Check logs for failing feeds
4. **Limit feed count** - 10-15 feeds is usually sufficient
5. **Use category-specific feeds** - Better content diversity

## Configuration

You can modify feed behavior in `news_fetcher.py`:

- **Limit per feed**: Change `limit=5` in `fetch_from_rss()` calls
- **Total limit**: Change `limit` parameter in `fetch_today_news()`
- **Feed selection**: Modify `indian_rss_feeds` or `international_rss_feeds` lists

## Need Help?

If you encounter issues:
1. Check the terminal output for error messages
2. Test the RSS feed URL in a browser
3. Verify the feed format is valid RSS/XML
4. Check if the website requires authentication

