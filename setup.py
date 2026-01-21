"""
Setup script for Pi-Sat voice assistant package
Enables editable installation: pip install -e .
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="pi-sat",
    version="2.0.0",
    description="Local-first voice assistant for Raspberry Pi 5 with Hailo AI accelerator",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Pi-Sat Team",
    python_requires=">=3.8",
    packages=find_packages(exclude=["tests", "tests.*", "scripts", "hailo_examples"]),
    py_modules=["config"],
    install_requires=[
        "pyaudio>=0.2.11",
        "soundfile>=0.12.1",
        "librosa>=0.10.0",
        "scipy>=1.10.0",
        "webrtcvad>=2.0.10",
        # openwakeword installed separately in pi-sat.sh (Python 3.13 needs --no-deps + onnxruntime)
        "numpy>=1.26.4",
        "transformers>=4.30.0",
        "torch>=2.0.0",
        "python-mpd2>=3.1.0",
        "thefuzz>=0.20.0",
        "python-Levenshtein>=0.21.0",
    ],
    extras_require={
        "rpi": [
            "rpi-ws281x>=5.0.0",
            "RPi.GPIO>=0.7.1",
        ],
        "test": [
            "pytest>=7.4.0",
            "pytest-timeout>=2.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "pi-sat=modules.orchestrator:main",
        ],
    },
)


