#!/usr/bin/env python3
"""
SNARF OCR API SERVER
Flask endpoint for NEXUS pipeline orchestration
Port: 5001
"""
import os
import sys
from flask import Flask, request, jsonify
from datetime import datetime

# Import the enhanced OCR pipeline
sys.path.insert(0, '/home/nexus1')
from snarf_ocr_enhanced import ocr_pipeline

app = Flask(__name__)


@app.route('/status', methods=['GET'])
def status():
    """Health check endpoint"""
    return jsonify({
        'name': 'SNARF',
        'role': 'ocr_processing',
        'status': 'online',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/ocr', methods=['POST'])
def ocr_recognize():
    """
    OCR Recognition Endpoint
    
    POST /api/ocr
    {
        "image_path": "/mnt/scans/card.jpg"
    }
    
    Returns:
    {
        "success": true,
        "set_code": "LTR",
        "collector_number": "245",
        "card_name": "Lightning Bolt",
        "set_confidence": 98.5,
        "name_confidence": 97.2,
        "overall_confidence": 97.85,
        "approved": true,
        "method": "gpu"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'image_path' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing image_path parameter'
            }), 400
        
        image_path = data['image_path']
        
        # Verify file exists
        if not os.path.exists(image_path):
            return jsonify({
                'success': False,
                'error': f'Image not found: {image_path}'
            }), 404
        
        # Run OCR pipeline
        result = ocr_pipeline(image_path)
        
        # Check for pipeline errors
        if 'error' in result:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
        
        # Success response
        return jsonify({
            'success': True,
            **result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("="*60)
    print("SNARF OCR API SERVER")
    print("="*60)
    print("Name:     SNARF")
    print("Role:     OCR Processing")
    print("Port:     5001")
    print("Endpoint: POST /api/ocr")
    print("Status:   GET /status")
    print("="*60)
    
    app.run(host='0.0.0.0', port=5001, debug=False)
