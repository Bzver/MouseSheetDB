import matplotlib.pyplot as plt
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class MousePedigree:
    def __init__(self, master, analyzer, mouseDB):
        self.master = master
        self.analyzer = analyzer
        self.mouseDB = mouseDB

    def display_family_tree_window(self, mouse_data):
        # WIP
        if hasattr(self, 'family_tree_window') and self.family_tree_window.winfo_exists():
            self.family_tree_window.destroy()

        self.family_tree_window = tk.Toplevel(self.master)
        self.family_tree_window.title("Mice Pedigree Sheet")

        fig, ax = plt.subplots(figsize=(8,6))
        ax.set_title("Mice Pedigree Sheet")
        ax.axis('off')

        plt.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.family_tree_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

def add_to_family_tree(selected_mouse):
    # WIP
    if selected_mouse is not None:
        selected_mouse['parentF'] = 'Pending'
        selected_mouse['parentM'] = 'Pending'