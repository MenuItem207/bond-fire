# Projection Mapping (Bond Fire)

This app listens to the existing UDP packets and renders a projector-safe mapping surface with ambient visuals and text prompts.

## Setup

```bash
cd projection
python3 -m venv env && source env/bin/activate
pip install -r requirements.txt
```

## Run

```bash
cd projection && source env/bin/activate && python projection_app.py --config config.yaml --port 4210
```

From the repo root:

```bash
python projection/projection_app.py --config projection/config.yaml --port 4210
```

Fullscreen:

```bash
python projection_app.py --config config.yaml --port 4210 --fullscreen
```

Demo mode (no UDP):

```bash
python projection_app.py --config config.yaml --no-udp
```

## Calibration

Press `c` to toggle calibration overlay. Use arrow keys to move the active corner, `Tab` to cycle corners, and `Enter` to save to config. Hold `Shift` for larger steps. Press `t` to toggle text.

Circle + Ring (live adjustments):

- `[` / `]` decrease/increase center circle radius
- `,` / `.` decrease/increase ring gap
- `-` / `=` decrease/increase ring thickness
- `s` to save the current circle + ring values to config

## Notes

- Mapping quad points are normalized (0..1). Match them to your physical surface.
- The visuals respond to `state`, `fire_intensity`, `dominant_palette`, `pulse_active`, and `party_buildup_progress`.
- Text prompts are pulled from the packet `prompt` field.
- `wind` (0-100) boosts the fire intensity for wind-driven visuals.

## Video Layer (Optional)

Enable the video layer in [projection/config.yaml](projection/config.yaml):

```yaml
video:
	enabled: true
	path: "assets/video/fire.mp4"
	mix: 0.35
	alpha: 1.0
	colorize: 0.6
	speed: 1.0
	loop: true
```

The video is blended in the shader and can be colorized by the current state.
