#/usr/bin/env python3
import xcffib as xcb
import xcffib.xproto as xproto
import inspect

CONF = {
	'cols': 3,
	'tags': ['wrk', 'www', 'cmd', 'fun', 'etc'],
}

class Monitor:
	def __init__(self, root):
		self.w = root.width_in_pixels
		self.h = root.height_in_pixels
		self.workspaces = [ Workspace(x) for x in CONF['tags']]
		self.current_workspace = self.workspaces[0]

class Workspace:
	def __init__(self, tag):
		self.tag = tag
		self.clients = []
		self.skip = 0
		self.cols = CONF['cols']

class Client:
	def __init__(self, e):
		self.window = e.window
		self.x = e.x
		self.y = e.y
		self.w = e.width
		self.h = e.height

def members(x):
	for x in inspect.getmembers(x): print(x[0])

def arrange(conn, mon):
	i = 0
	for c in mon.current_workspace.clients:
		resize(conn, c.window, i*100, 0, 100, 200)
		i+=1

def resize(conn, window, x, y, w, h):
	mask = xproto.ConfigWindow.X | xproto.ConfigWindow.Y | xproto.ConfigWindow.Width | xproto.ConfigWindow.Height | xproto.ConfigWindow.BorderWidth
	x = conn.core.ConfigureWindow(window, mask, [x,y,w,h,4])
	print('>>>>>>>>>>', x)

def setup(conn):
	mask = xproto.EventMask.SubstructureNotify
	setup = conn.get_setup()
	root = setup.roots[0]
	x = conn.core.ChangeWindowAttributesChecked(root.root, xproto.CW.EventMask, [mask])
	print('>>>>>>>>>>>>', x)
	conn.flush()
	return root

def loop(conn, mon):
	while True:
		e = conn.wait_for_event()
		print(e)
		if isinstance(e, xproto.ConfigureNotifyEvent):
			configure_request(conn, mon, e)
		elif isinstance(e, xproto.MapNotifyEvent):
			arrange(conn, mon)
		elif isinstance(e, xproto.UnmapNotifyEvent):
			unmap_request(conn, mon, e)

def configure_request(conn, mon, e):
	client = Client(e)
	mon.current_workspace.clients.append(client)
	arrange(conn, mon)

def unmap_request(conn, mon, e):
	search = None
	for w in mon.workspaces:
		for (i, c) in enumerate(w.clients):
			if c.window == e.window:
				w.clients.pop(i)
				arrange(conn, mon)

def main():
	conn = xcb.connect()
	root = setup(conn)
	mon = Monitor(root)
	loop(conn, mon)

main()
