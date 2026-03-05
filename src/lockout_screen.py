#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Subscription Lockout Screen
Displays when account is locked due to non-payment
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from subscription_manager import SubscriptionManager

class LockoutScreen:
    """
    Full-screen lockout overlay when subscription is past due
    Blocks all system features until payment is made
    """
    
    def __init__(self, root=None, subscription_manager=None):
        """Initialize lockout screen"""
        self.root = root or tk.Tk()
        self.manager = subscription_manager or SubscriptionManager()
        
        # Get subscription info
        self.sub_info = self.manager.get_subscription_info()
        
        # Setup window
        self.root.title("Nexus Card System - Subscription Required")
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='#1a1a1a')
        
        # Prevent window closing
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_attempt)
        
        self._create_ui()
    
    def _create_ui(self):
        """Create lockout UI"""
        # Main container
        container = tk.Frame(self.root, bg='#1a1a1a')
        container.place(relx=0.5, rely=0.5, anchor='center')
        
        # Lock icon (using text)
        lock_label = tk.Label(
            container,
            text="🔒",
            font=("Segoe UI", 120),
            bg='#1a1a1a',
            fg='#f56565'
        )
        lock_label.pack(pady=(0, 30))
        
        # Title
        title_label = tk.Label(
            container,
            text="Subscription Payment Required",
            font=("Segoe UI", 32, "bold"),
            bg='#1a1a1a',
            fg='#ffffff'
        )
        title_label.pack(pady=(0, 20))
        
        # Message
        days_overdue = self.sub_info['days_overdue']
        tier = self.sub_info['tier'].title()
        price = self.sub_info['price']
        
        message = f"""Your {tier} subscription payment is {days_overdue} days overdue.

Account has been locked after the 90-day grace period.

To restore access, please make a payment of ${price:.2f}"""
        
        message_label = tk.Label(
            container,
            text=message,
            font=("Segoe UI", 16),
            bg='#1a1a1a',
            fg='#cbd5e0',
            justify='center'
        )
        message_label.pack(pady=(0, 40))
        
        # Payment info frame
        info_frame = tk.Frame(container, bg='#2d3748', relief='solid', bd=2)
        info_frame.pack(pady=(0, 40), padx=40, fill='x')
        
        info_text = f"""
        Subscription Tier: {tier}
        Monthly Price: ${price:.2f}
        Last Payment: {self.sub_info['last_payment_date'][:10] if self.sub_info['last_payment_date'] else 'None'}
        Payment Due: {self.sub_info['next_payment_date'][:10] if self.sub_info['next_payment_date'] else 'N/A'}
        Days Overdue: {days_overdue}
        """
        
        tk.Label(
            info_frame,
            text=info_text,
            font=("Segoe UI", 14),
            bg='#2d3748',
            fg='#ffffff',
            justify='left',
            padx=30,
            pady=20
        ).pack()
        
        # Buttons frame
        buttons_frame = tk.Frame(container, bg='#1a1a1a')
        buttons_frame.pack(pady=(0, 20))
        
        # Pay Now button
        pay_button = tk.Button(
            buttons_frame,
            text="💳 Pay Now ($%.2f)" % price,
            font=("Segoe UI", 16),
            bg='#48bb78',
            fg='white',
            activebackground='#68d391',
            relief='flat',
            cursor='hand2',
            padx=40,
            pady=15,
            command=self._open_payment_portal
        )
        pay_button.pack(side='left', padx=10)
        
        # Contact Support button
        support_button = tk.Button(
            buttons_frame,
            text="📞 Contact Support",
            font=("Segoe UI", 16),
            bg='#4299e1',
            fg='white',
            activebackground='#63b3ed',
            relief='flat',
            cursor='hand2',
            padx=40,
            pady=15,
            command=self._contact_support
        )
        support_button.pack(side='left', padx=10)
        
        # Emergency Exit (small, bottom right)
        exit_button = tk.Button(
            self.root,
            text="Exit System (No Access)",
            font=("Segoe UI", 10),
            bg='#4a5568',
            fg='white',
            activebackground='#718096',
            relief='flat',
            cursor='hand2',
            padx=20,
            pady=5,
            command=self._emergency_exit
        )
        exit_button.place(relx=0.95, rely=0.95, anchor='se')
        
        # Warning label
        warning_label = tk.Label(
            self.root,
            text="⚠️ All system features are disabled until payment is processed",
            font=("Segoe UI", 12),
            bg='#1a1a1a',
            fg='#f6ad55'
        )
        warning_label.place(relx=0.5, rely=0.05, anchor='n')
        
        # Check for payment periodically
        self.root.after(30000, self._check_payment_status)  # Check every 30 seconds
    
    def _open_payment_portal(self):
        """Open web browser to payment portal"""
        import webbrowser
        
        # Build payment URL with shop ID
        payment_url = f"https://nexus-cards.com/subscribe/pay?shop_id={self.sub_info['shop_id']}&tier={self.sub_info['tier']}"
        
        messagebox.showinfo(
            "Payment Portal",
            "Opening payment portal in your web browser.\n\n"
            f"Amount Due: ${self.sub_info['price']:.2f}\n\n"
            "After payment is processed, return here and the system will unlock automatically."
        )
        
        webbrowser.open(payment_url)
        
        # Start checking for payment
        self._check_payment_status()
    
    def _contact_support(self):
        """Open support contact dialog"""
        support_window = tk.Toplevel(self.root)
        support_window.title("Contact Support")
        support_window.geometry("500x400")
        support_window.configure(bg='#2d3748')
        
        tk.Label(
            support_window,
            text="Nexus Card System Support",
            font=("Segoe UI", 18, "bold"),
            bg='#2d3748',
            fg='white'
        ).pack(pady=20)
        
        support_info = f"""
        Email: support@nexus-cards.com
        Phone: 1-800-NEXUS-99
        Hours: Mon-Fri 9AM-6PM EST
        
        Your Shop ID: {self.sub_info['shop_id']}
        Subscription Tier: {self.sub_info['tier'].title()}
        Days Overdue: {self.sub_info['days_overdue']}
        
        Please reference your Shop ID when contacting support.
        
        If you believe this lockout is in error, our support
        team can verify your payment status and unlock your
        account immediately.
        """
        
        tk.Label(
            support_window,
            text=support_info,
            font=("Segoe UI", 12),
            bg='#2d3748',
            fg='#cbd5e0',
            justify='left',
            padx=30
        ).pack(pady=10)
        
        tk.Button(
            support_window,
            text="Close",
            font=("Segoe UI", 12),
            bg='#4a5568',
            fg='white',
            relief='flat',
            cursor='hand2',
            padx=30,
            pady=10,
            command=support_window.destroy
        ).pack(pady=20)
    
    def _check_payment_status(self):
        """Check if payment has been processed"""
        # Reload subscription info
        self.manager.current_subscription = self.manager._load_subscription()
        status, _, _ = self.manager.check_subscription_status()
        
        if status == 'active':
            messagebox.showinfo(
                "Payment Confirmed",
                "Payment has been processed successfully!\n\n"
                "Your account is now active.\n\n"
                "The system will now restart with full access."
            )
            self.manager.unlock_account()
            self.root.destroy()
        else:
            # Check again in 30 seconds
            self.root.after(30000, self._check_payment_status)
    
    def _on_close_attempt(self):
        """Handle window close attempt"""
        result = messagebox.askyesno(
            "Exit System?",
            "Your subscription is locked.\n\n"
            "Closing this window will exit the Nexus Card System.\n\n"
            "You will not have access to any features until payment is made.\n\n"
            "Exit anyway?"
        )
        
        if result:
            self._emergency_exit()
    
    def _emergency_exit(self):
        """Emergency exit the system"""
        self.root.destroy()
        sys.exit(0)
    
    def show(self):
        """Show the lockout screen"""
        self.root.mainloop()


def check_and_show_lockout():
    """
    Check subscription status and show lockout if necessary
    Returns True if locked, False if active
    """
    manager = SubscriptionManager()
    status, _, _ = manager.check_subscription_status()
    
    if status == 'locked':
        # Show lockout screen
        lockout = LockoutScreen(subscription_manager=manager)
        lockout.show()
        return True
    
    return False


if __name__ == "__main__":
    # Test lockout screen
    check_and_show_lockout()
