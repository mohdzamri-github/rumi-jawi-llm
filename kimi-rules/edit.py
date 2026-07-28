import csv

# Define the invisible characters to remove
# \u200c = ZWNJ, \u200d = ZWJ, \u200b = Zero-width space, \ufeff = BOM
TARGETS = ["\u200c", "\u200d", "\u200b", "\ufeff"]


def clean_text(text):
    if not isinstance(text, str):
        return text
    for char in TARGETS:
        text = text.replace(char, "")
    return text


# Open original file and create a cleaned version
with open("rumi-jawi-unicode.csv", "r", encoding="utf-8") as infile, open(
    "cleaned_output.csv", "w", encoding="utf-8", newline=""
) as outfile:

    reader = csv.reader(infile)
    writer = csv.writer(outfile)

    for row in reader:
        # Clean every cell in the row
        #print("clean")
        cleaned_row = [clean_text(cell) for cell in row]
        writer.writerow(cleaned_row)

print("Cleanup complete! Check cleaned_output.csv")
