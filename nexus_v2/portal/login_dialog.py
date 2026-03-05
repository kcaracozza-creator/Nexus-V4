#!/usr/bin/env python3
"""
NEXUS Login Dialog
==================
Login/Registration UI for NEXUS Portal integration.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable
from .client import NexusPortalClient, get_client


class LoginDialog(tk.Toplevel):
    """Login/Register dialog for NEXUS Portal"""

    def __init__(self, parent, on_success: Callable = None):
        super().__init__(parent)
        self.title("NEXUS - Login")
        self.geometry("400x350")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.client = get_client()
        self.on_success = on_success
        self.result = False

        self._create_widgets()
        self._center_window()

    def _center_window(self):
        """Center dialog on screen"""
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create dialog widgets"""
        # Main frame
        main = ttk.Frame(self, padding=20)
        main.pack(fill="both", expand=True)

        # Logo/Title
        title = ttk.Label(main, text="NEXUS", font=("Helvetica", 24, "bold"))
        title.pack(pady=(0, 5))

        subtitle = ttk.Label(main, text="Universal Collectibles Management")
        subtitle.pack(pady=(0, 20))

        # Notebook for Login/Register tabs
        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill="both", expand=True)

        # Login tab
        login_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(login_frame, text="Login")
        self._create_login_tab(login_frame)

        # Register tab
        register_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(register_frame, text="Register")
        self._create_register_tab(register_frame)

        # Status
        self.status_var = tk.StringVar(value="")
        status = ttk.Label(main, textvariable=self.status_var, foreground="gray")
        status.pack(pady=(10, 0))

        # Offline mode button
        offline_btn = ttk.Button(main, text="Continue Offline", command=self._continue_offline)
        offline_btn.pack(pady=(10, 0))

    def _create_login_tab(self, parent):
        """Create login form"""
        ttk.Label(parent, text="Email:").pack(anchor="w")
        self.login_email = ttk.Entry(parent, width=40)
        self.login_email.pack(fill="x", pady=(0, 10))

        ttk.Label(parent, text="Password:").pack(anchor="w")
        self.login_password = ttk.Entry(parent, width=40, show="*")
        self.login_password.pack(fill="x", pady=(0, 15))

        btn = ttk.Button(parent, text="Login", command=self._do_login)
        btn.pack()

        self.login_email.bind('<Return>', lambda e: self.login_password.focus())
        self.login_password.bind('<Return>', lambda e: self._do_login())

    def _create_register_tab(self, parent):
        """Create registration form"""
        ttk.Label(parent, text="Shop Name:").pack(anchor="w")
        self.reg_shop = ttk.Entry(parent, width=40)
        self.reg_shop.pack(fill="x", pady=(0, 10))

        ttk.Label(parent, text="Email:").pack(anchor="w")
        self.reg_email = ttk.Entry(parent, width=40)
        self.reg_email.pack(fill="x", pady=(0, 10))

        ttk.Label(parent, text="Password:").pack(anchor="w")
        self.reg_password = ttk.Entry(parent, width=40, show="*")
        self.reg_password.pack(fill="x", pady=(0, 15))

        btn = ttk.Button(parent, text="Register", command=self._do_register)
        btn.pack()

    def _do_login(self):
        """Handle login"""
        email = self.login_email.get().strip()
        password = self.login_password.get()

        if not email or not password:
            self.status_var.set("Please enter email and password")
            return

        self.status_var.set("Logging in...")
        self.update()

        result = self.client.login(email, password)

        if result['success']:
            self.status_var.set("Login successful!")
            self.result = True
            self._validate_and_close()
        else:
            error = result.get('data', {}).get('error') or result.get('error', 'Login failed')
            self.status_var.set(f"Error: {error}")

    def _do_register(self):
        """Handle registration"""
        shop = self.reg_shop.get().strip()
        email = self.reg_email.get().strip()
        password = self.reg_password.get()

        if not email or not password:
            self.status_var.set("Please enter email and password")
            return

        self.status_var.set("Registering...")
        self.update()

        result = self.client.register(email, password, shop)

        if result['success']:
            self.status_var.set("Registration successful!")
            messagebox.showinfo(
                "Registration Complete",
                f"Your license key:\n{result['data']['license_key']}\n\nSave this key!"
            )
            self.result = True
            self._validate_and_close()
        else:
            error = result.get('data', {}).get('error') or result.get('error', 'Registration failed')
            self.status_var.set(f"Error: {error}")

    def _validate_and_close(self):
        """Validate license and close dialog"""
        self.status_var.set("Validating license...")
        self.update()

        validation = self.client.validate_license()
        if validation['success']:
            if self.on_success:
                self.on_success()
            self.destroy()
        else:
            self.status_var.set("License validation failed")

    def _continue_offline(self):
        """Continue without license (offline mode)"""
        self.result = False
        self.destroy()


class UpdateDialog(tk.Toplevel):
    """Update available dialog"""

    def __init__(self, parent, version: str, changelog: str = "",
                 is_mandatory: bool = False, on_update: Callable = None):
        super().__init__(parent)
        self.title("NEXUS - Update Available")
        self.geometry("450x300")
        self.resizable(False, False)
        self.transient(parent)

        if is_mandatory:
            self.grab_set()
            self.protocol("WM_DELETE_WINDOW", lambda: None)  # Prevent close

        self.version = version
        self.on_update = on_update
        self.result = False

        self._create_widgets(version, changelog, is_mandatory)
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self, version, changelog, is_mandatory):
        main = ttk.Frame(self, padding=20)
        main.pack(fill="both", expand=True)

        # Header
        ttk.Label(main, text="Update Available!", font=("Helvetica", 16, "bold")).pack()
        ttk.Label(main, text=f"Version {version}").pack(pady=(5, 15))

        if is_mandatory:
            ttk.Label(main, text="This update is required.", foreground="red").pack()

        # Changelog
        if changelog:
            ttk.Label(main, text="What's New:").pack(anchor="w", pady=(10, 5))
            text = tk.Text(main, height=8, width=50, wrap="word")
            text.insert("1.0", changelog)
            text.config(state="disabled")
            text.pack(fill="both", expand=True)

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(pady=(15, 0))

        ttk.Button(btn_frame, text="Update Now", command=self._do_update).pack(side="left", padx=5)

        if not is_mandatory:
            ttk.Button(btn_frame, text="Later", command=self.destroy).pack(side="left", padx=5)

    def _do_update(self):
        self.result = True
        if self.on_update:
            self.on_update(self.version)
        self.destroy()


def show_login_dialog(parent) -> bool:
    """Show login dialog and return True if logged in"""
    dialog = LoginDialog(parent)
    parent.wait_window(dialog)
    return dialog.result


def show_update_dialog(parent, version: str, changelog: str = "",
                       is_mandatory: bool = False, on_update: Callable = None) -> bool:
    """Show update dialog"""
    dialog = UpdateDialog(parent, version, changelog, is_mandatory, on_update)
    parent.wait_window(dialog)
    return dialog.result


def check_and_prompt_updates(parent) -> bool:
    """Check for updates and prompt user if available"""
    client = get_client()
    if not client.is_licensed():
        return False

    result = client.check_for_updates()
    if not result['success']:
        return False

    data = result.get('data', {})
    if not data.get('update_available'):
        return False

    return show_update_dialog(
        parent,
        version=data['latest_version'],
        changelog=data.get('changelog', ''),
        is_mandatory=data.get('is_mandatory', False)
    )
