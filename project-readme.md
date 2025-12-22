# The Empathic Hearth

**A Socially Responsive Digital Campfire**

> **"Fire grows when we gather. Fire dies when we disconnect."**

### 📖 Project Overview

**The Empathic Hearth** is an interactive installation designed for *SCAPE Singapore to combat "social islands" among youths. It uses Computer Vision and a responsive "mist flame" to gamify physical proximity.

Beyond just lighting up, the installation acts as an **AI Host**. It observes the crowd dynamics (e.g., awkward distance, silence, phone usage) and generates unique, context-aware scrolling prompts to actively bridge the social gap.

---

### 🧠 The Logic: "Social Physics"

The installation operates as a Finite State Machine (FSM) driven by real-time computer vision and an LLM-based Text Generator.

| State Name               | Trigger Condition        | Visual Effect (LEDs)                            | Physical Effect (Mist & Fan)              | The "AI Host" (Generated Text)                                                                                                           |
| ------------------------ | ------------------------ | ----------------------------------------------- | ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **0. GHOST (Idle)**      | 0 People detected.       | **Breathing Blue/Teal.** (Cold, lonely).        | **OFF.** Silence.                         | **Lure Prompts:** *"It's cold alone..."*, *"I need a spark to start."*                                                                   |
| **1. SPARK (Engaged)**   | 1-2 People detected.     | **Flickering Orange.** (Warm candlelight).      | **Level 1 (Low).** Gentle wisps.          | **Contextual Icebreakers:** *"I see two strangers. Who traveled further to get here?"*, *"Silence is loud. Ask them about their shoes."* |
| **2. BONFIRE (Party)**   | 3+ People detected.      | **Roaring Red/Gold + Sparkles.** (High Energy). | **Level 3 (Max).** Tall, turbulent flame. | **Group Challenges:** *"Three's a crowd, but a fun one. Who is the funniest?"*, *"Connection Ignited!"*                                  |
| **99. GLITCH (Penalty)** | **Smartphone detected.** | **Static Grey/White.** (Digital interference).  | **CUT.** Immediate shutoff.               | **Shame/Nudge:** *"The fire feeds on attention, not Wi-Fi."*, *"Disconnect to Connect."*                                                 |

---

### 🛠️ Hardware Stack

The system uses a **Tethered Architecture**: A laptop handles the heavy AI processing (Vision + Text Generation), while an ESP32 handles the high-speed electrical switching.

#### **A. The Brain (Computer Vision & Generation)**

* **Compute:** Laptop running Python 3.10+ (hidden in base).
* **Vision:** Standard USB Webcam (1080p, Wide Angle).
* **Software Stack:**
* **Vision:** `Ultralytics YOLOv8` (Detects 'Person', 'Cell Phone').
* **Generation:** `OpenAI API` (or Local LLM like `Ollama`). The Python script sends scene data (e.g., "2 people, sitting far apart") to the AI to generate a 1-sentence prompt.
* **Comms:** `Socket` (UDP) to talk to ESP32.



#### **B. The Bridge (Controller)**

* **MCU:** **ESP32 Dev Module**.
* **Protocol:** UDP over Wi-Fi (Receives JSON packets from Laptop).
* **Role:** Parses state commands, manages micro-timing for LEDs/Mist, and **scrolls the text string** received from the Laptop.

#### **C. The Muscle (Actuators & Effects)**

* **Power:** **5V 10A Switching Power Supply** (Metal Brick) + Switched Mains Cable.
* **The Mist:** 5V USB Ultrasonic Mist Maker Kit (Driver Board + Disc).
* **The Wind:** **60mm 5V Waterproof Fan** (pushes mist upwards).
* **The Switch:** **MOSFET Trigger Modules (x2)** (IRF520) for PWM control of Mist & Fan.
* **The Light:**
* **WS2812B LED Ring (24/35 LED)**: Under-lights the mist.
* **WS2812B Flexible Matrix (8x32)**: Displays the AI-generated text.



---

### 🗓️ Prototyping Plan (Modular Build)

We will build and test in isolated sections to minimize risk.

#### **Module 1: The AI Brain (Software Only)**

* **Goal:** Verify Vision + **Text Generation**.
* **Action:** Write `main.py` using YOLOv8. Integrate a simple API call (e.g., `client.chat.completions.create`) that takes the `person_count` and generates a string.
* **Success Metric:** Console prints: `Status: ENGAGED | AI says: "Ask the person next to you about their lunch."`

#### **Module 2: The Nervous System (Connectivity)**

* **Goal:** Establish wireless link.
* **Action:** Flash ESP32 with `main.ino`. Run Python script.
* **Success Metric:** The generated text string from Python appears on the ESP32 Serial Monitor (and eventually the LED matrix).

#### **Module 3: The Visual Core (Lighting & Power)**

* **Goal:** Verify Power Supply and LED animations.
* **Action:** Wire PSU, ESP32, Matrix, and Ring.
* **Success Metric:** Text scrolls smoothly *while* the fire animation plays.

#### **Module 4: The Environmental Core (Mist & Fan)**

* **Goal:** Control mechanical parts with code.
* **Action:** Wire MOSFETs to Fan and Mist Maker.
* **Success Metric:** Fan speed scales with "Fire Intensity."

#### **Module 5: Integration & Assembly**

* **Goal:** The full experience.
* **Action:** Combine all modules.
* **Success Metric:** End-to-end reliability. A phone displayed to the camera triggers a "Glitch" state and specific text ("Put that away!") immediately.