"""
\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557
\u2551                    NEXUS V2 - CARD IMAGE TOOLTIP                             \u2551
\u2551                                                                              \u2551
\u2551   Hover-to-preview card images from Scryfall                                 \u2551
\u2551   Caches images locally for performance                                      \u2551
\u2551                                                                              \u2551
\u2551   \ud83c\udfce\ufe0f LEXUS \u2192 LAMBO: Instant visual feedback \ud83c\udfce\ufe0f                               \u2551
\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import urllib.request
import io
import os
import hashlib
from pathlib import Path
from typing import Optional, Dict, Callable
import threading
import logging

logger = logging.getLogger(__name__)


class CardImageTooltip:
    """
    Tooltip that shows card image on hover
    
    Features:
    - Async image loading (non-blocking)
    - Local disk caching
    - Memory caching for recent images
    - Smooth show/hide transitions
    - Follows mouse position
    """
    
    # Cache directory
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "image_cache"
    
    # Image dimensions
    TOOLTIP_WIDTH = 250
    TOOLTIP_HEIGHT = 350
    
    # Timing
    SHOW_DELAY_MS = 300  # Delay before showing
    HIDE_DELAY_MS = 100  # Delay before hiding
    
    def __init__(self, parent: tk.Widget):
        self.parent = parent
        self.tooltip_window: Optional[tk.Toplevel] = None
        self.current_image: Optional[ImageTk.PhotoImage] = None
        self.image_label: Optional[tk.Label] = None
        self.loading_label: Optional[tk.Label] = None
        
        # Memory cache (most recent N images)
        self._memory_cache: Dict[str, ImageTk.PhotoImage] = {}
        self._cache_order: list = []
        self._max_memory_cache = 50
        
        # Pending operations
        self._show_after_id: Optional[str] = None
        self._hide_after_id: Optional[str] = None
        self._current_url: Optional[str] = None
        
        # Ensure cache directory exists
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"CardImageTooltip initialized, cache at {self.CACHE_DIR}")


    def show(self, event: tk.Event, image_url: str, card_name: str = ""):
        """Schedule tooltip to show after delay"""
        # Cancel any pending hide
        if self._hide_after_id:
            self.parent.after_cancel(self._hide_after_id)
            self._hide_after_id = None
        
        # If already showing this URL, don't restart
        if self._current_url == image_url and self.tooltip_window:
            return
        
        self._current_url = image_url
        
        # Cancel pending show and reschedule
        if self._show_after_id:
            self.parent.after_cancel(self._show_after_id)
        
        self._show_after_id = self.parent.after(
            self.SHOW_DELAY_MS,
            lambda: self._do_show(event, image_url, card_name)
        )
    
    def hide(self, event: tk.Event = None):
        """Schedule tooltip to hide after delay"""
        # Cancel pending show
        if self._show_after_id:
            self.parent.after_cancel(self._show_after_id)
            self._show_after_id = None
        
        # Schedule hide
        if self._hide_after_id:
            self.parent.after_cancel(self._hide_after_id)
        
        self._hide_after_id = self.parent.after(
            self.HIDE_DELAY_MS,
            self._do_hide
        )
    
    def _do_show(self, event: tk.Event, image_url: str, card_name: str):
        """Actually show the tooltip"""
        self._show_after_id = None
        
        if not image_url:
            return
        
        # Create tooltip window
        if self.tooltip_window:
            self.tooltip_window.destroy()
        
        self.tooltip_window = tk.Toplevel(self.parent)
        self.tooltip_window.wm_overrideredirect(True)  # No window decorations
        self.tooltip_window.wm_attributes('-topmost', True)
        
        # Dark background
        self.tooltip_window.configure(bg='#1a1a2e')
        
        # Frame with border
        frame = tk.Frame(
            self.tooltip_window,
            bg='#1a1a2e',
            highlightbackground='#4a4a6a',
            highlightthickness=2
        )
        frame.pack(fill='both', expand=True, padx=2, pady=2)
        
        # Card name label
        if card_name:
            name_label = tk.Label(
                frame,
                text=card_name,
                bg='#1a1a2e',
                fg='#ffffff',
                font=('Segoe UI', 9, 'bold'),
                wraplength=self.TOOLTIP_WIDTH - 10
            )
            name_label.pack(pady=(5, 2))
        
        # Image label (or loading)
        self.image_label = tk.Label(
            frame,
            bg='#1a1a2e',
            width=self.TOOLTIP_WIDTH,
            height=self.TOOLTIP_HEIGHT
        )
        self.image_label.pack(pady=5)
        
        # Position tooltip
        x = event.x_root + 20
        y = event.y_root + 10
        
        # Keep on screen
        screen_width = self.parent.winfo_screenwidth()
        screen_height = self.parent.winfo_screenheight()
        
        if x + self.TOOLTIP_WIDTH + 30 > screen_width:
            x = event.x_root - self.TOOLTIP_WIDTH - 30
        if y + self.TOOLTIP_HEIGHT + 50 > screen_height:
            y = screen_height - self.TOOLTIP_HEIGHT - 60
        
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        # Load image (async)
        self._load_image(image_url)


    def _do_hide(self):
        """Actually hide the tooltip"""
        self._hide_after_id = None
        self._current_url = None
        
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
    
    def _load_image(self, url: str):
        """Load image from cache or network"""
        # Check memory cache first
        if url in self._memory_cache:
            self._display_image(self._memory_cache[url])
            return
        
        # Check disk cache
        cache_path = self._get_cache_path(url)
        if cache_path.exists():
            try:
                img = Image.open(cache_path)
                self._process_and_display(img, url)
                return
            except Exception as e:
                logger.warning(f"Failed to load cached image: {e}")
        
        # Show loading indicator
        if self.image_label:
            self.image_label.configure(text="Loading...", fg='#888888')
        
        # Fetch from network (async)
        thread = threading.Thread(
            target=self._fetch_image,
            args=(url,),
            daemon=True
        )
        thread.start()
    
    def _fetch_image(self, url: str):
        """Fetch image from URL (runs in thread)"""
        try:
            # Add headers to avoid 403
            request = urllib.request.Request(
                url,
                headers={'User-Agent': 'NEXUS-V2/1.0'}
            )
            
            with urllib.request.urlopen(request, timeout=10) as response:
                data = response.read()
            
            # Save to disk cache
            cache_path = self._get_cache_path(url)
            with open(cache_path, 'wb') as f:
                f.write(data)
            
            # Load and display
            img = Image.open(io.BytesIO(data))
            
            # Schedule display on main thread
            self.parent.after(0, lambda: self._process_and_display(img, url))
            
        except Exception as e:
            logger.warning(f"Failed to fetch image from {url}: {e}")
            self.parent.after(0, lambda: self._show_error())
    
    def _process_and_display(self, img: Image.Image, url: str):
        """Process image and display in tooltip"""
        try:
            # Resize to fit tooltip
            img.thumbnail((self.TOOLTIP_WIDTH, self.TOOLTIP_HEIGHT), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # Add to memory cache
            self._add_to_memory_cache(url, photo)
            
            # Display
            self._display_image(photo)
            
        except Exception as e:
            logger.warning(f"Failed to process image: {e}")
            self._show_error()
    
    def _display_image(self, photo: ImageTk.PhotoImage):
        """Display image in tooltip"""
        if self.image_label and self.tooltip_window:
            self.image_label.configure(image=photo, text='')
            self.image_label.image = photo  # Keep reference
    
    def _show_error(self):
        """Show error message in tooltip"""
        if self.image_label:
            self.image_label.configure(
                text="Image unavailable",
                fg='#ff6666'
            )


    def _get_cache_path(self, url: str) -> Path:
        """Get local cache path for URL"""
        # Hash URL to create filename
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.CACHE_DIR / f"{url_hash}.jpg"
    
    def _add_to_memory_cache(self, url: str, photo: ImageTk.PhotoImage):
        """Add image to memory cache with LRU eviction"""
        # Remove oldest if at capacity
        if len(self._memory_cache) >= self._max_memory_cache:
            oldest_url = self._cache_order.pop(0)
            if oldest_url in self._memory_cache:
                del self._memory_cache[oldest_url]
        
        # Add new entry
        self._memory_cache[url] = photo
        self._cache_order.append(url)
    
    def clear_cache(self, memory_only: bool = False):
        """Clear image cache"""
        # Clear memory
        self._memory_cache.clear()
        self._cache_order.clear()
        
        # Clear disk
        if not memory_only:
            try:
                for f in self.CACHE_DIR.glob("*.jpg"):
                    f.unlink()
                logger.info("Image cache cleared")
            except Exception as e:
                logger.warning(f"Failed to clear disk cache: {e}")
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        disk_count = len(list(self.CACHE_DIR.glob("*.jpg")))
        disk_size = sum(f.stat().st_size for f in self.CACHE_DIR.glob("*.jpg"))
        
        return {
            "memory_cached": len(self._memory_cache),
            "disk_cached": disk_count,
            "disk_size_mb": round(disk_size / (1024 * 1024), 2)
        }


class TreeviewImageTooltip(CardImageTooltip):
    """
    Image tooltip specifically for Treeview widgets
    
    Tracks which row is being hovered and shows appropriate image.
    """
    
    def __init__(self, treeview: ttk.Treeview, get_image_url: Callable):
        """
        Args:
            treeview: The Treeview widget to attach to
            get_image_url: Function(item_id) -> (url, name) to get image URL for item
        """
        super().__init__(treeview)
        self.treeview = treeview
        self.get_image_url = get_image_url
        self._current_item: Optional[str] = None
        
        # Bind events
        self.treeview.bind('<Motion>', self._on_motion)
        self.treeview.bind('<Leave>', self._on_leave)
    
    def _on_motion(self, event: tk.Event):
        """Handle mouse motion over treeview"""
        # Find item under cursor
        item = self.treeview.identify_row(event.y)
        
        if item and item != self._current_item:
            self._current_item = item
            
            # Get image URL for this item
            result = self.get_image_url(item)
            if result:
                url, name = result
                if url:
                    self.show(event, url, name)
                else:
                    self.hide(event)
            else:
                self.hide(event)
        elif not item:
            self._current_item = None
            self.hide(event)
    
    def _on_leave(self, event: tk.Event):
        """Handle mouse leaving treeview"""
        self._current_item = None
        self.hide(event)


# For testing
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Image Tooltip Test")
    root.geometry("400x300")
    
    tooltip = CardImageTooltip(root)
    
    # Test button
    btn = tk.Button(root, text="Hover for Lightning Bolt")
    btn.pack(pady=20)
    
    test_url = "https://cards.scryfall.io/normal/front/e/3/e3285e6b-3e79-4d7c-bf96-d920f973b122.jpg"
    btn.bind('<Enter>', lambda e: tooltip.show(e, test_url, "Lightning Bolt"))
    btn.bind('<Leave>', lambda e: tooltip.hide(e))
    
    root.mainloop()
