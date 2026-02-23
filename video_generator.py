from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip, CompositeAudioClip, TextClip, ColorClip
from moviepy.video.fx import resize, fadein, fadeout
from moviepy.audio.fx import audio_fadein, audio_fadeout, audio_normalize
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw, ImageFont
from typing import Dict, List
import os
import numpy as np
import random
import json
from config import VIDEO_WIDTH, VIDEO_HEIGHT, FPS, VIDEO_DURATION, OUTPUT_DIR, TEMP_DIR, EXTENDED_VIDEO_WIDTH, EXTENDED_VIDEO_HEIGHT, USE_CONTEXT_AWARE_OVERLAYS
from llm_client import LLMClient

# Fix for PIL.Image.ANTIALIAS deprecation in newer Pillow versions
# Pillow 10+ removed Image.ANTIALIAS, replaced with Image.Resampling.LANCZOS
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

class VideoGenerator:
    """Generates final video from images and audio"""
    
    def __init__(self, is_extended=False):
        """
        Initialize video generator
        Args:
            is_extended: If True, use 16:9 format (landscape) for extended videos
                        If False, use 9:16 format (portrait) for short videos
        """
        if is_extended:
            # Extended videos: 16:9 landscape format
            self.width = EXTENDED_VIDEO_WIDTH
            self.height = EXTENDED_VIDEO_HEIGHT
        else:
            # Short videos: 9:16 portrait format
            self.width = VIDEO_WIDTH
            self.height = VIDEO_HEIGHT
        self.fps = FPS
        # Fixed opening image path (check for both .png and .jpg)
        opening_png = os.path.join(TEMP_DIR, "opening", "open.png")
        opening_jpg = os.path.join(TEMP_DIR, "opening", "open.jpg")
        if os.path.exists(opening_jpg):
            self.opening_image_path = opening_jpg
        elif os.path.exists(opening_png):
            self.opening_image_path = opening_png
        else:
            self.opening_image_path = opening_png  # Default to .png if neither exists
        # Fixed closing image path
        self.closing_image_path = os.path.join(TEMP_DIR, "closing", "close.jpg")
        # Initialize LLM client for effect suggestions
        self.llm_client = LLMClient()
    
    def _add_ken_burns_effect(self, clip, segment_type, story_index):
        """
        Add Ken Burns effect (zoom/pan) to image clip for dynamic motion
        - Headlines: Slow zoom in (1.0x to 1.15x) with subtle pan
        - Summaries: Subtle zoom out (1.0x to 0.95x) or gentle pan
        - Ensures no static frames longer than 3-4 seconds
        """
        try:
            duration = clip.duration
            
            # For segments longer than 3 seconds, add motion
            if duration <= 3:
                # Short segments: subtle zoom only
                zoom_factor = 1.05
                return clip.resize(lambda t: 1 + (zoom_factor - 1) * (t / duration))
            
            # For longer segments: combine zoom and pan for dynamic effect
            # Randomize direction for variety
            import random
            # Use story_index for seed, or fallback to clip duration/hash if filename not available
            if story_index:
                seed_value = story_index
            else:
                try:
                    seed_value = hash(str(clip.filename)) % 1000 if hasattr(clip, 'filename') and clip.filename else hash(str(duration)) % 1000
                except:
                    seed_value = hash(str(duration)) % 1000
            random.seed(seed_value)
            
            # Choose motion pattern based on segment type
            if segment_type == 'headline':
                # Headlines: Zoom in with subtle pan (more dramatic)
                zoom_start = 1.0
                zoom_end = 1.15
                pan_x = random.uniform(-0.05, 0.05)  # Subtle horizontal pan
                pan_y = random.uniform(-0.03, 0.03)  # Subtle vertical pan
            else:
                # Summaries: Subtle zoom out or gentle pan
                zoom_start = 1.0
                zoom_end = 0.95
                pan_x = random.uniform(-0.03, 0.03)
                pan_y = random.uniform(-0.02, 0.02)
            
            # Apply zoom effect
            def make_frame(t):
                # Calculate zoom factor at time t
                zoom = zoom_start + (zoom_end - zoom_start) * (t / duration)
                
                # Calculate pan position at time t
                pan_x_t = pan_x * (t / duration)
                pan_y_t = pan_y * (t / duration)
                
                # Get frame at time t
                frame = clip.get_frame(t)
                
                # Apply zoom by resizing
                from PIL import Image
                import numpy as np
                
                pil_img = Image.fromarray(frame)
                w, h = pil_img.size
                
                # Calculate new size with zoom
                new_w = int(w * zoom)
                new_h = int(h * zoom)
                
                # Resize image
                pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                # Calculate crop area (centered with pan)
                crop_x = int((new_w - w) / 2 - pan_x_t * w)
                crop_y = int((new_h - h) / 2 - pan_y_t * h)
                
                # Ensure crop coordinates are valid
                crop_x = max(0, min(crop_x, new_w - w))
                crop_y = max(0, min(crop_y, new_h - h))
                
                # Crop to original size
                pil_img = pil_img.crop((crop_x, crop_y, crop_x + w, crop_y + h))
                
                return np.array(pil_img)
            
            # Create new clip with Ken Burns effect
            from moviepy.video.VideoClip import VideoClip
            ken_burns_clip = clip.fl(lambda gf, t: make_frame(t), apply_to=['video'])
            
            return ken_burns_clip
            
        except Exception as e:
            print(f"  ⚠️  Could not add Ken Burns effect: {e}, using static clip")
            return clip
    
    def _add_stylized_transition_in(self, clip, duration):
        """
        Add stylized transition IN effect (digital warp, film burn, or screen static)
        Uses faster fade-in with slight zoom for dynamic effect
        """
        try:
            import random
            transition_type = random.choice(['zoom_fade', 'quick_fade', 'zoom_in'])
            
            if transition_type == 'zoom_fade':
                # Zoom + fade: Start zoomed out, zoom in while fading in
                return clip.fadein(duration).resize(lambda t: 0.95 + 0.05 * (t / duration) if t < duration else 1.0)
            elif transition_type == 'quick_fade':
                # Quick fade: Faster transition
                return clip.fadein(duration * 0.7)
            else:  # zoom_in
                # Zoom in: Subtle zoom effect
                return clip.fadein(duration).resize(lambda t: 0.98 + 0.02 * (t / duration) if t < duration else 1.0)
                
        except Exception as e:
            print(f"  ⚠️  Could not add stylized transition IN: {e}, using fade")
            return clip.fadein(duration)
    
    def _add_stylized_transition_out(self, clip, duration):
        """
        Add stylized transition OUT effect (digital warp, film burn, or screen static)
        Uses fade-out with slight zoom for dynamic effect
        """
        try:
            import random
            transition_type = random.choice(['zoom_fade', 'quick_fade', 'zoom_out'])
            clip_duration = clip.duration
            
            if transition_type == 'zoom_fade':
                # Zoom + fade: Zoom out while fading out
                return clip.fadeout(duration).resize(lambda t: 1.0 - 0.05 * ((clip_duration - t) / duration) if t > clip_duration - duration else 1.0)
            elif transition_type == 'quick_fade':
                # Quick fade: Faster transition
                return clip.fadeout(duration * 0.7)
            else:  # zoom_out
                # Zoom out: Subtle zoom effect
                return clip.fadeout(duration).resize(lambda t: 1.0 - 0.02 * ((clip_duration - t) / duration) if t > clip_duration - duration else 1.0)
                
        except Exception as e:
            print(f"  ⚠️  Could not add stylized transition OUT: {e}, using fade")
            return clip.fadeout(duration)
    
    def _add_background_music(self, main_audio, duration):
        """
        Add subtle background music with ducking (volume reduction when TTS speaks)
        Creates a low-volume news beat track using audio synthesis
        """
        try:
            from pydub import AudioSegment
            import numpy as np
            
            # Normalize main audio first
            # Check if main_audio is a MoviePy clip or pydub AudioSegment
            if isinstance(main_audio, AudioSegment):
                # Use pydub's normalize method for AudioSegment
                normalized_audio = main_audio.normalize()
            else:
                # Assume it's a MoviePy AudioFileClip - use .fx() method for audio effects
                try:
                    # MoviePy audio effects should be used with .fx() method
                    normalized_audio = main_audio.fx(audio_normalize)
                except Exception as e1:
                    # If .fx() fails, try calling as function (older MoviePy versions)
                    try:
                        # Check if audio_normalize is callable
                        if callable(audio_normalize):
                            normalized_audio = audio_normalize(main_audio)
                        else:
                            raise Exception("audio_normalize is not callable")
                    except Exception as e2:
                        # If both fail, convert to AudioSegment and normalize
                        temp_audio_path = os.path.join(TEMP_DIR, "temp_audio_for_normalize.mp3")
                        try:
                            main_audio.write_audiofile(temp_audio_path, verbose=False, logger=None)
                            normalized_audio_seg = AudioSegment.from_mp3(temp_audio_path).normalize()
                            # Convert back to MoviePy clip
                            from moviepy.editor import AudioFileClip
                            normalized_audio_seg.export(temp_audio_path, format="mp3")
                            normalized_audio = AudioFileClip(temp_audio_path)
                            # Clean up temp file after use
                            # Note: We'll keep it for now and clean up later if needed
                        except Exception as e3:
                            print(f"  ⚠️  Audio normalization failed: {e3}, using original audio")
                            normalized_audio = main_audio
            
            # Create a subtle news beat background track
            # Generate a low-frequency, rhythmic pulse (like a news heartbeat)
            sample_rate = 44100
            duration_ms = int(duration * 1000)
            
            # Create a subtle beat pattern: low-frequency pulse every 2 seconds
            beat_pattern = []
            beat_duration_ms = 2000  # 2 seconds per beat
            num_beats = int(duration_ms / beat_duration_ms) + 1
            
            for i in range(num_beats):
                # Generate a subtle low-frequency pulse (60-80 Hz range)
                beat_samples = int(beat_duration_ms * sample_rate / 1000)
                t = np.linspace(0, beat_duration_ms / 1000, beat_samples)
                
                # Create a subtle pulse wave (very low volume)
                frequency = 70 + (10 * np.sin(i * 0.5))  # Slight variation
                pulse = np.sin(2 * np.pi * frequency * t)
                
                # Apply envelope (fade in/out for each beat)
                envelope = np.exp(-t * 2)  # Exponential decay
                pulse = pulse * envelope
                
                # Very low volume (5% of main audio)
                pulse = pulse * 0.05
                
                beat_pattern.extend(pulse)
            
            # Trim to exact duration
            beat_pattern = beat_pattern[:int(duration_ms * sample_rate / 1000)]
            
            # Convert to AudioSegment
            beat_array = (np.array(beat_pattern) * 32767).astype(np.int16)
            beat_audio = AudioSegment(
                beat_array.tobytes(),
                frame_rate=sample_rate,
                channels=1,
                sample_width=2
            )
            
            # Ensure same duration as main audio
            if len(beat_audio) < duration_ms:
                silence = AudioSegment.silent(duration=duration_ms - len(beat_audio))
                beat_audio = beat_audio + silence
            else:
                beat_audio = beat_audio[:duration_ms]
            
            # Mix with main audio (background music at very low volume)
            # Ducking: reduce background when speech is loud
            try:
                # Simple ducking: reduce background volume
                beat_audio = beat_audio - 20  # Reduce by 20dB (very quiet)
                combined = normalized_audio.overlay(beat_audio)
            except:
                # If overlay fails, just return normalized audio
                combined = normalized_audio
            
            # Apply subtle fade in/out
            # Check if combined is pydub AudioSegment or MoviePy clip
            if isinstance(combined, AudioSegment):
                # pydub uses fade_in/fade_out with milliseconds
                combined = combined.fade_in(500).fade_out(500)
            else:
                # MoviePy AudioFileClip - use audio effects from moviepy.audio.fx
                try:
                    combined = combined.fx(audio_fadein, 0.5).fx(audio_fadeout, 0.5)
                except:
                    # Fallback: try direct method if available
                    try:
                        combined = combined.fadein(0.5).fadeout(0.5)
                    except:
                        # If all fails, just return without fade
                        pass
            
            return combined
            
        except Exception as e:
            print(f"  ⚠️  Could not add background music: {e}, using normalized audio only")
            # If music generation fails, return normalized audio
            try:
                from pydub import AudioSegment
                if isinstance(main_audio, AudioSegment):
                    normalized_audio = main_audio.normalize()
                    normalized_audio = normalized_audio.fade_in(500).fade_out(500)  # pydub uses milliseconds
                    return normalized_audio
                else:
                    # Try MoviePy normalization with .fx() method
                    try:
                        normalized_audio = main_audio.fx(audio_normalize)
                    except:
                        # Fallback to function call (older MoviePy versions)
                        try:
                            if callable(audio_normalize):
                                normalized_audio = audio_normalize(main_audio)
                            else:
                                normalized_audio = main_audio  # Skip normalization if not callable
                        except:
                            normalized_audio = main_audio  # Skip normalization on error
                    
                    # Apply fade using audio effects
                    try:
                        normalized_audio = normalized_audio.fx(audio_fadein, 0.5).fx(audio_fadeout, 0.5)
                    except:
                        # Fallback: try direct method if available
                        try:
                            normalized_audio = normalized_audio.fadein(0.5).fadeout(0.5)
                        except:
                            # If all fails, return without fade
                            pass
                    return normalized_audio
            except Exception as e2:
                print(f"  ⚠️  Could not normalize audio: {e2}, returning original audio")
                return main_audio
    
    def _create_trending_indicator(self, start_time, duration, story_index):
        """
        Create trending indicator badges (🔥 Trending, ⚡ Breaking, etc.)
        """
        try:
            # Randomly assign indicators based on story position
            indicators = []
            if story_index == 1:
                indicators.append("🔥 Trending")
            elif story_index == 2:
                indicators.append("⚡ Breaking")
            elif story_index == 3:
                indicators.append("🌎 Worldwide")
            elif story_index >= 4:
                indicators.append("🇮🇳 India Focused")
            
            if not indicators:
                return None
            
            # Create indicator text image
            indicator_text = "  ".join(indicators)
            indicator_img = Image.new('RGBA', (300, 50), (0, 0, 0, 0))
            draw = ImageDraw.Draw(indicator_img)
            
            try:
                font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 24)
            except:
                font = ImageFont.load_default()
            
            # Draw indicator with background
            bbox = draw.textbbox((0, 0), indicator_text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            
            # Create semi-transparent background
            bg_img = Image.new('RGBA', (text_w + 20, text_h + 10), (0, 0, 0, 180))
            indicator_img.paste(bg_img, (0, 0), bg_img)
            
            # Draw text
            draw.text((10, 5), indicator_text, font=font, fill=(255, 255, 255, 255))
            
            # Save and create clip
            indicator_path = os.path.join(TEMP_DIR, f"indicator_{story_index}_{hash(indicator_text) % 10000}.png")
            indicator_img.save(indicator_path)
            
            indicator_clip = ImageClip(indicator_path, duration=duration)
            indicator_clip = indicator_clip.set_start(start_time)
            indicator_clip = indicator_clip.set_position((30, 50))  # Top-left corner
            
            return indicator_clip
        except Exception as e:
            print(f"  ⚠️  Could not create trending indicator: {e}")
            return None
    
    def _create_context_aware_overlay(self, overlay_data: Dict, start_time: float, duration: float, story_index: int = None) -> List:
        """
        Create context-aware visual overlays using PIL based on LLM suggestions
        overlay_data: Dict from ContentGenerator.generate_context_aware_overlays()
        Returns list of ImageClip objects
        """
        if not USE_CONTEXT_AWARE_OVERLAYS or not overlay_data:
            return []
        
        overlay_clips = []
        
        try:
            # Create primary overlay
            if overlay_data.get('primary_overlay'):
                primary = overlay_data['primary_overlay']
                primary_text = primary.get('text', '')
                style = primary.get('style', 'breaking')
                position = primary.get('position', 'top_center')
                
                if primary_text:
                    primary_clip = self._create_overlay_badge(
                        text=primary_text,
                        style=style,
                        position=position,
                        start_time=start_time,
                        duration=duration,
                        story_index=story_index
                    )
                    if primary_clip:
                        overlay_clips.append(primary_clip)
            
            # Create progress overlay
            if overlay_data.get('progress_overlay'):
                progress = overlay_data['progress_overlay']
                progress_text = progress.get('text', '')
                position = progress.get('position', 'top_right')
                
                if progress_text:
                    progress_clip = self._create_progress_indicator(
                        text=progress_text,
                        position=position,
                        start_time=start_time,
                        duration=duration
                    )
                    if progress_clip:
                        overlay_clips.append(progress_clip)
            
            # Create optional secondary overlay (curiosity hooks)
            if overlay_data.get('optional_secondary'):
                secondary = overlay_data['optional_secondary']
                secondary_text = secondary.get('text', '')
                position = secondary.get('position', 'center_top')
                
                if secondary_text:
                    secondary_clip = self._create_curiosity_hook(
                        text=secondary_text,
                        position=position,
                        start_time=start_time,
                        duration=duration
                    )
                    if secondary_clip:
                        overlay_clips.append(secondary_clip)
            
            return overlay_clips
            
        except Exception as e:
            print(f"  ⚠️  Could not create context-aware overlays: {e}")
            return []
    
    def _create_overlay_badge(self, text: str, style: str, position: str, start_time: float, duration: float, story_index: int = None) -> ImageClip:
        """
        Create a visual badge overlay with context-aware styling
        style: 'breaking', 'urgent', 'developing', 'final'
        position: 'top_center', 'top_left', 'top_right'
        """
        try:
            # Style colors based on urgency
            style_colors = {
                'breaking': {'bg': (220, 20, 20, 240), 'text': (255, 255, 255, 255), 'border': (255, 0, 0, 255)},  # Red
                'urgent': {'bg': (255, 165, 0, 240), 'text': (255, 255, 255, 255), 'border': (255, 200, 0, 255)},  # Orange
                'developing': {'bg': (30, 144, 255, 240), 'text': (255, 255, 255, 255), 'border': (0, 100, 255, 255)},  # Blue
                'final': {'bg': (255, 140, 0, 240), 'text': (255, 255, 255, 255), 'border': (255, 180, 0, 255)}  # Orange-red
            }
            
            colors = style_colors.get(style, style_colors['breaking'])
            
            # Load font
            try:
                font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 42)  # Larger for visibility
            except:
                try:
                    font = ImageFont.truetype('/System/Library/Fonts/Arial Bold.ttf', 42)
                except:
                    font = ImageFont.load_default()
            
            # Calculate text size
            test_img = Image.new('RGBA', (100, 100))
            test_draw = ImageDraw.Draw(test_img)
            bbox = test_draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            
            # Create badge with padding
            padding_x = 30
            padding_y = 15
            badge_w = text_w + (padding_x * 2)
            badge_h = text_h + (padding_y * 2)
            
            # Create badge image
            badge_img = Image.new('RGBA', (badge_w, badge_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(badge_img)
            
            # Draw background with rounded corners effect (using rectangle with border)
            # Main background
            draw.rectangle([(0, 0), (badge_w, badge_h)], fill=colors['bg'])
            # Border
            border_width = 3
            draw.rectangle([(0, 0), (badge_w, badge_h)], outline=colors['border'], width=border_width)
            
            # Draw text
            text_x = padding_x
            text_y = padding_y
            # Add text shadow for better visibility
            draw.text((text_x + 2, text_y + 2), text, font=font, fill=(0, 0, 0, 180))
            draw.text((text_x, text_y), text, font=font, fill=colors['text'])
            
            # Save badge
            badge_path = os.path.join(TEMP_DIR, f"badge_{hash(text)}_{story_index if story_index else 0}.png")
            badge_img.save(badge_path)
            
            # Create clip and position
            badge_clip = ImageClip(badge_path, duration=duration)
            badge_clip = badge_clip.set_start(start_time)
            
            # Position based on parameter
            if position == 'top_center':
                x_pos = (self.width - badge_w) // 2
                y_pos = 50
            elif position == 'top_left':
                x_pos = 30
                y_pos = 50
            elif position == 'top_right':
                x_pos = self.width - badge_w - 30
                y_pos = 50
            else:
                x_pos = (self.width - badge_w) // 2
                y_pos = 50
            
            badge_clip = badge_clip.set_position((x_pos, y_pos))
            
            return badge_clip
            
        except Exception as e:
            print(f"  ⚠️  Could not create overlay badge: {e}")
            return None
    
    def _create_progress_indicator(self, text: str, position: str, start_time: float, duration: float) -> ImageClip:
        """
        Create progress indicator overlay (e.g., "STORY 3 OF 8")
        """
        try:
            # Load font
            try:
                font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 28)
            except:
                font = ImageFont.load_default()
            
            # Calculate text size
            test_img = Image.new('RGBA', (100, 100))
            test_draw = ImageDraw.Draw(test_img)
            bbox = test_draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            
            # Create indicator with padding
            padding_x = 15
            padding_y = 8
            indicator_w = text_w + (padding_x * 2)
            indicator_h = text_h + (padding_y * 2)
            
            # Create indicator image
            indicator_img = Image.new('RGBA', (indicator_w, indicator_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(indicator_img)
            
            # Semi-transparent dark background
            bg_color = (0, 0, 0, 200)
            draw.rectangle([(0, 0), (indicator_w, indicator_h)], fill=bg_color)
            
            # Draw text
            text_x = padding_x
            text_y = padding_y
            draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))
            
            # Save indicator
            indicator_path = os.path.join(TEMP_DIR, f"progress_{hash(text)}.png")
            indicator_img.save(indicator_path)
            
            # Create clip and position
            indicator_clip = ImageClip(indicator_path, duration=duration)
            indicator_clip = indicator_clip.set_start(start_time)
            
            # Position (usually top-right)
            if position == 'top_right':
                x_pos = self.width - indicator_w - 30
                y_pos = 50
            else:
                x_pos = self.width - indicator_w - 30
                y_pos = 50
            
            indicator_clip = indicator_clip.set_position((x_pos, y_pos))
            
            return indicator_clip
            
        except Exception as e:
            print(f"  ⚠️  Could not create progress indicator: {e}")
            return None
    
    def _create_subscribe_cta(self, start_time: float, duration: float) -> ImageClip:
        """
        Create a subscribe call-to-action overlay for the end of videos
        """
        try:
            # Subscribe text with bell icon
            subscribe_text = "🔔 Subscribe for Daily News Updates"
            
            # Load font
            try:
                font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 48)  # Larger for visibility
            except:
                try:
                    font = ImageFont.truetype('/System/Library/Fonts/Arial Bold.ttf', 48)
                except:
                    font = ImageFont.load_default()
            
            # Calculate text size
            test_img = Image.new('RGBA', (200, 100))
            test_draw = ImageDraw.Draw(test_img)
            bbox = test_draw.textbbox((0, 0), subscribe_text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            
            # Create badge with padding
            padding_x = 40
            padding_y = 20
            badge_w = text_w + (padding_x * 2)
            badge_h = text_h + (padding_y * 2)
            
            # Create badge image
            badge_img = Image.new('RGBA', (badge_w, badge_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(badge_img)
            
            # Draw background with rounded corners effect
            # Red gradient background (YouTube subscribe button style)
            bg_color = (255, 0, 0, 255)  # Red
            border_color = (200, 0, 0, 255)  # Darker red border
            
            # Main background
            draw.rectangle([(0, 0), (badge_w, badge_h)], fill=bg_color)
            # Border
            border_width = 4
            draw.rectangle([(0, 0), (badge_w, badge_h)], outline=border_color, width=border_width)
            
            # Draw text with shadow for better visibility
            text_x = padding_x
            text_y = padding_y
            # Text shadow
            draw.text((text_x + 3, text_y + 3), subscribe_text, font=font, fill=(0, 0, 0, 200))
            # Main text (white)
            draw.text((text_x, text_y), subscribe_text, font=font, fill=(255, 255, 255, 255))
            
            # Save badge
            badge_path = os.path.join(TEMP_DIR, f"subscribe_cta_{hash(subscribe_text)}.png")
            badge_img.save(badge_path)
            
            # Create clip and position at center-bottom
            badge_clip = ImageClip(badge_path, duration=duration)
            badge_clip = badge_clip.set_start(start_time)
            
            # Position at center-bottom (above text panel)
            x_pos = (self.width - badge_w) // 2
            y_pos = int(self.height * 0.65)  # 65% down from top (above text panel at 80%)
            
            badge_clip = badge_clip.set_position((x_pos, y_pos))
            
            # Add fade-in animation
            badge_clip = badge_clip.fadein(0.3)
            
            return badge_clip
            
        except Exception as e:
            print(f"  ⚠️  Could not create subscribe CTA: {e}")
            return None
    
    def _create_curiosity_hook(self, text: str, position: str, start_time: float, duration: float) -> ImageClip:
        """
        Create curiosity hook overlay (e.g., "WAIT FOR IT...", "YOU WON'T BELIEVE")
        """
        try:
            # Load font
            try:
                font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 36)
            except:
                font = ImageFont.load_default()
            
            # Calculate text size
            test_img = Image.new('RGBA', (100, 100))
            test_draw = ImageDraw.Draw(test_img)
            bbox = test_draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            
            # Create hook with padding
            padding_x = 20
            padding_y = 12
            hook_w = text_w + (padding_x * 2)
            hook_h = text_h + (padding_y * 2)
            
            # Create hook image
            hook_img = Image.new('RGBA', (hook_w, hook_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(hook_img)
            
            # Yellow/orange background for curiosity
            bg_color = (255, 200, 0, 240)  # Yellow
            border_color = (255, 150, 0, 255)  # Orange border
            
            # Draw background
            draw.rectangle([(0, 0), (hook_w, hook_h)], fill=bg_color)
            draw.rectangle([(0, 0), (hook_w, hook_h)], outline=border_color, width=2)
            
            # Draw text
            text_x = padding_x
            text_y = padding_y
            # Text shadow
            draw.text((text_x + 1, text_y + 1), text, font=font, fill=(0, 0, 0, 150))
            draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))
            
            # Save hook
            hook_path = os.path.join(TEMP_DIR, f"hook_{hash(text)}.png")
            hook_img.save(hook_path)
            
            # Create clip and position
            hook_clip = ImageClip(hook_path, duration=duration)
            hook_clip = hook_clip.set_start(start_time)
            
            # Position (usually center-top)
            if position == 'center_top':
                x_pos = (self.width - hook_w) // 2
                y_pos = 120  # Below primary badge
            else:
                x_pos = (self.width - hook_w) // 2
                y_pos = 120
            
            hook_clip = hook_clip.set_position((x_pos, y_pos))
            
            return hook_clip
            
        except Exception as e:
            print(f"  ⚠️  Could not create curiosity hook: {e}")
            return None
    
    def _identify_keywords(self, text: str) -> set:
        """Identify important keywords that should be highlighted"""
        keywords = set()
        text_lower = text.lower()
        
        # Common important words
        important_words = [
            'crisis', 'breaking', 'shocking', 'urgent', 'emergency', 'alert',
            'karnataka', 'congress', 'siddaramaiah', 'shivakumar', 'india', 'delhi', 'mumbai',
            'war', 'conflict', 'clash', 'dispute', 'protest', 'strike',
            'crash', 'accident', 'death', 'killed', 'injured',
            'election', 'vote', 'government', 'minister', 'president', 'prime minister',
            'market', 'stock', 'economy', 'price', 'currency', 'rupee', 'dollar',
            'fire', 'flood', 'earthquake', 'disaster', 'storm'
        ]
        
        words = text.split()
        for word in words:
            word_clean = word.lower().strip('.,!?;:()[]{}"\'-')
            if word_clean in important_words or len(word_clean) > 6:  # Also highlight long words (likely names/places)
                keywords.add(word_clean)
        
        return keywords
    
    def _add_glitch_effect(self, clip, intensity: float = 0.3):
        """
        Add glitch effects to video clip: RGB shift, scan lines, digital artifacts
        intensity: 0.0 (none) to 1.0 (heavy glitch)
        """
        try:
            if intensity <= 0:
                return clip
            
            def glitch_frame(get_frame, t):
                try:
                    frame = get_frame(t)
                    
                    # Ensure frame is numpy array with correct shape
                    if not isinstance(frame, np.ndarray):
                        return frame
                    
                    # Handle different frame formats
                    if len(frame.shape) == 2:  # Grayscale
                        frame = np.stack([frame, frame, frame], axis=2)
                    elif len(frame.shape) != 3 or frame.shape[2] != 3:
                        return frame  # Invalid format, return as-is
                    
                    h, w = frame.shape[:2]
                    
                    # Random glitch chance based on intensity
                    glitch_chance = intensity * 0.15  # 15% max chance per frame (increased from 10%)
                    if random.random() > glitch_chance:
                        return frame
                    
                    # RGB channel shift (chromatic aberration)
                    shift_amount = max(1, int(intensity * 8))  # Max 8 pixels shift (increased from 5)
                    glitched = frame.copy().astype(np.uint8)
                    
                    # Red channel shift right
                    if random.random() < 0.6:  # Increased probability
                        if shift_amount < w:
                            glitched[:, shift_amount:, 0] = frame[:, :-shift_amount, 0]
                            glitched[:, :shift_amount, 0] = 0
                    
                    # Blue channel shift left
                    if random.random() < 0.6:  # Increased probability
                        if shift_amount < w:
                            glitched[:, :-shift_amount, 2] = frame[:, shift_amount:, 2]
                            glitched[:, -shift_amount:, 2] = 0
                    
                    # Add scan lines occasionally
                    if random.random() < intensity * 0.4:  # Increased from 0.3
                        scan_line_y = random.randint(0, max(1, h - 5))
                        scan_line_height = random.randint(2, 4)
                        scan_line_y_end = min(h, scan_line_y + scan_line_height)
                        glitched[scan_line_y:scan_line_y_end, :] = 0
                    
                    # Digital artifacts (block corruption)
                    if random.random() < intensity * 0.3:  # Increased from 0.2
                        block_size = random.randint(8, 25)  # Larger blocks
                        block_x = random.randint(0, max(1, w - block_size))
                        block_y = random.randint(0, max(1, h - block_size))
                        # Corrupt block with noise
                        noise = np.random.randint(0, 255, (block_size, block_size, 3), dtype=np.uint8)
                        block_y_end = min(h, block_y + block_size)
                        block_x_end = min(w, block_x + block_size)
                        glitched[block_y:block_y_end, block_x:block_x_end] = noise[:block_y_end-block_y, :block_x_end-block_x]
                    
                    return glitched.astype(np.uint8)
                except Exception as e:
                    # If glitch fails, return original frame
                    return frame
            
            glitched_clip = clip.fl(glitch_frame, apply_to=['video'])
            return glitched_clip
            
        except Exception as e:
            print(f"  ⚠️  Could not add glitch effect: {e}")
            return clip
    
    def _add_audio_reverb(self, audio_clip, room_size: float = 0.3, damping: float = 0.5):
        """
        Add reverb effect to audio using pydub
        room_size: 0.0 (dry) to 1.0 (large room)
        damping: 0.0 (bright) to 1.0 (damp)
        """
        try:
            from pydub import AudioSegment
            from pydub.effects import normalize
            
            # Convert MoviePy clip to file if needed
            if hasattr(audio_clip, 'filename'):
                audio_seg = AudioSegment.from_file(audio_clip.filename)
            else:
                # Save temporarily
                temp_path = os.path.join(TEMP_DIR, f"temp_reverb_{hash(str(audio_clip)) % 10000}.mp3")
                audio_clip.write_audiofile(temp_path, verbose=False, logger=None)
                audio_seg = AudioSegment.from_file(temp_path)
            
            # Simple reverb simulation using echo
            # Create delayed copies with reduced volume (more subtle to avoid echoing)
            reverb_delays = [50, 100, 150, 200]  # milliseconds
            reverb_volumes = [0.15, 0.1, 0.08, 0.05]  # Reduced volume multipliers to avoid echoing
            
            reverb_seg = audio_seg
            for delay_ms, volume in zip(reverb_delays, reverb_volumes):
                if delay_ms < len(audio_seg):
                    delayed = AudioSegment.silent(duration=delay_ms) + audio_seg
                    delayed = delayed - (20 - int(volume * 20))  # Reduce volume
                    # Mix with original
                    reverb_seg = reverb_seg.overlay(delayed[:len(reverb_seg)])
            
            # Apply damping (high-frequency rolloff)
            if damping > 0:
                # Simple low-pass filter simulation
                reverb_seg = reverb_seg.low_pass_filter(int(8000 * (1 - damping)))
            
            # Mix original with reverb (more subtle mix to avoid echoing)
            dry_wet = 1.0 - room_size  # More room = less dry
            # Reduce reverb mix to avoid echoing - keep it very subtle
            dry = audio_seg - int(10 * (1 - dry_wet))  # Less reduction on dry signal
            wet = reverb_seg - int(25 * (1 - room_size))  # More reduction on wet signal for subtlety
            final = dry.overlay(wet)
            
            # Normalize
            final = normalize(final)
            
            # Save and return as AudioFileClip
            output_path = os.path.join(TEMP_DIR, f"reverb_{hash(str(audio_clip)) % 10000}.mp3")
            final.export(output_path, format="mp3")
            
            from moviepy.editor import AudioFileClip
            return AudioFileClip(output_path)
            
        except Exception as e:
            print(f"  ⚠️  Could not add reverb: {e}")
            return audio_clip
    
    def _add_audio_echo(self, audio_clip, delay: float = 0.3, decay: float = 0.5, repeats: int = 2):
        """
        Add echo effect to audio
        delay: delay in seconds between echoes
        decay: volume decay per echo (0.0 to 1.0)
        repeats: number of echo repeats
        """
        try:
            from pydub import AudioSegment
            
            # Convert MoviePy clip to file if needed
            if hasattr(audio_clip, 'filename'):
                audio_seg = AudioSegment.from_file(audio_clip.filename)
            else:
                temp_path = os.path.join(TEMP_DIR, f"temp_echo_{hash(str(audio_clip)) % 10000}.mp3")
                audio_clip.write_audiofile(temp_path, verbose=False, logger=None)
                audio_seg = AudioSegment.from_file(temp_path)
            
            delay_ms = int(delay * 1000)
            echo_seg = audio_seg
            
            # Add echo repeats
            for i in range(repeats):
                echo_volume = decay ** (i + 1)
                echo_delay = delay_ms * (i + 1)
                
                if echo_delay < len(audio_seg):
                    # Create delayed echo
                    silence = AudioSegment.silent(duration=echo_delay)
                    echo = audio_seg - int(20 * (1 - echo_volume))  # Reduce volume
                    delayed_echo = silence + echo
                    
                    # Mix with original
                    echo_seg = echo_seg.overlay(delayed_echo[:len(echo_seg)])
            
            # Save and return
            output_path = os.path.join(TEMP_DIR, f"echo_{hash(str(audio_clip)) % 10000}.mp3")
            echo_seg.export(output_path, format="mp3")
            
            from moviepy.editor import AudioFileClip
            return AudioFileClip(output_path)
            
        except Exception as e:
            print(f"  ⚠️  Could not add echo: {e}")
            return audio_clip
    
    def _add_color_grading(self, clip, style: str = 'cinematic'):
        """
        Add color grading effects to video clip
        styles: 'cinematic', 'vibrant', 'dramatic', 'news', 'warm', 'cool'
        """
        try:
            def grade_frame(get_frame, t):
                frame = get_frame(t)
                
                if style == 'cinematic':
                    # Cinematic: desaturated, high contrast, slight blue tint
                    frame = frame.astype(np.float32)
                    # Desaturate slightly
                    gray = np.dot(frame[...,:3], [0.299, 0.587, 0.114])
                    frame[...,:3] = frame[...,:3] * 0.85 + gray[..., np.newaxis] * 0.15
                    # Add blue tint
                    frame[..., 2] = frame[..., 2] * 1.05  # Boost blue
                    # Increase contrast
                    frame = (frame - 128) * 1.1 + 128
                    frame = np.clip(frame, 0, 255).astype(np.uint8)
                    
                elif style == 'vibrant':
                    # Vibrant: boost saturation, increase contrast
                    frame = frame.astype(np.float32)
                    # Boost saturation
                    gray = np.dot(frame[...,:3], [0.299, 0.587, 0.114])
                    frame[...,:3] = frame[...,:3] * 1.2 + gray[..., np.newaxis] * (-0.2)
                    # Increase contrast
                    frame = (frame - 128) * 1.15 + 128
                    frame = np.clip(frame, 0, 255).astype(np.uint8)
                    
                elif style == 'dramatic':
                    # Dramatic: high contrast, dark shadows, bright highlights
                    frame = frame.astype(np.float32)
                    # High contrast curve
                    frame = np.power(frame / 255.0, 0.8) * 255
                    # Darken shadows
                    mask = frame < 128
                    frame[mask] = frame[mask] * 0.7
                    # Brighten highlights
                    mask = frame > 128
                    frame[mask] = frame[mask] * 1.1
                    frame = np.clip(frame, 0, 255).astype(np.uint8)
                    
                elif style == 'news':
                    # News: clean, neutral, slightly enhanced
                    frame = frame.astype(np.float32)
                    # Slight contrast boost
                    frame = (frame - 128) * 1.05 + 128
                    frame = np.clip(frame, 0, 255).astype(np.uint8)
                    
                elif style == 'warm':
                    # Warm: orange/yellow tint
                    frame = frame.astype(np.float32)
                    frame[..., 0] = frame[..., 0] * 1.1  # Boost red
                    frame[..., 1] = frame[..., 1] * 1.05  # Boost green
                    frame = np.clip(frame, 0, 255).astype(np.uint8)
                    
                elif style == 'cool':
                    # Cool: blue/cyan tint
                    frame = frame.astype(np.float32)
                    frame[..., 2] = frame[..., 2] * 1.1  # Boost blue
                    frame[..., 1] = frame[..., 1] * 1.05  # Boost green
                    frame = np.clip(frame, 0, 255).astype(np.uint8)
                
                return frame
            
            graded_clip = clip.fl(grade_frame, apply_to=['video'])
            return graded_clip
            
        except Exception as e:
            print(f"  ⚠️  Could not add color grading: {e}")
            return clip
    
    def _generate_effect_suggestions(self, script_data: Dict, image_prompts: List[str], video_description: str = "") -> Dict:
        """
        Use LLM to analyze script, image prompts, and video context to suggest which effects to apply where.
        Includes history of previous segments for each segment to ensure coherent flow.
        Returns a dict mapping segment indices to effect configurations.
        """
        try:
            segments = script_data.get('segments', [])
            if not segments:
                return {}
            
            # Build context for LLM with segment history
            video_title = script_data.get('title', 'News Video')
            segments_info = []
            
            for i, segment in enumerate(segments):
                segment_type = segment.get('type', 'summary')
                segment_text = segment.get('text', '')[:200]  # First 200 chars
                story_index = segment.get('story_index')
                image_prompt = image_prompts[i] if i < len(image_prompts) else "No image prompt"
                
                # Build history of previous segments (up to 3 previous segments for context)
                previous_segments = []
                for prev_idx in range(max(0, i - 3), i):
                    prev_segment = segments[prev_idx]
                    prev_segment_type = prev_segment.get('type', 'summary')
                    prev_segment_text = prev_segment.get('text', '')[:150]  # First 150 chars
                    prev_story_index = prev_segment.get('story_index')
                    prev_image_prompt = image_prompts[prev_idx] if prev_idx < len(image_prompts) else "No image prompt"
                    
                    previous_segments.append({
                        'index': prev_idx,
                        'type': prev_segment_type,
                        'text': prev_segment_text,
                        'story_index': prev_story_index,
                        'image_prompt': prev_image_prompt[:100]  # First 100 chars
                    })
                
                segments_info.append({
                    'index': i,
                    'type': segment_type,
                    'text': segment_text,
                    'story_index': story_index,
                    'image_prompt': image_prompt[:150],  # First 150 chars
                    'previous_segments': previous_segments  # History of previous segments
                })
            
            # Create prompt for LLM
            prompt = f"""You are a video production expert. Analyze this news video script and suggest appropriate visual and audio effects for each segment to maximize engagement while maintaining professionalism.

VIDEO TITLE: {video_title}
VIDEO DESCRIPTION: {video_description if video_description else "News video covering current events"}

AVAILABLE EFFECTS:
1. Visual Effects:
   - glitch: RGB shift, scan lines, digital artifacts (intensity: 0.0-1.0)
   - color_grading: cinematic, vibrant, dramatic, news, warm, cool
   - particles: sparkles, dust (intensity: 0.0-1.0)

2. Audio Effects:
   - reverb: room_size (0.0-1.0), damping (0.0-1.0)
   - echo: delay (seconds), decay (0.0-1.0), repeats (1-3)

SEGMENTS WITH HISTORY:
{json.dumps(segments_info, indent=2)}

IMPORTANT CONTEXT RULES:
- Each segment includes "previous_segments" showing what came before it
- Use this history to ensure smooth transitions and coherent effect flow
- If previous segment was dramatic, current segment can either continue the drama or transition to calmer
- If previous segment was calm, current segment can build tension or maintain calm
- Consider the narrative flow: opening → buildup → climax → resolution
- Effects should complement the story progression, not clash with previous segments

GUIDELINES:
- Headlines: Use dramatic color grading, subtle glitch effects (0.2-0.4 intensity), sparkles for breaking news
- Summaries: Use news or cinematic color grading, no glitch, subtle particles
- Breaking/Urgent news: Higher glitch intensity (0.3-0.5), dramatic color grading, echo effects
- Calm/Informative: Clean news color grading, no glitch, minimal effects
- Match effects to content tone: war/conflict = dramatic + glitch, business = news + warm, tech = vibrant + cool
- Audio effects: Use subtle reverb for depth (room_size: 0.1-0.2, damping: 0.6-0.8). AVOID echo effects - they cause unwanted echoing/repetition. Set echo enabled: false by default.
- TRANSITION CONSIDERATIONS:
  * If previous segment had high glitch (0.4+), current segment can reduce glitch for contrast (0.1-0.2) or maintain if same story
  * If previous segment was "dramatic" color grading, current segment can be "dramatic" (same story) or "news" (transition)
  * If previous segment had particles, current segment can continue or remove based on story continuity
  * Consider story_index: same story_index = similar effects, different story_index = can transition

Return JSON in this format:
{{
  "segment_effects": {{
    "0": {{
      "glitch": {{"enabled": true, "intensity": 0.3}},
      "color_grading": {{"style": "dramatic"}},
      "particles": {{"enabled": true, "type": "sparkles", "intensity": 0.2}},
      "audio_reverb": {{"enabled": true, "room_size": 0.2, "damping": 0.6}},
      "audio_echo": {{"enabled": false}},
      "transition_note": "Opening segment - setting dramatic tone"
    }},
    "1": {{
      "glitch": {{"enabled": false}},
      "color_grading": {{"style": "news"}},
      "particles": {{"enabled": false}},
      "audio_reverb": {{"enabled": true, "room_size": 0.15, "damping": 0.7}},
      "audio_echo": {{"enabled": false}},
      "transition_note": "Transitioning from dramatic opening to informative summary"
    }}
  }},
  "global_audio_effects": {{
    "reverb": {{"enabled": true, "room_size": 0.15, "damping": 0.7}},
    "echo": {{"enabled": false, "delay": 0.15, "decay": 0.3, "repeats": 1}}
  }}
}}

Return ONLY valid JSON, no markdown formatting."""
            
            # Get LLM response
            response = self.llm_client.generate(prompt, {
                "temperature": 0.3,  # Lower temperature for more consistent suggestions
                "num_predict": 2000,
            })
            
            if not response:
                print("  ⚠️  Could not get LLM effect suggestions, using defaults")
                return {}
            
            # Extract JSON from response
            content = response.get('response', '') if isinstance(response, dict) else str(response)
            
            # Try to extract JSON if wrapped in markdown
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            # Parse JSON
            try:
                suggestions = json.loads(content.strip())
                print(f"  ✅ Generated effect suggestions for {len(suggestions.get('segment_effects', {}))} segments")
                return suggestions
            except json.JSONDecodeError as e:
                print(f"  ⚠️  Could not parse LLM effect suggestions: {e}")
                print(f"  Response preview: {content[:200]}...")
                return {}
            
        except Exception as e:
            print(f"  ⚠️  Error generating effect suggestions: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _add_screen_shake(self, clip, intensity: float = 0.3, frequency: float = 10.0):
        """
        Add screen shake effect for dynamic impact
        intensity: 0.0 (none) to 1.0 (heavy shake)
        frequency: shakes per second
        """
        try:
            if intensity <= 0:
                return clip
            
            def shake_frame(get_frame, t):
                frame = get_frame(t)
                if not isinstance(frame, np.ndarray):
                    return frame
                
                h, w = frame.shape[:2]
                
                # Calculate shake offset based on time
                shake_amount = int(intensity * 15)  # Max 15 pixels at full intensity
                offset_x = int(np.sin(t * frequency * 2 * np.pi) * shake_amount * random.uniform(0.5, 1.5))
                offset_y = int(np.cos(t * frequency * 2 * np.pi) * shake_amount * random.uniform(0.5, 1.5))
                
                # Create new frame with shake
                new_frame = np.zeros_like(frame)
                
                # Calculate crop area
                x1 = max(0, offset_x)
                y1 = max(0, offset_y)
                x2 = min(w, w + offset_x)
                y2 = min(h, h + offset_y)
                
                # Calculate source area
                src_x1 = max(0, -offset_x)
                src_y1 = max(0, -offset_y)
                src_x2 = min(w, w - offset_x)
                src_y2 = min(h, h - offset_y)
                
                if x2 > x1 and y2 > y1 and src_x2 > src_x1 and src_y2 > src_y1:
                    new_frame[y1:y2, x1:x2] = frame[src_y1:src_y2, src_x1:src_x2]
                else:
                    return frame
                
                return new_frame
            
            return clip.fl(shake_frame, apply_to=['video'])
        except Exception as e:
            print(f"  ⚠️  Could not add screen shake: {e}")
            return clip
    
    def _add_flash_effect(self, clip, flash_times: List[float] = None, color: tuple = (255, 255, 255), intensity: float = 0.5):
        """
        Add flash/color pop effects at specific times
        flash_times: List of times (in seconds) to flash, or None for random
        color: RGB color of flash (default: white)
        intensity: 0.0 (none) to 1.0 (full flash)
        """
        try:
            if intensity <= 0:
                return clip
            
            duration = clip.duration
            if flash_times is None:
                # Random flashes: 2-4 flashes during the clip
                num_flashes = random.randint(2, 4)
                flash_times = [random.uniform(0.1, duration - 0.1) for _ in range(num_flashes)]
            
            def flash_frame(get_frame, t):
                frame = get_frame(t)
                if not isinstance(frame, np.ndarray):
                    return frame
                
                # Check if we're near a flash time
                flash_duration = 0.1  # 100ms flash
                for flash_time in flash_times:
                    if abs(t - flash_time) < flash_duration:
                        # Calculate flash intensity (fade in/out)
                        flash_progress = 1.0 - (abs(t - flash_time) / flash_duration)
                        flash_strength = intensity * flash_progress
                        
                        # Blend flash color with frame
                        flash_color = np.array(color, dtype=np.uint8)
                        if len(frame.shape) == 3:
                            frame = frame.astype(np.float32)
                            flash_color = flash_color.astype(np.float32)
                            frame = frame * (1 - flash_strength) + flash_color * flash_strength
                            frame = np.clip(frame, 0, 255).astype(np.uint8)
                
                return frame
            
            return clip.fl(flash_frame, apply_to=['video'])
        except Exception as e:
            print(f"  ⚠️  Could not add flash effect: {e}")
            return clip
    
    def _add_zoom_burst(self, clip, burst_times: List[float] = None, zoom_amount: float = 1.2):
        """
        Add quick zoom bursts for emphasis
        burst_times: List of times to zoom, or None for random
        zoom_amount: How much to zoom (1.2 = 20% zoom)
        """
        try:
            duration = clip.duration
            if burst_times is None:
                # Random bursts: 1-2 bursts during the clip
                num_bursts = random.randint(1, 2)
                burst_times = [random.uniform(0.2, duration - 0.2) for _ in range(num_bursts)]
            
            def zoom_burst_frame(get_frame, t):
                frame = get_frame(t)
                if not isinstance(frame, np.ndarray):
                    return frame
                
                h, w = frame.shape[:2]
                
                # Check if we're near a burst time
                burst_duration = 0.15  # 150ms burst
                zoom_factor = 1.0
                
                for burst_time in burst_times:
                    if abs(t - burst_time) < burst_duration:
                        # Calculate zoom (quick in and out)
                        progress = abs(t - burst_time) / burst_duration
                        if progress < 0.5:
                            # Zoom in
                            zoom_factor = 1.0 + (zoom_amount - 1.0) * (1 - progress * 2)
                        else:
                            # Zoom out
                            zoom_factor = 1.0 + (zoom_amount - 1.0) * ((progress - 0.5) * 2)
                
                if zoom_factor != 1.0:
                    from PIL import Image
                    pil_img = Image.fromarray(frame)
                    new_w = int(w * zoom_factor)
                    new_h = int(h * zoom_factor)
                    
                    # Resize
                    pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    
                    # Crop to center
                    crop_x = (new_w - w) // 2
                    crop_y = (new_h - h) // 2
                    pil_img = pil_img.crop((crop_x, crop_y, crop_x + w, crop_y + h))
                    
                    return np.array(pil_img)
                
                return frame
            
            return clip.fl(zoom_burst_frame, apply_to=['video'])
        except Exception as e:
            print(f"  ⚠️  Could not add zoom burst: {e}")
            return clip
    
    def _add_dynamic_transition(self, clip, transition_type: str = 'wipe', direction: str = 'right', duration: float = 0.3):
        """
        Add dynamic transitions (wipes, slides, etc.)
        transition_type: 'wipe', 'slide', 'fade', 'zoom'
        direction: 'left', 'right', 'up', 'down'
        """
        try:
            clip_duration = clip.duration
            
            if transition_type == 'wipe':
                def wipe_frame(get_frame, t):
                    frame = get_frame(t)
                    if not isinstance(frame, np.ndarray):
                        return frame
                    
                    h, w = frame.shape[:2]
                    
                    # Create wipe mask
                    if t < duration:
                        progress = t / duration
                        
                        if direction == 'right':
                            wipe_x = int(w * progress)
                            mask = np.zeros((h, w), dtype=np.uint8)
                            mask[:, :wipe_x] = 255
                        elif direction == 'left':
                            wipe_x = int(w * (1 - progress))
                            mask = np.zeros((h, w), dtype=np.uint8)
                            mask[:, wipe_x:] = 255
                        elif direction == 'down':
                            wipe_y = int(h * progress)
                            mask = np.zeros((h, w), dtype=np.uint8)
                            mask[:wipe_y, :] = 255
                        else:  # up
                            wipe_y = int(h * (1 - progress))
                            mask = np.zeros((h, w), dtype=np.uint8)
                            mask[wipe_y:, :] = 255
                        
                        # Apply mask
                        if len(frame.shape) == 3:
                            mask_3d = np.stack([mask, mask, mask], axis=2)
                            frame = frame * (mask_3d / 255.0)
                    
                    return frame
                
                return clip.fl(wipe_frame, apply_to=['video'])
            else:
                # Fallback to fade
                return clip.fadein(duration)
        except Exception as e:
            print(f"  ⚠️  Could not add dynamic transition: {e}")
            return clip
    
    def _add_speed_ramp(self, clip, ramp_times: List[tuple] = None):
        """
        Add speed ramping (slow motion / fast motion) at specific times
        ramp_times: List of (start_time, end_time, speed_factor) tuples
                    speed_factor: 0.5 = slow motion, 2.0 = fast motion
        """
        try:
            # This is a simplified version - full speed ramping requires frame interpolation
            # For now, we'll use time remapping
            if ramp_times:
                # Apply speed changes at specified times
                # Note: This is a placeholder - full implementation would require frame interpolation
                return clip
            return clip
        except Exception as e:
            print(f"  ⚠️  Could not add speed ramp: {e}")
            return clip
    
    def _add_motion_blur(self, clip, intensity: float = 0.3):
        """
        Add motion blur effect for dynamic movement
        intensity: 0.0 (none) to 1.0 (heavy blur)
        """
        try:
            if intensity <= 0:
                return clip
            
            def blur_frame(get_frame, t):
                frame = get_frame(t)
                if not isinstance(frame, np.ndarray):
                    return frame
                
                from PIL import Image, ImageFilter
                
                # Convert to PIL Image
                pil_img = Image.fromarray(frame)
                
                # Apply motion blur
                blur_radius = int(intensity * 5)  # Max 5 pixels blur
                if blur_radius > 0:
                    # Create motion blur effect
                    pil_img = pil_img.filter(ImageFilter.GaussianBlur(radius=blur_radius * 0.5))
                
                return np.array(pil_img)
            
            return clip.fl(blur_frame, apply_to=['video'])
        except Exception as e:
            print(f"  ⚠️  Could not add motion blur: {e}")
            return clip
    
    def _add_color_pop(self, clip, pop_times: List[float] = None, intensity: float = 0.5):
        """
        Add color pop effect (saturation boost) at specific times
        pop_times: List of times to pop, or None for random
        intensity: 0.0 (none) to 1.0 (full pop)
        """
        try:
            if intensity <= 0:
                return clip
            
            duration = clip.duration
            if pop_times is None:
                # Random pops: 2-3 pops during the clip
                num_pops = random.randint(2, 3)
                pop_times = [random.uniform(0.2, duration - 0.2) for _ in range(num_pops)]
            
            def pop_frame(get_frame, t):
                frame = get_frame(t)
                if not isinstance(frame, np.ndarray):
                    return frame
                
                # Check if we're near a pop time
                pop_duration = 0.2  # 200ms pop
                for pop_time in pop_times:
                    if abs(t - pop_time) < pop_duration:
                        # Calculate pop intensity (fade in/out)
                        pop_progress = 1.0 - (abs(t - pop_time) / pop_duration)
                        pop_strength = intensity * pop_progress
                        
                        # Boost saturation
                        frame = frame.astype(np.float32)
                        # Convert to HSV-like processing
                        gray = np.dot(frame[...,:3], [0.299, 0.587, 0.114])
                        gray_3d = gray[..., np.newaxis]
                        # Increase saturation by moving away from gray
                        frame[...,:3] = frame[...,:3] * (1 + pop_strength * 0.5) + gray_3d * (-pop_strength * 0.2)
                        frame = np.clip(frame, 0, 255).astype(np.uint8)
                
                return frame
            
            return clip.fl(pop_frame, apply_to=['video'])
        except Exception as e:
            print(f"  ⚠️  Could not add color pop: {e}")
            return clip
    
    def _add_strobe_effect(self, clip, strobe_frequency: float = 5.0, intensity: float = 0.3):
        """
        Add strobe/flashing effect
        strobe_frequency: flashes per second
        intensity: 0.0 (none) to 1.0 (full strobe)
        """
        try:
            if intensity <= 0:
                return clip
            
            def strobe_frame(get_frame, t):
                frame = get_frame(t)
                if not isinstance(frame, np.ndarray):
                    return frame
                
                # Calculate strobe (on/off based on time)
                strobe_phase = (t * strobe_frequency) % 1.0
                if strobe_phase < 0.5:  # On phase
                    strobe_strength = intensity * (1 - strobe_phase * 2)
                    # Brighten frame
                    frame = frame.astype(np.float32)
                    frame = frame * (1 + strobe_strength * 0.3)
                    frame = np.clip(frame, 0, 255).astype(np.uint8)
                
                return frame
            
            return clip.fl(strobe_frame, apply_to=['video'])
        except Exception as e:
            print(f"  ⚠️  Could not add strobe effect: {e}")
            return clip
    
    def _add_blank_cut_effect(self, clip, cut_times: List[float] = None, cut_duration: float = 0.1, color: tuple = (0, 0, 0)):
        """
        Add blank/black cut effect at specific times (quick cuts to black)
        cut_times: List of times (in seconds) to cut to blank, or None for random
        cut_duration: Duration of each cut in seconds (default: 0.1 = 100ms)
        color: Color of the blank cut (default: black (0,0,0))
        """
        try:
            duration = clip.duration
            if cut_times is None:
                # Random cuts: 1-3 cuts during the clip
                num_cuts = random.randint(1, 3)
                cut_times = [random.uniform(0.2, duration - 0.2) for _ in range(num_cuts)]
            
            def blank_cut_frame(get_frame, t):
                frame = get_frame(t)
                if not isinstance(frame, np.ndarray):
                    return frame
                
                h, w = frame.shape[:2]
                
                # Check if we're in a cut time
                for cut_time in cut_times:
                    if abs(t - cut_time) < cut_duration:
                        # Create blank frame with specified color
                        blank_frame = np.full((h, w, 3), color, dtype=np.uint8)
                        return blank_frame
                
                return frame
            
            return clip.fl(blank_cut_frame, apply_to=['video'])
        except Exception as e:
            print(f"  ⚠️  Could not add blank cut effect: {e}")
            return clip
    
    def _add_quick_cuts(self, clip, num_cuts: int = 2, cut_duration: float = 0.05):
        """
        Add quick cuts (very short blank cuts) for dynamic editing
        num_cuts: Number of quick cuts to add
        cut_duration: Duration of each cut (default: 0.05 = 50ms)
        """
        try:
            duration = clip.duration
            if duration < cut_duration * (num_cuts + 1):
                return clip  # Not enough time for cuts
            
            # Distribute cuts evenly throughout the clip
            cut_times = []
            spacing = duration / (num_cuts + 1)
            for i in range(1, num_cuts + 1):
                cut_time = spacing * i + random.uniform(-spacing * 0.2, spacing * 0.2)
                cut_time = max(0.1, min(cut_time, duration - 0.1))
                cut_times.append(cut_time)
            
            return self._add_blank_cut_effect(clip, cut_times=cut_times, cut_duration=cut_duration)
        except Exception as e:
            print(f"  ⚠️  Could not add quick cuts: {e}")
            return clip
    
    def _add_particle_overlay(self, clip, particle_type: str = 'sparkles', intensity: float = 0.3):
        """
        Add particle effects overlay (sparkles, dust, etc.)
        Note: This is a simplified version - full particle systems would require more complex rendering
        """
        try:
            if intensity <= 0:
                return clip
            
            def add_particles(get_frame, t):
                frame = get_frame(t)
                h, w = frame.shape[:2]
                
                if particle_type == 'sparkles':
                    # Add sparkle particles
                    num_particles = int(intensity * 20)
                    for _ in range(num_particles):
                        x = random.randint(0, w - 1)
                        y = random.randint(0, h - 1)
                        # Bright white sparkle
                        if 0 <= x < w and 0 <= y < h:
                            frame[y, x] = [255, 255, 255]
                            # Add glow
                            for dy in range(-1, 2):
                                for dx in range(-1, 2):
                                    ny, nx = y + dy, x + dx
                                    if 0 <= ny < h and 0 <= nx < w:
                                        frame[ny, nx] = np.minimum(frame[ny, nx] + 50, 255)
                
                elif particle_type == 'dust':
                    # Add dust particles (subtle)
                    num_particles = int(intensity * 10)
                    for _ in range(num_particles):
                        x = random.randint(0, w - 1)
                        y = random.randint(0, h - 1)
                        if 0 <= x < w and 0 <= y < h:
                            # Subtle gray particles
                            gray_val = random.randint(100, 150)
                            frame[y, x] = [gray_val, gray_val, gray_val]
                
                return frame
            
            particle_clip = clip.fl(add_particles, apply_to=['video'])
            return particle_clip
            
        except Exception as e:
            print(f"  ⚠️  Could not add particles: {e}")
            return clip
    
    def _create_transition_sound_effect(self, start_time: float, duration: float):
        """
        Create a subtle swish/glitch sound effect for image transitions
        Returns an AudioClip or None if creation fails
        """
        try:
            from pydub import AudioSegment
            import numpy as np
            
            sample_rate = 44100
            duration_ms = int(duration * 1000)
            num_samples = int(sample_rate * duration)
            
            # Create a subtle "swish" sound: white noise with frequency sweep
            t = np.linspace(0, duration, num_samples)
            
            # Generate white noise
            noise = np.random.normal(0, 0.1, num_samples)
            
            # Apply frequency sweep (high to low) for swish effect
            freq_start = 2000
            freq_end = 500
            freq_sweep = freq_start + (freq_end - freq_start) * t / duration
            sweep = np.sin(2 * np.pi * freq_sweep * t)
            
            # Combine noise and sweep, apply envelope
            envelope = np.exp(-t * 5)  # Quick decay
            sound = (noise * 0.3 + sweep * 0.2) * envelope
            
            # Very low volume (barely audible)
            sound = sound * 0.15
            
            # Convert to AudioSegment
            sound_array = (np.clip(sound, -1, 1) * 32767).astype(np.int16)
            audio_seg = AudioSegment(
                sound_array.tobytes(),
                frame_rate=sample_rate,
                channels=1,
                sample_width=2
            )
            
            # Save temporarily
            sfx_path = os.path.join(TEMP_DIR, f"transition_sfx_{hash(str(start_time)) % 10000}.mp3")
            audio_seg.export(sfx_path, format="mp3")
            
            # Create AudioClip
            from moviepy.editor import AudioFileClip
            sfx_clip = AudioFileClip(sfx_path)
            sfx_clip = sfx_clip.set_start(start_time)
            sfx_clip = sfx_clip.set_duration(duration)
            
            return sfx_clip
            
        except Exception as e:
            print(f"  ⚠️  Could not create transition sound effect: {e}")
            return None
    
    def _create_word_by_word_subtitles(self, text: str, start_time: float, duration: float, 
                                       position: str = 'center') -> List:
        """
        Create word-by-word subtitles that appear in the center of the screen, synced with audio
        
        Args:
            text: Full text to display word-by-word
            start_time: When subtitles start (seconds)
            duration: Total duration for the text (seconds)
            position: 'center' for middle of screen
            
        Returns:
            List of TextClip objects, one per word, appearing sequentially
        """
        words = text.split()
        if not words:
            return []
        
        # Calculate timing per word
        # Add small pause between words (0.1s) and account for word length
        base_time_per_word = duration / len(words)
        # Adjust for word length: longer words get slightly more time
        word_times = []
        total_chars = sum(len(word) for word in words)
        
        for word in words:
            # Base time + adjustment for word length
            word_time = base_time_per_word * (1 + len(word) / total_chars * 0.3)
            word_times.append(word_time)
        
        # Normalize to fit within duration
        total_time = sum(word_times)
        if total_time > duration:
            word_times = [t * (duration / total_time) for t in word_times]
        
        subtitle_clips = []
        current_time = start_time
        
        # Build text progressively (word 1, then word 1+2, then word 1+2+3, etc.)
        accumulated_text = ""
        
        for i, (word, word_duration) in enumerate(zip(words, word_times)):
            # Add word to accumulated text
            if accumulated_text:
                accumulated_text += " " + word
            else:
                accumulated_text = word
            
            # Create subtitle clip for accumulated text
            try:
                # Center position (middle of screen)
                if position == 'center':
                    y_pos = self.height // 2  # Middle vertically
                else:
                    y_pos = int(self.height * 0.80)  # Bottom (fallback)
                
                # Create text clip with viral-style formatting
                subtitle_clip = TextClip(
                    accumulated_text,
                    fontsize=72,  # Large font for center subtitles
                    color='white',
                    font='Arial-Bold',  # Bold for visibility
                    stroke_color='black',
                    stroke_width=4,  # Thick stroke for readability
                    method='caption',
                    size=(self.width - 100, None),  # Leave margins
                    align='center'
                ).set_start(current_time).set_duration(word_duration).set_position(('center', y_pos))
                
                subtitle_clips.append(subtitle_clip)
                
            except Exception as e:
                print(f"    ⚠️  Could not create subtitle for word {i+1}: {e}")
                # Continue with next word
            
            current_time += word_duration
        
        return subtitle_clips
    
    def _create_dynamic_captions(self, text: str, segment_type: str, start_time: float, 
                                 duration: float, panel_y: int, panel_height: int, story_index: int = None, headline_text: str = None) -> list:
        """
        Create dynamic captions with headline always visible and summary with progressive highlighting.
        - If headline_text is provided: Show headline at top (static), summary below with progressive highlighting
        - If no headline_text: Show text with progressive highlighting (for headline segments)
        Returns list of ImageClip objects.
        """
        clips = []
        
        # Format settings
        headline_font_size = 38  # Font size for headline/title
        summary_font_size = 30  # Font size for summary
        
        # Colors
        headline_color = (255, 215, 0)  # Gold for headline (always visible)
        summary_base_color = (180, 180, 180)  # Light gray for unspoken summary words
        summary_highlight_color = (255, 255, 255)  # White for currently spoken summary words
        summary_keyword_color = (100, 200, 255)  # Blue for keywords in summary
        
        stroke_color = (0, 0, 0)
        stroke_width = 2
        
        # Load fonts first (needed for both headline and summary)
        text_img_width = self.width - 80
        try:
            font_paths = [
                '/System/Library/Fonts/Helvetica.ttc',
                '/System/Library/Fonts/Arial.ttf',
                '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
            ]
            headline_font = None
            summary_font = None
            for font_path in font_paths:
                try:
                    if headline_font is None:
                        headline_font = ImageFont.truetype(font_path, headline_font_size)
                    if summary_font is None:
                        summary_font = ImageFont.truetype(font_path, summary_font_size)
                    if headline_font and summary_font:
                        break
                except:
                    continue
            if headline_font is None:
                headline_font = ImageFont.load_default()
            if summary_font is None:
                summary_font = ImageFont.load_default()
        except:
            headline_font = ImageFont.load_default()
            summary_font = ImageFont.load_default()
        
        # Calculate text layout variables (needed for both headline-only and summary segments)
        headline_line_height = int(headline_font_size * 1.3)
        summary_line_height = int(summary_font_size * 1.3)
        
        # If this is a headline-only segment (headline_text provided but no summary text), show headline statically
        # Note: 'story' type segments should have both headline and summary, so they should NOT return early
        # Extended video segments (content, introduction, conclusion, etc.) should also show text statically
        extended_segment_types = ['content', 'introduction', 'conclusion', 'opening', 'story_part1', 'story_part2', 'story_part3', 'story_part4']
        if headline_text and (not text or text.strip() == "" or segment_type == 'headline' or segment_type in extended_segment_types):
            # Just show the headline text statically (no progressive highlighting)
            caption_img = Image.new('RGBA', (text_img_width, panel_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(caption_img)
            
            # Use headline_text if provided, otherwise use text
            headline_display_text = headline_text if headline_text else text
            
            # Wrap headline text to fit
            headline_words = headline_display_text.split()
            headline_lines = []
            current_headline_line = []
            current_headline_width = 0
            
            for word in headline_words:
                test_bbox = draw.textbbox((0, 0), word, font=headline_font)
                word_width = test_bbox[2] - test_bbox[0] + 10
                
                if current_headline_width + word_width > text_img_width - 40 and current_headline_line:
                    headline_lines.append(' '.join(current_headline_line))
                    current_headline_line = [word]
                    current_headline_width = word_width
                else:
                    current_headline_line.append(word)
                    current_headline_width += word_width
            
            if current_headline_line:
                headline_lines.append(' '.join(current_headline_line))
            
            # Draw headline (max 3 lines for headline-only segments)
            headline_x = 20
            headline_y = 10
            for line_idx, headline_line in enumerate(headline_lines[:3]):
                if headline_y + headline_line_height > panel_height - 10:
                    break
                for adj in range(-stroke_width, stroke_width + 1):
                    for adj2 in range(-stroke_width, stroke_width + 1):
                        if adj != 0 or adj2 != 0:
                            draw.text((headline_x + adj, headline_y + adj2), headline_line, 
                                     font=headline_font, fill=stroke_color)
                draw.text((headline_x, headline_y), headline_line, font=headline_font, fill=headline_color)
                headline_y += headline_line_height
            
            # Save and create clip
            frame_img_path = os.path.join(TEMP_DIR, f"caption_headline_{hash(headline_display_text)}.png")
            caption_img.save(frame_img_path)
            
            # Ensure text appears immediately at start_time and stays for full duration
            # Use exact timing to avoid late appearance or early disappearance
            headline_clip = ImageClip(frame_img_path, duration=duration)
            headline_clip = headline_clip.set_start(start_time)
            # Explicitly set end time to ensure it doesn't end early
            headline_clip = headline_clip.set_end(start_time + duration)
            # Set duration explicitly to ensure full coverage
            headline_clip = headline_clip.set_duration(duration)
            headline_clip = headline_clip.set_position((40, panel_y + 10))
            
            clips.append(headline_clip)
            return clips
        
        # Identify keywords in summary text
        summary_text = text
        keywords = self._identify_keywords(summary_text)
        
        # Debug: Print what we're processing
        print(f"    📝 Caption function: text='{summary_text[:50]}...', headline_text={headline_text[:50] if headline_text else 'None'}...")
        
        # Text layout variables already calculated above (before headline-only check)
        
        # Reserve space for headline if present (account for wrapping)
        headline_space = 0
        if headline_text:
            # Create test draw object for accurate measurement
            test_img = Image.new('RGBA', (text_img_width, 100))
            test_draw = ImageDraw.Draw(test_img)
            
            # Calculate how many lines the headline will take
            headline_words = headline_text.split()
            headline_lines_count = 1
            current_headline_width = 0
            for word in headline_words:
                word_bbox = test_draw.textbbox((0, 0), word, font=headline_font)
                word_width = word_bbox[2] - word_bbox[0] + 10
                if current_headline_width + word_width > text_img_width - 40 and headline_lines_count == 1:
                    headline_lines_count = 2
                    break
                current_headline_width += word_width
            # Limit to 2 lines max to leave room for summary
            headline_lines_count = min(2, headline_lines_count)
            headline_space = (headline_line_height * headline_lines_count) + 10  # Headline lines + spacing
            print(f"    📏 Headline will take {headline_lines_count} lines, reserving {headline_space}px")
        
        # Available space for summary
        summary_max_height = panel_height - headline_space - 10
        # Allow more lines - calculate based on available space (up to 8-10 lines)
        # For extended videos or long summaries, we'll create multiple caption clips
        summary_max_lines = min(10, int(summary_max_height / summary_line_height))
        if summary_max_lines < 3:
            summary_max_lines = 3  # Minimum 3 lines
        
        # Calculate how summary text will wrap
        summary_words = summary_text.split()
        total_summary_words = len(summary_words)
        
        if total_summary_words == 0:
            return clips
        
        # Calculate timing: each word appears based on actual speaking rate
        speaking_rate = 2.5  # words per second
        
        # If there's a headline, calculate how long it takes to read
        headline_duration = 0
        if headline_text:
            headline_words = len(headline_text.split())
            headline_duration = headline_words / speaking_rate  # Time to read headline
            print(f"    ⏱️  Headline duration: {headline_duration:.2f}s ({headline_words} words)")
        
        # Summary duration is the remaining time after headline
        summary_duration = duration - headline_duration
        if summary_duration <= 0:
            summary_duration = duration * 0.7  # Fallback: use 70% of total duration for summary
        
        # Distribute summary time evenly across summary words
        word_duration = summary_duration / total_summary_words if total_summary_words > 0 else 0.3
        word_duration = max(0.1, min(word_duration, 0.5))  # Between 100ms and 500ms per word
        
        print(f"    ⏱️  Summary duration: {summary_duration:.2f}s, word_duration: {word_duration:.3f}s per word")
        
        # Calculate summary text wrapping
        summary_lines = []
        current_line = []
        current_line_width = 0
        
        # Create a test draw object for accurate width measurement
        test_img = Image.new('RGBA', (text_img_width, 100))
        test_draw = ImageDraw.Draw(test_img)
        
        # Available width for text (with padding on both sides)
        available_width = text_img_width - 40  # 20px left + 20px right padding
        
        print(f"    📏 Wrapping summary: {total_summary_words} words, available width: {available_width}px, max lines per page: {summary_max_lines}")
        
        # Don't truncate - allow all words to be wrapped into lines
        # We'll create multiple "pages" of captions if needed
        for word in summary_words:
            # Test word width using actual font
            word_bbox = test_draw.textbbox((0, 0), word, font=summary_font)
            word_width = word_bbox[2] - word_bbox[0] + 10  # Add space between words
            
            # Check if word fits on current line
            if current_line_width + word_width > available_width and current_line:
                # Start new line
                summary_lines.append(current_line)
                current_line = [word]
                current_line_width = word_width
            else:
                current_line.append(word)
                current_line_width += word_width
        
        # Add the last line
        if current_line:
            summary_lines.append(current_line)
        
        # If we have more lines than can fit in one panel, we'll create multiple caption pages
        # Each page will show a subset of lines and transition to the next
        total_summary_lines = len(summary_lines)
        print(f"    ✅ Created {total_summary_lines} summary lines (will create multiple pages if > {summary_max_lines} lines)")
        
        # Ensure we have at least one line
        if not summary_lines and summary_words:
            # Fallback: put all words in one line (will be truncated if too long)
            summary_lines = [summary_words[:20]]  # Limit to 20 words max
            print(f"    ⚠️  No lines created, using fallback: {len(summary_lines[0])} words")
        
        total_summary_lines = len(summary_lines)
        print(f"    ✅ Created {total_summary_lines} summary lines")
        
        # If we have more lines than can fit, create multiple "pages" of captions
        # Each page shows summary_max_lines lines, and we'll transition between pages
        num_pages = (total_summary_lines + summary_max_lines - 1) // summary_max_lines if summary_max_lines > 0 else 1
        if num_pages > 1:
            print(f"    📄 Summary is {total_summary_lines} lines, creating {num_pages} pages ({summary_max_lines} lines per page)")
        
        # Create images for progressive highlighting
        # Create a frame every 2-3 words for efficiency, or every word for very short segments
        words_per_frame = 2 if total_summary_words > 10 else 1  # More frames for short text, fewer for long
        num_frames = (total_summary_words + words_per_frame - 1) // words_per_frame  # Ceiling division
        
        for frame_idx in range(num_frames):
            words_in_frame = min(words_per_frame, total_summary_words - frame_idx * words_per_frame)
            word_start_idx = frame_idx * words_per_frame
            word_end_idx = min(word_start_idx + words_in_frame, total_summary_words)
            
            # Calculate timing for this frame
            # Summary highlighting starts immediately with segment (headline shows at same time)
            # Both headline and summary should be visible from start_time
            summary_start_time = start_time  # Start immediately, not after headline
            frame_start = summary_start_time + (word_start_idx * word_duration)
            frame_duration = words_in_frame * word_duration
            
            # For the first frame, ensure it starts exactly at segment start
            if frame_idx == 0:
                frame_start = start_time
            
            # For the last frame, ensure it extends to segment end
            if frame_idx == num_frames - 1:
                frame_end = start_time + duration
            else:
                # For intermediate frames, calculate end based on next frame start
                next_frame_start = summary_start_time + ((word_start_idx + words_in_frame) * word_duration)
                frame_end = min(next_frame_start, start_time + duration)
            
            # Ensure frame_end never exceeds segment end
            frame_end = min(frame_end, start_time + duration)
            
            # Create image with headline (if present) + summary with progressive highlighting
            caption_img = Image.new('RGBA', (text_img_width, panel_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(caption_img)
            
            current_y = 10
            
            # Draw headline (always visible, static) if present
            if headline_text:
                headline_x = 20
                # Wrap headline text to fit within text_img_width
                headline_words = headline_text.split()
                headline_lines = []
                current_headline_line = []
                current_headline_width = 0
                
                for word in headline_words:
                    # Test word width
                    test_bbox = ImageDraw.Draw(Image.new('RGBA', (100, 100))).textbbox((0, 0), word, font=headline_font)
                    word_width = test_bbox[2] - test_bbox[0] + 10  # Add space
                    
                    if current_headline_width + word_width > text_img_width - 40 and current_headline_line:  # 40 for padding
                        # Start new line
                        headline_lines.append(' '.join(current_headline_line))
                        current_headline_line = [word]
                        current_headline_width = word_width
                    else:
                        current_headline_line.append(word)
                        current_headline_width += word_width
                
                if current_headline_line:
                    headline_lines.append(' '.join(current_headline_line))
                
                # Draw headline lines (max 2 lines to leave room for summary)
                max_headline_lines = min(2, len(headline_lines))
                for line_idx, headline_line in enumerate(headline_lines[:max_headline_lines]):
                    if current_y + headline_line_height > panel_height * 0.4:  # Don't take more than 40% of panel
                        break
                    # Draw headline line with stroke
                    for adj in range(-stroke_width, stroke_width + 1):
                        for adj2 in range(-stroke_width, stroke_width + 1):
                            if adj != 0 or adj2 != 0:
                                draw.text((headline_x + adj, current_y + adj2), headline_line, 
                                         font=headline_font, fill=stroke_color)
                    draw.text((headline_x, current_y), headline_line, font=headline_font, fill=headline_color)
                    current_y += headline_line_height
                
                current_y += 10  # Spacing after headline
            
            # Draw summary with progressive highlighting
            # Determine which "page" of lines to show based on current word position
            word_count = 0
            summary_started = False
            
            # Calculate which page we're on based on word_start_idx
            # Distribute words across pages
            if num_pages > 1:
                words_per_page = total_summary_words / num_pages
                current_page = min(int(word_start_idx / words_per_page), num_pages - 1)
                page_start_line = current_page * summary_max_lines
                page_end_line = min((current_page + 1) * summary_max_lines, total_summary_lines)
                lines_to_show = summary_lines[page_start_line:page_end_line]
            else:
                lines_to_show = summary_lines[:summary_max_lines]  # Show first page only
            
            for line_idx, line_words in enumerate(lines_to_show):
                # Check if we have space for this line
                if current_y + summary_line_height > panel_height - 10:  # Leave 10px margin at bottom
                    # If we're on a multi-page summary, this is expected - continue to next page
                    if num_pages > 1:
                        # We'll create another caption clip for the next page
                        pass
                    elif not summary_started:
                        # If we haven't drawn any summary yet, draw at least one line
                        pass
                    else:
                        break
                
                current_x = 20
                summary_started = True
                
                # Calculate actual line index in full summary_lines array
                if num_pages > 1:
                    actual_line_idx = page_start_line + line_idx
                else:
                    actual_line_idx = line_idx
                
                # Calculate word start index for this line (cumulative word count up to this line)
                line_word_start = sum(len(summary_lines[i]) for i in range(actual_line_idx))
                
                for word_idx, word in enumerate(line_words):
                    # Get word width using the actual draw object
                    word_bbox = draw.textbbox((0, 0), word, font=summary_font)
                    word_width = word_bbox[2] - word_bbox[0] + 10  # Add space between words
                    
                    # Check if word fits on current line (with 20px padding on each side)
                    max_x = text_img_width - 20  # Right margin
                    if current_x + word_width > max_x and current_x > 20:
                        # Word doesn't fit on this line - this shouldn't happen if wrapping worked correctly
                        # But if it does, just break to avoid overflow
                        print(f"  ⚠️  Warning: Word '{word}' doesn't fit on line (x={current_x}, width={word_width}, max={max_x})")
                        break
                    
                    # Calculate global word index
                    word_count = line_word_start + word_idx
                    
                    word_clean = word.lower().strip('.,!?;:()[]{}"\'-')
                    is_keyword = word_clean in keywords
                    
                    # Determine color based on word position
                    if word_count < word_start_idx:
                        # Already spoken: use base color (lighter)
                        word_color = summary_base_color
                    elif word_start_idx <= word_count < word_end_idx:
                        # Currently being spoken: use highlight color
                        word_color = summary_highlight_color if not is_keyword else summary_keyword_color
                    else:
                        # Not yet spoken: use dimmed color
                        word_color = tuple(int(c * 0.5) for c in summary_base_color)
                    
                    # Draw word with stroke
                    for adj in range(-stroke_width, stroke_width + 1):
                        for adj2 in range(-stroke_width, stroke_width + 1):
                            if adj != 0 or adj2 != 0:
                                draw.text((current_x + adj, current_y + adj2), word, 
                                         font=summary_font, fill=stroke_color)
                    
                    draw.text((current_x, current_y), word, font=summary_font, fill=word_color)
                    
                    # Move to next word position
                    current_x += word_width
                
                current_y += summary_line_height
            
            # Save frame image
            frame_hash = hash(f"{headline_text}_{summary_text}") if headline_text else hash(summary_text)
            frame_img_path = os.path.join(TEMP_DIR, f"caption_frame_{frame_hash}_{frame_idx}.png")
            caption_img.save(frame_img_path)
            
            # Create clip for this frame
            # Ensure clip duration matches exactly and doesn't end early
            frame_clip_duration = frame_end - frame_start
            # Ensure minimum duration to avoid gaps
            frame_clip_duration = max(frame_clip_duration, 0.1)
            frame_clip = ImageClip(frame_img_path, duration=frame_clip_duration)
            frame_clip = frame_clip.set_start(frame_start)
            frame_clip = frame_clip.set_end(frame_end)
            # Explicitly set duration to ensure it doesn't get cut off
            frame_clip = frame_clip.set_duration(frame_clip_duration)
            frame_clip = frame_clip.set_position((40, panel_y + 10))
            
            # Debug: Log frame timing to verify it's correct
            if frame_idx == 0 or frame_idx == num_frames - 1:
                print(f"      Frame {frame_idx + 1}/{num_frames}: start={frame_start:.3f}s, end={frame_end:.3f}s, duration={frame_clip_duration:.3f}s (segment: {start_time:.3f}s to {start_time + duration:.3f}s)")
            
            clips.append(frame_clip)
        
        return clips
    
    def create_video(self, image_paths: list, audio_path: str, script_data: dict, output_filename: str, segment_timings: list = None, is_extended: bool = False) -> str:
        """
        Create final video from images and audio, syncing images with TTS segments
        segment_timings: List of dicts with 'start_time' and 'duration' for each segment
        is_extended: If True, assign unique image to each segment (for extended videos)
        """
        try:
            # Load audio
            audio = AudioFileClip(audio_path)
            # Use actual audio duration (don't limit to VIDEO_DURATION for extended videos)
            audio_duration = audio.duration
            
            # Use segment timings if provided, otherwise fall back to script_data segments
            # IMPORTANT: segment_timings might not have story_index, so prefer script_data segments
            if script_data.get('segments'):
                segments = script_data['segments']
                # Update with actual timings from segment_timings if available
                if segment_timings and len(segment_timings) == len(segments):
                    for i, timing in enumerate(segment_timings):
                        if i < len(segments):
                            segments[i]['start_time'] = timing.get('start_time', segments[i].get('start_time', 0))
                            segments[i]['duration'] = timing.get('duration', segments[i].get('duration', 0))
            elif segment_timings:
                segments = segment_timings
            else:
                # Fallback: divide evenly
                segments = [{'start_time': i * (audio_duration / len(image_paths)), 
                            'duration': audio_duration / len(image_paths)} 
                           for i in range(len(image_paths))]
            
            # Generate LLM-based effect suggestions
            print("\n  🤖 Generating AI effect suggestions based on script and image prompts...")
            image_prompts = script_data.get('image_prompts', [])
            video_description = script_data.get('description', script_data.get('title', ''))
            try:
                effect_suggestions = self._generate_effect_suggestions(script_data, image_prompts, video_description)
                segment_effects = effect_suggestions.get('segment_effects', {})
                global_audio_effects = effect_suggestions.get('global_audio_effects', {})
                print(f"  ✅ Effect suggestions generated: {len(segment_effects)} segments with effects")
            except Exception as e:
                print(f"  ⚠️  Could not generate effect suggestions: {e}")
                print(f"  🔄 Using default effects for headlines...")
                segment_effects = {}
                global_audio_effects = {}
            
            # Create video clips from images, synced with audio segments
            # Structure: headline segments get new images, summary segments reuse headline's image
            all_clips = []  # All video clips to composite together
            audio_clips = []  # All audio clips (SFX) to combine separately
            
            # Map story_index to image_index
            # Image order: [0=Hook, 1=Story1, 2=Story2, 3=Story3, 4=Story4, 5=Story5, 6=Closing]
            # Each story (headline + summary) should use the same image
            story_to_image = {}  # Maps story_index -> image_index
            
            print(f"\n  🖼️  Available images: {len(image_paths)}")
            print(f"  📋 Segments: {len(segments)}")
            
            # Iterate over segments to properly match headline+summary pairs with images
            for i, segment in enumerate(segments):
                segment_start = segment.get('start_time', i * (audio_duration / len(segments)))
                segment_duration = segment.get('duration', audio_duration / len(segments))
                segment_type = segment.get('type', 'summary')
                story_index = segment.get('story_index')  # Which story this segment belongs to (1, 2, 3, 4, 5)
                
                # Initialize image_path for this segment (reset from previous iteration)
                image_path = None
                image_index_to_use = None
                
                # Debug: Print segment info
                if i < 5:  # Print first 5 segments for debugging
                    print(f"  🔍 Debug Segment {i+1}: type={segment_type}, story_index={story_index}, text={segment.get('text', '')[:40]}...")
                
                # Check if this is the closing segment first (before checking story_index)
                is_closing_segment = (i == len(segments) - 1)
                
                # Determine which image to use for this segment
                if is_closing_segment:
                    # Closing segment: Use fixed closing image
                    print(f"  🔍 Detected closing segment at index {i} (total segments: {len(segments)})")
                    if os.path.exists(self.closing_image_path):
                        image_path = self.closing_image_path
                        print(f"  🎬 Using fixed closing image: {os.path.basename(image_path)}")
                    else:
                        # Fallback to last image if closing image doesn't exist
                        print(f"  ⚠️  Closing image not found at: {self.closing_image_path}")
                        if image_paths and len(image_paths) > 0:
                            image_index_to_use = len(image_paths) - 1
                            image_path = image_paths[image_index_to_use]
                            print(f"  🔄 Using fallback image: {os.path.basename(image_path)}")
                        else:
                            print(f"  ❌ No images available for closing segment!")
                            continue
                elif is_extended:
                    # For extended videos: Assign unique image to each segment (change images frequently)
                    # Use segment index to cycle through available images
                    if i == 0:
                        # Opening segment: Use fixed opening image
                        if os.path.exists(self.opening_image_path):
                            image_path = self.opening_image_path
                            print(f"  🎬 Using fixed opening image: {os.path.basename(image_path)}")
                        else:
                            image_index_to_use = 0
                            image_path = image_paths[0] if image_paths else None
                    else:
                        # Assign image based on segment index (cycle through ALL available images)
                        # For extended videos, we want to use different images for each segment
                        available_image_count = len(image_paths)
                        if available_image_count > 0:
                            # Cycle through all images using modulo
                            # Segment 1 (i=1) -> image 0, Segment 2 (i=2) -> image 1, etc.
                            # This ensures we use all images and cycle back if needed
                            image_index_to_use = (i - 1) % available_image_count
                            if image_index_to_use >= available_image_count:
                                image_index_to_use = available_image_count - 1
                            if image_index_to_use < 0:
                                image_index_to_use = 0
                        else:
                            image_index_to_use = 0
                        
                        if image_paths and len(image_paths) > image_index_to_use:
                            image_path = image_paths[image_index_to_use]
                        else:
                            image_path = image_paths[0] if image_paths else None
                        print(f"  🖼️  Extended video: Segment {i+1} -> Image {image_index_to_use + 1}/{len(image_paths)} ({os.path.basename(image_path) if image_path else 'None'})")
                # Check for viral format segments FIRST (regardless of story_index)
                # This handles single-story viral videos where segments might not have story_index or all have same story_index
                elif segment_type in ['hook', 'what_happened', 'impact', 'facts', 'cta']:
                    # Viral format: cycle through images based on segment type
                    if segment_type == 'what_happened':
                        # What happened uses first story image
                        image_index_to_use = 0
                        print(f"  🔄 What happened: Using image 1/{len(image_paths)}")
                    elif segment_type == 'impact':
                        # For impact segments, cycle through images (use different image for each impact statement)
                        # Count how many impact segments we've seen so far
                        impact_count = sum(1 for j in range(i) if segments[j].get('type') == 'impact')
                        # Use different image for each impact statement (start from image 1, after what_happened uses 0)
                        image_index_to_use = min(impact_count + 1, len(image_paths) - 1)
                        if image_index_to_use >= len(image_paths):
                            image_index_to_use = len(image_paths) - 1
                        if image_index_to_use < 1:
                            image_index_to_use = 1 if len(image_paths) > 1 else 0
                        print(f"  🔄 Impact statement {impact_count + 1}: Using image {image_index_to_use + 1}/{len(image_paths)}")
                    elif segment_type == 'facts':
                        # Facts segments use different images - cycle through available images
                        # Count facts segments seen so far
                        facts_count = sum(1 for j in range(i) if segments[j].get('type') == 'facts')
                        # Facts use images 2, 3, 4, etc. (after what_happened uses image 0, impact uses 1+)
                        image_index_to_use = min(facts_count + 2, len(image_paths) - 1)
                        if image_index_to_use >= len(image_paths):
                            image_index_to_use = len(image_paths) - 1
                        if image_index_to_use < 2:
                            image_index_to_use = 2 if len(image_paths) > 2 else min(1, len(image_paths) - 1)
                        print(f"  🔄 Facts segment {facts_count + 1}: Using image {image_index_to_use + 1}/{len(image_paths)}")
                    elif segment_type == 'cta':
                        # CTA uses last image or cycles back
                        image_index_to_use = len(image_paths) - 1 if len(image_paths) > 0 else 0
                        print(f"  🔄 CTA: Using image {image_index_to_use + 1}/{len(image_paths)}")
                    elif segment_type == 'hook':
                        # Hook uses first image (though hook is usually removed now)
                        image_index_to_use = 0
                        print(f"  🔄 Hook: Using image 1/{len(image_paths)}")
                    
                    # Validate and set image_path
                    if image_index_to_use < 0:
                        image_index_to_use = 0
                    if image_index_to_use >= len(image_paths):
                        image_index_to_use = len(image_paths) - 1
                    if image_paths and len(image_paths) > image_index_to_use:
                        image_path = image_paths[image_index_to_use]
                    else:
                        image_path = image_paths[0] if image_paths else None
                elif story_index is not None:
                    # This segment belongs to a specific story (non-viral format)
                    # story_index is 1-based (1, 2, 3, 4, 5)
                    # Image order: image_paths[0] = Story1, image_paths[1] = Story2, etc.
                    # Note: Hook and closing images are handled separately, so image_paths contains only story images
                    # Regular story mapping
                    if story_index not in story_to_image:
                        # First time seeing this story - map to corresponding image
                        # story_index 1 -> image_paths[0], story_index 2 -> image_paths[1], etc.
                        # Convert 1-based story_index to 0-based image index
                        image_index = story_index - 1  # story_index 1 -> 0, story_index 2 -> 1, etc.
                        
                        # Ensure we don't exceed available images
                        if image_index < 0:
                            image_index = 0
                        if image_index >= len(image_paths):
                            image_index = len(image_paths) - 1
                        
                        story_to_image[story_index] = image_index
                        print(f"  🔗 Mapped Story {story_index} -> Image {image_index} (image_paths[{image_index}])")
                    image_index_to_use = story_to_image[story_index]
                    
                    # Validate image_index_to_use is within bounds
                    if image_index_to_use < 0:
                        image_index_to_use = 0
                    if image_index_to_use >= len(image_paths):
                        image_index_to_use = len(image_paths) - 1
                    
                    # Set image_path from the mapped index
                    if image_paths and len(image_paths) > image_index_to_use:
                        image_path = image_paths[image_index_to_use]
                    else:
                        print(f"  ⚠️  Image index {image_index_to_use} out of range (available: {len(image_paths)}), using first image")
                        image_path = image_paths[0] if image_paths else None
                elif segment_type == 'summary' and i > 0:
                    # Summary segment without story_index - try to find the previous headline segment
                    # Look backwards to find the most recent headline segment with story_index
                    found_story_index = None
                    for j in range(i-1, -1, -1):
                        prev_seg = segments[j]
                        prev_story_idx = prev_seg.get('story_index')
                        if prev_story_idx is not None:
                            found_story_index = prev_story_idx
                            break
                    
                    if found_story_index is not None and found_story_index in story_to_image:
                        image_index_to_use = story_to_image[found_story_index]
                        # Set image_path from the mapped index
                        if image_paths and len(image_paths) > image_index_to_use:
                            image_path = image_paths[image_index_to_use]
                        else:
                            image_path = image_paths[0] if image_paths else None
                    else:
                        # If no story_index found, assign based on segment position
                        # After hook (i=0), segments should be: Story1 headline (i=1), Story1 summary (i=2), Story2 headline (i=3), etc.
                        # So: i=1,2 -> Story1 (image 1), i=3,4 -> Story2 (image 2), etc.
                        if i > 0:
                            # Calculate which story this should be: (i-1) // 2 + 1
                            # i=1,2 -> story 1, i=3,4 -> story 2, i=5,6 -> story 3
                            calculated_story = ((i - 1) // 2) + 1
                            # Convert story number to image index (0-based)
                            image_index_to_use = calculated_story - 1  # story 1 -> 0, story 2 -> 1
                            if image_index_to_use < 0:
                                image_index_to_use = 0
                            if image_index_to_use >= len(image_paths):
                                image_index_to_use = len(image_paths) - 1
                            print(f"  🔄 Calculated story {calculated_story} -> Image {image_index_to_use} for segment {i+1} (no story_index)")
                            # Set image_path from calculated index
                            if image_paths and len(image_paths) > image_index_to_use:
                                image_path = image_paths[image_index_to_use]
                            else:
                                image_path = image_paths[0] if image_paths else None
                        else:
                            image_index_to_use = 0
                            image_path = image_paths[0] if image_paths else None
                elif i == 0 and (story_index is None or segment_type == 'opening'):
                    # Hook/opening segment: Use fixed opening image (separate from first story)
                    if os.path.exists(self.opening_image_path):
                        image_path = self.opening_image_path
                        print(f"  🎬 Segment {i+1} (Opening): Using fixed opening image: {os.path.basename(image_path)}")
                    else:
                        # Fallback to first image if opening image doesn't exist
                        image_index_to_use = 0
                        if image_paths and len(image_paths) > 0:
                            image_path = image_paths[image_index_to_use]
                            print(f"  ⚠️  Opening image not found, using first story image as fallback")
                        else:
                            print(f"  ❌ No images available for opening segment!")
                            continue
                        print(f"  ⚠️  Opening image not found at {self.opening_image_path}, using first image instead")
                else:
                    # Other segments without story_index (shouldn't happen often, but handle gracefully)
                    print(f"  ⚠️  Segment {i+1} has no story_index and is not hook/closing, using calculated image")
                    # Calculate based on position
                    calculated_story = ((i - 1) // 2) + 1
                    # Convert story number to image index (0-based)
                    image_index_to_use = calculated_story - 1 if image_paths else 0
                    if image_index_to_use < 0:
                        image_index_to_use = 0
                    if image_paths and image_index_to_use >= len(image_paths):
                        image_index_to_use = len(image_paths) - 1
                    if image_paths and len(image_paths) > image_index_to_use:
                        image_path = image_paths[image_index_to_use]
                    else:
                        image_path = image_paths[0] if image_paths else None
                        if not image_path:
                            print(f"  ❌ No images available!")
                            continue
                
                # Ensure we have a valid image (only if not using fixed opening/closing)
                # Skip validation for hook (i==0 with no story_index) and closing segments (already handled above)
                # Also skip if image_path is already set (e.g., for viral format segments or fixed images)
                is_opening_segment = (i == 0 and story_index is None)
                if not is_opening_segment and i != len(segments) - 1 and image_path is None:  # Skip validation if image_path already set
                    if image_index_to_use is not None:
                        if image_index_to_use >= len(image_paths):
                            image_index_to_use = len(image_paths) - 1
                        if image_index_to_use < 0:
                            image_index_to_use = 0
                        # Set image_path from image_index_to_use
                        if image_paths and len(image_paths) > 0:
                            image_path = image_paths[image_index_to_use]
                    elif image_path is None:
                        # Fallback: use calculated story index or first available
                        if image_paths and len(image_paths) > 0:
                            if story_index is not None:
                                # Convert story index to image index (0-based)
                                # story_index 1 -> image_paths[0], story_index 2 -> image_paths[1], etc.
                                # Note: opening segment (i==0, no story_index) uses fixed image, so story_index starts at 1
                                image_index_to_use = story_index - 1
                                if image_index_to_use < 0:
                                    image_index_to_use = 0
                                if image_index_to_use >= len(image_paths):
                                    image_index_to_use = len(image_paths) - 1
                                print(f"  📍 Story {story_index} mapped to image {image_index_to_use + 1}/{len(image_paths)}")
                            else:
                                # Calculate based on position
                                calculated_story = ((i - 1) // 2) + 1
                                image_index_to_use = calculated_story - 1
                                if image_index_to_use < 0:
                                    image_index_to_use = 0
                                if image_index_to_use >= len(image_paths):
                                    image_index_to_use = len(image_paths) - 1
                            image_path = image_paths[image_index_to_use]
                        else:
                            print(f"  ❌ No images available!")
                            continue
                
                # Verify image file exists (only if image_path is set)
                if image_path and not os.path.exists(image_path):
                    print(f"  ⚠️  Warning: Image file not found: {image_path}")
                    # Use first available image as fallback
                    if image_paths:
                        image_path = image_paths[0]
                        print(f"  🔄 Using fallback image: {os.path.basename(image_path)}")
                    else:
                        print("  ❌ No images available!")
                        continue
                elif not image_path:
                    # If image_path is still None at this point, something went wrong
                    print(f"  ❌ Error: image_path is None for segment {i+1} (type: {segment_type})")
                    if image_paths:
                        image_path = image_paths[0]
                        print(f"  🔄 Using first image as emergency fallback: {os.path.basename(image_path)}")
                    else:
                        print("  ❌ No images available!")
                        continue
                
                # Log image assignment for debugging
                # Check if using fixed images (opening/closing) which don't have image_index_to_use
                # Only treat as opening if it's actually the opening image path AND has no story_index
                is_fixed_image = (i == 0 and story_index is None and image_path == self.opening_image_path) or \
                                (i == len(segments) - 1 and image_path == self.closing_image_path)
                
                if story_index is not None:
                    if is_fixed_image:
                        print(f"  📸 Segment {i+1}: Story {story_index} ({segment_type}) -> Fixed image: {os.path.basename(image_path)} [start={segment_start:.1f}s, dur={segment_duration:.1f}s]")
                    else:
                        print(f"  📸 Segment {i+1}: Story {story_index} ({segment_type}) -> Image {image_index_to_use + 1}/{len(image_paths)}: {os.path.basename(image_path)} [start={segment_start:.1f}s, dur={segment_duration:.1f}s]")
                elif i == 0 and story_index is None:
                    print(f"  📸 Segment {i+1}: Hook -> Fixed opening image: {os.path.basename(image_path)} [start={segment_start:.1f}s, dur={segment_duration:.1f}s]")
                elif i == len(segments) - 1:
                    print(f"  📸 Segment {i+1}: Closing -> Fixed closing image: {os.path.basename(image_path)} [start={segment_start:.1f}s, dur={segment_duration:.1f}s]")
                else:
                    if 'image_index_to_use' in locals():
                        print(f"  📸 Segment {i+1}: ({segment_type}) -> Image {image_index_to_use + 1}/{len(image_paths)}: {os.path.basename(image_path)} [start={segment_start:.1f}s, dur={segment_duration:.1f}s]")
                    else:
                        print(f"  📸 Segment {i+1}: ({segment_type}) -> Image: {os.path.basename(image_path)} [start={segment_start:.1f}s, dur={segment_duration:.1f}s]")
                
                # Ensure we don't exceed audio duration
                if segment_start >= audio_duration:
                    break
                    
                if segment_start + segment_duration > audio_duration:
                    segment_duration = audio_duration - segment_start
                
                if segment_duration <= 0:
                    break
                
                # Load and enhance image
                try:
                    pil_img = Image.open(image_path)
                except Exception as e:
                    print(f"  ⚠️  Error loading image {image_path}: {e}")
                    # Skip this segment or use placeholder
                    continue
                
                # Enhance image quality
                enhancer = ImageEnhance.Contrast(pil_img)
                pil_img = enhancer.enhance(1.1)
                enhancer = ImageEnhance.Sharpness(pil_img)
                pil_img = enhancer.enhance(1.2)
                
                # Check if this is opening or closing image - use full screen height for these
                # Only treat as opening if it's actually the opening image path AND has no story_index
                is_fixed_image = (i == 0 and story_index is None and image_path == self.opening_image_path) or \
                                (i == len(segments) - 1 and image_path == self.closing_image_path)
                
                if is_fixed_image:
                    # Opening/closing images: Use full screen height (100%) for better visibility
                    image_height = self.height  # Full screen height
                    image_width = self.width  # Full width
                else:
                    # Regular story images: Use full screen height (no cropping)
                    image_height = self.height  # Full screen height
                    image_width = self.width  # Full width
                
                # Resize image to fit the image area (maintain aspect ratio, then crop if needed)
                # For opening/closing: resize to fill screen completely (scale up or down as needed)
                # For regular images: thumbnail to fit 3/4 height (only scale down)
                if is_fixed_image:
                    # For opening/closing: resize to cover full screen, maintaining aspect ratio
                    # Calculate scale factor to fill screen (cover mode - image fills entire area)
                    img_w, img_h = pil_img.size
                    scale = max(image_width / img_w, image_height / img_h)
                    new_w = int(img_w * scale)
                    new_h = int(img_h * scale)
                    # Resize to fill screen (will be cropped/centered if needed)
                    pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    img_w, img_h = pil_img.size
                else:
                    # Regular images: resize to fill full screen (cover mode - scale up or down as needed)
                    img_w, img_h = pil_img.size
                    scale = max(image_width / img_w, image_height / img_h)
                    new_w = int(img_w * scale)
                    new_h = int(img_h * scale)
                    # Resize to fill screen (will be cropped/centered if needed)
                    pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    img_w, img_h = pil_img.size
                
                # Create a new image with exact dimensions and center the resized image
                final_img = Image.new('RGB', (image_width, image_height), color='black')
                x_offset = (image_width - img_w) // 2
                y_offset = (image_height - img_h) // 2
                final_img.paste(pil_img, (x_offset, y_offset))
                
                resized_path = image_path.replace('.png', '_resized.png')
                final_img.save(resized_path, quality=95)
                
                # Create image clip for full screen (centered)
                # Set clip to start at segment_start and have segment_duration
                # IMPORTANT: Clip duration must match segment_duration exactly, not extend beyond
                img_clip = ImageClip(resized_path, duration=segment_duration)
                img_clip = img_clip.set_fps(self.fps)
                img_clip = img_clip.set_start(segment_start)  # Set start time
                img_clip = img_clip.set_position('center')  # Center the image on screen
                # Ensure clip ends at the right time (don't let it extend beyond segment)
                img_clip = img_clip.set_end(segment_start + segment_duration)
                
                # Add Ken Burns effect (zoom/pan motion) for visual interest
                # Simplified: Use resize with position animation
                try:
                    img_clip = self._add_ken_burns_effect(img_clip, segment_type, story_index)
                except Exception as e:
                    print(f"  ⚠️  Could not add motion effect: {e}")
                    # Continue without effect
                
                # Add visual effects based on LLM suggestions or defaults
                try:
                    # Get effect suggestions for this segment
                    segment_effect_config = segment_effects.get(str(i), {})
                    
                    # Glitch effect
                    glitch_config = segment_effect_config.get('glitch', {})
                    if glitch_config.get('enabled', False):
                        glitch_intensity = glitch_config.get('intensity', 0.3)
                        try:
                            img_clip = self._add_glitch_effect(img_clip, intensity=glitch_intensity)
                            print(f"    ✨ Applied glitch effect (intensity: {glitch_intensity:.2f})")
                        except Exception as e:
                            print(f"    ⚠️  Could not apply glitch effect: {e}")
                    elif segment_type == 'headline' and story_index is not None:
                        # Fallback: more visible glitch for headlines if no suggestion
                        if random.random() < 0.5:  # 50% chance for default glitch
                            try:
                                img_clip = self._add_glitch_effect(img_clip, intensity=random.uniform(0.3, 0.5))  # More visible (was 0.2)
                                print(f"    ✨ Applied default glitch effect for headline")
                            except Exception as e:
                                print(f"    ⚠️  Could not apply default glitch effect: {e}")
                    # For viral segments (hook, what_happened, impact), add glitch even if not headline
                    # REDUCED frequency to avoid too many glitches
                    elif segment_type in ['hook', 'what_happened', 'impact']:
                        if random.random() < 0.20:  # 20% chance for viral segments (reduced from 50%)
                            try:
                                img_clip = self._add_glitch_effect(img_clip, intensity=random.uniform(0.15, 0.25))
                                print(f"    ✨ Applied glitch effect for viral segment")
                            except Exception as e:
                                print(f"    ⚠️  Could not apply glitch effect: {e}")
                    
                    # Color grading
                    color_config = segment_effect_config.get('color_grading', {})
                    color_style = color_config.get('style', None)
                    if not color_style:
                        # Fallback based on segment type
                        if segment_type == 'headline':
                            color_style = 'dramatic'
                        elif segment_type in ['content', 'introduction']:
                            color_style = 'cinematic'
                        else:
                            color_style = 'news'
                    try:
                        img_clip = self._add_color_grading(img_clip, style=color_style)
                        print(f"    🎨 Applied color grading: {color_style}")
                    except Exception as e:
                        print(f"    ⚠️  Could not apply color grading: {e}")
                    
                    # Particle effects - MORE VISIBLE
                    particle_config = segment_effect_config.get('particles', {})
                    if particle_config.get('enabled', False):
                        particle_type = particle_config.get('type', 'sparkles')
                        particle_intensity = particle_config.get('intensity', 0.3)
                        try:
                            img_clip = self._add_particle_overlay(img_clip, particle_type=particle_type, intensity=particle_intensity)
                            print(f"    ✨ Applied particles: {particle_type} (intensity: {particle_intensity:.2f})")
                        except Exception as e:
                            print(f"    ⚠️  Could not apply particles: {e}")
                    elif random.random() < 0.2:  # 20% chance fallback (increased from 10%)
                        try:
                            img_clip = self._add_particle_overlay(img_clip, particle_type='sparkles', intensity=0.3)
                            print(f"    ✨ Applied default particles")
                        except Exception as e:
                            print(f"    ⚠️  Could not apply default particles: {e}")
                    
                    # Screen shake for headlines and important segments - MORE AGGRESSIVE
                    if segment_type == 'headline' and story_index is not None:
                        if random.random() < 0.6:  # 60% chance for headlines (increased from 40%)
                            try:
                                shake_intensity = random.uniform(0.3, 0.6)  # More intense (was 0.2-0.4)
                                img_clip = self._add_screen_shake(img_clip, intensity=shake_intensity, frequency=random.uniform(10, 20))
                                print(f"    📳 Applied screen shake (intensity: {shake_intensity:.2f})")
                            except Exception as e:
                                print(f"    ⚠️  Could not apply screen shake: {e}")
                    
                    # Flash effects for emphasis - MORE VISIBLE
                    if segment_type == 'headline' and story_index is not None:
                        if random.random() < 0.5:  # 50% chance (increased from 30%)
                            try:
                                flash_color = random.choice([(255, 255, 255), (255, 200, 0), (255, 0, 0), (0, 150, 255)])  # White, yellow, red, blue
                                img_clip = self._add_flash_effect(img_clip, flash_times=None, color=flash_color, intensity=random.uniform(0.5, 0.8))  # More intense
                                print(f"    ⚡ Applied flash effect (color: {flash_color})")
                            except Exception as e:
                                print(f"    ⚠️  Could not apply flash effect: {e}")
                    
                    # Zoom bursts for dynamic emphasis - MORE FREQUENT
                    if segment_type in ['headline', 'why_this_matters'] and story_index is not None:
                        if random.random() < 0.4:  # 40% chance (increased from 25%)
                            try:
                                zoom_amount = random.uniform(1.2, 1.4)  # More zoom (was 1.15-1.3)
                                img_clip = self._add_zoom_burst(img_clip, burst_times=None, zoom_amount=zoom_amount)
                                print(f"    🔍 Applied zoom burst (zoom: {zoom_amount:.2f}x)")
                            except Exception as e:
                                print(f"    ⚠️  Could not apply zoom burst: {e}")
                    
                    # Add motion blur effect for dynamic segments
                    if segment_type == 'headline' and story_index is not None:
                        if random.random() < 0.3:  # 30% chance
                            try:
                                img_clip = self._add_motion_blur(img_clip, intensity=random.uniform(0.2, 0.4))
                                print(f"    🌊 Applied motion blur")
                            except Exception as e:
                                print(f"    ⚠️  Could not apply motion blur: {e}")
                    
                    # Add color pop effect (saturation boost at key moments)
                    # For viral format, increase frequency and intensity
                    is_viral_segment = segment_type in ['hook', 'what_happened', 'impact']
                    if segment_type == 'headline' or is_viral_segment:
                        # Higher chance for viral segments (60% vs 35%)
                        pop_chance = 0.60 if is_viral_segment else 0.35
                        if random.random() < pop_chance:
                            try:
                                # Higher intensity for viral segments
                                pop_intensity = random.uniform(0.5, 0.8) if is_viral_segment else random.uniform(0.3, 0.6)
                                img_clip = self._add_color_pop(img_clip, pop_times=None, intensity=pop_intensity)
                                print(f"    🎨 Applied color pop (intensity: {pop_intensity:.2f})")
                            except Exception as e:
                                print(f"    ⚠️  Could not apply color pop: {e}")
                    
                    # Add blank cut effect for dramatic pauses (cut to black)
                    if segment_type == 'headline' and story_index is not None:
                        if random.random() < 0.3:  # 30% chance
                            try:
                                cut_duration = random.uniform(0.08, 0.15)  # 80-150ms cuts
                                img_clip = self._add_blank_cut_effect(img_clip, cut_times=None, cut_duration=cut_duration, color=(0, 0, 0))
                                print(f"    ⚫ Applied blank cut effect ({cut_duration*1000:.0f}ms)")
                            except Exception as e:
                                print(f"    ⚠️  Could not apply blank cut: {e}")
                    
                    # Add quick cuts for dynamic editing (very short cuts)
                    # For viral format (hook, what_happened, impact segments), increase frequency
                    is_viral_segment = segment_type in ['hook', 'what_happened', 'impact']
                    if segment_type in ['headline', 'why_this_matters'] or is_viral_segment:
                        # Higher chance for viral segments (60% vs 25%)
                        cut_chance = 0.60 if is_viral_segment else 0.25
                        if random.random() < cut_chance:
                            try:
                                num_cuts = random.randint(2, 4) if is_viral_segment else random.randint(1, 2)
                                img_clip = self._add_quick_cuts(img_clip, num_cuts=num_cuts, cut_duration=random.uniform(0.03, 0.06))
                                print(f"    ✂️  Applied {num_cuts} quick cuts")
                            except Exception as e:
                                print(f"    ⚠️  Could not apply quick cuts: {e}")
                    
                except Exception as e:
                    print(f"  ⚠️  Could not add visual effects: {e}")
                    # Continue without effects
                
                # Add stylized transitions and sound effects
                # Use dynamic transitions (digital warp, film burn, screen static) instead of simple fades
                transition_duration = 0.2  # 200ms transition
                
                if segment_type == 'headline' and story_index is not None and story_index > 1:
                    # New story: Use dynamic transition (wipe, slide, etc.)
                    if i > 0:  # Not the first segment
                        if random.random() < 0.3:  # 30% chance for blank cut transition (dramatic)
                            try:
                                # Add a quick blank cut before the segment starts
                                cut_duration = random.uniform(0.05, 0.1)  # 50-100ms cut
                                img_clip = self._add_blank_cut_effect(img_clip, cut_times=[0.0], cut_duration=cut_duration, color=(0, 0, 0))
                                print(f"    ⚫ Applied blank cut transition ({cut_duration*1000:.0f}ms)")
                            except Exception as e:
                                print(f"    ⚠️  Could not apply blank cut transition: {e}")
                        elif random.random() < 0.4:  # 40% chance for dynamic transition
                            transition_type = random.choice(['wipe', 'slide'])
                            direction = random.choice(['right', 'left', 'down'])
                            img_clip = self._add_dynamic_transition(img_clip, transition_type=transition_type, direction=direction, duration=transition_duration)
                            print(f"    🎬 Applied {transition_type} transition ({direction})")
                        else:
                            # Fallback to stylized transition
                            img_clip = self._add_stylized_transition_in(img_clip, transition_duration)
                        # Add sound effect for image transition
                        transition_sfx = self._create_transition_sound_effect(segment_start, 0.15)
                        if transition_sfx:
                            audio_clips.append(transition_sfx)
                elif i > 0:
                    # Other segments: Add transition IN (mix of dynamic and stylized)
                    if random.random() < 0.15:  # 15% chance for blank cut
                        try:
                            cut_duration = random.uniform(0.03, 0.08)  # 30-80ms cut
                            img_clip = self._add_blank_cut_effect(img_clip, cut_times=[0.0], cut_duration=cut_duration, color=(0, 0, 0))
                            print(f"    ⚫ Applied blank cut transition")
                        except Exception as e:
                            print(f"    ⚠️  Could not apply blank cut transition: {e}")
                    elif random.random() < 0.2:  # 20% chance for dynamic transition
                        transition_type = random.choice(['wipe', 'fade'])
                        direction = random.choice(['right', 'left'])
                        img_clip = self._add_dynamic_transition(img_clip, transition_type=transition_type, direction=direction, duration=transition_duration)
                        print(f"    🎬 Applied {transition_type} transition")
                    else:
                        img_clip = self._add_stylized_transition_in(img_clip, transition_duration)
                
                if i == len(segments) - 1:  # Last segment: fade out
                    img_clip = img_clip.fadeout(0.5)
                elif i < len(segments) - 1:
                    next_segment = segments[i + 1]
                    next_story_index = next_segment.get('story_index')
                    # Only add transition if next segment is a headline (new story) or different story
                    if next_segment.get('type') in ['headline', 'story'] and next_story_index != story_index:
                        img_clip = self._add_stylized_transition_out(img_clip, transition_duration)
                        # Add sound effect for image transition
                        transition_sfx = self._create_transition_sound_effect(segment_start + segment_duration, 0.15)
                        if transition_sfx:
                            audio_clips.append(transition_sfx)
                
                # Removed bottom text panel - no longer needed since we removed bottom captions
                # Only center subtitles are used now
                text_bg = None
                
                # Get segment text to display (for center subtitles only)
                segment_text = segment.get('text', '')
                if not segment_text and i < len(script_data.get('segments', [])):
                    segment_text = script_data['segments'][i].get('text', '')
                
                # Create text clips for the panel using PIL (no ImageMagick required)
                text_clips = []
                
                # Add subscribe CTA for closing segment
                if is_closing_segment:
                    subscribe_clip = self._create_subscribe_cta(segment_start, segment_duration)
                    if subscribe_clip:
                        text_clips.append(subscribe_clip)
                        print(f"    🔔 Added subscribe CTA at end of video")
                
                # Add trending indicators (🔥 tags) for headlines
                if segment_type == 'headline' and story_index is not None:
                    indicator_clip = self._create_trending_indicator(segment_start, segment_duration, story_index)
                    if indicator_clip:
                        text_clips.append(indicator_clip)
                
                # Add context-aware overlays if enabled
                if USE_CONTEXT_AWARE_OVERLAYS and segment_type == 'headline' and story_index is not None:
                    overlay_suggestions = script_data.get('overlay_suggestions', {})
                    if story_index in overlay_suggestions:
                        overlay_data = overlay_suggestions[story_index]
                        overlay_clips = self._create_context_aware_overlay(
                            overlay_data=overlay_data,
                            start_time=segment_start,
                            duration=segment_duration,
                            story_index=story_index
                        )
                        text_clips.extend(overlay_clips)
                        if overlay_clips:
                            primary_text = overlay_data.get('primary_overlay', {}).get('text', '')
                            if primary_text:
                                print(f"    🎨 Added overlay: {primary_text}")
                
                # Add context-aware overlays if enabled
                if USE_CONTEXT_AWARE_OVERLAYS and segment_type == 'headline' and story_index is not None:
                    overlay_suggestions = script_data.get('overlay_suggestions', {})
                    if story_index in overlay_suggestions:
                        overlay_data = overlay_suggestions[story_index]
                        overlay_clips = self._create_context_aware_overlay(
                            overlay_data=overlay_data,
                            start_time=segment_start,
                            duration=segment_duration,
                            story_index=story_index
                        )
                        text_clips.extend(overlay_clips)
                        if overlay_clips:
                            primary_text = overlay_data.get('primary_overlay', {}).get('text', '')
                            if primary_text:
                                print(f"    🎨 Added overlay: {primary_text}")
                
                if segment_text:
                    try:
                        # For headline-only segments (no summaries), just show the headline
                        headline_text_for_caption = None
                        summary_text_for_caption = None
                        
                        if segment_type == 'headline':
                            # Headline-only segment: show just the headline (no summary)
                            headline_text_for_caption = segment_text
                            summary_text_for_caption = ""  # No summary for headline-only segments
                        elif segment_type in ['content', 'introduction', 'conclusion', 'opening', 'story_part1', 'story_part2', 'story_part3', 'story_part4']:
                            # Extended video segments: show the text as headline (static display)
                            # For extended videos, we show the full text as a headline-style caption
                            headline_text_for_caption = segment_text
                            summary_text_for_caption = ""  # No summary for extended video segments
                        elif segment_type == 'story':
                            # For 'story' type segments, the text is combined heading+why+how
                            # Extract heading from first part (usually ends with period or colon), rest is summary
                            words = segment_text.split()
                            # Try to find first sentence (ends with . ! ?) or colon
                            first_sentence_end = -1
                            for punct in ['.', '!', '?']:
                                idx = segment_text.find(punct)
                                if idx > 0 and (first_sentence_end == -1 or idx < first_sentence_end):
                                    first_sentence_end = idx
                            
                            # Also check for colon (common in "Breaking: ..." or "Alert: ...")
                            colon_idx = segment_text.find(':')
                            if colon_idx > 0 and colon_idx < len(segment_text) * 0.3:
                                # If colon is in first 30% of text, use text up to next period as heading
                                period_after_colon = segment_text.find('.', colon_idx)
                                if period_after_colon > colon_idx:
                                    first_sentence_end = period_after_colon
                            
                            if first_sentence_end > 0 and first_sentence_end < len(segment_text) * 0.5:
                                # Use first sentence as headline
                                headline_text_for_caption = segment_text[:first_sentence_end + 1].strip()
                                summary_text_for_caption = segment_text[first_sentence_end + 1:].strip()
                            elif len(words) > 8:
                                # Use first 8-12 words as headline (increased for better context)
                                headline_word_count = min(12, max(8, len(words) // 3))
                                headline_words = words[:headline_word_count]
                                headline_text_for_caption = ' '.join(headline_words)
                                summary_text_for_caption = ' '.join(words[headline_word_count:])
                            else:
                                # Short text: use first half as headline, rest as summary
                                mid_point = len(words) // 2
                                headline_text_for_caption = ' '.join(words[:mid_point])
                                summary_text_for_caption = ' '.join(words[mid_point:])
                            
                            # Always ensure we have a headline (even if short) - don't set to None
                            if not headline_text_for_caption or len(headline_text_for_caption.strip()) == 0:
                                # Fallback: use first 8 words as headline
                                headline_text_for_caption = ' '.join(words[:min(8, len(words))])
                                summary_text_for_caption = ' '.join(words[min(8, len(words)):])
                            
                            # Ensure summary is not empty
                            if not summary_text_for_caption or len(summary_text_for_caption.strip()) == 0:
                                summary_text_for_caption = segment_text  # Use full text if no summary extracted
                        elif segment_type in ['summary'] and False:  # Disabled - no summary segments
                            # Look for previous headline segment with same story_index
                            headline_found = False
                            for j in range(i-1, -1, -1):
                                prev_seg = segments[j]
                                prev_story_idx = prev_seg.get('story_index')
                                prev_type = prev_seg.get('type', '')
                                if prev_story_idx == story_index and prev_type in ['headline', 'story']:
                                    # Found previous headline/story segment
                                    prev_text = prev_seg.get('text', '')
                                    if prev_type == 'headline':
                                        # Direct headline segment
                                        headline_text_for_caption = prev_text
                                        headline_found = True
                                        break
                                    elif prev_type == 'story':
                                        # Story segment - extract headline from it
                                        prev_words = prev_text.split()
                                        # Try to find first sentence
                                        first_sentence_end = -1
                                        for punct in ['.', '!', '?', ':']:
                                            idx = prev_text.find(punct)
                                            if idx > 0 and (first_sentence_end == -1 or idx < first_sentence_end):
                                                first_sentence_end = idx
                                        
                                        if first_sentence_end > 0 and first_sentence_end < len(prev_text) * 0.5:
                                            headline_text_for_caption = prev_text[:first_sentence_end + 1].strip()
                                        elif len(prev_words) > 8:
                                            headline_word_count = min(12, max(8, len(prev_words) // 3))
                                            headline_text_for_caption = ' '.join(prev_words[:headline_word_count])
                                        else:
                                            headline_text_for_caption = ' '.join(prev_words[:min(8, len(prev_words))])
                                        
                                        if headline_text_for_caption:
                                            headline_found = True
                                            break
                            
                            # If no headline found, try to extract from current summary text
                            if not headline_found:
                                summary_words = segment_text.split()
                                if len(summary_words) > 8:
                                    # Use first 8-10 words as headline
                                    headline_text_for_caption = ' '.join(summary_words[:min(10, len(summary_words) // 2)])
                                    summary_text_for_caption = ' '.join(summary_words[min(10, len(summary_words) // 2):])
                                else:
                                    # Short summary: use first half as headline
                                    mid_point = len(summary_words) // 2
                                    headline_text_for_caption = ' '.join(summary_words[:mid_point])
                                    summary_text_for_caption = ' '.join(summary_words[mid_point:])
                            else:
                                summary_text_for_caption = segment_text
                        
                        # Fallback: If no headline/summary extracted, use full text as headline
                        if not headline_text_for_caption and segment_text:
                            headline_text_for_caption = segment_text
                            summary_text_for_caption = ""
                        
                        # Skip dynamic captions (bottom subtitles) - only use center subtitles
                        # Removed: dynamic_caption_clips to avoid subtitle overlap
                        pass
                    except Exception as e:
                        print(f"  ⚠️  Warning: Could not process captions: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Add all clips to the list (they're already positioned at their start times)
                # Add word-by-word center subtitles (viral style) - synced with audio
                if segment_text:
                    try:
                        center_subtitles = self._create_word_by_word_subtitles(
                            text=segment_text,
                            start_time=segment_start,
                            duration=segment_duration,
                            position='center'
                        )
                        text_clips.extend(center_subtitles)
                        if center_subtitles:
                            print(f"    📝 Added {len(center_subtitles)} word-by-word center subtitles")
                    except Exception as e:
                        print(f"    ⚠️  Could not add center subtitles: {e}")
                
                # Add all clips to the list (they're already positioned at their start times)
                all_clips.append(img_clip)
                # Removed: text_bg (bottom text panel) - no longer needed since we removed bottom captions
                all_clips.extend(text_clips)
            
            if not all_clips:
                raise Exception("No valid clips created")
            
            # Composite all video clips together (they're already positioned at their start times)
            # Sort clips by start time to ensure proper layering
            all_clips_sorted = sorted(all_clips, key=lambda c: c.start if hasattr(c, 'start') else 0)
            
            print(f"\n  🎬 Compositing {len(all_clips_sorted)} video clips...")
            for i, clip in enumerate(all_clips_sorted[:10]):  # Show first 10 clips
                clip_start = clip.start if hasattr(clip, 'start') else 0
                clip_duration = clip.duration if hasattr(clip, 'duration') else 0
                clip_end = clip_start + clip_duration
                print(f"    Clip {i+1}: start={clip_start:.2f}s, duration={clip_duration:.2f}s, end={clip_end:.2f}s")
            
            # Create composite video from video clips only
            final_video = CompositeVideoClip(all_clips_sorted, size=(self.width, self.height))
            
            # Combine all audio: main audio + background music + sound effects
            # Start with main audio
            audio_with_music = self._add_background_music(audio, audio_duration)
            
            # Add audio effects based on LLM suggestions or defaults
            try:
                print("  🎵 Adding audio effects based on AI suggestions...")
                
                # Reverb effect
                reverb_config = global_audio_effects.get('reverb', {})
                if reverb_config.get('enabled', True):  # Default to enabled
                    room_size = reverb_config.get('room_size', 0.2)
                    damping = reverb_config.get('damping', 0.6)
                    audio_with_music = self._add_audio_reverb(audio_with_music, room_size=room_size, damping=damping)
                    print(f"    🔊 Applied reverb (room_size: {room_size:.2f}, damping: {damping:.2f})")
                
                # Echo effect (disabled by default - too noticeable/echoing)
                echo_config = global_audio_effects.get('echo', {})
                if echo_config.get('enabled', False):  # Default to disabled to avoid echoing
                    delay = echo_config.get('delay', 0.15)
                    decay = echo_config.get('decay', 0.3)  # Reduced decay for more subtle effect
                    repeats = echo_config.get('repeats', 1)
                    audio_with_music = self._add_audio_echo(audio_with_music, delay=delay, decay=decay, repeats=repeats)
                    print(f"    🔊 Applied echo (delay: {delay:.2f}s, decay: {decay:.2f}, repeats: {repeats})")
                else:
                    print(f"    🔊 Echo disabled (to avoid echoing effect)")
            except Exception as e:
                print(f"  ⚠️  Could not add audio effects: {e}")
                # Continue without effects
            
            # Add transition sound effects if any
            if audio_clips:
                print(f"  🔊 Combining {len(audio_clips)} sound effects with main audio...")
                # Combine all audio clips (main audio + SFX)
                all_audio_clips = [audio_with_music] + audio_clips
                try:
                    final_audio = CompositeAudioClip(all_audio_clips)
                    # Ensure audio duration matches video duration
                    if final_audio.duration > audio_duration:
                        final_audio = final_audio.subclip(0, audio_duration)
                except Exception as e:
                    print(f"  ⚠️  Error combining audio clips: {e}, using main audio only")
                    import traceback
                    traceback.print_exc()
                    final_audio = audio_with_music
            else:
                final_audio = audio_with_music
            
            # Set audio
            final_video = final_video.set_audio(final_audio)
            
            # Calculate proper video duration - ensure closing segment is fully included
            # CRITICAL: Video duration must NOT exceed audio duration to avoid MoviePy errors
            video_duration = audio_duration
            
            if segments:
                last_segment = segments[-1]
                last_segment_start = last_segment.get('start_time', 0)
                last_segment_duration = last_segment.get('duration', 0)
                last_segment_end = last_segment_start + last_segment_duration
                
                # Also check all clips to ensure nothing is cut off
                max_clip_end = 0
                for clip in all_clips_sorted:
                    clip_end = clip.start + clip.duration if hasattr(clip, 'start') and hasattr(clip, 'duration') else 0
                    max_clip_end = max(max_clip_end, clip_end)
                
                # Calculate desired duration, but ensure it doesn't exceed audio duration
                desired_duration = max(audio_duration, last_segment_end, max_clip_end)
                
                # CRITICAL FIX: Video duration must be <= audio duration to prevent MoviePy errors
                # Trim to audio duration minus small buffer (0.1s) to account for floating point precision
                video_duration = min(desired_duration, audio_duration - 0.1)
                
                # Ensure minimum duration
                video_duration = max(video_duration, audio_duration - 0.5)
                
                print(f"  📊 Duration calculation:")
                print(f"     Audio duration: {audio_duration:.2f}s")
                print(f"     Last segment end: {last_segment_end:.2f}s")
                print(f"     Max clip end: {max_clip_end:.2f}s")
                print(f"     Desired duration: {desired_duration:.2f}s")
                print(f"     Final video duration: {video_duration:.2f}s (trimmed to audio duration)")
            
            # Set video duration - ensure it doesn't exceed audio
            final_video = final_video.set_duration(video_duration)
            
            # Also ensure audio duration matches video duration exactly
            if hasattr(audio_with_music, 'duration') and audio_with_music.duration > video_duration:
                audio_with_music = audio_with_music.subclip(0, video_duration)
                final_video = final_video.set_audio(audio_with_music)
            
            # Write video file with optimized settings
            output_path = os.path.join(OUTPUT_DIR, output_filename)
            final_video.write_videofile(
                output_path,
                fps=self.fps,
                codec='libx264',
                audio_codec='aac',
                preset='fast',  # Faster encoding
                bitrate='5000k',  # Lower bitrate for better compatibility
                audio_bitrate='192k',
                threads=4,
                logger=None  # Suppress verbose output
            )
            
            # Cleanup
            final_video.close()
            audio.close()
            
            # Clean up temporary images (resized images and text images)
            for clip in all_clips:
                if hasattr(clip, 'filename') and clip.filename:
                    try:
                        if os.path.exists(clip.filename):
                            # Remove temporary resized images and text images
                            if '_resized.png' in clip.filename or 'text_' in clip.filename:
                                os.remove(clip.filename)
                    except:
                        pass
            
            print(f"Video created: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Error creating video: {e}")
            import traceback
            traceback.print_exc()
            return None

