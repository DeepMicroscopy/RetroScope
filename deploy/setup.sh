#!/usr/bin/env bash
# deploy/setup.sh: Run once on the Raspberry Pi to configure the system.
# Must be run as root: sudo bash deploy/setup.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER="${SUDO_USER:-pi}"
APP_DIR="/home/${APP_USER}/retroscope"
USER_ID="$(id -u "$APP_USER")"

echo "==> Repo:     $REPO_DIR"
echo "==> App user: $APP_USER (uid=$USER_ID)"
echo "==> App dir:  $APP_DIR"
echo ""

# 1. Symlink the repo into the expected location (skip if already there)
if [ ! -e "$APP_DIR" ]; then
    ln -s "$REPO_DIR" "$APP_DIR"
    echo "[ok] Symlinked $REPO_DIR -> $APP_DIR"
else
    echo "[ok] $APP_DIR already exists"
fi

# 2. Autostart: labwc autostart script (Wayland)
LABWC_DIR="/home/${APP_USER}/.config/labwc"
mkdir -p "$LABWC_DIR"
LABWC_AUTOSTART="$LABWC_DIR/autostart"

# Append only if not already present
START_SCRIPT="$APP_DIR/deploy/start.sh"
OLD_START_ENTRY="$APP_DIR/start.sh --scale 1.5 &"
if [ -f "$LABWC_AUTOSTART" ] && grep -qF "$OLD_START_ENTRY" "$LABWC_AUTOSTART"; then
    TMP_AUTOSTART="${LABWC_AUTOSTART}.tmp"
    grep -vF "$OLD_START_ENTRY" "$LABWC_AUTOSTART" > "$TMP_AUTOSTART"
    mv "$TMP_AUTOSTART" "$LABWC_AUTOSTART"
fi
if ! grep -qF "$START_SCRIPT" "$LABWC_AUTOSTART" 2>/dev/null; then
    echo "$START_SCRIPT --scale 1.5 &" >> "$LABWC_AUTOSTART"
fi
chown -R "$APP_USER:$APP_USER" "$LABWC_DIR"
echo "[ok] Autostart entry added ($LABWC_AUTOSTART)"

# Also install the XDG .desktop fallback
AUTOSTART_DIR="/home/${APP_USER}/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
sed "s|/home/pi/retroscope|$APP_DIR|g" \
    "$REPO_DIR/deploy/retroscope.desktop" > "$AUTOSTART_DIR/retroscope.desktop"
chown -R "$APP_USER:$APP_USER" "$AUTOSTART_DIR"
echo "[ok] XDG .desktop autostart entry installed"

# 3. Autostart: systemd system service
SERVICE_SRC="$REPO_DIR/deploy/retroscope.service"
SERVICE_DST="/etc/systemd/system/retroscope.service"

sed "s|/home/pi/retroscope|$APP_DIR|g; s|User=pi|User=$APP_USER|g; s|Group=pi|Group=$APP_USER|g; s|XDG_RUNTIME_DIR=/run/user/1000|XDG_RUNTIME_DIR=/run/user/${USER_ID}|g" \
    "$SERVICE_SRC" > "$SERVICE_DST"

systemctl daemon-reload
systemctl enable retroscope.service
echo "[ok] systemd service installed and enabled (WantedBy=graphical.target)"

# 4. sudoers: passwordless shutdown for app user
SUDOERS_FILE="/etc/sudoers.d/retroscope"
echo "${APP_USER} ALL=(ALL) NOPASSWD: /sbin/shutdown" > "$SUDOERS_FILE"
chmod 440 "$SUDOERS_FILE"
echo "[ok] sudoers rule written to $SUDOERS_FILE"

# 5. Plymouth splash theme (Custom boot splahs)
PIX_DIR="/usr/share/plymouth/themes/pix"
PIX_SPLASH="$PIX_DIR/splash.png"
PIX_SRC="$REPO_DIR/deploy/background.png"

if [ ! -d "$PIX_DIR" ]; then
    echo "[..] pix theme not found. Installing plymouth-themes..."
    apt-get install -y --no-install-recommends plymouth-themes
fi

if [ ! -d "$PIX_DIR" ]; then
    echo "[error] pix theme is still unavailable after installing plymouth-themes"
    exit 1
fi

if [ ! -f "$PIX_SRC" ]; then
    echo "[error] Missing splash image: $PIX_SRC"
    exit 1
fi

[ -f "$PIX_SPLASH.orig" ] || cp "$PIX_SPLASH" "$PIX_SPLASH.orig" 2>/dev/null || true
cp "$PIX_SRC" "$PIX_SPLASH"
echo "[ok] pix splash image replaced with $PIX_SRC"

# Disable Pi firmware "rainbow" splash (noramlly shows before Plymouth)
CONFIG="/boot/firmware/config.txt"
[ -f "$CONFIG" ] || CONFIG="/boot/config.txt"
if [ -f "$CONFIG" ]; then
    if ! grep -q "disable_splash" "$CONFIG"; then
        echo "disable_splash=1" >> "$CONFIG"
        echo "[ok] Pi firmware splash disabled (disable_splash=1)"
    else
        echo "[ok] disable_splash already set in $CONFIG"
    fi
fi

# Pi OS Trixie can fallback to the a grey ellipsis screen at boot when the
# initramfs is built with MODULES=dep. Using MODULES=most keeps the DRM stack
# available early enough for Plymouth image themes such as pix.
# https://forums.raspberrypi.com/viewtopic.php?t=393289#p2366223
INITRAMFS_CONF="/etc/initramfs-tools/initramfs.conf"
if [ -f "$INITRAMFS_CONF" ]; then
    if grep -q '^MODULES=' "$INITRAMFS_CONF"; then
        sed -i 's/^MODULES=.*/MODULES=most/' "$INITRAMFS_CONF"
    else
        echo "MODULES=most" >> "$INITRAMFS_CONF"
    fi
    echo "[ok] initramfs configured with MODULES=most"
fi

# Activate the stock pix theme for boot and shutdown.
if command -v plymouth-set-default-theme &>/dev/null; then
    plymouth-set-default-theme -R pix
    echo "[ok] Plymouth default set to pix and initramfs rebuilt"
else
    echo "[warn] plymouth-set-default-theme not found, rebuilding initramfs manually"
    update-initramfs -u
fi

# Ensure 'quiet splash' is in cmdline.txt
CMDLINE="/boot/firmware/cmdline.txt"
[ -f "$CMDLINE" ] || CMDLINE="/boot/cmdline.txt"
if [ -f "$CMDLINE" ]; then
    if ! grep -q "splash" "$CMDLINE"; then
        sed -i 's/$/ quiet splash plymouth.ignore-serial-consoles/' "$CMDLINE"
        echo "[ok] Added 'quiet splash' to $CMDLINE"
    else
        echo "[ok] cmdline.txt already has splash"
    fi
fi

echo ""
echo "Setup complete. Reboot to apply all changes: sudo reboot"
