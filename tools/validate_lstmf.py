#!/usr/bin/env python3
"""Validate .lstmf files by probing with lstmtraining.

Runs lstmtraining with max_iterations=0 on small batches to find corrupt files.
Outputs a clean file list for training.
"""

import glob
import os
import re
import subprocess
import sys
import time

LSTMTRAINING = r"C:\Program Files\Tesseract-OCR\lstmtraining.exe"
ENG_BEST = r"E:\NEXUS_V2_RECREATED\training\eng_best.traineddata"
ENG_LSTM = r"E:\NEXUS_V2_RECREATED\training\eng_best.lstm"


def probe_batch(files: list, tmp_list: str) -> list:
    """Test a batch of lstmf files. Returns list of bad file paths."""
    with open(tmp_list, 'w') as f:
        f.write('\n'.join(files))

    result = subprocess.run(
        [LSTMTRAINING,
         '--traineddata', ENG_BEST,
         '--old_traineddata', ENG_BEST,
         '--continue_from', ENG_LSTM,
         '--train_listfile', tmp_list,
         '--model_output', tmp_list.replace('.list', '_probe'),
         '--max_iterations', '0'],
        capture_output=True, text=True, timeout=60
    )

    bad = set()
    for line in (result.stdout + result.stderr).splitlines():
        m = re.match(r'Deserialize header failed:\s*(.+\.lstmf)', line.strip())
        if m:
            bad.add(m.group(1).strip())
    return list(bad)


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else r"E:\NEXUS_V2_RECREATED\training\ocr_train_data"
    lstmf_files = sorted(glob.glob(os.path.join(data_dir, '*.lstmf')))
    print(f"Validating {len(lstmf_files)} .lstmf files...")

    tmp_list = os.path.join(data_dir, '_validate_tmp.list')
    all_bad = set()
    batch_size = 500  # Test 500 at a time

    t0 = time.time()
    for i in range(0, len(lstmf_files), batch_size):
        batch = [f for f in lstmf_files[i:i+batch_size] if f not in all_bad]
        if not batch:
            continue

        bad = probe_batch(batch, tmp_list)
        all_bad.update(bad)

        done = min(i + batch_size, len(lstmf_files))
        elapsed = time.time() - t0
        print(f"  [{done}/{len(lstmf_files)}] {len(all_bad)} bad files found ({elapsed:.0f}s)")

    # Clean up
    for f in glob.glob(tmp_list.replace('.list', '*')):
        os.remove(f)

    # Write clean list
    clean = [f for f in lstmf_files if f not in all_bad]
    output = os.path.join(os.path.dirname(data_dir), 'tesseract_training', 'validated.list')
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, 'w') as f:
        f.write('\n'.join(clean))

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s")
    print(f"  Total: {len(lstmf_files)}")
    print(f"  Bad:   {len(all_bad)}")
    print(f"  Clean: {len(clean)}")
    print(f"  Output: {output}")

    # Also write bad list for debugging
    bad_list = output.replace('validated.list', 'bad_files.list')
    with open(bad_list, 'w') as f:
        f.write('\n'.join(sorted(all_bad)))
    print(f"  Bad list: {bad_list}")


if __name__ == '__main__':
    main()
