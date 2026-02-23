import os
import requests
import json
from datetime import datetime, timezone, timedelta

# --- Configuration ---
API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Get API key from environment variable (Best Practice)
API_KEY = "AIzaSyDHaxrdbhUQvLMMns966Kg9nJyeBSRgo98"

def test_rest_api_web_search():
    """
    Tests web search grounding using the Gemini REST API via the Python requests library.
    """
    print("=" * 70)
    print("Testing Gemini 2.5 Flash Web Search Capability (REST API Method)")
    print("=" * 70)

    if not API_KEY:
        print("❌ Error: GEMINI_API_KEY environment variable is not set.")
        print('Please set it in your terminal: export GEMINI_API_KEY="YOUR_API_KEY_HERE"')
        return

    # Get today's date for a search that requires current information
    ist = timezone(timedelta(hours=5, minutes=30))
    today_ist = datetime.now(ist).strftime('%Y-%m-%d')
    
    # --- RELAXED PROMPT ---
    # Asking for a summary rather than ONLY a number increases output stability
    test_prompt = f"""What is the current projected GDP growth rate of India for the current fiscal year as of {today_ist}? 
    
Please search the web for the most recent, verified projection and provide a brief, factual summary including the source."""
    # ----------------------

    # --- 1. Define Headers and Payload ---
    headers = {
        "x-goog-api-key": API_KEY,
    }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": test_prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "max_output_tokens": 1024 # Increased tokens to ensure summary completes
        },
        "tools": [
            {
                "googleSearch": {}
            }
        ]
    }

    print(f"\n📅 Today's date (IST): {today_ist}")
    print(f"📝 Test Prompt: {test_prompt[:100]}...")
    print(f"\n🔍 Using Google Search via REST API...")
    print(f"⏳ Sending request to Gemini API endpoint: {API_ENDPOINT}...")

    try:
        # --- 2. Make the POST Request ---
        response = requests.post(API_ENDPOINT, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        response_data = response.json()
        print(f"\n✅ API Response Received (Status: {response.status_code})")

        # --- 3. Diagnostics and Output Extraction ---
        candidate = response_data.get("candidates", [{}])[0]
        
        # 3a. Extract Text and Finish Reason
        text = candidate.get("content", {}).get("parts", [{}])[0].get("text", "No text found.")
        finish_reason = candidate.get("finishReason", "UNKNOWN")
        
        # 3b. Check for grounding metadata
        grounding_metadata = candidate.get("groundingMetadata")
        
        print("\n📊 Response Analysis:")
        print(f"   - Finish Reason: {finish_reason}")
        
        if grounding_metadata and grounding_metadata.get("webSearchQueries"):
            queries = grounding_metadata.get("webSearchQueries")
            sources = grounding_metadata.get("groundingChunks", [])
            print(f"   - Web Search Queries: {len(queries)}")
            print(f"   - Sources Retrieved: {len(sources)}")
            print(f"\n✅ WEB SEARCH IS NOW WORKING via REST API! (Grounding Found)")
            
            print(f"\n📝 Gemini's Response:")
            print(f"   {text.strip()}")
            if sources:
                print("\n🌐 Sources Found:")
                for i, source in enumerate(sources[:3], 1):
                    uri = source.get("web", {}).get("uri", "N/A")
                    print(f"   {i}. {uri}")
        else:
            print("\n⚠️  NO Grounding Metadata Found. Web search did not trigger.")
            print(f"\n📝 Gemini's Raw Response Text:")
            print(f"   {text.strip()}")
            if finish_reason == "SAFETY":
                print("\n🛑 Model output was blocked due to SAFETY filters.")
            
    except requests.exceptions.HTTPError as errh:
        print(f"\n❌ HTTP Error: {errh}")
        print(f"   Response Body (Full Error):")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
    except Exception as err:
        print(f"\n❌ An Unexpected Error Occurred: {err}")
    
    print(f"\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)

if __name__ == "__main__":
    test_rest_api_web_search()