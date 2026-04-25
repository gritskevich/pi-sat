# Auto-Start Configuration

Pi-Sat can automatically start on boot using systemd.

## Systemd Service

Service file: `/etc/systemd/system/pi-sat.service` (source of truth: `pi-sat.service` in repo root).

The unit runs as **system service** with `User=dmitry`. `loginctl enable-linger dmitry`
is required so `/run/user/1000` (PipeWire/PulseAudio socket) exists at boot.

```ini
[Unit]
Description=Pi-Sat Voice-Controlled Music Player
After=network.target sound.target user@1000.service
Requires=user@1000.service

[Service]
Type=simple
User=dmitry
WorkingDirectory=/home/dmitry/pi-sat
Environment="PATH=/home/dmitry/pi-sat/venv/bin:/usr/local/bin:/usr/bin:/bin"
# NOTE: %U expands to the *manager* UID (0 for system services), not User=.
# Hardcode UID 1000 (dmitry) so PipeWire/PulseAudio is reachable.
Environment="XDG_RUNTIME_DIR=/run/user/1000"
Environment="PULSE_SERVER=unix:/run/user/1000/pulse/native"
Environment="PYTHONUNBUFFERED=1"

# pi-sat.sh run ensures user-level MPD is started before the orchestrator connects
ExecStart=/home/dmitry/pi-sat/pi-sat.sh run

Restart=always
RestartSec=5

# Graceful shutdown (CTRL+C equivalent)
KillSignal=SIGINT
TimeoutStopSec=30

StandardOutput=journal
StandardError=journal
SyslogIdentifier=pi-sat

[Install]
WantedBy=multi-user.target
```

**Notes:**
- `Requires=user@1000.service` chains the user manager (PipeWire/WirePlumber/MPD live there).
- MPD runs as a **user** unit (`systemctl --user status mpd`), not a system unit. `pi-sat.sh run` calls `ensure_mpd()` as a safety net.
- `Restart=always` masks transient USB enumeration races at boot.

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
