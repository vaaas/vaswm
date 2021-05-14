#/usr/bin/env python3
import sys
import xcffib as xcb
import xcffib.xproto as xproto
from collections import deque

workspace_is = lambda w: lambda c: c.workspace is w
different = lambda a: lambda b: a != b

MAP = {
	xproto.MapNotifyEvent: 0,
	xproto.UnmapNotifyEvent: 1
}

class Thing: pass

conf = Thing()
conf.border_width = 4
conf.accent_color = '#FF8888'
conf.plain_color = '#888888'

class Monitor:
	def __init__(self, root):
		self.clients = deque()
		self.workspaces = [ Workspace() ]
		self.workspace = self.workspaces[0]

class Client:
	def __init__(self, window, workspace):
		self.workspace = workspace
		self.window = window
		self.x = None
		self.y = None
		self.w = None
		self.h = None
	
	def resize(self, x, y, w, h):
		pass
	
	def accent(self):
		pass
	
	def plain(self):
		pass
	
	def border_colour(self):
		pass
	
	def focus(self):
		pass
	
	def kill(self):
		pass
	
	def next(self):
		pass
	
	def prev(self):
		pass
			
class Workspace:
	def __init__(self, monitor):
		self.monitor = monitor
		self.client = None

	def next(self):
		pass
	
	def prev(self):
		pass
	
	def layout(self):
		pass

conn = xcb.connect()
monitor = Monitor(conn.get_setup().roots[0])
conn.core.ChangeWindowAttributesChecked(root.root, xproto.CW.EventMask, [xproto.EventMask.SubstructureNotify])
conn.flush()

try:
	while True:	
		e = conn.wait_for_event()
		t = type(e)
		if t in MAP:
			print(MAP[t], e.window)
except xcb.ConnectionException:
	print('connection to X server was lost', file=sys.stderr)
	sys.exit(1)
