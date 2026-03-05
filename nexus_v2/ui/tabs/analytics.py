"""
NEXUS V2 Analytics Tab
======================
Business intelligence and collection analytics
"""

import tkinter as tk
from tkinter import ttk


class AnalyticsTab:
    """Analytics and Business Intelligence Tab"""

    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.library = kwargs.get('library')
        self.theme = kwargs.get('theme')
        self.colors = kwargs.get('colors')
        self.shop_personality = kwargs.get('shop_personality')

        if parent:
            self._create_ui()

    def _create_ui(self):
        """Create the analytics UI"""
        # Main container
        container = tk.Frame(self.parent, bg=self.colors.bg_dark)
        container.pack(fill='both', expand=True)

        # Header (fixed at top)
        header = tk.Frame(container, bg=self.colors.bg_surface)
        header.pack(fill='x', padx=10, pady=10)

        tk.Label(
            header,
            text="Analytics & Business Intelligence",
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface
        ).pack(pady=15, padx=20, anchor='w')

        # Scrollable content area
        canvas = tk.Canvas(container, bg=self.colors.bg_dark, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient='vertical', command=canvas.yview)
        main_frame = tk.Frame(canvas, bg=self.colors.bg_dark)

        main_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=main_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True, padx=10)

        # Mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Stats panel
        stats_frame = tk.Frame(main_frame, bg=self.colors.bg_surface)
        stats_frame.pack(fill='x', pady=5)

        # Get stats from library
        card_count = len(self.library) if self.library else 0
        box_count = len(self.library.box_inventory) if self.library else 0

        stats = [
            ("Total Cards", f"{card_count:,}"),
            ("Total Boxes", str(box_count)),
            ("Estimated Value", "$0.00"),
            ("Avg Card Value", "$0.00"),
        ]

        stats_inner = tk.Frame(stats_frame, bg=self.colors.bg_surface)
        stats_inner.pack(pady=15, padx=20)

        for i, (label, value) in enumerate(stats):
            col = tk.Frame(stats_inner, bg=self.colors.bg_surface)
            col.pack(side='left', padx=30)

            tk.Label(
                col,
                text=value,
                font=('Segoe UI', 20, 'bold'),
                fg=self.colors.accent,
                bg=self.colors.bg_surface
            ).pack()

            tk.Label(
                col,
                text=label,
                font=('Segoe UI', 10),
                fg=self.colors.text_secondary,
                bg=self.colors.bg_surface
            ).pack()

        # Shop Personality Section
        if self.shop_personality:
            personality_frame = tk.Frame(main_frame, bg=self.colors.bg_surface)
            personality_frame.pack(fill='x', pady=10)

            tk.Label(
                personality_frame,
                text="Shop Personality Insights (Patent Claim 4)",
                font=('Segoe UI', 12, 'bold'),
                fg=self.colors.text_primary,
                bg=self.colors.bg_surface
            ).pack(pady=10, padx=20, anchor='w')

            profile = self.shop_personality.personality
            insights_text = f"""
            Shop: {self.shop_personality.shop_name}
            Adaptation Level: {self.shop_personality.get_adaptation_level()}
            Days Active: {profile.get('days_active', 0)}
            Top Format: {profile.get('top_format', 'N/A')}
            Customer Type: {profile.get('customer_type', 'mixed').title()}
            Target Margin: {profile.get('target_margin', 0.3) * 100:.0f}%
            """

            tk.Label(
                personality_frame,
                text=insights_text,
                font=('Consolas', 10),
                fg=self.colors.text_secondary,
                bg=self.colors.bg_surface,
                justify='left'
            ).pack(pady=5, padx=20, anchor='w')

        # Placeholder for charts
        charts_frame = tk.Frame(main_frame, bg=self.colors.bg_surface)
        charts_frame.pack(fill='both', expand=True, pady=10)

        tk.Label(
            charts_frame,
            text="Charts and visualizations coming soon...\n\n"
                 "Features planned:\n"
                 "- Collection value over time\n"
                 "- Rarity distribution\n"
                 "- Set breakdown\n"
                 "- Price trend analysis\n"
                 "- Meta analysis",
            font=('Segoe UI', 11),
            fg=self.colors.text_muted,
            bg=self.colors.bg_surface,
            justify='center'
        ).pack(expand=True)
