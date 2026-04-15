"""
MicroLabxAI
Main public API for board discovery, capabilities, and workspace access.
"""


def _import_module(module_name):
    """Import a module using MicroPython-friendly builtins."""
    try:
        module = __import__(module_name, None, None, ("*",))
    except ImportError as exc:
        raise RuntimeError("Unable to import %s." % module_name) from exc
    return module


def _require_api(module_name, func_name):
    """Resolve a public runtime API only when it is needed."""
    module = _import_module(module_name)

    func = getattr(module, func_name, None)
    if not callable(func):
        raise NotImplementedError("%s.%s() is not implemented yet." % (module_name, func_name))
    return func


def _is_loader_name(value):
    """Return True when a value is safe to expose as a loader attribute."""
    if not value:
        return False

    text = str(value)
    for char in text:
        if char == "_":
            continue
        if "a" <= char <= "z":
            continue
        if "A" <= char <= "Z":
            continue
        if "0" <= char <= "9":
            continue
        return False

    return True


def _is_runtime_name(value):
    """Return True when a value can be exposed as a REPL variable or dot attribute."""
    if not _is_loader_name(value):
        return False

    first = str(value)[0]
    if first == "_":
        return True
    if "a" <= first <= "z":
        return True
    if "A" <= first <= "Z":
        return True
    return False


def _runtime_module():
    """Return the current top-level runtime module when available."""
    try:
        return __import__("__main__")
    except ImportError:
        return None


def _publish_runtime_object(name, value):
    """Expose a runtime object in the REPL using its workspace name."""
    if not _is_runtime_name(name):
        return

    module = _runtime_module()
    if module is None:
        return

    try:
        setattr(module, str(name), value)
    except Exception:
        pass


def _remove_runtime_object(name):
    """Remove a previously exposed runtime object from the REPL."""
    if not _is_runtime_name(name):
        return

    module = _runtime_module()
    if module is None or not hasattr(module, str(name)):
        return

    try:
        delattr(module, str(name))
    except Exception:
        pass


class _BoardAPI:
    """Board information namespace exposed as ``mlx.board``."""

    def __init__(self):
        self.load = _BoardLoadAPI(self)

    def _core(self, func_name):
        return _require_api("core.board", func_name)

    def info(self):
        """Return the current board profile."""
        return self._core("get_board_info")()

    def capabilities(self):
        """Return the current board capability map."""
        return self._core("get_capabilities")()

    def list(self):
        """List all available board profiles and aliases."""
        return self._core("list_boards")()

    def current(self):
        """Return the active board identifier."""
        return self._core("get_active_board")()


class _BoardLoadAPI:
    """Loader namespace exposed as ``mlx.board.load``."""

    def __init__(self, board_api):
        self._board_api = board_api
        self._families = []
        self.refresh()

    def _make_loader(self, alias):
        def loader():
            return self._board_api._core("load_board")(alias)

        return loader

    def refresh(self):
        """Rebuild the available board loader methods."""
        for name in self._families:
            if hasattr(self, name):
                delattr(self, name)

        self._families = []
        try:
            entries = self._board_api._core("list_boards")()
        except Exception:
            return self

        if not isinstance(entries, (list, tuple)):
            return self

        family_groups = {}
        for entry in entries:
            family_name = self._entry_family(entry)
            if not family_name:
                continue
            if family_name not in family_groups:
                family_groups[family_name] = []
            family_groups[family_name].append(entry)

        for family_name in family_groups:
            if family_name in self._families:
                continue
            setattr(
                self,
                family_name,
                _BoardFamilyLoadAPI(self._board_api, family_name, family_groups[family_name]),
            )
            self._families.append(family_name)

        return self

    def _entry_family(self, entry):
        if not isinstance(entry, dict):
            return None

        family = entry.get("family")
        if not _is_loader_name(family):
            return None
        return family

    def __dir__(self):
        names = set(self.__dict__.keys())
        for name in self._families:
            names.add(name)
        result = list(names)
        result.sort()
        return result


class _BoardFamilyLoadAPI:
    """Family namespace exposed as ``mlx.board.load.<family>``."""

    def __init__(self, board_api, family_name, entries):
        self._board_api = board_api
        self._family_name = family_name
        self._names = []
        self.refresh(entries)

    def _make_loader(self, alias):
        def loader():
            return self._board_api._core("load_board")(alias)

        return loader

    def refresh(self, entries):
        for name in self._names:
            if hasattr(self, name):
                delattr(self, name)

        self._names = []

        for entry in entries:
            for value in self._entry_series_names(entry):
                if not _is_loader_name(value):
                    continue
                if value in self._names:
                    continue
                setattr(self, value, self._make_loader(value))
                self._names.append(value)

        return self

    def _entry_series_names(self, entry):
        if not isinstance(entry, dict):
            return []

        values = []
        series = entry.get("series")
        if series:
            values.append(series)
        if not values:
            board_id = entry.get("id")
            if board_id:
                values.append(board_id)
        return values

    def __dir__(self):
        names = set(self.__dict__.keys())
        for name in self._names:
            names.add(name)
        result = list(names)
        result.sort()
        return result


class _WorkspaceAPI:
    """Workspace lifecycle namespace exposed as ``mlx.workspace``."""

    def __init__(self):
        self.switch = _WorkspaceSwitchAPI(self)
        self.remove = _WorkspaceRemoveAPI(self)

    def _manager(self, func_name):
        return _require_api("workspace.manager", func_name)

    def create(self, name):
        """Create a workspace and return its handle."""
        handle = self._manager("create_workspace")(name)
        if handle is not None:
            _publish_runtime_object(getattr(handle, "name", name), handle)
        self.switch.refresh()
        self.remove.refresh()
        return handle

    def list(self):
        """List available workspaces."""
        return self._manager("list_workspaces")()

    def current(self):
        """Return the current workspace handle."""
        handle = self._manager("get_current_workspace")()
        if handle is not None:
            _publish_runtime_object(getattr(handle, "name", ""), handle)
        return handle


class _WorkspaceDynamicAPI:
    """Base class for dynamic workspace action namespaces."""

    def __init__(self, workspace_api, manager_func_name):
        self._workspace_api = workspace_api
        self._manager_func_name = manager_func_name
        self._names = []
        self.refresh()

    def _make_loader(self, name):
        def loader():
            return self(name)

        return loader

    def refresh(self):
        for name in self._names:
            if hasattr(self, name):
                delattr(self, name)

        self._names = []

        try:
            names = self._workspace_api._manager("list_workspaces")()
        except Exception:
            return self

        if not isinstance(names, (list, tuple)):
            return self

        reserved = set(self.__dict__.keys())
        reserved.update(["refresh"])
        for name in names:
            if not _is_runtime_name(name):
                continue
            if name in reserved or name in self._names:
                continue
            setattr(self, name, self._make_loader(name))
            self._names.append(name)

        return self

    def __dir__(self):
        self.refresh()
        names = set(self.__dict__.keys())
        for name in self._names:
            names.add(name)
        result = list(names)
        result.sort()
        return result


class _WorkspaceSwitchAPI(_WorkspaceDynamicAPI):
    """Switch namespace exposed as ``mlx.workspace.switch``."""

    def __init__(self, workspace_api):
        _WorkspaceDynamicAPI.__init__(self, workspace_api, "open_workspace")

    def __call__(self, name):
        """Switch to a workspace by name and return its handle."""
        handle = self._workspace_api._manager(self._manager_func_name)(name)
        if handle is None:
            raise ValueError("Workspace '%s' does not exist. Create it first." % name)
        _publish_runtime_object(getattr(handle, "name", name), handle)
        self.refresh()
        self._workspace_api.remove.refresh()
        return handle


class _WorkspaceRemoveAPI(_WorkspaceDynamicAPI):
    """Removal namespace exposed as ``mlx.workspace.remove``."""

    def __init__(self, workspace_api):
        _WorkspaceDynamicAPI.__init__(self, workspace_api, "remove_workspace")

    def __call__(self, name):
        """Remove a workspace by name."""
        result = self._workspace_api._manager(self._manager_func_name)(name)
        if isinstance(result, dict) and result.get("success"):
            _remove_runtime_object(name)
        self._workspace_api.switch.refresh()
        self.refresh()
        return result


workspace = _WorkspaceAPI()
board = _BoardAPI()


__all__ = ["board", "workspace"]
