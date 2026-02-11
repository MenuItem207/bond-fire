# The Empathic Hearth

**A Socially Responsive Digital Campfire**

> **"Fire grows when we gather. Fire dies when we disconnect."**

## 📖 Project Overview

**The Empathic Hearth** is an interactive installation designed for SCAPE Singapore to combat "social islands" among youths. It uses Computer Vision and a responsive "mist flame" to gamify physical proximity and encourage deeper social connection.

The installation acts as a **Social Battery Charger**—visualizing group size through animated fire that grows progressively stronger as more people join. The system requires a critical mass of **5 people** for 2 seconds to unlock a "Supernova" celebration. Smartphones are treated as a tool: fanning with a phone boosts the fire instead of penalizing it.

**Current Status:** Phase 2 Complete ✅ (Python vision system fully implemented) | Phase 3 Ready (ESP32 firmware)

---

## 🎯 System Architecture

The system operates as a **Master-Slave Model** over WiFi:

```
MacBook (Master)          Phone Hotspot          ESP32 (Slave)
├─ YOLOv8 Vision         ├─ WiFi Bridge         ├─ JSON Parser
├─ State Machine         │                      ├─ Effect Engine
├─ Audio System    ────→ hotspot ─────→ UDP   ├─ LED Control
└─ Packet Builder        (port 4210)            └─ PWM Drivers
                                                   ├─ Mist Pump
                                                   ├─ Fan Motor
                                                   └─ LED Ring
```

**Communication:** One-way UDP broadcast, 30 packets/second, JSON protocol v2.1.

---

## 🧠 State Machine: The Core Logic

The installation operates on a **0-100% social battery scale**. Every person adds ~20% charge.

### State Transitions

```
        ┌─ IDLE (0 people) ─────────────────┐
        │  Battery: 0%                       │
        │  "I need a spark..."               │
        │  Mist: OFF, LEDs: Blue             │
        │                                    │
        └──→ FIRE (1-4 people) ────────┐    │
            Battery: 20-80%             │    │
            "Battery X%. Need Y more!"  │    │
            Mist: Variable, LEDs: Warm  │    │
                                        │    │
                ↓ (5+ people for 2s)    │    │
                │                       │    │
                ├─→ PARTY ◄─────────────┘    │
                │   Battery: 100%            │
                │   "CRITICAL MASS!"         │
                │   Mist: MAX, LEDs: Rainbow │
                │   + Supernova Celebration  │
                │                            │
                └─ (4- people for 3s) ──────┘

        ANY STATE ──→ PHONE_IDLE (phone detected, no fanning)
        Phone prompt delay: 2.0s before phone-idle prompt
        Mist/Fan: Low simmer (scaled by wind)
        └─ Fanning → FANNING (wind > threshold)
        └─ Phone removed for 0.5s → Previous State + Celebration
```

### State Details

| State          | People | Battery | Mist | Fan  | LEDs           | Text Theme |
| -------------- | ------ | ------- | ---- | ---- | -------------- | ---------- |
| **IDLE**       | 0      | 0%      | OFF  | Low  | Breathing Blue | Lure       |
| **FIRE**       | 1-4    | 20-80%  | Ramp | Ramp | Orange → Red   | Nudge      |
| **PARTY**      | 5+     | 100%    | MAX  | MAX  | Rainbow        | Celebrate  |
| **PHONE_IDLE** | Any    | -       | Low  | Low  | Warm ember     | Prompt     |
| **FANNING**    | Any    | -       | Ramp | Ramp | Bright ember   | Encourage  |

---

## 📦 UDP Protocol v2.1

The Mac broadcasts comprehensive JSON packets containing state, tracking data, visual effects, and audio cues.

### Full Packet Structure

```json
{
  "version": 2,
  "state": "FIRE",
  "people": [
    {"id": 1, "x": 320, "y": 240, "color": [255, 100, 50]},
    {"id": 2, "x": 400, "y": 200, "color": [200, 80, 40]}
  ],
  "phone_detected": false,
  "dominant_palette": [[255, 100, 50], [200, 80, 40]],
  "prompt": "Battery 60%. We need 2 more!",
  "mist_pwm": 180,
  "fan_pwm": 100,
  "wind": 35,
  "pulse_active": false,
  "entry_flash_id": 1,
  "audio_state": "AMBIENT",
  "party_buildup_progress": 0.0,
  "celebration": false,
  "narration": ""
}
```

### Protocol Evolution

- **v1.0** (Legacy): Simple 3-field format `{c, p, t}`
- **v2.1** (Current): Full state machine + effects + audio ✅

---

## 🔌 Hardware Configuration

**Compute:**
- MacBook Pro running Python 3.13 + YOLOv8n + Real-time vision

**Networking:**
- Phone hotspot bridges Mac and ESP32
- WiFi direct to both devices
- UDP broadcast on port 4210

**Controller:**
- ESP32 Dev Module (30 LEDS, WiFi, 16 GPIO pins)
- ArduinoJson for packet parsing

**Power:**
- 5V 10A Switching Power Supply
- Separate circuits for logic, actuators, LEDs

**Actuators:**
- **Mist:** 5V USB Ultrasonic Atomizer (MOSFET-controlled)
- **Fan:** 60mm 5V Waterproof Fan (PWM-controlled)
- **LED Ring:** WS2812B addressable (24-35 LEDs)
- **LED Matrix:** WS2812B flexible strip (8x32 optional)

---

## 🎵 Audio System

Integrated audio feedback across detection, state changes, and narration.

### Components

- **SFX:** 8 sound effects via pygame.mixer
- **Music:** Looping ambient/party tracks
- **Narration:** Text-to-speech via pyttsx3 (optional)
- **Queue:** 50-command background queue prevents audio drops
- **Worker Thread:** Non-blocking playback

### Audio Events

✅ **Entry Whoosh** - Person detected  
✅ **Party Horn** - Phone removed (celebration)  
✅ **Pulse Chime** - Every 15s in FIRE state  
✅ **Buildup SFX** - Start + 33%/66% milestones  
✅ **Narration** - All prompts (optional, voice-selectable)  

---

## ⚙️ Configuration Management

All timings and thresholds are adjustable via `vision/config.yaml` without code changes.

### Current Configuration

```yaml
state_machine:
  phone_entry_dwell: 1.0s    # Detect phone
  phone_exit_dwell: 0.5s     # Hysteresis
  frame_rate: 5 fps          # State eval frequency

prompts:
  normal_cooldown: 10s       # Min time between prompts
  phone_cooldown: 10s        # While phone detected
  phone_idle_prompt_delay: 2s # Delay before phone-idle prompt

celebration:
  duration_frames: 10 frames # 2 seconds at 5fps

audio:
  master_volume: 0.7
  audio_queue_size: 50
  tts:
    enabled: true
    speech_rate: 140 WPM
    voice_preference: [daniel, grandpa, rocko, reed]

vision:
  confidence_threshold: 0.5
  person_class_id: 0         # COCO dataset
  phone_class_id: 67         # COCO dataset
fanning:
  power_threshold: 50.0
  power_hysteresis: 5.0
```

See [vision/CONFIG.md](vision/CONFIG.md) for detailed documentation.