"""
workspace/handle.py
WorkspaceHandle provides the user-facing workspace module API.
"""

from core.registry import get_module_definition, list_supported_modules
from workspace import store as workspace_store


def _is_attr_name(value):
    """Return True when a value is safe to expose as a REPL attribute."""
    if not value:
        return False

    text = str(value)
    first = text[0]
    if first != "_" and not ("a" <= first <= "z" or "A" <= first <= "Z"):
        return False

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


def _coerce_field_value(field, value):
    """Convert a raw field value using the field metadata."""
    kind = str(field.get("kind", "str")).strip().lower()

    if kind == "int":
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return int(str(value), 0)

    if kind == "float":
        if isinstance(value, float):
            return value
        return float(value)

    if kind == "bool":
        if isinstance(value, bool):
            return value

        text = str(value).strip().lower()
        if text in ("1", "true", "yes", "y", "on"):
            return True
        if text in ("0", "false", "no", "n", "off"):
            return False
        raise ValueError("Expected true/false, yes/no, or 1/0.")

    if kind == "choice":
        choices = field.get("choices", [])
        if value in choices:
            return value

        text = str(value).strip()
        for choice in choices:
            if text == str(choice):
                return choice
            if isinstance(choice, str) and text.lower() == choice.lower():
                return choice

        raise ValueError("Choose one of: %s" % ", ".join(str(choice) for choice in choices))

    return value


def _prompt_field_value(field, current_config=None):
    """Prompt the user for one field value using field metadata."""
    key = field.get("key")
    label = field.get("label") or key or "Value"
    hint = field.get("hint")
    choices = field.get("choices", [])
    required = bool(field.get("required"))

    default = None
    if isinstance(current_config, dict) and key in current_config:
        default = current_config.get(key)
    elif "default" in field:
        default = field.get("default")

    if hint:
        print("%s: %s" % (label, hint))

    while True:
        prompt = label
        if choices:
            prompt += " [" + ", ".join(str(choice) for choice in choices) + "]"
        if default is not None:
            prompt += " <%s>" % default
        elif not required:
            prompt += " <skip>"
        prompt += ": "

        raw = input(prompt)
        if raw is None:
            raw = ""
        raw = str(raw).strip()

        if raw == "":
            if default is not None:
                return default
            if required:
                print("A value is required.")
                continue
            return None

        try:
            return _coerce_field_value(field, raw)
        except Exception as exc:
            print("Invalid value: %s" % exc)


class _WorkspaceModuleHandle:
    """User-facing handle for one persisted workspace module."""

    def __init__(self, workspace_handle, module_id):
        self.workspace = workspace_handle
        self.name = module_id

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

    def _entry(self):
        return self.workspace._module_entry(self.name)

    def setup(self, **kwargs):
        """Configure this module, prompting when no setup arguments are passed."""
        module_id, entry = self._entry()
        definition = self.workspace._definition_for_entry(entry)
        module_class = definition.get("handler_class")

        config = dict(kwargs)
        if not config:
            config = self.workspace._prompt_fields(
                getattr(module_class, "SETUP_FIELDS", []),
                entry.get("config", {}),
            )

        result = self.workspace.setup(module_id, **config)
        if not result.get("success"):
            raise ValueError(result.get("error"))
        return self.info()

    def get(self, **kwargs):
        """Read data from this module."""
        result = self.workspace.get(self.name, **kwargs)
        if not result.get("success"):
            raise ValueError(result.get("error"))
        return result.get("data")

    def set(self, **kwargs):
        """Update this module, prompting when no runtime arguments are passed."""
        module_id, entry = self._entry()
        definition = self.workspace._definition_for_entry(entry)
        module_class = definition.get("handler_class")

        updates = dict(kwargs)
        if not updates:
            updates = self.workspace._prompt_fields(
                getattr(module_class, "SET_FIELDS", []),
                entry.get("config", {}),
            )

        result = self.workspace.set(module_id, **updates)
        if not result.get("success"):
            raise ValueError(result.get("error"))
        return result.get("result")

    def info(self):
        """Return module metadata, saved config, and available fields."""
        module_id, entry = self._entry()
        definition = self.workspace._definition_for_entry(entry)
        module_class = definition.get("handler_class")

        return {
            "workspace": self.workspace.name,
            "id": module_id,
            "type": entry.get("type"),
            "protocol": entry.get("protocol"),
            "configured": bool(entry.get("configured")),
            "config": dict(entry.get("config", {})),
            "description": getattr(module_class, "DESCRIPTION", ""),
            "setup_fields": getattr(module_class, "SETUP_FIELDS", []),
            "read_fields": getattr(module_class, "READ_FIELDS", []),
            "set_fields": getattr(module_class, "SET_FIELDS", []),
        }


class _WorkspaceAddProtocolAPI:
    """Protocol namespace exposed as ``lab.add.<protocol>``."""

    def __init__(self, workspace_handle, protocol_name, definitions):
        self._workspace = workspace_handle
        self._protocol_name = protocol_name
        self._names = []
        self._refresh(definitions)

    def _make_loader(self, definition):
        module_type = definition.get("type")
        module_label = definition.get("handler") or definition.get("type")

        def loader(name=None, **kwargs):
            module_name = name

            if "name" in kwargs:
                if module_name is not None:
                    raise TypeError("Module name was provided more than once.")
                module_name = kwargs.pop("name")

            if kwargs:
                raise TypeError(
                    "Add only creates the module. Use %s.setup(...) after add." % module_label
                )

            return self._workspace._add_module(module_type, module_name)

        return loader

    def _definition_names(self, definition):
        values = []
        handler = definition.get("handler")
        module_type = definition.get("type")

        if handler:
            values.append(str(handler))
        if module_type:
            values.append(str(module_type).strip().lower())

        names = []
        for value in values:
            if not _is_attr_name(value):
                continue
            if value in names:
                continue
            names.append(value)
        return names

    def _refresh(self, definitions):
        for name in self._names:
            if name in self.__dict__:
                delattr(self, name)

        self._names = []

        for definition in definitions:
            for name in self._definition_names(definition):
                if name in self._names:
                    continue
                setattr(self, name, self._make_loader(definition))
                self._names.append(name)

        return self

    def __dir__(self):
        result = list(self._names)
        result.sort()
        return result


class _WorkspaceAddAPI:
    """Dynamic add namespace exposed as ``lab.add``."""

    def __init__(self, workspace_handle):
        self._workspace = workspace_handle
        self._protocols = []
        self._refresh()

    def __call__(self, module_type, name=None):
        """Add a module by type and return its module handle."""
        return self._workspace._add_module(module_type, name)

    def _refresh(self):
        for protocol in self._protocols:
            if protocol in self.__dict__:
                delattr(self, protocol)

        self._protocols = []

        groups = {}
        for definition in self._workspace._supported_module_definitions():
            protocol = str(definition.get("protocol", "")).strip().lower()
            if not _is_attr_name(protocol):
                continue
            if protocol not in groups:
                groups[protocol] = []
            groups[protocol].append(definition)

        protocol_names = list(groups.keys())
        protocol_names.sort()
        for protocol in protocol_names:
            setattr(
                self,
                protocol,
                _WorkspaceAddProtocolAPI(self._workspace, protocol, groups[protocol]),
            )
            self._protocols.append(protocol)

        return self

    def __dir__(self):
        result = list(self._protocols)
        result.sort()
        return result

    def __getattr__(self, name):
        self._refresh()
        if name in self.__dict__:
            return self.__dict__[name]
        raise AttributeError(name)


class _WorkspaceListAPI:
    """Dynamic module list namespace exposed as ``lab.list``."""

    def __init__(self, workspace_handle):
        self._workspace = workspace_handle
        self._names = []
        self._refresh()

    def __call__(self):
        """Return a lightweight summary of the modules in this workspace."""
        modules = []
        for entry in self._workspace.config.get("modules", {}).values():
            modules.append(
                {
                    "name": entry.get("type"),
                    "id": entry.get("id"),
                    "protocol_group": entry.get("protocol"),
                    "qty": 1,
                }
            )

        modules.sort(key=lambda item: item.get("id", ""))
        return {
            "success": True,
            "workspace_name": self._workspace.name,
            "modules": modules,
        }

    def _make_loader(self, module_id):
        def loader():
            return self._workspace._module_handle(module_id)

        return loader

    def _refresh(self):
        for name in self._names:
            if name in self.__dict__:
                delattr(self, name)

        self._names = []

        module_ids = list(self._workspace.config.get("modules", {}).keys())
        module_ids.sort()

        for module_id in module_ids:
            if not _is_attr_name(module_id):
                continue
            if module_id in self._names:
                continue
            setattr(self, module_id, self._make_loader(module_id))
            self._names.append(module_id)

        return self

    def __dir__(self):
        result = list(self._names)
        result.sort()
        return result

    def __getattr__(self, name):
        self._refresh()
        if name in self.__dict__:
            return self.__dict__[name]
        raise AttributeError(name)


class WorkspaceHandle:
    """Represents one persisted workspace."""

    def __init__(self, name, config=None):
        self.name = name
        self.config = config or {"name": name, "modules": {}}
        if "modules" not in self.config or not isinstance(self.config["modules"], dict):
            self.config["modules"] = {}
        self._drivers = {}
        self.add = _WorkspaceAddAPI(self)
        self.list = _WorkspaceListAPI(self)

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

    def _save(self):
        workspace_store.save_workspace_config(self.name, self.config)

    def _next_alias(self, module_type):
        base = str(module_type).strip().lower()
        index = 1
        while True:
            alias = "%s_%d" % (base, index)
            if alias not in self.config["modules"]:
                return alias
            index += 1

    def _resolve_module_id(self, module_ref):
        if module_ref in self.config["modules"]:
            return module_ref

        matches = []
        requested = str(module_ref).strip().upper()
        for module_id, entry in self.config["modules"].items():
            if str(entry.get("type", "")).strip().upper() == requested:
                matches.append(module_id)

        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                "Multiple modules of type '%s' exist. Use the module id instead." % module_ref
            )
        raise KeyError("Module '%s' is not present in workspace '%s'." % (module_ref, self.name))

    def _module_entry(self, module_ref):
        module_id = self._resolve_module_id(module_ref)
        return module_id, self.config["modules"][module_id]

    def _module_handle(self, module_id):
        return _WorkspaceModuleHandle(self, module_id)

    def _definition_for_entry(self, entry):
        definition = get_module_definition(entry.get("type"))
        if not definition:
            raise ValueError("Module type '%s' is not available in registry." % entry.get("type"))
        return definition

    def _default_setup_config(self, module_class):
        config = {}
        for field in getattr(module_class, "SETUP_FIELDS", []):
            key = field.get("key")
            if key and "default" in field:
                config[key] = field.get("default")
        return config

    def _prompt_fields(self, fields, current_config=None):
        values = {}
        for field in fields:
            key = field.get("key")
            if not key:
                continue

            value = _prompt_field_value(field, current_config)
            if value is None:
                continue
            values[key] = value
        return values

    def _supported_module_definitions(self):
        definitions = []
        for module_type in list_supported_modules():
            definition = get_module_definition(module_type)
            if definition:
                definitions.append(definition)

        definitions.sort(
            key=lambda item: (
                str(item.get("protocol", "")),
                str(item.get("handler") or item.get("type") or ""),
            )
        )
        return definitions

    def _ensure_board_loaded(self):
        try:
            import core.board as board_core
        except ImportError:
            board_core = None

        active_board = None
        if board_core is not None:
            try:
                active_board = board_core.get_active_board()
            except Exception:
                active_board = None

        if not active_board:
            raise ValueError("No board loaded. Use mlx.board.load.<family>.<series>() first.")

        return active_board

    def _ensure_driver(self, module_ref):
        module_id, entry = self._module_entry(module_ref)
        if module_id in self._drivers:
            definition = self._definition_for_entry(entry)
            return module_id, entry, definition, self._drivers[module_id]

        if not entry.get("configured"):
            raise ValueError("Module '%s' is not configured yet." % module_id)

        definition = self._definition_for_entry(entry)
        module_class = definition.get("handler_class")
        driver = module_class.setup(dict(entry.get("config", {})))
        self._drivers[module_id] = driver
        return module_id, entry, definition, driver

    def _add_module(self, module_type, name=None):
        """Add a supported module and return its module handle."""
        definition = get_module_definition(module_type)
        if not definition:
            raise ValueError("Module '%s' not found in registry." % module_type)

        self._ensure_board_loaded()

        supported = list_supported_modules()
        if definition.get("type") not in supported:
            raise ValueError(
                "Module '%s' is not supported by the currently loaded board." % module_type
            )

        module_id = name or self._next_alias(definition["type"])
        if module_id in self.config["modules"]:
            raise ValueError("Module id '%s' already exists." % module_id)

        module_entry = {
            "id": module_id,
            "type": definition["type"],
            "protocol": definition.get("protocol"),
            "configured": False,
            "config": {},
        }
        self.config["modules"][module_id] = module_entry
        self._save()
        self.add._refresh()
        self.list._refresh()
        return self._module_handle(module_id)

    def setup(self, module_ref, **kwargs):
        """Configure a workspace module and create its runtime driver."""
        try:
            module_id, entry = self._module_entry(module_ref)
            definition = self._definition_for_entry(entry)
            module_class = definition.get("handler_class")
            config = self._default_setup_config(module_class)
            config.update(entry.get("config", {}))
            config.update(kwargs)

            old_driver = self._drivers.get(module_id)
            if old_driver and hasattr(old_driver, "deinit"):
                old_driver.deinit()

            driver = module_class.setup(config)
            entry["config"] = config
            entry["configured"] = True
            self._drivers[module_id] = driver
            self._save()
            return {"success": True, "module": entry}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def get(self, module_ref, **kwargs):
        """Read data from a configured module."""
        module_id = None
        try:
            module_id, entry, definition, driver = self._ensure_driver(module_ref)
            module_class = definition.get("handler_class")
            payload = module_class.get(driver, kwargs or None)
            return {
                "success": True,
                "module": module_id,
                "type": entry.get("type"),
                "data": payload,
            }
        except Exception as exc:
            return {
                "success": False,
                "module": module_id or str(module_ref),
                "error": str(exc),
            }

    def set(self, module_ref, **kwargs):
        """Update runtime settings for a configured module."""
        module_id = None
        try:
            module_id, entry, definition, driver = self._ensure_driver(module_ref)
            module_class = definition.get("handler_class")
            result = module_class.set(driver, kwargs)
            entry["config"].update(kwargs)
            self._save()
            return {
                "success": True,
                "module": module_id,
                "type": entry.get("type"),
                "result": result,
            }
        except Exception as exc:
            return {
                "success": False,
                "module": module_id or str(module_ref),
                "error": str(exc),
            }
