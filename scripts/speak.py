#!/usr/bin/env python3
"""Standalone TTS utility - speaks text or reads from file"""
import sys
import os
from pathlib import Path

import config
from modules.piper_tts import PiperTTS
from modules.logging_utils import setup_logger

logger = setup_logger(__name__)


def main():
    if len(sys.argv) < 2:
        print("Usage: python speak.py <text> | <filename.txt>")
        sys.exit(1)

    arg = sys.argv[1]

    try:
        if arg.endswith('.txt') and Path(arg).exists():
            with open(arg, 'r', encoding='utf-8') as f:
                text = f.read().strip()
        else:
            text = ' '.join(sys.argv[1:])

        if not text:
            logger.error("Empty text provided")
            sys.exit(1)

        tts = PiperTTS(output_device=config.PIPER_OUTPUT_DEVICE)
        success = tts.speak(text)

        if not success:
            logger.error("Failed to speak text")
            sys.exit(1)

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

