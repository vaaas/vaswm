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
	def __init__(self, conn, root):
		self.w = root.width_in_pixels
		self.h = root.height_in_pixels
		self.workspaces = [Workspace(conn, self, x) for x in CONF['tags']]
		self.current_workspace = self.workspaces[0]
		self.clients = deque()

	def add_client(self, c, i=-1):
		if c.workspace.current_client == None:
			self.clients.append(c)
		else:
			self.clients.insert(c.workspace.index(c) + 1, c)
		c.workspace.update_clients()
		if self.current_workspace is c.workspace:
			self.current_workspace.arrange()

	def next_workspace(self, reverse=False):
		i = self.workspaces.index(self.current_workspace)
		if reverse:
			i = i-1 if i>0 else len(self.workspaces)-1
		else:
			i = i+1 if (i+1)<len(self.workspaces) else 0
		for c in self.current_workspace.clients:
			c.unmap()
		self.current_workspace = self.workspaces[i]
		self.current_workspace.arrange()

class Workspace:
	def __init__(self, conn, mon, tag):
		self.current_client = None
		self.monitor = monitor
		self.tag = tag
		self.cols = CONF['cols']
		self.clients = []
		self.range = range(0, 0)
		self.update_clients()
		self.update_range()

	def update_clients(self):
		self.clients = [x for x in self.monitor if x.workspace is self]

	def update_range(self):
		i = self.clients.index(self.current_client)
		if i < self.cols:
			self.range = range(0, self.cols)
		else:
			self.range = range(i + 1 - self.cols, i + 1)

	def arrange():
		if len(self.clients) == 0: return
		cols = min(self.cols, len(self.clients))
		cw = mon.w // cols
		if len(self.clients) <= cols:
			for (i, c) in enumerate(self.clients):
				c.map()
				c.resize(i*(cw-bp*2) + bp*2*i, 0, cw-bp*2, mon.h - bp*2)
		else:
			for (i, c) in enumerate(self.clients):
				if i in self.range:
					c.map()
					c.resize(i-rng.start)*(cw-bp*2) + bp*2*(i-rng.start), 0, cw-bp*2, mon.h - bp*2)
				else:
					c.unmap()
		self.conn.flush()

	def destroy_current_window(self):
		if not self.current_client: return
		else: self.current_client.destroy()

	def focus_next(self, reverse=False):
		cs = list(self.clients)
		if len(cs) < 1: return
		if reverse: cs.reverse()
		if len(cs) == 1:
			i = 0
		elif self.current_client == None:
			i = 0
		else:
			i = cs.index(self.current_client)
			i = i + 1 if i + 1 < len(cs) else 0
		cs[i].focus()

class Client:
	def __init__(self, conn, mon, e):
		self.conn = conn
		self.mon = mon
		self.window = e.window
		self.workspace = mon.current_workspace
		self.visible = False

	def destroy(self):
		self.conn.core.DestroyWindow(self.window)
		self.conn.flush()

	def map(self):
		if self.visible: return
		self.conn.core.MapWindow(self.window)
		self.visible = True
		self.conn.flush()

	def unmap(self):
		if not self.visible: return
		self.conn.core.UnmapWindowUnchecked(self.window)
		self.client.visible = False
		self.conn.flush()

	def resize(self, x, y, w, h):
		mask = xproto.ConfigWindow.X | xproto.ConfigWindow.Y | xproto.ConfigWindow.Width | xproto.ConfigWindow.Height
		self.conn.core.ConfigureWindow(self.window, mask, [x,y,w,h])
		self.conn.flush()

	def set_border_colour(self, colour)
		self.conn.core.ChangeWindowAttributes(self.window, xproto.CW.BorderPixel, [colour])
		self.conn.flush()

	def set_input_focus(self):
		self.conn.core.SetInputFocus(xproto.InputFocus.PointerRoot, self.window, xproto.Time.CurrentTime)
		self.conn.flush()

	def focus(self):
		if self.workspace.current_client is self: return
		elif not self.workspace is self.mon.current_workspace: return
		elif self.workspace.current_client == None:
			self.set_border_colour(CONF['colours']['accent'])
			self.workspace.current_client = self
			self.set_input_focus()
		else:
			i = self.workspace.clients.index(self)
			rng = self.workspace.range
			self.workspace.current_client.unfocus()
			self.set_border_colour(CONF['colours']['accent'])
			self.workspace.current_client = client
			self.set_input_focus()
			if not i in rng:
				self.workspace.arrange()

	def unfocus():
		self.set_border_colour(CONF['colours']['default'])
		if self.workspace.current_client is self:
			self.workspace.current_client = None
		self.conn.flush()

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
				for c in mon.clients:
					if c.window is e.event:
						c.focus()
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

def configure_request(conn, mon, e):
	conn.core.ConfigureWindow(e.window, xproto.ConfigWindow.X | xproto.ConfigWindow.Y | xproto.ConfigWindow.Width | xproto.ConfigWindow.Height | xproto.ConfigWindow.BorderWidth, [e.x, e.y, e.width, e.height, bp])
	conn.core.ChangeWindowAttributes(e.window, xproto.CW.EventMask, [xproto.EventMask.EnterWindow | xproto.EventMask.LeaveWindow])

def map_request(conn, mon, e):
	client = find(window_is(e.window), mon.clients)
	if client == None:
		mon.add_client(Client(conn, mon, e))
	map_window(conn, client)
	set_border_colour(conn, client, colour=CONF['colours']['default'])

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

async def server(conn, mon):
	fd = conn.get_file_descriptor()
	asyncio.get_running_loop().add_reader(fd, apply(poll, conn, mon))
	server = await asyncio.start_unix_server(request_handler(conn, mon), path='/tmp/vaswm.socket')
	await server.serve_forever()

def request_handler(conn, mon):
	async def inner(reader, writer):
		data = (await reader.read(2)).decode()
		if data == 'n':
			mon.current_workspace.focus_next()
		elif data == 'p':
			mon.current_workspace.focus_next(True)
		elif data == 'N':
			mon.next_workspace()
		elif data == 'P':
			mon.next_workspace(True)
		elif data == 'q':
			mon.current_workspace.destroy_current_window()
		writer.close()
	return inner

def main():
	conn = xcb.connect()
	root = setup(conn)
	mon = Monitor(conn, root)
	asyncio.run(server(conn, mon))

main()
