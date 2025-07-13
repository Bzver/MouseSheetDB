import tkinter as tk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class MousePedigree:
    def __init__(self, master, mouseDB):
        """
        Initializes the MousePedigree class, which is currently WIP.
        Args:
            master: The master Tkinter window.
            mouseDB: The mouse database object.
        """
        self.master = master
        self.mouseDB = mouseDB

    def display_family_tree_window(self):
        """
        Displays a new window for the mouse family tree. WIP
        """
        if hasattr(self, "family_tree_window") and self.family_tree_window.winfo_exists():
            self.family_tree_window.destroy()

        self.family_tree_window = tk.Toplevel(self.master)
        self.family_tree_window.title("Mice Pedigree Tree")

        fig, ax = plt.subplots(figsize=(8,6))
        ax.set_title("Mice Pedigree Tree")
        ax.axis("off")

        plt.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.family_tree_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

def add_to_family_tree(selected_mouse):
    """
    Adds a mouse(as in computer) selected mouse(as in rodent) to the family tree structure.
    Args:
        selected_mouse: The dictionary of selected_mouse, check mouse_artists in gui.
    """
    if selected_mouse is not None:
        selected_mouse["parentF"] = "Pending"
        selected_mouse["parentM"] = "Pending"