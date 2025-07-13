import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

class MouseTransfer:
    def __init__(self, master, mouseDB, sheet_name, mice_displayed):
        self.master = master
        self.mouseDB = mouseDB
        self.sheet_name = sheet_name
        self.mice_displayed = mice_displayed

        self.selected_mouse = None
        self.selected_target_cage = None
        self.new_cage_entry = None

    def transfer_to_existing_cage(self):
        if self.selected_mouse is not None:
            dialog = tk.Toplevel(self.master)
            dialog.title("Select Target Cage")
            dialog.transient(self.master)
            dialog.grab_set()
            dialog.geometry("+100+300")

            tk.Label(dialog, text="Select a cage:").pack(pady=10)

            current_cage = self.selected_mouse.get('nuCA')
            existing_cages = sorted([c for c in self.mice_displayed.regular.keys() if c != current_cage])

            if not existing_cages:
                messagebox.showinfo("No Cages", "No other existing cages available for transfer.")
                dialog.destroy()
                return

            selected_target_cage = tk.StringVar(dialog)
            selected_target_cage.set(existing_cages[0])

            cage_dropdown = ttk.Combobox(dialog, textvariable=selected_target_cage, values=existing_cages, state="readonly")
            cage_dropdown.pack(pady=5)

            tk.Button(dialog, text="Transfer", command=self.confirm_transfer).pack(pady=10)
            dialog.wait_window(dialog)
        self.cleanup_post_transfer()

    def transfer_to_waiting_room(self):
        if self.elected_mouse is not None:
            for cage_key, mice_list in self.mice_displayed.regular.items():
                if self.selected_mouse in mice_list:
                    mice_list.remove(self.selected_mouse)
                    if not mice_list:
                        del self.mice_displayed.regular[cage_key]
                    break

            if self.selected_mouse['ID'] in self.mice_displayed.death:
                del self.mice_displayed.death[self.selected_mouse['ID']]

            self.selected_mouse['nuCA'] = 'Waiting Room'
            self.selected_mouse['sheet'] = 'Waiting Room'
            self.mice_displayed.waiting[self.selected_mouse['ID']] = self.selected_mouse
        self.cleanup_post_transfer()

    def transfer_to_new_cage(self):
        if self.selected_mouse is not None:
            dialog = tk.Toplevel(self.master)
            dialog.title("Enter New Cage Number")
            dialog.transient(self.master)
            dialog.grab_set()
            dialog.geometry("+100+300")

            tk.Label(dialog, text="Enter the new cage number:").pack(pady=10)

            prefix = ""
            if self.sheet_name == "NEX + PP2A":
                prefix = "2-A-"
            elif self.sheet_name == "CMV + PP2A":
                prefix = "8-A-"

            prefix_label = tk.Label(dialog, text=prefix)
            prefix_label.pack(side=tk.LEFT, padx=(10, 0))

            self.new_cage_entry = tk.Entry(dialog)
            self.new_cage_entry.pack(side=tk.LEFT, padx=(0, 10))
            self.new_cage_entry.focus_set() # Set focus to the entry widget

            tk.Button(dialog, text="Transfer", command=self.validate_and_transfer).pack(pady=10)
            dialog.wait_window(dialog)

    def transfer_to_death_row(self):
        if self.selected_mouse is not None:
            for cage_key, mice_list in self.mice_displayed.regular.items():
                if self.selected_mouse in mice_list:
                    mice_list.remove(self.selected_mouse)
                    if not mice_list:
                        del self.mice_displayed.regular[cage_key]
                    break

            self.remove_from_waiting_room_dict()

            self.selected_mouse['nuCA'] = 'Death Row'
            self.selected_mouse['sheet'] = 'Death Row'
            self.mice_displayed.death[self.selected_mouse['ID']] = self.selected_mouse
        self.cleanup_post_transfer()

    def transfer_from_death_row(self): # Release back to wherever the mice once were
        if self.selected_mouse is not None:
            self.remove_from_death_row_dict()

            original_cage = self.selected_mouse['cage']
            self.selected_mouse['nuCA'] = original_cage
            
            if str(original_cage).startswith('8-A-'):
                self.selected_mouse['sheet'] = 'CMV + PP2A'
            elif str(original_cage).startswith('2-A-'):
                self.selected_mouse['sheet'] = 'NEX + PP2A'
            else:
                self.selected_mouse['sheet'] = 'BACKUP'

            if self.selected_mouse['sheet'] == self.sheet_name:
                if original_cage not in self.mice_displayed.regular:
                    self.mice_displayed.regular[original_cage] = []
                self.mice_displayed.regular[original_cage].append(self.selected_mouse)
        self.cleanup_post_transfer()

    #########################################################################################################################

    def confirm_transfer(self, dialog):
        taCA = self.selected_target_cage.get()
        if self.selected_mouse is not None:

            for cage_key, mice_list in self.mice_displayed.regular.items():
                if self.selected_mouse in mice_list:
                    mice_list.remove(self.selected_mouse)

                    if not mice_list:
                        del self.mice_displayed.regular[cage_key]
                    break

            self.remove_from_death_row_dict()
            self.remove_from_waiting_room_dict()

            self.selected_mouse['nuCA'] = taCA
            if str(taCA).startswith('8-A-'):
                self.selected_mouse['sheet'] = 'CMV + PP2A'
            elif str(taCA).startswith('2-A-'):
                self.selected_mouse['sheet'] = 'NEX + PP2A'
            else:
                self.selected_mouse['sheet'] = 'BACKUP'

            if taCA not in self.mice_displayed.regular:
                self.mice_displayed.regular[taCA] = []
            self.mice_displayed.regular[taCA].append(self.selected_mouse)
        self.cleanup_post_transfer(dialog)

    def validate_and_transfer(self, dialog):
        entered_name = self.new_cage_entry.get().strip()
        
        if not entered_name:
            messagebox.showwarning("Invalid Input", "Please enter the cage number.", parent=dialog)
            return
        if not entered_name[0].isdigit() or not entered_name[-1].isdigit():
            messagebox.showwarning("Invalid Input", "Must start and end with digits.", parent=dialog)
            return
        
        if self.sheet_name == 'BACKUP':
            if '-B-' in entered_name:
                prefix = entered_name.split("-B-")[0]
                entered_suffix = entered_name.split("-B-")[1]
            else:
                entered_suffix = entered_name
        else: entered_suffix = entered_name

        digits_only = entered_suffix.replace("-","")

        if len(digits_only) == 0:
            messagebox.showwarning("Invalid Input", "Must include at least one digit sans prefix.", parent=dialog)
            return
        if not digits_only.isdigit():
            messagebox.showwarning("Invalid Input", "Only numbers and '-' are allowed sans prefix.", parent=dialog)
            return 
        if len(digits_only) > 4:
            messagebox.showwarning("Invalid Input", "Can only include four digits at most sans prefix.", parent=dialog)
            return
        
        new_cage_no = prefix + entered_suffix

        if new_cage_no in self.mice_displayed.regular: # Check if key exists in the dict
            messagebox.showwarning("Cage Exists", f"Cage '{new_cage_no}' already exists. Please enter a different number.", parent=dialog)
            self.new_cage_entry.delete(0, tk.END)
            return
        if self.sheet_name == 'BACKUP' and (new_cage_no.startswith('8-A-') or new_cage_no.startswith('2-A-')):
            messagebox.showwarning("Format Error", f"Backup cages are not supposed to start with '8-A-' or '2-A-'. Please enter a different number.", parent=dialog)
            self.new_cage_entry.delete(0, tk.END)
            return
        
        self.remove_from_waiting_room_dict()

        self.selected_mouse['nuCA'] = new_cage_no
        self.selected_mouse['sheet'] = self.sheet_name

        if new_cage_no not in self.mice_displayed.regular:
            self.mice_displayed.regular[new_cage_no] = []
        self.mice_displayed.regular[new_cage_no].append(self.selected_mouse)
        self.cleanup_post_transfer(dialog)

    def remove_from_waiting_room_dict(self):
        if self.selected_mouse['ID'] in self.mice_displayed.waiting:
            del self.mice_displayed.waiting[self.selected_mouse['ID']]

    def remove_from_death_row_dict(self):
        if self.selected_mouse['ID'] in self.mice_displayed.death:
            del self.mice_displayed.death[self.selected_mouse['ID']]

    def cleanup_post_transfer(self, dialog=None):
        if dialog:
            dialog.destroy()
        self.master.redraw_canvas()
        self.master.determine_save_status()
        self.master.close_metadata_window()