from machine import I2C, Pin
import time

class AD5933:
    ADDRESS = 0x0D
    
    def __init__(self, i2c):
        self.i2c = i2c
        
    def write_reg(self, reg, data, debug=False):
        if isinstance(data, int):
            data = bytes([data])
        elif isinstance(data, list):
            data = bytes(data)
            
        if debug:
            print(f"Writing to reg 0x{reg:02X}: {[hex(x) for x in data]}")
        
        try:
            self.i2c.writeto_mem(self.ADDRESS, reg, data)
            time.sleep_ms(10)  # Increased delay
        except OSError as e:
            print(f"Error writing to reg 0x{reg:02X}: {e}")
            raise
        
    def read_reg(self, reg, nbytes=1, debug=False):
        try:
            data = self.i2c.readfrom_mem(self.ADDRESS, reg, nbytes)
            if debug:
                print(f"Read from reg 0x{reg:02X}: {[hex(x) for x in data]}")
            return data
        except OSError as e:
            print(f"Error reading from reg 0x{reg:02X}: {e}")
            raise

    def scan_bus(self):
        devices = self.i2c.scan()
        print("Devices found:", [hex(device) for device in devices])
        return devices
        
    def reset(self):
        """Reset the device"""
        print("\nResetting device...")
        
        # Power-down mode
        self.write_reg(0x80, 0xA0, debug=True)
        time.sleep_ms(100)
        
        # Read status
        status = self.read_reg(0x8F, debug=True)
        print(f"Status: 0x{status[0]:02X}")
        
        # Standby mode
        self.write_reg(0x80, 0xB0, debug=True)
        time.sleep_ms(100)
        
        status = self.read_reg(0x8F, debug=True)
        print(f"Status: 0x{status[0]:02X}")
            
    def test_registers(self):
        """Test reading and writing to each register"""
        print("\nTesting registers...")
        
        registers_to_test = [
            (0x80, [0xB0]),  # Control
            (0x82, [0x0F, 0x5C, 0x28]),  # Start frequency
            (0x85, [0x00, 0x01, 0x4F]),  # Frequency increment
            (0x88, [0x00, 0x0A]),  # Number of increments
            (0x8A, [0x07, 0xFF]),  # Settling time
        ]
        
        for reg, data in registers_to_test:
            print(f"\nTesting register 0x{reg:02X}...")
            try:
                # Try writing
                self.write_reg(reg, data, debug=True)
                time.sleep_ms(50)
                
                # Try reading if it's a readable register
                if reg in [0x8F]:  # Status register
                    value = self.read_reg(reg, debug=True)
                    print(f"Read back: {[hex(x) for x in value]}")
                    
            except OSError as e:
                print(f"Failed at register 0x{reg:02X}: {e}")
                return False
                
            time.sleep_ms(100)  # Longer delay between register tests
            
        return True

def test_device():
    """Run a basic test sequence"""
    # Initialize I2C at lower frequency
    print("\nInitializing I2C...")
    i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=100000)
    time.sleep_ms(100)
    
    ad = AD5933(i2c)
    
    # Scan bus
    print("\nScanning I2C bus...")
    devices = ad.scan_bus()
    
    if 0x0D not in devices:
        print("AD5933 not found!")
        return
        
    print("AD5933 found!")
    
    # Reset device
    ad.reset()
    
    # Test registers
    success = ad.test_registers()
    
    if success:
        print("\nAll register tests passed!")
    else:
        print("\nRegister tests failed!")

# Run the test if executed directly
if __name__ == '__main__':
    test_device()