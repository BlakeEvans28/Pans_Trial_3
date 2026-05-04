"""Run the Pan's Trial room server for desktop or web clients."""

from __future__ import annotations

import argparse
import os
import socket
import ssl
import time
from pathlib import Path

from multiplayer.local_room import (
    DEFAULT_MAX_ROOMS,
    DEFAULT_PORT,
    DEFAULT_ROOM_TIMEOUT_SECONDS,
    LocalRoomServer,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Host Pan's Trial local room matches.")
    parser.add_argument("--host", default="0.0.0.0", help="Address to bind. Use 0.0.0.0 for LAN play.")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", DEFAULT_PORT)),
        help="Starting port for the room server. Defaults to the PORT environment variable when set.",
    )
    parser.add_argument("--certfile", type=Path, help="TLS certificate file for HTTPS room hosting.")
    parser.add_argument("--keyfile", type=Path, help="TLS private key file for HTTPS room hosting.")
    parser.add_argument(
        "--web-root",
        type=Path,
        default=Path("WEB_BUILD") / "site",
        help="Static web build folder to serve from the room-server URL.",
    )
    parser.add_argument(
        "--max-rooms",
        type=int,
        default=int(os.environ.get("PAN_TRIAL_MAX_ROOMS", DEFAULT_MAX_ROOMS)),
        help="Maximum number of active rooms before create-room requests are rejected.",
    )
    parser.add_argument(
        "--room-timeout-seconds",
        type=int,
        default=int(os.environ.get("PAN_TRIAL_ROOM_TIMEOUT_SECONDS", DEFAULT_ROOM_TIMEOUT_SECONDS)),
        help="Inactive room cleanup timeout. Can also be set with PAN_TRIAL_ROOM_TIMEOUT_SECONDS.",
    )
    return parser.parse_args()


def create_ssl_context(certfile: Path | None, keyfile: Path | None) -> ssl.SSLContext | None:
    """Create a server TLS context when certificate paths are provided."""
    if certfile is None and keyfile is None:
        return None
    if certfile is None or keyfile is None:
        raise SystemExit("--certfile and --keyfile must be provided together.")

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context


def get_lan_addresses() -> list[str]:
    """Return likely LAN addresses for showing friendlier connection URLs."""
    addresses = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 80))
            address = sock.getsockname()[0]
            if not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass

    return sorted(addresses)


def main() -> None:
    args = parse_args()
    ssl_context = create_ssl_context(args.certfile, args.keyfile)
    requested_web_root = args.web_root
    if requested_web_root is not None and not requested_web_root.is_absolute():
        requested_web_root = Path(__file__).resolve().parent / requested_web_root
    web_root = requested_web_root if requested_web_root and requested_web_root.exists() else None
    server = LocalRoomServer(
        host=args.host,
        port=args.port,
        ssl_context=ssl_context,
        web_root=web_root,
        max_rooms=args.max_rooms,
        room_timeout_seconds=args.room_timeout_seconds,
    )
    server.start()
    scheme = "https" if ssl_context is not None else "http"

    print("=" * 54)
    print("Pan's Trial room server")
    print("=" * 54)
    print(f"Listening on : {server.host}:{server.port}")
    print(f"Health check : {scheme}://127.0.0.1:{server.port}/health")
    print(f"Room limits  : max {server.store.max_rooms}, timeout {server.store.room_timeout_seconds}s")
    if web_root is not None:
        print(f"Web root     : {web_root.resolve()}")
        print(f"Game URL     : {scheme}://127.0.0.1:{server.port}")
    else:
        print("Web root     : not found; serving room-server status page only")
        print(f"Local URL    : {scheme}://127.0.0.1:{server.port}")
    for address in get_lan_addresses():
        label = "LAN Game URL" if web_root is not None else "LAN URL"
        print(f"{label:<13}: {scheme}://{address}:{server.port}")
    if web_root is not None:
        print("Open the Game URL in a browser. The same URL is used for Two Player rooms.")
    else:
        print("Paste one of these URLs into the game's Two Player Server URL field.")
        print("Give your friend the LAN URL and the room code from the game.")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopping room server.")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
