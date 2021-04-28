#/usr/bin/env python3
import sys
import asyncio
import socket
import inspect
from collections import deque

import xcffib as xcb
import xcffib.xproto as xproto

CONF = {
	'cols': 3,
	'tags': ['wrk', 'www', 'cmd', 'fun', 'etc'],
	'borderpx': 4,
	'colours': {
		'accent': 0xFF0000,
		'default': 0x888888,
	},
}

bp = CONF['borderpx']

window_is = lambda x: lambda c: c.window == x
workspace_is = lambda x: lambda c: c.workspace == x
apply = lambda f, *args: lambda: f(*args)

def find(f, xs):
	for x in xs:
		if f(x):
			return x
	return None

def find_index(f, xs):
	for (i,x) in enumerate(xs):
		if f(x):
			return i
	return None

class Monitor:
	def __init__(self, root):
		self.w = root.width_in_pixels
		self.h = root.height_in_pixels
		self.workspaces = [ Workspace(x) for x in CONF['tags']]
		self.current_workspace = self.workspaces[0]
		self.clients = deque()
		self.current_client = None

class Workspace:
	def __init__(self, tag):
		self.tag = tag
		self.skip = 0
		self.cols = CONF['cols']

class Client:
	def __init__(self, e, workspace):
		self.workspace = workspace
		self.window = e.window
		self.x = e.x
		self.y = e.y
		self.w = e.width
		self.h = e.height

def members(x):
	for x in inspect.getmembers(x): print(x[0])

def set_border_colour(conn, window, colour):
	conn.core.ChangeWindowAttributes(window, xproto.CW.BorderPixel, [colour])

def arrange(conn, mon):
	current_clients = [ x for x in mon.clients if x.workspace is mon.current_workspace ]
	if len(current_clients) == 0: return
	cols = min(CONF['cols'], len(current_clients))
	cw = mon.w // cols
	i = 0
	while i < cols:
		resize(conn, current_clients[i].window,
			i*(cw-bp*2) + bp*2*i, 0, cw-bp*2, mon.h - bp*2)
		i+=1

def resize(conn, window, x, y, w, h):
	print(x,y,w,h)
	mask = xproto.ConfigWindow.X | xproto.ConfigWindow.Y | xproto.ConfigWindow.Width | xproto.ConfigWindow.Height
	conn.core.ConfigureWindow(window, mask, [x,y,w,h])

def setup(conn):
	mask = xproto.EventMask.SubstructureRedirect|xproto.EventMask.SubstructureNotify
	setup = conn.get_setup()
	root = setup.roots[0]
	conn.core.ChangeWindowAttributesChecked(root.root, xproto.CW.EventMask, [mask])
	conn.flush()
	return root

def poll(conn, mon):
	while True:
		e = conn.poll_for_event()
		if e == None: break
		if isinstance(e, xproto.EnterNotifyEvent):
			focus(conn, mon, find(window_is(e.event), mon.clients))
			conn.flush()
		elif isinstance(e, xproto.LeaveNotifyEvent):
			unfocus(conn, mon, find(window_is(e.event), mon.clients))
			conn.flush()
		elif isinstance(e, xproto.ConfigureRequestEvent):
			configure_request(conn, mon, e)
			conn.flush()
		elif isinstance(e, xproto.MapRequestEvent):
			conn.core.MapWindow(e.window)
			arrange(conn, mon)
			conn.flush()
		elif isinstance(e, xproto.UnmapNotifyEvent):
			i = find_index(window_is(e.window), mon.clients)
			if i == None: continue
			if mon.current_client is mon.clients[i]:
				focus(conn, mon, nearest_client(mon.clients, mon.clients[i]))
			del mon.clients[i]
			arrange(conn, mon)
			conn.flush()

def nearest_client(clients, C):
	p = None
	for c in clients:
		if not c.workspace is C.workspace: continue
		if c is C:
			if p: break
			else: continue
		else: p = c
	return p

def focus_next(conn, mon):
	i = 0
	while i < len(mon.clients) and not mon.clients[i] is mon.current_client: i += 1
	i += 1
	while i < len(mon.clients) and not mon.clients[i].workspace is mon.current_client.workspace: i += 1
	if i < len(mon.clients): focus(conn, mon, mon.clients[i])
	else:
		i = 0
		while i < len(mon.clients) and not mon.clients[i].workspace is mon.current_client.workspace: i += 1
		if i < len(mon.clients): focus(conn, mon, mon.clients[i])

def focus_prev(conn, mon):
	i = len(mon.clients) - 1
	while i >= 0 and not mon.clients[i] is mon.current_client: i -= 1
	i -= 1
	while i >= 0 and not mon.clients[i].workspace is mon.current_client.workspace: i -= 1
	if i >= 0: focus(conn, mon, mon.clients[i])
	else:
		i = len(mon.clients) - 1
		while i >= 0 and not mon.clients[i].workspace is mon.current_client.workspace: i -= 1
		if i >= 0: focus(conn, mon, mon.clients[i])

def focus(conn, mon, client):
	if not client: return
	if mon.current_client: unfocus(conn, mon, mon.current_client)
	set_border_colour(conn, client.window, colour=CONF['colours']['accent'])
	mon.current_client = client

def unfocus(conn, mon, client):
	if not client: return
	set_border_colour(conn, client.window, colour=CONF['colours']['default'])
	if mon.current_client is client: mon.current_client = None

def configure_request(conn, mon, e):
	client = find(window_is(e.window), mon.clients)
	if client == None:
		client = Client(e, mon.current_workspace)
		mon.clients.append(client)
	conn.core.ConfigureWindow(e.window, xproto.ConfigWindow.X | xproto.ConfigWindow.Y | xproto.ConfigWindow.Width | xproto.ConfigWindow.Height | xproto.ConfigWindow.BorderWidth, [e.x, e.y, e.width, e.height, bp])
	conn.core.ChangeWindowAttributes(e.window, xproto.CW.EventMask, [xproto.EventMask.EnterWindow | xproto.EventMask.LeaveWindow])
	set_border_colour(conn, e.window, colour=CONF['colours']['default'])

async def server(conn, mon):
	fd = conn.get_file_descriptor()
	asyncio.get_running_loop().add_reader(fd, apply(poll, conn, mon))
	server = await asyncio.start_unix_server(request_handler(conn, mon), path='/tmp/vaswm.socket')
	await server.serve_forever()

def request_handler(conn, mon):
	async def inner(reader, writer):
		data = (await reader.read(128)).decode()
		print('received', list(data))
		if data == 'n':
			print('hiiiiiiiii')
			focus_next(conn, mon)
			conn.flush()
		if data == 'p':
			focus_prev(conn, mon)
			conn.flush()
		writer.close()
	return inner

def main():
	conn = xcb.connect()
	root = setup(conn)
	mon = Monitor(root)
	asyncio.run(server(conn, mon))

main()
