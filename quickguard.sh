#!/bin/bash
# optionally source a file
# source someenvfile

p=$(ps -o comm= -p $PPID)
if [[ -t 0  && "$p" != "wofi" && "$p" != "systemd" ]]; then
	sudo -E quickguard.py --auto --overwrite --chown-file --reload
else
	if [ "$EUID" -ne 0 ]; then
		pkexec env PATH=$PATH HOME=$HOME \
			XDG_DATA_HOME=$XDG_DATA_HOME \
			QUICKGUARD_MASK=$QUICKGUARD_MASK \
			QUICKGUARD_ALLOWED_IPS=$QUICKGUARD_ALLOWED_IPS \
			QUICKGUARD_VPN_DIR=$QUICKGUARD_VPN_DIR \
			QUICKGUARD_OUTPUT=$QUICKGUARD_OUTPUT \
			quickguard.py --auto --overwrite --chown-file --reload
		notify-send -t 2000 "Quickguard exec status: $?"
		exit $?
	else
		notify-send -t 2000 "Quickguard exec status: $?"
		quickguard.py --auto --overwrite --chown-file --reload
	fi
fi


#sudo python3 $QG -o /etc/systemd/network/99-wg-vpn.netdev -a '0.0.0.0/2,64.0.0.0/3,96.0.0.0/6,100.0.0.0/10,100.128.0.0/9,101.0.0.0/8,102.0.0.0/7,104.0.0.0/5,112.0.0.0/4,128.0.0.0/1' -f 0x8888 -w $(find "$QUICKGUARD_VPN_DIR" -type f -name '*.conf' | fzf --prompt="Select VPN config > ") --overwrite --chown-file --reload
