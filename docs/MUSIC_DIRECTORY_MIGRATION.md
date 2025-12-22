# Music Directory Migration (Legacy Note)

Current expected layout is simple:

- MPD: `~/.mpd/mpd.conf` → `music_directory "~/Music"`
- Pi‑Sat: `config.py` → `MUSIC_LIBRARY = ~/Music`

If music doesn’t play after a reorg:

```bash
mpc update
mpc stats
mpc outputs
```

Installation details live in `INSTALL.md`.
