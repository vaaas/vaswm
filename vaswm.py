#/usr/bin/env python3
import xcffib as xcb
import xcffib.xproto as xproto
import inspect
from collections import deque

# TODO: focus https://www.x.org/releases/current/doc/man/man3/xcb_set_input_focus.3.xhtml

CONF = {
	'cols': 3,
	'tags': ['wrk', 'www', 'cmd', 'fun', 'etc'],
	'borderpx': 4,
	'colours': {
		'accent': 0xFF0000,
		'default': 0x888888,
	},
}

window_is = lambda x: lambda c: c.window == x
workspace_is = lambda x: lambda c: c.workspace == x

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

def set_border(conn, window, size=None, colour=None):
	if (size): conn.core.ConfigureWindow(window, xproto.ConfigWindow.BorderWidth, [size])
	if (colour): conn.core.ChangeWindowAttributes(window, xproto.CW.BorderPixel, [colour])

def arrange(conn, mon):
	current_clients = [ x for x in mon.clients if x.workspace is mon.current_workspace ]
	cols = min(CONF['cols'], len(current_clients))
	if cols == 0: return
	bw = 2*CONF['borderpx']
	cw = (mon.w - bw) // cols
	i = 0
	while i < cols:
		resize(conn, current_clients[i].window, i*cw, 0, cw, mon.h - bw)
		i+=1
	conn.flush()

def resize(conn, window, x, y, w, h):
	mask = xproto.ConfigWindow.X | xproto.ConfigWindow.Y | xproto.ConfigWindow.Width | xproto.ConfigWindow.Height
	conn.core.ConfigureWindow(window, mask, [x,y,w,h])

def setup(conn):
	mask = xproto.EventMask.SubstructureNotify | xproto.EventMask.SubstructureRedirect
	setup = conn.get_setup()
	root = setup.roots[0]
	conn.core.ChangeWindowAttributesChecked(root.root, xproto.CW.EventMask, [mask])
	conn.flush()
	return root

def loop(conn, mon):
	while True:
		e = conn.wait_for_event()
		print(e)
		if isinstance(e, xproto.EnterNotifyEvent):
			pass
			#set_border(conn, e.root, colour=CONF['colours']['accent'])
			#conn.flush()
		elif isinstance(e, xproto.LeaveNotifyEvent) and hasattr(e, 'window'):
			pass
			#set_border(conn, e.window, colour=CONF['colours']['default'])
			#conn.flush()
		elif isinstance(e, xproto.ConfigureNotifyEvent):
			configure_request(conn, mon, e)
		elif isinstance(e, xproto.MapNotifyEvent):
			conn.core.
			arrange(conn, mon)
		elif isinstance(e, xproto.UnmapNotifyEvent):
			unmap_request(conn, mon, e)

def configure_request(conn, mon, e):
	client = find(window_is(e.window), mon.clients)
	if client: return client
	client = Client(e, mon.current_workspace)
	mon.clients.append(client)
	conn.core.ChangeWindowAttributes(e.window, xproto.CW.EventMask, [xproto.EventMask.EnterWindow | xproto.EventMask.LeaveWindow])
	set_border(conn, e.window, size=CONF['borderpx'], colour=CONF['colours']['default'])
	conn.flush()

def unmap_request(conn, mon, e):
	i = find_index(window_is(e.window), mon.clients)
	if i != None:
		mon.clients.pop(i)
		arrange(conn, mon)

def main():
	conn = xcb.connect()
	root = setup(conn)
	mon = Monitor(root)
	loop(conn, mon)

main()
