import os
import shutil
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox

import pandas as pd
import matplotlib.pyplot as plt

import excel_visualizer
import excel_painter

class ExcelAnalyzer:
    def __init__(self, master):
        self.master = master

        # UI Title
        master.title("Excel Analyzer")

        # Button frames
        self.button_frame = tk.Frame(master)
        self.button_frame.pack()

        self.browse_button = tk.Button(self.button_frame, text="Browse", command=self.browse_file)
        self.browse_button.pack(side=tk.LEFT, padx=25)

        self.analyze_button = tk.Button(self.button_frame, text="Analyze", command=self.analyze_data, state=tk.DISABLED)
        self.analyze_button.pack(side=tk.LEFT, padx=5)

        self.monitor_button = tk.Button(self.button_frame, text="Monitor", command=self.monitor_cages, state=tk.DISABLED)
        self.monitor_button.pack(side=tk.LEFT, padx=5)

        self.save_button = tk.Button(self.button_frame, text="Save", command=self.save_changes, state=tk.DISABLED)
        self.save_button.pack(side=tk.RIGHT, padx=25)

        # Sheet navigation controls
        self.sheet_nav_frame = tk.Frame(master)
        self.sheet_nav_frame.pack()

        self.prev_sheet_button = tk.Button(self.sheet_nav_frame, text="◄ Prev Sheet", command=self.prev_sheet, state=tk.DISABLED)
        self.prev_sheet_button.pack(side=tk.LEFT)

        self.sheet_textbox = tk.Entry(self.sheet_nav_frame, width=30, state='readonly')
        self.sheet_textbox.pack(side=tk.LEFT, padx=10)

        self.next_sheet_button = tk.Button(self.sheet_nav_frame, text="Next Sheet ►", command=self.next_sheet, state=tk.DISABLED)
        self.next_sheet_button.pack(side=tk.LEFT)

        self.visualizer = None
        self.file_path = None
        self.backup_file = None
        self.mouseDB = None
        self.sheet_name = None
        self.sheet_index = 0
        self.sheet_names = ['BACKUP', 'NEX + PP2A', 'CMV + PP2A']
        self.canvas_widget = None
        self.last_action = "analyze"
        self.processed_data = None
        self.saveStatus = True

    #########################################################################################################################

    def browse_file(self):
        """Combined file loading and sheet validation"""
        self._reset_state()
        if self.load_excel_file() and self.validate_sheets():
            messagebox.showinfo("Success", "File loaded successfully!")
            self._on_sheet_selection_changed()  # Trigger initial analysis

    def load_excel_file(self):
        """Load and preprocess Excel file, return True if successful"""
        self.file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx;*.xls")])
        if not self.file_path:
            return False
        
        # Create backup before processing
        self.backup_file = self._create_backup(self.file_path)
        self.saveStatus = True

        try:
            # Validate file exists and is Excel
            if not os.path.exists(self.file_path):
                raise Exception("File does not exist")
            if not self.file_path.lower().endswith(('.xlsx', '.xls')):
                raise Exception("Invalid file type - must be .xlsx or .xls")

            # Process all data from MouseDatabase
            temp_excel = pd.ExcelFile(self.file_path)
            if 'MDb' not in temp_excel.sheet_names:
                raise Exception(f"No 'MDb' among sheets in chosen excel file. Check your chosen file.")
            sheet_name = 'MDb'
            temp_excel.close()
            
            # Validate required columns exist in each sheet
            required_columns = ['cage', 'sex', 'toe', 'genotype', 'birthDate', 'age', 'breedDate', 'breedDays']

            df = pd.read_excel(self.file_path, sheet_name)
            missing = [col for col in required_columns if col not in df.columns]
            if missing:
                raise Exception(f"Missing required columns {missing}")
            
            # Preprocess MDb sheet using excel_painter
            self.processed_data = excel_painter.data_preprocess(self.file_path, sheet_name)

            if self.processed_data is None:
                raise Exception("Failed to preprocess Excel data")
                
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error loading/preprocessing file: {e}")
            self._reset_state()
            return False

    def save_changes(self):
        try:
            if hasattr(self, 'visualizer') and self.visualizer and hasattr(self.visualizer, 'waiting_room_mice') and self.visualizer.waiting_room_mice:
                messagebox.showerror("Save Blocked",
                    "Cannot save while mice are in waiting room")
                return False
                
            if self.processed_data and self.file_path:
                # First log any changes
                output_dir = os.path.dirname(self.file_path)
                # Convert processed_data dict to DataFrame
                df = pd.DataFrame.from_dict(self.processed_data, orient='index')
                log_file = excel_painter.mice_changelog(df, output_dir)
                if log_file:
                    messagebox.showinfo("Changes Logged",
                                     f"Mice changes\nLogged to: {log_file}")

                    # Then save the main file
                    excel_painter.write_processed_data_to_excel(self.file_path, self.processed_data)
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save Excel file: {e}")
            return
            
        self.saveStatus = True
        self.save_button["state"] = tk.DISABLED

    #########################################################################################################################

    def _load_database(self):
        """Gets the preprocessed data from processed_data cache."""
        if not self.file_path or not self.processed_data:
            return False

        try:
            self.mouseDB = self.processed_data.copy()
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error getting preprocessed data: {e}")
            self.mouseDB = None
            return False

    def analyze_data(self):
        """Prepares data for the mouse count analyze visualization and passes it to the visualizer."""

        self.last_action = "analyze" # Update last action
        self._load_database()  # Force reload 

        try:
            self.visualizer = excel_visualizer.MouseVisualizer(
                self.master,
                self, # Pass the analyzer instance
                self.mouseDB,
                self.sheet_name,
                self.canvas_widget,
                self._update_processed_database
            )
            self.canvas_widget = self.visualizer.plot_data()
        except Exception as e:
            messagebox.showerror("Error", f"Error plotting analysis data: {e}")

    def monitor_cages(self):
        """Prepares data for the cage monitor visualization and passes it to the visualizer."""

        self.last_action = "monitor" # Update last action

        try:
            self.visualizer = excel_visualizer.MouseVisualizer(
                self.master,
                self, # Pass the analyzer instance
                self.mouseDB,
                self.sheet_name,
                self.canvas_widget,
                self._update_processed_database
            )
            self.canvas_widget = self.visualizer.display_cage_monitor()
        except Exception as e:
            messagebox.showerror("Error", f"Error displaying cage monitor: {e}")

    def _update_processed_database(self, callback):
        """Callback to update the mouseDB from visualizer."""
        self.mouseDB = callback.copy()
        self.processed_data = self.mouseDB.copy()
        self.saveStatus = False
        self.save_button["state"] = tk.NORMAL

    #########################################################################################################################

    def validate_sheets(self):
        """Validate sheets and setup navigation"""
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
            messagebox.showerror("Error", f"Error validating sheets: {e}")
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
        self.sheet_textbox.insert(0, "Current Sheet: None")
        self.sheet_textbox.config(state='readonly')
        self.prev_sheet_button["state"] = tk.DISABLED
        self.next_sheet_button["state"] = tk.DISABLED
        self.analyze_button["state"] = tk.DISABLED
        self.monitor_button["state"] = tk.DISABLED
        self.save_button["state"] = tk.DISABLED
        if self.canvas_widget:
            self.canvas_widget.destroy()
            self.canvas_widget = None
        plt.close('all')

    def _update_sheet_ui(self):
        """Update UI elements for current sheet"""
        self.sheet_textbox.config(state='normal')
        self.sheet_textbox.delete(0, tk.END)
        self.sheet_textbox.insert(0, f"Current Sheet: {self.sheet_name}")
        self.sheet_textbox.config(state='readonly')
        self.prev_sheet_button["state"] = tk.NORMAL
        self.next_sheet_button["state"] = tk.NORMAL
        self.analyze_button["state"] = tk.NORMAL
        self.monitor_button["state"] = tk.NORMAL

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
        self._perform_analysis_action()


    def _perform_analysis_action(self):
        """Perform analysis based on last action type"""
        if self.canvas_widget:
            self.canvas_widget.destroy()
            self.canvas_widget = None

        if self.last_action == "monitor":
            self.monitor_cages()
        else:
            self.analyze_data()

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
        """Save processed data and close application"""
        if not self.saveStatus:
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
                print(f"Error removing backup file: {e}")
                
        self.master.destroy()
        self.master.quit()

# --- Main application setup ---
root = tk.Tk()
excel_analyzer = ExcelAnalyzer(root)
root.protocol("WM_DELETE_WINDOW", excel_analyzer.commit_seppuku)
root.mainloop()