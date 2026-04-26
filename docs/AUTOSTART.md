# Auto-Start Configuration

Pi-Sat auto-starts on boot via a **systemd user service** under `dmitry`.

## Why user-level (not system)

| Reason | Detail |
|---|---|
| Audio is per-user | PipeWire/WirePlumber/MPD all live in `user@1000` — user unit inherits env (no `XDG_RUNTIME_DIR`/`PULSE_SERVER` workarounds). |
| No `%U` UID gotcha | In a system unit, `%U` expands to 0 (manager UID), not `User=` UID — silently broke MAX_VOLUME volume control. |
| Natural ordering | `Wants=mpd.service` resolves to user MPD directly, no `Requires=user@1000.service` chain. |
| Single-user appliance | Convention favors system services; function favors user. |

Boot autostart works because `loginctl enable-linger dmitry` keeps `user@1000` alive at boot.

## Service File

Source of truth: `pi-sat.service` in repo root. Installed at `~/.config/systemd/user/pi-sat.service`.

```ini
[Unit]
Description=Pi-Sat Voice-Controlled Music Player
After=mpd.service sound.target
Wants=mpd.service

[Service]
Type=simple
WorkingDirectory=/home/dmitry/pi-sat
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/just run

Restart=always
RestartSec=5

KillSignal=SIGINT
TimeoutStopSec=30

StandardOutput=journal
StandardError=journal
SyslogIdentifier=pi-sat

[Install]
WantedBy=default.target
```

`just run` runs the `_mpd` helper recipe as a defense-in-depth safety net in case user MPD isn't up.

## Installation

One-time setup (linger + install):

```bash
sudo loginctl enable-linger "$USER"
mkdir -p ~/.config/systemd/user
cp /home/dmitry/pi-sat/pi-sat.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now pi-sat.service
```

⚠️ Do NOT also install at `/etc/systemd/system/pi-sat.service` — both would race for `/dev/hailo0` (single VDevice) and one fails with `HAILO_OUT_OF_PHYSICAL_DEVICES`.

## Commands

```bash
# Status / logs
systemctl --user status pi-sat
journalctl --user -u pi-sat -f          # live
journalctl --user -u pi-sat -n 100      # last 100 lines

# Lifecycle
systemctl --user start pi-sat
systemctl --user stop pi-sat
systemctl --user restart pi-sat

# Autostart
systemctl --user enable pi-sat          # on
systemctl --user disable pi-sat         # off
```

No `sudo` needed for any of these.

## Troubleshooting

### Service won't start

```bash
journalctl --user -u pi-sat -n 50
```

Common issues:
- Hailo driver not loaded: `lsmod | grep hailo`, `ls /dev/hailo0`
- Audio devices not ready: `aplay -l && arecord -l`
- MPD not running: `systemctl --user status mpd`
- **Two pi-sat units**: check `ls /etc/systemd/system/pi-sat.service` — must NOT exist.

### `HAILO_OUT_OF_PHYSICAL_DEVICES`

A second pi-sat (or another Hailo client) is already holding `/dev/hailo0`. Kill duplicates: `pgrep -fa orchestrator.py`.

### Hailo driver auto-load

Required at boot — verified entry in `/etc/modules`:

```
hailo_pci
```

## Manual Testing (without systemd)

```bash
just run         # foreground
just run-debug   # foreground + RMS + confidence scores
```
