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


def send_cmd(var, val):
	payload = json.dumps({'var': var, 'val': val}, separators=(',', ':')) + '\n'
	try:
		with _serial_lock:
			if ser.in_waiting:
				leftover = ser.read(ser.in_waiting)
				if leftover and leftover.strip():
					print('UART leftover from ESP32:', leftover)
			ser.write(payload.encode())
			ser.flush()
			time.sleep(0.05)
			if ser.in_waiting:
				reply = ser.read(ser.in_waiting)
				print('UART from ESP32:', reply)
	except Exception as exc:
		print('UART write failed:', var, val, exc)


def setUpperIP(ipInput):
	global upperGlobalIP
	upperGlobalIP = ipInput

def forward(speed=100):
	print('robot-forward')
	send_cmd('move', 1)

def backward(speed=100):
	send_cmd('move', 5)
	print('robot-backward')

def left(speed=100):
	send_cmd('move', 2)
	print('robot-left')

def right(speed=100):
	send_cmd('move', 4)
	print('robot-right')

def stopLR():
	send_cmd('move', 6)
	print('robot-stop')

def stopFB():
	send_cmd('move', 3)
	print('robot-stop')



def speedSet(speed=100):
	print('robot-speed', speed)


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
