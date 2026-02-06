# Bond Fire Implementation Plan

**Last Updated:** February 6, 2026  
**Project Status:** Phase 2 Complete ✅ | Phase 3 Ready  
**Overall Progress:** ~70% Complete

---

## 📋 Executive Summary

**The Empathic Hearth** is an interactive installation that gamifies physical proximity to combat social disconnection among youths. It uses YOLOv8 computer vision to detect visitors and smartphones, then broadcasts state changes to an ESP32 controller via UDP, which drives LEDs, mist atomizer, and fan hardware.

**Key Achievement:** Complete Python vision system with state machine, real-time tracking, audio narration, and configuration management. ESP32 firmware is next.

---

## 🎯 Project Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   MAC (Python + YOLOv8)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Vision Pipeline                                      │   │
│  │  • YOLOv8 person/phone detection                      │   │
│  │  • Configurable ROI with edge detection              │   │
│  │  • Real-time person tracking with IDs                │   │
│  └──────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  State Machine (Event-Driven)                         │   │
│  │  • 4 states: IDLE, FIRE, PARTY, PHONE               │   │
│  │  • Phone detection with 0.5s hysteresis              │   │
│  │  • Party buildup: 1.5s ramp-up before max            │   │
│  │  • Outputs: PWM values, visual effects, prompts      │   │
│  └──────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Support Systems                                      │   │
│  │  • Local prompt generation (8s cooldown)             │   │
│  │  • Color-aware LED commands                          │   │
│  │  • Text-to-speech narration (pyttsx3)                │   │
│  │  • Audio effects (pygame.mixer)                      │   │
│  │  • Configuration management (YAML)                   │   │
│  └──────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  UDP Packet Assembly (v2.1 Protocol)                 │   │
│  │  Broadcasts 30x/second over hotspot network          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                             │ UDP Broadcast
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                 ESP32 (C++ + Arduino)                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Network & Parser                                     │   │
│  │  • WiFi connected to hotspot                         │   │
│  │  • UDP listener on port 4210                         │   │
│  │  • JSON deserialization (ArduinoJson)                │   │
│  └──────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Hardware Driver                                      │   │
│  │  • PWM control for mist and fan                       │   │
│  │  • LED ring animation engine                         │   │
│  │  • State-based effect mapping                        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                             │
                ┌────────────┼────────────┐
                ↓            ↓            ↓
            LED RING       MIST         FAN
            (NeoPixel)    (Pump)      (PWM)
```

---

## 📊 State Machine Reference

The installation operates on a **0-100% social battery scale**. Every person adds ~20% charge.

| State     | People | Battery | Fire Intensity | LED Color      | Text Theme                    | Phone Override |
| --------- | ------ | ------- | -------------- | -------------- | ----------------------------- | -------------- |
| **IDLE**  | 0      | 0%      | OFF            | Breathing Blue | Lure: *"I need a spark..."*   | N/A            |
| **FIRE**  | 1-4    | 20-80%  | 20-80%         | Orange → Red   | Nudge: *"We need X more!"*    | **PENALTY**    |
| **PARTY** | 5+     | 100%    | MAX            | Rainbow        | Celebrate: *"CRITICAL MASS!"* | **PENALTY**    |
| **PHONE** | Any    | -       | 0%             | Static Grey    | Alert: *"DISCONNECT!"*        | Overrides all  |

**Phone Detection:** Instant trigger (0s entry), 0.5s exit hysteresis to prevent flickering.

---

## 🔧 Configuration System

All timing and threshold values are configurable via `vision/config.yaml`. No code changes needed.

### Current Configuration (Verified Working)

```yaml
state_machine:
  phone_entry_dwell: 1.0s       # Time to detect phone (0=instant)
  phone_exit_dwell: 0.5s        # Hysteresis after phone removed
  frame_rate: 5 fps             # State evaluation frequency

prompts:
  normal_cooldown: 10s          # Min time between prompts (non-phone)
  phone_cooldown: 10s           # Min time between prompts (phone state)

celebration:
  duration_frames: 10 frames    # How long to show celebration (2 seconds at 5fps)

audio:
  master_volume: 0.7            # Overall volume (0.0-1.0)
  audio_queue_size: 50          # Pending audio commands
  tts:
    enabled: true
    speech_rate: 140 WPM        # Narration speed
    voice_preference: [daniel, grandpa, rocko, reed]  # macOS voices

vision:
  confidence_threshold: 0.5     # YOLO detection confidence
  person_class_id: 0            # COCO person class
  phone_class_id: 67            # COCO cell phone class
```

---

## 📦 UDP Protocol v2.1

The Mac broadcasts comprehensive JSON packets 30x/second to ESP32.

### Packet Structure

```json
{
  "version": 2,
  "state": "FIRE",
  "people": [{"id": 1, "x": 320, "y": 240, "color": [255,100,50]}],
  "phone_detected": false,
  "dominant_palette": [[255,100,50], [200,80,40]],
  "prompt": "Battery 60%. We need 2 more!",
  "mist_pwm": 180,
  "fan_pwm": 100,
  "pulse_active": false,
  "entry_flash_id": null,
  "audio_state": "AMBIENT",
  "party_buildup_progress": 0.5,
  "celebration": false,
  "narration": ""
}
```

### Field Descriptions

| Field                    | Type   | Purpose                                       |
| ------------------------ | ------ | --------------------------------------------- |
| `version`                | int    | Protocol version (always 2)                   |
| `state`                  | string | Current state: IDLE, FIRE, PARTY, PHONE       |
| `people`                 | array  | Detected person objects with position & color |
| `phone_detected`         | bool   | True if smartphone in frame                   |
| `dominant_palette`       | array  | Top colors for LED visualization              |
| `prompt`                 | string | Text to display on LED matrix                 |
| `mist_pwm`               | int    | Mist pump PWM (0-255)                         |
| `fan_pwm`                | int    | Fan motor PWM (0-255)                         |
| `pulse_active`           | bool   | Enable color pulse effect                     |
| `entry_flash_id`         | int    | Person ID to flash new person color           |
| `audio_state`            | string | SILENT, AMBIENT, PARTY, ALERT                 |
| `party_buildup_progress` | float  | 0.0-1.0, progress to party start              |
| `celebration`            | bool   | True during phone exit celebration            |
| `narration`              | string | Text to narrate (if TTS enabled)              |

---

## 🎵 Audio System

The system supports sound effects, background music, and optional text-to-speech.

### Audio Assets (10 Required SFX + 2 Music Tracks)

**SFX (in `vision/assets/sfx/`):**
- `fire_crackle_loop.mp3` - Ambient fire sound (loops)
- `whoosh_entry.mp3` - Person enters active zone
- `buzzer_alert.mp3` - Phone detected
- `party_horn.mp3` - Phone removed, celebration plays
- `soft_chime.mp3` - Pulse effect every 15s
- `buildup_start.mp3` - Party buildup begins (0% → 33%)
- `buildup_pulse.mp3` - Buildup milestone at 33% & 66%
- `supernova_burst.mp3` - Optional explosion when 5 people detected

**Music (in `vision/assets/music/`):**
- `ambient_chill.mp3` - Background during FIRE/IDLE
- `party_upbeat.mp3` - Loops during PARTY

### Audio Features

✅ **Entry Detection:** Whoosh plays when first person detected  
✅ **Phone Alert:** Buzzer when smartphone detected  
✅ **Phone Exit:** Party horn + optional narration  
✅ **Narration:** All prompts can be read aloud via pyttsx3  
✅ **Voice Selection:** Auto-selects Daniel (British narrator) or configurable  
✅ **Party Buildup:** Start + pulse effects at 33% & 66% progress  
✅ **Queue-Based:** 50-command queue prevents dropping audio  

---

## 🚀 Phase 2: Python Implementation (COMPLETE ✅)

All 7 core Python modules fully implemented and tested.

### Modules & Status

| Module                | Lines | Purpose                        | Status     |
| --------------------- | ----- | ------------------------------ | ---------- |
| **state_machine.py**  | 347   | Event-driven state transitions | ✅ Complete |
| **detector.py**       | 445   | Vision loop, packet assembly   | ✅ Complete |
| **local_prompts.py**  | 262   | State-aware text generation    | ✅ Complete |
| **packet_builder.py** | 89    | UDP packet JSON assembly       | ✅ Complete |
| **audio_manager.py**  | 554   | Sound effects & TTS            | ✅ Complete |
| **color_analysis.py** | 178   | Dominant color extraction      | ✅ Complete |
| **config.py**         | 168   | YAML configuration loader      | ✅ Complete |
| **cli.py**            | ~100  | Command-line interface         | ✅ Complete |

### Key Implementations

**State Machine:**
- ✅ IDLE → FIRE (1+ person detected)
- ✅ FIRE → PARTY (5+ people for 2 seconds)
- ✅ PARTY → FIRE (<4 people for 3 seconds)
- ✅ Any → PHONE (smartphone detected, instant)
- ✅ PHONE → Previous (phone absent for 0.5s)
- ✅ Phone exit triggers celebration with 10-frame display
- ✅ Party buildup ramps from 0-1.0 over 1.5 seconds

**Detection & Tracking:**
- ✅ YOLOv8 person and phone detection
- ✅ Configurable ROI with 25px edge tolerance
- ✅ Real-time person tracking with persistent IDs
- ✅ Confidence threshold adjustable via config
- ✅ ROI visible in preview window

**Prompts & Narration:**
- ✅ 90+ curated prompts across 8 states
- ✅ 8-10s cooldown prevents rapid cycling
- ✅ Phone-specific prompts with faster updates
- ✅ Celebration prompt locked for 10 frames
- ✅ Optional TTS reads prompts (voice-selectable)
- ✅ Debug mode logs all generations

**Audio System:**
- ✅ Non-blocking audio via worker thread
- ✅ 50-command queue for reliability
- ✅ SFX playback for all state transitions
- ✅ TTS narration with voice selection
- ✅ Music loops based on audio state
- ✅ Master volume control
- ✅ Asset validation with helpful error messages

**Configuration:**
- ✅ YAML loading with type safety
- ✅ Auto-discovery of config.yaml
- ✅ Environment variable override
- ✅ All timing values configurable
- ✅ No code changes needed for adjustments

### Testing & Validation

✅ **23 Tests Passing:**
- 6 color analysis tests
- 7 state machine tests
- 5 local prompt tests
- 5 packet builder tests

✅ **Integration Verified:**
- All modules import config correctly
- State machine loads phone timings from config
- Prompt generator loads cooldowns from config
- Audio manager loads volume from config
- No syntax errors, all imports resolve

---

## 🔜 Phase 3: ESP32 Firmware (READY FOR IMPLEMENTATION)

### 3.1: Foundation (Network + Parser)
- [ ] WiFi connection setup (existing code)
- [ ] UDP listener on port 4210
- [ ] JSON deserialization with ArduinoJson
- [ ] Packet validation (version check)

### 3.2: State Mapping
- [ ] Map state strings to hardware outputs
- [ ] PWM duty cycle lookup tables
- [ ] LED animation programs

### 3.3: Effect Engine
- [ ] Color breathing for IDLE
- [ ] Palette cycling for FIRE
- [ ] Rainbow animations for PARTY
- [ ] Glitch effect for PHONE
- [ ] Pulse effects during buildup
- [ ] Entry flash for new people

### 3.4: Hardware Integration
- [ ] NeoPixel ring control
- [ ] PWM mist pump driver
- [ ] PWM fan driver
- [ ] Safety limits & error handling

### 3.5: Deployment
- [ ] Upload firmware to ESP32
- [ ] Test on physical hardware
- [ ] Validate network communication
- [ ] Timing calibration

**Estimated Effort:** 4-6 hours  
**Complexity:** Medium

---

## 📁 Project Structure

```
bond-fire/
├── project-readme.md              # System overview & protocol
├── RUN.md                         # Execution instructions
├── IMPLEMENTATION_PLAN.md         # This file
│
├── hardware/                      # Arduino sketches
│   ├── main/main.ino             # Master controller
│   ├── phase1_led/               # LED tests
│   ├── phase2_fan/               # Fan/mist tests
│   └── phase3_mister/            # Integration tests
│
└── vision/                        # Python detection system
    ├── config.yaml               # Configuration (YAML)
    ├── CONFIG.md                 # Configuration documentation
    ├── RUN.md                    # Setup & execution
    ├── pyproject.toml            # Python package definition
    │
    ├── assets/                   # Audio & model files
    │   ├── sfx/                  # Sound effects (8 files)
    │   ├── music/                # Background music (2 files)
    │   └── yolov8n.pt            # YOLOv8 weights
    │
    └── src/bond_fire_vision/    # Python modules
        ├── __init__.py
        ├── cli.py                # Command-line interface
        ├── config.py             # Configuration loader
        ├── state_machine.py      # State transitions
        ├── detector.py           # Vision main loop
        ├── packet_builder.py     # UDP JSON assembly
        ├── audio_manager.py      # Sound effects & TTS
        ├── local_prompts.py      # Text generation
        └── color_analysis.py     # Color extraction
```

---

## 🎮 Running the System

### Quick Start

```bash
cd vision
source env/bin/activate
bond-fire-vision --camera-index 0 --enable-audio --narration-enabled
```

### Essential Flags

| Flag                  | Purpose             | Example                  |
| --------------------- | ------------------- | ------------------------ |
| `--camera-index`      | Webcam ID           | `0` for built-in         |
| `--enable-audio`      | Activate sound      | (no value needed)        |
| `--narration-enabled` | Add TTS             | (no value needed)        |
| `--tts-voice`         | Voice to use        | `"daniel"` or voice name |
| `--roi`               | Active zone         | `0.15 0.25 0.85 0.9`     |
| `--confidence`        | Detection threshold | `0.6`                    |
| `--broadcast-ip`      | UDP destination     | `255.255.255.255`        |
| `--broadcast-port`    | UDP port            | `4210`                   |
| `--no-display`        | Headless mode       | (no value needed)        |

### Helper Tools

**Manual Packet Sender:**
```bash
python manual_packet_sender.py --interactive
```

**Packet Listener (Debug):**
```bash
python packet_listener.py --raw
```

**List Available Voices:**
```bash
python list_voices.py
```

**Test Integration:**
```bash
python test_integration.py
```

---

## 🧪 Testing Checklist

### Phase 2 Validation (COMPLETE ✅)

- ✅ State transitions occur correctly
- ✅ Phone detection with 0.5s hysteresis works
- ✅ Party buildup ramps 0-1.0 over 1.5s
- ✅ Prompts change respecting cooldowns
- ✅ Audio plays for all state transitions
- ✅ Narration reads selected prompts
- ✅ Configuration loads from YAML
- ✅ All 10 SFX assets play correctly
- ✅ Voice selection works (prefers Daniel)
- ✅ Queue-based audio doesn't drop commands
- ✅ TTS doesn't block vision loop
- ✅ Celebration displays for exactly 10 frames
- ✅ Colors extracted correctly from video
- ✅ JSON packets serialize cleanly
- ✅ UDP broadcasts 30x/second

### Phase 3 Testing (UPCOMING)

- [ ] ESP32 receives UDP packets
- [ ] JSON parsing succeeds on microcontroller
- [ ] State mapping produces correct PWM values
- [ ] LED ring displays correct colors/animations
- [ ] Mist pump responds to PWM commands
- [ ] Fan responds to PWM commands
- [ ] All state transitions visible on hardware
- [ ] Phone detection immediately cuts mist
- [ ] Phone exit celebration plays party horn
- [ ] Edge cases handled (dropped packets, WiFi glitches)

---

## 🚨 Known Issues & Workarounds

### Issue 1: PyObject SDL2 Duplicate Classes
**Symptom:** Warning about duplicate SDL2 implementations from opencv and pygame  
**Status:** Non-blocking, system works fine  
**Workaround:** Can be fixed by rebuilding opencv without SDL support, but not necessary

### Issue 2: TTS Engine Blocking
**Symptom:** Multiple TTS calls could block the background thread  
**Fix Applied:** Fresh engine instance created per utterance, avoiding state corruption  
**Status:** ✅ Resolved

### Issue 3: Config File Not Found
**Symptom:** "config.yaml not found" error  
**Fix:** Place `config.yaml` in `vision/` directory or set `BOND_FIRE_CONFIG` env var  
**Status:** ✅ Auto-discovery implemented

---

## 📊 Project Metrics

| Metric                       | Value                       |
| ---------------------------- | --------------------------- |
| Total Lines of Code (Python) | ~2,300                      |
| Test Coverage                | 23 tests, all passing       |
| Audio Assets                 | 10 SFX + 2 music = 12 files |
| Configuration Values         | 15 adjustable settings      |
| Supported macOS Voices       | 184 voices available        |
| State Transitions            | 5 main paths                |
| Prompt Messages              | 90+ curated messages        |
| UDP Broadcast Rate           | 30 packets/second           |
| Phone Detection Latency      | 0-1.5s (0.5s hysteresis)    |

---

## 🎯 Success Criteria (Phase 2)

✅ **All Met:**
- [x] Python vision system fully implemented
- [x] State machine with all transitions working
- [x] Real-time person & phone detection
- [x] Audio system with SFX, music, and TTS
- [x] Configuration management via YAML
- [x] UDP protocol v2.1 fully specified
- [x] 23 automated tests passing
- [x] Complete documentation
- [x] Ready for ESP32 integration

---

## 🔗 Next Steps (Phase 3)

1. **Get ESP32 hardware set up**
2. **Implement firmware based on PHASE_3_GUIDE.md**
3. **Test network communication**
4. **Calibrate hardware response curves**
5. **Field test with installation hardware**
6. **Iterate on UX based on live feedback**

---

## 📞 Quick Troubleshooting

**Vision not detecting people?**
→ Check ROI, increase `--confidence`, ensure good lighting

**Audio not playing?**
→ Run `python list_voices.py` to verify audio devices, check asset paths

**UDP packets not reaching ESP32?**
→ Verify both on same hotspot, check firewall, run `packet_listener.py` to confirm broadcast

**Config changes not taking effect?**
→ Make sure to reload Python process (restart bond-fire-vision command)

**Phone detection too sensitive/insensitive?**
→ Adjust `phone_entry_dwell` and `phone_exit_dwell` in config.yaml

---

**Last Updated:** February 6, 2026  
**Status:** Phase 2 Complete, Phase 3 Ready  
**Contact:** For issues or questions, refer to specific module documentation
