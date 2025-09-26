#!/usr/bin/env python3
import os
import sys
import subprocess
import importlib.util
import shutil
import platform
from PIL import Image

# ==========================
# DEFAULT DIRECTORIES (inside repo)
# ==========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # current script folder
TOOLS_DIR = os.path.join(BASE_DIR, "plaac")
INPUT_DIR = os.path.join(BASE_DIR, "inputs")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
FILTER_OUTPUT_DIR = os.path.join(BASE_DIR, "redline_max_detected")
TEMP_IMAGE_DIR = os.path.join(BASE_DIR, "temp_pdf_pages")

# ==========================
# CREATE REQUIRED DIRECTORIES
# ==========================
for folder in [TOOLS_DIR, INPUT_DIR, OUTPUT_DIR, FILTER_OUTPUT_DIR, TEMP_IMAGE_DIR]:
    os.makedirs(folder, exist_ok=True)

# ==========================
# OPTIONAL USER OVERRIDE
# ==========================
dirs_input = input(
    f"Enter directories as: PLAAC_tools,input,output,filtered,temp [Press Enter to use defaults]: "
).strip()

if dirs_input:
    dirs = [d.strip() for d in dirs_input.split(",")]
    TOOLS_DIR = dirs[0] if len(dirs) > 0 and dirs[0] else TOOLS_DIR
    INPUT_DIR = dirs[1] if len(dirs) > 1 and dirs[1] else INPUT_DIR
    OUTPUT_DIR = dirs[2] if len(dirs) > 2 and dirs[2] else OUTPUT_DIR
    FILTER_OUTPUT_DIR = dirs[3] if len(dirs) > 3 and dirs[3] else FILTER_OUTPUT_DIR
    TEMP_IMAGE_DIR = dirs[4] if len(dirs) > 4 and dirs[4] else TEMP_IMAGE_DIR

# ==========================
# DEPENDENCIES
# ==========================
PYTHON_PACKAGES = {"cv2": "opencv-python", "numpy": "numpy", "PIL": "pillow"}
EXTERNAL_TOOLS = {
    "java": "Java (to run plaac.jar)",
    "Rscript": "R (to run plaac_plot.r)",
    "pdftoppm": "Poppler (to split PDFs into PNGs)"
}

def check_python_packages():
    status = {}
    for module, pip_name in PYTHON_PACKAGES.items():
        if importlib.util.find_spec(module) is None:
            print(f"❌ Python package missing: {pip_name} → installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            status[pip_name] = "✅ Installed (now)"
        else:
            status[pip_name] = "✅ Installed"
    return status

def check_external_tools():
    status = {}
    os_name = platform.system().lower()
    for tool, desc in EXTERNAL_TOOLS.items():
        if shutil.which(tool):
            status[tool] = "✅ Installed"
        else:
            print(f"❌ {desc} missing: {tool}")
            if "linux" in os_name:
                if tool == "java":
                    subprocess.run(["sudo", "apt-get", "install", "-y", "default-jre"])
                elif tool == "Rscript":
                    subprocess.run(["sudo", "apt-get", "install", "-y", "r-base"])
                elif tool == "pdftoppm":
                    subprocess.run(["sudo", "apt-get", "install", "-y", "poppler-utils"])
                status[tool] = "✅ Installed (now)"
            elif "darwin" in os_name:  # macOS
                if shutil.which("brew") is None:
                    print("❌ Homebrew not found. Please install from https://brew.sh/")
                    sys.exit(1)
                brew_map = {"java": "openjdk", "Rscript": "r", "pdftoppm": "poppler"}
                subprocess.run(["brew", "install", brew_map[tool]])
                status[tool] = "✅ Installed (now)"
            elif "windows" in os_name:
                status[tool] = f"❌ Missing (please install manually → {desc})"
            else:
                status[tool] = "❌ Unsupported OS"
    return status

def show_dependency_summary(py_status, tool_status):
    print("\n=== 🔍 Dependency Check Summary ===")
    print("📦 Python Packages:")
    for pkg, stat in py_status.items():
        print(f"   - {pkg}: {stat}")
    print("\n🛠 External Tools:")
    for tool, stat in tool_status.items():
        print(f"   - {tool}: {stat}")
    print("==================================\n")

def import_libraries():
    import cv2
    import numpy as np
    from PIL import Image
    return cv2, np, Image

# ==========================
# PIPELINE FUNCTIONS
# ==========================
def run_plaac(input_fasta, output_txt, output_pdf):
    print(f"▶ Running PLAAC on {os.path.basename(input_fasta)}...")
    cmd1 = ["java", "-jar", os.path.join(TOOLS_DIR, "plaac.jar"), "-i", input_fasta, "-p", "all"]
    with open(output_txt, "w") as out:
        subprocess.run(cmd1, check=True, cwd=TOOLS_DIR, stdout=out)
    cmd2 = ["Rscript", "plaac_plot.r", output_txt, output_pdf]
    subprocess.run(cmd2, check=True, cwd=TOOLS_DIR)
    print(f"✔ PLAAC analysis complete: {output_txt}, {output_pdf}")

def convert_pdf_to_images(pdf_path, output_basename):
    print("▶ Splitting PDF into images...")
    for f in os.listdir(TEMP_IMAGE_DIR):
        if f.startswith(output_basename):
            os.remove(os.path.join(TEMP_IMAGE_DIR, f))
    cmd = ["pdftoppm", "-png", pdf_path, os.path.join(TEMP_IMAGE_DIR, output_basename)]
    subprocess.run(cmd, check=True)
    images = [os.path.join(TEMP_IMAGE_DIR, f)
              for f in os.listdir(TEMP_IMAGE_DIR)
              if f.startswith(output_basename) and f.endswith(".png")]
    images.sort()
    return images

def redline_touches_top(image_path, cv2, np, Image):
    image = Image.open(image_path)
    cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    height, width, _ = cv_image.shape
    top_crop = cv_image[0:int(height*0.25), int(width*0.05):int(width*0.95)]
    red_channel = top_crop[:, :, 2]
    green_channel = top_crop[:, :, 1]
    blue_channel = top_crop[:, :, 0]
    red_diff = cv2.subtract(red_channel, cv2.max(green_channel, blue_channel))
    _, red_mask = cv2.threshold(red_diff, 30, 255, cv2.THRESH_BINARY)
    red_pixel_positions = (red_mask == 255).nonzero()
    return np.any(red_pixel_positions[0] <= 5)

# ==========================
# MAIN
# ==========================
def main():
    print("🔍 Checking dependencies...")
    py_status = check_python_packages()
    tool_status = check_external_tools()
    show_dependency_summary(py_status, tool_status)
    cv2, np, Image = import_libraries()

    # Ask for FASTA file (or all)
    input_file_name = input(f"Enter the input FASTA file name (in {INPUT_DIR}/) [Enter for ALL]: ").strip()
    if input_file_name == "":
        fasta_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".fasta")]
        if not fasta_files:
            raise FileNotFoundError("No FASTA files found in input folder!")
    else:
        fasta_files = [input_file_name]

    total_hits = 0
    for fname in fasta_files:
        input_fasta = os.path.join(INPUT_DIR, fname)
        output_txt = os.path.join(OUTPUT_DIR, fname.replace(".fasta", "_output.txt"))
        output_pdf = os.path.join(OUTPUT_DIR, fname.replace(".fasta", "_plot.pdf"))
        final_filtered_pdf = os.path.join(FILTER_OUTPUT_DIR, f"{fname.replace('.fasta','')}_filtered.pdf")

        print(f"\n=== Processing {fname} ===")
        run_plaac(input_fasta, output_txt, output_pdf)

        base_name = os.path.splitext(os.path.basename(output_pdf))[0]
        page_images = convert_pdf_to_images(output_pdf, base_name)

        detected_images = []
        for page_img_path in page_images:
            if redline_touches_top(page_img_path, cv2, np, Image):
                detected_images.append(page_img_path)
                print(f"✅ Red line touches top: {os.path.basename(page_img_path)}")
            else:
                print(f"❌ Skipped: {os.path.basename(page_img_path)}")

        if detected_images:
            pil_images = [Image.open(img_path).convert("RGB") for img_path in detected_images]
            pil_images[0].save(final_filtered_pdf, save_all=True, append_images=pil_images[1:])
            print(f"\n✔ Filtered PDF created: {final_filtered_pdf}")
            total_hits += 1
        else:
            print("\n⚠ No prion-like pages detected.")

        # Clean temp images
        for img_path in page_images:
            if os.path.exists(img_path):
                os.remove(img_path)

    print(f"\n📊 Summary: {len(fasta_files)} FASTA files processed, {total_hits} had prion-like hits.")
    print("\nPipeline complete ✅")

if __name__ == "__main__":
    main()
