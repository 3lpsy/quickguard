# QuickGuard
A Wireguard to NetDev converter

# About
This simple script will parse Wireguard files via a hacky ConfigParser setup and output a netdev file. I built this for my purposes so most NetDev / WG keys are not supported. My main goal was to simply pull a bunch of Wireguard configuration files and then be able to easily parse those and add them to `/etc/systemd/network/somefile.netdev` in the correct format.

## Auto
After downloading several VPN configurations to a directory, I can use the following, which is specfic to `systemd-networkd` and `tailscale`.

```bash
# these are set in my session via my shell
export QUICKGUARD_VPN_DIR=$HOME/somepath
export QUICKGUARD_ALLOWED_IPS="0.0.0.0/2,64.0.0.0/3,96.0.0.0/6,100.0.0.0/10,100.128.0.0/9,101.0.0.0/8,102.0.0.0/7,104.0.0.0/5,112.0.0.0/4,128.0.0.0/1"
export QUICKGUARD_MASK="0x8888"
export QUICKGUARD_OUTPUT="/etc/systemd/network/99-wg-vpn.netdev"
sudo -E python3 quickguard.py --auto --overwrite --chown-file --reload
```

The above environment variables are the only ones supported at the moment.

### History
The script will attempt to track the last file used when using `--auto` in a `history` file. This will be an `$XDG_DATA_HOME/quickguard/history`. If all potential files in the VPN directory have been used previously, the history is cleared. You can disable history with `--no-history` it will neither read the file nor write to it.

Alternatively to using `--auto`, you can use `fzf` to select which one you want to choose each time.
```bash
#!/bin/bash
QUICKGUARD_VPN_DIR="$HOME/path/to/your/vpnconfs"
ALLOWED_IPS="0.0.0.0/2,...omitted..."
sudo python3 quickguard.py -f 0x8888 -a "$ALLOWED_IPS" --overwrite --chown-file --reload -w $(find "$QUICKGUARD_VPN_DIR" -type f -name '*.conf' | fzf --prompt="Select VPN config > ") -o /etc/systemd/network/somefile.netdev
```

## Case Sensitivity
Case sensitivity within the configuration file matters. I based this off of what my VPN provider was using so adjust as appropriate until a more flexible approach is added.

## Output
All error messages are written to stderr by default with the netdev file being written to `stdout` by default. Additionally, Wireguard configurations can be writted in `stdin`.

## Reloading
The only reloading supported is calling `systemd-networkd` via `python-dbus`. This is optional and you don't need `python-dbus` to generate the NetDev files.

## Technical Parsing Details
Wireguard config files and NetDev files are `.ini` like but can have multiple entires such as `Peer` and `WireguardPeer`. `ConfigParser` does not like this. There's two main hacks in the script to permit the usage of `ConfigParser` with duplicate section names. The first uses a custom `dict` type. The second overwrites the `_name` property of the `SectionProxy` classes. This is why the `render` function just uses a separate `ConfigParser` for each section for laziness purposes. If extending, just know that many `ConfigParser` functions may be broken. If you want to use an external library, you may consider [wgconfig](https://www.github.com/towalink/wgconfig). Since I may want to run this as root, I tried to only use standard libraries for this script.

# Containerization
This script previously used an external library (`wgconfig`) so I built a container for it. It does not use any external libraries anymore (except optionally `python-dbus`) but if you wish to use containerization (which I do not recommend), you should review the following. If not reloading, containerization is probably unnecessary. Even so, `python-dbus` can be installed via your system package repo anyways. I used `podman` so things like handling `stdin` or file permissions (the user is dropped in the container) may not apply if using `docker`.

## Build Container in Podman
```
$ git clone https://github.com/3lpsy/quickguard
$ cd quickguard
$ podman build . -t quickguard
```

## Passing via stdin in Podman
Use the `-i` flag
```
$ cat mywireguard.conf | podman -i run quickguard
```

## Passing via mount in Podman
The container drops permissions so use `--userns=keep-id`
```
$ podman run --userns=keep-id -v /path/to/wg.conf:/data/wg.conf quickguard -w /data/wg.conf
```

## Automatically Updating Systemd in Container
While I don't use it anymore, you can review `quickguardc.sh` and customize it to your needs. Note that `QUICKGUARD_ARGS` cannot contain spaces. So if customizing `--allow-ips`, which is useful for tailscale, you shoud omit the spaces between the ranges.

# Options
```
usage: Quickguard [-h] [-w WG] [-n NAME] [-k KIND] [-d DESCRIPTION] [-f FIREWALL_MASK] [-F] [-a ALLOWED_IPS]
                  [-o OUTPUT] [-O] [-c] [-C CHOWN_USER] [-r] [-A] [-W VPN_DIR] [-H]

options:
  -h, --help            show this help message and exit
  -w, --wg WG           wireguard file
  -n, --name NAME       netdev name
  -k, --kind KIND       netdev kind
  -d, --description DESCRIPTION
                        netdev description
  -f, --firewall-mask FIREWALL_MASK
                        netdev firewall mask such as '0x8888'
  -F, --no-firewall-mask
                        do not include netdev firewall mask (QUICKGUARD_MASK
  -a, --allowed-ips ALLOWED_IPS
                        allowed IPs to override (QUICKGUARD_ALLOWED_IPS
  -o, --output OUTPUT   output location, will fail if it exists and --overwrite is not set(QUICKGUARD_OUTPUT)
  -O, --overwrite       overwrite output location, will destroy existing file
  -c, --chown-file      change ownership of file if running as root
  -C, --chown-user CHOWN_USER
                        user:group to chown to
  -r, --reload          reload via dbus if it exists
  -A, --auto            auto swap via VPN directory, requires -W or QUICKGUARD_VPN_DIR
  -W, --vpn-dir VPN_DIR
                        vpns directory (QUICKGUARD_VPN_DIR)
  -H, --no-history      don't save history of last auto swapped vpn
```
