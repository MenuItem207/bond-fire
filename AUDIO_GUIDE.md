# Bondfire Audio System Guide

## Overview
The audio system responds to installation state, user presence, and activities. It uses **10 audio assets** organized into background music, sound effects, and dynamic triggers.

---

## Audio Assets & Usage

### 🔥 Background Audio (State-Based)

#### **fire_crackle_loop.wav** (2.5 MB)
**Trigger:** AMBIENT state (0-1 user in space)  
**Volume:** Dynamic 0.2-0.7 (scales with fire intensity)  
**Loop:** Yes (continuous)  
**Purpose:** Atmospheric background during low activity
- **0 people:** 20% volume (faint crackling)
- **1 person:** 35% volume (medium presence)
- **2-3 people:** 45% volume (building energy)
- **4+ people:** 70% volume (full fire sound)

**Technical Detail:**
```python
volume = 0.2 + (fire_intensity * 0.5)  # Maps 0.0-1.0 → 0.2-0.7
```

---

#### **party_upbeat.wav** (15 MB)
**Trigger:** PARTY state (4+ users in space)  
**Volume:** 80% (0.8)  
**Loop:** Yes (continuous)  
**Purpose:** Celebration soundtrack during party mode
- Accompanies rainbow LED effects and party_horn
- Continuous upbeat music creates energetic atmosphere
- Pairs with buildup_start and buildup_pulse during state transitions

---

### 🎺 Event Sound Effects

#### **party_horn.wav**
**Trigger:** Two events
1. **PARTY state entry** (when people count hits threshold for party mode) - Volume: 100% (1.0)
2. **Phone exit celebration** (when phone is removed) - Volume: 80% (0.8)

**Purpose:** Celebratory blast
- Sharp, attention-grabbing sound
- Signals mode transitions (especially entering PARTY)
- Also signals accomplishment when device is removed

---

#### **whoosh_entry.wav**
**Trigger:** Person enters and entry flash activates  
**Volume:** 80% (0.8)  
**Loop:** No (one-shot)  
**Purpose:** Welcoming transition sound
- Plays when a new person is detected and color flash occurs
- Accompanies text prompt about the person's shirt color
- Creates sense of recognition/welcome

---

#### **soft_chime.wav**
**Trigger:** Color pulse effect (every 15 seconds in FIRE state)  
**Volume:** 40% (0.4)  
**Loop:** No (one-shot)  
**Purpose:** Subtle audio cue for visual pulse
- Gentle notification that doesn't interrupt
- Pairs with visual LED pulse on ring
- Low volume keeps it atmospheric

---

### 🎶 Build-Up Audio (Party Anticipation)

#### **buildup_start.wav**
**Trigger:** Party build-up begins (people count approaching party threshold)  
**Volume:** 90% (0.9)  
**Loop:** No (one-shot)  
**Purpose:** Signals build-up phase starting
- Low tone that indicates something is coming
- Plays once when build-up_progress transitions from 0.0 → > 0.0
- Sets anticipatory mood

**When It Plays:**
```
people_count increases → state machine detects party conditions
→ party_buildup_progress becomes > 0.0
→ buildup_start plays
```

---

#### **buildup_pulse.wav**
**Trigger:** During party build-up at 33% and 66% progress  
**Volume:** 70% (0.7)  
**Loop:** No (one-shot)  
**Purpose:** Rhythmic progression indicators
- Plays twice during build-up (at 1/3 and 2/3 completion)
- Pulsing tone creates sense of escalation
- Accompanies visual LED intensification

**When It Plays:**
```
build-up progress 0→33%: buildup_pulse #1 plays
build-up progress 33%→66%: buildup_pulse #2 plays
build-up progress 66%→100%: (no pulse, transitions to PARTY state)
```

---

#### **supernova_burst.wav** (Not Currently Used)
**Trigger:** None currently  
**Purpose:** Reserved for supernova/supernova effect
- Could be triggered on party state transition
- Currently available but not actively triggered
- Available for future explosion/climax moment

---

### ⚠️ Alert Audio

#### **buzzer_alert.wav**
**Trigger:** ALERT state (phone detected)  
**Volume:** 80% (0.8)  
**Loop:** No (one-shot per state change)  
**Purpose:** Warning/penalty indicator
- Sharp alert that something is wrong
- Indicates phone/device detected in space
- Demands attention

---

## State Transitions & Audio Timeline

### Scenario: 0 → 1 Person Enters (Fire Crackle Responsive)

```
[0 people - IDLE]
  ↓ (person enters)
[Fire crackle starts at 20% volume]
  ↓ (detection confirms)
[Whoosh entry sound plays at 80%]
[Text scrolls with entry prompt]
  ↓ (text settles)
[Fire crackle continues, dynamically adjusts with movement]
```

**Audio Timeline:**
- **T=0ms**: Person detected → fire_crackle @ 20%
- **T=100ms**: Entry confirmed → whoosh @ 80% + text
- **T+200ms**: Fire crackle volume adjusts based on fire_intensity
- **T+15s**: Color pulse → chime @ 40%

---

### Scenario: Approaching Party (Build-Up Sequence)

```
[3 people in FIRE state]
  ↓ (4th person enters)
[Build-up begins]
[Party music SILENT, but build-up_start plays @ 90%]
  ↓ (33% progress)
[buildup_pulse #1 @ 70%]
  ↓ (66% progress)
[buildup_pulse #2 @ 70%]
  ↓ (100% → PARTY)
[State change: party_music 80% + party_horn 100%]
```

**Key Point:** Build-up sequence doesn't play music yet—it's all SFX creating anticipation.

---

### Scenario: Phone Detected (ALERT State)

```
[FIRE or PARTY state with people]
  ↓ (phone detected in frame)
[buzzer_alert @ 80%]
[State changes to PHONE, music stops]
[Red glitch effect on ring]
```

---

### Scenario: Phone Removed (Celebration)

```
[PHONE state active]
  ↓ (phone exits)
[Celebration triggered]
[party_horn @ 80% plays]
[Celebration prompt shows for 2 seconds]
  ↓ (after celebration)
[State returns to FIRE or AMBIENT]
[Fire crackle resumes]
```

---

## Volume Control

### Master Volume
Set on AudioManager initialization:
```python
audio_manager = AudioManager(master_volume=0.7)  # 70% overall
```

### Per-Asset Override
Each `play_sfx()` or `play_music()` call can override volume:
```python
play_sfx("whoosh", volume=0.8)  # 80% regardless of master
play_music("party_music", volume=0.8)
```

---

## Dynamic Audio Features

### Fire Crackle Volume Scaling

The fire crackle volume responds to **how many people are in the space**:

```
Fire Intensity (from Python state machine):
  0 people    → intensity = 0.0 → volume = 0.2 (20%)
  1 person    → intensity = 0.25 → volume = 0.325 (32.5%)
  2 people    → intensity = 0.5 → volume = 0.45 (45%)
  3 people    → intensity = 0.75 → volume = 0.575 (57.5%)
  4+ people   → intensity = 1.0 → volume = 0.7 (70%)
```

**Implementation:**
```python
def set_fire_intensity(self, intensity: float):
    intensity = max(0.0, min(1.0, intensity))
    if self._current_state == AudioState.AMBIENT:
        volume = 0.2 + (intensity * 0.5)
        play_sfx("fire_crackle", volume=volume)
```

### Text-to-Speech Narration (Optional)

When enabled, the system speaks text prompts:
- Entry prompts: "Welcome, [color] shirt!"
- Pulse prompts: "Beautiful mix of [colors]!"
- Normal prompts: State-based commentary

---

## State Machine Audio Map

| State                            | Audio Behavior                                              |
| -------------------------------- | ----------------------------------------------------------- |
| **IDLE**                         | Silent (no users detected)                                  |
| **FIRE** (1-3 people)            | Fire crackle (responsive to intensity) + chimes (every 15s) |
| **PARTY** (4+ people)            | Party music 80% + party_horn 100% on entry                  |
| **PHONE** (device detected)      | Buzzer 80% + alarm sound                                    |
| **Build-Up** (approaching party) | buildup_start + buildup_pulse sequence                      |

---

## Audio Design Philosophy

✅ **Responsive:** Fire crackle volume changes with people count in real-time  
✅ **Informative:** Different SFX for different events (entry, pulse, celebration)  
✅ **Atmospheric:** Background audio creates immersive environment  
✅ **Non-Intrusive:** Most SFX are short (0.5-2s), music drives ambiance  
✅ **Celebratory:** Party sounds mark achievements (people entering, phone removed)  

---

## Troubleshooting

### Fire crackle not playing
- Check AMBIENT state is active (1-3 people)
- Verify fire_crackle_loop.wav exists in `vision/assets/sfx/`
- Check master_volume not muted

### Whoosh plays but text doesn't match
- Entry_flash_id may not align with person detection
- Text queue is waiting for previous text to finish scrolling

### Build-up sounds missing
- Verify people count is in 3-5 range
- Check party_buildup_progress is advancing (> 0.0)

### Phone celebration horn not playing
- Ensure audio_manager is initialized with `enabled=True`
- Check phone_just_exited flag is being set correctly in state machine

---

## Files Reference

**Audio Assets:**
- `/vision/assets/sfx/` - 8 SFX files (3 MB total)
- `/vision/assets/music/` - party_upbeat.wav (15 MB)

**Audio Code:**
- `vision/src/bond_fire_vision/audio_manager.py` - Audio playback engine
- `vision/src/bond_fire_vision/detector.py` - Triggers and state mapping
- `vision/src/bond_fire_vision/state_machine.py` - Fire intensity calculation

