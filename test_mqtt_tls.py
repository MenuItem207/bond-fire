#!/usr/bin/env python3
"""Test MQTT TLS connectivity on port 8883."""

import paho.mqtt.client as mqtt
import ssl
import time

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ MQTT TLS Connection successful!")
    else:
        print(f"❌ Connection failed: {rc}")

def on_disconnect(client, userdata, rc):
    pass

print("Testing MQTT TLS on port 8883...")
client = mqtt.Client()
client.on_connect = on_connect
client.on_disconnect = on_disconnect

# Set TLS/SSL
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.tls_insecure_set(True)

try:
    client.connect('test.mosquitto.org', 8883, keepalive=5)
    client.loop_start()
    
    for i in range(15):
        if client.is_connected():
            print("Connection established!")
            break
        time.sleep(0.2)
    
    if not client.is_connected():
        print("⏱️  Still waiting for connection...")
        time.sleep(3)
    
    client.loop_stop()
    client.disconnect()
    print("Test complete.")
    
except Exception as e:
    print(f"❌ Error: {e}")
