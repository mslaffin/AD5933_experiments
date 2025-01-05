from machine import I2C, Pin
import time

class AD5933:
    # Device address
    ADDRESS = 0x0D
    
    # Register addresses
    REG_CONTROL = 0x80
    REG_START_FREQ = 0x82 
    REG_FREQ_INCR = 0x85
    REG_NUM_INCR = 0x88
    REG_SETTLE_CYCLES = 0x8A
    REG_STATUS = 0x8F
    REG_REAL = 0x94
    REG_IMAG = 0x96
    
    def __init__(self, i2c, debug=False):
        self.i2c = i2c
        self.debug = debug
        
    def _write_reg(self, reg, data):
        if isinstance(data, int):
            data = bytes([data])
        elif isinstance(data, list):
            data = bytes(data)
            
        if self.debug:
            print(f"Writing {[hex(x) for x in data]} to reg 0x{reg:02X}")
        
        retries = 3
        while retries > 0:
            try:
                self.i2c.writeto_mem(self.ADDRESS, reg, data)
                time.sleep_ms(10)
                return True
            except OSError as e:
                retries -= 1
                if retries == 0:
                    if self.debug:
                        print(f"Write failed after 3 retries: {e}")
                    return False
                time.sleep_ms(50)
                
    def _read_reg(self, reg, nbytes=1):
        retries = 3
        while retries > 0:
            try:
                data = self.i2c.readfrom_mem(self.ADDRESS, reg, nbytes)
                if self.debug:
                    print(f"Read {[hex(x) for x in data]} from reg 0x{reg:02X}")
                return data
            except OSError as e:
                retries -= 1
                if retries == 0:
                    if self.debug:
                        print(f"Read failed after 3 retries: {e}")
                    return None
                time.sleep_ms(50)
    
    def reset(self):
        # Power-down mode
        if not self._write_reg(self.REG_CONTROL, 0xA0):
            return False
        time.sleep_ms(100)
        
        # Standby mode
        if not self._write_reg(self.REG_CONTROL, 0xB0):
            return False
        time.sleep_ms(100)
        
        status = self._read_reg(self.REG_STATUS)
        return status is not None
    
    def get_status(self):
        data = self._read_reg(self.REG_STATUS)
        if data is None:
            return 0
        return data[0]
    
    def configure_frequency(self, start_freq_hz, freq_incr_hz, num_points):
        # Using 16MHz clock divided by 4: MCLK = 16MHz/4 = 4MHz
        clock_freq = 4e6  
        
        # Calculate frequency codes
        start_code = int((start_freq_hz * (2**27)) / clock_freq)
        incr_code = int((freq_incr_hz * (2**27)) / clock_freq)
        
        # Start frequency (24-bit)
        if not self._write_reg(self.REG_START_FREQ, [
            (start_code >> 16) & 0xFF,
            (start_code >> 8) & 0xFF,
            start_code & 0xFF
        ]):
            return False
            
        # Frequency increment (24-bit)
        if not self._write_reg(self.REG_FREQ_INCR, [
            (incr_code >> 16) & 0xFF,
            (incr_code >> 8) & 0xFF,
            incr_code & 0xFF
        ]):
            return False
            
        # Number of increments (9-bit)
        if not self._write_reg(self.REG_NUM_INCR, [
            (num_points >> 8) & 0xFF,
            num_points & 0xFF
        ]):
            return False
            
        # Settling time cycles
        if not self._write_reg(self.REG_SETTLE_CYCLES, [0x00, 0xFF]):
            return False
            
        return True

    def start_frequency_sweep(self):
        # Initialize with start frequency
        if not self._write_reg(self.REG_CONTROL, 0x10):
            return False
        time.sleep_ms(100)
        
        # Begin frequency sweep
        if not self._write_reg(self.REG_CONTROL, 0x20):
            return False
        
        return True

    def read_complex_data(self):
        # Read real data (16 bits)
        real_data = self._read_reg(self.REG_REAL, 2)
        # Read imaginary data (16 bits)
        imag_data = self._read_reg(self.REG_IMAG, 2)
        
        if real_data is None or imag_data is None:
            return None
            
        # Convert to signed 16-bit integers
        real = int.from_bytes(real_data, 'big')
        if real & 0x8000:
            real -= 65536
        
        imag = int.from_bytes(imag_data, 'big')
        if imag & 0x8000:
            imag -= 65536
            
        return (real, imag)

def test_sweep():
    print("\nInitializing I2C...")
    i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=100000)
    ad = AD5933(i2c, debug=True)
    
    # Configure sweep
    start_freq = 30000  # 30 kHz
    freq_incr = 100     # 100 Hz steps
    num_points = 50     # 50 points
    
    print(f"\nConfiguring frequency sweep:")
    print(f"Start frequency: {start_freq} Hz")
    print(f"Frequency increment: {freq_incr} Hz")
    print(f"Number of points: {num_points}")
    
    if not ad.configure_frequency(start_freq, freq_incr, num_points):
        print("Failed to configure frequency sweep!")
        return
        
    print("\nStarting sweep...")
    if not ad.start_frequency_sweep():
        print("Failed to start sweep!")
        return
        
    # Wait for sweep completion
    print("\nMeasuring...")
    data_points = []
    
    time.sleep_ms(100)  # Initial settling time
    
    for i in range(num_points):
        # Wait for valid data
        valid_data = False
        for _ in range(20):
            status = ad.get_status()
            if status & 0x02:  # Valid real/imaginary data
                valid_data = True
                break
            time.sleep_ms(50)
            
        if not valid_data:
            print(f"Timeout waiting for data at point {i}")
            continue
            
        # Read data
        complex_data = ad.read_complex_data()
        if complex_data:
            real, imag = complex_data
            magnitude = (real*real + imag*imag)**0.5
            data_points.append(magnitude)
            print(f"Point {i}: Real={real}, Imag={imag}, Mag={magnitude:.2f}")
            
        # Increment frequency (unless last point)
        if i < num_points - 1:
            ad._write_reg(ad.REG_CONTROL, 0x30)
            time.sleep_ms(50)
            
    print("\nSweep complete!")
    return data_points

# Run sweep if file is executed directly
if __name__ == '__main__':
    test_sweep()