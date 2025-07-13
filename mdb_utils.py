import random
import pandas as pd
from datetime import date, datetime

import matplotlib.pyplot as plt

import traceback
import logging

def preprocess_df(df_data):
    df = df_data.copy()
    df = df.dropna(how="all")
    df = add_optional_cols(df)
    df = df_categorize(df)
    df = df_issue_ID(df)
    df = df_date_to_days(df)
    return df

def df_categorize(df_data):
    df_data["category"] = df_data["cage"].apply(assign_category)
    return df_data

def assign_category(cage:str) -> str: 
    """Categorize mouse cages based on naming conventions.
    Args:
        cage: Cage identifier (string or convertible to string)
    Returns:
        One of: "Memorial", "Death Row", "Waiting Room", 
                "CMV + PP2A", "NEX + PP2A", or "BACKUP"
    """
    cage_str = str(cage).strip()

    if cage_str in {"Memorial", "Death Row", "Waiting Room"}:
        return cage_str
    if cage_str.startswith("8-A-"):
        return "CMV + PP2A"
    if cage_str.startswith("2-A-"):
        return "NEX + PP2A"
    return "BACKUP"

def add_optional_cols(df):
    optional_columns = ["age","breedDays","parentF","parentM","category"]
    for col in optional_columns:
        if col not in df:
            df[col] = None
    df["nuCA"] = df.loc[:, "cage"] # Add nuCA for temporary cage storage solution, nuCA == new cage | nuka-ColA
    return df

def cleanup_optional_cols(df):
    cols_to_keep = ["ID", "cage", "sex", "toe", "genotype", "birthDate","age", "breedDate", "breedDays", "parentF", "parentM"]
    df_cleaned = df.loc[:, cols_to_keep]
    return df_cleaned

##########################################################################################################################

def df_issue_ID(df_data):
    """Generate IDs for rows with missing/blank IDs, ensuring uniqueness."""
    # Identify rows needing IDs
    ID_mask = df_data["ID"].isna() | (df_data["ID"] == "")
    
    if not ID_mask.any():
        return df_data

    # Generate component IDs
    components = {
        "genoID": ("genotype", process_genotypeID),
        "dobID": ("birthDate", process_birthDateID),
        "toeID": ("toe", process_toeID),
        "sexID": ("sex", process_sexID),
        "cageID": ("nuCA", process_cageID)
    }
    
    for col, (src_col, processor) in components.items():
        df_data.loc[ID_mask, col] = df_data.loc[ID_mask, src_col].apply(processor)

    # Compose full IDs
    df_data.loc[ID_mask, "ID"] = df_data.loc[ID_mask].apply(
        lambda row: f"{row["genoID"]}{row["dobID"]}{row["toeID"]}{row["sexID"]}{row["cageID"]}",
        axis=1
    )

    # Handle duplicates and conflicts
    new_ids = df_data.loc[ID_mask, "ID"]
    existing_ids = df_data.loc[~ID_mask, "ID"]
    
    # Combined check for duplicates within new IDs and conflicts with existing
    needs_regeneration = new_ids.duplicated(keep=False) | new_ids.isin(existing_ids)
    
    if needs_regeneration.any():
        # Regenerate full random IDs for problematic cases
        df_data.loc[needs_regeneration[needs_regeneration].index, "ID"] = \
            df_data.loc[needs_regeneration[needs_regeneration].index].apply(
                lambda _: generate_random_id(), axis=1
            )
        
    # Cleanup temporary columns
    df_data.drop(list(components.keys()), axis=1, inplace=True, errors="ignore")
    
    return df_data

def process_genotypeID(genotype: str) -> str:
    """Convert genotype to numeric code"""
    genotype_map = {
        "hom-PP2A": "1",
        "PP2A(w/-)": "2",
        "PP2A(f/w)": "3",
        "NEX-CRE-PP2A(f/w)": "4",
        "CMV-CRE": "5",
        "NEX-CRE": "6",
        "CMV-CRE-PP2A(f/w)": "7"
    }
    return genotype_map.get(str(genotype), str(random.randint(8,9)))

def process_birthDateID(bdate: datetime) -> str:
    """Convert birthdate to YYMMDD format"""
    try:
        if pd.notna(bdate) and not isinstance(bdate,datetime):
            bdate = pd.to_datetime(bdate, errors="coerce", yearfirst=True, format="%y-%m-%d")
        return bdate.strftime("%y%m%d") if pd.notna(bdate) else "000000"
    except Exception as e:
        logging.error(f"Error processing birth date: {e}\n{traceback.format_exc()}")
        return "000000"

def process_toeID(toe: str) -> str:
    """Extract toe number or generate random if invalid"""
    toe_str = str(toe)
    if "toe" not in toe_str:
        return str(random.randint(90, 99))
    
    toe_num = toe_str.split("toe")[1].split("a")[0]
    if len(toe_num) == 1:
        return f"0{toe_num}"
    elif len(toe_num) == 2:
        return toe_num
    else:
        return str(random.randint(91, 99))

def process_sexID(sex: str) -> str:
    """Generate sex ID (odd for male, even for female)"""
    return str(random.choice([1, 3, 5, 7, 9])) if sex == "♂" else str(random.choice([0, 2, 4, 6, 8]))

def process_cageID(cage: str) -> str:
    """Process cage number with consistent formatting.
    Rules:
    1. If no -A- or -B- designation, return random valid 6-digit number
    2. If -A- or -B- appears AND prefix is 2 or 8:
       - For -A-: Insert random 1-5
       - For -B-: Insert random 6-9
    3. Otherwise return random valid 6-digit number
    """
    cage_str = str(cage).strip()

    if "-A-" in cage_str:
        parts = cage_str.replace("-", "").split("A")
        prefix = parts[0]
        if prefix in ("2","8"):
            suffix = parts[1] if len(parts) > 1 else ""
            suffix_purged = purge_leading_zeros(suffix.zfill(4),4)
            return f"{prefix}{random.randint(1, 5)}{suffix_purged}"

    elif "-B-" in cage_str:
        parts = cage_str.replace("-", "").split("B")
        prefix = parts[0]
        if prefix in ("2","8"):
            suffix = parts[1] if len(parts) > 1 else ""
            suffix_purged = purge_leading_zeros(suffix.zfill(4),4)
            return f"{prefix}{random.randint(6, 9)}{suffix_purged}"
        
    return str(roll_with_rickroll())

##########################################################################################################################

def df_date_col_formatter(df, date_col):
    """Format date columns consistently to 'yy-mm-dd' strings"""
    for col in date_col:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: convert_date_to_string(x) if pd.notna(x) else "-")
    return df

def df_date_to_days(df_data):
    """Convert date columns to days calculations"""
    df_data["birthDate"] = df_data["birthDate"].apply(convert_to_date)
    df_data["age"] = df_data["birthDate"].apply(lambda dob: date_to_days(dob))
    # Calculate last breed days for alive and non-BACKUP mice
    breeding_mask = ~df_data["category"].isin(["Memorial", "BACKUP"])
    df_data["breedDays"] = None 
    if breeding_mask.any():
        df_data.loc[breeding_mask, "breedDate"] = df_data.loc[breeding_mask, "breedDate"].apply(convert_to_date)
        df_data.loc[breeding_mask, "breedDays"] = df_data.loc[breeding_mask, "breedDate"].apply(
            lambda bd: date_to_days(bd))
    return df_data

def date_to_days(date_obj):
    """Calculates age in days from birthDate"""
    today_date = date.today()
    date_obj = convert_to_date(date_obj) # Better safe than sorry
    if date_obj is None or pd.isna(date_obj):
        return None
    if date_obj > today_date:
        logging.error(f"Cannot calculate age from future date: {date_obj}.")
        return None
    return (today_date - date_obj).days
        
def convert_date_to_string(date_obj):
    """Convert date to 'yy-mm-dd' string format"""
    if isinstance(date_obj, (datetime, pd.Timestamp)):  # Proper datetime objects
        return date_obj.strftime("%y-%m-%d")
    if isinstance(date_obj, date):
        return date_obj.strftime("%y-%m-%d")
    if pd.isna(date_obj): # NaN / NaT
        return ""
    try: # Try to parse if it's a string date
        date_obj = convert_to_date(date_obj)
        return date_obj.strftime("%y-%m-%d") if date_obj else ""
    except:
        return str(date_obj)
    
def convert_to_date(date_val):
    """Convert input to date object, returns None for invalid dates"""
    if pd.isna(date_val):
        return None
    try: # Convert to date object
        if isinstance(date_val, (pd.Timestamp, datetime)):
            return date_val.date()
        if isinstance(date_val, date):
            return date_val
        # Try multiple common formats to parse if string
        if isinstance(date_val, str):
            for fmt in ("%y-%m-%d", "%Y-%m-%d", "%m/%d/%Y", "%d-%b-%y"):
                try:
                    return datetime.strptime(date_val, fmt).date()
                except ValueError:
                    continue
        return None
    except Exception as e:
        logging.error(f"Unexpected error processing {date_val}: {str(e)}")
        return None

##########################################################################################################################

def mice_dot_color_picker(sex, age):
    if age is not None and age > 300:
        color = "grey"
    else:
        color = "lightblue" if sex == "♂" else "lightpink"
    return color

def genotype_abbreviation_color_picker(genotype_string):
    geno_text = ""
    geno_color = "black"
    valid_identifier = False

    target_components = {
        "CMV-CRE": "C",
        "NEX-CRE": "N",
        "wt": "wt",
        "hom-PP2A": ("P", "gold"),
        "PP2A(f/w)": ("P", "olivedrab"),
        "PP2A(w/-)": ("P", "chocolate"),
        "PP2A": "P", # PP2A fallback
        }

    for component, marker in target_components.items():
        if component in genotype_string:
            valid_identifier = True
            if component == "wt":  # wt overrides other markers
                geno_text = "wt"
                geno_color = "black"
                break
            elif isinstance(marker, tuple):  # Special PP2A cases with colors
                geno_text += marker[0]
                geno_color = marker[1]
            else:
                if component != "PP2A" and marker not in geno_text:  # Avoid duplicates
                    geno_text += marker
                if component == "PP2A" and not any(x in genotype_string for x in ["hom-","(f/w)","w/-"]): # Avoid duplicates for PP2A
                    geno_text += marker

    if geno_text == "wt":
        geno_color = "black"
    if not valid_identifier:
        geno_text = "?"
        geno_color = "red"
    elif not geno_text:
        geno_text = "?"
        geno_color = "red"

    return geno_text, geno_color

def cleanup():
    plt.close("all")

##########################################################################################################################

def generate_random_id():
        return "".join([str(random.randint(0, 9)) for _ in range(16)])

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
    zero_run = True  # Track if we"re still in leading zeros
    for c in s:
        if c == "0" and zero_run:
            result.append(str(random.randint(1, 9)))
        else:
            result.append(c)
            zero_run = False
    return "".join(result)[:digits].ljust(digits, "0")