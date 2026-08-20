import csv
import re

# Mapping based on database schema and user input
# You may need to adjust the keys on the left to exactly match your CSV header row
COLUMN_MAPPING = {
    'NAME OF ASSET': 'name',
    'UNIQUE ASSET NUMBER': 'asset_number',
    'DESCRIPTION': 'model', # Mapping description to model as requested/assumed
    'SERIAL NUMBER': 'serial_number',
    'ASSET CLASS': 'category',
    'Location of Asset': 'department_id',
    'Cost': 'purchase_cost'
}

# Department mapping (Name -> ID)
# Ensure these match the exact strings from the database department list
DEPT_MAP = {
    "St Mary's 1": 1, "St Mary's 2": 2, "St Luke's 1": 3, 'Staff Clinic': 4, 'St Lukes 2': 5,
    'Mzilikazi 1': 6, 'Mzilikazi 2': 7, 'Nandi ': 8, 'Khumalo ': 9, 'Juvenile': 10,
    'Mambo ': 11, 'Out- Patient ': 12, 'St Annes ': 13, 'St Francis Home ': 14, 'Annexe': 15,
    'CSSD': 16, 'ECG Department': 17, 'EEG Department': 18, 'Radiology Services Department': 19, 'Dental Services Department': 20,
    'Matrons Block': 21, 'DMHE ': 22, 'Physio Therapy Department': 23, 'Dawson': 24
}

def clean_cost(value):
    if not value: return None
    # Remove currency symbol and commas
    return re.sub(r'[$,]', '', value)

def map_department(value):
    if not value: return None
    # Case-insensitive match, stripping whitespace
    val_clean = value.strip().lower()
    for name, dept_id in DEPT_MAP.items():
        if name.strip().lower() == val_clean:
            return dept_id
    return None

def transform_csv(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        
        # Prepare output headers
        fieldnames = ['asset_number', 'name', 'model', 'manufacturer', 'serial_number', 'category', 
                      'department_id', 'location', 'country_of_origin', 'donor_name', 'state', 'condition', 
                      'purchase_date', 'purchase_cost', 'warranty_expiry', 'last_maintenance', 'next_maintenance', 
                      'notes', 'received_by_id', 'quantity']
        
        with open(output_file, 'w', encoding='utf-8', newline='') as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in reader:
                new_row = {field: '' for field in fieldnames}
                
                # Apply mapping
                new_row['name'] = row.get('NAME OF ASSET', '')
                new_row['asset_number'] = row.get('UNIQUE ASSET NUMBER', '')
                new_row['model'] = row.get('DESCRIPTION', '')
                new_row['serial_number'] = row.get('SERIAL NUMBER', '')
                new_row['category'] = row.get('ASSET CLASS', '')
                new_row['department_id'] = map_department(row.get('Location of Asset ', ''))
                new_row['purchase_cost'] = clean_cost(row.get('Cost', ''))
                
                # State defaults to 'Active'
                new_row['state'] = 'Active'
                new_row['quantity'] = 1
                
                writer.writerow(new_row)

if __name__ == '__main__':
    transform_csv('medical-equipment.csv', 'cleaned_import.csv')
    print("Transformation complete. Check 'cleaned_import.csv'")
