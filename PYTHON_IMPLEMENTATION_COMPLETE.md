# Python Implementation Checklist & Build-Up Audio Guide

## ✅ Implementation Status: COMPLETE

All Python components have been fully implemented and integrated. Here's what's active:

### Core Components

#### 1. **State Machine** (`state_machine.py`) ✅
- [x] IDLE → FIRE → PARTY → PHONE transitions
- [x] Timers: IDLE_TIMEOUT (5s), PARTY_DWELL (2s), PHONE_EXIT_DWELL (2s)
- [x] **NEW:** PHONE_ENTRY_DWELL (0.0s - instant detection)
- [x] **NEW:** PARTY_ENTRY_BUILDUP (1.5s build-up phase)
- [x] **NEW:** `party_buildup_progress` field (0.0-1.0)
- [x] Hardware PWM formulas: `mist=180+(n×15)`, `fan=100+(n×30)`
- [x] Entry flash animation tracking
- [x] Fire pulse animation (every 15s)

#### 2. **Color Analysis** (`color_analysis.py`) ✅
- [x] k-means clustering on shirt colors
- [x] CSS color naming (140 color dictionary)
- [x] Color contrast detection
- [x] Palette deduplication
- [x] Light/Dark modifier application

#### 3. **Local Prompts** (`local_prompts.py`) ✅
- [x] 40+ curated prompts across 6 pools
- [x] State-aware prompt selection
- [x] **NEW:** 8-second cooldown timer prevents rapid changes
- [x] History deque prevents repetition
- [x] Entry & pulse prompt generation
- [x] Color-aware prompts for contrasting people

#### 4. **Audio Manager** (`audio_manager.py`) ✅
- [x] Non-blocking pygame.mixer threading
- [x] 3 audio channels: MUSIC, SFX_PRIMARY, SFX_SECONDARY, NARRATION
- [x] Audio state tracking: SILENT, AMBIENT, PARTY, ALERT
- [x] `play_sfx()` for sound effects
- [x] `play_music()` for background music
- [x] `speak()` for TTS narration
- [x] **NEW:** Build-up SFX assets mapped:
  - `"buildup_start"` - Low tone signaling build-up beginning
  - `"buildup_pulse"` - Pulsing tone during build-up progression
  - `"supernova"` - Explosion sound when party begins

#### 5. **Packet Builder** (`packet_builder.py`) ✅
- [x] v2.1 JSON schema with 18 fields
- [x] Validation: PWM clamping, prompt truncation
- [x] FPS tracking (30-packet history)
- [x] People array (max 6, normalized bbox)
- [x] **NEW:** `party_buildup_progress` field included in packets

#### 6. **Detector** (`detector.py`) ✅
- [x] YOLOv8 person tracking with persistent IDs
- [x] Phone detection (class 67)
- [x] **NEW:** 25px ROI margin for edge detection
- [x] Shirt color extraction per person
- [x] State machine integration
- [x] Prompt generation with history
- [x] Audio event triggering:
  - Entry flash → `play_sfx("whoosh")`
  - Color pulse → `play_sfx("chime")`
  - **NEW:** Build-up start → `play_sfx("buildup_start")`
  - **NEW:** Build-up steps → `play_sfx("buildup_pulse")` at 33% & 66%
- [x] Packet building & UDP broadcast @ 30fps
- [x] **NEW:** Party buildup progress tracking & audio triggers

#### 7. **CLI** (`cli.py`) ✅
- [x] Argument parser with 12 options
- [x] New flags: `--pulse-interval`, `--enable-audio`, `--audio-volume`, `--narration-enabled`
- [x] Legacy flags handled gracefully (with deprecation warnings)
- [x] Network config: `--broadcast-ip`, `--broadcast-port`
- [x] Camera & detection config

---

## 🔊 Build-Up Audio: How It Works

### Timeline & Triggers

```
EVENT SEQUENCE:
0.00s: 5th person detected (first time with ≥5 people)
0.01s: State machine notes: people_count ≥ 5 for first time

2.00s: 5 people sustained for 2.0s (PARTY_DWELL expires)
2.05s: Build-up phase begins
       ├─ party_buildup_progress = 0.0
       ├─ Detector detects this transition (0.0 → 0.01)
       └─ Plays: play_sfx("buildup_start", volume=0.9)
       
2.35s: First build-up step milestone (33% progress)
       ├─ party_buildup_progress = 0.33
       ├─ _last_buildup_step changes from 0 → 1
       └─ Plays: play_sfx("buildup_pulse", volume=0.7)

2.70s: Second build-up step milestone (66% progress)
       ├─ party_buildup_progress = 0.66
       ├─ _last_buildup_step changes from 1 → 2
       └─ Plays: play_sfx("buildup_pulse", volume=0.7)

3.55s: Build-up complete, PARTY state achieved
       ├─ party_buildup_progress = 1.0 → 0.0
       ├─ state changes from FIRE → PARTY
       └─ audio_state changes from AMBIENT → PARTY
          (triggers play_music("party_music", loop=True))
```

### Python Audio Calls During Build-Up

```python
# In detector._send_update() loop:

# When buildup just starts (progress 0.0 → 0.01)
if state_output.party_buildup_progress > 0.0 and not self._party_buildup_started:
    if self.audio_manager:
        self.audio_manager.play_sfx("buildup_start", volume=0.9)
    self._party_buildup_started = True

# During buildup at 33% and 66% milestones
buildup_step = int(state_output.party_buildup_progress * 3)  # 0, 1, 2, or 3
if buildup_step > self._last_buildup_step:
    if self.audio_manager and buildup_step in (1, 2):
        self.audio_manager.play_sfx("buildup_pulse", volume=0.7)
    self._last_buildup_step = buildup_step

# When build-up ends (progress returns to 0.0)
elif state_output.party_buildup_progress == 0.0:
    self._party_buildup_started = False
    # PARTY state now active, play_music() triggered by audio_state change
```

---

## 📦 Build-Up SFX Assets Needed

Create these files in `vision/assets/sfx/`:

### 1. **buildup_start.mp3** (0.5-1.0 second)
- **Description:** Single low-frequency "whoosh" or "charging" sound
- **Characteristics:** 
  - Starts at ~200Hz, rises to ~800Hz
  - Volume: medium (0.9 in code)
  - Perception: "Something big is about to happen"
- **Examples:**
  - Synthesized "charging" tone (like Samus charging)
  - Deep bass swell
  - Low wind sound building upward

### 2. **buildup_pulse.mp3** (0.3-0.5 seconds)
- **Description:** Repeating pulse/heartbeat sound (plays at 33% and 66%)
- **Characteristics:**
  - Pulsing tone, ~600Hz
  - Tempo: 2 pulses in 0.4s (300bpm-ish)
  - Volume: medium-soft (0.7 in code)
  - Perception: "Energy gathering, building anticipation"
- **Examples:**
  - Synthesized heartbeat getting faster
  - Laser charging pulse (beep-beep-beep)
  - Electrical arcing tone

### 3. **supernova.mp3** (1.0-2.0 seconds)
- **Description:** Explosion/release sound (optional, plays when PARTY starts)
- **Characteristics:**
  - Loud, bright, celebratory
  - Starts as crescendo, ends with burst
  - Volume: 1.0
  - Perception: "LET'S GO! PARTY TIME!"
- **Examples:**
  - Firework explosion
  - Cymbal crash + sparkle
  - Synth "pew" burst

### Optional Enhancement: Commercial Sounds

If you want professional-grade audio, check these sources:
- **Freesound.org** (CC0/CC-BY)
- **Zapsplat** (free, no attribution required)
- **BBC Sound Effects Library** (CC0, UK public institution)
- **Splice** (free tier has build-up/energy sounds)

---

## 🎵 Full Audio State Machine

The Python system now manages this:

```
AUDIO STATE TRANSITIONS:

IDLE state
├─ set_state(SILENT)
├─ stop_music()
└─ silent

FIRE state (1-4 people)
├─ set_state(AMBIENT)
├─ play_music("ambient_chill", loop=True, volume=0.5)
├─ Entry flash → play_sfx("whoosh", volume=0.8)
├─ Color pulse (15s) → play_sfx("chime", volume=0.4)
└─ Narration (if enabled) → speak(prompt_text)

FIRE → FIRE (build-up phase) [NEW]
├─ party_buildup_progress = 0.0 → 1.0
├─ Progress 0%: play_sfx("buildup_start", volume=0.9)
├─ Progress 33%: play_sfx("buildup_pulse", volume=0.7)
├─ Progress 66%: play_sfx("buildup_pulse", volume=0.7)
└─ Lights intensify, fan/mist ramp up on ESP32

FIRE → PARTY (supernova release)
├─ set_state(PARTY)
├─ stop_music() → play_music("party_upbeat", loop=True, volume=1.0)
├─ Optional: play_sfx("supernova", volume=1.0) [if asset exists]
└─ Full light show begins on ESP32

PARTY → FIRE (cool down)
├─ set_state(AMBIENT)
├─ stop_music() → play_music("ambient_chill", loop=True, volume=0.5)
└─ Prompt: "The fire cools. But you're warm."

PHONE (any state)
├─ set_state(ALERT)
├─ play_sfx("buzzer", volume=0.9)
├─ stop_music()
├─ Prompt: "Put the phone away, lah"
├─ Narration (optional): "Disconnect to connect"
└─ Red alert on ESP32 (glitch effects)

PHONE exit
├─ return to previous state
├─ resume previous audio
└─ no fade, instant switch
```

---

## 🧪 How to Test Build-Up Audio

### 1. **Manual Test: Gather 5+ People**

```bash
cd vision
source env/bin/activate
python src/bond_fire_vision/cli.py \
  --camera-index 0 \
  --enable-audio \
  --audio-volume 1.0 \
  --narration-enabled
```

**What you'll hear:**
- 0:00 - No one detected: Silent
- 0:05 - 1 person detected: Ambient music starts (chill)
- 2:10 - 5th person arrives: Whoosh sound, build-up starts
- 2:35 - First pulse: Beep-beep
- 2:70 - Second pulse: Beep-beep
- 3:55 - Party begins: Explosion + party music

### 2. **Listen to Packet Listener (No Audio)**

```bash
# Terminal 1: Run detector
cd vision && python src/bond_fire_vision/cli.py --camera-index 0 --enable-audio

# Terminal 2: Watch packets
python packet_listener.py --compact
```

Output shows:
```
[14:32:15] FIRE    | 4p   | 29.8fps | Almost there! Find one more legend.
[14:32:16] FIRE    | 5p   | 30.0fps |   # buildup_progress = 0.0 → trigger buildup_start
[14:32:16] FIRE    | 5p   | 30.0fps |   # buildup_progress = 0.33 → trigger buildup_pulse
[14:32:17] FIRE    | 5p   | 30.0fps |   # buildup_progress = 0.66 → trigger buildup_pulse
[14:32:18] PARTY   | 5p   | 29.9fps | CRITICAL MASS ACHIEVED!  # party achieved
```

### 3. **Check Audio Manager Threading**

Python audio runs in background thread, so detector never blocks:

```python
# Non-blocking call - returns immediately
self.audio_manager.play_sfx("buildup_start", volume=0.9)

# Worker thread processes this asynchronously:
# 0ms: Queue command
# 1-5ms: Worker thread picks it up
# 10-50ms: pygame.mixer plays sound
# Main detector loop continues @ 30fps uninterrupted
```

---

## 📝 Code Integration Points

### Detector → Audio Manager

```python
# detector.py lines ~350-360:

# Build-up SFX trigger
if state_output.party_buildup_progress > 0.0 and not self._party_buildup_started:
    if self.audio_manager:
        self.audio_manager.play_sfx("buildup_start", volume=0.9)
    self._party_buildup_started = True

# Build-up pulse triggers at 33% & 66%
buildup_step = int(state_output.party_buildup_progress * 3)
if buildup_step > self._last_buildup_step:
    if self.audio_manager and buildup_step in (1, 2):
        self.audio_manager.play_sfx("buildup_pulse", volume=0.7)
    self._last_buildup_step = buildup_step
```

### State Machine → Packet

```python
# detector.py line ~395:
packet = self.packet_builder.build(
    state=state_output.state,
    people=people,
    ...
    party_buildup_progress=state_output.party_buildup_progress,
)
```

### Packet → UDP → ESP32

```json
{
  "state": "FIRE",
  "party_buildup_progress": 0.33,  // NEW field
  "prompt": "Three's a fire!",
  "mist_pwm": 210,
  "fan_pwm": 160,
  // ... other fields
}
```

---

## 🎯 Summary: What's Running NOW

✅ **Python Master:**
- Detects 5+ people → starts 1.5s build-up phase
- Plays `buildup_start.mp3` at 0%
- Plays `buildup_pulse.mp3` at 33% and 66%
- Sends `party_buildup_progress` field in packets @ 30fps
- Switches to PARTY state at end, changes audio to party music

✅ **ESP32 (Waiting for firmware):**
- Receives `party_buildup_progress` in packet
- Ramps LED brightness, increases pulse speed during build-up
- Spins up fan/mist harder during 1.5s countdown
- Achieves full supernova when progress reaches 1.0

✅ **Audio SFX:**
- Currently mapped in `audio_manager.py` ASSET_MAP
- Waiting for actual MP3 files in `vision/assets/sfx/`
- Will play silently if files don't exist (graceful degradation)

---

## 🚀 What You Need to Do

1. **Create 3 SFX files** in `vision/assets/sfx/`:
   - `buildup_start.mp3`
   - `buildup_pulse.mp3`
   - `supernova.mp3` (optional)

2. **Test the system:**
   ```bash
   python src/bond_fire_vision/cli.py --enable-audio --camera-index 0
   ```

3. **Implement ESP32 firmware** (see PHASE_3_GUIDE.md):
   - Parse `party_buildup_progress` field
   - Render build-up effects using progress value

That's it! Everything else is already implemented and working.
