"""
workspace/store.py
Persistence helpers for workspace metadata on device flash.
Each workspace lives under `.mlx/workspaces/<name>/workspace.json`.
"""

try:
    import ujson as json
except ImportError:
    import json

try:
    import uos as os
except ImportError:
    import os


MLX_DIR = ".mlx"
WORKSPACES_DIR = "workspaces"
CURRENT_FILE = "current"
WORKSPACE_FILE = "workspace.json"
_DIR_FLAG = 0x4000


def _join(*parts):
    """Join path parts with '/' for MicroPython compatibility."""
    return "/".join(str(part).strip("/") for part in parts if part is not None and part != "")


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _is_dir(path):
    try:
        mode = os.stat(path)[0]
    except OSError:
        return False
    return (mode & _DIR_FLAG) == _DIR_FLAG


def _ensure_dir(path):
    """Create a directory if it does not exist."""
    if not _exists(path):
        os.mkdir(path)


def _ensure_base_dirs():
    """Create the .mlx base folders if needed."""
    _ensure_dir(MLX_DIR)
    _ensure_dir(_join(MLX_DIR, WORKSPACES_DIR))


def _write_json(path, payload):
    with open(path, "w") as handle:
        handle.write(json.dumps(payload))


def _remove_tree(path):
    if not _exists(path):
        return

    if _is_dir(path):
        for name in os.listdir(path):
            _remove_tree(_join(path, name))
        os.rmdir(path)
        return

    os.remove(path)


def get_workspace_path(name):
    """Return the path to a workspace folder."""
    return _join(MLX_DIR, WORKSPACES_DIR, name)


def workspace_exists(name):
    """Return True when the workspace folder exists."""
    return _is_dir(get_workspace_path(name))


def list_workspaces():
    """List all persisted workspaces."""
    _ensure_base_dirs()
    root = _join(MLX_DIR, WORKSPACES_DIR)
    try:
        names = os.listdir(root)
    except OSError:
        return []

    result = []
    for name in names:
        if _is_dir(_join(root, name)):
            result.append(name)
    result.sort()
    return result


def get_current_workspace():
    """Return the active workspace name, or None."""
    _ensure_base_dirs()
    path = _join(MLX_DIR, CURRENT_FILE)
    if not _exists(path):
        return None

    try:
        with open(path, "r") as handle:
            data = json.load(handle)
    except Exception:
        return None

    return data.get("workspace")


def set_current_workspace(name):
    """Persist the active workspace name."""
    _ensure_base_dirs()
    _write_json(_join(MLX_DIR, CURRENT_FILE), {"workspace": name})


def get_workspace_config(name):
    """Load a workspace configuration dictionary."""
    if not workspace_exists(name):
        return None

    path = _join(get_workspace_path(name), WORKSPACE_FILE)
    if not _exists(path):
        return None

    try:
        with open(path, "r") as handle:
            return json.load(handle)
    except Exception:
        return None


def save_workspace_config(name, config):
    """Write workspace configuration to flash."""
    _ensure_base_dirs()
    folder = get_workspace_path(name)
    _ensure_dir(folder)
    _write_json(_join(folder, WORKSPACE_FILE), config)


def remove_workspace(name):
    """Delete a workspace and its persisted metadata."""
    if not workspace_exists(name):
        return False

    try:
        _remove_tree(get_workspace_path(name))
        return True
    except Exception:
        return False
