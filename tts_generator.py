import os
from pydub import AudioSegment
from pydub.effects import normalize
import numpy as np
from config import TEMP_DIR, TTS_USE_EDGE_TTS, TTS_EDGE_VOICE, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, TTS_USE_ELEVENLABS, ELEVENLABS_MODEL_ID

# Fix Python 3.9 compatibility issue with importlib.metadata.packages_distributions
# This must be done BEFORE importing elevenlabs, as elevenlabs uses this function
import sys
if sys.version_info < (3, 10):
    try:
        import importlib.metadata
        # Check if packages_distributions exists, if not, add a fallback
        if not hasattr(importlib.metadata, 'packages_distributions'):
            # packages_distributions() returns a dict mapping package names to distribution names
            def _packages_distributions():
                """Fallback implementation for packages_distributions (Python 3.9 compatibility)"""
                try:
                    distributions = {}
                    for dist in importlib.metadata.distributions():
                        try:
                            name = dist.metadata.get('Name') or dist.metadata.get('name')
                            if name:
                                normalized_name = name.lower().replace('-', '_').replace('.', '_')
                                if normalized_name not in distributions:
                                    distributions[normalized_name] = []
                                distributions[normalized_name].append(name)
                        except:
                            pass
                    return distributions
                except:
                    return {}
            # Add the function to importlib.metadata module
            importlib.metadata.packages_distributions = _packages_distributions
    except Exception as e:
        # Silently fail - if we can't patch it, the import will fail later and we'll handle it
        pass

# Try to import ElevenLabs (best quality, preferred)
ELEVENLABS_AVAILABLE = False
ELEVENLABS_CLIENT_CLASS = None

try:
    # Try importing the client class (newer API structure)
    from elevenlabs.client import ElevenLabs
    ELEVENLABS_CLIENT_CLASS = ElevenLabs
    ELEVENLABS_AVAILABLE = True
except (ImportError, AttributeError, ModuleNotFoundError) as e:
    # Check if it's the packages_distributions error
    error_str = str(e)
    if "packages_distributions" in error_str or "has no attribute 'packages_distributions'" in error_str:
        print("⚠️  Python 3.9 compatibility issue with elevenlabs detected.")
        print("   Consider upgrading to Python 3.10+ or installing importlib-metadata backport:")
        print("   pip install 'importlib-metadata>=4.0'")
        print("   Falling back to Edge-TTS or gTTS...")
        ELEVENLABS_AVAILABLE = False
    else:
        # Try alternative import methods
        try:
            # Try direct function imports (older API)
            from elevenlabs import generate, set_api_key
            ELEVENLABS_AVAILABLE = True
        except (ImportError, AttributeError, ModuleNotFoundError) as e2:
            # Check if it's a real import error or a compatibility issue
            error_str = str(e2)
            if "No module named" in error_str:
                print("⚠️  elevenlabs not installed. Install with: pip install elevenlabs")
                print("   Falling back to Edge-TTS or gTTS...")
            else:
                # Compatibility issue - try to work around it
                try:
                    import elevenlabs
                    # Check if client class is available
                    if hasattr(elevenlabs, 'client'):
                        from elevenlabs.client import ElevenLabs
                        ELEVENLABS_CLIENT_CLASS = ElevenLabs
                        ELEVENLABS_AVAILABLE = True
                        print("✅ ElevenLabs available (using client-based API)")
                    elif hasattr(elevenlabs, 'generate'):
                        ELEVENLABS_AVAILABLE = True
                        print("✅ ElevenLabs available (using function-based API)")
                    else:
                        print(f"⚠️  ElevenLabs module loaded but API not found: {e2}")
                except Exception as e3:
                    print(f"⚠️  ElevenLabs import issue: {e3}")
                    ELEVENLABS_AVAILABLE = False
        # End of else block for alternative import methods

# Try to import Edge-TTS (good quality, open-source)
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("⚠️  edge-tts not installed. Install with: pip install edge-tts")

# Try to import gTTS (fallback)
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("⚠️  gTTS not installed. Install with: pip install gtts")

class TTSGenerator:
    """Generates text-to-speech audio for narration with professional news anchor tone"""
    
    def __init__(self, language: str = 'en', slow: bool = False, use_elevenlabs: bool = None, use_edge_tts: bool = None):
        self.language = language
        self.slow = slow
        
        # Priority order: ElevenLabs > Edge-TTS > gTTS
        # Use config settings if not explicitly provided
        if use_elevenlabs is None:
            use_elevenlabs = TTS_USE_ELEVENLABS
        
        if use_edge_tts is None:
            use_edge_tts = TTS_USE_EDGE_TTS
        
        # Initialize ElevenLabs if available and enabled
        self.use_elevenlabs = use_elevenlabs and ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY
        self.elevenlabs_client = None
        self.elevenlabs_client_class = ELEVENLABS_CLIENT_CLASS
        
        if self.use_elevenlabs:
            try:
                # Initialize ElevenLabs client (preferred method)
                if ELEVENLABS_CLIENT_CLASS:
                    self.elevenlabs_client = ELEVENLABS_CLIENT_CLASS(api_key=ELEVENLABS_API_KEY)
                    self.elevenlabs_voice_id = ELEVENLABS_VOICE_ID
                    from config import ELEVENLABS_MODEL_ID
                    print(f"✅ Using ElevenLabs TTS (premium quality, professional news anchor)")
                    print(f"   Voice ID: {self.elevenlabs_voice_id}")
                    print(f"   Model: {ELEVENLABS_MODEL_ID}")
                else:
                    # Fallback to function-based API
                    try:
                        from elevenlabs import set_api_key
                        set_api_key(ELEVENLABS_API_KEY)
                        self.elevenlabs_voice_id = ELEVENLABS_VOICE_ID
                        print("✅ Using ElevenLabs TTS (function-based API)")
                    except Exception as e2:
                        print(f"  ⚠️  ElevenLabs function API failed: {e2}")
                        self.use_elevenlabs = False
            except Exception as e:
                print(f"  ⚠️  ElevenLabs initialization failed: {e}, falling back to Edge-TTS")
                import traceback
                traceback.print_exc()
                self.use_elevenlabs = False
        
        # Initialize Edge-TTS as fallback
        self.use_edge_tts = (not self.use_elevenlabs) and use_edge_tts and EDGE_TTS_AVAILABLE
        
        # Edge-TTS voice options (news anchor-like voices)
        # Prefer Indian English for better pronunciation of Indian names
        self.edge_voice = TTS_EDGE_VOICE if EDGE_TTS_AVAILABLE else None
        self.edge_voices = {
            'en': TTS_EDGE_VOICE if EDGE_TTS_AVAILABLE else 'en-IN-NeerjaNeural',  # Default to Indian English
            'en-IN': 'en-IN-NeerjaNeural',  # Indian English, Female - best for Indian names
            'en-US': 'en-US-AriaNeural',
            'en-GB': 'en-GB-SoniaNeural',
        }
        
        # gTTS fallback settings
        self.tld = 'co.uk'  # UK English sounds more authoritative/news-like
        
        if self.use_edge_tts:
            voice_name = self.edge_voice or self.edge_voices.get(self.language, 'en-IN-NeerjaNeural')
            is_indian = 'en-in' in voice_name.lower()
            if is_indian:
                print(f"✅ Using Edge-TTS with Indian English voice: {voice_name} (optimized for Indian name pronunciation)")
            else:
                print(f"✅ Using Edge-TTS (open-source, high-quality voices): {voice_name}")
            # Test Edge-TTS availability
            try:
                import asyncio
                import edge_tts
                async def test():
                    voices = await edge_tts.list_voices()
                    return len(voices) > 0
                
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                loop.run_until_complete(test())
            except Exception as e:
                print(f"  ⚠️  Edge-TTS test failed: {e}, will fallback to gTTS")
                self.use_edge_tts = False
        
        if not self.use_elevenlabs and not self.use_edge_tts:
            if GTTS_AVAILABLE:
                print("⚠️  Using gTTS (fallback)")
            else:
                raise ImportError("No TTS library available. Install elevenlabs, edge-tts, or gtts.")
    
    def generate_audio(self, text: str, output_filename: str = None) -> str:
        """Generate TTS audio file from text with professional news anchor tone"""
        if not output_filename:
            output_filename = f"tts_{hash(text) % 10000}.mp3"
        
        filepath = os.path.join(TEMP_DIR, output_filename)
        
        try:
            # Priority order: ElevenLabs > Edge-TTS > gTTS
            audio = None
            
            if self.use_elevenlabs:
                try:
                    audio = self._generate_with_elevenlabs(text, filepath)
                except Exception as e:
                    print(f"  ⚠️  ElevenLabs failed: {e}, falling back to Edge-TTS")
                    self.use_elevenlabs = False
            
            if audio is None and self.use_edge_tts:
                try:
                    audio = self._generate_with_edge_tts(text, filepath)
                except Exception as e:
                    print(f"  ⚠️  Edge-TTS failed: {e}, falling back to gTTS")
                    self.use_edge_tts = False
            
            if audio is None:
                # Final fallback to gTTS
                audio = self._generate_with_gtts(text, filepath)
            
            if audio is None:
                return None
            
            # Apply natural news anchor enhancements
            audio = self._enhance_for_natural_news_anchor(audio)
            
            # Export enhanced audio
            audio.export(filepath, format="mp3", bitrate="192k")
            
            print(f"Generated audio: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"Error generating TTS: {e}")
            return None
    
    def _generate_with_elevenlabs(self, text: str, output_path: str) -> AudioSegment:
        """Generate audio using ElevenLabs (premium quality, professional news anchor voices)"""
        try:
            # Use client-based API with text_to_speech.convert()
            client_to_use = self.elevenlabs_client
            if not client_to_use:
                # Create client if not already created
                from elevenlabs.client import ElevenLabs
                client_to_use = ElevenLabs(api_key=ELEVENLABS_API_KEY)
            
            # ElevenLabs multilingual model should handle Indian names reasonably well
            # For ElevenLabs, we don't need phonetic hints - the v3 model handles names well
            # Adding phonetic hints causes the TTS to read both the name and pronunciation (repetition)
            processed_text = text
            
            # Generate audio using client.text_to_speech.convert()
            # This returns a generator/stream of audio chunks
            # Use configured model (default: eleven_turbo_v2_5 - latest v3 model for best Indian name support)
            model_to_use = ELEVENLABS_MODEL_ID
            
            print(f"  🔊 Using ElevenLabs model: {model_to_use}")
            
            response = client_to_use.text_to_speech.convert(
                text=processed_text,
                voice_id=self.elevenlabs_voice_id,
                model_id=model_to_use  # Use v3 model (eleven_turbo_v2_5) for best multilingual/Indian name support
            )
            
            # Collect all audio chunks into bytes
            audio_bytes = b""
            for chunk in response:
                if isinstance(chunk, bytes):
                    audio_bytes += chunk
                elif hasattr(chunk, 'read'):
                    # If it's a file-like object
                    audio_bytes += chunk.read()
                else:
                    # Try to convert to bytes
                    try:
                        audio_bytes += bytes(chunk)
                    except:
                        audio_bytes += str(chunk).encode()
            
            # Save to temporary file
            temp_path = output_path.replace('.mp3', '_elevenlabs.mp3')
            with open(temp_path, 'wb') as f:
                f.write(audio_bytes)
            
            # Load audio
            audio = AudioSegment.from_mp3(temp_path)
            
            # Clean up temp file
            try:
                if os.path.exists(temp_path) and temp_path != output_path:
                    os.remove(temp_path)
            except:
                pass
            
            return audio
            
        except Exception as e:
            print(f"  ⚠️  ElevenLabs generation failed: {e}")
            raise
    
    @staticmethod
    def list_elevenlabs_voices():
        """List available ElevenLabs voices (useful for finding news anchor voices)"""
        if not ELEVENLABS_AVAILABLE or not ELEVENLABS_API_KEY:
            print("ElevenLabs not available. Install with: pip install elevenlabs and set ELEVENLABS_API_KEY")
            return []
        
        try:
            available_voices = []
            
            # Try client-based API first
            if ELEVENLABS_CLIENT_CLASS:
                client = ELEVENLABS_CLIENT_CLASS(api_key=ELEVENLABS_API_KEY)
                # Get voices using the client API
                voices_list = client.voices.get_all()
                
                # Handle both list and object responses
                if hasattr(voices_list, 'voices'):
                    voices_iter = voices_list.voices
                else:
                    voices_iter = voices_list
                
                for voice in voices_iter:
                    available_voices.append({
                        'voice_id': getattr(voice, 'voice_id', None) or getattr(voice, 'id', None),
                        'name': getattr(voice, 'name', 'Unknown'),
                        'description': getattr(voice, 'description', ''),
                        'category': getattr(voice, 'category', ''),
                        'labels': getattr(voice, 'labels', {})
                    })
            else:
                # Fallback to function-based API
                try:
                    from elevenlabs import voices, set_api_key
                    set_api_key(ELEVENLABS_API_KEY)
                    voices_list = voices()
                    
                    for voice in voices_list.voices:
                        available_voices.append({
                            'voice_id': voice.voice_id,
                            'name': voice.name,
                            'description': getattr(voice, 'description', ''),
                            'category': getattr(voice, 'category', ''),
                            'labels': getattr(voice, 'labels', {})
                        })
                except ImportError:
                    import elevenlabs
                    if hasattr(elevenlabs, 'voices'):
                        voices_func = elevenlabs.voices
                        set_api_key = elevenlabs.set_api_key
                        set_api_key(ELEVENLABS_API_KEY)
                        voices_list = voices_func()
                        
                        for voice in voices_list.voices:
                            available_voices.append({
                                'voice_id': voice.voice_id,
                                'name': voice.name,
                                'description': getattr(voice, 'description', ''),
                                'category': getattr(voice, 'category', ''),
                                'labels': getattr(voice, 'labels', {})
                            })
            
            return available_voices
            
        except Exception as e:
            print(f"Error listing ElevenLabs voices: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    @staticmethod
    def list_edge_tts_voices():
        """List available Edge-TTS voices (useful for finding news anchor voices)"""
        if not EDGE_TTS_AVAILABLE:
            print("Edge-TTS not installed. Install with: pip install edge-tts")
            return []
        
        try:
            import asyncio
            import edge_tts
            
            async def get_voices():
                voices = await edge_tts.list_voices()
                return voices
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            voices = loop.run_until_complete(get_voices())
            
            # Filter for English voices, especially Indian/UK/US news anchor voices
            news_voices = []
            for voice in voices:
                locale = voice.get('Locale', '').lower()
                if 'en' in locale:
                    if 'neural' in voice['ShortName'].lower():  # Neural voices are higher quality
                        # Prioritize Indian English voices
                        is_indian = 'in' in locale
                        news_voices.append({
                            'name': voice['ShortName'],
                            'locale': voice['Locale'],
                            'gender': voice['Gender'],
                            'description': voice.get('FriendlyName', voice['ShortName']),
                            'is_indian': is_indian
                        })
            
            # Sort: Indian English voices first
            news_voices.sort(key=lambda x: (not x.get('is_indian', False), x['name']))
            
            return news_voices
            
        except Exception as e:
            print(f"Error listing voices: {e}")
            return []
    
    def _preprocess_text_for_indian_names(self, text: str, use_ssml: bool = False) -> str:
        """
        Preprocess text to improve pronunciation of Indian names
        
        NOTE: This method is currently DISABLED because adding phonetic pronunciations
        in parentheses causes the TTS to read both the name and pronunciation (repetition).
        
        For Edge-TTS: Indian English voices (en-IN-NeerjaNeural) handle names correctly automatically
        For ElevenLabs: The v3 multilingual model handles Indian names well without hints
        
        This method now returns text as-is to prevent name repetition.
        The issue was that adding "(pronunciation)" causes TTS to read both:
        "Siddaramaiah (SID-dah-rah-MY-ah)" -> says "Siddaramaiah" then "SID-dah-rah-MY-ah"
        """
        # Return text as-is - no preprocessing needed
        # Both Edge-TTS (with Indian English voice) and ElevenLabs (v3 model) handle
        # Indian names correctly without phonetic hints
        return text
        
        # Process text for Indian name pronunciation
        # Note: Audio tags like [Indian English] are not reliably supported and may be spoken as text
        # Instead, we rely on phonetic hints and voice selection for proper pronunciation
        processed_text = text
        
        # Common Indian names and their phonetic pronunciations (for SSML or hints)
        # Format: (name, phonetic_pronunciation)
        indian_names = {
            # Politicians
            'Modi': 'MO-dee',
            'Siddaramaiah': 'SID-dah-rah-MY-ah',
            'Shivakumar': 'SHI-va-ku-MAR',
            'Rahul': 'RAH-hool',
            'Priyanka': 'PREE-yan-ka',
            'Kejriwal': 'KEJ-ri-wal',
            'Mamata': 'MA-ma-ta',
            'Nitish': 'NI-tish',
            'Yogi': 'YO-gee',
            'Akhilesh': 'AH-khi-lesh',
            
            # Cities/States
            'Karnataka': 'KAR-na-ta-ka',
            'Maharashtra': 'MA-ha-RASH-tra',
            'Tamil Nadu': 'TA-mil NA-du',
            'Gujarat': 'GU-ja-rat',
            'Rajasthan': 'RA-ja-sthan',
            'Uttar Pradesh': 'UT-tar Pra-DESH',
            'West Bengal': 'West BEN-gal',
            'Punjab': 'PUN-jab',
            'Haryana': 'HA-ri-ya-na',
            'Kerala': 'KE-ra-la',
            'Telangana': 'TE-lan-ga-na',
            'Andhra Pradesh': 'AN-dhra Pra-DESH',
            'Bihar': 'BI-har',
            'Madhya Pradesh': 'MAD-hya Pra-DESH',
            'Odisha': 'O-DI-sha',
            'Assam': 'AS-sam',
            'Delhi': 'DEL-hee',
            'Mumbai': 'MUM-bai',
            'Bangalore': 'BAN-ga-lore',
            'Chennai': 'CHEN-nai',
            'Kolkata': 'KOL-ka-ta',
            'Hyderabad': 'HY-der-a-bad',
            'Pune': 'POO-ne',
            'Ahmedabad': 'AH-med-a-bad',
            'Jaipur': 'JAI-pur',
            
            # Common Indian names
            'Raj': 'RAJ',
            'Kumar': 'KU-mar',
            'Singh': 'SING',
            'Patel': 'PA-tel',
            'Sharma': 'SHAR-ma',
            'Gupta': 'GUP-ta',
            'Reddy': 'RED-dy',
            'Rao': 'RAO',
            'Nair': 'NAIR',
            'Iyer': 'I-YER',
            'Menon': 'ME-non',
            'Pillai': 'PIL-lai',
            'Narayan': 'NA-ra-yan',
            'Krishna': 'KRISH-na',
            'Ravi': 'RA-vi',
            'Arjun': 'AR-jun',
            'Vikram': 'VI-kram',
            'Anjali': 'AN-ja-li',
            'Priya': 'PREE-ya',
            'Deepak': 'DEE-pak',
            'Amit': 'A-MIT',
            'Rohit': 'RO-hit',
            'Suresh': 'SU-resh',
            'Mahesh': 'MA-hesh',
            'Naresh': 'NA-resh',
            'Rajesh': 'RA-jesh',
            'Vijay': 'VI-jay',
            'Ajay': 'A-jay',
            'Sanjay': 'SAN-jay',
            'Vivek': 'VI-vek',
            'Ashok': 'A-shok',
            'Manoj': 'MA-noj',
            'Pankaj': 'PAN-kaj',
            'Sunil': 'SU-nil',
            'Ramesh': 'RA-mesh',
            'Dinesh': 'DI-nesh',
            'Ganesh': 'GA-nesh',
            'Lakshmi': 'LAK-shmi',
            'Sita': 'SI-ta',
            'Radha': 'RA-dha',
            'Meera': 'MEE-ra',
            'Kavita': 'KA-vi-ta',
            'Sunita': 'SU-ni-ta',
            'Anita': 'A-ni-ta',
            'Neeta': 'NEE-ta',
            'Reeta': 'REE-ta',
            'Seema': 'SEE-ma',
            'Geeta': 'GEE-ta',
            'Leela': 'LEE-la',
            'Veena': 'VEE-na',
            'Asha': 'A-sha',
            'Usha': 'U-sha',
            'Kiran': 'KI-ran',
            'Niranjan': 'NI-ran-jan',
            'Srinivas': 'SRI-ni-vas',
            'Venkatesh': 'VEN-ka-tesh',
            'Sathish': 'SA-thish',
            'Prakash': 'PRA-kash',
        }
        
        # Replace names with phonetic pronunciations (case-insensitive)
        # This helps TTS engines understand the pronunciation better
        
        for name, pronunciation in indian_names.items():
            # Use word boundaries to avoid partial matches
            # Match whole words only (case-insensitive)
            pattern = r'\b' + re.escape(name) + r'\b'
            
            # Replace with phonetic spelling: "Siddaramaiah" -> "Siddaramaiah (SID-dah-rah-MY-ah)"
            # This helps TTS engines understand the pronunciation better
            # Works for both ElevenLabs (with v3 audio tags) and Edge-TTS
            processed_text = re.sub(pattern, f"{name} ({pronunciation})", processed_text, flags=re.IGNORECASE)
        
        return processed_text
    
    def _generate_with_edge_tts(self, text: str, output_path: str) -> AudioSegment:
        """Generate audio using Edge-TTS (Microsoft Edge TTS - free, high quality)"""
        try:
            import asyncio
            import edge_tts
            
            # Select voice based on language or use configured voice
            # Prefer Indian English voice for better pronunciation of Indian names
            voice = self.edge_voice or self.edge_voices.get(self.language, 'en-IN-NeerjaNeural')
            
            # Check if using Indian English voice
            is_indian_voice = 'en-in' in voice.lower()
            if is_indian_voice:
                print(f"  🇮🇳 Using Indian English voice: {voice} (optimized for Indian name pronunciation)")
            else:
                print(f"  🔊 Using voice: {voice}")
            
            # Edge-TTS with Indian English voice (en-IN-NeerjaNeural or en-IN-PrabhatNeural)
            # should automatically handle Indian names correctly
            # No preprocessing needed - the voice is trained on Indian English
            # DO NOT add phonetic pronunciations as it causes the TTS to read both the name and pronunciation
            processed_text = text
            
            # Edge-TTS requires async, so we need to run it
            async def generate():
                communicate = edge_tts.Communicate(processed_text, voice)
                # Save to temporary file first (Edge-TTS saves as .mp3)
                temp_path = output_path.replace('.mp3', '_edge.mp3')
                await communicate.save(temp_path)
                return temp_path
            
            # Run async function
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            temp_file = loop.run_until_complete(generate())
            
            # Load generated audio
            audio = AudioSegment.from_mp3(temp_file)
            
            # Clean up temp file
            try:
                if os.path.exists(temp_file) and temp_file != output_path:
                    os.remove(temp_file)
            except:
                pass
            
            return audio
            
        except Exception as e:
            print(f"  ⚠️  Edge-TTS failed: {e}, falling back to gTTS")
            if GTTS_AVAILABLE:
                return self._generate_with_gtts(text, output_path)
            else:
                raise
    
    def _generate_with_gtts(self, text: str, output_path: str) -> AudioSegment:
        """Generate audio using gTTS (fallback)"""
        if not GTTS_AVAILABLE:
            raise ImportError("gTTS not available")
        
        from gtts import gTTS
        
        # Generate speech with UK English for news anchor-like tone
        tts = gTTS(text=text, lang=self.language, slow=self.slow, tld=self.tld)
        tts.save(output_path)
        
        # Load generated audio
        audio = AudioSegment.from_mp3(output_path)
        return audio
    
    def _enhance_for_natural_news_anchor(self, audio: AudioSegment) -> AudioSegment:
        """
        Enhance audio to sound natural and less robotic:
        - Minimal processing to preserve natural voice quality
        - Only normalize volume for consistency
        - No speed adjustments to avoid robotic sound
        - No aggressive volume boosts
        """
        # Only normalize audio to consistent levels (minimal processing)
        # This preserves the natural voice quality from ElevenLabs/Edge-TTS
        audio = normalize(audio)
        
        # Skip speed adjustments - they can make voices sound robotic
        # Modern TTS engines (ElevenLabs, Edge-TTS) already have natural pacing
        
        # Skip volume boosts - they can introduce artifacts
        # The TTS engines already produce well-balanced audio
        
        return audio
    
    def generate_segmented_audio(self, segments: list, output_filename: str = None) -> tuple:
        """
        Generate audio for multiple segments and combine them
        Returns: (audio_path, segment_timings) where segment_timings is list of (start_time, duration)
        """
        audio_files = []
        segment_timings = []
        current_time = 0
        
        for i, segment in enumerate(segments):
            text = segment.get('text', '')
            if text:
                segment_file = self.generate_audio(text, f"segment_{i}.mp3")
                if segment_file:
                    # Get actual duration of generated audio
                    audio_seg = AudioSegment.from_mp3(segment_file)
                    actual_duration_ms = len(audio_seg)
                    actual_duration_sec = actual_duration_ms / 1000.0
                    
                    audio_files.append((segment_file, audio_seg))
                    segment_timings.append({
                        'index': i,
                        'start_time': current_time,
                        'duration': actual_duration_sec,
                        'text': text
                    })
                    current_time += actual_duration_sec
        
        if not audio_files:
            return None, []
        
        # Combine all audio segments
        combined = AudioSegment.empty()
        for _, audio_seg in audio_files:
            combined += audio_seg
        
        # Ensure audio duration matches segments (don't cut off closing)
        # Calculate expected duration from segment timings
        expected_duration_ms = sum(s['duration'] for s in segment_timings) * 1000 if segment_timings else 60 * 1000
        actual_duration_ms = len(combined)
        target_duration_ms = 60 * 1000  # milliseconds
        
        print(f"  📊 Audio duration check:")
        print(f"     Expected from segments: {expected_duration_ms/1000:.2f}s")
        print(f"     Actual audio length: {actual_duration_ms/1000:.2f}s")
        print(f"     Target duration: {target_duration_ms/1000:.2f}s")
        
        # Never trim audio if it's close to expected duration (preserve closing)
        if actual_duration_ms > target_duration_ms:
            # Only trim if significantly over (more than 2 seconds) AND if it's way longer than expected
            if actual_duration_ms > (target_duration_ms + 2000) and actual_duration_ms > (expected_duration_ms + 1000):
                print(f"  ⚠️  Audio is {actual_duration_ms/1000:.1f}s, trimming to {expected_duration_ms/1000:.1f}s")
                combined = combined[:int(expected_duration_ms)]
                # Adjust last segment timing to match actual
                if segment_timings:
                    actual_duration_s = len(combined) / 1000
                    total_so_far = sum(s['duration'] for s in segment_timings[:-1])
                    segment_timings[-1]['duration'] = max(3.0, actual_duration_s - total_so_far)
            else:
                # Close to expected or slightly over, keep it to avoid cutting off closing
                print(f"  ℹ️  Audio is {actual_duration_ms/1000:.1f}s (preserving full audio to avoid cutting closing)")
        elif actual_duration_ms < expected_duration_ms - 500:
            # Audio is shorter than expected - add silence to match expected duration
            silence_needed = expected_duration_ms - actual_duration_ms
            print(f"  ℹ️  Audio is {actual_duration_ms/1000:.1f}s, adding {silence_needed/1000:.1f}s silence to match expected duration")
            silence = AudioSegment.silent(duration=int(silence_needed))
            combined += silence
            # Update last segment timing to match
            if segment_timings:
                actual_duration_s = len(combined) / 1000
                total_so_far = sum(s['duration'] for s in segment_timings[:-1])
                segment_timings[-1]['duration'] = actual_duration_s - total_so_far
        
        if not output_filename:
            output_filename = "final_audio.mp3"
        
        final_path = os.path.join(TEMP_DIR, output_filename)
        combined.export(final_path, format="mp3")
        
        print(f"Generated final audio: {final_path} ({len(combined)/1000:.1f}s)")
        print(f"Segment timings: {[(s['start_time'], s['duration']) for s in segment_timings]}")
        return final_path, segment_timings

