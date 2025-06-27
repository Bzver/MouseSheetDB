from datetime import date, datetime
import pandas as pd
import numpy as np
import random

import traceback

def data_preprocess(excel_file, sheet_name):
    """Preprocesses Excel data and returns processed DataFrames"""
    try:
        excel_file_obj = pd.ExcelFile(excel_file)
        sheet_df = excel_file_obj.parse(sheet_name)
        excel_file_obj.close()

        df_processed = process_sheet_data(sheet_df)
        processed_data = df_processed.to_dict('index')
        
        return processed_data

    except Exception as e:
        print(f"An error occurred during Excel preprocessing: {e}\n{traceback.format_exc()}")
        return None

def process_sheet_data(df_sheet):
    """Processes sheet data: fills missing values, calculates ages, assigns sheet categories, and generates IDs."""
    today_for_calc = date.today()
    df_data = df_sheet.copy()
    df_data = df_data.dropna(how='all')

    # Add optional cols if not already there
    optional_columns = ['age','breedDays','parentF','parentM']
    for col in optional_columns:
        if col not in df_data:
            df_data[col] = '-'

    # Load and process birthDate
    df_data['birthDate'] = pd.to_datetime(df_data['birthDate'], errors='coerce', yearfirst=True, format='%Y-%m-%d')

    # Add nuCA for temporary cage storage solution, nuCA == new cage / nuka-ColA
    df_data['nuCA'] = df_data.loc[:, 'cage']

    # Identify rows where ID is missing/blank/NaN
    ID_mask = df_data['ID'].isna() | (df_data['ID'] == '')

    # Only process rows where ID is blank
    if ID_mask.any():
        df_data.loc[ID_mask, 'genoID'] = df_data.loc[ID_mask, 'genotype'].apply(process_genotypeID)
        df_data.loc[ID_mask, 'dobID'] = df_data.loc[ID_mask, 'birthDate'].apply(process_birthDateID)
        df_data.loc[ID_mask, 'toeID'] = df_data.loc[ID_mask, 'toe'].apply(process_toeID)
        df_data.loc[ID_mask, 'sexID'] = df_data.loc[ID_mask, 'sex'].apply(process_sexID)
        df_data.loc[ID_mask, 'cageID'] = df_data.loc[ID_mask, 'nuCA'].apply(process_cageID)
        df_data.loc[ID_mask, 'ID'] = df_data.loc[ID_mask].apply(
            lambda row: f"{row['genoID']}{row['dobID']}{row['toeID']}{row['sexID']}{row['cageID']}", 
            axis='columns'
        )
        # Check for duplicate IDs in the newly generated ones
        new_ids = df_data.loc[ID_mask, 'ID']
        duplicates = new_ids[new_ids.duplicated()]

        if not duplicates.empty:
            raise ValueError(f"Duplicate IDs generated: {duplicates.unique().tolist()}")
            
        # Check if any new IDs conflict with existing non-blank IDs
        existing_ids = df_data.loc[~ID_mask, 'ID']
        conflicting_ids = new_ids[new_ids.isin(existing_ids)]
        if not conflicting_ids.empty:
            raise ValueError(f"Generated IDs conflict with existing IDs: {conflicting_ids.unique().tolist()}")
        
        # Drop the temporary columns
        df_data = df_data.drop(['genoID', 'dobID', 'sexID', 'toeID', 'cageID'], axis='columns', errors='ignore')

    # Apply categorical ident (sheet)
    df_data['sheet'] = np.select(
    [
        df_data['cage'].str.startswith('2-A-'),
        df_data['cage'].str.startswith('8-A-'),
        df_data['cage'] == 'Memorial'
    ],
    ['NEX + PP2A', 'CMV + PP2A', 'Memorial'],
    default='BACKUP'
    )

    # Calculate mouse ages for alive mice
    alive_mask = df_data['sheet'] != 'Memorial'
    if alive_mask.any():
        df_data.loc[alive_mask, 'age'] = df_data.loc[alive_mask, 'birthDate'].apply(
            lambda dob: get_age_days(dob, today_for_calc))
    
    # Calculate last breed days for alive and non-BACKUP mice
    breeding_mask = ~df_data['sheet'].isin(['Memorial', 'BACKUP'])
    if breeding_mask.any():
        df_data.loc[breeding_mask, 'breedDays'] = df_data.loc[breeding_mask, 'breedDate'].apply(
            lambda bd: get_days_since_last_breed(bd, today_for_calc))

    return df_data

##########################################################################################################################

def get_age_days(dob_val, today_date):
    """Calculates age in days from birthDate"""
    if pd.notna(dob_val):
        try:
            if isinstance(dob_val, (pd.Timestamp, datetime)):
                dob_date_obj = dob_val.date()
            elif isinstance(dob_val, date):
                dob_date_obj = dob_val
            else:
                dob_date_obj = pd.to_datetime(dob_val, errors='coerce', yearfirst=True, format='%Y-%m-%d').date()
                if pd.isna(dob_date_obj): # pd.to_datetime returns NaT for unparseable
                    return "-"

            if dob_date_obj <= today_date:
                return (today_date - dob_date_obj).days
            else:
                return "Time traveller"
        except Exception:
            return "-"
    return "-"

def get_days_since_last_breed(last_breed_val, today_date):
    """Calculates days since breed."""
    if pd.notna(last_breed_val):

        if isinstance(last_breed_val, str) and last_breed_val.strip() == '-':
            return "-" # Handle specific placeholder
        try:
            if isinstance(last_breed_val, (pd.Timestamp, datetime)):
                last_breed_date_obj = last_breed_val.date()
            elif isinstance(last_breed_val, date):
                last_breed_date_obj = last_breed_val
            else:
                last_breed_date_obj = pd.to_datetime(last_breed_val, errors='coerce', yearfirst=True, format='%Y-%m-%d').date()
                if pd.isna(last_breed_date_obj):
                    return "-"
            if last_breed_date_obj <= today_date:
                return (today_date - last_breed_date_obj).days
            else:
                return "Time traveller"
        except Exception:
            return "-"
    return "-"

def convert_dates_to_string(df, date_columns):
    for col in date_columns:
        if col in df.columns:
            # Handle datetime objects and pandas NaT
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%y-%m-%d')
            else:
                # Convert to string and clean missing values
                df[col] = df[col].apply(
                    lambda x: x.strftime('%y-%m-%d') 
                    if isinstance(x, (datetime, pd.Timestamp)) 
                    else ('' if pd.isna(x) else str(x))
                )
    return df

##########################################################################################################################

def mice_changelog(old_dict, new_dict, output_path):
    """Logs mice changes to a new Excel file"""
    try:
        old_dict_by_id = {entry['ID']: entry for entry in old_dict.values()}
        fields_to_compare = ['nuCA', 'sex', 'toe', 'genotype', 'birthDate', 'breedDate', 'parentF', 'parentM']
        added_entries = []
        changed_entries = []
        for new_entry in new_dict.values():
            old_entry = old_dict_by_id.get(new_entry['ID'])
            if not old_entry:
                added_entries.append(new_entry)
            elif any(new_entry.get(field) != old_entry.get(field) for field in fields_to_compare):
                changed_entries.append(new_entry)

        if not added_entries and not changed_entries:
            print("No changes found.")
            return None
        
        fields_to_keep = ['ID'] + fields_to_compare + ['age', 'breedDays', 'sheet']
        manual_keep = ['cage', 'nuCA', 'sex', 'toe', 'genotype', 'birthDate']
        df_added = pd.DataFrame(added_entries).loc[:, fields_to_keep] if added_entries else pd.DataFrame()
        df_changed = pd.DataFrame(changed_entries).loc[:, fields_to_keep] if changed_entries else pd.DataFrame()
        df_manual = pd.DataFrame(changed_entries).loc[:,manual_keep] if changed_entries else pd.DataFrame()
        df_manual = df_manual.loc[df_manual['nuCA'] != df_manual['cage']] if not df_manual.empty else pd.DataFrame()

        # Process date columns in each DataFrame
        date_cols = ['birthDate', 'breedDate']
        if not df_added.empty:
            df_added = convert_dates_to_string(df_added, date_cols)
        if not df_changed.empty:
            df_changed = convert_dates_to_string(df_changed, date_cols)
        if not df_manual.empty:
            df_manual = convert_dates_to_string(df_manual, ['birthDate'])

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
    return

def write_processed_data_to_excel(excel_file, processed_data):
    """Writes processed data to Excel file"""
    # Create a new dictionary to hold mice that will be written to Excel. Mice in 'Death Row' will be placed into Memorial sheet.
    mice_to_write = {}
    parental_mice = set()
    parental_mice_live =  set()
    living_mice = set()
    
    for mouse_id, mouse_info in processed_data.items():
        if mouse_info.get('nuCA') == 'Death Row':
            print(f"Death Row mouse {mouse_id} transfer to Memorial")
            mouse_info['nuCA'] = 'Memorial'
            mouse_info['sheet'] = 'Memorial'
        if mouse_info.get('sheet') == 'BACKUP':
            mouse_info['breedDate'] = '-'
            mouse_info['breedDays'] = '-'
        elif mouse_info.get('sheet') != 'BACKUP':
            breed_date = mouse_info.get('breedDate')
            # Try to parse as datetime if it's a string
            if isinstance(breed_date, str):
                breed_date = pd.to_datetime(breed_date, errors='coerce', yearfirst=True, format='%Y-%m-%d')
            # Only update if we couldn't parse a valid date
            if pd.isna(breed_date):
                mouse_info['breedDate'] = date.today()
                mouse_info['breedDays'] = 0
        current_parental_mice = mouse_info['parentF'] + mouse_info['parentM'] 
        parental_mice.add(current_parental_mice)
        if mouse_info['sheet'] != 'Memorial':
            parental_mice_live.add(current_parental_mice)
            living_mice.add(mouse_info['ID'])

    # Perform cleanup on memorial
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

    # Sort mice by cage number
    sorted_mice = dict(sorted(mice_to_write.items(),key=lambda x: x[1].get('cage')))
    df_sorted = pd.DataFrame.from_dict(sorted_mice, orient='index')

    # Format the dates into strings so they won't get ruined by Excel
    date_cols = ['birthDate', 'breedDate']
    df_format = convert_dates_to_string(df_sorted, date_cols)

    # Remove the temporary columns
    cols_to_keep = ['ID', 'cage', 'sex', 'toe', 'genotype', 'birthDate', 'breedDate', 'parentF', 'parentM']
    df_final = df_format.loc[:, cols_to_keep]

    try:
        with pd.ExcelWriter(excel_file, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, sheet_name='MDb', index=False)
            writer.sheets['MDb'].autofit()
            return True

    except Exception as e:
        print(f"An error occurred during Excel writing: {e}\n{traceback.format_exc()}")
        return False

#############################################################################################################################

def process_genotypeID(genotype: str) -> str:
    """Convert genotype to numeric code"""
    genotype_map = {
        'hom-PP2A': '1',
        'PP2A(w/-)': '2',
        'PP2A(f/w)': '3',
        'NEX-CRE-PP2A(f/w)': '4',
        'CMV-CRE': '5',
        'NEX-CRE': '6',
        'CMV-CRE-PP2A(f/w)': '7'
    }
    return genotype_map.get(str(genotype), str(random.randint(8,9)))

def process_birthDateID(bdate: datetime) -> str:
    """Convert birthdate to YYMMDD format"""
    try:
        if pd.notna(bdate) and not isinstance(bdate,datetime):
            bdate = pd.to_datetime(bdate, errors='coerce', yearfirst=True, format='%Y-%m-%d')
        return bdate.strftime("%y%m%d") if pd.notna(bdate) else '000000'
    except Exception as e:
        print(f"Error processing birth date: {e}\n{traceback.format_exc()}")
        return '000000'

def process_toeID(toe: str) -> str:
    """Extract toe number or generate random if invalid"""
    toe_str = str(toe)
    if 'toe' not in toe_str:
        return str(random.randint(90, 99))
    
    toe_num = toe_str.split('toe')[1].split('a')[0]
    if len(toe_num) == 1:
        return f'0{toe_num}'
    elif len(toe_num) == 2:
        return toe_num
    else:
        return str(random.randint(91, 99))

def process_sexID(sex: str) -> str:
    """Generate sex ID (odd for male, even for female)"""
    return str(random.choice([1, 3, 5, 7, 9])) if sex == '♂' else str(random.choice([0, 2, 4, 6, 8]))

def process_cageID(cage: str) -> str:
    """Process cage number with consistent formatting.
    Rules:
    1. If no -A- or -B- designation, return random valid 6-digit number
    2. If -A- or -B- appears AND prefix is 2 or 8:
       - For -A-: Insert random 1-5
       - For -B-: Insert random 6-9
    3. Otherwise return random valid 6-digit number
    """
    cage_str = str(cage)

    if '-A-' in cage_str:
        parts = cage_str.replace('-', '').split('A')
        prefix = parts[0]
        if prefix in ('2','8'):
            suffix = parts[1] if len(parts) > 1 else ''
            suffix_purged = purge_leading_zeros(suffix.zfill(4),4)
            return f"{prefix}{random.randint(1, 5)}{suffix_purged}"

    elif '-B-' in cage_str:
        parts = cage_str.replace('-', '').split('B')
        prefix = parts[0]
        if prefix in ('2','8'):
            suffix = parts[1] if len(parts) > 1 else ''
            suffix_purged = purge_leading_zeros(suffix.zfill(4),4)
            return f"{prefix}{random.randint(6, 9)}{suffix_purged}"
        
    return str(roll_with_rickroll())

def roll_with_rickroll() -> int:
    while True:
        num = random.randint(100000, 999999)
        # Check if number is in forbidden ranges
        if (200000 <= num <= 299999) or (800000 <= num <= 899999):
            continue  # Re-roll
        else:
            return f"{num:06d}"  # Valid number
        
def purge_leading_zeros(s:str, digits:int):
    # Truncate if longer than required
    if len(s) > digits:
        s = s[-digits:] 
    else:
        # Pad with zeros if shorter
        s = s.zfill(digits)
    result = []
    zero_run = True  # Track if we're still in leading zeros
    for c in s:
        if c == '0' and zero_run:
            result.append(str(random.randint(1, 9)))
        else:
            result.append(c)
            zero_run = False
    return ''.join(result)[:digits].ljust(digits, '0')