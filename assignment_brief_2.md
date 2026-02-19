# Assignment Brief 2 (All-in-One)

## Purpose
This document provides five copy-paste member prompts and a shared requirements checklist. Each member can paste their section into a new conversation to generate a highly detailed submission guide aligned to the project code and briefs.

## Shared Requirements (All Members)
- Output format: Markdown with clear headings, bolded key terms, and tables for data.
- Length target: 900-1500 words (approx 2-4 pages equivalent).
- Required sections in the response:
  - Subsystem/Test Objective
  - Technical Specifications (tables or lists of constants/logic derived from code)
  - Implementation/Methodology
  - Diagram Description (text-based, highly detailed)
  - Integration & Assumptions
- Use concrete constants, pin definitions, frequencies, buffer sizes, and thresholds.
- Include the verbatim sentence listed in the member brief.
- If test numbers are needed, base them on logical ranges derived from the code and the 30 packets/sec target.
- Use the file links below for references:
  - project overview: project-readme.md
  - ESP32 firmware: hardware/bondfire-v2/bondfire-v2.ino
  - state machine: vision/src/bond_fire_vision/state_machine.py
  - packet builder: vision/src/bond_fire_vision/packet_builder.py
  - config: vision/config.yaml

---

## Member 1 Prompt (ESP32 Actuation and LED Effects)

Copy-paste the prompt below into a new conversation.

```
Role & Context
Act as a Senior Systems Integration Consultant. I am working on "The Empathic Hearth", an interactive installation.

Project Architecture Reference
Master: Python running YOLOv8, State Machine, and Audio.
Slave: ESP32 receiving v2.1 JSON packets via UDP (Port 4210) to drive PWM (Mist/Fan) and LEDs (Ring/Matrix).
Core States: IDLE, FIRE, PARTY.

My Specific Assignment
Member 1 (Option A): ESP32 Actuation and LED Effects Subsystem.
Topic: Firmware-driven actuation (PWM mist/fan) and LED ring/matrix rendering.
Focus: Translate incoming state and PWM values into safe, responsive physical effects; include LED effect timing and safety constraints.

Instructions for Generation
Analyze the codebase and extract exact constants, pin definitions, and logic thresholds.
Do not use generic descriptions. Reference specific functions, variable names, and hardware constraints (PWM frequencies, buffer sizes, LED counts).

Technical Reference (Use in your response)
- Pins: PIN_MATRIX_FRONT=5, PIN_RING=18, PIN_FAN=4, PIN_MIST=12.
- LED ring size: RING1_SIZE=24, RING2_SIZE=35, NUM_LEDS_RING=59.
- Mist safety limits: MIST_MIN=150, MIST_IDLE=220, MIST_MAX=255.
- PWM setup: fan 5 kHz, mist 1 kHz, both 8-bit.
- UDP buffer: packetBuffer[1500].
- Watchdog timeout: 5000 ms.
- Matrix brightness init: 35; ring brightness init: 100.

Formatting
Structure the response into the following sections:
1) Subsystem/Test Objective
2) Technical Specifications (tables or lists)
3) Implementation/Methodology
4) Diagram Description
5) Integration & Assumptions

Diagram Instruction
Draw a hardware signal flow diagram from UDP payload fields (mist_pwm, fan_pwm, dominant_palette) into PWM outputs and LED ring/matrix render paths, including safety clamps and the watchdog timeout.

Required Deliverables
- Map each core state (IDLE/FIRE/PARTY) to LED ring effects, matrix text behavior, and mist/fan PWM range assumptions.
- Describe how pulse_active, entry_flash_id, party_buildup_progress, and wind alter the base effect.
- Provide a risk/safety section addressing PWM floors, watchdog timeout behavior, and thermal or moisture considerations.

Distinction Requirement (Verbatim Sentence)
“The ESP32 effect engine consumes the v2.1 UDP fields from `PacketBuilderV2.build()` and applies state, PWM, palette, and wind inputs to its LED renderers and actuation outputs, ensuring protocol-driven lighting stays synchronized with the vision state machine.”

Primary Code References
- hardware/bondfire-v2/bondfire-v2.ino
- vision/src/bond_fire_vision/packet_builder.py

Final Output Format
Produce a comprehensive report (900-1500 words). Use Markdown with clear headings, bolded key terms, and tables for data. Tone: professional, technical, concise.
```

---

## Member 2 Prompt (UDP Protocol + Packet Schema Integration)

Copy-paste the prompt below into a new conversation.

```
Role & Context
Act as a Senior Systems Integration Consultant. I am working on "The Empathic Hearth", an interactive installation.

Project Architecture Reference
Master: Python running YOLOv8, State Machine, and Audio.
Slave: ESP32 receiving v2.1 JSON packets via UDP (Port 4210) to drive PWM (Mist/Fan) and LEDs (Ring/Matrix).
Core States: IDLE, FIRE, PARTY.

My Specific Assignment
Member 2 (Option A): UDP Protocol + Packet Schema Integration.
Topic: v2.1 JSON packet schema, UDP transport, and parsing/validation strategy.
Focus: Define the packet contract and how it is enforced across Python and ESP32; address size limits, truncation, and field validation.

Instructions for Generation
Analyze the codebase and extract exact constants, field limits, and validation logic.
Do not use generic descriptions. Reference specific functions, variable names, and hardware constraints (buffer size, port, packet size goal).

Technical Reference (Use in your response)
- Protocol version: PROTOCOL_VERSION=2; schema v2.1.
- Packet fields: version, timestamp, fps, state, people, dominant_palette, prompt, mist_pwm, fan_pwm, wind, fan_pulse, fan_pulse_color, fire_intensity, pulse_active, entry_flash_id, audio_state, party_buildup_progress.
- People array max: 6 entries; shirt_name truncated to 24 chars.
- Palette truncation: max 12 values (4 colors).
- Prompt truncation: 120 chars.
- PWM clamp: 0-255; wind clamp: 0-100 then quantize to 25-step buckets.
- UDP port: 4210; ESP32 buffer: 1500 bytes.

Formatting
Structure the response into the following sections:
1) Subsystem/Test Objective
2) Technical Specifications (tables or lists)
3) Implementation/Methodology
4) Diagram Description
5) Integration & Assumptions

Diagram Instruction
Draw a sequence diagram: PacketBuilderV2.build() → UDP broadcast → ESP32 UDP listener → JSON parse → state dispatch → PWM/LED outputs.

Required Deliverables
- List every packet field used by the ESP32 (state, mist/fan PWM, wind, fire_intensity, palette, pulse, entry flash, prompt, and people for entry flash lookup) and describe expected data types and ranges.
- Define a validation policy (what to do if a field is missing, malformed, or out of range).
- Include a short section on packet-size budgeting and why truncation limits exist.

Distinction Requirement (Verbatim Sentence)
“The schema constraints (people ≤ 6, prompt ≤ 120, palette ≤ 4 colors, wind 0-100) are enforced in the packet builder and must be revalidated on the ESP32 to keep the master’s state machine and slave’s effect renderer in lockstep.”

Primary Code References
- vision/src/bond_fire_vision/packet_builder.py
- hardware/bondfire-v2/bondfire-v2.ino

Final Output Format
Produce a comprehensive report (900-1500 words). Use Markdown with clear headings, bolded key terms, and tables for data. Tone: professional, technical, concise.
```

---

## Member 3 Prompt (Vision State Machine and Behavior Logic)

Copy-paste the prompt below into a new conversation.

```
Role & Context
Act as a Senior Systems Integration Consultant. I am working on "The Empathic Hearth", an interactive installation.

Project Architecture Reference
Master: Python running YOLOv8, State Machine, and Audio.
Slave: ESP32 receiving v2.1 JSON packets via UDP (Port 4210) to drive PWM (Mist/Fan) and LEDs (Ring/Matrix).
Core States: IDLE, FIRE, PARTY.

My Specific Assignment
Member 3 (Option A): Vision State Machine and Behavior Logic.
Topic: Vision-driven state machine (IDLE/FIRE/PARTY) and behavior timings.
Focus: Explain the state transitions, dwell timers, and how output values map to PWM and effects.

Instructions for Generation
Analyze the codebase and extract exact constants, dwell timers, and output bounds.
Do not use generic descriptions. Reference specific functions, variable names, and hardware constraints.

Technical Reference (Use in your response)
- IDLE_TIMEOUT=5.0 s; PARTY_DWELL=2.0 s; PARTY_EXIT_DWELL=3.0 s.
- PARTY_ENTRY_BUILDUP=1.5 s; PULSE_INTERVAL=15.0 s; ENTRY_FLASH_DURATION=2.0 s.
- FIRE_ENTRY_DWELL from config: 0.3 s; frame_rate=5.
- Output bounds: MIST_MIN=150, MIST_IDLE=220, MIST_MAX=255; FAN_IDLE=60, FAN_MIN=100, FAN_MAX=255.
- FIRE intensity formula: intensity = min(1.0, 0.4 + people * 0.12).

Formatting
Structure the response into the following sections:
1) Subsystem/Test Objective
2) Technical Specifications (tables or lists)
3) Implementation/Methodology
4) Diagram Description
5) Integration & Assumptions

Diagram Instruction
Draw a state transition diagram with explicit dwell timers for IDLE, FIRE, and PARTY, and annotate output effects (mist_pwm, fan_pwm, pulse_active).

Required Deliverables
- A timing table summarizing all dwell timers and their triggers (from config and code).
- A mapping from state outputs to packet fields, describing how each output influences the slave's effects.
- A narrative of party build-up progression and entry flash behavior.

Distinction Requirement (Verbatim Sentence)
“The state machine’s dwell timers from config drive output PWM and effect flags that are serialized into UDP packets, which the ESP32 consumes to render synchronized LED and mist behaviors.”

Primary Code References
- vision/src/bond_fire_vision/state_machine.py
- vision/src/bond_fire_vision/packet_builder.py
- vision/config.yaml

Final Output Format
Produce a comprehensive report (900-1500 words). Use Markdown with clear headings, bolded key terms, and tables for data. Tone: professional, technical, concise.
```

---

## Member 4 Prompt (Vision Detection Accuracy and Robustness Testing)

Copy-paste the prompt below into a new conversation.

```
Role & Context
Act as a Senior Systems Integration Consultant. I am working on "The Empathic Hearth", an interactive installation.

Project Architecture Reference
Master: Python running YOLOv8, State Machine, and Audio.
Slave: ESP32 receiving v2.1 JSON packets via UDP (Port 4210) to drive PWM (Mist/Fan) and LEDs (Ring/Matrix).
Core States: IDLE, FIRE, PARTY.

My Specific Assignment
Member 4 (Option B): Vision Detection Accuracy and Robustness Testing.
Topic: Detection quality for people class and ROI accuracy.
Focus: Define a comprehensive test plan for detection accuracy and robustness to lighting and background clutter.

Instructions for Generation
Analyze the codebase and extract exact detection thresholds and IOU values.
Do not use generic descriptions. Reference specific configuration fields and testing thresholds.

Technical Reference (Use in your response)
- confidence_threshold=0.08; person_class_id=0; min_person_area_ratio=0.08; iou_threshold=0.45.
- frame_width=1920; frame_height=1080; imgsz=640.
- Prompt cooldowns: normal_cooldown=22 s; same_state_cooldown=22 s (avoid prompt contamination during tests).
- Suggested threshold sweep: 0.3, 0.5, 0.7 for sensitivity analysis.

Formatting
Structure the response into the following sections:
1) Subsystem/Test Objective
2) Technical Specifications (tables or lists)
3) Implementation/Methodology
4) Diagram Description
5) Integration & Assumptions

Diagram Instruction
Include a confusion matrix for person detection (TP/FP/FN/TN) and a histogram of detection confidences (separate bins for true positive and false positive).

Required Deliverables
- A test dataset plan: at least 6 scenes, 3 lighting conditions (bright, dim, mixed), 2 camera distances, minimum 300 labeled frames.
- A statistical summary: precision, recall, F1, and confidence-threshold sensitivity analysis (e.g., 0.3, 0.5, 0.7).
- A pass/fail rubric tied to the success thresholds in the checklist.

Distinction Requirement (Verbatim Sentence)
“Success threshold: person detection recall ≥ 0.90 and precision ≥ 0.95 at `confidence_threshold=0.08`, validated by confusion matrices and confidence histograms across lighting conditions.”

Primary Code References
- vision/config.yaml

Final Output Format
Produce a comprehensive report (900-1500 words). Use Markdown with clear headings, bolded key terms, and tables for data. Tone: professional, technical, concise.
```

---

## Member 5 Prompt (Latency, UDP Reliability, and Actuation Testing)

Copy-paste the prompt below into a new conversation.

```
Role & Context
Act as a Senior Systems Integration Consultant. I am working on "The Empathic Hearth", an interactive installation.

Project Architecture Reference
Master: Python running YOLOv8, State Machine, and Audio.
Slave: ESP32 receiving v2.1 JSON packets via UDP (Port 4210) to drive PWM (Mist/Fan) and LEDs (Ring/Matrix).
Core States: IDLE, FIRE, PARTY.

My Specific Assignment
Member 5 (Option B): End-to-End Latency, UDP Reliability, and Actuation Testing.
Topic: Timing and reliability of packet delivery and hardware response.
Focus: Measure packet rate, loss, jitter, and ESP32 actuation latency under realistic network conditions.

Instructions for Generation
Analyze the codebase and extract exact timing expectations, ports, and watchdog behavior.
Do not use generic descriptions. Reference specific file constants and expected packet rates.

Technical Reference (Use in your response)
- UDP port: 4210; target rate: ~30 packets/sec.
- Packet timestamp: packet field `timestamp` in v2.1 schema.
- ESP32 watchdog timeout: 5000 ms.
- Buffer: packetBuffer[1500].
- Logical test durations: 10-minute continuous runs with two network conditions (clean WiFi and congested hotspot).
- Logical latency targets: median <= 100 ms, p99 <= 250 ms; packet loss < 1% over 10 minutes.

Formatting
Structure the response into the following sections:
1) Subsystem/Test Objective
2) Technical Specifications (tables or lists)
3) Implementation/Methodology
4) Diagram Description
5) Integration & Assumptions

Diagram Instruction
Plot a latency histogram (packet timestamp to actuation) and a packet inter-arrival time histogram, plus a timeline trace for state changes.

Required Deliverables
- A measurement method describing time stamping at send, receive, and actuation, and how you compute latency and jitter.
- A test protocol for 10-minute continuous runs with at least two network conditions (clean WiFi vs congested hotspot).
- A reliability section reporting packet loss rate, watchdog-trigger rate, and recovery time after packet dropouts.

Distinction Requirement (Verbatim Sentence)
“Success threshold: median end-to-end latency ≤ 100 ms, 99th percentile ≤ 250 ms, and packet loss < 1% over 10 minutes at the 30 packets/sec target; report histograms and jitter statistics.”

Primary Code References
- project-readme.md
- hardware/bondfire-v2/bondfire-v2.ino

Final Output Format
Produce a comprehensive report (900-1500 words). Use Markdown with clear headings, bolded key terms, and tables for data. Tone: professional, technical, concise.
```
