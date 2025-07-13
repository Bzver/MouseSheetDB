import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

import mdb_utils as mut

import logging

class MouseTransfer:
    def __init__(self, master, mouseDB, gui, current_category, mice_status):
        """
        Initializes the MouseTransfer class, which is responsible for transfering mice between cages (virtually).
        Args:
            master: The master Tkinter window.
            mouseDB: The mouse database object.
            gui: The main GUI instance.
            current_category (str): The current category (as in "BACKUP", "CMV+PP2A", etc.) of mice being displayed.
            mice_status: An object containing dictionaries of mice categorized by their status (regular, waiting, death).
        """
        self.master = master
        self.mouseDB = mouseDB
        self.gui = gui
        self.current_category = current_category
        self.mice_status = mice_status

        self.selected_mouse = None
        self.selected_target_cage = None
        self.new_cage_entry = None

    def transfer_to_existing_cage(self):
        """
        Initiates the process to transfer a selected mouse to an existing cage.
        Opens a dialog for the user to select a target cage.
        """
        logging.debug(f"TRANSFER: transfer_to_existing_cage called for mouse ID: {self.gui.selected_mouse.get('ID')}")
        self.selected_mouse = self.gui.selected_mouse # Ensure we are working with the currently selected mouse from GUI
        if self.selected_mouse is not None:
            dialog = tk.Toplevel(self.master)
            dialog.title("Select Target Cage")
            dialog.transient(self.master)
            dialog.grab_set()
            dialog.geometry("+100+300")

            tk.Label(dialog, text="Select a cage:").pack(pady=10)

            current_cage = self.selected_mouse.get("nuCA")
            existing_cages = sorted([c for c in self.mice_status.regular.keys() if c != current_cage])

            if not existing_cages:
                logging.debug("No other existing cages available for transfer.")
                messagebox.showinfo("No Cages", "No other existing cages available for transfer.")
                dialog.destroy()
                return

            selected_target_cage = tk.StringVar(dialog)
            selected_target_cage.set(existing_cages[0])

            cage_dropdown = ttk.Combobox(dialog, textvariable=selected_target_cage, values=existing_cages, state="readonly")
            cage_dropdown.pack(pady=5)

            tk.Button(dialog, text="Transfer", command=lambda: self.confirm_transfer(dialog)).pack(pady=10)
            dialog.wait_window(dialog)
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
            logging.debug(f"Attempting to transfer mouse {self.selected_mouse.get('ID')} to Waiting Room.")
            for cage_key, mice_list in self.mice_status.regular.items():
                if self.selected_mouse in mice_list:
                    mice_list.remove(self.selected_mouse)
                    logging.debug(f"TRANSFER: Removed mouse {self.selected_mouse.get('ID')} from regular cage {cage_key}.")
                    if not mice_list:
                        del self.mice_status.regular[cage_key]
                        logging.debug(f"TRANSFER: Deleted empty regular cage {cage_key}.")
                    break

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
        if self.selected_mouse is not None:
            dialog = tk.Toplevel(self.master)
            dialog.title("Enter New Cage Number")
            dialog.transient(self.master)
            dialog.grab_set()
            dialog.geometry("+100+300")

            tk.Label(dialog, text="Enter the new cage number:").pack(pady=10)

            prefix = ""
            if self.current_category == "NEX + PP2A":
                prefix = "2-A-"
            elif self.current_category == "CMV + PP2A":
                prefix = "8-A-"
            logging.debug(f"New cage prefix: {prefix}")

            prefix_label = tk.Label(dialog, text=prefix)
            prefix_label.pack(side=tk.LEFT, padx=(10, 0))

            self.new_cage_entry = tk.Entry(dialog)
            self.new_cage_entry.pack(side=tk.LEFT, padx=(0, 10))
            self.new_cage_entry.focus_set() # Set focus to the entry widget

            tk.Button(dialog, text="Transfer", command=lambda: self.validate_and_transfer(dialog)).pack(pady=10)
            dialog.wait_window(dialog)

    def transfer_to_death_row(self):
        """
        Transfers the selected mouse to the "Death Row" category.
        Removes the mouse from its current regular or waiting room cage and adds it to death row.
        """
        logging.debug(f"TRANSFER: transfer_to_death_row called for mouse ID: {self.gui.selected_mouse.get('ID')}")
        self.selected_mouse = self.gui.selected_mouse # Ensure we are working with the currently selected mouse from GUI
        if self.selected_mouse is not None:
            logging.debug(f"TRANSFER: Before modification - Regular: {len(self.mice_status.regular)}, Waiting: {len(self.mice_status.waiting)}, Death: {len(self.mice_status.death)}")
            logging.debug(f"Attempting to transfer mouse {self.selected_mouse.get('ID')} to Death Row.")
            for cage_key, mice_list in self.mice_status.regular.items():
                if self.selected_mouse in mice_list:
                    mice_list.remove(self.selected_mouse)
                    logging.debug(f"TRANSFER: Removed mouse {self.selected_mouse.get('ID')} from regular cage {cage_key}.")
                    if not mice_list:
                        del self.mice_status.regular[cage_key]
                        logging.debug(f"TRANSFER: Deleted empty regular cage {cage_key}.")
                    break

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
            self.selected_mouse["category"] = mut.assign_category(original_cage)
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

    def confirm_transfer(self, dialog):
        """
        Confirms and executes the transfer of a selected mouse to an existing cage.
        Args:
            dialog: The Tkinter Toplevel dialog window for cage selection.
        """
        logging.debug(f"TRANSFER: confirm_transfer called for mouse ID: {self.gui.selected_mouse.get('ID')}")
        self.selected_mouse = self.gui.selected_mouse # Ensure we are working with the currently selected mouse from GUI
        taCA = self.selected_target_cage.get()
        if self.selected_mouse is not None:
            logging.debug(f"TRANSFER: Before modification - Regular: {len(self.mice_status.regular)}, Waiting: {len(self.mice_status.waiting)}, Death: {len(self.mice_status.death)}")

            for cage_key, mice_list in self.mice_status.regular.items():
                if self.selected_mouse in mice_list:
                    mice_list.remove(self.selected_mouse)

                    if not mice_list:
                        del self.mice_status.regular[cage_key]
                    break

            self._remove_from_dict("death")
            self._remove_from_dict("waiting")

            self.selected_mouse["nuCA"] = taCA
            self.selected_mouse["category"] = mut.assign_category(taCA)

            if taCA not in self.mice_status.regular:
                self.mice_status.regular[taCA] = []
            self.mice_status.regular[taCA].append(self.selected_mouse)
            logging.debug(f"TRANSFER: After modification - Regular: {len(self.mice_status.regular)}, Waiting: {len(self.mice_status.waiting)}, Death: {len(self.mice_status.death)}")
        self._cleanup_post_transfer(dialog)

    def validate_and_transfer(self, dialog):
        """
        Validates the new cage number input and transfers the selected mouse to the new cage.
        Args:
            dialog: The Tkinter Toplevel dialog window for new cage input.
        """
        logging.debug("validate_and_transfer called.")
        entered_name = self.new_cage_entry.get().strip()
        logging.debug(f"Entered new cage name: {entered_name}")
        
        if not entered_name:
            logging.warning("New cage input is empty.")
            messagebox.showwarning("Invalid Input", "Please enter the cage number.", parent=dialog)
            return
        if not entered_name[0].isdigit() or not entered_name[-1].isdigit():
            logging.warning("New cage input does not start/end with digits.")
            messagebox.showwarning("Invalid Input", "Must start and end with digits.", parent=dialog)
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
            logging.warning("New cage input has no digits sans prefix.")
            messagebox.showwarning("Invalid Input", "Must include at least one digit sans prefix.", parent=dialog)
            return
        if not digits_only.isdigit():
            logging.warning("New cage input contains non-digit characters sans prefix.")
            messagebox.showwarning("Invalid Input", "Only numbers and "-" are allowed sans prefix.", parent=dialog)
            return
        if len(digits_only) > 4:
            logging.warning("New cage input has more than four digits sans prefix.")
            messagebox.showwarning("Invalid Input", "Can only include four digits at most sans prefix.", parent=dialog)
            return
        
        new_cage_no = prefix + entered_suffix
        logging.debug(f"Final new cage number: {new_cage_no}")

        if new_cage_no in self.mice_status.regular: # Check if key exists in the dict
            logging.warning(f"Cage '{new_cage_no}' already exists.")
            messagebox.showwarning("Cage Exists", f"Cage '{new_cage_no}' already exists. Please enter a different number.", parent=dialog)
            self.new_cage_entry.delete(0, tk.END)
            return
        if self.current_category == "BACKUP" and (new_cage_no.startswith("8-A-") or new_cage_no.startswith("2-A-")):
            logging.warning(f"Backup cage '{new_cage_no}' has invalid prefix for backup category.")
            messagebox.showwarning("Format Error", f"Backup cages are not supposed to start with '8-A-' or '2-A-'. Please enter a different number.", parent=dialog)
            self.new_cage_entry.delete(0, tk.END)
            return
        
        self._remove_from_dict("waiting")
        logging.debug(f"Removed mouse from waiting room dict (if present).")

        self.selected_mouse["nuCA"] = new_cage_no
        self.selected_mouse["category"] = self.current_category
        logging.debug(f"Mouse {self.selected_mouse.get('ID')} nuCA updated to {new_cage_no}, category to {self.current_category}.")

        if new_cage_no not in self.mice_status.regular:
            self.mice_status.regular[new_cage_no] = []
            logging.debug(f"Created new regular cage entry for {new_cage_no}.")
        self.mice_status.regular[new_cage_no].append(self.selected_mouse)
        logging.debug(f"Mouse {self.selected_mouse.get('ID')} added to regular cage {new_cage_no}.")
        self._cleanup_post_transfer(dialog)

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
        Destroys the dialog (if provided), redraws the GUI canvas,
        updates the save status, and closes the metadata window.
        Args:
            dialog: The Tkinter Toplevel dialog window to destroy (optional).
        """
        if dialog:
            dialog.destroy()
        logging.debug("TRANSFER: _cleanup_post_transfer called. Calling gui.redraw_canvas().")
        self.gui.redraw_canvas()
        self.gui.determine_save_status()
        self.gui.close_metadata_window()