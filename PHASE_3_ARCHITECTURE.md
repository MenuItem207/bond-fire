# Phase 3 Architecture & State Machine Visual Reference

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   MASTER (MacBook + Python)                 │
│                                                              │
│  ┌────────────────┐  ┌─────────────┐  ┌────────────────┐   │
│  │  YOLOv8 Vision │→ │State Machine│→ │Packet Builder  │   │
│  │  (detector.py) │  │             │  │                │   │
│  └────────────────┘  └─────────────┘  └────────┬───────┘   │
│                                                  │            │
│  ┌────────────────┐                             │            │
│  │Audio Manager   │ (Optional TTS, SFX)         │            │
│  └────────────────┘                             │            │
│         ▲                                        │            │
│         │                    ┌──────────────────┘            │
│         │                    ▼                                │
│         │            ┌────────────────────┐                  │
│         │            │ UDP Broadcast v2.1 │                  │
│         │            │   (30 packets/sec) │                  │
│         │            │   (port 4210)      │                  │
│         └────────────│                    │                  │
│                      └──────────┬─────────┘                  │
└───────────────────────────────────┼────────────────────────┘
                                    │
                    WiFi Hotspot (Phone)
                                    │
┌───────────────────────────────────▼────────────────────────┐
│                   SLAVE (ESP32 + Phase 3)                   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              UDP Listener (port 4210)                │   │
│  └────────────────────┬─────────────────────────────────┘   │
│                       ▼                                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │        JSON Parser (ArduinoJson)                     │   │
│  │  • Validate version == 2                             │   │
│  │  • Extract state, PWM, palette, flags                │   │
│  └────────────────────┬─────────────────────────────────┘   │
│                       ▼                                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │     State Machine Dispatcher (applyStateEffects)     │   │
│  │                                                      │   │
│  │  switch (state) {                                    │   │
│  │    case STATE_IDLE:    renderIdleEffect()           │   │
│  │    case STATE_FIRE:    renderFireEffect()           │   │
│  │    case STATE_PARTY:   renderPartyEffect()          │   │
│  │    case STATE_PHONE:   renderPhoneGlitch()          │   │
│  │  }                                                   │   │
│  │                                                      │   │
│  │  if (pulse_active) renderPulseEffect()              │   │
│  │  if (entry_flash) renderEntryFlash()                │   │
│  └─────────┬──────────────────────┬──────────┬─────────┘   │
│            ▼                      ▼          ▼              │
│     ┌────────────────┐  ┌────────────────┐  ┌────────┐     │
│     │  FastLED Ring  │  │NeoMatrix Text  │  │  PWM   │     │
│     │  (59 LEDs)     │  │  (32x8 pixels) │  │Outputs │     │
│     └────────────────┘  └────────────────┘  └───┬────┘     │
│                                                  │           │
│                           ┌──────────────────────┘           │
│                           ▼                                  │
│                    ┌──────────────┐                          │
│                    │  Watchdog    │                          │
│                    │  (5s timeout)│                          │
│                    └──────────────┘                          │
└─────────────────────────────────────────────────────────────┘
            ▲                       │            │
            │                       │            │
            ▼                       ▼            ▼
      ┌─────────┐          ┌──────────┐     ┌────────┐
      │LED Ring │          │Fan Motor │     │Mist    │
      │         │          │(PWM 5kHz)│     │Pump    │
      │Colors  │          │          │     │(1kHz)  │
      │Effects │          │Speed     │     │Atomizer│
      └─────────┘          └──────────┘     └────────┘
```

---

## State Machine Logic

### State Transitions

```
                           ┌─────────────────────┐
                           │   ANY STATE → PHONE │
                           │  (instant trigger)  │
                           └────────┬────────────┘
                                    │
                           ┌────────▼────────┐
                           │   PHONE STATE   │
                           │ (phone detected)│
                           └────────┬────────┘
                                    │
                    ┌───────────────────────────┐
                    │Phone removed for 0.5s     │
                    │(exit hysteresis)          │
                    │→ Return to previous state │
                    │+ Celebration              │
                    └───────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │  ┌─────────────────┐        ┌───────────────────┐     │
    │  │  IDLE (0 people)│        │  FIRE (1-4 people)│     │
    │  │                 │◄──────►│                   │     │
    │  │ • Blue breathing│  ↔     │ • Fire animation  │     │
    │  │ • Mist: IDLE    │  ↔     │ • Mist: ramp      │     │
    │  │ • Fan: low      │  ↔     │ • Fan: ramp       │     │
    │  └─────────────────┘  ↔     │ • Intensity: 20%→80% │     │
    │                        ↔     └────────┬─────────┘     │
    │                        ↔              │                │
    │                        │              │ 5+ people      │
    │                        │              │ for 2s         │
    │                        │              ▼                │
    │                        │     ┌──────────────────┐     │
    │                        │     │  PARTY (5+ ppl)  │     │
    │                        │     │                  │     │
    │                        │     │ • Rainbow cycle  │     │
    │                        │     │ • Mist: MAX      │     │
    │                        │     │ • Fan: MAX       │     │
    │                        │     │ • Intensity: 100%│     │
    │                        │     └────────┬─────────┘     │
    │                        │              │                │
    │                        │ 4- people    │                │
    │                        │ for 3s       │                │
    │                        └──────────────┘                │
    │                                                         │
    └─────────────────────────────────────────────────────────┘
                                    ▲
                                    │
                        ┌───────────────────────┐
                        │Phone removed: +3s     │
                        │celebration on all     │
                        │state colors/effects   │
                        └───────────────────────┘
```

### Decision Tree (from UDP Packet)

```
                    ┌──────────────────────┐
                    │ UDP v2.1 Packet RX   │
                    └──────┬───────────────┘
                           ▼
                  ┌────────────────────┐
                  │ Parse "state" field│
                  └────┬─────┬─────┬──┤
                       │     │     │  │
           ┌───────────┘     │     │  └──────────────┐
           │                 │     │                  │
           ▼                 ▼     ▼                  ▼
     ┌──────────┐       ┌──────────┐            ┌──────────┐
     │ "IDLE"   │       │ "FIRE"   │            │ "PARTY"  │
     └────┬─────┘       └────┬─────┘            └────┬─────┘
          ▼                   ▼                       ▼
   renderIdleEffect()  renderFireEffect()    renderPartyEffect()
   + MIST=IDLE         + intensity scaling   + pulse (optional)
   + FAN=60            + pulse (optional)    + MIST=MAX
                       + MIST=variable       + FAN=MAX
                       + FAN=variable
    
    ┌─────────────────────────────────┐
    │         "PHONE"                 │
    │ (always highest priority)       │
    └─────────┬───────────────────────┘
              ▼
         renderPhoneGlitch()
         + MIST=MIN (150)
         + FAN=0
         + Red penalty effect
```

---

## UDP v2.1 Packet Flow

### Incoming Packet (Master → Slave)

```
Python Master                 WiFi Hotspot              ESP32 Firmware
─────────────                 ────────────              ──────────────

1. Vision Loop (30fps)
   - Detect people (YOLOv8)
   - Detect phones
   - Track IDs
   - Extract colors
        │
        ▼
2. State Machine
   - IDLE/FIRE/PARTY/PHONE
   - PWM values
   - Fire intensity
        │
        ▼
3. Build v2.1 JSON
   {
     "version": 2,
     "state": "FIRE",
     "people": [
       {"id": 1, "color": [255,100,50]},
       ...
     ],
     "mist_pwm": 180,
     "fan_pwm": 100,
     ...
   }
        │
        ▼
4. UDP Broadcast ─────────────┐
   (port 4210)                │ 30x/second
                              │
                              ▼
                         5. UDP Listen
                            (port 4210)
                                │
                                ▼
                         6. Parse JSON
                            (ArduinoJson)
                                │
                                ▼
                         7. Validate
                            (version==2)
                                │
                                ▼
                         8. Extract Fields
                            - state: "FIRE"
                            - mist_pwm: 180
                            - fan_pwm: 100
                            - palette: [...]
                            - entry_flash_id: -1
                                │
                                ▼
                         9. Apply State Effects
                            switch(state)→FIRE
                            renderFireEffect()
                                │
                                ▼
                         10. Update Hardware
                             ledcWrite(PIN_FAN, 100)
                             ledcWrite(PIN_MIST, 180)
                             FastLED.show()
                                │
                                ▼
                         11. Display Results
                             • Ring: Fire animation
                             • Matrix: Scrolling text
                             • Fan: 100/255 speed
                             • Mist: 180/255 output
```

---

## Effect Selection Logic

```
                    ┌──────────────────────┐
                    │  applyStateEffects() │
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │  FastLED.clear()     │
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │ switch(state)        │
                    └──┬────┬────┬────┬────┘
                       │    │    │    │
       ┌───────────────┘    │    │    └──────────────────┐
       │                    │    │                       │
       ▼                    ▼    ▼                       ▼
   IDLE                 FIRE   PARTY                 PHONE
   
   renderIdleEffect()   │    renderPartyEffect()    renderPhoneGlitch()
                        │
                        ▼
                   renderFireEffect()
                   (scaled by
                    fire_intensity)
   
   ┌──────────────────────────────────────┐
   │   Check overlay conditions:          │
   └──────────────────────────────────────┘
           │                      │
           │                      │
           ▼                      ▼
   ┌──────────────────┐   ┌─────────────────┐
   │if (pulse_active) │   │if (entry_flash) │
   │  render Pulse()  │   │  render Flash() │
   └──────────────────┘   └─────────────────┘
   
   ┌──────────────────────────────────────┐
   │   Apply PWM Outputs                  │
   └──────────────────────────────────────┘
           │
           ├─► ledcWrite(PIN_FAN, fan_pwm)
           │
           ├─► ledcWrite(PIN_MIST, 
           │      max(MIST_MIN, mist_pwm))
           │
           └─► FastLED.show()
               matrixFront.show()
```

---

## Watchdog Safety Timer

```
                  ┌──────────────────────┐
                  │  Packet Received     │
                  └──────────┬───────────┘
                             ▼
                  ┌──────────────────────┐
                  │lastWatchdog=millis() │
                  │(reset timer)         │
                  └──────────┬───────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
    No packet received    Timeout waiting        Check every loop
   <200ms typical         5 seconds              (every 30ms)
        │                    │                    │
        ▼                    ▼                    ▼
   (normal)            ┌──────────────┐    ┌─────────────────┐
                       │ millis() -   │    │watchdogCheck()  │
                       │lastWatchdog> │───►│                 │
                       │WATCHDOG_...? │    │if (timeout)     │
                       └──────────────┘    │  STATE=IDLE     │
                                           │  MIST=IDLE      │
                                           │  FAN=60         │
                                           │  print("timeout")│
                                           └─────────────────┘
```

---

## Effect Priority & Blending

```
┌─────────────────────────────────────────────┐
│        Rendered in Order (Top = Highest)    │
└─────────────────────────────────────────────┘

1. Base Effect (from state)
   ├─ STATE_IDLE    → renderIdleEffect()
   ├─ STATE_FIRE    → renderFireEffect()
   ├─ STATE_PARTY   → renderPartyEffect()
   └─ STATE_PHONE   → renderPhoneGlitch()

2. Overlay Effects (optional)
   ├─ if (pulse_active)    → renderPulseEffect()
   │  (modulates base colors with pulse)
   │
   └─ if (entry_flash)     → renderEntryFlash()
      (replaces base with person's color)

3. PWM Outputs
   ├─ ledcWrite(PIN_FAN, fan_pwm)
   └─ ledcWrite(PIN_MIST, max(MIST_MIN, mist_pwm))

4. Display Update
   ├─ FastLED.show()        (commit ring LEDs)
   └─ matrixFront.show()    (commit text matrix)
```

---

## Fire Intensity Scaling

```
People Count │ Intensity │ Effect
──────────────────────────────────────
    0        │   0.0f    │ No fire (IDLE)
    1        │  ~0.2f    │ 20% fire
    2        │  ~0.4f    │ 40% fire
    3        │  ~0.6f    │ 60% fire
    4        │  ~0.8f    │ 80% fire
    5+       │  ~1.0f    │ 100% fire (PARTY)

Formula: intensity = min(0.2 + (people-1)*0.2, 1.0)

Applied to:
 • Sparking probability: FIRE_SPARKING * intensity
 • Color brightness: 255 * intensity
 • Animation speed: base_speed * intensity
```

---

## State Memory & Transitions

```
┌─────────────────────────────────────────────────┐
│  StateConfig currentStateConfig                 │
├─────────────────────────────────────────────────┤
│  DisplayState state;           (IDLE/FIRE/..)  │
│  uint8_t mist_pwm;             (0-255)         │
│  uint8_t fan_pwm;              (0-255)         │
│  float fire_intensity;         (0.0-1.0)       │
│  bool pulse_active;            (true/false)    │
│  int entry_flash_id;           (-1 or ID)      │
│  CRGB palette[4];              (up to 4 colors)│
│  int palette_size;             (0-4)           │
└─────────────────────────────────────────────────┘
        ▲                   │
        │                   │ Updated every
   Every packet          packet reception
        │                   │
   (from master)            ▼
                    ┌──────────────────┐
                    │  applyStateEffects
                    │  (executes state)
                    └────────┬─────────┘
                             │
                       Hardware driven
                       • LED animations
                       • PWM outputs
```

---

## Error Handling Flow

```
                    ┌──────────────────┐
                    │  Packet Received │
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │ Try parse JSON   │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
        ✅ Success                   ❌ Parse Error
              │                             │
              ▼                             ▼
    ┌─────────────────────┐     ┌──────────────────────┐
    │ Version == 2 ?      │     │ Serial: JSON error   │
    └────────┬────────────┘     │ Skip packet          │
             │                  │ Keep current state   │
    ┌────────┴──────────┐       └──────────────────────┘
    │                   │
  ✅ Yes              ❌ No
    │                 │
    ▼                 ▼
  Parse State    ┌──────────────────┐
  Extract PWM    │Serial: Version err
  Handle Palette │Skip packet
  Reset Timer    │Keep current state
  Apply Effect   └──────────────────┘
```

---

## Memory & Performance

```
┌──────────────────────────────────────────────────┐
│  Memory Usage (ESP32 has 520KB RAM)              │
├──────────────────────────────────────────────────┤
│  packetBuffer[512]           512 bytes  (JSON)   │
│  ringLeds[59]                177 bytes  (RGB)    │
│  fireHeat[59]                59 bytes   (uint8) │
│  matrixFront                 ~1KB       (object) │
│  FireGradient                ~50 bytes  (palette)│
│  Other variables             ~500 bytes          │
│  ─────────────────────────────────────────────  │
│  Total sketch:               ~3KB                 │
│  Available for buffers:      ~500KB              │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│  Performance Targets                             │
├──────────────────────────────────────────────────┤
│  JSON parse time:            <50ms              │
│  Effect render time:         <10ms              │
│  PWM update:                 <1ms               │
│  Total loop time:            ~30ms (33fps)      │
│  WiFi latency:               <200ms             │
│  Packet loss tolerance:      0% (retransmit)    │
└──────────────────────────────────────────────────┘
```

---

## Compilation & Upload Flow

```
        bond-fire_v2.ino
              │
              ▼
    ┌──────────────────────────┐
    │ Arduino IDE Compiler     │
    │                          │
    │ 1. Preprocessor (expand) │
    │ 2. Compiler (verify)     │
    │ 3. Linker (link libs)    │
    │ 4. Encoder (binary)      │
    └──────────────────────────┘
              │
        ✅ Success or ❌ Error
              │
              ▼
    ┌──────────────────────────┐
    │ Serial Port Detection    │
    │ (/dev/cu.usbserial-...)  │
    └──────────────────────────┘
              │
              ▼
    ┌──────────────────────────┐
    │ Upload to ESP32          │
    │ (via USB Serial)         │
    └──────────────────────────┘
              │
              ▼
    ┌──────────────────────────┐
    │ Boot & Execute           │
    │                          │
    │ 1. setup() - Init hw     │
    │ 2. loop() - Main loop    │
    │ 3. Handle packets        │
    │ 4. Update effects        │
    └──────────────────────────┘
              │
              ▼
    Serial Monitor Output
    (115200 baud)
```

---

## Key Integration Points

```
Python Master              ←→ WiFi ←→  ESP32 Firmware
                        (UDP Hotspot)

detector.py            manual_packet_sender.py         bondfire_v2.ino
  │                            │                            │
  ├─ YOLOv8 detection          ├─ Test packets              ├─ JSON parser
  ├─ State machine             ├─ Manual testing            ├─ State machine
  ├─ Packet builder            ├─ Effect verification       ├─ Hardware driver
  └─ UDP broadcast             └─ Debug packets             └─ LED animations

config.yaml              packet_listener.py
  │                            │
  ├─ Timing thresholds         ├─ Monitor packets
  ├─ Prompt cooldowns          ├─ Watch payloads
  └─ Audio settings            └─ Debug reception
```

---

This visual reference shows the complete data flow, state machine logic, and architectural relationships in Bond Fire Phase 3. Use it alongside the code documentation for implementation and debugging.
