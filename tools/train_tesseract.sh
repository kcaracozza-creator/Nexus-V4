#!/bin/bash
# NEXUS Tesseract Training Pipeline — run in WSL2 on ZULTAN
#
# This script:
#   1. Installs tesstrain dependencies
#   2. Clones tesstrain if needed
#   3. Links training data from the generator output
#   4. Runs fine-tuning from the English base model
#
# Prerequisites:
#   - Run ocr_training_gen.py FIRST to generate .tif + .gt.txt pairs
#   - WSL2 or native Linux on ZULTAN
#
# Usage:
#   bash train_tesseract.sh /path/to/training_data [max_iterations]
#
# Example:
#   python3 ocr_training_gen.py --db ~/nexus_cards.db --out ~/ocr_train_data --count 5000 --hard-mode
#   bash train_tesseract.sh ~/ocr_train_data 10000

set -euo pipefail

TRAIN_DATA="${1:?Usage: $0 /path/to/training_data [max_iterations]}"
MAX_ITER="${2:-10000}"
MODEL_NAME="nexus_mtg"
START_MODEL="eng"
TESSTRAIN_DIR="$HOME/tesstrain"

echo "=== NEXUS Tesseract Training Pipeline ==="
echo "Training data: $TRAIN_DATA"
echo "Max iterations: $MAX_ITER"
echo "Model name: $MODEL_NAME"
echo ""

# ── Step 1: Install dependencies ──────────────────────────────────────────
echo "[1/4] Installing dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    tesseract-ocr \
    libtesseract-dev \
    bc \
    make \
    python3-pip \
    wget \
    2>/dev/null

# Check Tesseract version
TESS_VER=$(tesseract --version 2>&1 | head -1)
echo "  Tesseract: $TESS_VER"

# Find tessdata directory
TESSDATA=""
for d in /usr/share/tesseract-ocr/5/tessdata /usr/share/tesseract-ocr/4.00/tessdata /usr/share/tessdata; do
    if [ -d "$d" ]; then
        TESSDATA="$d"
        break
    fi
done

if [ -z "$TESSDATA" ]; then
    echo "ERROR: Could not find tessdata directory"
    exit 1
fi
echo "  Tessdata: $TESSDATA"

# Ensure eng.traineddata exists
if [ ! -f "$TESSDATA/eng.traineddata" ]; then
    echo "  Downloading eng.traineddata..."
    sudo wget -q -O "$TESSDATA/eng.traineddata" \
        "https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata"
fi

# ── Step 2: Clone tesstrain ──────────────────────────────────────────────
echo "[2/4] Setting up tesstrain..."
if [ ! -d "$TESSTRAIN_DIR" ]; then
    git clone --depth 1 https://github.com/tesseract-ocr/tesstrain.git "$TESSTRAIN_DIR"
fi
cd "$TESSTRAIN_DIR"
make tesseract-langdata 2>/dev/null || true

# ── Step 3: Link training data ───────────────────────────────────────────
echo "[3/4] Linking training data..."
GROUND_TRUTH="$TESSTRAIN_DIR/data/${MODEL_NAME}-ground-truth"

# Count training pairs
N_PAIRS=$(ls "$TRAIN_DATA"/*.gt.txt 2>/dev/null | wc -l)
if [ "$N_PAIRS" -eq 0 ]; then
    echo "ERROR: No .gt.txt files found in $TRAIN_DATA"
    echo "Run ocr_training_gen.py first!"
    exit 1
fi
echo "  Found $N_PAIRS training pairs"

# Symlink or copy
if [ -L "$GROUND_TRUTH" ]; then
    rm "$GROUND_TRUTH"
fi
ln -sf "$TRAIN_DATA" "$GROUND_TRUTH"
echo "  Linked: $GROUND_TRUTH -> $TRAIN_DATA"

# ── Step 4: Train ────────────────────────────────────────────────────────
echo "[4/4] Starting training (this will take a while)..."
echo "  Model: $MODEL_NAME (fine-tuning from $START_MODEL)"
echo "  Max iterations: $MAX_ITER"
echo "  Watch BCER — target < 1.0% by iteration 1000"
echo ""

make training \
    MODEL_NAME="$MODEL_NAME" \
    START_MODEL="$START_MODEL" \
    TESSDATA="$TESSDATA" \
    MAX_ITERATIONS="$MAX_ITER" \
    2>&1 | tee "$HOME/tesstrain_${MODEL_NAME}.log"

# ── Done ─────────────────────────────────────────────────────────────────
echo ""
echo "=== Training Complete ==="
TRAINED="$TESSTRAIN_DIR/data/$MODEL_NAME.traineddata"
if [ -f "$TRAINED" ]; then
    echo "Model: $TRAINED"
    echo ""
    echo "To install:"
    echo "  sudo cp $TRAINED $TESSDATA/"
    echo ""
    echo "To test:"
    echo "  tesseract /path/to/card_name_crop.tif stdout -l $MODEL_NAME --psm 7"
else
    echo "WARNING: Training may not have completed successfully."
    echo "Check log: $HOME/tesstrain_${MODEL_NAME}.log"
fi
