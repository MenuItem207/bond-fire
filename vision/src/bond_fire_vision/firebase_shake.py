"""Firebase Realtime Database shake detection listener for vision system."""

import json
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

from firebase_admin import db, initialize_app, credentials


class FirebaseShakeListener:
    """
    Listens for shake events from Firebase Realtime Database.
    
    Aggregates shake events per second and provides wind value (0-100).
    """

    def __init__(
        self,
        firebase_url: str,
        credentials_path: Optional[str] = None,
        max_concurrent_shakes: int = 5,
        shake_timeout: float = 2.0,
        wind_max: int = 100,
    ):
        """
        Initialize Firebase shake listener.

        Args:
            firebase_url: Firebase Realtime Database URL
            credentials_path: Path to Firebase service account JSON (optional for test mode)
            max_concurrent_shakes: Maximum shake events to count simultaneously
            shake_timeout: Seconds before shake expires
            wind_max: Maximum wind value (0-wind_max)
        """
        self.firebase_url = firebase_url
        self.credentials_path = credentials_path
        self.max_concurrent_shakes = max_concurrent_shakes
        self.shake_timeout = shake_timeout
        self.wind_max = wind_max

        self._app = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._use_rest = False
        self._shake_events: dict = {}  # user_id -> timestamp_sec
        self._lock = threading.Lock()

        self._initialize_firebase()

    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK."""
        try:
            if self.credentials_path:
                cred = credentials.Certificate(self.credentials_path)
                self._app = initialize_app(cred, {'databaseURL': self.firebase_url})
            else:
                # Use default credentials (works with ADC or emulator). If missing, fall back to REST polling.
                self._app = initialize_app(options={'databaseURL': self.firebase_url})
            print(f"✅ Firebase initialized with: {self.firebase_url}")
        except Exception as e:
            print(f"⚠️  Firebase initialization note: {e}")
            self._use_rest = True
            print("ℹ️  Falling back to RTDB REST polling (public/test mode)")

    def start(self):
        """Start listening for shake events."""
        if self._running:
            return

        self._running = True
        target = self._listen_loop_rest if self._use_rest else self._listen_loop
        self._thread = threading.Thread(target=target, daemon=True)
        self._thread.start()
        print("🎧 Firebase shake listener started")

    def stop(self):
        """Stop listening for shake events."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("🛑 Firebase shake listener stopped")

    def _listen_loop(self):
        """Main listening loop for Firebase events."""
        try:
            ref = db.reference('shakes')

            def on_event(message):
                if message.data is None:
                    return
                try:
                    self._process_event_data(message.path, message.data)
                except Exception as exc:
                    print(f"Error processing shake event: {exc}")

            ref.listen(on_event)
            
            # Keep alive
            while self._running:
                time.sleep(1)
                self._cleanup_expired_shakes()
        except Exception as e:
            print(f"❌ Firebase listener error: {e}")
            if "default credentials" in str(e).lower():
                self._use_rest = True
                print("ℹ️  Falling back to RTDB REST polling (public/test mode)")
                if self._running:
                    self._listen_loop_rest()
                return
            if self._running:
                time.sleep(2)
                self._listen_loop()  # Retry

    def _listen_loop_rest(self):
        """Fallback: poll RTDB via REST when credentials are unavailable."""
        last_error_at = 0.0
        while self._running:
            current_sec = int(time.time())
            try:
                data = self._fetch_shakes_for_second(current_sec)
                if isinstance(data, dict):
                    for user_id, payload in data.items():
                        timestamp_sec = self._parse_timestamp_sec(payload, current_sec)
                        self._record_shake(user_id, timestamp_sec)
                self._cleanup_expired_shakes()
            except Exception as exc:
                now = time.time()
                if now - last_error_at > 5:
                    print(f"❌ Firebase REST polling error: {exc}")
                    last_error_at = now
            time.sleep(0.25)

    def _cleanup_expired_shakes(self):
        """Remove shake events older than shake_timeout."""
        with self._lock:
            current_time = int(time.time())
            expired = [
                uid for uid, ts in self._shake_events.items()
                if current_time - ts > self.shake_timeout
            ]
            for uid in expired:
                del self._shake_events[uid]

    def get_wind_value(self) -> int:
        """
        Get current wind value (0-100) based on active shakes.
        
        Calculation:
        - Count unique active shake events (0 to max_concurrent_shakes)
        - Scale to 0-100 range
        - Returns: (count / max_concurrent_shakes) * wind_max
        """
        with self._lock:
            self._cleanup_expired_shakes()
            current_sec = int(time.time())
            active_count = sum(1 for ts in self._shake_events.values() if ts == current_sec)
            active_count = min(active_count, self.max_concurrent_shakes)

        wind_value = 0
        if self.max_concurrent_shakes > 0:
            wind_value = int((active_count / self.max_concurrent_shakes) * self.wind_max)
        return wind_value

    def _record_shake(self, user_id: str, timestamp_sec: int) -> None:
        if not user_id:
            return
        with self._lock:
            self._shake_events[user_id] = timestamp_sec

    def _fetch_shakes_for_second(self, timestamp_sec: int):
        base_url = self.firebase_url.rstrip("/")
        url = f"{base_url}/shakes/{timestamp_sec}.json"
        with urllib.request.urlopen(url, timeout=2) as response:
            raw = response.read().decode("utf-8")
        if not raw or raw == "null":
            return None
        return json.loads(raw)

    def _parse_timestamp_sec(self, payload, fallback_sec) -> int:
        timestamp_sec = None
        if isinstance(payload, dict):
            timestamp_sec = payload.get("timestamp") or payload.get("timestamp_sec")
        if timestamp_sec is None:
            timestamp_sec = fallback_sec
        try:
            return int(timestamp_sec)
        except (TypeError, ValueError):
            return int(time.time())

    def _process_second_bucket(self, sec_key, bucket_data) -> None:
        if not isinstance(bucket_data, dict):
            return
        for user_id, payload in bucket_data.items():
            timestamp_sec = self._parse_timestamp_sec(payload, sec_key)
            self._record_shake(user_id, timestamp_sec)

    def _process_event_data(self, path: str, data) -> None:
        parts = [part for part in path.split("/") if part]

        if not parts:
            if isinstance(data, dict):
                for sec_key, bucket_data in data.items():
                    self._process_second_bucket(sec_key, bucket_data)
            return

        if len(parts) >= 2:
            sec_key, user_id = parts[0], parts[1]
            timestamp_sec = self._parse_timestamp_sec(data, sec_key)
            self._record_shake(user_id, timestamp_sec)
            return

        sec_key = parts[0]
        if isinstance(data, dict) and "user_id" in data:
            user_id = data.get("user_id", "unknown")
            timestamp_sec = self._parse_timestamp_sec(data, sec_key)
            self._record_shake(user_id, timestamp_sec)
            return

        self._process_second_bucket(sec_key, data)
