# ad5933.py

import time
import math
import busio

class AD5933:
    """
    AD5933 I2C Communication Class
    Adapted for CircuitPython I2C communication
    """
    ADDRESS = 0x0D  # I2C address of AD5933

    # Register addresses
    REG_CONTROL         = 0x80
    REG_START_FREQ      = 0x82
    REG_FREQ_INCR       = 0x85
    REG_NUM_INCR        = 0x88
    REG_SETTLE_CYCLES   = 0x8A
    REG_STATUS          = 0x8F
    REG_TEMP_DATA       = 0x92
    REG_REAL            = 0x94
    REG_IMAG            = 0x96

    # Control Register Commands
    CTRL_INIT_START     = 0x10
    CTRL_START_SWEEP    = 0x20
    CTRL_INCR_FREQ      = 0x30
    CTRL_REPEAT_FREQ    = 0x40
    CTRL_MEAS_TEMP      = 0x90
    CTRL_POWER_DOWN     = 0xA0
    CTRL_POWER_UP       = 0x00
    CTRL_STANDBY        = 0xB0

    # Excitation ranges
    RANGE_2V      = 1  # 2.0 V p-p
    RANGE_1V      = 2  # 1.0 V p-p
    RANGE_400mV   = 3  # 0.4 V p-p
    RANGE_200mV   = 4  # 0.2 V p-p

    def __init__(self, i2c_bus, debug=False):
        """
        Initialize AD5933 with CircuitPython I2C bus
        
        :param i2c_bus: CircuitPython I2C bus object
        :param debug: Enable debug printing
        """
        self.i2c = i2c_bus
        self.debug = debug

    def _write_reg(self, reg, data):
        """
        Write to a register via I2C
        """
        try:
            if isinstance(data, int):
                data = [data]
            message = bytearray([reg] + data)
            self.i2c.writeto(self.ADDRESS, message)
            if self.debug:
                print(f"Write to reg {hex(reg)}: {[hex(x) for x in message]}")
            time.sleep(0.01)
            return True
        except Exception as e:
            print(f"I2C Write Error: {e}")
            return False

    def _read_reg(self, reg, nbytes=1):
        """
        Read from a register via I2C
        """
        try:
            result = bytearray(nbytes)
            self.i2c.writeto_then_readfrom(self.ADDRESS, bytes([reg]), result)
            if self.debug:
                print(f"Read from reg {hex(reg)}: {[hex(x) for x in result]}")
            return result
        except Exception as e:
            print(f"I2C Read Error: {e}")
            return None

    def measure_temperature(self):
        """
        Measure device temperature
        """
        try:
            # Trigger temperature measurement
            self._write_reg(self.REG_CONTROL, 0x90)
            # Wait for valid measurement
            for _ in range(20):
                status = self._read_reg(self.REG_STATUS)[0]
                if status & 0x01:
                    raw = self._read_reg(self.REG_TEMP_DATA, 2)
                    if raw:
                        raw_val = int.from_bytes(raw, 'big', signed=True)
                        # See AD5933 datasheet for sign logic
                        if raw_val & 0x2000:  # negative bit
                            temp_c = (raw_val - 16384) / 32.0
                        else:
                            temp_c = raw_val / 32.0
                        return round(temp_c, 2)
                time.sleep(0.05)
            return None
        except Exception as e:
            print(f"Temperature Measurement Error: {e}")
            return None

    def configure_sweep(self, start_freq_hz, freq_incr_hz, num_increments,
                        pga_gain_x1=True, excitation_range_code=1):
        """
        Configure frequency sweep parameters
        """
        try:
            # Reset device
            self._write_reg(self.REG_CONTROL, self.CTRL_POWER_DOWN)
            time.sleep(0.1)
            self._write_reg(self.REG_CONTROL, self.CTRL_STANDBY)

            # Range bits
            range_bits = {
                1: (0, 0),  # 2.0 V p-p
                2: (0, 1),  # 1.0 V p-p
                3: (1, 0),  # 0.4 V p-p
                4: (1, 1),  # 0.2 V p-p
            }
            rb = range_bits.get(excitation_range_code, (0, 0))

            # Build control register high byte
            ctrl_high = (0xA << 4) | \
                        ((rb[0] & 1) << 2) | \
                        ((rb[1] & 1) << 1) | \
                        (1 if pga_gain_x1 else 0)

            # Write control register
            self._write_reg(self.REG_CONTROL, [ctrl_high, 0x00])

            # Calculate frequency codes (assuming 4MHz clock)
            clock_freq = 4e6
            start_code = int((start_freq_hz * (2**27)) / clock_freq)
            incr_code  = int((freq_incr_hz * (2**27)) / clock_freq)

            # Write start frequency
            self._write_reg(self.REG_START_FREQ, [
                (start_code >> 16) & 0xFF,
                (start_code >> 8) & 0xFF,
                start_code & 0xFF
            ])

            # Write frequency increment
            self._write_reg(self.REG_FREQ_INCR, [
                (incr_code >> 16) & 0xFF,
                (incr_code >> 8) & 0xFF,
                incr_code & 0xFF
            ])

            # Write number of increments
            self._write_reg(self.REG_NUM_INCR, [
                (num_increments >> 8) & 0xFF,
                num_increments & 0xFF
            ])

            # Settling cycles (example fixed)
            self._write_reg(self.REG_SETTLE_CYCLES, [0x00, 0x0F])
            return True
        except Exception as e:
            print(f"Sweep Configuration Error: {e}")
            return False

    def configure_settling_time(self, cycles, multiply_by=1):
        """Configure settling time cycles"""
        # Multiply_by can be 1, 2, or 4 per datasheet
        msb = (multiply_by & 0x3) << 9 | (cycles >> 8) & 0x1
        lsb = cycles & 0xFF
        return self._write_reg(self.REG_SETTLE_CYCLES, [msb, lsb])

    def sweep_generator(self, start_freq_hz, freq_incr_hz, num_increments,
                        pga_gain_x1=True, excitation_range_code=1):
        """
        Generator that configures the sweep and then yields one data point at a time.
        """
        # Configure the device
        if not self.configure_sweep(start_freq_hz, freq_incr_hz, num_increments,
                                    pga_gain_x1, excitation_range_code):
            # If configuration fails, we yield nothing
            return

        # Initialize with start frequency
        self._write_reg(self.REG_CONTROL, self.CTRL_INIT_START)
        time.sleep(0.02)

        # Start sweep
        self._write_reg(self.REG_CONTROL, self.CTRL_START_SWEEP)
        time.sleep(0.02)

        # Collect data points
        for i in range(num_increments + 1):
            # Wait for valid data
            for _ in range(20):
                status = self._read_reg(self.REG_STATUS)[0]
                if status & 0x02:  # Data ready
                    break
                time.sleep(0.002)

            # Read real/imag
            raw_real = self._read_reg(self.REG_REAL, 2)
            raw_imag = self._read_reg(self.REG_IMAG, 2)
            real_val = int.from_bytes(raw_real, 'big', signed=True)
            imag_val = int.from_bytes(raw_imag, 'big', signed=True)

            freq = start_freq_hz + i * freq_incr_hz
            magnitude = math.sqrt(real_val**2 + imag_val**2)

            # Yield the data point back to the caller
            yield (freq, real_val, imag_val, magnitude)

            # Increment frequency unless it's the last point
            if i < num_increments:
                self._write_reg(self.REG_CONTROL, self.CTRL_INCR_FREQ)
                time.sleep(0.005)

    def calculate_phase(self, real, imag):
        """Calculate phase angle from real and imaginary components"""
        phase = math.atan2(imag, real)
        return math.degrees(phase)

    def calculate_impedance(self, real, imag, gain_factor):
        """Calculate impedance magnitude using calibration gain factor"""
        magnitude = math.sqrt(real**2 + imag**2)
        return 1 / (magnitude * gain_factor)
