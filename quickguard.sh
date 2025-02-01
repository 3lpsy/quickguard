#!/bin/bash
set -e
set -o pipefail

NETWORKD_DIR=/etc/systemd/network
OUTPUT_FILE=99-wg-vpn.netdev

NO_FZF=0
if ! command -v fzf &>/dev/null; then
  NO_FZF=1
fi

if [[ "$NO_FZ" -eq 0 &&  ${#QUICKGUARD_VPN_DIR} -gt 2 ]]; then
    INPUT_FILE=$(find "$QUICKGUARD_VPN_DIR" -type f -name '*.conf' | fzf --prompt="Select VPN config > ")
else
    INPUT_FILE="$1"
fi
echo "Converting $INPUT_FILE"
echo "cat $INPUT_FILE | podman run -i quickguard $QUICKGUARD_ARGS"
cat "$INPUT_FILE" | podman run -i quickguard ${QUICKGUARD_ARGS[@]} > "/tmp/${OUTPUT_FILE}"
echo "Wireguard file written to: /tmp/${OUTPUT_FILE}"

read -r -p "Do you want to write to $NETWORKD_DIR/${OUTPUT_FILE} (y/n): " answer
case "$answer" in
    [yY]|[yY][eE][sS])
        echo "Continuing..."
        echo "Moving /tmp/$OUTPUT_FILE" to "$NETWORKD_DIR/${OUTPUT_FILE}"
        sudo chown systemd-network:systemd-network "/tmp/$OUTPUT_FILE"
        sudo mv "/tmp/${OUTPUT_FILE}" "$NETWORKD_DIR/${OUTPUT_FILE}"
        sudo networkctl reload
        ;;
    *)
        echo "Aborting."
        exit 1
        ;;
esac
