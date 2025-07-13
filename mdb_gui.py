import os
import shutil
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox
from tkcalendar import Calendar

import copy
import pandas as pd
import matplotlib.pyplot as plt

import mdb_vis
import mdb_io
import mdb_utils

import traceback

class ExcelAnalyzer:
    def __init__(self, master):
        self.master = master

        master.title("Excel Analyzer V2.5")

        self.button_frame = tk.Frame(master)
        self.button_frame.pack()
        self.browse_button = tk.Button(self.button_frame, text="Browse", command=self.browse_file)
        self.browse_button.pack(side=tk.LEFT, padx=40)
        self.analyze_button = tk.Button(self.button_frame, text="Analyze", command=self.analyze_data, state=tk.DISABLED)
        self.analyze_button.pack(side=tk.LEFT, padx=5)
        self.monitor_button = tk.Button(self.button_frame, text="Monitor", command=self.monitor_cages, state=tk.DISABLED)
        self.monitor_button.pack(side=tk.LEFT, padx=5)
        self.tree_button = tk.Button(self.button_frame, text="Pedigree", command=self.family_tree, state=tk.DISABLED)
        self.tree_button.pack(side=tk.LEFT, padx=5)
        self.save_button = tk.Button(self.button_frame, text="Save", command=self.save_changes, state=tk.DISABLED)
        self.save_button.pack(side=tk.LEFT, padx=40)

        self.sheet_nav_frame = tk.Frame(master)
        self.sheet_nav_frame.pack()
        self.add_entries_button = tk.Button(self.sheet_nav_frame, text="Add Entries", command=self.new_mouse_entries, state=tk.DISABLED)
        self.add_entries_button.pack(side=tk.LEFT, padx=5) 
        self.prev_sheet_button = tk.Button(self.sheet_nav_frame, text="◄ Prev Sheet", command=self.prev_sheet, state=tk.DISABLED)
        self.prev_sheet_button.pack(side=tk.LEFT)
        self.sheet_textbox = tk.Entry(self.sheet_nav_frame, width=12, state='readonly')
        self.sheet_textbox.pack(side=tk.LEFT, padx=10)
        self.next_sheet_button = tk.Button(self.sheet_nav_frame, text="Next Sheet ►", command=self.next_sheet, state=tk.DISABLED)
        self.next_sheet_button.pack(side=tk.LEFT)
        self.load_changelog_button = tk.Button(self.sheet_nav_frame, text="Load Changes", command=self.load_changelog, state=tk.DISABLED)
        self.load_changelog_button.pack(side=tk.LEFT, padx=5)

        self.visualizer = None
        self.file_path = None
        self.backup_file = None

        self.processed_data = None
        self.mouseDB = None

        self.sheet_name = None
        self.sheet_index = 0
        self.sheet_names = ['BACKUP', 'NEX + PP2A', 'CMV + PP2A']
        
        self.canvas_widget = None
        self.last_action = "analyze"
        self.saveStatus = True
        self.edit_window = None
        self.today = datetime.now().date()

        self.isDebugging = True

    #########################################################################################################################

    def browse_file(self):
        if not self.saveStatus:
            response = messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes. Do you really want to load another excel without saving?"
            )
            if not response:
                return  # Prevent closing if the user chooses not to close
        self._reset_state()
        if self.load_excel_file() and self.validate_sheets():
            messagebox.showinfo("Success", "File loaded successfully!")
            self.load_changelog_button["state"] = tk.NORMAL
            self.add_entries_button["state"] = tk.NORMAL
            self._on_sheet_selection_changed()  # Trigger initial analysis

    def load_excel_file(self):
        self.file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx;*.xls")])
        if not self.file_path:
            return False
        
        # Create backup before processing
        if not self.isDebugging:
            self.backup_file = self._create_backup(self.file_path)
        else:
            print("Debugging! No backup will be generated!")
        self.saveStatus = True
        try:
            self.validate_excel(self.file_path)

            self.processed_data = mdb_io.data_preprocess(self.file_path, 'MDb')
            self.mouseDB = copy.deepcopy(self.processed_data) # Original data serving as change tracker
            if self.processed_data is None:
                raise Exception("Failed to preprocess Excel data")
            
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error loading/preprocessing file: {e}\n{traceback.format_exc()}")
            self._reset_state()
            return False

    def save_changes(self):
        try:
            if hasattr(self, 'visualizer') and self.visualizer and hasattr(self.visualizer, 'waiting_room_mice') and self.visualizer.waiting_room_mice:
                messagebox.showerror("Save Blocked",
                    "Cannot save while mice are in waiting room")
                return False
                
            if self.mouseDB and self.processed_data and self.file_path:
                output_dir = os.path.dirname(self.file_path)
                log_file = mdb_io.mice_changelog(self.processed_data, self.mouseDB, output_dir)
                if log_file:
                    messagebox.showinfo("Changes Logged",
                                     f"Mice changes\nLogged to: {log_file}")

                    # Then save the main file
                    if not self.isDebugging:
                        mdb_io.write_processed_data_to_excel(self.file_path, self.mouseDB)
                    else:
                        file_suffix = os.path.splitext(self.file_path)[1]
                        file_without_suffix = os.path.splitext(self.file_path)[0]
                        debug_filepath = f"{file_without_suffix}_DEBUG{file_suffix}" 
                        mdb_io.write_processed_data_to_excel(debug_filepath, self.mouseDB)                        
                        print(f"Debugging! Will save to {debug_filepath}!")
                        self.saveStatus = True
                        self.save_button["state"] = tk.DISABLED
                else:
                    messagebox.showinfo("Changes Not Logged", "No changes detected!")
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save Excel file: {e}\n{traceback.format_exc()}")
            return

    def load_changelog(self):
        """Loads a changelog file and applies changes to the current data."""
        if not self.processed_data:
            messagebox.showwarning("No Data Loaded", "Please load an Excel file first.")
            return

        changelog_file_path = filedialog.askopenfilename(
            filetypes=[("Excel files", "*.xlsx;*.xls")]
        )
        if not changelog_file_path:
            return

        try:
            # Read sheets for Added and Changed mice from the changelog file
            sheet_names = ['Added', 'Changed']
            changelog_dfs = {}
            
            for sheet_name in sheet_names:
                try:
                    df = pd.read_excel(changelog_file_path, sheet_name=sheet_name)
                    if not df.empty:
                        changelog_dfs[sheet_name] = df
                except:
                    continue  # Skip if sheet doesn't exist

            if not changelog_dfs:
                messagebox.showinfo("No Changes", "The selected changelog file is empty or has no valid sheets.")
                return

            changes_applied_count = 0
            inconsistent_entries = []
            new_mice_added = 0

            # Process each sheet type
            for sheet_type, changelog_df in changelog_dfs.items():
                if sheet_type == 'Added':
                    for index, changelog_row in changelog_df.iterrows():
                        changelog_id = str(changelog_row['ID'])
                        
                        # Check if mouse already exists
                        mouse_exists = any(
                            mouse_data.get('ID') == changelog_id 
                            for mouse_data in self.mouseDB.values()
                        )
                        
                        if not mouse_exists:
                            # Create new mouse entry
                            new_mouse = {
                                'ID': changelog_id,
                                'nuCA': changelog_row.get('nuCA', ''),
                                'sex': changelog_row.get('sex', ''),
                                'toe': changelog_row.get('toe', ''),
                                'genotype': changelog_row.get('genotype', ''),
                                'birthDate': changelog_row.get('birthDate', ''),
                                'breedDate': changelog_row.get('breedDate', ''),
                                'sheet': changelog_row.get('sheet', 'BACKUP'),
                                'cage': 'Waiting Room',
                                'age': changelog_row.get('age', ''),
                                'breedDays': changelog_row.get('breedDays', ''),
                                'parentF': changelog_row.get('parentF', ''),
                                'parentM': changelog_row.get('parentM', ''),
                            }
                            
                            # Add to mouseDB with a new index
                            new_index = max(self.mouseDB.keys()) + 1 if self.mouseDB else 0
                            self.mouseDB[new_index] = new_mouse
                            new_mice_added += 1
                            changes_applied_count += 1
                        else:
                            inconsistent_entries.append(f"ID: {changelog_id}, already exists in database (not added)")
                            
                else:  # Changed sheet
                    for index, changelog_row in changelog_df.iterrows():
                        changelog_id = str(changelog_row['ID'])
                        
                        mouse_found = False
                        for mouse_index, mouse_data in self.mouseDB.items():
                            if mouse_data.get('ID') == changelog_id:
                                mouse_found = True
                                
                                fields_to_update = ['nuCA', 'sex', 'toe', 'genotype', 'birthDate', 'breedDate', 'sheet', 'parentF', 'parentM']
                                for field in fields_to_update:
                                    if field in changelog_row:
                                        self.mouseDB[mouse_index][field] = changelog_row[field]
                                        # Update cage if nuCA changed
                                        if field == 'nuCA':
                                            self.mouseDB[mouse_index]['cage'] = changelog_row[field]
                                changes_applied_count += 1
                                
                                break  # Found the mouse, move to next entry
                        if not mouse_found:
                            inconsistent_entries.append(f"ID: {changelog_id}, not found in current data")

            # Show results to user
            result_message = [
                f"Successfully applied {changes_applied_count} changes:",
                f"- {new_mice_added} new mice added",
                f"- {changes_applied_count - new_mice_added} existing mice updated"
            ]
            
            if inconsistent_entries:
                result_message.append(
                    "\nThe following issues were encountered:\n" + 
                    "\n".join(inconsistent_entries)
                )
                messagebox.showwarning(
                    "Changelog Applied with Issues", 
                    "\n".join(result_message)
                )
            else:
                messagebox.showinfo(
                    "Changelog Applied", 
                    "\n".join(result_message)
                )

            # Update state to reflect changes
            self.saveStatus = False
            self.save_button["state"] = tk.NORMAL
            self._perform_analysis_action()  # Redraw visualization to show changes

        except Exception as e:
            messagebox.showerror(
                "Error", 
                f"Error loading or applying changelog: {e}\n{traceback.format_exc()}"
            )

    #########################################################################################################################

    def analyze_data(self):
        """Prepares data for the mouse count analyze visualization and passes it to the visualizer."""

        self.last_action = "analyze" # Update last action

        try:
            self.visualizer = mdb_vis.MouseVisualizer(
                self.master,
                self,
                self.mouseDB,
                self.sheet_name,
                self.canvas_widget
            )
            self.canvas_widget = self.visualizer.plot_data()
        except Exception as e:
            messagebox.showerror("Error", f"Error plotting analysis data: {e}\n{traceback.format_exc()}")

    def monitor_cages(self):
        """Prepares data for the cage monitor visualization and passes it to the visualizer."""

        self.last_action = "monitor"

        try:
            self.visualizer = mdb_vis.MouseVisualizer(
                self.master,
                self,
                self.mouseDB,
                self.sheet_name,
                self.canvas_widget
            )
            self.canvas_widget = self.visualizer.display_cage_monitor()
        except Exception as e:
            messagebox.showerror("Error", f"Error displaying cage monitor: {e}\n{traceback.format_exc()}")

    def family_tree(self):
        """Prepares data for the family tree visualization window and passes it to the visualizer."""
        try:
            # Create a new instance of MouseVisualizer for the family tree window
            family_tree_window = mdb_vis.MouseVisualizer(
                self.master,
                self,
                self.mouseDB,
                self.sheet_name,
                None, # No canvas widget for this separate window
            )
            family_tree_window.display_family_tree_window(self.mouseDB)
        except Exception as e:
            messagebox.showerror("Error", f"Error displaying pedigree: {e}\n{traceback.format_exc()}")

    def _update_database(self):
        """Callback to pass the mouseDB update notice from visualizer to analyzer."""
        self.saveStatus = False
        self.save_button["state"] = tk.NORMAL

    #########################################################################################################################

    def new_mouse_entries(self):
        """Displays the window for adding a new mouse entry."""
        self.new_window = tk.Toplevel(self.master)
        self.new_window.title("Add Mouse Entries")
        self.new_entry_frame = tk.Frame(self.new_window)
        self.new_entry_frame.pack(pady=10)

        # Clear previous widgets in new_entry_frame
        for widget in self.new_entry_frame.winfo_children():
            widget.destroy()

        # Form elements for NEW entry
        tk.Label(self.new_entry_frame, text="Sex:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.new_sex_var = tk.StringVar(self.new_entry_frame)
        self.new_sex_var.set("♂ ") # default value
        male_radio = tk.Radiobutton(self.new_entry_frame, text="♂", variable=self.new_sex_var, value="♂")
        female_radio = tk.Radiobutton(self.new_entry_frame, text="♀", variable=self.new_sex_var, value="♀")
        male_radio.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        female_radio.grid(row=1, column=2, padx=5, pady=5, sticky="w")

        tk.Label(self.new_entry_frame, text="Toe:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.new_toe_entry = tk.Entry(self.new_entry_frame)
        self.new_toe_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        tk.Label(self.new_entry_frame, text="Genotype:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.new_genotype_entry = tk.Entry(self.new_entry_frame)
        self.new_genotype_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        tk.Label(self.new_entry_frame, text="Birth Date:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.new_birthdate_cal = Calendar(self.new_entry_frame, selectmode='day', date_pattern='yyyy-mm-dd')
        self.new_birthdate_cal.grid(row=4, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        save_new_button = tk.Button(self.new_entry_frame, text="Save New Entry", command=self._save_new_entry)
        save_new_button.grid(row=5, column=0, columnspan=3, pady=10)

    def edit_mouse_entries(self):
        """Displays the window for editing an existing mouse entry."""
        self.edit_mouse_var = self.visualizer.selected_mouse
        self.edit_window = tk.Toplevel(self.master)
        self.edit_window.title("Edit Mouse Entries")
        self.edit_entry_frame = tk.Frame(self.edit_window)
        self.edit_entry_frame.pack(pady=10)
        self.edit_window.protocol("WM_DELETE_WINDOW", self._on_edit_window_close)
        # Inform the visualizer that editing has started
        if self.visualizer and self.visualizer.selected_mouse:
            self.visualizer.set_editing_state(True, self.visualizer.selected_mouse.get('ID'))

        # Clear previous widgets in edit_entry_frame
        for widget in self.edit_entry_frame.winfo_children():
            widget.destroy()

        # Form elements for EDIT entry (initially empty)
        tk.Label(self.edit_entry_frame, text = "ID:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.disp_id = tk.Entry(self.edit_entry_frame)
        self.disp_id.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.disp_id.insert(0, self.edit_mouse_var.get('ID'))
        self.disp_id.config(state='readonly')

        tk.Label(self.edit_entry_frame, text="Sex:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.edit_sex_var = tk.StringVar(self.edit_entry_frame)
        male_radio_edit = tk.Radiobutton(self.edit_entry_frame, text="♂", variable=self.edit_sex_var, value="♂")
        female_radio_edit = tk.Radiobutton(self.edit_entry_frame, text="♀", variable=self.edit_sex_var, value="♀")
        male_radio_edit.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        female_radio_edit.grid(row=2, column=2, padx=5, pady=5, sticky="w")

        tk.Label(self.edit_entry_frame, text="Toe:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.edit_toe_entry = tk.Entry(self.edit_entry_frame)
        self.edit_toe_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        tk.Label(self.edit_entry_frame, text="Genotype:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.edit_genotype_entry = tk.Entry(self.edit_entry_frame)
        self.edit_genotype_entry.grid(row=4, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        tk.Label(self.edit_entry_frame, text="Birth Date:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.edit_birthdate_cal = Calendar(self.edit_entry_frame, selectmode='day', date_pattern='yyyy-mm-dd')
        self.edit_birthdate_cal.grid(row=5, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        tk.Label(self.edit_entry_frame, text="Breed Date:").grid(row=6, column=0, padx=5, pady=5, sticky="w")
        self.edit_breeddate_cal = Calendar(self.edit_entry_frame, selectmode='day', date_pattern='yyyy-mm-dd')
        self.edit_breeddate_cal.grid(row=6, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        save_edit_button = tk.Button(self.edit_entry_frame, text="Save Changes", command=self._save_edited_entry)
        save_edit_button.grid(row=7, column=0, columnspan=3, pady=10)

        self._load_mouse_data_for_edit()

    def _load_mouse_data_for_edit(self):
        """Loads data of the selected mouse into the edit form."""
        selected_id = self.edit_mouse_var.get('ID')
        if not selected_id:
            return

        selected_mouse_data = None
        for mouse_data in self.mouseDB.values():
            if mouse_data.get('ID') == selected_id:
                selected_mouse_data = mouse_data
                break

        if selected_mouse_data:
            self.edit_sex_var.set(selected_mouse_data.get('sex', '♂'))
            self.edit_toe_entry.insert(0, selected_mouse_data.get('toe', '').replace('toe', ''))
            self.edit_genotype_entry.insert(0, selected_mouse_data.get('genotype', ''))
            
            # Set dates in calendar widgets
            birth_date_str = selected_mouse_data.get('birthDate', '')
            if birth_date_str and birth_date_str != '-':
                try:
                    if isinstance(birth_date_str, str):
                        birth_date_obj = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
                    else:
                        birth_date_obj = birth_date_str.date()
                    self.edit_birthdate_cal.selection_set(birth_date_obj)
                except ValueError:
                    pass

            breed_date_str = selected_mouse_data.get('breedDate', '')
            if breed_date_str and breed_date_str != '-':
                try:
                    if isinstance(breed_date_str, str):
                        breed_date_obj = datetime.strptime(breed_date_str, "%Y-%m-%d").date()
                    else:
                        breed_date_obj = breed_date_str.date()
                    self.edit_breeddate_cal.selection_set(breed_date_obj)
                except ValueError:
                    pass

    def _save_new_entry(self):
        """Saves a new mouse entry."""
        cage = 'Waiting Room'
        sex = self.new_sex_var.get()
        toe_input = self.new_toe_entry.get()
        genotype = self.new_genotype_entry.get()
        birth_date_str = self.new_birthdate_cal.get_date() # Get date from calendar

        # Basic validation
        if not all([sex, toe_input, genotype, birth_date_str]):
            messagebox.showerror("Input Error", "All fields must be filled for a new entry.")
            return

        # Format toe
        toe = f"toe{toe_input}" if not toe_input.startswith("toe") else toe_input

        age_days = mdb_utils.get_age_days(birth_date_str, self.today)

        # Generate a unique ID for the new mouse
        genoID = mdb_utils.process_genotypeID(genotype)
        dobID = mdb_utils.process_birthDateID(birth_date_str)
        toeID = mdb_utils.process_toeID(toe)
        sexID = mdb_utils.process_sexID(sex)
        cageID = mdb_utils.process_cageID(cage)
        new_id = f"{genoID}{dobID}{toeID}{sexID}{cageID}"

        new_mouse_data = {
            'ID': new_id,
            'cage': cage,
            'sex': sex,
            'toe': toe,
            'genotype': genotype,
            'birthDate': birth_date_str,
            'age': age_days if age_days != "-" else "-",
            'breedDate': '-',
            'breedDays': '-',
            'nuCA': cage,
            'sheet': cage
        }

        # Find a unique key for the new entry in mouseDB
        new_key = len(self.mouseDB) if self.mouseDB else 0
        while new_key in self.mouseDB:
            new_key += 1
        self.mouseDB[new_key] = new_mouse_data
        
        self.saveStatus = False
        self.save_button["state"] = tk.NORMAL
        messagebox.showinfo("Success", f"New mouse entry added with ID: {new_id}")
        self.new_window.destroy() # Close the edit window
        self._perform_analysis_action() # Redraw visualization to show changes

    def _save_edited_entry(self):
        """Saves changes to an existing mouse entry."""
        selected_id = self.edit_mouse_var.get('ID')
        if not selected_id:
            messagebox.showerror("Selection Error", "Please select a mouse to edit.")
            return

        # Find the mouse in mouseDB
        mouse_key_to_update = None
        for key, mouse_data in self.mouseDB.items():
            if mouse_data.get('ID') == selected_id:
                mouse_key_to_update = key
                break

        if mouse_key_to_update is None:
            messagebox.showerror("Error", "Selected mouse not found in data.")
            return

        # Get updated values from form
        updated_sex = self.edit_sex_var.get()
        updated_toe_input = self.edit_toe_entry.get()
        updated_genotype = self.edit_genotype_entry.get()
        updated_birth_date_str = self.edit_birthdate_cal.get_date() # Get date from calendar
        updated_breed_date_str = self.edit_breeddate_cal.get_date() # Get date from calendar

        # Basic validation
        if not all([updated_sex, updated_toe_input, updated_genotype, updated_birth_date_str]):
            messagebox.showerror("Input Error", "All fields (except Breed Date) must be filled for an edited entry.")
            return

        # Format toe
        updated_toe = f"toe{updated_toe_input}" if not updated_toe_input.startswith("toe") else updated_toe_input

        updated_birth_date = datetime.strptime(updated_birth_date_str, "%Y-%m-%d")
        updated_breed_date = datetime.strptime(updated_breed_date_str, "%Y-%m-%d")
        
        age_days = mdb_utils.get_age_days(updated_birth_date, self.today)
        breed_days = mdb_utils.get_days_since_last_breed(updated_breed_date, self.today) if updated_breed_date else "-"

        # Update the mouse data
        self.mouseDB[mouse_key_to_update]['sex'] = updated_sex
        self.mouseDB[mouse_key_to_update]['toe'] = updated_toe
        self.mouseDB[mouse_key_to_update]['genotype'] = updated_genotype
        self.mouseDB[mouse_key_to_update]['birthDate'] = updated_birth_date
        self.mouseDB[mouse_key_to_update]['age'] = age_days if age_days != "-" else "-"
        self.mouseDB[mouse_key_to_update]['breedDate'] = updated_breed_date if updated_breed_date else "-"
        self.mouseDB[mouse_key_to_update]['breedDays'] = breed_days if breed_days != "-" else "-"
        
        self.saveStatus = False
        self.save_button["state"] = tk.NORMAL
        messagebox.showinfo("Success", f"Mouse entry {selected_id} updated.")
        self.edit_window.destroy() # Close the edit window
        self._perform_analysis_action() # Redraw visualization to show changes

    #########################################################################################################################

    def validate_excel(self):
        # Validate is Excel
        if not self.file_path.lower().endswith(('.xlsx', '.xls')):
            raise Exception("Invalid file type - must be .xlsx or .xls")
        # Process all data from MouseDatabase
        temp_excel = pd.ExcelFile(self.file_path)
        if 'MDb' not in temp_excel.sheet_names:
            raise Exception(f"No 'MDb' among sheets in chosen excel file. Check your chosen file.")
        temp_excel.close()
            
        # Validate required columns exist in each sheet
        required_columns = ['ID', 'cage', 'sex', 'toe', 'genotype', 'birthDate', 'breedDate']

        df = pd.read_excel(self.file_path, 'MDb')
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise Exception(f"Missing required columns {missing}")

    def validate_sheets(self):
        """Detup navigation"""
        if not self.processed_data:
            return False
        try:
            self.sheet_names = ['BACKUP', 'NEX + PP2A', 'CMV + PP2A']
            if self.sheet_names:
                self.sheet_index = 0
                self.sheet_name = self.sheet_names[0]
                self._update_sheet_ui()
                return True
            else:
                messagebox.showerror("Error", "No sheets found in the Excel file.")
                self._reset_state()
                return False
            
        except Exception as e:
            messagebox.showerror("Error", f"Error validating sheets: {e}\n{traceback.format_exc()}")
            self._reset_state()
            return False

    def _reset_state(self):
        self.file_path = None
        self.df_current_sheet = None
        self.sheet_names = ['BACKUP', 'NEX + PP2A', 'CMV + PP2A']
        self.sheet_index = 0
        self.sheet_name = None
        self.sheet_textbox.config(state='normal')
        self.sheet_textbox.delete(0, tk.END)
        self.sheet_textbox.config(state='readonly')
        self.prev_sheet_button["state"] = tk.DISABLED
        self.next_sheet_button["state"] = tk.DISABLED
        self.analyze_button["state"] = tk.DISABLED
        self.monitor_button["state"] = tk.DISABLED
        self.tree_button["state"] = tk.DISABLED
        self.save_button["state"] = tk.DISABLED
        self.add_entries_button["state"] = tk.DISABLED
        if self.canvas_widget:
            self.canvas_widget.destroy()
            self.canvas_widget = None
        plt.close('all')

    def _update_sheet_ui(self):
        """Update UI elements for current sheet"""
        filename = os.path.basename(self.file_path)
        self.sheet_textbox.config(state='normal')
        self.sheet_textbox.delete(0, tk.END)
        self.sheet_textbox.insert(0, self.sheet_name)
        self.sheet_textbox.config(state='readonly')
        self.prev_sheet_button["state"] = tk.NORMAL
        self.next_sheet_button["state"] = tk.NORMAL
        self.analyze_button["state"] = tk.NORMAL
        self.monitor_button["state"] = tk.NORMAL
        self.tree_button["state"] = tk.NORMAL

    def prev_sheet(self):
        """Navigate to previous sheet"""
        plt.close('all')
        self.sheet_index = (self.sheet_index - 1) % len(self.sheet_names)
        self.sheet_name = self.sheet_names[self.sheet_index]
        self._update_sheet_ui()
        self._perform_analysis_action()

    def next_sheet(self):
        """Navigate to next sheet"""
        plt.close('all')
        self.sheet_index = (self.sheet_index + 1) % len(self.sheet_names)
        self.sheet_name = self.sheet_names[self.sheet_index]
        self._update_sheet_ui()
        self._perform_analysis_action()

    def _on_sheet_selection_changed(self, event=None):
        """Handle sheet selection changes (UI updates only)"""
        if not self.sheet_name:
            self.analyze_button["state"] = tk.DISABLED
            self.monitor_button["state"] = tk.DISABLED
            return

        self.analyze_button["state"] = tk.NORMAL
        self.monitor_button["state"] = tk.NORMAL
        if self.canvas_widget:
            self.canvas_widget.destroy()
            self.canvas_widget = None

        # Trigger analysis based on last action
        self._perform_analysis_action()

    def redraw_canvas(self):
        """Public method to trigger canvas redraw based on current state."""
        self._perform_analyswis_action()

    def _perform_analysis_action(self):
        if self.canvas_widget:
            self.canvas_widget.destroy()
            self.canvas_widget = None

        if self.last_action == "monitor":
            self.monitor_cages()
        else:
            self.analyze_data()

    def _on_edit_window_close(self):
        if self.edit_window:
            self.edit_window.destroy()
            self.edit_window = None # Clear the reference
        self._perform_analysis_action()
        
    #########################################################################################################################

    def _create_backup(self, excel_file):
        """Creates backup of original Excel file"""
        current_time = datetime.now().time()
        formatted_time = current_time.strftime("%H-%M-%S")
        excel_filename = excel_file.removesuffix(".xlsx")
        backup_file = f'{excel_filename}_{formatted_time}.xlsx'

        try:
            shutil.copy2(excel_file, backup_file)
            return backup_file
        except FileNotFoundError:
            print(f"Error: Original file '{excel_file}' not found. Cannot create backup.")
            return None

    def commit_seppuku(self):
        """Save reminder and close application"""
        if not self.saveStatus and not self.isDebugging:
            response = messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes. Do you really want to close without saving?"
            )
            if not response:
                return  # Prevent closing if the user chooses not to close
                
        # Clean up resources
        if self.canvas_widget:
            self.canvas_widget.destroy()
        plt.close('all')
            
        # Remove backup if no changes were made
        if not self.saveStatus and self.backup_file and os.path.exists(self.backup_file):
            try:
                os.remove(self.backup_file)
            except Exception as e:
                print(f"Error removing backup file: {e}\n{traceback.format_exc()}")
                
        self.master.destroy()
        self.master.quit()

# --- Main application setup ---
root = tk.Tk()
excel_analyzer = ExcelAnalyzer(root)
root.protocol("WM_DELETE_WINDOW", excel_analyzer.commit_seppuku)
root.mainloop()