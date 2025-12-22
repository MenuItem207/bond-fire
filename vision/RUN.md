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

## Optional Flags

- `--model /path/to/weights.pt` — override the YOLOv8 weights file.
- `--roi 0.15 0.25 0.85 0.9` — set a custom active zone (normalized coordinates).
- `--confidence 0.6` — require a higher detection confidence.
- `--no-display` — run headless and log state changes in the console.
- `--broadcast-ip 255.255.255.255` — change the UDP destination (defaults to broadcast).
- `--broadcast-port 4210` — match the listening port on the ESP32.
- `--updates-per-second 20` — lower the broadcast rate if the microcontroller struggles to keep up.
