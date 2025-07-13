from datetime import date, datetime
import pandas as pd
import random
import traceback

def issue_ID(df_data):
    """Generate IDs for rows with missing/blank IDs, ensuring uniqueness."""
    # Identify rows needing IDs
    ID_mask = df_data['ID'].isna() | (df_data['ID'] == '')
    
    if not ID_mask.any():
        return df_data

    # Generate component IDs
    components = {
        'genoID': ('genotype', process_genotypeID),
        'dobID': ('birthDate', process_birthDateID),
        'toeID': ('toe', process_toeID),
        'sexID': ('sex', process_sexID),
        'cageID': ('nuCA', process_cageID)
    }
    
    for col, (src_col, processor) in components.items():
        df_data.loc[ID_mask, col] = df_data.loc[ID_mask, src_col].apply(processor)

    # Compose full IDs
    df_data.loc[ID_mask, 'ID'] = df_data.loc[ID_mask].apply(
        lambda row: f"{row['genoID']}{row['dobID']}{row['toeID']}{row['sexID']}{row['cageID']}",
        axis=1
    )

    # Handle duplicates and conflicts
    new_ids = df_data.loc[ID_mask, 'ID']
    existing_ids = df_data.loc[~ID_mask, 'ID']
    
    # Combined check for duplicates within new IDs and conflicts with existing
    needs_regeneration = new_ids.duplicated(keep=False) | new_ids.isin(existing_ids)
    
    if needs_regeneration.any():
        # Regenerate full random IDs for problematic cases
        df_data.loc[needs_regeneration[needs_regeneration].index, 'ID'] = \
            df_data.loc[needs_regeneration[needs_regeneration].index].apply(
                lambda _: generate_random_id(), axis=1
            )
        
    # Cleanup temporary columns
    df_data.drop(list(components.keys()), axis=1, inplace=True, errors='ignore')
    
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

def generate_random_id():
        return ''.join([str(random.randint(0, 9)) for _ in range(16)])

def roll_with_rickroll():
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

def df_date_col_formatter(df, date_columns):
    for col in date_columns:
        if col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                # Handle datetime columns efficiently
                df[col] = df[col].dt.strftime('%y-%m-%d')
            else:
                # Handle mixed-type columns
                df[col] = df[col].apply(convert_dates_to_string)
    return df

def convert_dates_to_string(date):
    if isinstance(date, (datetime.datetime, pd.Timestamp)):  # Proper datetime objects
        return date.strftime('%y-%m-%d')
    elif pd.isna(date): # NaN / NaT
        return ''
    else: # Already a string date
        return str(date)

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

def calculate_genotype_counts(mice_dict, category):
    genotypes = []
    male_counts = []
    female_counts = []
    senile_counts = []
        
    for mouse_info in mice_dict.values():
        # Only consider mice in the current ( category ) for genotype counts
        if mouse_info['sheet'] == category and mouse_info['genotype'] not in genotypes:
            genotypes.append(mouse_info['genotype'])
        
    for genotype in genotypes:
        males = sum(1 for mouse_info in mice_dict.values()
                        if mouse_info['genotype'] == genotype
                        and mouse_info['sheet'] == category
                        and mouse_info['sex'] == '♂'
                        and mouse_info['age'] <= 300)
        females = sum(1 for mouse_info in mice_dict.values()
                        if mouse_info['genotype'] == genotype
                        and mouse_info['sheet'] == category
                        and mouse_info['sex'] == '♀'
                        and mouse_info['age'] <= 300)
        seniles = sum(1 for mouse_info in mice_dict.values()
                        if mouse_info['genotype'] == genotype
                        and mouse_info['sheet'] == category
                        and mouse_info['age'] > 300)
        male_counts.append(males)
        female_counts.append(females)
        senile_counts.append(seniles)
        
    return genotypes, male_counts, female_counts, senile_counts

def mice_dot_color_picker(sex, age):
    if age is not None and age > 300:
        color = 'grey'
    else:
        color = 'lightblue' if sex == '♂' else 'lightpink'
    return color

def genotype_abbreviation_color_picker(genotype_string):
    geno_text = ""
    geno_color = 'black'
    valid_identifier = False

    target_components = {
        'CMV-CRE': 'C',
        'NEX-CRE': 'N',
        'wt': 'wt',
        'hom-PP2A': ('P', 'gold'),
        'PP2A(f/w)': ('P', 'olivedrab'),
        'PP2A(w/-)': ('P', 'chocolate'),
        'PP2A': 'P', # PP2A fallback
        }

    for component, marker in target_components.items():
        if component in genotype_string:
            valid_identifier = True
            if component == 'wt':  # wt overrides other markers
                geno_text = 'wt'
                geno_color = 'black'
                break
            elif isinstance(marker, tuple):  # Special PP2A cases with colors
                geno_text += marker[0]
                geno_color = marker[1]
            else:
                if component != 'PP2A' and marker not in geno_text:  # Avoid duplicates
                    geno_text += marker
                if component == 'PP2A' and not any(x in genotype_string for x in ['hom-','(f/w)','w/-']): # Avoid duplicates for PP2A
                    geno_text += marker

    if geno_text == 'wt':
        geno_color = 'black'
    if not valid_identifier:
        geno_text = "?"
        geno_color = 'red'
    elif not geno_text:
        geno_text = "?"
        geno_color = 'red'

    return geno_text, geno_color

def mice_count_for_monitor(mice_dict, category, mice_displayed):
    for mouse_info in mice_dict.values():
        cage_key = mouse_info['nuCA']
        ID = mouse_info['ID']
        if mouse_info['sheet'] == category and mouse_info['nuCA'] not in ['Waiting Room', 'Death Row']:
            if cage_key not in mice_displayed.regular:
                mice_displayed.regular[cage_key] = []
            mice_displayed.regular[cage_key].append(mouse_info)
        elif mouse_info['nuCA'] == 'Waiting Room':
            mice_displayed.waiting[ID] = mouse_info 
        elif mouse_info['nuCA'] == 'Death Row':
            mice_displayed.death[ID] = mouse_info