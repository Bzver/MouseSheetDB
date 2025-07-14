from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLineEdit, QMessageBox, QLabel, QPushButton, QRadioButton

import mdb_utils as mut

import logging

class MouseEditor(QtWidgets.QDialog):
    def __init__(self, parent, mouseDB, selected_mouse, mode="edit"):
        """
        Initializes the MouseEditor class, in charge of the sole implementation of mice
        data edit (e.g. toe, genotype, day of birth) for correction.
        Args:
            parent: The parent PySide6 widget.
            gui: The main GUI instance.
            mouseDB: The mouse database object.
            selected_mouse: The dictionary representing the currently selected mouse,
            derived from gui and mouse_artists.
            mode (str): The mode of the editor ("edit" or "add").
        """
        super().__init__(parent)
        self.mouseDB = mouseDB
        self.gui = parent
        self.selected_mouse = selected_mouse
        self.mode = mode

        self.setWindowTitle(f"{mode.capitalize()} Mouse Entries")
        self.setModal(True)

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.edit_entry_form_layout = QtWidgets.QGridLayout()
        self.main_layout.addLayout(self.edit_entry_form_layout)

        self.edit_mouse_var = self.selected_mouse if self.mode == "edit" else None
        
        self.edit_sex_group = QtWidgets.QButtonGroup(self)
        self.edit_toe_entry = QLineEdit()
        self.edit_genotype_entry = QLineEdit()
        self.edit_birthdate_entry = QLineEdit()
        self.edit_breeddate_entry = QLineEdit()
        
        # ID animation control
        self.reroll_active = False
        self.reroll_timer = QTimer(self)
        self.reroll_timer.timeout.connect(self._update_id_animation)
        self.reroll_delay = 50  # Milliseconds between updates

        self.setup_editor_ui()

    def setup_editor_ui(self):
        """Sets up the UI elements for the MouseEditor."""
        self.edit_id_element()
        self.edit_sex_element()
        self.edit_toe_element()
        self.edit_genotype_element()
        self.edit_birthdate_element()
        self.edit_breeddate_element()

        self.save_edit_button = QPushButton("Save Changes")
        save_command = getattr(self, f"save_{self.mode}_entry")
        self.save_edit_button.clicked.connect(save_command)
        self.save_edit_button.setEnabled(False)
        self.main_layout.addWidget(self.save_edit_button)

    def edit_id_element(self):
        """
        Creates and configures the ID entry element.
        Handles ID display for editing entries.
        And random ID generation (cosmetical only) for new entries.
        """
        id_label = QLabel("ID:")
        self.disp_id_entry = QLineEdit()
        self.edit_entry_form_layout.addWidget(id_label, 0, 0)
        self.edit_entry_form_layout.addWidget(self.disp_id_entry, 0, 1, 1, 2) # Span 2 columns

        if self.mode == "edit":
            disp_id_content = self.edit_mouse_var.get("ID")
            self.disp_id_entry.setText(disp_id_content)
            self.disp_id_entry.setReadOnly(True)
        else:
            self.reroll_active = False  # Flag to control animation
            self.reroll_delay = 50  # FPS = 1000 / 50 = 20
            self.disp_id_entry.setFocusPolicy(Qt.NoFocus) # Disable focus to prevent manual editing
            self.reroll_timer.start(self.reroll_delay) # Start animation immediately for new entry
            self.disp_id_entry.setReadOnly(True)

    def _update_id_animation(self):
        """Updates the ID display with a random ID."""
        if self.reroll_active:
            self.disp_id_entry.setText(mut.generate_random_id())
        else:
            self.reroll_timer.stop()

    def edit_sex_element(self):
        """
        Creates and configures the sex selection element (radio buttons).
        """
        sex_label = QLabel("Sex:")
        male_radio_edit = QRadioButton("♂")
        female_radio_edit = QRadioButton("♀")

        self.edit_sex_group.addButton(male_radio_edit)
        self.edit_sex_group.addButton(female_radio_edit)

        sex_layout = QtWidgets.QHBoxLayout()
        sex_layout.addWidget(male_radio_edit)
        sex_layout.addWidget(female_radio_edit)
        sex_layout.addStretch(1) # Push buttons to the left

        self.edit_entry_form_layout.addWidget(sex_label, 1, 0)
        self.edit_entry_form_layout.addLayout(sex_layout, 1, 1, 1, 2)

        if self.mode == "edit":
            if self.edit_mouse_var.get("sex", "♂") == "♂":
                male_radio_edit.setChecked(True)
            else:
                female_radio_edit.setChecked(True)
        else:
            male_radio_edit.setChecked(True) # Default for new entry

    def edit_toe_element(self):
        """
        Creates and configures the toe entry element.
        """
        toe_label = QLabel("Toe:")
        self.edit_entry_form_layout.addWidget(toe_label, 2, 0)
        self.edit_entry_form_layout.addWidget(self.edit_toe_entry, 2, 1, 1, 2)

        if self.mode == "edit":
            self.edit_toe_entry.setText(self.edit_mouse_var.get("toe", "").replace("toe", ""))

    def edit_genotype_element(self):
        """
        Creates and configures the genotype entry element.
        """
        genotype_label = QLabel("Genotype:")
        self.edit_entry_form_layout.addWidget(genotype_label, 3, 0)
        self.edit_entry_form_layout.addWidget(self.edit_genotype_entry, 3, 1, 1, 2)

        if self.mode == "edit":
            self.edit_genotype_entry.setText(self.edit_mouse_var.get("genotype", ""))

    def edit_birthdate_element(self):
        """
        Creates and configures the birth date entry element.
        """
        birthdate_label = QLabel("Birth Date:")
        self.edit_entry_form_layout.addWidget(birthdate_label, 4, 0)
        self.edit_entry_form_layout.addWidget(self.edit_birthdate_entry, 4, 1, 1, 2)
        self.edit_birthdate_entry.textChanged.connect(self._save_blocker)

        if self.mode == "edit":
            birth_date = self.edit_mouse_var.get("birthDate", "")
            birth_date_str = mut.convert_date_to_string(birth_date)
            self.edit_birthdate_entry.setText(birth_date_str)

    def edit_breeddate_element(self):
        """
        Creates and configures the breed date entry element.
        """
        breeddate_label = QLabel("Breed Date:")
        self.edit_entry_form_layout.addWidget(breeddate_label, 5, 0)
        self.edit_entry_form_layout.addWidget(self.edit_breeddate_entry, 5, 1, 1, 2)
        self.edit_breeddate_entry.textChanged.connect(self._save_blocker)

        if self.mode == "edit" and self.edit_mouse_var.get("category") != "BACKUP":
            breed_date = self.edit_mouse_var.get("breedDate", "")
            breed_date_str = mut.convert_date_to_string(breed_date)
            self.edit_breeddate_entry.setText(breed_date_str)
        else:
            self.edit_breeddate_entry.setText("Non Applicable")
            self.edit_breeddate_entry.setReadOnly(True)

    def _validate_birthdate_input(self):
        """
        Validates the birth date input from the entry field.
        Returns:
            bool: True if the birth date is valid, False otherwise.
        """
        input_date_str = self.edit_birthdate_entry.text()
        logging.debug(f"Birth Date Input: '{input_date_str}'")
        validated_date = mut.convert_to_date(input_date_str)
        if validated_date is None:
            logging.debug(f"Invalid Birth Date detected: '{input_date_str}'")
            self.edit_birthdate_entry.setStyleSheet("background-color: salmon;")
            return False
        else:
            logging.debug(f"Valid Birth Date: '{input_date_str}' -> {validated_date}")
            self.edit_birthdate_entry.setStyleSheet("") # Clear background color
            return True

    def _validate_breeddate_input(self):
        """
        Validates the breed date input from the entry field.
        Returns:
            bool: True if the breed date is valid or "Non Applicable", False otherwise.
        """
        input_date_str = self.edit_breeddate_entry.text()
        logging.debug(f"Breed Date Input: '{input_date_str}'")
        validated_date = mut.convert_to_date(input_date_str)
        if validated_date is None and input_date_str not in ["", "Non Applicable"]:
            logging.debug(f"Invalid Breed Date detected: '{input_date_str}'")
            self.edit_breeddate_entry.setStyleSheet("background-color: salmon;")
            return False
        else:
            logging.debug(f"Valid Breed Date: '{input_date_str}' -> {validated_date}")
            self.edit_breeddate_entry.setStyleSheet("")
            return True

    def _start_reroll(self):
        """
        Starts the ID reroll animation.
        """
        self.reroll_active = True
        self.reroll_timer.start(self.reroll_delay)

    def _stop_reroll(self):
        """Stops the ID reroll animation."""
        self.reroll_active = False
        self.reroll_timer.stop()

    def _save_blocker(self):
        """
        Enables or disables the save button based on the validity of date inputs.
        """
        if self._validate_birthdate_input() and self._validate_breeddate_input():
            self.save_edit_button.setEnabled(True)  # Enable button when valid
        else:
            self.save_edit_button.setEnabled(False)  # Disable button when invalid

    def save_new_entry(self):
        """
        Saves a new mouse entry to the database.
        Performs basic validation and generates a unique ID.
        """
        logging.debug("save_new_entry called.")
        cage = "Waiting Room"
        selected_sex_button = self.edit_sex_group.checkedButton()
        sex = selected_sex_button.text() if selected_sex_button else ""
        toe_input = self.edit_toe_entry.text()
        genotype = self.edit_genotype_entry.text()
        birth_date_str = self.edit_birthdate_entry.text()

        # Basic validation
        if not all([sex, toe_input, genotype, birth_date_str]):
            QMessageBox.critical(self, "Input Error", "All fields must be filled for a new entry.")
            return

        # Format toe
        toe = f"toe{toe_input}" if not toe_input.startswith("toe") else toe_input

        birth_date = mut.convert_to_date(birth_date_str)
        age = mut.date_to_days(birth_date)

        # Generate a unique ID for the new mouse
        genoID = mut.process_genotypeID(genotype)
        dobID = mut.process_birthDateID(birth_date_str)
        toeID = mut.process_toeID(toe)
        sexID = mut.process_sexID(sex)
        cageID = mut.process_cageID(cage)
        new_id = f"{genoID}{dobID}{toeID}{sexID}{cageID}"

        new_mouse_data = {
            "ID": new_id,
            "cage": cage,
            "sex": sex,
            "toe": toe,
            "genotype": genotype,
            "birthDate": birth_date,
            "age": age,
            "breedDate": None,
            "breedDays": None,
            "nuCA": cage,
            "category": cage
        }

        # Find a unique key for the new entry in mouseDB
        new_key = len(self.mouseDB) if self.mouseDB else 0
        while new_key in self.mouseDB:
            new_key += 1
        self.mouseDB[new_key] = new_mouse_data

        QMessageBox.information(self, "Success", f"New mouse entry added with ID: {new_id}")
        self._close_and_refresh()

    def save_edit_entry(self):
        """
        Saves the edited mouse entry to the database.
        Validates inputs and updates the corresponding mouse data.
        """
        logging.debug("save_edit_entry called.")
        selected_id = self.edit_mouse_var.get("ID")
        if not selected_id:
            logging.warning("No mouse selected for editing.")
            QMessageBox.critical(self, "Selection Error", "Please select a mouse to edit.")
            return

        # Find the mouse in mouseDB using direct lookup
        if selected_id in self.mouseDB:
            mouse_key_to_update = selected_id
        else:
            logging.error(f"Selected mouse {selected_id} not found in data.")
            QMessageBox.critical(self, "Error", "Selected mouse not found in data.")
            return
        # Get updated values from form
        selected_sex_button = self.edit_sex_group.checkedButton()
        updated_sex = selected_sex_button.text() if selected_sex_button else ""
        updated_toe_input = self.edit_toe_entry.text()
        updated_genotype = self.edit_genotype_entry.text()
        updated_birth_date_str = self.edit_birthdate_entry.text()
        updated_breed_date_str = self.edit_breeddate_entry.text()
        logging.debug(f"Retrieved form values: Sex={updated_sex}, Toe={updated_toe_input}, Genotype={updated_genotype}, BirthDate={updated_birth_date_str}, BreedDate={updated_breed_date_str}")

        # Basic validation
        if not all([updated_sex, updated_toe_input, updated_genotype, updated_birth_date_str]):
            logging.warning("Missing required fields for edited entry.")
            QMessageBox.critical(self, "Input Error", "All fields (except Breed Date) must be filled for an edited entry.")
            return

        # Format toe
        updated_toe = f"toe{updated_toe_input}" if not updated_toe_input.startswith("toe") else updated_toe_input
        logging.debug(f"Formatted toe: {updated_toe}")

        updated_birth_date = mut.convert_to_date(updated_birth_date_str)
        if updated_breed_date_str and updated_breed_date_str != "Non Applicable":
            updated_breed_date = mut.convert_to_date(updated_breed_date_str)
        else: updated_breed_date = None
        
        age = mut.date_to_days(updated_birth_date)
        breed_days = mut.date_to_days(updated_breed_date) if updated_breed_date else None
        logging.debug(f"Calculated age_days: {age}, breed_days: {breed_days}")

        # Update the mouse data
        self.mouseDB[mouse_key_to_update]["sex"] = updated_sex
        self.mouseDB[mouse_key_to_update]["toe"] = updated_toe
        self.mouseDB[mouse_key_to_update]["genotype"] = updated_genotype
        self.mouseDB[mouse_key_to_update]["birthDate"] = updated_birth_date
        self.mouseDB[mouse_key_to_update]["age"] = age
        self.mouseDB[mouse_key_to_update]["breedDate"] = updated_breed_date if updated_breed_date else None
        self.mouseDB[mouse_key_to_update]["breedDays"] = breed_days
        logging.debug(f"Mouse {selected_id} data updated in mouseDB.")
        
        self.gui.determine_save_status() # Use gui's method to update save button state
        QMessageBox.information(self, "Success", f"Mouse entry {selected_id} updated.")
        self._close_and_refresh()

    def _close_and_refresh(self):
        """Closes the edit window and refreshes the GUI."""
        logging.debug("_close_and_refresh called.")
        self.accept() # Close the dialog
        self.gui.redraw_canvas()
        self.gui.determine_save_status()
        logging.debug("Edit window closed and GUI refreshed.")