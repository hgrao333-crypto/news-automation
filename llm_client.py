"""
Unified LLM Client with fallback support
Priority: Gemini → OpenRouter → Ollama
All API keys read from environment / config (no secrets in code).
"""
# Import compatibility fix FIRST (before any packages that use importlib.metadata)
import compat_fix

import os
import requests
import json
from typing import Dict, Optional, Any
import ollama

# Try to import Google Generative AI SDK
try:
    import google.generativeai as genai
    from google.generativeai import types
    GEMINI_SDK_AVAILABLE = True
except ImportError:
    GEMINI_SDK_AVAILABLE = False
    genai = None
    types = None


def _getenv(key: str, default: str = "") -> str:
    """Prefer config module if available (so .env is loaded), else os.getenv."""
    try:
        import config
        return getattr(config, key, None) or os.getenv(key, default)
    except ImportError:
        return os.getenv(key, default)


class LLMClient:
    """Unified LLM client with fallback support"""

    def __init__(self):
        self.providers = []
        self.current_provider = None

        # Priority 1: Gemini (set GEMINI_API_KEY in .env)
        self.gemini_config = {
            "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            "temperature": 0.1,
            "api_key": _getenv("GEMINI_API_KEY"),
            "base_url": "https://generativelanguage.googleapis.com/v1beta/models"
        }

        # Priority 2: OpenRouter (set OPENROUTER_API_KEY in .env)
        self.openrouter_config = {
            "model": os.getenv("OPENROUTER_MODEL", "tngtech/deepseek-r1t2-chimera:free"),
            "temperature": 0.1,
            "api_key": _getenv("OPENROUTER_API_KEY"),
            "base_url": "https://openrouter.ai/api/v1"
        }

        # Priority 3: Ollama (fallback; local)
        self.ollama_config = {
            "base_url": _getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            "model": _getenv("OLLAMA_MODEL", "llama3.1:8b")
        }

        # Initialize providers in priority order
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize providers and test availability"""
        # Test Gemini
        if self._test_gemini():
            self.providers.append("gemini")
            self.current_provider = "gemini"
            print("  ✅ Using Gemini 2.5 Flash")
            return
        
        # Test OpenRouter
        if self._test_openrouter():
            self.providers.append("openrouter")
            self.current_provider = "openrouter"
            print("  ✅ Using OpenRouter (DeepSeek)")
            return
        
        # Fallback to Ollama
        if self._test_ollama():
            self.providers.append("ollama")
            self.current_provider = "ollama"
            print("  ✅ Using Ollama (fallback)")
            return
        
        print("  ⚠️  No LLM providers available!")
    
    def _test_gemini(self) -> bool:
        """Test if Gemini is available (requires GEMINI_API_KEY in .env)."""
        if not (self.gemini_config.get("api_key") or "").strip():
            return False
        try:
            url = f"{self.gemini_config['base_url']}/{self.gemini_config['model']}:generateContent"
            params = {"key": self.gemini_config['api_key']}
            data = {
                "contents": [{"parts": [{"text": "test"}]}],
                "generationConfig": {
                    "temperature": self.gemini_config['temperature'],
                    "maxOutputTokens": 10
                }
            }
            response = requests.post(url, params=params, json=data, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _test_openrouter(self) -> bool:
        """Test if OpenRouter is available (requires OPENROUTER_API_KEY in .env)."""
        if not (self.openrouter_config.get("api_key") or "").strip():
            return False
        try:
            url = f"{self.openrouter_config['base_url']}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openrouter_config['api_key']}",
                "Content-Type": "application/json"
            }
            data = {
                "model": self.openrouter_config['model'],
                "messages": [{"role": "user", "content": "test"}],
                "temperature": self.openrouter_config['temperature'],
                "max_tokens": 10
            }
            response = requests.post(url, headers=headers, json=data, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _test_ollama(self) -> bool:
        """Test if Ollama is available"""
        try:
            client = ollama.Client(host=self.ollama_config['base_url'])
            models = client.list()
            model_names = [m['name'] for m in models.get('models', [])]
            if self.ollama_config['model'] in model_names:
                return True
            # Try to find alternative model
            if model_names:
                self.ollama_config['model'] = model_names[0]
                return True
            return False
        except:
            return False
    
    def generate(self, prompt: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate response using current provider, with fallback
        Returns: {"response": str, "provider": str}
        """
        if options is None:
            options = {}
        
        # Try current provider first
        if self.current_provider == "gemini":
            result = self._generate_gemini(prompt, options)
            if result:
                return result
        
        if self.current_provider == "openrouter":
            result = self._generate_openrouter(prompt, options)
            if result:
                return result
        
        if self.current_provider == "ollama":
            result = self._generate_ollama(prompt, options)
            if result:
                return result
        
        # Fallback chain
        if self.current_provider != "openrouter":
            result = self._generate_openrouter(prompt, options)
            if result:
                self.current_provider = "openrouter"
                return result
        
        if self.current_provider != "ollama":
            result = self._generate_ollama(prompt, options)
            if result:
                self.current_provider = "ollama"
                return result
        
        # Last resort: try Gemini again
        if self.current_provider != "gemini":
            result = self._generate_gemini(prompt, options)
            if result:
                self.current_provider = "gemini"
                return result
        
        raise Exception("All LLM providers failed")
    
    def _generate_gemini(self, prompt: str, options: Dict) -> Optional[Dict]:
        """Generate using Gemini with optional Google Search grounding"""
        use_google_search = options.get('use_google_search', False)
        temperature = options.get('temperature', self.gemini_config['temperature'])
        # Increase default max_tokens for better responses, especially with web search
        max_tokens = options.get('num_predict', 16384)  # Increased to 16384 to prevent truncation
        
        # Use REST API directly - SDK doesn't support googleSearch tool properly
        # REST API is more reliable and we've confirmed it works with web search
        return self._generate_gemini_rest(prompt, use_google_search, temperature, max_tokens)
    
    def _generate_gemini_sdk(self, prompt: str, use_google_search: bool, temperature: float, max_tokens: int) -> Optional[Dict]:
        """Generate using Gemini SDK (preferred method for Google Search)"""
        try:
            # Configure the API client
            genai.configure(api_key=self.gemini_config['api_key'])
            client = genai.Client(api_key=self.gemini_config['api_key'])
            
            # Select the model
            model_name = self.gemini_config['model']
            
            # Define the tool configuration for Google Search
            tool_config = None
            if use_google_search:
                tool_config = types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    temperature=temperature,
                    max_output_tokens=min(max_tokens, 8192)
                )
                print(f"  🔍 Using Google Search via SDK (tools=[{{\"google_search\": {{}}}}])...")
            else:
                tool_config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=min(max_tokens, 8192)
                )
                print(f"  💡 Using Gemini SDK (no web search)...")
            
            print(f"  ⏳ Sending request to Gemini API via SDK...")
            
            # Generate content with grounding
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=tool_config
            )
            
            # Get the response text
            text = response.text if hasattr(response, 'text') else str(response)
            
            # Check for grounding metadata (indicates web search was used)
            if use_google_search and hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata'):
                    grounding_metadata = candidate.grounding_metadata
                    web_search_queries = getattr(grounding_metadata, 'web_search_queries', [])
                    grounding_chunks = getattr(grounding_metadata, 'grounding_chunks', [])
                    
                    if web_search_queries or grounding_chunks:
                        print(f"  ✅ Web search confirmed: {len(web_search_queries)} queries, {len(grounding_chunks)} sources")
                    else:
                        print(f"  ⚠️  Web search requested but no grounding metadata found")
                        print(f"     This may indicate web search is not enabled or requires paid API")
            
            if text:
                print(f"  ✅ Got response from Gemini via SDK ({len(text)} characters)")
                return {"response": text, "provider": "gemini"}
            else:
                print(f"  ⚠️  Gemini SDK returned empty response")
                return None
                
        except Exception as e:
            print(f"  ⚠️  Gemini SDK error: {e}")
            import traceback
            print(f"  📋 Error details: {traceback.format_exc()[:300]}")
            return None
    
    def _generate_gemini_rest(self, prompt: str, use_google_search: bool, temperature: float, max_tokens: int) -> Optional[Dict]:
        """Generate using Gemini REST API (fallback method)"""
        try:
            url = f"{self.gemini_config['base_url']}/{self.gemini_config['model']}:generateContent"
            
            # Use same format as working test script
            # Match exact format: contents with role, generationConfig with maxOutputTokens
            data = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": min(max_tokens, 16384) if max_tokens else 16384
                }
            }
            
            # Explicitly enable Google Search grounding if requested
            if use_google_search:
                # Enable Google Search grounding via tools
                # Use "googleSearch" format (not "googleSearchRetrieval") - this is the working format
                data["tools"] = [{
                    "googleSearch": {}
                }]
                print(f"  🔍 Explicitly enabling Google Search grounding via REST API...")
                print(f"  ✅ Tools parameter added: {data.get('tools')}")
                print(f"  ⚠️  Note: Google Search grounding may require a paid Gemini API plan")
            else:
                print(f"  💡 Using REST API (no web search)...")
            
            print(f"  ⏳ Sending request to Gemini API via REST...")
            # Debug: Show if tools is in the payload
            if use_google_search:
                print(f"  🔍 Debug - Payload includes tools: {'tools' in data}")
                if 'tools' in data:
                    print(f"  🔍 Debug - Tools value: {data['tools']}")
            # Increase timeout for Google Search (it can take longer)
            timeout = 120 if use_google_search else 60
            # Use headers with API key (more reliable than query params)
            headers = {
                "x-goog-api-key": self.gemini_config['api_key'],
                "Content-Type": "application/json"
            }
            response = requests.post(url, headers=headers, json=data, timeout=timeout)
            
            print(f"  📡 Received response (status: {response.status_code})")
            
            if response.status_code == 200:
                result = response.json()
                candidate = result.get('candidates', [{}])[0]
                
                # Check finish reason first (like test script does)
                finish_reason = candidate.get('finishReason', 'UNKNOWN')
                
                # Extract text - handle both formats
                content = candidate.get('content', {})
                parts = content.get('parts', [])
                text = ''
                if parts:
                    text = parts[0].get('text', '')
                
                # Check for grounding metadata (indicates web search was used)
                if use_google_search:
                    grounding_metadata = candidate.get('groundingMetadata', {})
                    web_search_queries = grounding_metadata.get('webSearchQueries', [])
                    grounding_chunks = grounding_metadata.get('groundingChunks', [])
                    
                    if web_search_queries or grounding_chunks:
                        print(f"  ✅ Web search confirmed: {len(web_search_queries)} queries, {len(grounding_chunks)} sources")
                        # Show first few sources if available
                        if grounding_chunks:
                            print(f"  🌐 Sources:")
                            for i, chunk in enumerate(grounding_chunks[:3], 1):
                                uri = chunk.get('web', {}).get('uri', 'N/A')
                                print(f"     {i}. {uri[:80]}")
                    else:
                        print(f"  ⚠️  Web search requested but no grounding metadata found")
                        print(f"     This may indicate web search is not enabled or requires paid API")
                
                # Check finish reason for issues
                if finish_reason == 'SAFETY':
                    print(f"  ⚠️  Response blocked by safety filters (finishReason: {finish_reason})")
                elif finish_reason == 'MAX_TOKENS':
                    print(f"  ⚠️  Response hit token limit (finishReason: {finish_reason})")
                    print(f"  💡 Consider increasing max_output_tokens")
                elif finish_reason == 'STOP':
                    print(f"  ✅ Response completed normally (finishReason: {finish_reason})")
                
                if text:
                    print(f"  ✅ Got response from Gemini via REST ({len(text)} characters)")
                else:
                    print(f"  ⚠️  Gemini returned empty response")
                    print(f"  📊 Finish reason: {finish_reason}")
                    # Check for errors in response
                    if 'error' in result:
                        print(f"  ❌ Gemini API error: {result.get('error', {})}")
                    # Debug: show candidate structure
                    print(f"  🔍 Debug - Candidate keys: {list(candidate.keys())}")
                    if 'content' in candidate:
                        print(f"  🔍 Debug - Content keys: {list(candidate.get('content', {}).keys())}")
                return {"response": text, "provider": "gemini"}
            else:
                error_text = response.text[:500] if hasattr(response, 'text') else str(response)
                print(f"  ❌ Gemini API returned status {response.status_code}: {error_text}")
                try:
                    error_json = response.json()
                    if 'error' in error_json:
                        error_msg = error_json['error'].get('message', 'Unknown error')
                        print(f"  ❌ Error message: {error_msg}")
                        # Check if it's a quota/API key issue
                        if 'quota' in error_msg.lower() or 'api key' in error_msg.lower() or 'billing' in error_msg.lower():
                            print(f"  💡 This might require a paid Gemini API. Check: https://ai.google.dev/pricing")
                except:
                    pass
                return None
        except requests.exceptions.Timeout as e:
            timeout_used = 120 if use_google_search else 60
            print(f"  ⏱️  Gemini API request timed out (took longer than {timeout_used} seconds)")
            print(f"  💡 Google Search grounding can take longer. Consider:")
            print(f"     - Using a paid Gemini API for faster responses")
            print(f"     - Disabling Google Search and using RSS feeds instead")
            return None
        except Exception as e:
            print(f"  ⚠️  Gemini REST API error: {e}")
            import traceback
            print(f"  📋 Error details: {traceback.format_exc()[:300]}")
            return None
    
    def _generate_openrouter(self, prompt: str, options: Dict) -> Optional[Dict]:
        """Generate using OpenRouter"""
        try:
            url = f"{self.openrouter_config['base_url']}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openrouter_config['api_key']}",
                "Content-Type": "application/json"
            }
            
            temperature = options.get('temperature', self.openrouter_config['temperature'])
            max_tokens = options.get('num_predict', 2048)
            
            data = {
                "model": self.openrouter_config['model'],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": min(max_tokens, 4096)
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=60)
            if response.status_code == 200:
                result = response.json()
                text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                return {"response": text, "provider": "openrouter"}
            return None
        except Exception as e:
            print(f"  ⚠️  OpenRouter error: {e}")
            return None
    
    def _generate_ollama(self, prompt: str, options: Dict) -> Optional[Dict]:
        """Generate using Ollama"""
        try:
            client = ollama.Client(host=self.ollama_config['base_url'])
            
            temperature = options.get('temperature', 0.7)
            num_predict = options.get('num_predict', 2048)
            
            response = client.generate(
                model=self.ollama_config['model'],
                prompt=prompt,
                options={
                    "temperature": temperature,
                    "num_predict": num_predict
                }
            )
            
            text = response.get('response', '')
            return {"response": text, "provider": "ollama"}
        except Exception as e:
            print(f"  ⚠️  Ollama error: {e}")
            return None

