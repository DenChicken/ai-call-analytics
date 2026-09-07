#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y postgresql

sudo systemctl enable --now postgresql

echo
echo "postgresql installed"
echo
echo "the database still has to be created and made reachable from the containers;"
echo "deploy.py init prints those steps with the values from deploy.toml"
