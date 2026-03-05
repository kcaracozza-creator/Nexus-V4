#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AI TRAINING TAB - NEXUS V2                                 ║
║                                                                                ║
║   Real-time monitoring of reinforcement learning training:                   ║
║   - Live training metrics display                                             ║
║   - GPU utilization monitoring                                                ║
║   - Model performance visualization                                           ║
║   - Training checkpoint management                                            ║
║   - Direct model deployment controls                                          ║
║                                                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import subprocess
import re
import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import logging
import os
import json
import zipfile
import requests

logger = logging.getLogger(__name__)

# Load Zultan URL and training dir from config, fallback to defaults
try:
    from nexus_v2.config.config_manager import config
    from pathlib import Path
    ZULTAN_URL = config.get('training.zultan_url', 'http://192.168.1.152:8000')
    TRAINING_DIR = config.get('training.training_dir', str(Path.home() / 'nexus_training'))
except ImportError:
    from pathlib import Path
    ZULTAN_URL = "http://192.168.1.152:8000"
    TRAINING_DIR = str(Path.home() / 'nexus_training')


class AITrainingTab:
    """
    AI Training Management and Monitoring Interface.
    
    Features:
    - Real-time training metrics
    - GPU/CPU utilization monitoring  
    - Training progress visualization
    - Model checkpoint management
    - Quick deployment controls
    """
    
    def __init__(self, parent):
        self.parent = parent
        self.root = parent
        
        # Data storage
        self.training_data = {
            'timesteps': [],
            'fps': [],
            'explained_variance': [],
            'value_loss': [],
            'policy_gradient': [],
            'gpu_temp': [],
            'gpu_memory': []
        }
        
        # Monitoring threads
        self.monitoring_active = False
        self.monitor_thread = None
        
        self._build_ui()
        self._start_monitoring()
    
    def _build_ui(self):
        """Build the training interface"""
        # Main container
        self.frame = ttk.Frame(self.parent)
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            self.frame,
            text="🤖 AI Training Control Center",
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=10)
        
        # Create main sections
        self._create_status_section()
        self._create_metrics_section()
        self._create_control_section()
        self._create_visualization_section()
    
    def _create_status_section(self):
        """Create training status display"""
        status_frame = ttk.LabelFrame(self.frame, text="Training Status", padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Current status display
        info_frame = ttk.Frame(status_frame)
        info_frame.pack(fill=tk.X)
        
        # Status indicators
        ttk.Label(info_frame, text="Status:").grid(row=0, column=0, sticky=tk.W)
        self.status_label = ttk.Label(info_frame, text="Checking...", foreground="orange")
        self.status_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        ttk.Label(info_frame, text="Progress:").grid(row=1, column=0, sticky=tk.W)
        self.progress_label = ttk.Label(info_frame, text="0 / 2,000,000 timesteps")
        self.progress_label.grid(row=1, column=1, sticky=tk.W, padx=(10, 0))
        
        ttk.Label(info_frame, text="FPS:").grid(row=2, column=0, sticky=tk.W)
        self.fps_label = ttk.Label(info_frame, text="0")
        self.fps_label.grid(row=2, column=1, sticky=tk.W, padx=(10, 0))
        
        ttk.Label(info_frame, text="GPU Temp:").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        self.gpu_temp_label = ttk.Label(info_frame, text="N/A")
        self.gpu_temp_label.grid(row=0, column=3, sticky=tk.W, padx=(10, 0))
        
        ttk.Label(info_frame, text="GPU Memory:").grid(row=1, column=2, sticky=tk.W, padx=(20, 0))
        self.gpu_memory_label = ttk.Label(info_frame, text="N/A")
        self.gpu_memory_label.grid(row=1, column=3, sticky=tk.W, padx=(10, 0))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(status_frame, length=400, mode='determinate')
        self.progress_bar.pack(pady=(10, 0))
    
    def _create_metrics_section(self):
        """Create training metrics display"""
        metrics_frame = ttk.LabelFrame(self.frame, text="Training Metrics", padding=10)
        metrics_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Metrics grid
        metrics_grid = ttk.Frame(metrics_frame)
        metrics_grid.pack(fill=tk.X)
        
        # Explained Variance
        ttk.Label(metrics_grid, text="Explained Variance:").grid(row=0, column=0, sticky=tk.W)
        self.explained_var_label = ttk.Label(metrics_grid, text="N/A")
        self.explained_var_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        # Value Loss
        ttk.Label(metrics_grid, text="Value Loss:").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        self.value_loss_label = ttk.Label(metrics_grid, text="N/A")
        self.value_loss_label.grid(row=0, column=3, sticky=tk.W, padx=(10, 0))
        
        # Policy Gradient
        ttk.Label(metrics_grid, text="Policy Gradient:").grid(row=1, column=0, sticky=tk.W)
        self.policy_grad_label = ttk.Label(metrics_grid, text="N/A")
        self.policy_grad_label.grid(row=1, column=1, sticky=tk.W, padx=(10, 0))
        
        # Entropy Loss
        ttk.Label(metrics_grid, text="Entropy Loss:").grid(row=1, column=2, sticky=tk.W, padx=(20, 0))
        self.entropy_loss_label = ttk.Label(metrics_grid, text="N/A")
        self.entropy_loss_label.grid(row=1, column=3, sticky=tk.W, padx=(10, 0))
    
    def _create_control_section(self):
        """Create training control buttons"""
        control_frame = ttk.LabelFrame(self.frame, text="Training Controls", padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X)
        
        # Training controls
        self.start_btn = ttk.Button(
            button_frame,
            text="Start Training",
            command=self._start_training
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(
            button_frame,
            text="Stop Training",
            command=self._stop_training
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.pause_btn = ttk.Button(
            button_frame,
            text="Pause Training",
            command=self._pause_training
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        # Model controls
        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        self.test_model_btn = ttk.Button(
            button_frame,
            text="Test Current Model",
            command=self._test_current_model
        )
        self.test_model_btn.pack(side=tk.LEFT, padx=5)
        
        self.deploy_btn = ttk.Button(
            button_frame,
            text="Deploy Model",
            command=self._deploy_model
        )
        self.deploy_btn.pack(side=tk.LEFT, padx=5)
        
        # Checkpoint controls
        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        self.save_checkpoint_btn = ttk.Button(
            button_frame,
            text="Save Checkpoint",
            command=self._save_checkpoint
        )
        self.save_checkpoint_btn.pack(side=tk.LEFT, padx=5)
        
        self.load_checkpoint_btn = ttk.Button(
            button_frame,
            text="Load Checkpoint",
            command=self._load_checkpoint
        )
        self.load_checkpoint_btn.pack(side=tk.LEFT, padx=5)
    
    def _create_visualization_section(self):
        """Create training visualization charts"""
        viz_frame = ttk.LabelFrame(self.frame, text="Training Visualization", padding=10)
        viz_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create matplotlib figure
        self.fig, self.axes = plt.subplots(2, 2, figsize=(12, 6))
        self.fig.patch.set_facecolor('#2b2b2b')
        
        # Configure subplots
        self.axes[0, 0].set_title("Training FPS", color='white')
        self.axes[0, 1].set_title("Explained Variance", color='white')
        self.axes[1, 0].set_title("Value Loss", color='white')
        self.axes[1, 1].set_title("GPU Temperature", color='white')
        
        for ax in self.axes.flat:
            ax.set_facecolor('#1a1a1a')
            ax.tick_params(colors='white')
            ax.spines['bottom'].set_color('white')
            ax.spines['top'].set_color('white')
            ax.spines['right'].set_color('white')
            ax.spines['left'].set_color('white')
        
        # Embed in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, viz_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def _start_monitoring(self):
        """Start monitoring training progress"""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
    
    def _stop_monitoring(self):
        """Stop monitoring training progress"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                # Check training status
                self._update_training_status()
                
                # Check GPU status
                self._update_gpu_status()
                
                # Update visualizations
                self._update_visualizations()
                
                time.sleep(2)  # Update every 2 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
    
    def _update_training_status(self):
        """Update training status from log file"""
        try:
            log_file = os.path.join(TRAINING_DIR, "training_16env.log")
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                
                # Parse latest metrics
                latest_metrics = {}
                for line in reversed(lines[-20:]):  # Check last 20 lines
                    if 'total_timesteps' in line:
                        # Extract timesteps
                        match = re.search(r'total_timesteps:(\d+)', line)
                        if match:
                            latest_metrics['timesteps'] = int(match.group(1))
                    
                    if 'fps' in line:
                        # Extract FPS
                        match = re.search(r'fps:(\d+)', line)
                        if match:
                            latest_metrics['fps'] = int(match.group(1))
                    
                    if 'explained_variance' in line:
                        # Extract explained variance
                        match = re.search(r'explained_variance:([0-9.-]+)', line)
                        if match:
                            latest_metrics['explained_variance'] = float(match.group(1))
                    
                    if 'value_loss' in line:
                        # Extract value loss
                        match = re.search(r'value_loss:([0-9.-]+)', line)
                        if match:
                            latest_metrics['value_loss'] = float(match.group(1))
                
                # Update UI in main thread
                self.root.after_idle(lambda: self._update_status_ui(latest_metrics))
                
        except Exception as e:
            logger.error(f"Error updating training status: {e}")
    
    def _update_status_ui(self, metrics):
        """Update status UI elements"""
        if 'timesteps' in metrics:
            timesteps = metrics['timesteps']
            progress = (timesteps / 2000000) * 100
            self.progress_label.config(text=f"{timesteps:,} / 2,000,000 timesteps")
            self.progress_bar['value'] = progress
            
            # Update status
            if timesteps >= 2000000:
                self.status_label.config(text="Complete", foreground="green")
            else:
                self.status_label.config(text="Training", foreground="orange")
        
        if 'fps' in metrics:
            self.fps_label.config(text=f"{metrics['fps']:,}")
            self.training_data['fps'].append(metrics['fps'])
        
        if 'explained_variance' in metrics:
            self.explained_var_label.config(text=f"{metrics['explained_variance']:.3f}")
            self.training_data['explained_variance'].append(metrics['explained_variance'])
        
        if 'value_loss' in metrics:
            self.value_loss_label.config(text=f"{metrics['value_loss']:.3f}")
            self.training_data['value_loss'].append(metrics['value_loss'])
        
        # Add timestep for plotting
        if 'timesteps' in metrics:
            self.training_data['timesteps'].append(metrics['timesteps'])
    
    def _update_gpu_status(self):
        """Update GPU status via Zultan API"""
        try:
            resp = requests.get(f"{ZULTAN_URL}/gpu", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('available'):
                    temp = data.get('temperature', 0)
                    memory_used = data.get('memory_used', 0)
                    memory_total = data.get('memory_total', 12288)

                    # Update UI in main thread
                    self.root.after_idle(lambda: self._update_gpu_ui(temp, memory_used, memory_total))

                    # Store for plotting
                    self.training_data['gpu_temp'].append(temp)
                    self.training_data['gpu_memory'].append((memory_used / memory_total) * 100)

        except requests.exceptions.ConnectionError:
            logger.debug("Cannot connect to Zultan training agent")
        except Exception as e:
            logger.error(f"Error getting GPU status: {e}")
    
    def _update_gpu_ui(self, temp, memory_used, memory_total):
        """Update GPU UI elements"""
        try:
            # Check if widget still exists before updating
            if not self.monitoring_active:
                return
            if not hasattr(self, 'gpu_temp_label') or not self.gpu_temp_label.winfo_exists():
                return
            self.gpu_temp_label.config(text=f"{temp}°C")
            memory_pct = (memory_used / memory_total) * 100
            self.gpu_memory_label.config(text=f"{memory_used}MB ({memory_pct:.1f}%)")
        except tk.TclError:
            # Widget destroyed, ignore
            pass
    
    def _update_visualizations(self):
        """Update visualization charts"""
        try:
            # Don't update if shutting down
            if not self.monitoring_active:
                return
            
            # Limit data points for performance
            max_points = 100
            for key in self.training_data:
                if len(self.training_data[key]) > max_points:
                    self.training_data[key] = self.training_data[key][-max_points:]
            
            # Clear and replot
            for ax in self.axes.flat:
                ax.clear()
            
            # Plot data if available
            if len(self.training_data['timesteps']) > 1:
                x = self.training_data['timesteps']
                
                # FPS plot
                if len(self.training_data['fps']) > 1:
                    self.axes[0, 0].plot(x[-len(self.training_data['fps']):], 
                                        self.training_data['fps'], 'g-', linewidth=2)
                    self.axes[0, 0].set_title("Training FPS", color='white')
                    self.axes[0, 0].set_ylabel("FPS", color='white')
                
                # Explained Variance plot
                if len(self.training_data['explained_variance']) > 1:
                    self.axes[0, 1].plot(x[-len(self.training_data['explained_variance']):], 
                                        self.training_data['explained_variance'], 'b-', linewidth=2)
                    self.axes[0, 1].set_title("Explained Variance", color='white')
                    self.axes[0, 1].set_ylabel("Variance", color='white')
                
                # Value Loss plot
                if len(self.training_data['value_loss']) > 1:
                    self.axes[1, 0].plot(x[-len(self.training_data['value_loss']):], 
                                        self.training_data['value_loss'], 'r-', linewidth=2)
                    self.axes[1, 0].set_title("Value Loss", color='white')
                    self.axes[1, 0].set_ylabel("Loss", color='white')
                
                # GPU Temperature plot
                if len(self.training_data['gpu_temp']) > 1:
                    self.axes[1, 1].plot(x[-len(self.training_data['gpu_temp']):], 
                                        self.training_data['gpu_temp'], 'orange', linewidth=2)
                    self.axes[1, 1].set_title("GPU Temperature", color='white')
                    self.axes[1, 1].set_ylabel("°C", color='white')
            
            # Configure all axes
            for ax in self.axes.flat:
                ax.set_facecolor('#1a1a1a')
                ax.tick_params(colors='white')
                ax.spines['bottom'].set_color('white')
                ax.spines['top'].set_color('white')
                ax.spines['right'].set_color('white')
                ax.spines['left'].set_color('white')
                ax.set_xlabel("Timesteps", color='white')
            
            # Update canvas
            self.canvas.draw()
            
        except Exception as e:
            logger.error(f"Error updating visualizations: {e}")
    
    def _start_training(self):
        """Start training process"""
        try:
            training_dir = "TRAINING_DIR"
            os.chdir(training_dir)
            
            # Start training in background
            subprocess.Popen([
                "python3", "train_stable.py"
            ], stdout=open("training_16env.log", "w"), stderr=subprocess.STDOUT)
            
            messagebox.showinfo("Training Started", "Training process started successfully!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start training: {e}")
    
    def _stop_training(self):
        """Stop training via Zultan API"""
        try:
            resp = requests.post(f"{ZULTAN_URL}/stop_all", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                stopped = data.get('stopped', [])
                messagebox.showinfo("Training Stopped", f"Stopped sessions: {stopped}")
            else:
                messagebox.showerror("Error", f"API error: {resp.text}")
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Error", "Cannot connect to Zultan (192.168.1.152:8000)\nIs the training agent running?")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop training: {e}")

    def _pause_training(self):
        """Pause not supported via API - show message"""
        messagebox.showinfo("Pause", "Pause not supported. Use Stop to end training.")
    
    def _test_current_model(self):
        """Test the current trained model"""
        try:
            training_dir = "TRAINING_DIR"
            
            # Check for latest model
            model_files = [f for f in os.listdir(training_dir) if f.startswith("nexus_") and f.endswith(".zip")]
            if not model_files:
                messagebox.showerror("Error", "No trained models found!")
                return
            
            # Get latest model
            latest_model = max(model_files, key=lambda x: os.path.getctime(os.path.join(training_dir, x)))
            
            # Start testing via Zultan API
            messagebox.showinfo("Testing Model", f"Testing model: {latest_model}\n\nModel test runs on Zultan server.")
            try:
                resp = requests.post(f"{ZULTAN_URL}/test_model",
                                    json={'model_path': os.path.join(training_dir, latest_model)},
                                    timeout=30)
                if resp.status_code == 200:
                    result = resp.json()
                    messagebox.showinfo("Test Results", f"Score: {result.get('score', 'N/A')}")
            except requests.exceptions.ConnectionError:
                messagebox.showwarning("Offline", "Zultan server not available for remote testing.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to test model: {e}")
    
    def _deploy_model(self):
        """Deploy trained model to hardware via Zultan"""
        try:
            resp = requests.post(f"{ZULTAN_URL}/deploy_model", timeout=60)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('success'):
                    messagebox.showinfo("Deploy Model", f"Model deployed to ESP32!\n{result.get('message', '')}")
                else:
                    messagebox.showwarning("Deploy Failed", result.get('error', 'Unknown error'))
            else:
                messagebox.showerror("Error", f"API error: {resp.status_code}")
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Error", "Cannot connect to Zultan server for deployment.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to deploy model: {e}")
    
    def _save_checkpoint(self):
        """Save training checkpoint via Zultan"""
        try:
            resp = requests.post(f"{ZULTAN_URL}/save_checkpoint", timeout=30)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('success'):
                    path = result.get('checkpoint_path', 'unknown')
                    messagebox.showinfo("Checkpoint", f"Checkpoint saved:\n{path}")
                else:
                    messagebox.showwarning("Save Failed", result.get('error', 'Unknown error'))
            else:
                messagebox.showerror("Error", f"API error: {resp.status_code}")
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Error", "Cannot connect to Zultan server.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save checkpoint: {e}")
    
    def _load_checkpoint(self):
        """Load training checkpoint via file dialog"""
        try:
            from tkinter import filedialog
            checkpoint = filedialog.askopenfilename(
                title="Select Checkpoint",
                filetypes=[("Model files", "*.zip"), ("All files", "*.*")],
                initialdir="TRAINING_DIR"
            )
            if checkpoint:
                resp = requests.post(f"{ZULTAN_URL}/load_checkpoint",
                                    json={'checkpoint_path': checkpoint},
                                    timeout=30)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get('success'):
                        messagebox.showinfo("Checkpoint", f"Checkpoint loaded:\n{checkpoint}")
                    else:
                        messagebox.showwarning("Load Failed", result.get('error', 'Unknown error'))
                else:
                    messagebox.showerror("Error", f"API error: {resp.status_code}")
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Error", "Cannot connect to Zultan server.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load checkpoint: {e}")
    
    def destroy(self):
        """Clean up resources"""
        self._stop_monitoring()
        if hasattr(self, 'frame'):
            self.frame.destroy()