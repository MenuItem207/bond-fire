import argparse
import json
import socket
import time
import urllib.request


def fetch_shakes(database_url: str, timestamp_sec: int):
    base_url = database_url.rstrip("/")
    url = f"{base_url}/shakes/{timestamp_sec}.json"
    with urllib.request.urlopen(url, timeout=2) as response:
        raw = response.read().decode("utf-8")
    if not raw or raw == "null":
        return {}
    return json.loads(raw)


def compute_wind(shakes: dict, max_concurrent_shakes: int, wind_max: int) -> int:
    if not isinstance(shakes, dict):
        return 0
    count = len(shakes.keys())
    if max_concurrent_shakes <= 0:
        return 0
    wind = int((min(count, max_concurrent_shakes) / max_concurrent_shakes) * wind_max)
    return max(0, min(wind_max, wind))


def main() -> int:
    parser = argparse.ArgumentParser(description="RTDB wind bridge (UDP).")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--max-concurrent-shakes", type=int, default=5)
    parser.add_argument("--wind-max", type=int, default=100)
    parser.add_argument("--poll-interval", type=float, default=0.25)
    parser.add_argument("--udp-host", default="127.0.0.1")
    parser.add_argument("--udp-port", type=int, default=4211)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(
        f"RTDB bridge sending wind to {args.udp_host}:{args.udp_port} (poll {args.poll_interval}s)",
        flush=True,
    )
    last_error_at = 0.0

    while True:
        timestamp_sec = int(time.time())
        try:
            shakes = fetch_shakes(args.database_url, timestamp_sec)
            wind = compute_wind(shakes, args.max_concurrent_shakes, args.wind_max)
            payload = json.dumps({"wind": wind}).encode("utf-8")
            sock.sendto(payload, (args.udp_host, args.udp_port))
            print(f"Sent wind={wind} from {timestamp_sec}", flush=True)
        except Exception as exc:
            now = time.time()
            if now - last_error_at > 5:
                print(f"RTDB bridge error: {exc}")
                last_error_at = now
        time.sleep(max(0.05, args.poll_interval))


if __name__ == "__main__":
    raise SystemExit(main())
