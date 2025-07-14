import shutil

import pandas as pd
from datetime import date, datetime

import mdb_utils as mut

import traceback
import logging


"""
This module handles input/output operations for the MouseSheetDB, including reading, writing,
validating Excel files, managing changelogs, and processing mouse data.
"""

# Define required columns for the mouse databasefor loaded Excel
REQUIRED_COLUMNS = ["ID", "cage", "sex", "toe", "genotype", "birthDate", "breedDate"]
# Define columns that contain date information
DATE_COLUMNS = ["birthDate", "breedDate"]
# Define columns used for comparing old and new mouse data in the changelog
COMPARE_COLUMNS = ["nuCA", "sex", "toe", "genotype", "birthDate", "breedDate", "parentF", "parentM"]
# Define sheet names used in the changelog Excel file
CHANGELOG_SHEETS = ["Added", "Changed"]
# Define columns to keep when organizing changelog data
KEEP_COLUMNS = ["ID"] + COMPARE_COLUMNS + ["age", "breedDays", "category"]
# Define columns that are manually editable in the database
MANUAL_COLUMNS = ["cage", "nuCA", "sex", "toe", "genotype", "birthDate"]


def data_preprocess(excel_file, sheet_name):
    """
    Preprocesses Excel data from a specified sheet and returns it as a dictionary.
    Args:
        excel_file (str): The path to the Excel file.
        sheet_name (str): The name of the sheet to read from.
    Returns:
        dict: A dictionary where keys are row indices and values are dictionaries
              representing processed mouse data, or None if an error occurs.
    """
    try:
        excel_file_obj = pd.ExcelFile(excel_file)
        df_sheet = excel_file_obj.parse(sheet_name)
        excel_file_obj.close()

        df_processed = mut.preprocess_df(df_sheet)
        processed_data = df_processed.to_dict("index")
        
        return processed_data

    except Exception as e:
        logging.error(f"An error occurred during Excel preprocessing: {e}\n{traceback.format_exc()}")
        return None

def write_processed_data_to_excel(excel_file, processed_data):
    """
    Writes processed mouse data to an Excel file.
    This function takes processed mouse data, organizes it, performs a memorial cleanup,
    and then writes the data to the "MDb" sheet in the specified Excel file.
    The sheet will be autofitted for better readability.
    Args:
        excel_file (str): The path to the Excel file where data will be written.
        processed_data (dict): A dictionary containing the processed mouse data.
    Returns:
        bool: True if the data was successfully written, False otherwise.
    """
    parental_mice_live, living_mice = parse_mice_data_for_write(processed_data)
    mice_to_write = memorial_cleanup(processed_data, living_mice, parental_mice_live)
    sorted_mice = dict(sorted(mice_to_write.items(),key=lambda x: x[1].get("cage")))
    df_sorted = pd.DataFrame.from_dict(sorted_mice, orient="index")
    df_postprocessed = mut.process_df_before_export(df_sorted, DATE_COLUMNS)

    try:
        with pd.ExcelWriter(excel_file, engine="xlsxwriter") as writer:
            df_postprocessed.to_excel(writer, sheet_name="MDb", index=False)
            writer.sheets["MDb"].autofit()
            return True

    except Exception as e:
        logging.error(f"An error occurred during Excel writing: {e}\n{traceback.format_exc()}")
        return False
    
##########################################################################################################################

def validate_excel(file_path, required_columns=REQUIRED_COLUMNS):
    """
    Validates an Excel file to ensure it's a valid .xlsx or .xls file,
    contains an "MDb" sheet, and has all required columns.
    Args:
        file_path (str): The path to the Excel file to validate.
        required_columns (list, optional): A list of column names that must be present.
                                           Defaults to REQUIRED_COLUMNS.
    Raises:
        Exception: If the file type is invalid, the "MDb" sheet or any required columns are missing.
    """
    if not file_path.lower().endswith((".xlsx", ".xls")):
        raise Exception("Invalid file type - must be .xlsx or .xls")
    # Process all data from MouseDatabase
    temp_excel = pd.ExcelFile(file_path)
    if "MDb" not in temp_excel.sheet_names:
        raise Exception(f"No 'MDb' among sheets in chosen excel file. Check your chosen file.")
    temp_excel.close()

    df = pd.read_excel(file_path, "MDb")
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise Exception(f"Missing required columns {missing}")

##########################################################################################################################

def mice_changelog(old_dict, new_dict, output_path):
    """
    Generates an Excel changelog file detailing additions and changes between two mouse datasets.
    The changelog will contain three sheets: "Manual" (for manual change instructions),
    "Added" (for newly added mice), and "Changed" (for modified existing mice).
    The file will be timestamped and saved to the specified output path.
    Args:
        old_dict (dict): The dictionary representing the old mouse data.
        new_dict (dict): The dictionary representing the new mouse data.
        output_path (str): The directory where the changelog Excel file will be saved.
    Returns:
        str or False: The path to the generated changelog file if successful, False otherwise.
    """
    try:
        added_entries, changed_entries = find_changes_for_changelog(old_dict, new_dict)
        df_added, df_changed, df_manual = organize_changelog_df(added_entries, changed_entries)

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%m%d_%H%M%S")
        log_file = f"{output_path}/mice_changelog_{timestamp}.xlsx"

        # Save to Excel
        with pd.ExcelWriter(log_file, engine="xlsxwriter") as writer:
            if not df_manual.empty:
                df_manual.to_excel(writer, sheet_name="Manual", index=False)
            if not df_added.empty:
                df_added.to_excel(writer, sheet_name="Added", index=False)
            if not df_changed.empty:
                df_changed.to_excel(writer, sheet_name="Changed", index=False)

            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                worksheet.autofit()

        logging.info(f"Log saved to: {log_file}")
        return log_file
    except Exception as e:
        logging.error(f"Error building changelog: {e}\n{traceback.format_exc()}")
    return False

def changelog_loader(changelog_file_path, mice_dict, changelog_sheets=CHANGELOG_SHEETS):
    """
    Loads changes from a changelog Excel file and applies them to the main mice dictionary.
    This function reads "Added" and "Changed" sheets from the changelog file,
    and then applies the respective additions and modifications to the `mice_dict`.
    It returns a summary message of applied changes and any entries that caused exceptions.
    Args:
        changelog_file_path (str): The path to the changelog Excel file.
        mice_dict (dict): The main dictionary containing mouse data to be updated.
        changelog_sheets (list, optional): A list of sheet names to process.
                                           Defaults to CHANGELOG_SHEETS.
    Returns:
        tuple: A tuple containing:
               - str: A message summarizing the applied changes.
               - list: A list of strings detailing entries that caused exceptions.
    Raises:
        Exception: If the selected changelog file is empty or has no valid sheets.
    """
    # Read sheets for Added and Changed mice from the changelog file
    changelog_dfs = {}
    for sheet_name in changelog_sheets:
        try:
            df = pd.read_excel(changelog_file_path, sheet_name=sheet_name)
            if not df.empty:
                changelog_dfs[sheet_name] = df
        except:
            continue  # Skip if sheet doesn"t exist
    if not changelog_dfs:
        raise Exception("The selected changelog file is empty or has no valid sheets.")
    
    changes_applied_count, mice_added_count = 0, 0
    exception_entries = []

    for sheet_type, changelog_df in changelog_dfs.items():
        if sheet_type == "Added":
            changes_applied_count, mice_added_count, exception_entries = load_changelog_add(changelog_df, mice_dict, changes_applied_count, mice_added_count, exception_entries)
        else:  # Changed sheet
            changes_applied_count, exception_entries = load_changelog_change(changelog_df, mice_dict, changes_applied_count, exception_entries)

    result_message = f"Successfully applied {changes_applied_count} changes:\n{mice_added_count} new mice added\n{changes_applied_count - mice_added_count} existing mice updated"
    return result_message, exception_entries

def load_changelog_add(changelog_df, mice_dict, changes_applied_count, mice_added_count, exception_entries):
    """
    Loads and applies "Added" entries from a changelog DataFrame to the main mice dictionary.
    This function iterates through rows in the "Added" changelog DataFrame. For each entry,
    if the mouse ID does not already exist in `mice_dict`, a new mouse entry is created
    and added. If the mouse ID already exists, an exception entry is recorded.
    Args:
        changelog_df (pd.DataFrame): DataFrame containing "Added" mouse entries.
        mice_dict (dict): The main dictionary containing mouse data to be updated.
        changes_applied_count (int): Current count of total changes applied.
        mice_added_count (int): Current count of new mice added.
        exception_entries (list): List to append exception messages.
    Returns:
        tuple: A tuple containing:
               - int: Updated count of total changes applied.
               - int: Updated count of new mice added.
               - list: Updated list of exception entries.
    """
    for index, changelog_row in changelog_df.iterrows():
        changelog_id = str(changelog_row["ID"])

        if changelog_id not in mice_dict: # Check if mouse already exists
            # Create new mouse entry
            new_mouse = {
                "ID": changelog_id,
                **{key: changelog_row.get(key, "") for key in [
                    "nuCA", "sex", "toe", "genotype", "birthDate", "breedDate",
                    "age", "breedDays", "parentF", "parentM"
                ]},
                "category": changelog_row.get("category", "BACKUP"),
                "cage": "Waiting Room",
            }
            # Add to mouseDB with a new index
            new_index = changelog_id if mice_dict else 0
            mice_dict[new_index] = new_mouse
            mice_added_count += 1
            changes_applied_count += 1
        else:
            exception_entries.append(f"ID: {changelog_id}, already exists in database (not added)")
    return changes_applied_count, mice_added_count, exception_entries

def load_changelog_change(changelog_df, mice_dict, changes_applied_count, exception_entries):
    """
    Loads and applies "Changed" entries from a changelog DataFrame to the main mice dictionary.
    This function iterates through rows in the "Changed" changelog DataFrame. For each entry,
    if the mouse ID exists in `mice_dict`, relevant fields (nuCA, sex, toe, etc.) are updated.
    If the mouse ID is not found, an exception entry is recorded.
    Args:
        changelog_df (pd.DataFrame): DataFrame containing "Changed" mouse entries.
        mice_dict (dict): The main dictionary containing mouse data to be updated.
        changes_applied_count (int): Current count of total changes applied.
        exception_entries (list): List to append exception messages.
    Returns:
        tuple: A tuple containing:
               - int: Updated count of total changes applied.
               - list: Updated list of exception entries.
    """
    for index, changelog_row in changelog_df.iterrows():
        changelog_id = str(changelog_row["ID"])
        
        if changelog_id in mice_dict:
            mouse_data = mice_dict[changelog_id]
            fields_to_update = ["nuCA", "sex", "toe", "genotype", "birthDate", "breedDate", "category", "parentF", "parentM"]
            for field in fields_to_update:
                if field in changelog_row:
                    mouse_data[field] = changelog_row[field]
                    # Update cage if nuCA changed
                    if field == "nuCA":
                        mouse_data["cage"] = changelog_row[field]
            changes_applied_count += 1
        else:
            exception_entries.append(f"ID: {changelog_id}, not found in current data")
    return changes_applied_count, exception_entries

def find_changes_for_changelog(old_dict, new_dict, fields_to_compare=COMPARE_COLUMNS, check_only=False):
    """
    Compares two mouse data dictionaries to identify added and changed entries for a changelog.
    Args:
        old_dict (dict): The dictionary representing the old mouse data.
        new_dict (dict): The dictionary representing the new mouse data.
        fields_to_compare (list, optional): A list of fields to compare for changes.
                                            Defaults to COMPARE_COLUMNS.
        check_only (bool, optional): If True, the function returns True immediately
                                     upon finding any change (added or modified)
                                     without collecting all changes. Defaults to False.
    Returns:
        tuple or bool: If `check_only` is True, returns True if changes are found, False otherwise.
                       If `check_only` is False, returns a tuple containing two lists:
                       - list: IDs of added mice.       - list: IDs of changed mice.
                       Returns False if no changes are found and `check_only` is False.
    """
    if not check_only:
        added, changed = [], []
    for mouse in new_dict:
        if mouse not in old_dict:
            if check_only:
                return True
            added.append(mouse)
        elif any(mouse.get(f) != old_dict[mouse].get(f) for f in fields_to_compare):
            if check_only:
                return True
            changed.append(mouse)

    if not added and not changed:
        logging.info("No changes found.")
        return False
    else:
        return added, changed
    
def organize_changelog_df(added_entries, changed_entries, fields_to_keep=KEEP_COLUMNS, manual_cols=MANUAL_COLUMNS, date_cols=DATE_COLUMNS):
    """
    Organizes added and changed mouse entries into DataFrames for changelog generation.
    This function takes lists of added and changed mouse entries, converts them into
    Pandas DataFrames, formats date columns, and identifies entries requiring manual
    review (where 'nuCA' and 'cage' differ).
    Args:
        added_entries (list): A list of dictionaries for newly added mice.
        changed_entries (list): A list of dictionaries for changed mice.
        fields_to_keep (list, optional): Columns to retain in the DataFrames.
                                         Defaults to KEEP_COLUMNS.
        manual_cols (list, optional): Columns relevant for manual review.
                                      Defaults to MANUAL_COLUMNS.
        date_cols (list, optional): Columns that should be formatted as dates.
                                    Defaults to DATE_COLUMNS.
    Returns:
        tuple: A tuple containing three pandas.DataFrame objects:
               - df_added (pd.DataFrame or None): DataFrame of added mice.
               - df_changed (pd.DataFrame or None): DataFrame of changed mice.
               - df_manual (pd.DataFrame or None): DataFrame of mice requiring manual review.
    """
    df_added, df_changed, df_manual = None, None, None
    if added_entries:
        df_added = mut.df_date_col_formatter(pd.DataFrame(added_entries).loc[:, fields_to_keep], date_cols)
    if changed_entries:
        df_changed_temp = pd.DataFrame(changed_entries).loc[:, fields_to_keep]
        df_changed = mut.df_date_col_formatter(df_changed_temp, date_cols)
        df_manual = df_changed_temp.loc[df_changed_temp["nuCA"] != df_changed_temp["cage"], manual_cols]
    return df_added, df_changed, df_manual

##########################################################################################################################

def parse_mice_data_for_write(processed_data):
    """
    Parses processed mouse data to identify parental mice and living mice for writing.
    This function iterates through the processed mouse data, updates "Death Row" mice
    to "Memorial" category, handles `breedDate` for "BACKUP" and non-"BACKUP" mice,
    and populates sets of living mice and parental mice that have living offspring.
    Args:
        processed_data (dict): A dictionary containing the processed mouse data.
    Returns:
        tuple: A tuple containing two sets:
               - parental_mice_live (set): IDs of parental mice with living offspring.
               - living_mice (set): IDs of all living mice.
    """
    parental_mice, parental_mice_live, living_mice = set(), set(), set()
    for mouse_id, mouse_info in processed_data.items():
        if mouse_info.get("nuCA") == "Death Row":
            logging.info(f"Death Row mouse {mouse_id} transfer to Memorial")
            mouse_info["nuCA"] = "Memorial"
            mouse_info["category"] = "Memorial"
        if mouse_info.get("category") == "BACKUP": # Remove breedDate for non-breeding ( BACKUP ) mice
            mouse_info["breedDate"] = None
            mouse_info["breedDays"] = None
        elif mouse_info.get("category") != "BACKUP":  # Set nearest breedDate to today for newly introduced breeding mice
            breed_date = mouse_info.get("breedDate")
            if isinstance(breed_date, str):
                breed_date = pd.to_datetime(breed_date, errors="coerce", yearfirst=True, format="%y-%m-%d")
            if pd.isna(breed_date):
                mouse_info["breedDate"] = date.today()
                mouse_info["breedDays"] = 0
        current_parental_mice = mouse_info["parentF"] + mouse_info["parentM"]
        parental_mice.add(current_parental_mice)
        if mouse_info["category"] != "Memorial":
            parental_mice_live.add(current_parental_mice)
            living_mice.add(mouse_info["ID"])
    return parental_mice_live, living_mice

def memorial_cleanup(processed_data, living_mice, parental_mice_live):
    """
    Performs a cleanup of "Memorial" mice based on age, living parents, and living offspring.
    Mice in the "Memorial" category that are older than 365 days, have no living parents,
    and are not parents of any living mice will be excluded from the data to be written.
    For other mice, the 'cage' field is updated to match 'nuCA'.
    Args:
        processed_data (dict): The dictionary containing all processed mouse data.
        living_mice (set): A set of IDs of all currently living mice.
        parental_mice_live (set): A set of IDs of parental mice with living offspring.
    Returns:
        dict: A new dictionary containing mouse data after the memorial cleanup,
              ready for writing to Excel.
    """
    mice_to_write = {}
    for mouse_id, mouse_info in processed_data.items():
        isAncient = mouse_info["age"] > 365
        hasLivingParent = mouse_info["parentF"] in living_mice or mouse_info["parentM"] in living_mice
        isParent = mouse_info["ID"] in parental_mice_live # is parent of still living mice
        if mouse_info.get("nuCA") == "Memorial" and isAncient and not hasLivingParent and not isParent:
            logging.info(f"Cleaned up mouse {mouse_id}, which has no living parents or children and is born more than 365 days ago.")
            continue
        cleaned_mouse_info = mouse_info.copy()
        cleaned_mouse_info["cage"] = cleaned_mouse_info["nuCA"]
        mice_to_write[mouse_id] = cleaned_mouse_info
    return mice_to_write

##########################################################################################################################

def create_backup(excel_file):
    """
    Creates a timestamped backup copy of the original Excel file.
    The backup file will be named with the original filename appended with "_BACKUP_"
    and the current time (HH-MM-SS).
    Args:
        excel_file (str): The path to the original Excel file to be backed up.
    Returns:
        str or None: The path to the created backup file if successful, None otherwise.
    """
    current_time = datetime.now().time()
    formatted_time = current_time.strftime("%H-%M-%S")
    excel_filename = excel_file.removesuffix(".xlsx")
    backup_file = f"{excel_filename}_BACKUP_{formatted_time}.xlsx"
    try:
        shutil.copy2(excel_file, backup_file)
        return backup_file
    except FileNotFoundError:
        logging.error(f"Error: Original file '{excel_file}' not found. Cannot create backup.")
        return None