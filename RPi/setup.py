#!/usr/bin/python3
# File name   : setup.py for WAVEGO (Raspberry Pi 5 / Bookworm)
# Date        : 2022/1/5
# Updated     : 2026/8/27

"""Install WAVEGO on Raspberry Pi OS Bookworm without using system pip.

Raspberry Pi OS Bookworm marks the system Python as an externally-managed
environment (PEP 668). Packages are installed into a project venv instead.
"""

import getpass
import grp
import os
import pwd
import re
import shlex
import sys

curpath = os.path.realpath(__file__)
thisPath = os.path.dirname(curpath)
venvPath = os.path.join(thisPath, ".venv")
reqPath = os.path.join(thisPath, "requirements.txt")
serviceName = "wavego.service"
servicePath = os.path.join("/etc/systemd/system", serviceName)


def log(msg):
    print("[WAVEGO] " + msg, flush=True)


def run(cmd, tries=3):
    for attempt in range(1, tries + 1):
        log("run: " + cmd)
        if os.system(cmd) == 0:
            return True
        log("failed (%d/%d): %s" % (attempt, tries, cmd))
    return False


def real_user():
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user and sudo_user != "root":
        return sudo_user
    user = os.environ.get("USER") or getpass.getuser()
    if user and user != "root":
        return user
    return "pi"


def run_as_user(user, cmd, tries=3):
    if os.geteuid() == 0 and user and user != "root":
        wrapped = "sudo -u %s -H bash -lc %s" % (user, shlex.quote(cmd))
        return run(wrapped, tries=tries)
    return run(cmd, tries=tries)


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


def configure_boot():
    config = boot_config_path()
    cmdline = boot_cmdline_path()
    log("boot config: " + config)
    log("boot cmdline: " + cmdline)

    # Pi 5 UART on GPIO 14/15. Keep libcamera auto-detect enabled.
    ensure_config_setting(config, "enable_uart=1", replace_prefix="enable_uart=")
    ensure_config_setting(config, "dtparam=uart0=on")
    ensure_config_setting(
        config, "camera_auto_detect=1", replace_prefix="camera_auto_detect="
    )
    disable_serial_console(cmdline)

    run("raspi-config nonint do_serial_hw 0", tries=1)
    run("raspi-config nonint do_serial_cons 1", tries=1)
    run("raspi-config nonint do_i2c 0", tries=1)


def install_apt_packages():
    # Keep this list to packages that exist on Bookworm and Trixie.
    # libatlas-base-dev was dropped; OpenBLAS replaced it.
    required = [
        "python3-venv",
        "python3-pip",
        "python3-dev",
        "python3-opencv",
        "python3-numpy",
        "i2c-tools",
        "libfreetype6-dev",
        "libjpeg-dev",
        "build-essential",
        "network-manager",
        "util-linux",
        "procps",
        "iproute2",
        "iw",
    ]
    optional = [
        "libopenblas-dev",
        "libhdf5-dev",
        "python3-smbus",
        "python3-smbus2",
        "python3-libcamera",
        "python3-picamera2",
        "libcamera-apps",
        "rpicam-apps",
    ]
    run("apt update")
    if not run("apt-get install -y " + " ".join(required)):
        raise SystemExit("Failed to install required apt packages")
    for pkg in optional:
        run("apt-get install -y " + pkg, tries=1)


def venv_imports_ok(user, python_bin):
    check = (
        "%s -c \"import flask, flask_cors, serial, websockets, imutils, psutil; "
        "print('venv imports ok')\""
        % shlex.quote(python_bin)
    )
    return run_as_user(user, check, tries=1)


def create_venv(user):
    python_bin = os.path.join(venvPath, "bin", "python3")
    pip_bin = os.path.join(venvPath, "bin", "pip")
    if not os.path.exists(python_bin):
        if not run_as_user(
            user,
            "python3 -m venv --system-site-packages %s" % shlex.quote(venvPath),
        ):
            raise SystemExit("Failed to create virtualenv at %s" % venvPath)
    run_as_user(user, "%s -m pip install -U pip" % shlex.quote(python_bin))
    # Ignore leftover system type-stubs (e.g. types-flask-migrate) that are
    # unrelated to WAVEGO but make pip print a dependency conflict ERROR.
    run_as_user(
        user,
        "%s uninstall -y types-flask-migrate" % shlex.quote(pip_bin),
        tries=1,
    )
    pip_ok = run_as_user(
        user,
        "%s install -r %s" % (shlex.quote(pip_bin), shlex.quote(reqPath)),
    )
    if not venv_imports_ok(user, python_bin):
        raise SystemExit("Failed to install Python packages into the venv")
    if not pip_ok:
        log("pip reported a dependency warning; required WAVEGO packages imported OK")


def add_user_groups(user):
    for group in ("dialout", "video", "gpio", "i2c", "render", "input"):
        run("usermod -aG %s %s" % (group, user), tries=1)


def install_systemd_service(user):
    python_bin = os.path.join(venvPath, "bin", "python3")
    try:
        group_name = grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name
    except KeyError:
        group_name = user

    unit = """[Unit]
Description=WAVEGO web and control server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
Group={group}
SupplementaryGroups=dialout video gpio i2c render
WorkingDirectory={workdir}
ExecStart={python} {script}
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
""".format(
        user=user,
        group=group_name,
        workdir=thisPath,
        python=python_bin,
        script=os.path.join(thisPath, "webServer.py"),
    )
    with open(servicePath, "w") as handle:
        handle.write(unit)
    run("systemctl daemon-reload", tries=1)
    run("systemctl enable %s" % serviceName, tries=1)

    sudoers = "/etc/sudoers.d/wavego"
    with open(sudoers, "w") as handle:
        handle.write("%s ALL=(ALL) NOPASSWD: /usr/bin/nmcli\n" % user)
    os.chmod(sudoers, 0o440)


def main():
    if os.geteuid() != 0:
        print("Run this script with sudo:")
        print("  sudo python3 setup.py")
        sys.exit(1)

    user = real_user()
    log("installing for user: " + user)
    log("project path: " + thisPath)

    install_apt_packages()
    create_venv(user)
    configure_boot()
    add_user_groups(user)
    install_systemd_service(user)

    python_bin = os.path.join(venvPath, "bin", "python3")
    print("")
    print("Completed.")
    print("Reboot is required so UART and group membership take effect:")
    print("  sudo reboot")
    print("")
    print("After reboot, start the server:")
    print("  sudo systemctl start wavego")
    print("or:")
    print("  sudo -u %s %s %s" % (user, python_bin, os.path.join(thisPath, "webServer.py")))
    print("")
    print("Web UI:  http://<pi-ip>:5000")
    print("Login:   admin / 123456")


if __name__ == "__main__":
    main()
