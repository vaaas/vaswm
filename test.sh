Xephyr -ac -screen 640x480 -br -reset -terminate 2> /dev/null :1 &
sleep 0.5s
DISPLAY=:1 python3 vaswm.py &
sleep 0.5s
DISPLAY=:1 xterm -e htop &
sleep 0.1s
DISPLAY=:1 xterm -e pulsemixer &
sleep 0.1s
DISPLAY=:1 xterm -e nmtui &
