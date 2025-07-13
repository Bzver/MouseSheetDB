import os
import shutil
import copy

from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import mdb_io
from mdb_edit import MouseEditor
from mdb_transfer import MouseTransfer
import mdb_vis
import mdb_pedig

import traceback

class MouseDatabaseGUI:
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
        self.add_entries_button = tk.Button(self.sheet_nav_frame, text="Add Entries", command=lambda:self.edit_mouse_entries("add"), state=tk.DISABLED)
        self.add_entries_button.pack(side=tk.LEFT, padx=5) 
        self.prev_sheet_button = tk.Button(self.sheet_nav_frame, text="◄ Prev Sheet", command=self._prev_sheet, state=tk.DISABLED)
        self.prev_sheet_button.pack(side=tk.LEFT)
        self.sheet_textbox = tk.Entry(self.sheet_nav_frame, width=12, state='readonly')
        self.sheet_textbox.pack(side=tk.LEFT, padx=10)
        self.next_sheet_button = tk.Button(self.sheet_nav_frame, text="Next Sheet ►", command=self._next_sheet, state=tk.DISABLED)
        self.next_sheet_button.pack(side=tk.LEFT)
        self.load_changelog_button = tk.Button(self.sheet_nav_frame, text="Load Changes", command=self.load_changelog, state=tk.DISABLED)
        self.load_changelog_button.pack(side=tk.LEFT, padx=5)

        self.file_path = None
        self.backup_file = None

        self.processed_data = None
        self.mouseDB = None

        self.sheet_name = None
        self.sheet_index = 0
        self.sheet_names = ['BACKUP', 'NEX + PP2A', 'CMV + PP2A']

        self.visualizer = None
        self.editor = MouseEditor
        self.transfer = MouseTransfer
        
        self.selected_mouse = None
        self.leaving_timer = None
        self.current_metadata_window = None

        self.edited_mouse_artist = None
        self.last_hovered_mouse = None

        self.canvas_widget = None
        self.last_action = "analyze"
        self.is_saved = True

        self.is_debug = True

    #########################################################################################################################

    def browse_file(self):
        if not self.is_saved:
            response = messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes. Do you really want to load another excel without saving?"
            )
            if not response:
                return  # Prevent closing if the user chooses not to close
        self._reset_state()
        if self.load_excel_file():
            messagebox.showinfo("Success", "File loaded successfully!")
            self.load_changelog_button["state"] = tk.NORMAL
            self.add_entries_button["state"] = tk.NORMAL
            self._on_sheet_selection_changed()  # Trigger initial analysis

    def load_excel_file(self):
        self.file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx;*.xls")])
        if not self.file_path:
            return False
        # Create backup before processing
        if not self.is_debug:
            self.backup_file = self._create_backup(self.file_path)
        else:
            print("Debugging! No backup will be generated!")
        self.is_saved = True
        try:
            self.validate_excel(self.file_path)
            self.processed_data = mdb_io.data_preprocess(self.file_path, 'MDb')
            self.mouseDB = copy.deepcopy(self.processed_data) # Original data serving as change tracker
            self.sheet_name = self.sheet_names[0]
            self._update_sheet_ui()
            if self.processed_data is None:
                raise Exception("Failed to preprocess Excel data") 
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error loading/preprocessing file: {e}\n{traceback.format_exc()}")
            self._reset_state()
            return False

    def save_changes(self):
        try:
            if self.visualizer and hasattr(self.visualizer, 'waiting_room_mice') and self.visualizer.waiting_room_mice:
                messagebox.showerror("Save Blocked","Cannot save while mice are in waiting room")
                return False
            if self.mouseDB and self.processed_data and self.file_path:
                output_dir = os.path.dirname(self.file_path)
                log_file = mdb_io.mice_changelog(self.processed_data, self.mouseDB, output_dir)
                if self.is_debug: # Save in debug no matter what
                    file_suffix = os.path.splitext(self.file_path)[1]
                    file_without_suffix = os.path.splitext(self.file_path)[0]
                    debug_filepath = f"{file_without_suffix}_DEBUG{file_suffix}" 
                    mdb_io.write_processed_data_to_excel(debug_filepath, self.mouseDB)                        
                    print(f"Debugging! Will save to {debug_filepath}!")
                    self.is_saved = True
                    self.save_button["state"] = tk.DISABLED
                elif log_file:
                    messagebox.showinfo("Changes Logged", f"Mice changes\nLogged to: {log_file}")
                    mdb_io.write_processed_data_to_excel(self.file_path, self.mouseDB)
                else:
                    messagebox.showinfo("Changes Not Logged", "No changes detected, save operation cancelled!")
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
            result_message, exception_entries = mdb_io.changelog_loader(changelog_file_path, self.mouseDB)
            if exception_entries:
                result_message.append("\nThe following issues were encountered:\n" +"\n".join(exception_entries))
                messagebox.showwarning("Changelog Applied with Issues","\n".join(result_message))
            else:
                messagebox.showinfo("Changelog Applied","\n".join(result_message))
            self.is_saved = False
            self.save_button["state"] = tk.NORMAL
            self._perform_analysis_action()
        except Exception as e:
            messagebox.showerror("Error",f"Error loading or applying changelog: {e}\n{traceback.format_exc()}")

    #########################################################################################################################

    def analyze_data(self):
        """Prepares data for the mouse count analyze visualization and passes it to the visualizer."""
        self.last_action = "analyze" # Update last action
        try:
            self.visualizer = mdb_vis.MouseVisualizer(self.master, None, self.mouseDB, self.sheet_name, self.canvas_widget)
            self.canvas_widget = self.visualizer.display_genotype_bar_plot()
        except Exception as e:
            messagebox.showerror("Error", f"Error plotting analysis data: {e}\n{traceback.format_exc()}")

    def monitor_cages(self):
        """Prepares data for the cage monitor visualization and passes it to the visualizer."""
        self.last_action = "monitor"
        try:
            self.visualizer = mdb_vis.MouseVisualizer(self.master, self, self.mouseDB, self.sheet_name, self.canvas_widget)
            self.canvas_widget = self.visualizer.display_cage_monitor()
        except Exception as e:
            messagebox.showerror("Error", f"Error displaying cage monitor: {e}\n{traceback.format_exc()}")

    def family_tree(self):
        """Prepares data for the family tree visualization window and passes it to pedigree."""
        try:
            # Create a new instance of MouseVisualizer for the family tree window
            family_tree_window = mdb_pedig.MousePedigree(self.master, self.mouseDB)
            family_tree_window.display_family_tree_window(self.mouseDB)
        except Exception as e:
            messagebox.showerror("Error", f"Error displaying pedigree: {e}\n{traceback.format_exc()}")

    def mouse_edit(self):
        """Prepares data for the mouse editing and passes it to editor."""
        try:
            self.editor = self.editor.MouseEditor(self.master, self.mouseDB, self.selected_mouse) # Create instance
        except Exception as e:
            messagebox.showerror("Error", f"Error editing mice: {e}\n{traceback.format_exc()}")

    #########################################################################################################################

    def on_hover(self, event):
        if event.inaxes and event.xdata is not None and event.ydata is not None:
            for artist, mouse in self.visualizer.mouse_artists:
                if artist.contains(event)[0]:
                    if self.leaving_timer:  # Cancel pending close timer if exists
                        self.master.after_cancel(self.leaving_timer)
                        self.leaving_timer = None

                    # Skip if same mouse is already highlighted
                    if (self.last_hovered_mouse and 
                        self.last_hovered_mouse.get('ID') == mouse.get('ID')):
                        return

                    if self.current_metadata_window: # Destroy current window when hover on new mouse
                        self.current_metadata_window.destroy()

                    self._show_metadata_window(mouse)
                    self.last_hovered_mouse = mouse
                    return

            self.schedule_close_metadata_window()

    def on_click(self, event):
        if event.button == 1 and event.inaxes:
            for artist, mouse in self.visualizer.mouse_artists:
                if artist.contains(event)[0]:
                    self.selected_mouse = mouse
                    self.show_context_menu()
                    return
                
    #########################################################################################################################         

    def _show_metadata_window(self, mouse):
        if self.current_metadata_window:
            self.current_metadata_window.destroy()

        sex = mouse.get('sex', 'N/A')
        toe = mouse.get('toe', 'N/A')
        age = mouse.get('age', 'N/A')
        genotype = mouse.get('genotype', 'N/A')
        mouseID = mouse.get('ID', 'N/A')

        if len(genotype) < 15:
            genotype = genotype.center(25,' ') # Padded the short genotype for a centered look
        
        metadata_window = tk.Toplevel(self.master)
        metadata_window.title("Mouse Metadata")
        metadata_window.geometry("+100+100")

        style = ttk.Style()
        style.configure("Metadata.TLabel", font=("Arial", 9), padding=5)
        separ_geno = '------GENOTYPE------'
        separ_ID = '------------I-D------------'
        message = (f"Sex: {sex}   Toe: {toe}\nAge: {age}d ({int(age) // 7}w{int(age) % 7}d)\n{separ_geno}\n{genotype}\n{separ_ID}\n{mouseID}")
        label = ttk.Label(metadata_window, text=message, style="Metadata.TLabel")
        label.pack(padx=10, pady=10)

        self.current_metadata_window = metadata_window

    def schedule_close_metadata_window(self):
        if self.current_metadata_window and not self.leaving_timer:
            self.leaving_timer = self.master.after(100, self.close_metadata_window)

    def close_metadata_window(self):
        if self.current_metadata_window:
            self.current_metadata_window.destroy()
            self.current_metadata_window = None
        self.last_hovered_mouse = None
        self.leaving_timer = None

    #########################################################################################################################

    def show_context_menu(self):
        menu = tk.Menu(self.master, tearoff=0)

        is_in_waiting_room = self.selected_mouse.get('nuCA') == 'Waiting Room'
        is_on_death_row = self.selected_mouse.get('nuCA') == 'Death Row'

        menu.add_command(label="Edit mouse entry", command=self.editor.edit_mouse_entries)
        menu.add_command(label="Add to pedigree graph", command=mdb_pedig.add_to_family_tree)

        if is_on_death_row:
            menu.add_command(label="Release from Death Row", command=self.transfer.transfer_from_death_row)
        else:
            menu.add_command(label="Transfer to current cages", command=self.transfer.transfer_to_existing_cage)
            menu.add_command(label="Transfer to Death Row", command=self.transfer.transfer_to_death_row)
            if is_in_waiting_room:
                menu.add_command(label="Transfer to a new cage", command=self.transfer.transfer_to_new_cage)
            else: # in reguular cages
                menu.add_command(label="Transfer to waiting room", command=self.transfer.transfer_to_waiting_room)

        try: # Display the menu at the mouse click position using Tkinter's pointer coordinates
            menu.tk_popup(self.master.winfo_pointerx(), self.master.winfo_pointery())
        finally:
            menu.grab_release()

    #########################################################################################################################

    def determine_save_status(self):
        if mdb_io.find_changes_for_changelog(self.processed_data, self.mouseDB, check_only=True):
            self.is_saved = False
            self.save_button["state"] = tk.NORMAL
        else:
            self.is_saved = True
            self.save_button["state"] = tk.DISABLED

    def redraw_canvas(self):
        """Public method to trigger canvas redraw based on current state."""
        self._perform_analyswis_action()
        
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
        self.visualizer.cleanup()

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

    def _prev_sheet(self):
        """Navigate to previous sheet"""
        self.visualizer.cleanup()
        self.sheet_index = (self.sheet_index - 1) % len(self.sheet_names)
        self.sheet_name = self.sheet_names[self.sheet_index]
        self._update_sheet_ui()
        self._perform_analysis_action()

    def _next_sheet(self):
        """Navigate to next sheet"""
        self.visualizer.cleanup()
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

    def _perform_analysis_action(self):
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
        """Save reminder and close application"""
        if not self.is_saved and not self.is_debug:
            response = messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes. Do you really want to close without saving?"
            )
            if not response:
                return  # Prevent closing if the user chooses not to close
                
        # Clean up resources
        if self.canvas_widget:
            self.canvas_widget.destroy()
        self.visualizer.cleanup()
            
        # Remove backup if no changes were made
        if not self.is_saved and self.backup_file and os.path.exists(self.backup_file):
            try:
                os.remove(self.backup_file)
            except Exception as e:
                print(f"Error removing backup file: {e}\n{traceback.format_exc()}")
                
        self.master.destroy()
        self.master.quit()

# --- Main application setup ---
root = tk.Tk()
mdb_main = MouseDatabaseGUI(root)
root.protocol("WM_DELETE_WINDOW", mdb_main.commit_seppuku)
root.mainloop()