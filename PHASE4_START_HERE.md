# 🔥 Bond Fire - Phase 4: MQTT Shake Detection

**Status:** ✅ **IMPLEMENTATION COMPLETE - TESTING REQUIRED**  
**Date:** February 6, 2026  
**System:** Master-Slave Architecture with Web App Control  

---

## 🚀 Quick Start

### What Changed in Phase 4?
**Phone detection via computer vision has been replaced with a web app + MQTT shake detection system.**

Old way: YOLOv8 tries to detect phones → unreliable, jittery  
New way: Users shake their phones → web app reports to MQTT → Python aggregates → reliable wind control

### System Status
- ✅ Vision system updated (phone detection removed)
- ✅ State machine simplified (3 states: IDLE, FIRE, PARTY)
- ✅ MQTT shake listener implemented
- ✅ Hardware updated (removed PHONE_IDLE/FANNING states)
- ✅ Projection updated (3 states only)
- ✅ Web app created ([webapp/index.html](webapp/index.html))
- ⚠️ **Requires testing** - system not yet validated end-to-end

---

## 📋 Phase 4 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    BOND FIRE PHASE 4                         │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  👥 Users (Mobile Devices)                                   │
│   │                                                           │
│   ├─> Web App (webapp/index.html)                           │
│   │   • Accelerometer shake detection                        │
│   │   • MQTT WebSocket connection                           │
│   │   • Publishes: {user_id, timestamp}                     │
│   │                                                           │
│   └─> MQTT Broker (test.mosquitto.org:8081)                 │
│       Topic: "bondfire/shakes"                               │
│                                                               │
│  🖥️  Master System (MacBook)                                │
│   │                                                           │
│   ├─> Python Vision (YOLOv8n.pt)                            │
│   │   • People detection only (no phone)                     │
│   │   • MQTT ShakeListener subscribes to shake events        │
│   │   • Aggregates: 0-5 concurrent shakes → 0-100 wind      │
│   │   • Simplified state machine (3 states)                  │
│   │   • Broadcasts UDP packets (v2.1 protocol)              │
│   │                                                           │
│   └─> Projection System (Pygame)                            │
│       • Receives UDP packets                                 │
│       • 3 visual states (IDLE/FIRE/PARTY)                    │
│       • Wind-driven particle effects                          │
│                                                               │
│  🔌 Slave System (ESP32)                                     │
│   │                                                           │
│   ├─> Hardware Controller                                    │
│   │   • LED ring (59 LEDs)                                   │
│   │   • LED matrix (32x8 scrolling text)                     │
│   │   • Mist pump (PWM)                                      │
│   │   • Fan motor (PWM)                                      │
│   │                                                           │
│   └─> 3 animation states                                     │
│       • IDLE: Cool blue                                      │
│       • FIRE: Orange flames                                  │
│       • PARTY: Rainbow effects                               │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 🎮 Testing the System

### 1. Test Vision System (No MQTT)
```bash
cd vision
source env/bin/activate
bond-fire-vision --display
```
**Expected behavior:**
- Window shows camera feed with people detection
- Wind bar shows 0% (no MQTT shakes yet)
- Status shows 3 states only: IDLE, FIRE, PARTY
- No phone detection bounding boxes

### 2. Test MQTT Shake Publishing
```bash
# Terminal 1: Run vision system
cd vision && source env/bin/activate
bond-fire-vision --display

# Terminal 2: Publish test shakes
cd vision && source env/bin/activate
python test_mqtt_shakes.py --continuous --users 3
```
**Expected behavior:**
- Vision system console shows "Shake received from test_user_0"
- Wind bar increases (3 users → 60% wind)
- UDP packets sent with wind=60

### 3. Test Web App (Mobile Device)
```bash
# Serve web app locally
cd webapp
python3 -m http.server 8000

# On mobile (same WiFi network):
# Open: http://<your-mac-ip>:8000
```
**Expected behavior:**
- Page loads with "Connected - Ready to Fan!"
- Shake phone → visual pulse animation
- Check vision system console for received shake events

### 4. Test Full System (Vision + Hardware)
```bash
# Terminal 1: Vision system
cd vision && source env/bin/activate
bond-fire-vision --display

# Terminal 2: Test shakes
cd vision && source env/bin/activate
python test_mqtt_shakes.py --continuous --users 5
```
**Expected behavior:**
- Vision system receives shakes
- UDP packets broadcast with wind=100 (5 users)
- ESP32 receives packets and adjusts fan/mist PWM
- LED ring brightness increases with wind

---

## 📁 Key Files

### Vision System
- `vision/config.yaml` - MQTT configuration
- `vision/src/bond_fire_vision/mqtt_shake.py` - ShakeListener class
- `vision/src/bond_fire_vision/state_machine.py` - 3-state machine
- `vision/src/bond_fire_vision/detector.py` - Main vision loop
- `vision/test_mqtt_shakes.py` - Test script for shake events

### Web App
- `webapp/index.html` - Single-page web app (standalone)
- `webapp/README.md` - Deployment and configuration guide

### Hardware
- `hardware/bondfire-v2/bondfire-v2.ino` - ESP32 firmware (3 states)

### Projection
- `projection/projection_app.py` - Visual effects system
- `projection/config.yaml` - State color palettes

### Documentation
- `PHASE4_MQTT_MIGRATION.md` - Complete technical guide
- `00_START_HERE.md` - This file

---

## 🔧 Configuration

### MQTT Settings (vision/config.yaml)
```yaml
mqtt:
  enabled: true
  broker: test.mosquitto.org
  port: 1883
  topic: bondfire/shakes
  wind_max: 100
  shake_timeout: 2000      # How long a shake counts (ms)
  max_concurrent_shakes: 5  # Max simultaneous contributors
```

### Web App Settings (webapp/index.html)
```javascript
const MQTT_BROKER = 'wss://test.mosquitto.org:8081';
const MQTT_TOPIC = 'bondfire/shakes';
const SHAKE_THRESHOLD = 20; // m/s² acceleration
const SHAKE_COOLDOWN = 500; // ms between shakes
```

### State Machine (3 states only)
- **IDLE**: 0 people → cool blue, no mist
- **FIRE**: 1-3 people → orange flames, light mist
- **PARTY**: 4+ people → rainbow effects, full mist/fan

---

## 🐛 Troubleshooting

### Vision system shows "Import paho.mqtt could not be resolved"
```bash
cd vision && source env/bin/activate
pip install paho-mqtt
```

### No shake events received
1. Check MQTT broker connectivity: `ping test.mosquitto.org`
2. Verify topic matches in config.yaml and web app
3. Check firewall allows port 1883 (MQTT) and 8081 (WebSocket)
4. Test with `test_mqtt_shakes.py` script first

### Web app doesn't detect shakes
1. Check browser console for errors
2. Allow motion sensor permission (iOS Settings → Safari)
3. Try tapping the fire button as fallback
4. Increase shake threshold if too sensitive

### Wind doesn't affect hardware
1. Verify UDP packets contain wind field: `python vision/packet_listener.py`
2. Check ESP32 serial monitor for "Wind:" value
3. Ensure fan/mist pins connected properly
4. Test with manual UDP packets: `python vision/manual_packet_sender.py`

---

## 📊 System States

### State Transitions
```
IDLE (0 people)
  │
  ├─> FIRE (1-3 people detected)
  │     │
  │     └─> PARTY (4+ people detected)
  │           │
  │           └─> FIRE (people leave, 1-3 remain)
  │                 │
  │                 └─> IDLE (all people leave)
```

### Wind Calculation
```
Concurrent Shakes → Wind Value
─────────────────────────────
0 shakes         → 0% wind
1 shake          → 20% wind
2 shakes         → 40% wind
3 shakes         → 60% wind
4 shakes         → 80% wind
5 shakes         → 100% wind (max)
```

---

## 🚢 Deployment

### Web App Deployment
```bash
# Option 1: GitHub Pages (recommended)
git checkout --orphan gh-pages
git add webapp/*
git commit -m "Deploy Phase 4 web app"
git push origin gh-pages

# Access at: https://<username>.github.io/<repo>/webapp/

# Option 2: Local network (testing)
cd webapp && python3 -m http.server 8000
# Access at: http://<mac-ip>:8000
```

### Production MQTT Broker (optional)
For production use, deploy a private MQTT broker:
```bash
# Install Mosquitto
sudo apt install mosquitto

# Configure WebSocket support
# /etc/mosquitto/conf.d/websockets.conf:
listener 8081
protocol websockets

# Restart
sudo systemctl restart mosquitto
```

---

## 📚 Documentation

### Full Technical Docs
- [PHASE4_MQTT_MIGRATION.md](PHASE4_MQTT_MIGRATION.md) - Complete migration guide
- [webapp/README.md](webapp/README.md) - Web app deployment and troubleshooting
- [vision/CONFIG.md](vision/CONFIG.md) - Vision system configuration reference

### Previous Phases
- [PHASE_3_SUMMARY.md](PHASE_3_SUMMARY.md) - Phase 3 ESP32 firmware
- [PHASE_3_QUICKSTART.md](PHASE_3_QUICKSTART.md) - Hardware testing guide
- [project-readme.md](project-readme.md) - Original project overview

---

## 🎯 Next Steps

### Immediate (Required)
1. ✅ System implementation complete
2. ⚠️ **Test vision system with MQTT test script**
3. ⚠️ **Test web app shake detection on mobile device**
4. ⚠️ **Validate end-to-end flow (web app → MQTT → vision → hardware)**
5. ⚠️ **Deploy web app to GitHub Pages or static hosting**

### Future Enhancements
- [ ] Progressive Web App (install to home screen)
- [ ] User leaderboard (top fans)
- [ ] Real-time wind visualization in web app
- [ ] Private MQTT broker with authentication
- [ ] Multiple installation support
- [ ] Analytics dashboard

---

## 🤝 Support

### Common Issues
- See [PHASE4_MQTT_MIGRATION.md](PHASE4_MQTT_MIGRATION.md) for detailed troubleshooting
- Check vision system logs: `bond-fire-vision --display`
- Monitor MQTT traffic: `mosquitto_sub -h test.mosquitto.org -t bondfire/shakes`
- Watch UDP packets: `python vision/packet_listener.py`

### Project Structure
```
bond-fire/
├── vision/                 # Python vision system
│   ├── src/bond_fire_vision/
│   │   ├── detector.py    # Main vision loop (YOLOv8 + MQTT)
│   │   ├── mqtt_shake.py  # ShakeListener class
│   │   └── state_machine.py  # 3-state logic
│   ├── config.yaml        # System configuration
│   └── test_mqtt_shakes.py  # Testing tool
├── webapp/                # Web app for shake detection
│   ├── index.html        # Single-page app
│   └── README.md         # Deployment guide
├── hardware/             # ESP32 firmware
│   └── bondfire-v2/
│       └── bondfire-v2.ino  # 3-state controller
├── projection/           # Pygame visual effects
│   ├── projection_app.py
│   └── config.yaml
└── docs/                # Documentation
    ├── PHASE4_MQTT_MIGRATION.md
    └── 00_START_HERE.md (this file)
```

---

**Last Updated:** February 6, 2026  
**System Version:** Phase 4 - MQTT Shake Detection  
**Status:** ✅ Implementation complete, testing required
