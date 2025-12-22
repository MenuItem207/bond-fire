
# The Empathic Hearth

**A Socially Responsive Digital Campfire**

> **"Fire grows when we gather. Fire dies when we disconnect."**

### 📖 Project Overview

**The Empathic Hearth** is an interactive installation designed for *SCAPE Singapore to combat "social islands" among youths. It uses Computer Vision and a responsive "mist flame" to gamify physical proximity.

The installation acts as a **Social Battery Charger**. The "fire" visualizes the group's size, starting weak and growing progressively stronger as more people join. It requires a "Critical Mass" of **5 people** to trigger the hidden "Supernova" celebration.

---

### 🔌 Data Communication (UDP Protocol)

The system uses a **One-Way UDP Broadcast**. The Mac (Brain) analyzes the scene and broadcasts a JSON packet to the ESP32 (Body) 30 times a second.

#### **The Packet Structure**

The Mac sends a JSON object containing exactly three data points:

```json
{
  "c": 3,           // Count: Number of people detected (Integer)
  "p": false,       // Phone: Is a phone visible? (Boolean)
  "t": "Message"    // Text: Context-aware prompt to scroll (String)
}

```

#### **Scenario Examples**

**1. The "Idle" Packet (0 Pax)**

* *Context:* Empty installation.
* *Mac Logic:* `c=0`, `p=false`. Selects "Lure" text.
* *ESP32 Action:* Mist OFF. LEDs breathe Blue. Text scrolls.

```json
{ "c": 0, "p": false, "t": "Social Battery: 0%. I need a spark..." }

```

**2. The "Building" Packet (3 Pax)**

* *Context:* 3 friends sitting together.
* *Mac Logic:* `c=3`, `p=false`. Selects "Nudge" text.
* *ESP32 Action:* Mist at 60% intensity. Fan Medium. LEDs Orange.

```json
{ "c": 3, "p": false, "t": "Battery at 60%. We need 2 more humans!" }

```

**3. The "Penalty" Packet (Phone Detected)**

* *Context:* Someone pulls out a smartphone.
* *Mac Logic:* `c=3`, `p=true`. Overrides text with warning.
* *ESP32 Action:* **Immediate Override.** Mist CUTS (0%). LEDs Glitch Grey.

```json
{ "c": 3, "p": true, "t": "SIGNAL INTERFERENCE. DISCONNECT TO CONNECT." }

```

---

### 🧠 The Logic: "The Social Battery"

The installation operates on a **0% to 100% Scale**. Every person adds ~20% charge to the fire.

| Pax Count (`c`) | State Name    | Fire Intensity   | LED Visuals              | Text Strategy (`t`)                                      |
| --------------- | ------------- | ---------------- | ------------------------ | -------------------------------------------------------- |
| **0**           | **GHOST**     | **OFF** (0%)     | **Breathing Blue/Teal**  | **Lure:** *"I need a spark..."*                          |
| **1**           | **SPARK**     | **Weak** (20%)   | **Dim Amber**            | **Hint:** *"One is a start... Battery: 20%."*            |
| **2**           | **KINDLE**    | **Low** (40%)    | **Warm Orange**          | **Icebreaker:** *"Ask them: What's your hidden talent?"* |
| **3**           | **FLAME**     | **Medium** (60%) | **Bright Orange**        | **Nudge:** *"Battery 60%. We need 2 more!"*              |
| **4**           | **BLAZE**     | **High** (80%)   | **Red/Gold**             | **Tease:** *"So close! Find ONE more human!"*            |
| **5+**          | **SUPERNOVA** | **MAX** (100%)   | **Rainbow / Sparkles**   | **Reward:** *"CRITICAL MASS ACHIEVED!"*                  |
| **Any**         | **PENALTY**   | **CUT** (0%)     | **Static Grey / Glitch** | **Shame:** *"Phone Detected."*                           |

---

### 🛠️ Hardware Stack (Tethered Architecture)

* **Compute:** MacBook running Python + YOLOv8 + OpenAI API.
* **Connectivity:** **Phone Hotspot** (The Bridge). Laptop & ESP32 connect to this Personal Hotspot.
* **Controller:** ESP32 Dev Module (UDP Listener).
* **Power:** 5V 10A Switching PSU + Switched Mains Cable.
* **Actuators:**
* **Mist:** 5V USB Ultrasonic Mist Maker Kit controlled via MOSFET.
* **Wind:** 60mm 5V Waterproof Fan controlled via MOSFET.


* **Lighting:**
* **Fire:** WS2812B LED Ring (24/35 LED).
* **Voice:** WS2812B Flexible Matrix (8x32).



---

### 🗓️ Prototyping Plan (Modular Build)

#### **Module 1: The AI Brain (Software)**

* **Focus:** Packet Generation.
* **Task:** Write `main.py` to detect `pax` count and form the JSON packet `{ "c": x, "p": y, "t": z }`.
* **Check:** Verify console output matches the JSON structure above.

#### **Module 2: The Wireless Link**

* **Focus:** Connectivity.
* **Task:** Connect Laptop and ESP32 to Phone Hotspot.
* **Check:** ESP32 Serial Monitor prints the received JSON string instantly.

#### **Module 3: Visuals & Power**

* **Focus:** The "Look."
* **Task:** Code the 5 distinct fire animations (Blue -> Dim Amber -> Orange -> Red -> Rainbow).
* **Check:** Does the "Glitch" effect trigger when `p: true` is received?

#### **Module 4: The Physics**

* **Focus:** The Mist.
* **Task:** Map the `c` (Count) integer to PWM duty cycles.
* `c=1`: 20% Fan Speed, 200ms Mist Pulses.
* `c=5`: 100% Fan Speed, Constant Mist.



#### **Module 5: Integration**

* **Focus:** Final Experience.
* **Task:** Assemble into housing. Water seal test.
* **Check:** Full run-through with 5 friends to hit "Supernova."