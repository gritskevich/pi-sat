# Event Contract

Pi-Sat uses in-process domain events to keep modules independent.

## Common Fields

All events use:

- `name`: Event name (string).
- `payload`: Event-specific fields (dict).
- `source`: Optional origin module (string).
- `timestamp`: Unix epoch seconds (float).

## Event Names and Payloads

### Input

- `button_pressed`
  - `payload`: `{}` (no fields)
- `button_double_pressed`
  - `payload`: `{}` (no fields)
- `volume_up_requested`
  - `payload`: `{}` (no fields)
- `volume_down_requested`
  - `payload`: `{}` (no fields)

### Playback Control

- `pause_requested`
  - `payload`: `{}` (no fields)
- `continue_requested`
  - `payload`: `{}` (no fields)
- `next_track_requested`
  - `payload`: `{}` (no fields)
- `previous_track_requested`
  - `payload`: `{}` (no fields)
- `set_volume_requested`
  - `payload`: `{ "volume": int }`
- `play_requested`
  - `payload`: `{ "query": str, "matched_file": str, "confidence": float }`
- `play_favorites_requested`
  - `payload`: `{}` (no fields)
- `add_favorite_requested`
  - `payload`: `{}` (no fields)
- `sleep_timer_requested`
  - `payload`: `{ "duration_minutes": int }`
- `repeat_mode_requested`
  - `payload`: `{ "mode": "off" | "single" | "playlist" }`
- `shuffle_requested`
  - `payload`: `{ "enabled": bool }`
- `queue_add_requested`
  - `payload`: `{ "query": str, "play_next": bool }`

### Intent + Search

- `intent_detected`
  - `payload`: `{ "intent_type": str, "confidence": float, "language": str, "text": str, "parameters": dict }`
- `music_search_requested`
  - `payload`: `{ "query": str, "raw_text": str, "language": str }`
- `music_resolved`
  - `payload`: `{ "query": str, "matched_file": str, "confidence": float }`

### Recording

- `recording_started`
  - `payload`: `{}` (no fields)
- `recording_finished`
  - `payload`: `{}` (no fields)

## Event Bus Config

Configured in `config.py`:

- `EVENT_BUS_MAX_QUEUE` (default `1000`)
- `EVENT_BUS_DROP_POLICY` (`drop_new` or `drop_oldest`)
- `EVENT_LOGGER` (`jsonl` or `none`)
- `EVENT_LOG_PATH` (default `logs/events.jsonl`)
