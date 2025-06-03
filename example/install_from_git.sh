#!/bin/bash

if ! command -v adb &> /dev/null; then
  echo "❌ adb not found. Please install Android Platform Tools."
  exit 1
fi

echo "🔍 Detecting device architecture..."
ARCH=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')

if [ -z "$ARCH" ]; then
  echo "❌ Failed to detect architecture from device."
  exit 2
fi

FILE="app-$ARCH-release.apk"
URL="https://github.com/ArnoldSchiller/playcard/raw/refs/heads/main/example/$FILE"
TMP_APK="/tmp/$FILE"

echo "🔽 Downloading $FILE for $ARCH..."
curl -L -o "$TMP_APK" "$URL"

if [ $? -ne 0 ]; then
  echo "❌ Download failed. APK not found for $ARCH?"
  exit 3
fi

echo "📦 Removing old version (if any)..."
adb uninstall de.jaquearnoux.playcard_app

echo "📱 Installing APK on device..."
adb install -r "$TMP_APK"

if [ $? -eq 0 ]; then
  echo "✅ Successfully installed $FILE"
else
  echo "❌ Installation failed"
fi

