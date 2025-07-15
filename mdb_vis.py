import numpy as np
import pandas as pd
from collections import namedtuple

from PySide6 import QtWidgets
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene, QGraphicsWidget, QGraphicsGridLayout, QMessageBox
from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QColor, QBrush, QPen, QFont

import mdb_utils as mut
import mdb_transfer as mtrans

import logging

class MouseGraphicsItem(QGraphicsWidget):
    """A custom QGraphicsWidget to represent a single mouse, including its dot and genotype text."""
    def __init__(self, mouse_data, size=30, parent=None):
        super().__init__(parent)
        self.setMinimumSize(size, size)
        self.setPreferredSize(size, size)
        self.setMaximumSize(size, size)
        self.mouse_data = mouse_data
        self.setFlag(QGraphicsWidget.ItemIsSelectable, True)
        self.setFlag(QGraphicsWidget.ItemIsMovable, False)
        self.setData(0, mouse_data) # Store mouse data in the item
        self.setAcceptHoverEvents(True) # Enable hover events

        self.sex = self.mouse_data.get("sex", "N/A")
        self.age = self.mouse_data.get("age", None)
        self.genotype = self.mouse_data.get("genotype", "N/A")

        self.dot_color = QColor(mut.mice_dot_color_picker(self.sex, self.age))
        self.geno_text, geno_color_str = mut.genotype_abbreviation_color_picker(self.genotype)
        self.geno_color = QColor(geno_color_str)

    def paint(self, painter, option, widget):
        # Draw the ellipse
        painter.setBrush(QBrush(self.dot_color))
        painter.setPen(QPen(Qt.NoPen))
        painter.drawEllipse(self.rect())

        # Draw the genotype text
        painter.setFont(QFont("Arial", 14))
        painter.setPen(QPen(self.geno_color))
        text_rect = painter.fontMetrics().boundingRect(self.geno_text)
        painter.drawText(
            self.rect().center().x() - text_rect.width() / 2,
            self.rect().center().y() + text_rect.height() / 2 - 3,
            self.geno_text
        )

class CageGraphicsItem(QGraphicsWidget):
    """A custom QGraphicsWidget to represent a single cage, containing its mice."""
    def __init__(self, cage_no, mice_data, parent=None):
        super().__init__(parent)
        self.cage_no = cage_no
        self.mice_data = mice_data
        self.cage_color = None
        self.setFlag(QGraphicsWidget.ItemIsMovable, False) # Cages should not be movable

        self.setMinimumSize(180, 150) # Minimum size for the cage
        self.setPreferredSize(180, 150)
        self.setMaximumSize(180, 150)

        self.setContentsMargins(10, 40, 10, 10) # Left, Top, Right, Bottom margins for internal layout

        self.cage_layout = QGraphicsGridLayout()
        self.setLayout(self.cage_layout)

        self._plot_mice_in_cage()

    def paint(self, painter, option, widget):
        # Draw the cage rectangle
        cage_color = self.cage_color if self.cage_color is not None else QColor(Qt.black)
        for mouse in self.mice_data:
            breed_days = pd.to_numeric(mouse.get("breedDays"), errors="coerce")
            if pd.notna(breed_days) and breed_days > 90:
                cage_color = QColor(Qt.red)
                break
        
        painter.setPen(QPen(cage_color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect())

        # Draw cage number text
        painter.setFont(QFont("Arial", 10))
        painter.setPen(QPen(Qt.black))
        text_rect = painter.fontMetrics().boundingRect(f"Cage: {self.cage_no}")
        painter.drawText(
            self.rect().center().x() - text_rect.width() / 2,
            self.rect().top() + 15, # Position above the rectangle
            f"Cage: {self.cage_no}"
        )

    def _plot_mice_in_cage(self):
        num_mice = len(self.mice_data)
        if num_mice == 0:
            return

        # Simple grid layout for mice within the cage
        max_cols = int(np.sqrt(num_mice)) + 1
        
        for i, mouse in enumerate(self.mice_data):
            row = i // max_cols
            col = i % max_cols
            mouse_item = MouseGraphicsItem(mouse, size=30)
            self.cage_layout.addItem(mouse_item, row, col)

class MouseVisualizer(QWidget):
    def __init__(self, parent, mouseDB, current_category, canvas_widget):
        super().__init__(parent)
        self.gui = parent
        self.mouseDB = mouseDB
        self.current_category = current_category
        self.canvas_widget = canvas_widget

        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)

        self.gui.setGeometry(300, 300, 1000, 700) # x, y, width, height
        self.graphics_view = None # For QGraphicsView
        self.graphics_scene = None # For QGraphicsScene

        MiceContainers = namedtuple("MiceContainers", ["regular", "waiting", "death"])
        self.mice_status = MiceContainers(regular={}, waiting={}, death={})
        self.mouse_artists = []
        self.selected_mouse = None

        self.leaving_timer = None
        self.current_metadata_window = None
        self.edited_mouse_artist = None
        self.last_hovered_mouse = None

        self.menu = None

    def display_cage_monitor(self):
        """
        Displays the cage monitor visualization using QGraphicsView.
        Mice with "nuCA" set to "Waiting Room" or "Death Row" are plotted in special areas.
        """
        logging.debug(f"VIS: display_cage_monitor called. current_category: {self.current_category}")

        # Clear existing graphics view if any
        if self.graphics_view:
            # Remove the event filter before deleting the old graphics view
            self.graphics_view.viewport().removeEventFilter(self)
            self.graphics_view.deleteLater()
            self.graphics_view = None
            self.graphics_scene = None
        
        self.graphics_scene = QGraphicsScene(self)
        self.graphics_view = QGraphicsView(self.graphics_scene)
        self.main_layout.addWidget(self.graphics_view)

        # Set scene rectangle to define the drawing area (similar to xlim/ylim)
        self.graphics_scene.setSceneRect(0, 0, 1000, 800) # Adjust scene size as needed

        self.mice_count_for_monitor()
        logging.debug(f"DEBUG: Mice displayed - Regular: {len(self.mice_status.regular)}, Waiting: {len(self.mice_status.waiting)}, Death: {len(self.mice_status.death)}")

        if not self.mice_status.regular and not self.mice_status.waiting and not self.mice_status.death:
            logging.debug("DEBUG: No mice data to plot for cage monitor.")
            return None # Return None if no data to plot

        self.mouse_artists.clear() # Clear previous mouse artists

        # Use QGraphicsGridLayout for regular cages
        self.cage_grid_layout = QGraphicsGridLayout()
        self.draw_cages_qt(self.mice_status.regular, self.cage_grid_layout)

        # Add the grid layout to a QGraphicsWidget to be able to add it to the scene
        grid_widget = QGraphicsWidget()
        grid_widget.setLayout(self.cage_grid_layout)
        self.graphics_scene.addItem(grid_widget)

        # Position the grid_widget (adjust as needed)
        grid_widget.setPos(50, 50) # Example position

        self.draw_special_cages_qt()

        # Connect mouse events for interaction
        self.graphics_view.setMouseTracking(True) # Enable mouse tracking for hover events
        self.graphics_view.viewport().installEventFilter(self) # Install event filter to capture mouse events

        self.canvas_widget = self.graphics_view # Store the QGraphicsView object
        return self.canvas_widget
    
    def eventFilter(self, watched, event):
        if watched == self.graphics_view.viewport():
            if event.type() == QEvent.MouseMove:
                self.on_hover(event, self.graphics_view)
            elif event.type() == QEvent.MouseButtonPress:
                self.on_click(event, self.graphics_view)
        return super().eventFilter(watched, event)

    #########################################################################################################################

    def draw_cages_qt(self, cage_data, layout):
        cols = 3 # Number of columns for the grid layout
        for cage_index, (cage_no, mice) in enumerate(cage_data.items()):
            row = cage_index // cols
            col = cage_index % cols
            cage_item = CageGraphicsItem(cage_no, mice)
            layout.addItem(cage_item, row, col)
            self.mouse_artists.extend([(mouse_item, mouse_item.mouse_data) for mouse_item in cage_item.findChildren(MouseGraphicsItem)])

    def draw_special_cages_qt(self):
        # Waiting Room
        waiting_cage_item = CageGraphicsItem("Waiting Room", list(self.mice_status.waiting.values()))
        waiting_cage_item.setPos(850 - waiting_cage_item.preferredSize().width()/2, 600 - waiting_cage_item.preferredSize().height()/2) # Position manually for now
        waiting_cage_item.cage_color = QColor(Qt.blue) # Set border color
        self.graphics_scene.addItem(waiting_cage_item)
        
        # Death Row
        death_cage_item = CageGraphicsItem("Death Row", list(self.mice_status.death.values()))
        death_cage_item.setPos(850 - death_cage_item.preferredSize().width()/2, 300 - death_cage_item.preferredSize().height()/2) # Position manually for now
        death_cage_item.cage_color = QColor(Qt.darkMagenta)
        self.graphics_scene.addItem(death_cage_item)

    def mice_count_for_monitor(self):
        # Clear data from previous category
        self.mice_status.regular.clear()
        self.mice_status.waiting.clear()
        self.mice_status.death.clear()

        logging.debug(f"DEBUG: mice_count_for_monitor - mouseDB size: {len(self.mouseDB) if self.mouseDB else 0}")
        logging.debug(f"DEBUG: mice_count_for_monitor - current_category: {self.current_category}")

        if not self.mouseDB:
            logging.debug("DEBUG: mouseDB is empty in mice_count_for_monitor.")
            return

        for mouse_info in self.mouseDB.values():
            cage_key = mouse_info.get("nuCA")
            ID = mouse_info.get("ID")
            category = mouse_info.get("category")

            if category == self.current_category and cage_key not in ["Waiting Room", "Death Row"]:
                if cage_key not in self.mice_status.regular:
                    self.mice_status.regular[cage_key] = []
                self.mice_status.regular[cage_key].append(mouse_info)
            elif cage_key == "Waiting Room":
                self.mice_status.waiting[ID] = mouse_info
            elif cage_key == "Death Row":
                self.mice_status.death[ID] = mouse_info
        logging.debug(f"VIS: mice_count_for_monitor completed. Regular: {len(self.mice_status.regular)}, Waiting: {len(self.mice_status.waiting)}, Death: {len(self.mice_status.death)}")

    #########################################################################################################################

    def on_hover(self, event, graphics_view): # Map event position to scene coordinates
        scene_position = graphics_view.mapToScene(event.position().toPoint())
        item = graphics_view.scene().itemAt(scene_position, graphics_view.transform())

        if item and isinstance(item, QGraphicsWidget):
            mouse = item.data(0) # Retrieve stored mouse data
            if mouse:
                if self.leaving_timer and self.leaving_timer.isActive():
                    self.leaving_timer.stop()
                    self.leaving_timer = None

                if self.last_hovered_mouse and self.last_hovered_mouse == mouse:
                    return

                if self.current_metadata_window:
                    self.current_metadata_window.close()

                self.show_metadata_window(mouse, graphics_view.mapToGlobal(event.position().toPoint()))
                self.selected_mouse = mouse # Set selected mouse on hover
                self.last_hovered_mouse = mouse
                return
        
        self.schedule_close_metadata_window()
    
    def on_click(self, event, graphics_view):
        if event.button() == Qt.LeftButton:
            scene_position = graphics_view.mapToScene(event.position().toPoint())
            item = graphics_view.scene().itemAt(scene_position, graphics_view.transform())

            if item and isinstance(item, QGraphicsWidget):
                mouse = item.data(0)
                if mouse:
                    self.selected_mouse = mouse
                    self.show_context_menu(graphics_view.mapToGlobal(event.position().toPoint()))
                    return
                
   #########################################################################################################################

    def show_context_menu(self, global_pos):
        self.close_metadata_window() # Close metadata window when context menu appears
        self.menu = QtWidgets.QMenu(self)

        is_in_waiting_room = self.selected_mouse.get("nuCA") == "Waiting Room"
        is_on_death_row = self.selected_mouse.get("nuCA") == "Death Row"

        if is_on_death_row:
            self.menu.addAction("Release from Death Row", lambda: self._transfer_mouse_action("from_death_row"))
        else:
            self.menu.addAction("Transfer to current cages", lambda: self._transfer_mouse_action("existing_cage"))
            self.menu.addAction("Transfer to Death Row", lambda: self._transfer_mouse_action("death_row"))
            if is_in_waiting_room:
                self.menu.addAction("Transfer to a new cage", lambda: self._transfer_mouse_action("new_cage"))
            else: # in regular cages
                self.menu.addAction("Transfer to waiting room", lambda: self._transfer_mouse_action("waiting_room"))
                self.menu.addAction("Add to pedigree graph", lambda: self.gui.add_selected_mouse_to_family_tree(self.selected_mouse))
                self.menu.addAction("Edit mouse entry", self.gui.edit_selected_mouse_entry)

        self.menu.exec(global_pos)

    def _transfer_mouse_action(self, action_type): # Wrapper for transfer
        logging.debug(f"GUI: Initiating transfer action: {action_type} for mouse ID: {self.selected_mouse.get('ID')}")
        # Pass self (the GUI instance) as the parent for the transfer dialog
        transfer_instance = mtrans.MouseTransfer(self, self.mouseDB, self.current_category, self.mice_status)
        if action_type == "death_row":
            transfer_instance.transfer_to_death_row()
        elif action_type == "existing_cage":
            transfer_instance.transfer_to_existing_cage()
        elif action_type == "waiting_room":
            transfer_instance.transfer_to_waiting_room()
        elif action_type == "new_cage":
            transfer_instance.transfer_to_new_cage()
        elif action_type == "from_death_row":
            transfer_instance.transfer_from_death_row()
        else:
            QMessageBox.critical(self, "Error", f"Unknown transfer action: {action_type}")

    #########################################################################################################################

    def show_metadata_window(self, mouse, global_pos):
        if self.menu:  # Don not open if context menu is open
            return
        if self.current_metadata_window:
            self.current_metadata_window.close()

        sex = mouse.get("sex", "N/A")
        toe = mouse.get("toe", "N/A")
        age = mouse.get("age", "N/A")
        genotype = mouse.get("genotype", "N/A")
        mouseID = mouse.get("ID", "N/A")

        if len(genotype) < 15:
            genotype = genotype.center(20)
        
        metadata_window = QtWidgets.QDialog(self)
        metadata_window.setWindowTitle("Mouse Metadata")
        metadata_window.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint) # ToolTip for no taskbar entry, Frameless for no title bar
        metadata_window.setAttribute(Qt.WA_DeleteOnClose) # Ensure it's deleted when closed

        layout = QVBoxLayout(metadata_window)
        layout.setContentsMargins(5, 5, 5, 5) # Smaller margins
        
        separ_geno = "------GENOTYPE------"
        separ_ID = "------------I-D------------"
        message = (f"Sex: {sex}   Toe: {toe}\nAge: {age}d ({int(age) // 7}w{int(age) % 7}d)\n{separ_geno}\n{genotype}\n{separ_ID}\n{mouseID}")
        label = QtWidgets.QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-family: Arial; font-size: 9pt; padding: 5px; background-color: lightyellow; border: 1px solid gray;") # Added background and border
        layout.addWidget(label)

        metadata_window.setLayout(layout)
        metadata_window.adjustSize()
        metadata_window.move(global_pos) # Position at mouse cursor
        metadata_window.show()

        self.current_metadata_window = metadata_window

    def schedule_close_metadata_window(self):
        if self.current_metadata_window and not self.leaving_timer:
            self.leaving_timer = QTimer(self) # Parent the timer to self
            self.leaving_timer.setSingleShot(True)
            self.leaving_timer.timeout.connect(self.close_metadata_window)
            self.leaving_timer.start(100)

    def close_metadata_window(self):
        if self.current_metadata_window:
            self.current_metadata_window.close()
            self.current_metadata_window = None
        self.last_hovered_mouse = None
        if self.leaving_timer:
            self.leaving_timer.stop()
            self.leaving_timer = None