# Firmware build and security profile

The supported compiler is **ESPHome 2026.9.1**, upstream commit
`0b2b16e664ecfc0add37f3435db1c2140b8a687e`. The build uses the official image
`ghcr.io/esphome/esphome:2026.9.1@sha256:776a845d508909bf426d2ee7bdd81796361ebe6a7f091807ce1d6d0b48985413`.
The YAML also rejects compilers older than 2026.9.1. Under this compiler,
`framework: arduino / version: recommended` resolves to Arduino 3.3.11 on ESP-IDF
5.5.5. Updating the compiler requires repeating configuration and build checks.
This profile does not describe firmware already installed on a device.

## Local configuration

Copy `secrets.yaml.example` to `secrets.yaml` and replace every null value.
Keep that file private (`chmod 600 esphome/secrets.yaml` from the repository root).
It and generated build directories are ignored by Git. Do not force-add them;
compiled firmware contains credentials and must also be kept private.

For a **new device**, generate a unique API/OTA key from 32 operating-system random
bytes, then put the printed value in `api_encryption_key`:

```sh
python3 -c 'import base64, secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())'
```

Do not replace an existing device's API key during migration. Configure clients
with the same key. Length validation does not establish randomness: never use
example, repeated, reused or guessed key bytes. Use a strong unique fallback-AP
password as well.

`ct_calibration_points` must be a list of at least two appropriate **measured**
`input -> output` points for the existing ADC-to-current filter. The example's
empty list intentionally fails validation. There are no verified default points.
The synthetic two-point table used in CI is only a compiler fixture and must not
be flashed or used as meter calibration.

The template retains its original ADC sampling, nominal 230 V, power factor 1 and
sign-processing algorithms. It does not establish true RMS current, actual real
power or import/export direction. Validate the installed circuit and readings
against appropriate reference instrumentation before any control use. The energy
integrators compute watt-hours; their `multiply: 0.001` filters convert that value
to the already-declared kWh unit, before the existing reverse-energy sign filter.

GPIO2 remains a strapping pin; follow the board's electrical requirements. The
fallback Wi-Fi AP has no captive portal or web server and does not provide a web
configuration/recovery page. This profile does not add a plaintext web OTA route.

## Validation and local build

From the repository root, run the same synthetic configuration checks and full
compile as CI. This reads the tracked YAML, creates only temporary synthetic
secrets/builds, checks invalid configurations and encrypted build flags, then
removes the temporary firmware. It never uploads to a device:

```sh
docker run --rm --volume "$PWD:/workspace:ro" --workdir /workspace \
  --entrypoint python \
  ghcr.io/esphome/esphome:2026.9.1@sha256:776a845d508909bf426d2ee7bdd81796361ebe6a7f091807ce1d6d0b48985413 \
  tests/firmware/check_profile.py --compile
```

After supplying your actual local secrets and calibration, a separate **compile**
creates private firmware for that configuration, without flashing it:

```sh
docker run --rm --volume "$PWD/esphome:/config" --workdir /config \
  --entrypoint python \
  ghcr.io/esphome/esphome:2026.9.1@sha256:776a845d508909bf426d2ee7bdd81796361ebe6a7f091807ce1d6d0b48985413 \
  -m esphome compile grid-sensor.yaml
```

Compilation proves neither electrical safety nor measurement accuracy. Provision
or update the actual device only after reviewing its configuration, backup and
recovery procedure. Repository CI does not perform that action.

## Required encrypted OTA and migration

The final YAML uses `ota: platform: esphome / encryption:` and inherits the static
native API key. ESPHome 2026.9.1 uses Noise NNpsk0 (Curve25519,
ChaCha20-Poly1305 and SHA-256) for these authenticated channels. Required encryption
prevents both the device and the uploader from falling back to plaintext OTA.
Do not combine `password:` and `encryption:`. MQTT traffic is not protected by this
API/OTA profile: the current MQTT configuration remains plaintext and requires
appropriate broker ACLs, isolation and a trusted network.

For a new device, provision the final encrypted configuration through the
appropriate serial procedure. An existing password-OTA device needs the
[upstream two-stage migration](https://esphome.io/components/ota/esphome/#enabling-encryption-on-an-existing-device):

1. Preserve its **existing API key and OTA password**. In a separate local bridge
   configuration, retain `ota.password` instead of `ota.encryption`, compile with
   ESPHome 2026.9.1 and install through the reviewed device procedure. Confirm the
   running device reports `Encryption: offered, plaintext accepted` before going
   further. An older device cannot offer encryption yet: this first upload can be
   plaintext and expose all embedded secrets. Prefer serial provisioning; otherwise
   use only a controlled trusted local network. Do not claim this stage is the
   final secure profile.
2. With the same API key, switch to the final `ota.encryption` configuration and
   remove `ota.password`. Install and verify `Encryption: required` on the actual
   device. Simply enabling encryption in the uploader before stage 1 is complete
   refuses the update; it does not securely bootstrap an old device.

Do not generate a new API key halfway through this process. ESPHome 2026.9.1 does
not support this profile's key rotation over OTA. If the key is lost or compromised,
reprovision through serial and update clients with the new key. Keep transitional
bridge files and credentials local; they are not repository defaults.

Noise requests random bytes through ESPHome's ESP32 hardware RNG integration.
This profile uses active Wi-Fi with power saving disabled; the ESP-IDF hardware
entropy conditions apply. This is source/build evidence, not a measurement of
physical RNG health or deployed key entropy. See the
[OTA documentation](https://esphome.io/components/ota/esphome/) and
[ESP-IDF 5.5.5 RNG documentation](https://docs.espressif.com/projects/esp-idf/en/v5.5.5/esp32/api-reference/system/random.html).
