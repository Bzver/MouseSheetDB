
from datetime import date, datetime
import pandas as pd
import random
import traceback

def issue_ID(df_data):
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
    return df_data

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

def date_calculator(df_data):
    today_for_calc = date.today()
    # Load and process birthDate
    df_data['birthDate'] = pd.to_datetime(df_data['birthDate'], errors='coerce', yearfirst=True, format='%Y-%m-%d')

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
        
##########################################################################################################################

def add_optional_cols(df_data):
    # Add optional cols if not already there
    optional_columns = ['age','breedDays','parentF','parentM']
    for col in optional_columns:
        if col not in df_data:
            df_data[col] = '-'
    # Add nuCA for temporary cage storage solution, nuCA == new cage / nuka-ColA
    df_data['nuCA'] = df_data.loc[:, 'cage']
    return df_data