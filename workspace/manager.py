"""
workspace/manager.py
Workspace lifecycle management for create/open/list/remove/current.
"""

from workspace import store as workspace_store


def _default_workspace_config(name):
    return {
        "name": name,
        "modules": {},
        "created_at": 0,
    }


def create_workspace(name):
    """Create a workspace if needed and return its handle."""
    if not workspace_store.workspace_exists(name):
        workspace_store.save_workspace_config(name, _default_workspace_config(name))

    workspace_store.set_current_workspace(name)
    return open_workspace(name)


def open_workspace(name=None):
    """Open a workspace and return its handle."""
    if name is None:
        name = workspace_store.get_current_workspace()

    if not name or not workspace_store.workspace_exists(name):
        return None

    config = workspace_store.get_workspace_config(name) or _default_workspace_config(name)
    workspace_store.set_current_workspace(name)

    from workspace.handle import WorkspaceHandle

    return WorkspaceHandle(name, config)


def get_current_workspace():
    """Return the current workspace handle, or None."""
    return open_workspace()


def list_workspaces():
    """Return the persisted workspace names."""
    return workspace_store.list_workspaces()


def remove_workspace(name):
    """Remove a workspace and return a result dictionary."""
    current_name = workspace_store.get_current_workspace()
    if not workspace_store.remove_workspace(name):
        return {"success": False, "error": "Failed to remove workspace '%s'." % name}

    if current_name == name:
        remaining = workspace_store.list_workspaces()
        workspace_store.set_current_workspace(remaining[0] if remaining else None)

    return {"success": True, "removed": name}
