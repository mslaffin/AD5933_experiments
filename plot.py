# plot.py

import math
import tkinter as tk

class Plot:
    def __init__(self, canvas):
        self.canvas = canvas
        self.show_grid = False
        self.plot_type = 'linear'  # 'linear', 'bode', or 'phase'
        self.padding = 80

        self.configure_canvas()
        
    def configure_canvas(self):
        """Set up canvas bindings and scrolling"""
        self.canvas.bind('<Configure>', lambda e: self.redraw())

        # Add zoom bindings (for systems that support <Button-4> and <Button-5>)
        self.canvas.bind('<Button-4>', self.zoom_in)   # Mouse wheel up
        self.canvas.bind('<Button-5>', self.zoom_out)  # Mouse wheel down
        
    def toggle_grid(self):
        self.show_grid = not self.show_grid
        self.redraw()
        
    def draw_grid(self, w, h):
        """Draw grid lines"""
        if not self.show_grid:
            return
            
        # Draw vertical grid lines
        step_x = (w - 2*self.padding) / 10
        for x in range(self.padding, w - self.padding, int(step_x)):
            self.canvas.create_line(x, self.padding, x, h - self.padding,
                                    fill='lightgray', dash=(2,2))
                                  
        # Draw horizontal grid lines
        step_y = (h - 2*self.padding) / 10
        for y in range(self.padding, h - self.padding, int(step_y)):
            self.canvas.create_line(self.padding, y, w - self.padding, y,
                                    fill='lightgray', dash=(2,2))

    def redraw(self):
        """Trigger appropriate redraw based on plot type"""
        # We rely on the canvas's master's redraw methods
        if hasattr(self.canvas, 'redraw_plot'):
            # If you previously assigned a method to canvas, do so. Otherwise:
            if self.plot_type == 'bode':
                self.canvas.master.redraw_bode_plot()
            elif self.plot_type == 'phase':
                self.canvas.master.redraw_phase_plot()
            else:
                self.canvas.master.redraw_plot()

    def zoom_in(self, event):
        """Handle zoom in event (mouse wheel up)"""
        factor = 0.9
        self.calculate_zoom(factor)
        self.redraw()

    def zoom_out(self, event):
        """Handle zoom out event (mouse wheel down)"""
        factor = 1.1
        self.calculate_zoom(factor)
        self.redraw()

    def calculate_zoom(self, factor):
        """Recalculate plot range based on zoom factor"""
        # We store ranges in the canvas.master (the AD5933GUI instance)
        x_range = self.canvas.master.freq_max - self.canvas.master.freq_min
        y_range = self.canvas.master.mag_max - self.canvas.master.mag_min
        
        new_x_range = x_range * factor
        new_y_range = y_range * factor
        
        x_center = (self.canvas.master.freq_max + self.canvas.master.freq_min) / 2
        y_center = (self.canvas.master.mag_max + self.canvas.master.mag_min) / 2
        
        self.canvas.master.freq_min = x_center - new_x_range / 2
        self.canvas.master.freq_max = x_center + new_x_range / 2
        self.canvas.master.mag_min = y_center - new_y_range / 2
        self.canvas.master.mag_max = y_center + new_y_range / 2
