#!/usr/bin/env python3
"""
Extract script/transcript from a video file
"""
import sys
import os
from moviepy.editor import VideoFileClip

def extract_audio_from_video(video_path: str, output_audio_path: str = None):
    """Extract audio from video file"""
    if not output_audio_path:
        output_audio_path = video_path.replace('.mp4', '_audio.wav').replace('output/', 'temp/')
    
    print(f"Extracting audio from: {video_path}")
    clip = VideoFileClip(video_path)
    print(f"Video duration: {clip.duration:.2f} seconds ({clip.duration/60:.2f} minutes)")
    
    if clip.audio:
        print(f"Writing audio to: {output_audio_path}")
        clip.audio.write_audiofile(output_audio_path, verbose=False, logger=None)
        clip.close()
        return output_audio_path
    else:
        print("No audio track found in video")
        clip.close()
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_script_from_video.py <video_path>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)
    
    audio_path = extract_audio_from_video(video_path)
    if audio_path:
        print(f"\n✅ Audio extracted to: {audio_path}")
        print(f"\n💡 To transcribe, you can use:")
        print(f"   - OpenAI Whisper: whisper {audio_path}")
        print(f"   - Or use an online transcription service")
    else:
        print("\n❌ Failed to extract audio")

