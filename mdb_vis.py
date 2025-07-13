import tkinter as tk
from tkinter import ttk

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as patches

import mdb_utils
import mdb_transfer

from collections import namedtuple

import warnings

class MouseVisualizer:
    def __init__(self, master, analyzer, mouseDB, sheet_name, canvas_widget):
        self.master = master
        self.analyzer = analyzer
        self.mouseDB = mouseDB
        self.sheet_name = sheet_name
        self.canvas_widget = canvas_widget

        MiceContainers = namedtuple("MiceContainers", ["regular", "waiting", "death"])
        self.mice_displayed = MiceContainers(
            regular={}, 
            waiting={}, 
            death={}
        )
        self.selected_mouse = None
        self.leaving_timer = None
        self.current_metadata_window = None
        self.mouse_artists = []
        self.last_hovered_mouse = None
        self.highlight_circle = None

        self.ax = None #
        self.mpl_canvas = None

        self.is_editing = False # New: Flag to indicate if an edit window is open
        self.edited_mouse_artist = None # New: Store the artist of the mouse being edited

        if self.canvas_widget:
            self.canvas_widget.destroy()
            plt.close('all')

    def plot_data(self):
        """Plot mouse count by genotype data."""
        genotypes, male_counts, female_counts, senile_counts = mdb_utils.calculate_genotype_counts(self.mouseDB, self.sheet_name)

        fig, axes = plt.subplots(1, 1, figsize=(8, 6))
        ax = axes
        ax.bar(genotypes, male_counts, label='♂', color='lightblue')
        ax.bar(genotypes, female_counts, bottom=male_counts, label='♀', color='lightpink')
        ax.bar(genotypes, senile_counts, bottom=[male_counts[j] + female_counts[j] for j in range(len(genotypes))], label='Senile', color='grey')

        for j, genotype in enumerate(genotypes):
            male_y = male_counts[j] / 2
            female_y = male_counts[j] + (female_counts[j] / 2)
            senile_y = male_counts[j] + female_counts[j] + (senile_counts[j] / 2)

            if male_counts[j] > 0:
                ax.text(genotype, male_y, str(male_counts[j]), ha='center', va='center', color='black')
            if female_counts[j] > 0:
                ax.text(genotype, female_y, str(female_counts[j]), ha='center', va='center', color='black')
            if senile_counts[j] > 0:
                ax.text(genotype, senile_y, str(senile_counts[j]), ha='center', va='center', color='black')

        ax.set_title(f"Genotype Counts in Sheet: {self.sheet_name}")
        ax.set_xlabel("Genotype")
        ax.set_ylabel("Number of Mice")
        ax.legend()
        labels = [label.get_text().replace('-P', '\nP') for label in ax.get_xticklabels()]
        ax.set_xticks(ax.get_xticks())
        ax.set_xticklabels(labels)

        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.master)
        canvas.draw()
        self.canvas_widget = canvas.get_tk_widget()
        self.canvas_widget.pack()
        return self.canvas_widget
    
    #########################################################################################################################

    def display_cage_monitor(self):
        """
        Displays the cage monitor visualization, using the 'nuCA' key for current cage location.
        Mice with 'nuCA' set to 'Waiting Room' or 'Death Row' are plotted in special areas.
        """
        if self.canvas_widget:
            self.canvas_widget.destroy()
            plt.close('all')

        fig, ax = plt.subplots(figsize=(10, 8))
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 8)
        ax.set_aspect('equal')
        ax.set_title(f"Cage Monitor - Sheet: {self.sheet_name}")
        ax.axis('off')

        self.mice_displayed.regular, self.mice_displayed.waiting, self.mice_displayed.death = mdb_utils.mice_count_for_monitor(self.mouseDB, self.sheet_name)

        # Use the regular_cage_data for calculating positions and plotting regular cages
        cage_positions = self._calculate_cage_positions(len(self.mice_displayed.regular))
        self.mouse_artists.clear()  # Clear existing artists

        # Draw cages and plot mice
        self._draw_cages(ax, self.mice_displayed.regular, cage_positions)
        self._plot_mice(ax, self.mice_displayed.regular, cage_positions) 
        self._draw_special_cages(ax)
        self.ax = ax # Store the axes object

        # Connect events to the figure
        fig.canvas.mpl_connect('motion_notify_event', lambda event: self.on_hover(event))
        fig.canvas.mpl_connect('button_press_event', lambda event: self.on_click(event))

        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.master)
        self.mpl_canvas = canvas # Store the FigureCanvasTkAgg object
        self.mpl_canvas.draw()
        self.canvas_widget = self.mpl_canvas.get_tk_widget()
        self.canvas_widget.pack()
        return self.canvas_widget

    def _draw_cages(self, ax, cage_data, cage_positions):
        # Draw regular cages
        for cage_index, (cage_no, mice) in enumerate(cage_data.items()):
            x, y = cage_positions[cage_index]

            # Check if any mouse in the cage has breedDays > 90
            cage_color = 'black' # Default color
            for mouse in mice:
                # Ensure breedDays is numeric, coercing errors to NaN
                breed_days = pd.to_numeric(mouse.get('breedDays'), errors='coerce')
                if pd.notna(breed_days) and breed_days > 90:
                    cage_color = 'red' # Change to red if any mouse has breedDays > 90
                    break # No need to check further if one such mouse is found
                
            cage_rect = patches.Rectangle((x - 0.8, y - 0.6), 1.6, 1.2, linewidth=1, edgecolor=cage_color, facecolor='none')
            ax.add_patch(cage_rect)
            cage_text = ax.text(x, y + 0.4, f"Cage: {cage_no}", ha='center', va='bottom', picker=True)
            cage_text.cage_no = cage_no  # Store cage_no for click event
            cage_text.set_picker(True)

    def _draw_cages(self, ax):
        # Waiting Room
        wr_x, wr_y, wr_width, wr_height = 8.5, 6.0, 2.5, 1.5 # Position and size for Waiting Room (moved to right edge)
        wr_rect = patches.Rectangle((wr_x - wr_width/2, wr_y - wr_height/2), wr_width, wr_height, linewidth=1, edgecolor='blue', facecolor='none')
        ax.add_patch(wr_rect)
        ax.text(wr_x, wr_y + wr_height/2 + 0.2, "Waiting Room", ha='center', va='bottom', color='blue', fontsize=12)
        # Pass values from the waiting_room_mice dictionary to _plot_mice_in_area
        self._plot_mice_in_area(ax, list(self.mice_displayed.waiting.values()), wr_x, wr_y, wr_width, wr_height)

        # Death Row
        dr_x, dr_y, dr_width, dr_height = 8.5, 3.0, 2.5, 1.5 # Position and size for Death Row (moved to right edge)
        dr_rect = patches.Rectangle((dr_x - dr_width/2, dr_y - dr_height/2), dr_width, dr_height, linewidth=1, edgecolor='purple', facecolor='none')
        ax.add_patch(dr_rect)
        ax.text(dr_x, dr_y + dr_height/2 + 0.2, "Death Row", ha='center', va='bottom', color='purple', fontsize=12)
        # Pass values from the death_row_mice dictionary to _plot_mice_in_area
        self._plot_mice_in_area(ax, list(self.mice_displayed.death.values()), dr_x, dr_y, dr_width, dr_height)

    def _calculate_cage_positions(self, num_cages):
        positions = []
        cols = 3  # Number of cages per row
        rows = (num_cages + cols - 1) // cols  # Calculate number of rows needed

        # Define the plotting area for regular cages
        x_min_reg = 0.5 # Left padding
        x_max_reg = 7.0 # Right boundary for regular cages
        y_min_reg = 0.5 # Bottom padding
        y_max_reg = 7.5 # Top boundary for regular cages

        # Calculate spacing for regular cages
        col_spacing = (x_max_reg - x_min_reg) / (cols + 1)
        row_spacing = (y_max_reg - y_min_reg) / (rows + 1)

        for i in range(num_cages):
            row = i // cols
            col = i % cols
            x = x_min_reg + (col + 1) * col_spacing
            y = y_max_reg - (row + 1) * row_spacing # Invert y-axis for better display
            positions.append((x, y))
        return positions

    def _plot_mice(self, ax, cage_data, cage_positions):
        # Plot mice in regular cages
        for cage_index, (cage_no, mice) in enumerate(cage_data.items()):
            x, y = cage_positions[cage_index]
            self._plot_mice_in_area(ax, mice, x, y, 1.6, 1.2) # Use cage dimensions for plotting area

    def _plot_mice_in_area(self, ax, mice, center_x, center_y, area_width, area_height):
        num_mice = len(mice)
        if num_mice == 0:
            return
        
        # Calculate positions within the given area
        max_cols = int(np.sqrt(num_mice)) + 1
        col_spacing = area_width / (max_cols + 1)
        row_spacing = area_height / ((num_mice + max_cols - 1) // max_cols + 1)

        for i, mouse in enumerate(mice):
            col = i % max_cols
            row = i // max_cols
            mx = center_x - (area_width / 2) + (col + 1) * col_spacing
            my = center_y + (area_height / 2) - (row + 1) * row_spacing
            sex = mouse.get('sex', 'N/A')
            age = mouse.get('age', None) # Use None for default age
            genotype = mouse.get('genotype', 'N/A')

            dot_color = mdb_utils.mice_dot_color_picker(sex, age)
            geno_text, geno_color = mdb_utils.genotype_abbreviation_color_picker(genotype)

            mouse_dot, = ax.plot(mx, my, marker='o', markersize=15, color=dot_color, picker=5)
            ax.text(mx, my, geno_text, ha='center', va='center', color=geno_color, fontsize=14)
            self.mouse_artists.append((mouse_dot, mouse))

    #########################################################################################################################

    def on_hover(self, event):
        if event.inaxes and event.xdata is not None and event.ydata is not None and not self.is_editing:
            # Check all mouse artists
            for artist, mouse in self.mouse_artists:
                if artist.contains(event)[0]:
                    # Cancel pending close timer if exists
                    if self.leaving_timer:
                        self.master.after_cancel(self.leaving_timer)
                        self.leaving_timer = None

                    # Skip if same mouse is already highlighted
                    if (self.last_hovered_mouse and 
                        self.last_hovered_mouse.get('ID') == mouse.get('ID')):
                        return

                    # Clear existing window and highlight
                    if self.current_metadata_window:
                        self.current_metadata_window.destroy()
                    if self.highlight_circle:
                        self.highlight_circle.remove()
                    
                    # Create new highlight
                    x, y = artist.get_xdata()[0], artist.get_ydata()[0]
                    self.highlight_circle = patches.Circle((x, y), radius=0.2, color='red', fill=False, linewidth=2)
                    self.ax.add_patch(self.highlight_circle)
                    self.mpl_canvas.draw_idle()

                    # Show metadata window
                    self._show_metadata_window(mouse)
                    self.last_hovered_mouse = mouse
                    return

            self.schedule_close_metadata_window()

    def schedule_close_metadata_window(self):
        if self.current_metadata_window and not self.leaving_timer:
            self.leaving_timer = self.master.after(100, self.close_metadata_window)

    def close_metadata_window(self):
        """Close metadata window and clear highlights, unless in editing mode."""
        if self.is_editing:
            # If in editing mode, only destroy the metadata window, but keep the highlight
            if self.current_metadata_window:
                self.current_metadata_window.destroy()
                self.current_metadata_window = None
            return # Do not clear highlight or last_hovered_mouse

        if self.current_metadata_window:
            self.current_metadata_window.destroy()
            self.current_metadata_window = None
        if self.highlight_circle:
            self.highlight_circle.remove()
            self.highlight_circle = None
            self.mpl_canvas.draw_idle()
        self.last_hovered_mouse = None
        self.leaving_timer = None

    def set_editing_state(self, is_editing, mouse_id=None):
        """
        Sets the editing state and manages the highlight and metadata window.
        If is_editing is True, the highlight for the specified mouse_id will persist.
        If is_editing is False, the highlight and metadata window will be cleared.
        """
        self.is_editing = is_editing
        if is_editing and mouse_id:
            # Find the artist for the edited mouse and ensure it's highlighted
            for artist, mouse in self.mouse_artists:
                if mouse.get('ID') == mouse_id:
                    self.edited_mouse_artist = artist
                    # Ensure highlight is drawn
                    if self.highlight_circle:
                        self.highlight_circle.remove()
                    x, y = artist.get_xdata()[0], artist.get_ydata()[0]
                    self.highlight_circle = patches.Circle((x, y), radius=0.2,
                                                           color='red', fill=False, linewidth=2)
                    self.ax.add_patch(self.highlight_circle)
                    self.mpl_canvas.draw_idle()
                    if self.current_metadata_window:
                        self.current_metadata_window.destroy()
                        self.current_metadata_window = None
                    break
        else:
            # If not editing, clear any persistent highlight and metadata window
            if self.highlight_circle:
                self.highlight_circle.remove()
                self.highlight_circle = None
            if self.current_metadata_window:
                self.current_metadata_window.destroy()
                self.current_metadata_window = None
            self.edited_mouse_artist = None
            self.last_hovered_mouse = None
            self.mpl_canvas.draw_idle()

    #########################################################################################################################

    def _show_metadata_window(self, mouse):
        if self.current_metadata_window:
            self.current_metadata_window.destroy()

        sex = mouse.get('sex', 'N/A')
        toe = mouse.get('toe', 'N/A')
        age = mouse.get('age', 'N/A')
        genotype = mouse.get('genotype', 'N/A')
        mouseID = mouse.get('ID', 'N/A')

        if len(genotype) < 15:
            genotype = genotype.center(25,' ') # Padded the short genotype for a centered look
        
        metadata_window = tk.Toplevel(self.master)
        metadata_window.title("Mouse Metadata")
        metadata_window.geometry("+100+100")

        style = ttk.Style()
        style.configure("Metadata.TLabel", font=("Arial", 9), padding=5)
        separ_geno = '------GENOTYPE------'
        separ_ID = '------------I-D------------'
        message = (f"Sex: {sex}   Toe: {toe}\nAge: {age}d ({int(age) // 7}w{int(age) % 7}d)\n{separ_geno}\n{genotype}\n{separ_ID}\n{mouseID}")
        label = ttk.Label(metadata_window, text=message, style="Metadata.TLabel")
        label.pack(padx=10, pady=10)

        self.current_metadata_window = metadata_window

    def on_click(self, event):
        if event.button == 1 and event.inaxes:
            for artist, mouse in self.mouse_artists:
                if artist.contains(event)[0]:
                    self.selected_mouse = mouse
                    self.show_context_menu(event)
                    return
                
    def show_context_menu(self, event):
        menu = tk.Menu(self.master, tearoff=0)

        # Check if the selected mouse is in the waiting room
        is_in_waiting_room = self.selected_mouse.get('nuCA') == 'Waiting Room'
        is_on_death_row = self.selected_mouse.get('nuCA') == 'Death Row'

        menu.add_command(label="Edit mouse entry", command=self.analyzer.edit_mouse_entries)
        menu.add_command(label="Add to pedigree graph", command=self.add_to_family_tree)

        if is_on_death_row:
            menu.add_command(label="Release from Death Row", command=mdb_transfer.transfer_from_death_row)
        else:
            menu.add_command(label="Transfer to current cages", command=mdb_transfer.transfer_to_existing_cage)
            menu.add_command(label="Transfer to Death Row", command=mdb_transfer.transfer_to_death_row)
            if is_in_waiting_room:
                menu.add_command(label="Transfer to a new cage", command=mdb_transfer.transfer_to_new_cage)
            else: # in reguular cages
                menu.add_command(label="Transfer to waiting room", command=mdb_transfer.transfer_to_waiting_room)

        try:
            # Display the menu at the mouse click position using Tkinter's pointer coordinates
            menu.tk_popup(self.master.winfo_pointerx(), self.master.winfo_pointery())
        finally:
            menu.grab_release()

    #########################################################################################################################

    def add_to_family_tree(self):
        # WIP
        if self.selected_mouse is not None:
            self.selected_mouse['parentF'] = 'Pending'
            self.selected_mouse['parentM'] = 'Pending'

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
        
warnings.simplefilter(action="ignore",category=FutureWarning)