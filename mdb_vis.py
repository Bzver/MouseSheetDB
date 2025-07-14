import numpy as np
import pandas as pd
from collections import namedtuple

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem, QGraphicsEllipseItem
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor, QBrush, QPen, QFont

import mdb_utils as mut

import logging

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

        cage_positions = self.calculate_cage_positions(len(self.mice_status.regular))
        self.mouse_artists.clear() # Clear Matplotlib artists, now we'll use QGraphicsItems

        self.draw_cages_qt(self.mice_status.regular, cage_positions)
        self.plot_mice_qt(self.mice_status.regular, cage_positions)
        self.draw_special_cages_qt()

        # Connect mouse events for interaction
        self.graphics_view.setMouseTracking(True) # Enable mouse tracking for hover events
        self.graphics_view.viewport().installEventFilter(self) # Install event filter to capture mouse events

        self.canvas_widget = self.graphics_view # Store the QGraphicsView object
        return self.canvas_widget
    
    def eventFilter(self, watched, event):
        if watched == self.graphics_view.viewport():
            if event.type() == QEvent.MouseMove:
                self.gui.on_hover(event, self.graphics_view)
            elif event.type() == QEvent.MouseButtonPress:
                self.gui.on_click(event, self.graphics_view)
        return super().eventFilter(watched, event)

    #########################################################################################################################

    def draw_cages_qt(self, cage_data, cage_positions):
        for cage_index, (cage_no, mice) in enumerate(cage_data.items()):
            x_center, y_center = cage_positions[cage_index]

            cage_width = 160
            cage_height = 120
            x_rect = x_center - cage_width / 2
            y_rect = y_center - cage_height / 2

            cage_color = QColor(Qt.black)
            for mouse in mice:
                breed_days = pd.to_numeric(mouse.get("breedDays"), errors="coerce")
                if pd.notna(breed_days) and breed_days > 90:
                    cage_color = QColor(Qt.red)
                    break
                
            cage_rect_item = QGraphicsRectItem(x_rect, y_rect, cage_width, cage_height)
            cage_rect_item.setPen(QPen(cage_color, 2)) # Thicker pen for visibility
            self.graphics_scene.addItem(cage_rect_item)

            cage_text_item = QGraphicsTextItem(f"Cage: {cage_no}")
            cage_text_item.setPos(x_center - cage_text_item.boundingRect().width() / 2, y_rect - 30) # Position above rectangle
            cage_text_item.setFont(QFont("Arial", 10))
            self.graphics_scene.addItem(cage_text_item)

    def draw_special_cages_qt(self):
        # Waiting Room
        wr_x, wr_y, wr_width, wr_height = 850, 600, 250, 150 # Scene coordinates
        wr_rect_item = QGraphicsRectItem(wr_x - wr_width/2, wr_y - wr_height/2, wr_width, wr_height)
        wr_rect_item.setPen(QPen(QColor(Qt.blue), 2))
        self.graphics_scene.addItem(wr_rect_item)
        wr_text_item = QGraphicsTextItem("Waiting Room")
        wr_text_item.setPos(wr_x - wr_text_item.boundingRect().width()/2, wr_y + wr_height/2 + 20)
        wr_text_item.setDefaultTextColor(QColor(Qt.blue))
        wr_text_item.setFont(QFont("Arial", 12))
        self.graphics_scene.addItem(wr_text_item)
        self.plot_mice_in_area_qt(list(self.mice_status.waiting.values()), wr_x, wr_y, wr_width, wr_height)

        # Death Row
        dr_x, dr_y, dr_width, dr_height = 850, 300, 250, 150 # Scene coordinates
        dr_rect_item = QGraphicsRectItem(dr_x - dr_width/2, dr_y - dr_height/2, dr_width, dr_height)
        dr_rect_item.setPen(QPen(QColor(Qt.darkMagenta), 2))
        self.graphics_scene.addItem(dr_rect_item)
        dr_text_item = QGraphicsTextItem("Death Row")
        dr_text_item.setPos(dr_x - dr_text_item.boundingRect().width()/2, dr_y + dr_height/2 + 20)
        dr_text_item.setDefaultTextColor(QColor(Qt.darkMagenta))
        dr_text_item.setFont(QFont("Arial", 12))
        self.graphics_scene.addItem(dr_text_item)
        self.plot_mice_in_area_qt(list(self.mice_status.death.values()), dr_x, dr_y, dr_width, dr_height)

    def calculate_cage_positions(self, num_cages):
        positions = []
        cols = 3
        rows = (num_cages + cols - 1) // cols

        x_min_reg = 50 # Left padding in scene coordinates
        x_max_reg = 700 # Right boundary for regular cages in scene coordinates
        y_min_reg = 50 # Bottom padding in scene coordinates
        y_max_reg = 750 # Top boundary for regular cages in scene coordinates

        col_spacing = (x_max_reg - x_min_reg) / (cols + 1)
        row_spacing = (y_max_reg - y_min_reg) / (rows + 1)

        for i in range(num_cages):
            row = i // cols
            col = i % cols
            x = x_min_reg + (col + 1) * col_spacing
            y = y_max_reg - (row + 1) * row_spacing
            positions.append((x, y))
        return positions

    def plot_mice_qt(self, cage_data, cage_positions):
        for cage_index, (cage_no, mice) in enumerate(cage_data.items()):
            x_center, y_center = cage_positions[cage_index]
            # Use scene coordinates for area
            self.plot_mice_in_area_qt(mice, x_center, y_center, 160, 120) # width, height in scene units

    def plot_mice_in_area_qt(self, mice, center_x, center_y, area_width, area_height):
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
            sex = mouse.get("sex", "N/A")
            age = mouse.get("age", None)
            genotype = mouse.get("genotype", "N/A")

            dot_color = QColor(mut.mice_dot_color_picker(sex, age))
            geno_text, geno_color_str = mut.genotype_abbreviation_color_picker(genotype)
            geno_color = QColor(geno_color_str)

            # Create QGraphicsEllipseItem for the mouse dot
            mouse_dot_item = QGraphicsEllipseItem(0, 0, 30, 30) # x, y, width, height
            mouse_dot_item.setPos(mx - 15, my - 15) # Adjust position to center the ellipse
            mouse_dot_item.setBrush(QBrush(dot_color))
            mouse_dot_item.setPen(QPen(Qt.NoPen)) # No border for the dot
            mouse_dot_item.setFlag(QGraphicsEllipseItem.ItemIsSelectable, True) # Make it selectable
            mouse_dot_item.setFlag(QGraphicsEllipseItem.ItemIsMovable, False) # Not movable
            mouse_dot_item.setAcceptHoverEvents(True) # Enable hover events
            mouse_dot_item.setData(0, mouse) # Store mouse data in the item
            self.graphics_scene.addItem(mouse_dot_item)

            # Create QGraphicsTextItem for the genotype text
            geno_text_item = QGraphicsTextItem(geno_text)
            geno_text_item.setPos(mx - 15, my - 15)
            geno_text_item.setDefaultTextColor(geno_color)
            geno_text_item.setFont(QFont("Arial", 14))
            geno_text_item.setParentItem(mouse_dot_item) # Make text a child of the dot
            
            self.mouse_artists.append((mouse_dot_item, mouse)) # Store QGraphicsItem and mouse data

    ##########################################################################################################################

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