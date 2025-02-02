#!/usr/bin/env python3

import grp
import os
import pwd
import sys
from argparse import ArgumentParser
from collections import OrderedDict
from configparser import ConfigParser, SectionProxy
from io import StringIO
from pathlib import Path
from typing import Any, TextIO


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
    parser = ArgumentParser("Quickguard")
    parser.add_argument("-w", "--wg", help="wireguard file")
    parser.add_argument("-n", "--name", help="netdev name", default="wg0")
    parser.add_argument("-k", "--kind", help="netdev kind", default="wireguard")
    parser.add_argument("-d", "--description", help="netdev description", default="Wireguard tunnel")
    parser.add_argument("-f", "--firewall-mask", help="netdev firewall mask", default="0x8888")
    parser.add_argument("-F", "--no-firewall-mask", help="do not include netdev firewall mask", action="store_true")
    parser.add_argument("-a", "--allowed-ips", help="allowed IPs to override")
    parser.add_argument("-o", "--output", help="output location, will fail if it exists and --overwrite is not set")
    parser.add_argument(
        "-O",
        "--overwrite",
        action="store_true",
        help="overwrite output location, will destroy existing file",
    )
    parser.add_argument("-c", "--chown-file", action="store_true", help="change ownership of file if running as root")
    parser.add_argument("-C", "--chown-user", help="user:group to chown to", default="systemd-network:systemd-network")
    parser.add_argument("-r", "--reload", help="reload via dbus if it exists", action="store_true")

    args = parser.parse_args()
    wg = ConfigParser(defaults=None, dict_type=MultiSectionDict, strict=False)
    wg.optionxform = str
    if args.wg:
        wgp = Path(args.wg)
        if not wgp.exists():
            eprint(f"[!] Wireguard file does not exist: {args.wg}")
            sys.exit(1)
        eprint(f"Parsing Wireguard configuration file: {wgp.resolve()}")
        wg.read_file(wgp.open())
    elif not sys.stdin.isatty():
        # Need to pass -i to podman for stdin
        stdin = sys.stdin.read()
        if not stdin:
            eprint("[!] No wireguard file provided via --wg or stdin")
            sys.exit(1)
        wg.read_file(StringIO(stdin))
    else:
        parser.print_help()
        eprint("[!] No wireguard file provided via --wg or stdin")
        sys.exit(1)
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
    if args.firewall_mask:
        wireguard["FirewallMark"] = args.firewall_mask
    peers: list[dict] = []
    for peer_key in peer_keys:
        # Original _name is Peer, need Peer1, Peer2 etc
        peer_section = wg[peer_key]
        peer_section._name = peer_key
        peer = dict(peer_section)
        wireguard_peer = {}
        allowed_ips = args.allowed_ips
        if not allowed_ips and "AllowedIPs" in peer:
            allowed_ips = peer["AllowedIPs"]
        if allowed_ips:
            wireguard_peer["AllowedIPs"] = allowed_ips
        if "PublicKey" in peer:
            wireguard_peer["PublicKey"] = peer["PublicKey"]
        if "Endpoint" in peer:
            wireguard_peer["Endpoint"] = peer["Endpoint"]
        peers.append(wireguard_peer)

    if args.output:
        op = Path(args.output)
        if op.exists() and not args.overwrite:
            eprint(f"[!] Output file exists and overwrite is not set: {args.output}")
            sys.exit(1)
        if not op.exists():
            op.touch()
        # If writing to file do not care about stderr
        eprint(f"Writing netdev to file: {args.output}")
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
                eprint(f"Changing ownership of output to: {user}({cuid})/{group}({cgid})")
                os.chown(op, cuid, cgid)
            except PermissionError:
                eprint("[!]Permission denied - cannot change ownership")
                sys.exit(1)
            except (OSError, KeyError) as e:
                eprint(f"Error changing ownership: {e}")
                sys.exit(1)

    else:
        render(netdev, wireguard, peers, sys.stdout)

    if args.reload:
        try:
            import dbus

            # Connect to the system bus
            bus = dbus.SystemBus()
            # Get the networkd object from the correct service and object path
            networkd_obj = bus.get_object("org.freedesktop.network1", "/org/freedesktop/network1")
            # Use the correct Manager interface which provides the Reload method
            networkd_iface = dbus.Interface(networkd_obj, "org.freedesktop.network1.Manager")
            # Call the Reload method
            networkd_iface.Reload()
            eprint("Reloaded triggered for systemd-networkd")
        except ImportError:
            eprint("[!] Python dbus package not installed")


if __name__ == "__main__":
    main()
