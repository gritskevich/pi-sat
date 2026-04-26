"""
This setup helper is deprecated.

All setup is now handled by the top-level `Justfile` to keep a single
virtual environment and avoid duplication. To set up everything, run:

    just install

This file remains only as documentation for existing references.
"""

import os
import subprocess

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
APP_DIR = os.path.join(ROOT_DIR, "app")


def download_resources():
    try:
        subprocess.run("./download_resources.sh", shell=True, cwd=APP_DIR, check=True)
        print("Downloading inference files.")
    except subprocess.CalledProcessError:
        print("Inference files download failed.")


def main():
    print("This setup is deprecated. Use 'just install' at repo root.")
    # Still allow resource download if someone runs this directly
    download_resources()


if __name__ == "__main__":
    main()
