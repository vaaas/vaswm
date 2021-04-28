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
		self.workspaces = [Workspace(x, self) for x in CONF['tags']]
		self.current_workspace = self.workspaces[0]
		self.clients = deque()

	def __iter__(self): return self.clients.__iter__()

class Workspace:
	def __init__(self, tag, monitor):
		self.current_client = None
		self.monitor = monitor
		self.tag = tag
		self.skip = 0
		self.cols = CONF['cols']

	def __iter__(self):
		return (x for x in self.monitor if x.workspace is self).__iter__()

class Client:
	def __init__(self, e, workspace):
		self.workspace = workspace
		self.window = e.window
		self.x = e.x
		self.y = e.y
		self.w = e.width
		self.h = e.height

def set_border_colour(conn, client, colour):
	conn.core.ChangeWindowAttributes(client.window, xproto.CW.BorderPixel, [colour])

def arrange(conn, mon):
	current_clients = list(mon.current_workspace)
	if len(current_clients) == 0: return
	cols = min(CONF['cols'], len(current_clients))
	cw = mon.w // cols
	for (i, c) in enumerate(current_clients):
		resize(conn, c, i*(cw-bp*2) + bp*2*i, 0, cw-bp*2, mon.h - bp*2)

def resize(conn, client, x, y, w, h):
	mask = xproto.ConfigWindow.X | xproto.ConfigWindow.Y | xproto.ConfigWindow.Width | xproto.ConfigWindow.Height
	conn.core.ConfigureWindow(client.window, mask, [x,y,w,h])

def setup(conn):
	mask = xproto.EventMask.SubstructureRedirect|xproto.EventMask.SubstructureNotify
	setup = conn.get_setup()
	root = setup.roots[0]
	conn.core.ChangeWindowAttributesChecked(root.root, xproto.CW.EventMask, [mask])
	conn.flush()
	return root

def poll(conn, mon):
	try:
		while True:
			e = conn.poll_for_event()
			if e == None: break
			if isinstance(e, xproto.EnterNotifyEvent):
				focus(conn, mon, find(window_is(e.event), mon))
				conn.flush()
			elif isinstance(e, xproto.LeaveNotifyEvent):
				unfocus(conn, mon, find(window_is(e.event), mon))
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
				c = mon.clients[i]
				del mon.clients[i]
				if c.workspace.current_client is c:
					c.workspace.current_client = None
					focus(conn, mon, c.workspace.__iter__().__next__())
				if c.workspace is mon.current_workspace:
					arrange(conn, mon)
				conn.flush()
	except xproto.WindowError as e:
		print('BAD')
	except:
		sys.exit(1)

def nearest_client(c):
	p = None
	for x in c.workspace:
		if x is c:
			if p: return p
			else: continue
		else: p = x
	return p

def focus_next(conn, mon, reverse=False):
	cs = list(mon.current_workspace)
	if reverse: cs.reverse()
	if len(cs) < 1: return
	i = 0
	while i < len(cs) and not cs[i].workspace.current_client is cs[i]: i += 1
	i += 1
	if i < len(cs): focus(conn, mon, cs[i])
	else: focus(conn, mon, cs[0])

def focus(conn, mon, client):
	if not client: return
	if not client.workspace.current_client is client and not client.workspace.current_client is None:
		unfocus(conn, mon, client.workspace.current_client)
	set_border_colour(conn, client, colour=CONF['colours']['accent'])
	client.workspace.current_client = client

def unfocus(conn, mon, client):
	if not client: return
	set_border_colour(conn, client, colour=CONF['colours']['default'])
	if client.workspace.current_client is client: client.workspace.current_client = None

def configure_request(conn, mon, e):
	client = find(window_is(e.window), mon.clients)
	if client == None:
		client = Client(e, mon.current_workspace)
		mon.clients.append(client)
	conn.core.ConfigureWindow(e.window, xproto.ConfigWindow.X | xproto.ConfigWindow.Y | xproto.ConfigWindow.Width | xproto.ConfigWindow.Height | xproto.ConfigWindow.BorderWidth, [e.x, e.y, e.width, e.height, bp])
	conn.core.ChangeWindowAttributes(e.window, xproto.CW.EventMask, [xproto.EventMask.EnterWindow | xproto.EventMask.LeaveWindow])
	set_border_colour(conn, client, colour=CONF['colours']['default'])

async def server(conn, mon):
	fd = conn.get_file_descriptor()
	asyncio.get_running_loop().add_reader(fd, apply(poll, conn, mon))
	server = await asyncio.start_unix_server(request_handler(conn, mon), path='/tmp/vaswm.socket')
	await server.serve_forever()

def request_handler(conn, mon):
	async def inner(reader, writer):
		data = (await reader.read(128)).decode()
		if data == 'n':
			focus_next(conn, mon)
			conn.flush()
		if data == 'p':
			focus_next(conn, mon, True)
			conn.flush()
		writer.close()
	return inner

def main():
	conn = xcb.connect()
	root = setup(conn)
	mon = Monitor(root)
	asyncio.run(server(conn, mon))

main()
