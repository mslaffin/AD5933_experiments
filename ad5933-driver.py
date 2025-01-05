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
    
    def __init__(self, i2c, debug=False):
        self.i2c = i2c
        self.debug = debug
        
    def _write_reg(self, reg, data):
        """Write data to register with error checking and retry"""
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
        """Read from register with error checking and retry"""
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
        """Reset device"""
        # Enter power down mode
        if not self._write_reg(self.REG_CONTROL, 0xA0):
            return False
        time.sleep_ms(100)
        
        # Enter standby mode
        if not self._write_reg(self.REG_CONTROL, 0xB0):
            return False
        time.sleep_ms(100)
        
        status = self._read_reg(self.REG_STATUS)
        return status is not None
    
    def test_registers(self):
        """Test basic register read/write"""
        test_values = {
            self.REG_CONTROL: [0xB0],
            self.REG_START_FREQ: [0x0F, 0x5C, 0x28],
            self.REG_FREQ_INCR: [0x00, 0x01, 0x4F],
            self.REG_NUM_INCR: [0x00, 0x0A],
            self.REG_SETTLE_CYCLES: [0x07, 0xFF]
        }
        
        for reg, data in test_values.items():
            if self.debug:
                print(f"\nTesting register 0x{reg:02X}")
            if not self._write_reg(reg, data):
                return False
            time.sleep_ms(50)
        
        return True

def test_device():
    """Test AD5933 functionality"""
    print("\nInitializing I2C...")
    i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=100000)
    time.sleep_ms(100)
    
    # Create AD5933 instance with debug enabled
    ad = AD5933(i2c, debug=True)
    
    # Scan I2C bus
    print("\nScanning I2C bus...")
    devices = i2c.scan()
    print("Found devices:", [hex(x) for x in devices])
    
    if AD5933.ADDRESS not in devices:
        print("AD5933 not found!")
        return
        
    print("AD5933 found!")
    
    # Reset device
    print("\nResetting device...")
    if not ad.reset():
        print("Reset failed!")
        return
    print("Reset successful")
    
    # Test registers
    print("\nTesting registers...")
    if not ad.test_registers():
        print("Register tests failed!")
        return
    print("Register tests passed!")

# Run test if file is executed directly
if __name__ == '__main__':
    test_device()