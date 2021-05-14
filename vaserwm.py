#/usr/bin/env python3
import sys
import xcffib as xcb
import xcffib.xproto as xproto

MAP = {
	xproto.MapNotifyEvent: 0,
	xproto.UnmapNotifyEvent: 1
}

conn = xcb.connect()
root = conn.get_setup().roots[0]
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
