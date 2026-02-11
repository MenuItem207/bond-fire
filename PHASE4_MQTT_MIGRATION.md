# Phase 4: MQTT Shake Detection Migration

## Overview
Phase 4 completely removes phone detection from the computer vision system and replaces it with a web app + MQTT architecture. This change was necessary because phone detection via YOLOv8 proved unreliable despite multiple tuning attempts (model upgrades, confidence thresholds, debouncing, persistence).

## Architecture Changes

### Old System (Phase 1-3)
- **Vision**: YOLOv8x.pt detecting people + phones (class 67)
- **States**: 5 states (IDLE, FIRE, PARTY, PHONE_IDLE, FANNING)
- **Fanning**: Tracked phone motion via X-coordinate history
- **Wind Calculation**: Python vision system calculated fan_power (0-100) from phone movement
- **Issues**: Spotty phone detection, jittery tracking, inconsistent state transitions

### New System (Phase 4)
- **Vision**: YOLOv8n.pt detecting people only (reverted to fast model)
- **States**: 3 states (IDLE, FIRE, PARTY) - simplified state machine
- **Shake Detection**: Web app publishes shake events to public MQTT broker
- **Wind Calculation**: Python MQTT listener aggregates shake events → wind value (0-100)
- **Benefits**: Reliable accelerometer data, no CV false positives, better performance

## Implementation Details

### 1. MQTT Configuration (config.yaml)
```yaml
mqtt:
  enabled: true
  broker: test.mosquitto.org
  port: 1883
  topic: bondfire/shakes
  wind_max: 100
  shake_timeout: 2000  # ms - how long a shake event counts
  max_concurrent_shakes: 5  # max simultaneous shake contributors
```

### 2. Shake Listener (mqtt_shake.py)
- **ShakeListener class**: Manages MQTT client connection
- **Shake Tracking**: Stores user_id → timestamp mapping
- **Wind Calculation**: Maps 0-5 concurrent active shakes → 0-100 wind value
- **Cleanup**: Removes stale shake events after timeout (default 2s)
- **Thread Safety**: Runs MQTT loop in background thread

### 3. State Machine Simplification (state_machine.py)
- **Removed**: State.PHONE_IDLE, State.FANNING
- **StateContext**: Removed phone_detected and fan_power fields
- **StateOutput**: Removed phone_just_exited flag
- **Transitions**: Simplified to IDLE ↔ FIRE ↔ PARTY only

### 4. Vision System Updates (detector.py)
- **Removed**: All CLASS_PHONE detection logic
- **Removed**: Phone X-coordinate tracking, debouncing, persistence
- **Removed**: _compute_fan_movement() method
- **Added**: ShakeListener initialization and lifecycle management
- **Wind Source**: Now gets wind value from shake_listener.get_wind_value()
- **Display**: Wind bar shows MQTT shake-based wind instead of phone fanning

### 5. Prompt System Updates (local_prompts.py)
- **Removed**: PHONE_IDLE_PROMPTS, FANNING_PROMPTS, PHONE_EXIT_PROMPTS
- **Removed**: get_phone_exit_prompt() method
- **Removed**: Phone-specific cooldown logic
- **Simplified**: Only generates prompts for 3 states

### 6. Hardware Updates (bondfire-v2.ino)
- **Removed**: STATE_PHONE_IDLE, STATE_FANNING from enum
- **Removed**: Phone state cases from color transitions
- **Removed**: Phone fallback text ("Fan the flames", "Keep fanning")
- **Removed**: Phone state rendering cases
- **Simplified**: State parsing only handles IDLE/FIRE/PARTY

## Files Modified

### Vision System
- ✅ `vision/config.yaml` - Removed phone/fanning config, added MQTT section
- ✅ `vision/src/bond_fire_vision/config.py` - Updated dataclasses (removed FanningConfig, added MQTTConfig)
- ✅ `vision/src/bond_fire_vision/state_machine.py` - Replaced with simplified 3-state version
- ✅ `vision/src/bond_fire_vision/mqtt_shake.py` - NEW FILE - ShakeListener implementation
- ✅ `vision/src/bond_fire_vision/detector.py` - Removed all phone detection code, integrated ShakeListener
- ✅ `vision/src/bond_fire_vision/local_prompts.py` - Removed phone-related prompts and logic
- ✅ `vision/pyproject.toml` - Added paho-mqtt>=2.0.0 dependency

### Hardware
- ✅ `hardware/bondfire-v2/bondfire-v2.ino` - Removed phone states from enum, parsing, rendering, and text fallbacks

### Projection (TODO)
- ⚠️ `projection/projection_app.py` - Need to remove PHONE_IDLE/FANNING from _state_to_index()
- ⚠️ `projection/config.yaml` - Need to remove phone states from state_palettes

### Web App (TODO)
- ⚠️ Need to create `webapp/` folder with shake detection web app
- ⚠️ HTML page with accelerometer API integration
- ⚠️ MQTT WebSocket client (paho-mqtt.js or similar)
- ⚠️ Shake threshold detection logic
- ⚠️ User ID generation and shake event publishing

## Testing Plan

### 1. Vision System Only (No MQTT)
```bash
cd vision
source env/bin/activate
bond-fire-vision --display
```
- Should show 3 states only
- Wind bar should show 0 (no MQTT connection yet)
- No errors about missing phone detection

### 2. MQTT Integration Test
```bash
# Terminal 1: Start vision system
cd vision && source env/bin/activate && bond-fire-vision --display

# Terminal 2: Publish test shake events
cd vision && source env/bin/activate
python manual_packet_sender.py  # May need to create MQTT test script
```

### 3. Full System Test (Vision + Hardware + Projection)
- Start all three systems
- Verify state transitions work (IDLE → FIRE → PARTY)
- Test manual UDP wind packets
- Verify hardware responds to wind field

### 4. Web App Integration (Once Created)
- Open web app on mobile device
- Shake phone, verify events published to MQTT
- Check vision system receives events and updates wind value
- Verify hardware fan/mist respond to wind changes

## MQTT Protocol

### Topic
`bondfire/shakes`

### Message Format
```json
{
  "user_id": "abc123",
  "timestamp": 1234567890.123
}
```

### Wind Calculation
- Count unique `user_id` entries with timestamps within last 2 seconds
- Map count (0-5) to wind value (0-100) linearly
- Example: 3 concurrent shakes → 60% wind

## Web App Requirements

### Core Functionality
1. **Device Orientation Access**: Request permission to access accelerometer
2. **Shake Detection**: Detect rapid acceleration changes (threshold ~15 m/s²)
3. **Debouncing**: Prevent multiple events from single shake gesture
4. **MQTT Publishing**: Connect to test.mosquitto.org:1883 via WebSocket
5. **User ID**: Generate stable client ID (localStorage + UUID)

### UI Elements
- Simple landing page with "Start Fanning" button
- Connection status indicator (MQTT connected/disconnected)
- Shake detection feedback (visual pulse when shake detected)
- Wind contribution indicator (show current shake count)

### Technical Stack Options
1. Vanilla HTML + paho-mqtt.js (lightest)
2. React + MQTT.js (if framework preferred)
3. Progressive Web App (for install-to-homescreen)

## Next Steps

### Immediate (Required for Testing)
1. ⚠️ Update projection system to remove phone states
2. ⚠️ Create basic web app with shake detection
3. ⚠️ Test end-to-end with manual MQTT events
4. ⚠️ Update documentation (README, 00_START_HERE.md)

### Future Enhancements
- Web app UI improvements (install prompt, offline support)
- Analytics dashboard showing shake participation
- Multiple MQTT topics for different installations
- Private MQTT broker instead of public test broker
- Authentication and rate limiting

## Migration Notes

### Breaking Changes
- Vision system no longer detects phones
- State machine API changed (removed phone_detected, fan_power from StateContext)
- UDP packets still include `wind` field but source changed
- Hardware state enum reduced from 5 to 3 states

### Backward Compatibility
- UDP packet format unchanged (v2.1)
- Wind field still transmitted (0-100)
- Hardware can gracefully ignore unknown states

### Configuration Migration
Old config files with phone/fanning sections will ignore those values. No manual migration needed - system uses defaults for missing MQTT config.

## Rollback Plan
If Phase 4 needs to be reverted:
1. `git restore vision/src/bond_fire_vision/state_machine_old.py` → state_machine.py
2. Restore old config.yaml from version control
3. Restore old detector.py (has phone detection code)
4. `pip uninstall paho-mqtt`
5. Restore old hardware .ino file
6. Rebuild and upload hardware firmware

## Performance Impact
- **Vision FPS**: Improved (yolov8n.pt instead of yolov8x.pt)
- **CPU Usage**: Reduced (fewer detections, simpler state machine)
- **Network**: Added MQTT connection but minimal bandwidth (~10 bytes/shake)
- **Latency**: Better shake → wind responsiveness (no CV false positives)
