"""
aPE-Watchdog: a live view of aPEOSI's simulated RAM.

This is a separate program. It maps the same .aperam file as aPEOSI
(read-only) and redraws it 20 times per second, showing the OS
switch bits as it runs: context switches in the header, PCBs changing in the
process table, page tables filling in, and typed text landing in a page.

Usage:
    python ape_watchdog.py                   # RAM of motherboard/board.json
    python ape_watchdog.py --board my.json   # RAM of another board
    python ape_watchdog.py path/to/ram0.aperam

Start it before or after aPEOSI; it waits for the RAM file and follows reboots.
"""

import argparse
import mmap
import os
import sys
import tkinter as tk
from tkinter import ttk

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from devices.internal.A.apeos.system2.sys import aperam, hardware  # noqa: E402
from devices.internal.A.apeos.system2.sys.aperam import (  # noqa: E402
    FT_FREE, FT_KERNEL, FT_PAGETABLE, FT_USER, KERNEL_PID, STATE_NAMES, ft_decode)

POLL_MS = 50
DECAY = 0.8          # how fast the "just changed" glow fades each poll
HEAT_LEVELS = 6      # glow is drawn in this many steps

# --- colours ------------------------------------------------------------------
BG = "#16181d"
PANEL = "#1f232a"
TEXT = "#d7dae0"
MUTED = "#8a919e"
FREE = "#2b3038"
KERNEL = "#3d6fa8"
PAGETABLE = "#6b6f9e"
BIT_OFF = "#262a31"
BIT_ON = "#3ddc84"
FLASH = "#ffb000"
SLOT_COLOURS = [
    "#e0694c", "#4cb5e0", "#c45cd1", "#58c46c", "#d16bb3", "#4ce0c3", "#e09a4c", "#8f9cff",
    "#c4e04c", "#e04c7a", "#4c7ae0", "#b07a52", "#7ae0a0", "#e07ae0", "#a0a0a0", "#e0e0a0",
]


def _rgb(colour):
    return int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)


def mix(a, b, t):
    """Blends colour a towards colour b by t (0..1)."""
    (r1, g1, b1), (r2, g2, b2) = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % (round(r1 + (r2 - r1) * t), round(g1 + (g2 - g1) * t), round(b1 + (b2 - b1) * t))


def quantize(heat):
    return round(heat * HEAT_LEVELS) / HEAT_LEVELS


class RamFile:
    """Read-only view of an .aperam file that survives aPEOSI reboots."""

    def __init__(self, path):
        self.path = path
        self._file = None
        self._mm = None
        self._identity = None

    def _close(self):
        if self._mm is not None:
            self._mm.close()
        if self._file is not None:
            self._file.close()
        self._mm = self._file = self._identity = None

    def snapshot(self):
        """Returns a bytes copy of the whole RAM, or None if it is not there."""
        try:
            st = os.stat(self.path)
        except OSError:
            self._close()
            return None
        identity = (st.st_ino, st.st_size)
        if identity != self._identity:
            # New or replaced file (e.g. aPEOSI booted with another RAM module).
            self._close()
            if st.st_size == 0:
                return None
            try:
                self._file = open(self.path, "rb")
                self._mm = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
            except (OSError, ValueError):
                self._close()
                return None
            self._identity = identity
        return self._mm[:]


class Watchdog:
    def __init__(self, root, ram_path):
        self.root = root
        self.ram = RamFile(ram_path)
        self.ram_path = ram_path
        self.prev = None
        self.layout = None
        self.geometry = None
        self.selected = None
        self.frame_heat = []
        self.bit_heat = {}
        self.frame_items = []
        self.frame_fill = []
        self.bit_items = []
        self.bit_fill = []
        self.last_seq = None
        self.writes_per_sec = 0.0
        self.hex_cache = None

        root.title("aPE-Watchdog")
        root.configure(bg=BG)
        self._build_ui()
        self.poll()

    # ------------------------------------------------------------------ UI ---
    def _build_ui(self):
        mono = ("Consolas", 10) if sys.platform == "win32" else ("DejaVu Sans Mono", 9)
        self.mono = mono
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        rowheight=18, font=mono, borderwidth=0)
        style.configure("Treeview.Heading", background=BG, foreground=MUTED, font=mono, relief="flat")
        style.map("Treeview", background=[("selected", "#2f3540")])

        self.status = tk.Label(self.root, font=mono, bg=BG, fg=TEXT, anchor="w", justify="left")
        self.status.grid(row=0, column=0, columnspan=2, sticky="we", padx=10, pady=(8, 2))
        self.status2 = tk.Label(self.root, font=mono, bg=BG, fg=MUTED, anchor="w", justify="left")
        self.status2.grid(row=1, column=0, columnspan=2, sticky="we", padx=10, pady=(0, 6))

        left = tk.Frame(self.root, bg=BG)
        left.grid(row=2, column=0, sticky="nw", padx=(10, 6))
        tk.Label(left, text="PHYSICAL FRAMES  (click one, or use the arrow keys)", font=mono, bg=BG, fg=MUTED,
                 anchor="w").pack(fill="x")
        self.map_canvas = tk.Canvas(left, bg=BG, highlightthickness=0, width=420, height=420)
        self.map_canvas.pack(anchor="w")
        self.map_canvas.bind("<Button-1>", self._on_map_click)
        self.map_canvas.bind("<Motion>", self._on_map_hover)
        self.hover = tk.Label(left, font=mono, bg=BG, fg=MUTED, anchor="w", justify="left", width=52)
        self.hover.pack(fill="x", pady=(2, 6))

        legend = tk.Frame(left, bg=BG)
        legend.pack(fill="x", pady=(0, 6))
        for name, colour in (("free", FREE), ("kernel", KERNEL), ("page table", PAGETABLE),
                             ("user (colour = process)", SLOT_COLOURS[0]), ("just written", FLASH)):
            tk.Label(legend, text="  ", bg=colour).pack(side="left", padx=(0, 3))
            tk.Label(legend, text=name, font=mono, bg=BG, fg=MUTED).pack(side="left", padx=(0, 10))

        tk.Label(left, text="PROCESS TABLE  (read from RAM)", font=mono, bg=BG, fg=MUTED,
                 anchor="w").pack(fill="x")
        cols = ("slot", "pid", "name", "state", "runs", "pages", "pt")
        self.ptable = ttk.Treeview(left, columns=cols, show="headings", height=8, selectmode="none")
        for col, width in zip(cols, (40, 50, 120, 90, 70, 50, 40)):
            self.ptable.heading(col, text=col.upper())
            self.ptable.column(col, width=width, anchor="w", stretch=False)
        self.ptable.pack(anchor="w")
        for slot, colour in enumerate(SLOT_COLOURS):
            self.ptable.tag_configure(f"slot{slot}", foreground=colour)
        self.ptable.tag_configure("current", background="#3a3220")

        right = tk.Frame(self.root, bg=BG)
        right.grid(row=2, column=1, sticky="nw", padx=(6, 10))
        self.page_title = tk.Label(right, font=mono, bg=BG, fg=TEXT, anchor="w", justify="left")
        self.page_title.pack(fill="x")
        self.bit_canvas = tk.Canvas(right, bg=BG, highlightthickness=0, width=760, height=200)
        self.bit_canvas.pack(anchor="w", pady=(2, 6))
        tk.Label(right, text="HEX + ASCII", font=mono, bg=BG, fg=MUTED, anchor="w").pack(fill="x")
        hex_frame = tk.Frame(right, bg=BG)
        hex_frame.pack(anchor="w", fill="x")
        self.hex = tk.Text(hex_frame, font=mono, bg=PANEL, fg=TEXT, height=16, width=92,
                           relief="flat", borderwidth=6, wrap="none")
        scroll = tk.Scrollbar(hex_frame, command=self.hex.yview)
        self.hex.configure(yscrollcommand=scroll.set, state="disabled")
        self.hex.pack(side="left")
        scroll.pack(side="left", fill="y")

        self.auto_select = True
        self.root.bind("<Left>", lambda e: self._step_selection(-1))
        self.root.bind("<Right>", lambda e: self._step_selection(1))
        self.root.bind("<Up>", lambda e: self._step_selection(-16))
        self.root.bind("<Down>", lambda e: self._step_selection(16))

    # --------------------------------------------------------- geometry ---
    def _rebuild(self, layout):
        """(Re)creates canvas items when the RAM module changes."""
        self.layout = layout
        self.geometry = (layout.page_size, layout.num_pages)
        n = layout.num_pages
        self.cols = 16 if n > 64 else 8
        rows = -(-n // self.cols)
        self.cell = max(18, min(48, 400 // max(self.cols, rows)))
        c = self.map_canvas
        c.delete("all")
        c.configure(width=self.cols * self.cell + 2, height=rows * self.cell + 2)
        self.frame_items, self.frame_fill = [], []
        font = (self.mono[0], 7 if self.cell < 28 else 8)
        for f in range(n):
            x, y = (f % self.cols) * self.cell + 1, (f // self.cols) * self.cell + 1
            rect = c.create_rectangle(x + 1, y + 1, x + self.cell - 3, y + self.cell - 3, fill=FREE,
                                      outline=BG, width=3)
            c.create_text(x + self.cell / 2 - 1, y + self.cell / 2 - 1, text=f"{f:02X}", fill="#0e1014",
                          font=font)
            self.frame_items.append(rect)
            self.frame_fill.append(None)
        self.selection_box = c.create_rectangle(0, 0, 0, 0, outline="#ffffff", width=2)
        self.auto_select = True
        self.frame_heat = [0.0] * n
        if self.selected is None or self.selected >= n:
            self.selected = layout.first_user_frame
        self._build_bit_view()

    def _build_bit_view(self):
        ps = self.layout.page_size
        rows = ps // 16
        self.bw = 5
        self.bh = 11 if rows <= 16 else (6 if rows <= 64 else 3)
        gap, label_w = 3, 66
        c = self.bit_canvas
        c.delete("all")
        c.configure(width=label_w + 16 * (8 * self.bw + gap), height=rows * (self.bh + 1) + 2)
        self.bit_items, self.bit_fill = [], []
        font = (self.mono[0], 7)
        self.row_labels = []
        for r in range(rows):
            y = r * (self.bh + 1) + 1
            if self.bh >= 6 and (self.bh >= 11 or r % 4 == 0):
                self.row_labels.append(c.create_text(label_w - 6, y + self.bh / 2, anchor="e", text="",
                                                     fill=MUTED, font=font))
            else:
                self.row_labels.append(None)
            for byte in range(16):
                for bit in range(8):
                    x = label_w + byte * (8 * self.bw + gap) + bit * self.bw
                    self.bit_items.append(c.create_rectangle(x, y, x + self.bw - 1, y + self.bh - 1,
                                                             fill=BIT_OFF, width=0))
                    self.bit_fill.append(BIT_OFF)
        self.bit_heat = {}
        self.hex_cache = None

    # ---------------------------------------------------------- polling ---
    def poll(self):
        try:
            self._update()
        finally:
            self.root.after(POLL_MS, self.poll)

    def _update(self):
        data = self.ram.snapshot()
        header = aperam.parse_header(data) if data else None
        if header is None:
            self.status.configure(text=f"Waiting for aPEOSI to power on its RAM...  ({self.ram_path})")
            self.status2.configure(text="Boot aPEOSI with:  python main.py")
            self.prev = None
            return
        try:
            layout = aperam.Layout.from_header(header)
        except ValueError:
            return
        if len(data) < layout.size:
            return
        if (layout.page_size, layout.num_pages) != self.geometry:
            self._rebuild(layout)
            self.prev = None

        prev = self.prev if self.prev is not None and len(self.prev) == len(data) else data
        self.prev = data
        ps = layout.page_size

        # --- header numbers ---
        seq = header["write_seq"]
        if self.last_seq is not None:
            delta = (seq - self.last_seq) & 0xFFFFFFFF
            self.writes_per_sec = 0.7 * self.writes_per_sec + 0.3 * delta * (1000 / POLL_MS)
        self.last_seq = seq

        pcbs = {}
        for slot in range(layout.max_procs):
            pcb = aperam.parse_pcb(data, layout.pcb_addr(slot))
            if pcb["used"]:
                pcbs[slot] = pcb
        cur = header["current_pid"]
        running = "kernel" if cur == KERNEL_PID else next(
            (f"PID {p['pid']} {p['name']}" for p in pcbs.values() if p["pid"] == cur), f"PID {cur}")
        self.status.configure(text=(
            f"{header['ram_name']}  {layout.size:,} bytes = {layout.num_pages} x {ps}   "
            f"aPEOSI {header['os_version']}   tick {header['tick']:,}   "
            f"writes {seq:,} ({self.writes_per_sec:,.0f}/s)   CPU: {running}"))
        kb = layout.kbd_page * ps
        kb_len = min(int.from_bytes(data[kb:kb + 2], "little"), ps - 2)
        typed = data[kb + 2:kb + 2 + kb_len].decode("utf-8", "replace")
        self.status2.configure(text=f"keyboard buffer: {typed!r}      file: {self.ram_path}")

        # --- frame map ---
        table = data[layout.frame_table_page * ps: layout.frame_table_page * ps + layout.num_pages]
        self.frame_info = []
        for f in range(layout.num_pages):
            a = f * ps
            if data[a:a + ps] != prev[a:a + ps]:
                self.frame_heat[f] = 1.0
            else:
                self.frame_heat[f] *= DECAY
            ftype, owner = ft_decode(table[f])
            if f < layout.first_user_frame:
                ftype = FT_KERNEL
            base = {FT_FREE: FREE, FT_KERNEL: KERNEL, FT_PAGETABLE: PAGETABLE}.get(
                ftype, SLOT_COLOURS[owner % len(SLOT_COLOURS)])
            heat = quantize(self.frame_heat[f])
            look = (base, mix(BG, FLASH, heat))
            if look != self.frame_fill[f]:
                self.map_canvas.itemconfigure(self.frame_items[f], fill=look[0], outline=look[1])
                self.frame_fill[f] = look
            self.frame_info.append((ftype, owner))
        self.pcbs = pcbs
        self.data = data
        if self.auto_select:
            # Until the user clicks, show the first page that belongs to a program.
            user = [f for f, (t, _) in enumerate(self.frame_info) if t == FT_USER]
            if user:
                self._select(user[0])
                prev = data
            if user or self.selected != layout.first_user_frame:
                self.auto_select = False
        sel = self.selected
        x, y = (sel % self.cols) * self.cell + 1, (sel // self.cols) * self.cell + 1
        self.map_canvas.coords(self.selection_box, x - 1, y - 1, x + self.cell - 1, y + self.cell - 1)
        self.map_canvas.tag_raise(self.selection_box)

        self._update_process_table(pcbs, cur)
        self._update_bits(data, prev)

    def describe_frame(self, f):
        ftype, owner = self.frame_info[f]
        lay = self.layout
        if ftype == FT_KERNEL:
            return f"frame 0x{f:02X}: kernel - {lay.kernel_frame_role(f)}"
        if ftype == FT_FREE:
            return f"frame 0x{f:02X}: free"
        pcb = self.pcbs.get(owner)
        who = f"PID {pcb['pid']} '{pcb['name']}'" if pcb else f"slot {owner}"
        if ftype == FT_PAGETABLE:
            return f"frame 0x{f:02X}: page table of {who}"
        # find which virtual page maps here
        vpage = None
        if pcb:
            pt = pcb["pt_frame"] * lay.page_size
            entries = self.data[pt:pt + aperam.VPAGES]
            if f in entries:
                vpage = entries.index(f)
        if vpage is None:
            return f"frame 0x{f:02X}: user page of {who}"
        lo = vpage * lay.page_size
        return (f"frame 0x{f:02X}: user page of {who}, "
                f"virtual 0x{lo:04X}-0x{lo + lay.page_size - 1:04X}")

    def _update_process_table(self, pcbs, cur):
        rows = []
        for slot, p in sorted(pcbs.items()):
            values = (slot, p["pid"], p["name"], STATE_NAMES.get(p["state"], "?"), p["sched_count"],
                      p["pages_mapped"], f"{p['pt_frame']:02X}")
            tags = [f"slot{slot}"] + (["current"] if p["pid"] == cur else [])
            rows.append((values, tuple(tags)))
        existing = self.ptable.get_children()
        if len(existing) != len(rows):
            self.ptable.delete(*existing)
            existing = [self.ptable.insert("", "end") for _ in rows]
        for item, (values, tags) in zip(existing, rows):
            self.ptable.item(item, values=values, tags=tags)

    def _update_bits(self, data, prev):
        ps = self.layout.page_size
        base = self.selected * ps
        page, old = data[base:base + ps], prev[base:base + ps]
        self.page_title.configure(text=f"BITS OF {self.describe_frame(self.selected).upper()}")

        # Mark bits that flipped since the last poll.
        if page != old:
            for i in range(ps):
                diff = page[i] ^ old[i]
                if diff:
                    for bit in range(8):
                        if diff & (0x80 >> bit):
                            self.bit_heat[i * 8 + bit] = 1.0

        changed = set(self.bit_heat)
        for idx in list(self.bit_heat):
            self.bit_heat[idx] *= DECAY
            if self.bit_heat[idx] < 0.05:
                del self.bit_heat[idx]
        if self.hex_cache is None or page != old:
            changed.update(range(ps * 8))  # full redraw on page change / selection

        for idx in changed:
            on = page[idx // 8] & (0x80 >> (idx % 8))
            fill = mix(BIT_ON if on else BIT_OFF, FLASH, 0.9 * quantize(self.bit_heat.get(idx, 0.0)))
            if fill != self.bit_fill[idx]:
                self.bit_canvas.itemconfigure(self.bit_items[idx], fill=fill)
                self.bit_fill[idx] = fill

        if page != self.hex_cache:
            self.hex_cache = page
            for r, label in enumerate(self.row_labels):
                if label is not None:
                    self.bit_canvas.itemconfigure(label, text=f"0x{base + r * 16:05X}")
            lines = []
            for r in range(0, ps, 16):
                chunk = page[r:r + 16]
                hexes = " ".join(f"{b:02X}" for b in chunk)
                text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                lines.append(f"0x{base + r:05X}  {hexes}  |{text}|")
            top = self.hex.yview()[0]
            self.hex.configure(state="normal")
            self.hex.delete("1.0", "end")
            self.hex.insert("1.0", "\n".join(lines))
            self.hex.configure(state="disabled")
            self.hex.yview_moveto(top)

    # ------------------------------------------------------------ input ---
    def _frame_at(self, event):
        if not self.layout:
            return None
        col, row = (event.x - 1) // self.cell, (event.y - 1) // self.cell
        f = row * self.cols + col
        if 0 <= col < self.cols and 0 <= f < self.layout.num_pages:
            return f
        return None

    def _select(self, f):
        if f is not None and f != self.selected:
            self.selected = f
            self.bit_heat = {}
            self.hex_cache = None

    def _step_selection(self, delta):
        self.auto_select = False
        if self.layout:
            self._select((self.selected + delta) % self.layout.num_pages)

    def _on_map_click(self, event):
        self.auto_select = False
        self._select(self._frame_at(event))

    def _on_map_hover(self, event):
        f = self._frame_at(event)
        if f is not None and getattr(self, "frame_info", None):
            self.hover.configure(text=self.describe_frame(f))


def main():
    parser = argparse.ArgumentParser(description="Live view of aPEOSI's aPE-RAM.")
    parser.add_argument("ram_file", nargs="?", help="path to an .aperam file")
    parser.add_argument("--board", default="board.json", help="motherboard file inside /motherboard")
    args = parser.parse_args()

    if args.ram_file:
        path = os.path.abspath(args.ram_file)
    else:
        try:
            path = hardware.load_board(os.path.join(ROOT, "motherboard"), args.board).ram_file
        except hardware.HardwareError as e:
            print(f"Watchdog: {e}")
            sys.exit(1)

    root = tk.Tk()
    Watchdog(root, path)
    root.mainloop()


if __name__ == "__main__":
    main()
