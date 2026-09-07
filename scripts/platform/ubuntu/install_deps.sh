#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    ca-certificates

echo
echo "system packages installed, prepare the environment deploy.py runs in:"
echo "  python3 -m venv .venv"
echo "  source .venv/bin/activate"
echo "  pip install -r scripts/requirements.txt"
