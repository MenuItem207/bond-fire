#!/usr/bin/env python3
"""UDP packet listener for Bond Fire v2.1 protocol.

Listens for JSON packets on UDP port 4210 and displays them in real-time.
Useful for debugging without ESP32 hardware.
"""

import argparse
import json
import socket
import sys
from datetime import datetime
from typing import Any, Dict


def colorize(text: str, color_code: int) -> str:
    """Add ANSI color to text."""
    return f"\033[{color_code}m{text}\033[0m"


def format_state(state: str) -> str:
    """Colorize state names."""
    colors = {
        "IDLE": 36,   # Cyan
        "FIRE": 31,   # Red
        "PARTY": 35,  # Magenta
        "PHONE": 33,  # Yellow
    }
    return colorize(state, colors.get(state, 37))


def format_rgb(rgb: list[int]) -> str:
    """Format RGB as colored text."""
    r, g, b = rgb
    # Use background color for better visibility
    return f"\033[48;2;{r};{g};{b}m   \033[0m ({r},{g},{b})"


def display_packet(packet: Dict[str, Any], show_raw: bool = False) -> None:
    """Display packet in human-readable format."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    print(f"\n{'='*80}")
    print(f"[{timestamp}] Packet v{packet.get('version', '?')}")
    print(f"{'='*80}")
    
    # State and counts
    state = packet.get("state", "UNKNOWN")
    people_count = len(packet.get("people", []))
    phone = packet.get("phone_detected", False)
    fps = packet.get("fps", 0)
    
    print(f"State: {format_state(state)} | People: {people_count} | Phone: {'🚨 YES' if phone else 'NO'} | FPS: {fps:.1f}")
    
    # People tracking
    if people_count > 0:
        print("\nPeople in ROI:")
        for person in packet.get("people", []):
            pid = person.get("id", "?")
            shirt_name = person.get("shirt_name", "Unknown")
            shirt_rgb = person.get("shirt_rgb", [0, 0, 0])
            bbox = person.get("bbox", [0, 0, 0, 0])
            
            color_display = format_rgb(shirt_rgb)
            print(f"  • ID {pid}: {shirt_name} {color_display}")
            print(f"    BBox: [{bbox[0]:.2f}, {bbox[1]:.2f}, {bbox[2]:.2f}, {bbox[3]:.2f}]")
    
    # Dominant palette
    palette = packet.get("dominant_palette", [])
    if palette:
        print("\nDominant Palette:")
        palette_colors = [palette[i:i+3] for i in range(0, len(palette), 3)]
        for rgb in palette_colors:
            print(f"  {format_rgb(rgb)}")
    
    # Prompt
    prompt = packet.get("prompt", "")
    if prompt:
        print(f"\nPrompt: \"{colorize(prompt, 32)}\"")
    
    # Hardware outputs
    mist = packet.get("mist_pwm", 0)
    fan = packet.get("fan_pwm", 0)
    print(f"\nHardware: Mist={mist} | Fan={fan}")
    
    # Effects
    pulse = packet.get("pulse_active", False)
    entry_flash = packet.get("entry_flash_id")
    audio_state = packet.get("audio_state", "SILENT")
    
    effects = []
    if pulse:
        effects.append(colorize("PULSE", 35))
    if entry_flash is not None:
        effects.append(colorize(f"ENTRY_FLASH(ID:{entry_flash})", 33))
    if audio_state != "SILENT":
        effects.append(f"Audio:{colorize(audio_state, 36)}")
    
    if effects:
        print(f"Effects: {' | '.join(effects)}")
    
    # Raw JSON
    if show_raw:
        print(f"\n{colorize('Raw JSON:', 90)}")
        print(json.dumps(packet, indent=2))
    
    print(f"{'='*80}\n")


def listen(port: int, show_raw: bool = False, compact: bool = False) -> None:
    """Listen for UDP packets and display them."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        sock.bind(("", port))
        print(f"{colorize('UDP Listener Started', 32)}")
        print(f"Listening on port {port}...")
        print(f"Press Ctrl+C to stop\n")
        
        packet_count = 0
        while True:
            data, addr = sock.recvfrom(4096)
            packet_count += 1
            
            try:
                packet = json.loads(data.decode("utf-8"))
                
                if compact:
                    # Compact one-line display
                    state = packet.get("state", "?")
                    people = len(packet.get("people", []))
                    phone = "📱" if packet.get("phone_detected") else "  "
                    fps = packet.get("fps", 0)
                    prompt = packet.get("prompt", "")[:40]
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    print(f"[{timestamp}] {format_state(state):8} | {people}p {phone} | {fps:4.1f}fps | {prompt}")
                else:
                    display_packet(packet, show_raw)
                    
            except json.JSONDecodeError as e:
                print(f"{colorize('JSON Error:', 31)} {e}")
                print(f"Raw data: {data[:100]}")
            except Exception as e:
                print(f"{colorize('Error:', 31)} {e}")
    
    except KeyboardInterrupt:
        print(f"\n\n{colorize('Listener stopped', 33)}")
        print(f"Total packets received: {packet_count}")
    finally:
        sock.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Listen for Bond Fire v2.1 UDP packets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic listening
  python packet_listener.py
  
  # Compact mode (one line per packet)
  python packet_listener.py --compact
  
  # Show raw JSON
  python packet_listener.py --raw
  
  # Custom port
  python packet_listener.py --port 5000
        """
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=4210,
        help="UDP port to listen on (default: 4210)"
    )
    
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Show raw JSON for each packet"
    )
    
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact one-line display mode"
    )
    
    args = parser.parse_args()
    
    try:
        listen(args.port, args.raw, args.compact)
    except PermissionError:
        print(f"{colorize('Error:', 31)} Permission denied. Try running with sudo or use a port > 1024")
        sys.exit(1)
    except OSError as e:
        print(f"{colorize('Error:', 31)} {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
