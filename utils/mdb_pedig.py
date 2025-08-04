from PySide6.QtWidgets import QDialog, QVBoxLayout

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class MousePedigree(QDialog):
    def __init__(self, parent, mouseDB):
        """
        Initializes the MousePedigree class, which is currently WIP.
        Args:
            parent: The parent PySide6 widget.
            mouseDB: The mouse database object.
        """
        super().__init__(parent)
        self.mouseDB = mouseDB
        self.setWindowTitle("Mice Pedigree Tree")
        self.setGeometry(200, 200, 800, 600) # x, y, width, height

        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)

    def display_family_tree_window(self):
        """
        Displays a new window for the mouse family tree. WIP
        """
        # Clear existing content if any
        for i in reversed(range(self.main_layout.count())):
            widget = self.main_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        fig = Figure(figsize=(8,6))
        ax = fig.add_subplot(111)
        ax.set_title("Mice Pedigree Tree")
        ax.axis("off")

        fig.tight_layout()

        canvas = FigureCanvas(fig)
        self.main_layout.addWidget(canvas)
        canvas.draw()
        self.exec() # Show as modal dialog