Xephyr -ac -screen 640x480 -br -reset -terminate 2> /dev/null :1 &
sleep 0.5s
DISPLAY=:1 python3 vaserwm.py &
sleep 0.1s
DISPLAY=:1 xterm &
sleep 0.1s
DISPLAY=:1 epiphany &
