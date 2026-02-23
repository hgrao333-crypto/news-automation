# YouTube Upload Setup Guide

This guide will help you set up automatic video uploads to your YouTube channel.

## Prerequisites

1. A Google account with a YouTube channel
2. Python packages installed (run `pip install -r requirements.txt`)

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **YouTube Data API v3**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"

## Step 2: Create OAuth 2.0 Credentials

1. In Google Cloud Console, go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. If prompted, configure the OAuth consent screen:
   - Choose "External" user type
   - Fill in required fields (App name, User support email, etc.)
   - Add your email to test users
   - Save and continue
4. Create OAuth client ID:
   - Application type: **Desktop app**
   - Name: "News Automation" (or any name you prefer)
   - Click "Create"
5. Download the credentials file:
   - Click the download icon next to your OAuth client
   - Save it as `client_secret.json` in the project root directory

## Step 3: Configure Environment Variables (Optional)

You can configure YouTube upload settings via environment variables or `.env` file:

```bash
# Enable/disable auto-upload (default: false)
YOUTUBE_AUTO_UPLOAD=true

# Privacy status: public, unlisted, or private (default: public)
YOUTUBE_PRIVACY_STATUS=public

# YouTube category ID (default: 22 = People & Blogs)
# See category list: https://developers.google.com/youtube/v3/docs/videoCategories/list
YOUTUBE_CATEGORY_ID=22

# Custom credentials file path (default: client_secret.json)
YOUTUBE_CREDENTIALS_FILE=client_secret.json

# Custom token file path (default: token.pickle)
YOUTUBE_TOKEN_FILE=token.pickle
```

## Step 4: First-Time Authentication

When you run the upload for the first time:

1. A browser window will open
2. Sign in with your Google account
3. Grant permissions to access your YouTube channel
4. The authentication token will be saved to `token.pickle`
5. You won't need to authenticate again unless the token expires

## Usage

### Option 1: Auto-upload (via environment variable)

```bash
# Set in .env file or export
export YOUTUBE_AUTO_UPLOAD=true

# Run normally - videos will auto-upload
python3 main.py --type today
```

### Option 2: Manual upload flag

```bash
# Use --upload flag to upload after generation
python3 main.py --type today --upload
```

### Option 3: Upload existing video

```python
from youtube_uploader import YouTubeUploader

uploader = YouTubeUploader()
uploader.authenticate()

result = uploader.upload_video(
    video_path="output/today_in_60_seconds_20251127_192337.mp4",
    title="Today's Top News Stories",
    description="Stay informed with the latest news updates!",
    tags=["news", "breaking news", "youtube shorts"],
    privacy_status="public"
)

if result:
    print(f"Video uploaded: {result['url']}")
```

## Privacy Status Options

- **public**: Anyone can view the video
- **unlisted**: Only people with the link can view
- **private**: Only you can view (useful for testing)

## YouTube Category IDs

Common categories:
- `1` - Film & Animation
- `2` - Autos & Vehicles
- `10` - Music
- `15` - Pets & Animals
- `17` - Sports
- `19` - Travel & Events
- `20` - Gaming
- `22` - People & Blogs (default)
- `23` - Comedy
- `24` - Entertainment
- `25` - News & Politics
- `26` - Howto & Style
- `27` - Education
- `28` - Science & Technology

## Troubleshooting

### "Credentials file not found"
- Make sure `client_secret.json` is in the project root directory
- Check the file path in your `.env` file if using custom path

### "Authentication failed"
- Make sure YouTube Data API v3 is enabled in Google Cloud Console
- Check that your OAuth consent screen is configured
- Make sure you're using a Desktop app OAuth client (not Web application)

### "Token expired"
- Delete `token.pickle` and re-authenticate
- The token will refresh automatically if it has a refresh token

### "Quota exceeded"
- YouTube API has daily quotas (default: 10,000 units/day)
- Each video upload uses ~1,600 units
- You can request quota increase in Google Cloud Console

## Security Notes

- **Never commit `client_secret.json` or `token.pickle` to git**
- Add them to `.gitignore`:
  ```
  client_secret.json
  token.pickle
  ```
- Keep your credentials secure and don't share them

## API Quotas

YouTube Data API v3 has default quotas:
- **Queries per day**: 10,000 units
- **Queries per 100 seconds per user**: 1,000 units

Each video upload costs ~1,600 units, so you can upload approximately 6 videos per day with default quotas.

To increase quotas, submit a request in Google Cloud Console under "APIs & Services" > "Quotas".

