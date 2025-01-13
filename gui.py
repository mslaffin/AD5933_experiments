# gui.py

import time
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import board
import busio

from ad5933 import AD5933
from plot import Plot

class AD5933GUI:
    def __init__(self, master):
        """Initialize the GUI"""
        self.master = master
        master.title("AD5933 Impedance Analyzer")

        # Data range tracking
        self.freq_min = float('inf')
        self.freq_max = float('-inf')
        self.mag_min = float('inf')
        self.mag_max = float('-inf')

        # Create main container
        self.main_frame = ttk.Frame(master)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        
        # Create frames
        self.create_connection_frame()
        self.create_config_frame()
        self.create_plot_frame()
        
        # Initialize Plot handler
        self.plot = Plot(self.canvas)
        
        # Create menubar
        self.create_menubar()
        
        # Data storage
        self.data_points = []
        self.current_sweep = {
            'freq_min': float('inf'),
            'freq_max': float('-inf'),
            'mag_min': float('inf'),
            'mag_max': float('-inf'),
            'phase_min': float('inf'),
            'phase_max': float('-inf')
        }
        
        # Device references
        self.i2c_bus = None
        self.ad5933 = None

    def create_menubar(self):
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export Data...", command=self.export_data)
        file_menu.add_command(label="Import Data...", command=self.import_data)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.master.quit)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Linear Plot", command=lambda: self.set_plot_type('linear'))
        view_menu.add_command(label="Bode Plot", command=lambda: self.set_plot_type('bode'))
        view_menu.add_command(label="Phase Plot", command=lambda: self.set_plot_type('phase'))
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Show Grid", command=self.plot.toggle_grid)

    def create_connection_frame(self):
        frame = ttk.LabelFrame(self.main_frame, text="Connection")
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(frame, text="SCL Pin:").grid(row=0, column=0, padx=5, pady=5)
        self.scl_var = tk.StringVar(value="board.SCL")
        ttk.Entry(frame, textvariable=self.scl_var, width=15).grid(row=0, column=1)
        
        ttk.Label(frame, text="SDA Pin:").grid(row=0, column=2, padx=5)
        self.sda_var = tk.StringVar(value="board.SDA")
        ttk.Entry(frame, textvariable=self.sda_var, width=15).grid(row=0, column=3)
        
        self.btn_connect = ttk.Button(frame, text="Connect", command=self.connect_i2c)
        self.btn_connect.grid(row=0, column=4, padx=5)
        
        self.connection_status = ttk.Label(frame, text="Not Connected")
        self.connection_status.grid(row=0, column=5, padx=5)

    def create_config_frame(self):
        frame = ttk.LabelFrame(self.main_frame, text="Sweep Configuration")
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        basic_frame = ttk.Frame(frame)
        basic_frame.pack(fill=tk.X, padx=5, pady=5)
        
        config_params = [
            ("Start Freq (Hz)", "start_freq", "30000"),
            ("Freq Incr (Hz)",  "freq_incr",  "100"),
            ("# Points",        "num_points", "50"),
            ("Range",           "range",      "1"),
            ("PGA Gain",        "pga_gain",   "1")
        ]
        
        for i, (label, var_name, default) in enumerate(config_params):
            row = i // 3
            col = (i % 3) * 2
            ttk.Label(basic_frame, text=label).grid(row=row, column=col, padx=5, pady=2)
            var = tk.StringVar(value=default)
            setattr(self, f"{var_name}_var", var)
            ttk.Entry(basic_frame, textvariable=var, width=10).grid(
                row=row, column=col+1, padx=5, pady=2)
        
        # Advanced settings toggle
        ttk.Checkbutton(
            basic_frame, text="Show Advanced", command=self.toggle_advanced
        ).grid(row=2, column=4, columnspan=2, pady=5)
        
        self.create_advanced_frame(frame)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.btn_sweep = ttk.Button(btn_frame, text="Start Sweep",
                                    command=self.start_sweep, state=tk.DISABLED)
        self.btn_sweep.pack(side=tk.LEFT, padx=5)
        
        self.temp_label = ttk.Label(btn_frame, text="Temp: --- °C")
        self.temp_label.pack(side=tk.RIGHT, padx=5)

    def create_plot_frame(self):
        frame = ttk.LabelFrame(self.main_frame, text="Measurement Results")
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(frame, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

    def create_advanced_frame(self, parent):
        self.advanced_frame = ttk.LabelFrame(parent, text="Advanced Settings")
        
        advanced_params = [
            ("Settling Cycles",    "settling_cycles", "10"),
            ("Clock Source",       "clock_source",    "Internal"),
            ("Settling Multiplier","settling_mult",   "1"),
            ("Temperature Monitor","temp_monitor",    "0")
        ]
        
        for i, (label, var_name, default) in enumerate(advanced_params):
            ttk.Label(self.advanced_frame, text=label).grid(
                row=i, column=0, padx=5, pady=2, sticky="e")
            var = tk.StringVar(value=default)
            setattr(self, f"{var_name}_var", var)
            
            if var_name == "clock_source":
                ttk.Combobox(self.advanced_frame, textvariable=var,
                             values=["Internal", "External"], width=10).grid(
                    row=i, column=1, padx=5, pady=2)
            elif var_name == "temp_monitor":
                ttk.Checkbutton(self.advanced_frame, variable=var).grid(
                    row=i, column=1, padx=5, pady=2, sticky="w")
            else:
                ttk.Entry(self.advanced_frame, textvariable=var, width=10).grid(
                    row=i, column=1, padx=5, pady=2)
        
        ttk.Button(self.advanced_frame, text="Apply Settings",
                   command=self.apply_advanced_settings).grid(
                   row=len(advanced_params), column=0, columnspan=2, pady=10)

    def toggle_advanced(self):
        """Toggle advanced settings panel"""
        if self.advanced_frame.winfo_viewable():
            self.advanced_frame.pack_forget()
        else:
            self.advanced_frame.pack(fill=tk.X, padx=5, pady=5)

    def apply_advanced_settings(self):
        """Apply advanced settings from the GUI to the AD5933 (if connected)."""
        try:
            settling_cycles = int(self.settling_cycles_var.get())
            settling_mult   = int(self.settling_mult_var.get())
            clock_source    = self.clock_source_var.get()
            temp_monitor    = bool(int(self.temp_monitor_var.get())) if self.temp_monitor_var.get() else False
            
            if self.ad5933:
                self.ad5933.configure_settling_time(cycles=settling_cycles, multiply_by=settling_mult)
                # Handle clock_source or temp_monitor as needed for your system
                
            messagebox.showinfo("Advanced Settings", "Advanced settings applied successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply advanced settings:\n{e}")

    def export_data(self):
        """Export sweep data to CSV file"""
        if not self.data_points:
            messagebox.showwarning("Export", "No data to export!")
            return
            
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write("Frequency,Real,Imaginary,Magnitude,Phase\n")
                    for freq, real, imag, mag in self.data_points:
                        phase = math.degrees(math.atan2(imag, real))
                        f.write(f"{freq},{real},{imag},{mag},{phase}\n")
                messagebox.showinfo("Export", "Data exported successfully")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def import_data(self):
        """Import sweep data from CSV file"""
        filename = filedialog.askopenfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                self.reset_plot()
                with open(filename, 'r') as f:
                    # Skip header
                    header = f.readline()
                    for line in f:
                        freq, real, imag, mag, phase = map(float, line.strip().split(','))
                        self.data_points.append((freq, real, imag, mag))
                        
                        if freq < self.freq_min:
                            self.freq_min = freq
                        if freq > self.freq_max:
                            self.freq_max = freq
                        if mag < self.mag_min:
                            self.mag_min = mag
                        if mag > self.mag_max:
                            self.mag_max = mag
                        
                if self.plot.plot_type == 'bode':
                    self.redraw_bode_plot()
                elif self.plot.plot_type == 'phase':
                    self.redraw_phase_plot()
                else:
                    self.redraw_plot()
                    
                messagebox.showinfo("Import", "Data imported successfully")
            except Exception as e:
                messagebox.showerror("Import Error", str(e))

    def connect_i2c(self):
        """
        Connect to I2C bus
        """
        try:
            scl_pin = eval(self.scl_var.get())  # e.g. board.SCL
            sda_pin = eval(self.sda_var.get())  # e.g. board.SDA
            
            self.i2c_bus = busio.I2C(scl_pin, sda_pin)
            self.ad5933 = AD5933(self.i2c_bus, debug=True)
            
            self.connection_status.config(text="Connected")
            self.btn_connect.config(state=tk.DISABLED)
            self.btn_sweep.config(state=tk.NORMAL)

            # Optional: initial temperature read
            temp = self.ad5933.measure_temperature()
            if temp is not None:
                self.temp_label.config(text=f"Temp: {temp:.2f}°C")
        except Exception as e:
            print(f"I2C Connection Error: {e}")
            messagebox.showerror("Connection Error", str(e))

    def set_plot_type(self, plot_type):
        """Change the plot type and redraw"""
        self.plot.plot_type = plot_type
        if not self.data_points:
            return
        if plot_type == 'bode':
            self.redraw_bode_plot()
        elif plot_type == 'phase':
            self.redraw_phase_plot()
        else:
            self.redraw_plot()

    def reset_plot(self):
        """Clear old data and reset the canvas"""
        self.data_points.clear()
        self.freq_min = float('inf')
        self.freq_max = float('-inf')
        self.mag_min = float('inf')
        self.mag_max = float('-inf')
        self.canvas.delete("all")

    def redraw_plot(self):
        """Linear magnitude vs. frequency plot"""
        if len(self.data_points) < 2 or self.freq_min >= self.freq_max:
            self.canvas.delete("all")
            return

        self.canvas.delete("all")
        w = int(self.canvas["width"])
        h = int(self.canvas["height"])
        

        padding = self.plot.padding
        plot_w = w - 2 * padding
        plot_h = h - 2 * padding
        print(f"Canvas: width={w}, height={h}, plot_w={plot_w}, plot_h={plot_h}")
        # Axes
        self.canvas.create_line(padding, h - padding, w - padding, h - padding, fill="black")
        self.canvas.create_line(padding, padding, padding, h - padding, fill="black")

        def x_map(freq):
            return padding + (freq - self.freq_min) / (self.freq_max - self.freq_min) * plot_w

        def y_map(mag):
            return (h - padding) - (mag - self.mag_min) / (self.mag_max - self.mag_min) * plot_h

        # X ticks
        num_x_ticks = 5
        for i in range(num_x_ticks + 1):
            freq_value = self.freq_min + i * (self.freq_max - self.freq_min) / num_x_ticks
            x_pos = x_map(freq_value)
            self.canvas.create_line(x_pos, h - padding, x_pos, h - padding + 5, fill="black")
            self.canvas.create_text(x_pos, h - padding + 15,
                                    text=f"{freq_value:.0f}",
                                    anchor="n")

        # Y ticks
        num_y_ticks = 5
        for i in range(num_y_ticks + 1):
            mag_value = self.mag_min + i * (self.mag_max - self.mag_min) / num_y_ticks
            y_pos = y_map(mag_value)
            self.canvas.create_line(padding - 5, y_pos, padding, y_pos, fill="black")
            self.canvas.create_text(padding - 10, y_pos,
                                    text=f"{mag_value:.2f}",
                                    anchor="e")

        # Plot data
        prev_x = None
        prev_y = None
        for (freq, real_val, imag_val, mag) in self.data_points:
            x = x_map(freq)
            y = y_map(mag)
            self.canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill="blue")
            if prev_x is not None:
                self.canvas.create_line(prev_x, prev_y, x, y, fill="blue")
            prev_x, prev_y = x, y

        x_label_y = h - padding * 0.3
        self.canvas.create_text(
            w // 2,
            x_label_y,
            text="Frequency (Hz)",
            anchor="center",
            font=("Arial", 12, "bold"))
        
        y_label_x = padding * 0.1
        self.canvas.create_text(
            y_label_x,
            h // 2,
            text="Magnitude",
            anchor="center",
            angle=90,
            font=("Arial", 12, "bold"))

    def redraw_phase_plot(self):
        """Phase vs. frequency plot"""
        if len(self.data_points) < 2:
            return

        self.canvas.delete("all")
        w = int(self.canvas["width"])
        h = int(self.canvas["height"])
        padding = self.plot.padding
        plot_w = w - 2 * padding
        plot_h = h - 2 * padding

        phase_data = []
        phase_min = float('inf')
        phase_max = float('-inf')
        
        for (freq, real, imag, mag) in self.data_points:
            phase = math.degrees(math.atan2(imag, real))
            phase_data.append((freq, phase))
            if phase < phase_min:
                phase_min = phase
            if phase > phase_max:
                phase_max = phase

        def x_map(freq):
            return padding + (freq - self.freq_min) / (self.freq_max - self.freq_min) * plot_w

        def y_map(p):
            return (h - padding) - (p - phase_min) / (phase_max - phase_min) * plot_h

        # Grid
        if self.plot.show_grid:
            self.plot.draw_grid(w, h)

        # Axes
        self.canvas.create_line(padding, h - padding, w - padding, h - padding, fill="black", width=2)
        self.canvas.create_line(padding, padding, padding, h - padding, fill="black", width=2)

        # Ticks
        num_ticks = 5
        for i in range(num_ticks + 1):
            # X
            f_val = self.freq_min + (self.freq_max - self.freq_min) * i / num_ticks
            x = x_map(f_val)
            self.canvas.create_line(x, h - padding, x, h - padding + 5, fill="black")
            self.canvas.create_text(x, h - padding + 15, text=f"{f_val:.0f}", anchor="n")

            # Y
            ph_val = phase_min + (phase_max - phase_min) * i / num_ticks
            y = y_map(ph_val)
            self.canvas.create_line(padding - 5, y, padding, y, fill="black")
            self.canvas.create_text(padding - 10, y, text=f"{ph_val:.1f}°", anchor="e")

        self.canvas.create_text(w // 2, h - padding // 2, text="Frequency (Hz)", 
                                anchor="center", font=("Arial", 12, "bold"))
        self.canvas.create_text(padding // 2, h // 2, text="Phase (degrees)", 
                                anchor="center", angle=90, font=("Arial", 12, "bold"))

        prev_x = None
        prev_y = None
        for freq, phase in phase_data:
            x = x_map(freq)
            y = y_map(phase)
            self.canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill="green")
            if prev_x is not None:
                self.canvas.create_line(prev_x, prev_y, x, y, fill="green")
            prev_x, prev_y = x, y

    def redraw_bode_plot(self):
        """Bode-style plot: magnitude in dB vs. log10(frequency)"""
        if len(self.data_points) < 2:
            return

        transformed_points = []
        for (freq, real_val, imag_val, mag) in self.data_points:
            if freq <= 0:
                continue
            freq_log = math.log10(freq)
            mag_db   = 20 * math.log10(mag + 1e-12)
            transformed_points.append((freq_log, mag_db))

        if not transformed_points:
            return

        freq_log_min = min(p[0] for p in transformed_points)
        freq_log_max = max(p[0] for p in transformed_points)
        mag_db_min   = min(p[1] for p in transformed_points)
        mag_db_max   = max(p[1] for p in transformed_points)

        if freq_log_min == freq_log_max:
            return

        self.canvas.delete("all")
        w = int(self.canvas["width"])
        h = int(self.canvas["height"])
        padding = self.plot.padding
        plot_w = w - 2 * padding
        plot_h = h - 2 * padding

        # Axes
        self.canvas.create_line(padding, h - padding, w - padding, h - padding, fill="black")
        self.canvas.create_line(padding, padding, padding, h - padding, fill="black")

        def x_map(fl):
            return padding + (fl - freq_log_min) / (freq_log_max - freq_log_min) * plot_w

        def y_map(db):
            return (h - padding) - (db - mag_db_min) / (mag_db_max - mag_db_min) * plot_h

        # X-axis ticks
        num_x_ticks = 5
        for i in range(num_x_ticks + 1):
            fl_val = freq_log_min + i*(freq_log_max - freq_log_min)/num_x_ticks
            x_pos  = x_map(fl_val)
            freq_val = 10 ** fl_val
            self.canvas.create_line(x_pos, h - padding, x_pos, h - padding + 5, fill="black")
            self.canvas.create_text(x_pos, h - padding + 15, text=f"{freq_val:.0f}", anchor="n")

        # Y-axis ticks
        num_y_ticks = 6
        for i in range(num_y_ticks + 1):
            db_val = mag_db_min + i*(mag_db_max - mag_db_min)/num_y_ticks
            y_pos = y_map(db_val)
            self.canvas.create_line(padding - 5, y_pos, padding, y_pos, fill="black")
            self.canvas.create_text(padding - 10, y_pos, text=f"{db_val:.1f}", anchor="e")

        # Labels
        self.canvas.create_text(w // 2, h - 5, text="Frequency (Hz)",
                                anchor="s", font=("Arial", 12, "bold"))
        self.canvas.create_text(15, h // 2, text="Magnitude (dB)",
                                anchor="center", angle=90, font=("Arial", 12, "bold"))

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
        """Start impedance sweep, updating the plot in real time."""
        if not self.ad5933:
            messagebox.showerror("Error", "Not connected to I2C!")
            return

        self.reset_plot()
        try:
            start_freq = int(self.start_freq_var.get())
            if not 1000 <= start_freq <= 100000:
                messagebox.showerror("Error", "Start frequency must be between 1kHz and 100kHz")
                return
                
            freq_incr = int(self.freq_incr_var.get())
            if freq_incr <= 0:
                messagebox.showerror("Error", "Frequency increment must be positive")
                return
                
            num_points = int(self.num_points_var.get())
            if not 1 <= num_points <= 511:
                messagebox.showerror("Error", "Number of points must be between 1 and 511")
                return
                
            range_code = int(self.range_var.get())
            if not 1 <= range_code <= 4:
                messagebox.showerror("Error", "Range must be between 1 and 4")
                return
                
            pga_mode = bool(int(self.pga_gain_var.get()))
        except ValueError:
            messagebox.showerror("Error", "All inputs must be valid numbers")
            return

        # Optional temperature read before
        temp_before = self.ad5933.measure_temperature()
        if temp_before is not None:
            self.temp_label.config(text=f"Temp: {temp_before:.2f}°C")
        else:
            self.temp_label.config(text="Temp: ??? °C")

        try:
            gen = self.ad5933.sweep_generator(
                start_freq,
                freq_incr,
                num_points,
                pga_gain_x1=pga_mode,
                excitation_range_code=range_code
            )

            total_points = num_points + 1
            for i, (freq, real_val, imag_val, mag) in enumerate(gen):
                # collect data
                self.data_points.append((freq, real_val, imag_val, mag))

                # Update plot limits
                if freq < self.freq_min:
                    self.freq_min = freq
                if freq > self.freq_max:
                    self.freq_max = freq
                if mag < self.mag_min:
                    self.mag_min = mag
                if mag > self.mag_max:
                    self.mag_max = mag

                # Redraw
                self.redraw_plot()
                self.master.update_idletasks()

            # Optional temperature read after
            temp_after = self.ad5933.measure_temperature()
            if temp_after is not None:
                self.temp_label.config(text=f"Temp: {temp_after:.2f}°C")
            
            print("SWEEP_DONE")
        except Exception as e:
            messagebox.showerror("Sweep Error", f"Error during sweep: {str(e)}")
            raise

    def on_canvas_resize(self, event):
        """Handle canvas resize events so the plot scales on window resize."""
        try:
            w = max(event.width, 200)
            h = max(event.height, 200)

            print(f"Canvas resize event: width={w}, height={h}")
            print(f"Window size: {self.master.winfo_width()}x{self.master.winfo_height()}")
            print(f"Frame size: {self.main_frame.winfo_width()}x{self.main_frame.winfo_height()}")
            
            self.canvas.config(width=w, height=h)
            self.canvas.configure(scrollregion=(0, 0, w, h))

            self.canvas.update_idletasks()
            print(f"Post-update canvas size: {self.canvas.winfo_width()}x{self.canvas.winfo_height()}")
  
            if self.data_points:
                if self.plot.plot_type == 'bode':
                    self.redraw_bode_plot()
                elif self.plot.plot_type == 'phase':
                    self.redraw_phase_plot()
                else:
                    self.redraw_plot()
        except Exception as e:
            print(f"Canvas resize error: {str(e)}")
            import traceback
            traceback.print_exc()
