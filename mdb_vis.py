import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as patches

import mdb_utils

from collections import namedtuple

import warnings

class MouseVisualizer:
    def __init__(self, master, gui, mouseDB, sheet_name, canvas_widget):
        self.master = master
        self.gui = gui
        self.mouseDB = mouseDB
        self.sheet_name = sheet_name
        self.canvas_widget = canvas_widget

        MiceContainers = namedtuple("MiceContainers", ["regular", "waiting", "death"])
        self.mice_displayed = MiceContainers(
            regular={}, 
            waiting={}, 
            death={}
        )

        self.mouse_artists = []

        self.ax = None
        self.mpl_canvas = None

        if self.canvas_widget:
            self.canvas_widget.destroy()
            plt.close('all')

    def display_genotype_bar_plot(self):
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

        mdb_utils.mice_count_for_monitor(self.mouseDB, self.sheet_name, self.mice_displayed)

        cage_positions = self._calculate_cage_positions(len(self.mice_displayed.regular))
        self.mouse_artists.clear()

        self._draw_cages(ax, self.mice_displayed.regular, cage_positions)
        self._plot_mice(ax, self.mice_displayed.regular, cage_positions) 
        self._draw_special_cages(ax)
        self.ax = ax

        fig.canvas.mpl_connect('motion_notify_event', lambda event: self.gui.on_hover(event))
        fig.canvas.mpl_connect('button_press_event', lambda event: self.gui.on_click(event))

        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.master)
        self.mpl_canvas = canvas
        self.mpl_canvas.draw()
        self.canvas_widget = self.mpl_canvas.get_tk_widget()
        self.canvas_widget.pack()
        return self.canvas_widget
    
    #########################################################################################################################

    def _draw_cages(self, ax, cage_data, cage_positions):
        for cage_index, (cage_no, mice) in enumerate(cage_data.items()):
            x, y = cage_positions[cage_index]

            cage_color = 'black'
            for mouse in mice:
                breed_days = pd.to_numeric(mouse.get('breedDays'), errors='coerce')
                if pd.notna(breed_days) and breed_days > 90:
                    cage_color = 'red'
                    breakpoint
                
            cage_rect = patches.Rectangle((x - 0.8, y - 0.6), 1.6, 1.2, linewidth=1, edgecolor=cage_color, facecolor='none')
            ax.add_patch(cage_rect)
            cage_text = ax.text(x, y + 0.4, f"Cage: {cage_no}", ha='center', va='bottom', picker=True)
            cage_text.cage_no = cage_no
            cage_text.set_picker(True)

    def _draw_cages(self, ax):
        wr_x, wr_y, wr_width, wr_height = 8.5, 6.0, 2.5, 1.5
        wr_rect = patches.Rectangle((wr_x - wr_width/2, wr_y - wr_height/2), wr_width, wr_height, linewidth=1, edgecolor='blue', facecolor='none')
        ax.add_patch(wr_rect)
        ax.text(wr_x, wr_y + wr_height/2 + 0.2, "Waiting Room", ha='center', va='bottom', color='blue', fontsize=12)
        self._plot_mice_in_area(ax, list(self.mice_displayed.waiting.values()), wr_x, wr_y, wr_width, wr_height)

        dr_x, dr_y, dr_width, dr_height = 8.5, 3.0, 2.5, 1.5
        dr_rect = patches.Rectangle((dr_x - dr_width/2, dr_y - dr_height/2), dr_width, dr_height, linewidth=1, edgecolor='purple', facecolor='none')
        ax.add_patch(dr_rect)
        ax.text(dr_x, dr_y + dr_height/2 + 0.2, "Death Row", ha='center', va='bottom', color='purple', fontsize=12)
        self._plot_mice_in_area(ax, list(self.mice_displayed.death.values()), dr_x, dr_y, dr_width, dr_height)

    def _calculate_cage_positions(self, num_cages):
        positions = []
        cols = 3
        rows = (num_cages + cols - 1) // cols

        x_min_reg = 0.5 # Left padding
        x_max_reg = 7.0 # Right boundary for regular cages
        y_min_reg = 0.5 # Bottom padding
        y_max_reg = 7.5 # Top boundary for regular cages

        col_spacing = (x_max_reg - x_min_reg) / (cols + 1)
        row_spacing = (y_max_reg - y_min_reg) / (rows + 1)

        for i in range(num_cages):
            row = i // cols
            col = i % cols
            x = x_min_reg + (col + 1) * col_spacing
            y = y_max_reg - (row + 1) * row_spacing
            positions.append((x, y))
        return positions

    def _plot_mice(self, ax, cage_data, cage_positions):
        for cage_index, (cage_no, mice) in enumerate(cage_data.items()):
            x, y = cage_positions[cage_index]
            self._plot_mice_in_area(ax, mice, x, y, 1.6, 1.2)

    def _plot_mice_in_area(self, ax, mice, center_x, center_y, area_width, area_height):
        num_mice = len(mice)
        if num_mice == 0:
            return

        max_cols = int(np.sqrt(num_mice)) + 1
        col_spacing = area_width / (max_cols + 1)
        row_spacing = area_height / ((num_mice + max_cols - 1) // max_cols + 1)

        for i, mouse in enumerate(mice):
            col = i % max_cols
            row = i // max_cols
            mx = center_x - (area_width / 2) + (col + 1) * col_spacing
            my = center_y + (area_height / 2) - (row + 1) * row_spacing
            sex = mouse.get('sex', 'N/A')
            age = mouse.get('age', None)
            genotype = mouse.get('genotype', 'N/A')

            dot_color = mdb_utils.mice_dot_color_picker(sex, age)
            geno_text, geno_color = mdb_utils.genotype_abbreviation_color_picker(genotype)

            mouse_dot, = ax.plot(mx, my, marker='o', markersize=15, color=dot_color, picker=5)
            ax.text(mx, my, geno_text, ha='center', va='center', color=geno_color, fontsize=14)
            self.mouse_artists.append((mouse_dot, mouse))

    def cleanup(self):
        plt.close('all')

#########################################################################################################################

warnings.simplefilter(action="ignore",category=FutureWarning)