# Install the ESP32 firmware from your browser

**Build in ESPHome Device Builder, then flash from your browser.** Python and
PlatformIO do not need to be installed on the USB-connected computer. Desktop
Chrome or Edge can write your own factory image through
[ESPHome Web](https://web.esphome.io/).

This repository contains two different components:

- **ESP32 firmware:** [`esphome/grid-sensor.yaml`](../esphome/grid-sensor.yaml),
  compiled for the actual sensor circuit and your private configuration.
- **Venus OS host software:** the Python/D-Bus service distributed in GitHub
  releases as archives and Python packages. Those downloads are **not ESP32
  firmware** and must never be passed to a browser flasher.

## 1. Configure and build on the server

1. Open ESPHome Device Builder on Home Assistant or another server. Follow the
   [official installation guide](https://esphome.io/guides/installing_esphome/)
   if it is not already available.
2. Add `esphome/grid-sensor.yaml` as a device configuration. It targets a classic
   ESP32 DevKit (`esp32dev`), with ADC input on GPIO34 and the documented circuit.
   Do not select an ESP32-C3/S3/C6 or ESP8266 image for a different board.
3. Use the [firmware configuration guide](../esphome/README.md) to supply private
   network/MQTT settings, a unique API/OTA key and **measured CT calibration
   points**. Preserve an existing installation's identity and key. The empty
   calibration template must be completed with real measurements; the synthetic
   CI calibration table is not a device calibration.
4. Review the actual circuit, voltage assumptions and sensing limitations before
   installation. The supplied algorithm is not a validated true-RMS power meter
   and does not establish import/export direction. Do not use it for inverter
   control until the complete measurement path has been independently validated.
5. Choose **Install → Manual download → Factory format**. The server compiles
   and your browser downloads the merged `.factory.bin`. Use the pinned ESPHome
   version documented in the firmware guide; changing versions requires a fresh
   configuration/build check.

Keep the generated image private because it contains your credentials. Do not
upload it to GitHub releases, issues or shared CI artifacts. Nothing in the
browser route requires removing encrypted API/OTA access.

## 2. Flash through ESPHome Web

1. Preserve a known-good backup before changing a working device. Disconnect the
   board only after the circuit has been safely de-energized, and program on a
   low-voltage bench setup isolated from mains and active CT circuits. Never
   leave an energized current-transformer secondary open-circuit.
2. Connect the supported ESP32 to the browser computer with a USB data cable.
3. Open **[ESPHome Web](https://web.esphome.io/)**, choose **Connect**, and select
   the matching serial port.
4. Select **Install** and your downloaded factory image. Review the confirmation
   and any erase option before starting; keep power connected until completion.
   Do not select a generic first-use image in place of your configured firmware.
5. Check the boot logs and network connection, then validate measurements against
   the reference used for calibration. Test the ESP-to-MQTT path before adding
   the separate Venus OS bridge. Successful flashing is not measurement approval.

An advanced alternative is the
[Espressif browser flasher](https://espressif.github.io/esptool-js/), using the
**merged ESP32 factory image at `0x0`**. An OTA-only `.bin` or separate bootloader,
partition and application files require their own documented layout; do not
infer offsets from a filename.

## Release policy for firmware

Public release archives install the host service. CI's temporary ESPHome images
use synthetic secrets and calibration solely to check compilation, and are
removed after validation. They must not become downloadable install buttons.

A future public firmware release needs a reviewed runtime configuration and
calibration flow, exact board/flash support, checksums and a credential-free
factory image. The currently supported browser path uses your own personalised
factory image from Device Builder.

## Browser and USB troubleshooting

Use desktop Chrome or Edge on Windows, macOS, or Linux and open
[ESPHome Web](https://web.esphome.io/) directly over HTTPS. The browser must expose the Web Serial API (`navigator.serial`). If it does
not, use a current desktop Chrome or Edge; do not assume mobile/iOS support. The ESP device connects to the
computer running the browser; it does not need to connect to the Home Assistant
server's USB port.

- **No serial port:** use a USB data cable, try a direct USB port, and check that
  the USB-to-serial adapter appears in the operating system. Install the adapter
  manufacturer's CP210x or CH340 driver only if the operating system needs it.
- **Port busy or access denied:** close other browser tabs, serial monitors and
  ESPHome log sessions. On Linux, check your distribution's serial-port group
  permissions and sign in again after changing them; do not run the browser as
  root or make all serial devices world-writable.
- **Cannot connect to the bootloader:** follow the exact board's BOOT/EN procedure.
  For an ESP32 DevKit with those buttons, hold BOOT, briefly press EN/RESET, then
  release BOOT once the flasher connects. Do not short unidentified pins.
- **Write errors:** use a shorter data cable and stable USB power. With a generic
  flasher, reduce the serial baud rate before trying again.
- **Image rejected or repeated resets:** stop and verify the chip family, flash
  capacity, board configuration and factory-image format. Do not try arbitrary
  offsets or erase a working device merely to bypass a mismatch.

## Updates and recovery

Keep the original device configuration and its private secrets alongside a
known-good firmware backup. Initial USB installation and encrypted network OTA
are different transports: choosing a browser flasher does not require enabling
an HTTP server, weakening API authentication, or publishing credentials.

For an already working device, use the project's documented OTA update and
migration procedure with its existing identity and credentials. A full serial
factory installation may replace its partition layout or settings. Back up
first and review any erase option before confirming it.

## Upstream instructions

- [ESPHome Device Builder installation](https://esphome.io/guides/installing_esphome/)
- [ESPHome getting started](https://esphome.io/install/getting-started/)
- [ESPHome Web USB installer](https://web.esphome.io/)
- [Espressif generic browser flasher](https://espressif.github.io/esptool-js/)
