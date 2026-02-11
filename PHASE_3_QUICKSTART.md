# Phase 3 Quick Start & Testing Guide

## File Locations

```
📁 bond-fire/
├── hardware/
│   ├── bondfire_v2.ino          ← NEW: Phase 3 unified firmware
│   ├── phase1_led/phase1_led.ino        (reference, not used)
│   ├── phase2_fan/phase2_fan.ino        (reference, not used)
│   ├── phase3_mister/phase3_mister.ino  (reference, not used)
│   └── working/working.ino              (reference, superseded)
│
├── vision/
│   ├── src/bond_fire_vision/detector.py
│   ├── manual_packet_sender.py   ← Use for testing
│   └── packet_listener.py        ← Use for monitoring
│
└── PHASE_3_MIGRATION_COMPLETE.md ← Full documentation
```

---

## Step 1: Compile & Upload Firmware

### Arduino IDE Steps
```
1. Open:        hardware/bondfire_v2.ino
2. Select:      Tools → Board → ESP32 → ESP32-WROOM-32
3. Select:      Tools → Port → /dev/cu.usbserial-*
4. Verify:      Sketch → Verify/Compile
5. Upload:      Sketch → Upload
6. Monitor:     Tools → Serial Monitor (115200 baud)
```

### Expected Serial Output
```
===== BOND FIRE Phase 3 Startup =====
[INIT] Initializing LED matrix...
[INIT] Initializing PWM for fan and mist...
[INIT] Initializing LED ring...
[INIT] Connecting to WiFi...
[SUCCESS] WiFi Connected!
IP Address: 192.168.x.x
[INIT] Starting UDP listener on port 4210...
[INIT] Setup complete. Waiting for packets...
```

---

## Step 2: Test with Manual Packet Sender

### Test IDLE State
```bash
cd /Users/emmanuel/Documents/Dev/Projects/bond-fire/vision
source env/bin/activate
python manual_packet_sender.py --state IDLE --repeat 3
```

**Expected ESP32 Response:**
```
[UDP] State: IDLE | People: 0 | PWM: M=220 F=60 | Fire: 0.0%
```

**Expected LED Behavior:**
- Ring: Blue breathing glow
- Matrix: Blue text "IDLE" or waiting message
- Mist: Idle (PWM 220)
- Fan: Low (PWM 60)

---

### Test FIRE State (1-4 People)
```bash
python manual_packet_sender.py --state FIRE --people 3 --repeat 5
```

**Expected ESP32 Response:**
```
[UDP] State: FIRE | People: 3 | PWM: M=180 F=150 | Fire: 60.0%
```

**Expected LED Behavior:**
- Ring: Fire animation at 60% intensity
- Matrix: Orange text scrolling
- Mist: Ramping (PWM 180)
- Fan: Medium-high (PWM 150)

---

### Test PARTY State (5+ People)
```bash
python manual_packet_sender.py --state PARTY --people 5 --repeat 5
```

**Expected ESP32 Response:**
```
[UDP] State: PARTY | People: 5 | PWM: M=255 F=255 | Fire: 100.0%
```

**Expected LED Behavior:**
- Ring: Rainbow cycling fast
- Matrix: Magenta text "PARTY!"
- Mist: Maximum (PWM 255)
- Fan: Maximum (PWM 255)

---

### Test PHONE_IDLE State (Phone Present)
```bash
python manual_packet_sender.py --state PHONE_IDLE --repeat 3
```

**Expected ESP32 Response:**
```
[UDP] State: PHONE_IDLE | People: 0 | PWM: M=150 F=60 | Wind: 0 | Fire: 0.0%
```

**Expected LED Behavior:**
- Ring: Warm ember simmer
- Matrix: Prompt text (after delay)
- Mist/Fan: Low simmer (safety floor applies)

### Test FANNING State (Wind Active)
```bash
python manual_packet_sender.py --state FANNING --wind 80 --repeat 3
```

**Expected ESP32 Response:**
```
[UDP] State: FANNING | People: 0 | PWM: M=180 F=150 | Wind: 80 | Fire: 80.0%
```

**Expected LED Behavior:**
- Ring: Brighter ember + faster flicker
- Matrix: Encouraging prompt text
- Mist/Fan: Scales up with wind

---

## Step 3: Test with Python Master (Live)

### Start Vision System
```bash
cd /Users/emmanuel/Documents/Dev/Projects/bond-fire/vision
source env/bin/activate

# Option 1: With camera (live detection)
bond-fire-vision --camera-index 0 --enable-audio --narration-enabled

# Option 2: With test video file (if available)
bond-fire-vision --video-file test.mp4 --enable-audio

# Option 3: Debug mode with verbose output
bond-fire-vision --debug --enable-audio
```

### Expected Behavior
- Matrix shows initial "Waiting..." in blue
- WiFi indicator shows connection status
- As people enter camera frame, effects trigger in sequence:
  - 1 person → FIRE state starts, fire animation begins
  - 3+ people → Fire increases in intensity
  - 5 people for 2s → PARTY state, rainbow cycling starts
  - Phone detected → PHONE_IDLE/FANNING, ember glow, wind scales outputs

---

## Step 4: Monitor Packet Traffic

### Terminal 1: Watch Master Broadcasting
```bash
cd vision && source env/bin/activate
python packet_listener.py
```

Output will show every packet received by the monitor, like:
```
[IP_ADDRESS:4210] RX Packet
  version: 2
  state: FIRE
  people: 2
  mist_pwm: 180
  fan_pwm: 100
  prompt: "Battery 60%. We need 2 more!"
```

### Terminal 2: Check ESP32 Response
Keep Arduino IDE Serial Monitor open to see what ESP32 is parsing:
```
[UDP] State: FIRE | People: 2 | PWM: M=180 F=100 | Fire: 40.0%
```

---

## Step 5: Test Edge Cases

### Watchdog Timeout Test
```
1. Start live vision system: bond-fire-vision ...
2. Observe ESP32 showing: [UDP] State: FIRE ...
3. Stop Python master (Ctrl+C)
4. Wait 5+ seconds
5. Check Serial Monitor for: [WATCHDOG] No packet for 5s, reverting to IDLE
6. LED ring should return to blue breathing
```

### Mist Safety Floor Test
```bash
python manual_packet_sender.py --state FIRE --mist-pwm 50 --repeat 1
```

**Expected:**
- Packet sends `mist_pwm: 50`
- But ESP32 enforces: `max(MIST_MIN=150, 50) = 150`
- Serial shows: `[UDP] ... PWM: M=150 ...`

### Entry Flash Test
```bash
python manual_packet_sender.py --state IDLE \
  --entry-flash-id 1 \
  --person-color 255 100 50 \
  --repeat 1
```

**Expected:**
- Ring flashes with orange/warm color
- Continues for ~3 seconds
- Returns to blue breathing after timer expires

### Invalid JSON Test
```bash
# Send malformed packet directly
echo '{"invalid json' | nc -u localhost 4210
```

**Expected:**
- ESP32 Serial shows: `[UDP ERROR] JSON parse failed: ...`
- System stays in current state
- No crash or hang

---

## Troubleshooting

### Issue: ESP32 won't compile
**Solution:** Install all required libraries in Arduino IDE
```
Sketch → Include Library → Manage Libraries
Search for and install:
  - ArduinoJson (v6.x or v7.x)
  - FastLED
  - Adafruit GFX Library
  - Adafruit NeoMatrix
  - Adafruit NeoPixel
```

### Issue: WiFi shows "NO WIFI" on matrix
**Check:**
1. SSID correct? ("Emmanuel :)")
2. Password correct? ("onseneggpassword123")
3. Phone hotspot enabled?
4. Both Mac and ESP32 connected to same hotspot?

**Fix:** Edit lines 28-29 in bondfire_v2.ino with correct credentials

### Issue: No UDP packets received (Serial shows silence)
**Check:**
1. Is Python master running? `bond-fire-vision --camera-index 0`
2. Are both on same WiFi network?
3. Is ESP32 actually listening? Check Serial for "UDP listener started"

**Test:**
```bash
# From Mac, send test packet directly:
python vision/manual_packet_sender.py --state FIRE --repeat 1
# Should see serial output immediately
```

### Issue: LEDs don't light up
**Check:**
1. Is matrix showing text? (means display power OK)
2. Ring pin correct? (PIN_RING = 18)
3. LED count right? (59 = 24 + 35)

**Test:**
1. Build simple FastLED blink sketch to verify wiring
2. Check power supply (should be 5V, adequate amperage)
3. Try reducing FastLED brightness in code (line ~103)

### Issue: Fan/mist don't activate
**Check:**
1. Are PWM pins correct? (PIN_FAN=4, PIN_MIST=12)
2. Is packet sending PWM values? (check serial: "PWM: M=X F=Y")
3. Are MOSFET gates properly connected?

**Test:**
```bash
# Send PARTY state (should max out PWM)
python manual_packet_sender.py --state PARTY --repeat 1
# Serial should show: PWM: M=255 F=255
# Fan/mist should run at full power
```

---

## Configuration Changes

### WiFi Credentials
**File:** `hardware/bondfire_v2.ino` (lines 28-29)
```cpp
const char* ssid     = "YOUR_SSID";
const char* password = "YOUR_PASSWORD";
```

### LED Count (if using different ring sizes)
**File:** `hardware/bondfire_v2.ino` (lines 35-37)
```cpp
#define RING1_SIZE 24   // Change if needed
#define RING2_SIZE 35   // Change if needed
#define NUM_LEDS_RING (RING1_SIZE + RING2_SIZE)
```

### Safety Limits
**File:** `hardware/bondfire_v2.ino` (lines 39-41)
```cpp
#define MIST_MIN 150    // Minimum mist (prevent stall)
#define MIST_IDLE 220   // Default idle level
#define MIST_MAX 255    // Maximum output
```

### Hardware Pins
If you move hardware to different pins, update:
**File:** `hardware/bondfire_v2.ino` (lines 31-34)
```cpp
#define PIN_MATRIX_FRONT  5   // Change if needed
#define PIN_RING          18  // Change if needed
#define PIN_FAN           4   // Change if needed
#define PIN_MIST          12  // Change if needed
```

---

## Debug Output Codes

| Code          | Meaning             | Action                                |
| ------------- | ------------------- | ------------------------------------- |
| `[INIT]`      | Setup phase         | Normal, shows initialization progress |
| `[SUCCESS]`   | WiFi connected      | Good, system ready for packets        |
| `[WARNING]`   | Non-critical issue  | WiFi couldn't connect but continuing  |
| `[UDP]`       | Packet received     | Normal; shows state and PWM values    |
| `[UDP ERROR]` | Packet parse failed | Usually malformed JSON, skip packet   |
| `[WATCHDOG]`  | No packet for 5s    | Timeout; reverting to IDLE            |

---

## Performance Targets

| Metric         | Target  | Check                              |
| -------------- | ------- | ---------------------------------- |
| Startup time   | <5s     | Should see "OK!" on matrix         |
| Packet latency | <200ms  | From Python send to LED response   |
| Animation FPS  | 30+ fps | Smooth scrolling/effects           |
| PWM response   | <10ms   | Fan/mist speed changes immediately |

---

## Next Steps

1. ✅ **Compile & upload** firmware to ESP32
2. ✅ **Test with manual packets** (step 2 above)
3. ✅ **Test with live Python master** (step 3 above)
4. ✅ **Monitor packet traffic** (step 4 above)
5. ✅ **Test edge cases** (step 5 above)
6. 📋 **Deploy to installation location**
7. 📋 **Run full integration tests** with audience
8. 📋 **Document any calibrations needed**

---

## Support Resources

**Documentation:**
- Full migration details: `PHASE_3_MIGRATION_COMPLETE.md`
- System architecture: `project-readme.md`
- Python code reference: `PHASE_3_GUIDE.md`
- Implementation notes: `IMPLEMENTATION_PLAN.md`

**Code Reference:**
- Phase 1-2 sketches (in `hardware/`) for algorithm details
- Python master (`vision/detector.py`) for state logic
- Configuration (`vision/config.yaml`) for timing/thresholds

**Live Help:**
```bash
# Check what Python is sending
python vision/packet_listener.py

# Send specific test packets
python vision/manual_packet_sender.py --help

# Monitor ESP32 output
# (Arduino IDE Serial Monitor, 115200 baud)
```

---

**Status:** Ready for testing 🚀  
**Version:** Phase 3 (v2.1 Protocol)  
**Last Updated:** February 6, 2026
