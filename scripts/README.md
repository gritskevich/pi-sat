# Scripts

Utility scripts for testing and development.

## speak.py

Standalone TTS utility - speaks text or reads from file.

**Usage:**
```bash
python scripts/speak.py "Hello world"
python scripts/speak.py /path/to/story.txt
```

## test_live.py

Minimal live tests for wake word, STT, and full pipeline.

**Usage:**
```bash
python scripts/test_live.py wake      # Test wake word detection
python scripts/test_live.py stt       # Test STT (record → transcribe)
python scripts/test_live.py pipeline  # Test full pipeline
```

## monitor_connections.sh

Connection monitor - logs WiFi and USB mic status.

**Usage:**
```bash
./scripts/monitor_connections.sh
```

## test_fr.txt

Test file for French TTS testing.

