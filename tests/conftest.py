import os


def pytest_sessionfinish(session, exitstatus):
    """Cleanup long-running resources to ensure pytest exits cleanly."""
    try:
        from modules.hailo_stt import HailoSTT
        pipeline = getattr(HailoSTT, "_pipeline", None)
        if pipeline is not None:
            try:
                pipeline.stop()
            except Exception:
                pass
            try:
                HailoSTT._pipeline = None
                HailoSTT._initialized = False
            except Exception:
                pass
    except Exception:
        pass

    # Optional hard-exit for stubborn native threads (Hailo SDK, etc.)
    # Default is normal pytest exit so output is not truncated.
    if os.getenv("PISAT_PYTEST_FORCE_EXIT", "0") == "1":
        os._exit(exitstatus)

