#!/usr/bin/env python3
"""Simple MQTT broker connectivity test."""

import paho.mqtt.client as mqtt
import time
import sys

# Test different brokers
BROKERS = [
    ("test.mosquitto.org", 1883, "Test Mosquitto (TCP)"),
    ("broker.hivemq.com", 1883, "HiveMQ Public (TCP)"),
    ("broker.emqx.io", 1883, "EMQX (TCP)"),
]

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connected to {userdata['name']}")
        client.disconnect()
    else:
        print(f"❌ Failed to connect to {userdata['name']}: rc={rc}")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"⚠️  Unexpected disconnection from {userdata['name']}: rc={rc}")

def test_broker(host, port, name):
    print(f"\n🔍 Testing {name} ({host}:{port})...")
    
    client = mqtt.Client()
    client.user_data_set({"name": name})
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    
    try:
        client.connect(host, port, keepalive=5)
        client.loop_start()
        
        # Wait up to 5 seconds for connection
        timeout = time.time() + 5
        while time.time() < timeout and not client.is_connected():
            time.sleep(0.1)
        
        if client.is_connected():
            print(f"  ✅ Connection successful!")
            client.loop_stop()
            client.disconnect()
            return True
        else:
            print(f"  ❌ Connection timeout")
            client.loop_stop()
            return False
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("MQTT Broker Connectivity Test")
    print("=" * 50)
    
    results = {}
    for host, port, name in BROKERS:
        results[name] = test_broker(host, port, name)
    
    print("\n" + "=" * 50)
    print("Summary:")
    print("=" * 50)
    for name, success in results.items():
        status = "✅ WORKS" if success else "❌ FAILED"
        print(f"{status} - {name}")
