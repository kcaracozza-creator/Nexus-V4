#!/usr/bin/env python3
"""NEXUS Tesseract LSTM Fine-Tuning — Windows Native

Replaces tesstrain's Makefile workflow for Windows. Uses the Tesseract 5.x
training binaries directly (tesseract.exe, lstmtraining.exe, combine_tessdata.exe).

Pipeline:
  1. Generate .lstmf feature files from .tif + .gt.txt pairs
  2. Create training/eval file lists (90/10 split)
  3. Run lstmtraining to fine-tune from eng_best LSTM checkpoint
  4. Package final .traineddata

Usage:
    python train_tesseract_win.py --data E:/NEXUS_V2_RECREATED/training/ocr_train_data
    python train_tesseract_win.py --data ./ocr_train_data --max-iterations 10000 --workers 16

Prerequisites:
    - Tesseract 5.x installed (winget install tesseract-ocr.tesseract)
    - Run ocr_training_gen.py first to generate .tif + .gt.txt pairs
"""

import argparse
import glob
import os
import random
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from pathlib import Path

# Default paths — adjust if Tesseract is installed elsewhere
TESSERACT_DIR = r"C:\Program Files\Tesseract-OCR"
TESSERACT_EXE = os.path.join(TESSERACT_DIR, "tesseract.exe")
LSTMTRAINING_EXE = os.path.join(TESSERACT_DIR, "lstmtraining.exe")
COMBINE_TESSDATA_EXE = os.path.join(TESSERACT_DIR, "combine_tessdata.exe")
TESSDATA_DIR = os.path.join(TESSERACT_DIR, "tessdata")


def check_prerequisites(eng_best_path: str):
    """Verify all required binaries and files exist."""
    missing = []
    for exe in [TESSERACT_EXE, LSTMTRAINING_EXE, COMBINE_TESSDATA_EXE]:
        if not os.path.isfile(exe):
            missing.append(exe)
    if not os.path.isfile(eng_best_path):
        missing.append(eng_best_path)
    if missing:
        print("[ERROR] Missing prerequisites:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)


def generate_box_file(tif_path: str) -> bool:
    """Create LSTM box file from .gt.txt ground truth.

    LSTM box format: each character on its own line with full-image bbox,
    terminated by a tab character line. This is what tesstrain's
    generate_line_box.py produces.
    """
    try:
        from PIL import Image
    except ImportError:
        import cv2
        img = cv2.imread(tif_path)
        if img is None:
            return False
        height, width = img.shape[:2]
    else:
        im = Image.open(tif_path)
        width, height = im.size

    base = tif_path.rsplit('.tif', 1)[0]
    gt_path = base + '.gt.txt'
    box_path = base + '.box'

    if not os.path.isfile(gt_path):
        return False

    with open(gt_path, 'r', encoding='utf-8') as f:
        gt_text = f.read().strip()

    if not gt_text:
        return False

    lines = []
    for char in gt_text:
        # Each char gets full image bbox: char x1 y1 x2 y2 page
        lines.append(f"{char} 0 0 {width} {height} 0")
    # Tab terminator for line end
    lines.append(f"\t 0 0 {width} {height} 0")

    with open(box_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    return True


def generate_lstmf(tif_path: str, tessdata: str) -> str:
    """Run tesseract on a single .tif + .box pair to produce .lstmf features.

    Returns the .lstmf path on success, empty string on failure.
    """
    base = tif_path.rsplit('.tif', 1)[0]
    gt_path = base + '.gt.txt'
    box_path = base + '.box'
    lstmf_path = base + '.lstmf'

    if not os.path.isfile(gt_path):
        return ''

    # Skip if .lstmf already exists (resume support)
    if os.path.isfile(lstmf_path) and os.path.getsize(lstmf_path) > 0:
        return lstmf_path

    # Step 1: Generate .box file from ground truth
    if not os.path.isfile(box_path):
        if not generate_box_file(tif_path):
            return ''

    # Step 2: Run tesseract lstm.train with box file present
    try:
        result = subprocess.run(
            [TESSERACT_EXE, tif_path, base, '--psm', '13', 'lstm.train'],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, 'TESSDATA_PREFIX': tessdata}
        )
        if os.path.isfile(lstmf_path) and os.path.getsize(lstmf_path) > 0:
            return lstmf_path
    except (subprocess.TimeoutExpired, Exception):
        pass

    return ''


def generate_all_lstmf(data_dir: str, tessdata: str, workers: int) -> list:
    """Generate .lstmf files for all .tif files in data_dir using parallel workers."""
    tif_files = glob.glob(os.path.join(data_dir, '*.tif'))
    if not tif_files:
        print(f"[ERROR] No .tif files found in {data_dir}")
        sys.exit(1)

    # Check how many already have .lstmf
    existing = sum(1 for t in tif_files
                   if os.path.isfile(t.rsplit('.tif', 1)[0] + '.lstmf'))
    remaining = len(tif_files) - existing
    print(f"[LSTMF] {len(tif_files)} .tif files, {existing} already have .lstmf, {remaining} to process")

    if remaining == 0:
        lstmf_files = [t.rsplit('.tif', 1)[0] + '.lstmf' for t in tif_files
                       if os.path.isfile(t.rsplit('.tif', 1)[0] + '.lstmf')]
        return lstmf_files

    t0 = time.time()
    lstmf_files = []
    failed = 0

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(generate_lstmf, tif, tessdata): tif
                   for tif in tif_files}
        done = 0
        for future in as_completed(futures):
            result = future.result()
            if result:
                lstmf_files.append(result)
            else:
                failed += 1
            done += 1
            if done % 2000 == 0:
                elapsed = time.time() - t0
                rate = done / max(elapsed, 0.001)
                eta = (len(tif_files) - done) / max(rate, 0.1)
                print(f"[LSTMF] {done}/{len(tif_files)} "
                      f"({len(lstmf_files)} ok, {failed} failed, "
                      f"{rate:.0f}/s, ETA: {eta:.0f}s)")

    elapsed = time.time() - t0
    print(f"[LSTMF] Done: {len(lstmf_files)} .lstmf files in {elapsed:.1f}s "
          f"({failed} failed)")

    # Validate: filter out corrupt/tiny .lstmf files that crash lstmtraining
    min_size = 100  # valid .lstmf files are typically >1KB
    valid = [f for f in lstmf_files if os.path.getsize(f) >= min_size]
    rejected = len(lstmf_files) - len(valid)
    if rejected:
        print(f"[LSTMF] Filtered {rejected} undersized .lstmf files (<{min_size} bytes)")
    lstmf_files = valid

    return lstmf_files


def create_file_lists(lstmf_files: list, output_dir: str,
                      eval_fraction: float = 0.1):
    """Split .lstmf files into training and eval lists."""
    random.shuffle(lstmf_files)
    split = int(len(lstmf_files) * (1 - eval_fraction))
    train_files = lstmf_files[:split]
    eval_files = lstmf_files[split:]

    train_list = os.path.join(output_dir, 'train.list')
    eval_list = os.path.join(output_dir, 'eval.list')

    with open(train_list, 'w') as f:
        f.write('\n'.join(train_files))
    with open(eval_list, 'w') as f:
        f.write('\n'.join(eval_files))

    print(f"[SPLIT] Train: {len(train_files)}, Eval: {len(eval_files)}")
    return train_list, eval_list


def run_training(train_list: str, eval_list: str, eng_best_lstm: str,
                 eng_best_traineddata: str, output_dir: str,
                 model_name: str, max_iterations: int):
    """Run lstmtraining to fine-tune from eng_best."""
    checkpoint_dir = os.path.join(output_dir, 'checkpoints')
    os.makedirs(checkpoint_dir, exist_ok=True)

    cmd = [
        LSTMTRAINING_EXE,
        '--traineddata', eng_best_traineddata,
        '--old_traineddata', eng_best_traineddata,
        '--continue_from', eng_best_lstm,
        '--train_listfile', train_list,
        '--eval_listfile', eval_list,
        '--model_output', os.path.join(checkpoint_dir, model_name),
        '--max_iterations', str(max_iterations),
        '--target_error_rate', '0.01',
        '--debug_interval', '100',
    ]

    print(f"\n[TRAIN] Starting LSTM fine-tuning")
    print(f"[TRAIN] Model: {model_name}")
    print(f"[TRAIN] Max iterations: {max_iterations}")
    print(f"[TRAIN] Checkpoints: {checkpoint_dir}")
    print(f"[TRAIN] Target BCER: < 1.0%")
    print(f"[TRAIN] --- Training output below ---\n")

    # Retry loop: lstmtraining is fatal on corrupt .lstmf files.
    # Catch "Deserialize header failed" filenames, remove from lists, retry.
    import re
    max_retries = 5
    for attempt in range(max_retries):
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )

        bad_files = set()
        for line in process.stdout:
            print(line, end='', flush=True)
            m = re.match(r'Deserialize header failed:\s*(.+\.lstmf)', line.strip())
            if m:
                bad_files.add(m.group(1).strip())

        process.wait()

        if process.returncode == 0 or not bad_files:
            break

        if bad_files and attempt < max_retries - 1:
            print(f"\n[TRAIN] Retry {attempt+1}: removing {len(bad_files)} corrupt .lstmf files")
            # Read current lists, filter, rewrite
            for list_file in [train_list, eval_list]:
                with open(list_file, 'r') as f:
                    lines = [l.strip() for l in f if l.strip() not in bad_files]
                with open(list_file, 'w') as f:
                    f.write('\n'.join(lines))
            print(f"[TRAIN] Cleaned lists. Retrying...")
            continue

    if process.returncode != 0 and bad_files:
        print(f"\n[TRAIN] Training failed after {max_retries} retries")
        return None

    # Find the best checkpoint
    best_checkpoint = os.path.join(checkpoint_dir, f"{model_name}_checkpoint")
    if not os.path.isfile(best_checkpoint):
        # Try finding any checkpoint
        checkpoints = glob.glob(os.path.join(checkpoint_dir, f"{model_name}*_checkpoint"))
        if checkpoints:
            best_checkpoint = sorted(checkpoints)[-1]
        else:
            print("[TRAIN] No checkpoint found!")
            return None

    print(f"\n[TRAIN] Best checkpoint: {best_checkpoint}")
    return best_checkpoint


def package_model(checkpoint: str, eng_best_traineddata: str,
                  output_dir: str, model_name: str) -> str:
    """Combine checkpoint + tessdata into final .traineddata."""
    final_path = os.path.join(output_dir, f"{model_name}.traineddata")

    # lstmtraining outputs a checkpoint — we need to combine it with tessdata
    cmd = [
        LSTMTRAINING_EXE,
        '--stop_training',
        '--traineddata', eng_best_traineddata,
        '--continue_from', checkpoint,
        '--model_output', final_path,
    ]

    print(f"\n[PACKAGE] Creating {final_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[PACKAGE] Error: {result.stderr}")
        return ''

    if os.path.isfile(final_path):
        size_mb = os.path.getsize(final_path) / 1024 / 1024
        print(f"[PACKAGE] Success: {final_path} ({size_mb:.1f} MB)")

        # Install to tessdata
        install_path = os.path.join(TESSDATA_DIR, f"{model_name}.traineddata")
        print(f"[PACKAGE] To install: copy {final_path} to {install_path}")

        return final_path

    print("[PACKAGE] Failed to create .traineddata")
    return ''


def main():
    parser = argparse.ArgumentParser(
        description='NEXUS Tesseract LSTM Fine-Tuning (Windows)')
    parser.add_argument('--data', required=True,
                        help='Directory with .tif + .gt.txt training pairs')
    parser.add_argument('--model-name', default='nexus_mtg',
                        help='Output model name (default: nexus_mtg)')
    parser.add_argument('--max-iterations', type=int, default=10000,
                        help='Max training iterations (default: 10000)')
    parser.add_argument('--workers', type=int, default=0,
                        help='Parallel workers for .lstmf generation (0=auto)')
    parser.add_argument('--eng-best', default=None,
                        help='Path to eng_best.traineddata (auto-detected)')
    parser.add_argument('--eval-fraction', type=float, default=0.1,
                        help='Fraction of data for evaluation (default: 0.1)')
    parser.add_argument('--skip-lstmf', action='store_true',
                        help='Skip .lstmf generation (resume from file lists)')
    args = parser.parse_args()

    n_workers = args.workers or cpu_count()
    data_dir = os.path.abspath(args.data)
    output_dir = os.path.join(os.path.dirname(data_dir), 'tesseract_training')
    os.makedirs(output_dir, exist_ok=True)

    # Find eng_best.traineddata
    eng_best = args.eng_best
    if not eng_best:
        # Check common locations
        candidates = [
            os.path.join(os.path.dirname(data_dir), 'eng_best.traineddata'),
            os.path.join(TESSDATA_DIR, 'eng.traineddata'),
        ]
        for c in candidates:
            if os.path.isfile(c):
                eng_best = c
                break
    if not eng_best:
        print("[ERROR] eng_best.traineddata not found. Specify with --eng-best")
        sys.exit(1)

    # Extract LSTM from traineddata if needed
    eng_best_lstm = eng_best.replace('.traineddata', '.lstm')
    if not os.path.isfile(eng_best_lstm):
        print(f"[SETUP] Extracting LSTM from {eng_best}")
        subprocess.run(
            [COMBINE_TESSDATA_EXE, '-e', eng_best, eng_best_lstm],
            check=True
        )

    # CRITICAL: lstmf generation MUST use the same traineddata as training.
    # Create a custom tessdata dir with eng_best as "eng.traineddata" plus
    # the configs/ and tessconfigs/ dirs (needed for lstm.train config file).
    import shutil
    tessdata_for_gen = os.path.join(os.path.dirname(data_dir), 'tessdata_best')
    tessdata_eng_link = os.path.join(tessdata_for_gen, 'eng.traineddata')
    if not os.path.isfile(tessdata_eng_link):
        os.makedirs(tessdata_for_gen, exist_ok=True)
        shutil.copy2(eng_best, tessdata_eng_link)
    # Copy configs from system tessdata (lstm.train config required)
    for subdir in ['configs', 'tessconfigs']:
        src = os.path.join(TESSDATA_DIR, subdir)
        dst = os.path.join(tessdata_for_gen, subdir)
        if os.path.isdir(src) and not os.path.isdir(dst):
            shutil.copytree(src, dst)
    print(f"[SETUP] tessdata_best dir ready with eng_best + configs")

    print(f"{'='*60}")
    print(f" NEXUS Tesseract LSTM Fine-Tuning")
    print(f"{'='*60}")
    print(f" Data:          {data_dir}")
    print(f" Model name:    {args.model_name}")
    print(f" Base model:    {eng_best}")
    print(f" LSTM weights:  {eng_best_lstm}")
    print(f" Workers:       {n_workers}")
    print(f" Max iter:      {args.max_iterations}")
    print(f" Output:        {output_dir}")
    print(f"{'='*60}\n")

    check_prerequisites(eng_best)

    # Step 1: Generate .lstmf feature files
    if not args.skip_lstmf:
        print("[1/4] Generating .lstmf feature files...")
        lstmf_files = generate_all_lstmf(data_dir, tessdata_for_gen, n_workers)
    else:
        lstmf_files = glob.glob(os.path.join(data_dir, '*.lstmf'))
        print(f"[1/4] Skipped — found {len(lstmf_files)} existing .lstmf files")

    if len(lstmf_files) < 10:
        print(f"[ERROR] Only {len(lstmf_files)} .lstmf files — need at least 10")
        sys.exit(1)

    # Step 2: Create train/eval file lists
    print("\n[2/4] Creating train/eval split...")
    train_list, eval_list = create_file_lists(
        lstmf_files, output_dir, args.eval_fraction)

    # Step 3: Run LSTM training
    print("\n[3/4] Running LSTM fine-tuning...")
    checkpoint = run_training(
        train_list, eval_list, eng_best_lstm, eng_best,
        output_dir, args.model_name, args.max_iterations)

    if not checkpoint:
        print("\n[FAIL] Training did not produce a checkpoint.")
        sys.exit(1)

    # Step 4: Package final model
    print("\n[4/4] Packaging final model...")
    final = package_model(checkpoint, eng_best, output_dir, args.model_name)

    if final:
        print(f"\n{'='*60}")
        print(f" TRAINING COMPLETE")
        print(f"{'='*60}")
        print(f" Model:    {final}")
        print(f" Install:  copy to {TESSDATA_DIR}\\{args.model_name}.traineddata")
        print(f" Test:     tesseract image.tif stdout -l {args.model_name} --psm 7")
        print(f"{'='*60}")


if __name__ == '__main__':
    main()
