#!/usr/bin/env bash
set -euo pipefail

sudo ubuntu-drivers install

echo
echo "driver installed, reboot before checking it with nvidia-smi"
