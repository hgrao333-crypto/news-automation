#!/usr/bin/env python3
"""
Test script for LLM-based effect suggestions with a single image/segment
Tests the effect suggestion generation logic without requiring full video generator
"""

import json
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_client import LLMClient

def generate_effect_suggestions_test(script_data, image_prompts, video_description=""):
    """
    Test version of _generate_effect_suggestions - replicates the logic
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
            segment_text = segment.get('text', '')[:200]
            story_index = segment.get('story_index')
            image_prompt = image_prompts[i] if i < len(image_prompts) else "No image prompt"
            
            # Build history of previous segments (up to 3 previous segments)
            previous_segments = []
            for prev_idx in range(max(0, i - 3), i):
                prev_segment = segments[prev_idx]
                prev_segment_type = prev_segment.get('type', 'summary')
                prev_segment_text = prev_segment.get('text', '')[:150]
                prev_story_index = prev_segment.get('story_index')
                prev_image_prompt = image_prompts[prev_idx] if prev_idx < len(image_prompts) else "No image prompt"
                
                previous_segments.append({
                    'index': prev_idx,
                    'type': prev_segment_type,
                    'text': prev_segment_text,
                    'story_index': prev_story_index,
                    'image_prompt': prev_image_prompt[:100]
                })
            
            segments_info.append({
                'index': i,
                'type': segment_type,
                'text': segment_text,
                'story_index': story_index,
                'image_prompt': image_prompt[:150],
                'previous_segments': previous_segments
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
- Audio effects: Use reverb for depth (room_size: 0.1-0.3), echo for emphasis (delay: 0.1-0.3s, decay: 0.3-0.5)
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
    }}
  }},
  "global_audio_effects": {{
    "reverb": {{"enabled": true, "room_size": 0.2, "damping": 0.6}},
    "echo": {{"enabled": true, "delay": 0.15, "decay": 0.4, "repeats": 1}}
  }}
}}

Return ONLY valid JSON, no markdown formatting."""
        
        # Get LLM response
        llm_client = LLMClient()
        response = llm_client.generate(prompt, {
            "temperature": 0.3,
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

def test_single_segment_effects():
    """Test effect suggestions for a single segment"""
    print("=" * 60)
    print("Testing Effect Suggestions for 1 Segment")
    print("=" * 60)
    
    # Create a minimal script_data with 1 segment
    script_data = {
        'title': 'Breaking: Major Tech Announcement',
        'description': 'Breaking news about a major technology announcement',
        'segments': [
            {
                'type': 'headline',
                'text': 'Breaking: Major tech company announces revolutionary AI breakthrough that could change everything',
                'story_index': 1,
                'start_time': 0.0,
                'duration': 5.0
            }
        ],
        'image_prompts': [
            'Futuristic AI technology visualization with glowing neural networks and digital particles, dramatic lighting, tech aesthetic'
        ]
    }
    
    print("\n📋 Test Data:")
    print(f"  Title: {script_data['title']}")
    print(f"  Segments: {len(script_data['segments'])}")
    print(f"  Image Prompts: {len(script_data['image_prompts'])}")
    print(f"\n  Segment 0:")
    print(f"    Type: {script_data['segments'][0]['type']}")
    print(f"    Text: {script_data['segments'][0]['text'][:60]}...")
    print(f"    Story Index: {script_data['segments'][0]['story_index']}")
    print(f"    Image Prompt: {script_data['image_prompts'][0][:60]}...")
    print(f"    Previous Segments: {len([])} (none - this is the first segment)")
    
    # Test effect suggestion generation
    print("\n🤖 Generating Effect Suggestions...")
    print("-" * 60)
    
    try:
        effect_suggestions = generate_effect_suggestions_test(
            script_data=script_data,
            image_prompts=script_data['image_prompts'],
            video_description=script_data['description']
        )
        
        if effect_suggestions:
            print("\n✅ Effect Suggestions Generated Successfully!")
            print("-" * 60)
            
            # Pretty print the suggestions
            print("\n📊 Full Effect Suggestions JSON:")
            print(json.dumps(effect_suggestions, indent=2))
            
            # Check segment effects
            segment_effects = effect_suggestions.get('segment_effects', {})
            if '0' in segment_effects:
                seg_0 = segment_effects['0']
                print("\n🎬 Segment 0 Effects Summary:")
                print(f"  Glitch: {seg_0.get('glitch', {})}")
                print(f"  Color Grading: {seg_0.get('color_grading', {})}")
                print(f"  Particles: {seg_0.get('particles', {})}")
                if 'transition_note' in seg_0:
                    print(f"  Transition Note: {seg_0['transition_note']}")
            
            # Check global audio effects
            global_effects = effect_suggestions.get('global_audio_effects', {})
            if global_effects:
                print("\n🔊 Global Audio Effects:")
                print(f"  Reverb: {global_effects.get('reverb', {})}")
                print(f"  Echo: {global_effects.get('echo', {})}")
            
            print("\n✅ Test Passed!")
            return True
        else:
            print("\n❌ No effect suggestions returned")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_multiple_segments_with_history():
    """Test effect suggestions with multiple segments to verify history works"""
    print("\n" + "=" * 60)
    print("Testing Effect Suggestions with Multiple Segments (History)")
    print("=" * 60)
    
    # Create script_data with 3 segments to test history
    script_data = {
        'title': 'Breaking: Major Conflict Escalates',
        'description': 'Breaking news about escalating conflict',
        'segments': [
            {
                'type': 'headline',
                'text': 'Breaking: Major conflict erupts in region',
                'story_index': 1,
                'start_time': 0.0,
                'duration': 3.0
            },
            {
                'type': 'summary',
                'text': 'Initial reports indicate tensions have escalated dramatically with multiple casualties reported',
                'story_index': 1,
                'start_time': 3.0,
                'duration': 5.0
            },
            {
                'type': 'headline',
                'text': 'International community responds to crisis',
                'story_index': 2,
                'start_time': 8.0,
                'duration': 3.0
            }
        ],
        'image_prompts': [
            'Dramatic conflict scene with tension and urgency, dark colors, dramatic lighting',
            'War-torn landscape with smoke and destruction, cinematic style',
            'Diplomatic meeting scene, professional and serious tone, news style'
        ]
    }
    
    print("\n📋 Test Data:")
    print(f"  Title: {script_data['title']}")
    print(f"  Segments: {len(script_data['segments'])}")
    for i, seg in enumerate(script_data['segments']):
        prev_count = min(3, i)  # Up to 3 previous segments
        print(f"\n  Segment {i}:")
        print(f"    Type: {seg['type']}")
        print(f"    Text: {seg['text'][:50]}...")
        print(f"    Story Index: {seg['story_index']}")
        print(f"    Will have {prev_count} previous segment(s) in history")
    
    print("\n🤖 Generating Effect Suggestions with History...")
    print("-" * 60)
    
    try:
        effect_suggestions = generate_effect_suggestions_test(
            script_data=script_data,
            image_prompts=script_data['image_prompts'],
            video_description=script_data['description']
        )
        
        if effect_suggestions:
            print("\n✅ Effect Suggestions Generated Successfully!")
            print("-" * 60)
            
            segment_effects = effect_suggestions.get('segment_effects', {})
            
            # Check each segment
            for i in range(len(script_data['segments'])):
                seg_key = str(i)
                if seg_key in segment_effects:
                    seg_effects = segment_effects[seg_key]
                    print(f"\n🎬 Segment {i} Effects:")
                    print(f"  Glitch: {seg_effects.get('glitch', {})}")
                    print(f"  Color Grading: {seg_effects.get('color_grading', {})}")
                    print(f"  Particles: {seg_effects.get('particles', {})}")
                    if 'transition_note' in seg_effects:
                        print(f"  Note: {seg_effects['transition_note']}")
            
            print("\n✅ Multi-Segment Test Passed!")
            return True
        else:
            print("\n❌ No effect suggestions returned")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n🧪 Testing LLM-Based Effect Suggestions\n")
    
    # Test 1: Single segment
    result1 = test_single_segment_effects()
    
    # Test 2: Multiple segments with history
    result2 = test_multiple_segments_with_history()
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print(f"  Single Segment Test: {'✅ PASSED' if result1 else '❌ FAILED'}")
    print(f"  Multi-Segment Test: {'✅ PASSED' if result2 else '❌ FAILED'}")
    print("=" * 60)

