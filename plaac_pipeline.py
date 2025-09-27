#!/usr/bin/env python3
import os
import sys
import subprocess
import importlib.util
import shutil
import platform
from PIL import Image
import cv2
import numpy as np

# ==========================
# WORKING PATHS (dynamic)
# ==========================
BASE_DIR = os.getcwd()
TOOLS_DIR = os.path.join(BASE_DIR, "plaac")
INPUT_DIR = os.path.join(BASE_DIR, "inputs")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
FILTER_OUTPUT_DIR = os.path.join(BASE_DIR, "redline_max_detected")
TEMP_IMAGE_DIR = os.path.join(BASE_DIR, "temp_pdf_pages")

# Create directories if missing
for folder in [TOOLS_DIR, INPUT_DIR, OUTPUT_DIR, FILTER_OUTPUT_DIR, TEMP_IMAGE_DIR]:
    os.makedirs(folder, exist_ok=True)

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
            elif "darwin" in os_name:
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
# PLAAC PIPELINE
# ==========================
def run_plaac(input_fasta, output_txt, output_pdf):
    print(f"▶ Running PLAAC on {os.path.basename(input_fasta)}...")
    cmd1 = ["java", "-jar", os.path.join(TOOLS_DIR, "plaac.jar"), "-i", input_fasta, "-p", "all"]
    with open(output_txt, "w") as out:
        subprocess.run(cmd1, check=True, cwd=TOOLS_DIR, stdout=out)
    cmd2 = ["Rscript", "plaac_plot.r", output_txt, output_pdf]
    subprocess.run(cmd2, check=True, cwd=TOOLS_DIR)
    print(f"✔ PLAAC analysis complete: {output_txt}, {output_pdf}")

# ==========================
# PDF FILTER
# ==========================
def convert_pdf_to_images(pdf_path, temp_dir):
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    output_path = os.path.join(temp_dir, base_name)
    for f in os.listdir(temp_dir):
        if f.startswith(base_name):
            os.remove(os.path.join(temp_dir, f))
    cmd = ["pdftoppm", "-png", pdf_path, output_path]
    subprocess.run(cmd, check=True)
    images = sorted([
        os.path.join(temp_dir, f)
        for f in os.listdir(temp_dir)
        if f.startswith(base_name) and f.endswith(".png")
    ])
    return images

def redline_touches_top(image_path):
    """Detect if red line in top graph reaches the top (value 1)."""
    image = Image.open(image_path)
    cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    top_crop = gray[180:400, 100:1800]
    red_channel = cv_image[180:400, 100:1800, 2]
    green_channel = cv_image[180:400, 100:1800, 1]
    blue_channel = cv_image[180:400, 100:1800, 0]
    red_diff = cv2.subtract(red_channel, cv2.max(green_channel, blue_channel))
    _, red_mask = cv2.threshold(red_diff, 30, 255, cv2.THRESH_BINARY)
    red_pixel_positions = np.where(red_mask == 255)
    return np.any(red_pixel_positions[0] == 0)

def filter_plaac_pdfs(output_dir, filter_dir, temp_dir):
    pdf_files = [f for f in os.listdir(output_dir) if f.lower().endswith(".pdf")]
    total_hits = 0
    for pdf_file in pdf_files:
        input_pdf = os.path.join(output_dir, pdf_file)
        print(f"\nFiltering: {input_pdf}")
        base_name = os.path.splitext(pdf_file)[0]
        output_pdf = os.path.join(filter_dir, f"{base_name}_filtered.pdf")
        try:
            page_images = convert_pdf_to_images(input_pdf, temp_dir)
            detected_images = []
            for img_path in page_images:
                if redline_touches_top(img_path):
                    detected_images.append(img_path)
                    print(f"✅ Red line touches top: {os.path.basename(img_path)}")
                else:
                    print(f"❌ Skipped: {os.path.basename(img_path)}")
            if detected_images:
                pil_images = [Image.open(p).convert("RGB") for p in detected_images]
                pil_images[0].save(output_pdf, save_all=True, append_images=pil_images[1:])
                print(f"✔ Filtered PDF created: {output_pdf}")
                total_hits += 1
            else:
                print("⚠ No pages detected with red line touching top.")
            # Cleanup temp images
            for img_path in page_images:
                if os.path.exists(img_path):
                    os.remove(img_path)
        except Exception as e:
            print(f"⚠ Error processing {input_pdf}: {e}")
    print(f"\n📊 Filter Summary: {total_hits} PDFs had prion-like hits.\n")

# ==========================
# MAIN
# ==========================
def main():
    print("🔍 Checking dependencies...")
    py_status = check_python_packages()
    tool_status = check_external_tools()
    show_dependency_summary(py_status, tool_status)
    cv2, np, Image = import_libraries()

    # ==========================
    # FASTA Processing
    # ==========================
    fasta_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".fasta")]

    if fasta_files:
        user_choice = input("Enter FASTA filename (or press Enter for all): ").strip()
        if user_choice:
            if user_choice in fasta_files:
                fasta_files = [user_choice]
            else:
                print(f"❌ File not found: {user_choice}")
                return
        for fname in fasta_files:
            input_fasta = os.path.join(INPUT_DIR, fname)
            output_txt = os.path.join(OUTPUT_DIR, fname.replace(".fasta", "_output.txt"))
            output_pdf = os.path.join(OUTPUT_DIR, fname.replace(".fasta", "_plot.pdf"))
            print(f"\n=== Processing {fname} ===")
            run_plaac(input_fasta, output_txt, output_pdf)

    else:
        print(f"No FASTA files found in {INPUT_DIR}")
        # ==========================
        # PDF Filtering
        # ==========================
        pdf_files = [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(".pdf")]
        if not pdf_files:
            print(f"No PDF files found in {OUTPUT_DIR}")
            return
        user_choice = input("Enter PDF filename to filter (or press Enter for all): ").strip()
        if user_choice:
            if user_choice in pdf_files:
                pdf_files = [user_choice]
            else:
                print(f"❌ PDF not found: {user_choice}")
                return
        # filter PDFs
        filter_plaac_pdfs(OUTPUT_DIR, FILTER_OUTPUT_DIR, TEMP_IMAGE_DIR)

    print("\nPipeline complete ✅")

if __name__ == "__main__":
    main()
