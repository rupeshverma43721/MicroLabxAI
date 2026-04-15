"""
drivers/i2c/ads1115.py
Complete, production-ready low-level driver for ADS1115 16-bit I2C ADC
"""

from machine import I2C, Pin


class ADS1115Driver:
    """Full-featured ADS1115 driver."""

    # I2C Addresses
    ADDR_GND = 0x48
    ADDR_VDD = 0x49
    ADDR_SDA = 0x4A
    ADDR_SCL = 0x4B

    # Registers
    REG_CONVERSION = 0x00
    REG_CONFIG     = 0x01

    # Config bits
    OS_SINGLE      = 0x8000
    MODE_SINGLE    = 0x0100
    COMP_QUE_DISABLE = 0x0003

    # Gain settings (PGA)
    GAIN = {
        "6.144V": 0x0000,
        "4.096V": 0x0200,
        "2.048V": 0x0400,
        "1.024V": 0x0600,
        "0.512V": 0x0800,
        "0.256V": 0x0A00,
    }

    # Data rate (SPS)
    DATA_RATE = {
        8:   0x0000,
        16:  0x0020,
        32:  0x0040,
        64:  0x0060,
        128: 0x0080,
        250: 0x00A0,
        475: 0x00C0,
        860: 0x00E0,
    }

    def __init__(
        self,
        i2c_bus=0,
        scl=16,
        sda=2,
        freq=400000,
        address=0x48,
        gain="2.048V",
        data_rate=128,
    ):
        self.address = address
        self.gain = gain
        self.data_rate = data_rate
        self.i2c_bus = i2c_bus
        self.scl = scl
        self.sda = sda
        self.freq = freq

        # Pins and frequency must be configurable so the same driver works
        # across different boards and alternate bus mappings.
        self.i2c = I2C(i2c_bus, scl=Pin(scl), sda=Pin(sda), freq=freq)

    def _write_register(self, reg, value):
        """Write 16-bit value to a register."""
        data = bytes([(value >> 8) & 0xFF, value & 0xFF])
        self.i2c.writeto_mem(self.address, reg, data)

    def _read_register(self, reg):
        """Read 16-bit value from a register."""
        data = self.i2c.readfrom_mem(self.address, reg, 2)
        return (data[0] << 8) | data[1]

    def read_single(self, channel):
        """Read single-ended channel (0 to 3) and return voltage in volts."""
        if channel < 0 or channel > 3:
            raise ValueError("Channel must be 0-3 (A0 to A3)")

        # Build config
        mux = 0x4000 + (channel << 12)          # Single-ended channel
        gain_bits = self.GAIN.get(self.gain, 0x0400)
        dr_bits = self.DATA_RATE.get(self.data_rate, 0x0080)

        config = (
            self.OS_SINGLE |
            mux |
            gain_bits |
            self.MODE_SINGLE |
            dr_bits |
            self.COMP_QUE_DISABLE
        )

        self._write_register(self.REG_CONFIG, config)

        # Wait for conversion
        while True:
            status = self._read_register(self.REG_CONFIG)
            if status & 0x8000:   # OS bit set = conversion done
                break

        # Read result
        raw = self._read_register(self.REG_CONVERSION)
        if raw & 0x8000:          # Convert to signed 16-bit
            raw -= 0x10000

        # Convert to voltage
        full_scale = {
            "6.144V": 6.144, "4.096V": 4.096, "2.048V": 2.048,
            "1.024V": 1.024, "0.512V": 0.512, "0.256V": 0.256
        }.get(self.gain, 2.048)

        voltage = raw * full_scale / 32768.0
        return round(voltage, 4)

    def set_gain(self, gain):
        """Change gain at runtime."""
        if gain not in self.GAIN:
            raise ValueError(f"Invalid gain: {gain}")
        self.gain = gain

    def set_data_rate(self, data_rate):
        """Change data rate at runtime."""
        if data_rate not in self.DATA_RATE:
            raise ValueError(f"Invalid data rate: {data_rate}")
        self.data_rate = data_rate

    def deinit(self):
        """Clean up I2C bus."""
        if hasattr(self.i2c, "deinit"):
            self.i2c.deinit()
