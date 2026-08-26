# WAVEGO

ESP32와 Raspberry Pi로 동작하는 오픈소스 생체모방 로봇. Raspberry Pi 쪽은 Flask로 조작 화면·영상을 제공하고, WebSocket으로 제어 명령을 받아 UART로 ESP32에 전달합니다.

이 저장소의 Raspberry Pi 코드는 **Raspberry Pi 5 + Raspberry Pi OS Bookworm (64-bit)** 기준으로 맞춰 두었습니다.

## Raspberry Pi 5에서 달라진 점

| 기존 (Pi 4 / Bullseye 이전) | Pi 5 / Bookworm |
|---|---|
| `sudo pip3 install ...` | PEP 668 때문에 시스템 pip 설치 불가. 프로젝트 venv 사용 |
| `opencv-contrib-python==3.4.11.45`, `numpy==1.21` | Python 3.11과 호환되지 않음. apt의 OpenCV/NumPy 사용 |
| `/boot/config.txt`, `/boot/cmdline.txt` | `/boot/firmware/config.txt`, `/boot/firmware/cmdline.txt` |
| `start_x=1` + `camera_auto_detect` 끄기 | libcamera. `camera_auto_detect=1` 유지 |
| `/dev/ttyS0` | GPIO 14/15 UART는 `/dev/serial0` 또는 `/dev/ttyAMA0` |
| `create_ap` + `rc.local` | NetworkManager 핫스팟 + systemd (`wavego.service`) |

## 준비물

- Raspberry Pi 5, Raspberry Pi OS Bookworm 64-bit
- WAVEGO ESP32 보드와 Pi를 UART로 연결 (GPIO 14/15, 115200 baud)
- CSI 카메라 또는 USB 웹캠 (선택)

ESP32에는 `Arduino/WAVEGO` 스케치를 먼저 올려 두세요.

## 설치

Pi에서 저장소를 받은 뒤:

```bash
cd WAVEGO/RPi
sudo python3 setup.py
sudo reboot
```

`setup.py`가 하는 일:

1. apt 패키지 설치 (`python3-opencv`, `python3-picamera2` 등)
2. `RPi/.venv` 가상환경 생성 (`--system-site-packages`)
3. `requirements.txt`를 venv 안에 설치 (시스템 Python은 건드리지 않음)
4. UART 활성화 (`enable_uart=1`, `dtparam=uart0=on`), 시리얼 콘솔 제거
5. 사용자를 `dialout`, `video` 그룹 등에 추가
6. `wavego.service` 등록 (부팅 시 자동 시작)

설치가 끝나면 **반드시 재부팅**하세요. UART와 그룹 변경은 재부팅 후에 적용됩니다.

## 실행

재부팅 후 서비스가 자동으로 올라갑니다. 수동으로 다룰 때는:

```bash
sudo systemctl start wavego
sudo systemctl status wavego
sudo systemctl stop wavego
journalctl -u wavego -f
```

서비스 없이 직접 실행:

```bash
cd WAVEGO/RPi
source .venv/bin/activate
python3 webServer.py
```

같은 네트워크의 브라우저에서:

- 주소: `http://<라즈베리파이IP>:5000`
- 로그인: `admin` / `123456`
- 조작 WebSocket 포트: `8888`

Pi IP 확인:

```bash
hostname -I
```

Wi-Fi가 없으면 SSID `WAVE_BOT` / 비밀번호 `12345678` 핫스팟이 뜹니다. 그때는 `http://192.168.4.1:5000` 으로 접속합니다.

## 가상환경만 따로 만들 때

`setup.py` 없이 패키지만 설치하려면:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip python3-dev python3-opencv \
  python3-numpy python3-picamera2 python3-smbus i2c-tools libcamera-apps

cd WAVEGO/RPi
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

`--system-site-packages`가 필요합니다. 빼면 apt로 깐 OpenCV·Picamera2가 venv에서 보이지 않습니다.

시스템 Python에 `pip install` 하지 마세요. `--break-system-packages`도 쓰지 않는 것이 좋습니다.

## 카메라 / UART 확인

```bash
# CSI 카메라
rpicam-hello -t 2000

# UART 장치 (Pi 5는 ttyAMA0 인 경우가 많음)
ls -l /dev/serial0 /dev/ttyAMA0 /dev/ttyS0
```

시리얼 포트를 강제하려면:

```bash
export WAVEGO_SERIAL=/dev/ttyAMA0
python3 webServer.py
```

## 구조

```
브라우저
  ├─ HTTP :5000   Flask — UI, MJPEG 영상 (/video_feed)
  └─ WS   :8888   제어 명령
        ↓
  camera_opencv.commandAct()
        ↓
  robot.py  →  /dev/serial0  →  ESP32
```

## 문제 해결

**`error: externally-managed-environment`**  
시스템 `pip3`를 쓰고 있습니다. `RPi/.venv`를 활성화한 뒤 그 안의 `pip`를 쓰거나, `sudo python3 setup.py`로 다시 설치하세요.

**카메라가 안 열림**  
`camera_auto_detect=1` 인지 `/boot/firmware/config.txt`를 확인하세요. 구버전 `setup.py`가 `start_x=1`로 바꿨다면 그 줄을 지우고 재부팅하세요. CSI가 없으면 USB 웹캠으로 OpenCV `VideoCapture` 폴백이 됩니다.

**시리얼이 안 열림**  
`dtparam=uart0=on` 이 `/boot/firmware/config.txt`에 있는지, `cmdline.txt`에 `console=serial0,115200` 이 없는지 확인한 뒤 재부팅하세요. 사용자는 `dialout` 그룹이어야 합니다.

**웹 화면은 뜨는데 조작이 안 됨**  
브라우저가 `8888` 포트에 연결할 수 있어야 합니다. 방화벽과 ESP32 펌웨어, UART 배선을 확인하세요.

**예전에 구버전 `setup.py`를 돌린 경우**  
`/etc/rc.local`에 `webServer.py` 실행 줄이 남아 있으면 지우세요. 지금은 systemd `wavego.service`가 대신합니다. `/boot/firmware/config.txt`의 `start_x=1` 과 `#camera_auto_detect=1` 도 원래대로 되돌리세요.
