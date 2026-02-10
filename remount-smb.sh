#!/bin/bash

# SMB Remount Script with GUI Credential Prompts
# This script will prompt you for credentials via macOS dialogs

echo "🔧 SMB Remount with Optimized Settings"
echo ""

# Get input via GUI dialogs
SERVER_IP=$(osascript -e 'text returned of (display dialog "Enter Windows 11 machine IP address:\n(e.g., 192.168.1.100)" default answer "" with title "SMB Remount")' 2>/dev/null)

if [ -z "$SERVER_IP" ]; then
    echo "❌ Cancelled by user"
    exit 1
fi

USERNAME=$(osascript -e 'text returned of (display dialog "Enter Windows username:" default answer "" with title "SMB Remount")' 2>/dev/null)

if [ -z "$USERNAME" ]; then
    echo "❌ Cancelled by user"
    exit 1
fi

PASSWORD=$(osascript -e 'password returned of (display dialog "Enter Windows password:" default answer "" with hidden answer true with title "SMB Remount")' 2>/dev/null)

if [ -z "$PASSWORD" ]; then
    echo "❌ Cancelled by user"
    exit 1
fi

echo ""
echo "📍 Settings:"
echo "  IP: $SERVER_IP"
echo "  Username: $USERNAME"
echo "  Share: 3D-Models"
echo ""

# Unmount existing mount
echo "🔓 Unmounting current share..."
umount /Volumes/3D-Files 2>/dev/null
sleep 1

# Mount with optimized parameters
echo "🔐 Mounting with optimized SMB3 settings..."
mount_smbfs -o rw,vers=3,iosize=131072,noalloc,noacl,nobrowse \
  "//${USERNAME}:${PASSWORD}@${SERVER_IP}/3D-Models" /Volumes/3D-Files 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Mount successful!"
    echo ""
    echo "📊 Mount details:"
    mount | grep 3D-Files
    echo ""
    echo "🚀 Ready to resume indexing"
else
    echo "❌ Mount failed. Check IP, username, and password."
    exit 1
fi
