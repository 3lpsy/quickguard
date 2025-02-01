#!/usr/bin/env python3

import sys
from argparse import ArgumentParser
from configparser import ConfigParser
from io import StringIO
from pathlib import Path
from typing import Any

from wgconfig import WGConfig


def eprint(*args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    if not kwargs:
        kwargs = {}
    print(*args, file=sys.stderr, **kwargs)


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
    parser.add_argument("-O", "--overwrite", help="overwrite output location, will destroy existing file")

    args = parser.parse_args()
    wg = WGConfig()
    if args.wg:
        wgp = Path(args.wg)
        if not wgp.exists():
            eprint(f"[!] Wireguard file does not exist: {args.wg}")
            sys.exit(1)
        wg.read_from_fileobj(wgp.open())
    elif not sys.stdin.isatty():
        # Need to pass -i to podman for stdin
        stdin = sys.stdin.read()
        if not stdin:
            eprint("[!] No wireguard file provided via --wg or stdin")
            sys.exit(1)
        wg.read_from_fileobj(StringIO(stdin))
    else:
        parser.print_help()
        eprint("[!] No wireguard file provided via --wg or stdin")
        sys.exit(1)
    interface = wg.get_interface()
    if not interface:
        eprint("[!] Failed to parse interface in provided Wireguard configuration")
        sys.exit(1)
    # returns dict keyed by peers public key when keys_only=False
    peers = wg.get_peers(keys_only=False)
    if not isinstance(peers, dict):
        raise TypeError
    if not peers:
        eprint("[!] Failed to find peers in Wireguard configuration")
        sys.exit(1)
    if len(peers.keys()) > 1:
        eprint("[!] Multiple peers not supported yet")
        sys.exit(1)
    netdev = ConfigParser()
    netdev.optionxform = str
    netdev["NetDev"] = {
        "Name": args.name,
        "Kind": args.kind,
        "Description": args.description,
    }
    netdev["WireGuard"] = {
        "PrivateKey": wg.get_interface()["PrivateKey"],
    }
    if args.firewall_mask:
        netdev["WireGuard"]["FirewallMark"] = args.firewall_mask

    peer = next(iter(peers.values()))
    allowed_ips = args.allowed_ips if args.allowed_ips else peer["AllowedIPs"]
    netdev["WireGuardPeer"] = {
        "AllowedIPs": allowed_ips,
        "PublicKey": peer["PublicKey"],
        "Endpoint": peer["Endpoint"],
    }
    if args.output:
        op = Path(args.output)
        if op.exists() and not args.overwrite:
            eprint(f"[!] Output file exists and overwrite is not set: {args.output}")
            sys.exit(1)
        if not op.exists():
            op.touch()
        # If writing to file do not care about stderr
        eprint(f"Writing netdev to file: {args.output}")
        netdev.write(op.open(mode="w"))
    else:
        netdev.write(sys.stdout)


if __name__ == "__main__":
    main()
