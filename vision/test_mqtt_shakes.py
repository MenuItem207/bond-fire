#!/usr/bin/env python3
"""
MQTT Shake Event Test Publisher

Simulates shake events from multiple users to test the vision system's
MQTT shake listener without needing actual mobile devices.

Usage:
    python test_mqtt_shakes.py                 # Single shake
    python test_mqtt_shakes.py --continuous    # Continuous shakes
    python test_mqtt_shakes.py --users 5       # Simulate 5 users
"""

import argparse
import json
import time
import random
from datetime import datetime

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Error: paho-mqtt not installed")
    print("Install with: pip install paho-mqtt")
    exit(1)


def on_connect(client, userdata, flags, rc, properties=None):
    """Callback when MQTT client connects."""
    if rc == 0:
        print("✅ Connected to MQTT broker")
    else:
        print(f"❌ Connection failed with code {rc}")


def on_publish(client, userdata, mid, reason_code=None, properties=None):
    """Callback when message is published."""
    print(f"📤 Published shake event (mid={mid})")


def publish_shake(client, user_id):
    """Publish a single shake event."""
    message = {
        "user_id": user_id,
        "timestamp": time.time()
    }
    
    payload = json.dumps(message)
    result = client.publish("bondfire/shakes", payload, qos=0)
    
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"🔥 Shake from {user_id} at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
    else:
        print(f"⚠️ Failed to publish: {result.rc}")


def main():
    parser = argparse.ArgumentParser(description="Test MQTT shake detection")
    parser.add_argument("--broker", default="test.mosquitto.org",
                       help="MQTT broker address (default: test.mosquitto.org)")
    parser.add_argument("--port", type=int, default=1883,
                       help="MQTT broker port (default: 1883)")
    parser.add_argument("--users", type=int, default=1,
                       help="Number of simulated users (default: 1)")
    parser.add_argument("--continuous", action="store_true",
                       help="Send continuous shake events (Ctrl+C to stop)")
    parser.add_argument("--interval", type=float, default=1.0,
                       help="Interval between shakes in seconds (default: 1.0)")
    
    args = parser.parse_args()
    
    # Generate user IDs
    user_ids = [f"test_user_{i+1}" for i in range(args.users)]
    
    print(f"🔌 Connecting to {args.broker}:{args.port}...")
    print(f"👥 Simulating {args.users} user(s)")
    
    # Create MQTT client
    client = mqtt.Client(
        client_id=f"test_publisher_{int(time.time())}",
        protocol=mqtt.MQTTv5
    )
    client.on_connect = on_connect
    client.on_publish = on_publish
    
    # Connect to broker
    try:
        client.connect(args.broker, args.port, keepalive=60)
        client.loop_start()
        
        # Wait for connection
        time.sleep(1)
        
        if args.continuous:
            print("\n🔄 Continuous mode - Press Ctrl+C to stop\n")
            try:
                shake_count = 0
                while True:
                    # Randomly select user(s) to shake
                    num_shakers = random.randint(1, min(args.users, 5))
                    shakers = random.sample(user_ids, num_shakers)
                    
                    for user_id in shakers:
                        publish_shake(client, user_id)
                        shake_count += 1
                    
                    if shake_count % 10 == 0:
                        print(f"📊 Total shakes sent: {shake_count}")
                    
                    time.sleep(args.interval)
                    
            except KeyboardInterrupt:
                print(f"\n\n⏹️ Stopped. Total shakes sent: {shake_count}")
        else:
            # Single burst mode
            print("\n🔥 Sending shake burst...\n")
            for user_id in user_ids:
                publish_shake(client, user_id)
                time.sleep(0.1)  # Small delay between users
            
            print(f"\n✅ Sent {len(user_ids)} shake event(s)")
        
        # Wait for messages to be sent
        time.sleep(1)
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        print("👋 Disconnected from broker")


if __name__ == "__main__":
    main()
