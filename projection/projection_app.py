from __future__ import annotations

import argparse
import math
import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import List, Optional, Tuple

import moderngl
import moderngl_window as mglw
import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

sys.path.append(str(Path(__file__).parent))

from udp_listener import UDPListener
from visual_state import VisualState


@dataclass
class QuadConfig:
    points: List[Tuple[float, float]]


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def save_config(path: str, config: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)


def compute_homography(src: List[Tuple[float, float]], dst: List[Tuple[float, float]]) -> np.ndarray:
    if len(src) != 4 or len(dst) != 4:
        raise ValueError("Homography requires 4 source and 4 destination points")
    a = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        a.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    a = np.asarray(a, dtype=np.float64)
    _u, _s, vh = np.linalg.svd(a)
    h = vh[-1].reshape(3, 3)
    return h / h[2, 2]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class TextLayer:
    def __init__(self, size: Tuple[int, int], font_name: str, font_size: int) -> None:
        self.size = size
        self.font_name = font_name
        self.font_size = font_size
        self._font = self._load_font(font_name, font_size)
        self._image = Image.new("RGBA", size, (0, 0, 0, 0))
        self._dirty = True
        self._current_text = ""

    def _load_font(self, font_name: str, font_size: int) -> ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype(font_name, font_size)
        except OSError:
            return ImageFont.load_default()

    def update_text(
        self,
        text: str,
        position: Tuple[float, float],
        color: Tuple[int, int, int],
        box_width: float,
        max_chars: int,
        mode: str = "linear",
        circle_radius: float = 0.35,
        start_angle_deg: float = -90.0,
        letter_spacing: float = 1.0,
        clockwise: bool = True,
        outline_px: int = 0,
        outline_color: Tuple[int, int, int] | None = None,
        shadow_offset: Tuple[int, int] | None = None,
        shadow_alpha: int = 0,
        glyph_scale: float = 1.0,
        repeat_text: bool = False,
    ) -> None:
        text = text[:max_chars]
        if text == self._current_text:
            return
        base_image = Image.new("RGBA", self.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(base_image)
        wrapped = self._wrap_text(draw, text, box_width)
        color_rgba = (color[0], color[1], color[2], 255)
        x = int(position[0] * self.size[0])
        y = int(position[1] * self.size[1])
        if mode == "circular":
            line = " ".join(text.split())
            if repeat_text:
                line = self._repeat_to_width(draw, line, self.size[0] * 0.95)
            self._draw_text_with_outline(
                draw,
                line,
                (x, y),
                color_rgba,
                outline_px,
                outline_color,
                shadow_offset,
                shadow_alpha,
            )
        else:
            draw.multiline_text((x, y), wrapped, fill=color_rgba, font=self._font, anchor="mm", align="center")
        self._image = self._scale_vertical(base_image, glyph_scale)
        self._dirty = True

    def _draw_text_with_outline(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        pos: Tuple[int, int],
        fill: Tuple[int, int, int, int],
        outline_px: int,
        outline_color: Tuple[int, int, int] | None,
        shadow_offset: Tuple[int, int] | None,
        shadow_alpha: int,
    ) -> None:
        if shadow_offset and shadow_alpha > 0:
            shadow_rgba = (0, 0, 0, shadow_alpha)
            draw.text(
                (pos[0] + shadow_offset[0], pos[1] + shadow_offset[1]),
                text,
                fill=shadow_rgba,
                font=self._font,
                anchor="mm",
                align="center",
            )

        if outline_px > 0 and outline_color:
            outline_rgba = (outline_color[0], outline_color[1], outline_color[2], 255)
            for dx in range(-outline_px, outline_px + 1):
                for dy in range(-outline_px, outline_px + 1):
                    if dx == 0 and dy == 0:
                        continue
                    draw.text(
                        (pos[0] + dx, pos[1] + dy),
                        text,
                        fill=outline_rgba,
                        font=self._font,
                        anchor="mm",
                        align="center",
                    )

        draw.text(pos, text, fill=fill, font=self._font, anchor="mm", align="center")

    def _wrap_text(self, draw: ImageDraw.ImageDraw, text: str, box_width: float) -> str:
        max_width = int(self.size[0] * box_width)
        words = text.split()
        lines: List[str] = []
        current: List[str] = []
        for word in words:
            test = " ".join(current + [word])
            width = draw.textlength(test, font=self._font)
            if width <= max_width or not current:
                current.append(word)
            else:
                lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
        return "\n".join(lines)

    def _repeat_to_width(self, draw: ImageDraw.ImageDraw, text: str, target_width: float) -> str:
        if not text:
            return text
        repeated = text
        spacer = "   "
        for _ in range(8):
            if draw.textlength(repeated, font=self._font) >= target_width:
                break
            repeated = f"{repeated}{spacer}{text}"
        return repeated

    def _scale_vertical(self, image: Image.Image, scale: float) -> Image.Image:
        if scale <= 1.0:
            return image
        width, height = image.size
        scaled_height = max(1, int(height * scale))
        resized = image.resize((width, scaled_height), resample=Image.BICUBIC)

        if scaled_height >= height:
            top = (scaled_height - height) // 2
            return resized.crop((0, top, width, top + height))

        output = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        top = (height - scaled_height) // 2
        output.alpha_composite(resized, dest=(0, top))
        return output

    def to_texture(self, ctx: moderngl.Context) -> moderngl.Texture:
        texture = ctx.texture(self.size, 4)
        texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        texture.repeat_x = False
        texture.repeat_y = False
        texture.write(self._image.tobytes())
        self._dirty = False
        return texture


class VideoLayer:
    def __init__(self, path: str, speed: float = 1.0, loop: bool = True) -> None:
        self._path = path
        self._speed = max(0.1, speed)
        self._loop = loop
        self._cap = None
        self._cv2 = None
        self._accum = 0.0
        self._last_frame: Optional[np.ndarray] = None
        self.width = 0
        self.height = 0
        self.fps = 30.0
        self.frame_interval = 1.0 / self.fps
        self.available = False

        try:
            import cv2
        except Exception:
            return

        self._cv2 = cv2
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return

        self._cap = cap
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps and fps > 1:
            self.fps = fps
        self.frame_interval = 1.0 / self.fps

        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.available = True

    def update(self, dt: float) -> Optional[np.ndarray]:
        if not self.available or not self._cap or not self._cv2:
            return None

        self._accum += dt * self._speed
        if self._last_frame is None:
            self._last_frame = self._read_next()
            return self._last_frame

        if self._accum < self.frame_interval:
            return self._last_frame

        while self._accum >= self.frame_interval:
            frame = self._read_next()
            if frame is None:
                break
            self._last_frame = frame
            self._accum -= self.frame_interval

        return self._last_frame

    def _read_next(self) -> Optional[np.ndarray]:
        if not self._cap or not self._cv2:
            return None
        ok, frame = self._cap.read()
        if not ok:
            if self._loop:
                self._cap.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self._cap.read()
            if not ok:
                return None
        frame = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
        frame = np.flipud(frame)
        if self.width <= 0 or self.height <= 0:
            self.height, self.width = frame.shape[:2]
        return frame

    def _draw_circular_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        center: Tuple[int, int],
        circle_radius: float,
        start_angle_deg: float,
        letter_spacing: float,
        clockwise: bool,
        color_rgba: Tuple[int, int, int, int],
    ) -> None:
        if not text:
            return
        text = " ".join(text.split())
        radius_px = circle_radius * min(self.size[0], self.size[1])
        radius_px = max(10.0, radius_px)

        glyphs = [ch for ch in text if ch != "\n"]
        widths = []
        for ch in glyphs:
            try:
                width = draw.textlength(ch, font=self._font)
            except Exception:
                bbox = draw.textbbox((0, 0), ch, font=self._font)
                width = max(1, bbox[2] - bbox[0])
            widths.append(width * letter_spacing)
        total_arc = sum(widths) / radius_px
        start_angle = math.radians(start_angle_deg)
        angle = start_angle - (total_arc / 2.0)
        direction = -1.0 if clockwise else 1.0

        for ch, ch_width in zip(glyphs, widths):
            advance = (ch_width / radius_px) * direction
            angle += advance / 2.0
            x = center[0] + radius_px * math.cos(angle)
            y = center[1] + radius_px * math.sin(angle)

            bbox = draw.textbbox((0, 0), ch, font=self._font)
            glyph_w = max(1, bbox[2] - bbox[0])
            glyph_h = max(1, bbox[3] - bbox[1])

            glyph_img = Image.new("RGBA", (glyph_w * 2, glyph_h * 2), (0, 0, 0, 0))
            glyph_draw = ImageDraw.Draw(glyph_img)
            glyph_draw.text((glyph_w, glyph_h), ch, fill=color_rgba, font=self._font, anchor="mm")

            rotate_deg = math.degrees(angle) + (90.0 if clockwise else -90.0)
            glyph_img = glyph_img.rotate(rotate_deg, resample=Image.BICUBIC, expand=True)

            paste_x = int(x - glyph_img.size[0] / 2)
            paste_y = int(y - glyph_img.size[1] / 2)
            self._image.alpha_composite(glyph_img, dest=(paste_x, paste_y))

            angle += advance / 2.0

    def to_texture(self, ctx: moderngl.Context) -> moderngl.Texture:
        texture = ctx.texture(self.size, 4)
        texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        texture.repeat_x = False
        texture.repeat_y = False
        texture.write(self._image.tobytes())
        self._dirty = False
        return texture


class BondFireProjection(mglw.WindowConfig):
    gl_version = (3, 3)
    title = "Bond Fire Projection"
    window_size = (1280, 720)
    aspect_ratio = None
    resizable = False

    config_data: dict = {}
    args: argparse.Namespace

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.ctx = self.wnd.ctx
        self._lock = threading.Lock()
        self._state = VisualState()
        self._demo_time = 0.0
        self._video_layer = None
        self._video_texture = None
        self._smoothed_palette: List[Tuple[float, float, float]] = []
        self._smoothed_state_color: Tuple[float, float, float] = (1.0, 0.5, 0.1)
        self._state_current_index = self._state_to_index(self._state.state_name)
        self._state_prev_index = self._state_current_index
        self._state_transition_start = -1.0

        window_cfg = self.config_data.get("window", {})
        if window_cfg.get("vsync", True):
            self.wnd.vsync = True
        if window_cfg.get("fullscreen", False) or self.args.fullscreen:
            self.wnd.fullscreen = True

        self._load_visual_config()
        self._setup_geometry()
        self._setup_text()
        self._setup_video()

        self._listener = None
        if not self.args.no_udp:
            self._listener = UDPListener(self.args.port, self._on_packet)
            self._listener.start()

        self._calibration = False
        self._selected_corner = 0
        self._wind_prompts = [
            "Keep feeding my flames.",
            "More wind. More glow.",
            "Don't stop. Stoke me harder.",
            "Fan the fire. Feed the heat.",
            "That wind hits different.",
            "Fuel me. Keep it coming.",
        ]
        self._wind_prompt_until = 0.0
        self._wind_prompt_cooldown_until = 0.0
        self._active_wind_prompt: Optional[str] = None
        self._last_packet_prompt = ""
        self._wind_prompt_min = int(self._visuals.get("wind_prompt_min", 25))
        self._wind_prompt_hold_sec = float(self._visuals.get("wind_prompt_hold_sec", 2.5))
        self._wind_prompt_cooldown_sec = float(self._visuals.get("wind_prompt_cooldown_sec", 4.0))

    def close(self) -> None:
        if self._listener:
            self._listener.stop()
        super().close()

    def _load_visual_config(self) -> None:
        config = self.config_data
        mapping = config.get("mapping", {})
        quad = mapping.get("quad", [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]])
        self._quad = QuadConfig(points=[(float(x), float(y)) for x, y in quad])
        self._visuals = config.get("visuals", {})
        self._text_cfg = config.get("text", {})

        self._center_radius = float(self._visuals.get("center_radius", self._visuals.get("base_radius", 0.18)))
        ring_inner = self._visuals.get("ring_inner")
        ring_outer = self._visuals.get("ring_outer")
        if ring_inner is None or ring_outer is None:
            self._ring_gap = float(self._visuals.get("ring_gap", 0.02))
            self._ring_thickness = float(self._visuals.get("ring_thickness", 0.04))
            ring_inner = self._center_radius + self._ring_gap
            ring_outer = ring_inner + self._ring_thickness
        else:
            ring_inner = float(ring_inner)
            ring_outer = float(ring_outer)
            self._ring_gap = max(0.0, ring_inner - self._center_radius)
            self._ring_thickness = max(0.01, ring_outer - ring_inner)

        self._ring_inner = ring_inner
        self._ring_outer = ring_outer

        self._update_homography()

    def _update_homography(self) -> None:
        quad = self._quad.points
        dst = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        content_to_screen = compute_homography(dst, quad)
        self._homography = np.linalg.inv(content_to_screen).astype(np.float32)

    def _setup_geometry(self) -> None:
        vertices = np.array(
            [
                -1.0, -1.0,
                1.0, -1.0,
                -1.0, 1.0,
                1.0, 1.0,
            ],
            dtype="f4",
        )
        self._vbo = self.ctx.buffer(vertices.tobytes())
        self._vao = self.ctx.simple_vertex_array(self._create_program(), self._vbo, "in_pos")

    def _create_program(self) -> moderngl.Program:
        return self.ctx.program(
            vertex_shader="""
                #version 330
                in vec2 in_pos;
                out vec2 v_uv;
                void main() {
                    v_uv = in_pos * 0.5 + 0.5;
                    gl_Position = vec4(in_pos, 0.0, 1.0);
                }
            """,
            fragment_shader="""
                #version 330
                uniform mat3 u_h;
                uniform vec2 u_aspect;
                uniform float u_time;
                uniform int u_state;
                uniform int u_state_prev;
                uniform float u_state_blend;
                uniform int u_people;
                uniform float u_fire;
                uniform float u_pulse;
                uniform float u_pulse_speed;
                uniform float u_pulse_strength;
                uniform float u_force_pulse;
                uniform float u_party;
                uniform vec3 u_palette[4];
                uniform vec3 u_state_color;
                uniform float u_ring_floor;
                uniform sampler2D u_video;
                uniform int u_video_enabled;
                uniform float u_video_mix;
                uniform float u_video_alpha;
                uniform float u_video_colorize;
                uniform sampler2D u_text;
                uniform float u_text_mix;
                uniform int u_text_mode;
                uniform float u_text_radius;
                uniform float u_text_band;
                uniform float u_text_angle;
                uniform float u_text_dir;
                uniform float u_text_alpha;
                uniform float u_text_speed;
                uniform float u_text_stretch;
                uniform float u_baseline_fire;
                uniform float u_background;
                uniform float u_texture_strength;
                uniform float u_base_radius;
                uniform float u_ring_inner;
                uniform float u_ring_outer;
                out vec4 f_color;
                in vec2 v_uv;

                float hash(vec2 p) {
                    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
                }

                float noise(vec2 p) {
                    vec2 i = floor(p);
                    vec2 f = fract(p);
                    float a = hash(i);
                    float b = hash(i + vec2(1.0, 0.0));
                    float c = hash(i + vec2(0.0, 1.0));
                    float d = hash(i + vec2(1.0, 1.0));
                    vec2 u = f * f * (3.0 - 2.0 * f);
                    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
                }

                vec3 hsv2rgb(vec3 c) {
                    vec4 k = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
                    vec3 p = abs(fract(c.xxx + k.xyz) * 6.0 - k.www);
                    return c.z * mix(k.xxx, clamp(p - k.xxx, 0.0, 1.0), c.y);
                }

                void main() {
                    vec3 proj = u_h * vec3(v_uv, 1.0);
                    vec2 uv = proj.xy / proj.z;

                    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
                        f_color = vec4(0.0, 0.0, 0.0, 1.0);
                        return;
                    }

                    vec2 center = vec2(0.5, 0.5);
                    vec2 delta = uv - center;
                    delta *= u_aspect;
                    float dist = length(delta);

                    float fill_factor = clamp(float(u_people) / 5.0, 0.0, 1.0);
                    float fill_boost = pow(fill_factor, 0.6);
                    float base = smoothstep(0.55, 0.0, dist);
                    float center_mask = smoothstep(u_base_radius, u_base_radius - 0.015, dist);
                    float ring = smoothstep(u_ring_inner, u_ring_inner - 0.01, dist)
                               - smoothstep(u_ring_outer, u_ring_outer - 0.01, dist);
                    float inner_band = smoothstep(u_base_radius + 0.03, u_base_radius - 0.01, dist)
                                     - smoothstep(u_ring_inner + 0.01, u_ring_inner - 0.02, dist);
                    float ring_glow = smoothstep(u_ring_outer + 0.10, u_ring_inner - 0.02, dist);

                    float flame = sin(u_time * 3.0 + dist * 8.0) * 0.5 + 0.5;
                    float flicker = mix(0.5, 1.0, flame);

                    vec3 fire = mix(u_palette[0], u_palette[1], clamp(dist * 2.0, 0.0, 1.0));
                    vec3 ember = mix(u_palette[2], u_palette[3], clamp(dist * 1.8, 0.0, 1.0));

                    float swirl = sin((delta.x * 8.0 - delta.y * 6.0) + u_time * 1.3);
                    float base_pulse = 0.5 + 0.5 * sin(u_time * u_pulse_speed);
                    float pulse_gate = max(u_pulse, u_force_pulse);
                    float pulse_amp = mix(0.15, 1.0, pulse_gate) * u_pulse_strength;
                    float pulse = smoothstep(0.0, 1.0, u_pulse) *
                                  (0.6 + 0.4 * sin((dist * 12.0 - u_time * 5.0)));

                    float ring_pulse = (0.7 + 0.3 * sin(u_time * 2.2 + dist * 10.0)) *
                                       (0.65 + 0.35 * base_pulse);

                    float party = smoothstep(0.0, 1.0, u_party) *
                                  (0.5 + 0.5 * cos((delta.x * 12.0 + delta.y * 12.0) + u_time * 4.0));


                    vec2 warp = vec2(
                        noise(uv * 6.0 + vec2(u_time * 0.15, 0.0)),
                        noise(uv * 6.0 + vec2(0.0, u_time * 0.12))
                    ) * 0.02;
                    vec2 uv_warp = uv + warp + vec2(0.0, -u_time * 0.03);

                    float ember_field = noise(uv_warp * 18.0 + vec2(0.0, u_time * 0.7));
                    float embers = smoothstep(0.6, 1.0, ember_field) * (0.4 + 0.6 * base);

                    float flicker_a = noise(uv_warp * 6.0 + vec2(0.0, u_time * 0.4));
                    float flicker_b = noise(uv_warp * 14.0 + vec2(u_time * 0.7, 0.0));
                    float flicker_c = noise(uv_warp * 30.0 + vec2(u_time * 1.1, u_time * 0.3));
                    float flicker_mix = clamp((flicker_a * 0.6 + flicker_b * 0.3 + flicker_c * 0.1), 0.0, 1.0);
                    flicker_mix = smoothstep(0.2, 0.95, flicker_mix);

                    float gain_prev = 1.0;
                    if (u_state_prev == 2) {
                        gain_prev = 1.25;
                    }

                    float gain_curr = 1.0;
                    if (u_state == 2) {
                        gain_curr = 1.25;
                    }

                    float state_gain = mix(gain_prev, gain_curr, u_state_blend);

                    float fire_gain = clamp(u_fire * state_gain + 0.15, 0.0, 1.4);

                    float glow_gain = fire_gain + u_baseline_fire;

                    float pulse_boost = 1.0 + (base_pulse * pulse_amp) + 0.4 * u_pulse;

                    vec3 color = fire * (base * (0.45 + 0.65 * flicker)) * glow_gain * pulse_boost;
                    color += ember * (ring * (2.2 + ring_pulse)) * glow_gain * pulse_boost;
                    color += ember * ring_glow * 0.9 * glow_gain * pulse_boost;
                    float ring_floor = u_ring_floor * (1.0 + base_pulse * pulse_amp);
                    color += ember * ring * ring_floor;
                    color += ember * ring_glow * (ring_floor * 0.6);
                    color += u_state_color * ring * (ring_floor * 0.8);
                    color += u_state_color * ring_glow * (ring_floor * 0.35);
                    color += u_state_color * inner_band * (0.9 * fill_boost);

                    float idle_prev = u_state_prev == 0 ? 1.0 : 0.0;
                    float idle_curr = u_state == 0 ? 1.0 : 0.0;
                    float idle_weight = mix(idle_prev, idle_curr, u_state_blend);
                    float idle_breath = 0.6 + 0.4 * base_pulse;
                    color += u_state_color * ring_glow * (0.6 * idle_breath) * idle_weight;

                    float party_prev = u_state_prev == 2 ? 1.0 : 0.0;
                    float party_curr = u_state == 2 ? 1.0 : 0.0;
                    float party_weight = mix(party_prev, party_curr, u_state_blend);
                    vec3 party_color = vec3(0.0);
                    float hue = fract(u_time * 0.02);
                    float hue_b = fract(hue + 0.2);
                    vec3 color_a = hsv2rgb(vec3(hue, 0.9, 1.0));
                    vec3 color_b = hsv2rgb(vec3(hue_b, 0.9, 1.0));
                    float blend = 0.5 + 0.5 * sin(u_time * 0.6);
                    party_color = mix(color_a, color_b, blend);
                    color += party_color * ring * 0.7 * party_weight;
                    color += party_color * ring_glow * 0.4 * party_weight;

                    color += ember * (0.2 + 0.4 * swirl) * base;
                    color += ember * embers * 0.65;
                    color += u_palette[2] * pulse * 0.6;
                    color += u_palette[1] * party * 0.5;
                    color += vec3(0.0);

                    vec3 texture_warm = mix(u_palette[0], u_palette[1], flicker_mix);
                    vec3 texture_hot = mix(u_palette[2], u_palette[3], flicker_mix);
                    vec3 texture_color = mix(texture_warm, texture_hot, base);

                    float streaks = smoothstep(0.3, 1.0, noise(vec2(uv_warp.x * 6.0, uv_warp.y * 12.0)));
                    float flame_rise = clamp(1.0 - uv.y, 0.0, 1.0);
                    float texture_mask = (0.35 + 0.8 * flicker_mix) * (0.5 + 0.7 * base) * flame_rise;
                    texture_mask += streaks * (0.45 + 0.55 * base) * flame_rise;
                    vec3 filled = mix(vec3(u_background + u_baseline_fire * 0.2), color, clamp(glow_gain + 0.35, 0.0, 1.4));
                    vec3 core = mix(vec3(u_background), filled, clamp(base + fill_boost, 0.0, 1.0));
                    vec3 flood = mix(vec3(u_background), filled, clamp(0.5 + fill_boost * 1.5, 0.0, 1.0));
                    color = mix(filled, core, fill_boost);
                    color = mix(color, flood, fill_boost);
                    vec3 flood_tint = mix(u_state_color, party_color, party_weight);
                    color = mix(color, flood_tint * 0.85, fill_boost * 0.9);
                    float tex_strength = clamp(u_texture_strength, 0.0, 2.0);
                    color *= (1.0 + texture_mask * tex_strength * 0.6);

                    float inner_tint = smoothstep(u_base_radius + 0.02, u_base_radius - 0.04, dist);
                    color = mix(color, flood_tint * 0.9, inner_tint * fill_boost);


                    color = mix(color, vec3(0.0), center_mask * (1.0 - fill_boost));

                    if (u_video_enabled == 1) {
                        vec2 vuv = vec2(uv.x, 1.0 - uv.y);
                        vec3 vid = texture(u_video, vuv).rgb;
                        vec3 vid_color = mix(vid, u_state_color, u_video_colorize);
                        color = mix(color, vid_color, clamp(u_video_mix, 0.0, 1.0) * u_video_alpha);
                    }

                    vec4 text_sample = vec4(0.0);
                    if (u_text_mode == 1) {
                        float angle = atan(delta.y, delta.x);
                        float u = angle / (2.0 * 3.14159265) + 0.5 + u_text_angle + (u_time * u_text_speed);
                        float v = ((dist - u_text_radius) / u_text_band) * u_text_stretch + 0.5;
                        vec4 arc_a = texture(u_text, vec2(fract(u * u_text_dir), v));
                        vec4 arc_b = texture(u_text, vec2(fract((u + 0.5) * u_text_dir), v));
                        text_sample = max(arc_a, arc_b);
                    } else {
                        vec2 text_uv = vec2(uv.x, 1.0 - uv.y);
                        text_sample = texture(u_text, text_uv);
                    }
                    color = mix(color, text_sample.rgb, text_sample.a * u_text_mix * u_text_alpha);

                    float vignette = smoothstep(0.98, 0.25, dist);
                    float edge_fade = smoothstep(0.98, 0.82, dist);
                    color *= mix(vignette, edge_fade, fill_boost);

                    f_color = vec4(color, 1.0);
                }
            """,
        )

    def _setup_text(self) -> None:
        text_cfg = self._text_cfg
        font_name = text_cfg.get("font", "Arial")
        font_size = int(text_cfg.get("font_size", 44))
        mode = str(text_cfg.get("mode", "linear"))
        if mode == "circular":
            size = (2048, 512)
        else:
            size = (1024, 512)
        self._text_layer = TextLayer(size, font_name, font_size)
        self._text_texture = self._text_layer.to_texture(self.ctx)

    def _setup_video(self) -> None:
        video_cfg = self.config_data.get("video", {})
        if not video_cfg.get("enabled", False):
            return
        path = str(video_cfg.get("path", "")).strip()
        if not path:
            return

        video_path = Path(path)
        if not video_path.is_absolute():
            video_path = Path(self.args.config).parent / video_path

        layer = VideoLayer(str(video_path), speed=float(video_cfg.get("speed", 1.0)), loop=bool(video_cfg.get("loop", True)))
        if not layer.available or layer.width <= 0 or layer.height <= 0:
            return

        self._video_layer = layer
        self._video_texture = self.ctx.texture((layer.width, layer.height), 3)
        self._video_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._video_texture.repeat_x = False
        self._video_texture.repeat_y = False

    def _on_packet(self, packet: dict) -> None:
        with self._lock:
            self._state.update_from_packet(packet)
            if "prompt" in packet:
                self._last_packet_prompt = str(packet.get("prompt", ""))

            wind_value = int(packet.get("wind", self._state.wind))
            now = time.monotonic()
            if wind_value >= self._wind_prompt_min:
                if now >= self._wind_prompt_until and now >= self._wind_prompt_cooldown_until:
                    self._active_wind_prompt = random.choice(self._wind_prompts)
                    self._wind_prompt_until = now + self._wind_prompt_hold_sec
                    self._wind_prompt_cooldown_until = now + self._wind_prompt_cooldown_sec
                if self._active_wind_prompt:
                    self._state.prompt = self._active_wind_prompt
            else:
                if now < self._wind_prompt_until and self._active_wind_prompt:
                    self._state.prompt = self._active_wind_prompt
                elif self._last_packet_prompt:
                    self._state.prompt = self._last_packet_prompt

    @staticmethod
    def _smooth_value(current: float, target: float, dt: float, tau: float) -> float:
        if tau <= 0.0:
            return target
        alpha = 1.0 - math.exp(-dt / tau)
        return current + (target - current) * alpha

    def _smooth_color(
        self,
        current: Tuple[float, float, float],
        target: Tuple[float, float, float],
        dt: float,
        tau: float,
    ) -> Tuple[float, float, float]:
        return (
            self._smooth_value(current[0], target[0], dt, tau),
            self._smooth_value(current[1], target[1], dt, tau),
            self._smooth_value(current[2], target[2], dt, tau),
        )

    def _smooth_palette(
        self,
        current: List[Tuple[float, float, float]],
        target: List[Tuple[float, float, float]],
        dt: float,
        tau: float,
    ) -> List[Tuple[float, float, float]]:
        if not current or len(current) != len(target):
            return list(target)
        return [self._smooth_color(c, t, dt, tau) for c, t in zip(current, target)]

    def on_render(self, time: float, frame_time: float) -> None:
        if self.args.no_udp:
            self._advance_demo(frame_time)

        with self._lock:
            state_snapshot = VisualState(**self._state.__dict__)

        self.ctx.clear(0.0, 0.0, 0.0, 1.0)

        palette_target = self._resolve_palette(
            state_snapshot.dominant_palette,
            state_snapshot.state_name,
            state_snapshot.pulse_active,
        )
        state_color_target = self._resolve_state_color(state_snapshot.state_name)
        dt = max(0.0, float(frame_time))
        color_tau = float(self._visuals.get("color_smooth_sec", 0.2))
        self._smoothed_palette = self._smooth_palette(self._smoothed_palette, palette_target, dt, color_tau)
        self._smoothed_state_color = self._smooth_color(
            self._smoothed_state_color,
            state_color_target,
            dt,
            color_tau,
        )
        palette = self._smoothed_palette
        state_color = self._smoothed_state_color

        state_index = self._state_to_index(state_snapshot.state_name)
        if state_index != self._state_current_index:
            self._state_prev_index = self._state_current_index
            self._state_current_index = state_index
            self._state_transition_start = time

        text_cfg = self._text_cfg
        if text_cfg.get("enabled", True):
            self._text_layer.update_text(
                state_snapshot.prompt,
                tuple(text_cfg.get("position", [0.5, 0.84])),
                tuple(text_cfg.get("color", [255, 236, 210])),
                float(text_cfg.get("box_width", 0.86)),
                int(text_cfg.get("max_chars", 90)),
                str(text_cfg.get("mode", "linear")),
                float(text_cfg.get("circle_radius", 0.35)),
                float(text_cfg.get("start_angle_deg", -90.0)),
                float(text_cfg.get("letter_spacing", 1.0)),
                bool(text_cfg.get("clockwise", True)),
                int(text_cfg.get("outline_px", 2)),
                tuple(text_cfg.get("outline_color", [10, 10, 10])),
                tuple(text_cfg.get("shadow_offset", [2, 2])),
                int(text_cfg.get("shadow_alpha", 140)),
                float(text_cfg.get("glyph_scale", 1.0)),
                bool(text_cfg.get("repeat_text", False)),
            )
            if self._text_layer._dirty:
                self._text_texture.release()
                self._text_texture = self._text_layer.to_texture(self.ctx)

        if self._video_layer and self._video_texture:
            frame = self._video_layer.update(frame_time)
            if frame is not None:
                self._video_texture.write(frame.tobytes())

        prog = self._vao.program
        self._set_uniform(prog, "u_h", self._homography.T.tobytes(), is_matrix=True)
        self._set_uniform(prog, "u_time", time)
        aspect = float(self.wnd.width) / max(1.0, float(self.wnd.height))
        self._set_uniform(prog, "u_aspect", (aspect, 1.0))
        transition_sec = float(self._visuals.get("state_transition_sec", 1.2))
        if transition_sec <= 0.0:
            blend = 1.0
        else:
            if self._state_transition_start < 0.0:
                self._state_transition_start = time - transition_sec
            blend = clamp((time - self._state_transition_start) / transition_sec, 0.0, 1.0)
        self._set_uniform(prog, "u_state", int(self._state_current_index))
        self._set_uniform(prog, "u_state_prev", int(self._state_prev_index))
        self._set_uniform(prog, "u_state_blend", float(blend))
        self._set_uniform(prog, "u_people", int(state_snapshot.people_count))
        render_fire = float(state_snapshot.fire_intensity)
        if not math.isfinite(render_fire):
            render_fire = 0.0
        if render_fire <= 0.01:
            if state_index == 0:
                render_fire = 0.35
            elif state_index == 1:
                render_fire = 0.7
            elif state_index == 2:
                render_fire = 1.0
            elif state_index == 3:
                render_fire = 0.5
        
        # Boost fire with wind - wind is 0-100, scale to 0.0-1.0 multiplier
        wind_boost = float(state_snapshot.wind) / 100.0
        wind_boost = clamp(wind_boost, 0.0, 1.0)
        if wind_boost > 0.05:  # Only boost when wind is active
            render_fire = render_fire * (1.0 + wind_boost * 1.6)

        # Step fire size/brightness by state (IDLE=0, FIRE=1, PARTY=2)
        render_fire = render_fire * (1.0 + 0.2 * state_index)
        
        baseline_fire = float(self._visuals.get("baseline_fire", 0.35))
        if not math.isfinite(baseline_fire) or baseline_fire <= 0.0:
            baseline_fire = 0.35
        render_fire = max(0.25, render_fire, baseline_fire)
        self._set_uniform(prog, "u_baseline_fire", baseline_fire)
        self._set_uniform(prog, "u_fire", render_fire)
        self._set_uniform(prog, "u_pulse", 1.0 if state_snapshot.pulse_active else 0.0)
        self._set_uniform(prog, "u_pulse_speed", float(self._visuals.get("pulse_speed", 2.4)))
        pulse_strength = float(self._visuals.get("pulse_strength", 0.8)) * (1.0 + wind_boost * 1.25)
        self._set_uniform(prog, "u_pulse_strength", pulse_strength)
        self._set_uniform(prog, "u_force_pulse", 1.0 if self._visuals.get("always_pulse", True) else 0.0)
        self._set_uniform(prog, "u_party", float(state_snapshot.party_buildup_progress))
        ring_floor = float(self._visuals.get("ring_floor", 0.35))
        ring_floor = clamp(ring_floor + wind_boost * float(self._visuals.get("wind_ring_boost", 0.65)), 0.0, 2.0)
        self._set_uniform(prog, "u_ring_floor", ring_floor)
        text_mode = 1 if str(text_cfg.get("mode", "linear")) == "circular" else 0
        ring_offset = float(text_cfg.get("ring_offset", 0.06))
        ring_band = float(text_cfg.get("ring_band", 0.05))
        ring_radius = float(self._ring_outer + ring_offset)
        angle_offset = float(text_cfg.get("angle_offset_deg", 0.0)) / 360.0
        self._set_uniform(prog, "u_text_mix", 1.0 if text_cfg.get("enabled", True) else 0.0)
        self._set_uniform(prog, "u_text_mode", text_mode)
        self._set_uniform(prog, "u_text_radius", clamp(ring_radius, 0.05, 0.95))
        self._set_uniform(prog, "u_text_band", max(0.01, ring_band))
        self._set_uniform(prog, "u_text_angle", angle_offset)
        self._set_uniform(prog, "u_text_dir", 1.0 if text_cfg.get("clockwise", True) else -1.0)
        self._set_uniform(prog, "u_text_alpha", float(text_cfg.get("alpha", 1.0)))
        self._set_uniform(prog, "u_text_speed", float(text_cfg.get("spin_speed", 0.02)))
        self._set_uniform(prog, "u_text_stretch", float(text_cfg.get("height_scale", 1.0)))
        self._set_uniform(prog, "u_background", float(self._visuals.get("background_intensity", 0.1)))
        self._set_uniform(prog, "u_texture_strength", float(self._visuals.get("texture_strength", 1.2)))
        self._set_uniform(prog, "u_base_radius", float(self._center_radius))
        self._set_uniform(prog, "u_ring_inner", float(self._ring_inner))
        self._set_uniform(prog, "u_ring_outer", float(self._ring_outer))

        video_cfg = self.config_data.get("video", {})
        video_enabled = 1 if self._video_layer and self._video_texture and video_cfg.get("enabled", False) else 0
        self._set_uniform(prog, "u_video_enabled", video_enabled)
        self._set_uniform(prog, "u_video_mix", float(video_cfg.get("mix", 0.0)))
        self._set_uniform(prog, "u_video_alpha", float(video_cfg.get("alpha", 1.0)))
        self._set_uniform(prog, "u_video_colorize", float(video_cfg.get("colorize", 0.0)))

        for idx in range(4):
            self._set_uniform(prog, f"u_palette[{idx}]", palette[idx])
        self._set_uniform(prog, "u_state_color", state_color)

        self._set_uniform(prog, "u_text", 0)
        self._text_texture.use(location=0)
        if self._video_texture:
            self._set_uniform(prog, "u_video", 1)
            self._video_texture.use(location=1)
        self._vao.render(moderngl.TRIANGLE_STRIP)

        if self._calibration:
            self._render_calibration_overlay()

    def _advance_demo(self, frame_time: float) -> None:
        self._demo_time += frame_time
        with self._lock:
            self._state.state_name = "FIRE"
            self._state.fire_intensity = 0.6 + 0.4 * math.sin(self._demo_time * 0.5)
            self._state.pulse_active = math.sin(self._demo_time * 0.2) > 0.7
            self._state.party_buildup_progress = 0.5 + 0.5 * math.sin(self._demo_time * 0.3)
            self._state.wind = int((math.sin(self._demo_time * 0.6) * 0.5 + 0.5) * 100)
            self._state.prompt = "Projection demo mode"

    def _state_to_index(self, state: str) -> int:
        mapping = {
            "IDLE": 0,
            "FIRE": 1,
            "PARTY": 2,
        }
        return mapping.get(state.upper(), 0)

    def _resolve_palette(
        self,
        udp_palette: List[int],
        state_name: str,
        pulse_active: bool,
    ) -> List[Tuple[float, float, float]]:
        fallback = self._visuals.get("palette_fallback", [])
        state_palettes = self._visuals.get("state_palettes", {})

        palette: List[int] = []
        if pulse_active and udp_palette:
            avg = sum(udp_palette) / max(1, len(udp_palette))
            if avg >= 8:
                palette = list(udp_palette)

        if not palette:
            state_key = str(state_name).upper()
            state_palette = state_palettes.get(state_key, [])
            if state_palette:
                palette = [c for triplet in state_palette for c in triplet]
            else:
                palette = [c for triplet in fallback for c in triplet]

        if len(palette) < 12:
            palette = list(palette) + [255, 120, 20] * 4
        colors = []
        for idx in range(0, 12, 3):
            r, g, b = palette[idx:idx + 3]
            colors.append((r / 255.0, g / 255.0, b / 255.0))
        return colors

    def _resolve_state_color(self, state_name: str) -> Tuple[float, float, float]:
        state_palettes = self._visuals.get("state_palettes", {})
        state_key = str(state_name).upper()
        palette = state_palettes.get(state_key, [])
        if palette and len(palette[0]) >= 3:
            r, g, b = palette[0][:3]
            return (r / 255.0, g / 255.0, b / 255.0)
        return (1.0, 0.5, 0.1)

    def key_event(self, key, action, modifiers) -> None:
        if action != self.wnd.keys.ACTION_PRESS:
            return

        if key == self.wnd.keys.C:
            self._calibration = not self._calibration
            return
        if key == self.wnd.keys.T:
            self._text_cfg["enabled"] = not self._text_cfg.get("enabled", True)
            return
        if key == self.wnd.keys.S:
            self._write_visuals_to_config()
            return

        step = 0.005
        if modifiers.shift:
            step = 0.02

        if key == self.wnd.keys.LEFT_BRACKET:
            self._nudge_visuals(delta_radius=-step)
            return
        if key == self.wnd.keys.RIGHT_BRACKET:
            self._nudge_visuals(delta_radius=step)
            return
        if key == self.wnd.keys.MINUS:
            self._nudge_visuals(delta_ring=-step)
            return
        if key == self.wnd.keys.EQUAL:
            self._nudge_visuals(delta_ring=step)
            return
        if key == self.wnd.keys.COMMA:
            self._nudge_visuals(delta_gap=-step)
            return
        if key == self.wnd.keys.PERIOD:
            self._nudge_visuals(delta_gap=step)
            return

        if not self._calibration:
            return

        x, y = self._quad.points[self._selected_corner]
        if key == self.wnd.keys.TAB:
            self._selected_corner = (self._selected_corner + 1) % 4
        elif key == self.wnd.keys.LEFT:
            x -= step
        elif key == self.wnd.keys.RIGHT:
            x += step
        elif key == self.wnd.keys.UP:
            y -= step
        elif key == self.wnd.keys.DOWN:
            y += step
        elif key == self.wnd.keys.ENTER:
            self._write_quad_to_config()
            return

        self._quad.points[self._selected_corner] = (clamp(x, 0.0, 1.0), clamp(y, 0.0, 1.0))
        self._update_homography()

    def _write_quad_to_config(self) -> None:
        config = self.config_data
        config.setdefault("mapping", {})["quad"] = [[x, y] for x, y in self._quad.points]
        save_config(self.args.config, config)

    def _write_visuals_to_config(self) -> None:
        config = self.config_data
        visuals = config.setdefault("visuals", {})
        visuals["center_radius"] = round(self._center_radius, 4)
        visuals["ring_gap"] = round(self._ring_gap, 4)
        visuals["ring_thickness"] = round(self._ring_thickness, 4)
        visuals["base_radius"] = round(self._center_radius, 4)
        visuals["ring_inner"] = round(self._ring_inner, 4)
        visuals["ring_outer"] = round(self._ring_outer, 4)
        save_config(self.args.config, config)

    def _nudge_visuals(
        self,
        delta_radius: float = 0.0,
        delta_ring: float = 0.0,
        delta_gap: float = 0.0,
    ) -> None:
        self._center_radius = clamp(self._center_radius + delta_radius, 0.05, 0.45)
        self._ring_gap = clamp(self._ring_gap + delta_gap, 0.0, 0.2)
        self._ring_thickness = clamp(self._ring_thickness + delta_ring, 0.01, 0.2)

        ring_inner = self._center_radius + self._ring_gap
        ring_outer = ring_inner + self._ring_thickness
        if ring_outer > 0.95:
            ring_outer = 0.95
            self._ring_thickness = max(0.01, ring_outer - ring_inner)

        self._ring_inner = ring_inner
        self._ring_outer = ring_outer

    def _render_calibration_overlay(self) -> None:
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        overlay = np.array(
            [
                -1.0, -1.0,
                1.0, -1.0,
                -1.0, 1.0,
                1.0, 1.0,
            ],
            dtype="f4",
        )
        vbo = self.ctx.buffer(overlay.tobytes())
        program = self.ctx.program(
            vertex_shader="""
                #version 330
                in vec2 in_pos;
                out vec2 v_uv;
                void main() {
                    v_uv = in_pos * 0.5 + 0.5;
                    gl_Position = vec4(in_pos, 0.0, 1.0);
                }
            """,
            fragment_shader="""
                #version 330
                in vec2 v_uv;
                out vec4 f_color;
                void main() {
                    float grid = step(0.98, fract(v_uv.x * 10.0)) + step(0.98, fract(v_uv.y * 10.0));
                    vec3 color = mix(vec3(0.0, 0.4, 0.6), vec3(0.0, 0.8, 1.0), grid);
                    f_color = vec4(color, 0.35);
                }
            """,
        )
        vao = self.ctx.simple_vertex_array(program, vbo, "in_pos")
        vao.render(moderngl.TRIANGLE_STRIP)
        vao.release()
        program.release()
        vbo.release()
        self.ctx.disable(moderngl.BLEND)

    @staticmethod
    def _set_uniform(
        program: moderngl.Program,
        name: str,
        value,
        is_matrix: bool = False,
    ) -> None:
        try:
            if is_matrix:
                program[name].write(value)
            else:
                program[name].value = value
        except KeyError:
            return


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bond Fire projection mapping")
    parser.add_argument("--config", default="projection/config.yaml", help="Path to config.yaml")
    parser.add_argument("--port", type=int, default=4210, help="UDP port to listen on")
    parser.add_argument("--no-udp", action="store_true", help="Run in demo mode (no UDP)")
    parser.add_argument("--fullscreen", action="store_true", help="Start in fullscreen")
    return parser


def main() -> None:
    args, mglw_args = build_arg_parser().parse_known_args()
    sys.argv = [sys.argv[0], *mglw_args]
    config = load_config(args.config)

    window_cfg = config.get("window", {})
    width = int(window_cfg.get("width", 1280))
    height = int(window_cfg.get("height", 720))

    BondFireProjection.window_size = (width, height)
    BondFireProjection.args = args
    BondFireProjection.config_data = config

    mglw.run_window_config(BondFireProjection, args=mglw_args)


if __name__ == "__main__":
    main()
