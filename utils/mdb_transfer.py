from PySide6 import QtWidgets
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QMessageBox

from . import mdb_helper as muh

import logging

class MouseTransfer(QDialog):
    def __init__(self, parent, mouseDB, current_category, mice_status):
        """
        Initializes the MouseTransfer class, which is responsible for transferring mice between cages (virtually).
        Args:
            parent: The parent PySide6 widget.
            mouseDB: The mouse database object.
            current_category (str): The current category (as in "BACKUP", "CMV+PP2A", etc.) of mice being displayed.
            mice_status: An object containing dictionaries of mice categorized by their status (regular, waiting, death).
        """
        super().__init__(parent)
        self.mouseDB = mouseDB
        self.gui = parent
        self.current_category = current_category
        self.mice_status = mice_status

        self.selected_mouse = None
        self.new_cage_entry = None

    def transfer_to_existing_cage(self):
        """
        Initiates the process to transfer a selected mouse to an existing cage.
        Opens a dialog for the user to select a target cage.
        """
        logging.debug(f"TRANSFER: transfer_to_existing_cage called for mouse ID: {self.gui.selected_mouse.get('ID')}")
        self.selected_mouse = self.gui.selected_mouse # Ensure we are working with the currently selected mouse from GUI
        if self.selected_mouse is not None:
            dialog = QDialog(self) # Parent is self (MouseTransfer dialog)
            dialog.setWindowTitle("Select Target Cage")
            dialog.setModal(True) # Make it modal
            dialog.setGeometry(100, 300, 300, 150) # x, y, width, height (adjust as needed)

            layout = QtWidgets.QVBoxLayout(dialog)
            layout.addWidget(QLabel("Select a cage:"))

            current_cage = self.selected_mouse.get("nuCA")
            existing_cages = sorted([c for c in self.mice_status.regular if c != current_cage])

            if not existing_cages:
                logging.debug("No other existing cages available for transfer.")
                QMessageBox.information(dialog, "No Cages", "No other existing cages available for transfer.")
                dialog.close()
                return

            cage_dropdown = QtWidgets.QComboBox()
            cage_dropdown.addItems(existing_cages)
            layout.addWidget(cage_dropdown)

            transfer_button = QPushButton("Transfer")
            transfer_button.clicked.connect(lambda: self.confirm_transfer(dialog, cage_dropdown.currentText()))
            layout.addWidget(transfer_button)

            dialog.exec() # Show as modal dialog
        self._cleanup_post_transfer()

    def transfer_to_waiting_room(self):
        """
        Transfers the selected mouse to the "Waiting Room" category.
        Removes the mouse from its current regular or death row cage and adds it to the waiting room.
        """
        logging.debug(f"TRANSFER: transfer_to_waiting_room called for mouse ID: {self.gui.selected_mouse.get('ID')}")
        self.selected_mouse = self.gui.selected_mouse # Ensure we are working with the currently selected mouse from GUI
        if self.selected_mouse is not None:
            logging.debug(f"TRANSFER: Before modification - Regular: {len(self.mice_status.regular)}, Waiting: {len(self.mice_status.waiting)}, Death: {len(self.mice_status.death)}")
            logging.debug(f"Attempting to transfer mouse {self.selected_mouse} to Waiting Room.")
            current_cage = self.selected_mouse.get("nuCA")
            if current_cage and current_cage in self.mice_status.regular:
                mice_list = self.mice_status.regular[current_cage]
                if self.selected_mouse in mice_list:
                    mice_list.remove(self.selected_mouse)
                    logging.debug(f"TRANSFER: Removed mouse {self.selected_mouse} from regular cage {current_cage}.")
                    if not mice_list:
                        del self.mice_status.regular[current_cage]
                        logging.debug(f"TRANSFER: Deleted empty regular cage {current_cage}.")

            if self.selected_mouse["ID"] in self.mice_status.death:
                del self.mice_status.death[self.selected_mouse["ID"]]
                logging.debug(f"Removed mouse from death row.")

            self.selected_mouse["nuCA"] = "Waiting Room"
            self.selected_mouse["category"] = "Waiting Room"
            self.mice_status.waiting[self.selected_mouse["ID"]] = self.selected_mouse
            logging.debug(f"TRANSFER: Mouse {self.selected_mouse.get('ID')} added to waiting room.")
            logging.debug(f"TRANSFER: After modification - Regular: {len(self.mice_status.regular)}, Waiting: {len(self.mice_status.waiting)}, Death: {len(self.mice_status.death)}")
        self._cleanup_post_transfer()

    def transfer_to_new_cage(self):
        """
        Initiates the process to transfer a selected mouse to a newly created cage.
        Opens a dialog for the user to enter a new cage number.
        """
        logging.debug(f"TRANSFER: transfer_to_new_cage called for mouse ID: {self.gui.selected_mouse.get('ID')}")
        self.selected_mouse = self.gui.selected_mouse # Ensure we are working with the currently selected mouse from GUI
        dialog = QDialog(self) # Parent is self (MouseTransfer dialog)
        dialog.setWindowTitle("Enter New Cage Number")
        dialog.setModal(True)
        dialog.setGeometry(100, 300, 300, 150)

        layout = QtWidgets.QVBoxLayout(dialog)
        layout.addWidget(QLabel("Enter the new cage number:"))

        prefix = ""
        if self.current_category == "NEX + PP2A":
            prefix = "2-A-"
        elif self.current_category == "CMV + PP2A":
            prefix = "8-A-"
        logging.debug(f"New cage prefix: {prefix}")

        prefix_label = QLabel(prefix)
        self.new_cage_entry = QtWidgets.QLineEdit()
        
        input_layout = QtWidgets.QHBoxLayout()
        input_layout.addWidget(prefix_label)
        input_layout.addWidget(self.new_cage_entry)
        layout.addLayout(input_layout)

        transfer_button = QPushButton("Transfer")
        transfer_button.clicked.connect(lambda: self.validate_and_transfer(dialog))
        layout.addWidget(transfer_button)

        self.new_cage_entry.setFocus() # Set focus to the entry widget
        dialog.exec() # Show as modal dialog

    def transfer_to_death_row(self):
        """
        Transfers the selected mouse to the "Death Row" category.
        Removes the mouse from its current regular or waiting room cage and adds it to death row.
        """
        logging.debug(f"TRANSFER: transfer_to_death_row called for mouse ID: {self.gui.selected_mouse.get('ID')}")
        self.selected_mouse = self.gui.selected_mouse # Ensure we are working with the currently selected mouse from GUI
        if self.selected_mouse is not None:
            logging.debug(f"TRANSFER: Before modification - Regular: {len(self.mice_status.regular)}, Waiting: {len(self.mice_status.waiting)}, Death: {len(self.mice_status.death)}")
            logging.debug(f"Attempting to transfer mouse {self.selected_mouse} to Death Row.")
            current_cage = self.selected_mouse.get("nuCA")
            if current_cage and current_cage in self.mice_status.regular:
                mice_list = self.mice_status.regular[current_cage]
                if self.selected_mouse in mice_list:
                    mice_list.remove(self.selected_mouse)
                    logging.debug(f"TRANSFER: Removed mouse {self.selected_mouse} from regular cage {current_cage}.")
                    if not mice_list:
                        del self.mice_status.regular[current_cage]
                        logging.debug(f"TRANSFER: Deleted empty regular cage {current_cage}.")

            self._remove_from_dict("waiting")
            logging.debug(f"Removed mouse from waiting room dict (if present).")

            self.selected_mouse["nuCA"] = "Death Row"
            self.selected_mouse["category"] = "Death Row"
            self.mice_status.death[self.selected_mouse["ID"]] = self.selected_mouse
            
            logging.debug(f"TRANSFER: Mouse {self.selected_mouse.get('ID')} added to death row.")
            logging.debug(f"TRANSFER: After modification - Regular: {len(self.mice_status.regular)}, Waiting: {len(self.mice_status.waiting)}, Death: {len(self.mice_status.death)}")
        self._cleanup_post_transfer()

    def transfer_from_death_row(self):
        """
        Transfers the selected mouse from "Death Row" back to its original cage.
        Restores the mouse's original cage and category, and adds it back to the regular cages.
        """
        logging.debug(f"TRANSFER: transfer_from_death_row called for mouse ID: {self.gui.selected_mouse.get('ID')}")
        self.selected_mouse = self.gui.selected_mouse # Ensure we are working with the currently selected mouse from GUI
        if self.selected_mouse is not None:
            logging.debug(f"TRANSFER: Before modification - Regular: {len(self.mice_status.regular)}, Waiting: {len(self.mice_status.waiting)}, Death: {len(self.mice_status.death)}")
            logging.debug(f"Attempting to transfer mouse {self.selected_mouse.get('ID')} from Death Row.")
            self._remove_from_dict("death")
            logging.debug(f"TRANSFER: Removed mouse from death row dict.")

            original_cage = self.selected_mouse["cage"]
            self.selected_mouse["nuCA"] = original_cage
            self.selected_mouse["category"] = muh.assign_category(original_cage)
            logging.debug(f"Mouse {self.selected_mouse.get('ID')} restored to original cage {original_cage} and category {self.selected_mouse['category']}.")

            if self.selected_mouse["category"] == self.current_category:
                if original_cage not in self.mice_status.regular:
                    self.mice_status.regular[original_cage] = []
                    logging.debug(f"TRANSFER: Created new regular cage entry for {original_cage}.")
                self.mice_status.regular[original_cage].append(self.selected_mouse)
                logging.debug(f"TRANSFER: Mouse {self.selected_mouse.get('ID')} added to regular cage {original_cage}.")
            logging.debug(f"TRANSFER: After modification - Regular: {len(self.mice_status.regular)}, Waiting: {len(self.mice_status.waiting)}, Death: {len(self.mice_status.death)}")
        self._cleanup_post_transfer()

    #########################################################################################################################

    def confirm_transfer(self, dialog, target_cage, mode="existing"):
        """
        Confirms and executes the transfer of a selected mouse to an existing cage.
        Args:
            dialog: The PySide6 QDialog window for cage selection.
            target_cage (str): The selected target cage number.
            mode (str): "existing" or "new"
        """
        logging.debug(f"TRANSFER: confirm_transfer called for mouse ID: {self.gui.selected_mouse.get('ID')}")
        self.selected_mouse = self.gui.selected_mouse # Ensure working with the currently selected mouse from GUI
        taCA = target_cage

        current_cage = self.selected_mouse.get("nuCA")
        if current_cage in self.mice_status.regular:
            mice_list = self.mice_status.regular[current_cage]
            if self.selected_mouse in mice_list: # Remove mice from original cage display
                mice_list.remove(self.selected_mouse)
                if not mice_list: # Remove the empty cages
                    del self.mice_status.regular[current_cage]

        self._remove_from_dict("waiting")

        self.selected_mouse["nuCA"] = taCA
        self.selected_mouse["category"] = muh.assign_category(taCA) if mode == "existing" else self.current_category

        if taCA not in self.mice_status.regular:
            self.mice_status.regular[taCA] = []
        self.mice_status.regular[taCA].append(self.selected_mouse)
        self._cleanup_post_transfer(dialog)

    def validate_and_transfer(self, dialog):
        """
        Validates the new cage number input and transfers the selected mouse to the new cage.
        Args:
            dialog: The PySide6 QDialog window for new cage input.
        """
        logging.debug("validate_and_transfer called.")
        entered_name = self.new_cage_entry.text().strip()
        logging.debug(f"Entered new cage name: {entered_name}")
        
        if not entered_name:
            QMessageBox.warning(dialog, "Invalid Input", "Please enter the cage number.")
            return
        if not entered_name[0].isdigit() or not entered_name[-1].isdigit():
            QMessageBox.warning(dialog, "Invalid Input", "Must start and end with digits.")
            return
        
        prefix = ""
        if self.current_category == "BACKUP":
            if "-B-" in entered_name:
                prefix = entered_name.split("-B-")[0] + "-B-"
                entered_suffix = entered_name.split("-B-")[1]
            else:
                entered_suffix = entered_name
        else: entered_suffix = entered_name
        logging.debug(f"Prefix: {prefix}, Entered suffix: {entered_suffix}")

        digits_only = entered_suffix.replace("-","")
        logging.debug(f"Digits only from suffix: {digits_only}")

        if len(digits_only) == 0:
            QMessageBox.warning(dialog, "Invalid Input", "Must include at least one digit sans prefix.")
            return
        if not digits_only.isdigit():
            QMessageBox.warning(dialog, "Invalid Input", "Only numbers and '-' are allowed sans prefix.")
            return
        if len(digits_only) > 4:
            QMessageBox.warning(dialog, "Invalid Input", "Can only include four digits at most sans prefix.")
            return
        
        new_cage_no = prefix + entered_suffix
        logging.debug(f"Final new cage number: {new_cage_no}")

        if new_cage_no in self.mice_status.regular: # Check if key exists in the dict
            QMessageBox.warning(dialog, "Cage Exists", f"Cage '{new_cage_no}' already exists. Please enter a different number.")
            self.new_cage_entry.clear()
            return
        if self.current_category == "BACKUP" and (new_cage_no.startswith("8-A-") or new_cage_no.startswith("2-A-")):
            QMessageBox.warning(dialog, "Format Error", f"Backup cages are not supposed to start with '8-A-' or '2-A-'. Please enter a different number.")
            self.new_cage_entry.clear()
            return
        
        self.confirm_transfer(dialog, new_cage_no, "new")
        
    def _remove_from_dict(self, container_type: str):
        """
        Removes the selected mouse from a specified dictionary (e.g., 'waiting' or 'death').
        Args:
            container_type (str): The name of the dictionary to remove the mouse from (e.g., "waiting", "death").
        """
        # Get the dict from string (e.g. "waiting" -> waiting)
        target_dict = getattr(self.mice_status, container_type)
        # Remove mouse ID if it exists
        if self.selected_mouse["ID"] in target_dict:
            del target_dict[self.selected_mouse["ID"]]

    def _cleanup_post_transfer(self, dialog=None):
        """
        Performs cleanup actions after a mouse transfer operation.
        Closes the dialog (if provided), redraws the GUI canvas,
        updates the save status, and closes the metadata window.
        Args:
            dialog: The PySide6 QDialog window to close (optional).
        """
        if dialog:
            dialog.close()
        logging.debug("TRANSFER: _cleanup_post_transfer called. Calling gui.redraw_canvas().")
        self.mouseDB[self.selected_mouse["ID"]] = self.selected_mouse # Update the main mouseDB
        self.gui.redraw_canvas()
        self.gui.determine_save_status()