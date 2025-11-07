from PySide6 import QtWidgets
from PySide6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox

import mdb_io.io_helper as mio
import utils.mdb_plot as mplt
import utils.mdb_vis as mvis
import utils.mdb_edit as medit
import utils.mdb_transfer as mtrans
from mdb_io import Mouse_DB

import traceback
import logging
logging.getLogger().setLevel(logging.INFO)

DEBUG = True

class MDB_App(QWidget):
    def __init__(self):
        super().__init__()
        logging.info("GUI initialized.")
        self.setWindowTitle("MiceDatabase V3.0")

        self.main_layout = QVBoxLayout(self)

        self._setup_top_btn_frame()
        self._setup_category_nav_frame()

        self.canvas_container_layout = QVBoxLayout()
        self.main_layout.addLayout(self.canvas_container_layout)

        self._reset_state()

        if DEBUG: logging.getLogger().setLevel(logging.DEBUG)
        self.is_debug = DEBUG
        logging.debug(f"is_debug set to: {self.is_debug}")

    def _setup_top_btn_frame(self):
        self.button_layout = QHBoxLayout()
        self.main_layout.addLayout(self.button_layout)

        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_file)
        self.button_layout.addWidget(self.browse_button)

        self.table_button = QPushButton("Table")
        self.table_button.clicked.connect(self._on_table_btn_clicked)
        self.table_button.setEnabled(False)
        self.button_layout.addWidget(self.table_button)

        self.cageview_button = QPushButton("Visualize")
        self.cageview_button.clicked.connect(self._on_cageview_btn_clicked)
        self.cageview_button.setEnabled(False)
        self.button_layout.addWidget(self.cageview_button)

        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.clicked.connect(self._on_analyze_btn_clicked)
        self.analyze_button.setEnabled(False)
        self.button_layout.addWidget(self.analyze_button)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_changes)
        self.save_button.setEnabled(False)
        self.button_layout.addWidget(self.save_button)

    def _setup_category_nav_frame(self):
        self.category_nav_layout = QHBoxLayout()
        self.main_layout.addLayout(self.category_nav_layout)

        self.add_entries_button = QPushButton("Add Entries")
        self.add_entries_button.clicked.connect(self.add_new_mouse_entry)
        self.add_entries_button.setEnabled(False)
        self.category_nav_layout.addWidget(self.add_entries_button)

        self.prev_category_button = QPushButton("◄ Prev Category")
        self.prev_category_button.clicked.connect(self._prev_category)
        self.prev_category_button.setEnabled(False)
        self.category_nav_layout.addWidget(self.prev_category_button)

        self.category_textbox = QtWidgets.QLineEdit()
        self.category_textbox.setReadOnly(True)
        self.category_textbox.setFixedWidth(200)
        self.category_nav_layout.addWidget(self.category_textbox)

        self.next_category_button = QPushButton("Next Category ►")
        self.next_category_button.clicked.connect(self._next_category)
        self.next_category_button.setEnabled(False)
        self.category_nav_layout.addWidget(self.next_category_button)

        self.load_changelog_button = QPushButton("Load Changes")
        self.load_changelog_button.clicked.connect(self.load_changelog)
        self.load_changelog_button.setEnabled(False)
        self.category_nav_layout.addWidget(self.load_changelog_button)
        
    def _reset_state(self):
        self.file_path = None

        self.processed_data = None
        self.mouse_dict = None

        self.current_category = "DEFAULT" 
        self.category_index = 0
        self.category_names = ["DEFAULT"]

        self.visualizer, self.editor, self.plotter = None, None, None
        self.db = Mouse_DB()
        
        self.canvas_widget = None
        self.last_action = "table"
        self.is_saved = True

        self.selected_mouse = None

        self.category_textbox.setReadOnly(False)
        self.category_textbox.clear()
        self.category_textbox.setReadOnly(True)
        self.prev_category_button.setEnabled(False)
        self.next_category_button.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.table_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.add_entries_button.setEnabled(False)

    #########################################################################################################################

    def browse_file(self):
        logging.debug("browse_file called.")
        if not self.is_saved:
            reply = QMessageBox.question(self, "Unsaved Changes",
            "You have unsaved changes. Do you really want to load another file without saving?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        self._reset_state()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Workspace", "", "DB Files (*.db);;Excel Files (*.xlsx *.xls)"
        )
        if not file_path:
            return
        
        self.is_saved = True
        
        try:
            if file_path.endswith(".db"):
                self._load_db_file(file_path)
            else:
                self._load_excel_file(file_path)
            QMessageBox.information(self, "Success", "File loaded successfully!")
            self.load_changelog_button.setEnabled(True)
            self.add_entries_button.setEnabled(True)
            self._on_category_selection_changed()
            logging.debug("File loaded successfully and initial analysis triggered.")
        except Exception as e:
            logging.error(f"Error loading/preprocessing file: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error loading/preprocessing file: {e}\n{traceback.format_exc()}")

    def _load_db_file(self, file_path):
        self.db.set_db_path(file_path)

    def _load_excel_file(self, file_path):   # To be changed to load excel into DB
        mio.validate_excel(file_path)
        processed_data = mio.data_preprocess(file_path, "MDb")
        mouse_dict = self.processed_data.copy()
        self._update_control_ui()
        if processed_data is None:
            raise Exception("Failed to preprocess Excel data")
        logging.debug("Excel file loaded and preprocessed successfully.")

    def save_changes(self):
        pass # To be re-implemented in sql backend

    def load_changelog(self):
        pass # To be re-implemented in sql backend

    #########################################################################################################################

    def _show_tables(self):
        pass # To be implemented

    def _analyze_data(self):
        self.last_action = "analyze" # Update last action
        logging.debug("analyze_data called.")
        try:
            self.plotter = mplt.MousePlotter(self, self.mouse_dict, self.current_category, self.canvas_widget)
            self.canvas_widget = self.plotter.display_genotype_bar_plot()
            if self.canvas_widget:
                self.canvas_container_layout.addWidget(self.canvas_widget) # Add canvas to the canvas_container
                logging.debug("Genotype bar plot displayed successfully.")
            else:
                logging.warning("Genotype bar plot was not displayed (canvas_widget is None).")
        except Exception as e:
            logging.error(f"Error plotting analysis data: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error plotting analysis data: {e}\n{traceback.format_exc()}")

    def _monitor_cages(self):
        self.last_action = "monitor"
        logging.debug("monitor_cages called.")
        try:
            self.visualizer = mvis.MouseVisualizer(self, self.mouse_dict, self.current_category, self.canvas_widget)
            self.canvas_widget = self.visualizer.display_cage_monitor()
            if self.canvas_widget:
                self.canvas_container_layout.addWidget(self.canvas_widget)
                logging.debug("Cage monitor displayed successfully.")
            else:
                logging.warning("Cage monitor was not displayed (canvas_widget is None).")
        except Exception as e:
            logging.error(f"Error displaying cage monitor: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error displaying cage monitor: {e}\n{traceback.format_exc()}")

    #########################################################################################################################

    def determine_save_status(self):
        if mio.find_changes_for_changelog(self.processed_data, self.mouse_dict, check_only=True):
            self.is_saved = False
            self.save_button.setEnabled(True)
        else:
            self.is_saved = True
            self.save_button.setEnabled(False)

    def redraw_canvas(self):
        """Public method to trigger canvas redraw based on current state."""
        logging.debug("GUI: redraw_canvas called. Triggering _refresh_canvas_container.")
        self._refresh_canvas_container()

    def _update_control_ui(self):
        """Update UI elements for current category and mode"""
        self.category_textbox.setReadOnly(False)
        self.category_textbox.setText(self.current_category.center(40))
        self.category_textbox.setReadOnly(True)
        self.prev_category_button.setEnabled(True)
        self.next_category_button.setEnabled(True)
        self.table_button.setEnabled(True)
        self.analyze_button.setEnabled(True)
        if self.plotter:
            self.analyze_button.setEnabled(False)
        elif self.visualizer:
            self.table_button.setEnabled(False)

    def _prev_category(self):
        """Navigate to previous category"""
        self.category_index = (self.category_index - 1) % len(self.category_names)
        self.current_category = self.category_names[self.category_index]
        self._refresh_canvas_container()

    def _next_category(self):
        """Navigate to next category"""
        self.category_index = (self.category_index + 1) % len(self.category_names)
        self.current_category = self.category_names[self.category_index]
        self._refresh_canvas_container()

    def _on_category_selection_changed(self, event=None):
        """Handle category selection changes (UI updates only)"""
        if not self.current_category:
            self.analyze_button.setEnabled(False)
            self.table_button.setEnabled(False)
            return
        self._ensure_canvas_deletion()
        self.canvas_widget = None
        self.visualizer = None
        self.plotter = None 
        self._refresh_canvas_container()

    def _on_analyze_btn_clicked(self):
        self.last_action = "analyze"
        self._refresh_canvas_container()

    def _on_table_btn_clicked(self):
        self.last_action = "table"
        self._refresh_canvas_container()

    def _on_cageview_btn_clicked(self):
        self.last_action = "visualize"
        self._refresh_canvas_container()

    def _refresh_canvas_container(self):
        self.showMaximized()
        self._ensure_canvas_deletion()
        self.canvas_widget = None
        self.visualizer = None
        self.plotter = None
        if self.last_action == "table":
            self._show_tables()
        elif self.last_action == "visualize":
            self._monitor_cages()
        elif self.last_action == "analyze":
            self._analyze_data()
        else:
            raise KeyError(f"Invalid mode: {self.last_action}.")
        self._update_control_ui()

    def _ensure_canvas_deletion(self):
        while self.canvas_container_layout.count():
            widget = self.canvas_container_layout.takeAt(0).widget()
            if widget:
                if isinstance(widget, QtWidgets.QGraphicsView) and self.visualizer:
                    try:
                        widget.viewport().removeEventFilter(self.visualizer)
                    except RuntimeError as e:
                        logging.warning(f"Failed to remove event filter from old canvas: {e}")
                widget.deleteLater()

    #########################################################################################################################

    def transfer_mouse_action(self, action_type): # Wrapper for transfer
        self.selected_mouse = self.visualizer.selected_mouse
        logging.debug(f"GUI: Initiating transfer action: {action_type} for mouse ID: {self.selected_mouse.get('ID')}")
        transfer_instance = mtrans.MouseTransfer(self, self.mouse_dict, self.current_category, self.visualizer.mice_status)
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
        self.selected_mouse = None

    def add_new_mouse_entry(self):
        self.editor = medit.MouseEditor(self, self.mouse_dict, None, mode="new")
        self.editor.exec()

    def edit_selected_mouse_entry(self):
        self.selected_mouse = self.visualizer.selected_mouse
        self.editor = medit.MouseEditor(self, self.mouse_dict, self.selected_mouse, mode="edit")
        self.editor.exec()
        self.selected_mouse = None

    #########################################################################################################################

    def commit_seppuku(self, event):
        """Handles the close event for the main window."""
        if not self.is_saved and not self.is_debug:
            reply = QMessageBox.question(self, "Unsaved Changes",
            "You have unsaved changes. Do you really want to close without saving?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore()
                return
                
        if self.canvas_widget:
            self.canvas_widget.deleteLater()

        event.accept()

if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    mdb_main = MDB_App()
    mdb_main.show()
    app.exec()