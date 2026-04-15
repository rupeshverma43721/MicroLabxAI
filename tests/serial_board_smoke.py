#!/usr/bin/env python3
"""Simple pyserial smoke test for mlx.board on a MicroPython device."""

import argparse
import json
import sys
import time

import serial


RAW_REPL_BANNER = b"raw REPL; CTRL-B to exit\r\n>"


class RawReplClient:
    """Minimal raw REPL client for MicroPython."""

    def __init__(self, port, baudrate, timeout):
        self.serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)

    def close(self):
        self.serial.close()

    def _read_until(self, marker, timeout=5.0):
        end_time = time.time() + timeout
        data = b""

        while time.time() < end_time:
            chunk = self.serial.read(1)
            if chunk:
                data += chunk
                if data.endswith(marker):
                    return data

        raise TimeoutError("Timed out waiting for %r. Received: %r" % (marker, data))

    def enter_raw_repl(self):
        self.serial.write(b"\r\x03\x03")
        time.sleep(0.2)
        self.serial.reset_input_buffer()
        self.serial.write(b"\r\x01")
        self._read_until(RAW_REPL_BANNER)

    def exit_raw_repl(self):
        self.serial.write(b"\x02")

    def exec(self, code):
        if isinstance(code, str):
            code = code.encode("utf-8")

        self.serial.reset_input_buffer()
        self.serial.write(code)
        self.serial.write(b"\x04")

        response = self._read_until(b"\x04", timeout=10.0)
        if not response.startswith(b"OK"):
            raise RuntimeError("Unexpected raw REPL response: %r" % response)
        stdout = response[2:-1]

        stderr = self._read_until(b"\x04", timeout=10.0)[:-1]
        self._read_until(b">", timeout=5.0)

        if stderr:
            raise RuntimeError(stderr.decode("utf-8", "replace"))

        return stdout.decode("utf-8", "replace")


def _load_statement(load_path):
    parts = [part for part in str(load_path).split(".") if part]
    if not parts:
        raise ValueError("Board load path is required.")

    expr = "mlx.board.load"
    for part in parts:
        expr += "." + part
    return expr + "()"


def run_smoke_test(port, baudrate, timeout, load_path):
    client = RawReplClient(port=port, baudrate=baudrate, timeout=timeout)
    try:
        client.enter_raw_repl()
        output = client.exec(
            "\n".join(
                [
                    "try:",
                    "    import ujson as json",
                    "except ImportError:",
                    "    import json",
                    "",
                    "import mlx",
                    _load_statement(load_path),
                    "result = {",
                    "    'current': mlx.board.current(),",
                    "    'boards': mlx.board.list(),",
                    "    'info': mlx.board.info(),",
                    "    'capabilities': mlx.board.capabilities(),",
                    "}",
                    "print(json.dumps(result))",
                ]
            )
        )
        return json.loads(output.strip())
    finally:
        try:
            client.exit_raw_repl()
        finally:
            client.close()


def main():
    parser = argparse.ArgumentParser(description="Read mlx.board info over pyserial.")
    parser.add_argument("--port", required=True, help="Serial port, e.g. /dev/ttyACM0")
    parser.add_argument(
        "--board",
        default="esp32.s3",
        help="Board load path, e.g. esp32.s3 or rp.rp2040",
    )
    parser.add_argument("--baudrate", type=int, default=115200, help="Serial baudrate")
    parser.add_argument("--timeout", type=float, default=1.0, help="Serial timeout in seconds")
    args = parser.parse_args()

    result = run_smoke_test(args.port, args.baudrate, args.timeout, args.board)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
