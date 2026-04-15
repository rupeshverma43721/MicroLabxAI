"""
Device-side workspace flow smoke test for MicroLabxAI.

Run on the board terminal:

    import tests.serial_workspace_flow as test_flow
    test_flow.run_workspace_flow_test()

Or execute the file directly on the device if your workflow supports it.
"""

try:
    import ujson as json
except ImportError:
    import json

import sys


DEFAULT_BOARD = "esp32.s3"
DEFAULT_WORKSPACE = "serial_workspace_flow"
DEFAULT_I2C_BUS = 0
DEFAULT_SCL = 16
DEFAULT_SDA = 2
DEFAULT_ADDRESS = 0x48
DEFAULT_GAIN = "4.096V"
DEFAULT_DATA_RATE = 250


def _load_board(load_path):
    import mlx

    parts = [part for part in str(load_path).split(".") if part]
    if not parts:
        raise ValueError("Board load path is required.")

    loader = mlx.board.load
    for part in parts:
        loader = getattr(loader, part)
    return loader()


def _clear_runtime_modules():
    names = [
        "mlx",
        "workspace.handle",
        "workspace.manager",
        "workspace.store",
        "core.registry",
        "modules.ads1115",
    ]

    for name in names:
        try:
            del sys.modules[name]
        except KeyError:
            pass


def run_workspace_flow_test(
    board=DEFAULT_BOARD,
    workspace_name=DEFAULT_WORKSPACE,
    i2c_bus=DEFAULT_I2C_BUS,
    scl=DEFAULT_SCL,
    sda=DEFAULT_SDA,
    address=DEFAULT_ADDRESS,
    gain=DEFAULT_GAIN,
    data_rate=DEFAULT_DATA_RATE,
    cleanup=True,
    fresh_imports=True,
):
    """
    Run the full workspace flow directly on the device.

    Returns a result dictionary and also prints it as JSON.
    """
    if fresh_imports:
        _clear_runtime_modules()

    import mlx

    _load_board(board)

    try:
        mlx.workspace.remove(workspace_name)
    except Exception:
        pass

    lab = mlx.workspace.create(workspace_name)
    adc = lab.add.i2c.ads1115()
    setup = adc.setup(i2c_bus=i2c_bus, scl=scl, sda=sda, address=address)
    summary = lab.list()
    lookup = lab.list.ads1115_1()
    single = lookup.get(channel="A0")
    all_data = lookup.get()
    updated = lookup.set(gain=gain, data_rate=data_rate)
    info = lookup.info()

    result = {
        "workspace": repr(lab),
        "adc": repr(adc),
        "setup": setup,
        "summary": summary,
        "lookup": repr(lookup),
        "single": single,
        "all_data": all_data,
        "updated": updated,
        "info": info,
    }

    if cleanup:
        result["cleanup"] = mlx.workspace.remove(workspace_name)

    print(json.dumps(result))
    return result


if __name__ == "__main__":
    run_workspace_flow_test()
