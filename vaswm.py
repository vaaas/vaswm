#/usr/bin/env python3
import sys
import asyncio
import socket
import inspect
import traceback
from collections import deque
from pprint import pprint

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
		self.cols = CONF['cols']

	def __iter__(self):
		return (x for x in self.monitor if x.workspace is self).__iter__()

	def range(self):
		i = list(self).index(self.current_client)
		if i < self.cols:
			return range(0, self.cols)
		else:
			return range(i + 1 - self.cols, i + 1)

class Client:
	def __init__(self, e, workspace):
		self.workspace = workspace
		self.window = e.window
		self.visible = False

def set_border_colour(conn, client, colour):
	conn.core.ChangeWindowAttributes(client.window, xproto.CW.BorderPixel, [colour])

def arrange(conn, mon):
	current_clients = list(mon.current_workspace)
	if len(current_clients) == 0: return
	cols = min(mon.current_workspace.cols, len(current_clients))
	cw = mon.w // cols
	if len(current_clients) <= cols:
		for (i, c) in enumerate(current_clients):
			map_window(conn, c)
			resize(conn, c, i*(cw-bp*2) + bp*2*i, 0, cw-bp*2, mon.h - bp*2)
	else:
		rng = mon.current_workspace.range()
		for (i, c) in enumerate(current_clients):
			if i in rng:
				map_window(conn, c)
				resize(conn, c, (i-rng.start)*(cw-bp*2) + bp*2*(i-rng.start), 0, cw-bp*2, mon.h - bp*2)
			else:
				unmap_window(conn, c)

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
			elif isinstance(e, xproto.ConfigureRequestEvent):
				configure_request(conn, mon, e)
				conn.flush()
			elif isinstance(e, xproto.MapRequestEvent):
				map_request(conn, mon, e)
				conn.flush()
			elif isinstance(e, xproto.DestroyNotifyEvent):
				destroy_notify(conn, mon, e)
				conn.flush()
	except:
		traceback.print_exc()
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
	if len(cs) < 1: return
	if reverse: cs.reverse()
	if len(cs) == 1:
		i = 0
	elif mon.current_workspace.current_client == None:
		i = 0
	else:
		i = cs.index(mon.current_workspace.current_client)
		i = i + 1 if i + 1 < len(cs) else 0
	focus(conn, mon, cs[i])

def next_workspace(conn, mon, reverse=False):
	i = mon.workspaces.index(mon.current_workspace)
	if reverse:
		i = i-1 if i>0 else len(mon.workspaces)-1
	else:
		i = i+1 if (i+1)<len(mon.workspaces) else 0
	for c in mon.current_workspace: unmap_window(conn, c)
	mon.current_workspace = mon.workspaces[i]
	arrange(conn, mon)

def focus(conn, mon, client):
	if not client: return
	elif client.workspace.current_client is client: return
	elif not client.workspace is mon.current_workspace: return
	elif client.workspace.current_client == None:
		set_border_colour(conn, client, colour=CONF['colours']['accent'])
		client.workspace.current_client = client
		return
	else:
		cs = list(client.workspace)
		me = cs.index(client)
		rng = client.workspace.range()
		unfocus(conn, mon, client.workspace.current_client)
		set_border_colour(conn, client, colour=CONF['colours']['accent'])
		client.workspace.current_client = client
		conn.core.SetInputFocus(xproto.InputFocus.PointerRoot, client.window, xproto.Time.CurrentTime)
		if not me in rng:
			arrange(conn, mon)

def unfocus(conn, mon, client):
	if not client: return
	set_border_colour(conn, client, colour=CONF['colours']['default'])
	if client.workspace.current_client is client: client.workspace.current_client = None

def configure_request(conn, mon, e):
	conn.core.ConfigureWindow(e.window, xproto.ConfigWindow.X | xproto.ConfigWindow.Y | xproto.ConfigWindow.Width | xproto.ConfigWindow.Height | xproto.ConfigWindow.BorderWidth, [e.x, e.y, e.width, e.height, bp])
	conn.core.ChangeWindowAttributes(e.window, xproto.CW.EventMask, [xproto.EventMask.EnterWindow | xproto.EventMask.LeaveWindow])

def map_request(conn, mon, e):
	client = find(window_is(e.window), mon.clients)
	if client == None:
		client = Client(e, mon.current_workspace)
		if mon.current_workspace.current_client == None:
			mon.clients.append(client)
		else:
			mon.clients.insert(
				1 + mon.clients.index(mon.current_workspace.current_client),
				client)
	map_window(conn, client)
	set_border_colour(conn, client, colour=CONF['colours']['default'])
	arrange(conn, mon)

def map_window(conn, client):
	if client.visible: return
	conn.core.MapWindow(client.window)
	client.visible = True

def unmap_window(conn, client):
	if not client.visible: return
	conn.core.UnmapWindowUnchecked(client.window)
	client.visible = False

def destroy_notify(conn, mon, e):
	i = find_index(window_is(e.window), mon.clients)
	if i == None: return
	c = mon.clients[i]
	del mon.clients[i]
	if c.workspace.current_client is c:
		c.workspace.current_client = None
		try: focus(conn, mon, c.workspace.__iter__().__next__())
		except StopIteration: return
	if c.workspace is mon.current_workspace:
		arrange(conn, mon)

def destroy_current_window(conn, mon):
	if not mon.current_workspace.current_client: return
	else: conn.core.DestroyWindow(mon.current_workspace.current_client.window)

async def server(conn, mon):
	fd = conn.get_file_descriptor()
	asyncio.get_running_loop().add_reader(fd, apply(poll, conn, mon))
	server = await asyncio.start_unix_server(request_handler(conn, mon), path='/tmp/vaswm.socket')
	await server.serve_forever()

def request_handler(conn, mon):
	async def inner(reader, writer):
		data = (await reader.read(2)).decode()
		if data == 'n':
			focus_next(conn, mon)
			conn.flush()
		elif data == 'p':
			focus_next(conn, mon, True)
			conn.flush()
		elif data == 'N':
			next_workspace(conn, mon)
			conn.flush()
		elif data == 'P':
			next_workspace(conn, mon, True)
			conn.flush()
		elif data == 'q':
			destroy_current_window(conn, mon)
			conn.flush()
		writer.close()
	return inner

def main():
	conn = xcb.connect()
	root = setup(conn)
	mon = Monitor(root)
	asyncio.run(server(conn, mon))

main()
