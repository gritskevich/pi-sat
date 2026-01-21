# Auto-Start Configuration

Pi-Sat can automatically start on boot using systemd.

## Systemd Service

Service file: `/etc/systemd/system/pi-sat.service`

```ini
[Unit]
Description=Pi-Sat Voice Assistant
After=network.target sound.target mpd.service
Requires=sound.target

[Service]
Type=simple
User=dmitry
WorkingDirectory=/home/dmitry/pi-sat
ExecStart=/home/dmitry/pi-sat/pi-sat.sh run
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

## Commands

```bash
# Enable auto-start on boot
sudo systemctl enable pi-sat

# Start service now
sudo systemctl start pi-sat

# Stop service
sudo systemctl stop pi-sat

# Restart service
sudo systemctl restart pi-sat

# Check status
sudo systemctl status pi-sat

# View logs (live)
sudo journalctl -u pi-sat -f

# View logs (last 100 lines)
sudo journalctl -u pi-sat -n 100

# Disable auto-start
sudo systemctl disable pi-sat
```

## Installation

The systemd service can be installed via the installer:

```bash
./pi-sat.sh install
```

Or manually:

```bash
sudo cp /path/to/pi-sat.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pi-sat
```

## Troubleshooting

### Service won't start

Check logs:
```bash
sudo journalctl -u pi-sat -n 50
```

Common issues:
- Hailo driver not loaded: `lsmod | grep hailo`
- Audio devices not ready: `aplay -l && arecord -l`
- MPD not running: `systemctl status mpd`

### Restart after crash

The service is configured with `Restart=on-failure` and will automatically restart if it crashes.

## Hailo Driver Auto-Load

The Hailo PCIe driver must be loaded before Pi-Sat starts.

Add to `/etc/modules`:
```
hailo_pci
```

Verify:
```bash
lsmod | grep hailo
ls -l /dev/hailo0
```

## Manual Testing

To test without systemd:

```bash
./pi-sat.sh run
```

Or with debug mode:

```bash
./pi-sat.sh run_debug
```
