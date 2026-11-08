#!/bin/bash
# disable-daemons.sh ROOT_IMAGE
# Writes /private/var/db/com.apple.xpc.launchd/disabled.plist into the HFS+ root image FILE
# (on this PC only; does not touch the phone). Disables crash-looping / useless daemons.
# v2: fsck -f -y before mounting; skips labels with no plist in the image.
# Verified earlier (measured): launchd honors disabled.plist on this build (v36).
# UNTESTED: this v2 script itself, and whether each extra daemon is safe to disable.
set -euo pipefail
img=${1:?usage: disable-daemons.sh ROOT_IMAGE}
test -f "$img"

labels=(
	com.apple.bluetoothd
	com.apple.fairplayd.H2
	com.apple.nanotimekitcompaniond
	com.apple.fmflocatord
	com.apple.familycircled
	com.apple.carkitd
	com.apple.wcd
	com.apple.UARPUpdaterServiceUSBPD
	com.apple.UARPUpdaterServiceLegacyAudio
	com.apple.UARPUpdaterServiceHID
	com.apple.UARPUpdaterServiceAFU
)

# repair first (the earlier edit left "Volume header needs minor repair")
fsck.hfsplus -f -y "$img" || true

mnt=$(mktemp -d)
cleanup() { mountpoint -q "$mnt" && sudo umount "$mnt"; rmdir "$mnt" 2>/dev/null || true; }
trap cleanup EXIT
sudo mount -t hfsplus -o loop,rw,force "$img" "$mnt"
d="$mnt/private/var/db/com.apple.xpc.launchd"
sudo test -d "$d"

{
	printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>' \
		'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' \
		'<plist version="1.0"><dict>'
	for l in "${labels[@]}"; do
		if sudo test -f "$mnt/System/Library/LaunchDaemons/$l.plist"; then
			printf '<key>%s</key><true/>\n' "$l"
			echo "disable: $l" >&2
		else
			echo "SKIP (no plist in image): $l" >&2
		fi
	done
	printf '%s\n' '</dict></plist>'
} | sudo install -m 0644 -o 0 -g 0 /dev/stdin "$d/disabled.plist"

sudo cat "$d/disabled.plist"
sudo umount "$mnt"
fsck.hfsplus -f -y "$img" || true
fsck.hfsplus -f -y "$img"
echo "done: $img"
