"""Local multiplayer helpers for Pan's Trial."""

__all__ = ["LocalRoomClient", "LocalRoomServer", "create_quick_match_game"]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from .local_room import LocalRoomClient, LocalRoomServer, create_quick_match_game

    exports = {
        "LocalRoomClient": LocalRoomClient,
        "LocalRoomServer": LocalRoomServer,
        "create_quick_match_game": create_quick_match_game,
    }
    globals().update(exports)
    return exports[name]
