#!/usr/bin/env python3
import os, sys, json, logging, time
import numpy as np
from flask import Flask, jsonify, request
import cv2

# Coral TPU setup
tflite_runtime = None
interpreter = None
CORAL_LOADED = False

MODEL_PATH = "/mnt/nexus_data/models/card_embedding_fp32.tflite"
FAISS_INDEX_PATH = "/mnt/nexus_data/models/faiss_index/card_art.index"
EDGETPU_LIB = "/usr/lib/aarch64-linux-gnu/libedgetpu.so.1"

logger = logging.getLogger("BROK_ART")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

app = Flask(__name__)

def init_coral():
    global tflite_runtime, interpreter, CORAL_LOADED
    try:
        import tflite_runtime.interpreter as tflite
        tflite_runtime = tflite
        logger.info("tflite_runtime imported successfully")
        
        # Try EdgeTPU delegate
        try:
            if os.path.exists(EDGETPU_LIB):
                interpreter = tflite.Interpreter(
                    model_path=MODEL_PATH,
                    experimental_delegates=[tflite.load_delegate(EDGETPU_LIB)]
                )
                CORAL_LOADED = True
                logger.info(f"Coral EdgeTPU loaded: {EDGETPU_LIB}")
            else:
                logger.warning(f"EdgeTPU library not found: {EDGETPU_LIB}")
                raise Exception("EdgeTPU not available")
        except Exception as e:
            logger.warning(f"Coral EdgeTPU failed: {e}, falling back to CPU")
            interpreter = tflite.Interpreter(model_path=MODEL_PATH)
            CORAL_LOADED = False
            
        interpreter.allocate_tensors()
        logger.info(f"Model loaded: {MODEL_PATH}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize model: {e}")
        return False

def extract_embedding(image_path):
    if interpreter is None:
        return None
        
    try:
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Failed to load image: {image_path}")
            return None
            
        # Preprocess: 224x224, RGB, normalized
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (224, 224))
        img_normalized = img_resized.astype(np.float32) / 255.0
        img_batch = np.expand_dims(img_normalized, axis=0)
        
        # Inference
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        interpreter.set_tensor(input_details[0]["index"], img_batch)
        interpreter.invoke()
        
        embedding = interpreter.get_tensor(output_details[0]["index"])
        return embedding.flatten()
        
    except Exception as e:
        logger.error(f"Embedding extraction failed: {e}")
        return None

def match_art(embedding, top_k=5):
    try:
        import faiss
        
        if not os.path.exists(FAISS_INDEX_PATH):
            logger.error(f"FAISS index not found: {FAISS_INDEX_PATH}")
            return None
            
        index = faiss.read_index(FAISS_INDEX_PATH)
        logger.info(f"FAISS index loaded: {index.ntotal} vectors")
        
        # Search
        query = np.array([embedding], dtype=np.float32)
        distances, indices = index.search(query, top_k)
        
        # Convert to results
        results = []
        for i in range(top_k):
            distance = float(distances[0][i])
            confidence = 100.0 / (1.0 + distance)
            results.append({
                "index": int(indices[0][i]),
                "distance": distance,
                "confidence": round(confidence, 2)
            })
            
        return results
        
    except Exception as e:
        logger.error(f"FAISS matching failed: {e}")
        return None

@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "name": "BROK",
        "role": "art_recognition",
        "coral_loaded": CORAL_LOADED,
        "model_path": MODEL_PATH,
        "faiss_index": FAISS_INDEX_PATH,
        "status": "online"
    })

@app.route("/api/art/recognize", methods=["POST"])
def recognize_art():
    data = request.json
    image_path = data.get("image_path")
    top_k = data.get("top_k", 5)
    
    if not image_path:
        return jsonify({"error": "image_path required"}), 400
        
    if not os.path.exists(image_path):
        return jsonify({"error": f"Image not found: {image_path}"}), 404
        
    # Extract embedding
    embedding = extract_embedding(image_path)
    if embedding is None:
        return jsonify({"error": "Failed to extract embedding"}), 500
        
    # Match against FAISS index
    results = match_art(embedding, top_k)
    if results is None:
        return jsonify({"error": "FAISS matching failed"}), 500
        
    best_match = results[0]
    confidence = best_match["confidence"]
    
    return jsonify({
        "success": True,
        "confidence": confidence,
        "best_match": best_match,
        "all_matches": results,
        "status": "match_found" if confidence >= 95 else "low_confidence",
        "trigger_ocr": confidence < 95
    })

if __name__ == "__main__":
    logger.info("Starting BROK Art Recognition Server...")
    
    # Initialize Coral TPU
    if init_coral():
        logger.info("✅ Coral TPU initialized successfully")
    else:
        logger.error("❌ Coral TPU initialization failed")
        sys.exit(1)
        
    # Start Flask server
    app.run(host="0.0.0.0", port=5002, debug=False)
