#!/bin/bash

set -e

tag="v2.3.0"
version="2.5.0-5"
framework_version="2.6.0"
artifact_version="ef30488.191113"

function upload_toolchain {
	python3 upload_artifact.py --tag "$tag" --version "$version" --name toolchain-xtensa-esphome --description "Xtensa ESP8266 toolchain for ESPHome" --description-url 'https://github.com/OttoWinter/esp-quick-toolchain' --url "https://github.com/OttoWinter/esp-quick-toolchain/releases/download/v${version}/${1}.xtensa-lx106-elf-${artifact_version}.tar.gz" "${@:2}"
}

upload_toolchain 'aarch64-linux-gnu' --system linux_aarch64 linux_aarch64_be linux_arm64
upload_toolchain 'arm-linux-gnueabihf' --system linux_armv6l linux_armv7l linux_armv8l
upload_toolchain 'i686-linux-gnu' --system linux_i686
upload_toolchain 'i686-w64-mingw32' --system windows_x86
upload_toolchain 'x86_64-apple-darwin14' --system darwin_x86_64 darwin_i386
upload_toolchain 'x86_64-linux-gnu' --system linux_x86_64 linux_x64
upload_toolchain 'x86_64-w64-mingw32' --system windows_amd64
python3 upload_artifact.py --tag "$tag" --version "$framework_version" --url "https://github.com/OttoWinter/esp8266-arduino/releases/download/$framework_version/framework-arduinoespressif8266-2.20600.0.tar.gz" --name framework-arduinoespressif8266-esphome --description "ESP8266 Arduino Framework Fork by ESPHome" --description-url 'https://github.com/OttoWinter/esp8266-arduino'
