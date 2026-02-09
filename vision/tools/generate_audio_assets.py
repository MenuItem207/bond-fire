#!/usr/bin/env python3
"""Generate clean, warm audio assets for Bondfire (except fire crackle).

This script synthesizes WAV files using only the Python standard library.
It overwrites existing assets with the same names.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import struct
import wave
from pathlib import Path
from typing import Callable, Iterable, List, Tuple

Sample = float


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def env_adsr(t: float, duration: float, attack: float, decay: float, sustain: float, release: float) -> float:
    if duration <= 0.0:
        return 0.0
    if t < 0.0 or t > duration:
        return 0.0

    attack = max(0.0001, attack)
    decay = max(0.0001, decay)
    release = max(0.0001, release)
    sustain = max(0.0, min(1.0, sustain))

    if t < attack:
        return t / attack
    if t < attack + decay:
        return 1.0 - (1.0 - sustain) * ((t - attack) / decay)
    if t < duration - release:
        return sustain
    return sustain * (1.0 - (t - (duration - release)) / release)


def env_exp_decay(t: float, duration: float, start: float = 1.0, end: float = 0.001) -> float:
    if t < 0.0 or t > duration:
        return 0.0
    if duration <= 0.0:
        return 0.0
    if start <= 0.0:
        return 0.0
    ratio = end / start
    return start * (ratio ** (t / duration))


def lowpass(samples: List[Sample], cutoff_hz: Callable[[int], float], sr: int) -> List[Sample]:
    out: List[Sample] = [0.0] * len(samples)
    y = 0.0
    for i, x in enumerate(samples):
        fc = max(10.0, min(sr / 2.5, cutoff_hz(i)))
        alpha = (2.0 * math.pi * fc) / (2.0 * math.pi * fc + sr)
        y = y + alpha * (x - y)
        out[i] = y
    return out


def write_wav(path: Path, samples: List[Sample], sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for s in samples:
            s = clamp(s)
            frames.extend(struct.pack("<h", int(s * 32767)))
        wf.writeframes(frames)


def normalize(samples: List[Sample], peak: float = 0.95) -> List[Sample]:
    max_abs = max((abs(s) for s in samples), default=0.0)
    if max_abs == 0.0:
        return samples
    scale = peak / max_abs
    return [s * scale for s in samples]


def mix(buffers: Iterable[List[Sample]]) -> List[Sample]:
    buffers = list(buffers)
    if not buffers:
        return []
    length = max(len(buf) for buf in buffers)
    out = [0.0] * length
    for buf in buffers:
        for i, s in enumerate(buf):
            out[i] += s
    return out


def render(duration: float, sr: int, fn: Callable[[float, int], float]) -> List[Sample]:
    length = int(duration * sr)
    return [fn(i / sr, i) for i in range(length)]


def sine_wave(freq: float, duration: float, sr: int, amp: float = 1.0, phase: float = 0.0) -> List[Sample]:
    return render(duration, sr, lambda t, i: amp * math.sin(2.0 * math.pi * freq * t + phase))


def sine_sweep(start: float, end: float, duration: float, sr: int, amp: float = 1.0) -> List[Sample]:
    def _fn(t: float, _i: int) -> float:
        ratio = t / duration if duration > 0.0 else 0.0
        freq = start + (end - start) * ratio
        return amp * math.sin(2.0 * math.pi * freq * t)

    return render(duration, sr, _fn)


def noise(duration: float, sr: int, amp: float = 1.0) -> List[Sample]:
    length = int(duration * sr)
    return [amp * random.uniform(-1.0, 1.0) for _ in range(length)]


def make_whoosh(duration: float, sr: int) -> List[Sample]:
    base = noise(duration, sr, amp=0.1)
    sweep = sine_sweep(140.0, 70.0, duration, sr, amp=0.65)
    sub = sine_sweep(70.0, 45.0, duration, sr, amp=0.35)
    env = [env_adsr(t, duration, 0.12, 0.3, 0.7, 0.45) for t in (i / sr for i in range(len(base)))]
    base = [s * e for s, e in zip(base, env)]
    sweep = [s * e for s, e in zip(sweep, env)]
    sub = [s * e for s, e in zip(sub, env)]
    filtered = lowpass(base, lambda i: 800.0 + (350.0 * (1.0 - i / len(base))), sr)
    return normalize(mix([filtered, sweep, sub]), peak=0.9)


def make_buzzer(duration: float, sr: int) -> List[Sample]:
    tone_a = sine_wave(330.0, duration, sr, amp=0.4)
    tone_b = sine_wave(440.0, duration, sr, amp=0.25)
    env = [env_adsr(t, duration, 0.02, 0.08, 0.55, 0.2) for t in (i / sr for i in range(len(tone_a)))]
    combined = [(a + b) * e for a, b, e in zip(tone_a, tone_b, env)]
    return normalize(combined, peak=0.7)


def make_horn(duration: float, sr: int) -> List[Sample]:
    base_freq = 260.0
    phases = [random.uniform(0.0, math.pi * 2.0) for _ in range(3)]
    env = [env_adsr(t, duration, 0.02, 0.18, 0.7, 0.25) for t in (i / sr for i in range(int(duration * sr)))]

    def _fn(t: float, i: int) -> float:
        v = 0.0
        pitch = base_freq * (1.0 + 0.12 * (t / duration))
        for h, ph in enumerate(phases, start=1):
            v += (1.0 / (h * 1.2)) * math.sin(2.0 * math.pi * pitch * h * t + ph)
        return v * env[i] * 0.55

    return normalize(render(duration, sr, _fn), peak=0.8)


def make_chime(duration: float, sr: int) -> List[Sample]:
    length = int(duration * sr)
    out = [0.0] * length

    ding_count = 3
    ding_spacing = duration / (ding_count + 0.5)
    ding_len = max(0.12, ding_spacing * 0.7)
    base = 880.0
    ratios = [1.0, 2.03, 2.57, 3.96]

    for idx in range(ding_count):
        start_t = idx * ding_spacing
        end_t = min(duration, start_t + ding_len)
        start = int(start_t * sr)
        end = int(end_t * sr)
        pitch = base * (1.0 + idx * 0.18)
        for i in range(start, end):
            t = (i - start) / sr
            env = env_exp_decay(t, (end - start) / sr, start=1.0, end=0.0008)
            bell = 0.0
            for r_i, r in enumerate(ratios, start=1):
                bell += (1.0 / (r_i * 1.5)) * math.sin(2.0 * math.pi * pitch * r * t)
            out[i] += bell * env * 0.45

    return normalize(out, peak=0.6)


def make_buildup_start(duration: float, sr: int) -> List[Sample]:
    sweep = sine_sweep(65.0, 110.0, duration, sr, amp=0.7)
    sub = sine_sweep(45.0, 60.0, duration, sr, amp=0.35)
    pad = noise(duration, sr, amp=0.08)
    env = [env_adsr(t, duration, 0.12, 0.3, 0.75, 0.3) for t in (i / sr for i in range(len(sweep)))]
    sweep = [s * e for s, e in zip(sweep, env)]
    sub = [s * e for s, e in zip(sub, env)]
    pad = lowpass(pad, lambda i: 600.0 + (250.0 * (i / len(pad))), sr)
    pad = [s * e * 0.5 for s, e in zip(pad, env)]
    return normalize(mix([sweep, sub, pad]), peak=0.8)


def make_buildup_pulse(duration: float, sr: int) -> List[Sample]:
    length = int(duration * sr)
    out = [0.0] * length
    pulse_positions = [0.0, 0.45]
    pulse_length = 0.18
    for pos in pulse_positions:
        start = int(pos * sr)
        end = min(length, start + int(pulse_length * sr))
        for i in range(start, end):
            t = (i - start) / sr
            amp = env_adsr(t, pulse_length, 0.01, 0.05, 0.5, 0.08)
            out[i] += math.sin(2.0 * math.pi * 180.0 * t) * amp * 0.7
    return normalize(out, peak=0.7)


def make_supernova(duration: float, sr: int) -> List[Sample]:
    burst = noise(duration, sr, amp=0.6)
    burst = lowpass(burst, lambda i: 4000.0 * (1.0 - i / len(burst)) + 300.0, sr)
    drop = sine_sweep(120.0, 45.0, duration, sr, amp=0.7)
    env = [env_adsr(t, duration, 0.02, 0.25, 0.5, 0.4) for t in (i / sr for i in range(len(burst)))]
    burst = [s * e for s, e in zip(burst, env)]
    drop = [s * e for s, e in zip(drop, env)]
    return normalize(mix([burst, drop]), peak=0.9)


def make_party_music(duration: float, sr: int, bpm: float = 80.0) -> List[Sample]:
    bars = int(duration / (60.0 / bpm * 4.0))
    beat_len = 60.0 / bpm
    length = int(duration * sr)

    chords = [
        (220.0, 261.63, 329.63),
        (174.61, 220.0, 261.63),
        (130.81, 164.81, 196.0),
        (146.83, 196.0, 246.94),
    ]

    pad = [0.0] * length
    bass = [0.0] * length
    for bar in range(bars):
        chord = chords[bar % len(chords)]
        start_t = bar * beat_len * 4.0
        end_t = min(duration, start_t + beat_len * 4.0)
        for i in range(int(start_t * sr), int(end_t * sr)):
            t = i / sr
            local = t - start_t
            amp = env_adsr(local, end_t - start_t, 0.2, 0.4, 0.7, 0.4)
            pad[i] += (
                math.sin(2.0 * math.pi * chord[0] * t)
                + math.sin(2.0 * math.pi * chord[1] * t)
                + math.sin(2.0 * math.pi * chord[2] * t)
            ) * amp * 0.12

    total_beats = int(duration / beat_len)
    for beat in range(total_beats):
        start = int(beat * beat_len * sr)
        end = min(length, start + int(0.25 * beat_len * sr))
        for i in range(start, end):
            t = (i - start) / sr
            amp = env_adsr(t, (end - start) / sr, 0.01, 0.05, 0.5, 0.1)
            bass[i] += math.sin(2.0 * math.pi * 55.0 * (beat % 2 + 1) * t) * amp * 0.2

    return normalize(mix([pad, bass]), peak=0.85)


def make_party_layer(duration: float, sr: int, bpm: float = 80.0) -> List[Sample]:
    beat_len = 60.0 / bpm
    length = int(duration * sr)
    shimmer = [0.0] * length
    pulse = [0.0] * length

    total_beats = int(duration / beat_len)
    for beat in range(total_beats):
        start = int(beat * beat_len * sr)
        end = min(length, start + int(0.2 * beat_len * sr))
        for i in range(start, end):
            t = (i - start) / sr
            amp = env_adsr(t, (end - start) / sr, 0.01, 0.05, 0.6, 0.1)
            shimmer[i] += math.sin(2.0 * math.pi * 880.0 * t) * amp * 0.15
            shimmer[i] += math.sin(2.0 * math.pi * 1320.0 * t) * amp * 0.1

    for beat in range(total_beats):
        start = int((beat + 0.5) * beat_len * sr)
        end = min(length, start + int(0.25 * beat_len * sr))
        for i in range(start, end):
            t = (i - start) / sr
            amp = env_adsr(t, (end - start) / sr, 0.01, 0.08, 0.55, 0.1)
            pulse[i] += math.sin(2.0 * math.pi * 110.0 * t) * amp * 0.25

    return normalize(mix([shimmer, pulse]), peak=0.8)


def generate_assets(
    base_dir: Path,
    sr: int,
    music_duration: float,
    sfx_only: bool,
    pulse_interval: float,
) -> None:
    sfx_dir = base_dir / "sfx"
    music_dir = base_dir / "music"

    chime_duration = max(0.5, min(1.2, pulse_interval * 0.06))
    assets = {
        "whoosh_entry.wav": make_whoosh(1.2, sr),
        "buzzer_alert.wav": make_buzzer(0.7, sr),
        "party_horn.wav": make_horn(1.2, sr),
        "soft_chime.wav": make_chime(chime_duration, sr),
        "buildup_start.wav": make_buildup_start(1.2, sr),
        "buildup_pulse.wav": make_buildup_pulse(0.9, sr),
        "supernova_burst.wav": make_supernova(1.5, sr),
    }

    for name, data in assets.items():
        write_wav(sfx_dir / name, data, sr)

    if not sfx_only:
        party_music = make_party_music(music_duration, sr)
        write_wav(music_dir / "party_upbeat.wav", party_music, sr)
        party_layer = make_party_layer(music_duration, sr)
        write_wav(music_dir / "party_layer.wav", party_layer, sr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Bondfire audio assets (except fire crackle).")
    parser.add_argument(
        "--assets-dir",
        default=str(Path(__file__).resolve().parents[1] / "assets"),
        help="Path to assets directory (default: vision/assets)",
    )
    parser.add_argument("--sample-rate", type=int, default=44100, help="Sample rate in Hz")
    parser.add_argument(
        "--music-duration",
        type=float,
        default=16.0,
        help="Party music duration in seconds (shorter renders faster)",
    )
    parser.add_argument(
        "--pulse-interval",
        type=float,
        default=15.0,
        help="Pulse interval in seconds (scales chime duration)",
    )
    parser.add_argument(
        "--sfx-only",
        action="store_true",
        help="Generate SFX only (skip party music)",
    )
    args = parser.parse_args()

    assets_dir = Path(args.assets_dir)
    generate_assets(
        assets_dir,
        args.sample_rate,
        args.music_duration,
        args.sfx_only,
        args.pulse_interval,
    )
    print(f"Generated assets in {assets_dir}")


if __name__ == "__main__":
    main()
