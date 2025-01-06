import time
import math
import board
import busio
import tkinter as tk
import tkinter.messagebox as messagebox

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
    CTRL_STANDBY        = 0xB0

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
                        if raw_val & 0x2000:  # negative
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
            incr_code = int((freq_incr_hz * (2**27)) / clock_freq)

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

            # Settling cycles
            self._write_reg(self.REG_SETTLE_CYCLES, [0x00, 0x0F])
            return True
        except Exception as e:
            print(f"Sweep Configuration Error: {e}")
            return False

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

            # --- YIELD the data point back to the caller ---
            yield (freq, real_val, imag_val, magnitude)

            # Increment frequency unless it's the last point
            if i < num_increments:
                self._write_reg(self.REG_CONTROL, self.CTRL_INCR_FREQ)
                time.sleep(0.005)

class AD5933GUI:
    def __init__(self, master):
        """
        Initialize the GUI
        """
        self.master = master
        master.title("AD5933 Impedance Spectroscopy")

        # I2C Setup Frame
        frm_i2c = tk.Frame(master)
        frm_i2c.pack(pady=5)
        
        tk.Label(frm_i2c, text="SCL Pin:").grid(row=0, column=0, sticky="e")
        self.scl_var = tk.StringVar(value="board.SCL")
        self.scl_entry = tk.Entry(frm_i2c, textvariable=self.scl_var, width=15)
        self.scl_entry.grid(row=0, column=1, padx=5)
        
        tk.Label(frm_i2c, text="SDA Pin:").grid(row=0, column=2, sticky="e")
        self.sda_var = tk.StringVar(value="board.SDA")
        self.sda_entry = tk.Entry(frm_i2c, textvariable=self.sda_var, width=15)
        self.sda_entry.grid(row=0, column=3, padx=5)
        
        self.btn_connect = tk.Button(frm_i2c, text="Connect", command=self.connect_i2c)
        self.btn_connect.grid(row=0, column=4, padx=5)
        
        self.i2c_label = tk.Label(frm_i2c, text="Not Connected")
        self.i2c_label.grid(row=0, column=5, padx=5)

        # Sweep Configuration Frame
        frm_cfg = tk.Frame(master)
        frm_cfg.pack(pady=5)

        config_params = [
            ("Start Freq (Hz)", "start_freq_entry", "30000"),
            ("Freq Incr (Hz)", "incr_freq_entry", "100"),
            ("# Points",        "num_points_entry", "50"),
            ("Range",          "range_entry",       "1"),
            ("PGA (0=×5, 1=×1)","pga_entry",        "1")
        ]

        for i, (label, attr, default) in enumerate(config_params):
            row = i // 3
            col = (i % 3) * 2
            
            tk.Label(frm_cfg, text=label+":").grid(row=row, column=col, sticky="e")
            entry = tk.Entry(frm_cfg, width=10)
            entry.insert(0, default)
            entry.grid(row=row, column=col+1, padx=5)
            setattr(self, attr, entry)

        self.btn_sweep = tk.Button(frm_cfg, text="Start Sweep",
                                   command=self.start_sweep, state=tk.DISABLED)
        self.btn_sweep.grid(row=2, column=4, padx=5)

        self.temp_label = tk.Label(frm_cfg, text="Temp: --- °C")
        self.temp_label.grid(row=2, column=5, padx=5)

        # Canvas for plotting
        self.canvas = tk.Canvas(master, width=600, height=300, bg="white")
        self.canvas.pack(pady=5)

        # Data storage
        self.data_points = []
        self.freq_min = float('inf')
        self.freq_max = float('-inf')
        self.mag_min = float('inf')
        self.mag_max = float('-inf')

        # I2C/AD5933 references
        self.i2c_bus = None
        self.ad5933 = None

    def connect_i2c(self):
        """
        Connect to I2C bus
        """
        try:
            scl_pin = eval(self.scl_var.get())
            sda_pin = eval(self.sda_var.get())
            
            self.i2c_bus = busio.I2C(scl_pin, sda_pin)
            self.ad5933 = AD5933(self.i2c_bus, debug=True)
            
            self.i2c_label.config(text="Connected")
            self.btn_connect.config(state=tk.DISABLED)
            self.btn_sweep.config(state=tk.NORMAL)

            # Optional: initial temperature read
            temp = self.ad5933.measure_temperature()
            if temp is not None:
                self.temp_label.config(text=f"Temp: {temp:.2f}°C")

        except Exception as e:
            print(f"I2C Connection Error: {e}")
            messagebox.showerror("Connection Error", str(e))

    ###
    # 1) Method to clear data and canvas before a new sweep
    ###
    def reset_plot(self):
        """
        Clear any old data and reset the canvas
        """
        self.data_points.clear()
        self.freq_min = float('inf')
        self.freq_max = float('-inf')
        self.mag_min = float('inf')
        self.mag_max = float('-inf')
        self.canvas.delete("all")

    ###
    # 2) Method to plot data on the Tkinter canvas
    ###
    def redraw_plot(self):
        """
        Plot the magnitude vs frequency using the Tkinter Canvas.
        """
        if len(self.data_points) < 2 or self.freq_min >= self.freq_max:
            return

        w = int(self.canvas["width"])
        h = int(self.canvas["height"])
        padding = 40
        plot_w = w - 2 * padding
        plot_h = h - 2 * padding

        self.canvas.delete("all")

        # Draw X-axis
        self.canvas.create_line(padding, h - padding, w - padding, h - padding, fill="black")
        # Draw Y-axis
        self.canvas.create_line(padding, padding, padding, h - padding, fill="black")

        def x_map(freq):
            return padding + (freq - self.freq_min) / (self.freq_max - self.freq_min) * plot_w

        def y_map(mag):
            # Higher magnitude => lower on canvas
            return (h - padding) - (mag - self.mag_min) / (self.mag_max - self.mag_min) * plot_h

        num_x_ticks = 5  # or however many you want
        for i in range(num_x_ticks + 1):
            # Interpolate between freq_min and freq_max
            freq_value = self.freq_min + i * (self.freq_max - self.freq_min) / num_x_ticks
            x_pos = x_map(freq_value)
            # Short tick line
            self.canvas.create_line(x_pos, h - padding, x_pos, h - padding + 5, fill="black")
            # Numeric label under the tick
            self.canvas.create_text(x_pos, h - padding + 15,
                                    text=f"{freq_value:.0f}",
                                    anchor="n")

        num_y_ticks = 5
        for i in range(num_y_ticks + 1):
            mag_value = self.mag_min + i * (self.mag_max - self.mag_min) / num_y_ticks
            y_pos = y_map(mag_value)
            # Short tick
            self.canvas.create_line(padding - 5, y_pos, padding, y_pos, fill="black")
            # Numeric label
            self.canvas.create_text(padding - 10, y_pos,
                                    text=f"{mag_value:.2f}",
                                    anchor="e")

        # 4) Axis labels
        # X-axis label
        self.canvas.create_text(w // 2, h - 5, text="Frequency (Hz)", anchor="s", font=("Arial", 12, "bold"))
        # Y-axis label - rotate if you want vertical text
        self.canvas.create_text(15, h // 2, text="Magnitude", anchor="center", angle=90,
                                font=("Arial", 12, "bold"))

        prev_x = None
        prev_y = None
        for (freq, real_val, imag_val, mag) in self.data_points:
            x = x_map(freq)
            y = y_map(mag)
            self.canvas.create_oval(x-2, y-2, x+2, y+2, fill="blue")
            if prev_x is not None:
                self.canvas.create_line(prev_x, prev_y, x, y, fill="blue")
            prev_x, prev_y = x, y

    def redraw_bode_plot(self):
        """
        Example: Bode plot style, with magnitude in dB vs. log(frequency).
        """
        if len(self.data_points) < 2:
            return

        # 1) Transform data into log(f) and dB(mag)
        transformed_points = []
        for (freq, real_val, imag_val, mag) in self.data_points:
            if freq <= 0:
                continue
            freq_log = math.log10(freq)
            mag_db = 20 * math.log10(mag + 1e-12)
            transformed_points.append((freq_log, mag_db))

        if not transformed_points:
            return

        # 2) Find min/max in log(freq) and dB(mag)
        freq_log_min = min(p[0] for p in transformed_points)
        freq_log_max = max(p[0] for p in transformed_points)
        mag_db_min   = min(p[1] for p in transformed_points)
        mag_db_max   = max(p[1] for p in transformed_points)

        # If there's no range, bail
        if freq_log_min == freq_log_max:
            return

        w = int(self.canvas["width"])
        h = int(self.canvas["height"])
        padding = 40
        plot_w = w - 2 * padding
        plot_h = h - 2 * padding

        self.canvas.delete("all")

        # Draw axes
        self.canvas.create_line(padding, h - padding, w - padding, h - padding, fill="black")  # X-axis
        self.canvas.create_line(padding, padding, padding, h - padding, fill="black")          # Y-axis

        def x_map(fl):
            # fl is log10(freq)
            return padding + (fl - freq_log_min) / (freq_log_max - freq_log_min) * plot_w

        def y_map(db):
            # bigger dB => lower on canvas
            return (h - padding) - (db - mag_db_min) / (mag_db_max - mag_db_min) * plot_h

        # Ticks for x-axis (log scale in base 10)
        num_x_ticks = 5
        for i in range(num_x_ticks + 1):
            fl_val = freq_log_min + i * (freq_log_max - freq_log_min) / num_x_ticks
            x_pos = x_map(fl_val)
            # Convert back to linear for labeling
            freq_val = 10 ** fl_val
            self.canvas.create_line(x_pos, h - padding, x_pos, h - padding + 5, fill="black")
            self.canvas.create_text(x_pos, h - padding + 15, text=f"{freq_val:.0f}", anchor="n")

        # Ticks for y-axis (dB)
        num_y_ticks = 6
        for i in range(num_y_ticks + 1):
            db_val = mag_db_min + i * (mag_db_max - mag_db_min) / num_y_ticks
            y_pos = y_map(db_val)
            self.canvas.create_line(padding - 5, y_pos, padding, y_pos, fill="black")
            self.canvas.create_text(padding - 10, y_pos, text=f"{db_val:.1f}", anchor="e")

        # Axis Labels
        self.canvas.create_text(w // 2, h - 5, text="Frequency (Hz)", anchor="s", font=("Arial", 12, "bold"))
        self.canvas.create_text(15, h // 2, text="Magnitude (dB)", anchor="center",
                                angle=90, font=("Arial", 12, "bold"))

        # Plot the data
        prev_x = None
        prev_y = None
        for (fl, db) in transformed_points:
            x = x_map(fl)
            y = y_map(db)
            self.canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill="red")
            if prev_x is not None:
                self.canvas.create_line(prev_x, prev_y, x, y, fill="red")
            prev_x, prev_y = x, y

    def start_sweep(self):
        """
        Start impedance sweep, updating the plot in real time.
        """
        if not self.ad5933:
            messagebox.showerror("Error", "Not connected to I2C!")
            return

        # Clear old data/plot
        self.reset_plot()

        try:
            # Parse user inputs
            start_freq = int(self.start_freq_entry.get())
            freq_incr = int(self.incr_freq_entry.get())
            num_points = int(self.num_points_entry.get())
            range_code = int(self.range_entry.get())
            pga_mode = bool(int(self.pga_entry.get()))

            # Optional temperature read before
            temp_before = self.ad5933.measure_temperature()
            if temp_before is not None:
                self.temp_label.config(text=f"Temp: {temp_before:.2f}°C")
            else:
                self.temp_label.config(text="Temp: ??? °C")

            # Create the generator
            gen = self.ad5933.sweep_generator(
                start_freq,
                freq_incr,
                num_points,
                pga_gain_x1=pga_mode,
                excitation_range_code=range_code
            )

            # Iterate over each new data point
            for (freq, real_val, imag_val, mag) in gen:
                # Append to local data store
                self.data_points.append((freq, real_val, imag_val, mag))

                # Update min/max tracking
                if freq < self.freq_min:
                    self.freq_min = freq
                if freq > self.freq_max:
                    self.freq_max = freq
                if mag < self.mag_min:
                    self.mag_min = mag
                if mag > self.mag_max:
                    self.mag_max = mag

                # Redraw the plot
                self.redraw_plot()
                # Give Tkinter a chance to update the window
                self.master.update_idletasks()
                # Or self.master.update() - but be cautious with potential re-entry
                # Optionally add a small delay if you want slower updates
                # time.sleep(0.02)

            # Optional temperature read after
            temp_after = self.ad5933.measure_temperature()
            if temp_after is not None:
                self.temp_label.config(text=f"Temp: {temp_after:.2f}°C")

            print("SWEEP_DONE")

        except Exception as e:
            messagebox.showerror("Sweep Error", str(e))


def main():
    root = tk.Tk()
    app = AD5933GUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
