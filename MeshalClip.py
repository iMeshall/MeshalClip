import json
import os
import subprocess
import sys
import threading
import tkinter as tk

import customtkinter as ctk
from tkinter import filedialog
import yt_dlp

APP_NAME = "MeshalClip"
APP_AUTHOR = "Made By Meshal"
HEIGHTS = [None, 1080, 720, 480]  # None = best available

# ---------------- design tokens ----------------
# Neutral graphite background with a canary-yellow accent (a nod to the original yellow-on-black tool).
BG = "#121316"
SURFACE = "#1B1D22"
FIELD = "#15171B"
BORDER = "#2C2F37"
TRACK = "#2A2D35"
HOVER = "#24272E"
TEXT = "#ECEDEF"
MUTED = "#8E929B"
ACCENT = "#FFD23F"
ACCENT_H = "#EDBF1E"
ON_ACCENT = "#1B1F0A"
OK = "#5BE3A0"
ERR = "#FF8A80"

UI_FONT = "Segoe UI"
DISPLAY_FONT = "Bahnschrift"  # ships with Windows 10/11; falls back automatically


def F(size, weight="normal", family=UI_FONT):
    return ctk.CTkFont(family=family, size=size, weight=weight)


STRINGS = {
    "en": {
        "subtitle": "Paste a link, pick a format, download.",
        "placeholder": "Paste video link here...",
        "paste": "Paste",
        "mode_video": "Video  MP4",
        "mode_audio": "Audio  MP3",
        "quality": "Quality",
        "best": "Best",
        "save_to": "Save to",
        "change_folder": "Change",
        "open_folder": "Open",
        "download": "Download",
        "downloading_btn": "Downloading...",
        "idle": "Waiting for a link",
        "ready": "Ready",
        "need_link": "Paste a link first",
        "starting": "Starting...",
        "downloading": "Downloading",
        "processing": "Processing file...",
        "done": "Done ✔",
        "failed": "Failed - see details",
        "saved": "Saved to: ",
        "show_details": "Show details ▾",
        "hide_details": "Hide details ▴",
        "lang_btn": "العربية",
    },
    "ar": {
        "subtitle": "الصق الرابط، اختر الصيغة، ثم حمّل.",
        "placeholder": "الصق رابط الفيديو هنا...",
        "paste": "لصق",
        "mode_video": "فيديو  MP4",
        "mode_audio": "صوت  MP3",
        "quality": "الجودة",
        "best": "الأفضل",
        "save_to": "مكان الحفظ",
        "change_folder": "تغيير",
        "open_folder": "فتح",
        "download": "تحميل",
        "downloading_btn": "جارٍ التحميل...",
        "idle": "بانتظار الرابط",
        "ready": "جاهز",
        "need_link": "الصق رابطاً أولاً",
        "starting": "جارٍ البدء...",
        "downloading": "جارٍ التحميل",
        "processing": "جارٍ معالجة الملف...",
        "done": "تم التحميل ✔",
        "failed": "فشل التحميل - راجع التفاصيل",
        "saved": "تم الحفظ في: ",
        "show_details": "إظهار التفاصيل ▾",
        "hide_details": "إخفاء التفاصيل ▴",
        "lang_btn": "English",
    },
}


# ---------------- helpers ----------------
def resource_dir():
    """Where bundled files live (PyInstaller temp folder, or script folder)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def find_ffmpeg():
    """Look for ffmpeg.exe inside the bundle first, then next to the exe/script."""
    candidates = [resource_dir()]
    if getattr(sys, "frozen", False):
        candidates.append(os.path.dirname(sys.executable))
    for d in candidates:
        if os.path.isfile(os.path.join(d, "ffmpeg.exe")):
            return d
    return None  # fall back to ffmpeg in PATH


def settings_path():
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "MeshalClip")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        pass
    return os.path.join(folder, "settings.json")


def load_settings():
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(data):
    try:
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def system_lang():
    """Arabic Windows UI -> 'ar', otherwise 'en'."""
    try:
        import ctypes
        lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "ar" if (lid & 0x3FF) == 0x01 else "en"
    except Exception:
        return "en"


def shorten(text, n):
    return text if len(text) <= n else text[: n - 1] + "…"


def shorten_path(path, n=44):
    return path if len(path) <= n else "…" + path[-(n - 1):]


def fmt_bytes(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def fmt_eta(seconds):
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def make_logo(px=256):
    """Draw the app mark (viewfinder corners + play triangle) with PIL. Returns an image or None."""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    ss = 4  # supersampling for smooth edges
    S = px * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.26), fill=ACCENT)
    ink = ON_ACCENT
    m, arm, w = S * 0.21, S * 0.19, max(2, int(S * 0.065))
    for cx, cy, sx, sy in ((m, m, 1, 1), (S - m, m, -1, 1), (m, S - m, 1, -1), (S - m, S - m, -1, -1)):
        d.line([(cx + sx * arm, cy), (cx, cy), (cx, cy + sy * arm)], fill=ink, width=w, joint="curve")
    cx, cy, r = S * 0.53, S * 0.5, S * 0.17
    d.polygon([(cx - r * 0.85, cy - r), (cx - r * 0.85, cy + r), (cx + r * 1.05, cy)], fill=ink)
    return img.resize((px, px), Image.LANCZOS)


class QuietLogger:
    def __init__(self, log_fn):
        self.log_fn = log_fn

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        self.log_fn(msg)


class Chips(ctk.CTkFrame):
    """Pill-style option picker: selected chip is filled with the accent color."""

    def __init__(self, master, labels, index, command, rtl=False):
        super().__init__(master, fg_color=FIELD, corner_radius=12, border_width=1, border_color=BORDER)
        self.index = index
        self.command = command
        self.enabled = True
        self.buttons = []
        for i, text in enumerate(labels):
            b = ctk.CTkButton(
                self, text=text, height=28, width=10, corner_radius=8, border_width=0,
                font=F(12, "bold"), command=lambda i=i: self._pick(i),
            )
            b.pack(side="right" if rtl else "left", padx=3, pady=3)
            self.buttons.append(b)
        self.refresh()

    def _pick(self, i):
        if not self.enabled:
            return
        self.index = i
        self.refresh()
        self.command(i)

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.refresh()

    def refresh(self):
        for i, b in enumerate(self.buttons):
            if i == self.index:
                if self.enabled:
                    b.configure(fg_color=ACCENT, hover_color=ACCENT_H, text_color=ON_ACCENT)
                else:
                    b.configure(fg_color=TRACK, hover_color=TRACK, text_color=MUTED)
            else:
                b.configure(
                    fg_color="transparent",
                    hover_color=HOVER if self.enabled else FIELD,
                    text_color=TEXT if self.enabled else MUTED,
                )


# ---------------- app ----------------
class App(ctk.CTk):
    W, H = 620, 560
    MIN_W, MIN_H = 560, 520
    LOG_EXTRA = 150

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=BG)

        self.logo_img = None
        pil_logo = make_logo(256)
        if pil_logo is not None:
            self.logo_img = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(40, 40))
            self._set_window_icon(pil_logo)

        settings = load_settings()
        lang = settings.get("lang") or system_lang()
        self.lang = lang if lang in STRINGS else "en"

        default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        saved_dir = settings.get("save_dir")
        self.save_dir = saved_dir if saved_dir and os.path.isdir(saved_dir) else default_dir

        self.busy = False
        self.mode_idx = 0
        self.quality_idx = 0
        self.url_text = ""
        self.log_lines = []
        self.log_visible = False
        self.progress_val = 0.0
        self.pct_text = "0%"
        self.meta_text = ""
        self.now_title = ""
        self.status_key = "ready"
        self.status_color = MUTED
        self.container = None

        self.title(APP_NAME)
        x = max(0, (self.winfo_screenwidth() - self.W) // 2)
        y = max(0, (self.winfo_screenheight() - self.H) // 2 - 30)
        self.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self.minsize(self.MIN_W, self.MIN_H)

        self._build_ui()
        self._autofill_clipboard()

    def _set_window_icon(self, img):
        if not sys.platform.startswith("win"):
            return
        try:
            import tempfile
            path = os.path.join(tempfile.gettempdir(), "meshalclip_icon.ico")
            img.save(path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
            self.iconbitmap(path)
        except Exception:
            pass

    # ---------- i18n ----------
    def t(self, key):
        return STRINGS[self.lang][key]

    @property
    def rtl(self):
        return self.lang == "ar"

    def toggle_language(self):
        self.lang = "ar" if self.lang == "en" else "en"
        self._save()
        self._build_ui()

    def _save(self):
        save_settings({"lang": self.lang, "save_dir": self.save_dir})

    # ---------- UI ----------
    def _build_ui(self):
        if self.container is not None:
            self.url_text = self.url_entry.get()
            self.container.destroy()

        rtl = self.rtl
        start = "right" if rtl else "left"
        end = "left" if rtl else "right"
        anchor = "e" if rtl else "w"
        justify = "right" if rtl else "left"
        gap = (0, 10) if rtl else (10, 0)  # space between a widget and the one before it

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=24)
        c = self.container

        # footer first, so it stays pinned to the bottom
        ctk.CTkLabel(c, text=APP_AUTHOR, font=F(10), text_color=MUTED).pack(side="bottom", pady=(4, 10))

        # ----- header -----
        head = ctk.CTkFrame(c, fg_color="transparent")
        head.pack(fill="x", pady=(18, 14))
        if self.logo_img is not None:
            ctk.CTkLabel(head, text="", image=self.logo_img, width=40, height=40).pack(side=start)
        else:  # fallback when Pillow is missing
            ctk.CTkLabel(
                head, text="M", width=40, height=40, corner_radius=11, fg_color=ACCENT,
                text_color=ON_ACCENT, font=F(20, "bold", DISPLAY_FONT),
            ).pack(side=start)
        titles = ctk.CTkFrame(head, fg_color="transparent")
        titles.pack(side=start, padx=14)
        ctk.CTkLabel(
            titles, text=APP_NAME, font=F(19, "bold", DISPLAY_FONT), text_color=TEXT, anchor=anchor
        ).pack(fill="x")
        ctk.CTkLabel(
            titles, text=self.t("subtitle"), font=F(11), text_color=MUTED, anchor=anchor
        ).pack(fill="x")
        ctk.CTkButton(
            head, text=self.t("lang_btn"), width=78, height=28, corner_radius=14,
            fg_color="transparent", border_width=1, border_color=BORDER, hover_color=HOVER,
            text_color=TEXT, font=F(12), command=self.toggle_language,
        ).pack(side=end)

        # ----- main panel -----
        panel = ctk.CTkFrame(c, fg_color=SURFACE, corner_radius=18, border_width=1, border_color=BORDER)
        panel.pack(fill="x")

        # link row
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        self.url_entry = ctk.CTkEntry(
            row, placeholder_text=self.t("placeholder"), height=40, corner_radius=10,
            fg_color=FIELD, border_color=BORDER, border_width=1, text_color=TEXT,
            placeholder_text_color=MUTED, font=F(13), justify=justify,
        )
        self.url_entry.pack(side=start, fill="x", expand=True)
        self.url_entry.bind("<Return>", lambda e: self.start())
        if self.url_text:
            self.url_entry.insert(0, self.url_text)
        ctk.CTkButton(
            row, text=self.t("paste"), width=80, height=40, corner_radius=10,
            fg_color=TRACK, hover_color=BORDER, text_color=TEXT, font=F(13, "bold"),
            command=self.paste,
        ).pack(side=start, padx=gap)

        ctk.CTkFrame(panel, height=1, fg_color=BORDER, corner_radius=0).pack(fill="x", padx=16)

        # format + quality row
        opts = ctk.CTkFrame(panel, fg_color="transparent")
        opts.pack(fill="x", padx=16, pady=12)
        self.mode_chips = Chips(
            opts, [self.t("mode_video"), self.t("mode_audio")], self.mode_idx,
            self._mode_changed, rtl=rtl,
        )
        self.mode_chips.pack(side=start)
        self.quality_chips = Chips(
            opts, self._quality_labels(), self.quality_idx, self._quality_changed, rtl=rtl
        )
        self.quality_chips.pack(side=end)
        ctk.CTkLabel(opts, text=self.t("quality"), font=F(12), text_color=MUTED).pack(side=end, padx=10)
        self.quality_chips.set_enabled(self.mode_idx == 0)

        ctk.CTkFrame(panel, height=1, fg_color=BORDER, corner_radius=0).pack(fill="x", padx=16)

        # save location row
        frow = ctk.CTkFrame(panel, fg_color="transparent")
        frow.pack(fill="x", padx=16, pady=(10, 12))
        for key, cmd in (("open_folder", self.open_folder), ("change_folder", self.choose_folder)):
            ctk.CTkButton(
                frow, text=self.t(key), width=60, height=28, corner_radius=8,
                fg_color="transparent", hover_color=HOVER, text_color=ACCENT, font=F(12, "bold"),
                command=cmd,
            ).pack(side=end)
        ctk.CTkLabel(frow, text=self.t("save_to"), font=F(12), text_color=MUTED).pack(side=start)
        self.folder_label = ctk.CTkLabel(
            frow, text=shorten_path(self.save_dir), font=F(12), text_color=TEXT, anchor=anchor
        )
        self.folder_label.pack(side=start, fill="x", expand=True, padx=10)

        # ----- download button -----
        self.dl_btn = ctk.CTkButton(
            c, text=self.t("downloading_btn" if self.busy else "download"), height=46,
            corner_radius=12, fg_color=ACCENT, hover_color=ACCENT_H, text_color=ON_ACCENT,
            text_color_disabled="#5C5A2C", font=F(15, "bold"), command=self.start,
            state="disabled" if self.busy else "normal",
        )
        self.dl_btn.pack(fill="x", pady=(14, 14))

        # ----- progress readout (open on the background, no card) -----
        top = ctk.CTkFrame(c, fg_color="transparent")
        top.pack(fill="x")
        self.pct_label = ctk.CTkLabel(top, text="", font=F(28, "bold", DISPLAY_FONT), text_color=TEXT)
        self.pct_label.pack(side=start)
        self.status_label = ctk.CTkLabel(top, text="", font=F(12, "bold"))
        self.status_label.pack(side=end, pady=(10, 0))

        self.progress = ctk.CTkProgressBar(
            c, height=8, corner_radius=4, fg_color=TRACK,
            progress_color=OK if self.status_key == "done" else ACCENT,
        )
        self.progress.set(self.progress_val)
        self.progress.pack(fill="x", pady=(0, 6))

        bottom = ctk.CTkFrame(c, fg_color="transparent")
        bottom.pack(fill="x")
        self.meta_label = ctk.CTkLabel(bottom, text="", font=F(11), text_color=MUTED)
        self.meta_label.pack(side=end)
        self.title_label = ctk.CTkLabel(bottom, text="", font=F(12), text_color=MUTED, anchor=anchor)
        self.title_label.pack(side=start, fill="x", expand=True)

        # ----- details (collapsed by default) -----
        self.details_btn = ctk.CTkButton(
            c, text="", height=22, width=10, fg_color="transparent", hover_color=BG,
            text_color=MUTED, font=F(11), command=self.toggle_details,
        )
        self.details_btn.pack(anchor=anchor, pady=(10, 0))
        self.log_box = ctk.CTkTextbox(
            c, height=120, fg_color=SURFACE, border_width=1, border_color=BORDER,
            corner_radius=12, text_color=TEXT, font=("Consolas", 11),
        )
        for line in self.log_lines:
            self.log_box.insert("end", line + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

        self._apply_details(resize=False)
        self._render_progress()

    # ---------- small helpers ----------
    def _quality_labels(self):
        return [self.t("best")] + [f"{h}p" for h in HEIGHTS[1:]]

    def _mode_changed(self, index):
        self.mode_idx = index
        self.quality_chips.set_enabled(index == 0)

    def _quality_changed(self, index):
        self.quality_idx = index

    def _render_progress(self):
        self.pct_label.configure(text=self.pct_text)
        self.meta_label.configure(text=self.meta_text)
        title = shorten(self.now_title, 56) if self.now_title else self.t("idle")
        self.title_label.configure(text=title)
        self.status_label.configure(text=self.t(self.status_key), text_color=self.status_color)

    def set_status(self, key, color=MUTED):
        self.status_key, self.status_color = key, color
        self._render_progress()

    def toggle_details(self):
        self.log_visible = not self.log_visible
        self._apply_details(resize=True)

    def _apply_details(self, resize=False):
        if self.log_visible:
            self.details_btn.configure(text=self.t("hide_details"))
            self.log_box.pack(fill="both", expand=True, pady=(4, 0))
        else:
            self.details_btn.configure(text=self.t("show_details"))
            self.log_box.pack_forget()
        if resize:
            self.update_idletasks()
            w, h = self.winfo_width(), self.winfo_height()  # real pixels
            scale = getattr(self, "_get_window_scaling", lambda: 1.0)()
            if self.log_visible:
                self._closed_h = h
                max_h = self.winfo_screenheight() - 80
                new_h = min(h + int(self.LOG_EXTRA * scale), max_h)
            else:
                new_h = getattr(self, "_closed_h", None) or h
            # tk.Tk.geometry takes real pixels (ctk's own geometry() would scale them again)
            tk.Tk.geometry(self, f"{w}x{new_h}")

    def _autofill_clipboard(self):
        try:
            clip = self.clipboard_get().strip()
            if clip.startswith(("http://", "https://")) and not self.url_entry.get():
                self.url_entry.insert(0, clip)
        except Exception:
            pass

    def paste(self):
        try:
            text = self.clipboard_get().strip()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text)
        except Exception:
            pass

    def choose_folder(self):
        d = filedialog.askdirectory(initialdir=self.save_dir)
        if d:
            self.save_dir = d
            self.folder_label.configure(text=shorten_path(d))
            self._save()

    def open_folder(self):
        try:
            if sys.platform.startswith("win"):
                os.startfile(self.save_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.save_dir])
            else:
                subprocess.Popen(["xdg-open", self.save_dir])
        except Exception:
            pass

    # ---------- thread-safe UI updates ----------
    def log(self, text):
        text = str(text)

        def _do():
            self.log_lines.append(text)
            self.log_box.configure(state="normal")
            self.log_box.insert("end", text + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, _do)

    def _progress_update(self, value, key, pct=None, meta=None, title=None):
        def _do():
            self.progress_val = value
            self.progress.set(value)
            if pct is not None:
                self.pct_text = pct
            if meta is not None:
                self.meta_text = meta
            if title:
                self.now_title = title
            self.set_status(key, TEXT)

        self.after(0, _do)

    def _finish(self, ok):
        def _do():
            self.busy = False
            self.dl_btn.configure(state="normal", text=self.t("download"))
            if ok:
                self.progress_val = 1.0
                self.progress.set(1.0)
                self.progress.configure(progress_color=OK)
                self.pct_text, self.meta_text = "100%", ""
                self.set_status("done", OK)
            else:
                self.set_status("failed", ERR)
                if not self.log_visible:
                    self.toggle_details()

        self.after(0, _do)

    # ---------- download ----------
    def start(self):
        if self.busy:
            return
        url = self.url_entry.get().strip()
        if not url:
            self.set_status("need_link", ERR)
            return
        self.busy = True
        self.dl_btn.configure(state="disabled", text=self.t("downloading_btn"))
        self.progress_val = 0.0
        self.progress.set(0)
        self.progress.configure(progress_color=ACCENT)
        self.pct_text, self.meta_text, self.now_title = "0%", "", ""
        self.set_status("starting", TEXT)
        threading.Thread(target=self._run, args=(url,), daemon=True).start()

    def _hook(self, d):
        title = (d.get("info_dict") or {}).get("title")
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                p = d["downloaded_bytes"] / total
                parts = []
                if d.get("speed"):
                    parts.append(fmt_bytes(d["speed"]) + "/s")
                if d.get("eta") is not None:
                    parts.append(fmt_eta(d["eta"]))
                self._progress_update(p, "downloading", f"{int(p * 100)}%", "   ".join(parts), title)
        elif d["status"] == "finished":
            self._progress_update(1.0, "processing", "100%", "", title)

    def _run(self, url):
        is_video = self.mode_idx == 0
        outtmpl = os.path.join(self.save_dir, "%(title).100s [%(id)s].%(ext)s")

        opts = {
            "outtmpl": outtmpl,
            "noplaylist": True,
            "windowsfilenames": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "no_color": True,
            "logger": QuietLogger(self.log),
            "progress_hooks": [self._hook],
        }
        ffmpeg_dir = find_ffmpeg()
        if ffmpeg_dir:
            opts["ffmpeg_location"] = ffmpeg_dir

        if is_video:
            height = HEIGHTS[self.quality_idx]
            h = f"[height<={height}]" if height else ""
            opts["format"] = (
                f"bv*{h}[ext=mp4]+ba[ext=m4a]/b{h}[ext=mp4]/bv*{h}+ba/b{h}/b"
            )
            opts["merge_output_format"] = "mp4"
        else:
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            self.log(self.t("saved") + self.save_dir)
            self._finish(True)
        except Exception as e:
            self.log(str(e))
            self._finish(False)


if __name__ == "__main__":
    App().mainloop()