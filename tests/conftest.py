import os
import sys
from pathlib import Path
import config

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def pytest_sessionfinish(session, exitstatus):
    """Cleanup long-running resources to ensure pytest exits cleanly."""
    if config.STT_BACKEND != "hailo":
        if os.getenv("PISAT_PYTEST_FORCE_EXIT", "0") == "1":
            os._exit(exitstatus)
        return
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
