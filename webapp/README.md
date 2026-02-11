# Bond Fire Web App

## Overview
Mobile web app for controlling the Bond Fire installation via shake detection. Users shake their phones to "fan the flames" - shake events are published to an MQTT broker and aggregated by the Python vision system to calculate wind intensity.

## Quick Start

### Development
```bash
# Serve locally
cd webapp
python3 -m http.server 8000

# Open on mobile device (same WiFi network)
# http://<your-ip>:8000
```

### Production
Deploy to any static hosting service:
- GitHub Pages
- Netlify
- Vercel
- Cloudflare Pages
- S3 + CloudFront

## Features

### Shake Detection
- **Accelerometer-based**: Uses DeviceMotionEvent API
- **Threshold**: 20 m/s² total acceleration delta
- **Cooldown**: 500ms between shake events (prevents spam)
- **iOS Permission**: Requests motion sensor access on iOS 13+
- **Fallback**: Tap button if shake doesn't work

### MQTT Communication
- **Broker**: test.mosquitto.org:8081 (WebSocket)
- **Topic**: bondfire/shakes
- **Protocol**: JSON payloads with user_id and timestamp
- **QoS**: 0 (fire-and-forget for low latency)

### User Interface
- **Clean Design**: Gradient background, fire-themed colors
- **Status Indicator**: Shows connection state (connecting/connected/error)
- **Fire Button**: Visual feedback on shake (pulse animation)
- **Statistics**: Personal shake count, active fans
- **Instructions**: Clear usage guide for first-time users

## Technical Details

### Motion Detection Algorithm
```javascript
// Calculate total acceleration delta
const deltaX = Math.abs(acc.x - lastX);
const deltaY = Math.abs(acc.y - lastY);
const deltaZ = Math.abs(acc.z - lastZ);
const totalDelta = deltaX + deltaY + deltaZ;

// Trigger shake if above threshold
if (totalDelta > SHAKE_THRESHOLD) {
    publishShake();
}
```

### MQTT Message Format
```json
{
  "user_id": "user_abc123xyz",
  "timestamp": 1234567890.123
}
```

### User ID Generation
- Stored in localStorage for persistence
- Format: `user_<random9chars>`
- Used to track unique contributors

## Configuration

### Constants (in index.html)
```javascript
const MQTT_BROKER = 'wss://test.mosquitto.org:8081';
const MQTT_TOPIC = 'bondfire/shakes';
const SHAKE_THRESHOLD = 20; // m/s²
const SHAKE_COOLDOWN = 500; // ms
```

### Tuning Shake Sensitivity
- **Increase SHAKE_THRESHOLD**: Less sensitive (harder shake required)
- **Decrease SHAKE_THRESHOLD**: More sensitive (easier to trigger)
- Current value (20) works well for most phones

## Browser Compatibility

### Supported
- ✅ iOS Safari 13+ (with permission prompt)
- ✅ Android Chrome/Firefox
- ✅ Desktop browsers (tap mode only)

### Motion Sensor Support
- **iOS 13+**: Requires user permission via DeviceMotionEvent.requestPermission()
- **Android**: Automatic (no permission needed)
- **Desktop**: No motion sensors, tap button instead

## Deployment Guide

### GitHub Pages (Recommended)
```bash
# 1. Create gh-pages branch
git checkout --orphan gh-pages
git add webapp/*
git commit -m "Deploy webapp"
git push origin gh-pages

# 2. Enable in repo settings
# Settings → Pages → Source: gh-pages, /webapp

# 3. Access at:
# https://<username>.github.io/<repo>/webapp/
```

### Custom Domain
Add CNAME file to webapp/ directory:
```
fire.yourdomain.com
```

Configure DNS:
```
CNAME fire -> <username>.github.io
```

## Security Considerations

### Public MQTT Broker
Currently using test.mosquitto.org (public, no auth):
- ✅ Easy setup for prototyping
- ⚠️ No access control
- ⚠️ Anyone can publish messages
- ⚠️ Rate limiting not guaranteed

### Production Recommendations
1. **Private MQTT Broker**: Deploy Mosquitto on your server
2. **Authentication**: Add username/password
3. **TLS**: Use wss:// with valid certificate
4. **Rate Limiting**: Prevent spam/DoS
5. **Topic ACLs**: Restrict who can publish

### Example Private Broker Setup
```bash
# Install Mosquitto (Ubuntu)
sudo apt install mosquitto mosquitto-clients

# Configure websockets (/etc/mosquitto/conf.d/websockets.conf)
listener 8081
protocol websockets
certfile /etc/letsencrypt/live/yourdomain.com/fullchain.pem
keyfile /etc/letsencrypt/live/yourdomain.com/privkey.pem

# Restart
sudo systemctl restart mosquitto
```

## Troubleshooting

### Motion not detected on iOS
- Ensure permission prompt was accepted
- Try force-reload (Cmd+Shift+R)
- Check Settings → Safari → Motion & Orientation Access

### Shakes not reaching installation
1. Check browser console for MQTT errors
2. Verify MQTT broker connectivity (try mqtt.org client)
3. Check vision system logs for received messages
4. Ensure topics match (bondfire/shakes)

### False positive shakes
- Increase SHAKE_THRESHOLD (current: 20)
- Increase SHAKE_COOLDOWN (current: 500ms)

### Web app offline
- Check hosting service status
- Verify DNS configuration
- Clear browser cache

## Future Enhancements

### Planned Features
- [ ] Progressive Web App (offline support, install prompt)
- [ ] User names/avatars
- [ ] Leaderboard (top fans)
- [ ] Real-time wind visualization
- [ ] Multiple installations support
- [ ] Audio feedback on shake
- [ ] Haptic feedback
- [ ] Dark/light mode toggle

### Technical Improvements
- [ ] Service worker for offline mode
- [ ] IndexedDB for local stats
- [ ] WebRTC for peer discovery
- [ ] Analytics (privacy-friendly)
- [ ] A/B testing for shake threshold

## Analytics (Optional)

### Add Privacy-Friendly Analytics
```html
<!-- Plausible (privacy-focused, no cookies) -->
<script defer data-domain="yourdomain.com" src="https://plausible.io/js/script.js"></script>
```

Track events:
```javascript
// After shake
plausible('Shake', { props: { user_id: userId } });
```

## License
Part of Bond Fire installation project. See main repo for license details.

## Support
For issues or questions, contact the Bond Fire installation team.
