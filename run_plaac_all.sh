#!/bin/bash

# Path to PLAAC jar
PLAAC_JAR=~/tools/plaac/cli/target/plaac.jar

# Input folder (where your FASTA files are)
INPUT_DIR=~/fasta_inputs

# Output folder (where results will be saved)
OUTPUT_DIR=~/plaac_results
mkdir -p "$OUTPUT_DIR"

# Loop through all .fasta or .fa files in INPUT_DIR
for fasta in "$INPUT_DIR"/*.fa "$INPUT_DIR"/*.fasta; do
    # Skip if no files are found
    [ -e "$fasta" ] || continue
    
    # Get filename without path
    fname=$(basename "$fasta")
    
    # Define output file
    out="$OUTPUT_DIR/${fname%.fa}_plaac.txt"
    out="${out%.fasta}_plaac.txt"
    
    echo "Running PLAAC on $fname..."
    java -jar "$PLAAC_JAR" -i "$fasta" > "$out"
done

echo "✅ Done! Results are in $OUTPUT_DIR"
