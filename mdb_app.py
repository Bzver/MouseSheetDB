import os
import copy

from PySide6 import QtWidgets
from PySide6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox

import utils.mdb_io as mio
import utils.mdb_pedig as mped
import utils.mdb_plot as mplt
import utils.mdb_vis as mvis
import utils.mdb_edit as medit
import utils.mdb_transfer as mtrans

import traceback
import logging

logging.getLogger().setLevel(logging.INFO)

class MouseDatabaseGUI(QWidget):
    def __init__(self):
        super().__init__()
        logging.info("MouseDatabaseGUI initialized.")

        self.setWindowTitle("MiceDatabase V2.7a")

        self.main_layout = QVBoxLayout(self)

        # Top button frame
        self.button_layout = QHBoxLayout()
        self.main_layout.addLayout(self.button_layout)

        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_file)
        self.button_layout.addWidget(self.browse_button)

        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.clicked.connect(lambda:self._perform_analysis_action("analyze"))
        self.analyze_button.setEnabled(False)
        self.button_layout.addWidget(self.analyze_button)

        self.tree_button = QPushButton("Pedigree (Unimplemented)")
        self.tree_button.clicked.connect(self.family_tree)
        self.tree_button.setEnabled(False)
        self.button_layout.addWidget(self.tree_button)

        self.monitor_button = QPushButton("Monitor")
        self.monitor_button.clicked.connect(lambda:self._perform_analysis_action("monitor"))
        self.monitor_button.setEnabled(False)
        self.button_layout.addWidget(self.monitor_button)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_changes)
        self.save_button.setEnabled(False)
        self.button_layout.addWidget(self.save_button)

        # Category navigation frame
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
        self.category_textbox.setFixedWidth(200) # Adjust width as needed
        self.category_nav_layout.addWidget(self.category_textbox)

        self.next_category_button = QPushButton("Next Category ►")
        self.next_category_button.clicked.connect(self._next_category)
        self.next_category_button.setEnabled(False)
        self.category_nav_layout.addWidget(self.next_category_button)

        self.load_changelog_button = QPushButton("Load Changes")
        self.load_changelog_button.clicked.connect(self.load_changelog)
        self.load_changelog_button.setEnabled(False)
        self.category_nav_layout.addWidget(self.load_changelog_button)

        # Container for dynamically added canvas widgets
        self.canvas_container_layout = QVBoxLayout()
        self.main_layout.addLayout(self.canvas_container_layout)

        self.file_path = None
        self.backup_file = None

        self.processed_data = None
        self.mouseDB = None

        # The category is based on genotype and breeding strategy, unlike self.visualizer.status which is based on mice's cage status in a category
        # category1 ( status1, status2, status3 ... ), category 2 ( status1, status2, status3 ... ), ...
        self.current_category = None 
        self.category_index = 0
        self.category_names = ["BACKUP", "NEX + PP2A", "CMV + PP2A"]

        self.visualizer = None
        self.editor = None
        self.plotter = None
        
        self.canvas_widget = None
        self.last_action = "analyze"
        self.is_saved = True

        self.selected_mouse = None

        self.is_debug = True # Make if False before merging to main
        if self.is_debug: logging.getLogger().setLevel(logging.DEBUG)
        logging.debug(f"is_debug set to: {self.is_debug}")

    #########################################################################################################################

    def browse_file(self):
        logging.debug("browse_file called.")
        if not self.is_saved:
            reply = QMessageBox.question(self, "Unsaved Changes",
            "You have unsaved changes. Do you really want to load another excel without saving?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        self._reset_state()
        if self.load_excel_file():
            QMessageBox.information(self, "Success", "File loaded successfully!")
            self.load_changelog_button.setEnabled(True)
            self.add_entries_button.setEnabled(True)
            self._on_category_selection_changed()  # Trigger initial analysis
            logging.debug("File loaded successfully and initial analysis triggered.")

    def load_excel_file(self):
        self.file_path, _ = QFileDialog.getOpenFileName(self, "Open Excel File", "", "Excel Files (*.xlsx *.xls)")
        if not self.file_path:
            logging.debug("No file selected in load_excel_file.")
            return False
        self.is_saved = True
        try:
            mio.validate_excel(self.file_path)
            self.processed_data = mio.data_preprocess(self.file_path, "MDb")
            self.mouseDB = copy.deepcopy(self.processed_data) # Original data serving as change tracker
            self.current_category = self.category_names[0]
            self._update_control_ui()
            if self.processed_data is None:
                raise Exception("Failed to preprocess Excel data")
            logging.debug("Excel file loaded and preprocessed successfully.")
            return True
        except Exception as e:
            logging.error(f"Error loading/preprocessing file: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error loading/preprocessing file: {e}\n{traceback.format_exc()}")
            self._reset_state()
            return False

    def save_changes(self):
        logging.debug("save_changes called.")
        try:
            if self.visualizer and self.visualizer.mice_status.waiting:
                QMessageBox.critical(self, "Save Blocked","Cannot save while mice are in waiting room")
                return
            output_dir = os.path.dirname(self.file_path)
            log_file = mio.mice_changelog(self.processed_data, self.mouseDB, output_dir)
            if self.is_debug: # Save in debug no matter what
                file_suffix = os.path.splitext(self.file_path)[1]
                file_without_suffix = os.path.splitext(self.file_path)[0]
                debug_filepath = f"{file_without_suffix}_DEBUG{file_suffix}"
                mio.write_processed_data_to_excel(debug_filepath, self.mouseDB)
                logging.debug(f"Debugging! Will save to {debug_filepath}!")
                return
            if not log_file:
                logging.error("Error generating log file, save operation cancelled.")
                QMessageBox.information(self, "Changes Not Logged", f"Log file fail to generate. \n{traceback.format_exc()}")
                return
            if not mio.create_backup(self.file_path):
                logging.error("Error generating backup, save operation cancelled.")
                QMessageBox.information(self, "Backup Not created", f"Fail to create backup. \n{traceback.format_exc()}")

            logging.info(f"Changes logged and saved to: {log_file}")
            QMessageBox.information(self, "Changes Logged", f"Mice changes Logged to: \n{log_file}")
            if mio.write_processed_data_to_excel(self.file_path, self.mouseDB):
                self.processed_data = copy.deepcopy(self.mouseDB) # Update the reference data upon successfully saving
        except Exception as e:
            logging.error(f"Failed to save Excel file: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to save Excel file: {e}\n{traceback.format_exc()}")
            return

    def load_changelog(self):
        """Loads a changelog file and applies changes to the current data."""
        if not self.processed_data:
            logging.warning("load_changelog: No data loaded.")
            QMessageBox.warning(self, "No Data Loaded", "Please load an Excel file first.")
            return
        changelog_file_path, _ = QFileDialog.getOpenFileName(self, "Open Changelog File", "", "Excel Files (*.xlsx *.xls)")
        if not changelog_file_path:
            logging.debug("No changelog file selected.")
            return
        try:
            result_message, exception_entries = mio.changelog_loader(changelog_file_path, self.mouseDB)
            if exception_entries:
                result_message.append("\nThe following issues were encountered:\n" +"\n".join(exception_entries))
                logging.warning(f"Changelog applied with issues: {exception_entries}")
                QMessageBox.warning(self, "Changelog Applied with Issues","\n".join(result_message))
            else:
                logging.info("Changelog applied successfully.")
                QMessageBox.information(self, "Changelog Applied","\n".join(result_message))
            self.is_saved = False
            self.save_button.setEnabled(True)
            self._perform_analysis_action()
        except Exception as e:
            logging.error(f"Error loading or applying changelog: {e}", exc_info=True)
            QMessageBox.critical(self, "Error",f"Error loading or applying changelog: {e}\n{traceback.format_exc()}")

    #########################################################################################################################

    def analyze_data(self):
        """Prepares data for the mouse count analyze visualization and passes it to the visualizer."""
        self.last_action = "analyze" # Update last action
        logging.debug("analyze_data called.")
        try:
            # Pass the GUI instance (self) as the parent for the visualizer
            self.plotter = mplt.MousePlotter(self, self.mouseDB, self.current_category, self.canvas_widget)
            self.canvas_widget = self.plotter.display_genotype_bar_plot()
            if self.canvas_widget:
                self.canvas_container_layout.addWidget(self.canvas_widget) # Add canvas to the canvas_container
                logging.debug("Genotype bar plot displayed successfully.")
            else:
                logging.warning("Genotype bar plot was not displayed (canvas_widget is None).")
        except Exception as e:
            logging.error(f"Error plotting analysis data: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error plotting analysis data: {e}\n{traceback.format_exc()}")

    def monitor_cages(self):
        """Prepares data for the cage monitor visualization and passes it to the visualizer."""
        self.last_action = "monitor"
        logging.debug("monitor_cages called.")
        try:
            self.visualizer = mvis.MouseVisualizer(self, self.mouseDB, self.current_category, self.canvas_widget)
            self.canvas_widget = self.visualizer.display_cage_monitor()
            if self.canvas_widget:
                self.canvas_container_layout.addWidget(self.canvas_widget)
                logging.debug("Cage monitor displayed successfully.")
            else:
                logging.warning("Cage monitor was not displayed (canvas_widget is None).")
        except Exception as e:
            logging.error(f"Error displaying cage monitor: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error displaying cage monitor: {e}\n{traceback.format_exc()}")

    def family_tree(self):
        """Prepares data for the family tree visualization window and passes it to pedigree."""
        logging.debug("family_tree called.")
        try:
            # Create a new window for pedigree display in the form of MousePedigree instance, passing self as the parent
            self.pedigree = mped.MousePedigree(self, self.mouseDB)
            self.pedigree.display_family_tree_window()
            logging.debug("Family tree window displayed successfully.")
        except Exception as e:
            logging.error(f"Error displaying pedigree: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error displaying pedigree: {e}\n{traceback.format_exc()}")

    #########################################################################################################################

    def determine_save_status(self):
        if mio.find_changes_for_changelog(self.processed_data, self.mouseDB, check_only=True):
            self.is_saved = False
            self.save_button.setEnabled(True)
        else:
            self.is_saved = True
            self.save_button.setEnabled(False)

    def redraw_canvas(self):
        """Public method to trigger canvas redraw based on current state."""
        logging.debug("GUI: redraw_canvas called. Triggering _perform_analysis_action.")
        self._perform_analysis_action()
        
    def _reset_state(self):
        self.file_path = None
        self.category_names = ["BACKUP", "NEX + PP2A", "CMV + PP2A"]
        self.category_index = 0
        self.current_category = None
        self.category_textbox.setReadOnly(False)
        self.category_textbox.clear()
        self.category_textbox.setReadOnly(True)
        self.prev_category_button.setEnabled(False)
        self.next_category_button.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.monitor_button.setEnabled(False)
        self.tree_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.add_entries_button.setEnabled(False)
        self.canvas_widget = None
        self.visualizer = None # Clear visualizer reference
        self.plotter = None # Clear plotter reference

    def _update_control_ui(self):
        """Update UI elements for current category and mode"""
        self.category_textbox.setReadOnly(False)
        self.category_textbox.setText(self.current_category.center(40))
        self.category_textbox.setReadOnly(True)
        self.prev_category_button.setEnabled(True)
        self.next_category_button.setEnabled(True)
        self.monitor_button.setEnabled(True)
        self.analyze_button.setEnabled(True)
        if self.plotter: # Disable the respective button when already plotting or monitoring
            self.analyze_button.setEnabled(False)
        elif self.visualizer:
            self.monitor_button.setEnabled(False)
        self.tree_button.setEnabled(True)

    def _prev_category(self):
        """Navigate to previous category"""
        self.category_index = (self.category_index - 1) % len(self.category_names)
        self.current_category = self.category_names[self.category_index]
        self._perform_analysis_action()

    def _next_category(self):
        """Navigate to next category"""
        self.category_index = (self.category_index + 1) % len(self.category_names)
        self.current_category = self.category_names[self.category_index]
        self._perform_analysis_action()

    def _on_category_selection_changed(self, event=None):
        """Handle category selection changes (UI updates only)"""
        if not self.current_category:
            self.analyze_button.setEnabled(False)
            self.monitor_button.setEnabled(False)
            return
        self._ensure_canvas_deletion()
        self.canvas_widget = None # Ensure canvas_widget is None before creating a new one
        self.visualizer = None # Clear visualizer reference
        self.plotter = None # Clear plotter reference
        self._perform_analysis_action() # Trigger analysis based on last action
        
    def _perform_analysis_action(self, verbose=None): # Clear the canvas container layout before adding new content
        self.showMaximized()
        self._ensure_canvas_deletion()
        self.canvas_widget = None
        self.visualizer = None
        self.plotter = None
        action = verbose if verbose is not None else self.last_action
        if action == "monitor":
            self.monitor_cages()
        else:
            self.analyze_data()
        self._update_control_ui()

    def _ensure_canvas_deletion(self):
        while self.canvas_container_layout.count():
            widget = self.canvas_container_layout.takeAt(0).widget()
            if widget: # Before deleting the widget, remove the event filter if it's a QGraphicsView
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
        # Pass self (the GUI instance) as the parent for the transfer dialog
        transfer_instance = mtrans.MouseTransfer(self, self.mouseDB, self.current_category, self.visualizer.mice_status)
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
        self.selected_mouse = None # Cleanup the selected mouse

    def add_new_mouse_entry(self): # Wrapper for add
        self.editor = medit.MouseEditor(self, self.mouseDB, None, mode="new")
        self.editor.exec()

    def edit_selected_mouse_entry(self): # Wrapper for edit
        self.selected_mouse = self.visualizer.selected_mouse
        self.editor = medit.MouseEditor(self, self.mouseDB, self.selected_mouse, mode="edit")
        self.editor.exec()
        self.selected_mouse = None

    def add_selected_mouse_to_family_tree(self):
        self.selected_mouse = self.visualizer.selected_mouse
        if self.selected_mouse is not None:
            self.selected_mouse["parentF"] = "Pending"
            self.selected_mouse["parentM"] = "Pending"
            self.selected_mouse = None

    #########################################################################################################################

    def commit_seppuku(self, event):
        """Handles the close event for the main window."""
        if not self.is_saved and not self.is_debug:
            reply = QMessageBox.question(self, "Unsaved Changes",
            "You have unsaved changes. Do you really want to close without saving?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore() # Ignore the close event
                return
                
        # Clean up resources
        if self.canvas_widget:
            self.canvas_widget.deleteLater()

        event.accept() # Accept the close event

# --- Main application setup ---
if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    mdb_main = MouseDatabaseGUI()
    mdb_main.show()
    app.exec()