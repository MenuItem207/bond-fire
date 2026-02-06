# Vision System - Setup & Execution Guide

The Bond Fire vision system detects people and phones in real-time using YOLOv8, manages state transitions, broadcasts UDP packets to ESP32, and provides optional audio feedback.

---

## 🚀 Quick Start (5 minutes)

### 1. Setup Environment

```bash
cd vision
python3.13 -m venv env
source env/bin/activate
pip install --upgrade pip
pip install -e .
```

### 2. Run Basic Vision (Camera Only)

```bash
bond-fire-vision --camera-index 0
```

Press `q` to exit. You should see:
- Video preview with bounding boxes
- Detected people highlighted in blue
- Detected phones highlighted in red
- Console output showing state changes

### 3. Run with Audio & Narration

```bash
bond-fire-vision --camera-index 0 --enable-audio --narration-enabled
```

Features enabled:
- ✅ Sound effects for state transitions
- ✅ Background music in ambient/party modes
- ✅ Text-to-speech narration (uses Daniel voice by default)
- ✅ Party horn + celebration when phone removed

---

## ⚙️ Essential Flags

| Flag | Purpose | Example | Default |
|------|---------|---------|---------|
| `--camera-index` | Video input device | `0` (built-in) | Required |
| `--enable-audio` | Activate audio system | (no value) | Disabled |
| `--narration-enabled` | Add TTS narration | (no value) | Off |
| `--tts-voice` | Voice name | `"daniel"` | Auto-select |
| `--roi` | Active detection zone | `0.15 0.25 0.85 0.9` | Full frame |
| `--confidence` | Detection threshold | `0.6` | 0.5 |
| `--no-display` | Run headless (no preview) | (no value) | Display on |
| `--broadcast-ip` | UDP destination | `255.255.255.255` | Broadcast |
| `--broadcast-port` | UDP port | `4210` | 4210 |
| `--updates-per-second` | Broadcast rate | `30` | 30 |

### Common Scenarios

**Testing Vision Only:**
```bash
bond-fire-vision --camera-index 0 --no-display
```

**Faster Updates (for debug):**
```bash
bond-fire-vision --camera-index 0 --updates-per-second 60
```

**Custom Active Zone:**
```bash
bond-fire-vision --camera-index 0 --roi 0.2 0.3 0.8 0.9
```

**Specific UDP Destination:**
```bash
bond-fire-vision --camera-index 0 --broadcast-ip 192.168.1.100
```

---

## 🔧 Configuration

All timing and parameter values are in `vision/config.yaml`:

```yaml
state_machine:
  phone_exit_dwell: 0.5       # Hysteresis (seconds)
prompts:
  normal_cooldown: 10         # Min time between prompts
audio:
  master_volume: 0.7
  tts:
    speech_rate: 140          # Words per minute
```

**To change values:** Edit `config.yaml` and restart the vision system. No code changes needed.

See [CONFIG.md](CONFIG.md) for all available settings.

---

## 🧪 Helper Tools

### Manual Packet Sender (Test Packets)

Craft and broadcast test UDP packets without needing the vision system:

```bash
# Interactive mode
python manual_packet_sender.py --interactive

# Preset scenarios
python manual_packet_sender.py ghost    # Empty installation
python manual_packet_sender.py idle     # 0 people
python manual_packet_sender.py party    # 5 people

# Custom packets
python manual_packet_sender.py --count 3 --text "Hi there"

# Stream continuously at 2 Hz
python manual_packet_sender.py --repeat 0 --rate 2
```

### Packet Listener (Monitor Broadcast)

Watch UDP packets being sent to ESP32 in real-time:

```bash
# Formatted output
python packet_listener.py

# Raw JSON output
python packet_listener.py --raw

# Hexadecimal format
python packet_listener.py --hex

# Custom port
python packet_listener.py --port 4210
```

Displays:
- State machine state (IDLE, FIRE, PARTY, PHONE)
- Number of detected people with IDs
- Dominant color palette (RGB values)
- Prompt text
- PWM values (mist, fan)
- Active effects (pulse, buildup, celebration)
- Audio state

### List Available Voices

See all TTS voices installed on your Mac:

```bash
python list_voices.py
```

Sample output:
```
Available macOS voices (184 total):
  - Daniel (British, recommended)
  - Grandpa
  - Rocko
  - Reed
  - Alex
  ... and more
```

### Integration Tests

Verify all modules are correctly configured:

```bash
python test_integration.py
```

Output shows:
- ✅ Config loading
- ✅ State machine integration
- ✅ Prompt generator integration
- ✅ Audio manager integration
- ✅ All values from YAML

---

## 🐛 Troubleshooting

### "Camera not found"
```
Error: Could not open camera at index 0
```
**Fix:** Try different indices:
```bash
bond-fire-vision --camera-index 1
bond-fire-vision --camera-index 2
```

### "Audio disabled: pygame.mixer not available"
```
Warning: Audio disabled: pygame.mixer not available
```
**Fix:** Reinstall pygame:
```bash
pip install --upgrade pygame
```

### "Vision detects people, but state doesn't change"
**Possible Causes:**
- ROI doesn't include your location (`--roi 0 0 1 1` for full frame)
- Confidence threshold too high (`--confidence 0.3` to be more sensitive)

**Debug:** Add verbose logging in `config.yaml`:
```yaml
debug:
  verbose_logging: true
```

### "Config.yaml not found"
**Fix:** Make sure it's in the vision directory:
```bash
ls vision/config.yaml
```

Or set the path:
```bash
export BOND_FIRE_CONFIG=~/.config/bond-fire/config.yaml
```

### "UDP packets not reaching ESP32"
**Verification Steps:**
1. Check both devices on same hotspot
2. Run `packet_listener.py` to confirm broadcast
3. Disable Mac firewall or add Python to exceptions

```bash
python packet_listener.py
```

### "TTS voice not working"
```bash
python list_voices.py
bond-fire-vision --camera-index 0 --narration-enabled --tts-voice "daniel"
```

---

## 📊 Monitoring

### Enable Verbose Logging

Edit `vision/config.yaml`:
```yaml
debug:
  verbose_logging: true       # Show state transitions
  log_prompts: true          # Show all generated prompts
```

### Monitor Packets in Real-Time

```bash
# Terminal 1: Vision system
bond-fire-vision --camera-index 0 --enable-audio

# Terminal 2: Monitor packets
python packet_listener.py
```

### Validate Installation

```bash
python test_integration.py
```

---

## 🔌 Network Setup

### 1. Create Personal Hotspot (iPhone)
Settings → Personal Hotspot → WiFi Password

### 2. Connect Mac
WiFi icon → Select your hotspot → Enter password

### 3. Connect ESP32
In Arduino code: `WiFi.begin(ssid, password)`

### 4. Test Connection
```bash
python packet_listener.py
```

Should show packets every ~33ms.

---

## 📚 Documentation

- [project-readme.md](../project-readme.md) - System overview
- [CONFIG.md](CONFIG.md) - Configuration reference  
- [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) - Full technical details
- Source: `src/bond_fire_vision/` (7 Python modules)

---

## ⏱️ Next Phase

**Phase 3 (ESP32 Firmware):** See [PHASE_3_GUIDE.md](../PHASE_3_GUIDE.md)
