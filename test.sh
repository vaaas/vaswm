Xephyr -ac -screen 640x480 -br -reset -terminate 2> /dev/null :1 &
sleep 1s
DISPLAY=:1 python3 vaswm.py &
sleep 1s
DISPLAY=:1 xterm -e htop &
DISPLAY=:1 xterm -e pulsemixer &
DISPLAY=:1 xterm -e python3 &
DISPLAY=:1 xterm &
