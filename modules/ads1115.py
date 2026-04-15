"""
modules/ads1115.py
ADS1115 Module - Clean, final version
Follows BaseModule contract with rich AI-friendly hints
"""

from core.base import BaseModule


class Module(BaseModule):
    TYPE = "ADS1115"
    PROTOCOL = "i2c"
    DESCRIPTION = "Texas Instruments 16-bit 4-channel I2C Analog-to-Digital Converter (ADC)"

    SETUP_FIELDS = [
        {
            "key": "i2c_bus",
            "label": "I2C Bus",
            "kind": "int",
            "required": False,
            "default": 0,
            "hint": "I2C bus number on the current board. Usually auto-filled from board defaults."
        },
        {
            "key": "scl",
            "label": "SCL Pin",
            "kind": "int",
            "required": False,
            "default": 16,
            "hint": "I2C clock pin. Should normally come from the loaded board profile."
        },
        {
            "key": "sda",
            "label": "SDA Pin",
            "kind": "int",
            "required": False,
            "default": 2,
            "hint": "I2C data pin. Should normally come from the loaded board profile."
        },
        {
            "key": "freq",
            "label": "I2C Frequency",
            "kind": "int",
            "required": False,
            "default": 400000,
            "hint": "I2C bus frequency in Hz. Usually 100000 or 400000."
        },
        {
            "key": "address",
            "label": "I2C Address",
            "kind": "int",
            "required": True,
            "default": 0x48,
            "hint": "I2C address of the ADS1115. Common values: 0x48 (ADDR=GND), 0x49 (ADDR=VDD), 0x4A, 0x4B."
        },
        {
            "key": "gain",
            "label": "Gain Range",
            "kind": "choice",
            "required": True,
            "default": "2.048V",
            "choices": ["6.144V", "4.096V", "2.048V", "1.024V", "0.512V", "0.256V"],
            "hint": "Full-scale voltage range. Higher gain = better resolution but smaller measurable voltage."
        },
        {
            "key": "data_rate",
            "label": "Data Rate (SPS)",
            "kind": "choice",
            "required": True,
            "default": 128,
            "choices": [8, 16, 32, 64, 128, 250, 475, 860],
            "hint": "Samples per second. Higher value = faster readings but slightly more noise."
        }
    ]

    READ_FIELDS = [
        {
            "key": "channel",
            "label": "Channel",
            "kind": "choice",
            "required": False,
            "default": None,
            "choices": ["A0", "A1", "A2", "A3"],
            "hint": "If omitted, all four channels are read."
        }
    ]

    SET_FIELDS = [
        {
            "key": "gain",
            "label": "Gain Range",
            "kind": "choice",
            "required": False,
            "choices": ["6.144V", "4.096V", "2.048V", "1.024V", "0.512V", "0.256V"],
            "hint": "Change full-scale range at runtime."
        },
        {
            "key": "data_rate",
            "label": "Data Rate",
            "kind": "choice",
            "required": False,
            "choices": [8, 16, 32, 64, 128, 250, 475, 860],
            "hint": "Change ADC sample rate at runtime."
        }
    ]

    @classmethod
    def setup(cls, config):
        """Create and return the low-level ADS1115 driver."""
        from drivers.i2c.ads1115 import ADS1115Driver

        merged = {
            "i2c_bus": config.get("i2c_bus", 0),
            "scl": config.get("scl", 16),
            "sda": config.get("sda", 2),
            "freq": config.get("freq", 400000),
            "address": config.get("address", 0x48),
            "gain": config.get("gain", "2.048V"),
            "data_rate": config.get("data_rate", 128),
        }
        return ADS1115Driver(**merged)

    @classmethod
    def get(cls, driver, options=None):
        """Read data from ADS1115."""
        options = options or {}
        channel = cls._normalize_channel(options.get("channel"))
        if channel is not None:
            voltage = driver.read_single(channel)
            return {
                "channel": "A%d" % channel,
                "value": round(voltage, 4),
                "unit": "V",
            }

        return {
            "channels": {"A%d" % i: round(driver.read_single(i), 4) for i in range(4)},
            "unit": "V",
        }

    @classmethod
    def set(cls, driver, updates):
        """Change runtime settings."""
        changed = {}
        if "gain" in updates:
            driver.set_gain(updates["gain"])
            changed["gain"] = updates["gain"]
        if "data_rate" in updates:
            driver.set_data_rate(updates["data_rate"])
            changed["data_rate"] = updates["data_rate"]
        return {"updated": changed}

    @staticmethod
    def _normalize_channel(channel):
        if channel is None:
            return None

        if isinstance(channel, int):
            if 0 <= channel <= 3:
                return channel
            raise ValueError("Channel integer must be between 0 and 3.")

        text = str(channel).strip().upper()
        if len(text) == 2 and text[0] == "A" and text[1] in "0123":
            return int(text[1])

        raise ValueError("Channel must be A0, A1, A2, A3, or an integer 0-3.")
