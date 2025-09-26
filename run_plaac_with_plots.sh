#!/bin/bash

# Path to PLAAC jar
PLAAC_JAR=~/tools/plaac/cli/target/plaac.jar

# Input folder (where your FASTA files are)
INPUT_DIR=~/fasta_inputs

# Output folder (text + plots)
OUTPUT_DIR=~/plaac_results
mkdir -p "$OUTPUT_DIR"

# Loop through all FASTA files
for fasta in "$INPUT_DIR"/*.fa "$INPUT_DIR"/*.fasta; do
    [ -e "$fasta" ] || continue
    
    # Get filename without path & extension
    fname=$(basename "$fasta")
    base="${fname%.fa}"
    base="${base%.fasta}"
    
    # Output text file
    out_txt="$OUTPUT_DIR/${base}_plaac.txt"
    
    echo "Running PLAAC on $fname..."
    java -jar "$PLAAC_JAR" -i "$fasta" > "$out_txt"
    
    # Generate PDF plot using Rscript (plaac_plot.r must exist in PLAAC folder)
    out_pdf="$OUTPUT_DIR/${base}_plaac.pdf"
    Rscript ~/tools/plaac/cli/plaac_plot.r "$out_txt" "$out_pdf"
    
    echo "✅ Finished $fname -> $out_txt + $out_pdf"
done

echo "🎉 All PLAAC runs complete! Results in $OUTPUT_DIR"
