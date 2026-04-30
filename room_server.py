"""Run the Pan's Trial room server for desktop or web clients."""

from __future__ import annotations

import argparse
import socket
import time

from multiplayer.local_room import DEFAULT_PORT, LocalRoomServer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Host Pan's Trial local room matches.")
    parser.add_argument("--host", default="0.0.0.0", help="Address to bind. Use 0.0.0.0 for LAN play.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Starting port for the room server.")
    return parser.parse_args()


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
    server = LocalRoomServer(host=args.host, port=args.port)
    server.start()

    print("=" * 54)
    print("Pan's Trial room server")
    print("=" * 54)
    print(f"Listening on : {server.host}:{server.port}")
    print(f"Local URL    : http://127.0.0.1:{server.port}")
    for address in get_lan_addresses():
        print(f"LAN URL      : http://{address}:{server.port}")
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
