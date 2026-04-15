# MicroLabxAI Docs

MicroLabxAI is a MicroPython runtime for board-aware hardware modules.

The current runtime is built around three ideas:

- select a board first
- expose only the modules supported by that board
- manage module instances inside named workspaces

## 1. Quick Start

Typical REPL flow:

```python
import mlx

mlx.board.list()
mlx.board.load.esp32.s3()
mlx.board.current()
mlx.board.info()
mlx.board.capabilities()

mlx.workspace.create("lab")
lab

adc = lab.add.i2c.ads1115()
adc.setup()
adc.get()
adc.get(channel="A0")
adc.set()
adc.info()
```

## 2. Public API

Current top-level public API:

- `mlx.board`
- `mlx.workspace`

Current board commands:

- `mlx.board.list()`
- `mlx.board.current()`
- `mlx.board.info()`
- `mlx.board.capabilities()`
- `mlx.board.load.<family>.<series>()`

Current workspace commands:

- `mlx.workspace.create(name)`
- `mlx.workspace.list()`
- `mlx.workspace.current()`
- `mlx.workspace.switch(name)`
- `mlx.workspace.switch.<workspace_name>()`
- `mlx.workspace.remove(name)`
- `mlx.workspace.remove.<workspace_name>()`

## 3. Board Commands

Board selection is explicit.

Example:

```python
import mlx

mlx.board.list()
mlx.board.load.esp32.s3()
mlx.board.current()
mlx.board.info()
mlx.board.capabilities()
```

Current board loader shape is family-first:

- `mlx.board.load.esp32.s3()`
- `mlx.board.load.rp.rp2040()`
- `mlx.board.load.stm32.f401()`

This is intentionally shorter and more REPL-friendly than long string ids.

## 4. Workspace Commands

Create a workspace:

```python
mlx.workspace.create("lab")
```

This returns the workspace handle and also exposes the same name in the REPL:

```python
lab
mlx.workspace.current()
```

List available workspaces:

```python
mlx.workspace.list()
```

Switch workspaces:

```python
mlx.workspace.switch("lab")
mlx.workspace.switch.lab()
```

Remove workspaces:

```python
mlx.workspace.remove("lab")
mlx.workspace.remove.lab()
```

## 5. Module Lifecycle

The module workflow is:

1. load a board
2. create or switch to a workspace
3. add a module to that workspace
4. run `setup()`
5. use `get()`, `set()`, and `info()`

Recommended add flow:

```python
adc = lab.add.i2c.ads1115()
```

This creates a module entry in the workspace and returns a module handle such as:

```python
ads1115_1
```

Then configure it:

```python
adc.setup()
```

Or pass setup values directly:

```python
adc.setup(i2c_bus=0, scl=16, sda=2, address=0x48)
```

Read values:

```python
adc.get()
adc.get(channel="A0")
```

Update runtime settings:

```python
adc.set()
adc.set(gain="4.096V", data_rate=250)
```

Inspect saved metadata:

```python
adc.info()
```

## 6. Interactive Behavior

MicroLabxAI is designed for both humans and AI.

Human-friendly behavior:

- `adc.setup()` with no arguments prompts from `SETUP_FIELDS`
- `adc.set()` with no arguments prompts from `SET_FIELDS`

Automation-friendly behavior:

- `adc.setup(...)` accepts explicit keyword arguments
- `adc.get(...)` accepts targeted read arguments
- `adc.set(...)` accepts explicit update arguments

This means the same API works for:

- REPL use
- scripts
- AI agents

## 7. Workspace Module Lookup

To see what belongs to a workspace:

```python
lab.list()
```

Current summary shape:

```python
{
    "success": True,
    "workspace_name": "lab",
    "modules": [
        {
            "name": "ADS1115",
            "id": "ads1115_1",
            "protocol_group": "i2c",
            "qty": 1
        }
    ]
}
```

To get a specific module handle back from the workspace:

```python
lab.list.ads1115_1()
```

That returned handle supports the same module methods:

```python
lab.list.ads1115_1().setup()
lab.list.ads1115_1().get()
lab.list.ads1115_1().set()
lab.list.ads1115_1().info()
```

This makes it clear which workspace a module belongs to.

## 8. Example ADS1115 Session

```python
import mlx

mlx.board.load.esp32.s3()
mlx.workspace.create("lab")

adc = lab.add.i2c.ads1115()
adc.setup(i2c_bus=0, scl=16, sda=2, address=0x48)

adc.get()
adc.get(channel="A0")
adc.set(gain="4.096V", data_rate=250)
adc.info()

lab.list()
lab.list.ads1115_1().get(channel="A0")
```

## 9. Current Device Test

There is a device-side workspace flow test at:

- `tests/serial_workspace_flow.py`

Run it on the board terminal:

```python
import tests.serial_workspace_flow as test_flow
test_flow.run_workspace_flow_test()
```

This test covers:

- board load
- workspace creation
- `lab.add.i2c.ads1115()`
- `setup()`
- `lab.list()`
- `lab.list.ads1115_1()`
- `get()`
- `set()`
- `info()`

## 10. Repository Layout

Current top-level layout:

- `mlx.py`
- `core/`
- `modules/`
- `drivers/`
- `workspace/`
- `platforms/boards/`
- `tests/`

Purpose of each:

- `mlx.py` exposes the public REPL API
- `core/` contains board loading, registry logic, and base abstractions
- `modules/` contains runtime-facing hardware modules
- `drivers/` contains low-level protocol drivers
- `workspace/` contains workspace lifecycle and persistence logic
- `platforms/boards/` contains board metadata
- `tests/` contains validation helpers and smoke tests

## 11. Metadata Model

Board metadata is split into:

- `platforms/boards/<board_id>/info.json`
- `platforms/boards/<board_id>/capabilities.json`

Module metadata is split into:

- `modules/_registry.json`
- `modules/_protocol_map.json`

Rules:

- `info.json` identifies the board
- `capabilities.json` describes what the board can do
- `_registry.json` declares all known modules
- board capabilities decide which modules are actually available

## 12. Current Status

Implemented and validated so far:

- family-first board loading
- board capability loading
- board-aware module filtering
- REPL-friendly workspace API
- dynamic workspace switching and removal
- dynamic `lab.add.<protocol>.<module>()`
- module handles with `setup()`, `get()`, `set()`, `info()`
- workspace lookup via `lab.list.<module_id>()`
- live ADS1115 validation on ESP32-S3

Current example board:

- `esp32_s3_wroom_1_n16r8`

Current example module:

- `ADS1115`

## 13. Design Rules

- board must be loaded before modules are added
- module registry is global, support is board-specific
- public commands should be short and REPL-friendly
- workspaces own module instances
- module handles should work equally well for humans and AI
- runtime code must stay MicroPython-safe
