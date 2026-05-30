# FFX Monster Arena Tracker

A desktop tracker for the Monster Arena in Final Fantasy X HD Remaster (PC/Steam).
Tracks capture counts, area creation unlocks, species creation unlocks, and original creation progress.

---

## Running the App

**Without Python installed:**
Double-click `FFX_MonsterArena_Tracker.exe`. No setup needed.

**If you have Python:**
```
python ffx_tracker.py
```

---

## How to Use

### Areas Tab
- Click an **area name** to expand/collapse its monster list
- Use **−** and **+** buttons to update your capture count for each monster
- A green **✓ Unlocked** appears when you've captured at least one of every monster in that area (unlocking its Area Creation)

### Species Tab
- Click a **creation name** (e.g. Fenrir) to expand/collapse its member monsters
- **−** and **+** buttons update counts here too — the same count synced with the Areas tab
- The header turns green when the creation is unlocked (all members at their required capture count)

### Creations Tab
- **Area Conquest** — shows each Area Creation with a progress bar (monsters captured / total needed)
- **Original** — shows each Original Creation with its unlock condition and live progress

### Summary Tab
- Overall stats at a glance: area creations, species creations, total monsters captured

### Detail Panel (right side)
- Click any monster name or thumbnail to see its info: HP, location, sensor/scan text, drops, and steals
- Use the **−** and **+** in the detail panel to update captures without leaving the view

### Dark / Light Mode
Toggle with the button in the top-right toolbar. Preference is saved automatically.

---

## Files

| File | Purpose |
|---|---|
| `FFX_MonsterArena_Tracker.exe` | Run this to launch the app |
| `ffx_tracker.py` | Python source (for editing/development) |
| `monsters.json` | ⚠️ DO NOT DELETE — monster database the app runs on |
| `banner.png` | Left sidebar image (swap with any portrait PNG) |
| `images/thumbnails/` | Monster card images |
| `ffx_save.json` | Your save data — created on first run |

> **To reset your progress:** delete `ffx_save.json`. It will be recreated fresh the next time you launch the app.
>
> **Never delete `monsters.json`** — the app will open empty with nothing to track.

---

## Customising the Banner

Replace `banner.png` with any image you like.
- **Format:** PNG
- **Best dimensions:** roughly 1:5 portrait ratio (e.g. 200×900 px)
- The image stretches to fill the sidebar automatically

---

## Notes

- Monster data and species assignments are sourced from [Jegged.com](https://jegged.com/Games/Final-Fantasy-X/)
- Species capture requirements vary: most need ×3–5, Ironclad needs ×10 of each member
- `ffx_save.json` stores both your capture progress and dark/light mode preference — back this file up if you want to preserve your progress

---

## Requirements (source only)

If running `ffx_tracker.py` directly rather than the exe:
```
pip install pillow
```
