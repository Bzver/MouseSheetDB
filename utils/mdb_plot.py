from PySide6.QtWidgets import QWidget, QVBoxLayout

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

import logging
import warnings

class MousePlotter(QWidget):
    def __init__(self, parent, mouseDB, current_category, canvas_widget):
        super().__init__(parent)
        self.gui = parent
        self.mouseDB = mouseDB
        self.current_category = current_category
        self.canvas_widget = canvas_widget

        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)

        self.ax = None
        self.mpl_canvas = None

        self.genotypes = []
        self.male_counts = []
        self.female_counts = []
        self.senile_counts = []

    def display_genotype_bar_plot(self):
        """Plot mouse count by genotype data."""
        logging.debug(f"DEBUG: display_genotype_bar_plot called. current_category: {self.current_category}")
        try:
            self.mice_count_for_genotype()
            logging.debug(f"DEBUG: Genotypes: {self.genotypes}, Male Counts: {self.male_counts}, Female Counts: {self.female_counts}, Senile Counts: {self.senile_counts}")
        except Exception as e:
            logging.error(f"Error processing mouse data for genotype bar plot: {e}", exc_info=True)
            return False

        fig, axes = plt.subplots(1, 1, figsize=(8, 6))
        ax = axes
        ax.bar(self.genotypes, self.male_counts, label="♂", color="lightblue")
        ax.bar(self.genotypes, self.female_counts, bottom=self.male_counts, label="♀", color="lightpink")
        ax.bar(self.genotypes, self.senile_counts, bottom=[self.male_counts[j] + self.female_counts[j] for j in range(len(self.genotypes))], label="Senile", color="grey")

        for j, genotype in enumerate(self.genotypes):
            male_y = self.male_counts[j] / 2
            female_y = self.male_counts[j] + (self.female_counts[j] / 2)
            senile_y = self.male_counts[j] + self.female_counts[j] + (self.senile_counts[j] / 2)

            if self.male_counts[j] > 0:
                ax.text(genotype, male_y, str(self.male_counts[j]), ha="center", va="center", color="black")
            if self.female_counts[j] > 0:
                ax.text(genotype, female_y, str(self.female_counts[j]), ha="center", va="center", color="black")
            if self.senile_counts[j] > 0:
                ax.text(genotype, senile_y, str(self.senile_counts[j]), ha="center", va="center", color="black")

        ax.set_title(f"Genotype Counts in Category: {self.current_category}")
        ax.set_xlabel("Genotype")
        ax.set_ylabel("Number of Mice")
        ax.legend()
        labels = [label.get_text().replace("-P", "\nP") for label in ax.get_xticklabels()]
        ax.set_xticks(ax.get_xticks())
        ax.set_xticklabels(labels)

        plt.tight_layout()
        canvas = FigureCanvas(fig)
        self.main_layout.addWidget(canvas) # Add canvas to the layout
        canvas.draw()
        self.canvas_widget = canvas # Store the FigureCanvas object
        return self.canvas_widget

    def mice_count_for_genotype(self):
        logging.debug(f"DEBUG: mice_count_for_genotype - mouseDB size: {len(self.mouseDB) if self.mouseDB else 0}")
        logging.debug(f"DEBUG: mice_count_for_genotype - current_category: {self.current_category}")

        if not self.mouseDB:
            logging.debug("DEBUG: mouseDB is empty in mice_count_for_genotype.")
            return [], [], [], []

        logging.debug(f"DEBUG: first five entries in self.mouseDB: {list(self.mouseDB.items())[:5]}")
        logging.debug(f"DEBUG: current_category: {self.current_category}")

        for mouse_info in self.mouseDB.values():
            # Only consider mice in the current category for genotype counts
            if mouse_info.get("category") == self.current_category and mouse_info.get("genotype") not in self.genotypes:
                self.genotypes.append(mouse_info.get("genotype"))
            
        for genotype in self.genotypes:
            males = sum(1 for mouse_info in self.mouseDB.values()
                            if mouse_info.get("genotype") == genotype
                            and mouse_info.get("category") == self.current_category
                            and mouse_info.get("sex") == "♂"
                            and mouse_info.get("age", 0) <= 300)
            females = sum(1 for mouse_info in self.mouseDB.values()
                            if mouse_info.get("genotype") == genotype
                            and mouse_info.get("category") == self.current_category
                            and mouse_info.get("sex") == "♀"
                            and mouse_info.get("age", 0) <= 300)
            seniles = sum(1 for mouse_info in self.mouseDB.values()
                            if mouse_info.get("genotype") == genotype
                            and mouse_info.get("category") == self.current_category
                            and mouse_info.get("age", 0) > 300)
            self.male_counts.append(males)
            self.female_counts.append(females)
            self.senile_counts.append(seniles)

    #########################################################################################################################

    warnings.simplefilter(action="ignore",category=FutureWarning)