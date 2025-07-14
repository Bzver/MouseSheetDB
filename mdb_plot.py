from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

import logging
import warnings

def display_genotype_bar_plot(self):
    """Plot mouse count by genotype data."""
    logging.debug(f"DEBUG: display_genotype_bar_plot called. current_category: {self.current_category}")
    try:
        genotypes, male_counts, female_counts, senile_counts = self.mice_count_for_genotype()
        logging.debug(f"DEBUG: Genotypes: {genotypes}, Male Counts: {male_counts}, Female Counts: {female_counts}, Senile Counts: {senile_counts}")
    except Exception as e:
        logging.error(f"Error processing mouse data for genotype bar plot: {e}", exc_info=True)
        return False

    if not genotypes:
        logging.debug("DEBUG: No genotypes to plot for bar plot.")
        return None # Return None if no data to plot

    fig, axes = plt.subplots(1, 1, figsize=(8, 6))
    ax = axes
    ax.bar(genotypes, male_counts, label="♂", color="lightblue")
    ax.bar(genotypes, female_counts, bottom=male_counts, label="♀", color="lightpink")
    ax.bar(genotypes, senile_counts, bottom=[male_counts[j] + female_counts[j] for j in range(len(genotypes))], label="Senile", color="grey")

    for j, genotype in enumerate(genotypes):
        male_y = male_counts[j] / 2
        female_y = male_counts[j] + (female_counts[j] / 2)
        senile_y = male_counts[j] + female_counts[j] + (senile_counts[j] / 2)

        if male_counts[j] > 0:
            ax.text(genotype, male_y, str(male_counts[j]), ha="center", va="center", color="black")
        if female_counts[j] > 0:
            ax.text(genotype, female_y, str(female_counts[j]), ha="center", va="center", color="black")
        if senile_counts[j] > 0:
            ax.text(genotype, senile_y, str(senile_counts[j]), ha="center", va="center", color="black")

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
    genotypes = []
    male_counts = []
    female_counts = []
    senile_counts = []

    logging.debug(f"DEBUG: mice_count_for_genotype - mouseDB size: {len(self.mouseDB) if self.mouseDB else 0}")
    logging.debug(f"DEBUG: mice_count_for_genotype - current_category: {self.current_category}")

    if not self.mouseDB:
        logging.debug("DEBUG: mouseDB is empty in mice_count_for_genotype.")
        return [], [], [], []

    logging.debug(f"DEBUG: first five entries in self.mouseDB: {list(self.mouseDB.items())[:5]}")
    logging.debug(f"DEBUG: current_category: {self.current_category}")

    for mouse_info in self.mouseDB.values():
        # Only consider mice in the current category for genotype counts
        if mouse_info.get("category") == self.current_category and mouse_info.get("genotype") not in genotypes:
            genotypes.append(mouse_info.get("genotype"))
        
    for genotype in genotypes:
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
        male_counts.append(males)
        female_counts.append(females)
        senile_counts.append(seniles)
        
    return genotypes, male_counts, female_counts, senile_counts

#########################################################################################################################

warnings.simplefilter(action="ignore",category=FutureWarning)