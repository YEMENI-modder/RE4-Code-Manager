"""
RE4 Code Patcher Tool
=====================
Main application entry point.
Reads code definitions from the_codes/codes_info.json
Reads hex patch data  from the_codes/codes_data.json
"""

import sys
import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox

# ── paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
CODES_DIR = os.path.join(BASE_DIR, "the_codes")
INFO_FILE = os.path.join(CODES_DIR, "codes_info.json")
DATA_FILE = os.path.join(CODES_DIR, "codes_data.json")
ORIG_FILE    = os.path.join(CODES_DIR, "bio4_original.exe")
PROFILES_DIR = os.path.join(BASE_DIR, "Profiles")
LOG_FILE     = os.path.join(BASE_DIR, "patch_log.txt")

# ── language ─────────────────────────────────────────────────────────────────
CURRENT_LANG = "en"   # "ar" or "en" — change in Settings

def t(ar_text, en_text):
    """Return Arabic or English string based on current language."""
    return en_text if CURRENT_LANG == "en" else ar_text


def write_log(action, code_name, exe_path=""):
    """Append an entry to patch_log.txt."""
    from datetime import datetime
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {action}: {code_name}")
            if exe_path:
                f.write(f"  |  EXE: {exe_path}")
            f.write("\n")
    except Exception:
        pass


# ── colors ───────────────────────────────────────────────────────────────────
BG_MAIN    = "#0d0d0d"
BG_PANEL   = "#111111"
BG_SIDEBAR = "#0a0a0a"
BG_ROW     = "#141414"
BG_ROW_ON  = "#0d1a0d"
BG_ROW_LK  = "#0d0d0d"
BG_ROW_SEL = "#1a1a0a"
BG_HEADER  = "#0f0c00"
BG_TOPBAR  = "#0f0c00"
BG_PATHBAR = "#111111"
BG_NOTICE  = "#1a1200"
BG_STATUS  = "#0a0a0a"
BG_APPLY   = "#0a1a0a"

ACCENT     = "#e8c060"
ACCENT2    = "#ffd060"
GREEN      = "#7aff7a"
RED_SOFT   = "#ff9090"
ORANGE     = "#e8b860"
MUTED      = "#888888"
TEXT_MAIN  = "#e0d0b0"
TEXT_DIM   = "#aaaaaa"
TEXT_LOCK  = "#666666"
BORDER     = "#4a4a2a"
BORDER_ON  = "#3a7a3a"
BORDER_LK  = "#3a2a2a"
BORDER_SEL = "#8a8a3a"

FONT_TITLE  = ("Courier New", 13, "bold")
FONT_NORMAL = ("Courier New", 11)
FONT_SMALL  = ("Courier New", 10)
FONT_TINY   = ("Courier New", 9)
FONT_BOLD   = ("Courier New", 11, "bold")


# ═════════════════════════════════════════════════════════════════════════════
#  Arabic RTL helper
# ═════════════════════════════════════════════════════════════════════════════

def fix_ar(text):
    """
    Manual bidi for tkinter (no external libs).
    Splits text into Arabic and non-Arabic runs,
    reverses the run order so Arabic displays RTL.
    English words inside Arabic text stay readable.
    """
    if not text:
        return text
    if not any("\u0600" <= c <= "\u06ff" for c in text):
        return text

    # Split into tokens by space
    tokens = text.split(" ")

    # Separate into runs: each run is a list of tokens of same direction
    runs = []
    cur_type = None
    cur_tokens = []

    for tok in tokens:
        # determine token type: arabic if contains arabic char, else latin
        is_ar = any("\u0600" <= c <= "\u06ff" for c in tok)
        ttype = "ar" if is_ar else "en"

        if ttype != cur_type:
            if cur_tokens:
                runs.append((cur_type, cur_tokens))
            cur_type = ttype
            cur_tokens = [tok]
        else:
            cur_tokens.append(tok)

    if cur_tokens:
        runs.append((cur_type, cur_tokens))

    # Reverse overall run order for RTL
    runs.reverse()

    # Build final string
    # For Arabic runs: keep token order (already reversed by run reversal)
    # For English runs inside: keep as-is
    parts = []
    for rtype, rtokens in runs:
        if rtype == "ar":
            # reverse tokens within arabic run for correct word order
            parts.append(" ".join(reversed(rtokens)))
        else:
            parts.append(" ".join(rtokens))

    return " ".join(parts)


# ═════════════════════════════════════════════════════════════════════════════
#  Data helpers
# ═════════════════════════════════════════════════════════════════════════════

def load_json(path):
    if not os.path.exists(path):
        messagebox.showerror("Missing File", "Cannot find:\n" + path)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def scan_exe(path, codes_info, codes_data):
    """
    Scan bio4.exe for ALL codes.
    A code is considered applied only if ALL its patches match.
    For find_replace  -> replace bytes must be present.
    For offset_paste / offset_replace -> bytes at offset must match.
    """
    results = {}
    try:
        with open(path, "rb") as f:
            exe_bytes = f.read()
    except Exception:
        return results

    for code in codes_info.get("codes", []):
        cid = code["id"]

        # special case: link_tweaks_exe detected by offset 7212FC != "31 2E 30 2E 36"
        if cid == "link_tweaks_exe":
            try:
                off = 0x7212FC
                chunk = exe_bytes[off:off + 5]
                results[cid] = chunk != bytes.fromhex("312E302E36")
            except Exception:
                results[cid] = False
            continue

        data = codes_data.get(cid, {})

        # get patches (handle variants — check first variant)
        if "variants" in data:
            first_variant = list(data["variants"].values())[0]
            patches = first_variant.get("patches", [])
        else:
            patches = data.get("patches", [])

        if not patches:
            results[cid] = False
            continue

        # check ALL patches — code is applied only if every patch matches
        all_match = True
        for patch in patches:
            try:
                ptype = patch["type"]
                if ptype == "find_replace":
                    needle = bytes.fromhex(patch["replace"].replace(" ", ""))
                    if needle not in exe_bytes:
                        all_match = False
                        break
                elif ptype in ("offset_paste", "offset_replace"):
                    offset = int(patch["offset"], 16)
                    needle = bytes.fromhex(patch["bytes"].replace(" ", ""))
                    if exe_bytes[offset:offset + len(needle)] != needle:
                        all_match = False
                        break
                else:
                    all_match = False
                    break
            except Exception:
                all_match = False
                break

        results[cid] = all_match

    return results


def is_game_running(exe_path):
    """Check if bio4.exe process is currently running."""
    import subprocess
    exe_name = os.path.basename(exe_path).lower()
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq " + exe_name, "/NH"],
            capture_output=True, text=True
        )
        return exe_name in result.stdout.lower()
    except Exception:
        return False


def _friendly_error(e):
    msg = str(e)
    if "13" in msg or "Permission denied" in msg or "Access is denied" in msg:
        return (
            "Permission Denied -- Cannot write to EXE.\n\n"
            "Solutions:\n"
            "1. Run this tool as Administrator (right-click -> Run as administrator)\n"
            "2. Copy bio4.exe to Desktop or Documents and use that copy"
        )
    return msg


BACKUP_FILE = os.path.join(BASE_DIR, "patch_backup.json")


def load_patch_backup():
    if os.path.isfile(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_patch_backup(backup):
    try:
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def apply_patch(exe_path, code_id, codes_data, mod_expansion=None):
    entry = codes_data.get(code_id)
    if not entry:
        return False, "No patch data for '" + code_id + "'"

    try:
        with open(exe_path, "rb") as f:
            exe = bytearray(f.read())
    except Exception as e:
        return False, _friendly_error(e)

    if "variants" in entry:
        patches = list(entry["variants"][
            "with_mod_expansion" if mod_expansion else "without_mod_expansion"
        ]["patches"])
    else:
        patches = list(entry.get("patches", []))

    all_patches = patches + entry.get("shared_patches", [])

    backup = load_patch_backup()
    code_backup = {}

    for patch in all_patches:
        try:
            ptype = patch["type"]
            if ptype == "find_replace":
                find_b    = bytes.fromhex(patch["find"].replace(" ", ""))
                replace_b = bytes.fromhex(patch["replace"].replace(" ", ""))
                idx = exe.find(find_b)
                if idx == -1:
                    return False, "Pattern not found:\n" + patch["find"][:40] + "..."
                exe[idx:idx + len(find_b)] = replace_b
            elif ptype in ("offset_paste", "offset_replace"):
                off    = int(patch["offset"], 16)
                data_b = bytes.fromhex(patch["bytes"].replace(" ", ""))
                key    = patch["offset"].upper().lstrip("0") or "0"
                code_backup[key] = exe[off:off + len(data_b)].hex().upper()
                exe[off:off + len(data_b)] = data_b
        except Exception as e:
            return False, _friendly_error(e)

    backup[code_id] = code_backup
    save_patch_backup(backup)

    try:
        with open(exe_path, "wb") as f:
            f.write(exe)
    except Exception as e:
        return False, _friendly_error(e)

    return True, "OK"


def revert_patch(exe_path, orig_path, code_id, codes_data, mod_expansion=None):
    """
    Revert using (priority):
    1. find_replace  -> swap replace->find
    2. offset_*      -> bio4_original.exe (most reliable — true original)
    3. offset_*      -> patch_backup.json fallback (stored at apply time)
    4. offset_replace -> skip if neither available
    5. offset_paste   -> fail if neither available
    Returns (success, message, skipped)
    """
    entry = codes_data.get(code_id)
    if not entry:
        return False, "No patch data for '" + code_id + "'", 0

    try:
        with open(exe_path, "rb") as f:
            exe = bytearray(f.read())
    except Exception as e:
        return False, _friendly_error(e), 0

    orig = None
    if os.path.isfile(orig_path):
        try:
            with open(orig_path, "rb") as f:
                orig = f.read()
        except Exception:
            pass

    backup     = load_patch_backup()
    code_backup = backup.get(code_id, {})

    if "variants" in entry:
        patches = list(entry["variants"][
            "with_mod_expansion" if mod_expansion else "without_mod_expansion"
        ]["patches"])
    else:
        patches = list(entry.get("patches", []))

    skipped = 0
    for patch in patches:
        ptype = patch.get("type", "")
        try:
            if ptype == "find_replace":
                find_b    = bytes.fromhex(patch["find"].replace(" ", ""))
                replace_b = bytes.fromhex(patch["replace"].replace(" ", ""))
                idx = exe.find(replace_b)
                if idx == -1:
                    skipped += 1
                    continue
                exe[idx:idx + len(replace_b)] = find_b

            elif ptype in ("offset_paste", "offset_replace"):
                off    = int(patch["offset"], 16)
                length = len(bytes.fromhex(patch["bytes"].replace(" ", "")))
                key    = patch["offset"].upper().lstrip("0") or "0"

                # 1. bio4_original.exe — الأولوية القصوى (نسخة أصلية مضمونة)
                if orig is not None:
                    chunk = orig[off:off + length]
                    if len(chunk) == length:
                        exe[off:off + length] = chunk
                        continue

                # 2. patch_backup.json — fallback (بايتات مخزّنة وقت التطبيق)
                if key in code_backup:
                    chunk = bytes.fromhex(code_backup[key])
                    if len(chunk) == length:
                        exe[off:off + length] = chunk
                        continue

                # 3. لا يوجد مصدر
                if ptype == "offset_paste":
                    return False, (
                        "Cannot revert at " + patch["offset"] + ".\n"
                        "Place bio4_original.exe in the_codes/ folder."
                    ), skipped
                else:
                    skipped += 1

        except Exception as e:
            return False, str(e), skipped

    try:
        with open(exe_path, "wb") as f:
            f.write(exe)
    except Exception as e:
        return False, _friendly_error(e), skipped

    if code_id in backup:
        del backup[code_id]
        save_patch_backup(backup)

    return True, "OK", skipped


# ═════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═════════════════════════════════════════════════════════════════════════════

def make_label(parent, text="", fg=TEXT_MAIN, bg=BG_MAIN,
               font=FONT_SMALL, **kw):
    return tk.Label(parent, text=text, fg=fg, bg=bg, font=font, **kw)


def make_button(parent, text, command, fg=ACCENT, bg="#2a2a1a",
                active_bg="#3a3a2a", font=FONT_SMALL, width=10, **kw):
    return tk.Button(
        parent, text=text, command=command,
        fg=fg, bg=bg,
        activeforeground=fg, activebackground=active_bg,
        font=font, width=width,
        relief="flat", bd=0, cursor="hand2",
        highlightthickness=1, highlightbackground=BORDER,
        **kw
    )


# ═════════════════════════════════════════════════════════════════════════════
#  CodeRow
# ═════════════════════════════════════════════════════════════════════════════

class CodeRow(tk.Frame):
    def __init__(self, parent, code, app, **kw):
        super().__init__(parent, bg=BG_ROW,
                         highlightthickness=1,
                         highlightbackground=BORDER, **kw)
        self.code      = code
        self.app       = app
        self._expanded = False
        self.selected  = False
        self._build()

    def _get_name(self):
        if CURRENT_LANG == "en":
            return self.code.get("name_en", self.code["name"])
        return self.code["name"]

    def _get_desc(self):
        if CURRENT_LANG == "en":
            return self.code.get("desc_en", self.code.get("desc", ""))
        return fix_ar(self.code.get("desc", ""))

    def _get_notes(self):
        if CURRENT_LANG == "en":
            return self.code.get("notes_en", [])
        return self.code.get("notes", [])

    def _build(self):
        top = tk.Frame(self, bg=BG_ROW)
        top.pack(fill="x", padx=6, pady=4)

        # ── checkbox (queue for Apply Selected) ──
        self.sel_var = tk.IntVar(value=0)
        self.sel_chk = tk.Checkbutton(
            top, variable=self.sel_var,
            bg=BG_ROW, activebackground=BG_ROW,
            fg=ACCENT, selectcolor="#1a1a1a",
            relief="flat", bd=0,
            command=self._on_select
        )
        self.sel_chk.pack(side="left", padx=(0, 2))

        # ── ON/OFF toggle button ──
        self.toggle_btn = tk.Button(
            top, text="OFF", width=5, font=FONT_TINY,
            fg="#bbbbbb", bg="#1a1a1a",
            activeforeground="#bbbbbb", activebackground="#222",
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground="#555",
            cursor="hand2",
            command=self._on_toggle
        )
        self.toggle_btn.pack(side="left", padx=(0, 6))

        # ── status badge [L] / blank ──
        self.status_var = tk.StringVar(value="")
        self.status_lbl = tk.Label(
            top, textvariable=self.status_var,
            font=FONT_TINY, fg=MUTED, bg=BG_ROW, width=3,
            anchor="center"
        )
        self.status_lbl.pack(side="left", padx=(0, 4))

        # ── name + desc ──
        info_frame = tk.Frame(top, bg=BG_ROW)
        info_frame.pack(side="left", fill="x", expand=True)

        self.name_lbl = tk.Label(
            info_frame, text=self._get_name(),
            font=FONT_NORMAL, fg="#f0e0c0", bg=BG_ROW,
            anchor="w", justify="left"
        )
        self.name_lbl.pack(anchor="w")

        self.desc_lbl = tk.Label(
            info_frame, text=self._get_desc(),
            font=FONT_TINY, fg="#aaaaaa", bg=BG_ROW,
            anchor="w", justify="left", wraplength=500
        )
        self.desc_lbl.pack(anchor="w")

        notes = self._get_notes()

        # ── expand arrow (only if notes) ──
        if notes:
            self.arrow_btn = tk.Button(
                top, text="[v]", width=3, font=FONT_TINY,
                fg=MUTED, bg=BG_ROW,
                activeforeground=MUTED, activebackground=BG_ROW,
                relief="flat", bd=0, cursor="hand2",
                command=self._toggle_notes
            )
            self.arrow_btn.pack(side="right")

        # ── notes frame ──
        self.notes_frame = tk.Frame(self, bg="#0d0d00")
        for note in notes:
            txt = note if CURRENT_LANG == "en" else fix_ar(note)
            tk.Label(
                self.notes_frame, text=txt,
                font=FONT_TINY, fg="#ffcc66", bg="#0d0d00",
                anchor="w", justify="left"
            ).pack(anchor="w", padx=8, pady=1)

    def _toggle_notes(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.notes_frame.pack(fill="x")
            self.arrow_btn.configure(text="[^]")
        else:
            self.notes_frame.pack_forget()
            self.arrow_btn.configure(text="[v]")

    def _on_toggle(self):
        self.app.handle_toggle(self.code["id"])

    def _on_select(self):
        if self.sel_var.get() == 1 and not self.app._is_unlocked(self.code["id"]):
            self.sel_var.set(0)
            self.app.handle_toggle(self.code["id"])  # shows the locked message
            return
        self.selected = bool(self.sel_var.get())
        self.app.on_row_select_change()

    def refresh(self, applied, locked, detected):
        if detected and not applied:
            applied = True

        has_arrow = hasattr(self, "arrow_btn")

        # checkbox: disabled if locked or already applied
        if locked or applied:
            self.sel_chk.configure(state="disabled")
            self.sel_var.set(0)
            self.selected = False
        else:
            self.sel_chk.configure(state="normal")

        if locked and applied:
            # Special: code is ON in EXE but base dependency is off
            # Show ON (green) but with [L] badge and disabled toggle
            bg = "#0d1a0a"  # slightly darker green
            self.configure(bg=bg, highlightbackground="#1a4a1a")
            self.toggle_btn.configure(
                text="ON", fg="#3a9a3a", bg="#1a2a1a",
                highlightbackground="#2a5a2a", state="disabled"
            )
            self.status_var.set("[L]")
            self.status_lbl.configure(fg="#c85a2a", bg=bg)
            self.name_lbl.configure(fg="#a0c0a0", bg=bg, font=FONT_BOLD)
            self.desc_lbl.configure(bg=bg)
            self.sel_chk.configure(bg=bg, activebackground=bg)
            if has_arrow:
                self.arrow_btn.configure(bg=bg, activebackground=bg)

        elif locked:
            bg = BG_ROW_LK
            self.configure(bg=bg, highlightbackground=BORDER_LK)
            self.toggle_btn.configure(
                text="OFF", fg=TEXT_LOCK, bg="#1a1a1a",
                highlightbackground="#333", state="disabled"
            )
            self.status_var.set("[L]")
            self.status_lbl.configure(fg="#c85a2a", bg=bg)
            self.name_lbl.configure(fg=TEXT_LOCK, bg=bg, font=FONT_NORMAL)
            self.desc_lbl.configure(bg=bg)
            self.sel_chk.configure(bg=bg, activebackground=bg)
            if has_arrow:
                self.arrow_btn.configure(bg=bg, activebackground=bg)
            self.notes_frame.configure(bg="#0d0d00")

        elif applied:
            bg = BG_ROW_ON
            self.configure(bg=bg, highlightbackground=BORDER_ON)
            self.toggle_btn.configure(
                text="ON", fg=GREEN, bg="#2a5a2a",
                highlightbackground=GREEN, state="normal"
            )
            self.status_var.set("")
            self.status_lbl.configure(fg=MUTED, bg=bg)
            self.name_lbl.configure(fg="#e8e0c0", bg=bg, font=FONT_BOLD)
            self.desc_lbl.configure(bg=bg)
            self.sel_chk.configure(bg=bg, activebackground=bg)
            if has_arrow:
                self.arrow_btn.configure(bg=bg, activebackground=bg)

        else:
            bg = BG_ROW_SEL if self.selected else BG_ROW
            border = BORDER_SEL if self.selected else BORDER
            self.configure(bg=bg, highlightbackground=border)
            self.toggle_btn.configure(
                text="OFF", fg=MUTED, bg="#1a1a1a",
                highlightbackground="#444", state="normal"
            )
            self.status_var.set("")
            self.status_lbl.configure(fg=MUTED, bg=bg)
            self.name_lbl.configure(fg=TEXT_MAIN, bg=bg, font=FONT_NORMAL)
            self.desc_lbl.configure(bg=bg)
            self.sel_chk.configure(bg=bg, activebackground=bg)
            if has_arrow:
                self.arrow_btn.configure(bg=bg, activebackground=bg)


# ═════════════════════════════════════════════════════════════════════════════
#  SidebarItem
# ═════════════════════════════════════════════════════════════════════════════

class SidebarItem(tk.Frame):
    def __init__(self, parent, section, app, **kw):
        super().__init__(parent, bg=BG_SIDEBAR, **kw)
        self.section = section
        self.app     = app

        self.indicator = tk.Frame(self, bg=BG_SIDEBAR, width=3)
        self.indicator.pack(side="left", fill="y")

        label = section.get("label_en", section["label"]) if CURRENT_LANG == "en" else section["label"]
        self.btn = tk.Button(
            self, text=label,
            font=FONT_SMALL, fg="#cccccc", bg=BG_SIDEBAR,
            activeforeground=ACCENT2, activebackground="#1a1200",
            anchor="w", relief="flat", bd=0, cursor="hand2",
            command=lambda: app.select_section(section["id"])
        )
        self.btn.pack(side="left", fill="x", expand=True, ipady=6)

    def set_active(self, active):
        if active:
            self.btn.configure(fg=ACCENT2, bg="#1a1200",
                               activebackground="#1a1200")
            self.indicator.configure(bg=ACCENT)
        else:
            self.btn.configure(fg="#cccccc", bg=BG_SIDEBAR,
                               activebackground="#1a1200")
            self.indicator.configure(bg=BG_SIDEBAR)


# ═════════════════════════════════════════════════════════════════════════════
#  Main App
# ═════════════════════════════════════════════════════════════════════════════

class RE4PatcherApp(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("RE4 Code Patcher Tool -- Preview")
        self.geometry("1000x680")
        self.minsize(820, 560)
        self.configure(bg=BG_MAIN)

        self.exe_path       = tk.StringVar()
        self.scanned        = False
        self.detected       = {}
        self.applied        = {}
        self.active_section = None

        self.codes_info = load_json(INFO_FILE)
        self.codes_data = load_json(DATA_FILE)

        self.sections_list    = self.codes_info["sections"]
        self.all_codes        = self.codes_info["codes"]
        self.code_by_id       = {c["id"]: c for c in self.all_codes}
        self.codes_by_section = {}
        for c in self.all_codes:
            self.codes_by_section.setdefault(c["section"], []).append(c)

        self._build_ui()
        self.select_section(self.sections_list[0]["id"])
        # set initial total count
        self.status_total_var.set(
            ("Total codes: " if CURRENT_LANG == "en" else "إجمالي الأكواد: ")
            + str(len(self.all_codes))
        )

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # top bar
        topbar = tk.Frame(self, bg=BG_TOPBAR)
        topbar.pack(fill="x")
        make_label(topbar, "RE4 Code Patcher Tool",
                   fg=ACCENT2, bg=BG_TOPBAR, font=FONT_TITLE
                   ).pack(side="left", padx=14, pady=6)
        make_label(topbar, "v1.0.0",
                   fg=MUTED, bg=BG_TOPBAR, font=FONT_TINY
                   ).pack(side="left")
        make_label(topbar, "by YEMENI",
                   fg="#888", bg=BG_TOPBAR, font=FONT_TINY
                   ).pack(side="right", padx=14)
        make_button(topbar, "Settings", self._open_settings,
                    fg=ACCENT, bg=BG_TOPBAR, active_bg="#1a1200",
                    font=FONT_TINY, width=8
                    ).pack(side="right", padx=4)

        # exe path row
        path_bar = tk.Frame(self, bg=BG_PATHBAR)
        path_bar.pack(fill="x")
        make_label(path_bar, "Game Executable (bio4.exe):",
                   fg=TEXT_DIM, bg=BG_PATHBAR
                   ).pack(side="left", padx=(12, 6), pady=5)
        self.path_entry = tk.Entry(
            path_bar, textvariable=self.exe_path,
            font=FONT_SMALL, fg="#7cfc7c", bg="#0d1a0d",
            insertbackground="#7cfc7c",
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground="#2a5a2a",
            width=48
        )
        self.path_entry.pack(side="left", pady=5, ipady=3)

        make_button(path_bar, "Browse...", self._browse,
                    fg=ACCENT, bg="#2a2a1a", active_bg="#3a3a2a", width=9
                    ).pack(side="left", padx=6, pady=5)
        self.scan_btn = make_button(
            path_bar, "Scan EXE", self._scan,
            fg=GREEN, bg="#1a2a0a", active_bg="#2a4a1a", width=9
        )
        self.scan_btn.pack(side="left", padx=2, pady=5)
        self.scan_status_var = tk.StringVar(value="")
        make_label(path_bar, fg=GREEN, bg=BG_PATHBAR, font=FONT_TINY,
                   textvariable=self.scan_status_var
                   ).pack(side="left", padx=8)

        # notice bar
        self.notice = tk.Frame(self, bg=BG_NOTICE)
        make_label(
            self.notice,
            fix_ar("[!] حط مسار bio4.exe واضغط Scan عشان تشوف وتفعل الاكواد"),
            fg=ACCENT, bg=BG_NOTICE
        ).pack(side="left", padx=10, pady=4)
        self.notice.pack(fill="x")

        # main body
        body = tk.Frame(self, bg=BG_MAIN)
        body.pack(fill="both", expand=True)

        # sidebar
        sidebar_outer = tk.Frame(body, bg=BG_SIDEBAR, width=210)
        sidebar_outer.pack(side="left", fill="y")
        sidebar_outer.pack_propagate(False)

        sb_canvas = tk.Canvas(sidebar_outer, bg=BG_SIDEBAR,
                              highlightthickness=0, width=210)
        sb_scroll = tk.Scrollbar(sidebar_outer, orient="vertical",
                                 command=sb_canvas.yview)
        sb_canvas.configure(yscrollcommand=sb_scroll.set)
        sb_scroll.pack(side="right", fill="y")
        sb_canvas.pack(side="left", fill="both", expand=True)

        self.sidebar_inner = tk.Frame(sb_canvas, bg=BG_SIDEBAR)
        sb_canvas.create_window((0, 0), window=self.sidebar_inner, anchor="nw")
        self.sidebar_inner.bind(
            "<Configure>",
            lambda e: sb_canvas.configure(
                scrollregion=sb_canvas.bbox("all"))
        )

        self.sidebar_items = {}
        for sec in self.sections_list:
            item = SidebarItem(self.sidebar_inner, sec, self)
            item.pack(fill="x")
            self.sidebar_items[sec["id"]] = item

        # right panel
        right = tk.Frame(body, bg=BG_PANEL)
        right.pack(side="left", fill="both", expand=True)

        # section header
        sec_header = tk.Frame(right, bg=BG_HEADER)
        sec_header.pack(fill="x")
        self.section_title_var = tk.StringVar(value="")
        make_label(sec_header, fg=ACCENT2, bg=BG_HEADER,
                   font=("Courier New", 14, "bold"),
                   textvariable=self.section_title_var
                   ).pack(side="left", padx=14, pady=6)
        self.section_count_var = tk.StringVar(value="")
        make_label(sec_header, fg=MUTED, bg=BG_HEADER, font=FONT_TINY,
                   textvariable=self.section_count_var
                   ).pack(side="left", pady=6)

        # search bar
        search_bar = tk.Frame(right, bg=BG_PATHBAR)
        search_bar.pack(fill="x", padx=10, pady=(6, 0))
        make_label(search_bar, text="Search:", fg=TEXT_DIM, bg=BG_PATHBAR,
                   font=FONT_TINY).pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_bar, textvariable=self.search_var,
            font=FONT_SMALL, fg=ACCENT2, bg="#1a1a1a",
            insertbackground=ACCENT2,
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground=BORDER,
            width=30
        )
        self.search_entry.pack(side="left", ipady=3)
        self.search_var.trace_add("write", lambda *_: self._on_search())
        make_button(search_bar, "X", self._clear_search,
                    fg=MUTED, bg="#1a1a1a", active_bg="#2a2a2a",
                    font=FONT_TINY, width=2
                    ).pack(side="left", padx=4)

        # search results frame (hidden by default) — with scrollable canvas
        self.search_results_outer = tk.Frame(right, bg="#0d0d1a",
                                             highlightthickness=1,
                                             highlightbackground="#2a2a5a")
        self.search_results_canvas = tk.Canvas(self.search_results_outer,
                                               bg="#0d0d1a", highlightthickness=0,
                                               height=180)
        sr_scroll = tk.Scrollbar(self.search_results_outer, orient="vertical",
                                 command=self.search_results_canvas.yview)
        self.search_results_canvas.configure(yscrollcommand=sr_scroll.set)
        sr_scroll.pack(side="right", fill="y")
        self.search_results_canvas.pack(side="left", fill="both", expand=True)

        self.search_results_frame = tk.Frame(self.search_results_canvas, bg="#0d0d1a")
        self._sr_win = self.search_results_canvas.create_window(
            (0, 0), window=self.search_results_frame, anchor="nw"
        )
        self.search_results_frame.bind(
            "<Configure>",
            lambda e: self.search_results_canvas.configure(
                scrollregion=self.search_results_canvas.bbox("all"))
        )

        codes_outer = tk.Frame(right, bg=BG_PANEL)
        codes_outer.pack(fill="both", expand=True, padx=10, pady=(8, 0))

        self.codes_canvas = tk.Canvas(codes_outer, bg=BG_PANEL,
                                      highlightthickness=0)
        codes_scroll = tk.Scrollbar(codes_outer, orient="vertical",
                                    command=self.codes_canvas.yview)
        self.codes_canvas.configure(yscrollcommand=codes_scroll.set)
        codes_scroll.pack(side="right", fill="y")
        self.codes_canvas.pack(side="left", fill="both", expand=True)

        self.codes_inner = tk.Frame(self.codes_canvas, bg=BG_PANEL)
        self._codes_win = self.codes_canvas.create_window(
            (0, 0), window=self.codes_inner, anchor="nw"
        )
        self.codes_inner.bind(
            "<Configure>",
            lambda e: self.codes_canvas.configure(
                scrollregion=self.codes_canvas.bbox("all"))
        )
        self.codes_canvas.bind(
            "<Configure>",
            lambda e: self.codes_canvas.itemconfig(
                self._codes_win, width=e.width)
        )

        # smart mousewheel: scroll whichever pane the cursor is over
        def _on_mousewheel(e):
            x, y = e.x_root, e.y_root
            try:
                sr = self.search_results_canvas
                if self.search_results_outer.winfo_ismapped():
                    sx, sy = sr.winfo_rootx(), sr.winfo_rooty()
                    if sx <= x <= sx + sr.winfo_width() and sy <= y <= sy + sr.winfo_height():
                        sr.yview_scroll(int(-1 * (e.delta / 120)), "units")
                        return
            except Exception:
                pass
            self.codes_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        self.bind_all("<MouseWheel>", _on_mousewheel)

        # Apply Selected bar
        apply_bar = tk.Frame(right, bg=BG_APPLY,
                             highlightthickness=1,
                             highlightbackground="#2a4a2a")
        apply_bar.pack(fill="x", padx=10, pady=6)

        self.selected_count_var = tk.StringVar(value="0 selected")
        make_label(apply_bar, fg=MUTED, bg=BG_APPLY, font=FONT_TINY,
                   textvariable=self.selected_count_var
                   ).pack(side="left", padx=10, pady=6)

        make_button(apply_bar, "Select All", self._select_all,
                    fg=ACCENT, bg="#2a2a0a", active_bg="#3a3a1a", width=10
                    ).pack(side="left", padx=4, pady=4)
        make_button(apply_bar, "Clear", self._clear_selection,
                    fg=MUTED, bg="#1a1a1a", active_bg="#2a2a2a", width=8
                    ).pack(side="left", padx=4, pady=4)
        self.apply_btn = make_button(
            apply_bar, "Apply Selected", self._apply_selected,
            fg=GREEN, bg="#1a3a1a", active_bg="#2a5a2a", width=14
        )
        self.apply_btn.pack(side="right", padx=10, pady=4)

        # status bar
        statusbar = tk.Frame(self, bg=BG_STATUS, height=24)
        statusbar.pack(fill="x")
        statusbar.pack_propagate(False)

        self.status_applied_var  = tk.StringVar(value="Applied: 0")
        self.status_detected_var = tk.StringVar(value="Detected: 0")
        self.status_exe_var      = tk.StringVar(value="")
        self.status_total_var    = tk.StringVar(value="Total codes: 0")

        make_label(statusbar, fg=MUTED, bg=BG_STATUS, font=FONT_TINY,
                   textvariable=self.status_applied_var
                   ).pack(side="left", padx=12)
        make_label(statusbar, fg=MUTED, bg=BG_STATUS, font=FONT_TINY,
                   textvariable=self.status_detected_var
                   ).pack(side="left", padx=8)
        make_label(statusbar, fg=GREEN, bg=BG_STATUS, font=FONT_TINY,
                   textvariable=self.status_exe_var
                   ).pack(side="left", padx=8)
        make_label(statusbar, fg=MUTED, bg=BG_STATUS, font=FONT_TINY,
                   textvariable=self.status_total_var
                   ).pack(side="right", padx=12)

        self.code_rows = {}

    # ── logic ─────────────────────────────────────────────────────────────────

    # ── Best Settings preset ─────────────────────────────────────────────────
    BEST_SETTINGS = [
        "pointer_edit",
        "sanity_check",
        "aev_type6",
        "aev_fse",
        "aev_ese",
        "aev_auto_door",
        "aev_cam",
        "aev_checkpoint",
        "aev_chain",
        "aev_osd",
        "aev_auto_type5",
        "aev_option",
        "aev_ita",
        "aev_ear",
        "aev_timer",
        "etm_lever",
        "spawn_enemies",
        "em_ita_preload",
        "rsert_order",
        "loot_no_disappear",
        "u3_esl",
        "regen_esl",
        "merchant_init",
        "em_incompat_fix",
        "fix_r100_crash",
        "fix_r101_disappear",
        "grey_screen_fix",
    ]

    def _apply_best_settings(self):
        exe = self.exe_path.get().strip()
        if not exe or not os.path.isfile(exe):
            messagebox.showerror("Error", "Please select a valid bio4.exe first.")
            return
        if not self.scanned:
            messagebox.showerror("Error", "Please Scan the EXE first.")
            return

        # Build queue in exact order, skip already applied
        queue = [cid for cid in self.BEST_SETTINGS
                 if not self.applied.get(cid, False)]

        if not queue:
            messagebox.showinfo("Best Settings", "All recommended codes are already applied.")
            return

        names = "\n".join("  - " + self.code_by_id.get(c, {}).get("name", c)
                          for c in queue)
        if not messagebox.askyesno("Best Settings",
                                   "Apply the following codes in order?\n\n" + names):
            return

        # Apply one by one in exact order to respect dependencies
        success, failed = [], []
        for cid in queue:
            ok, msg = apply_patch(exe, cid, self.codes_data)
            if ok:
                self.applied[cid] = True
                success.append(cid)
            else:
                failed.append((cid, msg))
                # stop on first failure — later codes may depend on this one
                break

        summary = "Applied " + str(len(success)) + " code(s) successfully."
        if failed:
            summary += "\n\nStopped at:\n"
            for cid, err in failed:
                summary += "- " + self.code_by_id.get(cid, {}).get("name", cid)
                summary += "\n  " + err + "\n"
            messagebox.showwarning("Done with errors", summary)
        else:
            messagebox.showinfo("[+] Done", summary)

        self._after_state_change()

    def _open_settings(self):
        global CURRENT_LANG
        dlg = tk.Toplevel(self)
        dlg.title("Settings")
        dlg.geometry("320x530")
        dlg.resizable(False, False)
        dlg.configure(bg="#111")
        dlg.grab_set()

        make_label(dlg, "Language / اللغة",
                   fg=ACCENT2, bg="#111", font=FONT_NORMAL
                   ).pack(pady=(18, 10))

        lang_var = tk.StringVar(value=CURRENT_LANG)
        btn_frame = tk.Frame(dlg, bg="#111")
        btn_frame.pack()

        def _make_lang_btn(text, val):
            def cmd():
                lang_var.set(val)
            b = tk.Radiobutton(
                btn_frame, text=text, variable=lang_var, value=val,
                font=FONT_SMALL, fg=TEXT_MAIN, bg="#111",
                activebackground="#111", selectcolor="#1a1a1a",
                relief="flat", cursor="hand2", command=cmd
            )
            b.pack(side="left", padx=16)

        _make_lang_btn("العربية", "ar")
        _make_lang_btn("English", "en")

        def apply_lang():
            global CURRENT_LANG
            CURRENT_LANG = lang_var.get()
            dlg.destroy()
            self._reload_ui()

        make_button(dlg, "Apply Language", apply_lang,
                    fg=GREEN, bg="#1a2a0a", active_bg="#2a4a1a", width=14
                    ).pack(pady=10)

        # separator
        tk.Frame(dlg, bg="#333", height=1).pack(fill="x", padx=20, pady=6)

        # Profiles
        make_label(dlg, "Profiles",
                   fg=ACCENT2, bg="#111", font=FONT_SMALL
                   ).pack(pady=(4, 6))

        prof_row = tk.Frame(dlg, bg="#111")
        prof_row.pack()
        make_button(prof_row, "New Profile", lambda: [dlg.destroy(), self._new_profile()],
                    fg=ACCENT, bg="#2a2a0a", active_bg="#3a3a1a", width=12
                    ).pack(side="left", padx=6)
        make_button(prof_row, "Load Profile", lambda: [dlg.destroy(), self._load_profile()],
                    fg=GREEN, bg="#1a2a0a", active_bg="#2a4a1a", width=12
                    ).pack(side="left", padx=6)

        # separator
        tk.Frame(dlg, bg="#333", height=1).pack(fill="x", padx=20, pady=6)

        # Add New Code
        make_label(dlg, "Custom Codes",
                   fg=ACCENT2, bg="#111", font=FONT_SMALL
                   ).pack(pady=(4, 6))
        make_button(dlg, "Add New Code", lambda: [dlg.destroy(), self._add_new_code()],
                    fg=ACCENT2, bg="#1a1a2a", active_bg="#2a2a3a", width=14
                    ).pack(pady=(0, 6))

        # separator
        tk.Frame(dlg, bg="#333", height=1).pack(fill="x", padx=20, pady=6)

        # EXE Analysis
        make_label(dlg,
                   "EXE Analysis" if CURRENT_LANG == "en" else "تحليل EXE",
                   fg=ACCENT2, bg="#111", font=FONT_SMALL
                   ).pack(pady=(4, 6))

        cmp_row = tk.Frame(dlg, bg="#111")
        cmp_row.pack()
        make_button(cmp_row, "Compare Two EXEs",
                    lambda: [dlg.destroy(), self._compare_two_exes()],
                    fg=ACCENT, bg="#2a2a0a", active_bg="#3a3a1a", width=16
                    ).pack(side="left", padx=4)
        make_button(cmp_row, "Compare with Original",
                    lambda: [dlg.destroy(), self._compare_with_original()],
                    fg="#60c8ff", bg="#0a1a2a", active_bg="#1a2a3a", width=18
                    ).pack(side="left", padx=4)

        # separator
        tk.Frame(dlg, bg="#333", height=1).pack(fill="x", padx=20, pady=6)

        # Reset All
        make_label(dlg,
                   "Reset All Codes" if CURRENT_LANG == "en" else "إعادة تعيين كل الأكواد",
                   fg="#ff6060", bg="#111", font=FONT_SMALL
                   ).pack(pady=(4, 6))
        make_button(dlg,
                    "Reset All" if CURRENT_LANG == "en" else "إعادة تعيين",
                    lambda: [dlg.destroy(), self._reset_all_codes()],
                    fg="#ff6060", bg="#2a0a0a", active_bg="#3a1010", width=14
                    ).pack(pady=(0, 10))

    # ── EXE Comparison ────────────────────────────────────────────────────────

    def _show_report(self, title, report):
        """Show report in a scrollable window and offer to save."""
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.geometry("700x500")
        dlg.configure(bg="#111")

        txt_frame = tk.Frame(dlg, bg="#111")
        txt_frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        txt = tk.Text(txt_frame, font=("Courier New", 9),
                      fg="#c8c8c8", bg="#0d0d0d",
                      relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=BORDER,
                      wrap="none")
        sc_y = tk.Scrollbar(txt_frame, orient="vertical", command=txt.yview)
        sc_x = tk.Scrollbar(dlg, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)
        sc_y.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        sc_x.pack(fill="x", padx=10, pady=(0, 4))

        txt.insert("1.0", report)
        txt.configure(state="disabled")

        btn_row = tk.Frame(dlg, bg="#111")
        btn_row.pack(pady=6)

        def save_report():
            from tkinter import filedialog as fd
            path = fd.asksaveasfilename(
                title="Save Report",
                defaultextension=".txt",
                filetypes=[("Text file", "*.txt"), ("All files", "*.*")]
            )
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(report)
                messagebox.showinfo("Saved", "Report saved:\n" + path)

        make_button(btn_row, "Save Report", save_report,
                    fg=ACCENT, bg="#2a2a1a", active_bg="#3a3a2a", width=12
                    ).pack(side="left", padx=8)
        make_button(btn_row, "Close", dlg.destroy,
                    fg=MUTED, bg="#1a1a1a", active_bg="#2a2a2a", width=8
                    ).pack(side="left", padx=4)

    def _scan_codes_in_file(self, path):
        """Run scan_exe on a given path and return {code_id: bool}."""
        return scan_exe(path, self.codes_info, self.codes_data)

    def _build_codes_report(self, results_a, results_b, label_a, label_b):
        """Compare two scan results and build a readable report."""
        lines = []
        lines.append("=" * 60)
        lines.append("  " + label_a + "  vs  " + label_b)
        lines.append("=" * 60)

        only_a, only_b, both_on, both_off = [], [], [], []

        all_ids = sorted(set(list(results_a.keys()) + list(results_b.keys())))
        for cid in all_ids:
            a = results_a.get(cid, False)
            b = results_b.get(cid, False)
            code = self.code_by_id.get(cid, {})
            name = code.get("name_en" if CURRENT_LANG == "en" else "name", cid)
            if a and not b:
                only_a.append(name)
            elif b and not a:
                only_b.append(name)
            elif a and b:
                both_on.append(name)
            else:
                both_off.append(name)

        if only_a:
            lines.append("\n[ON in " + label_a + " only]  (" + str(len(only_a)) + " codes)")
            for n in only_a:
                lines.append("  + " + n)

        if only_b:
            lines.append("\n[ON in " + label_b + " only]  (" + str(len(only_b)) + " codes)")
            for n in only_b:
                lines.append("  + " + n)

        if both_on:
            lines.append("\n[ON in both]  (" + str(len(both_on)) + " codes)")
            for n in both_on:
                lines.append("  = " + n)

        lines.append("\n[OFF in both]  (" + str(len(both_off)) + " codes)")
        for n in both_off:
            lines.append("  - " + n)

        lines.append("\n" + "=" * 60)
        lines.append(
            "Total codes: " + str(len(all_ids)) +
            "  |  " + label_a + " applied: " + str(sum(results_a.values())) +
            "  |  " + label_b + " applied: " + str(sum(results_b.values()))
        )
        return "\n".join(lines)

    def _compare_two_exes(self):
        dlg = tk.Toplevel(self)
        dlg.title("Compare Two EXEs")
        dlg.geometry("480x200")
        dlg.resizable(False, False)
        dlg.configure(bg="#111")
        dlg.grab_set()

        def pick(var):
            path = filedialog.askopenfilename(
                title="Select EXE",
                filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
            )
            if path:
                var.set(path)

        var_a = tk.StringVar(value=self.exe_path.get())
        var_b = tk.StringVar()

        for label, var in [("EXE  A:", var_a), ("EXE  B:", var_b)]:
            row = tk.Frame(dlg, bg="#111")
            row.pack(fill="x", padx=16, pady=6)
            make_label(row, label, fg=TEXT_DIM, bg="#111",
                       font=FONT_SMALL, width=7).pack(side="left")
            tk.Entry(row, textvariable=var, font=FONT_SMALL,
                     fg=ACCENT2, bg="#1a1a1a", insertbackground=ACCENT2,
                     relief="flat", bd=0,
                     highlightthickness=1, highlightbackground=BORDER,
                     width=36).pack(side="left", ipady=2)
            make_button(row, "...", lambda v=var: pick(v),
                        fg=ACCENT, bg="#2a2a1a", active_bg="#3a3a2a",
                        font=FONT_TINY, width=3
                        ).pack(side="left", padx=4)

        def run():
            a, b = var_a.get().strip(), var_b.get().strip()
            if not a or not os.path.isfile(a):
                messagebox.showerror("Error", "Invalid EXE A path."); return
            if not b or not os.path.isfile(b):
                messagebox.showerror("Error", "Invalid EXE B path."); return
            dlg.destroy()
            res_a = self._scan_codes_in_file(a)
            res_b = self._scan_codes_in_file(b)
            report = self._build_codes_report(
                res_a, res_b,
                os.path.basename(a),
                os.path.basename(b)
            )
            self._show_report(
                "Compare: " + os.path.basename(a) + " vs " + os.path.basename(b),
                report
            )

        make_button(dlg, "Compare", run,
                    fg=GREEN, bg="#1a2a0a", active_bg="#2a4a1a", width=12
                    ).pack(pady=12)

    def _compare_with_original(self):
        exe = self.exe_path.get().strip()
        if not exe or not os.path.isfile(exe):
            messagebox.showerror("Error",
                "Please select a valid bio4.exe first."
                if CURRENT_LANG == "en" else
                "حط مسار bio4.exe أول.")
            return
        if not os.path.isfile(ORIG_FILE):
            messagebox.showerror("Error",
                "bio4_original.exe not found in the_codes/ folder."
                if CURRENT_LANG == "en" else
                "ما لقيت bio4_original.exe في مجلد the_codes/.")
            return
        res_orig = self._scan_codes_in_file(ORIG_FILE)
        res_exe  = self._scan_codes_in_file(exe)
        report = self._build_codes_report(
            res_orig, res_exe,
            "bio4_original.exe",
            os.path.basename(exe)
        )
        self._show_report(
            "Compare: Original vs " + os.path.basename(exe),
            report
        )

    def _reset_all_codes(self):
        confirm_msg = (
            "Are you sure you want to revert ALL applied codes?\n\n"
            "This will restore all patched bytes in bio4.exe.\n"
            "Make sure bio4_original.exe is in the_codes/ folder."
            if CURRENT_LANG == "en" else
            "هل أنت متأكد أنك تبي تشيل كل الأكواد؟\n\n"
            "هذا يرجع كل البايتات المعدلة في bio4.exe.\n"
            "تأكد أن bio4_original.exe موجود في مجلد the_codes/."
        )
        if not messagebox.askyesno(
            "Reset All" if CURRENT_LANG == "en" else "إعادة تعيين",
            confirm_msg
        ):
            return

        exe = self.exe_path.get().strip()
        if not exe or not os.path.isfile(exe):
            messagebox.showerror("Error", "Please select a valid bio4.exe first.")
            return

        applied_ids = [cid for cid, v in self.applied.items() if v]
        if not applied_ids:
            messagebox.showinfo(
                "Reset All" if CURRENT_LANG == "en" else "إعادة تعيين",
                "No codes are currently applied." if CURRENT_LANG == "en"
                else "ما في أكواد مفعّلة حالياً."
            )
            return

        success, failed = [], []
        for cid in applied_ids:
            ok, msg, _ = revert_patch(exe, ORIG_FILE, cid, self.codes_data)
            if ok:
                self.applied[cid] = False
                self.detected[cid] = False
                write_log("REVERTED (reset all)", self.code_by_id.get(cid, {}).get("name", cid), exe)
                success.append(cid)
            else:
                failed.append((cid, msg))

        summary = (
            "Reverted " + str(len(success)) + " code(s)."
            if CURRENT_LANG == "en" else
            "تم إزالة " + str(len(success)) + " كود."
        )
        if failed:
            summary += "\n\nFailed:\n"
            for cid, err in failed:
                summary += "- " + self.code_by_id.get(cid, {}).get("name", cid) + "\n"
            messagebox.showwarning("Done with errors", summary)
        else:
            messagebox.showinfo("[+] Done", summary)

        self._after_state_change()

    def _reload_ui(self):
        """Rebuild entire UI with new language."""
        # Save state
        exe = self.exe_path.get()
        sec = self.active_section

        # Destroy all children
        for w in self.winfo_children():
            w.destroy()

        # Reset widget refs
        self.code_rows = {}
        self.sidebar_items = {}

        # Rebuild
        self._build_ui()

        # Restore state
        self.exe_path.set(exe)
        if self.scanned:
            n_det = sum(1 for v in self.detected.values() if v)
            orig_status = "  |  [orig: OK]" if os.path.isfile(ORIG_FILE) else "  |  [orig: missing]"
            self.scan_status_var.set("Scanned -- " + str(n_det) + " codes detected" + orig_status)
            self.notice.pack_forget()
            self._update_statusbar()

        if sec:
            self.select_section(sec)
        else:
            self.select_section(self.sections_list[0]["id"])

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select bio4.exe",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
        )
        if path:
            self.exe_path.set(path)
            self._make_backup(path)

    def _make_backup(self, exe_path):
        """Create BIO4_BACKUP.EXE next to bio4.exe if not already exists."""
        import shutil
        backup = os.path.join(os.path.dirname(exe_path), "BIO4_BACKUP.EXE")
        if not os.path.isfile(backup):
            try:
                shutil.copy2(exe_path, backup)
                messagebox.showinfo(
                    "Backup Created",
                    "Backup created successfully:\n" + backup
                )
            except Exception as e:
                messagebox.showwarning(
                    "Backup Failed",
                    "Could not create backup:\n" + str(e)
                )
        # also check path entry manual edits on scan

    def _scan(self):
        path = self.exe_path.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showerror("Error", "Please select a valid bio4.exe file.")
            return

        # make backup if not exists
        self._make_backup(path)

        self.scan_btn.configure(text="Scanning...", state="disabled")
        self.update_idletasks()

        # reset state completely — fresh scan
        self.applied  = {}
        self.detected = {}

        self.detected = scan_exe(path, self.codes_info, self.codes_data)
        for cid, found in self.detected.items():
            if found:
                self.applied[cid] = True

        self.scanned = True
        n_det = sum(1 for v in self.detected.values() if v)
        self.scan_btn.configure(text="Re-Scan", state="normal")
        orig_status = "  |  [orig: OK]" if os.path.isfile(ORIG_FILE) else "  |  [orig: missing - revert disabled]"
        self.scan_status_var.set("Scanned -- " + str(n_det) + " codes detected" + orig_status)
        self.notice.pack_forget()
        self._after_state_change()

    def select_section(self, section_id):
        for sid, item in self.sidebar_items.items():
            item.set_active(sid == section_id)
        self.active_section = section_id

        sec = next((s for s in self.sections_list if s["id"] == section_id), None)
        if sec:
            self.section_title_var.set(sec["label"])

        for w in self.codes_inner.winfo_children():
            w.destroy()
        self.code_rows.clear()

        codes = self.codes_by_section.get(section_id, [])
        self.section_count_var.set("  " + str(len(codes)) + " codes")

        if not codes:
            make_label(self.codes_inner,
                       "-- No codes in this section yet --",
                       fg=MUTED, bg=BG_PANEL, font=FONT_SMALL
                       ).pack(pady=24)
            self._update_apply_bar()
            return

        for code in codes:
            row = CodeRow(self.codes_inner, code, self)
            row.pack(fill="x", pady=2)
            self.code_rows[code["id"]] = row
            self._refresh_row(code["id"])

        self.codes_canvas.yview_moveto(0)
        self._update_apply_bar()

    def _is_unlocked(self, code_id):
        if not self.scanned:
            return False
        code = self.code_by_id.get(code_id, {})
        for dep in code.get("requires", []):
            if not (self.applied.get(dep) or self.detected.get(dep)):
                return False
        return True

    def _get_missing_requires(self, code_id):
        """Return list of (dep_id, dep_name, section_label) for unmet requires."""
        code = self.code_by_id.get(code_id, {})
        missing = []
        sec_map = {s["id"]: s for s in self.sections_list}
        for dep in code.get("requires", []):
            if not (self.applied.get(dep) or self.detected.get(dep)):
                dep_code = self.code_by_id.get(dep, {})
                dep_name = dep_code.get("name_en" if CURRENT_LANG == "en" else "name", dep)
                dep_sec  = dep_code.get("section", "")
                sec_obj  = sec_map.get(dep_sec, {})
                sec_label = sec_obj.get("label_en" if CURRENT_LANG == "en" else "label", dep_sec)
                missing.append((dep, dep_name, sec_label))
        return missing

    def _get_dependents(self, code_id):
        """Return all applied codes that directly or transitively require code_id."""
        dependents = []
        for code in self.all_codes:
            cid = code["id"]
            if cid == code_id:
                continue
            if not self.applied.get(cid, False):
                continue
            # check if code_id is in transitive requires
            if code_id in self._transitive_requires(cid):
                dependents.append(cid)
        return dependents

    def _transitive_requires(self, cid, visited=None):
        if visited is None:
            visited = set()
        if cid in visited:
            return set()
        visited.add(cid)
        direct = set(self.code_by_id.get(cid, {}).get("requires", []))
        result = set(direct)
        for dep in direct:
            result |= self._transitive_requires(dep, visited)
        return result

    def handle_toggle(self, code_id):
        if not self.scanned:
            messagebox.showinfo(
                "Scan Required" if CURRENT_LANG == "en" else "لازم تسوي Scan",
                "Please select bio4.exe and press Scan EXE first."
                if CURRENT_LANG == "en" else
                "حط مسار bio4.exe واضغط Scan EXE أول."
            )
            return

        if not self._is_unlocked(code_id):
            missing = self._get_missing_requires(code_id)
            if missing:
                msg = ("You need to enable the following codes first:\n\n"
                       if CURRENT_LANG == "en" else
                       "لازم تشغل الأكواد التالية أول:\n\n")
                for dep_id, dep_name, sec_label in missing:
                    msg += "  - " + dep_name + "\n"
                    msg += ("    (Found in: " + sec_label + ")\n"
                            if CURRENT_LANG == "en" else
                            "    (تجده في قسم: " + sec_label + ")\n")
                messagebox.showwarning(
                    "Code Locked" if CURRENT_LANG == "en" else "الكود مقفل",
                    msg
                )
            return
        code = self.code_by_id.get(code_id, {})

        if self.applied.get(code_id, False):
            # revert
            exe = self.exe_path.get().strip()
            if not exe or not os.path.isfile(exe):
                messagebox.showerror("Error", "EXE path is invalid.")
                return

            if is_game_running(exe):
                messagebox.showerror(
                    "Game is Running" if CURRENT_LANG == "en" else "اللعبة شغالة",
                    "Please close the game before reverting codes."
                    if CURRENT_LANG == "en" else
                    "طفي اللعبة أول عشان تقدر تشيل الكود."
                )
                return

            # check if code has offset patches requiring original
            data = self.codes_data.get(code_id, {})
            if "variants" in data:
                all_patches = []
                for v in data["variants"].values():
                    all_patches += v.get("patches", [])
            else:
                all_patches = data.get("patches", [])

            needs_orig = any(p["type"] == "offset_paste"
                             for p in all_patches)

            if needs_orig and not os.path.isfile(ORIG_FILE):
                messagebox.showerror(
                    "Cannot Revert",
                    "This code has offset-based patches.\n"
                    "To revert it, place the original bio4.exe in:\n\n"
                    "the_codes/bio4_original.exe"
                )
                return

            ok, msg, skipped = revert_patch(exe, ORIG_FILE, code_id, self.codes_data)
            if ok:
                self.applied[code_id] = False
                self.detected[code_id] = False
                write_log("REVERTED", self.code_by_id.get(code_id, {}).get("name", code_id), exe)

                # cascade: revert all applied codes that depend on this one
                dependents = self._get_dependents(code_id)
                if dependents:
                    dep_names = "\n".join(
                        "  - " + self.code_by_id.get(d, {}).get(
                            "name_en" if CURRENT_LANG == "en" else "name", d)
                        for d in dependents
                    )
                    title = "Cascade Revert" if CURRENT_LANG == "en" else "إيقاف الأكواد التابعة"
                    msg_cascade = (
                        "The following codes depend on this one.\n"
                        "Turn them OFF too?\n\n" + dep_names
                    ) if CURRENT_LANG == "en" else (
                        "الأكواد التالية تعتمد على هذا الكود.\n"
                        "تطفيها كذلك؟\n\n" + dep_names
                    )
                    if messagebox.askyesno(title, msg_cascade):
                        for dep in dependents:
                            ok2, _, _ = revert_patch(exe, ORIG_FILE, dep, self.codes_data)
                            if ok2:
                                self.applied[dep] = False
                                self.detected[dep] = False
                                write_log("REVERTED (cascade)",
                                          self.code_by_id.get(dep, {}).get("name", dep), exe)
                    # If No: leave dependents as applied=True in EXE
                    # _is_unlocked returns False so they show locked [L]
                    # but their toggle shows ON — user must re-enable base code first

                if skipped > 0:
                    messagebox.showinfo(
                        "Reverted",
                        "Code reverted.\n(" + str(skipped) + " patch(es) were already at original state)"
                    )
                self._after_state_change()
            else:
                messagebox.showerror("Revert Failed", msg)
            return

        if code.get("dialog") == "mod_expansion":
            self._dialog_mod_expansion(code_id)
            return
        if code.get("dialog") == "bgm_files":
            self._dialog_bgm_files(code_id)
            return
        if code.get("dialog") == "link_tweaks":
            self._dialog_link_tweaks(code_id)
            return
        self._do_apply(code_id)

    def _dialog_link_tweaks(self, code_id):
        """Dialog for link tweaks with EXE code."""
        # check if already applied (scan detects via offset 7212FC)
        # detect: bytes at 7212FC != 31 2E 30 2E 36 means ON
        exe = self.exe_path.get().strip()

        dlg = tk.Toplevel(self)
        dlg.title("Link Tweaks with EXE" if CURRENT_LANG == "en" else "ربط التويكس مع EXE")
        dlg.geometry("420x300")
        dlg.resizable(False, False)
        dlg.configure(bg="#111")
        dlg.grab_set()

        make_label(dlg,
                   "Link Tweaks with EXE" if CURRENT_LANG == "en" else "ربط التويكس مع EXE",
                   fg=ACCENT2, bg="#111", font=FONT_NORMAL
                   ).pack(pady=(16, 4))
        make_label(dlg,
                   "Enter a 5-character keyword (e.g. 3MKOO)"
                   if CURRENT_LANG == "en" else
                   "أدخل كلمة من 5 أحرف (مثال: 3MKOO)",
                   fg=MUTED, bg="#111", font=FONT_TINY
                   ).pack(pady=(0, 10))

        fields_frame = tk.Frame(dlg, bg="#111")
        fields_frame.pack(fill="x", padx=20)

        def add_row(label_text, default=""):
            row = tk.Frame(fields_frame, bg="#111")
            row.pack(fill="x", pady=3)
            make_label(row, label_text, fg=TEXT_DIM, bg="#111",
                       font=FONT_TINY, width=20, anchor="w"
                       ).pack(side="left")
            var = tk.StringVar(value=default)
            e = tk.Entry(row, textvariable=var,
                         font=FONT_SMALL, fg=ACCENT2, bg="#1a1a1a",
                         insertbackground=ACCENT2, relief="flat", bd=0,
                         highlightthickness=1, highlightbackground=BORDER,
                         width=24)
            e.pack(side="left", ipady=2)
            return var

        exe_var  = add_row("EXE path:", exe)
        word_var = add_row("Keyword (5 chars):", "")
        dll_var  = add_row("DLL path:", "")

        # word length validation
        def on_word_change(*_):
            w = word_var.get()
            if len(w) > 5:
                word_var.set(w[:5])

        word_var.trace_add("write", on_word_change)

        def do_apply():
            exe_path = exe_var.get().strip()
            word     = word_var.get().strip()
            dll_path = dll_var.get().strip()

            if not exe_path or not os.path.isfile(exe_path):
                messagebox.showerror("Error", "Invalid EXE path.")
                return
            if len(word) != 5:
                messagebox.showerror("Error",
                    "Keyword must be exactly 5 characters."
                    if CURRENT_LANG == "en" else
                    "الكلمة لازم تكون 5 أحرف بالضبط.")
                return

            # convert word to hex bytes
            word_bytes = word.encode("ascii").hex().upper()
            word_spaced = " ".join(word_bytes[i:i+2] for i in range(0, len(word_bytes), 2))

            # build patches
            patches = [
                {"type": "offset_replace", "offset": "7212FC", "bytes": word_spaced},
            ]
            if dll_path and os.path.isfile(dll_path):
                patches.append({"type": "offset_replace", "offset": "894054",
                                 "bytes": word_spaced})

            # apply directly
            try:
                with open(exe_path, "rb") as f:
                    exe_data = bytearray(f.read())
            except Exception as e:
                messagebox.showerror("Error", str(e))
                return

            backup = load_patch_backup()
            code_backup = {}
            for p in patches:
                target = exe_path if p["offset"] == "7212FC" else dll_path
                try:
                    with open(target, "r+b") as f:
                        off = int(p["offset"], 16)
                        data_b = bytes.fromhex(p["bytes"].replace(" ", ""))
                        f.seek(off)
                        orig_b = f.read(len(data_b))
                        code_backup[p["offset"]] = orig_b.hex().upper()
                        f.seek(off)
                        f.write(data_b)
                except Exception as e:
                    messagebox.showerror("Error", "Failed at offset " + p["offset"] + ":\n" + str(e))
                    return

            backup[code_id] = code_backup
            save_patch_backup(backup)
            self.applied[code_id] = True
            write_log("APPLIED", "Link Tweaks with EXE -- keyword: " + word, exe_path)
            dlg.destroy()
            messagebox.showinfo("[+] Applied",
                                "Tweaks linked with keyword: " + word
                                if CURRENT_LANG == "en" else
                                "تم ربط التويكس بالكلمة: " + word)
            self._after_state_change()

        make_button(dlg, "Apply" if CURRENT_LANG == "en" else "تطبيق",
                    do_apply, fg=GREEN, bg="#1a2a0a", active_bg="#2a4a1a", width=12
                    ).pack(pady=14)

    def _dialog_bgm_files(self, code_id):
        # ── Step 1: ask how many files ──
        dlg1 = tk.Toplevel(self)
        dlg1.title("Additional BGM Files")
        dlg1.geometry("340x160")
        dlg1.resizable(False, False)
        dlg1.configure(bg="#111")
        dlg1.grab_set()

        make_label(dlg1, "How many BGM files to add? (max 8)",
                   fg=ACCENT2, bg="#111", font=FONT_NORMAL
                   ).pack(pady=(18, 6))
        make_label(dlg1, "Each file = one XWB + one XSB pair",
                   fg=MUTED, bg="#111", font=FONT_TINY
                   ).pack()

        count_var = tk.IntVar(value=1)
        spin_frame = tk.Frame(dlg1, bg="#111")
        spin_frame.pack(pady=10)
        tk.Spinbox(
            spin_frame, from_=1, to=8,
            textvariable=count_var, width=5,
            font=FONT_NORMAL, fg=ACCENT2, bg="#1a1a1a",
            buttonbackground="#2a2a2a",
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground=BORDER
        ).pack(side="left", ipady=4)

        def next_step():
            n = count_var.get()
            dlg1.destroy()
            self._dialog_bgm_names(code_id, n)

        btn_row = tk.Frame(dlg1, bg="#111")
        btn_row.pack(pady=4)
        make_button(btn_row, "Next >>", next_step,
                    fg=GREEN, bg="#1a2a0a", active_bg="#2a4a1a", width=10
                    ).pack(side="left", padx=8)
        make_button(btn_row, "Cancel", dlg1.destroy,
                    fg=MUTED, bg="#1a1a1a", active_bg="#2a2a2a", width=8
                    ).pack(side="left", padx=4)

    def _dialog_bgm_names(self, code_id, count):
        MAX_NAME = 20   # BIO4\snd\ = 10 chars, name+ext ≤ 22 chars, total ≤ 32
        ENTRY_SIZE = 32 # bytes per entry (matches game expectation)
        BASE_PATH = "BIO4\\snd\\"

        dlg2 = tk.Toplevel(self)
        dlg2.title("BGM File Names")
        dlg2.geometry("420x" + str(80 + count * 56))
        dlg2.resizable(False, True)
        dlg2.configure(bg="#111")
        dlg2.grab_set()

        make_label(dlg2, "Enter file names (without path or extension):",
                   fg=ACCENT2, bg="#111", font=FONT_SMALL
                   ).pack(pady=(14, 4), padx=16, anchor="w")
        make_label(dlg2, "Example: 1234567   ->  BIO4\\snd\\1234567.xwb / .xsb",
                   fg=MUTED, bg="#111", font=FONT_TINY
                   ).pack(padx=16, anchor="w")

        entries = []
        for i in range(count):
            row = tk.Frame(dlg2, bg="#111")
            row.pack(fill="x", padx=16, pady=4)
            make_label(row, "File " + str(i + 1) + ":",
                       fg=TEXT_DIM, bg="#111", font=FONT_TINY, width=7
                       ).pack(side="left")
            var = tk.StringVar()
            tk.Entry(
                row, textvariable=var,
                font=FONT_SMALL, fg=ACCENT2, bg="#1a1a1a",
                insertbackground=ACCENT2,
                relief="flat", bd=0,
                highlightthickness=1, highlightbackground=BORDER,
                width=24
            ).pack(side="left", ipady=3)
            entries.append(var)

        def do_apply():
            # validate
            names = [v.get().strip() for v in entries]
            for i, name in enumerate(names):
                if not name:
                    messagebox.showerror("Error", "File " + str(i+1) + " name is empty.")
                    return
                full = BASE_PATH + name + ".xwb"
                if len(full) > ENTRY_SIZE - 1:   # -1 for null terminator
                    messagebox.showerror("Error",
                        "File " + str(i+1) + " name too long.\n"
                        "Max " + str(ENTRY_SIZE - 1 - len(BASE_PATH) - 4) + " characters.")
                    return

            # build the 32-byte entries: XWB then XSB for each file, packed together
            # layout: [xwb_entry_32][xsb_entry_32] per file, sequential
            payload = bytearray()
            for name in names:
                xwb = (BASE_PATH + name + ".xwb").encode("ascii")
                xsb = (BASE_PATH + name + ".xsb").encode("ascii")
                # pad each to ENTRY_SIZE bytes with nulls
                xwb_entry = xwb + b'\x00' * (ENTRY_SIZE - len(xwb))
                xsb_entry = xsb + b'\x00' * (ENTRY_SIZE - len(xsb))
                payload += xwb_entry + xsb_entry

            # patch the additional_bgm code normally first (the JMP patches)
            # then write the string table at 0x0078C200
            dlg2.destroy()

            exe = self.exe_path.get().strip()
            if not exe or not os.path.isfile(exe):
                messagebox.showerror("Error", "EXE path is invalid.")
                return

            # apply the code patches (JMP hooks) first
            ok, msg = apply_patch(exe, code_id, self.codes_data)
            if not ok:
                messagebox.showerror("Error", "Failed applying BGM patches:\n" + msg)
                return

            # now write the string table
            STRING_TABLE_OFFSET = 0x0078C200
            try:
                with open(exe, "r+b") as f:
                    f.seek(STRING_TABLE_OFFSET)
                    # clear the area first (8 files max * 2 entries * 32 bytes)
                    f.write(b'\x00' * (8 * 2 * ENTRY_SIZE))
                    f.seek(STRING_TABLE_OFFSET)
                    f.write(bytes(payload))
            except Exception as e:
                messagebox.showerror("Error", "Failed writing string table:\n" + str(e))
                return

            self.applied[code_id] = True
            self._refresh_all()
            self._update_statusbar()
            self._update_apply_bar()

            summary = "BGM files written:\n"
            for name in names:
                summary += "  " + BASE_PATH + name + ".xwb/.xsb\n"
            messagebox.showinfo("[+] Done", summary)

        btn_row = tk.Frame(dlg2, bg="#111")
        btn_row.pack(pady=8)
        make_button(btn_row, "Apply", do_apply,
                    fg=GREEN, bg="#1a2a0a", active_bg="#2a4a1a", width=10
                    ).pack(side="left", padx=8)
        make_button(btn_row, "Cancel", dlg2.destroy,
                    fg=MUTED, bg="#1a1a1a", active_bg="#2a2a2a", width=8
                    ).pack(side="left", padx=4)

    def _dialog_mod_expansion(self, code_id):
        dlg = tk.Toplevel(self)
        dlg.title("Enemy Spawn Persistence")
        dlg.geometry("380x180")
        dlg.resizable(False, False)
        dlg.configure(bg="#111")
        dlg.grab_set()

        make_label(dlg, fix_ar("هل انت مفعل EnableModExpansion؟"),
                   fg=ACCENT2, bg="#111", font=FONT_NORMAL
                   ).pack(pady=(20, 6))
        make_label(dlg, fix_ar("سيؤثر هاذا على الكود اللي راح ينحط في EXE"),
                   fg=MUTED, bg="#111", font=FONT_TINY
                   ).pack()

        btn_frame = tk.Frame(dlg, bg="#111")
        btn_frame.pack(pady=20)

        make_button(btn_frame, "[Y] Yes",
                    lambda: [dlg.destroy(),
                             self._do_apply(code_id, mod_expansion=True)],
                    fg=GREEN, bg="#1a2a0a", active_bg="#2a4a1a", width=9
                    ).pack(side="left", padx=8)
        make_button(btn_frame, "[N] No",
                    lambda: [dlg.destroy(),
                             self._do_apply(code_id, mod_expansion=False)],
                    fg=RED_SOFT, bg="#2a0a0a", active_bg="#4a1a1a", width=9
                    ).pack(side="left", padx=8)
        make_button(btn_frame, "Cancel", dlg.destroy,
                    fg=MUTED, bg="#1a1a1a", active_bg="#2a2a2a", width=9
                    ).pack(side="left", padx=8)

    def _do_apply(self, code_id, mod_expansion=None):
        exe = self.exe_path.get().strip()
        if not exe or not os.path.isfile(exe):
            messagebox.showerror("Error", "EXE path is invalid.")
            return
        if is_game_running(exe):
            messagebox.showerror(
                "Game is Running" if CURRENT_LANG == "en" else "اللعبة شغالة",
                "Please close the game before applying codes.\nClose bio4.exe and try again."
                if CURRENT_LANG == "en" else
                "طفي اللعبة أول عشان تقدر تفعل الكود.\nأغلق bio4.exe وحاول مرة ثانية."
            )
            return
        # handle mutual exclusion before applying
        self._handle_dll_mutex(code_id)
        ok, msg = apply_patch(exe, code_id, self.codes_data, mod_expansion)
        if ok:
            self.applied[code_id] = True
            write_log("APPLIED", self.code_by_id[code_id]["name"], exe)
            messagebox.showinfo(
                "[+] Applied",
                "Code applied:\n" + self.code_by_id[code_id]["name"]
            )
            self._after_state_change()
        else:
            messagebox.showerror("Error", "Failed:\n" + msg)

    # ── Apply Selected ────────────────────────────────────────────────────────

    def on_row_select_change(self):
        self._update_apply_bar()

    def _update_apply_bar(self):
        n = sum(1 for r in self.code_rows.values() if r.selected)
        self.selected_count_var.set(str(n) + " selected")

    def _select_all(self):
        for cid, row in self.code_rows.items():
            if self._is_unlocked(cid) and not self.applied.get(cid, False):
                row.sel_var.set(1)
                row.selected = True
        self._refresh_all()
        self._update_apply_bar()

    def _clear_selection(self):
        for row in self.code_rows.values():
            row.sel_var.set(0)
            row.selected = False
        self._refresh_all()
        self._update_apply_bar()

    def _apply_selected(self):
        exe = self.exe_path.get().strip()
        if not exe or not os.path.isfile(exe):
            messagebox.showerror("Error", "Please select a valid bio4.exe first.")
            return

        queue = [cid for cid, row in self.code_rows.items()
                 if row.selected and not self.applied.get(cid, False)]

        if not queue:
            messagebox.showinfo("Info", "No codes selected.")
            return

        needs_dialog = [c for c in queue
                        if self.code_by_id.get(c, {}).get("dialog") == "mod_expansion"]
        if needs_dialog:
            self._dialog_mod_expansion_batch(queue)
        else:
            self._run_apply_queue(queue, mod_expansion=None)

    def _dialog_mod_expansion_batch(self, full_queue):
        dlg = tk.Toplevel(self)
        dlg.title("Enemy Spawn Persistence")
        dlg.geometry("380x180")
        dlg.resizable(False, False)
        dlg.configure(bg="#111")
        dlg.grab_set()

        make_label(dlg, fix_ar("هل انت مفعل EnableModExpansion؟"),
                   fg=ACCENT2, bg="#111", font=FONT_NORMAL
                   ).pack(pady=(20, 6))
        make_label(dlg, fix_ar("سيؤثر هاذا على الكود اللي راح ينحط في EXE"),
                   fg=MUTED, bg="#111", font=FONT_TINY
                   ).pack()

        btn_frame = tk.Frame(dlg, bg="#111")
        btn_frame.pack(pady=20)

        make_button(btn_frame, "[Y] Yes",
                    lambda: [dlg.destroy(),
                             self._run_apply_queue(full_queue, mod_expansion=True)],
                    fg=GREEN, bg="#1a2a0a", active_bg="#2a4a1a", width=9
                    ).pack(side="left", padx=8)
        make_button(btn_frame, "[N] No",
                    lambda: [dlg.destroy(),
                             self._run_apply_queue(full_queue, mod_expansion=False)],
                    fg=RED_SOFT, bg="#2a0a0a", active_bg="#4a1a1a", width=9
                    ).pack(side="left", padx=8)
        make_button(btn_frame, "Cancel", dlg.destroy,
                    fg=MUTED, bg="#1a1a1a", active_bg="#2a2a2a", width=9
                    ).pack(side="left", padx=8)

    def _run_apply_queue(self, queue, mod_expansion=None):
        exe = self.exe_path.get().strip()
        success, failed = [], []

        for code_id in queue:
            self._handle_dll_mutex(code_id)
            me = mod_expansion if self.code_by_id.get(
                code_id, {}).get("dialog") == "mod_expansion" else None
            ok, msg = apply_patch(exe, code_id, self.codes_data, me)
            if ok:
                self.applied[code_id] = True
                write_log("APPLIED", self.code_by_id.get(code_id, {}).get("name", code_id), exe)
                success.append(code_id)
            else:
                failed.append((code_id, msg))

        summary = "Applied " + str(len(success)) + " code(s) successfully."
        if failed:
            summary += "\n\nFailed:\n"
            for cid, err in failed:
                summary += "- " + self.code_by_id[cid]["name"] + "\n  " + err + "\n"
            messagebox.showwarning("Done with errors", summary)
        else:
            messagebox.showinfo("[+] Done", summary)

        self._after_state_change()

    # ── refresh ───────────────────────────────────────────────────────────────

    def _refresh_row(self, code_id):
        row = self.code_rows.get(code_id)
        if not row:
            return
        row.refresh(
            applied  = self.applied.get(code_id, False),
            locked   = not self._is_unlocked(code_id),
            detected = self.detected.get(code_id, False)
        )

    def _refresh_all(self):
        """Refresh all visible rows in current section."""
        for cid in list(self.code_rows.keys()):
            self._refresh_row(cid)

    def _after_state_change(self):
        """
        Called after any apply/revert.
        Refreshes visible rows AND re-renders the current section
        so locked/unlocked states are always up to date without re-scan.
        """
        # Refresh visible rows first
        self._refresh_all()
        # Re-select current section to rebuild rows with fresh state
        if self.active_section:
            self.select_section(self.active_section)
        self._update_statusbar()
        self._update_apply_bar()

    # ── mutual exclusion: codes sharing same offsets ─────────────────────────
    # Format: code_id -> list of conflicting code_ids
    OFFSET_MUTEX = {
        # DLL apply codes share offset 156
        "apply_dll_qingsheng": ["apply_dll_raz0r"],
        "apply_dll_raz0r":     ["apply_dll_qingsheng"],
        # bodies disappear/no-disappear share same offsets
        "bodies_disappear":    ["bodies_no_disappear"],
        "bodies_no_disappear": ["bodies_disappear"],
        # verdugo versions share same find pattern + offset C2440
        "verdugo_no_teleport":       ["verdugo_no_teleport_raz0r"],
        "verdugo_no_teleport_raz0r": ["verdugo_no_teleport"],
        # saw: killable vs survive chainsaw share offset 3E4E3
        "saw_killable":     ["survive_chainsaw"],
        "survive_chainsaw": ["saw_killable"],
        # u3: esl vs form1 share offset 1034CA
        "u3_esl":       ["u3_form1_kill"],
        "u3_form1_kill": ["u3_esl"],
        # u3: form1 vs die_in_place share offset FE9C2
        "u3_form1_kill":  ["u3_die_in_place"],
        "u3_die_in_place": ["u3_form1_kill"],
        # xwb sideload vs em_xwb_xsb share offset 575487
        "xwb_sideload_r": ["em_xwb_xsb"],
        "em_xwb_xsb":     ["xwb_sideload_r"],
    }

    def _handle_dll_mutex(self, code_id):
        """Revert all conflicting codes before applying code_id."""
        conflicts = self.OFFSET_MUTEX.get(code_id, [])
        exe = self.exe_path.get().strip()
        if not exe or not os.path.isfile(exe):
            return
        for other in conflicts:
            if self.applied.get(other, False):
                ok, _, _ = revert_patch(exe, ORIG_FILE, other, self.codes_data)
                if ok:
                    self.applied[other] = False
                    self.detected[other] = False

    def _dialog_mod_expansion_batch_profile(self, queue, exe):
        """Called when profile queue contains enemy_persistence."""
        dlg = tk.Toplevel(self)
        dlg.title("Enemy Spawn Persistence")
        dlg.geometry("380x190")
        dlg.resizable(False, False)
        dlg.configure(bg="#111")
        dlg.grab_set()

        make_label(dlg,
                   "Is EnableModExpansion active?" if CURRENT_LANG == "en"
                   else fix_ar("هل انت مفعل EnableModExpansion؟"),
                   fg=ACCENT2, bg="#111", font=FONT_NORMAL
                   ).pack(pady=(20, 6))
        make_label(dlg,
                   "This affects the enemy_persistence code in the profile."
                   if CURRENT_LANG == "en"
                   else fix_ar("سيؤثر هاذا على كود enemy_persistence في البروفايل"),
                   fg=MUTED, bg="#111", font=FONT_TINY
                   ).pack()

        btn_frame = tk.Frame(dlg, bg="#111")
        btn_frame.pack(pady=20)

        def run(mod_exp):
            dlg.destroy()
            success, failed = [], []
            for cid in queue:
                self._handle_dll_mutex(cid)
                me = mod_exp if self.code_by_id.get(cid, {}).get("dialog") == "mod_expansion" else None
                ok, msg = apply_patch(exe, cid, self.codes_data, me)
                if ok:
                    self.applied[cid] = True
                    write_log("APPLIED (profile)", self.code_by_id.get(cid, {}).get("name", cid), exe)
                    success.append(cid)
                else:
                    failed.append((cid, msg))
                    break
            summary = "Applied " + str(len(success)) + " code(s)."
            if failed:
                summary += "\n\nStopped at:\n"
                for cid, err in failed:
                    summary += "- " + self.code_by_id.get(cid, {}).get("name", cid) + "\n  " + err + "\n"
                messagebox.showwarning("Done with errors", summary)
            else:
                messagebox.showinfo("[+] Done", summary)
            self._after_state_change()

        make_button(btn_frame, "[Y] Yes", lambda: run(True),
                    fg=GREEN, bg="#1a2a0a", active_bg="#2a4a1a", width=9
                    ).pack(side="left", padx=8)
        make_button(btn_frame, "[N] No", lambda: run(False),
                    fg=RED_SOFT, bg="#2a0a0a", active_bg="#4a1a1a", width=9
                    ).pack(side="left", padx=8)
        make_button(btn_frame, "Cancel", dlg.destroy,
                    fg=MUTED, bg="#1a1a1a", active_bg="#2a2a2a", width=9
                    ).pack(side="left", padx=8)

    def _update_statusbar(self):
        n_applied  = sum(1 for v in self.applied.values() if v)
        n_detected = sum(1 for v in self.detected.values() if v)
        n_total    = len(self.all_codes)
        self.status_applied_var.set(
            ("Applied: " if CURRENT_LANG == "en" else "مفعّل: ") + str(n_applied))
        self.status_detected_var.set(
            ("Detected: " if CURRENT_LANG == "en" else "مكتشف: ") + str(n_detected))
        self.status_exe_var.set(
            ("[OK] EXE Loaded" if CURRENT_LANG == "en" else "[OK] EXE محمّل")
            if self.scanned else "")
        self.status_total_var.set(
            ("Total codes: " if CURRENT_LANG == "en" else "إجمالي الأكواد: ") + str(n_total))

    # ── Search ────────────────────────────────────────────────────────────────

    def _on_search(self):
        query = self.search_var.get().strip().lower()
        # clear old results
        for w in self.search_results_frame.winfo_children():
            w.destroy()

        if not query:
            self.search_results_outer.pack_forget()
            return

        # find matching codes
        matches = []
        for code in self.all_codes:
            name    = code.get("name_en" if CURRENT_LANG == "en" else "name", "")
            desc    = code.get("desc_en" if CURRENT_LANG == "en" else "desc", "")
            if query in name.lower() or query in desc.lower():
                matches.append(code)

        if not matches:
            make_label(self.search_results_frame,
                       text="No results found" if CURRENT_LANG == "en" else "ما في نتائج",
                       fg=MUTED, bg="#0d0d1a", font=FONT_TINY
                       ).pack(padx=8, pady=4)
        else:
            for code in matches[:12]:  # max 12 results
                sec = next((s for s in self.sections_list if s["id"] == code["section"]), None)
                sec_label = sec.get("label_en" if CURRENT_LANG == "en" else "label", "") if sec else ""
                name = code.get("name_en" if CURRENT_LANG == "en" else "name", code["name"])

                row = tk.Frame(self.search_results_frame, bg="#0d0d1a",
                               cursor="hand2")
                row.pack(fill="x", padx=4, pady=1)

                make_label(row, text=name,
                           fg=ACCENT2, bg="#0d0d1a", font=FONT_TINY
                           ).pack(side="left", padx=6, pady=2)
                make_label(row, text="[" + sec_label + "]",
                           fg=MUTED, bg="#0d0d1a", font=FONT_TINY
                           ).pack(side="left")

                # click -> go to section and highlight
                def _goto(c=code):
                    self._clear_search()
                    self.select_section(c["section"])
                    # scroll to the row
                    self.after(100, lambda: self._scroll_to_code(c["id"]))

                row.bind("<Button-1>", lambda e, c=code: _goto(c))
                for child in row.winfo_children():
                    child.bind("<Button-1>", lambda e, c=code: _goto(c))

        self.search_results_outer.pack(fill="x", padx=10, pady=(0, 4))

    def _scroll_to_code(self, code_id):
        row = self.code_rows.get(code_id)
        if not row:
            return
        self.codes_canvas.update_idletasks()
        row.update_idletasks()
        # get row y position relative to codes_inner
        y = row.winfo_y()
        total = self.codes_inner.winfo_height()
        if total > 0:
            frac = y / total
            self.codes_canvas.yview_moveto(frac)

    def _clear_search(self):
        self.search_var.set("")
        self.search_results_outer.pack_forget()
        for w in self.search_results_frame.winfo_children():
            w.destroy()

    # ── Profiles ─────────────────────────────────────────────────────────────

    def _new_profile(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Profile")
        dlg.geometry("500x520")
        dlg.resizable(False, True)
        dlg.configure(bg="#111")
        dlg.grab_set()

        make_label(dlg, "Profile Name:",
                   fg=ACCENT2, bg="#111", font=FONT_NORMAL
                   ).pack(pady=(16, 4), padx=16, anchor="w")
        name_var = tk.StringVar()
        tk.Entry(dlg, textvariable=name_var,
                 font=FONT_SMALL, fg=ACCENT2, bg="#1a1a1a",
                 insertbackground=ACCENT2, relief="flat", bd=0,
                 highlightthickness=1, highlightbackground=BORDER,
                 width=40
                 ).pack(padx=16, ipady=3, anchor="w")

        make_label(dlg, "Select codes to include:",
                   fg=TEXT_DIM, bg="#111", font=FONT_SMALL
                   ).pack(pady=(12, 4), padx=16, anchor="w")

        # scrollable checklist
        list_outer = tk.Frame(dlg, bg="#111")
        list_outer.pack(fill="both", expand=True, padx=16)
        list_canvas = tk.Canvas(list_outer, bg="#1a1a1a",
                                highlightthickness=1,
                                highlightbackground=BORDER, height=300)
        list_scroll = tk.Scrollbar(list_outer, orient="vertical",
                                   command=list_canvas.yview)
        list_canvas.configure(yscrollcommand=list_scroll.set)
        list_scroll.pack(side="right", fill="y")
        list_canvas.pack(side="left", fill="both", expand=True)

        list_inner = tk.Frame(list_canvas, bg="#1a1a1a")
        list_canvas.create_window((0, 0), window=list_inner, anchor="nw")
        list_inner.bind("<Configure>",
                        lambda e: list_canvas.configure(
                            scrollregion=list_canvas.bbox("all")))

        chk_vars = {}
        for code in self.all_codes:
            var = tk.IntVar(value=0)
            name = code.get("name_en" if CURRENT_LANG == "en" else "name", code["name"])
            tk.Checkbutton(
                list_inner, text=name, variable=var,
                font=FONT_TINY, fg=TEXT_MAIN, bg="#1a1a1a",
                activebackground="#1a1a1a", selectcolor="#2a2a2a",
                anchor="w", relief="flat"
            ).pack(fill="x", padx=6, pady=1)
            chk_vars[code["id"]] = var

        def save_profile():
            pname = name_var.get().strip()
            if not pname:
                messagebox.showerror("Error", "Please enter a profile name.")
                return
            selected = [cid for cid, v in chk_vars.items() if v.get()]
            if not selected:
                messagebox.showerror("Error", "Select at least one code.")
                return
            os.makedirs(PROFILES_DIR, exist_ok=True)
            path = os.path.join(PROFILES_DIR, pname + ".json")
            profile = {
                "name": pname,
                "description": "",
                "codes": selected
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(profile, f, ensure_ascii=False, indent=2)
            dlg.destroy()
            messagebox.showinfo("[+] Saved",
                                "Profile saved:\n" + path)

        make_button(dlg, "Save Profile", save_profile,
                    fg=GREEN, bg="#1a2a0a", active_bg="#2a4a1a", width=14
                    ).pack(pady=10)

    def _load_profile(self):
        os.makedirs(PROFILES_DIR, exist_ok=True)
        files = [f for f in os.listdir(PROFILES_DIR) if f.endswith(".json")]
        if not files:
            messagebox.showinfo("Profiles",
                                "No profiles found in:\n" + PROFILES_DIR)
            return

        dlg = tk.Toplevel(self)
        dlg.title("Load Profile")
        dlg.geometry("360x300")
        dlg.resizable(False, True)
        dlg.configure(bg="#111")
        dlg.grab_set()

        make_label(dlg, "Select a profile:",
                   fg=ACCENT2, bg="#111", font=FONT_NORMAL
                   ).pack(pady=(16, 8))

        listbox = tk.Listbox(
            dlg, font=FONT_SMALL,
            fg=TEXT_MAIN, bg="#1a1a1a",
            selectbackground="#2a3a1a", selectforeground=GREEN,
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground=BORDER,
            height=10
        )
        for f in files:
            listbox.insert("end", f.replace(".json", ""))
        listbox.pack(fill="both", expand=True, padx=16, pady=4)

        def do_load():
            sel = listbox.curselection()
            if not sel:
                messagebox.showerror("Error", "Select a profile first.")
                return
            fname = files[sel[0]]
            path = os.path.join(PROFILES_DIR, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    profile = json.load(f)
            except Exception as e:
                messagebox.showerror("Error", "Failed to load profile:\n" + str(e))
                return

            dlg.destroy()

            exe = self.exe_path.get().strip()
            if not exe or not os.path.isfile(exe):
                messagebox.showerror("Error", "Please select a valid bio4.exe first.")
                return
            if not self.scanned:
                messagebox.showerror("Error", "Please Scan the EXE first.")
                return

            queue = [cid for cid in profile.get("codes", [])
                     if cid in self.code_by_id and not self.applied.get(cid, False)]
            if not queue:
                messagebox.showinfo("Profile", "All codes in this profile are already applied.")
                return

            names = "\n".join("  - " + self.code_by_id.get(c, {}).get("name", c)
                              for c in queue)
            if not messagebox.askyesno("Load Profile",
                                       "Apply codes from profile '" +
                                       profile.get("name", fname) + "'?\n\n" + names):
                return

            # check if queue has enemy_persistence (needs mod_expansion dialog)
            needs_dialog = [c for c in queue
                            if self.code_by_id.get(c, {}).get("dialog") == "mod_expansion"]
            if needs_dialog:
                self._dialog_mod_expansion_batch_profile(queue, exe)
                return

            # apply in order, stop on failure
            success, failed = [], []
            for cid in queue:
                self._handle_dll_mutex(cid)
                ok, msg = apply_patch(exe, cid, self.codes_data)
                if ok:
                    self.applied[cid] = True
                    write_log("APPLIED (profile)", self.code_by_id.get(cid, {}).get("name", cid), exe)
                    success.append(cid)
                else:
                    failed.append((cid, msg))
                    break

            summary = "Applied " + str(len(success)) + " code(s)."
            if failed:
                summary += "\n\nStopped at:\n"
                for cid, err in failed:
                    summary += "- " + self.code_by_id.get(cid, {}).get("name", cid) + "\n  " + err + "\n"
                messagebox.showwarning("Done with errors", summary)
            else:
                messagebox.showinfo("[+] Done", summary)

            self._after_state_change()

        btn_row = tk.Frame(dlg, bg="#111")
        btn_row.pack(pady=8)
        make_button(btn_row, "Load", do_load,
                    fg=GREEN, bg="#1a2a0a", active_bg="#2a4a1a", width=10
                    ).pack(side="left", padx=8)
        make_button(btn_row, "Cancel", dlg.destroy,
                    fg=MUTED, bg="#1a1a1a", active_bg="#2a2a2a", width=8
                    ).pack(side="left", padx=4)

    # ── Add New Code ──────────────────────────────────────────────────────────

    def _add_new_code(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add New Code")
        dlg.geometry("480x560")
        dlg.resizable(False, True)
        dlg.configure(bg="#111")
        dlg.grab_set()

        fields = {}

        def add_field(label, key, height=1):
            make_label(dlg, label, fg=TEXT_DIM, bg="#111", font=FONT_SMALL
                       ).pack(pady=(10, 2), padx=16, anchor="w")
            if height == 1:
                var = tk.StringVar()
                tk.Entry(dlg, textvariable=var,
                         font=FONT_SMALL, fg=ACCENT2, bg="#1a1a1a",
                         insertbackground=ACCENT2, relief="flat", bd=0,
                         highlightthickness=1, highlightbackground=BORDER,
                         width=52
                         ).pack(padx=16, ipady=3, anchor="w")
                fields[key] = var
            else:
                t = tk.Text(dlg, font=FONT_SMALL, fg=ACCENT2, bg="#1a1a1a",
                            insertbackground=ACCENT2, relief="flat", bd=0,
                            highlightthickness=1, highlightbackground=BORDER,
                            width=52, height=height)
                t.pack(padx=16, anchor="w")
                fields[key] = t

        # Section dropdown
        make_label(dlg, "Section:", fg=TEXT_DIM, bg="#111", font=FONT_SMALL
                   ).pack(pady=(16, 2), padx=16, anchor="w")
        sec_var = tk.StringVar()
        sec_names = [s.get("label_en" if CURRENT_LANG == "en" else "label", s["id"])
                     for s in self.sections_list]
        sec_ids   = [s["id"] for s in self.sections_list]
        sec_menu = tk.OptionMenu(dlg, sec_var, *sec_names)
        sec_menu.configure(font=FONT_SMALL, fg=TEXT_MAIN, bg="#1a1a1a",
                           activebackground="#2a2a2a", relief="flat",
                           highlightthickness=1, highlightbackground=BORDER)
        sec_menu.pack(padx=16, anchor="w")
        sec_var.set(sec_names[0])

        add_field("Code Name:", "name")
        add_field("Description:", "desc")

        # Requires
        make_label(dlg, "Requires another code? (leave blank if none):",
                   fg=TEXT_DIM, bg="#111", font=FONT_SMALL
                   ).pack(pady=(10, 2), padx=16, anchor="w")
        req_var = tk.StringVar()
        req_names = ["(none)"] + [c.get("name_en" if CURRENT_LANG == "en" else "name", c["id"])
                                   for c in self.all_codes]
        req_ids   = [None]    + [c["id"] for c in self.all_codes]
        req_menu = tk.OptionMenu(dlg, req_var, *req_names)
        req_menu.configure(font=FONT_SMALL, fg=TEXT_MAIN, bg="#1a1a1a",
                           activebackground="#2a2a2a", relief="flat",
                           highlightthickness=1, highlightbackground=BORDER)
        req_menu.pack(padx=16, anchor="w")
        req_var.set(req_names[0])

        add_field("Code (offset - bytes, e.g.  4DE390 - C3):", "code", height=4)

        def parse_code_text(text):
            """
            Parse code text in any of these formats:

            Format 1 - offset/paste:
                Find: 002B8417
                Paste:
                E8 68 8D D4 FF

            Format 2 - find/replace (Change To):
                83 C4 08 81 60 54
                Change To:
                A3 00 0E 2E 10 83

            Format 3 - simple offset:
                4DE390 - C3
                4DE391 to C3
            """
            patches = []
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            i = 0
            while i < len(lines):
                line = lines[i]
                line_up = line.upper()

                # Format 1: Find: OFFSET  /  Paste: / BYTES
                if line_up.startswith("FIND:") or line_up.startswith("FIND :"):
                    offset = line.split(":", 1)[1].strip()
                    # next non-empty line should be Paste: or bytes
                    i += 1
                    # skip "Paste:" line
                    if i < len(lines) and lines[i].upper().startswith("PASTE"):
                        i += 1
                    # collect bytes (may span multiple lines until next keyword)
                    byte_parts = []
                    while i < len(lines):
                        nxt = lines[i]
                        nxt_up = nxt.upper()
                        if (nxt_up.startswith("FIND") or
                            nxt_up.startswith("CHANGE") or
                            ("-" in nxt and len(nxt.split("-")[0].strip()) <= 8)):
                            break
                        byte_parts.append(nxt)
                        i += 1
                    byt = " ".join(" ".join(byte_parts).split())
                    if offset and byt:
                        patches.append({
                            "type": "offset_paste",
                            "offset": offset,
                            "bytes": byt
                        })
                    continue

                # Format 2: FIND_BYTES / Change To: / REPLACE_BYTES
                # detect if next non-empty line contains "Change To"
                if i + 1 < len(lines) and "CHANGE TO" in lines[i+1].upper():
                    find_bytes = line
                    i += 2  # skip "Change To:" line
                    # collect replace bytes
                    rep_parts = []
                    while i < len(lines):
                        nxt = lines[i]
                        nxt_up = nxt.upper()
                        if (nxt_up.startswith("FIND") or
                            "CHANGE TO" in nxt_up or
                            ("-" in nxt and len(nxt.split("-")[0].strip()) <= 8)):
                            break
                        rep_parts.append(nxt)
                        i += 1
                    rep_bytes = " ".join(" ".join(rep_parts).split())
                    if find_bytes and rep_bytes:
                        patches.append({
                            "type": "find_replace",
                            "find": find_bytes,
                            "replace": rep_bytes
                        })
                    continue

                # Format 3: OFFSET - BYTES  or  OFFSET to BYTES
                sep = None
                if " - " in line:
                    sep = " - "
                elif " to " in line.lower():
                    sep = line.lower().index(" to ")
                    sep = line[sep:sep+4]  # preserve original case

                if sep:
                    parts = line.split(sep, 1)
                    if len(parts) == 2:
                        offset = parts[0].strip()
                        byt    = parts[1].strip()
                        if offset and byt:
                            patches.append({
                                "type": "offset_replace",
                                "offset": offset,
                                "bytes": byt
                            })
                    i += 1
                    continue

                # skip unrecognized lines
                i += 1

            return patches

        def save_new_code():
            name = fields["name"].get().strip()
            desc = fields["desc"].get().strip()
            code_text = fields["code"].get("1.0", "end").strip()
            sec_label = sec_var.get()
            sec_id = sec_ids[sec_names.index(sec_label)]
            req_label = req_var.get()
            req_id = req_ids[req_names.index(req_label)] if req_label != "(none)" else None

            if not name:
                messagebox.showerror("Error", "Code name is required.")
                return
            if not code_text:
                messagebox.showerror("Error", "Code bytes are required.")
                return

            patches = parse_code_text(code_text)
            if not patches:
                messagebox.showerror("Error",
                    "Could not parse the code.\n\n"
                    "Supported formats:\n"
                    "  Find: OFFSET\n  Paste:\n  BYTES\n\n"
                    "  FIND_BYTES\n  Change To:\n  REPLACE_BYTES\n\n"
                    "  OFFSET - BYTES\n  OFFSET to BYTES")
                return

            # generate id from name
            import re
            cid = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            if cid in self.code_by_id:
                cid = cid + "_custom"

            # add to codes_info
            new_info = {
                "id": cid,
                "section": sec_id,
                "name": name,
                "name_en": name,
                "desc": desc,
                "desc_en": desc,
                "notes": [],
                "notes_en": [],
                "requires": [req_id] if req_id else [],
                "detectable": True
            }
            self.codes_info["codes"].append(new_info)
            self.code_by_id[cid] = new_info
            self.codes_by_section.setdefault(sec_id, []).append(new_info)
            self.all_codes = self.codes_info["codes"]

            # add to codes_data
            self.codes_data[cid] = {"patches": patches}

            # save both files
            try:
                with open(INFO_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.codes_info, f, ensure_ascii=False, indent=2)
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.codes_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                messagebox.showerror("Error", "Failed to save:\n" + str(e))
                return

            dlg.destroy()
            messagebox.showinfo("[+] Added",
                                "Code added successfully:\n" + name +
                                "\nIn section: " + sec_label)
            self._after_state_change()

        make_button(dlg, "Add Code", save_new_code,
                    fg=GREEN, bg="#1a2a0a", active_bg="#2a4a1a", width=12
                    ).pack(pady=12)




# ═════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = RE4PatcherApp()
    app.mainloop()
