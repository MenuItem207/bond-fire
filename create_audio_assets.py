#!/usr/bin/env python3
"""Generate all required audio assets for Bond Fire installation.

Creates WAV files using sine wave synthesis. These are placeholder files
that allow the system to run without external audio assets.

Run this once:
    python create_audio_assets.py

For production MP3 files, convert with ffmpeg:
    ffmpeg -i audio.wav -q:a 5 audio.mp3
"""

import struct
import math
from pathlib import Path


def sine_wave(frequency: float, duration: float, sample_rate: int = 44100) -> bytes:
    """Generate a sine wave at given frequency."""
    num_samples = int(duration * sample_rate)
    frames = []
    
    for i in range(num_samples):
        sample = math.sin(2.0 * math.pi * frequency * i / sample_rate)
        sample_int = int(sample * 32767)
        frames.append(struct.pack('<h', sample_int))
    
    return b''.join(frames)


def frequency_sweep(start_freq: float, end_freq: float, duration: float, sample_rate: int = 44100) -> bytes:
    """Generate a frequency sweep (chirp)."""
    num_samples = int(duration * sample_rate)
    frames = []
    
    for i in range(num_samples):
        progress = i / num_samples
        freq = start_freq + (end_freq - start_freq) * progress
        sample = math.sin(2.0 * math.pi * freq * i / sample_rate)
        sample_int = int(sample * 32767)
        frames.append(struct.pack('<h', sample_int))
    
    return b''.join(frames)


def white_noise(duration: float, sample_rate: int = 44100) -> bytes:
    """Generate white noise."""
    import random
    num_samples = int(duration * sample_rate)
    frames = []
    
    for i in range(num_samples):
        sample = random.uniform(-1, 1)
        sample_int = int(sample * 32767)
        frames.append(struct.pack('<h', sample_int))
    
    return b''.join(frames)


def write_wav(filename: Path, audio_data: bytes, sample_rate: int = 44100, channels: int = 1) -> None:
    """Write raw audio data to a WAV file."""
    byte_rate = sample_rate * channels * 2
    block_align = channels * 2
    data_size = len(audio_data)
    file_size = 36 + data_size
    
    with open(filename, 'wb') as f:
        # WAV header
        f.write(b'RIFF')
        f.write(struct.pack('<I', file_size))
        f.write(b'WAVE')
        
        # fmt subchunk
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))
        f.write(struct.pack('<H', 1))   # PCM
        f.write(struct.pack('<H', channels))
        f.write(struct.pack('<I', sample_rate))
        f.write(struct.pack('<I', byte_rate))
        f.write(struct.pack('<H', block_align))
        f.write(struct.pack('<H', 16))
        
        # data subchunk
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        f.write(audio_data)


# ============================================================================
# SFX Generators
# ============================================================================

def create_fire_crackle_loop() -> bytes:
    """30s fire crackle loop with varied frequencies."""
    # Simulate crackling by layering multiple sine waves with variations
    sample_rate = 44100
    duration = 30
    num_samples = int(duration * sample_rate)
    samples = [0] * num_samples
    
    # Multiple crackle frequencies
    frequencies = [120, 250, 400, 600]
    amplitudes = [0.2, 0.15, 0.1, 0.08]
    
    for freq, amp in zip(frequencies, amplitudes):
        for i in range(num_samples):
            # Add slight frequency variation for natural crackle
            var_freq = freq * (0.9 + 0.2 * math.sin(i / sample_rate * 0.5))
            sample = math.sin(2.0 * math.pi * var_freq * i / sample_rate)
            samples[i] += sample * amp * 32767
    
    # Normalize and convert
    frames = []
    for sample in samples:
        sample_int = max(-32767, min(32767, int(sample / len(frequencies))))
        frames.append(struct.pack('<h', sample_int))
    
    return b''.join(frames)


def create_whoosh_entry() -> bytes:
    """1s whoosh sound for person entry."""
    return frequency_sweep(200, 800, 0.5) + frequency_sweep(800, 200, 0.5)


def create_buzzer_alert() -> bytes:
    """0.5s buzzer alert tone."""
    return sine_wave(900, 0.5)


def create_party_horn() -> bytes:
    """2s celebratory party horn tone."""
    # Upward sweep with decay
    sweep = frequency_sweep(400, 1200, 2.0)
    
    # Add fade out in last 0.5s
    fade_start = int(44100 * 1.5 * 2)
    fade_section = bytearray(sweep[fade_start:])
    
    for i in range(len(fade_section) // 2):
        progress = i / (len(fade_section) // 2)
        fade_factor = 1.0 - (progress * progress)  # Quadratic fade
        
        sample = struct.unpack('<h', fade_section[i*2:i*2+2])[0]
        sample = int(sample * fade_factor)
        struct.pack_into('<h', fade_section, i*2, sample)
    
    return sweep[:fade_start] + bytes(fade_section)


def create_soft_chime() -> bytes:
    """Short soft chime tone."""
    # Two harmonics for pleasant chime
    sample_rate = 44100
    duration = 0.5
    num_samples = int(duration * sample_rate)
    samples = [0] * num_samples
    
    # Fundamental and 2nd harmonic
    for i in range(num_samples):
        fund = math.sin(2.0 * math.pi * 440 * i / sample_rate) * 0.6
        harmonic = math.sin(2.0 * math.pi * 880 * i / sample_rate) * 0.4
        # Fade out
        progress = i / num_samples
        fade = 1.0 - (progress * progress * progress)
        samples[i] = (fund + harmonic) * fade * 32767
    
    frames = []
    for sample in samples:
        sample_int = max(-32767, min(32767, int(sample)))
        frames.append(struct.pack('<h', sample_int))
    
    return b''.join(frames)


def create_buildup_start() -> bytes:
    """Rising tone for buildup start (200Hz → 800Hz)."""
    return frequency_sweep(200, 800, 0.8)


def create_buildup_pulse() -> bytes:
    """Pulsing tone during buildup (heartbeat pattern)."""
    pulse1 = sine_wave(600, 0.1)
    silence = b'\x00' * int(44100 * 0.05 * 2)
    pulse2 = sine_wave(600, 0.1)
    silence2 = b'\x00' * int(44100 * 0.05 * 2)
    pulse3 = sine_wave(600, 0.1)
    
    return pulse1 + silence + pulse2 + silence2 + pulse3


def create_supernova_burst() -> bytes:
    """Explosion sound for party start."""
    # Quick sweep with decay
    sweep = frequency_sweep(400, 2000, 0.5)
    
    fade_start = int(44100 * 0.3 * 2)
    fade_section = bytearray(sweep[fade_start:])
    
    for i in range(len(fade_section) // 2):
        progress = i / (len(fade_section) // 2)
        fade_factor = 1.0 - progress
        
        sample = struct.unpack('<h', fade_section[i*2:i*2+2])[0]
        sample = int(sample * fade_factor)
        struct.pack_into('<h', fade_section, i*2, sample)
    
    return sweep[:fade_start] + bytes(fade_section)


# ============================================================================
# Music Generators
# ============================================================================

def create_party_upbeat() -> bytes:
    """3min looping upbeat track (rhythm pattern)."""
    # Simulated upbeat rhythm with multiple tones
    sample_rate = 44100
    duration = 180  # 3 minutes
    num_samples = int(duration * sample_rate)
    samples = [0] * num_samples
    
    # Create a repeating beat pattern (4/4 rhythm)
    beat_length = int(sample_rate * 0.5)  # 500ms per beat
    
    for i in range(num_samples):
        beat_position = i % (beat_length * 4)
        
        # Play different tones on different beats
        if beat_position < beat_length:
            # Beat 1: high tone
            sample = math.sin(2.0 * math.pi * 800 * i / sample_rate) * 0.3
        elif beat_position < beat_length * 2:
            # Beat 2: medium tone
            sample = math.sin(2.0 * math.pi * 600 * i / sample_rate) * 0.25
        elif beat_position < beat_length * 3:
            # Beat 3: high tone
            sample = math.sin(2.0 * math.pi * 800 * i / sample_rate) * 0.3
        else:
            # Beat 4: low tone
            sample = math.sin(2.0 * math.pi * 400 * i / sample_rate) * 0.2
        
        # Envelope each beat
        beat_progress = (beat_position % beat_length) / beat_length
        envelope = math.sin(beat_progress * math.pi) * 0.5 + 0.5
        samples[i] = sample * envelope * 32767
    
    frames = []
    for sample in samples:
        sample_int = max(-32767, min(32767, int(sample)))
        frames.append(struct.pack('<h', sample_int))
    
    return b''.join(frames)


def main() -> None:
    """Generate all audio assets."""
    # Ensure directories exist
    sfx_dir = Path(__file__).parent / "vision" / "assets" / "sfx"
    music_dir = Path(__file__).parent / "vision" / "assets" / "music"
    
    sfx_dir.mkdir(parents=True, exist_ok=True)
    music_dir.mkdir(parents=True, exist_ok=True)
    
    print("Generating Bond Fire audio assets...")
    print(f"  SFX directory: {sfx_dir}")
    print(f"  Music directory: {music_dir}\n")
    
    # SFX files
    sfx_files = {
        "fire_crackle_loop.wav": (create_fire_crackle_loop, "30s fire crackle"),
        "whoosh_entry.wav": (create_whoosh_entry, "1s whoosh"),
        "buzzer_alert.wav": (create_buzzer_alert, "0.5s buzzer"),
        "party_horn.wav": (create_party_horn, "2s party horn"),
        "soft_chime.wav": (create_soft_chime, "0.5s soft chime"),
        "buildup_start.wav": (create_buildup_start, "0.8s buildup start"),
        "buildup_pulse.wav": (create_buildup_pulse, "0.5s buildup pulse"),
        "supernova_burst.wav": (create_supernova_burst, "0.5s supernova"),
    }
    
    print("Generating SFX...")
    for filename, (generator, description) in sfx_files.items():
        filepath = sfx_dir / filename
        audio_data = generator()
        write_wav(filepath, audio_data)
        size_kb = len(audio_data) / 1024
        print(f"  ✓ {filename:<25} ({size_kb:>6.1f} KB) - {description}")
    
    # Music files
    music_files = {
        "party_upbeat.wav": (create_party_upbeat, "3min upbeat rhythm"),
    }
    
    print("\nGenerating Music...")
    for filename, (generator, description) in music_files.items():
        filepath = music_dir / filename
        audio_data = generator()
        write_wav(filepath, audio_data)
        size_kb = len(audio_data) / 1024
        print(f"  ✓ {filename:<25} ({size_kb:>6.1f} KB) - {description}")
    
    print("\n✅ All audio assets created successfully!")
    print("\nNote: pygame.mixer can play .wav files directly.")
    print("For production, convert to MP3 using ffmpeg:")
    print("  cd vision/assets/sfx && for f in *.wav; do ffmpeg -i \"$f\" -q:a 5 \"${f%.wav}.mp3\"; done")
    print("  cd ../music && for f in *.wav; do ffmpeg -i \"$f\" -q:a 5 \"${f%.wav}.mp3\"; done")


if __name__ == "__main__":
    main()
