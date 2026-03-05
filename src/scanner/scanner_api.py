#!/usr/bin/env python3
"""
Scanner API Server - Runs on ASUS
Receives scan commands from Windows mtg_core.py over network
Controls Arduino + Nikon D7500 camera
"""

from flask import Flask, jsonify, request
import serial
import time
import subprocess
from datetime import datetime
import os

app = Flask(__name__)

# Configuration
ARDUINO_PORT = '/dev/ttyACM0'
ARDUINO_BAUD = 115200
OUTPUT_DIR = '/home/danielson/Desktop/Scanner_Images'
SCRYFALL_API_KEY = '2177a4a6-4ff6-4001-aafb-8e39d610b380'

def connect_arduino():
    """Connect to Arduino"""
    try:
        arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=2)
        time.sleep(2)  # Reset delay
        # Clear startup messages
        while arduino.in_waiting:
            arduino.readline()
        return arduino
    except Exception as e:
        raise Exception(f"Arduino connection failed: {e}")

def send_arduino_command(arduino, command):
    """Send command to Arduino"""
    arduino.write(f"{command}\n".encode())
    time.sleep(0.1)
    response = arduino.readline().decode().strip()
    return response

def capture_dslr():
    """Capture image with Nikon D7500"""
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scan_{timestamp}.jpg"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    # Use gphoto2 to capture
    result = subprocess.run(
        ['gphoto2', '--capture-image-and-download', '--filename', filepath],
        capture_output=True,
        text=True
    )
    
    print(f"Camera capture attempt: returncode={result.returncode}")
    print(f"Output: {result.stdout}")
    if result.stderr:
        print(f"Errors: {result.stderr}")
    
    if result.returncode == 0 and os.path.exists(filepath):
        file_size = os.path.getsize(filepath)
        print(f"Image captured: {filepath} ({file_size} bytes)")
        return filepath
    else:
        raise Exception(f"Camera capture failed: {result.stderr}")


def detect_card_edges(image_path):
    """Detect card edges and crop to card boundary"""
    try:
        import cv2
        
        if not os.path.exists(image_path):
            print(f"Image file not found: {image_path}")
            return image_path, None
        
        img = cv2.imread(image_path)
        if img is None:
            print(f"Failed to load image: {image_path}")
            return image_path, None
        
        print(f"Image loaded: {img.shape}")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Edge detection
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        print(f"Found {len(contours)} contours")
        
        # Find largest rectangular contour (the card)
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)
            
            print(f"Largest contour: x={x}, y={y}, w={w}, h={h}")
            
            # Crop to card
            card_img = img[y:y+h, x:x+w]
            
            # Save cropped version
            cropped_path = image_path.replace('.jpg', '_cropped.jpg')
            cv2.imwrite(cropped_path, card_img)
            
            print(f"Cropped image saved: {cropped_path}")
            return cropped_path, (x, y, w, h)
        
        print("No contours found, returning original image")
        return image_path, None
    except Exception as e:
        print(f"Edge detection error: {e}")
        import traceback
        traceback.print_exc()
        return image_path, None


def ocr_card_name(image_path):
    """Extract card name using OCR"""
    try:
        import pytesseract
        import cv2
        
        if not os.path.exists(image_path):
            print(f"OCR: Image not found: {image_path}")
            return None
        
        img = cv2.imread(image_path)
        if img is None:
            print(f"OCR: Failed to load image: {image_path}")
            return None
        
        # Focus on top 20% of card where name typically is
        height = img.shape[0]
        name_region = img[0:int(height*0.2), :]
        
        # Preprocess for better OCR
        gray = cv2.cvtColor(name_region, cv2.COLOR_BGR2GRAY)
        enhanced = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
        # Extract text
        text = pytesseract.image_to_string(enhanced, config='--psm 7')
        
        # Clean up text
        card_name = text.strip().split('\n')[0]
        
        print(f"OCR extracted: '{card_name}'")
        return card_name
    except Exception as e:
        print(f"OCR error: {e}")
        import traceback
        traceback.print_exc()
        return None


def ocr_set_info(image_path):
    """Extract set code and collector number from bottom left corner"""
    try:
        import pytesseract
        import cv2
        import re
        
        if not os.path.exists(image_path):
            print(f"Set OCR: Image not found: {image_path}")
            return None, None
        
        img = cv2.imread(image_path)
        if img is None:
            print(f"Set OCR: Failed to load image: {image_path}")
            return None, None
        
        height, width = img.shape[:2]
        
        # Extract bottom left corner (last 10% height, first 40% width)
        bottom_left = img[int(height*0.90):height, 0:int(width*0.40)]
        
        # Preprocess for better OCR
        gray = cv2.cvtColor(bottom_left, cv2.COLOR_BGR2GRAY)
        # Use adaptive threshold for varying lighting
        enhanced = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY, 11, 2)
        
        # Extract text
        text = pytesseract.image_to_string(enhanced, config='--psm 6')
        
        print(f"Set region text: '{text.strip()}'")
        
        # Parse set code and collector number
        # Format examples: "NEO 123", "BRO 45", "MOM 267"
        # Some cards: "123/456" or "NEO・123"
        
        set_code = None
        collector_number = None
        
        # Try to match patterns like "ABC 123" or "ABC・123"
        match = re.search(r'([A-Z]{3})[・\s]+(\d+)', text)
        if match:
            set_code = match.group(1)
            collector_number = match.group(2)
        else:
            # Try standalone 3-letter code
            set_match = re.search(r'\b([A-Z]{3})\b', text)
            if set_match:
                set_code = set_match.group(1)
            
            # Try standalone number
            num_match = re.search(r'\b(\d{1,4})\b', text)
            if num_match:
                collector_number = num_match.group(1)
        
        print(f"Extracted: Set='{set_code}', Number='{collector_number}'")
        return set_code, collector_number
        
    except Exception as e:
        print(f"Set OCR error: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def extract_set_symbol(image_path):
    """Extract set symbol region from right-center of card for visual matching"""
    try:
        import cv2
        
        if not os.path.exists(image_path):
            print(f"Symbol extraction: Image not found: {image_path}")
            return None
        
        img = cv2.imread(image_path)
        if img is None:
            print(f"Symbol extraction: Failed to load image: {image_path}")
            return None
        
        height, width = img.shape[:2]
        
        # Extract right-center region where set symbol is located
        # Typically at 85-95% width, 45-55% height
        symbol_region = img[int(height*0.45):int(height*0.55),
                           int(width*0.85):int(width*0.95)]
        
        # Save symbol region for reference/debugging
        symbol_path = image_path.replace('.jpg', '_symbol.jpg')
        cv2.imwrite(symbol_path, symbol_region)
        
        print(f"Set symbol region saved: {symbol_path}")
        
        # Return path to symbol image for future ML-based symbol recognition
        return symbol_path
        
    except Exception as e:
        print(f"Symbol extraction error: {e}")
        import traceback
        traceback.print_exc()
        return None


def extract_artwork_region(image_path):
    """Extract main artwork area for perceptual hash matching"""
    try:
        import cv2
        
        if not os.path.exists(image_path):
            print(f"Artwork extraction: Image not found: {image_path}")
            return None, None
        
        img = cv2.imread(image_path)
        if img is None:
            print(f"Artwork extraction: Failed to load image: {image_path}")
            return None, None
        
        height, width = img.shape[:2]
        
        # Extract artwork region (typically top 55% of card, center 80%)
        # Skip top 15% (card name) and bottom 30% (text box)
        artwork_region = img[int(height*0.15):int(height*0.55),
                            int(width*0.10):int(width*0.90)]
        
        # Save artwork region
        artwork_path = image_path.replace('.jpg', '_artwork.jpg')
        cv2.imwrite(artwork_path, artwork_region)
        
        # Calculate perceptual hash (pHash) for artwork matching
        # Resize to 32x32 for consistent hashing
        gray = cv2.cvtColor(artwork_region, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
        
        # Compute DCT (Discrete Cosine Transform)
        import numpy as np
        dct = cv2.dct(np.float32(resized))
        
        # Extract top-left 8x8 corner (low frequency components)
        dct_low = dct[:8, :8]
        
        # Calculate median
        median = np.median(dct_low)
        
        # Create hash: 1 if above median, 0 if below
        phash = (dct_low > median).flatten()
        
        # Convert to hex string
        phash_hex = ''.join(['1' if bit else '0' for bit in phash])
        phash_hex = hex(int(phash_hex, 2))[2:].zfill(16)
        
        print(f"Artwork region saved: {artwork_path}")
        print(f"Perceptual hash: {phash_hex}")
        
        return artwork_path, phash_hex
        
    except Exception as e:
        print(f"Artwork extraction error: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def compare_artwork_hash(hash1, hash2):
    """Compare two perceptual hashes using Hamming distance"""
    try:
        if not hash1 or not hash2:
            return None
        
        # Convert hex to binary
        bin1 = bin(int(hash1, 16))[2:].zfill(64)
        bin2 = bin(int(hash2, 16))[2:].zfill(64)
        
        # Calculate Hamming distance (number of different bits)
        distance = sum(c1 != c2 for c1, c2 in zip(bin1, bin2))
        
        # Calculate similarity percentage
        similarity = (64 - distance) / 64 * 100
        
        print(f"Artwork similarity: {similarity:.1f}% (distance: {distance})")
        
        return similarity
        
    except Exception as e:
        print(f"Hash comparison error: {e}")
        return None


def search_scryfall(card_name, set_code=None):
    """Search Scryfall API for card data with optional set filtering"""
    try:
        import requests
        
        url = "https://nexus-cards.com/api/cards/search"
        params = {'name': card_name}
        
        # Add set code filter if available for exact match
        if set_code:
            params['set'] = set_code.lower()
        
        headers = {'Authorization': f'Bearer {SCRYFALL_API_KEY}'}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'name': data.get('name'),
                'set': data.get('set_name'),
                'set_code': data.get('set'),
                'collector_number': data.get('collector_number'),
                'mana_cost': data.get('mana_cost'),
                'type': data.get('type_line'),
                'rarity': data.get('rarity'),
                'price_usd': data.get('prices', {}).get('usd'),
                'image_url': data.get('image_uris', {}).get('normal'),
                'scryfall_id': data.get('id')
            }
        
        return None
    except Exception as e:
        print(f"Scryfall error: {e}")
        return None


@app.route('/scan', methods=['POST'])
def scan_card():
    """Scan a card - full automated sequence with edge detection, OCR, and Scryfall"""
    arduino = None
    
    try:
        # Connect to Arduino
        print("🔌 Connecting to Arduino...")
        arduino = connect_arduino()
        
        # Lights off (baseline)
        print("💡 Setting lights OFF...")
        send_arduino_command(arduino, 'OFF')
        time.sleep(0.3)
        
        # Set brightness and color
        print("💡 Setting brightness B255...")
        send_arduino_command(arduino, 'B255')
        print("💡 Setting color C255,255,255...")
        send_arduino_command(arduino, 'C255,255,255')
        
        # Lights on
        print("💡 Turning lights ON...")
        send_arduino_command(arduino, 'ON')
        print("⏳ Waiting for camera stabilization...")
        time.sleep(2.0)  # Increased settle time for DSLR
        
        # Capture image with DSLR
        print("📷 Capturing with DSLR...")
        image_path = capture_dslr()
        print(f"✅ Image saved: {image_path}")
        
        # Check if image file exists and has size
        if os.path.exists(image_path):
            file_size = os.path.getsize(image_path)
            print(f"📁 File size: {file_size} bytes")
        else:
            print(f"❌ Image file not found: {image_path}")
        
        # Lights off
        print("💡 Turning lights OFF...")
        send_arduino_command(arduino, 'OFF')
        
        # Edge detection to crop card
        print("✂️ Detecting edges...")
        cropped_path, bbox = detect_card_edges(image_path)
        
        # OCR to extract card name
        print("🔍 Running OCR for card name...")
        card_name = ocr_card_name(cropped_path)
        print(f"🎴 Detected name: {card_name}")
        
        # OCR to extract set code and collector number
        print("🔍 Running OCR for set info...")
        set_code, collector_number = ocr_set_info(cropped_path)
        print(f"📦 Detected set: {set_code}, Number: {collector_number}")
        
        # Extract set symbol region
        print("🔍 Extracting set symbol...")
        symbol_path = extract_set_symbol(cropped_path)
        
        # Extract artwork region and calculate perceptual hash
        print("🎨 Extracting artwork for visual matching...")
        artwork_path, artwork_hash = extract_artwork_region(cropped_path)
        
        # Scryfall lookup with enhanced matching
        scryfall_data = None
        if card_name:
            print(f"🌐 Querying nexus-cards.com for: {card_name}")
            if set_code:
                print(f"   Using set filter: {set_code}")
            time.sleep(0.1)  # Rate limiting
            scryfall_data = search_scryfall(card_name, set_code)
            if scryfall_data:
                print("✅ Found card data")
                # Verify set code matches if we have both
                if set_code and scryfall_data.get('set_code'):
                    api_set = scryfall_data.get('set_code', '').upper()
                    if set_code.upper() == api_set:
                        print(f"✅ Set verified: {set_code}")
                    else:
                        print(f"⚠️ Set mismatch: OCR={set_code}, API={api_set}")
                
                # TODO: Compare artwork_hash with Scryfall image hash
                # This requires downloading reference image and hashing it
                # For now, artwork_hash is stored for future ML/matching
            else:
                print("⚠️ No data found")
        
        return jsonify({
            'success': True,
            'message': 'Card scanned with multi-region OCR and artwork hash',
            'image_path': image_path,
            'cropped_path': cropped_path,
            'symbol_path': symbol_path,
            'artwork_path': artwork_path,
            'artwork_hash': artwork_hash,
            'card_name': card_name,
            'set_code': set_code,
            'collector_number': collector_number,
            'scryfall_data': scryfall_data,
            'bbox': bbox,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        
    finally:
        if arduino:
            arduino.close()

@app.route('/status', methods=['GET'])
def get_status():
    """Check scanner system status"""
    status = {
        'arduino': False,
        'camera': False
    }
    
    # Check Arduino
    try:
        arduino = connect_arduino()
        status['arduino'] = True
        arduino.close()
    except:
        pass
    
    # Check camera
    result = subprocess.run(['gphoto2', '--auto-detect'], capture_output=True)
    if b'Nikon' in result.stdout:
        status['camera'] = True
    
    return jsonify(status)

@app.route('/test_lights', methods=['POST'])
def test_lights():
    """Test Arduino lights"""
    arduino = None
    try:
        arduino = connect_arduino()
        send_arduino_command(arduino, 'TEST')
        return jsonify({'success': True, 'message': 'Rainbow test running'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if arduino:
            arduino.close()

if __name__ == '__main__':
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("🚀 MTG Scanner API Server Starting...")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print(f"🔌 Arduino port: {ARDUINO_PORT}")
    print(f"📷 Camera: gphoto2")
    print(f"🌐 Listening on http://0.0.0.0:5000")
    print("\nEndpoints:")
    print("  POST /scan - Scan a card")
    print("  GET /status - Check system status")
    print("  POST /test_lights - Test LED lights")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
