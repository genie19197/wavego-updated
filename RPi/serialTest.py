#!/usr/bin/python3
# File name   : serialTest.py
# Date        : 2022/1/5
# Updated     : 2026/8/27 — Raspberry Pi OS Bookworm / Pi 5 paths

import os
import re


def boot_config_path():
    for path in ("/boot/firmware/config.txt", "/boot/config.txt"):
        if os.path.exists(path):
            return path
    return "/boot/firmware/config.txt"


def boot_cmdline_path():
    for path in ("/boot/firmware/cmdline.txt", "/boot/cmdline.txt"):
        if os.path.exists(path):
            return path
    return "/boot/firmware/cmdline.txt"


def ensure_config_setting(path, setting, replace_prefix=None):
    setting = setting.strip()
    with open(path, "r") as handle:
        lines = handle.readlines()
    found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        prefix_hit = False
        if replace_prefix:
            prefix_hit = stripped.startswith(replace_prefix) or stripped.startswith(
                "#" + replace_prefix
            )
        if stripped == setting or stripped == "#" + setting or prefix_hit:
            if not found:
                new_lines.append(setting + "\n")
                found = True
            continue
        new_lines.append(line)
    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(setting + "\n")
    with open(path, "w") as handle:
        handle.writelines(new_lines)


def disable_serial_console(path):
    with open(path, "r") as handle:
        text = handle.read()
    text = re.sub(r"\s*console=serial0,\d+", "", text)
    text = re.sub(r"\s*console=ttyAMA0,\d+", "", text)
    with open(path, "w") as handle:
        handle.write(text)


if __name__ == "__main__":
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo: sudo python3 serialTest.py")

    config = boot_config_path()
    cmdline = boot_cmdline_path()
    print("config:", config)
    print("cmdline:", cmdline)

    ensure_config_setting(config, "enable_uart=1", replace_prefix="enable_uart=")
    ensure_config_setting(config, "dtparam=uart0=on")
    ensure_config_setting(
        config, "camera_auto_detect=1", replace_prefix="camera_auto_detect="
    )
    disable_serial_console(cmdline)
    print("UART enabled. Reboot for the change to take effect.")
