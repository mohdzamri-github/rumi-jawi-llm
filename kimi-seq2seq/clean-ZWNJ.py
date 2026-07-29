import csv

# Define file names
input_file = 'rumi-jawi-unicode.csv'
output_file = 'rumi-jawi-clean.csv'

# Unicode hex codes for ZWNJ and ZWJ
ZWNJ = '\u200c'
ZWJ = '\u200d'

print(f"Starting cleanup process on '{input_file}'...")

try:
    # Open input with utf-8-sig to handle Excel BOM smoothly
    with open(input_file, mode='r', encoding='utf-8-sig', newline='') as infile:
        reader = csv.reader(infile)

        cleaned_rows = []
        removal_count = 0

        for row in reader:
            cleaned_row = []
            for cell in row:
                # Count occurrences for tracking
                zwnj_count = cell.count(ZWNJ)
                zwj_count = cell.count(ZWJ)
                removal_count += (zwnj_count + zwj_count)

                # Strip out the hidden characters
                cleaned_cell = cell.replace(ZWNJ, '').replace(ZWJ, '')
                cleaned_row.append(cleaned_cell)

            # FIXED: Just append directly without assigning back to the list
            cleaned_rows.append(cleaned_row)

    # Write the cleaned data to the new file
    with open(output_file, mode='w', encoding='utf-8', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerows(cleaned_rows)

    print("Cleanup successful!")
    print(f"-> Created clean file: '{output_file}'")
    print(f"-> Total ZWNJ/ZWJ characters stripped: {removal_count}")

except FileNotFoundError:
    print(f"Error: The file '{input_file}' was not found in this directory.")
except Exception as e:
    print(f"An error occurred: {e}")
