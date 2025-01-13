# main.py

import tkinter as tk
from gui import AD5933GUI

def main():
    root = tk.Tk()
    root.title("AD5933 Impedance Analyzer")
    root.minsize(600, 400)
    
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    
    app = AD5933GUI(root)
    
    root.geometry('800x600')
    root.mainloop()

if __name__ == "__main__":
    main()