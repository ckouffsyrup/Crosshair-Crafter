import os
import json
import math
import shutil
import ctypes
import base64
import zlib
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, colorchooser, simpledialog, messagebox
from PIL import Image, ImageTk, ImageOps

APP_NAME = "Crosshair Crafter"
VERSION = "1.0.1"
BASE_DIR = Path(__file__).resolve().parent
SETTINGS_DIR = BASE_DIR / "settings"
IMPORTED_DIR = BASE_DIR / "images" / "imported"
CONFIG_FILE = SETTINGS_DIR / "config.json"
PRESETS_FILE = SETTINGS_DIR / "presets.json"
FAVORITES_FILE = SETTINGS_DIR / "favorites.json"
PACKS_DIR = BASE_DIR / "packs"
SAMPLES_DIR = BASE_DIR / "assets" / "samples"
BACKUPS_DIR = BASE_DIR / "settings" / "backups"

SETTINGS_DIR.mkdir(exist_ok=True)
IMPORTED_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
PACKS_DIR.mkdir(parents=True, exist_ok=True)

THEME = {
    "bg": "#080914",
    "panel": "#101320",
    "panel2": "#15192a",
    "card": "#171b2d",
    "card2": "#222943",
    "text": "#f8fafc",
    "muted": "#9aa3b2",
    "accent": "#8b5cf6",
    "accent2": "#c084fc",
    "danger": "#f43f5e",
    "green": "#22c55e",
    "line": "#2c344f",
}

DEFAULTS = {
    "mode": "generated",
    "color": "#8b5cf6",
    "preview_bg": "grid",
    "window_geometry": "1201x835",
    "first_run_seen": False,
    "launch_on_startup": False,
    "generated": {
        "h_length": 34,
        "v_length": 34,
        "h_gap": 10,
        "v_gap": 10,
        "thickness": 4,
        "outline": True,
        "outline_thickness": 2,
        "dot": True,
        "dot_size": 4,
        "rotation": 0,
        "opacity": 100,
    },
    "image": {
        "path": "",
        "size": 80,
        "stretch_x": 100,
        "stretch_y": 100,
        "rotation": 0,
        "flip_x": False,
        "flip_y": False,
        "opacity": 100,
        "offset_x": 0,
        "offset_y": 0,
    }
}


def load_json(path, fallback):
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return json.loads(json.dumps(fallback))


def save_json(path, data):
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def safe_file_name(name):
    safe = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in str(name)).strip()
    return safe or "crosshair"


def deep_merge(base, incoming):
    out = json.loads(json.dumps(base))
    if not isinstance(incoming, dict):
        return out
    for k, v in incoming.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class ModernButton(tk.Button):
    def __init__(self, master, text, command=None, accent=False, danger=False, **kw):
        bg = THEME["accent"] if accent else THEME["danger"] if danger else THEME["card2"]
        super().__init__(master, text=text, command=command, bg=bg, fg=THEME["text"], activebackground=THEME["accent2"],
                         activeforeground=THEME["text"], relief="flat", bd=0, padx=14, pady=10,
                         cursor="hand2", font=("Segoe UI", 10, "bold"), **kw)
        self.normal = bg
        self.hover = THEME["accent2"] if accent else "#2b3146"
        self.bind("<Enter>", lambda e: self.configure(bg=self.hover))
        self.bind("<Leave>", lambda e: self.configure(bg=self.normal))


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{VERSION}")

        # v1.0.1 bug patch: set the Tkinter window/taskbar icon.
        # PyInstaller's --icon changes the EXE file icon, but Tkinter still needs
        # iconbitmap/iconphoto so the running window does not show the default feather.
        self.set_app_icon()

        # v0.7.1 bug patch: config must exist before reading saved window geometry.
        self.config = deep_merge(DEFAULTS, load_json(CONFIG_FILE, DEFAULTS))

        self.root.geometry(self.config.get("window_geometry", "1201x835"))
        self.root.minsize(1050, 720)
        self.root.configure(bg=THEME["bg"])
        self.presets = load_json(PRESETS_FILE, {"presets": {}})
        self.favorites = load_json(FAVORITES_FILE, {"favorites": []})
        self.current_tab = tk.StringVar(value="Crosshair")
        self.overlay = None
        self.preview_img_ref = None
        self.overlay_img_ref = None
        self.toast_label = None
        self.current_pil = None
        self.varmap = {}

        self.build_ui()
        self.load_vars_from_config()
        self.ensure_sample_assets()
        self.ensure_sample_presets()
        self.show_tab("Home")
        self.refresh_all()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)


    def set_app_icon(self):
        ico_path = BASE_DIR / "assets" / "icon.ico"
        png_path = BASE_DIR / "assets" / "icon.png"

        try:
            if ico_path.exists():
                self.root.iconbitmap(str(ico_path))
        except Exception:
            pass

        try:
            if png_path.exists():
                self.app_icon_image = tk.PhotoImage(file=str(png_path))
                self.root.iconphoto(True, self.app_icon_image)
        except Exception:
            pass

    def build_ui(self):
        self.sidebar = tk.Frame(self.root, bg=THEME["panel"], width=235)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        logo = tk.Label(self.sidebar, text="✦", fg=THEME["accent2"], bg=THEME["panel"], font=("Segoe UI", 30, "bold"))
        logo.pack(anchor="w", padx=24, pady=(24, 0))
        tk.Label(self.sidebar, text="Crosshair\nCrafter", fg=THEME["text"], bg=THEME["panel"], justify="left",
                 font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=24, pady=(0, 8))
        tk.Label(self.sidebar, text=f"v{VERSION} • polish", fg=THEME["muted"], bg=THEME["panel"],
                 font=("Segoe UI", 9)).pack(anchor="w", padx=24, pady=(0, 22))

        self.nav_buttons = {}
        icons = {"Home":"⌂  Home", "Crosshair":"✚  Crosshair", "Images":"◇  Images", "Presets":"▤  Presets", "Overlay":"◉  Overlay", "Settings":"⚙  Settings"}
        for tab in ["Home", "Crosshair", "Images", "Presets", "Overlay", "Settings"]:
            b = tk.Button(self.sidebar, text=icons[tab], anchor="w", relief="flat", bd=0, padx=22, pady=14,
                          bg=THEME["panel"], fg=THEME["muted"], activebackground=THEME["card"],
                          activeforeground=THEME["text"], font=("Segoe UI", 11, "bold"),
                          command=lambda t=tab: self.show_tab(t), cursor="hand2")
            b.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[tab] = b

        tk.Frame(self.sidebar, bg=THEME["panel"]).pack(fill="both", expand=True)
        ModernButton(self.sidebar, "✓ Apply Overlay", self.apply_overlay, accent=True).pack(fill="x", padx=18, pady=(0, 8))
        ModernButton(self.sidebar, "× Close Overlay", self.close_overlay).pack(fill="x", padx=18, pady=(0, 22))

        self.main = tk.Frame(self.root, bg=THEME["bg"])
        self.main.pack(side="left", fill="both", expand=True)

        self.topbar = tk.Frame(self.main, bg=THEME["bg"], height=80)
        self.topbar.pack(fill="x")
        self.title_lbl = tk.Label(self.topbar, text="", fg=THEME["text"], bg=THEME["bg"], font=("Segoe UI", 28, "bold"))
        self.title_lbl.pack(side="left", padx=28, pady=(22, 8))
        self.mode_pill = tk.Label(self.topbar, text="", fg=THEME["text"], bg=THEME["accent"], font=("Segoe UI", 10, "bold"), padx=12, pady=5)
        self.mode_pill.pack(side="right", padx=30, pady=(24, 8))

        body = tk.Frame(self.main, bg=THEME["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        self.content = tk.Frame(body, bg=THEME["bg"])
        self.content.pack(side="left", fill="both", expand=True, padx=(0, 18))

        self.preview_panel = tk.Frame(body, bg=THEME["panel"], width=450)
        self.preview_panel.pack(side="right", fill="both")
        self.preview_panel.pack_propagate(False)
        tk.Label(self.preview_panel, text="Live Preview", fg=THEME["text"], bg=THEME["panel"],
                 font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=20, pady=(20, 8))
        self.preview = tk.Canvas(self.preview_panel, width=400, height=400, bg=THEME["card"], highlightthickness=0)
        self.preview.pack(padx=20, pady=(10, 12))
        self.preview.bind("<Configure>", lambda e: self.refresh_preview())
        tk.Label(self.preview_panel, text="Preview backgrounds help visibility. Overlay is click-through on Windows.",
                 fg=THEME["muted"], bg=THEME["panel"], wraplength=370,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(0, 10))
        ModernButton(self.preview_panel, "✚ Generated Mode", lambda: self.set_mode("generated")).pack(fill="x", padx=20, pady=4)
        ModernButton(self.preview_panel, "◇ Image Mode", lambda: self.set_mode("image"), accent=True).pack(fill="x", padx=20, pady=4)

    def clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def ensure_sample_assets(self):
        samples = {
            "tiny_purple_dot.png": ("dot", "#a78bfa"),
            "soft_green_plus.png": ("plus", "#22c55e"),
            "white_ring.png": ("ring", "#f8fafc"),
            "tiny_heart.png": ("heart", "#fb7185"),
            "purple_star.png": ("star", "#c084fc"),
            "diamond.png": ("diamond", "#38bdf8"),
            "hollow_ring.png": ("ring", "#e5e7eb"),
            "mini_cross.png": ("cross", "#f8fafc"),
        }
        for filename, (kind, color) in samples.items():
            path = SAMPLES_DIR / filename
            if path.exists():
                continue
            img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
            from PIL import ImageDraw
            d = ImageDraw.Draw(img)
            cx = cy = 48
            if kind == "dot":
                d.ellipse((39, 39, 57, 57), fill=color)
            elif kind == "plus":
                d.rounded_rectangle((18, 43, 39, 53), radius=4, fill=color)
                d.rounded_rectangle((57, 43, 78, 53), radius=4, fill=color)
                d.rounded_rectangle((43, 18, 53, 39), radius=4, fill=color)
                d.rounded_rectangle((43, 57, 53, 78), radius=4, fill=color)
                d.ellipse((44, 44, 52, 52), fill=color)
            elif kind == "ring":
                d.ellipse((31, 31, 65, 65), outline=color, width=5)
            elif kind == "heart":
                pts = [(48,70),(24,46),(24,31),(36,22),(48,34),(60,22),(72,31),(72,46)]
                d.polygon(pts, fill=color)
                d.ellipse((24,20,48,44), fill=color)
                d.ellipse((48,20,72,44), fill=color)
            elif kind == "star":
                import math
                pts=[]
                for n in range(10):
                    r = 30 if n % 2 == 0 else 13
                    a = math.radians(-90 + n * 36)
                    pts.append((cx + math.cos(a)*r, cy + math.sin(a)*r))
                d.polygon(pts, fill=color)
            elif kind == "diamond":
                d.polygon([(48,16),(80,48),(48,80),(16,48)], fill=color)
                d.polygon([(48,28),(68,48),(48,68),(28,48)], fill=(0,0,0,0))
            elif kind == "cross":
                d.rounded_rectangle((20, 42, 76, 54), radius=3, fill=color)
                d.rounded_rectangle((42, 20, 54, 76), radius=3, fill=color)
            img.save(path)

    def build_generated_preset(self, color, **updates):
        st = json.loads(json.dumps(DEFAULTS))
        st["mode"] = "generated"
        st["color"] = color
        st["generated"].update(updates)
        st["builtin"] = True
        return st

    def build_image_preset(self, filename, **updates):
        st = json.loads(json.dumps(DEFAULTS))
        st["mode"] = "image"
        st["image"]["path"] = str(SAMPLES_DIR / filename)
        st["image"].update(updates)
        st["builtin"] = True
        return st

    def ensure_sample_presets(self):
        presets = self.presets.setdefault("presets", {})
        builtins = {
            "Classic White": self.build_generated_preset("#f8fafc", h_length=34, v_length=34, h_gap=10, v_gap=10, thickness=3, dot=False, outline=True),
            "CS Green": self.build_generated_preset("#22c55e", h_length=42, v_length=42, h_gap=8, v_gap=8, thickness=4, dot=False, outline=True),
            "Purple Minimal": self.build_generated_preset("#a78bfa", h_length=28, v_length=28, h_gap=8, v_gap=8, thickness=3, dot=True, dot_size=3, outline=True),
            "Tiny Dot": self.build_generated_preset("#ffffff", h_length=0, v_length=0, h_gap=0, v_gap=0, thickness=1, dot=True, dot_size=5, outline=True),
            "Hollow Circle": self.build_image_preset("hollow_ring.png", size=46, opacity=100),
            "Dynamic Plus": self.build_generated_preset("#c084fc", h_length=48, v_length=48, h_gap=14, v_gap=14, thickness=4, dot=True, dot_size=5, outline=True),
            "Tiny Heart PNG": self.build_image_preset("tiny_heart.png", size=42, opacity=95),
            "Purple Star PNG": self.build_image_preset("purple_star.png", size=54, opacity=95),
            "Diamond PNG": self.build_image_preset("diamond.png", size=52, opacity=95),
            "Hollow Ring PNG": self.build_image_preset("hollow_ring.png", size=46, opacity=100),
            "Mini Cross PNG": self.build_image_preset("mini_cross.png", size=50, opacity=100),
        }
        changed = False
        for name, state in builtins.items():
            if name not in presets:
                presets[name] = state
                changed = True
            elif isinstance(presets.get(name), dict):
                presets[name]["builtin"] = presets[name].get("builtin", True)
        if changed:
            save_json(PRESETS_FILE, self.presets)
    def tab_home(self):
        c = self.card(self.content, "Welcome Back", "Quick actions for building, testing, and sharing crosshairs.")
        tk.Label(c, text="v1.0.0 is the official release: built-in presets, custom PNG crosshairs, sharing codes, preset packs, favorites, polished UI, and safer settings.",
                 fg=THEME["muted"], bg=THEME["panel"], wraplength=680, justify="left", font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(8, 12))
        row = tk.Frame(c, bg=THEME["panel"]); row.pack(fill="x", padx=18, pady=(0, 18))
        ModernButton(row, "Open Images", lambda: self.show_tab("Images"), accent=True).pack(side="left", padx=(0,8))
        ModernButton(row, "Open Presets", lambda: self.show_tab("Presets")).pack(side="left", padx=(0,8))
        ModernButton(row, "Apply Overlay", self.apply_overlay, accent=True).pack(side="left", padx=(10,8))

        c2 = self.card(self.content, "Recommended Flow", "The quickest way to make something clean.")
        steps = [
            "Start from a built-in preset, import a transparent PNG, or create a generated crosshair.",
            "Adjust size, stretch, opacity, and offsets until it lines up perfectly.",
            "Save it as a preset so you can switch back later.",
            "Copy a sharing code or export a preset pack when you want to share it."
        ]
        for n, step in enumerate(steps, 1):
            tk.Label(c2, text=f"{n}. {step}", fg=THEME["text"] if n == 1 else THEME["muted"], bg=THEME["panel"],
                     anchor="w", justify="left", font=("Segoe UI", 10), wraplength=680).pack(anchor="w", padx=18, pady=4)

        c3 = self.card(self.content, "Current Build", "Simple, lightweight, and no tray or hotkey system.")
        mode = self.config.get("mode", "generated").title()
        tk.Label(c3, text=f"Active mode: {mode}", fg=THEME["text"], bg=THEME["panel"], font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=18, pady=(8,2))
        tk.Label(c3, text=f"Saved presets: {len(self.presets.get('presets', {}))}", fg=THEME["muted"], bg=THEME["panel"], font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(0,18))

    def show_tab(self, tab):
        self.current_tab.set(tab)
        for name, b in self.nav_buttons.items():
            active = name == tab
            b.configure(bg=THEME["card"] if active else THEME["panel"], fg=THEME["text"] if active else THEME["muted"])
        self.title_lbl.configure(text=tab)
        if hasattr(self, "mode_pill"):
            self.mode_pill.configure(text=f"{self.config.get('mode', 'generated').title()} Mode")
        self.clear_content()
        getattr(self, f"tab_{tab.lower()}")()

    def card(self, parent, title, subtitle=None):
        outer = tk.Frame(parent, bg=THEME["line"])
        outer.pack(fill="x", pady=(0, 16))
        accent = tk.Frame(outer, bg=THEME["accent"], height=3)
        accent.pack(fill="x")
        c = tk.Frame(outer, bg=THEME["panel"])
        c.pack(fill="x", padx=1, pady=(0,1))
        tk.Label(c, text=title, fg=THEME["text"], bg=THEME["panel"], font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=20, pady=(18, 2))
        if subtitle:
            tk.Label(c, text=subtitle, fg=THEME["muted"], bg=THEME["panel"], font=("Segoe UI", 10), wraplength=660, justify="left").pack(anchor="w", padx=20, pady=(0, 12))
        return c

    def add_slider(self, parent, label, key, frm, to, resolution=1):
        row = tk.Frame(parent, bg=THEME["panel"])
        row.pack(fill="x", padx=18, pady=7)
        tk.Label(row, text=label, fg=THEME["text"], bg=THEME["panel"], font=("Segoe UI", 10)).pack(side="left")
        val = tk.Label(row, text="", fg=THEME["muted"], bg=THEME["panel"], font=("Segoe UI", 10, "bold"))
        val.pack(side="right")
        var = self.varmap[key]
        val.configure(textvariable=var)
        s = tk.Scale(parent, from_=frm, to=to, orient="horizontal", resolution=resolution, variable=var,
                     showvalue=False, bg=THEME["panel"], fg=THEME["text"], troughcolor=THEME["card2"],
                     activebackground=THEME["accent"], highlightthickness=0, bd=0, command=lambda e: self.refresh_all())
        s.pack(fill="x", padx=18, pady=(0, 6))

    def add_check(self, parent, label, key):
        cb = tk.Checkbutton(parent, text=label, variable=self.varmap[key], command=self.refresh_all,
                            bg=THEME["panel"], fg=THEME["text"], activebackground=THEME["panel"],
                            activeforeground=THEME["text"], selectcolor=THEME["card2"],
                            font=("Segoe UI", 10))
        cb.pack(anchor="w", padx=18, pady=4)

    def load_vars_from_config(self):
        g = self.config["generated"]
        i = self.config["image"]
        self.varmap = {
            "h_length": tk.IntVar(value=g["h_length"]), "v_length": tk.IntVar(value=g["v_length"]),
            "h_gap": tk.IntVar(value=g["h_gap"]), "v_gap": tk.IntVar(value=g["v_gap"]),
            "thickness": tk.IntVar(value=g["thickness"]), "outline": tk.BooleanVar(value=g["outline"]),
            "outline_thickness": tk.IntVar(value=g["outline_thickness"]), "dot": tk.BooleanVar(value=g["dot"]),
            "dot_size": tk.IntVar(value=g["dot_size"]), "g_rotation": tk.IntVar(value=g["rotation"]),
            "g_opacity": tk.IntVar(value=g["opacity"]),
            "size": tk.IntVar(value=i["size"]), "stretch_x": tk.IntVar(value=i["stretch_x"]),
            "stretch_y": tk.IntVar(value=i["stretch_y"]), "i_rotation": tk.IntVar(value=i["rotation"]),
            "flip_x": tk.BooleanVar(value=i["flip_x"]), "flip_y": tk.BooleanVar(value=i["flip_y"]),
            "i_opacity": tk.IntVar(value=i["opacity"]), "offset_x": tk.IntVar(value=i["offset_x"]),
            "offset_y": tk.IntVar(value=i["offset_y"]),
        }

    def sync_config_from_vars(self):
        g = self.config["generated"]
        i = self.config["image"]
        g.update({"h_length": self.varmap["h_length"].get(), "v_length": self.varmap["v_length"].get(),
                  "h_gap": self.varmap["h_gap"].get(), "v_gap": self.varmap["v_gap"].get(),
                  "thickness": self.varmap["thickness"].get(), "outline": self.varmap["outline"].get(),
                  "outline_thickness": self.varmap["outline_thickness"].get(), "dot": self.varmap["dot"].get(),
                  "dot_size": self.varmap["dot_size"].get(), "rotation": self.varmap["g_rotation"].get(),
                  "opacity": self.varmap["g_opacity"].get()})
        i.update({"size": self.varmap["size"].get(), "stretch_x": self.varmap["stretch_x"].get(),
                  "stretch_y": self.varmap["stretch_y"].get(), "rotation": self.varmap["i_rotation"].get(),
                  "flip_x": self.varmap["flip_x"].get(), "flip_y": self.varmap["flip_y"].get(),
                  "opacity": self.varmap["i_opacity"].get(), "offset_x": self.varmap["offset_x"].get(),
                  "offset_y": self.varmap["offset_y"].get()})

    def tab_crosshair(self):
        self.set_mode("generated", refresh=False)
        c1 = self.card(self.content, "Generated Crosshair", "Fine-tune a clean line-based crosshair.")
        grid = tk.Frame(c1, bg=THEME["panel"]); grid.pack(fill="x", padx=6, pady=(0, 14))
        left = tk.Frame(grid, bg=THEME["panel"]); left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(grid, bg=THEME["panel"]); right.pack(side="left", fill="both", expand=True)
        for args in [(left,"Horizontal Length","h_length",0,150),(left,"Vertical Length","v_length",0,150),(left,"Horizontal Gap","h_gap",0,90),(left,"Vertical Gap","v_gap",0,90),(left,"Thickness","thickness",1,25)]: self.add_slider(*args)
        for args in [(right,"Outline Thickness","outline_thickness",0,10),(right,"Center Dot Size","dot_size",0,40),(right,"Rotation","g_rotation",0,360),(right,"Opacity","g_opacity",20,100)]: self.add_slider(*args)
        self.add_check(right, "Show Outline", "outline"); self.add_check(right, "Show Center Dot", "dot")
        row = tk.Frame(c1, bg=THEME["panel"]); row.pack(fill="x", padx=18, pady=(0,18))
        ModernButton(row, "Pick Color", self.pick_color).pack(side="left", padx=(0,8))
        ModernButton(row, "Reset Generated", self.reset_generated).pack(side="left")

    def tab_images(self):
        self.set_mode("image", refresh=False)
        c = self.card(self.content, "Custom PNG / JPG Crosshair", "Import a transparent PNG or JPG and turn it into a crosshair overlay.")
        drop = tk.Frame(c, bg=THEME["card"], height=130)
        drop.pack(fill="x", padx=18, pady=(8, 14)); drop.pack_propagate(False)
        tk.Label(drop, text="Import your crosshair image", fg=THEME["text"], bg=THEME["card"], font=("Segoe UI", 16, "bold")).pack(pady=(24, 2))
        path = self.config["image"].get("path") or "No image imported yet"
        tk.Label(drop, text=path, fg=THEME["muted"], bg=THEME["card"], font=("Segoe UI", 9), wraplength=620).pack()
        ModernButton(drop, "Import PNG / JPG", self.import_image, accent=True).pack(pady=10)

        c2 = self.card(self.content, "Image Transform", "Resize, stretch, rotate, flip, fade, and offset the image.")
        grid = tk.Frame(c2, bg=THEME["panel"]); grid.pack(fill="x", padx=6, pady=(0, 14))
        left = tk.Frame(grid, bg=THEME["panel"]); left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(grid, bg=THEME["panel"]); right.pack(side="left", fill="both", expand=True)
        for args in [(left,"Size","size",5,350),(left,"Stretch Width %","stretch_x",10,300),(left,"Stretch Height %","stretch_y",10,300),(left,"Opacity","i_opacity",10,100)]: self.add_slider(*args)
        for args in [(right,"Rotation","i_rotation",0,360),(right,"X Offset","offset_x",-300,300),(right,"Y Offset","offset_y",-300,300)]: self.add_slider(*args)
        self.add_check(right, "Flip Horizontal", "flip_x"); self.add_check(right, "Flip Vertical", "flip_y")
        row = tk.Frame(c2, bg=THEME["panel"]); row.pack(fill="x", padx=18, pady=(0,18))
        ModernButton(row, "Reset Image Controls", self.reset_image_controls).pack(side="left", padx=(0,8))
        ModernButton(row, "Center Image", self.center_image).pack(side="left", padx=(0,8))
        ModernButton(row, "Use Sample PNG", self.use_sample_image, accent=True).pack(side="left")

    def tab_presets(self):
        c = self.card(self.content, "Preset Library", "Reliable list view is back. Thumbnails are disabled for now until we make them actually worth using.")
        row = tk.Frame(c, bg=THEME["panel"]); row.pack(fill="x", padx=20, pady=(6, 14))
        ModernButton(row, "Save Current Preset", self.save_preset, accent=True).pack(side="left", padx=(0,8))
        ModernButton(row, "Copy Code", self.copy_crosshair_code).pack(side="left", padx=(0,8))
        ModernButton(row, "Import Code", self.import_crosshair_code).pack(side="left", padx=(0,8))
        ModernButton(row, "Import Pack", self.import_preset_pack).pack(side="left", padx=(0,8))
        ModernButton(row, "Export All", self.export_all_presets).pack(side="left", padx=(0,8))
        ModernButton(row, "Refresh", lambda: self.show_tab("Presets")).pack(side="left")

        holder = tk.Frame(c, bg=THEME["panel"])
        holder.pack(fill="both", expand=True, padx=20, pady=(0,20))

        left = tk.Frame(holder, bg=THEME["card"], width=320)
        left.pack(side="left", fill="y", padx=(0,14))
        left.pack_propagate(False)
        tk.Label(left, text="Saved Presets", fg=THEME["text"], bg=THEME["card"], font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=(14,6))
        search_var = tk.StringVar()
        search_entry = tk.Entry(left, textvariable=search_var, bg=THEME["panel2"], fg=THEME["text"], insertbackground=THEME["text"],
                                relief="flat", highlightthickness=1, highlightbackground=THEME["line"], font=("Segoe UI", 10))
        search_entry.pack(fill="x", padx=14, pady=(0,10), ipady=7)
        search_entry.insert(0, "Search presets...")
        search_entry.bind("<FocusIn>", lambda e: search_entry.delete(0, "end") if search_entry.get() == "Search presets..." else None)

        lb_wrap = tk.Frame(left, bg=THEME["card"])
        lb_wrap.pack(fill="both", expand=True, padx=14, pady=(0,14))
        lb = tk.Listbox(lb_wrap, bg=THEME["panel2"], fg=THEME["text"], selectbackground=THEME["accent"],
                        selectforeground=THEME["text"], activestyle="none", relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=THEME["line"], font=("Segoe UI", 11), height=18)
        scrollbar = tk.Scrollbar(lb_wrap, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=scrollbar.set)
        lb.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        favorite_set = set(self.favorites.get("favorites", []))
        all_names = sorted(self.presets.get("presets", {}).keys(), key=lambda n: n.lower())
        display_to_name = {}
        header_rows = set()

        def add_header(text):
            idx = lb.size()
            lb.insert("end", text)
            lb.itemconfig(idx, fg=THEME["accent2"])
            header_rows.add(idx)

        def fill_list(filter_text=""):
            lb.configure(state="normal")
            lb.delete(0, "end")
            display_to_name.clear()
            header_rows.clear()
            needle = filter_text.lower().strip()
            if needle == "search presets...":
                needle = ""
            shown = [name for name in all_names if needle in name.lower()]
            fav_names = [name for name in shown if name in favorite_set]
            other_names = [name for name in shown if name not in favorite_set]
            if fav_names:
                add_header("★ Favorites")
                for name in fav_names:
                    display = "  ★ " + name
                    display_to_name[display] = name
                    lb.insert("end", display)
            if other_names:
                if fav_names:
                    add_header("────────────")
                add_header("All Presets")
                for name in other_names:
                    display = "  ☆ " + name
                    display_to_name[display] = name
                    lb.insert("end", display)
            if not shown:
                lb.insert("end", "No matching presets" if all_names else "No presets yet")
                lb.configure(state="disabled")

        fill_list()
        search_var.trace_add("write", lambda *args: fill_list(search_var.get()))

        detail = tk.Frame(holder, bg=THEME["card"])
        detail.pack(side="left", fill="both", expand=True)
        detail_title = tk.Label(detail, text="Select a preset", fg=THEME["text"], bg=THEME["card"], font=("Segoe UI", 18, "bold"))
        detail_title.pack(anchor="w", padx=18, pady=(18,4))
        detail_meta = tk.Label(detail, text="Load, duplicate, export, or delete saved presets from here.", fg=THEME["muted"], bg=THEME["card"], font=("Segoe UI", 10), wraplength=420, justify="left")
        detail_meta.pack(anchor="w", padx=18, pady=(0,18))

        preview_box = tk.Canvas(detail, width=180, height=180, bg=THEME["panel2"], highlightthickness=1, highlightbackground=THEME["line"])
        preview_box.pack(anchor="w", padx=18, pady=(0,18))

        def selected_name():
            sel = lb.curselection()
            if not sel:
                return None
            if sel[0] in header_rows:
                return None
            display = lb.get(sel[0])
            if display in ("No presets yet", "No matching presets", "★ Favorites", "All Presets", "────────────"):
                return None
            return display_to_name.get(display, display.lstrip("★☆ ").strip())

        def refresh_detail(event=None):
            name = selected_name()
            preview_box.delete("all")
            if not name:
                detail_title.configure(text="Select a preset")
                detail_meta.configure(text="Load, duplicate, export, or delete saved presets from here.")
                preview_box.create_text(90, 90, text="No preset", fill=THEME["muted"], font=("Segoe UI", 12, "bold"))
                return
            state = self.presets.get("presets", {}).get(name, {})
            mode = state.get("mode", "generated").title()
            detail_title.configure(text=name)
            extra = ""
            if state.get("mode") == "image":
                extra = "\nImage: " + (Path(state.get("image", {}).get("path", "")).name or "missing")
            detail_meta.configure(text=f"{mode} preset{extra}")
            self.draw_list_preview(preview_box, state, 180, 180)

        lb.bind("<<ListboxSelect>>", refresh_detail)
        lb.bind("<Double-Button-1>", lambda e: self.load_selected_preset(lb))
        refresh_detail()

        btns = tk.Frame(detail, bg=THEME["card"])
        btns.pack(anchor="w", padx=18, pady=(0,18))
        ModernButton(btns, "Load", lambda: self.load_selected_preset(lb), accent=True).pack(side="left", padx=(0,8))
        ModernButton(btns, "Favorite", lambda: self.toggle_selected_favorite(lb)).pack(side="left", padx=(0,8))
        ModernButton(btns, "Duplicate", lambda: self.duplicate_selected_preset(lb)).pack(side="left", padx=(0,8))
        ModernButton(btns, "Export", lambda: self.export_selected_preset(lb)).pack(side="left", padx=(0,8))
        ModernButton(btns, "Delete", lambda: self.delete_selected_preset(lb), danger=True).pack(side="left")



    def tab_overlay(self):
        c = self.card(self.content, "Overlay Controls", "Apply or close the click-through crosshair overlay. No tray and no hotkeys in this build.")
        status = "Overlay is currently active." if self.overlay else "Overlay is currently closed."
        tk.Label(c, text=status, fg=THEME["text"], bg=THEME["panel"], font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=18, pady=(8, 4))
        tk.Label(c, text="Best results usually come from borderless/windowed games. Some anti-cheat games may block or hide overlays.",
                 fg=THEME["muted"], bg=THEME["panel"], wraplength=680, justify="left", font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(0, 14))
        row = tk.Frame(c, bg=THEME["panel"]); row.pack(fill="x", padx=18, pady=(0, 18))
        ModernButton(row, "Apply / Refresh Overlay", self.apply_overlay, accent=True).pack(side="left", padx=(0,8))
        ModernButton(row, "Close Overlay", self.close_overlay).pack(side="left", padx=(0,8))
        ModernButton(row, "Use Generated Mode", lambda: self.set_mode_and_show("generated", "Crosshair")).pack(side="left", padx=(8,8))
        ModernButton(row, "Use Image Mode", lambda: self.set_mode_and_show("image", "Images"), accent=True).pack(side="left")

        c2 = self.card(self.content, "Preview Background", "Change the editor preview background so different crosshair colors are easier to see.")
        row2 = tk.Frame(c2, bg=THEME["panel"]); row2.pack(fill="x", padx=18, pady=(6, 18))
        for name, key in [("Dark Grid", "grid"), ("FPS Range", "range"), ("White", "white"), ("Gradient", "gradient"), ("Dark Solid", "dark")]:
            ModernButton(row2, name, lambda k=key: self.set_preview_bg(k), accent=(self.config.get("preview_bg") == key)).pack(side="left", padx=(0,8), pady=4)

    def tab_settings(self):
        c = self.card(self.content, "Settings", "Basic app options and reset tools.")
        startup = "Enabled" if self.config.get("launch_on_startup") else "Disabled"
        tk.Label(c, text=f"Launch on startup: {startup}", fg=THEME["text"], bg=THEME["panel"], font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=18, pady=(8, 4))
        tk.Label(c, text="Startup creates or removes a small batch file in your Windows Startup folder.",
                 fg=THEME["muted"], bg=THEME["panel"], wraplength=680, justify="left", font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(0, 14))
        row = tk.Frame(c, bg=THEME["panel"]); row.pack(fill="x", padx=18, pady=(0, 18))
        ModernButton(row, "Enable Startup", self.enable_startup, accent=True).pack(side="left", padx=(0,8))
        ModernButton(row, "Disable Startup", self.disable_startup).pack(side="left", padx=(0,8))
        ModernButton(row, "Back Up Presets", self.backup_presets).pack(side="left", padx=(0,8))
        ModernButton(row, "Open App Folder", self.open_app_folder).pack(side="left", padx=(0,8))
        ModernButton(row, "Factory Reset", self.factory_reset, danger=True).pack(side="left", padx=(12,0))

        c2 = self.card(self.content, "About This Build", "Current project info and release notes.")
        lines = [
            f"{APP_NAME} v{VERSION}",
            "A lightweight custom crosshair utility built for gamers who just want something that works.",
            "Final polish: built-in presets, sharing codes, favorites, preset packs, safer config handling, and a cleaner UI.",
            "No tray. No hotkeys. Clean editor + click-through overlay only.",
            "Created by Carl. Built with ChatGPT.",
            "Thanks for using Crosshair Crafter ❤️"
        ]
        for line in lines:
            tk.Label(c2, text=line, fg=THEME["muted"], bg=THEME["panel"], anchor="w", justify="left", font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=3)
        tk.Frame(c2, bg=THEME["panel"], height=10).pack()

    def set_mode_and_show(self, mode, tab):
        self.set_mode(mode)
        self.show_tab(tab)

    def draw_list_preview(self, canvas, state, w=180, h=180):
        canvas.delete("all")
        canvas.create_rectangle(0, 0, w, h, fill=THEME["panel2"], outline="")
        for x in range(0, w, 30): canvas.create_line(x, 0, x, h, fill=THEME["line"])
        for y in range(0, h, 30): canvas.create_line(0, y, w, y, fill=THEME["line"])
        cx = w / 2; cy = h / 2
        mode = state.get("mode", "generated")
        if mode == "image":
            path = state.get("image", {}).get("path", "")
            try:
                if path and Path(path).exists():
                    img = Image.open(path).convert("RGBA")
                    img.thumbnail((115, 115), Image.Resampling.LANCZOS)
                    tkimg = ImageTk.PhotoImage(img)
                    canvas.image_ref = tkimg
                    canvas.create_image(cx, cy, image=tkimg)
                    return
            except Exception:
                pass
            canvas.create_text(cx, cy, text="Image missing", fill=THEME["muted"], font=("Segoe UI", 12, "bold"))
            return
        g = deep_merge(DEFAULTS, state).get("generated", DEFAULTS["generated"])
        color = state.get("color", DEFAULTS["color"])
        scale = 0.9
        h_len = g.get("h_length", 34) * scale
        v_len = g.get("v_length", 34) * scale
        h_gap = g.get("h_gap", 10) * scale
        v_gap = g.get("v_gap", 10) * scale
        thick = max(1, int(g.get("thickness", 4)))
        canvas.create_line(cx-h_gap-h_len, cy, cx-h_gap, cy, fill=color, width=thick, capstyle=tk.ROUND)
        canvas.create_line(cx+h_gap, cy, cx+h_gap+h_len, cy, fill=color, width=thick, capstyle=tk.ROUND)
        canvas.create_line(cx, cy-v_gap-v_len, cx, cy-v_gap, fill=color, width=thick, capstyle=tk.ROUND)
        canvas.create_line(cx, cy+v_gap, cx, cy+v_gap+v_len, fill=color, width=thick, capstyle=tk.ROUND)
        if g.get("dot", True):
            r = max(1, g.get("dot_size", 4) / 2)
            canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=color, outline="")


    def clean_preset_display_name(self, value):
        name = str(value).lstrip("★☆ ").strip()
        if name in ("Favorites", "All Presets", "────────────", "No presets yet", "No matching presets"):
            return ""
        return name

    def show_toast(self, message, good=True):
        try:
            if self.toast_label and self.toast_label.winfo_exists():
                self.toast_label.destroy()
            bg = THEME["green"] if good else THEME["danger"]
            self.toast_label = tk.Label(self.topbar, text=("✓ " if good else "⚠ ") + message,
                                        fg=THEME["text"], bg=bg, font=("Segoe UI", 10, "bold"), padx=14, pady=7)
            self.toast_label.pack(side="right", padx=(0, 12), pady=(24, 8))
            self.root.after(2600, lambda: self.toast_label.destroy() if self.toast_label and self.toast_label.winfo_exists() else None)
        except Exception:
            pass

    def encode_crosshair_state(self, state):
        raw = json.dumps(state, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        packed = zlib.compress(raw, 9)
        encoded = base64.urlsafe_b64encode(packed).decode("ascii").rstrip("=")
        chunks = [encoded[i:i+4] for i in range(0, len(encoded), 4)]
        return "CCR-" + "-".join(chunks)

    def decode_crosshair_code(self, code):
        text = str(code).strip().replace(" ", "")
        if text.upper().startswith("CCR-"):
            text = text[4:]
        text = text.replace("-", "")
        padding = "=" * (-len(text) % 4)
        packed = base64.urlsafe_b64decode((text + padding).encode("ascii"))
        raw = zlib.decompress(packed).decode("utf-8")
        return json.loads(raw)

    def copy_crosshair_code(self):
        try:
            state = self.current_state()
            state["cc_meta"] = {"version": VERSION, "kind": "crosshair_code"}
            code = self.encode_crosshair_state(state)
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.show_toast("Crosshair code copied")
        except Exception as e:
            self.show_toast("Could not copy code", good=False)
            messagebox.showerror(APP_NAME, f"Could not create code:\n{e}")

    def import_crosshair_code(self):
        code = simpledialog.askstring(APP_NAME, "Paste Crosshair Crafter code:")
        if not code:
            return
        try:
            state = self.decode_crosshair_code(code)
            state.pop("cc_meta", None)
            self.config = deep_merge(DEFAULTS, state)
            self.load_vars_from_config()
            self.refresh_all()
            self.show_toast("Crosshair code imported")
            self.show_tab("Presets")
        except Exception as e:
            self.show_toast("Invalid crosshair code", good=False)
            messagebox.showerror(APP_NAME, f"Invalid crosshair code.\n\n{e}")

    def toggle_selected_favorite(self, lb):
        sel = lb.curselection()
        if not sel:
            return
        name = self.clean_preset_display_name(lb.get(sel[0]))
        if name not in self.presets.get("presets", {}):
            return
        favs = set(self.favorites.get("favorites", []))
        if name in favs:
            favs.remove(name)
            msg = "Removed favorite"
        else:
            favs.add(name)
            msg = "Favorited preset"
        self.favorites["favorites"] = sorted(favs, key=str.lower)
        save_json(FAVORITES_FILE, self.favorites)
        self.show_toast(msg)
        self.show_tab("Presets")

    def duplicate_selected_preset(self, lb):
        sel = lb.curselection()
        if not sel: return
        self.duplicate_preset_by_name(self.clean_preset_display_name(lb.get(sel[0])))

    def export_selected_preset(self, lb):
        sel = lb.curselection()
        if not sel: return
        self.export_single_preset(self.clean_preset_display_name(lb.get(sel[0])))

    def make_preset_card(self, parent, name, state):
        card = tk.Frame(parent, bg=THEME["card"], height=118)
        card.pack(fill="x", pady=(0,10))
        card.pack_propagate(False)

        thumb = tk.Canvas(card, width=92, height=92, bg=THEME["card2"], highlightthickness=0)
        thumb.pack(side="left", padx=14, pady=13)
        self.draw_preset_thumbnail(thumb, state)

        info = tk.Frame(card, bg=THEME["card"])
        info.pack(side="left", fill="both", expand=True, pady=14)
        mode = state.get("mode", "generated").title()
        tk.Label(info, text=name, fg=THEME["text"], bg=THEME["card"], font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(info, text=f"{mode} preset", fg=THEME["muted"], bg=THEME["card"], font=("Segoe UI", 9)).pack(anchor="w", pady=(2,0))
        if state.get("mode") == "image":
            img_name = Path(state.get("image", {}).get("path", "")).name or "No image"
            tk.Label(info, text=img_name, fg=THEME["muted"], bg=THEME["card"], font=("Segoe UI", 9), wraplength=330).pack(anchor="w", pady=(2,0))

        buttons = tk.Frame(card, bg=THEME["card"])
        buttons.pack(side="right", padx=14, pady=18)
        ModernButton(buttons, "Load", lambda n=name: self.load_preset_by_name(n), accent=True).pack(side="left", padx=(0,6))
        ModernButton(buttons, "Duplicate", lambda n=name: self.duplicate_preset_by_name(n)).pack(side="left", padx=(0,6))
        ModernButton(buttons, "Export", lambda n=name: self.export_single_preset(n)).pack(side="left", padx=(0,6))
        ModernButton(buttons, "Delete", lambda n=name: self.delete_preset_by_name(n), danger=True).pack(side="left")

    def draw_preset_thumbnail(self, canvas, state):
        canvas.delete("all")
        canvas.create_rectangle(0, 0, 92, 92, fill=THEME["card2"], outline="")
        for x in range(0, 92, 23): canvas.create_line(x, 0, x, 92, fill="#30364a")
        for y in range(0, 92, 23): canvas.create_line(0, y, 92, y, fill="#30364a")
        cx = cy = 46
        mode = state.get("mode", "generated")
        if mode == "image":
            path = state.get("image", {}).get("path", "")
            try:
                if path and Path(path).exists():
                    img = Image.open(path).convert("RGBA")
                    img.thumbnail((54, 54), Image.Resampling.LANCZOS)
                    tkimg = ImageTk.PhotoImage(img)
                    self.preset_thumb_refs.append(tkimg)
                    canvas.create_image(cx, cy, image=tkimg)
                    return
            except Exception:
                pass
            canvas.create_text(cx, cy, text="IMG", fill=THEME["muted"], font=("Segoe UI", 11, "bold"))
            return

        g = deep_merge(DEFAULTS, state).get("generated", DEFAULTS["generated"])
        color = state.get("color", DEFAULTS["color"])
        scale = 0.45
        h_len = g.get("h_length", 34) * scale
        v_len = g.get("v_length", 34) * scale
        h_gap = g.get("h_gap", 10) * scale
        v_gap = g.get("v_gap", 10) * scale
        thick = max(1, int(g.get("thickness", 4) * 0.7))
        canvas.create_line(cx-h_gap-h_len, cy, cx-h_gap, cy, fill=color, width=thick, capstyle=tk.ROUND)
        canvas.create_line(cx+h_gap, cy, cx+h_gap+h_len, cy, fill=color, width=thick, capstyle=tk.ROUND)
        canvas.create_line(cx, cy-v_gap-v_len, cx, cy-v_gap, fill=color, width=thick, capstyle=tk.ROUND)
        canvas.create_line(cx, cy+v_gap, cx, cy+v_gap+v_len, fill=color, width=thick, capstyle=tk.ROUND)
        if g.get("dot", True):
            r = max(1, g.get("dot_size", 4) * 0.35)
            canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=color, outline="")

    def load_preset_by_name(self, name):
        if name not in self.presets.get("presets", {}): return
        self.config = deep_merge(DEFAULTS, self.presets["presets"][name])
        self.load_vars_from_config(); self.refresh_all(); self.show_toast("Preset loaded"); self.show_tab("Presets")

    def delete_preset_by_name(self, name):
        if self.presets.get("presets", {}).get(name, {}).get("builtin"):
            self.show_toast("Built-in presets are protected", good=False)
            return
        if messagebox.askyesno(APP_NAME, f"Delete preset '{name}'?"):
            self.backup_presets(silent=True)
            self.presets.get("presets", {}).pop(name, None)
            favs=set(self.favorites.get("favorites", [])); favs.discard(name); self.favorites["favorites"]=sorted(favs, key=str.lower); save_json(FAVORITES_FILE, self.favorites)
            save_json(PRESETS_FILE, self.presets)
            self.show_toast("Preset deleted")
            self.show_tab("Presets")

    def export_single_preset(self, name):
        if name not in self.presets.get("presets", {}): return
        path = filedialog.asksaveasfilename(title="Export Preset", defaultextension=".ccpreset", initialfile=f"{name}.ccpreset", filetypes=[("Crosshair Crafter Preset", "*.ccpreset"), ("JSON", "*.json")])
        if not path: return
        pack = {"app": APP_NAME, "version": VERSION, "kind": "ccpreset", "presets": {name: self.presets["presets"][name]}, "favorites": [name] if name in self.favorites.get("favorites", []) else []}
        save_json(Path(path), pack)
        self.show_toast("Preset exported")
        messagebox.showinfo(APP_NAME, "Preset exported successfully.")

    def export_all_presets(self):
        if not self.presets.get("presets"):
            messagebox.showinfo(APP_NAME, "No presets to export yet.")
            return
        path = filedialog.asksaveasfilename(title="Export Preset Pack", defaultextension=".ccpack", initialfile="CrosshairCrafter_Presets.ccpack", filetypes=[("Crosshair Crafter Pack", "*.ccpack"), ("JSON", "*.json")])
        if not path: return
        pack = {"app": APP_NAME, "version": VERSION, "kind": "ccpack", "presets": self.presets.get("presets", {}), "favorites": self.favorites.get("favorites", [])}
        save_json(Path(path), pack)
        self.show_toast("Preset pack exported")
        messagebox.showinfo(APP_NAME, "Preset pack exported successfully.")

    def import_preset_pack(self):
        path = filedialog.askopenfilename(title="Import Preset Pack", filetypes=[("Crosshair Crafter Presets", "*.ccpack *.ccpreset *.json"), ("All Files", "*.*")])
        if not path: return
        try:
            data = load_json(Path(path), {})
            incoming = data.get("presets", {})
            if not incoming:
                messagebox.showerror(APP_NAME, "That file did not contain any presets.")
                return
            self.backup_presets(silent=True)
            target = self.presets.setdefault("presets", {})
            added = 0
            for name, preset in incoming.items():
                final = name
                suffix = 2
                while final in target:
                    final = f"{name} ({suffix})"
                    suffix += 1
                target[final] = preset
                added += 1
            incoming_favorites = data.get("favorites", [])
            favs = set(self.favorites.get("favorites", []))
            for fav in incoming_favorites:
                if fav in target:
                    favs.add(fav)
            self.favorites["favorites"] = sorted(favs, key=str.lower)
            save_json(PRESETS_FILE, self.presets)
            save_json(FAVORITES_FILE, self.favorites)
            self.show_toast(f"Imported {added} preset(s)")
            messagebox.showinfo(APP_NAME, f"Imported {added} preset(s).")
            self.show_tab("Presets")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not import preset pack:\n{e}")

    def backup_presets(self, silent=False):
        try:
            BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
            stamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUPS_DIR / f"presets_backup_{stamp}.json"
            save_json(backup_path, self.presets)
            if not silent:
                messagebox.showinfo(APP_NAME, f"Preset backup created:\n{backup_path}")
            return backup_path
        except Exception as e:
            if not silent:
                messagebox.showerror(APP_NAME, f"Could not back up presets:\n{e}")
            return None

    def open_app_folder(self):
        try:
            if os.name == "nt":
                os.startfile(BASE_DIR)
            else:
                messagebox.showinfo(APP_NAME, f"App folder:\n{BASE_DIR}")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not open app folder:\n{e}")

    def startup_file(self):
        startup = Path(os.environ.get("APPDATA", BASE_DIR)) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        return startup / "CrosshairCrafter.bat"

    def enable_startup(self):
        try:
            target = self.startup_file()
            target.parent.mkdir(parents=True, exist_ok=True)
            py = Path(__file__).resolve()
            target.write_text(f'@echo off\ncd /d "{BASE_DIR}"\nstart "" pythonw "{py}"\n', encoding="utf-8")
            self.config["launch_on_startup"] = True
            save_json(CONFIG_FILE, self.config)
            self.show_tab("Settings")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not enable startup:\n{e}")

    def disable_startup(self):
        try:
            target = self.startup_file()
            if target.exists(): target.unlink()
            self.config["launch_on_startup"] = False
            save_json(CONFIG_FILE, self.config)
            self.show_tab("Settings")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not disable startup:\n{e}")

    def set_mode(self, mode, refresh=True):
        self.config["mode"] = mode
        if refresh: self.refresh_all()

    def set_preview_bg(self, bg):
        self.config["preview_bg"] = bg
        self.refresh_all()

    def pick_color(self):
        color = colorchooser.askcolor(color=self.config["color"])[1]
        if color:
            self.config["color"] = color
            self.refresh_all()

    def import_image(self):
        path = filedialog.askopenfilename(title="Import Crosshair Image", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All Files", "*.*")])
        if not path: return
        src = Path(path)
        safe = safe_file_name(src.name)
        dest = IMPORTED_DIR / safe
        suffix = 2
        while dest.exists():
            dest = IMPORTED_DIR / f"{src.stem}_{suffix}{src.suffix}"
            suffix += 1
        try:
            Image.open(src).verify()
            shutil.copy2(src, dest)
            self.config["image"]["path"] = str(dest)
            self.config["mode"] = "image"
            self.refresh_all()
            self.show_tab("Images")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not import image:\n{e}")

    def reset_generated(self):
        self.config["generated"] = json.loads(json.dumps(DEFAULTS["generated"]))
        self.load_vars_from_config(); self.show_tab("Crosshair"); self.refresh_all()

    def center_image(self):
        self.config["image"]["offset_x"] = 0
        self.config["image"]["offset_y"] = 0
        self.load_vars_from_config()
        self.show_tab("Images")
        self.refresh_all()

    def use_sample_image(self):
        samples = sorted(SAMPLES_DIR.glob("*.png"))
        if not samples:
            messagebox.showerror(APP_NAME, "No sample PNGs were found.")
            return
        sample_names = "\n".join(f"{idx+1}. {p.name}" for idx, p in enumerate(samples))
        choice = simpledialog.askinteger(APP_NAME, "Choose a sample PNG:\n\n" + sample_names, minvalue=1, maxvalue=len(samples))
        if not choice:
            return
        self.config["image"]["path"] = str(samples[choice-1])
        self.config["mode"] = "image"
        self.refresh_all()
        self.show_tab("Images")

    def duplicate_preset_by_name(self, name):
        self.backup_presets(silent=True)
        src = self.presets.get("presets", {}).get(name)
        if not src:
            return
        target = self.presets.setdefault("presets", {})
        final = f"{name} Copy"
        suffix = 2
        while final in target:
            final = f"{name} Copy {suffix}"
            suffix += 1
        target[final] = json.loads(json.dumps(src))
        save_json(PRESETS_FILE, self.presets)
        self.show_tab("Presets")

    def reset_image_controls(self):
        old_path = self.config["image"].get("path", "")
        self.config["image"] = json.loads(json.dumps(DEFAULTS["image"]))
        self.config["image"]["path"] = old_path
        self.load_vars_from_config(); self.show_tab("Images"); self.refresh_all()

    def factory_reset(self):
        if messagebox.askyesno(APP_NAME, "Reset everything to defaults?"):
            self.config = json.loads(json.dumps(DEFAULTS))
            self.load_vars_from_config(); self.show_tab("Settings"); self.refresh_all()

    def current_state(self):
        self.sync_config_from_vars()
        return json.loads(json.dumps(self.config))

    def save_preset(self):
        name = simpledialog.askstring(APP_NAME, "Preset name:")
        if not name: return
        name = name.strip()
        if not name: return
        self.backup_presets(silent=True)
        target = self.presets.setdefault("presets", {})
        final = name
        suffix = 2
        while final in target and target.get(final, {}).get("builtin"):
            final = f"{name} {suffix}"
            suffix += 1
        if final in target and not messagebox.askyesno(APP_NAME, f"Overwrite preset '{final}'?"):
            return
        state = self.current_state()
        state.pop("builtin", None)
        target[final] = state
        save_json(PRESETS_FILE, self.presets)
        self.show_toast("Preset saved")
        self.show_tab("Presets")

    def load_selected_preset(self, lb):
        sel = lb.curselection()
        if not sel: return
        name = self.clean_preset_display_name(lb.get(sel[0]))
        if not name or name not in self.presets.get("presets", {}):
            return
        self.config = deep_merge(DEFAULTS, self.presets["presets"][name])
        self.load_vars_from_config(); self.refresh_all(); self.show_toast("Preset loaded"); self.show_tab("Presets")

    def delete_selected_preset(self, lb):
        sel = lb.curselection()
        if not sel: return
        name = self.clean_preset_display_name(lb.get(sel[0]))
        if not name or name not in self.presets.get("presets", {}):
            return
        if self.presets.get("presets", {}).get(name, {}).get("builtin"):
            self.show_toast("Built-in presets are protected", good=False)
            return
        if messagebox.askyesno(APP_NAME, f"Delete preset '{name}'?"):
            self.backup_presets(silent=True)
            self.presets["presets"].pop(name, None)
            save_json(PRESETS_FILE, self.presets)
            favs=set(self.favorites.get("favorites", [])); favs.discard(name); self.favorites["favorites"]=sorted(favs, key=str.lower); save_json(FAVORITES_FILE, self.favorites)
            self.show_toast("Preset deleted")
            self.show_tab("Presets")

    def draw_background(self, canvas):
        canvas.delete("bg")
        w = canvas.winfo_width() or 380; h = canvas.winfo_height() or 380
        bg = self.config.get("preview_bg", "grid")
        if bg == "white": canvas.create_rectangle(0,0,w,h,fill="#eeeeee",outline="",tags="bg")
        elif bg == "range":
            canvas.create_rectangle(0,0,w,h,fill="#1e293b",outline="",tags="bg")
            for x in range(20, int(w), 50): canvas.create_line(x,0,x,h,fill="#334155",tags="bg")
            for y in range(20, int(h), 50): canvas.create_line(0,y,w,y,fill="#334155",tags="bg")
            for i in range(5):
                canvas.create_oval(w/2-90+i*45, h/2-80, w/2-60+i*45, h/2-50, fill="#64748b", outline="", tags="bg")
        elif bg == "gradient":
            for y in range(int(h)):
                r = int(13 + y/h*25); g = int(15 + y/h*18); b = int(22 + y/h*48)
                canvas.create_line(0,y,w,y,fill=f"#{r:02x}{g:02x}{b:02x}",tags="bg")
        else:
            canvas.create_rectangle(0,0,w,h,fill=THEME["card"],outline="",tags="bg")
            if bg == "grid":
                for x in range(0, int(w), 25): canvas.create_line(x,0,x,h,fill="#252a3b",tags="bg")
                for y in range(0, int(h), 25): canvas.create_line(0,y,w,y,fill="#252a3b",tags="bg")

    def refresh_all(self):
        self.sync_config_from_vars()
        save_json(CONFIG_FILE, self.config)
        self.refresh_preview()
        if self.overlay: self.overlay_refresh()

    def refresh_preview(self):
        c = self.preview
        c.delete("all")
        self.draw_background(c)
        if self.config.get("mode") == "image": self.draw_image(c, preview=True)
        else: self.draw_generated(c)
        w = c.winfo_width() or 380; h = c.winfo_height() or 380
        c.create_line(w/2-8,h/2,w/2+8,h/2,fill="#ffffff",stipple="gray50")
        c.create_line(w/2,h/2-8,w/2,h/2+8,fill="#ffffff",stipple="gray50")

    def draw_generated(self, c):
        w = c.winfo_width() or 380; h = c.winfo_height() or 380; cx=w/2; cy=h/2
        g = self.config["generated"]; color=self.config["color"]
        rot=math.radians(g["rotation"])
        def rp(x,y):
            dx=x-cx; dy=y-cy
            return cx+dx*math.cos(rot)-dy*math.sin(rot), cy+dx*math.sin(rot)+dy*math.cos(rot)
        def line(x1,y1,x2,y2,fill,width):
            c.create_line(*rp(x1,y1),*rp(x2,y2),fill=fill,width=width,capstyle=tk.ROUND)
        lines=[(cx-g["h_gap"]-g["h_length"],cy,cx-g["h_gap"],cy),(cx+g["h_gap"],cy,cx+g["h_gap"]+g["h_length"],cy),(cx,cy-g["v_gap"]-g["v_length"],cx,cy-g["v_gap"]),(cx,cy+g["v_gap"],cx,cy+g["v_gap"]+g["v_length"])]
        if g["outline"]:
            for ln in lines: line(*ln,"#000000",g["thickness"]+g["outline_thickness"]*2)
        for ln in lines: line(*ln,color,g["thickness"])
        if g["dot"] and g["dot_size"]>0:
            r=g["dot_size"]/2
            if g["outline"]: c.create_oval(cx-r-g["outline_thickness"],cy-r-g["outline_thickness"],cx+r+g["outline_thickness"],cy+r+g["outline_thickness"],fill="#000000",outline="")
            c.create_oval(cx-r,cy-r,cx+r,cy+r,fill=color,outline="")

    def get_transformed_image(self):
        i = self.config["image"]; path=i.get("path")
        if not path or not Path(path).exists(): return None
        try:
            img = Image.open(path).convert("RGBA")
            if i["flip_x"]: img = ImageOps.mirror(img)
            if i["flip_y"]: img = ImageOps.flip(img)
            base = max(1, i["size"])
            ratio = img.height / img.width if img.width else 1
            nw = max(1, int(base * i["stretch_x"] / 100))
            nh = max(1, int(base * ratio * i["stretch_y"] / 100))
            img = img.resize((nw, nh), Image.Resampling.LANCZOS)
            if i["rotation"]: img = img.rotate(-i["rotation"], expand=True, resample=Image.Resampling.BICUBIC)
            if i["opacity"] < 100:
                alpha = img.getchannel("A").point(lambda p: int(p * i["opacity"] / 100))
                img.putalpha(alpha)
            return img
        except Exception:
            return None

    def draw_image(self, c, preview=True):
        img = self.get_transformed_image()
        w = c.winfo_width() or 380; h = c.winfo_height() or 380
        if img is None:
            c.create_text(w/2,h/2,text="No image imported",fill=THEME["muted"],font=("Segoe UI",14,"bold"))
            return
        tkimg = ImageTk.PhotoImage(img)
        if preview: self.preview_img_ref = tkimg
        else: self.overlay_img_ref = tkimg
        i = self.config["image"]
        c.create_image(w/2 + i["offset_x"], h/2 + i["offset_y"], image=tkimg)

    def apply_overlay(self):
        if self.overlay is None:
            self.overlay = tk.Toplevel(self.root)
            self.overlay.overrideredirect(True)
            self.overlay.attributes("-topmost", True)
            sw = self.overlay.winfo_screenwidth(); sh = self.overlay.winfo_screenheight()
            self.overlay.geometry(f"{sw}x{sh}+0+0")
            self.overlay.configure(bg="black")
            self.overlay.attributes("-transparentcolor", "black")
            self.overlay_canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
            self.overlay_canvas.pack(fill="both", expand=True)
            self.overlay_canvas.bind("<Configure>", lambda e: self.overlay_refresh())
            self.make_clickthrough()
        self.overlay_refresh()

    def make_clickthrough(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.overlay.winfo_id())
            styles = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, styles | 0x80000 | 0x20)
        except Exception:
            pass

    def overlay_refresh(self):
        if not self.overlay: return
        mode = self.config.get("mode")
        opacity = self.config["image"]["opacity"] if mode == "image" else self.config["generated"]["opacity"]
        self.overlay.attributes("-alpha", max(0.1, opacity / 100))
        c = self.overlay_canvas; c.delete("all")
        if mode == "image": self.draw_image(c, preview=False)
        else: self.draw_generated(c)

    def close_overlay(self):
        if self.overlay:
            self.overlay.destroy(); self.overlay = None

    def on_close(self):
        self.config["window_geometry"] = self.root.geometry()
        self.refresh_all(); self.close_overlay(); self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
