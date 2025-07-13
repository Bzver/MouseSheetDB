import tkinter as tk
from tkinter import messagebox
from datetime import datetime

import mdb_utils as mut

import logging

class MouseEditor:
    def __init__(self, master, gui, mouseDB, selected_mouse, mode="edit"):
        self.master = master
        self.mouseDB = mouseDB
        self.gui = gui
        self.selected_mouse = selected_mouse
        self.mode = mode

        self.edit_window = None
        self.edit_entry_frame = None

        self.edit_mouse_var = None
        
        self.edit_sex_var = None
        self.edit_toe_entry = None
        self.edit_genotype_entry = None
        self.edit_birthdate_entry = None
        self.edit_breeddate_entry = None
        
        # ID animation control
        self.reroll_active = False
        self.reroll_delay = 50  # Milliseconds between updates

    def edit_mouse_entries(self):
        self.edit_window = tk.Toplevel(self.master)
        self.edit_window.title(f"{self.mode.capitalize} Mouse Entries")
        self.edit_window.protocol("WM_DELETE_WINDOW", self._on_edit_window_close)

        self.edit_mouse_var = self.selected_mouse if self.mode == "edit" else None
        self.edit_entry_frame = tk.Frame(self.edit_window)
        self.edit_entry_frame.pack(pady=10)

        for widget in self.edit_entry_frame.winfo_children():
            widget.destroy()
        
        self.edit_ID_element()
        self.edit_gender_element()
        self.edit_toe_element()
        self.edit_genotype_element()
        self.edit_birthdate_element()
        self.edit_breeddate_element()

        save_command = getattr(self, f"save_{self.mode}_entry")
        self.save_edit_button = tk.Button(self.edit_entry_frame, text="Save Changes", command=save_command)
        self.save_edit_button.grid(row=7, column=0, columnspan=3, pady=10)

    def edit_ID_element(self):
        tk.Label(self.edit_entry_frame, text = "ID:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        disp_id = tk.Entry(self.edit_entry_frame)
        disp_id.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        if self.mode == "edit":
            disp_id_content = self.edit_mouse_var.get("ID")
            disp_id.insert(0, disp_id_content) 
            disp_id.config(state="readonly")
        else:
            self.reroll_active = False  # Flag to control animation
            self.reroll_delay = 50  # FPS = 1000 / 50 = 20
            def update_id_animation():
                if self.reroll_active:
                    disp_id.config(state="normal")
                    disp_id.delete(0, tk.END)
                    disp_id.insert(0, mut.generate_random_id())
                    disp_id.config(state="readonly")
                    self.edit_window.after(self.reroll_delay, update_id_animation)
            self.edit_window.bind("<FocusIn>", lambda e: self._start_reroll(update_id_animation))
            self.edit_window.bind("<FocusOut>", lambda e: self._stop_reroll())

    def edit_gender_element(self):
        tk.Label(self.edit_entry_frame, text="Sex:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.edit_sex_var = tk.StringVar(self.edit_entry_frame)
        male_radio_edit = tk.Radiobutton(self.edit_entry_frame, text="♂", variable=self.edit_sex_var, value="♂")
        female_radio_edit = tk.Radiobutton(self.edit_entry_frame, text="♀", variable=self.edit_sex_var, value="♀")
        male_radio_edit.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        female_radio_edit.grid(row=2, column=2, padx=5, pady=5, sticky="w")

        if self.mode == "edit":
            self.edit_sex_var.set(self.edit_mouse_var.get("sex", "♂"))
        else:
            self.edit_sex_var.set("♂ ")

    def edit_toe_element(self):
        tk.Label(self.edit_entry_frame, text="Toe:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.edit_toe_entry = tk.Entry(self.edit_entry_frame)
        self.edit_toe_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        if self.mode == "edit":
            self.edit_toe_entry.insert(0, self.edit_mouse_var.get("toe", "").replace("toe", ""))

    def edit_genotype_element(self):
        tk.Label(self.edit_entry_frame, text="Genotype:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.edit_genotype_entry = tk.Entry(self.edit_entry_frame)
        self.edit_genotype_entry.grid(row=4, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        if self.mode == "edit":
            self.edit_genotype_entry.insert(0, self.edit_mouse_var.get("genotype", ""))

    def edit_birthdate_element(self):
        tk.Label(self.edit_entry_frame, text="Birth Date:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.edit_birthdate_entry = tk.Entry(self.edit_entry_frame)
        self.edit_birthdate_entry.grid(row=5, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.edit_birthdate_entry.bind("<KeyRelease>", self._save_blocker)

        if self.mode == "edit":
            birth_date = self.edit_mouse_var.get("birthDate", "")
            birth_date_str = mut.convert_date_to_string(birth_date)
            self.edit_birthdate_entry.insert(0, birth_date_str)

    def edit_breeddate_element(self):
        tk.Label(self.edit_entry_frame, text="Breed Date:").grid(row=6, column=0, padx=5, pady=5, sticky="w")
        self.edit_breeddate_entry = tk.Entry(self.edit_entry_frame)
        self.edit_breeddate_entry.grid(row=6, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.edit_breeddate_entry.bind("<KeyRelease>", self._save_blocker)

        if self.mode == "edit" and self.edit_mouse_var.get("category") != "BACKUP":
            breed_date = self.edit_mouse_var.get("breedDate", "")
            breed_date_str = mut.convert_date_to_string(breed_date)
            self.edit_breeddate_entry.insert(0, breed_date_str)
        else:
            self.edit_breeddate_entry.insert(0, "Non Applicable")
            self.edit_breeddate_entry.config(state="readonly")

    def _validate_birthdate_input(self):
        input_date_str = self.edit_birthdate_entry.get()
        logging.debug(f"Birth Date Input: '{input_date_str}'")
        validated_date = mut.convert_to_date(input_date_str)
        if validated_date is None:
            logging.debug(f"Invalid Birth Date detected: '{input_date_str}'")
            self.edit_birthdate_entry.config(bg="salmon")
            return False
        else:
            logging.debug(f"Valid Birth Date: '{input_date_str}' -> {validated_date}")
            self.edit_birthdate_entry.config(bg="white")
            return True

    def _validate_breeddate_input(self):
        input_date_str = self.edit_breeddate_entry.get()
        logging.debug(f"Breed Date Input: '{input_date_str}'")
        validated_date = mut.convert_to_date(input_date_str)
        if validated_date is None and input_date_str not in ["", "Non Applicable"]:
            logging.debug(f"Invalid Breed Date detected: '{input_date_str}'")
            self.edit_breeddate_entry.config(bg="salmon")
            return False
        else:
            logging.debug(f"Valid Breed Date: '{input_date_str}' -> {validated_date}")
            self.edit_breeddate_entry.config(bg="white")
            return True

    def _start_reroll(self, callback):
        self.reroll_active = True
        callback()  # Start animation

    def _stop_reroll(self):
        self.reroll_active = False

    def _save_blocker(self, event=None):
        if self._validate_birthdate_input() and self._validate_breeddate_input():
            self.save_edit_button["state"] = tk.NORMAL  # Enable button when valid
        else:
            self.save_edit_button["state"] = tk.DISABLED  # Disable button when invalid

    def save_new_entry(self):
        logging.debug("save_new_entry called.")
        cage = "Waiting Room"
        sex = self.edit_sex_var.get()
        toe_input = self.edit_sex_var.get()
        genotype = self.edit_sex_var.get()
        birth_date_str = self.edit_sex_var.get()

        # Basic validation
        if not all([sex, toe_input, genotype, birth_date_str]):
            messagebox.showerror("Input Error", "All fields must be filled for a new entry.")
            return

        # Format toe
        toe = f"toe{toe_input}" if not toe_input.startswith("toe") else toe_input

        age_days = mut.date_to_days(birth_date_str)

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
            "birthDate": birth_date_str,
            "age": age_days,
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

        messagebox.showinfo("Success", f"New mouse entry added with ID: {new_id}")
        self._close_and_refresh()

    def save_edit_entry(self):
        logging.debug("save_edit_entry called.")
        selected_id = self.edit_mouse_var.get("ID")
        if not selected_id:
            logging.warning("No mouse selected for editing.")
            messagebox.showerror("Selection Error", "Please select a mouse to edit.")
            return

        # Find the mouse in mouseDB
        mouse_key_to_update = None
        for key, mouse_data in self.mouseDB.items():
            if mouse_data.get("ID") == selected_id:
                mouse_key_to_update = key
                break

        if mouse_key_to_update is None:
            logging.error(f"Selected mouse {selected_id} not found in data.")
            messagebox.showerror("Error", "Selected mouse not found in data.")
            return

        # Get updated values from form
        updated_sex = self.edit_sex_var.get()
        updated_toe_input = self.edit_toe_entry.get()
        updated_genotype = self.edit_genotype_entry.get()
        updated_birth_date_str = self.edit_birthdate_entry.get()
        updated_breed_date_str = self.edit_breeddate_entry.get()
        logging.debug(f"Retrieved form values: Sex={updated_sex}, Toe={updated_toe_input}, Genotype={updated_genotype}, BirthDate={updated_birth_date_str}, BreedDate={updated_breed_date_str}")

        # Basic validation
        if not all([updated_sex, updated_toe_input, updated_genotype, updated_birth_date_str]):
            logging.warning("Missing required fields for edited entry.")
            messagebox.showerror("Input Error", "All fields (except Breed Date) must be filled for an edited entry.")
            return

        # Format toe
        updated_toe = f"toe{updated_toe_input}" if not updated_toe_input.startswith("toe") else updated_toe_input
        logging.debug(f"Formatted toe: {updated_toe}")

        updated_birth_date = datetime.strptime(updated_birth_date_str, "%y-%m-%d")
        if updated_breed_date_str and updated_breed_date_str != "Non Applicable":
            updated_breed_date = datetime.strptime(updated_breed_date_str, "%y-%m-%d")
        else: updated_breed_date = None
        
        age_days = mut.date_to_days(updated_birth_date)
        breed_days = mut.date_to_days(updated_breed_date) if updated_breed_date else None
        logging.debug(f"Calculated age_days: {age_days}, breed_days: {breed_days}")

        # Update the mouse data
        self.mouseDB[mouse_key_to_update]["sex"] = updated_sex
        self.mouseDB[mouse_key_to_update]["toe"] = updated_toe
        self.mouseDB[mouse_key_to_update]["genotype"] = updated_genotype
        self.mouseDB[mouse_key_to_update]["birthDate"] = updated_birth_date
        self.mouseDB[mouse_key_to_update]["age"] = age_days
        self.mouseDB[mouse_key_to_update]["breedDate"] = updated_breed_date if updated_breed_date else None
        self.mouseDB[mouse_key_to_update]["breedDays"] = breed_days
        logging.debug(f"Mouse {selected_id} data updated in mouseDB.")
        
        self.gui.determine_save_status() # Use gui's method to update save button state
        messagebox.showinfo("Success", f"Mouse entry {selected_id} updated.")
        self._close_and_refresh()

    def _close_and_refresh(self):
        logging.debug("_on_edit_window_close called.")
        if self.edit_window:
            self.edit_window.destroy()
            self.edit_window = None # Clear the reference
            self.gui.redraw_canvas()
            self.gui.determine_save_status()
            logging.debug("Edit window closed and GUI refreshed.")

    def _on_edit_window_close(self):
        logging.debug("_on_edit_window_close called.")
        if self.edit_window:
            self.edit_window.destroy()
            self.edit_window = None # Clear the reference