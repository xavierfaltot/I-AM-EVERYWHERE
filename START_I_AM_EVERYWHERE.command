#!/bin/bash
cd "$(dirname "$0")/bridge"
clear
echo "Starting I AM EVERYWHERE..."
python3 bridge.py
echo
echo "Bridge stopped. Press any key to close."
read -n 1
