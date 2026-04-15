"""
Core registry for globally available modules.
Provides raw and board-filtered module listings.
"""

try:
    import ujson as json
except ImportError:
    import json


def _dirname(path):
    text = str(path).rstrip("/")
    if "/" not in text:
        return ""
    return text.rsplit("/", 1)[0]


def _join_path(*parts):
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


_THIS_FILE = globals().get("__file__", "core/registry.py")
_THIS_DIR = _dirname(_THIS_FILE)
_PROJECT_ROOT = _dirname(_THIS_DIR)
REGISTRY_PATH = _join_path(_PROJECT_ROOT, "modules", "_registry.json")


def _load_registry():
    try:
        with open(REGISTRY_PATH, "r") as handle:
            data = json.load(handle)
    except Exception:
        return {"modules": []}

    if not isinstance(data, dict):
        return {"modules": []}
    if "modules" not in data or not isinstance(data["modules"], list):
        return {"modules": []}
    return data


def _module_matches(module_type, record):
    name = str(module_type or "").strip().upper()
    return name and name == str(record.get("type", "")).strip().upper()


def _load_module_class(handler_name):
    module_path = "modules." + str(handler_name)
    module = __import__(module_path, None, None, ("Module",))
    handler_class = getattr(module, "Module", None)
    if handler_class is None:
        raise AttributeError("Module class not found in %s" % module_path)
    return handler_class


def _protocol_supported(protocol_name, capabilities):
    if not protocol_name or not isinstance(capabilities, dict):
        return False

    protocol = str(protocol_name).lower()

    if protocol == "gpio":
        return bool(capabilities.get("gpio"))

    if protocol in ("i2c", "spi", "uart"):
        section = capabilities.get("peripherals", {}).get(protocol, {})
        if isinstance(section, dict):
            return section.get("count", 0) > 0
        return bool(section)

    if protocol == "network":
        wireless = capabilities.get("wireless", {})
        if not isinstance(wireless, dict):
            return False

        wifi = wireless.get("wifi", {})
        ble = wireless.get("ble", {})
        classic = wireless.get("bluetooth_classic", False)

        wifi_ok = bool(wifi.get("supported")) if isinstance(wifi, dict) else bool(wifi)
        ble_ok = bool(ble.get("supported")) if isinstance(ble, dict) else bool(ble)
        return wifi_ok or ble_ok or bool(classic)

    if protocol == "usb":
        return bool(capabilities.get("usb"))

    return False


def list_all_modules():
    """Return every module listed in modules/_registry.json."""
    data = _load_registry()
    names = []

    for module in data.get("modules", []):
        module_type = module.get("type")
        if module_type:
            names.append(module_type)

    return names


def list_supported_modules():
    """Return only modules supported by the active board capabilities."""
    try:
        import core.board as board_core
    except ImportError:
        return []

    try:
        capabilities = board_core.get_capabilities()
    except Exception:
        return []

    supported = []
    for module in _load_registry().get("modules", []):
        module_type = module.get("type")
        protocol = module.get("protocol")

        if not module_type:
            continue
        if _protocol_supported(protocol, capabilities):
            supported.append(module_type)

    return supported


def get_module_definition(module_type):
    """
    Internal helper used by the workspace layer.
    Returns the module record plus its runtime class.
    """
    for record in _load_registry().get("modules", []):
        if not _module_matches(module_type, record):
            continue

        result = dict(record)
        handler_name = result.get("handler")
        if handler_name:
            result["handler_class"] = _load_module_class(handler_name)
        return result

    return None


__all__ = ["list_all_modules", "list_supported_modules"]
