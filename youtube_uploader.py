#!/usr/bin/env python3
"""
YouTube Uploader Module
Uploads and publishes videos to YouTube channel using YouTube Data API v3
"""

import os
import json
from typing import Optional, Dict
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import pickle

# YouTube API scopes
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

class YouTubeUploader:
    """
    Handles uploading videos to YouTube channel
    """
    
    def __init__(self, credentials_file: str = "client_secret.json", token_file: str = "token.pickle"):
        """
        Initialize YouTube uploader
        
        Args:
            credentials_file: Path to OAuth2 client credentials JSON file
            token_file: Path to store/load OAuth2 token
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.youtube = None
        self.credentials = None
        
    def authenticate(self) -> bool:
        """
        Authenticate with YouTube API using OAuth2
        Returns True if successful, False otherwise
        """
        try:
            # Load existing token if available
            if os.path.exists(self.token_file):
                with open(self.token_file, 'rb') as token:
                    self.credentials = pickle.load(token)
            
            # If no valid credentials, get new ones
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    # Refresh expired token
                    self.credentials.refresh(Request())
                else:
                    # Run OAuth flow
                    if not os.path.exists(self.credentials_file):
                        print(f"❌ Credentials file not found: {self.credentials_file}")
                        print("   Please download OAuth2 credentials from Google Cloud Console")
                        print("   and save as 'client_secret.json'")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES)
                    self.credentials = flow.run_local_server(port=0)
                
                # Save credentials for next time
                with open(self.token_file, 'wb') as token:
                    pickle.dump(self.credentials, token)
            
            # Build YouTube API service
            self.youtube = build('youtube', 'v3', credentials=self.credentials)
            print("✅ YouTube API authenticated successfully")
            return True
            
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False
    
    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: list = None,
        category_id: str = "22",  # People & Blogs
        privacy_status: str = "public",  # public, unlisted, private
        thumbnail_path: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Upload video to YouTube
        
        Args:
            video_path: Path to video file
            title: Video title
            description: Video description
            tags: List of tags
            category_id: YouTube category ID (default: 22 for People & Blogs)
            privacy_status: public, unlisted, or private
            thumbnail_path: Optional path to thumbnail image
        
        Returns:
            Video ID and URL if successful, None otherwise
        """
        if not self.youtube:
            if not self.authenticate():
                return None
        
        if not os.path.exists(video_path):
            print(f"❌ Video file not found: {video_path}")
            return None
        
        try:
            # Prepare video metadata
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags or [],
                    'categoryId': category_id
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # Create media upload object
            media = MediaFileUpload(
                video_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/*'
            )
            
            # Upload video
            print(f"📤 Uploading video to YouTube: {title}")
            print(f"   File: {video_path}")
            print(f"   Privacy: {privacy_status}")
            
            insert_request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            # Execute upload with progress tracking
            response = self._resumable_upload(insert_request)
            
            if response:
                video_id = response['id']
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                print(f"✅ Video uploaded successfully!")
                print(f"   Video ID: {video_id}")
                print(f"   URL: {video_url}")
                
                # Upload thumbnail if provided
                if thumbnail_path and os.path.exists(thumbnail_path):
                    try:
                        self.youtube.thumbnails().set(
                            videoId=video_id,
                            media_body=MediaFileUpload(thumbnail_path)
                        ).execute()
                        print(f"✅ Thumbnail uploaded")
                    except Exception as e:
                        print(f"⚠️  Could not upload thumbnail: {e}")
                
                return {
                    'video_id': video_id,
                    'url': video_url,
                    'title': title
                }
            else:
                print("❌ Upload failed")
                return None
                
        except Exception as e:
            print(f"❌ Error uploading video: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _resumable_upload(self, insert_request):
        """
        Execute resumable upload with progress tracking
        """
        response = None
        error = None
        retry = 0
        
        while response is None:
            try:
                print("   Uploading...", end='', flush=True)
                status, response = insert_request.next_chunk()
                if response is not None:
                    if 'id' in response:
                        print(" ✅")
                        return response
                    else:
                        print(" ❌")
                        print(f"   Unexpected response: {response}")
                        return None
                else:
                    if status:
                        progress = int(status.progress() * 100)
                        print(f"\r   Upload progress: {progress}%", end='', flush=True)
            except Exception as e:
                error = e
                retry += 1
                if retry > 3:
                    print(f"\n   ❌ Upload failed after {retry} retries: {error}")
                    return None
                print(f"\n   ⚠️  Upload error (retry {retry}/3): {error}")
        
        return response
    
    def get_channel_info(self) -> Optional[Dict]:
        """
        Get information about the authenticated channel
        """
        if not self.youtube:
            if not self.authenticate():
                return None
        
        try:
            request = self.youtube.channels().list(
                part='snippet,contentDetails,statistics',
                mine=True
            )
            response = request.execute()
            
            if response['items']:
                channel = response['items'][0]
                return {
                    'channel_id': channel['id'],
                    'title': channel['snippet']['title'],
                    'subscriber_count': channel['statistics'].get('subscriberCount', '0')
                }
            return None
        except Exception as e:
            print(f"❌ Error getting channel info: {e}")
            return None

