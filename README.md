#PLAAC Pipeline: Automated Prion-Like Amino Acid Composition Analysis

The PLAAC Pipeline is a comprehensive Python-based framework developed to automate the analysis of prion-like amino acid sequences in protein datasets. Leveraging the capabilities of the widely used PLAAC tool, this pipeline enables users to perform high-throughput prion-like amino acid composition detection, generate informative visualizations, and create filtered outputs highlighting sequences with significant prion-like features. The pipeline is designed for both individual and batch processing of FASTA files, making it suitable for small-scale experiments as well as large-scale bioinformatics studies.

A key feature of the PLAAC Pipeline is its automatic dependency management. The pipeline checks for the presence of essential Python packages such as opencv-python, numpy, and Pillow, and installs any missing modules. It also verifies the availability of external tools including Java (required for running plaac.jar), R (for generating plots via plaac_plot.r), and Poppler utilities (pdftoppm) for converting PDFs into images. On Linux and macOS, the pipeline can automatically install missing tools, reducing manual setup and simplifying user experience. Windows users are guided to install necessary dependencies manually.

The pipeline provides flexible directory management, allowing users to specify custom paths for the PLAAC tool, input FASTA files, output results, filtered PDFs, and temporary image files. Default directories are provided if the user does not supply custom paths. Users can analyze a single FASTA file or process all FASTA files in a folder, making the workflow adaptable to different experimental scales.

Once the PLAAC analysis is complete, the pipeline generates plot PDFs for each


````markdown
## Installation

### Prerequisites
- Python 3.6+
- Java Runtime Environment (JRE)
- R (for plotting)
- Poppler utilities (`pdftoppm`)

### Setup
Clone the repository:
```bash
git clone https://github.com/lohith2415/PLAAC.git
cd PLAAC
````

Install required Python packages:

```bash
pip install opencv-python numpy pillow
```

Ensure external tools are installed:

* **Java**: [Install Java](https://www.java.com/en/download/)
* **R**: [Install R](https://cran.r-project.org/)
* **Poppler**: [Install Poppler](https://poppler.freedesktop.org/)

## Usage

### Place Input FASTA Files
Put your input FASTA files in the `inputs/` directory:

```bash
ls inputs/
```

### Run the Pipeline
Make the main Python script executable and run:

```bash
chmod +x plaac_pipeline.py
./plaac_pipeline.py
```

Follow the interactive prompts to specify directories and input files.
