#!/usr/bin/env python3

import grp
import os
import pwd
import sys
from argparse import ArgumentParser, Namespace
from collections import OrderedDict
from configparser import ConfigParser, SectionProxy
from io import StringIO
from pathlib import Path
from typing import Any, TextIO
import random

# for debugging elevation
DEBUG_LOG=False

def get_target_wg(args: Namespace, rerun: bool | None = False) -> Path|None:
    if args.wg:
        return Path(args.wg)
    elif args.auto:
        wg_dirs_opt = args.vpn_dir or os.getenv("QUICKGUARD_VPN_DIR") or ""
        if not wg_dirs_opt:
            eprint("[!] Auto swapping requires a VPN directory")
            sys.exit(1)
        wg_dirs = Path(wg_dirs_opt)
        wgs = [f.name for f in wg_dirs.iterdir() if f.is_file()]
        if not wgs:
            eprint(f"[!] No wireguard configs found in vpn dir: {wg_dirs}")
            sys.exit(1)
        history = []
        history_path = get_data_home().joinpath("quickguard").joinpath("history")
        if not args.no_history:
            history_path.parent.mkdir(parents=True, exist_ok=True)
            history_path.touch(exist_ok=True)
            history = [line.strip() for line in history_path.open()]

        # loaded history, choose one not in
        random.shuffle(wgs)
        for target in wgs:
            if target not in history: # will be empty if no_history
                # save chosen target
                if not args.no_history:
                    history_path.open('a').write(f"{target}\n")
                eprint(f"[*] Auto configuration: {target}")
                return wg_dirs.joinpath(target)
        if rerun:
            eprint(f"[!] Unable to find a target in directory even after clearing history: Probably bug")
            eprint(f"[!] VPN Dir: {wg_dirs}")
            eprint(f"[!] History Path: {history_path}")
            sys.exit(1)
        # have not found a target not in history
        if not args.no_history:
            eprint(f"[-] Cleaning history")
            get_data_home().joinpath("quickguard").joinpath("history").write_text("")
        return get_target_wg(args, True) # lazy
    return None # maybe stdin

def get_data_home() -> Path:
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home)
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data)
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data)
        return Path.home()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path.home() / ".local" / "share"


# Multiple Peers Can Exist
class MultiSectionDict(OrderedDict):
    _dict_unique = 0  # class variable
    _proxy_unique = 0  # class variable

    # _proxies uses SectionProxy
    # DEFAULT key will throw off index between _sections and _proxies
    def __setitem__(self, key: str, val: Any) -> None:  # noqa: ANN401
        if key == "DEFAULT":
            OrderedDict.__setitem__(self, key, val)
        elif isinstance(val, dict):
            self._dict_unique += 1
            # Make key unique
            key += str(self._dict_unique)
        elif isinstance(val, SectionProxy):
            self._proxy_unique += 1
            # Make key unique
            key += str(self._proxy_unique)
        OrderedDict.__setitem__(self, key, val)

    # De
    def __getitem__(self, key: str) -> Any:  # noqa: ANN401
        return OrderedDict.__getitem__(self, key)


def eprint(*args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    if not kwargs:
        kwargs = {}
    print(*args, file=sys.stderr, **kwargs)
    if DEBUG_LOG:
        with open('/tmp/quickguard.txt', 'a') as file:
            file.write(f"{args[0]}\n")

# fp should be in append mode
def render(netdev: dict, wireguard: dict, peers: list[dict], fp: TextIO) -> None:
    # lazy, just use configparser
    sections = [("NetDev", netdev), ("WireGuard", wireguard)]
    sections.extend([("WireGuardPeer", p) for p in peers])
    for h, d in sections:
        c = ConfigParser()
        c.optionxform = str
        c[h] = d
        c.write(fp)


def main() -> None:
    if DEBUG_LOG:
        Path("/tmp/quickguard.txt").write_text("")
    parser = ArgumentParser("Quickguard")
    parser.add_argument("-w", "--wg", help="wireguard file")
    parser.add_argument("-n", "--name", help="netdev name", default="wg0")
    parser.add_argument("-k", "--kind", help="netdev kind", default="wireguard")
    parser.add_argument("-d", "--description", help="netdev description", default="Wireguard tunnel")
    parser.add_argument("-f", "--firewall-mask", help="netdev firewall mask such as '0x8888'")
    parser.add_argument("-F", "--no-firewall-mask", help="do not include netdev firewall mask (QUICKGUARD_MASK", action="store_true")
    parser.add_argument("-a", "--allowed-ips", help="allowed IPs to override (QUICKGUARD_ALLOWED_IPS")
    parser.add_argument("-o", "--output", help="output location, will fail if it exists and --overwrite is not set(QUICKGUARD_OUTPUT)")
    parser.add_argument(
        "-O",
        "--overwrite",
        action="store_true",
        help="overwrite output location, will destroy existing file",
    )
    parser.add_argument("-c", "--chown-file", action="store_true", help="change ownership of file if running as root")
    parser.add_argument("-C", "--chown-user", help="user:group to chown to", default="systemd-network:systemd-network")
    parser.add_argument("-r", "--reload", help="reload via dbus if it exists", action="store_true")
    parser.add_argument("-A", "--auto", help="auto swap via VPN directory, requires -W or QUICKGUARD_VPN_DIR", action="store_true")
    parser.add_argument("-W", "--vpn-dir", help="vpns directory (QUICKGUARD_VPN_DIR)", type=str)
    parser.add_argument("-H", "--no-history", help="don't save history of last auto swapped vpn", action="store_true")

    args = parser.parse_args()
    wg = ConfigParser(defaults=None, dict_type=MultiSectionDict, strict=False)
    wg.optionxform = str

    wg_target = get_target_wg(args)

    if wg_target:
        if not wg_target.exists():
            eprint(f"[!] Wireguard file does not exist: {wg_target}")
            sys.exit(1)
        eprint(f"[*] Parsing Wireguard configuration file: {wg_target.resolve()}")
        wg.read_file(wg_target.open())
    elif not sys.stdin.isatty():
        # Need to pass -i to podman for stdin
        stdin = sys.stdin.read()
        if not stdin:
            eprint("[!] No wireguard file provided via --wg or stdin")
            sys.exit(1)
        wg.read_file(StringIO(stdin))
    else:
        parser.print_help()
        eprint("[!] No wireguard file provided via --wg, stdin, or via auto")
        sys.exit(1)

    # resolve args vs env
    mask= args.firewall_mask or os.getenv("QUICKGUARD_MASK") or ""
    if mask:
        eprint(f"[*] Custom firewall mask: {mask}")
    allowed_ips = args.allowed_ips or os.getenv("QUICKGUARD_ALLOWED_IPS") or ""
    if allowed_ips:
        eprint(f"[*] Custom allowed IPs: {allowed_ips}")
    output = args.output or os.getenv("QUICKGUARD_OUTPUT") or ""
    if output:
        eprint(f"[*] Custom output: {output}")

    # get interface_key an ensure only one exist
    interface_key = ""
    for section in wg.sections():
        if section.startswith("Interface"):
            interface_key = section
            continue
        if interface_key and section.startswith("Interface"):
            eprint("[!] Multiple interfaces not supported in Wireguard configuration")
            sys.exit(1)
    if not interface_key:
        eprint("[!] Could not find Interface section in configuration")
        sys.exit(1)

    # build interface
    # At this point we know Interface exists
    # The SectionProxy holds it's real name Interface but ConfigParser has unique name
    # Just overwrite and grab data
    interface_section = wg[interface_key]
    interface_section._name = interface_key
    interface = dict(interface_section)
    private_key = ""
    if "PrivateKey" not in interface:
        eprint("[!] No PrivateKey found in Interface")
        sys.exit(1)
    else:
        private_key = interface["PrivateKey"]

    # Ensure perr exists
    peer_keys = [sn for sn in wg.sections() if sn.startswith("Peer")]
    if not peer_keys:
        eprint("[!] No Peer keys found in Wireguard configuration")
        sys.exit(1)

    # don't want to use ConfigParser for NetDev until rendering as most functions are broken
    netdev = {
        "Name": args.name,
        "Kind": args.kind,
        "Description": args.description,
    }
    wireguard = {
        "PrivateKey": private_key,
    }
    if mask:
        wireguard["FirewallMark"] = mask

    peers: list[dict] = []
    for peer_key in peer_keys:
        # Original _name is Peer, need Peer1, Peer2 etc
        peer_section = wg[peer_key]
        peer_section._name = peer_key
        peer = dict(peer_section)
        wireguard_peer = {}
        if allowed_ips and "AllowedIPs" in peer:
            eprint(f"[!] AllowedIPs found in configuration. Custom allowed IPs will be used instead.")
        if not allowed_ips and "AllowedIPs" in peer:
            allowed_ips = peer["AllowedIPs"]
        if allowed_ips:
            wireguard_peer["AllowedIPs"] = allowed_ips
        if "PublicKey" in peer:
            wireguard_peer["PublicKey"] = peer["PublicKey"]
        if "Endpoint" in peer:
            wireguard_peer["Endpoint"] = peer["Endpoint"]
        peers.append(wireguard_peer)

    if output:
        op = Path(output)
        if op.exists() and not args.overwrite:
            eprint(f"[!] Output file exists and overwrite is not set: {output}")
            sys.exit(1)
        if not op.exists():
            op.touch()
        # If writing to file do not care about stderr
        eprint(f"[*] Writing netdev to file: {output}")
        op.write_text("")
        render(netdev, wireguard, peers, op.open("+a"))
        if args.chown_file:
            if os.getuid() != 0:
                eprint("[!] Not root user. Attempting to chown anyways")
            ug = args.chown_user
            user = ug
            group = ""
            if ":" in ug:
                ugp = ug.split(":")
                if len(ugp) != 2:
                    eprint(f"[!] Invalid chown-user: {ug}")
                    sys.exit(1)
                user = ugp[0]
                group = ugp[1]
            try:
                cuid = pwd.getpwnam(user).pw_uid
                # use default group or custom group
                cgid = op.stat().st_gid if not group else grp.getgrnam(group).gr_gid
                eprint(f"[*] Changing ownership of output to: {user}({cuid})/{group}({cgid})")
                os.chown(op, cuid, cgid)
            except PermissionError:
                eprint("[!]Permission denied - cannot change ownership")
                sys.exit(1)
            except (OSError, KeyError) as e:
                eprint(f"[!] Error changing ownership: {e}")
                sys.exit(1)

    else:
        render(netdev, wireguard, peers, sys.stdout)

    if args.reload:
        try:
            import dbus
            try:
                if os.getuid() != 0:
                    eprint("[!] Not root user. Attempting to reliad anyways")
                # Connect to the system bus
                bus = dbus.SystemBus()
                networkd_obj = bus.get_object("org.freedesktop.network1", "/org/freedesktop/network1")
                networkd_iface = dbus.Interface(networkd_obj, "org.freedesktop.network1.Manager")
                networkd_iface.Reload()
                eprint("[*] Reload triggered for systemd-networkd")

                resolved_obj = bus.get_object("org.freedesktop.resolve1", "/org/freedesktop/resolve1")
                resolved_iface = dbus.Interface(resolved_obj, "org.freedesktop.resolve1.Manager")
                resolved_iface.FlushCaches()  # Optional: flush DNS caches
                resolved_iface.ResetStatistics()
                eprint("[*] Cache flushed for systemd-resolved")
            except dbus.exceptions.DBusException as e:
                eprint("[!] Error reloading with dbus. Either not permitted or not using systemd-{networkd,resolved}")
                sys.exit(1)
        except ImportError:
            eprint("[!] Python dbus package not installed")
        except Exception as e:
            print(type(e))


if __name__ == "__main__":
    main()
