# QuickGuard
A Wireguard to NetDev converter

# About
This simple script will parse Wireguard files via wgconfig and output a netdev file. All error messages are written to stderr by default with the netdev file being written to `stdout` by default. Additionally, Wireguard configurations can be writted in `stdin`.

# Containerization
This script uses an external library. If using docker, some of this may not apply. If you wish to run it in the a container you can do the following:

## Build Container
```
$ git clone https://github.com/3lpsy/quickguard
$ cd quickguard
$ podman build . -t quickguard
```

## Passing via stdin
Use the `-i` flag
```
$ cat mywireguard.conf | podman -i run quickguard
```

## Passing via mount
The container drops permissions so use `--userns=keep-id`
```
$ podman run --userns=keep-id -v /path/to/wg.conf:/data/wg.conf quickguard -w /data/wg.conf
```
# Automatically Updating Systemd
I wrote this so I can easily convert Wireguard VPN configurations to Netdev configurations for `systemd-network`. I would not recommend running this as root. You can review quickguard.sh and customize it to your needs. However, note that `QUICKGUARD_ARGS` cannot contain spaces so if customizing `--allow-ips`, which is useful for tailscale, you shoud omit the spaces between the ranges.

# Usage
```
usage: Quickguard [-h] [-w WG] [-n NAME] [-k KIND] [-d DESCRIPTION]
                  [-f FIREWALL_MASK] [-F] [-a ALLOWED_IPS] [-o OUTPUT]
                  [-O OVERWRITE]

options:
  -h, --help            show this help message and exit
  -w WG, --wg WG        wireguard file
  -n NAME, --name NAME  netdev name
  -k KIND, --kind KIND  netdev kind
  -d DESCRIPTION, --description DESCRIPTION
                        netdev description
  -f FIREWALL_MASK, --firewall-mask FIREWALL_MASK
                        netdev firewall mask
  -F, --no-firewall-mask
                        do not include netdev firewall mask
  -a ALLOWED_IPS, --allowed-ips ALLOWED_IPS
                        allowed IPs to override
  -o OUTPUT, --output OUTPUT
                        output location, will fail if it exists and
                        --overwrite is not set
  -O OVERWRITE, --overwrite OVERWRITE
                        overwrite output location, will destroy existing file
```
