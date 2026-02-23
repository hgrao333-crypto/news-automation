import subprocess
import os
import time
from typing import List
from config import TEMP_DIR

class ImageGenerator:
    """
    Generates images using MLX Flux (local generation)
    Uses the MLX Flux setup from /Users/prajwal.g/Library/mlx-examples/flux
    """
    
    def __init__(self):
        # Path to MLX Flux setup
        self.flux_dir = "/Users/prajwal.g/Library/mlx-examples/flux"
        self.flux_venv_python = os.path.join(self.flux_dir, "venv", "bin", "python3")
        self.txt2image_script = os.path.join(self.flux_dir, "txt2image.py")
        
        # Verify paths exist
        if not os.path.exists(self.flux_venv_python):
            raise FileNotFoundError(f"MLX Flux Python not found at {self.flux_venv_python}")
        if not os.path.exists(self.txt2image_script):
            raise FileNotFoundError(f"txt2image.py not found at {self.txt2image_script}")
    
    def _aspect_ratio_to_size(self, aspect_ratio: str) -> tuple:
        """Convert aspect ratio string to (width, height) tuple"""
        if aspect_ratio == "16:9":
            return (1920, 1080)  # Landscape
        elif aspect_ratio == "9:16":
            return (1080, 1920)  # Portrait
        else:
            # Default to portrait
            return (1080, 1920)
    
    def _sanitize_prompt(self, prompt: str) -> str:
        """
        Sanitize prompt to remove special characters that might break MLX Flux tokenizer
        MLX Flux CLIP tokenizer can fail on certain Unicode characters like en-dash (–), em-dash (—), etc.
        """
        import re
        
        if not prompt:
            return ""
        
        # Replace problematic Unicode characters with ASCII equivalents BEFORE encoding
        # En-dash (–) and em-dash (—) -> regular dash (-)
        prompt = prompt.replace('–', '-').replace('—', '-')
        prompt = prompt.replace('…', '...')
        prompt = prompt.replace('"', '"').replace('"', '"')  # Smart quotes -> regular quotes
        prompt = prompt.replace(''', "'").replace(''', "'")  # Smart apostrophes -> regular apostrophes
        
        # Replace other common problematic Unicode characters
        prompt = prompt.replace('•', '*')  # Bullet point
        prompt = prompt.replace('°', ' degrees')  # Degree symbol
        prompt = prompt.replace('€', 'EUR').replace('£', 'GBP').replace('¥', 'JPY')  # Currency symbols
        prompt = prompt.replace('®', '(R)').replace('©', '(C)').replace('™', '(TM)')  # Trademark symbols
        
        # Convert to ASCII, ignoring any remaining problematic characters
        # This ensures only ASCII characters remain, which the tokenizer can handle
        try:
            cleaned = prompt.encode('ascii', 'ignore').decode('ascii')
        except:
            # Fallback: manual filtering
            cleaned = ''
            for char in prompt:
                if ord(char) < 128 and (char.isprintable() or char.isspace()):
                    cleaned += char
                elif char.isspace():
                    cleaned += ' '
        
        # Clean up multiple spaces and strip
        cleaned = ' '.join(cleaned.split())
        
        return cleaned.strip()
    
    def _is_gpu_timeout_error(self, output_lines: List[str], return_code: int) -> bool:
        """Check if the error is a GPU timeout"""
        if return_code != 0:
            output_text = ' '.join(output_lines).lower()
            # Check for GPU timeout indicators
            if 'gpu timeout' in output_text or 'metal' in output_text and 'timeout' in output_text:
                return True
            # Exit code -6 is SIGABRT, often caused by GPU timeouts
            if return_code == -6:
                return True
        return False
    
    def _reduce_image_size(self, width: int, height: int) -> tuple:
        """Reduce image size by 25% to help avoid GPU timeouts"""
        new_width = int(width * 0.75)
        new_height = int(height * 0.75)
        # Ensure dimensions are divisible by 16 (MLX Flux requirement)
        new_width = (new_width // 16) * 16
        new_height = (new_height // 16) * 16
        return (new_width, new_height)
    
    def generate_image(self, prompt: str, style: str = "realistic", aspect_ratio: str = "9:16", seed: int = None, max_retries: int = 2) -> str:
        """
        Generate image using MLX Flux with retry logic for GPU timeouts
        Returns path to saved image file
        """
        # Sanitize prompt to remove problematic characters that break MLX Flux tokenizer
        sanitized_prompt = self._sanitize_prompt(prompt)
        if sanitized_prompt != prompt:
            print(f"  ⚠️  Sanitized prompt (removed problematic Unicode characters)")
        
        # Enhance prompt to use concept illustrations and avoid photorealistic people
        # Use editorial/stylized art style instead of photorealistic photography
        # CRITICAL: Add multiple emphatic "NO TEXT" instructions to prevent text generation
        # Put "NO TEXT" instruction FIRST for maximum weight
        no_text_instruction = "CRITICAL: ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO SIGNS, NO BANNERS, NO HEADLINES, NO WRITTEN CONTENT, NO TEXT OVERLAYS, NO CAPTIONS, NO SUBTITLES, NO LABELS, NO TITLES, NO QUOTES, NO SPEECH BUBBLES, NO NEWSPAPERS, NO MAGAZINES, NO BOOKS WITH VISIBLE TEXT, NO SCREENS WITH TEXT, NO COMPUTER MONITORS WITH TEXT, NO PHONES WITH TEXT, NO TABLETS WITH TEXT, NO BILLBOARDS, NO POSTERS WITH TEXT, NO STREET SIGNS, NO LICENSE PLATES, NO TEXT ON CLOTHING, NO TEXT ON BUILDINGS, NO TEXT ANYWHERE. The image MUST be 100% text-free, word-free, letter-free, number-free. Pure visual imagery only."
        enhanced_prompt = f"{no_text_instruction}. {sanitized_prompt}. CONCEPT ILLUSTRATION style, editorial art, stylized illustration, dramatic visual metaphor, symbolic representation. Use editorial cartoon style, magazine illustration aesthetic, satirical art when appropriate. AVOID photorealistic faces or actual people - use silhouettes, abstract human forms, symbolic figures, or focus on objects and scenes instead. Make it feel editorial and dramatic, not fake - audiences accept stylized illustrations for news. Focus on visual metaphors, symbols, abstract representations, stylized illustrations, composition, lighting, colors, textures, shapes, forms. NO TEXT WHATSOEVER."
        
        # Convert aspect ratio to image dimensions
        width, height = self._aspect_ratio_to_size(aspect_ratio)
        original_width, original_height = width, height
        
        # Generate unique filename with absolute path
        # Use seed, timestamp, and random component to ensure uniqueness even for similar prompts
        import time
        import random
        timestamp = int(time.time() * 1000000)  # Microseconds for better uniqueness
        prompt_hash = abs(hash(prompt)) % 100000  # Larger range to reduce collisions
        random_component = random.randint(1000, 9999)  # Random component
        seed_suffix = f"_s{seed}" if seed else ""
        filename = f"image_{prompt_hash}_{timestamp}_{random_component}{seed_suffix}.png"
        filepath = os.path.abspath(os.path.join(TEMP_DIR, filename))
        
        # Ensure temp directory exists
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        # Retry loop for GPU timeout errors
        for attempt in range(max_retries + 1):
            try:
                # On retry after GPU timeout, reduce image size
                if attempt > 0:
                    print(f"  🔄 Retry attempt {attempt}/{max_retries} (reduced image size to avoid GPU timeout)...")
                    width, height = self._reduce_image_size(width, height)
                    # Update filename for retry (keep same base but add retry suffix)
                    filename = f"image_{prompt_hash}_{timestamp}_{random_component}{seed_suffix}_retry{attempt}.png"
                    filepath = os.path.abspath(os.path.join(TEMP_DIR, filename))
                
                # Note: MLX Flux expects --image-size as "height x width" (not width x height)
                image_size = f"{height}x{width}"  # Swap: height x width for MLX Flux
                
                # Build command with speed optimizations
                cmd = [
                    self.flux_venv_python,
                    self.txt2image_script,
                    enhanced_prompt,
                    "--image-size", image_size,
                    "--output", filepath,
                    "--model", "schnell",  # Fast model (schnell = fast in German)
                    "--n-images", "1",  # Generate only 1 image
                    "--n-rows", "1",
                    "--no-t5-padding",  # Speed optimization: skip T5 padding (faster generation)
                    "--verbose",  # Show verbose output including progress bars and memory usage
                ]
                
                # Add seed if provided
                if seed:
                    cmd.extend(["--seed", str(seed)])
                
                # Run the command with real-time output streaming to show progress bars
                if attempt == 0:
                    print(f"Generating image with MLX Flux: {image_size}...")
                else:
                    print(f"Retrying with reduced size: {image_size}...")
                print("=" * 60)
                
                process = subprocess.Popen(
                    cmd,
                    cwd=self.flux_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # Combine stderr into stdout
                    text=True,
                    bufsize=1,  # Line buffered
                    universal_newlines=True
                )
                
                # Stream output in real-time to show progress bars
                output_lines = []
                start_time = time.time()
                timeout_seconds = 600  # 10 minutes
                
                # Read output line by line (this blocks until line is available, which is fine)
                for line in process.stdout:
                    # Check for timeout periodically
                    if time.time() - start_time > timeout_seconds:
                        process.kill()
                        process.wait()
                        print(f"\n⏱️  Image generation timed out after 10 minutes")
                        if attempt < max_retries:
                            print(f"  ⏳ Waiting 5 seconds before retry...")
                            time.sleep(5)
                            continue
                        return None
                    
                    line = line.rstrip()
                    print(line)  # Print immediately to show progress bars
                    output_lines.append(line)
                
                # Process finished, get return code
                return_code = process.wait()
                
                print("=" * 60)
                
                if return_code == 0:
                    if os.path.exists(filepath):
                        if attempt > 0:
                            print(f"✅ Generated image (retry {attempt} succeeded): {filepath}")
                        else:
                            print(f"✅ Generated image: {filepath}")
                        return filepath
                    else:
                        print(f"⚠️  Command succeeded but image file not found: {filepath}")
                        print(f"   Last output: {''.join(output_lines[-10:])}")
                        if attempt < max_retries:
                            print(f"  ⏳ Waiting 5 seconds before retry...")
                            time.sleep(5)
                            continue
                        return None
                else:
                    # Check if it's a GPU timeout error
                    if self._is_gpu_timeout_error(output_lines, return_code):
                        print(f"⚠️  GPU timeout detected (exit code: {return_code})")
                        if attempt < max_retries:
                            print(f"  ⏳ Waiting 10 seconds for GPU to recover before retry...")
                            time.sleep(10)  # Wait longer for GPU recovery
                            continue
                        else:
                            print(f"❌ GPU timeout after {max_retries + 1} attempts. Using placeholder image.")
                            return self._create_placeholder_image(aspect_ratio)
                    else:
                        print(f"❌ Error generating image (exit code: {return_code})")
                        print(f"   Output: {''.join(output_lines[-20:])}")
                        if attempt < max_retries:
                            print(f"  ⏳ Waiting 5 seconds before retry...")
                            time.sleep(5)
                            continue
                        return None
                        
            except Exception as e:
                if "TimeoutExpired" in str(type(e).__name__):
                    print(f"\n⏱️  Image generation timed out after 10 minutes")
                    if attempt < max_retries:
                        print(f"  ⏳ Waiting 5 seconds before retry...")
                        time.sleep(5)
                        continue
                else:
                    print(f"❌ Error in image generation: {e}")
                    if attempt < max_retries:
                        print(f"  ⏳ Waiting 5 seconds before retry...")
                        time.sleep(5)
                        continue
                return None
        
        # If all retries failed, return placeholder
        print(f"⚠️  All retry attempts failed. Using placeholder image.")
        return self._create_placeholder_image(aspect_ratio)
    
    def generate_images_for_segments(self, prompts: List[str], style: str = "realistic", aspect_ratio: str = "9:16") -> List[str]:
        """
        Generate multiple images for video segments
        Args:
            prompts: List of image prompts
            style: Image style (default: realistic)
            aspect_ratio: "9:16" for short videos (portrait), "16:9" for extended videos (landscape)
        """
        image_paths = []
        
        for i, prompt in enumerate(prompts):
            # Ensure prompt is a string
            if not isinstance(prompt, str):
                if isinstance(prompt, (list, tuple)):
                    prompt = ' '.join(str(p) for p in prompt)
                else:
                    prompt = str(prompt)
            
            # Truncate for display
            prompt_preview = prompt[:50] if len(prompt) > 50 else prompt
            print(f"Generating image {i+1}/{len(prompts)}: {prompt_preview}...")
            
            # Use unique seed for each image (i+1) and add small delay to ensure unique timestamps
            import time
            if i > 0:
                time.sleep(0.01)  # Small delay to ensure unique timestamps
            
            image_path = self.generate_image(
                prompt=prompt,
                style=style,
                aspect_ratio=aspect_ratio,  # Use provided aspect ratio
                seed=i+1  # Different seed for each image
            )
            if image_path:
                image_paths.append(image_path)
            else:
                # Use a placeholder if generation fails
                placeholder = self._create_placeholder_image(aspect_ratio)
                image_paths.append(placeholder)
        
        return image_paths
    
    def _create_placeholder_image(self, aspect_ratio: str = "9:16") -> str:
        """Create a simple placeholder image if API fails"""
        from PIL import Image, ImageDraw, ImageFont
        
        # Set dimensions based on aspect ratio
        if aspect_ratio == "16:9":
            width, height = 1920, 1080  # Landscape
        else:
            width, height = 1080, 1920  # Portrait (default)
        
        img = Image.new('RGB', (width, height), color='#1a1a1a')
        draw = ImageDraw.Draw(img)
        
        # Add text
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
        except:
            font = ImageFont.load_default()
        
        text = "News Update"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        position = ((width - text_width) // 2, (height - text_height) // 2)
        draw.text(position, text, fill='white', font=font)
        
        filename = f"placeholder_{hash(text) % 10000}.png"
        filepath = os.path.join(TEMP_DIR, filename)
        img.save(filepath)
        
        return filepath

