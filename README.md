PLAAC: Prion-Like Amino Acid Composition Analysis Pipeline
Overview

PLAAC (Prion-Like Amino Acid Composition) is a computational tool designed to identify candidate prion subsequences in protein sequences using a hidden-Markov model (HMM) algorithm. This repository provides a prebuilt version of PLAAC along with an automated Python pipeline to facilitate batch processing, visualization, and filtering of results.

##Features
Automated Setup: Installs necessary Python packages and external tools (Java, R, Poppler) if not already present.
Batch Processing: Processes multiple FASTA files to identify prion-like sequences.
Visualization: Generates PDF plots for each sequence analyzed.
Filtering: Detects and retains pages with prion-like features based on redline detection in images.
Directory Management: Automatically creates required directories for inputs, outputs, and temporary files.
