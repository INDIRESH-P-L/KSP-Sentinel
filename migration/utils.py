import os
import json
import logging
import numpy as np
import pandas as pd
from config import STATE_FILE

# Set up logging
logger = logging.getLogger("migration")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.FileHandler(os.path.join(os.path.dirname(__file__), "migration.log"))
fh.setFormatter(formatter)
logger.addHandler(fh)

class StateManager:
    def __init__(self):
        self.state_file = STATE_FILE
        self.state = self._load_state()

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load state file: {e}")
        return {}

    def _save_state(self):
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state file: {e}")

    def mark_completed(self, filename: str):
        self.state[filename] = "completed"
        self._save_state()

    def is_completed(self, filename: str) -> bool:
        return self.state.get(filename) == "completed"

def clean_data(df: pd.DataFrame) -> list[dict]:
    """
    Cleans a pandas DataFrame chunk and converts it to a list of dicts suitable
    for Zoho Catalyst Data Store bulk insert.
    """
    # Convert empty strings to NaN, strip whitespaces from string columns
    df_obj = df.select_dtypes(['object'])
    df[df_obj.columns] = df_obj.apply(lambda x: x.str.strip())
    
    # Replace all NaN, NaT, None with proper None for JSON serialization
    df = df.replace({pd.NA: None, pd.NaT: None, np.nan: None, "": None})
    
    # For dates, if they are parsed as datetime, convert to ISO format string
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')

    # Convert numeric and boolean types explicitly if needed (Pandas mostly handles this,
    # but we ensure no numpy types leak into the JSON payload)
    records = df.to_dict(orient="records")
    
    # Additional pass to clean out NaNs that may have slipped through as float('nan')
    cleaned_records = []
    for record in records:
        cleaned_record = {}
        for k, v in record.items():
            if pd.isna(v):
                cleaned_record[k] = None
            else:
                cleaned_record[k] = v
        cleaned_records.append(cleaned_record)
        
    return cleaned_records
