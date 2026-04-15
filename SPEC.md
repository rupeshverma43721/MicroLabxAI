# MicroLabxAI Specification

## 1. Goal

MicroLabxAI is a device-side runtime for board-aware hardware modules.

The core idea is:

- `mlx.py` is the public REPL-facing API.
- board selection happens first
- board capabilities define what the runtime can expose
- module availability is filtered by the currently loaded board
- workspace state is managed separately from board and module metadata

This document captures the design decisions made so far and the current implementation state.

## 2. Current Repository Shape

Current top-level runtime layout:

- `mlx.py`
- `core/`
- `modules/`
- `drivers/`
- `workspace/`
- `platforms/boards/`
- `tests/`

Layer intent:

- `mlx.py` exposes the public API used from REPL or host tooling.
- `core/` contains board loading, registry logic, and base abstractions.
- `modules/` contains high-level device modules plus shared JSON metadata.
- `drivers/` contains low-level protocol drivers.
- `workspace/` contains workspace lifecycle and persistence logic.
- `platforms/boards/` contains board-specific metadata.

## 3. Public API

The public API is intentionally small and namespace-based.

Current public exports from `mlx.py`:

- `mlx.board`
- `mlx.workspace`

Current board API:

- `mlx.board.list()`
- `mlx.board.current()`
- `mlx.board.info()`
- `mlx.board.capabilities()`
- `mlx.board.load.<family>.<series>()`

Current workspace API:

- `mlx.workspace.create(name)`
- `mlx.workspace.list()`
- `mlx.workspace.open(name)`
- `mlx.workspace.remove(name)`
- `mlx.workspace.current()`

Design rules:

- no broad top-level function soup in `mlx.py`
- board operations live under `mlx.board`
- workspace operations live under `mlx.workspace`
- REPL commands should be short and typo-resistant

## 4. Board Loading Model

Board selection is explicit. There is no permanent hardcoded default board in the runtime model.

Expected user flow:

```python
import mlx

mlx.board.list()
mlx.board.load.esp32.s3()
mlx.board.current()
mlx.board.info()
mlx.board.capabilities()
```

The load namespace is family-first:

- `mlx.board.load.esp32.s3()`
- `mlx.board.load.rp.rp2040()`
- `mlx.board.load.stm32.f401()`

Reason for this model:

- better REPL ergonomics than string-based load calls
- tab completion can expose families first, then series
- avoids errors from long raw board ids such as `esp32_s3_wroom_1_n16r8`

## 5. Board Metadata Model

Each board lives under:

`platforms/boards/<board_id>/`

Each board currently uses two JSON files:

- `info.json`
- `capabilities.json`

### 5.1 `info.json`

`info.json` is intentionally minimal. It contains identity and routing metadata, not detailed hardware data.

Current intent:

- `id`
- `name`
- `vendor`
- `family`
- `series`
- `soc`
- `module`
- `aliases`
- `runtime`
- `files.capabilities`

Example meaning:

- `family` drives the first level of `mlx.board.load`
- `series` drives the second level of `mlx.board.load.<family>.<series>()`
- `aliases` allow compatibility names and alternate lookup

### 5.2 `capabilities.json`

`capabilities.json` contains the detailed hardware capability map for the selected board.

Current capability categories used in the runtime:

- `module`
- `cpu`
- `memory`
- `wireless`
- `usb`
- `gpio`
- `analog`
- `peripherals`
- `security`
- `power`
- `ai`
- `runtime`

Design rule:

- `info.json` answers "what board is this?"
- `capabilities.json` answers "what can this board do?"

## 6. Current Boards

Current board folders:

- `esp32_s3_wroom_1_n16r8`
- `rp2040`
- `stm32_f401`

Current family/series mapping:

- `esp32` -> `s3`
- `rp` -> `rp2040`
- `stm32` -> `f401`

The ESP32-S3 profile is currently the most complete one and includes richer capability detail.

## 7. Core Board Responsibilities

`core/board.py` currently owns:

- board discovery
- board existence checks
- board selection
- board alias resolution
- loading `info.json`
- loading `capabilities.json`
- returning current board info
- returning current board capabilities
- simple feature checks via `has(feature)`

Important behavior:

- if no board is loaded, board-specific reads should fail clearly
- board resolution may use canonical ids or aliases
- MicroPython-safe string handling is required throughout

## 8. Module Registry Model

There is one global module registry file:

- `modules/_registry.json`

There is one global protocol defaults file:

- `modules/_protocol_map.json`

This was a deliberate design choice.

Rejected direction:

- one JSON file per protocol

Chosen direction:

- one module registry for all known modules
- one protocol map for shared protocol defaults
- board capabilities decide which registered modules are usable

## 9. Registry API

`core/registry.py` currently exposes only:

- `list_all_modules()`
- `list_supported_modules()`

Expected behavior:

- `list_all_modules()` returns every module declared in `_registry.json`
- `list_supported_modules()` filters that list using the currently loaded board capabilities

Current filtering rule is protocol-driven:

- `gpio` modules depend on GPIO support
- `i2c`, `spi`, and `uart` modules depend on `capabilities.peripherals`
- `network` modules depend on wireless support
- `usb` modules depend on USB support

Design rule:

- registry is global
- support is board-specific

## 10. Protocol Map Role

`modules/_protocol_map.json` is not a second registry.

Its role is:

- shared defaults per protocol
- protocol descriptions
- reusable hints for setup and configuration

This file should not determine module visibility by itself.

Module visibility belongs to:

- `_registry.json` for declared modules
- `core/registry.py` for board-aware filtering
- `core/board.py` for actual capability data

## 11. Module and Driver Split

Current intended separation:

- `modules/` = user-facing high-level abstractions
- `drivers/` = low-level hardware protocol access

Example:

- `modules/ads1115.py` is the runtime-facing module
- `drivers/i2c/ads1115.py` is the low-level bus driver

Design rule:

- modules should depend on drivers
- drivers should not depend on workspace
- board capability checks happen before exposing unsupported modules

## 12. Workspace Direction

Workspace APIs are already reserved in `mlx.py`, but the detailed workspace implementation is still behind the board and registry work.

Current intended responsibility split:

- `workspace/handle.py` for active workspace interaction
- `workspace/manager.py` for create/list/open/remove/current
- `workspace/store.py` for persistent `.mlx/` storage

At this stage, the public workspace API shape is defined even if implementation depth is still limited.

## 13. Architecture Summary

Current runtime flow:

1. user imports `mlx`
2. user selects a board through `mlx.board.load.<family>.<series>()`
3. `core.board` loads `info.json` and `capabilities.json`
4. `core.registry` filters modules using current board capabilities
5. user interacts with supported modules and workspaces through the public API

This means board selection is now the first-class runtime decision that controls the visible hardware surface.

## 14. Current Status

Implemented so far:

- repo structure aligned to the new top-level layout
- board namespace in `mlx.py`
- workspace namespace in `mlx.py`
- family-first board loader design
- split board metadata into `info.json` and `capabilities.json`
- detailed ESP32-S3 capabilities profile
- global registry plus board-aware supported-module filtering
- MicroPython-safe replacements for incompatible string handling

Known gaps:

- `architecture.mmd` still reflects older path names and should be updated later
- workspace internals are not fully implemented yet
- more module definitions still need to be added to `_registry.json`
- non-ESP32 board capability files are still placeholder-level compared to ESP32-S3
- live device validation depends on the current board filesystem being in sync with the local source tree

## 15. Guiding Principles

- board identity and board capability data stay separate
- public API stays small and REPL-friendly
- module discovery is global, module support is board-dependent
- family-first board selection is preferred over long string arguments
- MicroPython compatibility is a hard requirement for runtime code
