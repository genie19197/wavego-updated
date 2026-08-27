#!/usr/bin/env python3
# File name   : robot.py
# Description : Robot interfaces.
import os
import time
import json
import threading
import serial

_serial_lock = threading.Lock()
_last_buzzer = None


def _is_pi5():
	try:
		with open('/proc/device-tree/model', 'rb') as handle:
			return b'Raspberry Pi 5' in handle.read()
	except Exception:
		return False


def open_serial():
	candidates = []
	env_port = os.environ.get('WAVEGO_SERIAL')
	if env_port:
		candidates.append(env_port)
	# Pi 5: GPIO 14/15 is /dev/ttyAMA0. /dev/serial0 is the 3-pin debug UART
	# (/dev/ttyAMA10), which is NOT wired to the WAVEGO ESP32.
	if _is_pi5():
		candidates.extend(['/dev/ttyAMA0', '/dev/serial0', '/dev/ttyS0'])
	else:
		candidates.extend(['/dev/serial0', '/dev/ttyAMA0', '/dev/ttyS0'])
	last_error = None
	seen = set()
	for port in candidates:
		if not port or port in seen:
			continue
		seen.add(port)
		if not os.path.exists(port):
			print('UART skip (missing):', port)
			continue
		real = os.path.realpath(port)
		if os.path.basename(real) == 'ttyAMA10':
			print('UART skip (Pi 5 debug header):', port, '->', real)
			continue
		try:
			conn = serial.Serial(
				port=port,
				baudrate=115200,
				timeout=0.2,
				write_timeout=1,
				exclusive=True,
				dsrdtr=False,
				rtscts=False,
				xonxoff=False,
			)
			conn.dtr = False
			conn.rts = False
			print('UART opened:', port, '->', real)
			return conn
		except Exception as exc:
			last_error = exc
			print('UART open failed:', port, exc)
	raise RuntimeError(
		'Could not open UART (%s). Enable GPIO UART with dtparam=uart0=on and reboot.'
		% last_error
	)

ser = open_serial()
dataCMD = json.dumps({'var':"", 'val':0, 'ip':""})
upperGlobalIP = 'UPPER IP'


pitch, roll = 0, 0

# WAVEGO Pro: {"T":111,"FB":-1..1,"LR":-1..1}. Classic {"var":"move"} is ignored.
# Pro also heartbeats — it stops unless T:111 keeps arriving.
_move_lock = threading.Lock()
_fb = 0.0
_lr = 0.0
_speed = 100
_last_fb_set = 0.0
_last_lr_set = 0.0
_last_telemetry_log = 0.0
_STOP_BOUNCE_S = 0.45


def _drain_uart(force_log=False):
	global _last_telemetry_log
	if not ser.in_waiting:
		return
	leftover = ser.read(ser.in_waiting)
	if not leftover or not leftover.strip():
		return
	now = time.time()
	is_telem = b'"T":1001' in leftover or leftover.strip().startswith(b'0,"v"')
	if force_log or not is_telem or (now - _last_telemetry_log) > 3.0:
		print('UART from ESP32:', leftover)
		_last_telemetry_log = now


def _write_json(payload):
	line = json.dumps(payload, separators=(',', ':')) + '\n'
	try:
		with _serial_lock:
			_drain_uart()
			ser.write(line.encode())
			ser.flush()
	except Exception as exc:
		print('UART write failed:', payload, exc)


def _speed_scale():
	# Slider 1-100 → 0.4-1.0. Speed 38 used to become 0.38, too slow to see.
	return 0.4 + 0.6 * max(0.0, min(1.0, float(_speed) / 100.0))


def _send_vector(reason='hold'):
	with _move_lock:
		fb = round(_fb * _speed_scale(), 3)
		lr = round(_lr * _speed_scale(), 3)
	payload = {'T': 111, 'FB': fb, 'LR': lr}
	if reason != 'hold':
		print('UART send Pro move:', payload, reason)
	_write_json(payload)


def _repeater():
	while True:
		time.sleep(0.2)
		with _move_lock:
			moving = _fb != 0.0 or _lr != 0.0
		if moving:
			_send_vector('hold')


_repeat_thread = threading.Thread(target=_repeater, daemon=True)
_repeat_thread.start()


def send_cmd(var, val):
	# Lights/buzzer/legacy. WAVEGO Pro ignores these.
	_write_json({'var': var, 'val': val})


def setUpperIP(ipInput):
	global upperGlobalIP
	upperGlobalIP = ipInput

def forward(speed=100):
	global _fb, _last_fb_set
	print('robot-forward')
	with _move_lock:
		_fb = 1.0
		_last_fb_set = time.time()
	_send_vector('forward')

def backward(speed=100):
	global _fb, _last_fb_set
	print('robot-backward')
	with _move_lock:
		_fb = -1.0
		_last_fb_set = time.time()
	_send_vector('backward')

def left(speed=100):
	global _lr, _last_lr_set
	print('robot-left')
	with _move_lock:
		_lr = -1.0
		_last_lr_set = time.time()
	_send_vector('left')

def right(speed=100):
	global _lr, _last_lr_set
	print('robot-right')
	with _move_lock:
		_lr = 1.0
		_last_lr_set = time.time()
	_send_vector('right')

def stopLR():
	global _lr
	with _move_lock:
		age = time.time() - _last_lr_set
		if age < _STOP_BOUNCE_S:
			print('ignore bounce TS (%.3fs)' % age)
			return
		_lr = 0.0
	print('robot-stop TS')
	_send_vector('TS')

def stopFB():
	global _fb
	with _move_lock:
		age = time.time() - _last_fb_set
		if age < _STOP_BOUNCE_S:
			print('ignore bounce DS (%.3fs)' % age)
			return
		_fb = 0.0
	print('robot-stop DS')
	_send_vector('DS')


def speedSet(speed=100):
	global _speed
	with _move_lock:
		_speed = int(speed)
		moving = _fb != 0.0 or _lr != 0.0
	print('robot-speed', _speed)
	if moving:
		_send_vector('speed')


def lookUp():
	send_cmd('ges', 1)
	print('robot-lookUp')

def lookDown():
	send_cmd('ges', 2)
	print('robot-lookDown')

def lookStopUD():
	send_cmd('ges', 3)
	print('robot-lookStopUD')

def lookLeft():
	send_cmd('ges', 4)
	print('robot-lookLeft')

def lookRight():
	send_cmd('ges', 5)
	print('robot-lookRight')

def lookStopLR():
	send_cmd('ges', 6)
	print('robot-lookStopLR')



def steadyMode():
	send_cmd('funcMode', 1)
	print('robot-steady')

def jump():
	send_cmd('funcMode', 4)
	print('robot-jump')

def handShake():
	send_cmd('funcMode', 3)
	print('robot-handshake')



def lightCtrl(colorName, cmdInput):
	colorNum = 0
	if colorName == 'off':
		colorNum = 0
	elif colorName == 'blue':
		colorNum = 1
	elif colorName == 'red':
		colorNum = 2
	elif colorName == 'green':
		colorNum = 3
	elif colorName == 'yellow':
		colorNum = 4
	elif colorName == 'cyan':
		colorNum = 5
	elif colorName == 'magenta':
		colorNum = 6
	elif colorName == 'cyber':
		colorNum = 7
	send_cmd('light', colorNum)


def buzzerCtrl(buzzerCtrl, cmdInput):
	global _last_buzzer
	if buzzerCtrl == _last_buzzer:
		return
	_last_buzzer = buzzerCtrl
	send_cmd('buzzer', buzzerCtrl)



if __name__ == '__main__':
	print('sending left for 3 seconds')
	left()
	time.sleep(3)
	stopLR()
	print('done')
