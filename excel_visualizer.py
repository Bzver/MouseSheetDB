import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as patches

import warnings

class MouseVisualizer:
    def __init__(self, master, analyzer, mouseDB, sheet_name, canvas_widget, update_callback):
        self.master = master
        self.analyzer = analyzer # Store analyzer instance
        self.mouseDB = mouseDB
        self.sheet_name = sheet_name
        self.canvas_widget = canvas_widget
        self.update_callback = update_callback # Callback for updating the main DataFrame in analyzer

        self.mouse_artists = []
        self.regular_cage_mice = {}
        self.waiting_room_mice = {}
        self.death_row_mice = {}
        self.current_metadata_window = None
        self.last_hovered_mouse = None
        self.highlight_circle = None
        self.ax = None #
        self.mpl_canvas = None
        self.selected_mouse = None
        self.leaving_timer = None
        self.is_editing = False # New: Flag to indicate if an edit window is open
        self.edited_mouse_artist = None # New: Store the artist of the mouse being edited

        if self.canvas_widget:
            self.canvas_widget.destroy()
            plt.close('all')

    #########################################################################################################################

    def plot_data(self):
        """Plot mouse count by genotype data."""
        genotypes, male_counts, female_counts, senile_counts = self.calculate_genotype_counts()

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

    def calculate_genotype_counts(self):
        genotypes = []
        male_counts = []
        female_counts = []
        senile_counts = []
        
        for mouse_info in self.mouseDB.values():
            # Only consider mice in the current sheet for genotype counts
            if mouse_info['sheet'] == self.sheet_name and mouse_info['genotype'] not in genotypes:
                genotypes.append(mouse_info['genotype'])
        
        for genotype in genotypes:
            males = sum(1 for mouse_info in self.mouseDB.values()
                            if mouse_info['genotype'] == genotype
                            and mouse_info['sheet'] == self.sheet_name # Ensure sheet is current sheet
                            and mouse_info['sex'] == '♂'
                            and mouse_info['age'] <= 300)
            females = sum(1 for mouse_info in self.mouseDB.values()
                                if mouse_info['genotype'] == genotype
                                and mouse_info['sheet'] == self.sheet_name # Ensure sheet is current sheet
                                and mouse_info['sex'] == '♀'
                                and mouse_info['age'] <= 300)
            seniles = sum(1 for mouse_info in self.mouseDB.values()
                            if mouse_info['genotype'] == genotype
                            and mouse_info['sheet'] == self.sheet_name # Ensure sheet is current sheet
                            and mouse_info['age'] > 300)
            male_counts.append(males)
            female_counts.append(females)
            senile_counts.append(seniles)
        
        return genotypes, male_counts, female_counts, senile_counts
    
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

        self.regular_cage_mice = {}
        self.waiting_room_mice = {}
        self.death_row_mice = {}

        for mouse_info in self.mouseDB.values():
            cage_key = mouse_info['nuCA']
            ID = mouse_info['ID'] # Always get ID

            # Re-populate based on the 'sheet' and 'nuCA' fields in mouse_info
            if mouse_info['sheet'] == self.sheet_name and mouse_info['nuCA'] not in ['Waiting Room', 'Death Row']:
                if cage_key not in self.regular_cage_mice:
                    self.regular_cage_mice[cage_key] = []
                self.regular_cage_mice[cage_key].append(mouse_info)
            elif mouse_info['nuCA'] == 'Waiting Room':
                # Store the mouse dictionary directly under its ID
                self.waiting_room_mice[ID] = mouse_info 
            elif mouse_info['nuCA'] == 'Death Row':
                # Store the mouse dictionary directly under its ID
                self.death_row_mice[ID] = mouse_info

        # Use the regular_cage_data for calculating positions and plotting regular cages
        cage_positions = self.calculate_cage_positions(len(self.regular_cage_mice))
        self.mouse_artists.clear()  # Clear existing artists

        # Draw cages and plot mice
        self.draw_cages(ax, self.regular_cage_mice, cage_positions)
        self.plot_mice(ax, self.regular_cage_mice, cage_positions) 
        self.draw_special_cages(ax)
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

    def draw_cages(self, ax, cage_data, cage_positions):
        """
        Draws the regular cages on the monitor based on the provided cage_data.
        """
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

    def draw_special_cages(self, ax):
        # Waiting Room
        wr_x, wr_y, wr_width, wr_height = 8.5, 6.0, 2.5, 1.5 # Position and size for Waiting Room (moved to right edge)
        wr_rect = patches.Rectangle((wr_x - wr_width/2, wr_y - wr_height/2), wr_width, wr_height, linewidth=1, edgecolor='blue', facecolor='none')
        ax.add_patch(wr_rect)
        ax.text(wr_x, wr_y + wr_height/2 + 0.2, "Waiting Room", ha='center', va='bottom', color='blue', fontsize=12)
        # Pass values from the waiting_room_mice dictionary to _plot_mice_in_area
        self._plot_mice_in_area(ax, list(self.waiting_room_mice.values()), wr_x, wr_y, wr_width, wr_height)

        # Death Row
        dr_x, dr_y, dr_width, dr_height = 8.5, 3.0, 2.5, 1.5 # Position and size for Death Row (moved to right edge)
        dr_rect = patches.Rectangle((dr_x - dr_width/2, dr_y - dr_height/2), dr_width, dr_height, linewidth=1, edgecolor='purple', facecolor='none')
        ax.add_patch(dr_rect)
        ax.text(dr_x, dr_y + dr_height/2 + 0.2, "Death Row", ha='center', va='bottom', color='purple', fontsize=12)
        # Pass values from the death_row_mice dictionary to _plot_mice_in_area
        self._plot_mice_in_area(ax, list(self.death_row_mice.values()), dr_x, dr_y, dr_width, dr_height)

    def calculate_cage_positions(self, num_cages):
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

    def plot_mice(self, ax, cage_data, cage_positions):
        """
        Plots the mice within their respective regular cages based on the provided cage_data.
        """
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

            # Determine dot color based on age and sex
            if age is not None and age > 300:
                color = 'grey'
            else:
                color = 'lightblue' if sex == '♂' else 'lightpink'

            # Determine genotype abbreviation and color
            geno_text = ""
            geno_color = 'black'
            valid_identifier = False

            # Define genotype components we're looking for
            target_components = {
                'CMV-CRE': 'C',
                'NEX-CRE': 'N',
                'wt': 'wt',
                'hom-PP2A': ('P', 'gold'),
                'PP2A(f/w)': ('P', 'olivedrab'),
                'PP2A(w/-)': ('P', 'chocolate'),
                'PP2A': 'P', # PP2A fallback
            }

            # Process genotype string
            for component, marker in target_components.items():
                if component in genotype:
                    valid_identifier = True
                    if component == 'wt':  # wt overrides other markers
                        geno_text = 'wt'
                        geno_color = 'black'
                        break
                    elif isinstance(marker, tuple):  # Special PP2A cases with colors
                        geno_text += marker[0]
                        geno_color = marker[1]
                    else:  # Simple markers
                        if component != 'PP2A' and marker not in geno_text:  # Avoid duplicates
                            geno_text += marker
                        if component == 'PP2A' and not any(x in genotype for x in ['hom-','(f/w)','w/-']): # Avoid duplicates for PP2A
                            geno_text += marker

            # Handle invalid genotypes
            if not valid_identifier:
                geno_text = "?"
                geno_color = 'red'
            elif not geno_text:
                geno_text = "?"
                geno_color = 'red'

            # Ensure wt is clean (no additional letters)
            if geno_text == 'wt':
                geno_color = 'black'

            mouse_dot, = ax.plot(mx, my, marker='o', markersize=15, color=color, picker=5)
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
        """Schedule metadata window to close after delay"""
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
        """Displays the metadata window for a given mouse."""
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

        if not is_in_waiting_room and not is_on_death_row:
            menu.add_command(label="Transfer to current cages", command=self.transfer_to_existing_cage)
            menu.add_command(label="Transfer to waiting room", command=self.transfer_to_waiting_room)
            menu.add_command(label="Transfer to Death Row", command=self.transfer_to_death_row)
        elif is_in_waiting_room:
            menu.add_command(label="Transfer to current cages", command=self.transfer_from_waiting_room)
            menu.add_command(label="Transfer to a new cage", command=self.transfer_to_new_cage)
            menu.add_command(label="Transfer to Death Row", command=self.transfer_to_death_row)
        else: # is_on_death_row
            menu.add_command(label="Release from Death Row", command=self.transfer_from_death_row)
            
        try:
            # Display the menu at the mouse click position using Tkinter's pointer coordinates
            menu.tk_popup(self.master.winfo_pointerx(), self.master.winfo_pointery())
        finally:
            menu.grab_release()

    #########################################################################################################################

    def add_to_family_tree(self):
        # 2 B implemented
        pass

    def display_family_tree_window(self):
        # Dummy function for now
        if hasattr(self, 'family_tree_window') and self.family_tree_window.winfo_exists():
            self.family_tree_window.destroy()

        self.family_tree_window = tk.Toplevel(self.master)
        self.family_tree_window.title("Mice Pedigree Sheet")

        fig, ax = plt.subplots(figsize=(5, 4))
        ax.set_xlim(0, 5)
        ax.set_ylim(0, 4)
        ax.set_aspect('equal')
        ax.set_title("Mice Pedigree Sheet")
        ax.axis('off')

        plt.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.family_tree_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    #########################################################################################################################

    def transfer_to_existing_cage(self):
        if self.selected_mouse is not None:
            dialog = tk.Toplevel(self.master)
            dialog.title("Select Target Cage")
            dialog.transient(self.master) # Make it a transient window
            dialog.grab_set() # Make it modal
            dialog.geometry("+100+300")

            tk.Label(dialog, text="Select a cage:").pack(pady=10)

            current_cage = self.selected_mouse.get('nuCA')
            # Filter out the current cage from the list of existing cages
            existing_cages = sorted([c for c in self.regular_cage_mice.keys() if c != current_cage])

            if not existing_cages:
                messagebox.showinfo("No Cages", "No other existing cages available for transfer.")
                dialog.destroy()
                return

            self.selected_target_cage = tk.StringVar(dialog)
            self.selected_target_cage.set(existing_cages[0]) # Set initial value

            cage_dropdown = ttk.Combobox(dialog, textvariable=self.selected_target_cage, values=existing_cages, state="readonly")
            cage_dropdown.pack(pady=5)

            def confirm_transfer():
                taCA = self.selected_target_cage.get()
                if self.selected_mouse is not None:
                    # Remove from previous list if it was a regular cage mouse
                    # Iterate through items to find the list that contains the selected mouse
                    for cage_key, mice_list in self.regular_cage_mice.items():
                        if self.selected_mouse in mice_list:
                            mice_list.remove(self.selected_mouse)
                            # If the list becomes empty, remove the cage entry
                            if not mice_list:
                                del self.regular_cage_mice[cage_key]
                            break
                    # Remove from waiting room if it came from there
                    if self.selected_mouse['ID'] in self.waiting_room_mice:
                        del self.waiting_room_mice[self.selected_mouse['ID']]
                    # Remove from death row if it came from there
                    if self.selected_mouse['ID'] in self.death_row_mice:
                        del self.death_row_mice[self.selected_mouse['ID']]

                    self.selected_mouse['nuCA'] = taCA
                    # Ensure the sheet name is correctly updated for the mouse based on its new cage
                    if str(taCA).startswith('8-A-'):
                        self.selected_mouse['sheet'] = 'CMV + PP2A'
                    elif str(taCA).startswith('2-A-'):
                        self.selected_mouse['sheet'] = 'NEX + PP2A'
                    else:
                        self.selected_mouse['sheet'] = 'BACKUP'

                    # Add to the target regular cage
                    if taCA not in self.regular_cage_mice:
                        self.regular_cage_mice[taCA] = []
                    self.regular_cage_mice[taCA].append(self.selected_mouse)
                    
                    self.update_callback() # Call the callback to update the database
                self.analyzer.redraw_canvas()
                self.close_metadata_window()
                dialog.destroy()

            tk.Button(dialog, text="Transfer", command=confirm_transfer).pack(pady=10)
            dialog.wait_window(dialog) # Wait for the dialog to close
        self.analyzer.redraw_canvas()
        self.close_metadata_window()

    def transfer_to_waiting_room(self):
        if self.selected_mouse is not None:
            # Remove from previous regular cage if it was there
            for cage_key, mice_list in self.regular_cage_mice.items():
                if self.selected_mouse in mice_list:
                    mice_list.remove(self.selected_mouse)
                    if not mice_list: # If cage becomes empty, remove it
                        del self.regular_cage_mice[cage_key]
                    break
            # Remove from death row if it was there
            if self.selected_mouse['ID'] in self.death_row_mice:
                del self.death_row_mice[self.selected_mouse['ID']]

            self.selected_mouse['nuCA'] = 'Waiting Room'
            self.selected_mouse['sheet'] = 'Waiting Room'
            self.waiting_room_mice[self.selected_mouse['ID']] = self.selected_mouse # Store the mouse directly
            self.update_callback() # Call the callback to update the database
        self.analyzer.redraw_canvas()
        self.close_metadata_window()

    def transfer_from_waiting_room(self):
        if self.selected_mouse is not None:
            dialog = tk.Toplevel(self.master)
            dialog.title("Select Target Cage")
            dialog.transient(self.master) # Make it a transient window
            dialog.grab_set() # Make it modal
            dialog.geometry("+100+300")

            tk.Label(dialog, text="Select a cage:").pack(pady=10)

            # Only show cages relevant to the current sheet
            existing_cages = sorted([c for c in self.regular_cage_mice.keys() if c is not None])

            if not existing_cages:
                messagebox.showinfo("No Cages", "No existing cages available for transfer. Please create a new cage.")
                dialog.destroy()
                return

            self.selected_target_cage = tk.StringVar(dialog)
            self.selected_target_cage.set(existing_cages[0]) # Set initial value

            cage_dropdown = ttk.Combobox(dialog, textvariable=self.selected_target_cage, values=existing_cages, state="readonly")
            cage_dropdown.pack(pady=5)

            def confirm_transfer():
                taCA = self.selected_target_cage.get()
                if self.selected_mouse is not None:
                    # Remove from waiting room
                    if self.selected_mouse['ID'] in self.waiting_room_mice:
                        del self.waiting_room_mice[self.selected_mouse['ID']]
                    # Remove from death row if it came from there (safety check)
                    if self.selected_mouse['ID'] in self.death_row_mice:
                        del self.death_row_mice[self.selected_mouse['ID']]

                    self.selected_mouse['nuCA'] = taCA
                    # Set the sheet back based on the cage number if applicable
                    if str(taCA).startswith('8-A-'):
                        self.selected_mouse['sheet'] = 'CMV + PP2A'
                    elif str(taCA).startswith('2-A-'):
                        self.selected_mouse['sheet'] = 'NEX + PP2A'
                    else:
                        self.selected_mouse['sheet'] = 'BACKUP'

                    # Add to the target regular cage
                    if taCA not in self.regular_cage_mice:
                        self.regular_cage_mice[taCA] = []
                    self.regular_cage_mice[taCA].append(self.selected_mouse)
                    
                    self.update_callback() # Call the callback to update the database
                self.analyzer.redraw_canvas()
                self.close_metadata_window()
                dialog.destroy()

            tk.Button(dialog, text="Transfer", command=confirm_transfer).pack(pady=10)
            dialog.wait_window(dialog) # Wait for the dialog to close
        self.analyzer.redraw_canvas()
        self.close_metadata_window()

    def transfer_to_new_cage(self):
        if self.selected_mouse is not None:
            dialog = tk.Toplevel(self.master)
            dialog.title("Enter New Cage Number")
            dialog.transient(self.master) # Make it a transient window
            dialog.grab_set() # Make it modal
            dialog.geometry("+100+300")

            tk.Label(dialog, text="Enter the new cage number:").pack(pady=10)

            prefix = ""
            if self.sheet_name == "NEX + PP2A":
                prefix = "2-A-"
            elif self.sheet_name == "CMV + PP2A":
                prefix = "8-A-"

            prefix_label = tk.Label(dialog, text=prefix)
            prefix_label.pack(side=tk.LEFT, padx=(10, 0))

            new_cage_entry = tk.Entry(dialog)
            new_cage_entry.pack(side=tk.LEFT, padx=(0, 10))
            new_cage_entry.focus_set() # Set focus to the entry widget

            def validate_and_transfer():
                entered_name = new_cage_entry.get().strip()
                
                if not entered_name:
                    messagebox.showwarning("Invalid Input", "Please enter the cage number.", parent=dialog)
                    return
                if not entered_name[0].isdigit() or not entered_name[-1].isdigit():
                    messagebox.showwarning("Invalid Input", "Must start and end with digits.", parent=dialog)
                    return
                
                if self.sheet_name == 'BACKUP':
                    if '-B-' in entered_name:
                        prefix = entered_name.split("-B-")[0]
                        entered_suffix = entered_name.split("-B-")[1]
                    else:
                        entered_suffix = entered_name
                else: entered_suffix = entered_name

                digits_only = entered_suffix.replace("-","")

                if len(digits_only) == 0:
                    messagebox.showwarning("Invalid Input", "Must include at least one digit sans prefix.", parent=dialog)
                    return
                if not digits_only.isdigit():
                    messagebox.showwarning("Invalid Input", "Only numbers and '-' are allowed sans prefix.", parent=dialog)
                    return 
                if len(digits_only) > 4:
                    messagebox.showwarning("Invalid Input", "Can only include four digits at most sans prefix.", parent=dialog)
                    return
                
                new_cage_no = prefix + entered_suffix
                
                # Check if the new cage number already exists in regular cages
                if new_cage_no in self.regular_cage_mice: # Check if key exists in the dict
                    messagebox.showwarning("Cage Exists", f"Cage '{new_cage_no}' already exists. Please enter a different number.", parent=dialog)
                    new_cage_entry.delete(0, tk.END) # Clear the entry
                    return
                
                # Check if the new cage number fits the "NEX + PP2A" or "CMV + PP2A" scheme while current sheet is 'BACKUP'
                if self.sheet_name == 'BACKUP' and (new_cage_no.startswith('8-A-') or new_cage_no.startswith('2-A-')):
                    messagebox.showwarning("Format Error", f"Backup cages are not supposed to start with '8-A-' or '2-A-'. Please enter a different number.", parent=dialog)
                    new_cage_entry.delete(0, tk.END) # Clear the entry
                    return

                # Remove from waiting room if it came from there
                if self.selected_mouse['ID'] in self.waiting_room_mice:
                    del self.waiting_room_mice[self.selected_mouse['ID']]

                self.selected_mouse['nuCA'] = new_cage_no
                self.selected_mouse['sheet'] = self.sheet_name

                if new_cage_no not in self.regular_cage_mice:
                    self.regular_cage_mice[new_cage_no] = []
                self.regular_cage_mice[new_cage_no].append(self.selected_mouse)
                
                self.update_callback() # Update the main DataFrame for the current sheet
                self.analyzer.redraw_canvas()
                self.close_metadata_window()
                dialog.destroy()

            tk.Button(dialog, text="Transfer", command=validate_and_transfer).pack(pady=10)
            dialog.wait_window(dialog) # Wait for the dialog to close

    def transfer_to_death_row(self):
        if self.selected_mouse is not None:
            # Remove from previous regular cage if it was there
            for cage_key, mice_list in self.regular_cage_mice.items():
                if self.selected_mouse in mice_list:
                    mice_list.remove(self.selected_mouse)
                    if not mice_list: # If cage becomes empty, remove it
                        del self.regular_cage_mice[cage_key]
                    break
            # Remove from waiting room if it was there
            if self.selected_mouse['ID'] in self.waiting_room_mice:
                del self.waiting_room_mice[self.selected_mouse['ID']]

            self.selected_mouse['nuCA'] = 'Death Row'
            self.selected_mouse['sheet'] = 'Death Row' # Set sheet to Death Row
            self.death_row_mice[self.selected_mouse['ID']] = self.selected_mouse # Store the mouse directly
            self.update_callback() # Call the callback to update the database
        self.analyzer.redraw_canvas()
        self.close_metadata_window()

    def transfer_from_death_row(self):
        if self.selected_mouse is not None:
            # Remove from death row
            if self.selected_mouse['ID'] in self.death_row_mice:
                del self.death_row_mice[self.selected_mouse['ID']]
            # Remove from waiting room if it somehow ended up there (safety check)
            if self.selected_mouse['ID'] in self.waiting_room_mice:
                del self.waiting_room_mice[self.selected_mouse['ID']]

            # Restore original cage and sheet
            original_cage = self.selected_mouse['cage'] # Assuming 'cage' stores the original cage
            self.selected_mouse['nuCA'] = original_cage
            
            if str(original_cage).startswith('8-A-'):
                self.selected_mouse['sheet'] = 'CMV + PP2A'
            elif str(original_cage).startswith('2-A-'):
                self.selected_mouse['sheet'] = 'NEX + PP2A'
            else:
                self.selected_mouse['sheet'] = 'BACKUP' # Or whatever your default sheet is for other cages

            # Add back to the regular cage if it belongs to the current sheet being viewed
            if self.selected_mouse['sheet'] == self.sheet_name:
                if original_cage not in self.regular_cage_mice:
                    self.regular_cage_mice[original_cage] = []
                self.regular_cage_mice[original_cage].append(self.selected_mouse)
            
            self.update_callback() # Call the callback to update the database
        self.analyzer.redraw_canvas()
        self.close_metadata_window()
        
warnings.simplefilter(action="ignore",category=FutureWarning)