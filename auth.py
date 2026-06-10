"""
Authentication + User Management module for Warranty Manager.
Handles login, sessions, user CRUD, password hashing, activity logging.
"""

import sqlite3
import hashlib
import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

# ── Resolve DB path (shared or local) ────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def get_data_dir():
    """Returns the data directory — shared network path or local fallback."""
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
            path = cfg.get("data_path", "")
            if path and os.path.isdir(path):
                return path
    except Exception:
        pass
    # Fallback to local
    local = os.path.join(BASE_DIR, "warranty_data")
    os.makedirs(local, exist_ok=True)
    return local

def get_auth_db():
    db_path = os.path.join(get_data_dir(), "warranties.db")
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c

def hash_password(password):
    return hashlib.sha256(password.strip().encode()).hexdigest()

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ── Schema ─────────────────────────────────────────────────────────────────────
def init_auth_db():
    db = get_auth_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT UNIQUE NOT NULL,
        full_name   TEXT NOT NULL,
        password    TEXT NOT NULL,
        role        TEXT DEFAULT 'Staff',
        active      INTEGER DEFAULT 1,
        created_at  TEXT NOT NULL,
        last_login  TEXT
    );
    CREATE TABLE IF NOT EXISTS activity_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        username    TEXT,
        action      TEXT NOT NULL,
        detail      TEXT,
        timestamp   TEXT NOT NULL
    );
    """)

    # Create default admin if no users exist
    count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        db.execute("""
            INSERT INTO users (username, full_name, password, role, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("admin", "Administrator", hash_password("admin123"),
              "Admin", 1, now_str()))
        db.commit()
    db.close()

# ── Session ───────────────────────────────────────────────────────────────────
class Session:
    """Global session — holds the currently logged-in user."""
    user_id   = None
    username  = None
    full_name = None
    role      = None

    @classmethod
    def login(cls, user_row):
        cls.user_id   = user_row["id"]
        cls.username  = user_row["username"]
        cls.full_name = user_row["full_name"]
        cls.role      = user_row["role"]
        db = get_auth_db()
        db.execute("UPDATE users SET last_login=? WHERE id=?",
                   (now_str(), cls.user_id))
        db.commit()
        db.close()

    @classmethod
    def logout(cls):
        cls.user_id = cls.username = cls.full_name = cls.role = None

    @classmethod
    def is_admin(cls):
        return cls.role == "Admin"

    @classmethod
    def log(cls, action, detail=None):
        try:
            db = get_auth_db()
            db.execute("""INSERT INTO activity_log
                (user_id, username, action, detail, timestamp)
                VALUES (?,?,?,?,?)""",
                (cls.user_id, cls.username, action, detail, now_str()))
            db.commit()
            db.close()
        except Exception:
            pass

# ── Design tokens (match main app) ───────────────────────────────────────────
BG      = "#0F0F17"
SURFACE = "#1A1A2E"
SURFACE2= "#21213A"
BORDER  = "#2A2A45"
ACCENT  = "#7C6EF5"
TEXT    = "#EEEEF5"
TEXT2   = "#8888AA"
TEXT3   = "#55556A"
SUCCESS = "#34D399"
DANGER  = "#F87171"
WARNING = "#FBBF24"

F_DISPLAY = ("Segoe UI", 22, "bold")
F_H1      = ("Segoe UI", 14, "bold")
F_H2      = ("Segoe UI", 12, "bold")
F_BODY    = ("Segoe UI", 11)
F_SMALL   = ("Segoe UI",  9)
F_LABEL   = ("Segoe UI",  9, "bold")

def _h(hex_c, amt=20):
    h = hex_c.lstrip("#")
    r,g,b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return "#{:02x}{:02x}{:02x}".format(
        min(255,r+amt), min(255,g+amt), min(255,b+amt))

def flat_entry(parent, width=24, show=None, **kw):
    e = tk.Entry(parent, width=width, bg=SURFACE2, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=F_BODY,
                 highlightthickness=1, highlightcolor=ACCENT,
                 highlightbackground=BORDER, bd=0, **kw)
    if show:
        e.config(show=show)
    return e

def btn(parent, text, cmd, bg=ACCENT, fg=TEXT, font=F_BODY, pad=(16,7), **kw):
    b = tk.Button(parent, text=text, command=cmd,
                  bg=bg, fg=fg, activebackground=_h(bg,20),
                  activeforeground=fg, relief="flat", cursor="hand2",
                  font=font, padx=pad[0], pady=pad[1], bd=0, **kw)
    b.bind("<Enter>", lambda e: b.config(bg=_h(bg,20)))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b

def h_rule(parent, color=BORDER):
    tk.Frame(parent, bg=color, height=1).pack(fill="x")

def style_ttk():
    s = ttk.Style()
    try: s.theme_use("clam")
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
                padding=[18,8], font=F_BODY, borderwidth=0)
    s.map("D.TNotebook.Tab",
          background=[("selected", BG)],
          foreground=[("selected", TEXT)])

# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN SCREEN
# ══════════════════════════════════════════════════════════════════════════════
class LoginScreen(tk.Tk):
    def __init__(self):
        super().__init__()
        init_auth_db()
        self.title("Warranty Manager — Login")
        self.configure(bg=BG)
        self.resizable(False, False)
        style_ttk()

        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                pass
            self.tk.call("tk", "scaling", 1.0)

        W, H = 420, 500
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        self.success = False
        self._build()

    def _build(self):
        # Top accent bar
        tk.Frame(self, bg=ACCENT, height=3).pack(fill="x")

        # Logo
        logo = tk.Frame(self, bg=BG, pady=36)
        logo.pack(fill="x")
        tk.Label(logo, text="⚙", font=("Segoe UI", 40),
                 bg=BG, fg=ACCENT).pack()
        tk.Label(logo, text="Warranty Manager",
                 font=("Segoe UI", 18, "bold"), bg=BG, fg=TEXT).pack(pady=(8,2))
        tk.Label(logo, text="Sign in to continue",
                 font=F_SMALL, bg=BG, fg=TEXT3).pack()

        # Form card
        card = tk.Frame(self, bg=SURFACE, padx=36, pady=28)
        card.pack(fill="x", padx=32)

        tk.Label(card, text="USERNAME", bg=SURFACE,
                 fg=TEXT3, font=F_LABEL, anchor="w").pack(fill="x", pady=(0,4))
        self.e_user = flat_entry(card, width=30)
        self.e_user.pack(fill="x", ipady=7)

        tk.Label(card, text="PASSWORD", bg=SURFACE,
                 fg=TEXT3, font=F_LABEL, anchor="w").pack(fill="x", pady=(16,4))
        self.e_pass = flat_entry(card, width=30, show="●")
        self.e_pass.pack(fill="x", ipady=7)

        self.error_label = tk.Label(card, text="", bg=SURFACE,
                                    fg=DANGER, font=F_SMALL)
        self.error_label.pack(pady=(8,0))

        btn(card, "Sign In", self._login, bg=ACCENT).pack(
            fill="x", pady=(12,0), ipady=4)

        # Default credentials hint
        tk.Label(self, text="Default admin: admin / admin123",
                 font=("Segoe UI", 8), bg=BG, fg=TEXT3).pack(pady=(16,0))
        tk.Label(self, text="Please change your password after first login",
                 font=("Segoe UI", 8), bg=BG, fg=TEXT3).pack()

        # Bind Enter key
        self.e_user.bind("<Return>", lambda e: self.e_pass.focus())
        self.e_pass.bind("<Return>", lambda e: self._login())
        self.e_user.focus()

    def _login(self):
        username = self.e_user.get().strip().lower()
        password = self.e_pass.get().strip()

        if not username or not password:
            self.error_label.config(text="Please enter username and password.")
            return

        db  = get_auth_db()
        row = db.execute(
            "SELECT * FROM users WHERE username=? AND active=1",
            (username,)).fetchone()
        db.close()

        if not row or row["password"] != hash_password(password):
            self.error_label.config(text="Incorrect username or password.")
            Session.log("Failed login attempt", f"Username: {username}")
            return

        Session.login(row)
        Session.log("Login", f"Role: {row['role']}")
        self.success = True
        self.destroy()

# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN PANEL
# ══════════════════════════════════════════════════════════════════════════════
class AdminPanel(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Admin Panel")
        self.configure(bg=BG)
        self.grab_set()

        W, H = 900, 620
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.minsize(800, 500)

        self._build()

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x")
        tk.Frame(hdr, bg=ACCENT, height=3).pack(fill="x")
        hi = tk.Frame(hdr, bg=SURFACE, padx=24, pady=16)
        hi.pack(fill="x")
        tk.Label(hi, text="⚙  Admin Panel", font=F_DISPLAY,
                 bg=SURFACE, fg=TEXT).pack(side="left")
        tk.Label(hi, text=f"Logged in as {Session.full_name}",
                 font=F_SMALL, bg=SURFACE, fg=TEXT3).pack(side="right")

        # Tabs
        s = ttk.Style()
        s.configure("D.TNotebook", background=BG, borderwidth=0, tabmargins=0)
        s.configure("D.TNotebook.Tab", background=SURFACE, foreground=TEXT2,
                    padding=[18,8], font=F_BODY, borderwidth=0)
        s.map("D.TNotebook.Tab",
              background=[("selected", BG)],
              foreground=[("selected", TEXT)])

        nb = ttk.Notebook(self, style="D.TNotebook")
        nb.pack(fill="both", expand=True)

        t_users    = tk.Frame(nb, bg=BG)
        t_activity = tk.Frame(nb, bg=BG)
        t_settings = tk.Frame(nb, bg=BG)
        nb.add(t_users,    text="   Users   ")
        nb.add(t_activity, text="   Activity Log   ")
        nb.add(t_settings, text="   Settings   ")

        self._tab_users(t_users)
        self._tab_activity(t_activity)
        self._tab_settings(t_settings)

    # ── Users tab ─────────────────────────────────────────────────────────────
    def _tab_users(self, parent):
        # Toolbar
        bar = tk.Frame(parent, bg=BG, pady=14, padx=24)
        bar.pack(fill="x")
        tk.Label(bar, text="MANAGE USERS", bg=BG, fg=TEXT3,
                 font=F_LABEL).pack(side="left")
        btn(bar, "+ Add User", self._add_user, bg=ACCENT).pack(side="right")

        h_rule(parent, BORDER)

        # Table frame
        tbl_frame = tk.Frame(parent, bg=BG)
        tbl_frame.pack(fill="both", expand=True, padx=24, pady=12)

        # Treeview style
        s = ttk.Style()
        s.configure("Dark.Treeview",
                    background=SURFACE, foreground=TEXT,
                    fieldbackground=SURFACE, rowheight=36,
                    font=F_BODY, borderwidth=0)
        s.configure("Dark.Treeview.Heading",
                    background=SURFACE2, foreground=TEXT2,
                    font=F_LABEL, relief="flat")
        s.map("Dark.Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", TEXT)])

        cols = ("full_name","username","role","status","last_login")
        self.tree = ttk.Treeview(tbl_frame, columns=cols,
                                 show="headings", style="Dark.Treeview")
        for col, txt, w in [
            ("full_name",  "Full Name",  180),
            ("username",   "Username",   120),
            ("role",       "Role",        80),
            ("status",     "Status",      80),
            ("last_login", "Last Login",  160),
        ]:
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor="w")

        sb = ttk.Scrollbar(tbl_frame, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        # Action buttons below table
        act = tk.Frame(parent, bg=BG, pady=10, padx=24)
        act.pack(fill="x")
        btn(act, "✎  Edit User",      self._edit_user,
            bg=SURFACE2, fg=TEXT2).pack(side="left", padx=(0,6))
        btn(act, "🔑  Reset Password", self._reset_password,
            bg=SURFACE2, fg=TEXT2).pack(side="left", padx=(0,6))
        btn(act, "⊘  Deactivate",     self._toggle_active,
            bg=SURFACE2, fg=WARNING).pack(side="left", padx=(0,6))
        btn(act, "🗑  Delete",         self._delete_user,
            bg=DANGER, fg=TEXT).pack(side="left")

        self._load_users()

    def _load_users(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        db = get_auth_db()
        users = db.execute(
            "SELECT * FROM users ORDER BY role, full_name").fetchall()
        db.close()
        for u in users:
            status    = "Active" if u["active"] else "Inactive"
            last_login= u["last_login"] or "Never"
            self.tree.insert("", "end", iid=str(u["id"]),
                             values=(u["full_name"], u["username"],
                                     u["role"], status, last_login))

    def _selected_user_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a user first.",
                                   parent=self)
            return None
        return int(sel[0])

    def _add_user(self):
        UserForm(self, on_save=self._save_new_user)

    def _save_new_user(self, data):
        db = get_auth_db()
        try:
            db.execute("""INSERT INTO users
                (username, full_name, password, role, active, created_at)
                VALUES (?,?,?,?,1,?)""",
                (data["username"].lower(), data["full_name"],
                 hash_password(data["password"]),
                 data["role"], now_str()))
            db.commit()
            Session.log("Created user", f"{data['username']} ({data['role']})")
            self._load_users()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error",
                f"Username '{data['username']}' already exists.", parent=self)
        finally:
            db.close()

    def _edit_user(self):
        uid = self._selected_user_id()
        if not uid: return
        db  = get_auth_db()
        row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        db.close()
        UserForm(self, prefill=dict(row), on_save=lambda d: self._save_edit(uid, d))

    def _save_edit(self, uid, data):
        db = get_auth_db()
        db.execute("""UPDATE users SET full_name=?, username=?, role=?
                      WHERE id=?""",
                   (data["full_name"], data["username"].lower(),
                    data["role"], uid))
        db.commit()
        db.close()
        Session.log("Edited user", f"ID {uid}")
        self._load_users()

    def _reset_password(self):
        uid = self._selected_user_id()
        if not uid: return
        db   = get_auth_db()
        user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        db.close()

        ResetPasswordForm(self, user["full_name"],
                          on_save=lambda pw: self._save_password(uid, user["username"], pw))

    def _save_password(self, uid, username, new_password):
        db = get_auth_db()
        db.execute("UPDATE users SET password=? WHERE id=?",
                   (hash_password(new_password), uid))
        db.commit()
        db.close()
        Session.log("Reset password", f"User: {username}")
        messagebox.showinfo("Done", "Password has been reset.", parent=self)

    def _toggle_active(self):
        uid = self._selected_user_id()
        if not uid: return
        if uid == Session.user_id:
            messagebox.showwarning("Cannot deactivate yourself",
                                   "You cannot deactivate your own account.",
                                   parent=self)
            return
        db   = get_auth_db()
        user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        new  = 0 if user["active"] else 1
        db.execute("UPDATE users SET active=? WHERE id=?", (new, uid))
        db.commit()
        db.close()
        status = "Activated" if new else "Deactivated"
        Session.log(f"{status} user", user["username"])
        self._load_users()

    def _delete_user(self):
        uid = self._selected_user_id()
        if not uid: return
        if uid == Session.user_id:
            messagebox.showwarning("Cannot delete yourself",
                                   "You cannot delete your own account.",
                                   parent=self)
            return
        db   = get_auth_db()
        user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not messagebox.askyesno(
                "Delete User",
                f"Permanently delete '{user['full_name']}'?\nThis cannot be undone.",
                parent=self):
            db.close(); return
        db.execute("DELETE FROM users WHERE id=?", (uid,))
        db.commit()
        db.close()
        Session.log("Deleted user", user["username"])
        self._load_users()

    # ── Activity log tab ──────────────────────────────────────────────────────
    def _tab_activity(self, parent):
        bar = tk.Frame(parent, bg=BG, pady=14, padx=24)
        bar.pack(fill="x")
        tk.Label(bar, text="ACTIVITY LOG", bg=BG, fg=TEXT3,
                 font=F_LABEL).pack(side="left")
        btn(bar, "⟳ Refresh", self._load_activity,
            bg=SURFACE2, fg=TEXT2).pack(side="right")

        h_rule(parent, BORDER)

        tbl = tk.Frame(parent, bg=BG)
        tbl.pack(fill="both", expand=True, padx=24, pady=12)

        s = ttk.Style()
        s.configure("Log.Treeview",
                    background=SURFACE, foreground=TEXT,
                    fieldbackground=SURFACE, rowheight=30,
                    font=F_BODY, borderwidth=0)
        s.configure("Log.Treeview.Heading",
                    background=SURFACE2, foreground=TEXT2,
                    font=F_LABEL, relief="flat")
        s.map("Log.Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", TEXT)])

        cols = ("timestamp","username","action","detail")
        self.log_tree = ttk.Treeview(tbl, columns=cols,
                                     show="headings", style="Log.Treeview")
        for col, txt, w in [
            ("timestamp", "Time",     150),
            ("username",  "User",     120),
            ("action",    "Action",   160),
            ("detail",    "Detail",   300),
        ]:
            self.log_tree.heading(col, text=txt)
            self.log_tree.column(col, width=w, anchor="w")

        sb = ttk.Scrollbar(tbl, orient="vertical",
                           command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_tree.pack(fill="both", expand=True)

        self._load_activity()

    def _load_activity(self):
        for row in self.log_tree.get_children():
            self.log_tree.delete(row)
        db   = get_auth_db()
        rows = db.execute(
            "SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT 500"
        ).fetchall()
        db.close()
        for r in rows:
            self.log_tree.insert("", "end",
                values=(r["timestamp"], r["username"] or "—",
                        r["action"], r["detail"] or ""))

    # ── Settings tab ──────────────────────────────────────────────────────────
    def _tab_settings(self, parent):
        frame = tk.Frame(parent, bg=BG, padx=32, pady=24)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="NETWORK DATA PATH", bg=BG, fg=TEXT3,
                 font=F_LABEL, anchor="w").pack(fill="x", pady=(0,4))
        tk.Label(frame,
                 text="Point all PCs to a shared folder so everyone shares the same database.",
                 bg=BG, fg=TEXT2, font=F_SMALL, anchor="w").pack(fill="x", pady=(0,10))

        path_row = tk.Frame(frame, bg=BG)
        path_row.pack(fill="x")

        try:
            with open(CONFIG_FILE) as f:
                current_path = json.load(f).get("data_path", "")
        except Exception:
            current_path = ""

        self.path_var = tk.StringVar(value=current_path or "(using local storage)")
        path_entry = tk.Entry(path_row, textvariable=self.path_var,
                              bg=SURFACE2, fg=TEXT, insertbackground=TEXT,
                              relief="flat", font=F_BODY,
                              highlightthickness=1, highlightcolor=ACCENT,
                              highlightbackground=BORDER, bd=0, width=46)
        path_entry.pack(side="left", ipady=7, padx=(0,8))

        from tkinter import filedialog
        def browse():
            p = filedialog.askdirectory(title="Select Shared Data Folder",
                                        parent=self)
            if p:
                self.path_var.set(p)

        btn(path_row, "Browse", browse, bg=SURFACE2, fg=TEXT2).pack(side="left")

        def save_path():
            p = self.path_var.get().strip()
            if p == "(using local storage)":
                p = ""
            with open(CONFIG_FILE, "w") as f:
                json.dump({"data_path": p}, f)
            Session.log("Updated data path", p or "local")
            messagebox.showinfo("Saved",
                "Data path saved.\nRestart the app for changes to take effect.",
                parent=self)

        btn(frame, "Save Path", save_path, bg=ACCENT).pack(
            anchor="w", pady=(12,0))

        tk.Frame(frame, bg=BORDER, height=1).pack(fill="x", pady=(28,20))

        # Change own password
        tk.Label(frame, text="CHANGE MY PASSWORD", bg=BG, fg=TEXT3,
                 font=F_LABEL, anchor="w").pack(fill="x", pady=(0,10))

        def change_my_pw():
            ResetPasswordForm(self, Session.full_name,
                              on_save=lambda pw: self._save_password(
                                  Session.user_id, Session.username, pw))

        btn(frame, "Change My Password", change_my_pw,
            bg=SURFACE2, fg=TEXT2).pack(anchor="w")

# ══════════════════════════════════════════════════════════════════════════════
#  USER FORM DIALOG
# ══════════════════════════════════════════════════════════════════════════════
class UserForm(tk.Toplevel):
    def __init__(self, master, prefill=None, on_save=None):
        super().__init__(master)
        self.on_save = on_save
        p = prefill or {}
        is_edit = bool(p)
        self.title("Edit User" if is_edit else "Add User")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()

        W, H = 400, is_edit and 420 or 480
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        tk.Frame(self, bg=ACCENT, height=3).pack(fill="x")
        hdr = tk.Frame(self, bg=SURFACE, pady=16)
        hdr.pack(fill="x")
        tk.Label(hdr, text=self.title(), bg=SURFACE, fg=TEXT,
                 font=F_H1, padx=24).pack(anchor="w")

        body = tk.Frame(self, bg=BG, padx=24, pady=16)
        body.pack(fill="both", expand=True)

        def lf(text):
            tk.Label(body, text=text, bg=BG, fg=TEXT3,
                     font=F_LABEL, anchor="w").pack(fill="x", pady=(10,2))

        lf("FULL NAME")
        self.e_name = flat_entry(body, width=36)
        self.e_name.pack(fill="x", ipady=6)
        self.e_name.insert(0, p.get("full_name",""))

        lf("USERNAME")
        self.e_user = flat_entry(body, width=36)
        self.e_user.pack(fill="x", ipady=6)
        self.e_user.insert(0, p.get("username",""))

        if not is_edit:
            lf("PASSWORD")
            self.e_pass = flat_entry(body, width=36, show="●")
            self.e_pass.pack(fill="x", ipady=6)

        lf("ROLE")
        self.role_var = tk.StringVar(value=p.get("role","Staff"))
        role_cb = ttk.Combobox(body, textvariable=self.role_var,
                               values=["Staff","Admin"],
                               width=34, state="readonly", font=F_BODY,
                               style="D.TCombobox")
        role_cb.pack(fill="x", ipady=4)

        foot = tk.Frame(self, bg=SURFACE, pady=14)
        foot.pack(fill="x", side="bottom")
        btn(foot, "Cancel", self.destroy,
            bg=SURFACE2, fg=TEXT2).pack(side="right", padx=(0,24))
        btn(foot, "Save", self._save,
            bg=ACCENT).pack(side="right", padx=(0,8))

        self._is_edit = is_edit

    def _save(self):
        name = self.e_name.get().strip()
        user = self.e_user.get().strip()
        if not name or not user:
            messagebox.showwarning("Required",
                "Full name and username are required.", parent=self)
            return
        data = dict(full_name=name, username=user, role=self.role_var.get())
        if not self._is_edit:
            pw = self.e_pass.get().strip()
            if not pw:
                messagebox.showwarning("Required",
                    "Password is required.", parent=self)
                return
            data["password"] = pw
        if self.on_save:
            self.on_save(data)
        self.destroy()

# ══════════════════════════════════════════════════════════════════════════════
#  RESET PASSWORD DIALOG
# ══════════════════════════════════════════════════════════════════════════════
class ResetPasswordForm(tk.Toplevel):
    def __init__(self, master, user_name, on_save=None):
        super().__init__(master)
        self.on_save = on_save
        self.title("Reset Password")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()

        W, H = 380, 300
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        tk.Frame(self, bg=ACCENT, height=3).pack(fill="x")
        hdr = tk.Frame(self, bg=SURFACE, pady=16)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Reset Password", bg=SURFACE, fg=TEXT,
                 font=F_H1, padx=24).pack(anchor="w")
        tk.Label(hdr, text=f"for {user_name}", bg=SURFACE,
                 fg=TEXT3, font=F_SMALL, padx=24).pack(anchor="w")

        body = tk.Frame(self, bg=BG, padx=24, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="NEW PASSWORD", bg=BG, fg=TEXT3,
                 font=F_LABEL, anchor="w").pack(fill="x", pady=(0,4))
        self.e_pass = flat_entry(body, width=34, show="●")
        self.e_pass.pack(fill="x", ipady=6)

        tk.Label(body, text="CONFIRM PASSWORD", bg=BG, fg=TEXT3,
                 font=F_LABEL, anchor="w").pack(fill="x", pady=(12,4))
        self.e_confirm = flat_entry(body, width=34, show="●")
        self.e_confirm.pack(fill="x", ipady=6)

        self.err = tk.Label(body, text="", bg=BG, fg=DANGER, font=F_SMALL)
        self.err.pack(pady=(6,0))

        foot = tk.Frame(self, bg=SURFACE, pady=14)
        foot.pack(fill="x", side="bottom")
        btn(foot, "Cancel", self.destroy,
            bg=SURFACE2, fg=TEXT2).pack(side="right", padx=(0,24))
        btn(foot, "Reset Password", self._save,
            bg=ACCENT).pack(side="right", padx=(0,8))

    def _save(self):
        pw  = self.e_pass.get().strip()
        pw2 = self.e_confirm.get().strip()
        if not pw:
            self.err.config(text="Password cannot be empty.")
            return
        if pw != pw2:
            self.err.config(text="Passwords do not match.")
            return
        if len(pw) < 4:
            self.err.config(text="Password must be at least 4 characters.")
            return
        if self.on_save:
            self.on_save(pw)
        self.destroy()
