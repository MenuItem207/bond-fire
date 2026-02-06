#!/usr/bin/env python3
"""Generate test audio SFX using simple sine wave synthesis.

This creates placeholder build-up audio files so you can test the full
audio pipeline without needing to source real audio files.

Run this once to create the asset files:
    python generate_test_sfx.py

Then test with:
    python src/bond_fire_vision/cli.py --enable-audio --camera-index 0
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
        # Convert to 16-bit signed integer
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


def write_wav(filename: Path, audio_data: bytes, sample_rate: int = 44100, channels: int = 1) -> None:
    """Write raw audio data to a WAV file."""
    byte_rate = sample_rate * channels * 2  # 2 bytes per sample
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
        f.write(struct.pack('<I', 16))  # Subchunk1Size
        f.write(struct.pack('<H', 1))   # AudioFormat (PCM)
        f.write(struct.pack('<H', channels))
        f.write(struct.pack('<I', sample_rate))
        f.write(struct.pack('<I', byte_rate))
        f.write(struct.pack('<H', block_align))
        f.write(struct.pack('<H', 16))  # BitsPerSample
        
        # data subchunk
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        f.write(audio_data)


def create_buildup_start() -> bytes:
    """
    Create buildup_start.mp3 - Rising tone (200Hz → 800Hz over 0.8s).
    
    Represents energy charging up.
    """
    return frequency_sweep(200, 800, 0.8)


def create_buildup_pulse() -> bytes:
    """
    Create buildup_pulse.mp3 - Pulsing heartbeat-like tone.
    
    Plays at 33% and 66% of build-up phase.
    """
    # Pulse pattern: 3 quick beeps
    pulse1 = sine_wave(600, 0.1)  # 100ms beep
    silence = b'\x00' * int(44100 * 0.05 * 2)  # 50ms silence
    pulse2 = sine_wave(600, 0.1)
    silence2 = b'\x00' * int(44100 * 0.05 * 2)
    pulse3 = sine_wave(600, 0.1)
    
    return pulse1 + silence + pulse2 + silence2 + pulse3


def create_supernova() -> bytes:
    """
    Create supernova.mp3 - Explosion/cymbal crash effect.
    
    Sweeping upward tone that tapers off (celebratory).
    """
    # Quick sweep upward: 400Hz → 2000Hz over 0.3s, then fade
    sweep = frequency_sweep(400, 2000, 0.5)
    
    # Add decay (volume reduction) at end
    fade_start = int(44100 * 0.3 * 2)
    fade_section = bytearray(sweep[fade_start:])
    
    for i in range(len(fade_section) // 2):
        progress = i / (len(fade_section) // 2)
        fade_factor = 1.0 - progress
        
        sample = struct.unpack('<h', fade_section[i*2:i*2+2])[0]
        sample = int(sample * fade_factor)
        struct.pack_into('<h', fade_section, i*2, sample)
    
    return sweep[:fade_start] + bytes(fade_section)


def main() -> None:
    """Generate test audio files."""
    assets_dir = Path(__file__).parent / "vision" / "assets" / "sfx"
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Generating test SFX in {assets_dir}/")
    
    # Create placeholder MP3s (WAV files, Python can play these with pygame)
    files = {
        "buildup_start.wav": (create_buildup_start, "Buildup start tone (200→800Hz)"),
        "buildup_pulse.wav": (create_buildup_pulse, "Buildup pulse (heartbeat pattern)"),
        "supernova.wav": (create_supernova, "Supernova explosion (sweep + fade)"),
    }
    
    for filename, (generator, description) in files.items():
        filepath = assets_dir / filename
        audio_data = generator()
        write_wav(filepath, audio_data)
        print(f"  ✓ {filename} ({len(audio_data) // 2} samples) - {description}")
    
    print("\nNote: pygame.mixer can play .wav files directly.")
    print("If you want .mp3 files, convert these using ffmpeg:")
    print("  ffmpeg -i buildup_start.wav buildup_start.mp3")
    print("\nTest with:")
    print("  python src/bond_fire_vision/cli.py --enable-audio --camera-index 0")


if __name__ == "__main__":
    main()
