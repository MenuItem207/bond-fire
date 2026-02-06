# Run Instructions

Follow these steps to create an isolated environment and launch the vision detector:

1. Change into the vision project directory:
   ```bash
   cd vision
   ```
2. Create and activate a Python 3.13 virtual environment:
   ```bash
   python3.13 -m venv env
   source env/bin/activate
   ```
3. Upgrade pip and install the vision package along with its dependencies in editable mode:
   ```bash
   pip3.13 install --upgrade pip
   pip3.13 install -e .
   ```
4. Ensure both your Mac and ESP32 are connected to the same hotspot (the Mac will broadcast UDP packets on that network). Disable or allow Python through the macOS firewall if prompted.

5. Run the detector (press `q` to exit the preview window):
   ```bash
   bond-fire-vision --camera-index 0
   ```

### With Audio System

Enable sound effects and optional text-to-speech narration:

```bash
bond-fire-vision --camera-index 0 --enable-audio --narration-enabled
```

Features:
- Entry detection: Whoosh sound effect
- Color pulse: Soft chime every 15 seconds
- Party entry: Build-up SFX (start + progressive pulses)
- Phone detection: Alert buzzer
- Phone exit: Party horn + celebration narration (if enabled)
- Optional: Text-to-speech reads state-aware prompts

### Legacy: OpenAI Prompts (Deprecated)

**Note:** OpenAI integration was removed in v2. The system now uses local, curated prompts that are instant and deterministic. The following flags are no longer functional:

- `--ai-prompts` (ignored)
- `--ai-api-key` (ignored)
- `--ai-interval` (ignored)
- `--ai-model` (ignored)

### Manual Packet Sender

Use the CLI helper to craft and broadcast test payloads:

```bash
python manual_packet_sender.py --interactive
```

Common options:

- `python manual_packet_sender.py ghost` — send a single preset packet.
- `python manual_packet_sender.py --count 3 --text "Hey there"` — override people count and text.
- `python manual_packet_sender.py --repeat 0 --rate 2` — stream packets continuously at 2 Hz until Ctrl+C.
### Packet Listener (Debugging)

Monitor UDP packets being broadcast to ESP32 in real-time without hardware:

```bash
python packet_listener.py
```

This displays:
- Incoming state machine state (IDLE, FIRE, PARTY, PHONE)
- Detected people count and tracked individuals
- Dominant color palette with RGB visualization
- Current text prompt
- Hardware PWM values (mist, fan)
- Active effects (pulse, entry flash, build-up progress)
- Audio state and celebration flag

Optional flags:

- `--port 4210` — listen on a specific UDP port (default: 4210).
- `--raw` — show raw JSON instead of formatted output.
- `--hex` — display packets in hexadecimal format.
## Optional Flags

- `--model /path/to/weights.pt` — override the YOLOv8 weights file.
- `--roi 0.15 0.25 0.85 0.9` — set a custom active zone (normalized coordinates).
- `--confidence 0.6` — require a higher detection confidence.
- `--no-display` — run headless and log state changes in the console.
- `--broadcast-ip 255.255.255.255` — change the UDP destination (defaults to broadcast).
- `--broadcast-port 4210` — match the listening port on the ESP32.
- `--updates-per-second 20` — lower the broadcast rate if the microcontroller struggles to keep up.
