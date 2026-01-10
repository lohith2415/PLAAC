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
import multiprocessing as mp
import time
import gc

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
# PERFORMANCE TUNABLES
# ==========================
DEFAULT_WORKERS = max(1, min(mp.cpu_count() - 1, 8))  # number of parallel workers
DEFAULT_DPI = 150  # PDF render DPI
POOL_CHUNKSIZE = 32  # multiprocessing chunksize
BATCH_SIZE = 5000   # pages per batch

# ==========================
# DEPENDENCIES
# ==========================
PYTHON_PACKAGES = {"cv2": "opencv-python", "numpy": "numpy", "PIL": "pillow", "pypdf": "pypdf"}
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
# pypdf loader
# ==========================
def ensure_pypdf():
    try:
        from pypdf import PdfReader, PdfWriter
        return PdfReader, PdfWriter
    except Exception:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf"])
        from pypdf import PdfReader, PdfWriter
        return PdfReader, PdfWriter

def get_pdf_page_count(pdf_path):
    PdfReader, _ = ensure_pypdf()
    reader = PdfReader(pdf_path)
    return len(reader.pages)

# ==========================
# PDF -> PNG renderer
# ==========================
def render_single_page_to_png(pdf_path, page_num, temp_dir, dpi=DEFAULT_DPI):
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    out_prefix = os.path.join(temp_dir, f"{base_name}_p{page_num:06d}")
    cmd = ["pdftoppm", "-png", "-r", str(dpi), "-f", str(page_num), "-l", str(page_num), pdf_path, out_prefix]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for fname in os.listdir(temp_dir):
        if fname.startswith(os.path.basename(out_prefix)) and fname.endswith(".png"):
            return os.path.join(temp_dir, fname)
    cand = out_prefix + "-1.png"
    if os.path.exists(cand):
        return cand
    cand2 = out_prefix + ".png"
    if os.path.exists(cand2):
        return cand2
    raise FileNotFoundError(f"pdftoppm did not create PNG for page {page_num}")

# ==========================
# Redline detection
# ==========================
def redline_touches_top(image_path):
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

# ==========================
# Worker for multiprocessing
# ==========================
def worker_render_and_check(args):
    pdf_path, page_num, temp_dir, dpi = args
    try:
        png_path = render_single_page_to_png(pdf_path, page_num, temp_dir, dpi=dpi)
    except Exception as e:
        return (page_num, False, f"render_error:{e}")

    try:
        hit = redline_touches_top(png_path)
    except Exception as e:
        hit = False

    try:
        if os.path.exists(png_path):
            os.remove(png_path)
    except:
        pass

    gc.collect()
    return (page_num, bool(hit), None)

# ==========================
# Batch-based PDF filtering (streaming)
# ==========================
def filter_plaac_pdfs(output_dir, filter_dir, temp_dir, selected_files=None, workers=DEFAULT_WORKERS, dpi=DEFAULT_DPI, batch_size=BATCH_SIZE):
    if selected_files is None:
        pdf_files = [f for f in os.listdir(output_dir) if f.lower().endswith(".pdf")]
    else:
        pdf_files = selected_files

    total_hits = 0

    for pdf_file in pdf_files:
        input_pdf = os.path.join(output_dir, pdf_file)
        print(f"\nFiltering: {input_pdf}")
        base_name = os.path.splitext(pdf_file)[0]
        output_pdf = os.path.join(filter_dir, f"{base_name}_filtered.pdf")

        try:
            PdfReader, PdfWriter = ensure_pypdf()
            page_count = get_pdf_page_count(input_pdf)
        except Exception as e:
            print(f"⚠ Could not read page count for {input_pdf}: {e}")
            continue

        print(f"   → Total pages: {page_count}  |  Workers: {workers}  |  DPI: {dpi}")

        all_hit_pages = []

        for start_page in range(1, page_count + 1, batch_size):
            end_page = min(start_page + batch_size - 1, page_count)
            print(f"   → Processing batch: pages {start_page}-{end_page}")
            args_iter = ((input_pdf, pnum, temp_dir, dpi) for pnum in range(start_page, end_page + 1))
            hits = {}

            try:
                pool = mp.Pool(processes=workers)
                it = pool.imap_unordered(worker_render_and_check, args_iter, chunksize=POOL_CHUNKSIZE)
                processed = 0
                last_print = 0
                for res in it:
                    page_num, hit_flag, err = res
                    processed += 1
                    if hit_flag:
                        hits[page_num] = True
                    if processed == 1 or time.time() - last_print >= 0.5:
                        pct = (processed / (end_page - start_page + 1)) * 100
                        print(f"\r      Batch progress: {processed}/{end_page-start_page+1} pages ({pct:.2f}%)", end="")
                        last_print = time.time()
                pool.close()
                pool.join()
                print()
            except Exception as e:
                try:
                    pool.terminate()
                    pool.join()
                except:
                    pass
                print(f"\n⚠ Parallel processing error in batch: {e}")
                continue

            all_hit_pages.extend(sorted(hits.keys()))

            try:
                for f in os.listdir(temp_dir):
                    if f.startswith(base_name):
                        fp = os.path.join(temp_dir, f)
                        try: os.remove(fp)
                        except: pass
            except: pass

        if not all_hit_pages:
            print("⚠ No pages detected with red line touching top.")
            continue

        writer = PdfWriter()
        reader = PdfReader(input_pdf)
        for pnum in all_hit_pages:
            writer.add_page(reader.pages[pnum - 1])

        try:
            with open(output_pdf, "wb") as f_out:
                writer.write(f_out)
            print(f"✔ Filtered PDF created: {output_pdf}  (pages kept: {len(all_hit_pages)})")
            total_hits += 1
        except Exception as e:
            print(f"⚠ Error writing filtered PDF {output_pdf}: {e}")

    print(f"\n📊 Filter Summary: {total_hits} PDFs had prion-like hits.\n")

# ==========================
# MAIN
# ==========================
def main():
    print("🔍 Checking dependencies...")
    py_status = check_python_packages()
    tool_status = check_external_tools()
    show_dependency_summary(py_status, tool_status)
    global cv2, np, Image
    cv2, np, Image = import_libraries()

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
        filter_plaac_pdfs(OUTPUT_DIR, FILTER_OUTPUT_DIR, TEMP_IMAGE_DIR)

    print("\nPipeline complete ✅")

    pdf_files = [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(".pdf")]
    if pdf_files:
        print("\n🔎 Auto Prion Filtering on Outputs")
        user_choice = input("Enter PDF filename to filter (or press Enter for all): ").strip()
        if user_choice:
            if user_choice in pdf_files:
                filter_plaac_pdfs(OUTPUT_DIR, FILTER_OUTPUT_DIR, TEMP_IMAGE_DIR, [user_choice])
            else:
                print(f"❌ PDF not found: {user_choice}")
        else:
            filter_plaac_pdfs(OUTPUT_DIR, FILTER_OUTPUT_DIR, TEMP_IMAGE_DIR, pdf_files)

if __name__ == "__main__":
    main()

