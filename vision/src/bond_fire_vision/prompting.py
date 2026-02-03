from __future__ import annotations

import base64
import os
import queue
import random
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import cv2
from openai import OpenAI


@dataclass(frozen=True)
class PromptContext:
    people_in_roi: int
    phone_detected: bool
    frame_timestamp: float


class OpenAIPromptGenerator:
    """Background worker that turns frames into icebreaker prompts via OpenAI."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.9,
        max_output_tokens: int = 120,
        prompt_ttl: float = 30.0,
        max_queue: int = 2,
    ) -> None:
        if not api_key:
            raise ValueError("API key is required to enable AI prompts")

        self._client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.prompt_ttl = prompt_ttl

        self._queue: queue.Queue[tuple[PromptContext, bytes]] = queue.Queue(maxsize=max_queue)
        self._thread = threading.Thread(target=self._worker, name="openai-prompt-worker", daemon=True)
        self._stop_event = threading.Event()
        self._latest_prompt: Optional[tuple[str, float]] = None
        self._history: deque[str] = deque(maxlen=5)
        self._lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._thread.start()
            self._started = True

    def stop(self) -> None:
        self._stop_event.set()
        if self._started:
            # Unblock the worker if it is waiting on the queue.
            try:
                self._queue.put_nowait((PromptContext(0, False, time.monotonic()), b""))
            except queue.Full:
                pass
            self._thread.join(timeout=2.0)
            self._started = False

    def submit(self, frame, context: PromptContext) -> None:
        if not self._started:
            return

        success, buffer = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 65],
        )
        if not success:
            return

        jpeg_bytes = buffer.tobytes()

        try:
            self._queue.put_nowait((context, jpeg_bytes))
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait((context, jpeg_bytes))
            except queue.Full:
                return

    def get_latest_prompt(self) -> Optional[str]:
        with self._lock:
            if not self._latest_prompt:
                return None
            prompt, timestamp = self._latest_prompt
            if time.monotonic() - timestamp > self.prompt_ttl:
                return None
            return prompt

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            try:
                context, buffer = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                if self._stop_event.is_set():
                    break

                if not buffer:
                    continue

                self._dispatch_request(context, buffer)
            finally:
                self._queue.task_done()

    def _dispatch_request(self, context: PromptContext, buffer: bytes) -> None:
        payload = base64.b64encode(buffer).decode("ascii")
        image_url = {
            "type": "input_image",
            "image_url": f"data:image/jpeg;base64,{payload}",
        }
        stats_text = self._compose_stats_text(context)

        system_message = {
            "role": "system",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "You are the cheeky MC for a chill Singapore hangout. Sound like a playful bro with light Singlish vibes (" \
                        "bro, lah, sia). Output exactly one super short sentence (<80 chars) that mixes snarky humour with a call-out or dare. " \
                        "Mention real visible details (clothes, posture, props) only when obvious. Vary your openings; no repeating the same starter. Never use lists or multiple sentences. Always end with a cheeky question or dare."
                    ),
                }
            ],
        }

        history_snapshot = list(self._history)
        history_text = " \n".join(history_snapshot) if history_snapshot else "None"
        user_message = {
            "role": "user",
            "content": [
                {"type": "input_text", "text": stats_text},
                {"type": "input_text", "text": f"Recent prompts: {history_text}"},
                image_url,
            ],
        }

        backoff = 1.0
        for attempt in range(3):
            try:
                response = self._client.responses.create(
                    model=self.model,
                    input=[system_message, user_message],
                    max_output_tokens=self.max_output_tokens,
                    temperature=self.temperature,
                )
                text = (getattr(response, "output_text", "") or "").strip()
                if not text:
                    try:
                        segments: list[str] = []
                        outputs = getattr(response, "output", []) or []
                        for output in outputs:
                            output_content = getattr(output, "content", []) or []
                            for content in output_content:
                                content_type = getattr(content, "type", None)
                                if content_type is None and isinstance(content, dict):
                                    content_type = content.get("type")
                                text_value = getattr(content, "text", None)
                                if text_value is None and isinstance(content, dict):
                                    text_value = content.get("text")
                                if content_type == "output_text" and text_value:
                                    segments.append(text_value)
                        text = "\n".join(segments).strip()
                    except AttributeError:
                        text = ""
                if text:
                    self._record_prompt(text)
                    preview = text if len(text) <= 80 else text[:77] + "..."
                    print(f"AI prompt updated -> {preview}", flush=True)
                return
            except Exception as exc:
                print(
                    f"AI prompt request failed (attempt {attempt + 1}/3): {exc}",
                    flush=True,
                )
                if attempt == 2:
                    return
                time.sleep(backoff + random.uniform(0.0, 0.5))
                backoff *= 2

    def _compose_stats_text(self, context: PromptContext) -> str:
        phone_flag = "yes" if context.phone_detected else "no"
        return (
            "Scene details:\n"
            f"people_in_roi: {context.people_in_roi}\n"
            f"phone_detected: {phone_flag}\n"
            "Remind: Use exactly one tiny sentence (<80 chars), snarky and funny. Mention real outfits/props when obvious. Vary opening words. End with a cheeky question or dare."
        )

    def _record_prompt(self, prompt: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._latest_prompt = (prompt, now)
            self._history.append(prompt)


def resolve_api_key(explicit_key: Optional[str]) -> Optional[str]:
    if explicit_key:
        return explicit_key
    for env_var in ("BOND_FIRE_OPENAI_API_KEY", "OPENAI_API_KEY"):
        value = os.getenv(env_var)
        if value:
            return value
    return None
