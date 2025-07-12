from datetime import date, datetime
import pandas as pd
import numpy as np

import mdb_utils

import traceback


def data_preprocess(excel_file, sheet_name):
    """Preprocesses Excel data and returns processed data as dict"""
    try:
        excel_file_obj = pd.ExcelFile(excel_file)
        df_sheet = excel_file_obj.parse(sheet_name)
        excel_file_obj.close()

        df_processed = df_sheet.copy()
        df_processed = df_processed.dropna(how='all')
        add_optional_cols(df_processed) # Add optional cols
        mdb_utils.issue_ID(df_processed)
        mdb_utils.date_calculator(df_processed)
        processed_data = df_processed.to_dict('index')
        
        return processed_data

    except Exception as e:
        print(f"An error occurred during Excel preprocessing: {e}\n{traceback.format_exc()}")
        return None

def write_processed_data_to_excel(excel_file, processed_data):
    """Writes processed data to Excel file"""
    # Create a new dictionary to hold mice that will be written to Excel. Mice in 'Death Row' will be placed into Memorial sheet.
    parental_mice_live, living_mice = parse_mice_data_for_write(processed_data)
    mice_to_write = memorial_cleanup(processed_data, living_mice, parental_mice_live)

    sorted_mice = dict(sorted(mice_to_write.items(),key=lambda x: x[1].get('cage')))
    df_sorted = pd.DataFrame.from_dict(sorted_mice, orient='index')

    # Format the dates into strings so they won't get ruined by Excel
    date_cols = ['birthDate', 'breedDate']
    df_format = mdb_utils.convert_dates_to_string(df_sorted, date_cols)

    df_final = cleanup_optional_cols(df_format)

    try:
        with pd.ExcelWriter(excel_file, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, sheet_name='MDb', index=False)
            writer.sheets['MDb'].autofit()
            return True

    except Exception as e:
        print(f"An error occurred during Excel writing: {e}\n{traceback.format_exc()}")
        return False

##########################################################################################################################

def mice_changelog(old_dict, new_dict, output_path):
    """Logs mice changes to a new Excel file"""
    try:
        old_dict_by_id = {entry['ID']: entry for entry in old_dict.values()}
        fields_to_compare = ['nuCA', 'sex', 'toe', 'genotype', 'birthDate', 'breedDate', 'parentF', 'parentM']
        added_entries, changed_entries = find_changes_for_changelog(new_dict, old_dict_by_id, fields_to_compare)
        df_added, df_changed, df_manual = organize_changelog_df(added_entries, changed_entries, fields_to_compare)

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%m%d_%H%M%S")
        log_file = f"{output_path}/mice_changelog_{timestamp}.xlsx"

        # Save to Excel
        with pd.ExcelWriter(log_file, engine='xlsxwriter') as writer:
            if not df_manual.empty:
                df_manual.to_excel(writer, sheet_name='Manual', index=False)
            if not df_added.empty:
                df_added.to_excel(writer, sheet_name='Added', index=False)
            if not df_changed.empty:
                df_changed.to_excel(writer, sheet_name='Changed', index=False)

            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                worksheet.autofit()

        print(f"Log saved to: {log_file}")
        return log_file
    except Exception as e:
        print(f"Error building changelog: {e}\n{traceback.format_exc()}")
    return False

##########################################################################################################################

def find_changes_for_changelog(new_dict, old_dict, fields_to_compare):
    added_entries = []
    changed_entries = []

    for new_entry in new_dict.values():
        old_entry = old_dict.get(new_entry['ID'])
        if not old_entry:
            added_entries.append(new_entry)
        elif any(new_entry.get(field) != old_entry.get(field) for field in fields_to_compare):
            changed_entries.append(new_entry)

    if not added_entries and not changed_entries:
        print("No changes found.")
        return None
    else:
        return added_entries, changed_entries
    
def organize_changelog_df(added_entries, changed_entries, fields_to_compare):
    fields_to_keep = ['ID'] + fields_to_compare + ['age', 'breedDays', 'sheet']
    manual_keep = ['cage', 'nuCA', 'sex', 'toe', 'genotype', 'birthDate']
    df_added = pd.DataFrame(added_entries).loc[:, fields_to_keep] if added_entries else pd.DataFrame()
    df_changed = pd.DataFrame(changed_entries).loc[:, fields_to_keep] if changed_entries else pd.DataFrame()
    df_manual = pd.DataFrame(changed_entries).loc[:,manual_keep] if changed_entries else pd.DataFrame()
    df_manual = df_manual.loc[df_manual['nuCA'] != df_manual['cage']] if not df_manual.empty else pd.DataFrame()

    date_cols = ['birthDate', 'breedDate']
    if not df_added.empty:
        df_added = mdb_utils.convert_dates_to_string(df_added, date_cols)
    if not df_changed.empty:
        df_changed = mdb_utils.convert_dates_to_string(df_changed, date_cols)
    if not df_manual.empty:
        df_manual = mdb_utils.convert_dates_to_string(df_manual, ['birthDate'])
    return df_added, df_changed, df_manual

##########################################################################################################################

def parse_mice_data_for_write(processed_data):
    parental_mice = set()
    parental_mice_live =  set()
    living_mice = set()
    for mouse_id, mouse_info in processed_data.items():
        if mouse_info.get('nuCA') == 'Death Row':
            print(f"Death Row mouse {mouse_id} transfer to Memorial")
            mouse_info['nuCA'] = 'Memorial'
            mouse_info['sheet'] = 'Memorial'
        if mouse_info.get('sheet') == 'BACKUP': # Remove breedDate for non-breeding ( BACKUP ) mice
            mouse_info['breedDate'] = '-'
            mouse_info['breedDays'] = '-'
        elif mouse_info.get('sheet') != 'BACKUP':  # Set nearest breedDate to today for newly introduced breeding mice
            breed_date = mouse_info.get('breedDate')
            if isinstance(breed_date, str):
                breed_date = pd.to_datetime(breed_date, errors='coerce', yearfirst=True, format='%Y-%m-%d')
            if pd.isna(breed_date):
                mouse_info['breedDate'] = date.today()
                mouse_info['breedDays'] = 0
        current_parental_mice = mouse_info['parentF'] + mouse_info['parentM'] 
        parental_mice.add(current_parental_mice)
        if mouse_info['sheet'] != 'Memorial':
            parental_mice_live.add(current_parental_mice)
            living_mice.add(mouse_info['ID'])
    return parental_mice_live, living_mice

def memorial_cleanup(processed_data, living_mice, parental_mice_live):
    mice_to_write = {}
    for mouse_id, mouse_info in processed_data.items():
        isAncient = mouse_info['age'] > 365
        hasLivingParent = mouse_info['parentF'] in living_mice or mouse_info['parentM'] in living_mice
        isParent = mouse_info['ID'] in parental_mice_live # is parent of still living mice
        if mouse_info.get('nuCA') == 'Memorial' and isAncient and not hasLivingParent and not isParent:
            print(f"Cleaned up mouse {mouse_id}, which has no living parents or children and is born more than 365 days ago.")
            continue
        cleaned_mouse_info = mouse_info.copy()
        cleaned_mouse_info['cage'] = cleaned_mouse_info['nuCA']
        mice_to_write[mouse_id] = cleaned_mouse_info
    return mice_to_write

##########################################################################################################################

def add_optional_cols(df):
    optional_columns = ['age','breedDays','parentF','parentM']
    for col in optional_columns:
        if col not in df:
            df[col] = '-'
    df['nuCA'] = df.loc[:, 'cage'] # Add nuCA for temporary cage storage solution, nuCA == new cage | nuka-ColA
    return df

def cleanup_optional_cols(df):
    cols_to_keep = ['ID', 'cage', 'sex', 'toe', 'genotype', 'birthDate','age', 'breedDate', 'breedDays', 'parentF', 'parentM']
    df_cleaned = df.loc[:, cols_to_keep]
    return df_cleaned