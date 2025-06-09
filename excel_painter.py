from datetime import date, datetime
import pandas as pd

def data_preprocess(excel_file, sheet_name):
    """Preprocesses Excel data and returns processed DataFrames"""
    try:
        excel_file_obj = pd.ExcelFile(excel_file)
        mDb_df = excel_file_obj.parse(sheet_name)
        excel_file_obj.close()

        df_processed = process_sheet_data(mDb_df)
        processed_data = df_processed.to_dict('index')
        
        return processed_data

    except Exception as e:
        print(f"An error occurred during Excel preprocessing: {e}")
        return None
    
def process_sheet_data(df_sheet):
    """Processes sheet data: ffill, calculate ages, etc."""
    today_for_calc = date.today()
    df_data = df_sheet.copy()
    df_data = df_data.dropna(how='all')
    
    # Add nuCA for temporary cage storage solution, nuCA == new cage / nuka-ColA
    df_data['nuCA'] = df_data.loc[:, 'cage']

    # Generate an unique identifier for mice
    df_data['sexLetter'] = df_data['sex'].apply(lambda x: 'M' if x == '♂' else 'F')
    df_data['ID'] = df_data.apply(
        lambda row: f"{row['cage']}-{row['toe']}-{row['sexLetter']}".replace('nan', 'UNKNOWN'), 
        axis='columns'
    )
    df_data = df_data.drop('sexLetter', axis='columns')

    # Calculate mouse ages
    df_data['birthDate'] = pd.to_datetime(df_data['birthDate'], errors='coerce', yearfirst=True, format='%Y-%m-%d')
    ages_column_data = df_data['birthDate'].apply(lambda dob: get_age_days(dob, today_for_calc))
    df_data['age'] = ages_column_data

    # Apply categorical ident
    cond_nexPP2A = df_data['cage'].astype(str).str.startswith('2-A-')
    cond_cmvPP2A = df_data['cage'].astype(str).str.startswith('8-A-')

    ind_nexPP2A = df_data.index[cond_nexPP2A].tolist()
    ind_cmvPP2A = df_data.index[cond_cmvPP2A].tolist()
    ind_BACKUP = df_data.index[~cond_nexPP2A & ~cond_cmvPP2A].tolist()

    df_nexPP2A = df_data.loc[ind_nexPP2A]
    df_cmvPP2A = df_data.loc[ind_cmvPP2A]
    df_BACKUP = df_data.loc[ind_BACKUP]

    df_nexPP2A['sheet'] = 'NEX + PP2A'
    df_cmvPP2A['sheet'] = 'CMV + PP2A'
    df_BACKUP['sheet'] = 'BACKUP'

    # Calculate days since last breed for non BACKUP entries only
    df_notBACKUP = pd.concat([df_nexPP2A,df_cmvPP2A],ignore_index=True)
    df_notBACKUP['breedDate'] = pd.to_datetime(df_notBACKUP['breedDate'], errors='coerce', yearfirst=True, format='%Y-%m-%d')
    days_since_breed_data = df_notBACKUP['breedDate'].apply(lambda lb: get_days_since_last_breed(lb, today_for_calc))
    df_notBACKUP['breedDays'] = days_since_breed_data
    df_data = pd.concat([df_BACKUP,df_notBACKUP],ignore_index=True)

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

##########################################################################################################################

def mice_changelog(df, output_path):
    """Logs mice with cage/nuCA inconsistencies to a new Excel file"""
    try:
        # Validate input
        if not isinstance(df, pd.DataFrame):
            raise ValueError("Input must be a pandas DataFrame")
        
        df['old_cage'] = df.loc[:,'cage']
        df['new_cage'] = df.loc[:,'nuCA']
        required_cols = ['genotype','sex','toe', 'old_cage', 'new_cage']

        # Filter inconsistent mice (cage ≠ nuCA)
        mask = df['old_cage'] != df['new_cage']
        inconsistent = df.loc[mask, required_cols].copy() 

        if inconsistent.empty:
            print("No changes found.")
            return None

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%m%d_%H%M%S")
        log_file = f"{output_path}/mice_changelog_{timestamp}.xlsx"

        # Save to Excel (without index)
        with pd.ExcelWriter(log_file) as writer:
            inconsistent.to_excel(writer, sheet_name='MCl', index=False)
        
        print(f"Log saved to: {log_file}")
        return log_file
    except Exception as e:
        print(f"Error logging inconsistent mice: {e}")
    return None

def write_processed_data_to_excel(excel_file, processed_data):
    """Writes processed data to Excel file"""
    # Create a new dictionary to hold mice that will be written to Excel. Mice in 'Death Row' will be excluded and executed.
    mice_to_write = {}
    
    for mouse_id, mouse_info in processed_data.items():
        if mouse_info.get('nuCA') == 'Death Row':
            print(f"Skipping Death Row mouse {mouse_id}")
            continue
        current_mouse_info = mouse_info.copy()
        if current_mouse_info.get('sheet') == 'BACKUP':
            current_mouse_info['breedDate'] = '-'
            current_mouse_info['breedDays'] = '-'
        elif current_mouse_info.get('sheet') != 'BACKUP':
            breed_date = current_mouse_info.get('breedDate')
            # Try to parse as datetime if it's a string
            if isinstance(breed_date, str):
                breed_date = pd.to_datetime(breed_date, errors='coerce', yearfirst=True, format='%Y-%m-%d')
            # Only update if we couldn't parse a valid date
            if pd.isna(breed_date):
                current_mouse_info['breedDate'] = date.today()
                current_mouse_info['breedDays'] = 0

        current_mouse_info['cage'] = current_mouse_info['nuCA']
        mice_to_write[mouse_id] = current_mouse_info

    # Sort mice by cage number
    sorted_mice = dict(sorted(mice_to_write.items(),key=lambda x: x[1].get('cage')))

    try:
        with pd.ExcelWriter(excel_file, engine='xlsxwriter') as writer:
            write_formatted_excel(writer, sorted_mice)
            return True

    except Exception as e:
        print(f"An error occurred during Excel writing: {e}")
        return False

def write_formatted_excel(writer, data_dict):
    """Writes formatted data to Excel worksheet from dictionary"""
    workbook = writer.book
    worksheet = workbook.add_worksheet('MDb')
    writer.sheets['MDb'] = worksheet

    # Format caching
    formats_cache = {}

    def get_cached_format(workbook, font_color, bg_color, num_format='general'):
        key = (font_color, bg_color, num_format)
        if key not in formats_cache:
            fmt_props = {}
            if font_color:
                fmt_props['font_color'] = font_color
            if bg_color:
                fmt_props['bg_color'] = bg_color
            if num_format != 'general':
                fmt_props['num_format'] = num_format
            formats_cache[key] = workbook.add_format(fmt_props)
        return formats_cache[key]

    # Get headers from first dict value, excluding temporary columns
    if not data_dict:
        return
    first_row = next(iter(data_dict.values()))
    excluded_columns = {'nuCA', 'sheet', 'ID'}
    headers = [k for k in first_row.keys() if k not in excluded_columns]

    # Write headers
    header_format = workbook.add_format({'bold': True})
    for col_idx, col_name in enumerate(headers):
        worksheet.write(0, col_idx, col_name, header_format)

    # Write data rows
    for r_idx, mouse_data in enumerate(data_dict.values()):
        row_styles = StyleRule.get_data_row_style(mouse_data)
        bg_color = row_styles['bg_color']
        font_color = row_styles['font_color']

        for c_idx, col_name in enumerate(headers):
            cell_value = mouse_data.get(col_name)
            current_num_format = 'general'

            if col_name in ['birthDate', 'breedDate']:
                if pd.notna(cell_value) and isinstance(cell_value, (pd.Timestamp, datetime, date)):
                    current_num_format = 'yy-mm-dd'

            cell_format = get_cached_format(workbook, font_color, bg_color, current_num_format)

            if current_num_format == 'yy-mm-dd' and pd.notna(cell_value):
                worksheet.write_datetime(r_idx + 1, c_idx, cell_value, cell_format)
            else:
                if pd.isna(cell_value):
                    worksheet.write_string(r_idx + 1, c_idx, '', cell_format)
                elif isinstance(cell_value, (int, float)):
                    worksheet.write_number(r_idx + 1, c_idx, cell_value, cell_format)
                elif isinstance(cell_value, bool):
                    worksheet.write_boolean(r_idx + 1, c_idx, cell_value, cell_format)
                else:
                    worksheet.write_string(r_idx + 1, c_idx, str(cell_value), cell_format)
                
class StyleRule:
    MALE_BG_COLOR = '#ADD8E6'   # Light Blue (hex code for lightblue)
    FEMALE_BG_COLOR = '#FFB6C1' # Light Pink (hex code for lightpink)
    NON_PERFORMING_FONT_COLOR = '#FF0000' # Red (hex code for red)
    SENILE_FONT_COLOR = '#808080' # Gray (hex code for gray)

    @classmethod
    def get_data_row_style(cls, row):
        """Returns style properties for data row based on row data"""
        styles = {'font_color': None, 'bg_color': None}
        latest_breed_val = row.get('breedDays')

        # Font color logic
        if not isinstance(latest_breed_val, str) and pd.notna(latest_breed_val):
            try:
                if latest_breed_val > 90:
                    styles['font_color'] = cls.NON_PERFORMING_FONT_COLOR
            except Exception:
                pass

        if not styles['font_color']:
            age = row.get('age')
            if pd.notna(age):
                if age > 300:
                    styles['font_color'] = cls.SENILE_FONT_COLOR

        # Background color logic
        sex_val = row.get('sex')
        if isinstance(sex_val, str):
            sex_clean = sex_val.strip()
            if sex_clean == '♂':
                styles['bg_color'] = cls.MALE_BG_COLOR
            elif sex_clean == '♀':
                styles['bg_color'] = cls.FEMALE_BG_COLOR

        return styles