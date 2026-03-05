#!/usr/bin/env python3
"""
Card Recognition Confirmation GUI
100% Accuracy Failsafe System - Visual verification for every scan
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2
import os
from typing import Dict, Optional, Callable

# Import similar card detector
try:
    from similar_card_detector import SimilarCardDetector
    SIMILAR_DETECTOR_AVAILABLE = True
except ImportError:
    SIMILAR_DETECTOR_AVAILABLE = False
    print("INFO: Similar card detector not available")


class RecognitionConfirmationDialog:
    """
    Visual confirmation dialog for card recognition
    Shows card image alongside recognized name with user override options
    """
    
    def __init__(self, parent, card_image, recognition_result: Dict, 
                 on_confirm: Callable, on_reject: Callable, on_manual: Callable,
                 similar_detector: Optional['SimilarCardDetector'] = None):
        """
        Args:
            parent: Parent tkinter window
            card_image: OpenCV image (BGR format)
            recognition_result: Dict with keys: card_name, confidence, matches
            on_confirm: Callback when user confirms (called with card_name)
            on_reject: Callback when user rejects
            on_manual: Callback for manual entry (called with corrected name)
            similar_detector: Optional SimilarCardDetector for variant detection
        """
        self.parent = parent
        self.card_image = card_image
        self.result = recognition_result
        self.on_confirm = on_confirm
        self.on_reject = on_reject
        self.on_manual = on_manual
        self.similar_detector = similar_detector
        self.user_choice = None
        
        # Create modal dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Confirm Card Recognition")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Build UI
        self._build_ui()
        
        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        # Auto-confirm if confidence is very high (>95%)
        if recognition_result.get('confidence', 0) >= 0.95:
            self.dialog.after(2000, self._auto_confirm)  # Auto-confirm after 2 seconds
            self.countdown_label.config(text="Auto-confirming in 2 seconds... (Click to override)")
            self._start_countdown(2)
    
    def _build_ui(self):
        """Build the confirmation interface"""
        # Main container
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top section: Image and Recognition side-by-side
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Left: Card Image
        image_frame = ttk.LabelFrame(content_frame, text="Captured Image", padding=10)
        image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.image_label = ttk.Label(image_frame)
        self.image_label.pack(fill=tk.BOTH, expand=True)
        self._display_image()
        
        # Right: Recognition Result
        result_frame = ttk.LabelFrame(content_frame, text="Recognition Result", padding=10)
        result_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Card name (large, bold)
        card_name = self.result.get('card_name', 'Unknown')
        name_label = tk.Label(result_frame, text=card_name, font=('Arial', 18, 'bold'),
                             fg='#2c3e50', wraplength=300)
        name_label.pack(pady=10)
        
        # Confidence indicator
        confidence = self.result.get('confidence', 0)
        confidence_color = self._get_confidence_color(confidence)
        confidence_text = f"Confidence: {confidence:.1%}"
        confidence_label = tk.Label(result_frame, text=confidence_text, 
                                   font=('Arial', 14), fg=confidence_color)
        confidence_label.pack(pady=5)
        
        # Progress bar for confidence
        progress = ttk.Progressbar(result_frame, length=300, mode='determinate',
                                  value=confidence * 100)
        progress.pack(pady=10)
        
        # Method used
        method = self.result.get('method', 'unknown')
        method_label = ttk.Label(result_frame, text=f"Method: {method}",
                                font=('Arial', 10, 'italic'))
        method_label.pack(pady=5)
        
        # Processing time
        proc_time = self.result.get('processing_time', 0)
        time_label = ttk.Label(result_frame, text=f"Time: {proc_time:.2f}s",
                              font=('Arial', 10))
        time_label.pack(pady=5)
        
        # Alternative matches (if confidence < 90%)
        if confidence < 0.90 and self.result.get('matches'):
            alt_frame = ttk.LabelFrame(result_frame, text="Alternative Matches", padding=5)
            alt_frame.pack(fill=tk.X, pady=10)
            
            for i, match in enumerate(self.result['matches'][:3], 1):
                match_btn = ttk.Button(
                    alt_frame,
                    text=f"{i}. {match['name']} ({match['score']:.1%})",
                    command=lambda m=match['name']: self._select_alternative(m)
                )
                match_btn.pack(fill=tk.X, pady=2)
        
        # Check for similar cards/variants
        if self.similar_detector and self.similar_detector.needs_disambiguation(card_name):
            variant_frame = ttk.LabelFrame(result_frame, text="⚠️ Multiple Versions Exist", padding=5)
            variant_frame.pack(fill=tk.X, pady=10)
            
            info_label = ttk.Label(variant_frame, 
                                  text="This card has multiple versions. Select correct one:",
                                  font=('Arial', 9), foreground='#e74c3c')
            info_label.pack(pady=5)
            
            options = self.similar_detector.get_disambiguation_options(card_name)
            for opt in options[:5]:  # Show max 5 variants
                variant_btn = ttk.Button(
                    variant_frame,
                    text=f"📦 {opt['display_name']}",
                    command=lambda name=opt['name']: self._select_variant(name)
                )
                variant_btn.pack(fill=tk.X, pady=2)
        
        # Countdown label (for auto-confirm)
        self.countdown_label = ttk.Label(main_frame, text="", font=('Arial', 10, 'italic'))
        self.countdown_label.pack(pady=5)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Confirm button (green)
        confirm_btn = tk.Button(button_frame, text="✅ CORRECT", font=('Arial', 14, 'bold'),
                               bg='#27ae60', fg='white', relief=tk.RAISED, bd=3,
                               padx=20, pady=10, command=self._confirm)
        confirm_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        # Wrong button (red)
        reject_btn = tk.Button(button_frame, text="❌ WRONG", font=('Arial', 14, 'bold'),
                              bg='#e74c3c', fg='white', relief=tk.RAISED, bd=3,
                              padx=20, pady=10, command=self._reject)
        reject_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        # Manual entry button (blue)
        manual_btn = tk.Button(button_frame, text="⌨️ MANUAL", font=('Arial', 14, 'bold'),
                              bg='#3498db', fg='white', relief=tk.RAISED, bd=3,
                              padx=20, pady=10, command=self._manual_entry)
        manual_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        # Keyboard shortcuts
        self.dialog.bind('<Return>', lambda e: self._confirm())
        self.dialog.bind('<Escape>', lambda e: self._reject())
        self.dialog.bind('<space>', lambda e: self._manual_entry())
        
        # Help text
        help_text = "Shortcuts: Enter=Confirm | Esc=Wrong | Space=Manual"
        help_label = ttk.Label(main_frame, text=help_text, font=('Arial', 9, 'italic'),
                              foreground='gray')
        help_label.pack(pady=5)
    
    def _display_image(self):
        """Display the captured card image"""
        # Convert OpenCV BGR to RGB
        rgb_image = cv2.cvtColor(self.card_image, cv2.COLOR_BGR2RGB)
        
        # Resize to fit display (maintain aspect ratio)
        height, width = rgb_image.shape[:2]
        max_height = 400
        if height > max_height:
            scale = max_height / height
            new_width = int(width * scale)
            rgb_image = cv2.resize(rgb_image, (new_width, max_height))
        
        # Convert to PIL Image
        pil_image = Image.fromarray(rgb_image)
        
        # Convert to PhotoImage
        self.photo = ImageTk.PhotoImage(pil_image)
        self.image_label.config(image=self.photo)
    
    def _get_confidence_color(self, confidence: float) -> str:
        """Get color based on confidence level"""
        if confidence >= 0.90:
            return '#27ae60'  # Green
        elif confidence >= 0.70:
            return '#f39c12'  # Orange
        else:
            return '#e74c3c'  # Red
    
    def _confirm(self):
        """User confirms recognition is correct"""
        self.user_choice = 'confirm'
        card_name = self.result.get('card_name', 'Unknown')
        self.dialog.destroy()
        self.on_confirm(card_name)
    
    def _reject(self):
        """User rejects recognition"""
        self.user_choice = 'reject'
        self.dialog.destroy()
        self.on_reject()
    
    def _manual_entry(self):
        """User wants to manually enter card name"""
        from tkinter import simpledialog
        
        card_name = simpledialog.askstring(
            "Manual Card Entry",
            "Enter the card name:",
            initialvalue=self.result.get('card_name', ''),
            parent=self.dialog
        )
        
        if card_name:
            self.user_choice = 'manual'
            self.dialog.destroy()
            self.on_manual(card_name)
        # If cancelled, dialog stays open
    
    def _select_alternative(self, card_name: str):
        """User selected an alternative match"""
        self.user_choice = 'alternative'
        self.dialog.destroy()
        self.on_manual(card_name)  # Treat as manual correction
    
    def _select_variant(self, card_name: str):
        """User selected a specific variant"""
        self.user_choice = 'variant'
        self.dialog.destroy()
        self.on_confirm(card_name)  # Confirm with specific variant
    
    def _auto_confirm(self):
        """Auto-confirm if user doesn't intervene"""
        if self.dialog.winfo_exists():
            self._confirm()
    
    def _start_countdown(self, seconds: int):
        """Start countdown for auto-confirm"""
        def countdown(remaining):
            if remaining > 0 and self.dialog.winfo_exists():
                self.countdown_label.config(text=f"Auto-confirming in {remaining}s... (Click to override)")
                self.dialog.after(1000, countdown, remaining - 1)
        
        countdown(seconds)


def show_confirmation_dialog(parent, card_image, recognition_result: Dict,
                           similar_detector: Optional['SimilarCardDetector'] = None) -> Optional[str]:
    """
    Show confirmation dialog and return confirmed card name
    
    Args:
        parent: Parent tkinter window
        card_image: OpenCV image (BGR format)
        recognition_result: Recognition result dict
        similar_detector: Optional SimilarCardDetector for variant handling
    
    Returns:
        Confirmed card name or None if rejected
    """
    confirmed_name = [None]  # Use list to allow modification in callback
    
    def on_confirm(name):
        confirmed_name[0] = name
    
    def on_reject():
        confirmed_name[0] = None
    
    def on_manual(name):
        confirmed_name[0] = name
    
    # Create and show dialog
    dialog = RecognitionConfirmationDialog(
        parent, card_image, recognition_result,
        on_confirm, on_reject, on_manual,
        similar_detector
    )
    
    # Wait for dialog to close
    parent.wait_window(dialog.dialog)
    
    return confirmed_name[0]


# Example usage
if __name__ == "__main__":
    import numpy as np
    
    # Create dummy data for testing
    root = tk.Tk()
    root.withdraw()
    
    # Dummy card image (replace with actual camera capture)
    dummy_image = np.zeros((600, 400, 3), dtype=np.uint8)
    cv2.putText(dummy_image, "Lightning Bolt", (50, 300), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
    
    # Dummy recognition result
    dummy_result = {
        'card_name': 'Lightning Bolt',
        'confidence': 0.87,
        'method': 'ocr',
        'processing_time': 0.45,
        'matches': [
            {'name': 'Lightning Bolt', 'score': 0.87},
            {'name': 'Lightning Strike', 'score': 0.72},
            {'name': 'Chain Lightning', 'score': 0.65}
        ]
    }
    
    # Show dialog
    result = show_confirmation_dialog(root, dummy_image, dummy_result)
    print(f"User confirmed: {result}")
