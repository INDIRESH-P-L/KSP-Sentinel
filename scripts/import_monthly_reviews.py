import os
import csv
import re
from datetime import datetime
from backend.app.database.session import SessionLocal, engine
from backend.app.database.models import Base, MonthlyCrimeReview

# Ensure table exists
Base.metadata.create_all(bind=engine)

REVIEW_GLOB_DIR = os.path.join(os.path.dirname(__file__))
FILENAME_REGEX = re.compile(r'CRIME_REVIEW_FOR_THE_MONTH_OF_([A-Z]+)_(\d{4})\.csv', re.IGNORECASE)

MONTH_MAP = {
    'JANUARY':1,'FEBRUARY':2,'MARCH':3,'APRIL':4,'MAY':5,'JUNE':6,
    'JULY':7,'AUGUST':8,'SEPTEMBER':9,'OCTOBER':10,'NOVEMBER':11,'DECEMBER':12
}


def parse_int(val):
    try:
        return int(val)
    except Exception:
        return None


def import_reviews():
    files = [f for f in os.listdir(REVIEW_GLOB_DIR) if f.upper().startswith('CRIME_REVIEW_FOR_THE_MONTH_OF_') and f.lower().endswith('.csv')]
    session = SessionLocal()
    total_inserted = 0
    try:
        for fname in files:
            m = FILENAME_REGEX.match(fname)
            if not m:
                print(f"Skipping file with unexpected name: {fname}")
                continue
            month_name = m.group(1).upper()
            year = int(m.group(2))
            month = MONTH_MAP.get(month_name)
            if not month:
                print(f"Unknown month name in {fname}")
                continue

            path = os.path.join(REVIEW_GLOB_DIR, fname)
            with open(path, newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                headers = next(reader, None)
                # find indices for known columns
                # Common columns in these reports:
                # Sl.No., Heads of Crime, Major Heads, Minor Heads, During the current year upto the end of month under review, During the corresponding month of previous year, During the previous month, During the current month
                # Normalize header names
                hdrs = [h.strip() if h else h for h in headers]
                def idx(name_options):
                    for i,h in enumerate(hdrs):
                        for opt in name_options:
                            if h and opt.lower() in h.lower():
                                return i
                    return None

                i_sl = idx(['Sl.No','Sl. No','Sl.No.'])
                i_heads = idx(['Heads of Crime','Heads'])
                i_major = idx(['Major Heads','Major'])
                i_minor = idx(['Minor Heads','Minor'])
                i_upto = idx(['upto the end of month','During the current year upto'])
                i_prev_year = idx(['corresponding month of previous year','corresponding month'])
                i_prev_month = idx(['previous month'])
                i_curr_month = idx(['current month','During the current month'])

                for row in reader:
                    if not row or len(row) < 4:
                        continue
                    sl_no = parse_int(row[i_sl]) if i_sl is not None and row[i_sl].strip() else None
                    heads = row[i_heads].strip() if i_heads is not None and row[i_heads] else None
                    major = row[i_major].strip() if i_major is not None and row[i_major] else None
                    minor = row[i_minor].strip() if i_minor is not None and row[i_minor] else None
                    upto = parse_int(row[i_upto]) if i_upto is not None and row[i_upto].strip() else None
                    prev_year = parse_int(row[i_prev_year]) if i_prev_year is not None and row[i_prev_year].strip() else None
                    prev_month = parse_int(row[i_prev_month]) if i_prev_month is not None and row[i_prev_month].strip() else None
                    curr_month = parse_int(row[i_curr_month]) if i_curr_month is not None and row[i_curr_month].strip() else None

                    # Skip rows that are clearly subtotal or header repeats
                    if not heads and not major and not minor:
                        continue

                    # Remove existing rows with same source file & sl_no to avoid duplicates
                    if sl_no is not None:
                        session.query(MonthlyCrimeReview).filter(MonthlyCrimeReview.source_file==fname, MonthlyCrimeReview.sl_no==sl_no).delete()

                    record = MonthlyCrimeReview(
                        source_file=fname,
                        sl_no=sl_no,
                        month=month,
                        year=year,
                        heads_of_crime=heads,
                        major_head=major,
                        minor_head=minor,
                        upto_end_of_month=upto,
                        corresponding_month_prev_year=prev_year,
                        previous_month=prev_month,
                        current_month=curr_month
                    )
                    session.add(record)
                    total_inserted += 1

        session.commit()
        print(f"Imported {total_inserted} review rows from {len(files)} files.")
    except Exception as e:
        session.rollback()
        print('Error importing reviews:', e)
        raise
    finally:
        session.close()


if __name__ == '__main__':
    import_reviews()
