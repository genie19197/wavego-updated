#!/usr/bin/env python3
# File name   : server.py
# Production  : Upper Ctrl for Robots
# Author	  : WaveShare

import time
import threading
import os
import socket
import info

#websocket
import asyncio
import websockets

import json
import app


ipaddr_check = "192.168.4.1"


def ap_thread():
	# Bookworm uses NetworkManager. create_ap is unmaintained on Pi 5.
	os.system("sudo nmcli device wifi hotspot ifname wlan0 ssid WAVE_BOT password 12345678")


def wifi_check():
	global ipaddr_check
	time.sleep(5)
	try:
		s =socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
		s.connect(("1.1.1.1",80))
		ipaddr_check=s.getsockname()[0]
		s.close()
		print(ipaddr_check)
	except:
		ap_threading=threading.Thread(target=ap_thread)   
		ap_threading.daemon = True
		ap_threading.start()


def _recv_text(message):
	if isinstance(message, bytes):
		return message.decode('utf-8')
	return message


async def check_permit(websocket):
	while True:
		recv_str = _recv_text(await websocket.recv())
		print('WS auth message:', repr(recv_str))
		cred_dict = recv_str.split(":")
		if cred_dict[0] == "admin" and cred_dict[1] == "123456":
			response_str = "Connected!"
			await websocket.send(response_str)
			return True
		else:
			response_str = "sorry, the username or password is wrong, please submit again"
			await websocket.send(response_str)


async def recv_msg(websocket):
	while True: 
		response = {
			'status' : 'ok',
			'title' : '',
			'data' : None
		}

		data = ''
		raw = _recv_text(await websocket.recv())
		print('WS recv:', repr(raw))
		data = raw
		try:
			data = json.loads(data)
		except Exception as e:
			print('not A JSON')

		if not data:
			continue

		if isinstance(data,str):
			try:
				flask_app.commandInput(data)
			except Exception as exc:
				print('commandInput error:', repr(data), type(exc).__name__, exc)

			if 'get_info' == data:
				response['title'] = 'get_info'
				response['data'] = [info.get_cpu_tempfunc(), info.get_cpu_use(), info.get_ram_info()]

			if 'findColor' == data:
				flask_app.modeselect('findColor')
				print('set mode as findColor')

			elif 'scan' == data:
				print('scanning')
				# ds = app.camera_opencv.ultra.checkdist()
				# print(ds)
				radar_send = [[3,60],[10,70],[10,80],[10,90],[10,100],[10,110],[3,120]]
				# radar_send = []
				# for i in range(1,150):
				# 	radar_send.append[ds]
				response['title'] = 'scanResult'
				response['data'] = radar_send
				time.sleep(0.3)
				pass

			elif 'motionGet' == data:
				flask_app.modeselect('watchDog')
				print('set mode as watchDog')

			elif 'stopCV' == data:
				flask_app.modeselect('none')

			#CVFL
			elif 'CVFL' == data:
				flask_app.modeselect('findlineCV')
				print('set mode as findlineCV')

			elif 'CVFLColorSet' in data:
				color = int(data.split()[1])
				flask_app.camera.colorSet(color)

			elif 'CVFLL1' in data:
				pos = int(data.split()[1])
				flask_app.camera.linePosSet_1(pos)

			elif 'CVFLL2' in data:
				pos = int(data.split()[1])
				flask_app.camera.linePosSet_2(pos)

			elif 'CVFLSP' in data:
				err = int(data.split()[1])
				flask_app.camera.errorSet(err)

			elif 'defEC' in data:#Z
				fpv.defaultExpCom()


		elif(isinstance(data,dict)):
			if data['title'] == "findColorSet":
				color = data['data']
				flask_app.colorFindSet(color[0],color[1],color[2])

		if data != "get_info":
			print(data)
			
		response = json.dumps(response)
		await websocket.send(response)


async def client_handler(websocket, *args):
	peer = getattr(websocket, 'remote_address', None)
	print('WS client connected:', peer)
	try:
		await check_permit(websocket)
		print('WS auth ok:', peer)
		await recv_msg(websocket)
	except Exception as exc:
		print('WS client error:', peer, type(exc).__name__, exc)
	finally:
		print('WS client disconnected:', peer)


def _ws_serve():
	try:
		from websockets.asyncio.server import serve
		return serve
	except ImportError:
		pass
	try:
		from websockets.server import serve
		return serve
	except ImportError:
		return websockets.serve


async def start_ws_server():
	serve = _ws_serve()
	print('starting WebSocket server 0.0.0.0:8888 using', serve)
	try:
		server = serve(
			client_handler,
			'0.0.0.0',
			8888,
			ping_interval=None,
			ping_timeout=None,
		)
	except TypeError:
		server = serve(client_handler, '0.0.0.0', 8888)

	if hasattr(server, '__aenter__'):
		async with server:
			print('waiting for connection...')
			await asyncio.Future()
	else:
		started = await server
		print('waiting for connection...')
		try:
			await asyncio.Future()
		finally:
			started.close()
			await started.wait_closed()


if __name__ == '__main__':
	global flask_app

	wifi_check()
	flask_app = app.webapp()
	flask_app.startthread()
	flask_app.sendIP(ipaddr_check)

	while True:
		try:
			asyncio.run(start_ws_server())
		except KeyboardInterrupt:
			print('stopped')
			break
		except Exception as e:
			print('WebSocket server error:', type(e).__name__, e)
			time.sleep(1)
