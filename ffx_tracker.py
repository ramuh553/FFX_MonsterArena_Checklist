#!/usr/bin/env python3
"""
FFX Monster Arena Tracker
Monster data loaded from monsters.json (run scrape_ffx_monsters.py to generate).
Capture progress saved to ffx_captures.json.
"""

import json
import os
import re
import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path

try:
    from PIL import Image, ImageTk, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# When frozen by PyInstaller (--onefile), __file__ is inside a temp dir.
# Data files (monsters.json, images/, banner.png) live next to the .exe instead.
SCRIPT_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
SAVE_FILE  = SCRIPT_DIR / "ffx_save.json"
DATA_FILE  = SCRIPT_DIR / "monsters.json"
BANNER_FILE   = SCRIPT_DIR / "banner.png"

THUMB_SM = 44
THUMB_LG = 130  # detail panel image — larger now that hint text moved to toolbar


def _lerp_color(c1: str, c2: str, t: float) -> str:
    """Interpolate between two hex colours for crossfade animation."""
    r1,g1,b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
    r = max(0, min(255, int(r1 + (r2-r1)*t)))
    g = max(0, min(255, int(g1 + (g2-g1)*t)))
    b = max(0, min(255, int(b1 + (b2-b1)*t)))
    return f"#{r:02x}{g:02x}{b:02x}"

# Semantic accent colors (same in both themes)
GREEN  = "#4caf50"
ORANGE = "#e65100"
GRAY   = "#888888"

# ── Themes ─────────────────────────────────────────────────────────────────────

DARK = {
    "bg":    "#1a1a1a",
    "panel": "#222222",
    "text":  "#e8e8e8",
    "dim":   "#888888",
    "sep":   "#303030",
    "input": "#282828",
    "tab":   "#1e1e1e",
}
LIGHT = {
    "bg":    "#f0f0f0",
    "panel": "#ffffff",
    "text":  "#1a1a1a",
    "dim":   "#555555",
    "sep":   "#cccccc",
    "input": "#ffffff",
    "tab":   "#dcdcdc",
}

# ── Font scale ──────────────────────────────────────────────────────────────────
# All using Segoe UI for crisp Windows rendering.

F_AREA_HDR   = ("Segoe UI", 12, "bold")   # area section header
F_AREA_SUB   = ("Segoe UI", 10)           # "-> Stratoavis" subtitle
F_AREA_COUNT = ("Segoe UI", 10, "bold")   # "1/3" status label
F_MONSTER    = ("Segoe UI", 11)           # monster name + HP row
F_SPECIES    = ("Segoe UI", 10)           # [Canine] species tag
F_SP_HDR     = ("Segoe UI", 10, "bold")   # "Creation / Species / Status" header
F_SP_CREATE  = ("Segoe UI", 11, "bold")   # creation boss name
F_SP_MEMBER  = ("Segoe UI", 10)           # member monster name
F_SP_COUNT   = ("Segoe UI", 10)           # "3/10" count
F_DETAIL_NM  = ("Segoe UI", 14, "bold")   # name in detail panel
F_DETAIL_MT  = ("Segoe UI", 10)           # area / species meta
F_DETAIL_HP  = ("Segoe UI", 12, "bold")   # HP in detail panel
F_DETAIL_FLD = ("Segoe UI", 10, "bold")   # field label (Location:, Sensor:)
F_DETAIL_TXT = ("Segoe UI", 10)           # field body text
F_SUM_HDR    = ("Segoe UI", 14, "bold")   # Summary page header
F_SUM_LBL    = ("Segoe UI", 10)           # stat labels
F_SUM_VAL    = ("Segoe UI", 11, "bold")   # stat values
F_SUM_SM     = ("Segoe UI", 9)            # small list text in summary
F_HINT       = ("Segoe UI", 9)            # placeholder / hint text
F_TOGGLE     = ("Segoe UI", 9)            # theme toggle button

# ── Settings ────────────────────────────────────────────────────────────────────

def _load_save() -> dict:
    """Load ffx_save.json, migrating old split files if needed."""
    # One-time migration from the old two-file layout
    old_captures = SCRIPT_DIR / "ffx_captures.json"
    old_settings = SCRIPT_DIR / "ffx_settings.json"
    if not SAVE_FILE.exists() and (old_captures.exists() or old_settings.exists()):
        data: dict = {"settings": {"dark_mode": True}, "captures": {}}
        if old_settings.exists():
            try:
                data["settings"] = json.loads(old_settings.read_text(encoding="utf-8"))
            except Exception:
                pass
        if old_captures.exists():
            try:
                data["captures"] = json.loads(old_captures.read_text(encoding="utf-8")).get("captures", {})
            except Exception:
                pass
        SAVE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        old_captures.unlink(missing_ok=True)
        old_settings.unlink(missing_ok=True)
    if SAVE_FILE.exists():
        try:
            return json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"settings": {"dark_mode": True}, "captures": {}}


def _write_save(data: dict) -> None:
    SAVE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_settings() -> dict:
    return _load_save().get("settings", {"dark_mode": True})


def save_settings(settings: dict) -> None:
    data = _load_save()
    data["settings"] = settings
    _write_save(data)

# ── Hardcoded game data ────────────────────────────────────────────────────────

MONSTER_SPECIES: dict[str, str] = {
    # ── Fenrir (Canine) ── x3 each ────────────────────────────────────────────
    "Dingo":         "Canine",
    "Mi'ihen Fang":  "Canine",
    "Garm":          "Canine",
    "Snow Wolf":     "Canine",
    "Sand Wolf":     "Canine",
    "Skoll":         "Canine",
    "Bandersnatch":  "Canine",

    # ── Ornitholestes (Reptile) ── x3 each ───────────────────────────────────
    "Dinonix":  "Reptile",
    "Ipiria":   "Reptile",
    "Raptor":   "Reptile",
    "Melusine": "Reptile",
    "Iguion":   "Reptile",
    "Yowie":    "Reptile",   # not Evil Eye — confirmed via Jegged
    "Zaurus":   "Reptile",

    # ── Pteryx (Avian) ── x5 each ─────────────────────────────────────────────
    "Condor":  "Avian",
    "Simurgh": "Avian",
    "Alcyone": "Avian",

    # ── Hornet (Wasp) ── x4 each ──────────────────────────────────────────────
    "Killer Bee": "Wasp",
    "Bite Bug":   "Wasp",
    "Wasp":       "Wasp",
    "Nebiros":    "Wasp",    # not Avian — confirmed via Jegged

    # ── Vidatu (Imp) ── x4 each ───────────────────────────────────────────────
    "Gandarewa": "Imp",      # not Bomb — confirmed via Jegged
    "Aerouge":   "Imp",
    "Imp":       "Imp",

    # ── One-Eye (Evil Eye) ── x4 each ─────────────────────────────────────────
    "Floating Eye":   "Evil Eye",
    "Buer":           "Evil Eye",
    "Evil Eye":       "Evil Eye",
    "Ahriman":        "Evil Eye",
    "Floating Death": "Evil Eye",

    # ── Jumbo Flan (Flan) ── x3 each ─────────────────────────────────────────
    "Water Flan":   "Flan",
    "Thunder Flan": "Flan",
    "Snow Flan":    "Flan",
    "Ice Flan":     "Flan",
    "Flame Flan":   "Flan",
    "Dark Flan":    "Flan",

    # ── Nega Elemental (Elemental) ── x3 each ────────────────────────────────
    "Yellow Element": "Elemental",
    "White Element":  "Elemental",
    "Red Element":    "Elemental",
    "Gold Element":   "Elemental",
    "Blue Element":   "Elemental",
    "Dark Element":   "Elemental",
    "Black Element":  "Elemental",

    # ── Tanket (Helm) ── x3 each ──────────────────────────────────────────────
    "Raldo":   "Helm",
    "Bunyip":  "Helm",    # not Ruminant — confirmed via Jegged
    "Mafdet":  "Helm",    # not Feline — confirmed via Jegged
    "Murussu": "Helm",
    "Shred":   "Helm",    # not Reptile — confirmed via Jegged
    "Halma":   "Helm",    # not Imp — confirmed via Jegged

    # ── Fafnir (Dragon) ── x4 each ───────────────────────────────────────────
    "Vouivre":   "Dragon",
    "Lamashtu":  "Dragon",  # not Reptile — confirmed via Jegged
    "Kusariqqu": "Dragon",  # not Imp — confirmed via Jegged
    "Mushussu":  "Dragon",  # not Reptile — confirmed via Jegged
    "Nidhogg":   "Dragon",  # not Reptile — confirmed via Jegged

    # ── Sleep Sprout (Plantoid) ── x5 each ───────────────────────────────────
    "Funguar": "Plantoid",
    "Exoray":  "Plantoid",
    "Thorn":   "Plantoid",

    # ── Bomb King (Bomb) ── x5 each ──────────────────────────────────────────
    "Bomb":      "Bomb",
    "Grenade":   "Bomb",
    "Puroboros": "Bomb",

    # ── Juggernaut (Ruminant) ── x5 each ─────────────────────────────────────
    "Dual Horn": "Ruminant",
    "Grendel":   "Ruminant",  # not Dragon — confirmed via Jegged
    "Valaha":    "Ruminant",

    # ── Ironclad (Iron Giant) ── x10 each ────────────────────────────────────
    "Iron Giant":     "Iron Giant",
    "Gemini (Club)":  "Iron Giant",  # not Dragon — confirmed via Jegged
    "Gemini (Sword)": "Iron Giant",  # not Dragon — confirmed via Jegged

    # ── Not part of any Species Creation ─────────────────────────────────────
    "Ragora": "", "Garuda": "", "Basilisk": "", "Ochu": "", "Larva": "",
    "Qactuar": "", "Xiphos": "", "Chimera": "", "Zu": "", "Cactuar": "",
    "Sand Worm": "", "Anacondaur": "", "Ogre": "", "Coeurl": "",
    "Chimera Brain": "", "Malboro": "", "Tonberry": "", "Ghost": "",
    "Behemoth": "", "Splasher": "", "Achelous": "", "Maelspike": "",
    "Wraith": "", "Demonolith": "", "Great Malboro": "", "Barbatos": "",
    "Adamantoise": "", "Behemoth King": "", "Varuna": "", "Spirit": "",
    "Machea": "", "Master Coeurl": "", "Master Tonberry": "",
    "Bashura": "", "Epaaj": "",
}

SPECIES_CREATIONS: dict[str, str] = {
    "Fenrir":         "Canine",
    "Ornitholestes":  "Reptile",
    "Pteryx":         "Avian",
    "Hornet":         "Wasp",
    "Vidatu":         "Imp",
    "One-Eye":        "Evil Eye",
    "Jumbo Flan":     "Flan",
    "Nega Elemental": "Elemental",
    "Tanket":         "Helm",
    "Fafnir":         "Dragon",
    "Sleep Sprout":   "Plantoid",
    "Bomb King":      "Bomb",
    "Juggernaut":     "Ruminant",
    "Ironclad":       "Iron Giant",
}

# Captures of each member required to unlock that creation (source: Jegged.com)
SPECIES_REQUIREMENTS: dict[str, int] = {
    "Fenrir":         3,
    "Ornitholestes":  3,
    "Pteryx":         5,
    "Hornet":         4,
    "Vidatu":         4,
    "One-Eye":        4,
    "Jumbo Flan":     3,
    "Nega Elemental": 3,
    "Tanket":         3,
    "Fafnir":         4,
    "Sleep Sprout":   5,
    "Bomb King":      5,
    "Juggernaut":     5,
    "Ironclad":       10,
}

AREA_CREATION_MAP: dict[str, str | None] = {
    "Besaid":              "Stratoavis",
    "Kilika":              "Malboro Menace",
    "Mi'ihen Highroad":    "Kottos",
    "Mushroom Rock Road":  "Coeurlregina",
    "Djose Road":          "Jormungand",
    "Thunder Plains":      "Cactuar King",
    "Macalania":           "Espada",
    "Bikanel":             "Abyss Wyrm",
    "Calm Lands":          "Chimerageist",
    "Stolen Fayth Cavern": "Don Tonberry",
    "Mt. Gagazet":         "Catoblepas",
    "Inside Sin":          "Abaddon",
    "Omega Ruins":         "Vorban",
}

AREA_ORDER = [
    "Besaid", "Kilika", "Mi'ihen Highroad", "Mushroom Rock Road",
    "Djose Road", "Thunder Plains", "Macalania", "Bikanel",
    "Calm Lands", "Stolen Fayth Cavern", "Mt. Gagazet", "Inside Sin", "Omega Ruins",
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    return (name
            .replace("Miâihen", "Mi'ihen")  # Miâihen → Mi'ihen (encoding artifact)
            .replace("Miaihen",      "Mi'ihen")
            .replace("Thâuban", "Th'uban")  # Thâuban → Th'uban (encoding artifact)
            .replace("Thauban",      "Th'uban")
            .strip())


def clean_text(s: str) -> str:
    s = re.sub(r'[^\x00-\x7F]', '', s)
    return s.strip().strip('"').strip("'").strip()


def resolve(rel: str) -> str:
    if not rel:
        return ""
    p = SCRIPT_DIR / rel
    return str(p) if p.exists() else ""


# ── Data helpers ───────────────────────────────────────────────────────────────

def load_raw_monsters() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    for m in raw:
        m["name"] = normalize_name(m["name"])
    return raw


def build_areas(raw: list[dict]) -> list[dict]:
    by_area: dict[str, list[dict]] = {}
    for m in raw:
        if m.get("category") == "Area Fiend":
            by_area.setdefault(m["area"], []).append(m)
    areas = []
    for area_name in AREA_ORDER:
        if area_name not in by_area:
            continue
        monsters = [
            (m["name"], MONSTER_SPECIES.get(m["name"], ""))
            for m in by_area[area_name]
        ]
        areas.append({
            "name":          area_name,
            "area_creation": AREA_CREATION_MAP.get(area_name),
            "monsters":      monsters,
        })
    return areas


def all_unique_monsters(areas: list[dict]) -> dict[str, str]:
    seen: dict[str, str] = {}
    for area in areas:
        for name, species in area["monsters"]:
            seen.setdefault(name, species)
    return seen


def load_captures(areas: list[dict]) -> dict[str, int]:
    captures: dict[str, int] = _load_save().get("captures", {})
    for name in all_unique_monsters(areas):
        captures.setdefault(name, 0)
    return captures


def save_captures(captures: dict[str, int]) -> None:
    data = _load_save()
    data["captures"] = captures
    _write_save(data)


def area_unlocked(area: dict, captures: dict[str, int]) -> bool:
    return all(captures.get(n, 0) >= 1 for n, _ in area["monsters"])


def species_monsters(species: str, areas: list[dict]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for area in areas:
        for name, sp in area["monsters"]:
            if sp == species and name not in seen:
                seen.add(name)
                result.append(name)
    return result


def species_unlocked(species: str, captures: dict[str, int], areas: list[dict]) -> bool:
    ms = species_monsters(species, areas)
    return bool(ms) and all(captures.get(n, 0) >= 10 for n in ms)


def creation_progress(creation: str, captures: dict[str, int], areas: list[dict]) -> tuple[int, int, bool]:
    """Return (members_done, total_members, unlocked) using the creation's actual requirement."""
    sp  = SPECIES_CREATIONS.get(creation, "")
    req = SPECIES_REQUIREMENTS.get(creation, 10)
    ms  = species_monsters(sp, areas)
    done = sum(1 for n in ms if captures.get(n, 0) >= req)
    return done, len(ms), done == len(ms)


# Underwater fiends in Mt. Gagazet caves (required for Shinryu)
_GAGAZET_AQUAN = ["Splasher", "Achelous", "Maelspike"]

def original_progress(name: str, captures: dict[str, int], areas: list[dict]) -> tuple[str, int, int]:
    """Return (condition_text, current, maximum) for an Original Creation."""
    ac_done = sum(1 for a in areas if a["area_creation"] and area_unlocked(a, captures))
    sc_done = sum(1 for sp in SPECIES_CREATIONS.values()
                  if species_unlocked(sp, captures, areas))
    all_m   = list(all_unique_monsters(areas).keys())

    if name == "Earth Eater":
        return "Unlock 2 Area Conquest fiends", min(ac_done, 2), 2
    if name == "Greater Sphere":
        return "Unlock 2 Species Conquest fiends", min(sc_done, 2), 2
    if name == "Catastrophe":
        return "Unlock 6 Area Conquest fiends", min(ac_done, 6), 6
    if name == "Th'uban":
        return "Unlock 6 Species Conquest fiends", min(sc_done, 6), 6
    if name == "Neslug":
        done = sum(1 for m in all_m if captures.get(m, 0) >= 1)
        return "Capture 1 of each fiend in Spira", done, len(all_m)
    if name == "Ultima Buster":
        done = sum(1 for m in all_m if captures.get(m, 0) >= 5)
        return "Capture 5 of each fiend in Spira", done, len(all_m)
    if name == "Shinryu":
        done = sum(1 for m in _GAGAZET_AQUAN if captures.get(m, 0) >= 2)
        return "Capture 2 of each underwater fiend in Mt. Gagazet caves", done, len(_GAGAZET_AQUAN)
    if name == "Nemesis":
        done = sum(1 for m in all_m if captures.get(m, 0) >= 10)
        return "Capture 10 of every fiend and defeat all creations", done, len(all_m)
    return "", 0, 1


# ── Image cache ────────────────────────────────────────────────────────────────

class ImageCache:
    def __init__(self) -> None:
        self._cache: dict[tuple, object] = {}

    def get(self, path: str, size: int) -> object:
        if not HAS_PIL or not path or not os.path.exists(path):
            return None
        key = (path, size)
        if key in self._cache:
            return self._cache[key]
        try:
            img   = Image.open(path).convert("RGBA")
            img   = ImageOps.fit(img, (size, size), Image.LANCZOS, centering=(0.5, 0.35))
            photo = ImageTk.PhotoImage(img)
            self._cache[key] = photo
            return photo
        except Exception:
            return None


# ── Application ────────────────────────────────────────────────────────────────

class FFXTracker(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("FFX Monster Arena Tracker")
        self.geometry("1060x760")
        self.minsize(800, 520)

        # ── Theme setup ────────────────────────────────────────────────────────
        settings    = load_settings()
        self._dark  = settings.get("dark_mode", True)
        self._style = ttk.Style(self)
        self._style.theme_use("clam")
        self._apply_theme(save=False)

        # ── Data ───────────────────────────────────────────────────────────────
        raw             = load_raw_monsters()
        self.monster_db = {m["name"]: m for m in raw}
        self.areas      = build_areas(raw)
        self.captures   = load_captures(self.areas)
        self.imgs       = ImageCache()

        # ── Widget registries ──────────────────────────────────────────────────
        self.count_vars:         dict[str, tk.IntVar]       = {}
        self.monster_bars:       dict[str, list]            = {}
        self.one_markers:        dict[str, list]            = {}
        self.ten_markers:        dict[str, list]            = {}
        self.area_status_labels: dict[str, ttk.Label]       = {}
        self.species_status_lbl: dict[str, ttk.Label]       = {}
        self.species_min_bars:   dict[str, ttk.Progressbar] = {}
        self._summary_host:      ttk.Frame | None           = None
        self._detail_panel:      ttk.Frame | None           = None
        self._detail_content:    ttk.Frame | None           = None
        self._toggle_btn:        ttk.Button | None          = None

        # Collapsible area state
        self._area_expanded: dict[str, bool]      = {}
        self._area_bodies:   dict[str, ttk.Frame] = {}
        self._area_arrows:   dict[str, ttk.Label] = {}
        self._area_spacers:  dict[str, ttk.Label] = {}

        # Collapsible creations-tab section state
        self._cr_expanded: dict[str, bool]      = {}
        self._cr_bodies:   dict[str, ttk.Frame] = {}
        self._cr_arrows:   dict[str, ttk.Label] = {}
        self._cr_spacers:  dict[str, ttk.Label] = {}

        # Collapsible species state
        self._sp_expanded:      dict[str, bool]      = {}
        self._sp_bodies:        dict[str, ttk.Frame] = {}
        self._sp_arrows:        dict[str, ttk.Label] = {}
        self._sp_spacers:       dict[str, ttk.Label] = {}
        self._sp_unlock_dots:   dict[str, ttk.Label] = {}

        # Count display labels (for +/- buttons)
        self.count_labels: dict[str, list] = {}

        for name in self.captures:
            var = tk.IntVar(value=self.captures[name])
            var.trace_add("write", lambda *_, n=name: self._on_change(n))
            self.count_vars[name]   = var
            self.monster_bars[name] = []
            self.one_markers[name]  = []
            self.ten_markers[name]  = []
            self.count_labels[name] = []

        self._build()

    # ── Theme helpers ───────────────────────────────────────────────────────────

    @property
    def T(self) -> dict:
        """Current theme colour dict."""
        return DARK if self._dark else LIGHT

    def _apply_theme(self, save: bool = True, palette: dict | None = None) -> None:
        T   = palette if palette is not None else self.T
        s   = self._style
        bg  = T["bg"];  panel = T["panel"]; text = T["text"]
        dim = T["dim"]; sep   = T["sep"];   inp  = T["input"]; tab = T["tab"]

        s.configure(".",
            background=bg, foreground=text, fieldbackground=inp,
            selectbackground=panel, selectforeground=text,
            bordercolor=sep, lightcolor=panel, darkcolor=sep)
        s.configure("TFrame",    background=bg)
        s.configure("TLabel",    background=bg, foreground=text)
        s.configure("TNotebook", background=tab, tabmargins=[2, 5, 2, 0])
        s.configure("TNotebook.Tab",
            background=tab, foreground=dim, padding=[12, 5], focuscolor=bg)
        s.map("TNotebook.Tab",
            background=[("selected", bg)],
            foreground=[("selected", text)])
        s.configure("TSeparator",          background=sep)
        s.configure("Vertical.TSeparator", background=sep)
        s.configure("Vertical.TScrollbar",
            background=panel, troughcolor=bg, arrowcolor=text, bordercolor=sep)
        s.configure("Horizontal.TScrollbar",
            background=panel, troughcolor=bg, arrowcolor=text)
        s.configure("TProgressbar", troughcolor=panel, background="#5566dd")
        s.configure("TSpinbox",
            fieldbackground=inp, foreground=text, background=inp,
            arrowcolor=text, insertcolor=text)
        s.configure("TButton",
            background=panel, foreground=text, padding=[8, 4],
            bordercolor=sep, relief="flat")
        s.map("TButton", background=[("active", sep)])
        s.configure("TLabelframe",       background=bg, bordercolor=sep)
        s.configure("TLabelframe.Label", background=bg, foreground=dim,
                    font=F_SUM_LBL)

        self.configure(bg=bg)
        self._repaint_canvases()

        if getattr(self, "_toggle_btn", None):
            self._toggle_btn.configure(
                text="Light Mode" if self._dark else "Dark Mode")

        if save:
            save_settings({"dark_mode": self._dark})

    def _repaint_canvases(self, widget=None) -> None:
        """Update bg on tk.Canvas widgets (ttk handles itself)."""
        if widget is None:
            widget = self
        bg = self.T["bg"]
        for w in widget.winfo_children():
            if w.winfo_class() == "Canvas":
                try:
                    w.configure(bg=bg)
                except Exception:
                    pass
            self._repaint_canvases(w)

    def _toggle_theme(self) -> None:
        start     = DARK if self._dark else LIGHT   # capture before flip
        self._dark = not self._dark
        if self._toggle_btn:
            self._toggle_btn.configure(
                text="Light Mode" if self._dark else "Dark Mode")
        save_settings({"dark_mode": self._dark})
        self._animate_theme(start, self.T, step=0, steps=22)

    def _animate_theme(self, start: dict, end: dict, step: int, steps: int) -> None:
        t = step / steps
        t = t * t * (3 - 2 * t)   # smoothstep easing
        blended = {k: _lerp_color(start[k], end[k], t) for k in end}
        self._apply_theme(save=False, palette=blended)
        if step < steps:
            self.after(13, lambda: self._animate_theme(start, end, step + 1, steps))
        else:
            self._apply_theme(save=False)
            if self._detail_content:
                name = getattr(self._detail_content, "_monster_name", None)
                if name:
                    self._show_detail(name)

    # ── Change handler ──────────────────────────────────────────────────────────

    def _on_change(self, name: str) -> None:
        try:
            val = max(0, min(10, self.count_vars[name].get()))
        except tk.TclError:
            return
        if val == self.captures.get(name):
            return
        self.captures[name] = val

        for bar in self.monster_bars.get(name, []):
            bar.configure(value=val)
        for lbl in self.count_labels.get(name, []):
            lbl.configure(text=str(val))
        for lbl in self.one_markers.get(name, []):
            lbl.configure(text="✓" if val >= 1 else " ",
                          foreground=GREEN if val >= 1 else GRAY)
        for lbl in self.ten_markers.get(name, []):
            lbl.configure(text="✓" if val >= 10 else "·",
                          foreground=GREEN if val >= 10 else GRAY)

        for area in self.areas:
            if area["area_creation"] and any(n == name for n, _ in area["monsters"]):
                lbl = self.area_status_labels.get(area["name"])
                if lbl:
                    unlocked = area_unlocked(area, self.captures)
                    done = sum(1 for n, _ in area["monsters"] if self.captures.get(n, 0) >= 1)
                    lbl.configure(
                        text="Unlocked" if unlocked else f"{done}/{len(area['monsters'])}",
                        foreground=GREEN if unlocked else GRAY,
                    )

        for creation, sp in SPECIES_CREATIONS.items():
            if name in species_monsters(sp, self.areas):
                done, total, unlocked = creation_progress(creation, self.captures, self.areas)
                dot = self._sp_unlock_dots.get(creation)
                if dot:
                    dot.configure(text="✓" if unlocked else "·",
                                  foreground=GREEN if unlocked else GRAY)
                lbl = self.species_status_lbl.get(creation)
                if lbl:
                    lbl.configure(
                        text="Unlocked" if unlocked else f"{done}/{total}",
                        foreground=GREEN if unlocked else GRAY,
                    )

        save_captures(self.captures)

    # ── Detail panel ────────────────────────────────────────────────────────────

    def _show_detail(self, name: str) -> None:
        data = self.monster_db.get(name, {})

        # Clean up destroyed widgets from previous detail view
        if self._detail_content:
            old = getattr(self._detail_content, "_monster_name", None)
            if old:
                self.monster_bars[old]  = [w for w in self.monster_bars.get(old, [])
                                            if w.winfo_exists()]
                self.count_labels[old]  = [w for w in self.count_labels.get(old, [])
                                            if w.winfo_exists()]
            self._detail_content.destroy()

        content = ttk.Frame(self._detail_panel)
        content.pack(fill="both", expand=True)
        content._monster_name = name          # type: ignore[attr-defined]
        self._detail_content  = content

        # ── Header: large image centred, then name/stats below it ─────────────
        top = ttk.Frame(content, padding=(8, 8, 8, 4))
        top.pack(fill="x")

        thumb_path = resolve(data.get("thumbnail_local_path", ""))
        photo = self.imgs.get(thumb_path, THUMB_LG)
        if photo:
            il = tk.Label(top, image=photo, bg=self.T["panel"], relief="flat")
            il.image = photo  # type: ignore[attr-defined]
            il.pack(anchor="center")

        species = MONSTER_SPECIES.get(name, "")
        area    = data.get("area", "")
        hp      = data.get("hp", "")

        ttk.Label(content, text=name, font=F_DETAIL_NM,
                  wraplength=260, justify="center").pack(anchor="center", padx=8)
        if area:
            ttk.Label(content, text=area, foreground=self.T["dim"],
                      font=F_DETAIL_MT, justify="center").pack(anchor="center")
        if species:
            ttk.Label(content, text=f"Species: {species}",
                      foreground=self.T["dim"], font=F_DETAIL_MT).pack(anchor="center")
        if hp:
            ttk.Label(content, text=f"HP: {hp}",
                      font=F_DETAIL_HP, foreground=ORANGE).pack(anchor="center", pady=(2, 0))

        # ── Capture counter (+/- bar) ─────────────────────────────────────────
        if name in self.count_vars:
            count = self.captures.get(name, 0)
            cap   = ttk.Frame(content, padding=(8, 6, 8, 2))
            cap.pack(fill="x")
            ttk.Label(cap, text="Captured:", font=F_DETAIL_FLD).pack(side="left")
            ttk.Button(cap, text="−", width=2,
                       command=lambda: self._adjust(name, -1)).pack(side="left", padx=(8, 0))
            cnt_lbl = ttk.Label(cap, text=str(count), width=3,
                                anchor="center", font=F_DETAIL_HP)
            cnt_lbl.pack(side="left")
            ttk.Button(cap, text="+", width=2,
                       command=lambda: self._adjust(name, +1)).pack(side="left")
            bar = ttk.Progressbar(cap, length=90, maximum=10, value=count)
            bar.pack(side="left", padx=(8, 0))
            self.count_labels[name].append(cnt_lbl)
            self.monster_bars[name].append(bar)

        ttk.Separator(content, orient="horizontal").pack(fill="x", padx=8, pady=(4, 6))

        # ── Scrollable body for all text + drop data ──────────────────────
        sc_outer  = ttk.Frame(content)
        sc_outer.pack(fill="both", expand=True)
        sc_canvas = tk.Canvas(sc_outer, highlightthickness=0, bg=self.T["bg"])
        sc_vbar   = ttk.Scrollbar(sc_outer, orient="vertical", command=sc_canvas.yview)
        sc_canvas.configure(yscrollcommand=sc_vbar.set)
        sc_inner  = ttk.Frame(sc_canvas)
        sc_wid    = sc_canvas.create_window((0, 0), window=sc_inner, anchor="nw")
        sc_canvas.bind("<Configure>", lambda e: sc_canvas.itemconfigure(sc_wid, width=e.width))
        sc_inner.bind("<Configure>",  lambda _: sc_canvas.configure(scrollregion=sc_canvas.bbox("all")))

        def _sc_scroll(e): sc_canvas.yview_scroll(-1 * (e.delta // 120), "units")
        sc_canvas.bind("<Enter>", lambda _: sc_canvas.bind_all("<MouseWheel>", _sc_scroll))
        sc_canvas.bind("<Leave>", lambda _: sc_canvas.unbind_all("<MouseWheel>"))

        sc_vbar.pack(side="right", fill="y")
        sc_canvas.pack(side="left", fill="both", expand=True)

        def field(label: str, value) -> None:
            v = clean_text(str(value)) if value else ""
            if not v or v in ("-", "—", "N/A"):
                return
            ttk.Label(sc_inner, text=label, font=F_DETAIL_FLD,
                      anchor="w").pack(anchor="w", padx=8, pady=(4, 0))
            ttk.Label(sc_inner, text=v, wraplength=255, justify="left",
                      foreground=self.T["dim"], font=F_DETAIL_TXT,
                      anchor="w").pack(anchor="w", padx=8, pady=(0, 5))

        def drop_list(label: str, items) -> None:
            if not items:
                return
            if isinstance(items, str):
                items = [items]
            items = [clean_text(str(i)) for i in items
                     if clean_text(str(i)) not in ("", "-", "—", "N/A")]
            if not items:
                return
            ttk.Label(sc_inner, text=label, font=F_DETAIL_FLD,
                      anchor="w").pack(anchor="w", padx=8, pady=(4, 0))
            for item in items:
                ttk.Label(sc_inner, text=f"  • {item}", wraplength=230,
                          justify="left", foreground=self.T["dim"],
                          font=F_DETAIL_TXT).pack(anchor="w", padx=8)
            ttk.Label(sc_inner, text="").pack()

        field("Location:", data.get("location_notes", ""))
        field("Sensor:",   data.get("sensor_text",   ""))
        field("Scan:",     data.get("scan_text",     ""))
        field("AP:",       data.get("ap",            ""))
        field("Gil:",      data.get("gil",           ""))

        # Drop data — tries several common field name patterns from scraped data
        drop_list("Common Drop:",
                  data.get("common_drop") or data.get("drop_common") or data.get("drops", []))
        drop_list("Rare Drop:",
                  data.get("rare_drop") or data.get("drop_rare", []))
        drop_list("Common Steal:",
                  data.get("common_steal") or data.get("steal_common") or data.get("steal", []))
        drop_list("Rare Steal:",
                  data.get("rare_steal") or data.get("steal_rare", []))
        drop_list("Bribe:",
                  data.get("bribe") or data.get("bribe_item", []))
        field("Bribe Gil:", data.get("bribe_gil", ""))

    # ── UI scaffold ─────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Thin top toolbar with theme toggle
        toolbar = ttk.Frame(self, padding=(6, 4, 6, 2))
        toolbar.pack(fill="x", side="top")
        btn = ttk.Button(toolbar,
                         text="Light Mode" if self._dark else "Dark Mode",
                         command=self._toggle_theme,
                         width=12)
        btn.pack(side="right")
        self._toggle_btn = btn
        ttk.Label(toolbar, text="Click any monster or image to see details",
                  foreground=self.T["dim"], font=F_HINT).pack(side="left", padx=4)
        ttk.Separator(self, orient="horizontal").pack(fill="x", side="top")

        # Main container: banner | notebook | detail panel
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        # Footer attribution (clickable link)
        import webbrowser
        ttk.Separator(self, orient="horizontal").pack(fill="x", side="bottom")
        link = ttk.Label(self, text="Contents sourced from https://jegged.com/Games/Final-Fantasy-X/",
                         foreground="#cc2222", font=("Segoe UI", 8),
                         anchor="center", cursor="hand2")
        link.pack(side="bottom", pady=(2, 3))
        link.bind("<Button-1>",
                  lambda _: webbrowser.open("https://jegged.com/Games/Final-Fantasy-X/"))

        # Left banner sidebar
        banner_frame = ttk.Frame(container, width=134)
        banner_frame.pack(side="left", fill="y", padx=(4, 0), pady=4)
        banner_frame.pack_propagate(False)
        self._load_banner(banner_frame)

        left = ttk.Frame(container)
        left.pack(side="left", fill="both", expand=True)

        nb = ttk.Notebook(left)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        self._populate_areas(self._scrollable_tab(nb, "  Areas  "))
        self._populate_species(self._scrollable_tab(nb, "  Species  "))
        self._populate_creations(self._scrollable_tab(nb, "  Creations  "))

        host = ttk.Frame(nb)
        nb.add(host, text="  Summary  ")
        self._summary_host = host
        self._populate_summary(host)

        nb.bind("<<NotebookTabChanged>>", lambda _: self._on_tab_change(nb))

        # Detail panel
        ttk.Separator(container, orient="vertical").pack(side="left", fill="y")
        panel = ttk.Frame(container, width=280)
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)
        self._detail_panel = panel

        # Detail panel starts empty — hint is in the toolbar

    def _load_banner(self, parent: ttk.Frame) -> None:
        if not (HAS_PIL and BANNER_FILE.exists()):
            ttk.Label(parent, text="Drop\nbanner.png\nnext to\nthis script",
                      foreground=self.T["dim"], justify="center",
                      font=F_HINT).pack(expand=True)
            return
        try:
            orig = Image.open(BANNER_FILE).convert("RGB")
            c    = tk.Canvas(parent, highlightthickness=0, bd=0, bg=self.T["bg"])
            c.pack(fill="both", expand=True)
            c._orig  = orig   # type: ignore[attr-defined]
            c._photo = None   # type: ignore[attr-defined]

            def _resize(event, _c=c, _orig=orig):
                w, h = event.width, event.height
                if w < 2 or h < 2:
                    return
                resized   = _orig.resize((w, h), Image.LANCZOS)
                photo     = ImageTk.PhotoImage(resized)
                _c._photo = photo  # type: ignore[attr-defined]
                _c.delete("all")
                _c.create_image(0, 0, anchor="nw", image=photo)

            c.bind("<Configure>", _resize)
        except Exception as e:
            ttk.Label(parent, text=f"Banner error:\n{e}",
                      foreground=self.T["dim"], justify="center",
                      font=F_HINT, wraplength=120).pack(expand=True)

    def _adjust(self, name: str, delta: int) -> None:
        new_val = max(0, min(10, self.captures.get(name, 0) + delta))
        self.count_vars[name].set(new_val)

    def _on_tab_change(self, nb: ttk.Notebook) -> None:
        if nb.tab(nb.select(), "text").strip() == "Summary":
            for w in self._summary_host.winfo_children():  # type: ignore[union-attr]
                w.destroy()
            self._populate_summary(self._summary_host)     # type: ignore[arg-type]

    def _scrollable_tab(self, nb: ttk.Notebook, title: str) -> ttk.Frame:
        outer  = ttk.Frame(nb)
        canvas = tk.Canvas(outer, highlightthickness=0, bg=self.T["bg"])
        vbar   = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        inner  = ttk.Frame(canvas)
        wid    = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(wid, width=e.width))
        inner.bind("<Configure>",  lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        def _scroll(e): canvas.yview_scroll(-1 * (e.delta // 120), "units")
        canvas.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>", _scroll))
        canvas.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))
        vbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        nb.add(outer, text=title)
        return inner

    # ── Areas tab (collapsible) ──────────────────────────────────────────────────

    def _toggle_area(self, area_name: str) -> None:
        expanded = self._area_expanded.get(area_name, False)
        body     = self._area_bodies.get(area_name)
        arrow    = self._area_arrows.get(area_name)
        spacer   = self._area_spacers.get(area_name)
        if body is None:
            return
        if expanded:
            body.pack_forget()
            if arrow: arrow.configure(text="▶")
        else:
            # Insert body just before its spacer
            body.pack(fill="x", before=spacer)
            if arrow: arrow.configure(text="▼")
        self._area_expanded[area_name] = not expanded

    def _populate_areas(self, parent: ttk.Frame) -> None:
        for area in self.areas:
            monsters = area["monsters"]
            done     = sum(1 for n, _ in monsters if self.captures.get(n, 0) >= 1)
            unlocked = done == len(monsters) and bool(area["area_creation"])

            # ── Clickable header ──────────────────────────────────────────────
            hdr = ttk.Frame(parent, padding=(6, 8, 6, 4), cursor="hand2")
            hdr.pack(fill="x")

            arrow = ttk.Label(hdr, text="▶", width=2, font=F_AREA_HDR,
                              cursor="hand2")
            arrow.pack(side="left")
            self._area_arrows[area["name"]] = arrow

            ttk.Label(hdr, text=area["name"], font=F_AREA_HDR,
                      cursor="hand2").pack(side="left", padx=(2, 0))

            if area["area_creation"]:
                ttk.Label(hdr, text=f"  →  {area['area_creation']}",
                          foreground=self.T["dim"], font=F_AREA_SUB,
                          cursor="hand2").pack(side="left")
                sl = ttk.Label(hdr,
                    text="Unlocked" if unlocked else f"{done}/{len(monsters)}",
                    foreground=GREEN if unlocked else GRAY,
                    font=F_AREA_COUNT, cursor="hand2")
                sl.pack(side="right", padx=6)
                self.area_status_labels[area["name"]] = sl

            # Bind click to header and all its children
            for w in [hdr] + list(hdr.winfo_children()):
                w.bind("<Button-1>", lambda _, n=area["name"]: self._toggle_area(n))

            ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=6)

            # ── Collapsible body (starts hidden) ──────────────────────────────
            body = ttk.Frame(parent)
            self._area_bodies[area["name"]] = body
            self._area_expanded[area["name"]] = False

            for name, species in monsters:
                count = self.captures.get(name, 0)
                mdata = self.monster_db.get(name, {})
                hp    = mdata.get("hp", "")
                thumb = self.imgs.get(resolve(mdata.get("thumbnail_local_path", "")), THUMB_SM)

                row = ttk.Frame(body, padding=(8, 3, 6, 3))
                row.pack(fill="x")

                if thumb is not None:
                    il = tk.Label(row, image=thumb, cursor="hand2",
                                  relief="groove", bd=1)
                    il.image = thumb  # type: ignore[attr-defined]
                    il.pack(side="left", padx=(0, 8))
                    il.bind("<Button-1>", lambda _, n=name: self._show_detail(n))
                else:
                    sp = ttk.Frame(row, width=THUMB_SM, height=THUMB_SM)
                    sp.pack_propagate(False)
                    sp.pack(side="left", padx=(0, 8))

                mk = ttk.Label(row, text="✓" if count >= 1 else " ", width=2,
                               foreground=GREEN if count >= 1 else GRAY,
                               font=F_MONSTER)
                mk.pack(side="left")
                self.one_markers[name].append(mk)

                label_text = name + (f"   HP: {hp}" if hp else "")
                nl = ttk.Label(row, text=label_text, width=30, anchor="w",
                               font=F_MONSTER, cursor="hand2")
                nl.pack(side="left")
                nl.bind("<Button-1>", lambda _, n=name: self._show_detail(n))

                ttk.Label(row, text=f"[{species}]" if species else "",
                          width=14, anchor="w",
                          foreground=self.T["dim"], font=F_SPECIES).pack(side="left")

                var = self.count_vars.get(name)
                if var is not None:
                    ttk.Button(row, text="−", width=2,
                               command=lambda n=name: self._adjust(n, -1)).pack(side="left")
                    cnt = ttk.Label(row, text=str(count), width=3,
                                    anchor="center", font=F_MONSTER)
                    cnt.pack(side="left")
                    ttk.Button(row, text="+", width=2,
                               command=lambda n=name: self._adjust(n, +1)).pack(side="left", padx=(0, 6))
                    self.count_labels[name].append(cnt)
                    bar = ttk.Progressbar(row, length=110, maximum=10, value=count)
                    bar.pack(side="left")
                    self.monster_bars[name].append(bar)

            # Spacer — body is inserted before this when expanded
            spacer = ttk.Label(parent, text="")
            spacer.pack()
            self._area_spacers[area["name"]] = spacer

    # ── Species tab (collapsible by species name) ────────────────────────────────

    def _toggle_species(self, creation: str) -> None:
        expanded = self._sp_expanded.get(creation, False)
        body     = self._sp_bodies.get(creation)
        arrow    = self._sp_arrows.get(creation)
        spacer   = self._sp_spacers.get(creation)
        if body is None:
            return
        if expanded:
            body.pack_forget()
            if arrow: arrow.configure(text="▶")
        else:
            body.pack(fill="x", before=spacer)
            if arrow: arrow.configure(text="▼")
        self._sp_expanded[creation] = not expanded

    def _populate_species(self, parent: ttk.Frame) -> None:
        for creation, sp in SPECIES_CREATIONS.items():
            monsters         = species_monsters(sp, self.areas)
            req              = SPECIES_REQUIREMENTS.get(creation, 10)
            done, total, unlocked = creation_progress(creation, self.captures, self.areas)

            # ── Clickable header — species name is the primary label ──────────
            hdr = ttk.Frame(parent, padding=(4, 8, 6, 4), cursor="hand2")
            hdr.pack(fill="x")

            arrow = ttk.Label(hdr, text="▶", width=2, font=F_AREA_HDR,
                              cursor="hand2")
            arrow.pack(side="left")
            self._sp_arrows[creation] = arrow

            # ✓/· unlock dot stays left of species name
            dot = ttk.Label(hdr, text="✓" if unlocked else "·", width=2,
                            foreground=GREEN if unlocked else GRAY,
                            font=F_AREA_HDR, cursor="hand2")
            dot.pack(side="left")
            self._sp_unlock_dots[creation] = dot

            # Creation name → Species name
            ttk.Label(hdr, text=creation, font=F_AREA_HDR,
                      cursor="hand2").pack(side="left", padx=(2, 0))
            ttk.Label(hdr, text=f"  →  {sp}", foreground=self.T["dim"],
                      font=F_AREA_SUB, cursor="hand2").pack(side="left")

            # Status text on the right — matches Areas header style
            st = "Unlocked" if unlocked else f"{done}/{total}"
            sf = GREEN if unlocked else GRAY
            sl = ttk.Label(hdr, text=st, foreground=sf, font=F_AREA_COUNT,
                           cursor="hand2")
            sl.pack(side="right", padx=(4, 6))
            self.species_status_lbl[creation] = sl

            # Bind entire header to toggle
            for w in [hdr] + list(hdr.winfo_children()):
                w.bind("<Button-1>", lambda _, c=creation: self._toggle_species(c))

            ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=6)

            # ── Collapsible body ──────────────────────────────────────────────
            body = ttk.Frame(parent)
            self._sp_bodies[creation]   = body
            self._sp_expanded[creation] = False

            # Creation boss row — indented LESS than members so it sticks out left
            cdata  = self.monster_db.get(creation, {})
            cthumb = self.imgs.get(resolve(cdata.get("thumbnail_local_path", "")), THUMB_SM)
            boss_row = ttk.Frame(body, padding=(8, 4, 6, 2))   # 8px vs members' 20px
            boss_row.pack(fill="x")
            if cthumb:
                bl = tk.Label(boss_row, image=cthumb, cursor="hand2",
                              relief="groove", bd=1)
                bl.image = cthumb  # type: ignore[attr-defined]
                bl.pack(side="left", padx=(0, 6))
                bl.bind("<Button-1>", lambda _, n=creation: self._show_detail(n))
            bn = ttk.Label(boss_row, text=creation, font=F_SP_CREATE, cursor="hand2")
            bn.pack(side="left")
            bn.bind("<Button-1>", lambda _, n=creation: self._show_detail(n))
            ttk.Label(boss_row, text=f"({sp} — capture ×{req} of each to unlock)",
                      foreground=self.T["dim"], font=("Segoe UI", 8)).pack(side="left", padx=(8, 0))
            ttk.Separator(body, orient="horizontal").pack(fill="x", padx=12, pady=2)

            for mname in monsters:
                count  = self.captures.get(mname, 0)
                mdata  = self.monster_db.get(mname, {})
                mthumb = self.imgs.get(resolve(mdata.get("thumbnail_local_path", "")), THUMB_SM)

                mrow = ttk.Frame(body, padding=(20, 2, 6, 2))
                mrow.pack(fill="x")

                if mthumb:
                    ml = tk.Label(mrow, image=mthumb, cursor="hand2")
                    ml.image = mthumb  # type: ignore[attr-defined]
                    ml.pack(side="left", padx=(0, 6))
                    ml.bind("<Button-1>", lambda _, n=mname: self._show_detail(n))

                mk = ttk.Label(mrow, text="✓" if count >= 10 else "·", width=2,
                               foreground=GREEN if count >= 10 else GRAY,
                               font=F_SP_MEMBER)
                mk.pack(side="left")
                self.ten_markers[mname].append(mk)

                mn = ttk.Label(mrow, text=mname, width=22, anchor="w",
                               font=F_SP_MEMBER, cursor="hand2")
                mn.pack(side="left")
                mn.bind("<Button-1>", lambda _, n=mname: self._show_detail(n))

                ttk.Button(mrow, text="−", width=2,
                           command=lambda n=mname: self._adjust(n, -1)).pack(side="left")
                cnt = ttk.Label(mrow, text=str(count), width=3,
                                anchor="center", font=F_SP_MEMBER)
                cnt.pack(side="left")
                ttk.Button(mrow, text="+", width=2,
                           command=lambda n=mname: self._adjust(n, +1)).pack(side="left", padx=(0, 4))
                self.count_labels[mname].append(cnt)

                bar = ttk.Progressbar(mrow, length=90, maximum=10, value=count)
                bar.pack(side="left", padx=(0, 4))
                self.monster_bars[mname].append(bar)

                ttk.Label(mrow, text=f"{count}/10",
                          font=F_SP_COUNT,
                          foreground=self.T["dim"]).pack(side="left")

            spacer = ttk.Label(parent, text="")
            spacer.pack()
            self._sp_spacers[creation] = spacer

    # ── Creations tab ────────────────────────────────────────────────────────────

    def _toggle_cr_section(self, key: str) -> None:
        expanded = self._cr_expanded.get(key, True)
        body   = self._cr_bodies.get(key)
        arrow  = self._cr_arrows.get(key)
        spacer = self._cr_spacers.get(key)
        if body is None:
            return
        if expanded:
            body.pack_forget()
            if arrow: arrow.configure(text="▶")
        else:
            body.pack(fill="x", before=spacer)
            if arrow: arrow.configure(text="▼")
        self._cr_expanded[key] = not expanded

    def _cr_section(self, parent: ttk.Frame, title: str) -> ttk.Frame:
        """Create a collapsible section header and return its body frame."""
        hdr = ttk.Frame(parent, padding=(4, 8, 6, 4), cursor="hand2")
        hdr.pack(fill="x")
        arrow = ttk.Label(hdr, text="▶", width=2, font=F_AREA_HDR, cursor="hand2")
        arrow.pack(side="left")
        self._cr_arrows[title] = arrow
        ttk.Label(hdr, text=title, font=F_AREA_HDR, cursor="hand2").pack(side="left", padx=(2, 0))
        for w in [hdr] + list(hdr.winfo_children()):
            w.bind("<Button-1>", lambda _, k=title: self._toggle_cr_section(k))
        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=6)
        body = ttk.Frame(parent)
        # body starts hidden — user clicks to expand
        self._cr_bodies[title]   = body
        self._cr_expanded[title] = False
        spacer = ttk.Label(parent, text="")
        spacer.pack()
        self._cr_spacers[title] = spacer
        return body

    def _populate_creations(self, parent: ttk.Frame) -> None:
        raw = list(self.monster_db.values())

        # ── Area Conquest ─────────────────────────────────────────────────────
        ac_by_name = {m["name"]: m for m in raw if m.get("category") == "Area Conquest"}
        body_ac = self._cr_section(parent, "Area Conquest")

        for area in self.areas:
            creation_name = area.get("area_creation")
            if not creation_name or creation_name not in ac_by_name:
                continue
            mdata    = ac_by_name[creation_name]
            monsters = area["monsters"]
            done     = sum(1 for n, _ in monsters if self.captures.get(n, 0) >= 1)
            total    = len(monsters)
            unlocked = done == total

            row = ttk.Frame(body_ac, padding=(10, 4, 10, 4))
            row.pack(fill="x")

            thumb = self.imgs.get(resolve(mdata.get("thumbnail_local_path", "")), THUMB_SM)
            if thumb:
                il = tk.Label(row, image=thumb, cursor="hand2", relief="groove", bd=1)
                il.image = thumb  # type: ignore[attr-defined]
                il.pack(side="left", padx=(0, 10))
                il.bind("<Button-1>", lambda _, n=creation_name: self._show_detail(n))

            # Text block
            txt = ttk.Frame(row)
            txt.pack(side="left", fill="x", expand=True)
            nl = ttk.Label(txt, text=creation_name, font=F_SP_CREATE, cursor="hand2")
            nl.pack(anchor="w")
            nl.bind("<Button-1>", lambda _, n=creation_name: self._show_detail(n))
            ttk.Label(txt, text=f"Unlocks from: {area['name']}",
                      foreground=self.T["dim"], font=F_DETAIL_MT).pack(anchor="w")

            # Right: status + bar
            right = ttk.Frame(row)
            right.pack(side="right", anchor="center")
            ttk.Label(right,
                      text="✓ Unlocked" if unlocked else f"{done} / {total} captured",
                      foreground=GREEN if unlocked else GRAY,
                      font=F_AREA_COUNT).pack(anchor="e")
            bar = ttk.Progressbar(right, length=120, maximum=total, value=done)
            bar.pack(anchor="e", pady=(2, 0))

            ttk.Separator(body_ac, orient="horizontal").pack(fill="x", padx=20)

        # ── Original ──────────────────────────────────────────────────────────
        originals = [m for m in raw if m.get("category") == "Original"]
        body_or = self._cr_section(parent, "Original")

        for mdata in originals:
            name          = mdata.get("name", "")
            hp            = mdata.get("hp", "")
            cond, cur, mx = original_progress(name, self.captures, self.areas)
            unlocked      = cur >= mx

            # Same layout as Area Conquest rows
            row = ttk.Frame(body_or, padding=(10, 4, 10, 4))
            row.pack(fill="x")

            thumb = self.imgs.get(resolve(mdata.get("thumbnail_local_path", "")), THUMB_SM)
            if thumb:
                il = tk.Label(row, image=thumb, cursor="hand2", relief="groove", bd=1)
                il.image = thumb  # type: ignore[attr-defined]
                il.pack(side="left", padx=(0, 10))
                il.bind("<Button-1>", lambda _, n=name: self._show_detail(n))

            # Centre text block
            txt = ttk.Frame(row)
            txt.pack(side="left", fill="x", expand=True)
            nl = ttk.Label(txt, text=name, font=F_SP_CREATE, cursor="hand2")
            nl.pack(anchor="w")
            nl.bind("<Button-1>", lambda _, n=name: self._show_detail(n))
            if cond:
                ttk.Label(txt, text=cond, foreground=self.T["dim"],
                          font=F_DETAIL_MT, wraplength=180).pack(anchor="w", pady=(2, 0))

            # Right block: status + bar (identical structure to Area Conquest)
            right = ttk.Frame(row)
            right.pack(side="right", anchor="center")
            ttk.Label(right,
                      text="✓ Unlocked" if unlocked else f"{cur} / {mx}",
                      foreground=GREEN if unlocked else GRAY,
                      font=F_AREA_COUNT).pack(anchor="e")
            ttk.Progressbar(right, length=120, maximum=max(mx, 1),
                            value=cur).pack(anchor="e", pady=(2, 0))

            ttk.Separator(body_or, orient="horizontal").pack(fill="x", padx=20)

    # ── Summary tab ─────────────────────────────────────────────────────────────

    def _populate_summary(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Unlock Summary", font=F_SUM_HDR).pack(anchor="w", pady=(0, 12))

        area_done = sum(1 for a in self.areas if a["area_creation"] and area_unlocked(a, self.captures))
        area_tot  = sum(1 for a in self.areas if a["area_creation"])
        sp_done   = sum(1 for _, sp in SPECIES_CREATIONS.items()
                        if species_unlocked(sp, self.captures, self.areas))
        total   = len(self.captures)
        cap_any = sum(1 for v in self.captures.values() if v >= 1)
        cap_ten = sum(1 for v in self.captures.values() if v >= 10)

        stats = ttk.LabelFrame(frame, text="Overall Progress", padding=10)
        stats.pack(fill="x", pady=(0, 12))
        for label, value in [
            ("Area Creations unlocked",    f"{area_done} / {area_tot}"),
            ("Species Creations unlocked", f"{sp_done} / {len(SPECIES_CREATIONS)}"),
            ("Monsters captured (>=1)",    f"{cap_any} / {total}"),
            ("Monsters maxed at 10",       f"{cap_ten} / {total}"),
        ]:
            r = ttk.Frame(stats)
            r.pack(fill="x", pady=3)
            ttk.Label(r, text=label, width=30, anchor="w",
                      font=F_SUM_LBL, foreground=self.T["dim"]).pack(side="left")
            ttk.Label(r, text=value, font=F_SUM_VAL).pack(side="left", padx=8)

        cols = ttk.Frame(frame)
        cols.pack(fill="x")
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)

        alf = ttk.LabelFrame(cols, text="Area Creations", padding=8)
        alf.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        for area in self.areas:
            if not area["area_creation"]:
                continue
            unlocked = area_unlocked(area, self.captures)
            done_m   = sum(1 for n, _ in area["monsters"] if self.captures.get(n, 0) >= 1)
            tot_m    = len(area["monsters"])
            r = ttk.Frame(alf)
            r.pack(fill="x", pady=2)
            ttk.Label(r, text="✓" if unlocked else "·", width=2,
                      foreground=GREEN if unlocked else GRAY,
                      font=F_SUM_SM).pack(side="left")
            ttk.Label(r, text=area["name"], width=22, anchor="w",
                      font=F_SUM_SM).pack(side="left")
            ttk.Label(r, text=f"{done_m}/{tot_m}", foreground=self.T["dim"],
                      font=F_SUM_SM).pack(side="left")

        slf = ttk.LabelFrame(cols, text="Species Creations", padding=8)
        slf.grid(row=0, column=1, sticky="nsew")
        for creation, sp in SPECIES_CREATIONS.items():
            unlocked = species_unlocked(sp, self.captures, self.areas)
            monsters = species_monsters(sp, self.areas)
            done_m   = sum(1 for n in monsters if self.captures.get(n, 0) >= 10)
            r = ttk.Frame(slf)
            r.pack(fill="x", pady=2)
            ttk.Label(r, text="✓" if unlocked else "·", width=2,
                      foreground=GREEN if unlocked else GRAY,
                      font=F_SUM_SM).pack(side="left")
            ttk.Label(r, text=creation, width=18, anchor="w",
                      font=F_SUM_SM).pack(side="left")
            ttk.Label(r, text=f"{done_m}/{len(monsters)}@10",
                      foreground=self.T["dim"], font=F_SUM_SM).pack(side="left")



def main() -> None:
    FFXTracker().mainloop()


if __name__ == "__main__":
    main()
