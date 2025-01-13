import math
import tkinter as tk

class Plot:
    def __init__(self, canvas):
        self.canvas = canvas
        self.show_grid = False
        self.plot_type = 'linear'  # 'linear', 'bode', 'phase', 'ohms', 'gain_phase'
        self.padding = 80
        self.subplot_spacing = 30  # Space between subplots
        
        # For gain/phase subplot
        self.gain_height_ratio = 0.5  # Top plot takes 50% of height
        
        self.configure_canvas()
        
    def configure_canvas(self):
        """Set up canvas bindings and scrolling"""
        self.canvas.bind('<Button-4>', self.zoom_in)   # Linux mouse wheel up
        self.canvas.bind('<Button-5>', self.zoom_out)  # Linux mouse wheel down
        self.canvas.bind('<MouseWheel>', self._handle_mousewheel)  # Windows/Mac
        
    def _handle_mousewheel(self, event):
        """Handle mousewheel events for Windows/Mac"""
        if event.delta > 0:
            self.zoom_in(event)
        else:
            self.zoom_out(event)
            
    def toggle_grid(self):
        """Toggle grid visibility"""
        self.show_grid = not self.show_grid
        self.redraw()
        
    def draw_grid(self, x_start, y_start, width, height):
        """Draw grid lines for a subplot region"""
        if not self.show_grid:
            return
            
        # Vertical grid lines
        step_x = width / 10
        for x in range(int(x_start), int(x_start + width), int(step_x)):
            self.canvas.create_line(x, y_start, x, y_start + height,
                                  fill='lightgray', dash=(2,2))
                                  
        # Horizontal grid lines
        step_y = height / 10
        for y in range(int(y_start), int(y_start + height), int(step_y)):
            self.canvas.create_line(x_start, y, x_start + width, y,
                                  fill='lightgray', dash=(2,2))

    def draw_gain_phase_plot(self):
        """Draw combined gain and phase plot"""
        if len(self.canvas.master.data_points) < 2:
            return

        self.canvas.delete("all")
        w = int(self.canvas["width"])
        h = int(self.canvas["height"])
        
        # Calculate subplot dimensions
        gain_height = (h - 2*self.padding - self.subplot_spacing) * self.gain_height_ratio
        phase_height = h - 2*self.padding - self.subplot_spacing - gain_height
        plot_width = w - 2*self.padding
        
        # Process data
        gain_data = []
        phase_data = []
        for freq, real, imag, mag in self.canvas.master.data_points:
            phase = math.degrees(math.atan2(imag, real))
            impedance = 1 / (mag * 1e-5)  # Example gain factor
            gain_data.append((freq, impedance))
            phase_data.append((freq, phase))
        
        # Calculate ranges
        freq_min = min(p[0] for p in gain_data)
        freq_max = max(p[0] for p in gain_data)
        gain_min = min(p[1] for p in gain_data)
        gain_max = max(p[1] for p in gain_data)
        phase_min = min(p[1] for p in phase_data)
        phase_max = max(p[1] for p in phase_data)
        
        # Draw gain subplot
        self._draw_subplot(
            self.padding, self.padding, plot_width, gain_height,
            gain_data, freq_min, freq_max, gain_min, gain_max,
            "Impedance (Ω)", "blue"
        )
        
        # Draw phase subplot
        self._draw_subplot(
            self.padding, self.padding + gain_height + self.subplot_spacing,
            plot_width, phase_height,
            phase_data, freq_min, freq_max, phase_min, phase_max,
            "Phase (degrees)", "green"
        )
        
        # X-axis label (only on bottom subplot)
        self.canvas.create_text(
            w // 2, h - 10,
            text="Frequency (Hz)",
            anchor="s",
            font=("Arial", 12, "bold")
        )

    def _draw_subplot(self, x, y, width, height, data, x_min, x_max, y_min, y_max, y_label, color):
        """Helper method to draw a single subplot"""
        # Draw grid if enabled
        self.draw_grid(x, y, width, height)
        
        # Draw axes
        self.canvas.create_line(x, y + height, x + width, y + height, fill="black", width=2)
        self.canvas.create_line(x, y, x, y + height, fill="black", width=2)
        
        # Mapping functions
        def map_x(val):
            return x + (val - x_min) / (x_max - x_min) * width
            
        def map_y(val):
            return y + height - (val - y_min) / (y_max - y_min) * height
            
        # Draw ticks and labels
        self._draw_ticks(x, y, width, height, x_min, x_max, y_min, y_max)
        
        # Y-axis label
        self.canvas.create_text(
            x - 60, y + height/2,
            text=y_label,
            anchor="center",
            angle=90,
            font=("Arial", 10, "bold")
        )
        
        # Plot data points
        prev_x = prev_y = None
        for freq, val in data:
            plot_x = map_x(freq)
            plot_y = map_y(val)
            
            self.canvas.create_oval(
                plot_x-2, plot_y-2, plot_x+2, plot_y+2,
                fill=color, outline=color
            )
            
            if prev_x is not None:
                self.canvas.create_line(
                    prev_x, prev_y, plot_x, plot_y,
                    fill=color, width=1
                )
            prev_x, prev_y = plot_x, plot_y

    def _draw_ticks(self, x, y, width, height, x_min, x_max, y_min, y_max):
        """Draw tick marks and labels for a subplot"""
        # X-axis ticks
        num_x_ticks = 5
        for i in range(num_x_ticks + 1):
            x_val = x_min + (x_max - x_min) * i / num_x_ticks
            tick_x = x + width * i / num_x_ticks
            self.canvas.create_line(
                tick_x, y + height,
                tick_x, y + height + 5,
                fill="black"
            )
            self.canvas.create_text(
                tick_x, y + height + 15,
                text=f"{x_val:.0f}",
                anchor="n"
            )
            
        # Y-axis ticks
        num_y_ticks = 5
        for i in range(num_y_ticks + 1):
            y_val = y_min + (y_max - y_min) * i / num_y_ticks
            tick_y = y + height - height * i / num_y_ticks
            self.canvas.create_line(
                x - 5, tick_y,
                x, tick_y,
                fill="black"
            )
            self.canvas.create_text(
                x - 10, tick_y,
                text=f"{y_val:.1f}",
                anchor="e"
            )

    def redraw(self):
        """Trigger appropriate redraw based on plot type"""
        if self.plot_type == 'gain_phase':
            self.draw_gain_phase_plot()
        elif self.plot_type == 'ohms':
            self.canvas.master.redraw_ohms_plot()
        elif self.plot_type == 'bode':
            self.canvas.master.redraw_bode_plot()
        elif self.plot_type == 'phase':
            self.canvas.master.redraw_phase_plot()
        else:
            self.canvas.master.redraw_plot()

    def zoom_in(self, event):
        """Handle zoom in event"""
        self._zoom(0.9, event)

    def zoom_out(self, event):
        """Handle zoom out event"""
        self._zoom(1.1, event)

    def _zoom(self, factor, event):
        """Calculate and apply zoom"""
        if not hasattr(self.canvas.master, 'freq_min'):
            return
            
        # Get current ranges
        x_range = self.canvas.master.freq_max - self.canvas.master.freq_min
        y_range = self.canvas.master.mag_max - self.canvas.master.mag_min
        
        # Calculate new ranges
        new_x_range = x_range * factor
        new_y_range = y_range * factor
        
        # Update maintaining center point
        x_center = (self.canvas.master.freq_max + self.canvas.master.freq_min) / 2
        y_center = (self.canvas.master.mag_max + self.canvas.master.mag_min) / 2
        
        self.canvas.master.freq_min = x_center - new_x_range / 2
        self.canvas.master.freq_max = x_center + new_x_range / 2
        self.canvas.master.mag_min = y_center - new_y_range / 2
        self.canvas.master.mag_max = y_center + new_y_range / 2
        
        self.redraw()