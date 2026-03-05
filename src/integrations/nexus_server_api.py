"""
NEXUS Server API
Receives images from scanner stations and returns card identifications
Uses existing NEXUS AI systems for card recognition
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np

# Import existing NEXUS modules (adjust paths as needed)
# import ai_card_recognition
# import scryfall_integration

app = Flask(__name__)
CORS(app)  # Enable cross-origin requests

# Configuration
UPLOAD_FOLDER = Path('scanner_uploads')
UPLOAD_FOLDER.mkdir(exist_ok=True)

API_KEY = os.environ.get('NEXUS_API_KEY', None)  # Optional security


def verify_api_key():
    """Verify API key if enabled"""
    if not API_KEY:
        return True
    
    key = request.headers.get('X-API-Key')
    return key == API_KEY


@app.route('/api/ping', methods=['GET'])
def ping():
    """Health check endpoint"""
    return jsonify({
        'status': 'online',
        'server': 'NEXUS',
        'version': '1.0',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/identify', methods=['POST'])
def identify_card():
    """
    Identify card from uploaded image
    Returns: JSON with card data
    """
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Check if image was uploaded
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    
    try:
        # Save uploaded image
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f"card_{timestamp}.jpg"
        filepath = UPLOAD_FOLDER / filename
        file.save(str(filepath))
        
        print(f"[API] Received image: {filename}")
        
        # TODO: Integrate with actual NEXUS AI recognition
        # For now, return mock data
        result = identify_card_mock(str(filepath))
        
        return jsonify(result)
    
    except Exception as e:
        print(f"[API] Error identifying card: {e}")
        return jsonify({'error': str(e)}), 500


def identify_card_real(image_path):
    """
    Real card identification using image analysis
    Returns card data or mock if recognition fails
    """
    try:
        # Load and analyze image
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError("Could not load image")
        
        h, w = img.shape[:2]
        print(f"[AI] Analyzing image: {w}x{h} pixels")
        
        # TODO: Implement actual AI recognition here
        # For now, return image analysis results
        avg_color = img.mean(axis=(0,1))
        is_dark = avg_color.mean() < 100
        
        return {
            'name': 'Unknown Card',
            'set': 'UNK',
            'set_name': 'Unknown Set',
            'collector_number': '000',
            'rarity': 'common',
            'type': 'Unknown',
            'mana_cost': '',
            'oracle_text': 'Card recognition in progress...',
            'colors': [],
            'color_identity': [],
            'cmc': 0,
            'price_usd': '0.00',
            'price_usd_foil': None,
            'confidence': 50.0,
            'recognition_method': 'image_analysis',
            'timestamp': datetime.now().isoformat(),
            'image_path': str(image_path),
            'image_size': f'{w}x{h}',
            'avg_brightness': float(avg_color.mean()),
            'is_dark_card': bool(is_dark)
        }
    except Exception as e:
        print(f"[AI] Recognition error: {e}")
        # Return mock Black Lotus on error
        return {
            'name': 'Black Lotus (Mock)',
            'set': 'LEA',
            'set_name': 'Limited Edition Alpha',
            'collector_number': '232',
            'rarity': 'rare',
            'type': 'Artifact',
            'mana_cost': '{0}',
            'oracle_text': '{T}, Sacrifice Black Lotus: Add three mana...',
            'colors': [],
            'color_identity': [],
            'cmc': 0,
            'price_usd': '15000.00',
            'price_usd_foil': None,
            'confidence': 95.5,
            'recognition_method': 'fallback_mock',
            'timestamp': datetime.now().isoformat(),
            'image_path': str(image_path),
            'error': str(e)
        }


@app.route('/api/collection/add', methods=['POST'])
def add_to_collection():
    """
    Add identified card to collection database
    """
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        card_data = request.get_json()
        
        if not card_data:
            return jsonify({'error': 'No data provided'}), 400
        
        print(f"[API] Adding to collection: {card_data.get('name', 'Unknown')}")
        
        # TODO: Integrate with NEXUS collection system
        # - Add to nexus_library.json
        # - Update inventory CSVs
        # - Sync to cloud database
        
        # Mock success
        return jsonify({
            'success': True,
            'card_name': card_data.get('name'),
            'collection_size': 31264  # Mock count
        })
    
    except Exception as e:
        print(f"[API] Error adding to collection: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/collection/stats', methods=['GET'])
def collection_stats():
    """Get collection statistics"""
    # TODO: Pull from actual NEXUS databases
    return jsonify({
        'total_cards': 31263,
        'unique_cards': 2613,
        'total_value': 26.50,
        'last_updated': datetime.now().isoformat()
    })


@app.route('/api/scanner/register', methods=['POST'])
def register_scanner():
    """Register a new scanner station"""
    data = request.get_json()
    
    scanner_id = data.get('scanner_id', 'unknown')
    location = data.get('location', 'unknown')
    
    print(f"[API] Scanner registered: {scanner_id} at {location}")
    
    return jsonify({
        'success': True,
        'scanner_id': scanner_id,
        'api_key': API_KEY if API_KEY else 'none'
    })


@app.route('/api/sync', methods=['POST'])
def cloud_sync():
    """
    Cloud sync endpoint for multi-scanner networks
    Receives collection updates from scanners
    """
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        sync_data = request.get_json()
        
        scanner_id = sync_data.get('scanner_id')
        cards = sync_data.get('cards', [])
        
        print(f"[API] Cloud sync from {scanner_id}: {len(cards)} cards")
        
        # TODO: Implement cloud sync logic
        # - Merge collections
        # - Handle conflicts
        # - Update central database
        # - Broadcast to other scanners
        
        return jsonify({
            'success': True,
            'synced_cards': len(cards),
            'total_network_cards': 45678  # Mock
        })
    
    except Exception as e:
        print(f"[API] Sync error: {e}")
        return jsonify({'error': str(e)}), 500


def integrate_nexus_ai():
    """
    Helper function to integrate existing NEXUS AI systems
    Call this to connect to:
    - ai_card_recognition.py
    - ai_learning_engine.py
    - scryfall cache
    - OCR systems
    """
    # TODO: Import and initialize NEXUS AI modules
    pass


def start_server(host='0.0.0.0', port=5000, debug=False):
    """Start the NEXUS API server"""
    print("\n" + "="*60)
    print("NEXUS SERVER API")
    print("="*60)
    print(f"Listening on: http://{host}:{port}")
    print(f"Upload folder: {UPLOAD_FOLDER.absolute()}")
    if API_KEY:
        print("API Key authentication: ENABLED")
    else:
        print("API Key authentication: DISABLED")
    print("="*60 + "\n")
    
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    # Start server
    # Access from scanner: http://YOUR_SERVER_IP:5000
    start_server(host='0.0.0.0', port=5000, debug=False)
