#/usr/bin/env python3
import sys
import asyncio
import traceback
from collections import deque
import xcffib as xcb
import xcffib.xproto as xproto

CONF = {
	'cols': 2,
	'tags': ['wrk', 'www', 'cmd', 'fun', 'etc'],
	'borderpx': 4,
	'colours': {
		'accent': 0xFF0000,
		'default': 0x888888,
	},
}

bp = CONF['borderpx']

apply = lambda f, *args: lambda: f(*args)

class Monitor:
	def __init__(self):
		self.conn = xcb.connect()
		mask = xproto.EventMask.SubstructureRedirect|xproto.EventMask.SubstructureNotify
		root = self.conn.get_setup().roots[0]
		self.conn.core.ChangeWindowAttributesChecked(root.root, xproto.CW.EventMask, [mask])
		self.conn.flush()

		self.w = root.width_in_pixels
		self.h = root.height_in_pixels
		self.clients = deque()
		self.workspaces = [Workspace(self, x) for x in CONF['tags']]
		self.current_workspace = self.workspaces[0]

	def add_client(self, c):
		try:
			self.clients.insert(self.clients.index(c.workspace.current_client) + 1, c)
		except:
			self.clients.append(c)
		c.workspace.update_clients()
		c.workspace.update_range()
		if c.workspace.current_client == None: c.focus()
		c.workspace.arrange()

	def delete_client(self, c):
		i = c.workspace.clients.index(c)
		del self.clients[self.clients.index(c)]
		if c.workspace.current_client is c:
			c.workspace.current_client = None
		c.workspace.update_clients()
		c.workspace.update_range()
		if len(c.workspace.clients) == 0:
			return
		elif i == 0:
			c.workspace.clients[0].focus()
		else:
			c.workspace.clients[-1].focus()
		c.workspace.arrange()

	def next_workspace(self, reverse=False):
		i = self.workspaces.index(self.current_workspace)
		if reverse:
			i = i-1 if i>0 else len(self.workspaces)-1
		else:
			i = i+1 if (i+1)<len(self.workspaces) else 0
		for c in self.current_workspace.clients:
			c.hide()
		self.current_workspace = self.workspaces[i]
		self.current_workspace.arrange()

class Workspace:
	def __init__(self, mon, tag):
		self.current_client = None
		self.monitor = mon
		self.tag = tag
		self.cols = CONF['cols']
		self.clients = []
		self.range = range(0, 0)
		self.update_clients()
		self.update_range()

	def update_clients(self):
		self.clients = [x for x in self.monitor.clients if x.workspace is self]

	def update_range(self):
		if len(self.clients) == 0 or self.current_client == None:
			self.range = range(0,0)
		else:
			i = self.clients.index(self.current_client)
			if i < self.cols:
				self.range = range(0, self.cols)
			else:
				self.range = range(i + 1 - self.cols, i + 1)

	def arrange(self):
		if not self.monitor.current_workspace is self: return
		if len(self.clients) == 0: return
		cols = min(self.cols, len(self.clients))
		cw = self.monitor.w // cols
		if len(self.clients) <= cols:
			for (i, c) in enumerate(self.clients):
				c.resize(i*(cw-bp*2) + bp*2*i, 0, cw-bp*2, self.monitor.h - bp*2)
		else:
			for (i, c) in enumerate(self.clients):
				if i in self.range:
					c.resize((i-self.range.start)*(cw-bp*2) + bp*2*(i-self.range.start), 0, cw-bp*2, self.monitor.h - bp*2)
				else:
					c.hide()

	def destroy_current_window(self):
		if not self.current_client: return
		else: self.current_client.destroy()

	def focus_next(self, reverse=False):
		if len(self.clients) < 2: return
		i = self.clients.index(self.current_client) + 1
		if i >= len(self.clients): i = 0
		self.current_client.unfocus()
		self.current_client = self.clients[i]
		self.current_client.accent_border()

class Client:
	def __init__(self, mon, e):
		self.conn = mon.conn
		self.mon = mon
		self.window = e.window
		self.workspace = mon.current_workspace

	def destroy(self):
		self.conn.core.DestroyWindow(self.window)

	def map(self):
		self.conn.core.MapWindow(self.window)

	def hide(self):
		mask = xproto.ConfigWindow.X
		self.conn.core.ConfigureWindow(self.window, mask, [-self.mon.w])

	def resize(self, x, y, w, h):
		mask = xproto.ConfigWindow.X | xproto.ConfigWindow.Y | xproto.ConfigWindow.Width | xproto.ConfigWindow.Height
		self.conn.core.ConfigureWindow(self.window, mask, [x,y,w,h])

	def set_border_colour(self, colour):
		self.conn.core.ChangeWindowAttributes(self.window, xproto.CW.BorderPixel, [colour])

	def accent_border(self):
		self.set_border_colour(CONF['colours']['accent'])

	def default_border(self):
		self.set_border_colour(CONF['colours']['default'])

	def focus(self):
		if self.workspace.current_client is self: return
		elif self.workspace.current_client != None:
			self.workspace.current_client.unfocus()
		self.workspace.current_client = self
		self.accent_border()
		if not self.workspace.clients.index(self) in self.workspace.range:
			self.workspace.update_range()
			self.workspace.arrange()

	def unfocus(self):
		self.default_border()
		if self.workspace.current_client is self:
			self.workspace.current_client = None

def poll(mon):
	try:
		while True:
			e = mon.conn.poll_for_event()
			if e == None: break
			if isinstance(e, xproto.EnterNotifyEvent):
				for c in mon.clients:
					if c.window == e.event:
						c.focus()
						break
			if isinstance(e, xproto.ConfigureRequestEvent):
				configure_request(mon, e)
			elif isinstance(e, xproto.MapRequestEvent):
				map_request(mon, e)
			elif isinstance(e, xproto.UnmapNotifyEvent):
				unmap_notify(mon, e)
			mon.conn.flush()
	except:
		traceback.print_exc()
		sys.exit(1)

def configure_request(mon, e):
	mon.conn.core.ConfigureWindow(e.window, xproto.ConfigWindow.X | xproto.ConfigWindow.Y | xproto.ConfigWindow.Width | xproto.ConfigWindow.Height | xproto.ConfigWindow.BorderWidth, [e.x, e.y, e.width, e.height, bp])
	mon.conn.core.ChangeWindowAttributes(e.window, xproto.CW.EventMask, [xproto.EventMask.EnterWindow | xproto.EventMask.LeaveWindow])

def map_request(mon, e):
	c = None
	for x in mon.clients:
		if x.window == e.window:
			c = x
			break
	if c == None:
		c = Client(mon, e)
		mon.add_client(c)
	c.map()
	c.default_border()

def unmap_notify(mon, e):
	for x in mon.clients:
		if x.window == e.window:
			return mon.delete_client(x)

def request_handler(mon):
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
		mon.conn.flush()
		writer.close()
	return inner

async def main():
	mon = Monitor()
	fd = mon.conn.get_file_descriptor()
	asyncio.get_running_loop().add_reader(fd, apply(poll, mon))
	server = await asyncio.start_unix_server(request_handler(mon), path='/tmp/vaswm.socket')
	await server.serve_forever()

asyncio.run(main())
