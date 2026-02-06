#!/usr/bin/env python3
"""List available TTS voices for configuration."""

import sys

try:
    import pyttsx3
except ImportError:
    print("Error: pyttsx3 not installed. Run: pip install pyttsx3")
    sys.exit(1)


def list_voices():
    """List all available TTS voices."""
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        
        if not voices:
            print("No TTS voices available on this system.")
            return
        
        print(f"\nAvailable TTS Voices ({len(voices)} found):\n")
        
        for i, voice in enumerate(voices, 1):
            print(f"{i}. {voice.name}")
            print(f"   ID: {voice.id}")
            print()
        
        print("\nUsage:")
        print("  bond-fire-vision --enable-audio --narration-enabled --tts-voice 'Voice Name'")
        print("\nExample:")
        if voices:
            print(f"  bond-fire-vision --enable-audio --narration-enabled --tts-voice '{voices[0].name}'")
    
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    list_voices()
