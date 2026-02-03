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

### Enable AI-Generated Prompts

1. Set your OpenAI API key (or pass via `--ai-api-key`):
   ```bash
   export BOND_FIRE_OPENAI_API_KEY=sk-...
   ```
2. Launch the detector with AI prompts (frames sampled every 5 s by default):
   ```bash
   bond-fire-vision --camera-index 0 --ai-prompts --ai-interval 5
   ```
   - Console logs will show when the AI worker starts and whenever it updates the prompt.
   - Environment overrides:
     - `BOND_FIRE_OPENAI_MODEL` (defaults to `gpt-4o-mini`)
     - `BOND_FIRE_AI_INTERVAL`, `BOND_FIRE_AI_TEMPERATURE`, `BOND_FIRE_AI_PROMPT_TTL`

### Manual Packet Sender

Use the CLI helper to craft and broadcast test payloads:

```bash
python manual_packet_sender.py --interactive
```

Common options:

- `python manual_packet_sender.py ghost` — send a single preset packet.
- `python manual_packet_sender.py --count 3 --text "Hey there"` — override people count and text.
- `python manual_packet_sender.py --repeat 0 --rate 2` — stream packets continuously at 2 Hz until Ctrl+C.

## Optional Flags

- `--model /path/to/weights.pt` — override the YOLOv8 weights file.
- `--roi 0.15 0.25 0.85 0.9` — set a custom active zone (normalized coordinates).
- `--confidence 0.6` — require a higher detection confidence.
- `--no-display` — run headless and log state changes in the console.
- `--broadcast-ip 255.255.255.255` — change the UDP destination (defaults to broadcast).
- `--broadcast-port 4210` — match the listening port on the ESP32.
- `--updates-per-second 20` — lower the broadcast rate if the microcontroller struggles to keep up.
