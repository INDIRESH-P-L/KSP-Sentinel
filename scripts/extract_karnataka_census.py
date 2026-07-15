import openpyxl
import csv
import os

excel_path = 'datasets/raw/census/2011-IndiaStateDistSbDistTwnWrd-0000.xlsx'
output_path = 'datasets/cleaned/karnataka_census_2011.csv'

print(f"Opening workbook: {excel_path}...")
wb = openpyxl.load_workbook(excel_path, read_only=True)
sheet = wb['Data']

print("Extracting Karnataka (State 29) rows...")
with open(output_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    
    # Read headers
    iterator = sheet.iter_rows(values_only=True)
    header_row = next(iterator, None)
    if header_row:
        writer.writerow(header_row)
    
    count = 0
    for row in iterator:
        if not row:
            continue
        state_val = str(row[0]).strip()
        # State 29 is Karnataka
        if state_val == '29' or state_val == '29.0':
            writer.writerow(row)
            count += 1

print(f"Extraction complete. Saved {count} rows to {output_path}.")
wb.close()
