# Consultant-Grade Assignment Briefs (High Specificity)

## Project Context (Read First)

**Product:** The Empathic Hearth, an interactive installation that uses computer vision to detect people and drive a mist-flame, fan, LED ring, and LED matrix to encourage social connection.

**Architecture Summary:** A Python "master" runs YOLOv8 vision, a state machine, and an audio system. It broadcasts a v2.1 JSON packet over WiFi UDP (port 4210) ~30 packets/sec to an ESP32 "slave". The ESP32 parses packets and renders visual effects while controlling PWM outputs for mist and fan. A phone hotspot bridges the Mac and ESP32. The system is designed as a social feedback loop: people count and wind/shake input alter visual effects, mist/fan intensity, and prompts.

**Standalone Reference (No Repo Access Needed):**
- **Master (Python):** YOLOv8 detects people, tracks IDs, extracts dominant shirt colors, runs a state machine, builds a JSON packet, and sends UDP broadcast at ~30 packets/sec. Wind is sourced from Firebase RTDB shake input or a secondary UDP listener.
- **Slave (ESP32):** Receives UDP, parses JSON, and renders LED ring + LED matrix while driving mist and fan via PWM.
- **UDP Port:** 4210. **Packet size goal:** under 1 KB. **ESP32 buffer:** 1500 bytes.
- **Core States:** IDLE, FIRE, PARTY.
	- IDLE: 0 people for 5 seconds.
	- FIRE: 1-4 people (after a short entry dwell).
	- PARTY: 5+ people for 2 seconds.
	- Exit PARTY: <4 people for 3 seconds.
- **State Outputs (Master to Slave):** `mist_pwm` (0-255), `fan_pwm` (0-255), `wind` (0-100), `fire_intensity` (0.0-1.0), `pulse_active` (15s pulse), `entry_flash_id` (new person), `party_buildup_progress` (0.0-1.0).
- **Protocol Fields (v2.1 JSON):**
	- `version` (2)
	- `state` (IDLE/FIRE/PARTY)
	- `people` (array, max 6)
	- `dominant_palette` (up to 4 colors, 12 values total)
	- `prompt` (max 120 chars)
	- `mist_pwm`, `fan_pwm`, `wind`, `fire_intensity`
	- `pulse_active`, `entry_flash_id`, `party_buildup_progress`, `audio_state`, `timestamp`, `fps`
- **Hardware Outputs:**
	- Mist PWM: 1 kHz, 8-bit. Safe floor 150, idle 220, max 255.
	- Fan PWM: 5 kHz, 8-bit. Idle 60, min 100, max 255.
	- LED ring: 59 WS2812B LEDs (24 + 35 daisy-chained).
	- LED matrix: 32x8 NeoMatrix.
- **Watchdog:** 5-second timeout safety fallback on ESP32.
- **Vision Config (Default):**
	- Detection confidence threshold: 0.08
	- Person class ID: 0 (COCO)
	- Minimum person area ratio: 0.08
	- NMS IOU threshold: 0.45
	- Fire entry dwell: 0.3s
	- Frame rate for state timing: 5 fps
	- Prompt cooldowns: 22s (normal, same-state)
- **Audio:** SFX and music playback; optional TTS narration; audio queue size 50.

**Embedded Code Snippets (For Standalone Use):**

**ESP32 hardware constants (mist/fan PWM, LED ring sizing, safety limits):**
```cpp
// Pins and sizes
#define PIN_MATRIX_FRONT  5
#define PIN_RING          18
#define PIN_FAN           4
#define PIN_MIST          12
#define RING1_SIZE 24
#define RING2_SIZE 35
#define NUM_LEDS_RING (RING1_SIZE + RING2_SIZE)  // 59

// Safety limits
#define MIST_MIN 150
#define MIST_IDLE 220
#define MIST_MAX 255

// PWM setup (ESP32)
ledcAttach(PIN_FAN, 5000, 8);  // 5 kHz, 8-bit
ledcAttach(PIN_MIST, 1000, 8); // 1 kHz, 8-bit
```

**State machine timing and hardware bounds (master logic):**
```python
# Timing constants (seconds)
IDLE_TIMEOUT = 5.0
PARTY_DWELL = 2.0
PARTY_EXIT_DWELL = 3.0
PARTY_ENTRY_BUILDUP = 1.5
PULSE_INTERVAL = 15.0
ENTRY_FLASH_DURATION = 3.0

# Hardware bounds
MIST_MIN = 150
MIST_IDLE = 220
MIST_MAX = 255
FAN_IDLE = 60
FAN_MIN = 100
FAN_MAX = 255
```

**Config defaults (dwell timers, frame rate, detection thresholds):**
```yaml
state_machine:
	fire_entry_dwell: 0.3
	frame_rate: 5

prompts:
	normal_cooldown: 22
	same_state_cooldown: 22

vision:
	confidence_threshold: 0.08
	person_class_id: 0
	min_person_area_ratio: 0.08
	iou_threshold: 0.45
```

**Packet schema builder (v2.1 JSON fields):**
```python
packet = {
	"version": 2,
	"timestamp": now,
	"fps": round(avg_fps, 1),
	"state": state.value,              # IDLE/FIRE/PARTY
	"people": people_data,             # max 6
	"dominant_palette": palette,       # max 4 colors
	"prompt": prompt[:120],
	"mist_pwm": mist_pwm,
	"fan_pwm": fan_pwm,
	"wind": wind,
	"fire_intensity": round(fire_intensity, 2),
	"pulse_active": pulse_active,
	"entry_flash_id": entry_flash_id,
	"audio_state": audio_state.value,
	"party_buildup_progress": round(party_buildup_progress, 2),
}
```

**UDP transport and packet sizing (ESP32 buffer):**
```cpp
WiFiUDP udp;
unsigned int localPort = 4210;
char packetBuffer[1500]; // buffer for v2.1 packets
```

**State transition logic (concise summary):**
- IDLE enters after 5 seconds of zero people.
- FIRE enters after fire_entry_dwell when people > 0.
- PARTY enters after 5+ people for 2 seconds, with a 1.5 second build-up.
- PARTY exits when people <= 4 for 3 seconds.

**Key Files (If You Have Repo Access):**
- project overview and system diagram: [project-readme.md](project-readme.md)
- ESP32 firmware: [hardware/bondfire-v2/bondfire-v2.ino](hardware/bondfire-v2/bondfire-v2.ino)
- Python state machine: [vision/src/bond_fire_vision/state_machine.py](vision/src/bond_fire_vision/state_machine.py)
- Python packet builder: [vision/src/bond_fire_vision/packet_builder.py](vision/src/bond_fire_vision/packet_builder.py)
- Configuration values: [vision/config.yaml](vision/config.yaml)

**Core States:** IDLE, FIRE, PARTY. Party requires 5+ people for 2s; exit party when <4 people for 3s. Timings are configurable in [vision/config.yaml](vision/config.yaml).

**State Outputs (Master to Slave):** The state machine produces `mist_pwm`, `fan_pwm`, `fire_intensity` (0.0 to 1.0), `pulse_active` (15s pulse), `entry_flash_id` (new person), and `party_buildup_progress` (0.0 to 1.0). Wind input (0-100) is sourced externally and included in the v2.1 packet along with `state`, `people`, `dominant_palette`, and `prompt`.

**Hardware Outputs (ESP32):**
- Mist atomizer PWM (1 kHz, 8-bit)
- Fan PWM (5 kHz, 8-bit)
- LED ring (59 WS2812B LEDs) via FastLED
- LED matrix (32x8) via Adafruit NeoMatrix

**Network + Timing Expectations:** The master attempts ~30 packets/sec; UDP packets should remain under 1 KB for reliability. The ESP32 has a 1500-byte packet buffer and a 5-second watchdog timeout as a safety fallback.

**Protocol Highlights (v2.1):**
- `version=2` schema
- `people` list truncated to 6
- `prompt` truncated to 120 chars
- `dominant_palette` max 4 colors (12 values)
- `wind` clamped to 0-100 and quantized to 25-step buckets

**Audio Context:** The master can play SFX/music and optional TTS narration; audio state is embedded in packets for synchronized cues (e.g., AMBIENT vs PARTY).

**Expected Deliverable Format (All Members):**
- 2-4 pages equivalent (approx. 900-1500 words)
- One diagram required (more allowed)
- A short "Integration" section explaining how your subsystem or test aligns with the rest of the system
- A short "Assumptions" section (hardware setup, environment, and data collection conditions)

---

## MEMBER 1 (Option A): ESP32 Actuation and LED Effects Subsystem

**Topic:** Firmware-driven actuation (PWM mist/fan) and LED ring/matrix rendering.

**Focus:** Translate incoming state and PWM values into safe, responsive physical effects; include LED effect timing and safety constraints.

**Required Specs (Extrapolate from Code):**
- Mist PWM safety bounds `MIST_MIN=150`, `MIST_IDLE=220`, `MIST_MAX=255` [hardware/bondfire-v2/bondfire-v2.ino](hardware/bondfire-v2/bondfire-v2.ino#L45-L48)
- Ring LED count `NUM_LEDS_RING=59` (24 + 35) [hardware/bondfire-v2/bondfire-v2.ino](hardware/bondfire-v2/bondfire-v2.ino#L40-L43)
- PWM frequencies: fan 5 kHz, mist 1 kHz (8-bit) [hardware/bondfire-v2/bondfire-v2.ino](hardware/bondfire-v2/bondfire-v2.ino#L174-L178)

**Diagram Instruction:**
- Draw a hardware signal flow diagram from UDP payload fields (`mist_pwm`, `fan_pwm`, `dominant_palette`) into PWM outputs and LED ring/matrix render paths, including safety clamps and the watchdog timeout.

**Required Deliverables:**
- Map each core state (IDLE/FIRE/PARTY) to LED ring effects, matrix text behavior, and mist/fan PWM range assumptions.
- Describe how `pulse_active`, `entry_flash_id`, `party_buildup_progress`, and `wind` alter the base effect.
- Provide a risk/safety section addressing PWM floors, watchdog timeout behavior, and thermal or moisture considerations.

**Distinction Checklist:**
- Write this sentence verbatim: “The ESP32 effect engine consumes the v2.1 UDP fields from `PacketBuilderV2.build()` and applies state, PWM, palette, and wind inputs to its LED renderers and actuation outputs, ensuring protocol-driven lighting stays synchronized with the vision state machine.” [vision/src/bond_fire_vision/packet_builder.py](vision/src/bond_fire_vision/packet_builder.py#L55-L150)

---

## MEMBER 2 (Option A): UDP Protocol + Packet Schema Integration

**Topic:** v2.1 JSON packet schema, UDP transport, and parsing/validation strategy.

**Focus:** Define the packet contract and how it is enforced across Python and ESP32; address size limits, truncation, and field validation.

**Required Specs (Extrapolate from Code):**
- Protocol version `PROTOCOL_VERSION=2` and schema v2.1; max packet size < 1 KB [vision/src/bond_fire_vision/packet_builder.py](vision/src/bond_fire_vision/packet_builder.py#L39-L48)
- Max people array length = 6 and prompt length = 120 chars [vision/src/bond_fire_vision/packet_builder.py](vision/src/bond_fire_vision/packet_builder.py#L110-L127)
- Wind clamped to 0-100 and quantized to 25-step buckets [vision/src/bond_fire_vision/packet_builder.py](vision/src/bond_fire_vision/packet_builder.py#L118-L124)
- UDP port 4210 and packet buffer size 1500 bytes [hardware/bondfire-v2/bondfire-v2.ino](hardware/bondfire-v2/bondfire-v2.ino#L29-L33), [hardware/bondfire-v2/bondfire-v2.ino](hardware/bondfire-v2/bondfire-v2.ino#L83-L85)

**Diagram Instruction:**
- Draw a sequence diagram: `PacketBuilderV2.build()` → UDP broadcast → ESP32 UDP listener → JSON parse → state dispatch → PWM/LED outputs.

**Required Deliverables:**
- List every packet field used by the ESP32 (state, mist/fan PWM, wind, fire_intensity, palette, pulse, entry flash, prompt, and people for entry flash lookup) and describe expected data types and ranges.
- Define a validation policy (what to do if a field is missing, malformed, or out of range).
- Include a short section on packet-size budgeting and why truncation limits exist.

**Distinction Checklist:**
- Write this sentence verbatim: “The schema constraints (people ≤ 6, prompt ≤ 120, palette ≤ 4 colors, wind 0-100) are enforced in the packet builder and must be revalidated on the ESP32 to keep the master’s state machine and slave’s effect renderer in lockstep.” [vision/src/bond_fire_vision/packet_builder.py](vision/src/bond_fire_vision/packet_builder.py#L110-L132)

---

## MEMBER 3 (Option A): Vision State Machine and Behavior Logic

**Topic:** Vision-driven state machine (IDLE/FIRE/PARTY) and behavior timings.

**Focus:** Explain the state transitions, dwell timers, and how output values map to PWM and effects.

**Required Specs (Extrapolate from Code):**
- Party entry/exit dwell: 2.0 s entry, 3.0 s exit; pulse interval 15 s [vision/src/bond_fire_vision/state_machine.py](vision/src/bond_fire_vision/state_machine.py#L61-L67)
- Fire entry dwell and frame rate from config: `fire_entry_dwell=0.3`, `frame_rate=5` [vision/config.yaml](vision/config.yaml#L5-L8)
- Hardware output bounds: `MIST_MIN=150`, `MIST_MAX=255`, `FAN_MIN=100`, `FAN_MAX=255` [vision/src/bond_fire_vision/state_machine.py](vision/src/bond_fire_vision/state_machine.py#L69-L75)

**Diagram Instruction:**
- Draw a state transition diagram with explicit dwell timers for IDLE, FIRE, and PARTY, and annotate output effects (`mist_pwm`, `fan_pwm`, `pulse_active`).

**Required Deliverables:**
- A timing table summarizing all dwell timers and their triggers (from config and code).
- A mapping from state outputs to packet fields, describing how each output influences the slave's effects.
- A narrative of party build-up progression and entry flash behavior.

**Distinction Checklist:**
- Write this sentence verbatim: “The state machine’s dwell timers from config drive output PWM and effect flags that are serialized into UDP packets, which the ESP32 consumes to render synchronized LED and mist behaviors.” [vision/config.yaml](vision/config.yaml#L5-L9), [vision/src/bond_fire_vision/packet_builder.py](vision/src/bond_fire_vision/packet_builder.py#L55-L150)

---

## MEMBER 4 (Option B): Vision Detection Accuracy and Robustness Testing

**Topic:** Detection quality for people class and ROI accuracy.

**Focus:** Define a comprehensive test plan for detection accuracy and robustness to lighting and background clutter.

**Required Specs (Extrapolate from Code):**
- YOLO confidence threshold `confidence_threshold=0.08` [vision/config.yaml](vision/config.yaml#L43-L52)
- Class ID: person 0 [vision/config.yaml](vision/config.yaml#L43-L52)
- Minimum person area ratio `min_person_area_ratio=0.08` and IOU threshold `iou_threshold=0.45` [vision/config.yaml](vision/config.yaml#L43-L52)
- Prompt cooldowns to avoid test contamination (normal/same-state cooldowns at 22 s) [vision/config.yaml](vision/config.yaml#L11-L15)

**Diagram Instruction:**
- Include a confusion matrix for person detection (TP/FP/FN/TN) and a histogram of detection confidences (separate bins for true positive and false positive).

**Required Deliverables:**
- A test dataset plan: at least 6 scenes, 3 lighting conditions (bright, dim, mixed), 2 camera distances, minimum 300 labeled frames.
- A statistical summary: precision, recall, F1, and confidence-threshold sensitivity analysis (e.g., 0.3, 0.5, 0.7).
- A pass/fail rubric tied to the success thresholds in the checklist.

**Distinction Checklist:**
- Write this sentence verbatim: “Success threshold: person detection recall ≥ 0.90 and precision ≥ 0.95 at `confidence_threshold=0.08`, validated by confusion matrices and confidence histograms across lighting conditions.” [vision/config.yaml](vision/config.yaml#L43-L52)

---

## MEMBER 5 (Option B): End-to-End Latency, UDP Reliability, and Actuation Testing

**Topic:** Timing and reliability of packet delivery and hardware response.

**Focus:** Measure packet rate, loss, jitter, and ESP32 actuation latency under realistic network conditions.

**Required Specs (Extrapolate from Code):**
- UDP architecture and ~30 packets/sec expectation [project-readme.md](project-readme.md#L17-L32)
- UDP port 4210 for master-slave transport [hardware/bondfire-v2/bondfire-v2.ino](hardware/bondfire-v2/bondfire-v2.ino#L29-L33)
- Watchdog timeout 5 s for safety fallback [hardware/bondfire-v2/bondfire-v2.ino](hardware/bondfire-v2/bondfire-v2.ino#L98-L100)

**Diagram Instruction:**
- Plot a latency histogram (packet timestamp to actuation) and a packet inter-arrival time histogram, plus a timeline trace for state changes.

**Required Deliverables:**
- A measurement method describing time stamping at send, receive, and actuation, and how you compute latency and jitter.
- A test protocol for 10-minute continuous runs with at least two network conditions (clean WiFi vs congested hotspot).
- A reliability section reporting packet loss rate, watchdog-trigger rate, and recovery time after packet dropouts.

**Distinction Checklist:**
- Write this sentence verbatim: “Success threshold: median end-to-end latency ≤ 100 ms, 99th percentile ≤ 250 ms, and packet loss < 1% over 10 minutes at the 30 packets/sec target; report histograms and jitter statistics.” [project-readme.md](project-readme.md#L17-L32)
