"""
Core board management.
Loads a minimal board profile and a separate capabilities document.
"""

try:
    import ujson as json
except ImportError:
    import json

try:
    import uos as os
except ImportError:
    import os


ACTIVE_BOARD = None
INFO_FILE = "info.json"


def _dirname(path):
    """Return the parent directory for a filesystem path."""
    text = str(path).rstrip("/")
    if "/" not in text:
        return ""
    return text.rsplit("/", 1)[0]


def _join_path(*parts):
    """Join path fragments without depending on pathlib or os.path."""
    prefix = ""
    clean = []

    for index, part in enumerate(parts):
        if part is None:
            continue
        text = str(part)
        if index == 0 and text.startswith("/"):
            prefix = "/"
        text = text.strip("/")
        if text:
            clean.append(text)

    return prefix + "/".join(clean)


_THIS_FILE = globals().get("__file__", "core/board.py")
_THIS_DIR = _dirname(_THIS_FILE)
_PROJECT_ROOT = _dirname(_THIS_DIR)
BOARDS_ROOT = _join_path(_PROJECT_ROOT, "platforms", "boards")


def _board_dir(board_id=None):
    return _join_path(BOARDS_ROOT, board_id or ACTIVE_BOARD)


def _load_json(path):
    with open(path, "r") as handle:
        return json.load(handle)


def _normalize_name(name):
    text = str(name or "").strip().lower()
    chars = []
    for char in text:
        if "a" <= char <= "z":
            chars.append(char)
            continue
        if "0" <= char <= "9":
            chars.append(char)
    return "".join(chars)


def _require_active_board(board_id=None):
    selected = board_id or ACTIVE_BOARD
    if not selected:
        raise RuntimeError("No board loaded. Use mlx.board.load.<alias>() first.")
    return selected


def get_active_board():
    """Return the active board identifier."""
    return ACTIVE_BOARD


def set_active_board(board_id):
    """Switch the active board profile."""
    if not board_exists(board_id):
        raise ValueError("Unknown board '%s'." % board_id)

    global ACTIVE_BOARD
    ACTIVE_BOARD = board_id
    return ACTIVE_BOARD


def board_exists(board_id):
    """Return True when a board profile exists and is readable."""
    try:
        _load_json(_join_path(BOARDS_ROOT, board_id, INFO_FILE))
        return True
    except Exception:
        return False


def list_boards():
    """Return available board entries with aliases."""
    try:
        names = os.listdir(BOARDS_ROOT)
    except OSError:
        return []

    boards = []
    for name in names:
        if not board_exists(name):
            continue

        profile = load_board_profile(name)
        aliases = profile.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []

        boards.append(
            {
                "id": profile.get("id", name),
                "name": profile.get("name", name),
                "family": profile.get("family"),
                "series": profile.get("series"),
                "aliases": aliases,
            }
        )

    boards.sort(key=lambda item: item.get("id", ""))
    return boards


def resolve_board(name):
    """Resolve a board alias or id to its canonical board id."""
    target = _normalize_name(name)
    if not target:
        raise ValueError("Board name is required.")

    for entry in list_boards():
        board_id = entry.get("id")
        values = [board_id] + list(entry.get("aliases", []))
        for value in values:
            if _normalize_name(value) == target:
                return board_id

    raise ValueError("Unknown board '%s'." % name)


def load_board(name):
    """Load a board by alias or canonical id and make it active."""
    board_id = resolve_board(name)
    set_active_board(board_id)
    return get_board_info(board_id)


def load_board_profile(board_id=None):
    """Load the minimal board profile JSON."""
    selected = _require_active_board(board_id)
    return _load_json(_join_path(_board_dir(selected), INFO_FILE))


def load_board_capabilities(board_id=None):
    """Load the detailed capabilities JSON for a board."""
    profile = load_board_profile(board_id)
    files = profile.get("files", {})
    capabilities_file = files.get("capabilities", "capabilities.json")
    return _load_json(_join_path(_board_dir(board_id), capabilities_file))


def get_board_info(board_id=None):
    """Return the public board identity and runtime profile."""
    profile = load_board_profile(board_id)
    return {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "vendor": profile.get("vendor"),
        "family": profile.get("family"),
        "series": profile.get("series"),
        "soc": profile.get("soc"),
        "module": profile.get("module"),
        "aliases": profile.get("aliases", []),
        "runtime": profile.get("runtime", {}),
    }


def get_capabilities(board_id=None):
    """Return the full capability map for the selected board."""
    return load_board_capabilities(board_id)


def has(feature, board_id=None):
    """Return True if a top-level or sectioned feature is available."""
    capabilities = get_capabilities(board_id)

    if feature in capabilities:
        value = capabilities[feature]
        return bool(value)

    for section_name in ("wireless", "usb", "analog", "peripherals", "security", "ai"):
        section = capabilities.get(section_name, {})
        if not isinstance(section, dict) or feature not in section:
            continue

        value = section[feature]
        if isinstance(value, dict) and "supported" in value:
            return bool(value["supported"])
        return bool(value)

    return False
