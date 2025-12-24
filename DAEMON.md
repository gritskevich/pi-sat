# Pi-Sat Daemon Mode

Run Pi-Sat as a system service with automatic startup and crash recovery.

## Quick Start

### Install Daemon
```bash
sudo ./install-daemon.sh install
```

This will:
- Install Pi-Sat as a systemd service
- Enable auto-start on boot
- Configure automatic restart on crash (5 second delay)
- Start the service immediately

### Check Status
```bash
sudo systemctl status pi-sat
```

### View Live Logs
```bash
sudo journalctl -u pi-sat -f
```

### Uninstall Daemon
```bash
sudo ./install-daemon.sh uninstall
```

## Management Commands

### Start/Stop/Restart
```bash
sudo systemctl start pi-sat      # Start service
sudo systemctl stop pi-sat       # Stop service
sudo systemctl restart pi-sat    # Restart service
sudo systemctl status pi-sat     # Check status
```

### Enable/Disable Auto-Start
```bash
sudo systemctl enable pi-sat     # Enable auto-start on boot
sudo systemctl disable pi-sat    # Disable auto-start
```

### Logs
```bash
# View live logs (follow mode)
sudo journalctl -u pi-sat -f

# View last 100 lines
sudo journalctl -u pi-sat -n 100

# View logs since boot
sudo journalctl -u pi-sat -b

# View logs from specific time
sudo journalctl -u pi-sat --since "1 hour ago"
sudo journalctl -u pi-sat --since "2024-12-23 10:00"

# Search logs
sudo journalctl -u pi-sat | grep ERROR
```

## Health Monitoring

The service automatically restarts on crash. To check if restarts have occurred:

```bash
# Show service restart count
systemctl show pi-sat -p NRestarts

# Show service uptime
systemctl show pi-sat -p ActiveEnterTimestamp

# Full service details
systemctl show pi-sat
```

## Configuration

Service file: `/etc/systemd/system/pi-sat.service`

After editing the service file:
```bash
sudo systemctl daemon-reload
sudo systemctl restart pi-sat
```

### Key Settings

- **Restart Policy:** `Restart=always` (always restart on failure)
- **Restart Delay:** `RestartSec=5` (5 seconds between restart attempts)
- **Shutdown Timeout:** `TimeoutStopSec=30` (30s for graceful shutdown)
- **Kill Signal:** `SIGINT` (graceful shutdown, like CTRL+C)

### Optional: Resource Limits

Uncomment in `pi-sat.service` to enable:
```ini
LimitNOFILE=1024      # Max open files
MemoryMax=512M        # Max memory usage
```

## Troubleshooting

### Service won't start
```bash
# Check detailed status
sudo systemctl status pi-sat -l

# Check for errors in service file
sudo systemd-analyze verify /etc/systemd/system/pi-sat.service

# Test manually
cd /home/dmitry/pi-sat
./venv/bin/python -u main.py
```

### Service keeps restarting
```bash
# View crash logs
sudo journalctl -u pi-sat -n 200

# Check for recent crashes
sudo journalctl -u pi-sat --since "10 minutes ago"
```

### Logs not appearing
- Logs go to systemd journal (not file)
- Use `journalctl -u pi-sat` to view
- Python stdout/stderr are captured automatically with `-u` flag

### Changes not taking effect
```bash
# Always reload after editing service file
sudo systemctl daemon-reload
sudo systemctl restart pi-sat
```

## Running Mode Comparison

| Mode | Command | Auto-Start | Auto-Restart | Logs | Use Case |
|------|---------|------------|--------------|------|----------|
| **Interactive** | `./pi-sat.sh run` | No | No | Console | Development, testing |
| **Debug** | `./pi-sat.sh run_debug` | No | No | Console + verbose | Debugging |
| **Daemon** | `sudo systemctl start pi-sat` | Yes | Yes | journalctl | Production, always-on |

## Best Practices

1. **Test first:** Run interactively to verify everything works before installing daemon
2. **Check logs:** Use `journalctl -u pi-sat -f` to monitor after installation
3. **Graceful updates:** Stop daemon before updating code: `sudo systemctl stop pi-sat`
4. **Restart after config changes:** `sudo systemctl restart pi-sat`

## Advanced: Multiple Instances

To run multiple Pi-Sat instances (e.g., different rooms):

1. Copy service file with new name: `cp pi-sat.service pi-sat-bedroom.service`
2. Edit to use different config/directory
3. Install: `sudo cp pi-sat-bedroom.service /etc/systemd/system/`
4. Enable: `sudo systemctl enable --now pi-sat-bedroom`

## Sources

Based on systemd best practices from:
- [Raspberry Pi Forums - systemd Python scripts](https://forums.raspberrypi.com/viewtopic.php?t=343733)
- [The Digital Picture Frame - systemd guide](https://www.thedigitalpictureframe.com/ultimate-guide-systemd-autostart-scripts-raspberry-pi/)
- [Raspberry Pi Spy - Autorun Python on boot](https://www.raspberrypi-spy.co.uk/2015/10/how-to-autorun-a-python-script-on-boot-using-systemd/)
