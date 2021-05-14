#/usr/bin/env python3
import sys
import asyncio
import traceback
from collections import deque
import xcffib as xcb
import xcffib.xproto as xproto

CONF = {
	'tags': ['wrk', 'www', 'cmd', 'fun', 'etc'],
	'borderpx': 4,
	'colours': {
		'accent': 0xFF0055,
		'default': 0xFFEEDD,
	},
}

bp = CONF['borderpx']

class Monitor:
	w = None
	h = None
	clients = []
	workspaces = []
	current_workspace = None
	def __init__(self):
		self.conn = xcb.connect()
		mask = xproto.EventMask.SubstructureRedirect|xproto.EventMask.SubstructureNotify
		root = self.conn.get_setup().roots[0]
		self.conn.core.ChangeWindowAttributesChecked(root.root, xproto.CW.EventMask, [mask])
		self.conn.flush()

		self.atoms = {}
		for x in ['WM_DELETE_WINDOW', 'WM_PROTOCOLS']:
			self.atoms[x] = self.conn.core.InternAtom(False, len(x), x).reply().atom
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
		c.workspace.layout.update_range()
		if c.workspace.current_client == None: c.focus()

	def delete_client(self, c):
		i = c.workspace.clients.index(c)
		del self.clients[self.clients.index(c)]
		if c.workspace.current_client is c:
			c.workspace.current_client = None
		c.workspace.update_clients()
		c.workspace.layout.update_range()
		if len(c.workspace.clients) == 0:
			return
		elif i == 0:
			c.workspace.clients[0].focus()
		else:
			c.workspace.clients[-1].focus()

	def next_workspace(self, reverse=False):
		i = self.workspaces.index(self.current_workspace)
		if reverse:
			i = i-1 if i>0 else len(self.workspaces)-1
		else:
			i = i+1 if (i+1)<len(self.workspaces) else 0
		self.set_workspace(self.workspaces[i])

	def set_workspace(self, w):
		if w is self.current_workspace: return
		for c in self.current_workspace.clients:
			c.hide()
		self.current_workspace = w
		w.layout.arrange()
		if w.current_client:
			w.current_client.set_input_focus()

class Layout:
	workspace = None
	range = None
	def __init__(self, workspace):
		self.workspace = workspace
		self.range = range(0,0)
	def update_range(self): pass
	def arrange(self): pass

class ColumnarLayout(Layout):
	max = 1
	def __init__(self, workspace, max=1):
		super().__init__(workspace)
		self.max = max

	def update_range(self):
		if len(self.workspace.clients) == 0 or self.workspace.current_client == None:
			self.range = range(0,0)
		else:
			i = self.workspace.clients.index(self.workspace.current_client)
			if i < self.max:
				self.range = range(0, self.max)
			else:
				self.range = range(i + 1 - self.max, i + 1)
		self.arrange()
	
	def arrange(self):
		if not self.workspace.monitor.current_workspace is self.workspace: return
		elif len(self.workspace.clients) == 0: return
		elif len(self.workspace.clients) == 1:
			self.workspace.clients[0].resize(-bp, -bp, self.workspace.monitor.w, self.workspace.monitor.h)
		elif len(self.workspace.clients) <= self.max:
			cw = self.workspace.monitor.w // len(self.workspace.clients)
			for (i, c) in enumerate(self.workspace.clients):
				c.resize(i*(cw-bp*2) + bp*2*i, 0, cw-bp*2, self.workspace.monitor.h - bp*2)
		else:
			cw = self.workspace.monitor.w // self.max
			for (i, c) in enumerate(self.workspace.clients):
				if i in self.range:
					c.resize((i-self.range.start)*(cw-bp*2) + bp*2*(i-self.range.start), 0, cw-bp*2, self.workspace.monitor.h - bp*2)
				else:
					c.hide()

class OneColumn(ColumnarLayout):
	def __init__(self, workspace):
		super().__init__(workspace, 1)
	
	def arrange(self):
		if not self.workspace.monitor.current_workspace is self.workspace: return
		elif len(self.workspace.clients) == 0: return
		else:
			for c in self.workspace.clients:
				if c is self.workspace.current_client:
					c.resize(-bp, -bp, self.workspace.monitor.w, self.workspace.monitor.h)
				else:
					c.hide()

class TwoColumns(ColumnarLayout):
	def __init__(self, workspace):
		super().__init__(workspace, 2)

class ThreeColumns(ColumnarLayout):
	def __init__(self, workspace):
		super().__init__(workspace, 3)

class FourColumns(ColumnarLayout):
	def __init__(self, workspace):
		super().__init__(workspace, 4)

"""
class Fullscreen(Layout):
	def __init__(self, workspace):
		super().__init__(workspace)
		
	def arrange(self):
		if not self.workspace.monitor.current_workspace is self.workspace: return
		elif len(self.workspace.clients) == 0: return
		else:
			for c in self.workspace.clients:
				if c is self.workspace.current_client:
					c.resize(-bp, -bp, self.workspace.monitor.w, self.workspace.monitor.h)
				else:
					c.hide()
"""

layouts = [OneColumn, TwoColumns, ThreeColumns, FourColumns]

class Workspace:
	current_client = None
	monitor = None
	tag = None
	clients = []
	layout = None
	def __init__(self, mon, tag):
		self.monitor = mon
		self.tag = tag
		self.layout = ThreeColumns(self)
		self.update_clients()
		self.layout.update_range()
		
	def next_layout(self, reverse=False):
		i = layouts.index(type(self.layout))
		if reverse:
			i = i - 1
		else:
			i = i + 1 if i + 1 < len(layouts) else 0
		self.layout = layouts[i](self)
		self.layout.update_range()

	def update_clients(self):
		self.clients = [x for x in self.monitor.clients if x.workspace is self]

	def destroy_current_window(self):
		if not self.current_client: return
		else:
			self.current_client.destroy()

	def focus_next(self, reverse=False):
		if len(self.clients) < 2: return
		if reverse:
			i = self.clients.index(self.current_client) - 1
		else:
			i = self.clients.index(self.current_client) + 1
			if i >= len(self.clients): i = 0
		self.clients[i].focus()
		self.clients[i].set_input_focus()

class Client:
	conn = None
	monitor = None
	window = None
	workspace = None
	x = None
	y = None
	w = None
	h = None
	def __init__(self, mon, e):
		self.conn = mon.conn
		self.monitor = mon
		self.window = e.window
		self.workspace = mon.current_workspace

		geom = self.conn.core.GetGeometry(self.window).reply()
		self.x = geom.x
		self.y = geom.y
		self.w = geom.width
		self.h = geom.height

		self.map()
		self.default_border()

	def send_event(self, data, mask=xproto.EventMask.NoEvent, format=32, type='WM_PROTOCOLS'):
		event = xproto.ClientMessageEvent.synthetic(
			format=32,
			window=self.window,
			type=self.monitor.atoms[type],
			data=data,
		).pack()
		self.conn.core.SendEvent(False, self.window, xproto.EventMask.NoEvent, event)

	def destroy(self):
		self.send_event(xproto.ClientMessageData.synthetic([
			self.monitor.atoms['WM_DELETE_WINDOW'],
			xproto.Time.CurrentTime,
			0, 0, 0
		], 'I'*5))

	def map(self):
		self.conn.core.MapWindow(self.window)

	def hide(self):
		mask = xproto.ConfigWindow.X
		self.conn.core.ConfigureWindow(self.window, mask, [-2*self.w])

	def resize(self, x, y, w, h):
		self.x = x
		self.y = y
		self.w = w
		self.h = h
		mask = xproto.ConfigWindow.X | xproto.ConfigWindow.Y | xproto.ConfigWindow.Width | xproto.ConfigWindow.Height
		self.conn.core.ConfigureWindow(self.window, mask, [x,y,w,h])

	def set_border_colour(self, colour):
		self.conn.core.ChangeWindowAttributes(self.window, xproto.CW.BorderPixel, [colour])

	def accent_border(self):
		self.set_border_colour(CONF['colours']['accent'])

	def default_border(self):
		self.set_border_colour(CONF['colours']['default'])

	def focus(self):
		if self.workspace.current_client is self:
			return
		elif self.workspace.current_client != None:
			self.workspace.current_client.unfocus()
		self.workspace.current_client = self
		self.set_input_focus()
		self.accent_border()
		if not self.workspace.clients.index(self) in self.workspace.layout.range:
			self.workspace.layout.update_range()

	def unfocus(self):
		self.default_border()
		if self.workspace.current_client is self:
			self.workspace.current_client = None

	def set_input_focus(self):
		self.conn.core.SetInputFocus(xproto.InputFocus.PointerRoot, self.window, xproto.Time.CurrentTime)

def poll(mon):
	try:
		while True:
			e = mon.conn.poll_for_event()
			if e == None: break
			if isinstance(e, xproto.EnterNotifyEvent):
				# there's some sort of bug with focus. fix later. ask in a mailing list
				# for c in mon.clients:
				# 	if c.window == c.window:
				# 		return c.focus()
				c = mon.current_workspace.current_client
				if e.event != c.window:
					c.set_input_focus()
					c.accent_border()
			if isinstance(e, xproto.ConfigureRequestEvent):
				configure_request(mon, e)
			elif isinstance(e, xproto.MapRequestEvent):
				map_request(mon, e)
			elif isinstance(e, xproto.UnmapNotifyEvent):
				unmap_notify(mon, e)
			mon.conn.flush()
	except:
		# there HAS to be a cleaner way.
		traceback.print_exc()
		sys.exit(1)

def configure_request(mon, e):
	c = None
	for x in mon.clients:
		if e.window == x.window:
			c = x
			break
	if c == None:
		mon.conn.core.ConfigureWindow(e.window, xproto.ConfigWindow.X | xproto.ConfigWindow.Y | xproto.ConfigWindow.Width | xproto.ConfigWindow.Height | xproto.ConfigWindow.BorderWidth, [e.x, e.y, e.width, e.height, bp])
		mon.conn.core.ChangeWindowAttributes(e.window, xproto.CW.EventMask, [xproto.EventMask.EnterWindow])
	else:
		c.resize(c.x, c.y, c.w, c.h)

def map_request(mon, e):
	c = None
	for x in mon.clients:
		if x.window == e.window:
			c = x
			break
	if c == None:
		c = Client(mon, e)
		mon.add_client(c)
	else:
		c.map()

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
		elif data == 'l':
			mon.current_workspace.next_layout()
		elif data == 'L':
			mon.current_workspace.next_layout(True)
		elif data in ['1', '2', '3', '4', '5']:
			mon.set_workspace(mon.workspaces[int(data)-1])
		mon.conn.flush()
		writer.close()
	return inner

async def main():
	mon = Monitor()
	fd = mon.conn.get_file_descriptor()
	asyncio.get_running_loop().add_reader(fd, lambda: poll(mon))
	server = await asyncio.start_unix_server(request_handler(mon), path='/tmp/vaswm.socket')
	await server.serve_forever()

asyncio.run(main())
