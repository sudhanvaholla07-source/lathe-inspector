#!/bin/bash
# Day 1: Hailo-8L bring-up verification.
# Run this on the Pi after physically installing the AI Kit (M.2 HAT+ and
# module) and enabling PCIe in /boot/firmware/config.txt
# (dtparam=pciex1 and dtparam=pciex1_gen=3), then rebooting.

set -e

echo "1. Checking the device is visible on the PCIe bus..."
lspci | grep -i hailo || {
  echo "No Hailo device found on the PCIe bus.";
  echo "Check the HAT+ ribbon cable orientation and that the M.2 module is fully seated.";
  exit 1;
}

echo "2. Checking the HailoRT software stack is installed..."
if ! command -v hailortcli &> /dev/null; then
  echo "hailortcli not found. Install with: sudo apt install hailo-all"
  exit 1
fi

echo "3. Scanning for the device via HailoRT..."
hailortcli scan

echo "4. Reading firmware identity..."
hailortcli fw-control identify

echo "Done. If a device identity printed above, the Hailo-8L is ready for inference later."
