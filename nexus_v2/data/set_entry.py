#!/usr/bin/env python3
"""
Set List Quick Entry - Just type qty + Tab
Pre-loaded card list in collector number order.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
from datetime import datetime

class SetListEntry:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("WOE Set Entry")
        self.root.geometry("600x750")
        self.root.configure(bg='#1a1a2e')
        
        # WOE cards 1-59
        self.cards = [
            ("Archon's Glory", "1"), ("Armored Scrapgorger", "2"),
            ("Besotted Knight", "3"), ("Break the Spell", "4"),
            ("Cheeky House-Mouse", "5"), ("Cooped Up", "6"),
            ("Cursed Courtier", "7"), ("Discerning Financier", "8"),
            ("Dutiful Griffin", "9"), ("Eerie Interference", "10"),
            ("Expel the Interlopers", "11"), ("Fairytale Titan", "12"),
            ("Gallant Pie-Wielder", "13"), ("Gilded Goose", "14"),
            ("Glass Casket", "15"), ("Graceful Takedown", "16"),
            ("Grand Ball Guest", "17"), ("Hopeful Vigil", "18"),
            ("Knight of Doves", "19"), ("Moment of Valor", "20"),
            ("Moonshaker Cavalry", "21"), ("Plunge into Winter", "22"),
            ("The Princess Takes Flight", "23"), ("Protective Parents", "24"),
            ("Regal Bunnicorn", "25"), ("Return Triumphant", "26"),
            ("Rimefur Reindeer", "27"), ("Savior of the Sleeping", "28"),
            ("Sleepless Lookout", "29"), ("Solitary Sanctuary", "30"),
            ("Spellbook Vendor", "31"), ("Stockpiling Celebrant", "32"),
            ("Stroke of Midnight", "33"), ("A Tale for the Ages", "34"),
            ("Three Blind Mice", "35"), ("Tuinvale Guide", "36"),
            ("Unassuming Sage", "37"), ("Virtue of Loyalty", "38"),
            ("Werefox Bodyguard", "39"), ("Woodland Acolyte", "40"),
            ("Archive Dragon", "41"), ("Asinine Antics", "42"),
            ("Beluna's Gatekeeper", "43"), ("Bitter Chill", "44"),
            ("Chancellor of Tales", "45"), ("Diminisher Witch", "46"),
            ("Disdainful Stroke", "47"), ("Extraordinary Journey", "48"),
            ("Farsight Ritual", "49"), ("Freeze in Place", "50"),
            ("Gadwick's First Duel", "51"), ("Galvanic Giant", "52"),
            ("Horned Loch-Whale", "53"), ("Ice Out", "54"),
            ("Icewrought Sentry", "55"), ("Ingenious Prodigy", "56"),
            ("Into the Fae Court", "57"), ("Johann's Stopgap", "58"),
            ("Living Lectern", "59"),
        ]
        
        self.qty_entries = []
        self._build_ui()
    
    def _build_ui(self):
        tk.Label(self.root, text="WOE Set Entry", font=('Segoe UI', 16, 'bold'),
                fg='#f1c40f', bg='#1a1a2e').pack(pady=8)
        tk.Label(self.root, text="Type qty + Tab, qty + Tab...",
                font=('Segoe UI', 10), fg='#888', bg='#1a1a2e').pack()
        
        # Jump
        jf = tk.Frame(self.root, bg='#1a1a2e')
        jf.pack(pady=8)
        tk.Label(jf, text="Jump #:", fg='#eee', bg='#1a1a2e').pack(side='left')
        self.jump_var = tk.StringVar()
        je = tk.Entry(jf, textvariable=self.jump_var, width=4)
        je.pack(side='left', padx=5)
        je.bind('<Return>', self._jump)
        
        # List
        cf = tk.Frame(self.root, bg='#1a1a2e')
        cf.pack(fill='both', expand=True, padx=15, pady=5)
        
        canvas = tk.Canvas(cf, bg='#1a1a2e', highlightthickness=0)
        sb = ttk.Scrollbar(cf, orient='vertical', command=canvas.yview)
        self.lf = tk.Frame(canvas, bg='#1a1a2e')
        
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.create_window((0,0), window=self.lf, anchor='nw')
        self.lf.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind_all('<MouseWheel>', lambda e: canvas.yview_scroll(-1*(e.delta//120), 'units'))
        self.canvas = canvas
        
        for i, (name, num) in enumerate(self.cards):
            row = tk.Frame(self.lf, bg='#1a1a2e')
            row.pack(fill='x', pady=1)
            
            tk.Label(row, text=f"#{num}", font=('Consolas', 10), fg='#e94560',
                    bg='#1a1a2e', width=4).pack(side='left')
            
            q = tk.Entry(row, font=('Segoe UI', 13, 'bold'), bg='#0f3460',
                        fg='#f1c40f', insertbackground='#f1c40f', width=4, justify='center')
            q.pack(side='left', padx=4)
            q.bind('<Tab>', lambda e, x=i: self._next(x))
            q.bind('<Return>', lambda e, x=i: self._next(x))
            q.bind('<Down>', lambda e, x=i: self._next(x))
            q.bind('<Up>', lambda e, x=i: self._prev(x))
            self.qty_entries.append(q)
            
            tk.Label(row, text=name, font=('Segoe UI', 10), fg='#eee',
                    bg='#1a1a2e').pack(side='left', padx=8)
        
        # Bottom
        bf = tk.Frame(self.root, bg='#16213e')
        bf.pack(fill='x', side='bottom')
        self.tot = tk.Label(bf, text="0 cards", font=('Segoe UI', 11),
                           fg='#eee', bg='#16213e')
        self.tot.pack(side='left', padx=15, pady=12)
        tk.Button(bf, text="Export NEXUS", font=('Segoe UI', 11, 'bold'),
                 bg='#2ecc71', fg='black', command=self._export).pack(side='right', padx=15, pady=8)
        
        self.qty_entries[0].focus_set()
        self.root.bind('<KeyRelease>', lambda e: self._upd())
    
    def _next(self, i):
        if i+1 < len(self.qty_entries):
            self.qty_entries[i+1].focus_set()
            self.qty_entries[i+1].select_range(0, tk.END)
            self.canvas.yview_moveto((i+1)/len(self.cards))
        return "break"
    
    def _prev(self, i):
        if i > 0:
            self.qty_entries[i-1].focus_set()
            self.qty_entries[i-1].select_range(0, tk.END)
        return "break"
    
    def _jump(self, e=None):
        try:
            n = int(self.jump_var.get())
            for i, (_, num) in enumerate(self.cards):
                if int(num) == n:
                    self.qty_entries[i].focus_set()
                    self.canvas.yview_moveto(i/len(self.cards))
                    break
        except (ValueError, IndexError):
            pass

    def _upd(self):
        t, c = 0, 0
        for e in self.qty_entries:
            try:
                q = int(e.get())
                if q > 0: t += q; c += 1
            except ValueError:
                pass
        self.tot.config(text=f"{c} cards | qty: {t}")
    
    def _export(self):
        data = []
        for i, (name, num) in enumerate(self.cards):
            try:
                q = int(self.qty_entries[i].get())
                if q > 0:
                    data.append({'name': name, 'set': 'WOE', 'collector_number': num, 'quantity': q})
            except ValueError:
                pass
        
        if not data:
            messagebox.showwarning("Empty", "No qty entered")
            return
        
        lp = r"E:\MTTGG\PYTHON SOURCE FILES\nexus_v2\data\nexus_library.json"
        try:
            with open(lp) as f: lib = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            lib = {"cards": []}
        if "cards" not in lib: lib["cards"] = []
        
        for c in data:
            found = False
            for lc in lib["cards"]:
                if lc.get('collector_number') == c['collector_number'] and lc.get('set') == 'WOE':
                    lc['quantity'] = lc.get('quantity', 0) + c['quantity']
                    found = True
                    break
            if not found:
                lib["cards"].append({**c, 'condition': 'NM', 'added': datetime.now().isoformat()})
        
        with open(lp, 'w') as f: json.dump(lib, f, indent=2)
        messagebox.showinfo("Done", f"Added {len(data)} cards to NEXUS!")
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    SetListEntry().run()
