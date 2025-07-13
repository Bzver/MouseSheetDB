import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from mdb_gui import redraw_canvas
from mdb_vis import close_metadata_window

def transfer_to_existing_cage(master, selected_mouse, selected_target_cage, mice_displayed):
    if selected_mouse is not None:
        dialog = tk.Toplevel(master)
        dialog.title("Select Target Cage")
        dialog.transient(master)
        dialog.grab_set()
        dialog.geometry("+100+300")

        tk.Label(dialog, text="Select a cage:").pack(pady=10)

        current_cage = selected_mouse.get('nuCA')
        existing_cages = sorted([c for c in mice_displayed.regular.keys() if c != current_cage])

        if not existing_cages:
            messagebox.showinfo("No Cages", "No other existing cages available for transfer.")
            dialog.destroy()
            return

        selected_target_cage = tk.StringVar(dialog)
        selected_target_cage.set(existing_cages[0])

        cage_dropdown = ttk.Combobox(dialog, textvariable=selected_target_cage, values=existing_cages, state="readonly")
        cage_dropdown.pack(pady=5)

        tk.Button(dialog, text="Transfer", command=confirm_transfer).pack(pady=10)
        dialog.wait_window(dialog)
    redraw_canvas()
    close_metadata_window()

def transfer_to_waiting_room(selected_mouse, mice_displayed):
    if selected_mouse is not None:
        for cage_key, mice_list in mice_displayed.regular.items():
            if selected_mouse in mice_list:
                mice_list.remove(selected_mouse)
                if not mice_list:
                    del mice_displayed.regular[cage_key]
                break

        if selected_mouse['ID'] in mice_displayed.death:
            del mice_displayed.death[selected_mouse['ID']]

        selected_mouse['nuCA'] = 'Waiting Room'
        selected_mouse['sheet'] = 'Waiting Room'
        mice_displayed.waiting[selected_mouse['ID']] = selected_mouse
    redraw_canvas()
    close_metadata_window()

def transfer_to_new_cage(master, selected_mouse, sheet_name):
    if selected_mouse is not None:
        dialog = tk.Toplevel(master)
        dialog.title("Enter New Cage Number")
        dialog.transient(master)
        dialog.grab_set()
        dialog.geometry("+100+300")

        tk.Label(dialog, text="Enter the new cage number:").pack(pady=10)

        prefix = ""
        if sheet_name == "NEX + PP2A":
            prefix = "2-A-"
        elif sheet_name == "CMV + PP2A":
            prefix = "8-A-"

        prefix_label = tk.Label(dialog, text=prefix)
        prefix_label.pack(side=tk.LEFT, padx=(10, 0))

        new_cage_entry = tk.Entry(dialog)
        new_cage_entry.pack(side=tk.LEFT, padx=(0, 10))
        new_cage_entry.focus_set() # Set focus to the entry widget

        tk.Button(dialog, text="Transfer", command=validate_and_transfer).pack(pady=10)
        dialog.wait_window(dialog)

def transfer_to_death_row(selected_mouse, mice_displayed):
    if selected_mouse is not None:
        for cage_key, mice_list in mice_displayed.regular.items():
            if selected_mouse in mice_list:
                mice_list.remove(selected_mouse)
                if not mice_list:
                    del mice_displayed.regular[cage_key]
                break

        if selected_mouse['ID'] in mice_displayed.waiting:
            del mice_displayed.waiting[selected_mouse['ID']]

        selected_mouse['nuCA'] = 'Death Row'
        selected_mouse['sheet'] = 'Death Row'
        mice_displayed.death[selected_mouse['ID']] = selected_mouse
    redraw_canvas()
    close_metadata_window()

def transfer_from_death_row(selected_mouse, mice_displayed, sheet_name): # Release back to wherever the mice once were
    if selected_mouse is not None:
        if selected_mouse['ID'] in mice_displayed.death:
            del mice_displayed.death[selected_mouse['ID']]
        if selected_mouse['ID'] in mice_displayed.waiting:
            del mice_displayed.waiting[selected_mouse['ID']]

        original_cage = selected_mouse['cage']
        selected_mouse['nuCA'] = original_cage
        
        if str(original_cage).startswith('8-A-'):
            selected_mouse['sheet'] = 'CMV + PP2A'
        elif str(original_cage).startswith('2-A-'):
            selected_mouse['sheet'] = 'NEX + PP2A'
        else:
            selected_mouse['sheet'] = 'BACKUP'

        if selected_mouse['sheet'] == sheet_name:
            if original_cage not in mice_displayed.regular:
                mice_displayed.regular[original_cage] = []
            mice_displayed.regular[original_cage].append(selected_mouse)
        
    redraw_canvas()
    close_metadata_window()

#########################################################################################################################

def confirm_transfer(dialog, selected_mouse, selected_target_cage, mice_displayed):
    taCA = selected_target_cage.get()
    if selected_mouse is not None:

        for cage_key, mice_list in mice_displayed.regular.items():
            if selected_mouse in mice_list:
                mice_list.remove(selected_mouse)

                if not mice_list:
                    del mice_displayed.regular[cage_key]
                break

        if selected_mouse['ID'] in mice_displayed.waiting:
            del mice_displayed.waiting[selected_mouse['ID']]
        if selected_mouse['ID'] in mice_displayed.death:
            del mice_displayed.death[selected_mouse['ID']]

        selected_mouse['nuCA'] = taCA
        if str(taCA).startswith('8-A-'):
            selected_mouse['sheet'] = 'CMV + PP2A'
        elif str(taCA).startswith('2-A-'):
            selected_mouse['sheet'] = 'NEX + PP2A'
        else:
            selected_mouse['sheet'] = 'BACKUP'

        if taCA not in mice_displayed.regular:
            mice_displayed.regular[taCA] = []
        mice_displayed.regular[taCA].append(selected_mouse)
        
    redraw_canvas()
    dialog.destroy()
    close_metadata_window()

def validate_and_transfer(dialog, selected_mouse, new_cage_entry, mice_displayed, sheet_name):
    entered_name = new_cage_entry.get().strip()
    
    if not entered_name:
        messagebox.showwarning("Invalid Input", "Please enter the cage number.", parent=dialog)
        return
    if not entered_name[0].isdigit() or not entered_name[-1].isdigit():
        messagebox.showwarning("Invalid Input", "Must start and end with digits.", parent=dialog)
        return
    
    if sheet_name == 'BACKUP':
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

    if new_cage_no in mice_displayed.regular: # Check if key exists in the dict
        messagebox.showwarning("Cage Exists", f"Cage '{new_cage_no}' already exists. Please enter a different number.", parent=dialog)
        new_cage_entry.delete(0, tk.END)
        return
    if sheet_name == 'BACKUP' and (new_cage_no.startswith('8-A-') or new_cage_no.startswith('2-A-')):
        messagebox.showwarning("Format Error", f"Backup cages are not supposed to start with '8-A-' or '2-A-'. Please enter a different number.", parent=dialog)
        new_cage_entry.delete(0, tk.END)
        return
    
    if selected_mouse['ID'] in mice_displayed.waiting:
        del mice_displayed.waiting[selected_mouse['ID']]

    selected_mouse['nuCA'] = new_cage_no
    selected_mouse['sheet'] = sheet_name

    if new_cage_no not in mice_displayed.regular:
        mice_displayed.regular[new_cage_no] = []
    mice_displayed.regular[new_cage_no].append(selected_mouse)
    
    redraw_canvas()
    close_metadata_window()
    dialog.destroy()