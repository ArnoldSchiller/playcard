##### 📲 Install Playcard on your Android device
adb must be installed and the device must be connected for this to work ```adb devices``` should display at least one device.

To install the Playcard app directly from this repository, run the following command on your computer with ADB installed and a connected Android device:

```bash
curl -s https://raw.githubusercontent.com/ArnoldSchiller/playcard/main/example/install_from_git.sh | bash
```
This will:

    Detect your device's architecture

    Download the correct APK from GitHub

    Remove any previously installed version

    Install the app onto your device

💡 No need to manually choose your CPU type or download anything yourself!
