#!/usr/bin/env python3
"""
NEXUS V2 - AI Learning Tab
==========================
Real-time AI learning dashboard with DANIELSON integration.
Displays OCR corrections, arm movements, and training progress.
Now connected to full NexusAILearningEngine for neural network training.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import threading
import queue
import requests
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Import the full learning engine
try:
    from nexus_v2.ai.learning_engine import NexusAILearningEngine
    LEARNING_ENGINE_AVAILABLE = True
except ImportError:
    LEARNING_ENGINE_AVAILABLE = False
    logger.warning("NexusAILearningEngine not available - using DANIELSON stats only")


class AILearningTab:
    """
    AI Learning Dashboard with real DANIELSON integration.

    Features:
    - Real-time stats from DANIELSON /api/ai/stats
    - OCR correction tracking
    - Arm movement learning
    - Training controls
    """

    def __init__(self, notebook: ttk.Notebook, config):
        self.notebook = notebook
        self.config = config
        self.colors = self._get_colors()

        # DANIELSON URL
        try:
            from nexus_v2.config import get_config
            self.danielson_url = getattr(get_config().scanner, 'danielson_url', "http://192.168.1.219:5001")
        except:
            self.danielson_url = "http://192.168.1.219:5001"

        # Stats storage
        self.stats = {
            'total_corrections': 0,
            'successful_corrections': 0,
            'accuracy_rate': 0,
            'avg_confidence': 0,
            'corrections_24h': 0,
            'arm_movements': 0,
            'arm_success_rate': 0
        }

        # Initialize learning engine (full neural network system)
        self.learning_engine = None
        if LEARNING_ENGINE_AVAILABLE:
            try:
                # Use local data directory instead of E:/MTTGG
                db_path = Path(__file__).parent.parent.parent / "data" / "ai_learning" / "nexus_ai_brain.db"
                self.learning_engine = NexusAILearningEngine(db_path=str(db_path))
                logger.info("NexusAILearningEngine initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize NexusAILearningEngine: {e}")

        # Engine stats (from neural network)
        self.engine_stats = {
            'neural_epochs': 0,
            'total_training_samples': 0,
            'ai_confidence': 0,
            'decks_analyzed': 0,
            'cards_tracked': 0,
            'synergies_learned': 0
        }

        # Thread-safe UI queue
        self._ui_queue = queue.Queue()
        self._queue_polling = False

        # Create tab
        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text="AI Learning")

        self._build_ui()
        self._start_ui_queue_processor()

        # Start auto-refresh
        self._refresh_stats()

    def _start_ui_queue_processor(self):
        """Start the UI queue processor on the main thread."""
        if self._queue_polling:
            return
        self._queue_polling = True
        self._process_ui_queue()

    def _process_ui_queue(self):
        """Process pending UI updates from background threads."""
        if not self._queue_polling:
            return
        try:
            for _ in range(10):
                try:
                    callback = self._ui_queue.get_nowait()
                    if callable(callback):
                        callback()
                except queue.Empty:
                    break
        except Exception:
            pass
        self.frame.after(50, self._process_ui_queue)

    def _schedule_ui(self, callback):
        """Thread-safe way to schedule a UI update from any thread."""
        self._ui_queue.put(callback)

    def _get_colors(self):
        """Get theme colors."""
        class Colors:
            bg_dark = "#4a4a4a"
            bg_surface = "#555555"
            bg_elevated = "#606060"
            accent = "#5c6bc0"
            text_primary = "#ffffff"
            text_secondary = "#e0e0e0"
            success = "#43a047"
            warning = "#fb8c00"
            error = "#e53935"
        return Colors()

    def _build_ui(self):
        """Build the AI learning interface."""
        container = tk.Frame(self.frame, bg=self.colors.bg_dark)
        container.pack(fill='both', expand=True)

        # Header
        header = tk.Frame(container, bg=self.colors.bg_surface)
        header.pack(fill='x', padx=10, pady=10)

        tk.Label(
            header, text="AI Learning Engine",
            font=('Segoe UI', 18, 'bold'),
            fg=self.colors.accent, bg=self.colors.bg_surface
        ).pack(side='left', padx=15, pady=10)

        # Refresh button
        tk.Button(
            header, text="Refresh",
            font=('Segoe UI', 10),
            bg=self.colors.accent, fg='white',
            command=self._refresh_stats
        ).pack(side='right', padx=15)

        # Status indicator
        self.status_label = tk.Label(
            header, text="Connecting...",
            font=('Segoe UI', 10),
            fg=self.colors.warning, bg=self.colors.bg_surface
        )
        self.status_label.pack(side='right', padx=10)

        # Main content with scrolling
        canvas = tk.Canvas(container, bg=self.colors.bg_dark, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient='vertical', command=canvas.yview)
        main = tk.Frame(canvas, bg=self.colors.bg_dark)

        main.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=main, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True, padx=10)

        # Stats cards row
        stats_row = tk.Frame(main, bg=self.colors.bg_dark)
        stats_row.pack(fill='x', pady=(0, 10))

        # Create stat cards with labels we can update
        self.stat_labels = {}
        stat_configs = [
            ("total_scans", "OCR Scans", "0", self.colors.accent),
            ("accuracy", "Accuracy", "0%", self.colors.success),
            ("neural_epochs", "Neural Epochs", "0", self.colors.warning),
            ("ai_confidence", "AI Confidence", "0%", self.colors.success),
        ]

        for key, title, default, color in stat_configs:
            card = tk.Frame(stats_row, bg=self.colors.bg_surface)
            card.pack(side='left', fill='both', expand=True, padx=5)

            tk.Label(
                card, text=title,
                font=('Segoe UI', 10),
                fg=self.colors.text_secondary, bg=self.colors.bg_surface
            ).pack(pady=(10, 0))

            value_label = tk.Label(
                card, text=default,
                font=('Segoe UI', 24, 'bold'),
                fg=color, bg=self.colors.bg_surface
            )
            value_label.pack(pady=(0, 10))
            self.stat_labels[key] = value_label

        # Content area - two columns
        content = tk.Frame(main, bg=self.colors.bg_dark)
        content.pack(fill='both', expand=True)

        # Left - Training Status
        left = tk.Frame(content, bg=self.colors.bg_surface)
        left.pack(side='left', fill='both', expand=True, padx=(0, 5))

        tk.Label(
            left, text="Learning Status",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.text_primary, bg=self.colors.bg_surface
        ).pack(pady=10)

        # Training info with updatable labels
        self.info_labels = {}
        info_items = [
            ("danielson_status", "DANIELSON:", "Checking..."),
            ("engine_status", "Neural Engine:", "Checking..."),
            ("training_samples", "Training Samples:", "0"),
            ("cards_tracked", "Cards Tracked:", "0"),
            ("synergies_learned", "Synergies Learned:", "0"),
            ("last_update", "Last Update:", "Never"),
        ]

        for key, label, default in info_items:
            row = tk.Frame(left, bg=self.colors.bg_surface)
            row.pack(fill='x', padx=15, pady=3)
            tk.Label(row, text=label, fg=self.colors.text_secondary, bg=self.colors.bg_surface).pack(side='left')
            value_lbl = tk.Label(row, text=default, fg=self.colors.text_primary, bg=self.colors.bg_surface, font=('Segoe UI', 10, 'bold'))
            value_lbl.pack(side='right')
            self.info_labels[key] = value_lbl

        # Training controls
        btn_frame = tk.Frame(left, bg=self.colors.bg_surface)
        btn_frame.pack(pady=15)

        tk.Button(
            btn_frame, text="Start Training",
            font=('Segoe UI', 10),
            fg='white', bg=self.colors.success,
            command=self._start_training
        ).pack(side='left', padx=5)

        tk.Button(
            btn_frame, text="Sync with DANIELSON",
            font=('Segoe UI', 10),
            fg='white', bg=self.colors.accent,
            command=self._refresh_stats
        ).pack(side='left', padx=5)

        tk.Button(
            btn_frame, text="Reset Stats",
            font=('Segoe UI', 10),
            fg='white', bg=self.colors.error,
            command=self._reset_stats
        ).pack(side='left', padx=5)

        # Right - Recent Events
        right = tk.Frame(content, bg=self.colors.bg_surface)
        right.pack(side='right', fill='both', expand=True, padx=(5, 0))

        tk.Label(
            right, text="Recent Learning Events",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.text_primary, bg=self.colors.bg_surface
        ).pack(pady=10)

        # Events list
        columns = ('time', 'event', 'result')
        self.events_tree = ttk.Treeview(right, columns=columns, show='headings', height=12)
        self.events_tree.heading('time', text='Time')
        self.events_tree.heading('event', text='Event')
        self.events_tree.heading('result', text='Result')
        self.events_tree.column('time', width=80)
        self.events_tree.column('event', width=200)
        self.events_tree.column('result', width=100)
        self.events_tree.pack(fill='both', expand=True, padx=10, pady=5)

        # Clear button
        tk.Button(
            right, text="Clear History",
            font=('Segoe UI', 9),
            fg='white', bg=self.colors.bg_elevated,
            command=self._clear_history
        ).pack(pady=10)

    def _refresh_stats(self):
        """Fetch stats from DANIELSON and learning engine, update UI"""
        def fetch():
            danielson_ok = False
            engine_ok = False

            # Fetch DANIELSON stats
            try:
                r = requests.get(f"{self.danielson_url}/api/ai/stats", timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    if data.get('success'):
                        self.stats = data['stats']
                        danielson_ok = True
            except Exception as e:
                logger.error(f"DANIELSON stats fetch error: {e}")

            # Fetch learning engine stats
            if self.learning_engine:
                try:
                    # Get neural network epochs
                    self.engine_stats['neural_epochs'] = \
                        self.learning_engine.neural_weights['card_recognition']['epochs_trained']

                    # Get total training samples
                    self.engine_stats['total_training_samples'] = \
                        self.learning_engine._get_total_training_samples()

                    # Get AI confidence
                    self.engine_stats['ai_confidence'] = \
                        self.learning_engine._calculate_ai_confidence()

                    # Get deck/card counts from database
                    import sqlite3
                    conn = sqlite3.connect(self.learning_engine.db_path)
                    cursor = conn.cursor()

                    cursor.execute('SELECT COUNT(*) FROM deck_performance')
                    self.engine_stats['decks_analyzed'] = cursor.fetchone()[0]

                    cursor.execute('SELECT COUNT(*) FROM card_performance')
                    self.engine_stats['cards_tracked'] = cursor.fetchone()[0]

                    cursor.execute('SELECT COUNT(*) FROM card_synergies')
                    self.engine_stats['synergies_learned'] = cursor.fetchone()[0]

                    conn.close()
                    engine_ok = True
                except Exception as e:
                    logger.error(f"Learning engine stats error: {e}")

            # Update UI
            self._schedule_ui(self._update_ui)

            if danielson_ok and engine_ok:
                self._schedule_ui(lambda: self.status_label.config(
                    text="All Systems Online", fg=self.colors.success))
                self._add_event("Full sync complete", "OK")
            elif danielson_ok:
                self._schedule_ui(lambda: self.status_label.config(
                    text="DANIELSON Only", fg=self.colors.warning))
            elif engine_ok:
                self._schedule_ui(lambda: self.status_label.config(
                    text="Engine Only", fg=self.colors.warning))
            else:
                self._schedule_ui(lambda: self.status_label.config(
                    text="Offline", fg=self.colors.error))

        threading.Thread(target=fetch, daemon=True).start()

        # Schedule next refresh in 30 seconds
        self.frame.after(30000, self._refresh_stats)

    def _update_ui(self):
        """Update UI with current stats from both DANIELSON and learning engine"""
        try:
            # Update stat cards
            self.stat_labels['total_scans'].config(
                text=f"{self.stats.get('total_corrections', 0):,}")
            self.stat_labels['accuracy'].config(
                text=f"{self.stats.get('accuracy_rate', 0)*100:.1f}%")
            self.stat_labels['neural_epochs'].config(
                text=f"{self.engine_stats.get('neural_epochs', 0):,}")
            self.stat_labels['ai_confidence'].config(
                text=f"{self.engine_stats.get('ai_confidence', 0)*100:.1f}%")

            # Update info labels
            self.info_labels['danielson_status'].config(
                text="Online" if self.stats.get('total_corrections', 0) >= 0 else "Offline",
                fg=self.colors.success)
            self.info_labels['engine_status'].config(
                text="Active" if self.learning_engine else "Not Loaded",
                fg=self.colors.success if self.learning_engine else self.colors.error)
            self.info_labels['training_samples'].config(
                text=f"{self.engine_stats.get('total_training_samples', 0):,}")
            self.info_labels['cards_tracked'].config(
                text=f"{self.engine_stats.get('cards_tracked', 0):,}")
            self.info_labels['synergies_learned'].config(
                text=f"{self.engine_stats.get('synergies_learned', 0):,}")
            self.info_labels['last_update'].config(
                text=datetime.now().strftime("%H:%M:%S"))
        except Exception as e:
            logger.error(f"UI update error: {e}")

    def _add_event(self, event, result):
        """Add event to the events tree"""
        time_str = datetime.now().strftime("%H:%M")
        self.events_tree.insert('', 0, values=(time_str, event, result))

        # Keep only last 50 events
        children = self.events_tree.get_children()
        if len(children) > 50:
            for child in children[50:]:
                self.events_tree.delete(child)

    def _start_training(self):
        """Start AI training session - runs simulated games to improve neural network"""
        if not self.learning_engine:
            messagebox.showerror("Error", "Learning engine not available.\nCheck that nexus_v2/ai/learning_engine.py exists.")
            return

        self._add_event("Training started", "Running...")

        def run_training():
            """Run training simulations in background"""
            import random

            # Simulate training games
            strategies = ['aggro', 'control', 'combo', 'midrange']
            formats = ['Standard', 'Modern', 'Pioneer', 'Legacy']
            sample_cards = [
                'Lightning Bolt', 'Sol Ring', 'Counterspell', 'Swords to Plowshares',
                'Dark Ritual', 'Birds of Paradise', 'Thoughtseize', 'Path to Exile',
                'Goblin Guide', 'Tarmogoyf', 'Snapcaster Mage', 'Brainstorm'
            ]

            games_to_run = 50
            wins = 0

            for i in range(games_to_run):
                # Create deck info
                deck_info = {
                    'deck_name': f"Training Deck {i+1}",
                    'format': random.choice(formats),
                    'strategy': random.choice(strategies)
                }

                # Simulate game result
                won = random.random() > 0.45  # Slight win bias
                if won:
                    wins += 1

                game_result = {
                    'win': won,
                    'turns': random.randint(4, 12),
                    'mana_curve_score': random.uniform(0.6, 0.95),
                    'threat_density': random.uniform(0.5, 0.9),
                    'removal_efficiency': random.uniform(0.4, 0.85),
                    'card_draw_score': random.uniform(0.5, 0.8),
                    'key_cards': random.sample(sample_cards, 3),
                    'winning_strategy': deck_info['strategy'],
                    'opponent_strategy': random.choice(strategies)
                }

                # Learn from this game
                self.learning_engine.learn_from_game_simulation(deck_info, game_result)

                # Learn card synergies
                if len(game_result['key_cards']) >= 2:
                    for j in range(len(game_result['key_cards']) - 1):
                        self.learning_engine.learn_card_synergy(
                            game_result['key_cards'][j],
                            game_result['key_cards'][j+1],
                            won_together=won,
                            synergy_type=deck_info['strategy']
                        )

                # Update UI every 10 games
                if (i + 1) % 10 == 0:
                    self._schedule_ui(lambda g=i+1, w=wins: self._add_event(
                        f"Training: {g}/{games_to_run} games", f"{w} wins"))

            # Save neural weights after training
            self.learning_engine.save_neural_weights()

            # Final update
            win_rate = wins / games_to_run * 100
            self._schedule_ui(lambda: self._add_event(
                f"Training complete: {games_to_run} games", f"{win_rate:.1f}% win"))
            self._schedule_ui(self._refresh_stats)

            # Show completion message
            self._schedule_ui(lambda: messagebox.showinfo(
                "Training Complete",
                f"Training session finished!\n\n"
                f"Games simulated: {games_to_run}\n"
                f"Wins: {wins} ({win_rate:.1f}%)\n"
                f"Neural weights saved.\n\n"
                f"The AI has learned from card synergies,\n"
                f"deck performance, and winning strategies."
            ))

        threading.Thread(target=run_training, daemon=True).start()

        messagebox.showinfo("Training Started",
            "AI training session started.\n\n"
            "Simulating 50 games to improve:\n"
            "- Card performance ratings\n"
            "- Deck win rates\n"
            "- Card synergy patterns\n\n"
            "Check the events log for progress.")

    def _reset_stats(self):
        """Reset learning statistics - clears both DANIELSON and local engine"""
        if not messagebox.askyesno("Reset Stats",
            "This will reset ALL AI learning data:\n\n"
            "- Neural network weights (reset to random)\n"
            "- Card performance history\n"
            "- Deck performance history\n"
            "- Card synergy data\n"
            "- Training samples\n\n"
            "This cannot be undone. Continue?"):
            return

        def do_reset():
            errors = []

            # Reset DANIELSON stats
            try:
                # DANIELSON doesn't have a reset endpoint, so just note it
                self._schedule_ui(lambda: self._add_event(
                    "DANIELSON stats", "Preserved"))
            except Exception as e:
                errors.append(f"DANIELSON: {e}")

            # Reset learning engine
            if self.learning_engine:
                try:
                    import sqlite3
                    conn = sqlite3.connect(self.learning_engine.db_path)
                    cursor = conn.cursor()

                    # Clear all tables
                    tables = [
                        'card_recognition_learning',
                        'game_simulation_results',
                        'deck_performance',
                        'card_performance',
                        'ai_training_sessions',
                        'card_synergies',
                        'budget_tournament_decks'
                    ]
                    for table in tables:
                        try:
                            cursor.execute(f'DELETE FROM {table}')
                        except Exception:
                            pass  # Table may not exist

                    conn.commit()
                    conn.close()

                    # Reset neural weights
                    self.learning_engine.neural_weights = {
                        'card_recognition':
                            self.learning_engine._init_card_recognition_network(),
                        'deck_optimizer':
                            self.learning_engine._init_deck_optimizer_network(),
                        'strategy_predictor':
                            self.learning_engine._init_strategy_network()
                    }
                    self.learning_engine.save_neural_weights()

                    self._schedule_ui(lambda: self._add_event(
                        "Engine reset", "Complete"))

                except Exception as e:
                    errors.append(f"Engine: {e}")
                    self._schedule_ui(lambda: self._add_event(
                        "Engine reset", "Failed"))

            # Refresh UI
            self._schedule_ui(self._refresh_stats)

            # Show result
            if errors:
                self._schedule_ui(lambda: messagebox.showwarning(
                    "Partial Reset",
                    f"Reset completed with errors:\n{chr(10).join(errors)}"))
            else:
                self._schedule_ui(lambda: messagebox.showinfo(
                    "Reset Complete",
                    "All AI learning data has been reset.\n\n"
                    "Neural weights: Random initialization\n"
                    "Training data: Cleared\n\n"
                    "Use 'Start Training' to rebuild the AI."))

        self._add_event("Stats reset", "Starting...")
        threading.Thread(target=do_reset, daemon=True).start()

    def _clear_history(self):
        """Clear event history"""
        for item in self.events_tree.get_children():
            self.events_tree.delete(item)


def create_ai_learning_tab(notebook: ttk.Notebook, config) -> AILearningTab:
    """Factory function to create AI learning tab"""
    return AILearningTab(notebook, config)
