from datetime import date, datetime
import pandas as pd

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
    # Create a new dictionary to hold mice that will be written to Excel. Mice in 'Death Row' will be placed into Memorial sheet.
    parental_mice_live, living_mice = parse_mice_data_for_write(processed_data)
    mice_to_write = memorial_cleanup(processed_data, living_mice, parental_mice_live)

    sorted_mice = dict(sorted(mice_to_write.items(),key=lambda x: x[1].get('cage')))
    df_sorted = pd.DataFrame.from_dict(sorted_mice, orient='index')

    # Format the dates into strings so they won't get ruined by Excel
    date_cols = ['birthDate', 'breedDate']
    df_format = mdb_utils.df_date_col_formatter(df_sorted, date_cols)

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

def validate_excel(file_path, required_column=None): 
    if required_column is None: # Fallback to default ones
        required_columns = ['ID', 'cage', 'sex', 'toe', 'genotype', 'birthDate', 'breedDate']
    if not file_path.lower().endswith(('.xlsx', '.xls')):
        raise Exception("Invalid file type - must be .xlsx or .xls")
    # Process all data from MouseDatabase
    temp_excel = pd.ExcelFile(file_path)
    if 'MDb' not in temp_excel.sheet_names:
        raise Exception(f"No 'MDb' among sheets in chosen excel file. Check your chosen file.")
    temp_excel.close()
        


    df = pd.read_excel(file_path, 'MDb')
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise Exception(f"Missing required columns {missing}")

##########################################################################################################################

def mice_changelog(old_dict, new_dict, output_path):
    try:
        old_dict_by_id = {entry['ID']: entry for entry in old_dict.values()}
        added_entries, changed_entries = find_changes_for_changelog(new_dict, old_dict_by_id)
        df_added, df_changed, df_manual = organize_changelog_df(added_entries, changed_entries)

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

def changelog_loader(changelog_file_path, mice_dict):
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
        raise Exception("The selected changelog file is empty or has no valid sheets.")
    
    changes_applied_count = 0
    exception_entries = []
    mice_added_count = 0

    # Process each sheet type
    for sheet_type, changelog_df in changelog_dfs.items():
        if sheet_type == 'Added':
            changes_applied_count, mice_added_count, exception_entries = load_changelog_add(
                changelog_df, mice_dict, changes_applied_count, mice_added_count, exception_entries)       
        else:  # Changed sheet
            changes_applied_count, exception_entries = load_changelog_change(
                changelog_df, mice_dict, changes_applied_count, exception_entries)

    result_message = [
    f"Successfully applied {changes_applied_count} changes:",
    f"- {mice_added_count} new mice added",
    f"- {changes_applied_count - mice_added_count} existing mice updated"
    ]
            
    return result_message, exception_entries

def load_changelog_add(changelog_df, mice_dict, changes_applied_count, exception_entries):
    for index, changelog_row in changelog_df.iterrows():
        changelog_id = str(changelog_row['ID'])
        
        # Check if mouse already exists
        mouse_exists = any(
            mouse_data.get('ID') == changelog_id 
            for mouse_data in mice_dict.values()
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
            new_index = max(mice_dict.keys()) + 1 if mice_dict else 0
            mice_dict[new_index] = new_mouse
            mice_added_count += 1
            changes_applied_count += 1
        else:
            exception_entries.append(f"ID: {changelog_id}, already exists in database (not added)")
    return changes_applied_count, mice_added_count, exception_entries

def load_changelog_change(changelog_df, mice_dict, changes_applied_count, exception_entries):
    for index, changelog_row in changelog_df.iterrows():
        changelog_id = str(changelog_row['ID'])
        mouse_found = False
        for mouse_index, mouse_data in mice_dict.items():
            if mouse_data.get('ID') == changelog_id:
                mouse_found = True
                fields_to_update = ['nuCA', 'sex', 'toe', 'genotype', 'birthDate', 'breedDate', 'sheet', 'parentF', 'parentM']
                for field in fields_to_update:
                    if field in changelog_row:
                        mice_dict[mouse_index][field] = changelog_row[field]
                        # Update cage if nuCA changed
                        if field == 'nuCA':
                            mice_dict[mouse_index]['cage'] = changelog_row[field]
                changes_applied_count += 1

                break  # Found the mouse, move to next entry
        if not mouse_found:
            exception_entries.append(f"ID: {changelog_id}, not found in current data")
    return changes_applied_count, exception_entries

def find_changes_for_changelog(old_dict, new_dict, fields_to_compare=None, check_only=False):
    if fields_to_compare is None: # Fallback to default fields
        fields_to_compare = ['nuCA', 'sex', 'toe', 'genotype', 'birthDate', 'breedDate', 'parentF', 'parentM']

    if check_only:
        return any(
            (new_entry['ID'] not in old_dict) or
            any(new_entry.get(f) != old_dict[new_entry['ID']].get(f) for f in fields_to_compare)
            for new_entry in new_dict.values()
        )

    added = [e for e in new_dict.values() if e['ID'] not in old_dict]
    changed = [
        e for e in new_dict.values() if e['ID'] in old_dict and
        any(e.get(f) != old_dict[e['ID']].get(f) for f in fields_to_compare)
    ]

    if not added and not changed:
        print("No changes found.")
        return None
    else:
        return added, changed
    
def organize_changelog_df(added_entries, changed_entries, fields_to_compare):
    fields_to_keep = ['ID'] + fields_to_compare + ['age', 'breedDays', 'sheet']
    manual_keep = ['cage', 'nuCA', 'sex', 'toe', 'genotype', 'birthDate']
    df_added = pd.DataFrame(added_entries).loc[:, fields_to_keep] if added_entries else pd.DataFrame()
    df_changed = pd.DataFrame(changed_entries).loc[:, fields_to_keep] if changed_entries else pd.DataFrame()
    df_manual = pd.DataFrame(changed_entries).loc[:,manual_keep] if changed_entries else pd.DataFrame()
    df_manual = df_manual.loc[df_manual['nuCA'] != df_manual['cage']] if not df_manual.empty else pd.DataFrame()

    date_cols = ['birthDate', 'breedDate']
    if not df_added.empty:
        df_added = mdb_utils.df_date_col_formatter(df_added, date_cols)
    if not df_changed.empty:
        df_changed = mdb_utils.df_date_col_formatter(df_changed, date_cols)
    if not df_manual.empty:
        df_manual = mdb_utils.df_date_col_formatter(df_manual, ['birthDate'])
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