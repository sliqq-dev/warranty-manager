# ── Windows DPI fix (must be FIRST, before tkinter is imported) ───────────────
import sys, os, ctypes

if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()   # Fallback
        except Exception:
            pass

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3, shutil
from datetime import datetime
from PIL import Image, ImageTk
from auth import LoginScreen, AdminPanel, Session, init_auth_db

# ── Paths ─────────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR   = os.path.join(BASE_DIR, "warranty_data")
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
DB_PATH    = os.path.join(DATA_DIR, "warranties.db")
os.makedirs(PHOTOS_DIR, exist_ok=True)

# ── Design tokens ─────────────────────────────────────────────────────────────
BG        = "#0F0F17"
SIDEBAR   = "#13131E"
SURFACE   = "#1A1A2E"
SURFACE2  = "#21213A"
BORDER    = "#2A2A45"
ACCENT    = "#7C6EF5"
TEXT      = "#EEEEF5"
TEXT2     = "#8888AA"
TEXT3     = "#55556A"

SUCCESS   = "#34D399"; SUCCESS_BG = "#0F2922"
WARNING   = "#FBBF24"; WARNING_BG = "#2A1E04"
DANGER    = "#F87171"; DANGER_BG  = "#2A0F0F"
INFO      = "#60A5FA"; INFO_BG    = "#0F1E2A"
VIOLET    = "#C084FC"; VIOLET_BG  = "#1E1028"

STATUS_META = {
    "Open":        (INFO,    INFO_BG,    "●"),
    "In Progress": (WARNING, WARNING_BG, "◎"),
    "Pending":     (VIOLET,  VIOLET_BG,  "◷"),
    "Resolved":    (SUCCESS, SUCCESS_BG, "✓"),
    "Closed":      (TEXT3,   SURFACE,    "○"),
    "Rejected":    (DANGER,  DANGER_BG,  "✕"),
}
PRIORITY_META = {
    "Low": TEXT3, "Normal": TEXT2, "High": WARNING, "Critical": DANGER
}

F_DISPLAY = ("Segoe UI", 22, "bold")
F_H1      = ("Segoe UI", 14, "bold")
F_H2      = ("Segoe UI", 12, "bold")
F_BODY    = ("Segoe UI", 11)
F_SMALL   = ("Segoe UI",  9)
F_LABEL   = ("Segoe UI",  9, "bold")
F_MONO    = ("Consolas", 10)

# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS warranties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_no TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        customer TEXT, product TEXT, serial_no TEXT,
        status TEXT DEFAULT 'Open',
        priority TEXT DEFAULT 'Normal',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        description TEXT
    );
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        warranty_id INTEGER NOT NULL,
        author TEXT, content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(warranty_id) REFERENCES warranties(id)
    );
    CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        warranty_id INTEGER NOT NULL,
        filename TEXT NOT NULL, caption TEXT,
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY(warranty_id) REFERENCES warranties(id)
    );
    """)
    db.close()

def next_ticket():
    db = get_db()
    n  = db.execute("SELECT COUNT(*) FROM warranties").fetchone()[0]
    db.close()
    return f"WRT-{n+1:04d}"

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def fmt_dt(s, short=False):
    try:
        d = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return d.strftime("%d %b %Y") if short else d.strftime("%d %b %Y  %H:%M")
    except Exception:
        return s or "—"

# ── Widget helpers ─────────────────────────────────────────────────────────────
def flat_entry(parent, width=24, **kw):
    return tk.Entry(parent, width=width, bg=SURFACE2, fg=TEXT,
                    insertbackground=TEXT, relief="flat", font=F_BODY,
                    highlightthickness=1, highlightcolor=ACCENT,
                    highlightbackground=BORDER, bd=0, **kw)

def flat_text(parent, height=5, **kw):
    return tk.Text(parent, height=height, bg=SURFACE2, fg=TEXT,
                   insertbackground=TEXT, relief="flat", font=F_BODY,
                   highlightthickness=1, highlightcolor=ACCENT,
                   highlightbackground=BORDER, wrap="word", bd=0, **kw)

def h_rule(parent, color=BORDER):
    tk.Frame(parent, bg=color, height=1).pack(fill="x")

def btn(parent, text, cmd, bg=ACCENT, fg=TEXT, font=F_BODY, pad=(16, 7), **kw):
    b = tk.Button(parent, text=text, command=cmd,
                  bg=bg, fg=fg, activebackground=_h(bg, 20),
                  activeforeground=fg, relief="flat", cursor="hand2",
                  font=font, padx=pad[0], pady=pad[1], bd=0, **kw)
    b.bind("<Enter>", lambda e: b.config(bg=_h(bg, 20)))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b

def icon_btn(parent, text, cmd, bg=SURFACE2, fg=TEXT2, **kw):
    return btn(parent, text, cmd, bg=bg, fg=fg, font=F_SMALL, pad=(10, 5), **kw)

def _h(hex_c, amt=20):
    h = hex_c.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#{:02x}{:02x}{:02x}".format(min(255,r+amt), min(255,g+amt), min(255,b+amt))

def scroll_frame(parent, bg=BG):
    outer  = tk.Frame(parent, bg=bg)
    canvas = tk.Canvas(outer, bg=bg, highlightthickness=0)
    sb     = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(canvas, bg=bg)
    win   = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>",
                lambda e: canvas.itemconfig(win, width=e.width))
    canvas.bind_all("<MouseWheel>",
                    lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
    return outer, inner

def section_header(parent, title, bg=BG):
    row = tk.Frame(parent, bg=bg)
    row.pack(fill="x", pady=(20, 8))
    tk.Label(row, text=title.upper(), bg=bg, fg=TEXT3,
             font=F_LABEL, anchor="w").pack(side="left")
    tk.Frame(row, bg=BORDER, height=1).pack(
        side="left", fill="x", expand=True, padx=(10, 0), pady=6)

def style_ttk():
    s = ttk.Style()
    try:    s.theme_use("clam")
    except: pass
    s.configure("D.TCombobox",
                fieldbackground=SURFACE2, background=SURFACE2,
                foreground=TEXT, selectbackground=SURFACE2,
                selectforeground=TEXT, arrowcolor=TEXT2,
                bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
    s.map("D.TCombobox",
          fieldbackground=[("readonly", SURFACE2)],
          foreground=[("readonly", TEXT)])
    s.configure("D.TNotebook", background=BG, borderwidth=0, tabmargins=0)
    s.configure("D.TNotebook.Tab",
                background=SURFACE, foreground=TEXT2,
                padding=[18, 8], font=F_BODY, borderwidth=0)
    s.map("D.TNotebook.Tab",
          background=[("selected", BG)],
          foreground=[("selected", TEXT)])

def flat_combo(parent, var, values, width=14):
    return ttk.Combobox(parent, textvariable=var, values=values,
                        width=width, state="readonly", font=F_BODY,
                        style="D.TCombobox")

# ══════════════════════════════════════════════════════════════════════════════
#  TICKET FORM DIALOG
# ══════════════════════════════════════════════════════════════════════════════
class TicketForm(tk.Toplevel):
    def __init__(self, master, title_text="New Ticket", prefill=None, on_save=None):
        super().__init__(master)
        self.on_save = on_save
        self.title(title_text)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self._build(prefill or {})
        self.update_idletasks()
        pw, ph = master.winfo_rootx(), master.winfo_rooty()
        pw2, ph2 = master.winfo_width(), master.winfo_height()
        w, h = 560, 640
        self.geometry(f"{w}x{h}+{pw+(pw2-w)//2}+{ph+(ph2-h)//2}")

    def _build(self, p):
        hdr = tk.Frame(self, bg=SURFACE, pady=20)
        hdr.pack(fill="x")
        tk.Label(hdr, text=self.title(), bg=SURFACE, fg=TEXT,
                 font=F_DISPLAY, padx=28).pack(anchor="w")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=28, pady=16)

        def lf(text):
            tk.Label(body, text=text, bg=BG, fg=TEXT3,
                     font=F_LABEL, anchor="w").pack(fill="x", pady=(10, 2))

        lf("TICKET TITLE")
        self.e_title = flat_entry(body, width=50)
        self.e_title.pack(fill="x", ipady=6)
        self.e_title.insert(0, p.get("title", ""))

        row1 = tk.Frame(body, bg=BG)
        row1.pack(fill="x", pady=(10, 0))
        row1.columnconfigure(0, weight=1)
        row1.columnconfigure(1, weight=1)

        def lfc(parent, text):
            tk.Label(parent, text=text, bg=BG, fg=TEXT3,
                     font=F_LABEL, anchor="w").pack(fill="x", pady=(0, 2))

        col0 = tk.Frame(row1, bg=BG)
        col0.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        lfc(col0, "CUSTOMER / CLIENT")
        self.e_customer = flat_entry(col0, width=22)
        self.e_customer.pack(fill="x", ipady=6)
        self.e_customer.insert(0, p.get("customer", "") or "")

        col1 = tk.Frame(row1, bg=BG)
        col1.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        lfc(col1, "PRODUCT / ITEM")
        self.e_product = flat_entry(col1, width=22)
        self.e_product.pack(fill="x", ipady=6)
        self.e_product.insert(0, p.get("product", "") or "")

        row2 = tk.Frame(body, bg=BG)
        row2.pack(fill="x", pady=(10, 0))
        row2.columnconfigure(0, weight=1)
        row2.columnconfigure(1, weight=1)

        col2 = tk.Frame(row2, bg=BG)
        col2.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        lfc(col2, "SERIAL NUMBER")
        self.e_serial = flat_entry(col2, width=22)
        self.e_serial.pack(fill="x", ipady=6)
        self.e_serial.insert(0, p.get("serial_no", "") or "")

        col3 = tk.Frame(row2, bg=BG)
        col3.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        lfc(col3, "PRIORITY")
        self.pri_var = tk.StringVar(value=p.get("priority", "Normal"))
        flat_combo(col3, self.pri_var,
                   ["Low", "Normal", "High", "Critical"], width=20).pack(
            fill="x", ipady=4)

        lf("DESCRIPTION")
        self.desc = flat_text(body, height=6)
        self.desc.pack(fill="x")
        self.desc.insert("1.0", p.get("description", "") or "")

        foot = tk.Frame(self, bg=SURFACE, pady=14)
        foot.pack(fill="x", side="bottom")
        btn(foot, "Cancel", self.destroy, bg=SURFACE2, fg=TEXT2).pack(side="right", padx=(0, 28))
        btn(foot, "Save Ticket", self._save, bg=ACCENT).pack(side="right", padx=(0, 8))

    def _save(self):
        title = self.e_title.get().strip()
        if not title:
            messagebox.showwarning("Required", "Ticket title is required.", parent=self)
            return
        if self.on_save:
            self.on_save(dict(
                title      = title,
                customer   = self.e_customer.get().strip() or None,
                product    = self.e_product.get().strip()  or None,
                serial_no  = self.e_serial.get().strip()   or None,
                priority   = self.pri_var.get(),
                description= self.desc.get("1.0", "end").strip() or None,
            ))
        self.destroy()

# ══════════════════════════════════════════════════════════════════════════════
#  STATUS PICKER
# ══════════════════════════════════════════════════════════════════════════════
class StatusPicker(tk.Toplevel):
    def __init__(self, master, current, on_pick):
        super().__init__(master)
        self.configure(bg=SURFACE)
        self.overrideredirect(True)
        self.grab_set()
        for status, (fg, bg, icon) in STATUS_META.items():
            is_cur = (status == current)
            row = tk.Frame(self, bg=SURFACE2 if is_cur else SURFACE, cursor="hand2")
            row.pack(fill="x", padx=1, pady=1)
            tk.Label(row, text=icon, bg=row["bg"], fg=fg,
                     font=F_BODY, width=2).pack(side="left", padx=(12, 4), pady=10)
            tk.Label(row, text=status, bg=row["bg"],
                     fg=TEXT if is_cur else TEXT2,
                     font=F_H2 if is_cur else F_BODY).pack(side="left", pady=10)
            if is_cur:
                tk.Label(row, text="current", bg=row["bg"],
                         fg=TEXT3, font=F_SMALL).pack(side="right", padx=12)
            def _click(e, s=status):
                on_pick(s); self.destroy()
            row.bind("<Button-1>", _click)
            for child in row.winfo_children():
                child.bind("<Button-1>", _click)
        self.update_idletasks()
        mx = master.winfo_rootx() + master.winfo_width()//2  - self.winfo_width()//2
        my = master.winfo_rooty() + master.winfo_height()//2 - self.winfo_height()//2
        self.geometry(f"+{mx}+{my}")
        self.bind("<FocusOut>", lambda e: self.destroy())

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        init_db()

        # ── Critical: disable Windows DPI virtual scaling BEFORE anything draws
        if sys.platform == "win32":
            self.tk.call("tk", "scaling", 1.0)

        style_ttk()
        self.title("Warranty Manager")
        self.configure(bg=BG)

        # Window sizing — use actual screen pixels
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = min(1380, int(sw * 0.88))
        h  = min(840,  int(sh * 0.88))
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(900, 580)

        self._active_id  = None
        self._photo_refs = []
        self._author_var = tk.StringVar()
        self._build()
        self.refresh_list()

    # ── Shell ──────────────────────────────────────────────────────────────────
    def _build(self):
        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(root, bg=SIDEBAR, width=300)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        tk.Frame(root, bg=BORDER, width=1).pack(side="left", fill="y")

        self.main = tk.Frame(root, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)
        self._show_empty()

    # ── Sidebar ────────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = self.sidebar

        logo = tk.Frame(sb, bg=SIDEBAR, pady=16)
        logo.pack(fill="x", padx=20)
        tk.Label(logo, text="⚙", bg=SIDEBAR, fg=ACCENT,
                 font=("Segoe UI", 18)).pack(side="left")
        tk.Label(logo, text="  Warranty", bg=SIDEBAR, fg=TEXT,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Label(logo, text=" Manager", bg=SIDEBAR, fg=TEXT2,
                 font=("Segoe UI", 14)).pack(side="left")

        h_rule(sb, BORDER)

        # User info bar
        user_bar = tk.Frame(sb, bg=SURFACE, padx=16, pady=10)
        user_bar.pack(fill="x")
        tk.Label(user_bar, text="👤", bg=SURFACE, fg=TEXT2,
                 font=("Segoe UI", 11)).pack(side="left")
        tk.Label(user_bar, text=f"  {Session.full_name}",
                 bg=SURFACE, fg=TEXT, font=F_BODY).pack(side="left")
        role_col = ACCENT if Session.is_admin() else TEXT3
        tk.Label(user_bar, text=Session.role, bg=SURFACE,
                 fg=role_col, font=F_SMALL).pack(side="right")

        h_rule(sb, BORDER)

        wrap = tk.Frame(sb, bg=SIDEBAR, pady=14, padx=16)
        wrap.pack(fill="x")
        btn(wrap, "+ New Ticket", self._new_ticket, bg=ACCENT).pack(fill="x", ipady=3)

        # Admin panel button (only visible to admins)
        if Session.is_admin():
            btn(wrap, "⚙  Admin Panel",
                lambda: AdminPanel(self),
                bg=SURFACE2, fg=TEXT2).pack(fill="x", ipady=3, pady=(6,0))

        btn(wrap, "⇤  Logout", self._logout,
            bg=SURFACE2, fg=TEXT2).pack(fill="x", ipady=3, pady=(4,0))

        sf = tk.Frame(sb, bg=SIDEBAR, padx=16)
        sf.pack(fill="x", pady=(4, 0))
        tk.Label(sf, text="SEARCH", bg=SIDEBAR, fg=TEXT3,
                 font=F_LABEL).pack(anchor="w", pady=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_list())
        se = flat_entry(sf, width=28)
        se.configure(textvariable=self.search_var, bg=SURFACE2)
        se.pack(fill="x", ipady=6)

        ff = tk.Frame(sb, bg=SIDEBAR, padx=16, pady=8)
        ff.pack(fill="x")
        tk.Label(ff, text="FILTER BY STATUS", bg=SIDEBAR, fg=TEXT3,
                 font=F_LABEL).pack(anchor="w", pady=(0, 4))
        self.filter_var = tk.StringVar(value="All")
        cb = flat_combo(ff, self.filter_var,
                        ["All"] + list(STATUS_META.keys()), width=24)
        cb.pack(fill="x", ipady=3)
        cb.bind("<<ComboboxSelected>>", lambda _: self.refresh_list())

        h_rule(sb, BORDER)

        self.stats_bar = tk.Frame(sb, bg=SIDEBAR, padx=16, pady=10)
        self.stats_bar.pack(fill="x")

        h_rule(sb, BORDER)

        list_outer, self.list_inner = scroll_frame(sb, bg=SIDEBAR)
        list_outer.pack(fill="both", expand=True)

    # ── Ticket list ────────────────────────────────────────────────────────────
    def refresh_list(self):
        for w in self.list_inner.winfo_children():
            w.destroy()
        for w in self.stats_bar.winfo_children():
            w.destroy()

        db   = get_db()
        rows = db.execute(
            "SELECT * FROM warranties ORDER BY updated_at DESC").fetchall()
        db.close()

        search  = self.search_var.get().lower()
        fstatus = self.filter_var.get()
        visible = [r for r in rows
                   if (fstatus == "All" or r["status"] == fstatus)
                   and (not search or search in
                        f'{r["ticket_no"]} {r["title"]} {r["customer"] or ""}'.lower())]

        active = sum(1 for r in rows
                     if r["status"] in ("Open", "In Progress", "Pending"))
        for txt, val, col in [("TOTAL", str(len(rows)), TEXT2),
                               ("ACTIVE", str(active), WARNING),
                               ("SHOWN", str(len(visible)), ACCENT)]:
            f = tk.Frame(self.stats_bar, bg=SIDEBAR)
            f.pack(side="left", expand=True)
            tk.Label(f, text=val, bg=SIDEBAR, fg=col,
                     font=("Segoe UI", 16, "bold")).pack()
            tk.Label(f, text=txt, bg=SIDEBAR, fg=TEXT3, font=F_LABEL).pack()

        for r in visible:
            self._ticket_card(r)
        if not visible:
            tk.Label(self.list_inner, text="No tickets found",
                     bg=SIDEBAR, fg=TEXT3, font=F_BODY).pack(pady=32)

    def _ticket_card(self, r):
        fg, bg_pill, icon = STATUS_META.get(r["status"], (TEXT3, SURFACE, "○"))
        is_active = (r["id"] == self._active_id)
        card_bg   = SURFACE2 if is_active else SIDEBAR

        card = tk.Frame(self.list_inner, bg=card_bg, cursor="hand2")
        card.pack(fill="x")
        tk.Frame(card, bg=ACCENT if is_active else BORDER, width=3).pack(
            side="left", fill="y")

        body = tk.Frame(card, bg=card_bg, pady=12, padx=14)
        body.pack(side="left", fill="both", expand=True)

        r1 = tk.Frame(body, bg=card_bg)
        r1.pack(fill="x")
        tk.Label(r1, text=r["ticket_no"], bg=card_bg, fg=TEXT3,
                 font=F_MONO).pack(side="left")
        pf = tk.Frame(r1, bg=bg_pill)
        pf.pack(side="right")
        tk.Label(pf, text=f"{icon} {r['status']}", bg=bg_pill, fg=fg,
                 font=F_SMALL, padx=7, pady=2).pack()

        tk.Label(body, text=r["title"], bg=card_bg, fg=TEXT, font=F_H2,
                 anchor="w", wraplength=210, justify="left").pack(
            fill="x", pady=(3, 1))

        meta = "  ·  ".join(filter(None, [r["customer"], r["product"]])) or "—"
        tk.Label(body, text=meta, bg=card_bg, fg=TEXT3,
                 font=F_SMALL, anchor="w").pack(fill="x")

        r4 = tk.Frame(body, bg=card_bg)
        r4.pack(fill="x", pady=(4, 0))
        tk.Label(r4, text=fmt_dt(r["updated_at"], short=True),
                 bg=card_bg, fg=TEXT3, font=F_SMALL).pack(side="left")
        tk.Label(r4, text=f"● {r['priority']}",
                 bg=card_bg, fg=PRIORITY_META.get(r["priority"], TEXT3),
                 font=F_SMALL).pack(side="right")

        tk.Frame(self.list_inner, bg=BORDER, height=1).pack(fill="x")

        def on_click(e, wid=r["id"]):
            self._active_id = wid
            self.refresh_list()
            self.open_detail(wid)

        all_widgets = ([card, body, r1, r4, pf]
                       + list(body.winfo_children())
                       + list(r1.winfo_children())
                       + list(r4.winfo_children()))
        for w in all_widgets:
            try: w.bind("<Button-1>", on_click)
            except: pass

    # ── Empty state ────────────────────────────────────────────────────────────
    def _show_empty(self):
        for w in self.main.winfo_children():
            w.destroy()
        f = tk.Frame(self.main, bg=BG)
        f.place(relx=.5, rely=.5, anchor="center")
        tk.Label(f, text="📋", font=("Segoe UI", 52), bg=BG, fg=BORDER).pack()
        tk.Label(f, text="Select a ticket to view details",
                 font=F_BODY, bg=BG, fg=TEXT3).pack(pady=(8, 16))
        btn(f, "+ Create your first ticket", self._new_ticket, bg=ACCENT).pack()

    # ══════════════════════════════════════════════════════════════════════════
    #  DETAIL VIEW
    # ══════════════════════════════════════════════════════════════════════════
    def open_detail(self, wid):
        for w in self.main.winfo_children():
            w.destroy()
        db     = get_db()
        row    = db.execute(
            "SELECT * FROM warranties WHERE id=?", (wid,)).fetchone()
        notes  = db.execute(
            "SELECT * FROM notes WHERE warranty_id=? ORDER BY created_at DESC",
            (wid,)).fetchall()
        photos = db.execute(
            "SELECT * FROM photos WHERE warranty_id=? ORDER BY uploaded_at",
            (wid,)).fetchall()
        db.close()
        if not row:
            self._show_empty(); return

        fg, bg_pill, icon = STATUS_META.get(row["status"], (TEXT3, SURFACE, "○"))

        # Header
        hdr = tk.Frame(self.main, bg=SURFACE)
        hdr.pack(fill="x")
        tk.Frame(hdr, bg=fg, height=3).pack(fill="x")
        hi = tk.Frame(hdr, bg=SURFACE, padx=28, pady=18)
        hi.pack(fill="x")

        left = tk.Frame(hi, bg=SURFACE)
        left.pack(side="left", fill="both", expand=True)
        tk.Label(left, text=row["ticket_no"], bg=SURFACE, fg=TEXT3,
                 font=F_MONO).pack(anchor="w")
        tk.Label(left, text=row["title"], bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 17, "bold"),
                 wraplength=680, justify="left").pack(anchor="w", pady=(2, 4))
        meta = "  ·  ".join(filter(None, [
            row["customer"], row["product"],
            f"S/N {row['serial_no']}" if row["serial_no"] else None]))
        tk.Label(left, text=meta or "No additional info",
                 bg=SURFACE, fg=TEXT3, font=F_SMALL).pack(anchor="w")

        right = tk.Frame(hi, bg=SURFACE)
        right.pack(side="right", anchor="n")

        def change_status():
            StatusPicker(self, row["status"],
                         lambda s: self._set_status(wid, s))

        tk.Button(right, text=f"{icon}  {row['status']}",
                  bg=bg_pill, fg=fg, activebackground=_h(bg_pill, 10),
                  activeforeground=fg, relief="flat", cursor="hand2",
                  font=F_H2, padx=14, pady=6, bd=0,
                  command=change_status).pack(pady=(0, 8))

        ar = tk.Frame(right, bg=SURFACE)
        ar.pack()
        icon_btn(ar, "✎  Edit",   lambda: self._edit_ticket(wid)).pack(side="left", padx=2)
        icon_btn(ar, "🗑  Delete", lambda: self._delete_ticket(wid),
                 bg=DANGER_BG, fg=DANGER).pack(side="left", padx=2)

        # Notebook
        nb = ttk.Notebook(self.main, style="D.TNotebook")
        nb.pack(fill="both", expand=True)
        td = tk.Frame(nb, bg=BG)
        tn = tk.Frame(nb, bg=BG)
        tp = tk.Frame(nb, bg=BG)
        nb.add(td, text="   Details   ")
        nb.add(tn, text=f"   Notes  ({len(notes)})   ")
        nb.add(tp, text=f"   Photos  ({len(photos)})   ")
        self._tab_details(td, row)
        self._tab_notes(tn, wid, notes)
        self._tab_photos(tp, wid, photos)

    # ── Details tab ────────────────────────────────────────────────────────────
    def _tab_details(self, parent, r):
        outer, inner = scroll_frame(parent)
        outer.pack(fill="both", expand=True)
        inner.configure(padx=32)
        section_header(inner, "Ticket Info")
        grid = tk.Frame(inner, bg=BG)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(3, weight=1)

        def field(lbl, val, row, col=0):
            tk.Label(grid, text=lbl, bg=BG, fg=TEXT3,
                     font=F_LABEL, anchor="w").grid(
                row=row, column=col, sticky="nw", padx=(0, 20), pady=6)
            tk.Label(grid, text=val or "—", bg=BG, fg=TEXT,
                     font=F_BODY, anchor="w", wraplength=300,
                     justify="left").grid(row=row, column=col+1, sticky="w", pady=6)

        field("Status",   r["status"],   0, 0)
        field("Priority", r["priority"], 0, 2)
        field("Customer", r["customer"], 1, 0)
        field("Product",  r["product"],  1, 2)
        field("Serial No",r["serial_no"],2, 0)
        field("Created",  fmt_dt(r["created_at"]), 3, 0)
        field("Updated",  fmt_dt(r["updated_at"]), 3, 2)

        section_header(inner, "Description")
        db = tk.Text(inner, height=8, bg=SURFACE, fg=TEXT, relief="flat",
                     font=F_BODY, wrap="word", highlightthickness=0,
                     bd=0, padx=16, pady=12, cursor="arrow")
        db.insert("1.0", r["description"] or "No description provided.")
        db.config(state="disabled")
        db.pack(fill="x", pady=(0, 24))

    # ── Notes tab ──────────────────────────────────────────────────────────────
    def _tab_notes(self, parent, wid, notes):
        compose = tk.Frame(parent, bg=SURFACE, pady=16)
        compose.pack(fill="x")
        ic = tk.Frame(compose, bg=SURFACE, padx=28)
        ic.pack(fill="x")
        tk.Label(ic, text="ADD NOTE", bg=SURFACE, fg=TEXT3,
                 font=F_LABEL).pack(anchor="w", pady=(0, 6))
        ra = tk.Frame(ic, bg=SURFACE)
        ra.pack(fill="x", pady=(0, 8))
        tk.Label(ra, text="Your name", bg=SURFACE, fg=TEXT3,
                 font=F_SMALL).pack(side="left", padx=(0, 8))
        ae = flat_entry(ra, width=22)
        ae.configure(textvariable=self._author_var)
        ae.pack(side="left", ipady=4)
        nb_text = flat_text(ic, height=3)
        nb_text.pack(fill="x")

        def post():
            content = nb_text.get("1.0", "end").strip()
            if not content: return
            author = self._author_var.get().strip() or "Staff"
            db = get_db()
            db.execute(
                "INSERT INTO notes (warranty_id,author,content,created_at) VALUES(?,?,?,?)",
                (wid, author, content, now_str()))
            db.execute("UPDATE warranties SET updated_at=? WHERE id=?",
                       (now_str(), wid))
            db.commit(); db.close()
            self.refresh_list(); self.open_detail(wid)

        btn(ic, "Post Note", post, bg=ACCENT).pack(anchor="e", pady=(8, 0))
        h_rule(parent, BORDER)

        outer, inner = scroll_frame(parent)
        outer.pack(fill="both", expand=True)
        inner.configure(padx=28)

        if not notes:
            tk.Label(inner, text="No notes yet.",
                     bg=BG, fg=TEXT3, font=F_BODY).pack(pady=40)
            return

        for n in notes:
            card = tk.Frame(inner, bg=SURFACE,
                            highlightthickness=1, highlightbackground=BORDER)
            card.pack(fill="x", pady=(14, 0))
            top = tk.Frame(card, bg=SURFACE, padx=16, pady=10)
            top.pack(fill="x")
            tk.Label(top, text=n["author"] or "Staff",
                     bg=SURFACE, fg=ACCENT, font=F_H2).pack(side="left")
            tk.Label(top, text=fmt_dt(n["created_at"]),
                     bg=SURFACE, fg=TEXT3, font=F_SMALL).pack(side="right")
            tk.Frame(card, bg=BORDER, height=1).pack(fill="x")
            tk.Label(card, text=n["content"], bg=SURFACE, fg=TEXT,
                     font=F_BODY, anchor="w", wraplength=700,
                     justify="left", padx=16, pady=12).pack(fill="x")

    # ── Photos tab ─────────────────────────────────────────────────────────────
    def _tab_photos(self, parent, wid, photos):
        top_bar = tk.Frame(parent, bg=BG, pady=14, padx=28)
        top_bar.pack(fill="x")
        tk.Label(top_bar, text="ATTACHMENTS", bg=BG, fg=TEXT3,
                 font=F_LABEL).pack(side="left")
        btn(top_bar, "+ Attach Photos",
            lambda: self._attach_photos(wid), bg=ACCENT).pack(side="right")
        h_rule(parent, BORDER)

        outer, inner = scroll_frame(parent)
        outer.pack(fill="both", expand=True)
        inner.configure(padx=28)
        self._photo_refs = []

        if not photos:
            ef = tk.Frame(inner, bg=BG)
            ef.pack(pady=60)
            tk.Label(ef, text="📎", font=("Segoe UI", 36),
                     bg=BG, fg=BORDER).pack()
            tk.Label(ef, text="No photos attached yet",
                     bg=BG, fg=TEXT3, font=F_BODY).pack(pady=8)
            btn(ef, "+ Attach Photos",
                lambda: self._attach_photos(wid), bg=ACCENT).pack()
            return

        COLS = 3
        grid = tk.Frame(inner, bg=BG)
        grid.pack(fill="x", pady=14)
        for c in range(COLS):
            grid.columnconfigure(c, weight=1)

        for idx, ph in enumerate(photos):
            path = os.path.join(PHOTOS_DIR, ph["filename"])
            r, c = divmod(idx, COLS)
            cell = tk.Frame(grid, bg=SURFACE,
                            highlightthickness=1, highlightbackground=BORDER)
            cell.grid(row=r, column=c, padx=8, pady=8, sticky="n")
            try:
                img = Image.open(path)
                img.thumbnail((210, 158))
                tk_img = ImageTk.PhotoImage(img)
                self._photo_refs.append(tk_img)
                lbl = tk.Label(cell, image=tk_img, bg=SURFACE, cursor="hand2")
                lbl.pack(padx=1, pady=1)
                lbl.bind("<Button-1>", lambda e, p=path: self._full_image(p))
            except Exception:
                tk.Label(cell, text="⚠ Cannot load", bg=SURFACE,
                         fg=DANGER, font=F_SMALL, padx=20, pady=30).pack()
            foot = tk.Frame(cell, bg=SURFACE2, padx=10, pady=6)
            foot.pack(fill="x")
            cap = ph["caption"] or os.path.basename(ph["filename"])
            tk.Label(foot, text=cap, bg=SURFACE2, fg=TEXT3,
                     font=F_SMALL, anchor="w", wraplength=190).pack(side="left")
            icon_btn(foot, "✕",
                     lambda p=ph["id"], f=ph["filename"]: self._del_photo(wid, p, f),
                     bg=DANGER_BG, fg=DANGER).pack(side="right")

    def _attach_photos(self, wid):
        paths = filedialog.askopenfilenames(
            title="Select Photos",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tiff"),
                       ("All files", "*.*")])
        if not paths: return
        db = get_db()
        for path in paths:
            ext   = os.path.splitext(path)[1].lower()
            ts    = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            fname = f"w{wid}_{ts}{ext}"
            shutil.copy2(path, os.path.join(PHOTOS_DIR, fname))
            cap = simpledialog.askstring(
                "Caption", f"Caption for {os.path.basename(path)}:",
                parent=self) or ""
            db.execute(
                "INSERT INTO photos (warranty_id,filename,caption,uploaded_at) VALUES(?,?,?,?)",
                (wid, fname, cap.strip() or None, now_str()))
            db.execute("UPDATE warranties SET updated_at=? WHERE id=?",
                       (now_str(), wid))
        db.commit(); db.close()
        self.refresh_list(); self.open_detail(wid)

    def _del_photo(self, wid, pid, fname):
        if not messagebox.askyesno("Remove Photo", "Remove this photo?", parent=self):
            return
        db = get_db()
        db.execute("DELETE FROM photos WHERE id=?", (pid,))
        db.commit(); db.close()
        try: os.remove(os.path.join(PHOTOS_DIR, fname))
        except: pass
        self.open_detail(wid)

    def _full_image(self, path):
        win = tk.Toplevel(self)
        win.title(os.path.basename(path))
        win.configure(bg="#000")
        try:
            img = Image.open(path)
            img.thumbnail((self.winfo_screenwidth()-100,
                           self.winfo_screenheight()-120))
            tk_img = ImageTk.PhotoImage(img)
            lbl = tk.Label(win, image=tk_img, bg="#000")
            lbl.image = tk_img
            lbl.pack()
        except Exception as ex:
            tk.Label(win, text=f"Cannot open:\n{ex}",
                     bg="#000", fg="white").pack(padx=40, pady=40)

    # ── Logout ─────────────────────────────────────────────────────────────────
    def _logout(self):
        Session.log("Logout")
        Session.logout()
        self.destroy()

    # ── CRUD ───────────────────────────────────────────────────────────────────
    def _new_ticket(self):
        def save(data):
            db = get_db()
            db.execute("""INSERT INTO warranties
                (ticket_no,title,customer,product,serial_no,
                 status,priority,created_at,updated_at,description)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (next_ticket(), data["title"], data["customer"],
                 data["product"], data["serial_no"], "Open",
                 data["priority"], now_str(), now_str(), data["description"]))
            db.commit()
            wid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.close()
            Session.log("Created ticket", data["title"])
            self._active_id = wid
            self.refresh_list(); self.open_detail(wid)
        TicketForm(self, "New Ticket", on_save=save)

    def _edit_ticket(self, wid):
        db  = get_db()
        row = db.execute("SELECT * FROM warranties WHERE id=?", (wid,)).fetchone()
        db.close()
        def save(data):
            db2 = get_db()
            db2.execute("""UPDATE warranties SET title=?,customer=?,product=?,
                serial_no=?,priority=?,description=?,updated_at=? WHERE id=?""",
                (data["title"], data["customer"], data["product"],
                 data["serial_no"], data["priority"], data["description"],
                 now_str(), wid))
            db2.commit(); db2.close()
            Session.log("Edited ticket", data["title"])
            self.refresh_list(); self.open_detail(wid)
        TicketForm(self, "Edit Ticket", prefill=dict(row), on_save=save)

    def _set_status(self, wid, status):
        db  = get_db()
        row = db.execute("SELECT ticket_no FROM warranties WHERE id=?", (wid,)).fetchone()
        db.execute("UPDATE warranties SET status=?,updated_at=? WHERE id=?",
                   (status, now_str(), wid))
        db.commit(); db.close()
        Session.log("Status change", f"{row['ticket_no']} -> {status}")
        self.refresh_list(); self.open_detail(wid)

    def _delete_ticket(self, wid):
        if not messagebox.askyesno(
                "Delete Ticket",
                "Permanently delete this ticket and all its data?\nThis cannot be undone.",
                parent=self, icon="warning"):
            return
        db  = get_db()
        row = db.execute("SELECT ticket_no FROM warranties WHERE id=?", (wid,)).fetchone()
        for ph in db.execute(
                "SELECT filename FROM photos WHERE warranty_id=?", (wid,)).fetchall():
            try: os.remove(os.path.join(PHOTOS_DIR, ph["filename"]))
            except: pass
        db.execute("DELETE FROM photos WHERE warranty_id=?", (wid,))
        db.execute("DELETE FROM notes  WHERE warranty_id=?", (wid,))
        db.execute("DELETE FROM warranties WHERE id=?", (wid,))
        db.commit(); db.close()
        Session.log("Deleted ticket", row["ticket_no"])
        self._active_id = None
        self.refresh_list(); self._show_empty()

# ── Entry ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from updater import check_and_update
    check_and_update()

    # Login loop — keeps showing login screen after logout
    while True:
        login = LoginScreen()
        login.mainloop()
        if not login.success:
            break
        app = App()
        app.mainloop()
        # If session was cleared (logout), loop back to login
        if Session.username is not None:
            break
