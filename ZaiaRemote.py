# -*- coding: utf-8 -*-
import sys, os, json, socket, threading, time, io, ctypes, subprocess, winreg, re, ipaddress, uuid, urllib.request, zlib, queue, hashlib, struct, ntpath, select
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, simpledialog, filedialog
from PIL import Image, ImageGrab, ImageChops
import pystray
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except Exception:
    TkinterDnD = None
DND = [False]
try:
    import av  # H.264: ลื่นและคมกว่า JPEG ใช้เน็ตน้อยกว่า ~10 เท่า (ไม่มี/พัง -> ใช้ JPEG เหมือนเดิม)
    if not hasattr(av, "CodecContext"):  # ติดตั้งมาไม่ครบ/ชื่อชนแพ็กเกจอื่น (เช่น "av" คนละตัว) ใช้ H.264 จริงไม่ได้
        av = None
except Exception:
    av = None

APP_NAME = "ZaiaRemoteDesktop"
APP_VER = "9.1.2"
SETUP_REV = 3  # เลขรุ่นของตัวติดตั้ง/ไลบรารีใน python\ ถ้า update.json ระบุ setup_rev สูงกว่านี้ ต้องลงด้วยตัวติดตั้งใหม่
UPDATE_URL = "https://raw.githubusercontent.com/Minos117/ZaiaRemote.py/refs/heads/main/ZaiaRemote.py"  # ต้องเป็นลิงก์ดาวน์โหลดตรง (repo public)
DEFAULT_NB_URL = "https://api.netbird.io:443"
DEFAULT_NB_KEY = "91F120E5-D6F9-4D7C-BBB9-2BF1E32DDCAA"  # Setup Key ฝังไว้ให้เชื่อมต่ออัตโนมัติ (ถ้าเปลี่ยนใน update.json หรือหน้าตั้งค่า จะใช้ค่าใหม่แทน)
DEFAULT_PEER_IP = "100.123.145.188"  # IP NetBird ของเครื่องปลายทางหลัก ใส่ให้ในช่อง "ต่อด้วยเลข IP"
PORT = 47101
JPEG_Q = 75  # ใช้เฉพาะสำรองเมื่อไม่มี H.264; ค่าคงที่ ไม่ปรับเอง
DOC_JPEG_Q = 80  # โหมดเอกสาร: ส่วนที่เปลี่ยนมากทั้งหน้า (เลื่อนจอ) ส่งเป็น JPEG แล้วจะส่งซ้ำแบบไม่สูญเสียเมื่อจอนิ่ง
DOC_LOSSY_AREA = 300000  # พิกเซล: กล่องที่เปลี่ยนใหญ่กว่านี้ส่งเป็น JPEG ที่เล็กกว่านี้ส่ง PNG (ตัวอักษรคมเป๊ะ)
H264_KBPS = {0: 4000, 1: 8000, 2: 12000}  # บิตเรตคงที่ต่อระดับคุณภาพ ที่ผู้ใช้เลือกเอง
QUALITY = [(1280, 30, "720p 30fps"), (1920, 30, "1080p 30fps"), (1920, 60, "1080p 60fps"), (0, 15, "เอกสาร (คมชัด)")]  # (กว้างสูงสุด, fps, ชื่อ); ตัวที่ 3 = โหมดเอกสาร ไม่ย่อภาพ
CTRL_PORT = 47102
APPDIR = os.path.join(os.environ["APPDATA"], "ZaiaRemote")
CONFIG_PATH = os.path.join(APPDIR, "config.json")
ERRLOG = os.path.join(APPDIR, "error.log")
os.makedirs(APPDIR, exist_ok=True)
SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
ICON_PATH = os.path.join(SCRIPT_DIR, "zaia.ico")
LOGO_PATH = os.path.join(SCRIPT_DIR, "zaia_logo.png")

ROLES = ["สัสดีจังหวัด", "สัสดีอำเภอ", "เสมียนจังหวัด", "เสมียนหน่วยสัสดีอำเภอ"]
UNITS = ["สกลนคร", "เมืองสกลนคร", "บ้านม่วง", "คำตากล้า", "วานรนิวาส", "กุสุมาลย์", "กุดบาก",
         "ส่องดาว", "เจริญศิลป์", "วาริชภูมิ", "สว่างแดนดิน", "โพนนาแก้ว", "ภูพาน",
         "พังโคน", "พรรณานิคม", "อากาศอำนวย", "เต่างอย", "โคกศรีสุพรรณ", "นิคมน้ำอูน", "(อื่นๆ)"]

def log_err(e):
    with open(ERRLOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.ctime()}] {e}\n")

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"autostart": True, "nb_mgmt_url": DEFAULT_NB_URL}

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False)

cfg = load_config()
HOSTNAME = socket.gethostname()
if not cfg.get("uid") or cfg.get("host") != HOSTNAME:  # config ถูกก๊อปมาจากเครื่องอื่น -> id ซ้ำ จะมองไม่เห็นกัน
    cfg["uid"] = uuid.uuid4().hex[:8]
    cfg["host"] = HOSTNAME
    save_config(cfg)
MY_ID = cfg["uid"]
NAVY2RED = {"#101a2e": "#1a0505", "#16233d": "#3a0d0d", "#20314f": "#6b1f1f",
            "#e7f0ff": "#f5d9d9", "#8fa3c4": "#d79a9a", "#2fa8ff": "#ff6b81"}
def tc(c):  # สีธีมน้ำเงิน -> แดงดำ เมื่ออยู่โหมดแอดมิน
    return NAVY2RED.get(c, c) if ADMIN[0] else c
FONT = ["Tahoma"]  # ตั้งใหม่ตอนเปิดโปรแกรม: Leelawadee UI (ฟอนต์ไทยของ Windows) ถ้าไม่มีใช้ Tahoma
SCALE = [1.0]
_FONTS = {}
def FNT(size, weight="normal"):  # ฟอนต์แบบมีชื่อ ปรับขนาดทั้งโปรแกรมพร้อมกันได้เมื่อหน้าต่างเปลี่ยนขนาด
    k = (size, weight)
    if k not in _FONTS:
        _FONTS[k] = tkfont.Font(family=FONT[0], size=max(int(round(size * SCALE[0])), 8), weight=weight)
    return _FONTS[k]
def rescale_fonts(f):
    SCALE[0] = f
    for (size, weight), ft in _FONTS.items():
        ft.configure(size=max(int(round(size * f)), 8))
ADMIN = [False]  # โหมดแอดมิน (ซ่อน): พิมพ์ "god" (แป้นอังกฤษ) หรือ "เนก" (แป้นไทย) ที่ไหนก็ได้ในโปรแกรมเพื่อเปิด/ปิด

def username():
    if ADMIN[0] and cfg.get("username"):
        return cfg["username"]
    return (cfg.get("role", "") + cfg.get("unit", "")) or HOSTNAME

def ver_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))

def is_old(ver):
    return not ver[:1].isdigit() or ver_tuple(ver) < (1, 6)

def update_urls():
    u = cfg.get("update_url") or UPDATE_URL
    return [u + ("" if "?" in u else f"?t={int(time.time())}")]  # ?t= กันแคชของ raw.githubusercontent (~5 นาที)

def fetch_update():
    errs = []
    for url in update_urls():
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ZaiaRemote"}), timeout=30) as r:
                data = r.read()
            break
        except urllib.error.HTTPError as e:
            errs.append(f"HTTP {e.code} {e.read()[:120].decode('utf-8', 'replace')}")
        except Exception as e:
            errs.append(str(e))
    else:
        raise ValueError(" | ".join(errs))
    src = data.decode("utf-8-sig", "replace")
    m = re.search(r'^APP_VER = "([\d.]+)"', src, re.M)
    if not m:
        raise ValueError("ไฟล์ที่โหลดมาไม่ใช่ ZaiaRemote.py (ลิงก์อาจต้องล็อกอิน)")
    compile(src, "ZaiaRemote.py", "exec")  # กันไฟล์เสียก่อนเขียนทับ
    return m.group(1), data

def http_get(url):
    u = url + ("" if "?" in url else f"?t={int(time.time())}")
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "ZaiaRemote"}), timeout=30) as r:
        return r.read()

def update_base():  # โฟลเดอร์ดิบของ repo = ลิงก์อัปเดตตัดชื่อไฟล์ท้ายออก
    return (cfg.get("update_url") or UPDATE_URL).split("?")[0].rsplit("/", 1)[0] + "/"

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def fetch_manifest():  # update.json = {"version","files":{ชื่อไฟล์:sha256},"nb_setup_key"?,"nb_mgmt_url"?,"setup_rev"?}
    m = json.loads(http_get(update_base() + "update.json").decode("utf-8-sig"))
    if not re.fullmatch(r"\d+(\.\d+)*", str(m.get("version", ""))) or not isinstance(m.get("files"), dict):
        raise ValueError("update.json ไม่ถูกต้อง")
    for name in m["files"]:  # รับเฉพาะชื่อไฟล์เปล่า ๆ ในโฟลเดอร์โปรแกรม กันเขียนออกนอกโฟลเดอร์
        if name != os.path.basename(name) or name.startswith(".") or "\\" in name or ":" in name:
            raise ValueError(f"ชื่อไฟล์ใน update.json ไม่ปลอดภัย: {name}")
    return m

def changed_files(m):
    out = []
    for name, sha in m["files"].items():
        p = os.path.join(SCRIPT_DIR, name)
        if not os.path.exists(p) or sha256_file(p) != sha.lower(): out.append(name)
    return out

def check_update():  # -> (เลขรุ่น, manifest หรือ None, ข้อมูลไฟล์ที่โหลดมาแล้ว หรือ None)
    try:
        m = fetch_manifest()
    except urllib.error.HTTPError as e:
        if e.code != 404: raise
        v, data = fetch_update()  # repo ที่ยังไม่มี update.json: อัปเดตไฟล์เดียวแบบเดิม
        return v, None, {"ZaiaRemote.py": data}
    return m["version"], m, None

def stage_update(m):  # โหลดเฉพาะไฟล์ที่ต่างจากในเครื่อง ตรวจแฮชทุกไฟล์ก่อนแตะของเดิม
    out = {}
    for name in changed_files(m):
        data = http_get(update_base() + name)
        if hashlib.sha256(data).hexdigest() != m["files"][name].lower():
            raise ValueError(f"{name}: แฮชไม่ตรง (ไฟล์เสียหรือเพิ่งอัปโหลดไม่ครบ) ลองใหม่ภายหลัง")
        if name.endswith(".py"): compile(data.decode("utf-8-sig"), name, "exec")
        out[name] = data
    return out

def relaunch(moves=()):
    me = os.path.abspath(__file__)
    flag = "" if is_admin() else " --noelev"
    mv = "".join(f'move /y "{a}" "{b}" >nul & ' for a, b in moves)  # ไฟล์ที่ถูกล็อกตอนนี้ ย้ายหลังโปรแกรมปิด
    subprocess.Popen(f'cmd /c ping -n 3 127.0.0.1 >nul & {mv}start "" "{sys.executable}" "{me}"{flag}',
                     shell=True, creationflags=0x08000000)  # รอให้ตัวเก่าปล่อย mutex ก่อนเปิดตัวใหม่
    os._exit(0)

def apply_staged(m, staged):
    moves = []
    for name, data in staged.items():
        p = os.path.join(SCRIPT_DIR, name)
        if name.endswith(".py") and os.path.exists(p):
            with open(p, "rb") as f: old = f.read()
            with open(p + ".bak", "wb") as f: f.write(old)
        with open(p + ".new", "wb") as f: f.write(data)
        try: os.replace(p + ".new", p)
        except OSError: moves.append((p + ".new", p))
    if nb_changed(m):  # ปรับค่า NetBird เฉพาะตอนค่าใน update.json เปลี่ยน
        u, k = nb_vals(m)
        if u: cfg["nb_mgmt_url"] = u
        if k: cfg["nb_setup_key"] = k
        cfg["nb_applied"] = nb_sig((u, k))
        save_config(cfg)
    relaunch(moves)

def apply_update(data):
    apply_staged({}, {"ZaiaRemote.py": data})

try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception: pass
try: ctypes.windll.winmm.timeBeginPeriod(1)  # นาฬิกา Windows ปกติหยาบ ~15ms -> sleep() คุมจังหวะเฟรมไม่ได้ 60fps จะสะดุด
except Exception: pass

# ---------- admin / elevate ----------
def is_admin():
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception: return False

UAC_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
def uac_secure_on():  # True = UAC ขึ้นบน Secure Desktop (ค่าปกติของ Windows) ผู้คุมจะเห็นเป็นจอดำ
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, UAC_KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            return winreg.QueryValueEx(k, "PromptOnSecureDesktop")[0] != 0
    except OSError:
        return True

def set_uac_secure(on):  # ต้องเป็น admin ถ้าไม่ใช่จะ raise PermissionError
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, UAC_KEY, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as k:
        winreg.SetValueEx(k, "PromptOnSecureDesktop", 0, winreg.REG_DWORD, 1 if on else 0)

def task_exists():
    try:
        return subprocess.run(["schtasks", "/Query", "/TN", "ZAIA Remote"], capture_output=True,
                              creationflags=0x08000000, timeout=10).returncode == 0
    except Exception:
        return False

# ควบคุมหน้าต่าง admin/UAC และตั้งงานเปิดตอนเริ่มเครื่องได้ต้องเป็น admin; ถ้าไม่ใช่ ขอสิทธิ์ 1 ครั้ง (ปฏิเสธก็ใช้ต่อได้)
def already_running():  # mutex ของตัว admin เปิดจาก user ธรรมดาไม่ได้ (error 5) = มีตัวที่รันอยู่แล้ว
    k = ctypes.windll.kernel32
    k.OpenMutexW.restype = ctypes.c_void_p
    h = k.OpenMutexW(0x100000, False, "ZaiaRemoteDesktopMutex")
    if h:
        k.CloseHandle(ctypes.c_void_p(h))
        return True
    return k.GetLastError() == 5

def ask_show():  # สั่งตัวที่รันอยู่ให้เด้งหน้าต่างขึ้นมา (ผ่าน UDP ในเครื่อง ไม่ติดสิทธิ์ admin)
    try:
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sk.sendto(b"ZAIA_SHOW", ("127.0.0.1", PORT))
        sk.close()
    except Exception:
        pass

# ---------- ส่วน SYSTEM (4.0.0) ----------
# งาน Scheduled Task "ZAIA Remote SYSTEM" (SYSTEM) รัน --sysagent -> เปิดตัวทำงาน --sysworker (SYSTEM) ในเซสชันผู้ใช้
# ตัวทำงานผูกกับ Desktop ที่รับอินพุตอยู่ (รวม Secure Desktop ของ UAC/ล็อกจอ) แล้วจับภาพ/ส่งเมาส์คีย์บอร์ดให้โปรแกรมหลักผ่าน 127.0.0.1 (ต้องมี token ในไฟล์ที่เฉพาะ admin/SYSTEM อ่านได้)
SYS_DIR = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "ZaiaRemote")
SYS_FILE = os.path.join(SYS_DIR, "sysagent.json")
SYS_TASK = "ZAIA Remote SYSTEM"
_SYS_DOWN = {0: 0x0002, 1: 0x0008, 2: 0x0020}
_SYS_UP = {0: 0x0004, 1: 0x0010, 2: 0x0040}

def _sys_attach(st):  # ผูกเธรดกับ Desktop ที่รับอินพุตอยู่ ต้องทำก่อนจับภาพ/ส่งอินพุต
    u = ctypes.windll.user32
    u.OpenInputDesktop.restype = ctypes.c_void_p
    u.OpenInputDesktop.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    u.SetThreadDesktop.argtypes = [ctypes.c_void_p]
    u.CloseDesktop.argtypes = [ctypes.c_void_p]
    h = u.OpenInputDesktop(0, False, 0x10000000)
    if not h: return False
    if u.SetThreadDesktop(h):
        if st.get("h"): u.CloseDesktop(st["h"])
        st["h"] = h
        return True
    u.CloseDesktop(h)
    return False

def _sys_grab(l, t, w, h):  # จับภาพจากจอด้วย GDI ของ Desktop ที่เธรดนี้ผูกอยู่
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    V, I, U = ctypes.c_void_p, ctypes.c_int, ctypes.c_uint
    u.GetDC.restype = V; u.GetDC.argtypes = [V]; u.ReleaseDC.argtypes = [V, V]
    g.CreateCompatibleDC.restype = V; g.CreateCompatibleDC.argtypes = [V]
    g.CreateCompatibleBitmap.restype = V; g.CreateCompatibleBitmap.argtypes = [V, I, I]
    g.SelectObject.restype = V; g.SelectObject.argtypes = [V, V]
    g.BitBlt.argtypes = [V, I, I, I, I, V, I, I, ctypes.c_uint32]
    g.GetDIBits.argtypes = [V, V, U, U, V, V, U]
    g.DeleteObject.argtypes = [V]; g.DeleteDC.argtypes = [V]
    sdc = u.GetDC(None)
    if not sdc: raise OSError("GetDC")
    mdc = bmp = None
    try:
        mdc = g.CreateCompatibleDC(sdc)
        bmp = g.CreateCompatibleBitmap(sdc, w, h)
        old = g.SelectObject(mdc, bmp)
        ok = g.BitBlt(mdc, 0, 0, w, h, sdc, l, t, 0x00CC0020 | 0x40000000)  # SRCCOPY | CAPTUREBLT
        g.SelectObject(mdc, old)
        if not ok: raise OSError("BitBlt")
        buf = ctypes.create_string_buffer(w * h * 4)
        bmi = ctypes.create_string_buffer(struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0))
        if not g.GetDIBits(mdc, bmp, 0, h, buf, bmi, 0): raise OSError("GetDIBits")
        return Image.frombuffer("RGB", (w, h), bytes(buf), "raw", "BGRX", 0, 1)
    finally:
        if bmp: g.DeleteObject(bmp)
        if mdc: g.DeleteDC(mdc)
        u.ReleaseDC(None, sdc)

def _sys_rx(c, n):
    buf = b""
    while len(buf) < n:
        d = c.recv(n - len(buf))
        if not d: return None
        buf += d
    return buf

def _sys_conn(c, token):
    st, u = {}, ctypes.windll.user32
    try:
        c.settimeout(5)
        if _sys_rx(c, 32) != token.encode("latin1"): return
        c.settimeout(None)
        v = APP_VER.encode()
        c.sendall(bytes([len(v)]) + v)
        last = 0.0
        while True:
            t = _sys_rx(c, 1)
            if not t: break
            t = t.decode("latin1")
            if t == "G":
                l, tp, w, h = struct.unpack("<iiii", _sys_rx(c, 16))
                if w < 1 or h < 1 or w > 16384 or h > 16384: break
                _sys_attach(st)
                buf = io.BytesIO()
                _sys_grab(l, tp, w, h).save(buf, "JPEG", quality=85)
                d = buf.getvalue()
                c.sendall(len(d).to_bytes(4, "little") + d)
            elif t in "MDUWKJ":
                b = _sys_rx(c, {"M": 8, "D": 1, "U": 1, "W": 4, "K": 4, "J": 4}[t])
                if b is None: break
                now = time.time()
                if t != "M" or now - last > 0.2:  # ขยับเมาส์ถี่ ๆ ไม่ต้องผูก Desktop ซ้ำทุกครั้ง
                    _sys_attach(st); last = now
                if t == "M":
                    u.SetCursorPos(int.from_bytes(b[:4], "little", signed=True), int.from_bytes(b[4:], "little", signed=True))
                elif t == "D": u.mouse_event(_SYS_DOWN.get(b[0], 0x0002), 0, 0, 0, 0)
                elif t == "U": u.mouse_event(_SYS_UP.get(b[0], 0x0004), 0, 0, 0, 0)
                elif t == "W": u.mouse_event(0x0800, 0, 0, ctypes.c_uint32(int.from_bytes(b, "little", signed=True)).value, 0)
                else: u.keybd_event(int.from_bytes(b, "little", signed=True), 0, 2 if t == "J" else 0, 0)
            else:
                break
    except Exception as e:
        log_err(e)
    finally:
        try: c.close()
        except Exception: pass

def _sys_worker():
    import secrets
    os.makedirs(SYS_DIR, exist_ok=True)
    subprocess.run(["icacls", SYS_DIR, "/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F"],
                   capture_output=True, creationflags=0x08000000, timeout=30)  # เฉพาะ SYSTEM กับ Administrators
    token = secrets.token_hex(16)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    tmp = SYS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"port": srv.getsockname()[1], "token": token, "ver": APP_VER, "pid": os.getpid()}, f)
    os.replace(tmp, SYS_FILE)
    while True:
        c, _ = srv.accept()
        threading.Thread(target=_sys_conn, args=(c, token), daemon=True).start()

class _SI(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_uint32), ("lpReserved", ctypes.c_wchar_p), ("lpDesktop", ctypes.c_wchar_p), ("lpTitle", ctypes.c_wchar_p),
                ("dwX", ctypes.c_uint32), ("dwY", ctypes.c_uint32), ("dwXSize", ctypes.c_uint32), ("dwYSize", ctypes.c_uint32),
                ("dwXCountChars", ctypes.c_uint32), ("dwYCountChars", ctypes.c_uint32), ("dwFillAttribute", ctypes.c_uint32),
                ("dwFlags", ctypes.c_uint32), ("wShowWindow", ctypes.c_uint16), ("cbReserved2", ctypes.c_uint16),
                ("lpReserved2", ctypes.c_void_p), ("hStdInput", ctypes.c_void_p), ("hStdOutput", ctypes.c_void_p), ("hStdError", ctypes.c_void_p)]
class _PI(ctypes.Structure):
    _fields_ = [("hProcess", ctypes.c_void_p), ("hThread", ctypes.c_void_p), ("dwProcessId", ctypes.c_uint32), ("dwThreadId", ctypes.c_uint32)]

def _sys_spawn(sid, cmd):  # เปิดโปรเซส SYSTEM ในเซสชัน sid (ทำสำเนา token ของตัวเองแล้วเปลี่ยนเซสชัน) คืน handle โปรเซส
    k, a = ctypes.windll.kernel32, ctypes.windll.advapi32
    V = ctypes.c_void_p
    k.GetCurrentProcess.restype = V
    a.OpenProcessToken.argtypes = [V, ctypes.c_uint32, ctypes.POINTER(V)]
    a.DuplicateTokenEx.argtypes = [V, ctypes.c_uint32, V, ctypes.c_int, ctypes.c_int, ctypes.POINTER(V)]
    a.SetTokenInformation.argtypes = [V, ctypes.c_int, V, ctypes.c_uint32]
    a.AdjustTokenPrivileges.argtypes = [V, ctypes.c_int, V, ctypes.c_uint32, V, V]
    a.LookupPrivilegeValueW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, V]
    a.CreateProcessAsUserW.argtypes = [V, ctypes.c_wchar_p, ctypes.c_wchar_p, V, V, ctypes.c_int, ctypes.c_uint32, V, ctypes.c_wchar_p,
                                       ctypes.POINTER(_SI), ctypes.POINTER(_PI)]
    tok, new = V(), V()
    if not a.OpenProcessToken(k.GetCurrentProcess(), 0x2 | 0x8 | 0x20, ctypes.byref(tok)):  # DUPLICATE|QUERY|ADJUST_PRIVILEGES
        raise OSError("OpenProcessToken %d" % ctypes.GetLastError())
    try:
        luid = ctypes.c_uint64()
        if a.LookupPrivilegeValueW(None, "SeTcbPrivilege", ctypes.byref(luid)):  # เปิดสิทธิ์เปลี่ยนเซสชันของ token (ปกติ SYSTEM มีอยู่แล้ว)
            tp = ctypes.create_string_buffer(struct.pack("<IQI", 1, luid.value, 2))
            a.AdjustTokenPrivileges(tok, 0, tp, 0, None, None)
        if not a.DuplicateTokenEx(tok, 0x02000000, None, 2, 1, ctypes.byref(new)):
            raise OSError("DuplicateTokenEx %d" % ctypes.GetLastError())
        try:
            s = ctypes.c_uint32(sid)
            if not a.SetTokenInformation(new, 12, ctypes.byref(s), 4):  # TokenSessionId
                raise OSError("SetTokenInformation %d" % ctypes.GetLastError())
            si = _SI(); si.cb = ctypes.sizeof(_SI); si.lpDesktop = "winsta0\\default"
            pi = _PI()
            if not a.CreateProcessAsUserW(new, None, ctypes.create_unicode_buffer(cmd), None, None, False, 0x08000000, None, None,
                                          ctypes.byref(si), ctypes.byref(pi)):
                raise OSError("CreateProcessAsUser %d" % ctypes.GetLastError())
            k.CloseHandle(ctypes.c_void_p(pi.hThread))
            return pi.hProcess
        finally:
            k.CloseHandle(new)
    finally:
        k.CloseHandle(tok)

def _sys_launcher():
    k = ctypes.windll.kernel32
    k.WTSGetActiveConsoleSessionId.restype = ctypes.c_uint32
    k.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    k.WaitForSingleObject.restype = ctypes.c_uint32
    k.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    cmd = f'"{sys.executable}" "{os.path.abspath(__file__)}" --sysworker'
    while True:
        try:
            sid = k.WTSGetActiveConsoleSessionId()
            if sid in (0, 0xFFFFFFFF):
                time.sleep(3); continue
            hp = _sys_spawn(sid, cmd)
            while True:
                if k.WaitForSingleObject(hp, 2000) == 0: break  # ตัวทำงานจบเอง
                if k.WTSGetActiveConsoleSessionId() != sid:  # สลับผู้ใช้/ล็อกออก -> เปิดใหม่ในเซสชันใหม่
                    k.TerminateProcess(hp, 0); break
            k.CloseHandle(hp)
        except Exception as e:
            log_err(e)
        time.sleep(2)

if "--sysagent" in sys.argv or "--sysworker" in sys.argv:  # โหมดส่วน SYSTEM: ไม่เปิด UI ไม่แย่ง mutex ของโปรแกรมหลัก
    try:
        if "--sysworker" in sys.argv: _sys_worker()
        else: _sys_launcher()
    except Exception as e:
        log_err(e)
    os._exit(0)

if "--silent" not in sys.argv and "--noelev" not in sys.argv:
    if already_running():
        ask_show()
        sys.exit(0)
    if not is_admin():
        try:  # เปิดผ่าน Scheduled Task ที่ตัวติดตั้งสร้างไว้ ไม่ต้องขอ UAC
            if task_exists() and subprocess.run(["schtasks", "/Run", "/TN", "ZAIA Remote"], capture_output=True,
                                                creationflags=0x08000000, timeout=15).returncode == 0:
                for _ in range(30):
                    time.sleep(0.3)
                    if already_running():
                        for _ in range(16):  # ตัวใหม่ยังบูตไม่เสร็จ ส่งซ้ำจนกว่าจะรับ
                            ask_show()
                            time.sleep(0.5)
                        sys.exit(0)
        except SystemExit:
            raise
        except Exception:
            pass
        try:
            a = " ".join(f'"{x}"' for x in [os.path.abspath(sys.argv[0])] + sys.argv[1:])
            if ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, a, SCRIPT_DIR, 1) > 32:
                sys.exit(0)
        except Exception:
            pass

# ---------- single instance ----------
mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "ZaiaRemoteDesktopMutex")
if ctypes.windll.kernel32.GetLastError() in (183, 5):  # ERROR_ALREADY_EXISTS / ACCESS_DENIED
    ask_show()
    sys.exit(0)

# ---------- autostart ----------
def set_autostart():
    if task_exists():  # มี Scheduled Task (รันแบบ admin ตอน logon) แล้ว ไม่ต้องใช้ Run key ซ้ำ
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, APP_NAME)
            winreg.CloseKey(key)
        except Exception:
            pass
        return
    cmd_path = f'"{sys.executable}" "{os.path.abspath(__file__)}" --silent'
    if getattr(sys, "frozen", False):
        cmd_path = f'"{sys.executable}" --silent'
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd_path)
        winreg.CloseKey(key)
    except Exception as e:
        log_err(e)

if cfg.get("autostart", True):
    set_autostart()

# ---------- NetBird ----------
NB = {"ok": False, "ip": "", "cidrs": [], "peers": [], "det": [], "msg": "กำลังตรวจสอบ NetBird ..."}
nb_wake = threading.Event()

def nb_cli():
    for env, dflt in (("ProgramFiles", r"C:\Program Files"), ("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        p = os.path.join(os.environ.get(env, dflt), "NetBird", "netbird.exe")
        if os.path.exists(p):
            return p
    return None

def nb_run(*args, timeout=30):
    cli = nb_cli()
    if not cli:
        return None
    try:
        r = subprocess.run([cli, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, creationflags=0x08000000)
        return ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:
        log_err(e)
        return ""

def nb_update():
    out = nb_run("status", "--json", timeout=15)
    if out is None:
        NB.update(ok=False, ip="", cidrs=[], peers=[], det=[], msg="ไม่พบ NetBird — ติดตั้งโปรแกรมใหม่ด้วยตัวติดตั้ง")
        return
    try:
        j = json.loads(out)
    except Exception:
        first = out.splitlines()[0][:80] if out else "ไม่มีผลตอบกลับ"
        NB.update(ok=False, ip="", cidrs=[], peers=[], det=[], msg=f"NetBird ยังไม่พร้อม/ยังไม่ได้เข้าร่วม: {first}")
        return
    me = str(j.get("netbirdIp") or "")
    det = [d for d in ((j.get("peers") or {}).get("details") or []) if isinstance(d, dict)]
    peers = []
    for d in det:
        try: peers.append(str(ipaddress.ip_interface(d.get("netbirdIp")).ip))
        except Exception: pass
    cidrs = []
    try:
        if me: cidrs = [str(ipaddress.ip_interface(me))]
    except Exception:
        pass
    mg = bool((j.get("management") or {}).get("connected"))
    up = len([d for d in det if d.get("status") == "Connected"])
    if not mg: st = "ต่อเซิร์ฟเวอร์ NetBird ไม่ได้ (เช็กอินเทอร์เน็ต / Setup Key)"
    elif not me: st = "ยังไม่ได้รับ IP จากเครือข่าย"
    else: st = f"เชื่อมต่อเครือข่ายแล้ว  IP {me}  (เห็นเครื่องอื่นออนไลน์ {up}/{len(det)})"
    NB.update(ok=bool(mg and me), ip=me, cidrs=cidrs, peers=peers, det=det, msg=st)

def nb_poll():
    while True:
        try: nb_update()
        except Exception as e: log_err(e)
        nb_wake.wait(10)
        nb_wake.clear()

def nb_vals(m):  # ค่าเชื่อมต่อที่ update.json ส่งมา -> (url, key)
    return (str((m or {}).get("nb_mgmt_url") or ""), str((m or {}).get("nb_setup_key") or ""))

def nb_sig(v):
    return hashlib.sha256("|".join(v).encode("utf-8")).hexdigest()[:16]

def nb_changed(m):
    v = nb_vals(m)
    return any(v) and nb_sig(v) != cfg.get("nb_applied")

def ensure_netbird():
    if not nb_cli():
        notify("ยังไม่ได้ติดตั้ง NetBird — ติดตั้งโปรแกรมใหม่ด้วยตัวติดตั้ง", True)
        return
    for _ in range(6):  # service อาจยังไม่ขึ้นหลังติดตั้งใหม่
        nb_update()
        if NB["ok"] or NB["det"] or NB["ip"]: break
        if nb_run("status") is not None and "Daemon status" in (nb_run("status") or ""): break
        time.sleep(5)
    if NB["ok"]:
        nb_wake.set()
        return
    url = cfg.get("nb_mgmt_url") or DEFAULT_NB_URL
    key = cfg.get("nb_setup_key") or DEFAULT_NB_KEY
    if not key:  # เครื่องใหม่: ดึง Setup Key จาก update.json (ตรวจเงียบ ไม่โหลดไฟล์โปรแกรม)
        try:
            u, k = nb_vals(fetch_manifest())
            if u: cfg["nb_mgmt_url"] = url = u
            if k: cfg["nb_setup_key"] = key = k
            if u or k: save_config(cfg)
        except Exception as e:
            log_err(e)
    if not key:
        notify("ยังไม่มี NetBird Setup Key — ใส่ในหน้า 'ตั้งค่า'", True)
        return
    out = ""
    for _ in range(3):
        out = nb_run("up", "--management-url", url, "--setup-key", key, timeout=90) or ""
        time.sleep(3)
        nb_update()
        if NB["ok"]: break
        time.sleep(5)
    if not NB["ok"]:
        notify("NetBird เชื่อมต่อไม่สำเร็จ: " + (out.splitlines()[-1][:160] if out else NB["msg"]), True)
    nb_wake.set()

TASK_REV = 2
def ensure_startup_task():  # ทุกเครื่องได้งานเปิดตอนล็อกอินแบบเดียวกัน (ลงด้วยตัวติดตั้งหรือรันจากซอร์ส) และไม่ติดเงื่อนไขแบตเตอรี่ ทำได้เฉพาะตอนเป็น admin
    if not is_admin():
        return
    try:
        pw = os.path.join(SCRIPT_DIR, "python", "pythonw.exe")
        if not os.path.exists(pw) and not getattr(sys, "frozen", False):
            pw = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pw):
            return
        tr = f'"{pw}" "{os.path.abspath(__file__)}" --silent'
        mark = f"{TASK_REV}|{tr}"
        if task_exists() and cfg.get("task_mark") == mark:
            return
        nw = 0x08000000
        r = subprocess.run(["schtasks", "/Create", "/TN", "ZAIA Remote", "/TR", tr, "/SC", "ONLOGON", "/RU", "BUILTIN\\Users",
                            "/RL", "HIGHEST", "/F"], capture_output=True, text=True, creationflags=nw, timeout=30)
        if r.returncode != 0:
            log_err("สร้างงานเปิดตอนเริ่มเครื่องไม่สำเร็จ: " + (r.stdout + r.stderr).strip()[:200]); return
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                            "Set-ScheduledTask -TaskName 'ZAIA Remote' -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries)"],
                           capture_output=True, text=True, creationflags=nw, timeout=60)
        if r.returncode != 0:
            log_err("ตั้งค่างานเปิดตอนเริ่มเครื่องไม่สำเร็จ: " + (r.stdout + r.stderr).strip()[:200]); return
        cfg["task_mark"] = mark
        save_config(cfg)
        set_autostart()  # มีงานแล้ว ลบ Run key ซ้ำออก
    except Exception as e:
        log_err(e)

def _pyw():
    pw = os.path.join(SCRIPT_DIR, "python", "pythonw.exe")
    return pw if os.path.exists(pw) else sys.executable.replace("python.exe", "pythonw.exe")

def sys_task_set(on):  # เปิด/ปิดส่วน SYSTEM คืนข้อความผิดพลาด (ว่าง = สำเร็จ) ต้องเป็น admin
    nw = 0x08000000
    def run(a, t=60): return subprocess.run(a, capture_output=True, text=True, creationflags=nw, timeout=t)
    try:
        if not on:
            run(["schtasks", "/End", "/TN", SYS_TASK]); run(["schtasks", "/Delete", "/TN", SYS_TASK, "/F"])
            try: os.remove(SYS_FILE)
            except OSError: pass
            return ""
        tr = f'"{_pyw()}" "{os.path.abspath(__file__)}" --sysagent'
        r = run(["schtasks", "/Create", "/TN", SYS_TASK, "/TR", tr, "/SC", "ONSTART", "/RU", "SYSTEM", "/RL", "HIGHEST", "/F"])
        if r.returncode != 0: return (r.stdout + r.stderr).strip()[:200]
        r = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                 "Set-ScheduledTask -TaskName '" + SYS_TASK + "' -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Seconds 0))"])
        if r.returncode != 0: return (r.stdout + r.stderr).strip()[:200]
        run(["schtasks", "/End", "/TN", SYS_TASK])  # รีสตาร์ตให้ใช้โค้ดรุ่นปัจจุบัน
        r = run(["schtasks", "/Run", "/TN", SYS_TASK])
        return "" if r.returncode == 0 else (r.stdout + r.stderr).strip()[:200]
    except Exception as e:
        return str(e)[:200]

def sys_ensure():  # ตอนเปิดโปรแกรม: ถ้าเปิดส่วน SYSTEM ไว้ ตรวจว่ารุ่นตรงกัน (หลังอัปเดต/ย้อนรุ่น) ไม่ตรงหรือไม่ขึ้นก็สร้าง/รีสตาร์ตใหม่
    if not cfg.get("sys_on") or not is_admin(): return
    try:
        for _ in range(20):
            time.sleep(3)
            try:
                SysLink()._open().close(); return
            except RuntimeError:
                break  # คนละรุ่น
            except Exception:
                continue
        err = sys_task_set(True)
        if err: log_err("ส่วน SYSTEM เริ่มไม่ได้: " + err)
    except Exception as e:
        log_err(e)

def ensure_firewall():  # เครื่องที่ไม่ได้ลงด้วยตัวติดตั้ง (รันจากซอร์ส) จะไม่มีกฎ firewall -> รับ UDP/TCP ไม่ได้
    if not is_admin():
        return
    try:
        fw = ["netsh", "advfirewall", "firewall"]
        o = subprocess.run(fw + ["show", "rule", "name=ZAIA Remote"], capture_output=True, text=True,
                           creationflags=0x08000000, timeout=15).stdout or ""
        if str(PORT) in o and str(CTRL_PORT) in o:
            return
        subprocess.run(fw + ["delete", "rule", "name=ZAIA Remote"], capture_output=True, creationflags=0x08000000)
        for proto, port in (("UDP", PORT), ("TCP", CTRL_PORT)):
            subprocess.run(fw + ["add", "rule", "name=ZAIA Remote", "dir=in", "action=allow", f"protocol={proto}",
                                 f"localport={port}", "profile=any"], capture_output=True, creationflags=0x08000000)
    except Exception as e:
        log_err(e)

# ---------- presence (UDP) ----------
peers = {}  # id -> {"host","code","ver","last","ip","ips"}
PORT_OK = {"udp": None, "tcp": None}
peers_lock = threading.Lock()
notified = set()

CONNLOG = os.path.join(APPDIR, "connections.log")
_cl_lock = threading.Lock()
def conn_log(text):  # บันทึกว่าใครขอเข้า/ทำอะไรกับเครื่องนี้ (เก็บในเครื่องนี้เท่านั้น เกิน 512 KB เหลือ 2000 บรรทัดล่าสุด)
    try:
        with _cl_lock:
            if os.path.exists(CONNLOG) and os.path.getsize(CONNLOG) > 512 * 1024:
                with open(CONNLOG, "r", encoding="utf-8") as f: keep = f.readlines()[-2000:]
                with open(CONNLOG, "w", encoding="utf-8") as f: f.writelines(keep)
            with open(CONNLOG, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S  ") + text.replace("\n", " ") + "\n")
    except Exception as e:
        log_err(e)

def read_conn_log(n=300):
    try:
        with open(CONNLOG, "r", encoding="utf-8") as f: return "".join(f.readlines()[-n:])
    except Exception:
        return ""

def supports_new(ver):  # โหมดไฟล์ไม่ดูจอ / ข้อความแจ้งเตือน / ดึงโฟลเดอร์ ต้องรุ่น 1.13.0 ขึ้นไป
    return ver[:1].isdigit() and ver_tuple(ver) >= (1, 13, 0)

PING = {}
def ping_worker():  # วัดเวลาเชื่อม TCP ไปพอร์ตรับสาย (ส่ง "P" แล้วปิด ปลายทางไม่ถามผู้ใช้) ทำงานเฉพาะตอนเปิดโหมดแอดมิน
    def one(ip):
        t0 = time.time()
        try:
            c = socket.create_connection((ip, CTRL_PORT), timeout=1.5)
            c.sendall(b"P"); c.close()
            PING[ip] = int((time.time() - t0) * 1000)
        except Exception:
            PING[ip] = -1
    while True:
        try:
            if ADMIN[0]:
                with peers_lock:
                    ips = {v.get("ip") for v in peers.values() if v.get("ip")}
                for ip in ips:
                    threading.Thread(target=one, args=(ip,), daemon=True).start()
        except Exception as e:
            log_err(e)
        time.sleep(6)

def zip_folder(root, limit=2 << 30):  # บีบโฟลเดอร์เป็น zip ชั่วคราว (ข้ามโฟลเดอร์ระบบ/ไฟล์ที่ล็อก) เกิน 2 GB คืน None
    import tempfile, zipfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip"); tmp.close()
    total = 0
    try:
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            base = os.path.dirname(root.rstrip("\\/"))
            for d, dirs, files in os.walk(root):
                dirs[:] = [x for x in dirs if not blocked(os.path.join(d, x))]
                for fn in files:
                    fp = os.path.join(d, fn)
                    try:
                        total += os.path.getsize(fp)
                        if total > limit: raise OverflowError
                        z.write(fp, os.path.relpath(fp, base))
                    except OverflowError:
                        raise
                    except Exception:
                        continue
        return tmp.name
    except Exception as e:
        log_err(e)
        try: os.remove(tmp.name)
        except OSError: pass
        return None

def files_session(ips, work):  # เปิดการเชื่อมต่อโหมดไฟล์ (T) รอปลายทางอนุญาต (สูงสุด 60 วิ) แล้วเรียก work(sock) คืน (สำเร็จ?, ข้อความ)
    last, s = "เชื่อมต่อไม่ได้", None
    for ip in ips:
        c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        c.settimeout(5)
        try:
            c.connect((ip, CTRL_PORT)); c.sendall(b"T"); s = c
            break
        except Exception as e:
            last = f"{ip}: {e}"; c.close()
    if s is None:
        return False, last
    try:
        s.settimeout(60)
        hdr = recv_exact(s, 8)
        if not hdr: return False, "ปลายทางไม่อนุญาต"
        s.settimeout(None)
        work(s)
        return True, "สำเร็จ"
    except socket.timeout:
        return False, "ปลายทางไม่กดอนุญาตภายใน 60 วินาที"
    except Exception as e:
        return False, str(e)
    finally:
        try: s.close()
        except Exception: pass

def fmt_size(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB": return f"{n:.0f} B" if u == "B" else f"{n:.1f} {u}"
        n /= 1024

def push_files(sock, paths, progress=None, stop=None, dest=None):  # คืนจำนวนไฟล์ที่ปลายทางตอบว่าวางแล้ว (W); ปลายทางรุ่นเก่าไม่ตอบ = 0 (และวางที่เดสก์ท็อป)
    total = sum(os.path.getsize(x) for x in paths) or 1
    done, last, acks = 0, 0.0, 0
    def poll(wait):  # อ่านคำตอบจากปลายทาง: W = วางแล้ว, R = ปฏิเสธ (โฟลเดอร์ไม่อนุญาต)
        nonlocal acks
        r, _, _ = select.select([sock], [], [], wait)
        while r:
            lb = recv_exact(sock, 4)
            if not lb: return
            n = int.from_bytes(lb, "little"); d = recv_exact(sock, n & 0x1FFFFFFF)
            if not d: return
            if n & 0x80000000 and d[:1] == b"W": acks += 1
            elif n & 0x80000000 and d[:1] == b"R": raise RuntimeError(d[1:].decode("utf-8", "replace"))
            r, _, _ = select.select([sock], [], [], 0)
    for x in paths:
        base = os.path.basename(x)
        nb = (ntpath.join(dest, base) if dest else base).encode("utf-8")
        size = os.path.getsize(x)
        sock.sendall(b"F" + len(nb).to_bytes(2, "little") + nb + size.to_bytes(8, "little"))
        if dest: poll(0.15)  # ปลายทางปฏิเสธโฟลเดอร์จะตอบ R ทันที จะได้ไม่ส่งข้อมูลทิ้งเปล่า
        with open(x, "rb") as f:
            while True:
                if stop is not None and stop.is_set(): raise RuntimeError("ยกเลิก")
                b = f.read(131072)
                if not b: break
                sock.sendall(b"C" + len(b).to_bytes(4, "little") + b)
                done += len(b)
                if progress and time.time() - last > 0.3:
                    last = time.time(); progress(int(done * 100 / total))
    if dest:
        end = time.time() + 3
        while acks < len(paths) and time.time() < end: poll(0.3)
    return acks

def send_message(ips, text):  # ข้อความแจ้งเตือนสั้นๆ ไปเด้งบนเครื่องปลายทาง (ไม่ต้องกดอนุญาต แต่แสดงชื่อผู้ส่ง และกันรัว)
    tb = text.strip()[:300].encode("utf-8")
    for ip in ips:
        try:
            c = socket.create_connection((ip, CTRL_PORT), timeout=4)
            c.sendall(b"N" + len(tb).to_bytes(2, "little") + tb); c.close()
            return True
        except Exception:
            continue
    return False

def peer_user(ip):  # ชื่อผู้ใช้ (username) ของเครื่องที่ส่งมา ไม่มีชื่อเครื่องหรือ IP
    with peers_lock:
        for v in peers.values():
            if ip == v.get("ip") or ip in v.get("ips", ()):
                return v.get("code", "")
    return ""

_msg_last = {}
def handle_message_client(client, ip):
    try:
        client.settimeout(3)
        n = int.from_bytes(recv_exact(client, 2), "little")
        if n <= 0 or n > 1200: return
        text = recv_exact(client, n).decode("utf-8", "replace")[:300]
        now = time.time()
        if now - _msg_last.get(ip, 0) < 5: return  # กันรัวข้อความจาก IP เดิม
        _msg_last[ip] = now
        who = peer_name(ip) or ip
        conn_log(f"{ip} {who} | ส่งข้อความแจ้งเตือนมา: {text[:80]}")
        ctypes.windll.user32.MessageBoxW(0, f"{text}\n\n— จาก {peer_user(ip) or 'ไม่ทราบชื่อผู้ใช้'}", "ข้อความจาก ZAIA Remote", 0x40 | 0x40000 | 0x10000)
    except Exception as e:
        log_err(e)
    finally:
        try: client.close()
        except Exception: pass

def send_presence():
    # โหมดแอดมิน (god mode): ไม่โชว์ชื่อเครื่อง/IP/รุ่นให้เครื่องอื่นเห็น เหลือแค่ชื่อผู้ใช้ -- เครื่องเราเองยังเห็นตัวเองปกติเสมอ (ไม่ผ่านบรรทัดนี้)
    msg = f"{HOSTNAME}|{username()}|{APP_VER}|{MY_ID}|{'S' if ADMIN[0] else ''}|{'P' if POK_ACTIVE[0] > 0 else 'L' if POOL_ACTIVE[0] > 0 else ''}".encode("utf-8")
    try:
        ips = socket.gethostbyname_ex(HOSTNAME)[2]
    except Exception:
        ips = []
    for c in NB["cidrs"]:  # IP ของ NetBird เอง (hostname อาจไม่คืนมาถ้าเครื่องมีการ์ดเสมือนเยอะ)
        try:
            a = str(ipaddress.ip_interface(c).ip)
            if a not in ips: ips.append(a)
        except Exception:
            pass
    for ip in ips:
        if ip.startswith("127."):
            continue
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.bind((ip, 0))
            dsts = ["255.255.255.255", ip.rsplit(".", 1)[0] + ".255"]
            sweep = []  # ส่งตรงหาทุก IP ในวง ไม่พึ่ง broadcast (NetBird เป็น L3 ไม่มี broadcast)
            for c in NB["cidrs"]:
                try:
                    n = ipaddress.ip_network(c, strict=False)
                    if ipaddress.ip_address(ip) in n:
                        dsts.append(str(n.broadcast_address))
                        if n.num_addresses <= 1024:
                            sweep += [str(h) for h in n.hosts() if str(h) != ip]
                        else:  # วงใหญ่ (เช่น /16) ส่งตรงเฉพาะเครื่อง (peer) ที่ NetBird รู้จัก
                            sweep += [p for p in NB["peers"] if p != ip]
                except Exception:
                    pass
            if not NB["cidrs"]:  # อ่านสถานะ NetBird ไม่ได้ -> เดาเป็น /24
                base = ip.rsplit(".", 1)[0]
                sweep = [f"{base}.{i}" for i in range(1, 255) if f"{base}.{i}" != ip]
            for dst in dict.fromkeys(dsts + sweep):
                s.sendto(msg, (dst, PORT))
            s.close()
        except Exception as e:
            log_err(e)

def broadcaster():
    while True:
        send_presence()
        time.sleep(3)

def listener():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("", PORT))
        PORT_OK["udp"] = True
    except Exception as e:
        PORT_OK["udp"] = False
        notify(f"เปิดพอร์ตค้นหาเครื่อง {PORT} ไม่ได้: {e}", True)
        return
    while True:
        try:
            data, addr = s.recvfrom(1024)
            if data == b"ZAIA_SHOW":
                r = ROOT[0]
                if addr[0] == "127.0.0.1" and r:
                    r.after(0, lambda: (r.deiconify(), r.lift(), r.focus_force()))
                continue
            f = data.decode("utf-8").split("|")
            host, code = f[0], f[1]
            ver = f[2] if len(f) > 2 else "เก่า"
            uid = f[3] if len(f) > 3 else host
            stealth = len(f) > 4 and f[4] == "S"
            playing = len(f) > 5 and f[5] in ("P", "L")  # กำลังเล่น Play poker (8.0.0+; รุ่นเก่าอ่านช่องนี้ไม่เป็นก็ไม่เป็นไร)
            if uid == MY_ID:
                continue
            with peers_lock:
                p = peers.setdefault(uid, {"ips": set()})
                p.update(host=host, code=code, ver=ver, last=time.time(), ip=addr[0], stealth=stealth, poker=playing and f[5] == "P", pool=playing and f[5] == "L")
                p["ips"].add(addr[0])
        except Exception as e:
            log_err(e)
            time.sleep(0.2)

# ---------- remote control: win32 input injection ----------
user32 = ctypes.windll.user32
def set_cursor(x, y): user32.SetCursorPos(int(x), int(y))
def mouse_event(flags, data=0): user32.mouse_event(flags, 0, 0, data, 0)
MOUSE_FLAGS_DOWN = {0: 0x0002, 1: 0x0008, 2: 0x0020}
MOUSE_FLAGS_UP   = {0: 0x0004, 1: 0x0010, 2: 0x0040}
def keybd_event(vk, up=False): user32.keybd_event(vk, 0, 2 if up else 0, 0)

def recv_exact(sock, n):
    buf = bytearray(n)  # รับลง buffer เดียว (เดิมต่อ bytes ทีละก้อน = ก๊อปซ้ำ ๆ ช้าเมื่อเฟรมใหญ่)
    mv, got = memoryview(buf), 0
    while got < n:
        k = sock.recv_into(mv[got:], n - got)
        if not k:
            return None
        got += k
    return bytes(buf)

# ---------- control server (host side) ----------
def peer_name(ip):
    with peers_lock:
        for v in peers.values():
            if ip == v.get("ip") or ip in v.get("ips", ()):
                return f"{v.get('host','')} ({v.get('code','')})"
    return ""

def peer_ver(ip):  # รุ่นโปรแกรมของเครื่องที่รู้จัก ("" = ไม่รู้จัก)
    with peers_lock:
        for v in peers.values():
            if ip == v.get("ip") or ip in v.get("ips", ()):
                return v.get("ver") or ""
    return ""

def peer_code(ip):  # ชื่อสั้น (ตำแหน่ง+หน่วย หรือชื่อที่ตั้งเอง) สำหรับป้ายแจ้งบนจอ ไม่เอาชื่อเครื่องเพราะอ่านไม่รู้เรื่อง
    with peers_lock:
        for v in peers.values():
            if ip == v.get("ip") or ip in v.get("ips", ()):
                return v.get("code") or ip
    return ip

WATCHER = {"win": None, "names": []}  # ป้ายลอยมุมบนซ้าย บอกว่าใครกำลังดู/คุมจอเราอยู่ (เห็นทุกโปรแกรม หายเมื่อไม่มีใครต่อแล้ว)

def _watcher_render():
    names = WATCHER["names"]
    if not names:
        if WATCHER["win"]:
            try: WATCHER["win"].destroy()
            except Exception: pass
            WATCHER["win"] = None
        return
    txt = "\U0001F441  " + ", ".join(names) + "  กำลังดูจอนี้"
    if WATCHER["win"]:
        try:
            WATCHER["win"].lbl.config(text=txt)
            return
        except Exception:
            WATCHER["win"] = None
    r = ROOT[0]
    if not r:
        return
    w = tk.Toplevel(r)
    w.overrideredirect(True)
    try: w.attributes("-topmost", True)
    except Exception: pass
    try: w.attributes("-alpha", 0.93)
    except Exception: pass
    w.configure(bg="#c62828")
    lbl = tk.Label(w, text=txt, bg="#c62828", fg="#ffffff", font=("Tahoma", 12, "bold"), padx=12, pady=5)
    lbl.pack()
    w.lbl = lbl
    w.geometry("+8+8")
    WATCHER["win"] = w

def watcher_add(name):
    if ROOT[0]:
        ROOT[0].after(0, lambda: (WATCHER["names"].append(name or "ไม่ทราบชื่อ"), _watcher_render()))

def watcher_remove(name):
    if ROOT[0]:
        def f():
            if name in WATCHER["names"]:
                WATCHER["names"].remove(name)
            _watcher_render()
        ROOT[0].after(0, f)

def control_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("", CTRL_PORT))
        PORT_OK["tcp"] = True
    except Exception as e:
        PORT_OK["tcp"] = False
        notify(f"เปิดพอร์ตรับสาย {CTRL_PORT} ไม่ได้ (มีโปรแกรมอื่นใช้อยู่?): {e}", True)
        return
    srv.listen(5)
    while True:
        try:
            client, addr = srv.accept()
            client.settimeout(2)  # "P" = แค่ทดสอบพอร์ต ไม่ต้องถามผู้ใช้; "V" หรือรุ่นเก่า (เงียบ) = ขอควบคุมจริง
            try: hello = client.recv(1)
            except socket.timeout: hello = None
            except Exception: hello = b""
            q, h264, mon_idx = 1, False, 1
            if hello == b"V":  # 1.6 ส่งระดับคุณภาพต่อท้าย (0-2); รุ่น 1.5 ไม่ส่ง ใช้ค่ากลาง
                try:
                    client.settimeout(0.5)
                    qb = client.recv(1)
                    if qb and qb[0] < len(QUALITY): q = qb[0]
                    h264 = client.recv(1) == b"H"  # 1.8.4 ขึ้นไปบอกว่าถอดรหัส H.264 ได้
                    mb = client.recv(1)  # 3.1.0 ขึ้นไปส่งเลขจอที่เลือก (1=จอหลัก); รุ่นเก่าไม่ส่ง -> ใช้จอหลัก
                    if mb and mb[0] >= 1: mon_idx = mb[0]
                except Exception:
                    pass
            client.settimeout(None)
            if hello == b"N":  # ข้อความแจ้งเตือน (รุ่น 1.13.0+)
                threading.Thread(target=handle_message_client, args=(client, addr[0]), daemon=True).start()
                continue
            if hello == b"M":  # นับจำนวนจอ (3.1.0+) แค่ข้อมูลเฉยๆ ไม่เข้าจอ ไม่ต้องขออนุญาต
                try: client.sendall(bytes([monitor_count()]))
                except Exception: pass
                client.close()
                continue
            if hello == b"G":  # เกมป๊อกเด้ง (5.0.0+) ไม่เห็นจอ ไม่คุมเครื่อง จึงไม่ต้องขออนุญาต
                threading.Thread(target=poker_serve, args=(client, addr), daemon=True).start()
                continue
            if hello == b"Q":  # เกมพูล 8-ball (9.0.0+) ไม่เห็นจอ ไม่คุมเครื่อง จึงไม่ต้องขออนุญาต
                threading.Thread(target=pool_serve, args=(client, addr), daemon=True).start()
                continue
            if hello == b"I":  # ชวนเล่นป๊อกเด้ง (8.0.0+) แค่เด้งหน้าต่างถาม ไม่เห็นจอ ไม่คุมเครื่อง
                threading.Thread(target=poker_invite_recv, args=(client, addr), daemon=True).start()
                continue
            if hello == b"P" or hello == b"":
                client.close()
                continue
            pname = peer_name(addr[0])
            ans = 6 if cfg.get("auto_allow") else ctypes.windll.user32.MessageBoxW(0, (pname + "\n" if pname else "") + f"IP {addr[0]}\n\n" + ("ขอส่ง/ดึงไฟล์ในเครื่องนี้ (ไม่ดูจอ) อนุญาตไหม" if hello == b"T" else "ขอเข้ามาดูและควบคุมจอเครื่องนี้ อนุญาตไหม") + "\n(ถ้าไม่รู้จัก ให้กดไม่อนุญาต)", "มีคนขอส่ง/ดึงไฟล์" if hello == b"T" else "มีคนขอเข้ามาช่วยดูจอ", 0x04 | 0x20 | 0x100 | 0x40000)
            conn_log(f"{addr[0]} {peer_name(addr[0])} | ขอ{'ส่ง/ดึงไฟล์ (ไม่ดูจอ)' if hello == b'T' else 'ดูจอ/ควบคุม'} | "
                     + ("อนุญาตอัตโนมัติ" if cfg.get("auto_allow") else "อนุญาต" if ans == 6 else "ปฏิเสธ"))
            if ans != 6:  # IDYES
                client.close()
                continue
            if hello == b"T":  # โหมดไฟล์อย่างเดียว (ไม่จับภาพ ไม่รับเมาส์/คีย์บอร์ด) ยังต้องผ่านกล่องอนุญาตเหมือนเดิม
                threading.Thread(target=handle_files_client, args=(client,), daemon=True).start()
            else:
                threading.Thread(target=handle_control_client, args=(client, q, h264 and av is not None, mon_idx, peer_code(addr[0])), daemon=True).start()
        except Exception as e:
            log_err(e)

# ---------- Play poker: ป๊อกเด้ง (6.0.0) เหรียญเสมือน เล่นเอาสนุก ไม่มีเงินจริง ----------
# เครื่องที่กดเปิดโต๊ะเป็นเจ้าของโต๊ะ (เซิร์ฟเวอร์) เจ้ามือคือบอท คนอื่นต่อเข้า TCP พอร์ตเดิม (47102) ด้วยไบต์เปิด "G" ไม่ต้องขออนุญาต ไม่เห็นจอ/ไม่คุมเครื่อง
import random
POK_BANK, POK_COINS, POK_MAX, POK_MIN, POK_SEATS = 40000, 10000, 8, 100, 4  # POK_SEATS = จำนวนที่นั่งขั้นต่ำ ไม่ครบเติมบอท
POK_T_BET, POK_T_TURN, POK_T_RES = 30, 15, 9
_POK_R = "A23456789TJQK"
_POK_S = "♠♥♦♣"

def pok_info(cards):  # cards = [(rank 0-12, suit 0-3)] คืนแต้ม/ป๊อก/จำนวนเด้ง/ชื่อเรียก
    val = sum(0 if r >= 9 else r + 1 for r, _ in cards) % 10
    n, deng, tag = len(cards), 1, ""
    pok = n == 2 and val >= 8
    rs, ss = sorted(r for r, _ in cards), {s for _, s in cards}
    if n == 2:
        if cards[0][1] == cards[1][1] or cards[0][0] == cards[1][0]: deng = 2
    elif n == 3:
        trips, flush = rs[0] == rs[2], len(ss) == 1
        straight = rs[1] == rs[0] + 1 and rs[2] == rs[1] + 1
        if trips: deng, tag = 5, "ตอง"
        elif straight and flush: deng, tag = 5, "สเตรทฟลัช"
        elif rs[0] >= 10: deng, tag = 3, "เซียน"  # J Q K ครบสามใบ
        elif straight: deng, tag = 3, "เรียง"
        elif flush: deng = 3
    lab = f"ป๊อก {val}" if pok else f"{val} แต้ม"
    if tag: lab += " " + tag
    if deng > 1: lab += f" {deng} เด้ง"
    return {"val": val, "pok": pok, "deng": deng, "lab": lab}

class PokTable:
    def __init__(s):
        s.lock = threading.RLock()
        s.pl, s.nid, s.bank, s.phase, s.round = {}, 1, POK_BANK, "bet", 0
        s.dealer, s.deck, s.msg, s.closed = [], [], "ลงเดิมพันได้เลย", False
        s.deadline = time.time() + POK_T_BET
        s.go_at, s.turn, s.bot_at, s.nbot = 0.0, 0, 0.0, 0
        with s.lock: s.fill(); s.sync()
    # ---- ผู้เล่น/บอท ----
    def _add(s, name, send, owner, bot=False):
        pid = s.nid; s.nid += 1
        s.pl[pid] = {"id": pid, "name": (name or "ผู้เล่น")[:24], "coins": POK_COINS, "bet": 0, "pass": False, "in": False,
                     "done": False, "cards": [], "res": None, "send": send, "owner": owner, "gone": False, "bot": bot}
        return pid
    def seats(s): return [p for p in s.pl.values() if not p["gone"]]
    def fill(s):  # บอทเติมให้ครบ POK_SEATS ที่นั่ง (เฉพาะตอนลงเดิมพัน) คนจริงเข้ามาบอทออกทีละตัว
        if s.phase != "bet": return
        hum = [p for p in s.pl.values() if not p["bot"] and not p["gone"]]
        bots = [p for p in s.pl.values() if p["bot"]]
        want = max(0, POK_SEATS - len(hum))
        for p in bots[want:]: del s.pl[p["id"]]
        bots = bots[:want]
        while len(bots) < want and len(s.seats()) < POK_MAX:
            s.nbot += 1
            bots.append(s.pl[s._add("บอท %d" % s.nbot, None, False, True)])
        for p in bots:
            if p["coins"] < POK_MIN: p["coins"] = POK_COINS  # บอทเติมเหรียญเสมือนเอง
            if p["bet"] == 0 and not p["pass"]: p["bet"] = min(p["coins"], random.choice((100, 200, 500, 1000)))
    def join(s, name, send, owner, ip=""):
        with s.lock:
            if len(s.seats()) >= POK_MAX:
                idle = [p for p in s.pl.values() if p["bot"] and not p["in"]]
                if not idle: return None
                del s.pl[idle[0]["id"]]
            pid = s._add(name, send, owner)
            s.pl[pid]["ip"] = ip
            s.msg = f"{s.pl[pid]['name']} เข้าร่วมโต๊ะ"
            s.fill(); s.sync(); s.push()
            return pid
    def leave(s, pid):
        with s.lock:
            p = s.pl.get(pid)
            if not p: return
            p["gone"] = True
            if not p["in"]: del s.pl[pid]
            elif s.phase in ("deal", "play") and not p["done"]:
                p["done"] = True
                if s.phase == "play" and s.turn == pid: s.next_turn()
            s.msg = f"{p['name']} ออกจากโต๊ะ"
            if p.get("owner"):  # เจ้าของโต๊ะออก = ปิดโต๊ะ แจ้งทุกคน
                s.closed = True
                for q in list(s.pl.values()):
                    try: q["send"]({"t": "closed"})
                    except Exception: pass
                return
            s.fill(); s.sync(); s.push()
    def act(s, pid, a):
        with s.lock:
            p = s.pl.get(pid)
            if not p or p["gone"] or s.closed: return
            k = a.get("a")
            if k == "bet" and s.phase == "bet":
                try: v = int(a.get("v", 0))
                except (TypeError, ValueError): return
                if p["coins"] <= 0 or v < min(POK_MIN, p["coins"]) or v > p["coins"]: return
                p["bet"], p["pass"] = v, False
            elif k == "pass" and s.phase == "bet":
                p["bet"], p["pass"] = 0, True
            elif k == "deal" and s.phase == "bet" and p["owner"]:
                if s.human_bet(): s.start()
                else: s.msg = "ยังไม่มีใครลงเดิมพัน"
            elif k in ("hit", "stand") and s.phase == "play" and s.turn == pid:
                s.do(pid, k)
            elif k == "restart" and s.phase == "over" and p["owner"]:
                s.bank, s.phase, s.msg = POK_BANK, "bet", "เริ่มโต๊ะใหม่ เจ้ามือมีเหรียญ %d" % POK_BANK
                s.deadline = time.time() + POK_T_BET
                s.fill()
            s.sync(); s.push()
    def human_bet(s): return any(p["bet"] > 0 for p in s.seats() if not p["bot"])
    def sync(s):  # เริ่มรอบอัตโนมัติเมื่อทุกคนลงเดิมพัน/ข้ามแล้ว (ต้องมีคนจริงลงอย่างน้อย 1)
        if s.phase != "bet": s.go_at = 0.0; return
        act = [q for q in s.seats() if q["coins"] > 0]
        if act and all(q["bet"] > 0 or q["pass"] for q in act) and s.human_bet():
            if not s.go_at: s.go_at = time.time() + 1.5
        else: s.go_at = 0.0
    # ---- รอบเล่น ----
    def start(s):
        d = [(r, c) for r in range(13) for c in range(4)]
        random.SystemRandom().shuffle(d)
        s.deck, s.go_at = d, 0.0
        n = 0
        for p in list(s.pl.values()):
            p["res"], p["cards"], p["in"], p["done"] = None, [], False, False
            if p["gone"]: del s.pl[p["id"]]; continue
            if p["bet"] > 0 and p["coins"] > 0:
                p["in"], p["cards"] = True, [s.deck.pop(), s.deck.pop()]
                p["bet"] = min(p["bet"], p["coins"]); n += 1
        s.dealer = [s.deck.pop(), s.deck.pop()]
        s.phase, s.turn, s.msg = "deal", 0, "กำลังแจกไพ่ ..."
        s.deadline = time.time() + 0.34 * (2 * n + 2) + 1.0  # เวลาให้ฝั่งผู้เล่นเล่นแอนิเมชันแจกไพ่
    def begin_play(s):
        for p in s.pl.values():
            if p["in"]: p["done"] = pok_info(p["cards"])["pok"]
        if pok_info(s.dealer)["pok"]: s.to_dealer(); return
        s.turn = 0; s.next_turn()
    def next_turn(s):
        now = time.time()
        ords = [p for p in s.pl.values() if p["in"]]
        ids = [p["id"] for p in ords]
        start = ids.index(s.turn) + 1 if s.turn in ids else 0
        for p in ords[start:]:
            if not p["done"]:
                s.phase, s.turn, s.deadline = "play", p["id"], now + POK_T_TURN
                s.msg = f"ตาของ {p['name']}"
                if p["bot"]: s.bot_at = now + random.uniform(1.0, 2.0)
                return
        s.to_dealer()
    def to_dealer(s):
        s.phase, s.turn, s.msg, s.deadline = "dealer", 0, "ตาของเจ้ามือ (บอท)", time.time() + 1.8
    def do(s, pid, k):
        p = s.pl[pid]
        if k == "hit" and len(p["cards"]) == 2: p["cards"].append(s.deck.pop())
        p["done"] = True
        s.next_turn()
        if s.phase == "play": s.deadline = time.time() + POK_T_TURN + 0.6; s.bot_at += 0.6  # เผื่อเวลาแอนิเมชันจั่ว
    def bot_move(s, p):  # บอทจั่วเมื่อแต้ม 0-4 และบางครั้งที่ 5 ไม่โกงเห็นไพ่คนอื่น
        v = pok_info(p["cards"])["val"]
        return "hit" if v <= 4 or (v == 5 and random.random() < 0.4) else "stand"
    def finish(s):
        di = pok_info(s.dealer)
        if not di["pok"] and di["val"] <= 4: s.dealer.append(s.deck.pop()); di = pok_info(s.dealer)  # บอทเจ้ามือจั่วเมื่อแต้ม 0-4
        win = []
        for p in s.pl.values():  # คนแพ้จ่ายก่อน
            if not p["in"]: continue
            pi = pok_info(p["cards"])
            pk, dk = (pi["val"], pi["pok"]), (di["val"], di["pok"])  # แต้มเท่ากัน: ป๊อก (2 ใบ) ชนะ 3 ใบ
            if pk > dk: win.append((p, p["bet"] * pi["deng"], pi["deng"]))
            elif pk < dk:
                loss = min(p["bet"] * di["deng"], p["coins"])
                p["coins"] -= loss; s.bank += loss
                p["res"] = {"o": "lose", "amt": loss, "mult": di["deng"]}
            else: p["res"] = {"o": "tie", "amt": 0, "mult": 1}
        for p, amt, m in win:  # คนชนะรับตามลำดับที่นั่ง จ่ายได้ไม่เกินเงินที่เจ้ามือมี
            pay = min(amt, s.bank)
            s.bank -= pay; p["coins"] += pay
            p["res"] = {"o": "win", "amt": pay, "mult": m, "part": pay < amt}
        s.round += 1
        s.phase, s.turn, s.deadline = "result", 0, time.time() + POK_T_RES
        s.msg = "เจ้ามือ " + di["lab"]
        for p in s.pl.values(): p["bet"], p["pass"] = 0, False
    def tick(s):
        with s.lock:
            now = time.time()
            if s.phase == "bet":
                if s.go_at and now >= s.go_at: s.start()
                elif now >= s.deadline:
                    if s.human_bet(): s.start()
                    else: s.deadline = now + POK_T_BET
            elif s.phase == "deal" and now >= s.deadline: s.begin_play()
            elif s.phase == "play":
                p = s.pl.get(s.turn)
                if p is None or p["done"]: s.next_turn()
                elif p["bot"] and now >= s.bot_at: s.do(p["id"], s.bot_move(p))
                elif now >= s.deadline: s.do(p["id"], "stand")  # หมดเวลา = อยู่
                else: return
            elif s.phase == "dealer" and now >= s.deadline: s.finish()
            elif s.phase == "result" and now >= s.deadline:
                if s.bank <= 0: s.phase, s.msg = "over", "เจ้ามือหมดตัว! เจ้าของโต๊ะกด 'เริ่มโต๊ะใหม่' ได้"
                else: s.phase, s.msg, s.deadline = "bet", "ลงเดิมพันได้เลย", now + POK_T_BET
                s.dealer = []  # ล้างไพ่ทั้งโต๊ะก่อนเริ่มรอบใหม่
                for p in list(s.pl.values()):
                    if p["gone"]: del s.pl[p["id"]]; continue
                    p["cards"], p["res"], p["in"], p["done"] = [], None, False, False
                s.fill()
            else: return
            s.sync(); s.push()
    # ---- ส่งสถานะ ----
    def view(s, me):
        rev = s.phase in ("result", "over")
        def hid(n): return [None] * n
        pls = []
        for p in s.pl.values():
            if p["gone"] and not p["in"]: continue
            show = rev or p["id"] == me
            pls.append({"id": p["id"], "name": p["name"], "bot": p["bot"], "coins": p["coins"], "bet": p["bet"], "pass": p["pass"], "in": p["in"],
                        "done": p["done"], "cards": p["cards"] if show else hid(len(p["cards"])),
                        "lab": pok_info(p["cards"])["lab"] if show and p["cards"] else "", "res": p["res"]})
        return {"t": "st", "phase": s.phase, "round": s.round, "left": max(0, int(s.deadline - time.time())), "bank": s.bank, "you": me,
                "turn": s.turn, "owner": bool(s.pl.get(me, {}).get("owner")), "msg": s.msg,
                "ips": [p["ip"] for p in s.pl.values() if not p["bot"] and not p["gone"] and p.get("ip") and p["ip"] != "127.0.0.1"],
                "dealer": {"cards": s.dealer if rev else hid(len(s.dealer)), "lab": pok_info(s.dealer)["lab"] if rev and s.dealer else ""},
                "players": pls}
    def say(s, pid, text):  # แชทในโต๊ะ: ทุกคนในโต๊ะเห็น (จำกัด 100 ตัวอักษร ห่างกันอย่างน้อย 0.6 วินาที ไม่เก็บประวัติ)
        with s.lock:
            p = s.pl.get(pid)
            if not p or p["gone"] or s.closed: return
            now = time.time()
            if now - p.get("chat_at", 0) < 0.6: return
            t = "".join(ch for ch in str(text) if ch.isprintable()).strip()[:100]
            if not t: return
            p["chat_at"] = now
            for q in list(s.pl.values()):
                if q["gone"] or q["send"] is None: continue
                try: q["send"]({"t": "chat", "n": p["name"], "m": t})
                except Exception: q["gone"] = True
    def push(s):
        for p in list(s.pl.values()):
            if p["gone"] or p["send"] is None: continue
            try: p["send"](s.view(p["id"]))
            except Exception: p["gone"] = True

POKER = {"table": None}
RETRO = [False]  # ธีม Retro 8-bit (หน้าต่างเกมที่เปิดใหม่จะอ่านค่านี้)
def RFONT(): return "Courier New" if RETRO[0] else "Segoe UI"
POK_ACTIVE = [0]  # จำนวนหน้าต่าง Play poker ที่เปิดอยู่ในเครื่องนี้ (>0 = ประกาศในรายชื่อว่ากำลังเล่น)

def poker_ticker(tb):
    while not tb.closed:
        time.sleep(0.4)
        try: tb.tick()
        except Exception as e: log_err(e)

def poker_serve(client, addr):  # เซิร์ฟเวอร์ฝั่งเจ้าของโต๊ะ: 1 การเชื่อมต่อ = 1 ผู้เล่น (ข้อความ JSON ทีละบรรทัด)
    tb, pid = POKER["table"], None
    slk = threading.Lock()
    def send(o):
        with slk: client.sendall((json.dumps(o, ensure_ascii=False) + "\n").encode("utf-8"))
    try:
        client.settimeout(5)
        n = client.recv(1)
        name = b""
        while n and len(name) < n[0]:
            d = client.recv(n[0] - len(name))
            if not d: break
            name += d
        name = "".join(ch for ch in name.decode("utf-8", "replace") if ch.isprintable()).strip()[:16] or "ผู้เล่น"
        if tb is None or tb.closed:
            send({"t": "none"}); return
        client.settimeout(10)
        pid = tb.join(name, send, addr[0] == "127.0.0.1", addr[0])
        if pid is None:
            send({"t": "full"}); return
        client.settimeout(None)
        buf = b""
        while not tb.closed:
            d = client.recv(4096)
            if not d: break
            buf += d
            if len(buf) > 8192: break
            while b"\n" in buf:
                ln, buf = buf.split(b"\n", 1)
                try: a = json.loads(ln.decode("utf-8"))
                except ValueError: continue
                if isinstance(a, dict):
                    if a.get("a") == "chat": tb.say(pid, a.get("m", ""))
                    else: tb.act(pid, a)
    except Exception as e:
        log_err(e)
    finally:
        if pid is not None: tb.leave(pid)
        try: client.close()
        except Exception: pass

def poker_open_table():  # เปิดโต๊ะของเครื่องนี้ (ถ้ามีโต๊ะเก่าที่ปิดแล้วจะเปิดใหม่) คืน PokTable
    tb = POKER["table"]
    if tb is None or tb.closed:
        tb = POKER["table"] = PokTable()
        threading.Thread(target=poker_ticker, args=(tb,), daemon=True).start()
    return tb


POK_INV = {}  # ip -> เวลาที่ได้รับคำเชิญล่าสุด (กันสแปม)

def poker_invite_recv(client, addr):  # รับคำเชิญ: {"n": ชื่อผู้เชิญ, "ip": เครื่องเจ้าของโต๊ะ หรือว่าง = เครื่องที่ส่งมา}
    try:
        client.settimeout(3)
        b = b""
        while len(b) < 2:
            d = client.recv(2 - len(b))
            if not d: return
            b += d
        n = int.from_bytes(b, "little")
        if n > 400: return
        body = b""
        while len(body) < n:
            d = client.recv(n - len(body))
            if not d: return
            body += d
        o = json.loads(body.decode("utf-8"))
        who = "".join(c for c in str(o.get("n", "")) if c.isprintable()).strip()[:24] or addr[0]
        tip = str(o.get("ip") or addr[0])
        with peers_lock: known = {x for v in peers.values() for x in v.get("ips", ())}
        if tip != addr[0] and tip not in known: return  # โต๊ะต้องเป็นเครื่องของผู้เชิญ หรือเครื่องที่เห็นในวงเดียวกัน
        now = time.time()
        if now - POK_INV.get(addr[0], 0) < 20: return
        POK_INV[addr[0]] = now
        r = ROOT[0]
        if r is not None: r.after(0, poker_show_invite, who, tip, "pool" if o.get("g") == "pool" else "poker")
    except Exception as e:
        log_err(e)
    finally:
        try: client.close()
        except Exception: pass

def poker_invite_send(ip, name, host_ip, game="poker"):  # คืน None = ส่งแล้ว, ข้อความ = ผิดพลาด
    try:
        pb = json.dumps({"n": name, "ip": host_ip, "g": game}, ensure_ascii=False).encode("utf-8")
        c = socket.create_connection((ip, CTRL_PORT), timeout=4)
        c.sendall(b"I" + len(pb).to_bytes(2, "little") + pb); c.close()
        return None
    except Exception as e:
        return str(e)

def poker_show_invite(who, ip, game="poker"):  # หน้าต่างถามว่าจะเข้าร่วมไหม (ปิดเองใน 60 วินาที)
    root = ROOT[0]
    if root is None: return
    d = tk.Toplevel(root); d.title("ชวนเล่นเกม"); d.configure(bg="#2a1a5e"); d.resizable(False, False)
    try: d.attributes("-topmost", True)
    except Exception: pass
    tk.Label(d, text=f"{who} ชวนคุณเล่น" + ("พูล 8-ball" if game == "pool" else "ป๊อกเด้ง"), bg="#2a1a5e", fg="#ffe082", font=(RFONT(), 14, "bold")).pack(padx=28, pady=(18, 4))
    tk.Label(d, text="เล่นเอาสนุก ไม่มีเงินจริง", bg="#2a1a5e", fg="white", font=(RFONT(), 11)).pack(padx=28)
    row = tk.Frame(d, bg="#2a1a5e"); row.pack(pady=16)
    def yes(): d.destroy(); poker_start(ip, False, game)
    tk.Button(row, text="เข้าร่วม", bg="#2e9e3a", fg="white", font=(RFONT(), 12, "bold"), relief="flat", padx=18, pady=4, command=yes).pack(side="left", padx=8)
    tk.Button(row, text="ไม่เล่น", bg="#546e7a", fg="white", font=(RFONT(), 12, "bold"), relief="flat", padx=18, pady=4, command=d.destroy).pack(side="left", padx=8)
    d.after(60000, lambda: d.winfo_exists() and d.destroy())
    pok_snd("invite")

def poker_start(ip, host=False, game="poker"):  # ถามชื่อก่อนเข้าโต๊ะทุกครั้ง (เติมชื่อเดิมให้) แล้วค่อยเปิดหน้าต่างเกม host=True คือเปิดโต๊ะที่เครื่องนี้
    root = ROOT[0]
    if root is None: return
    d = tk.Toplevel(root); d.title("ชื่อผู้เล่น"); d.configure(bg="#2a1a5e"); d.resizable(False, False)
    try: d.iconbitmap(ICON_PATH)
    except Exception: pass
    tk.Label(d, text="ใส่ชื่อที่จะใช้ในโต๊ะนี้", bg="#2a1a5e", fg="white", font=(RFONT(), 13, "bold")).pack(padx=28, pady=(18, 6))
    v = tk.StringVar(value=(cfg.get("poker_name") or username() or HOSTNAME)[:16])
    e = tk.Entry(d, textvariable=v, font=(RFONT(), 14), width=20, justify="center"); e.pack(padx=28, pady=6)
    def ok(_=None):
        nm = "".join(c for c in v.get() if c.isprintable()).strip()[:16] or username() or HOSTNAME
        cfg["poker_name"] = nm
        try: save_config(cfg)
        except Exception as ex: log_err(ex)
        d.destroy()
        if game == "pool":
            if host: pool_open_table()
            pool_window(ip, nm)
        else:
            if host: poker_open_table()
            poker_window(ip, nm)
    row = tk.Frame(d, bg="#2a1a5e"); row.pack(pady=(8, 18))
    tk.Button(row, text="เข้าโต๊ะ", bg="#2e9e3a", fg="white", font=(RFONT(), 12, "bold"), relief="flat", padx=18, pady=4, command=ok).pack(side="left", padx=8)
    tk.Button(row, text="ยกเลิก", bg="#546e7a", fg="white", font=(RFONT(), 12, "bold"), relief="flat", padx=18, pady=4, command=d.destroy).pack(side="left", padx=8)
    e.bind("<Return>", ok); d.bind("<Escape>", lambda _e: d.destroy())
    try:
        d.update_idletasks()
        d.geometry(f"+{root.winfo_rootx() + max(0, (root.winfo_width() - d.winfo_width()) // 2)}+{root.winfo_rooty() + 120}")
    except Exception: pass
    e.focus_force(); e.select_range(0, "end")

POK_SND = {  # เสียง 8-bit: (ความถี่ Hz, มิลลิวินาที) ความถี่ 0 = เงียบ
    "deal": [(1200, 22), (900, 25)], "flip": [(660, 25), (990, 40)], "bet": [(1320, 40), (1760, 70)],
    "turn": [(988, 90), (0, 20), (1318, 150)], "hit": [(440, 40), (660, 70)], "stand": [(330, 90)],
    "win": [(523, 90), (659, 90), (784, 90), (1047, 260)], "lose": [(392, 160), (330, 160), (262, 340)],
    "tie": [(440, 110), (0, 30), (440, 110)], "chat": [(1568, 35), (2093, 55)], "cue": [(-1, 14), (180, 40), (1200, 18)], "clack": [(-1, 12), (2400, 14), (1400, 30), (900, 30)], "rail": [(-1, 10), (320, 40), (200, 50)], "pocket": [(-1, 14), (700, 40), (450, 50), (240, 90)], "invite": [(880, 80), (1175, 80), (1568, 80), (0, 30), (1568, 160)]}

def pok_wav(name, path):  # สร้างไฟล์เสียง WAV 8 บิตจากคลื่นสี่เหลี่ยม (เสียงแบบเกมเก่า)
    import wave
    rate, buf = 22050, bytearray()
    for f, ms in POK_SND[name]:
        n = int(rate * ms / 1000)
        for i in range(n):
            top = 100 if name in ("cue", "clack", "rail", "pocket") else 44  # เสียงลูกพูลดังกว่าเสียงป๊อก
            amp = 0 if f == 0 else int(top * (1 - 0.6 * i / n))
            if f < 0: buf.append(128 + random.randint(-amp, amp))  # f = -1 -> เสียงแตกซ่า (noise) ให้เหมือนลูกกระทบกัน
            else: buf.append(128 + (amp if int(2 * f * i / rate) % 2 == 0 else -amp))
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(1); w.setframerate(rate); w.writeframes(bytes(buf))

POK_SQ = queue.Queue()
POK_SW = {"on": False}
def _pok_worker():  # เล่นเสียงทีละอัน ต่อคิว (เดิมเล่นแบบ async ซ้อนกัน เสียงใหม่ตัดเสียงเก่า = ขาดๆ หายๆ)
    try:
        import winsound
        d = os.path.join(APPDIR, "poker_snd"); os.makedirs(d, exist_ok=True)
        for n in POK_SND:
            p = os.path.join(d, n + ".wav")
            if not os.path.exists(p): pok_wav(n, p)
    except Exception as e:
        log_err(e); POK_SW["on"] = False; return
    while True:
        name = POK_SQ.get()
        try: winsound.PlaySound(os.path.join(d, name + ".wav"), winsound.SND_FILENAME | winsound.SND_NODEFAULT)
        except Exception: pass

def pok_snd(name):  # เล่นเสียงเกม (ปิดได้ด้วยปุ่มเสียงในหน้าต่างเกม) ไม่มีเสียง/พัง = ข้ามเงียบๆ
    if cfg.get("poker_mute") or name not in POK_SND: return
    if not POK_SW["on"]:
        POK_SW["on"] = True; threading.Thread(target=_pok_worker, daemon=True).start()
    if name in ("deal", "flip", "chat", "clack", "rail") and POK_SQ.qsize() >= 3: return  # เสียงเล็กๆ ที่ซ้อนกันเยอะ = ทิ้ง กันเสียงเลื่อนช้ากว่าภาพ (ชนะ/แพ้/ตาคุณ ไม่ทิ้ง)
    POK_SQ.put(name)

FELT, FELT2 = "#0b6b3f", "#0e7a4d"
POK_RULES = ("วิธีเล่นสั้นๆ: 1) เลือกชิปเพิ่มเดิมพัน 2) กด 'ลงเดิมพัน' (ไม่เล่นรอบนี้กด 'ข้ามรอบ') 3) รอแจกไพ่ 4) ถึงตาคุณกด 'จั่ว' (ขอเพิ่ม 1 ใบ) หรือ 'อยู่' (พอแล้ว) 5) ดูผล แล้วรอบใหม่เริ่มเอง\n\n"
             "กติกาป๊อกเด้ง (เหรียญเสมือน)\n"
             "• ไพ่ 52 ใบ A=1, 2-9 ตามแต้ม, 10 J Q K = 0 แต้มรวมเอาหลักหน่วย\n"
             "• แจกคนละ 2 ใบ ถ้ารวมได้ 8 หรือ 9 = ป๊อก ไม่ต้องจั่ว\n"
             "• ผลัดกันเล่นทีละคนตามที่นั่ง ไม่ป๊อกจั่วเพิ่มได้ 1 ใบ หมดเวลา = อยู่ เจ้ามือบอทจั่วเมื่อได้ 0-4 แต้ม ถ้าเจ้ามือป๊อกทุกคนเปิดทันที\n"
             "• เด้ง: 2 ใบดอกเดียวกัน/เลขเดียวกัน = 2 เด้ง, 3 ใบดอกเดียวกัน/เรียง/เซียน (J Q K) = 3 เด้ง, ตอง/สเตรทฟลัช = 5 เด้ง\n"
             "• แต้มมากกว่าชนะ แต้มเท่ากันถ้าฝ่ายหนึ่งป๊อก (2 ใบ) ชนะอีกฝ่ายที่ได้แต้มเท่ากันด้วย 3 ใบ นอกนั้นเสมอ ผู้ชนะได้เดิมพัน x จำนวนเด้งของฝ่ายชนะ\n"
             "• เจ้ามือเริ่ม 40,000 ผู้เล่นเริ่มคนละ 10,000 โต๊ะรองรับสูงสุด 8 คน ที่นั่งไม่ครบ 4 จะมีบอทมานั่งแทน เจ้ามือหมดเหรียญ = จบโต๊ะ\n"
             "• เป็นเกมเหรียญเสมือน เล่นเอาสนุก ไม่มีการเล่นพนันเงินจริง")
CW, CH, GAP = 40, 56, 4  # ขนาดไพ่ (ของเรา x1.3)
POK_CHIPS = ((100, "#d32f2f"), (500, "#1976d2"), (1000, "#2e7d32"), (5000, "#6a1b9a"))
POK_AV = ("#e53935", "#fb8c00", "#fdd835", "#43a047", "#00acc1", "#3949ab", "#8e24aa", "#6d4c41")

def poker_window(ip, myname=None):  # หน้าต่างเกมสไตล์เกมมือถือ: โต๊ะรองรับ 8 ที่นั่ง อวาตาร์ ชิป ปุ่มใหญ่ แอนิเมชันแจกไพ่ และข้อความบอกตา
    import math
    root = ROOT[0]
    if root is None: return
    win = tk.Toplevel(root)
    win.title("Play poker — ป๊อกเด้ง"); win.configure(bg="#150a2e"); win.resizable(True, True); win.minsize(1000, 560)
    try: win.geometry(f"{min(1560, win.winfo_screenwidth() - 60)}x{min(800, win.winfo_screenheight() - 100)}+20+20")
    except Exception: win.geometry("1500x800")
    try: win.iconbitmap(ICON_PATH)
    except Exception: pass
    KK = {"k": 1.0}
    F = lambda n, b=False: (RFONT(), max(6, round(n * KK["k"])), "bold") if b else (RFONT(), max(6, round(n * KK["k"])))
    W, H, CX, CY = 1100, 780, 550, 318
    st = {"m": None, "t0": time.time(), "sock": None, "dead": False, "shown": {}, "flip": {}, "q": [], "busy": False, "prevhid": {},
          "lay": {}, "bet": POK_MIN, "note": "", "pop": 0, "throw": 0.0, "bank0": None, "bdelta": 0, "fr": 0, "ids": None, "me": "", "olist": []}
    PB, PF = "#1a1040", "#2a1a5e"
    left = tk.Frame(win, bg=PB, width=210); left.pack(side="left", fill="y"); left.pack_propagate(False)
    right = tk.Frame(win, bg=PB, width=260); right.pack(side="right", fill="y"); right.pack_propagate(False)
    mid = tk.Frame(win, bg="#150a2e"); mid.pack(side="left", fill="both", expand=True)
    cv = tk.Canvas(mid, width=W, height=H, bg="#150a2e", highlightthickness=0); cv.pack(expand=True)
    DECK = (710, 112)

    def rr(x1, y1, x2, y2, r, **kw):  # สี่เหลี่ยมมุมมน (ธีม Retro = มุมเหลี่ยม)
        if RETRO[0]: return cv.create_polygon([x1, y1, x2, y1, x2, y2, x1, y2], **kw)
        p = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return cv.create_polygon(p, smooth=True, splinesteps=10, **kw)
    # ---- พื้นหลัง/โต๊ะ ----
    def build_bg():
        cv.delete("bg"); old_ids = set(cv.find_all())
        for i in range(52):
            t = i / 51
            col = "#%02x%02x%02x" % (int(26 + 4 * t), int(10 + 28 * t), int(58 + 30 * t))
            cv.create_rectangle(0, i * H / 52, W, (i + 1) * H / 52 + 1, fill=col, outline=col)
        cv.create_oval(34, 62, W - 34, 580, fill="#0a0420", outline="")
        cv.create_oval(40, 66, W - 40, 572, fill="#3b2a78", outline="#8a6cf0", width=5)
        cv.create_oval(66, 90, W - 66, 548, fill="#0c7a48", outline="#e6c34a", width=4)
        cv.create_oval(190, 112, W - 190, 330, fill="#0f8a52", outline="")
        cv.create_oval(120, 130, W - 120, 508, outline="#139a5d", width=2)
        cv.create_text(CX, 318, text="ป๊อกเด้ง", fill="#139a5d", font=F(54, True))
        for k in range(3):
            rr(DECK[0] - 24 + k * 2, DECK[1] - 32 - k * 2, DECK[0] + 24 + k * 2, DECK[1] + 32 - k * 2, 6, fill="#2a3f9a", outline="#ffffff", width=2)
        cv.create_text(DECK[0], DECK[1], text="♣", fill="#9fb4ff", font=F(20))
        for i_ in set(cv.find_all()) - old_ids: cv.addtag_withtag("bg", f"{i_}")
        cv.scale("bg", 0, 0, KK["k"], KK["k"]); cv.tag_lower("bg")
    build_bg()

    def fit(tag):
        k = KK["k"]
        if k != 1.0: cv.scale(tag, 0, 0, k, k)

    # ---- เจ้ามือ 8-bit (ตัวละครออริจินัล): พิกเซล 24x22 ----
    DPAL = {"K": "#1a1020", "S": "#f2c08a", "s": "#d9a066", "H": "#3a2a1a", "V": "#43c46f", "v": "#2a8a4c", "W": "#ffffff", "R": "#d32f2f",
            "B": "#2b2b45", "Y": "#ffd54f", "M": "#4a3320", "C": "#4fc3f7"}
    DBASE = ["......KKKKKKKKKKKK......", ".....KvvvvvvvvvvvvK.....", ".....KVVVVVVVVVVVVK.....", "....KKvvvvvvvvvvvvKK....",
             "....KHHSSSSSSSSSSHHK....", ".....KSSSSSSSSSSSSK.....", ".....KSKKSSSSSSKKSK.....", ".....KSSSSSSSSSSSSK.....",
             ".....KSSSSSSssSSSSK.....", ".....KSMMMMMMMMMMSK.....", ".....KSSSKKKKKKSSSK.....", "......KSSSSSSSSSSK......",
             ".......KKKKKKKKKK.......", "........KSSSSSSK........", "..KKBBBBWWRRRRWWBBBBKK..", ".KBBBBBBBWWWWWWBBBBBBBK.",
             ".KBBBBBBBWWYWWWBBBBBBBK.", ".KBBBBBBBWWWWWWBBBBBBBK.", ".KBBBBBBBWWYWWWBBBBBBBK.", ".KBBBBBBBWWWWWWBBBBBBBK.",
             ".KBBBBBBBWWYWWWBBBBBBBK.", ".KBBBBBBBBBBBBBBBBBBBBK."]
    DBASE = [r.ljust(24, ".")[:24] for r in DBASE]
    def dsprite(x, y, px, state, fr):
        g = [list(r) for r in DBASE]
        def put(r, c0, c1, ch):
            for c in range(max(0, c0), min(23, c1) + 1): g[r][c] = ch
        eyes = lambda r, ch: [put(r, 7, 8, ch), put(r, 15, 16, ch)]
        if state == "blink" or (state in ("idle", "shuffle", "throw") and fr % 24 in (0, 1)): eyes(6, "S"); eyes(7, "K")
        dx = 0
        if state == "shuffle":
            if fr % 2 == 0: put(19, 6, 8, "S"); put(19, 15, 17, "S"); put(20, 6, 8, "S"); put(20, 15, 17, "S"); put(19, 9, 14, "W")
            else: put(18, 8, 10, "S"); put(18, 13, 15, "S"); put(17, 10, 13, "W"); put(16, 11, 12, "W")
        elif state == "throw":
            t = min(23, 18 + (fr % 4) * 2); put(17, 15, t, "S"); put(16, t - 1, t, "W"); put(15, t - 1, t, "W")
        elif state == "think":
            if fr % 6 < 3: g[6][7], g[6][8], g[6][15], g[6][16] = "K", "S", "K", "S"
            else: g[6][7], g[6][8], g[6][15], g[6][16] = "S", "K", "S", "K"
        elif state == "laugh":
            dx = px if fr % 2 else 0
            eyes(6, "S"); eyes(5, "K"); put(10, 8, 13, "K"); put(11, 8, 13, "R"); g[11][8] = g[11][13] = "K"
            put(19, 1, 3, "S"); put(20, 1, 3, "S")
        elif state == "shock":
            dx = px // 2 if fr % 2 else 0
            eyes(6, "W"); eyes(7, "W"); g[7][8] = g[7][15] = "K"; put(10, 10, 11, "K"); put(11, 10, 11, "K")
            put(4, 19, 19, "C"); put(5, 19, 19, "C"); put(6, 20, 20, "C") if fr % 4 < 2 else put(7, 20, 20, "C")
            for r in (15, 16, 17): put(r, 0, 2, "S"); put(r, 21, 23, "S")
        x0, y0 = x - 12 * px + dx, y - 11 * px
        for r, row in enumerate(g):
            c = 0
            while c < 24:
                ch = row[c]
                if ch == ".": c += 1; continue
                c2 = c
                while c2 + 1 < 24 and row[c2 + 1] == ch: c2 += 1
                cv.create_rectangle(x0 + c * px, y0 + r * px, x0 + (c2 + 1) * px, y0 + (r + 1) * px, fill=DPAL[ch], outline="", tags="dealer")
                c = c2 + 1
    def dstate():
        m = st["m"]; fr = st["fr"]
        if not m: return "idle", ""
        ph = m["phase"]
        if time.time() - st["throw"] < 0.45 or ph == "deal": return "throw", "แจกไพ่!"
        if ph == "bet": return "shuffle", ("ลงเดิมพันเลย!", "มาเสี่ยงดวงกัน~", "ใครกล้าบ้าง?")[(fr // 14) % 3]
        if ph == "play": return "think", "จั่วหรืออยู่ดี~"
        if ph == "dealer": return "think", "ตาข้าแล้ว..."
        d = st["bdelta"]
        if d > 0: return "laugh", "ฮ่าๆๆ กินเรียบ!"
        if d < 0: return "shock", "โอ๊ย! เสียหนัก!"
        return "idle", "เสมอกัน"
    def draw_dealer():
        cv.delete("dealer")
        stt, say = dstate()
        dsprite(CX, 104, 4, stt, st["fr"])
        if say:
            w = max(110, len(say) * 11 + 20)
            rr(604, 59, 604 + w, 83, 10, fill="#fff8e1", outline="#1a1020", width=2, tags="dealer")
            cv.create_polygon(604, 66, 594, 72, 606, 74, fill="#fff8e1", outline="#1a1020", tags="dealer")
            cv.create_text(604 + w / 2, 71, text=say, fill="#1a1020", font=F(11, True), tags="dealer")
        fit("dealer")
    def dealer_tick():
        if st["dead"]: return
        st["fr"] += 1; draw_dealer(); win.after(180, dealer_tick)

    # ---- แผงซ้าย: คนออนไลน์ + เชิญ / แผงขวา: แชท ----
    tk.Label(left, text="คนออนไลน์", bg=PB, fg="#ffe082", font=(RFONT(), 13, "bold")).pack(anchor="w", padx=12, pady=(12, 0))
    lb_cnt = tk.Label(left, text="", bg=PB, fg="#b0a8d8", font=(RFONT(), 9)); lb_cnt.pack(anchor="w", padx=12)
    lbx = tk.Listbox(left, bg="#110a2b", fg="#ffffff", selectbackground="#6a3fd6", selectforeground="#ffffff", font=(RFONT(), 11), relief="flat",
                     highlightthickness=0, activestyle="none", exportselection=False)
    lbx.pack(fill="both", expand=True, padx=10, pady=8)
    inv_msg = tk.Label(left, text="เลือกชื่อแล้วกดเชิญ\n(ต้องเป็นรุ่น 8.0.0 ขึ้นไป)", bg=PB, fg="#b0a8d8", font=(RFONT(), 9), wraplength=190, justify="left")
    inv_msg.pack(side="bottom", anchor="w", padx=12, pady=(0, 10))
    def do_invite():
        i = lbx.curselection()
        if not i or i[0] >= len(st["olist"]): inv_msg.config(text="คลิกเลือกชื่อก่อน"); return
        uid, ips, ok_ver, _t = st["olist"][i[0]]
        if not ok_ver: inv_msg.config(text="เครื่องนี้ยังเป็นรุ่นเก่า ต้องอัปเดตเป็น 8.0.0 ก่อนถึงจะรับเชิญได้"); return
        who = _t
        me_nm = st["me"] or myname or username() or HOSTNAME
        host_ip = "" if ip == "127.0.0.1" else ip
        inv_msg.config(text="กำลังส่งคำเชิญ ...")
        def work():
            err = None
            for tip in ips:
                err = poker_invite_send(tip, me_nm, host_ip)
                if err is None: break
            root.after(0, lambda: inv_msg.config(text=("ส่งคำเชิญให้ " + who.lstrip("● ").split("  ")[0] + " แล้ว") if err is None else "ส่งไม่ได้: " + err[:60]))
        threading.Thread(target=work, daemon=True).start()
    tk.Button(left, text="เชิญเข้าโต๊ะ", bg="#2e9e3a", fg="#ffffff", activebackground="#3cb84a", font=(RFONT(), 12, "bold"), relief="flat", pady=6, command=do_invite).pack(side="bottom", fill="x", padx=10)
    lbx.bind("<Double-1>", lambda e: do_invite())
    def refresh_online():
        if st["dead"]: return
        now = time.time(); rows = []
        seated = set((st["m"] or {}).get("ips", ()))
        with peers_lock:
            for uid, v in peers.items():
                if now - v.get("last", 0) > 9 or v.get("stealth"): continue
                ips = sorted(set(v.get("ips", ())) | ({v["ip"]} if v.get("ip") else set()))
                try: new = ver_tuple(v.get("ver", "")) >= (8, 0, 0)
                except Exception: new = False
                tag = "  ★เจ้าของโต๊ะ" if ip in ips else "  (อยู่ในโต๊ะ)" if seated & set(ips) else "" if new else "  (รุ่นเก่า)"
                rows.append((uid, ips, new, "● " + (v.get("code") or v.get("host") or "?") + tag))
        rows.sort(key=lambda r: r[3])
        if [r[3] for r in rows] != [r[3] for r in st["olist"]]:
            cur = lbx.curselection(); keep = st["olist"][cur[0]][0] if cur and cur[0] < len(st["olist"]) else None
            st["olist"] = rows; lbx.delete(0, "end")
            for r in rows: lbx.insert("end", r[3])
            for i, r in enumerate(rows):
                lbx.itemconfig(i, fg="#ffffff" if r[2] else "#8a84ad")
                if r[0] == keep: lbx.selection_set(i)
        else: st["olist"] = rows
        lb_cnt.config(text=f"{len(rows)} เครื่อง (ไม่นับเครื่องนี้)")
        win.after(2000, refresh_online)
    tk.Label(right, text="แชทในโต๊ะ", bg=PB, fg="#ffe082", font=(RFONT(), 13, "bold")).pack(anchor="w", padx=12, pady=(12, 4))
    crow2 = tk.Frame(right, bg=PB); crow2.pack(side="bottom", fill="x", padx=10, pady=10)
    chat_in = tk.Entry(crow2, font=(RFONT(), 11), bg="#110a2b", fg="#ffffff", insertbackground="#ffffff", relief="flat")
    chat_in.pack(side="left", fill="x", expand=True, ipady=5)
    def chat_send(_e=None):
        t = chat_in.get().strip()
        if t: send({"a": "chat", "m": t[:100]}); chat_in.delete(0, "end")
    tk.Button(crow2, text="ส่ง", bg="#6a3fd6", fg="#ffffff", relief="flat", font=(RFONT(), 10, "bold"), command=chat_send).pack(side="right", padx=(6, 0), ipady=2)
    chat_in.bind("<Return>", chat_send)
    chat_txt = tk.Text(right, bg="#110a2b", fg="#e8e4ff", font=(RFONT(), 10), wrap="word", relief="flat", highlightthickness=0, state="disabled", width=10)
    chat_txt.pack(fill="both", expand=True, padx=10)
    chat_txt.tag_config("nm", foreground="#ffd54f", font=(RFONT(), 10, "bold")); chat_txt.tag_config("me", foreground="#4dd0e1", font=(RFONT(), 10, "bold"))
    chat_txt.tag_config("sys", foreground="#9c95c8", font=(RFONT(), 9, "italic"))
    def chat_add(who, text, kind="u"):
        t = chat_txt; t.config(state="normal")
        if kind == "sys": t.insert("end", text + "\n", "sys")
        else: t.insert("end", who + ": ", "me" if who == st["me"] else "nm"); t.insert("end", text + "\n")
        n = int(t.index("end-1c").split(".")[0])
        if n > 300: t.delete("1.0", f"{n - 300}.0")
        t.config(state="disabled"); t.see("end")

    def card(x, y, c, tag, sx=1.0, back=None, big=1.0):
        big = 1.3 if big is True else (1.0 if big is False else big)
        w0, h0 = CW * big, CH * big
        w = max(2, w0 * sx) / 2
        if back is None: back = c is None
        if back:
            rr(x - w, y - h0 / 2, x + w, y + h0 / 2, 6, fill="#2a3f9a", outline="#ffffff", width=2, tags=tag)
            if sx > 0.5: cv.create_text(x, y, text="♣", fill="#9fb4ff", font=F(int(15 * big)), tags=tag)
        else:
            col = "#c62828" if c[1] in (1, 2) else "#111111"
            rr(x - w, y - h0 / 2, x + w, y + h0 / 2, 6, fill="#ffffff", outline="#cccccc", width=2, tags=tag)
            if sx > 0.6:
                cv.create_text(x, y - h0 * 0.17, text=_POK_R[c[0]].replace("T", "10"), fill=col, font=F(int(13 * big) + 1, True), tags=tag)
                cv.create_text(x, y + h0 * 0.19, text=_POK_S[c[1]], fill=col, font=F(int(16 * big)), tags=tag)

    def avatar(x, y, r, name, tag, ring=False, arc=None, crown=False, bot=False):
        col = POK_AV[sum(map(ord, name)) % len(POK_AV)]
        if ring: cv.create_oval(x - r - 7, y - r - 7, x + r + 7, y + r + 7, outline="#ffeb3b", width=4, tags=tag)
        if arc is not None: cv.create_arc(x - r - 12, y - r - 12, x + r + 12, y + r + 12, start=90, extent=-359.9 * arc, style="arc", outline="#ff7043", width=5, tags=tag)
        cv.create_oval(x - r, y - r, x + r, y + r, fill=col, outline="#ffffff", width=3, tags=tag)
        cv.create_text(x, y + 1, text=name[:1].upper(), fill="#ffffff", font=F(int(r * 0.9), True), tags=tag)
        if crown: cv.create_text(x, y - r - 12, text="♛", fill="#ffd54f", font=F(22, True), tags=tag)
        if bot: rr(x + r - 14, y + r - 12, x + r + 12, y + r + 4, 5, fill="#37474f", outline="#ffffff", tags=tag); cv.create_text(x + r - 1, y + r - 4, text="BOT", fill="#ffffff", font=F(7, True), tags=tag)

    def pill(x, y, w, text, fg, bg, tag, size=11, bold=True, outline=""):
        rr(x - w / 2, y - 11, x + w / 2, y + 11, 11, fill=bg, outline=outline, tags=tag)
        cv.create_text(x, y, text=text, fill=fg, font=F(size, bold), tags=tag)

    def me_p():
        m = st["m"]
        if m:
            for p in m["players"]:
                if p["id"] == m["you"]: return p
    def me_coins():
        p = me_p(); return p["coins"] if p else 0

    def layout(m):  # ที่นั่งรอบโต๊ะ (เรานั่งล่างกลาง เจ้ามือบนกลาง ที่เหลือซ้าย/ขวา) รองรับ 8 ที่นั่ง
        ps = m["players"]
        idx = next((i for i, p in enumerate(ps) if p["id"] == m["you"]), 0)
        S = ps[idx:] + ps[:idx]
        rest = S[1:]; k = len(rest)
        nl, nr = (k + 1) // 2, k // 2
        lin = lambda a, b, n: [190 if False else (a + b) / 2] if n == 1 else [a + (b - a) * i / (n - 1) for i in range(n)]
        angs = lin(150, 225, nl) + lin(315, 390, nr) if k > 2 else ([190, 350][:k] if k else [])
        if k > 2: angs = (lin(150, 225, nl) if nl > 1 else [190]) + (lin(315, 390, nr) if nr > 1 else [350])
        lay = {}
        def put(p, x, y, big):
            if big: cx_, cy_, sc, chip = CX, y - 100, 1.3, (CX + 120, y - 100)
            else:
                sg = 1 if x < CX else -1
                cx_, cy_, sc = x + sg * 136, y - 4, 0.8
                chip = (cx_, cy_ - 36)
            lay[p["id"]] = {"x": x, "y": y, "big": big, "s": sc, "cx": cx_, "cy": cy_, "chip": chip, "p": p}
        put(S[0], CX, 484, True)
        for p, a in zip(rest, angs):
            t = math.radians(a)
            put(p, CX + 470 * math.cos(t), CY + 215 * math.sin(t) + 2, False)
        lay["d"] = {"x": CX, "y": 112, "big": False, "s": 1.0, "cx": CX, "cy": 214}
        st["lay"] = lay
        return lay
    def slot(key, i):
        L = st["lay"].get(key)
        if not L: return CX, CY
        gap = CW * L["s"] + GAP
        return L["cx"] + (i - 0.5) * gap, L["cy"]

    def button(key, x, y, w, h, text, color, enabled, cb, size=15):
        cv.tag_unbind(key, "<Button-1>")
        col = color if enabled else "#4a4560"
        rr(x - w / 2, y - h / 2 + 4, x + w / 2, y + h / 2 + 4, 14, fill="#0c0620", outline="", tags=("ui", key))
        rr(x - w / 2, y - h / 2, x + w / 2, y + h / 2, 14, fill=col, outline="#ffffff" if enabled else "#6b6585", width=2, tags=("ui", key))
        rr(x - w / 2 + 5, y - h / 2 + 4, x + w / 2 - 5, y - h / 2 + h * 0.42, 9, fill="#ffffff", outline="", stipple="gray25" if enabled else "gray12", tags=("ui", key))
        cv.create_text(x, y, text=text, fill="#ffffff" if enabled else "#9a94b0", font=F(size, True), tags=("ui", key))
        if enabled: cv.tag_bind(key, "<Button-1>", lambda e: cb())

    def chipbtn(key, x, y, val, color, enabled, cb):
        cv.tag_unbind(key, "<Button-1>")
        c = color if enabled else "#4a4560"
        cv.create_oval(x - 30, y - 26, x + 30, y + 34, fill="#0c0620", outline="", tags=("ui", key))
        cv.create_oval(x - 30, y - 30, x + 30, y + 30, fill=c, outline="#ffffff", width=3, tags=("ui", key))
        cv.create_oval(x - 22, y - 22, x + 22, y + 22, outline="#ffffff", width=2, dash=(5, 4), tags=("ui", key))
        cv.create_text(x, y, text=f"{val:,}", fill="#ffffff", font=F(11, True), tags=("ui", key))
        if enabled: cv.tag_bind(key, "<Button-1>", lambda e: cb())

    def send(o):
        try: st["sock"].sendall((json.dumps(o) + "\n").encode("utf-8"))
        except Exception: pass
    def go(o, snd=None):
        send(o)
        if snd: pok_snd(snd)

    def draw_banner():
        draw_banner0(); fit("banner")
    def draw_banner0():
        cv.delete("banner")
        m = st["m"]
        if not m:
            tx, bg, fg = st["note"] or "กำลังเชื่อมต่อ ...", "#2a1a5e", "#ffffff"
        else:
            left = max(0, m["left"] - int(time.time() - st["t0"]))
            ph, turn = m["phase"], m["turn"]
            if st["note"]: tx, bg, fg = st["note"], "#b71c1c", "#ffffff"
            elif ph == "play":
                who = next((p for p in m["players"] if p["id"] == turn), None)
                mine = turn == m["you"]
                tx = ("ตาของคุณ — จั่ว หรือ อยู่?" if mine else f"ตาของ {who['name'] if who else ''}") + f"  ⏱{left}"
                bg, fg = ("#ffd54f", "#3e2714") if mine else ("#2a1a5e", "#ffe082")
            elif ph == "dealer": tx, bg, fg = "ตาของเจ้ามือ (บอท)", "#2a1a5e", "#ffe082"
            elif ph == "deal": tx, bg, fg = "กำลังแจกไพ่ ...", "#2a1a5e", "#ffffff"
            elif ph == "bet": tx, bg, fg = f"ลงเดิมพันได้เลย  ⏱{left}", "#2a1a5e", "#ffffff"
            else: tx, bg, fg = m["msg"], "#2a1a5e", "#ffe082"
        tw = max(300, len(tx) * 17)
        rr(CX - tw / 2, 12, CX + tw / 2, 56, 20, fill=bg, outline="#ffd54f", width=3, tags="banner")
        cv.create_text(CX, 34, text=tx, fill=fg, font=F(17, True), tags="banner")

    def render():
        render0(); fit("st"); fit("ui")
    def render0():
        cv.delete("st"); cv.delete("ui")
        m = st["m"]
        draw_banner()
        if not m: return
        mp = me_p()
        lay = layout(m)
        # HUD
        pill(90, 34, 130, f"รอบที่ {m['round']}", "#ffffff", "#2a1a5e", "ui", 12, True, "#8a6cf0")
        cv.create_oval(962, 22, 986, 46, fill="#ffca28", outline="#fff3b0", width=2, tags="ui"); cv.create_text(974, 34, text="$", fill="#7a5a00", font=F(12, True), tags="ui")
        pill(1030, 34, 100, f"{mp['coins']:,}" if mp else "-", "#ffe082", "#2a1a5e", "ui", 13, True, "#8a6cf0")
        button("b_snd", 870, 34, 84, 32, "เสียง " + ("ปิด" if cfg.get("poker_mute") else "เปิด"), "#455a64", True, snd_toggle, 11)
        button("b_rul", 770, 34, 84, 32, "กติกา", "#455a64", True, rules, 11)
        # เจ้ามือ
        D = lay["d"]
        pill(D["x"] - 122, D["y"] + 4, 120, "เจ้ามือ (บอท)", "#ffffff", "#1a1040", "st", 10)
        pill(D["x"] - 122, D["y"] + 30, 120, f"{m['bank']:,}", "#ffe082", "#3b2a00", "st", 11, True, "#e6c34a")
        sh = st["shown"].get("d", 0)
        for i, c in enumerate(m["dealer"]["cards"][:sh]):
            x, y = slot("d", i); fp = st["flip"].get("d")
            if fp is not None: card(x, y, c, "st", *((1 - 2 * fp, True) if fp < 0.5 else (2 * fp - 1, False)))
            else: card(x, y, c, "st")
        if m["dealer"]["lab"] and st["flip"].get("d") is None and sh >= len(m["dealer"]["cards"]):
            pill(D["cx"], D["cy"] + 46, 150, m["dealer"]["lab"], "#ffe082", "#1a1040", "st", 11)
        # ผู้เล่น
        for key, L in lay.items():
            if key == "d": continue
            p, x, y = L["p"], L["x"], L["y"]
            me = p["id"] == m["you"]; turn = p["id"] == m["turn"] and m["phase"] == "play"
            frac = max(0.0, min(1.0, (m["left"] - (time.time() - st["t0"])) / (POK_T_TURN + 0.6))) if turn else None
            avatar(x, y, 30 if me else 26, p["name"], "st", ring=turn, arc=frac, bot=p["bot"])
            pill(x, y + (44 if me else 40), 150 if me else 134, p["name"] + (" (คุณ)" if me else "") + "  " + f"{p['coins']:,}", "#ffe082", "#1a1040", "st", 10, True, "#ffd54f" if me else "#8a6cf0")
            sh = st["shown"].get(p["id"], 0)
            for j, c in enumerate(p["cards"][:sh]):
                cx_, cy_ = slot(p["id"], j); fp = st["flip"].get(p["id"])
                if fp is not None: card(cx_, cy_, c, "st", *((1 - 2 * fp, True) if fp < 0.5 else (2 * fp - 1, False)), big=L["s"])
                else: card(cx_, cy_, c, "st", big=L["s"])
            ch = CH * L["s"]
            r = p["res"]; done = st["flip"].get(p["id"]) is None and sh >= len(p["cards"])
            fin = bool(r) and m["phase"] in ("result", "over")
            if done and (p["lab"] or fin):
                txt = p["lab"]
                if fin:
                    t2 = {"win": f"+{r['amt']:,}", "lose": f"-{r['amt']:,}", "tie": "เสมอ"}[r["o"]]
                    txt = (txt + "  " if txt else "") + t2
                pill(L["cx"], L["cy"] + ch / 2 + 14, max(100, len(txt) * 7 + 22), txt, "#ffffff" if fin else "#ffe082",
                     {"win": "#2e7d32", "lose": "#c62828", "tie": "#546e7a"}[r["o"]] if fin else "#1a1040", "st", 10, True, "#ffffff" if fin else "")
            if p["bet"] and m["phase"] not in ("result", "over"):
                bx, by = L["chip"]
                cv.create_oval(bx - 15, by - 15, bx + 15, by + 15, fill="#d32f2f" if p["bet"] < 500 else "#1976d2" if p["bet"] < 1000 else "#2e7d32" if p["bet"] < 5000 else "#6a1b9a", outline="#ffffff", width=2, tags="st")
                cv.create_text(bx, by + 1, text=f"{p['bet']:,}" if p["bet"] < 1000 else f"{p['bet']/1000:g}k", fill="#ffffff", font=F(8, True), tags="st")
            elif p["pass"] and m["phase"] == "bet": pill(L["cx"], L["cy"], 80, "ข้ามรอบ", "#cfcfcf", "#1a1040", "st", 10)
        # ปุ่มด้านล่าง
        rr(0, 592, W, H, 0, fill="#0c0620", outline="", tags="ui")
        cv.create_line(0, 592, W, 592, fill="#8a6cf0", width=3, tags="ui")
        coins = mp["coins"] if mp else 0
        bet_ok = m["phase"] == "bet" and mp is not None and coins > 0
        play_ok = m["phase"] == "play" and m["turn"] == m["you"]
        st["bet"] = max(min(POK_MIN, coins) if coins else 0, min(st["bet"], coins))
        if m["phase"] in ("bet", "deal"):
            pill(CX, 622, 240, f"เดิมพัน  {st['bet']:,}", "#ffe082", "#2a1a5e", "ui", 15, True, "#e6c34a")
            button("b_all", 372, 622, 86, 34, "ทุ่มหมด", "#8e24aa", bet_ok, lambda: setbet(coins), 11)
            button("b_clr", 728, 622, 86, 34, "ล้าง", "#546e7a", bet_ok, lambda: setbet(POK_MIN), 11)
            for i, (v, col) in enumerate(POK_CHIPS):
                chipbtn(f"c{v}", 427 + i * 82, 678, v, col, bet_ok, lambda v=v: setbet(st["bet"] + v))
            button("b_pass", 215, 702, 150, 56, "ข้ามรอบ", "#6d4c41", bet_ok, lambda: go({"a": "pass"}), 14)
            button("b_bet", 880, 702, 230, 60, "ลงเดิมพัน", "#2e9e3a", bet_ok, lambda: go({"a": "bet", "v": st["bet"]}, "bet"), 18)
            if m["owner"]: button("b_deal", 215, 650, 150, 38, "แจกไพ่เลย", "#00838f", m["phase"] == "bet", lambda: go({"a": "deal"}), 12)
        else:
            button("b_hit", 300, 700, 250, 76, "จั่ว", "#1976d2", play_ok and mp is not None and len(mp["cards"]) == 2, lambda: go({"a": "hit"}, "hit"), 24)
            button("b_stand", 800, 700, 250, 76, "อยู่", "#ef6c00", play_ok, lambda: go({"a": "stand"}, "stand"), 24)
            if m["owner"] and m["phase"] == "over": button("b_new", 550, 700, 260, 60, "เริ่มโต๊ะใหม่", "#c62828", True, lambda: go({"a": "restart"}), 16)
        hint = ""
        ph = m["phase"]; left = max(0, m["left"] - int(time.time() - st["t0"]))
        if mp is not None and mp["coins"] <= 0 and ph != "result": hint = "เหรียญหมด — ปิดแล้วเข้าโต๊ะใหม่เพื่อเริ่ม 10,000 อีกครั้ง"
        elif ph == "bet":
            if mp is not None and mp["pass"]: hint = "คุณข้ามรอบนี้ — รอรอบถัดไป"
            elif mp is not None and mp["bet"] > 0: hint = f"ลงเดิมพัน {mp['bet']:,} แล้ว — รอคนอื่นลง (เจ้าของโต๊ะกด 'แจกไพ่เลย' ได้)"
            else: hint = "① เลือกชิปเพิ่มเดิมพัน   ② กด 'ลงเดิมพัน'   (ไม่เล่นรอบนี้ กด 'ข้ามรอบ')"
        elif ph == "deal": hint = "กำลังแจกไพ่ ..."
        elif ph == "play":
            lab = (mp or {}).get("lab", "")
            if m["turn"] == m["you"]: hint = f"ตาคุณ! ตอนนี้ {lab} — กด 'จั่ว' = ขอไพ่เพิ่ม 1 ใบ   กด 'อยู่' = พอแล้ว"
            elif mp is not None and mp["in"] and mp["done"] and lab.startswith("ป๊อก"): hint = f"คุณ {lab} — ไม่ต้องจั่ว รอคนอื่นเล่น"
            elif mp is not None and mp["in"]: hint = f"คุณ {lab} — รอถึงตาคุณ ({left} วิ)" if False else f"คุณ {lab} — รอถึงตาของคุณ"
            else: hint = "รอบนี้คุณไม่ได้ลงเดิมพัน — ดูเพื่อนเล่นไปก่อน"
        elif ph == "dealer": hint = "เจ้ามือกำลังเล่น ... แล้วจะเปิดไพ่ทุกคน"
        elif ph == "result": hint = f"ดูผลรอบนี้ได้เลย — รอบใหม่เริ่มใน {left} วินาที (ไพ่จะถูกเก็บเอง)"
        elif ph == "over": hint = "เจ้ามือหมดเหรียญ — เจ้าของโต๊ะกด 'เริ่มโต๊ะใหม่'"
        if hint: pill(CX, 574, max(360, len(hint) * 9 + 30), hint, "#ffffff", "#0c0620", "ui", 12, True, "#ffd54f")
    def setbet(v):
        m = st["m"]; coins = me_coins()
        st["bet"] = max(min(POK_MIN, coins), min(int(v), coins)); render()
    def snd_toggle():
        cfg["poker_mute"] = not cfg.get("poker_mute", False); save_config(cfg); pok_snd("bet"); render()
    def rules():
        w = tk.Toplevel(win); w.title("กติกา"); w.configure(bg="#2a1a5e")
        tk.Label(w, text=POK_RULES, bg="#2a1a5e", fg="white", font=F(12), justify="left", wraplength=640, padx=18, pady=14).pack()

    # ---- แอนิเมชัน ----
    def run_q():
        if st["busy"] or st["dead"] or not st["q"]: return
        key, idx = st["q"].pop(0)
        st["busy"] = True
        ex, ey = slot(key, idx)
        big = st["lay"].get(key, {}).get("s", 1.0)
        tag = f"fly{time.time_ns()}"; st["throw"] = time.time()
        sx, sy = DECK; card(sx, sy, None, tag, big=big); fit(tag)
        steps = 9
        def stepf(k):
            if st["dead"]: return
            if k < steps:
                cv.move(tag, (ex - sx) / steps * KK["k"], (ey - sy) / steps * KK["k"]); win.after(26, stepf, k + 1)
            else:
                cv.delete(tag); pok_snd("deal")
                st["shown"][key] = idx + 1; st["busy"] = False
                render(); win.after(40, run_q)
        stepf(0)
    def flip_run(keys):
        pok_snd("flip")
        for k in keys: st["flip"][k] = 0.0
        def sf(n):
            if st["dead"]: return
            if n > 9:
                for k in keys: st["flip"].pop(k, None)
            else:
                for k in keys: st["flip"][k] = n / 9
            render()
            if n <= 9: win.after(32, sf, n + 1)
        sf(0)
    def popup(txt, col):  # ข้อความชนะ/แพ้ ใหญ่กลางโต๊ะ + confetti
        import random
        cv.delete("pop")
        for dx, dy, c in ((3, 3, "#000000"), (0, 0, col)): cv.create_text(CX + dx, 330 + dy, text=txt, fill=c, font=F(48, True), tags="pop")
        if col == "#69f0ae":
            for _ in range(36):
                x0 = random.randint(120, 980); cc = random.choice(["#ffeb3b", "#ff5252", "#40c4ff", "#69f0ae", "#e040fb"])
                it = cv.create_rectangle(x0, 80, x0 + 8, 92, fill=cc, outline="", tags="pop")
                def fall(it=it, n=0, vx=random.randint(-3, 3), vy=random.randint(6, 12)):
                    if st["dead"] or n > 40: return
                    cv.move(it, vx * KK["k"], vy * KK["k"]); win.after(35, fall, it, n + 1, vx, vy)
                win.after(random.randint(0, 400), fall)
        fit("pop")
        win.after(2400, lambda: cv.delete("pop"))
    def sweep():  # เก็บไพ่ทั้งโต๊ะกลับกองก่อนเริ่มรอบใหม่
        n = 0
        for key, cnt in list(st["shown"].items()):
            for i in range(cnt):
                x, y = slot(key, i); tg = f"sw{time.time_ns()}{n}"; n += 1
                card(x, y, None, tg, big=st["lay"].get(key, {}).get("s", 1.0)); fit(tg)
                def mv(k=0, tg=tg, x=x, y=y):
                    if st["dead"]: return
                    if k < 8: cv.move(tg, (DECK[0] - x) / 8 * KK["k"], (DECK[1] - y) / 8 * KK["k"]); win.after(28, mv, k + 1, tg, x, y)
                    else: cv.delete(tg)
                mv()
        if n: pok_snd("flip")
        st["shown"].clear(); st["prevhid"].clear(); st["q"].clear()
    def on_state(o):
        prev = st["m"]
        st["m"], st["t0"], st["note"] = o, time.time(), ""
        if prev is None or (o["phase"] == "bet" and prev["phase"] != "bet"): st["bank0"] = o["bank"]
        if o["phase"] in ("result", "over") and st["bank0"] is not None: st["bdelta"] = o["bank"] - st["bank0"]
        elif o["phase"] != "result": st["bdelta"] = 0
        mine = next((p["name"] for p in o["players"] if p["id"] == o["you"]), "")
        if mine: st["me"] = mine
        ids = {p["id"]: p["name"] for p in o["players"] if not p["bot"]}
        if st["ids"] is not None:
            for k, nm in ids.items():
                if k not in st["ids"]: chat_add("", f"{nm} เข้าร่วมโต๊ะ", "sys")
            for k, nm in st["ids"].items():
                if k not in ids: chat_add("", f"{nm} ออกจากโต๊ะ", "sys")
        st["ids"] = ids
        if o["phase"] == "bet" and (prev is None or prev["phase"] != "bet"): st["bet"] = max(st["bet"], POK_MIN)
        keys = {"d": o["dealer"]["cards"]}
        for p in o["players"]: keys[p["id"]] = p["cards"]
        for k in list(st["shown"]):
            if k not in keys: st["shown"].pop(k)
        if prev is not None and o["phase"] == "bet" and prev["phase"] != "bet":
            sweep()
        layout(o)
        newc = []
        for k, cs in keys.items():
            if len(cs) < st["shown"].get(k, 0): st["shown"][k] = len(cs)
            have = st["shown"].get(k, 0) + sum(1 for q in st["q"] if q[0] == k)
            for i in range(have, len(cs)): newc.append((i, k))
        newc.sort(key=lambda t: (t[0], 1 if t[1] == "d" else 0))
        st["q"] += [(k, i) for i, k in newc]
        fl = []
        for k, cs in keys.items():
            was, now_hid = st["prevhid"].get(k, False), any(c is None for c in cs)
            if was and not now_hid and cs and not st["q"]: fl.append(k)
            st["prevhid"][k] = now_hid
        if o["phase"] == "play" and o["turn"] == o["you"] and (prev is None or prev["phase"] != "play" or prev["turn"] != o["turn"]): pok_snd("turn")
        if o["phase"] == "result" and (prev is None or prev["phase"] != "result"):
            mr = next((p["res"] for p in o["players"] if p["id"] == o["you"] and p["res"]), None)
            if mr:
                def fin():
                    pok_snd(mr["o"] if mr["o"] in ("win", "lose") else "tie")
                    popup({"win": f"ชนะ +{mr['amt']:,}", "lose": f"แพ้ -{mr['amt']:,}", "tie": "เสมอ"}[mr["o"]], {"win": "#69f0ae", "lose": "#ff8a80", "tie": "#ffffff"}[mr["o"]])
                win.after(1100, fin)
        render(); run_q()
        if fl: flip_run(fl)
    def on_msg(o):
        if st["dead"]: return
        t = o.get("t")
        if t == "st": on_state(o)
        elif t == "chat":
            chat_add(str(o.get("n", "?")), str(o.get("m", "")))
            if o.get("n") != st["me"]: pok_snd("chat")
        elif t in ("none", "full", "closed"):
            st["note"] = {"none": "เครื่องนี้ยังไม่ได้เปิดโต๊ะ", "full": "โต๊ะเต็ม (สูงสุด 8 คน)", "closed": "เจ้าของโต๊ะปิดโต๊ะแล้ว"}[t]
            st["m"] = None if t != "closed" else st["m"]; render()
    def on_end():
        if st["dead"]: return
        st["note"] = "หลุดการเชื่อมต่อ" if st["m"] else "เชื่อมต่อโต๊ะไม่ได้ (เครื่องปลายทางอาจยังไม่ใช่รุ่น 6.0.0 ขึ้นไป หรือไม่ได้เปิดโต๊ะ)"
        render()
    def tickui():
        if st["dead"]: return
        draw_banner(); win.after(500, tickui)
    def reader():
        buf = b""
        try:
            s = socket.create_connection((ip, CTRL_PORT), timeout=6)
            st["sock"] = s
            nb = (myname or username() or HOSTNAME).encode("utf-8")[:60]
            s.sendall(b"G" + bytes([len(nb)]) + nb)
            s.settimeout(None)
            while True:
                d = s.recv(65536)
                if not d: break
                buf += d
                while b"\n" in buf:
                    ln, buf = buf.split(b"\n", 1)
                    try: o = json.loads(ln.decode("utf-8"))
                    except ValueError: continue
                    root.after(0, on_msg, o)
        except Exception as e:
            log_err(e)
        root.after(0, on_end)
    def close():
        if not st["dead"]: POK_ACTIVE[0] = max(0, POK_ACTIVE[0] - 1)
        st["dead"] = True
        try: st["sock"].close()
        except Exception: pass
        win.destroy()
    RZ = {"j": None}
    def do_resize():
        RZ["j"] = None
        if st["dead"]: return
        k = max(0.4, min(mid.winfo_width() / W, mid.winfo_height() / H))
        if abs(k - KK["k"]) < 0.01: return
        KK["k"] = k
        cv.config(width=int(W * k), height=int(H * k))
        build_bg(); render()
    def on_cfg(e):
        if e.widget is mid:
            if RZ["j"]: win.after_cancel(RZ["j"])
            RZ["j"] = win.after(90, do_resize)
    mid.bind("<Configure>", on_cfg)
    win.bind("<F11>", lambda e: win.attributes("-fullscreen", not win.attributes("-fullscreen")))
    win.protocol("WM_DELETE_WINDOW", close)
    threading.Thread(target=reader, daemon=True).start()
    POK_ACTIVE[0] += 1
    render(); tickui(); dealer_tick(); refresh_online()
    chat_add("", "แชทกับคนในโต๊ะได้ที่ช่องด้านล่าง", "sys")

import math
# ---------- Play pool: 8-ball (9.0.0) เล่นกับบอทหรือเพื่อน 1 คน เหรียญ/เงินไม่เกี่ยว ----------
POOL = {"table": None}
POOL_ACTIVE = [0]
PL_W, PL_H, PL_R, PL_DT = 1000.0, 500.0, 11.0, 1.0 / 240
PL_POCKETS = ((0.0, 0.0, 25.0), (PL_W, 0.0, 25.0), (0.0, PL_H, 25.0), (PL_W, PL_H, 25.0), (PL_W / 2, -6.0, 23.0), (PL_W / 2, PL_H + 6.0, 23.0))
PL_T_TURN = 40
PL_HEAD = (PL_W * 0.25, PL_H / 2)

def pl_kind(n): return None if n in (0, 8) else ("solid" if n < 8 else "stripe")

def pl_seg_dist(px, py, ax, ay, bx, by):  # ระยะจุด P ถึงเส้น AB (ช่วง)
    dx, dy = bx - ax, by - ay
    d2 = dx * dx + dy * dy
    t = 0.0 if d2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / d2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

class PoolTable:
    def __init__(s):
        s.lock = threading.RLock()
        s.closed = False
        s.seats = [None, None]  # {"name","send","ip"} ; None = บอท (ที่นั่ง 0 คือเจ้าของโต๊ะ)
        s.names = ["", "บอท"]
        s.breaker = 1  # reset จะสลับเป็น 0
        s.dirty = True
        s.reset("พร้อมแล้ว")
        threading.Thread(target=s.loop, daemon=True).start()
    # ---- ตั้งโต๊ะ ----
    def reset(s, msg=""):
        s.breaker = 1 - s.breaker
        cy = PL_H / 2
        fx, dx, dy = PL_W * 0.72, 1.7320508 * PL_R + 0.3, 2 * PL_R + 0.3
        pos = [(fx + r * dx, cy + (i - r / 2) * dy) for r in range(5) for i in range(r + 1)]
        solids = list(range(1, 8)); stripes = list(range(9, 16)); random.shuffle(solids); random.shuffle(stripes)
        corner_a, corner_b = solids.pop(), stripes.pop()
        rest = solids + stripes; random.shuffle(rest)
        order = [None] * 15
        order[4], order[10], order[14] = 8, corner_a, corner_b
        for i in range(15):
            if order[i] is None: order[i] = rest.pop()
        s.b = {0: {"n": 0, "x": PL_HEAD[0], "y": cy, "vx": 0.0, "vy": 0.0, "on": True}}
        for n, (x, y) in zip(order, pos): s.b[n] = {"n": n, "x": x, "y": y, "vx": 0.0, "vy": 0.0, "on": True}
        s.phase, s.turn, s.groups, s.pocketed, s.breaking, s.winner = "aim", s.breaker, [None, None], [], True, None
        s.shot, s.aim, s.ev, s.acc, s.last = None, [0.0, 0.0], [], 0.0, time.time()
        s.msg = msg or f"{s.names[s.turn] or 'เจ้าของโต๊ะ'} เปิดเกม"
        s.start_turn(); s.dirty = True
    def start_turn(s):
        now = time.time()
        s.turn_at = now + PL_T_TURN
        s.bot_at, s.bot_plan = (now + random.uniform(1.2, 2.0), None) if s.seats[s.turn] is None else (0.0, None)
        s.aim = [0.0, 0.0]
    def is_bot(s, seat): return s.seats[seat] is None
    # ---- ผู้เล่นเข้า/ออก ----
    def join(s, name, send, owner, ip):
        with s.lock:
            if owner:
                if s.seats[0] is not None: return None
                seat = 0
            else:
                if s.seats[1] is not None or s.seats[0] is None: return None
                seat = 1
            s.seats[seat] = {"name": name, "send": send, "ip": ip}; s.names[seat] = name
            if seat == 1:
                s.breaker = 1; s.reset(f"{name} เข้าร่วม — เริ่มเกมใหม่")
            elif seat == 0: s.names[0] = name; s.msg = f"{name} เปิดโต๊ะ"; s.start_turn(); s.dirty = True
            s.dirty = True
            return seat
    def leave(s, seat):
        with s.lock:
            if seat == 0:
                s.closed = True
                for q in s.seats[1:]:
                    if q:
                        try: q["send"]({"t": "closed"})
                        except Exception: pass
                return
            s.seats[1] = None; s.names[1] = "บอท"
            s.msg = "เพื่อนออกจากโต๊ะ — บอทเล่นแทน"
            if s.turn == 1 and s.phase in ("aim", "place"): s.start_turn()
            s.dirty = True
    # ---- คำสั่งจากผู้เล่น ----
    def act(s, seat, a):
        with s.lock:
            k = a.get("a")
            try:
                if k == "aim" and seat == s.turn and s.phase == "aim":
                    s.aim = [float(a.get("ang", 0)) % (2 * math.pi), max(0.0, min(1.0, float(a.get("pull", 0))))]
                elif k == "shot" and seat == s.turn and s.phase == "aim":
                    s.shoot(float(a["ang"]), max(0.0, min(1.0, float(a["pw"]))), max(-1.0, min(1.0, float(a.get("sx", 0)))), max(-1.0, min(1.0, float(a.get("sy", 0)))))
                elif k == "place" and seat == s.turn and s.phase == "place":
                    s.place(float(a["x"]), float(a["y"]))
                elif k == "rematch" and s.phase == "over": s.reset("เริ่มเกมใหม่")
            except (KeyError, ValueError, TypeError): pass
    def valid_spot(s, x, y):
        if not (PL_R <= x <= PL_W - PL_R and PL_R <= y <= PL_H - PL_R): return False
        return all(b["n"] == 0 or not b["on"] or math.hypot(b["x"] - x, b["y"] - y) >= 2 * PL_R + 0.5 for b in s.b.values())
    def place(s, x, y):
        if not s.valid_spot(x, y): return False
        c = s.b[0]; c.update(x=x, y=y, vx=0.0, vy=0.0, on=True)
        s.phase = "aim"; s.msg = ""; s.turn_at = time.time() + PL_T_TURN; s.dirty = True
        if s.is_bot(s.turn): s.bot_at, s.bot_plan = time.time() + 0.9, None
        return True
    def shoot(s, ang, pw, sx, sy):
        c = s.b[0]; sp = 120 + pw * 2100
        c["vx"], c["vy"] = math.cos(ang) * sp, math.sin(ang) * sp
        s.shot = {"first": None, "pk": [], "rail": False, "sx": sx, "sy": sy, "cue_in": False}
        s.phase, s.msg = "roll", ""; s.ev.append(["cue", round(pw, 2)]); s.dirty = True
    # ---- ฟิสิกส์ (1 ก้าว = 1/240 วินาที) ----
    def step(s):
        R, live = PL_R, [b for b in s.b.values() if b["on"]]
        sh = s.shot
        for b in live:
            vx, vy = b["vx"], b["vy"]
            if vx == 0.0 and vy == 0.0: continue
            b["x"] += vx * PL_DT; b["y"] += vy * PL_DT
            sp = math.hypot(vx, vy)
            ns = sp * (1 - 0.45 * PL_DT) - 25 * PL_DT
            if ns < 6: b["vx"] = b["vy"] = 0.0
            else: k = ns / sp; b["vx"], b["vy"] = vx * k, vy * k
            x, y = b["x"], b["y"]
            for px, py, pr in PL_POCKETS:
                if (x - px) ** 2 + (y - py) ** 2 < pr * pr:
                    b["on"] = False; b["vx"] = b["vy"] = 0.0
                    s.ev.append(["pocket", 1.0])
                    if sh is not None:
                        sh["pk"].append(b["n"])
                        if b["n"] == 0: sh["cue_in"] = True
                    break
            if not b["on"]: continue
            hit, vn = None, 0.0
            if x < R: b["x"] = R; b["vx"] = -b["vx"] * 0.78; hit, vn = "x", abs(vx)
            elif x > PL_W - R: b["x"] = PL_W - R; b["vx"] = -b["vx"] * 0.78; hit, vn = "x", abs(vx)
            if y < R: b["y"] = R; b["vy"] = -b["vy"] * 0.78; hit, vn = "y", abs(vy)
            elif y > PL_H - R: b["y"] = PL_H - R; b["vy"] = -b["vy"] * 0.78; hit, vn = "y", abs(vy)
            if hit:
                s.ev.append(["rail", min(1.0, vn / 1200)])
                if sh is not None:
                    if sh["first"] is not None: sh["rail"] = True
                    if b["n"] == 0 and sh["sx"]:  # หมุนข้างของลูกขาว เบี่ยงตอนชนขอบ
                        t = sh["sx"] * 0.22 * vn
                        if hit == "x": b["vy"] += t * (1 if b["vx"] > 0 else -1)
                        else: b["vx"] -= t * (1 if b["vy"] > 0 else -1)
                        sh["sx"] = 0
        live = [b for b in live if b["on"]]
        n = len(live)
        for i in range(n):
            b1 = live[i]
            for j in range(i + 1, n):
                b2 = live[j]
                dx, dy = b2["x"] - b1["x"], b2["y"] - b1["y"]
                if dx > 2 * R or dx < -2 * R or dy > 2 * R or dy < -2 * R: continue
                d2 = dx * dx + dy * dy
                if d2 >= 4 * R * R or d2 == 0: continue
                if b1["vx"] == b1["vy"] == b2["vx"] == b2["vy"] == 0.0: continue
                d = math.sqrt(d2); nx, ny = dx / d, dy / d
                ov = (2 * R - d) / 2
                b1["x"] -= nx * ov; b1["y"] -= ny * ov; b2["x"] += nx * ov; b2["y"] += ny * ov
                rvn = (b1["vx"] - b2["vx"]) * nx + (b1["vy"] - b2["vy"]) * ny
                if rvn <= 0: continue
                j_ = (1 + 0.95) * rvn / 2
                b1["vx"] -= j_ * nx; b1["vy"] -= j_ * ny; b2["vx"] += j_ * nx; b2["vy"] += j_ * ny
                s.ev.append(["clack", min(1.0, rvn / 1000)])
                if sh is not None and (b1["n"] == 0 or b2["n"] == 0):
                    cue, obj, sgn = (b1, b2, 1) if b1["n"] == 0 else (b2, b1, -1)
                    if sh["first"] is None:
                        sh["first"] = obj["n"]
                        if sh["sy"]:  # ลูกตาม/ลูกดึง: เพิ่ม/ลดความเร็วลูกขาวตามแนวชน
                            cue["vx"] += sgn * nx * sh["sy"] * 0.5 * rvn; cue["vy"] += sgn * ny * sh["sy"] * 0.5 * rvn
                        sh["sy"] = 0
    def moving(s): return any(b["on"] and (b["vx"] or b["vy"]) for b in s.b.values())
    def remaining(s, kind): return [n for n, b in s.b.items() if b["on"] and pl_kind(n) == kind]
    # ---- ตัดสินหลังลูกหยุด ----
    def resolve(s):
        sh, me = s.shot, s.turn; opp = 1 - me
        s.shot = None
        pk = sh["pk"]; foul, why = False, ""
        if sh["cue_in"]: foul, why = True, "ลูกขาวลงหลุม"
        elif sh["first"] is None: foul, why = True, "ยิงไม่โดนลูกไหนเลย"
        elif not s.breaking:
            g = s.groups[me]
            want = (g if s.remaining(g) else 8) if g else None
            f = sh["first"]
            if g is None and f == 8: foul, why = True, "ตีโดนลูก 8 ก่อน"
            elif g is not None and (pl_kind(f) if f != 8 else 8) != want: foul, why = True, "ตีโดนลูกผิดกลุ่ม"
        if not foul and not s.breaking and not [b for b in pk if b != 0] and not sh["rail"]: foul, why = True, "ไม่มีลูกชนขอบเลย"
        if 8 in pk:
            if s.breaking:
                s.b[8].update(x=PL_W * 0.72, y=PL_H / 2, vx=0.0, vy=0.0, on=True)
                pk = [b for b in pk if b != 8]; s.ev.append(["rail", 0.3])
            else:
                g = s.groups[me]
                win = (not foul) and g is not None and not s.remaining(g)
                s.phase, s.winner = "over", (me if win else opp)
                s.msg = (f"{s.names[s.winner] or 'เจ้าของโต๊ะ'} ชนะ! " + ("ลงลูก 8 สำเร็จ" if win else ("ลงลูก 8 ผิดกติกา" if not foul else why + " + ลูก 8 ลง")))
                s.dirty = True; return
        s.pocketed += [b for b in pk if b not in (0, 8)]
        if s.groups[me] is None and not foul:
            first = [b for b in pk if b not in (0, 8)]
            if first:
                s.groups[me] = pl_kind(first[0]); s.groups[opp] = "stripe" if s.groups[me] == "solid" else "solid"
        own = [b for b in pk if b not in (0, 8) and pl_kind(b) == s.groups[me]]
        s.breaking = False
        if 0 in s.b and not s.b[0]["on"]: s.b[0].update(x=PL_HEAD[0], y=PL_H / 2, vx=0.0, vy=0.0, on=True)
        if foul:
            s.turn = opp; s.phase = "place"; s.msg = f"ฟาวล์: {why} — {s.names[opp] or 'เจ้าของโต๊ะ'} วางลูกขาวได้เอง"
        elif own: s.phase = "aim"; s.msg = "ลงลูกได้ ยิงต่อ!"
        else: s.turn = opp; s.phase = "aim"; s.msg = ""
        s.start_turn()
        if foul and s.is_bot(s.turn): s.bot_at = time.time() + 1.0
        s.dirty = True
    # ---- บอท ----
    def bot_targets(s, seat):
        g = s.groups[seat]
        if g is None: return [n for n, b in s.b.items() if b["on"] and n not in (0, 8)]
        r = s.remaining(g)
        return r if r else [8]
    def bot_plan_shot(s, seat):
        c = s.b[0]; cx, cy = c["x"], c["y"]
        others = [b for n, b in s.b.items() if b["on"] and n != 0]
        best = None
        for t in s.bot_targets(seat):
            tb = s.b[t]; tx, ty = tb["x"], tb["y"]
            for px, py, pr in PL_POCKETS:
                ex, ey = px, py
                if px in (0.0, PL_W) and py in (0.0, PL_H): ex, ey = px + (8 if px == 0 else -8), py + (8 if py == 0 else -8)
                elif py < 0: ey = 4
                elif py > PL_H: ey = PL_H - 4
                dx, dy = ex - tx, ey - ty; dd = math.hypot(dx, dy)
                if dd < 1: continue
                ux, uy = dx / dd, dy / dd
                gx, gy = tx - ux * 2 * PL_R, ty - uy * 2 * PL_R  # ตำแหน่งลูกขาวตอนชน (ghost ball)
                if not (PL_R <= gx <= PL_W - PL_R and PL_R <= gy <= PL_H - PL_R): continue
                vx, vy = gx - cx, gy - cy; vd = math.hypot(vx, vy)
                if vd < 1: continue
                cos_cut = (vx * ux + vy * uy) / vd
                if cos_cut < 0.35: continue
                if any(b["n"] != t and pl_seg_dist(b["x"], b["y"], cx, cy, gx, gy) < 2 * PL_R - 0.5 for b in others): continue
                if any(b["n"] != t and pl_seg_dist(b["x"], b["y"], tx, ty, ex, ey) < 2 * PL_R - 0.5 for b in others): continue
                score = (1 - cos_cut) * 3 + (vd + dd) / 1500 + random.random() * 0.15
                if best is None or score < best[0]: best = (score, math.atan2(vy, vx), vd + dd)
        if best is None:  # ไม่มีช่องลงชัดๆ: ตีลูกเป้าที่ใกล้สุดแบบเบาๆ
            ts = s.bot_targets(seat)
            t = min(ts, key=lambda n: math.hypot(s.b[n]["x"] - cx, s.b[n]["y"] - cy))
            tb = s.b[t]; d = math.hypot(tb["x"] - cx, tb["y"] - cy)
            return math.atan2(tb["y"] - cy, tb["x"] - cx) + random.gauss(0, 0.02), min(0.7, 0.3 + d / 1400)
        _sc, ang, dist = best
        ang += math.radians(random.gauss(0, 0.9 + dist / 2200))
        return ang, max(0.3, min(0.95, 0.26 + dist / 1300))
    def bot_place(s):
        for _ in range(200):
            x, y = random.uniform(PL_R, PL_W * 0.45), random.uniform(PL_R, PL_H - PL_R)
            if s.valid_spot(x, y): s.place(x, y); return
        s.place(PL_HEAD[0], PL_H / 2) if s.valid_spot(*PL_HEAD) else None
    # ---- ลูปหลัก ----
    def loop(s):
        while not s.closed:
            try:
                with s.lock: s.tick()
            except Exception as e: log_err(e)
            time.sleep(1 / 60)
    def tick(s):
        now = time.time()
        s.acc += min(0.1, now - s.last); s.last = now
        if s.phase == "roll":
            n = 0
            while s.acc >= PL_DT and n < 24: s.step(); s.acc -= PL_DT; n += 1
            if not s.moving(): s.resolve()
            s.nsend = getattr(s, "nsend", 0) + 1
            if s.nsend % 2 == 0 or s.phase != "roll": s.push()
            return
        s.acc = 0.0
        if s.seats[0] is None: return
        if s.phase in ("aim", "place") and s.seats[s.turn] is not None and now >= s.turn_at:  # คนจริงหมดเวลา = ฟาวล์
            opp = 1 - s.turn
            s.msg = f"{s.names[s.turn]} หมดเวลา — {s.names[opp] or 'เจ้าของโต๊ะ'} วางลูกขาวได้เอง"
            s.turn = opp; s.phase = "place"; s.breaking = False; s.start_turn(); s.dirty = True
        elif s.phase in ("aim", "place") and s.is_bot(s.turn) and now >= s.bot_at:
            if s.phase == "place": s.bot_place()
            elif s.bot_plan is None:
                s.bot_plan = s.bot_plan_shot(s.turn); s.aim = [s.bot_plan[0] % (2 * math.pi), 0.0]; s.bot_at = now + 0.9; s.dirty = True
            else:
                ang, pw = s.bot_plan; s.shoot(ang, pw, 0.0, 0.0)
        s.nsend = getattr(s, "nsend", 0) + 1
        if s.dirty or s.nsend % 10 == 0: s.push()
    def view(s, seat):
        return {"t": "pl", "you": seat, "names": [s.names[0] or "เจ้าของโต๊ะ", s.names[1]], "turn": s.turn, "phase": s.phase, "msg": s.msg,
                "groups": s.groups, "pk": s.pocketed, "winner": s.winner, "left": max(0, int(s.turn_at - time.time())) if s.phase in ("aim", "place") else 0,
                "aim": [round(s.aim[0], 4), round(s.aim[1], 3)], "bot": [s.is_bot(0), s.is_bot(1)], "breaking": s.breaking,
                "b": [[n, round(b["x"], 1), round(b["y"], 1), round(b["vx"]), round(b["vy"])] for n, b in s.b.items() if b["on"]], "ev": s.ev[:12]}
    def push(s):
        s.dirty = False
        for i, q in enumerate(s.seats):
            if q is None: continue
            try: q["send"](s.view(i))
            except Exception: q["send"] = lambda o: (_ for _ in ()).throw(OSError("gone"))
        s.ev = []

def pool_open_table():
    tb = POOL["table"]
    if tb is None or tb.closed:
        tb = POOL["table"] = PoolTable()
    return tb

def pool_serve(client, addr):  # เซิร์ฟเวอร์ฝั่งเจ้าของโต๊ะพูล: 1 การเชื่อมต่อ = 1 ผู้เล่น (JSON ทีละบรรทัด)
    tb, seat = POOL["table"], None
    slk = threading.Lock()
    def send(o):
        with slk: client.sendall((json.dumps(o, ensure_ascii=False) + "\n").encode("utf-8"))
    try:
        client.settimeout(5)
        n = client.recv(1)
        name = b""
        while n and len(name) < n[0]:
            d = client.recv(n[0] - len(name))
            if not d: break
            name += d
        name = "".join(ch for ch in name.decode("utf-8", "replace") if ch.isprintable()).strip()[:16] or "ผู้เล่น"
        if tb is None or tb.closed:
            send({"t": "none"}); return
        client.settimeout(10)
        seat = tb.join(name, send, addr[0] == "127.0.0.1", addr[0])
        if seat is None:
            send({"t": "full"}); return
        client.settimeout(None)
        buf = b""
        while not tb.closed:
            d = client.recv(4096)
            if not d: break
            buf += d
            if len(buf) > 8192: break
            while b"\n" in buf:
                ln, buf = buf.split(b"\n", 1)
                try: a = json.loads(ln.decode("utf-8"))
                except ValueError: continue
                if isinstance(a, dict): tb.act(seat, a)
    except Exception as e:
        log_err(e)
    finally:
        if seat is not None: tb.leave(seat)
        try: client.close()
        except Exception: pass


PL_BCOL = {1: "#f4c20d", 2: "#1d4fd8", 3: "#d32f2f", 4: "#7b1fa2", 5: "#f57c00", 6: "#2e7d32", 7: "#8d2f1c", 8: "#151515"}

def pool_window(ip, myname=None):  # หน้าต่างพูล 8-ball สไตล์เกมมือถือ: เล็งด้วยเมาส์ + ลากแถบแรงด้านซ้ายแล้วปล่อยเพื่อยิง
    root = ROOT[0]
    if root is None: return
    win = tk.Toplevel(root)
    win.title("Play pool — 8 Ball"); win.configure(bg="#0e1a2b"); win.resizable(True, True); win.minsize(900, 520)
    try: win.geometry(f"{min(1380, win.winfo_screenwidth() - 60)}x{min(790, win.winfo_screenheight() - 100)}+20+20")
    except Exception: win.geometry("1300x760")
    try: win.iconbitmap(ICON_PATH)
    except Exception: pass
    KK = {"k": 1.0}
    F = lambda n, b=False: (RFONT(), max(6, round(n * KK["k"])), "bold") if b else (RFONT(), max(6, round(n * KK["k"])))
    W, H, FX, FY, R = 1300, 740, 130, 150, PL_R
    st = {"m": None, "sock": None, "dead": False, "note": "", "balls": {}, "t_snap": time.time(), "items": {}, "ang": 0.0, "pull": 0.0, "pw": 0.0, "drag": False,
          "sx": 0.0, "sy": 0.0, "mx": FX + 250.0, "my": FY + 250.0, "sent": False, "last_aim": 0.0, "lastmsg": "", "me": "", "popt": 0.0}
    mid = tk.Frame(win, bg="#0e1a2b"); mid.pack(fill="both", expand=True)
    cv = tk.Canvas(mid, width=W, height=H, bg="#0e1a2b", highlightthickness=0); cv.pack(expand=True)
    K = lambda: KK["k"]
    def rr(x1, y1, x2, y2, r, **kw):
        if RETRO[0]: return cv.create_polygon([x1, y1, x2, y1, x2, y2, x1, y2], **kw)
        p = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return cv.create_polygon(p, smooth=True, splinesteps=10, **kw)
    def fit(tag):
        if K() != 1.0: cv.scale(tag, 0, 0, K(), K())
    def tcoord(x, y): return (FX + x) * K(), (FY + y) * K()
    def send(o):
        try: st["sock"].sendall((json.dumps(o) + "\n").encode("utf-8"))
        except Exception: pass
    def mine():
        m = st["m"]; return bool(m) and m["turn"] == m["you"]

    # ---------- พื้นหลัง/โต๊ะ ----------
    def build_bg():
        cv.delete("bg")
        for i in range(40):
            t = i / 39
            col = "#%02x%02x%02x" % (int(14 + 6 * t), int(26 + 14 * t), int(43 + 22 * t))
            cv.create_rectangle(0, i * H / 40, W, (i + 1) * H / 40 + 1, fill=col, outline=col, tags="bg")
        rr(FX - 40, FY - 40, FX + 1040, FY + 540, 34, fill="#2b1608", outline="#0b0502", width=3, tags="bg")
        rr(FX - 34, FY - 34, FX + 1034, FY + 534, 30, fill="#6b3a17", outline="#8a5426", width=3, tags="bg")
        rr(FX - 12, FY - 12, FX + 1012, FY + 512, 12, fill="#0a5c34", outline="#06361e", width=3, tags="bg")
        cv.create_rectangle(FX, FY, FX + 1000, FY + 500, fill="#12804a", outline="#0b5a33", width=2, tags="bg")
        cv.create_oval(FX + 140, FY + 60, FX + 860, FY + 440, fill="#16905a", outline="", tags="bg")
        cv.create_line(FX + 250, FY, FX + 250, FY + 500, fill="#0f6e3e", width=2, tags="bg")
        cv.create_oval(FX + 246, FY + 246, FX + 254, FY + 254, fill="#0f6e3e", outline="", tags="bg")
        cv.create_oval(FX + 716, FY + 246, FX + 724, FY + 254, fill="#0f6e3e", outline="", tags="bg")
        for px, py, pr in PL_POCKETS:
            r = pr * 0.92
            cv.create_oval(FX + px - r - 4, FY + py - r - 4, FX + px + r + 4, FY + py + r + 4, fill="#2b1608", outline="", tags="bg")
            cv.create_oval(FX + px - r, FY + py - r, FX + px + r, FY + py + r, fill="#050505", outline="#222", width=2, tags="bg")
        for i in range(1, 8):  # จุดไดมอนด์บนขอบโต๊ะ
            for yy in (FY - 22, FY + 522):
                if i != 4: cv.create_polygon(FX + i * 125, yy - 5, FX + i * 125 + 5, yy, FX + i * 125, yy + 5, FX + i * 125 - 5, yy, fill="#e8d9a8", outline="", tags="bg")
        for j in (1, 2, 3):
            for xx in (FX - 22, FX + 1022):
                cv.create_polygon(xx - 5, FY + j * 125, xx, FY + j * 125 + 5, xx + 5, FY + j * 125, xx, FY + j * 125 - 5, fill="#e8d9a8", outline="", tags="bg")
        fit("bg"); cv.tag_lower("bg")

    # ---------- ลูกบิลเลียด ----------
    def mk_ball(n):
        r = R; col = PL_BCOL.get(n if n <= 8 else n - 8, "#ffffff")
        ids = [cv.create_oval(0, 0, 1, 1, fill="#0a4a2e", outline="", tags="ball")]
        if n == 0 or n <= 8: ids.append(cv.create_oval(0, 0, 1, 1, fill="#f7f7f2" if n == 0 else col, outline="#222222", width=1, tags="ball"))
        else:
            ids.append(cv.create_oval(0, 0, 1, 1, fill=col, outline="#222222", width=1, tags="ball"))
            ids.append(cv.create_arc(0, 0, 1, 1, start=26.7, extent=126.6, style="chord", fill="#f7f7f2", outline="", tags="ball"))
            ids.append(cv.create_arc(0, 0, 1, 1, start=206.7, extent=126.6, style="chord", fill="#f7f7f2", outline="", tags="ball"))
        if n:
            ids.append(cv.create_oval(0, 0, 1, 1, fill="#f7f7f2", outline="", tags="ball"))
            ids.append(cv.create_text(0, 0, text=str(n), fill="#111111", font=F(8, True), tags="ball"))
        else: ids.append(cv.create_oval(0, 0, 1, 1, fill="#fbfbf6", outline="", tags="ball"))
        return ids
    def place_ball(n, x, y):
        ids = st["items"].get(n)
        if ids is None: ids = st["items"][n] = mk_ball(n)
        cx, cy = tcoord(x, y); r = R * K(); k = K()
        cv.coords(ids[0], cx - r + 2 * k, cy - r + 3 * k, cx + r + 2 * k, cy + r + 3 * k)
        for it in ids[1:]:
            t = cv.type(it)
            if t == "text": cv.coords(it, cx, cy)
            else:
                rr_ = r * 0.52 if (n and it == ids[-2]) else r * 0.42 if (not n and it == ids[-1]) else r
                if not n and it == ids[-1]: cv.coords(it, cx - r * 0.45 - r * 0.15, cy - r * 0.6, cx - r * 0.05, cy - r * 0.2)
                else: cv.coords(it, cx - rr_, cy - rr_, cx + rr_, cy + rr_)
    def clear_balls():
        for ids in st["items"].values():
            for it in ids: cv.delete(it)
        st["items"] = {}
    def sink(n, x, y):  # ลูกลงหลุม: หดหายเร็วๆ
        px, py, pr = min(PL_POCKETS, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
        cx, cy = tcoord(px, py); col = "#f7f7f2" if n == 0 else PL_BCOL.get(n if n <= 8 else n - 8, "#fff")
        it = cv.create_oval(0, 0, 1, 1, fill=col, outline="", tags="sink")
        def f(k=0):
            if st["dead"] or k > 7: cv.delete(it); return
            rr_ = R * K() * (1 - k / 8)
            cv.coords(it, cx - rr_, cy - rr_, cx + rr_, cy + rr_); win.after(30, f, k + 1)
        f()
    def ball_pos(n, now):  # คาดการณ์ตำแหน่งระหว่างรอ snapshot ถัดไป (ส่งมา 30 ครั้ง/วินาที)
        b = st["balls"][n]; dt = min(0.08, now - st["t_snap"])
        if b[3] or b[4]: return b[1] + b[3] * dt * 0.97, b[2] + b[4] * dt * 0.97
        return b[1], b[2]

    # ---------- เส้นเล็ง / ไม้คิว (วาดใหม่ทุกเฟรม) ----------
    def trace(cx, cy, ang):  # คืน (ชนอะไร, จุดชน, ลูกเป้า)
        dx, dy = math.cos(ang), math.sin(ang)
        best, kind, obj = 1e9, "wall", None
        for n, b in st["balls"].items():
            if n == 0: continue
            qx, qy = b[1] - cx, b[2] - cy
            tproj = qx * dx + qy * dy
            if tproj <= 0: continue
            d2 = qx * qx + qy * qy - tproj * tproj
            if d2 >= 4 * R * R: continue
            t = tproj - math.sqrt(4 * R * R - d2)
            if t < best: best, kind, obj = t, "ball", b
        tw = 1e9
        if dx > 1e-9: tw = min(tw, (PL_W - R - cx) / dx)
        elif dx < -1e-9: tw = min(tw, (R - cx) / dx)
        if dy > 1e-9: tw = min(tw, (PL_H - R - cy) / dy)
        elif dy < -1e-9: tw = min(tw, (R - cy) / dy)
        if tw < best: best, kind, obj = tw, "wall", None
        return kind, cx + dx * best, cy + dy * best, obj
    def draw_dyn():
        cv.delete("dyn")
        m = st["m"]; now = time.time()
        if not m or 0 not in st["balls"]: return
        k = K()
        ccx, ccy = ball_pos(0, now)
        if m["phase"] == "place":
            if mine():
                ok = st["m"] and all(n == 0 or math.hypot(b[1] - st["mx"] + FX, b[2] - st["my"] + FY) >= 2 * R + 0.5 for n, b in st["balls"].items()) and R <= st["mx"] - FX <= PL_W - R and R <= st["my"] - FY <= PL_H - R
                x, y = tcoord(min(max(st["mx"] - FX, R), PL_W - R), min(max(st["my"] - FY, R), PL_H - R)); r = R * k
                cv.create_oval(x - r, y - r, x + r, y + r, fill="", outline="#3ddc84" if ok else "#ff5252", width=3, tags="dyn")
            return
        if m["phase"] != "aim": return
        me_ = mine()
        ang, pull = (st["ang"], st["pw"]) if me_ else (m["aim"][0], m["aim"][1])
        dx, dy = math.cos(ang), math.sin(ang)
        if me_:
            kind, hx, hy, obj = trace(ccx, ccy, ang)
            x0, y0 = tcoord(ccx, ccy); x1, y1 = tcoord(hx, hy)
            cv.create_line(x0, y0, x1, y1, fill="#ffffff", width=max(1, 2 * k), dash=(8, 6), tags="dyn")
            r = R * k
            cv.create_oval(x1 - r, y1 - r, x1 + r, y1 + r, outline="#ffffff", width=max(1, 2 * k), tags="dyn")
            if kind == "ball":
                nx, ny = (obj[1] - hx) / (2 * R), (obj[2] - hy) / (2 * R)
                ox, oy = tcoord(obj[1], obj[2]); ex, ey = tcoord(obj[1] + nx * 90, obj[2] + ny * 90)
                cv.create_line(ox, oy, ex, ey, fill="#ffe082", width=max(1, 2 * k), tags="dyn")
                dd = dx * nx + dy * ny; tx, ty = dx - dd * nx, dy - dd * ny; tl = math.hypot(tx, ty)
                if tl > 0.08:
                    ax, ay = tcoord(hx + tx / tl * 55, hy + ty / tl * 55)
                    cv.create_line(x1, y1, ax, ay, fill="#b0bec5", width=max(1, 2 * k), tags="dyn")
            else:
                rx, ry = dx, dy
                if abs(hx - R) < 1 or abs(hx - (PL_W - R)) < 1: rx = -dx
                if abs(hy - R) < 1 or abs(hy - (PL_H - R)) < 1: ry = -dy
                ax, ay = tcoord(hx + rx * 130, hy + ry * 130)
                cv.create_line(x1, y1, ax, ay, fill="#b0bec5", width=max(1, 2 * k), dash=(4, 6), tags="dyn")
        # ไม้คิว
        back = (R + 5 + pull * 130) * k; L = 420 * k; cx0, cy0 = tcoord(ccx, ccy)
        bx0, by0 = cx0 - dx * back, cy0 - dy * back; bx1, by1 = cx0 - dx * (back + L), cy0 - dy * (back + L)
        px_, py_ = -dy, dx
        w0, w1 = 2.2 * k, 5.2 * k
        cv.create_polygon(bx0 + px_ * w0, by0 + py_ * w0, bx0 - px_ * w0, by0 - py_ * w0, bx1 - px_ * w1, by1 - py_ * w1, bx1 + px_ * w1, by1 + py_ * w1, fill="#d9a35f", outline="#4a2a10", tags="dyn")
        mx_, my_ = bx0 - dx * L * 0.62, by0 - dy * L * 0.62
        cv.create_polygon(mx_ + px_ * 4 * k, my_ + py_ * 4 * k, mx_ - px_ * 4 * k, my_ - py_ * 4 * k, bx1 - px_ * w1, by1 - py_ * w1, bx1 + px_ * w1, by1 + py_ * w1, fill="#3a2414", outline="#1a0f08", tags="dyn")
        cv.create_line(bx0, by0, bx0 - dx * 9 * k, by0 - dy * 9 * k, fill="#4fc3f7", width=max(2, 4 * k), tags="dyn")

    # ---------- HUD ----------
    def draw_player(seat, x):
        m = st["m"]; name = m["names"][seat]; g = m["groups"][seat]; on = m["turn"] == seat and m["phase"] in ("aim", "place", "roll")
        rr(x, 8, x + 400, 108, 18, fill="#16294a" if not on else "#1f3d6e", outline="#ffd54f" if on else "#35507f", width=3, tags="hud")
        col = ("#e53935", "#1e88e5")[seat]
        if on: cv.create_oval(x + 8, 20, x + 76, 88, outline="#ffeb3b", width=4, tags="hud")
        cv.create_oval(x + 14, 26, x + 70, 82, fill=col, outline="#ffffff", width=3, tags="hud")
        cv.create_text(x + 42, 54, text=name[:1].upper(), fill="#ffffff", font=F(24, True), tags="hud")
        if m["bot"][seat]:
            rr(x + 52, 70, x + 80, 86, 5, fill="#37474f", outline="#ffffff", tags="hud"); cv.create_text(x + 66, 78, text="BOT", fill="#ffffff", font=F(8, True), tags="hud")
        cv.create_text(x + 90, 32, text=name + (" (คุณ)" if seat == m["you"] else ""), fill="#ffffff", font=F(15, True), anchor="w", tags="hud")
        cv.create_text(x + 90, 54, text={"solid": "ลูกเต็ม 1-7", "stripe": "ลูกครึ่ง 9-15", None: "ยังไม่เลือกกลุ่ม"}[g], fill="#ffe082", font=F(11), anchor="w", tags="hud")
        nums = list(range(1, 8)) if g == "solid" else list(range(9, 16)) if g == "stripe" else []
        if g: nums.append(8)
        for i, n in enumerate(nums):
            bx, by = x + 100 + i * 36, 86
            gone = n in m["pk"] or (n == 8 and m["phase"] == "over")
            c = PL_BCOL.get(n if n <= 8 else n - 8, "#fff")
            cv.create_oval(bx - 12, by - 12, bx + 12, by + 12, fill=c if gone else "#0f1c33", outline="#ffffff" if gone else "#35507f", width=2, tags="hud")
            cv.create_text(bx, by, text=str(n), fill="#ffffff" if n in (1, 5) and False else ("#111111" if n in (1, 5, 9, 13) and gone else "#ffffff" if gone else "#35507f"), font=F(9, True), tags="hud")
    def btn(tag, x, y, w, h, text, color, size=13, enabled=True):
        rr(x - w / 2, y - h / 2 + 4, x + w / 2, y + h / 2 + 4, 14, fill="#050b16", outline="", tags=("hud", tag))
        rr(x - w / 2, y - h / 2, x + w / 2, y + h / 2, 14, fill=color if enabled else "#4a5568", outline="#ffffff", width=2, tags=("hud", tag))
        cv.create_text(x, y, text=text, fill="#ffffff", font=F(size, True), tags=("hud", tag))
    def draw_hud():
        cv.delete("hud")
        m = st["m"]
        if not m:
            tx = st["note"] or "กำลังเชื่อมต่อ ..."
            rr(W / 2 - 260, 330, W / 2 + 260, 390, 24, fill="#16294a", outline="#ffd54f", width=3, tags="hud")
            cv.create_text(W / 2, 360, text=tx, fill="#ffffff", font=F(18, True), tags="hud")
            fit("hud"); return
        draw_player(0, 20); draw_player(1, W - 420)
        ph, left = m["phase"], m["left"]
        if st["note"]: tx, bg, fg = st["note"], "#b71c1c", "#ffffff"
        elif ph == "aim": tx, bg, fg = (f"ตาของคุณ ⏱{left}", "#ffd54f", "#3e2714") if mine() else (f"ตาของ {m['names'][m['turn']]} ⏱{left}", "#16294a", "#ffe082")
        elif ph == "place": tx, bg, fg = (f"วางลูกขาวได้เลย ⏱{left}", "#ffd54f", "#3e2714") if mine() else (f"{m['names'][m['turn']]} กำลังวางลูกขาว", "#16294a", "#ffe082")
        elif ph == "roll": tx, bg, fg = "ลูกกำลังกลิ้ง ...", "#16294a", "#ffffff"
        else: tx, bg, fg = m["msg"], "#2e7d32", "#ffffff"
        tw = max(260, len(tx) * 15 + 40)
        rr(W / 2 - tw / 2, 24, W / 2 + tw / 2, 78, 24, fill=bg, outline="#ffffff", width=3, tags="hud")
        cv.create_text(W / 2, 51, text=tx, fill=fg, font=F(18, True), tags="hud")
        # แถบแรง (ซ้าย)
        cv.create_text(62, 128, text="แรง", fill="#ffe082", font=F(13, True), tags="hud")
        rr(40, FY, 84, FY + 500, 18, fill="#0b1626", outline="#35507f", width=3, tags="hud")
        p = st["pw"]
        if p > 0:
            col = "#%02x%02x%02x" % (int(60 + 195 * p), int(220 - 150 * p), 60)
            rr(46, FY + 6, 78, FY + 6 + p * 488, 12, fill=col, outline="", tags="hud")
        hy = FY + 6 + p * 488
        rr(32, hy - 14, 92, hy + 14, 10, fill="#ffffff" if (mine() and ph == "aim") else "#6b7a90", outline="#1a1a1a", width=2, tags="hud")
        cv.create_line(44, hy - 5, 80, hy - 5, 44, hy + 5, 80, hy + 5, fill="#8a96a8", width=2, tags="hud") if False else None
        # วงหมุนลูก (ขวา)
        sx0, sy0 = 1232, 300
        cv.create_text(sx0, 232, text="หมุนลูก", fill="#ffe082", font=F(13, True), tags="hud")
        cv.create_oval(sx0 - 56, sy0 - 56, sx0 + 56, sy0 + 56, fill="#f7f7f2", outline="#ffffff", width=4, tags="hud")
        cv.create_line(sx0 - 56, sy0, sx0 + 56, sy0, fill="#d0d0c8", tags="hud"); cv.create_line(sx0, sy0 - 56, sx0, sy0 + 56, fill="#d0d0c8", tags="hud")
        dx_, dy_ = sx0 + st["sx"] * 40, sy0 - st["sy"] * 40
        cv.create_oval(dx_ - 9, dy_ - 9, dx_ + 9, dy_ + 9, fill="#d32f2f", outline="#7f0000", width=2, tags="hud")
        cv.create_text(sx0, sy0 + 80, text="บน = ตาม  ล่าง = ดึง\nซ้าย/ขวา = เบี่ยง", fill="#b0bec5", font=F(10), justify="center", tags="hud")
        btn("b_snd", sx0, 420, 110, 36, "เสียง " + ("ปิด" if cfg.get("poker_mute") else "เปิด"), "#455a64", 12)
        btn("b_inv", sx0, 470, 110, 36, "เชิญเพื่อน", "#2e9e3a", 12)
        btn("b_rul", sx0, 520, 110, 36, "วิธีเล่น", "#546e7a", 12)
        # คำแนะนำ
        if ph == "aim" and mine(): hint = ("เปิดเกม: " if m["breaking"] else "") + "ชี้เมาส์ไปทางที่จะยิง → ลากแถบ 'แรง' ซ้ายแล้วปล่อย หรือกดค้าง Space แล้วปล่อย  •  ล้อเมาส์ = ปรับละเอียด  •  คลิกวงขวา = หมุนลูก"
        elif ph == "place" and mine(): hint = "ฟาวล์ของอีกฝ่าย: เลื่อนเมาส์ไปที่ที่อยากวางลูกขาว แล้วคลิกยืนยัน"
        elif ph == "over": hint = "จบเกม — กด 'เล่นอีกครั้ง' ที่กลางโต๊ะ"
        elif ph == "roll": hint = "ลูกกำลังกลิ้ง ..."
        else: hint = f"รอ {m['names'][m['turn']]} ..."
        pill_w = min(W - 100, len(hint) * 10 + 40)
        rr(W / 2 - pill_w / 2, 696, W / 2 + pill_w / 2, 728, 16, fill="#050b16", outline="#ffd54f", width=2, tags="hud")
        cv.create_text(W / 2, 712, text=hint, fill="#ffffff", font=F(12, True), tags="hud")
        if ph == "over": btn("b_again", FX + 500, FY + 380, 260, 64, "เล่นอีกครั้ง", "#2e9e3a", 20)
        fit("hud")
    def popup(txt, col="#ffffff"):
        cv.delete("pop")
        for dx, dy, c in ((3, 3, "#000000"), (0, 0, col)): cv.create_text(FX + 500 + dx, FY + 250 + dy, text=txt, fill=c, font=F(30, True), width=900, tags="pop")
        fit("pop"); st["popt"] = time.time() + 2.6

    # ---------- ข้อความจากโต๊ะ ----------
    def on_state(o):
        prev = st["m"]; st["m"] = o; st["note"] = ""
        now = time.time(); st["t_snap"] = now
        old = st["balls"]; st["balls"] = {b[0]: b for b in o["b"]}
        for n, b in old.items():
            if n not in st["balls"] and prev and prev["phase"] == "roll": sink(n, b[1], b[2])
        for n in list(st["items"]):
            if n not in st["balls"]:
                for it in st["items"].pop(n): cv.delete(it)
        for ev in o["ev"]:
            nm, vol = ev
            if nm == "cue": pok_snd("cue")
            elif nm == "clack" and vol > 0.04: pok_snd("clack")
            elif nm == "rail" and vol > 0.08: pok_snd("rail")
            elif nm == "pocket": pok_snd("pocket")
        if o["msg"] and o["msg"] != st["lastmsg"] and o["phase"] != "over": popup(o["msg"], "#ffe082")
        if o["phase"] == "over" and (prev is None or prev["phase"] != "over"):
            pok_snd("win" if o["winner"] == o["you"] else "lose"); popup(o["msg"], "#69f0ae" if o["winner"] == o["you"] else "#ff8a80")
        if o["phase"] == "aim" and o["turn"] == o["you"] and (prev is None or prev["phase"] != "aim" or prev["turn"] != o["turn"]):
            st["sent"] = False; st["pw"] = 0.0; st["drag"] = False
            if 0 in st["balls"]: st["ang"] = math.atan2(st["my"] - FY - st["balls"][0][2], st["mx"] - FX - st["balls"][0][1])
            pok_snd("turn")
        st["lastmsg"] = o["msg"]
        mp = o["names"][o["you"]]; st["me"] = mp
        if prev is None or prev["phase"] != o["phase"] or prev["turn"] != o["turn"] or prev["msg"] != o["msg"] or prev["groups"] != o["groups"] or prev["pk"] != o["pk"] or prev["left"] != o["left"]: draw_hud()
    def on_msg(o):
        if st["dead"]: return
        t = o.get("t")
        if t == "pl": on_state(o)
        elif t in ("none", "full", "closed"):
            st["note"] = {"none": "เครื่องนี้ยังไม่ได้เปิดโต๊ะพูล", "full": "โต๊ะเต็ม (เล่นได้ 2 คน)", "closed": "เจ้าของโต๊ะปิดโต๊ะแล้ว"}[t]
            if t != "closed": st["m"] = None
            draw_hud()
    def on_end():
        if st["dead"]: return
        st["note"] = "หลุดการเชื่อมต่อ" if st["m"] else "เชื่อมต่อโต๊ะไม่ได้ (เครื่องปลายทางอาจยังไม่ใช่รุ่น 9.0.0 หรือไม่ได้เปิดโต๊ะ)"
        draw_hud()
    def reader():
        buf = b""
        try:
            s = socket.create_connection((ip, CTRL_PORT), timeout=6)
            st["sock"] = s
            nb = (myname or username() or HOSTNAME).encode("utf-8")[:60]
            s.sendall(b"Q" + bytes([len(nb)]) + nb)
            s.settimeout(None)
            while True:
                d = s.recv(65536)
                if not d: break
                buf += d
                while b"\n" in buf:
                    ln, buf = buf.split(b"\n", 1)
                    try: o = json.loads(ln.decode("utf-8"))
                    except ValueError: continue
                    root.after(0, on_msg, o)
        except Exception as e:
            log_err(e)
        root.after(0, on_end)

    # ---------- เมาส์ ----------
    def to_base(e): return e.x / K(), e.y / K()
    def aim_to(bx, by):
        b = st["balls"].get(0)
        if not b: return
        if (bx - FX) ** 2 + (by - FY) ** 2 < 4 and False: return
        st["ang"] = math.atan2(by - FY - b[2], bx - FX - b[1])
    def send_aim(force=False):
        now = time.time()
        if force or now - st["last_aim"] > 0.08:
            st["last_aim"] = now; send({"a": "aim", "ang": round(st["ang"], 4), "pull": round(st["pw"], 3)})
    def on_motion(e):
        bx, by = to_base(e); st["mx"], st["my"] = bx, by
        m = st["m"]
        if not m: return
        if st["drag"]:
            st["pw"] = max(0.0, min(1.0, (by - FY - 6) / 488)); draw_hud(); send_aim(); return
        if m["phase"] == "aim" and mine() and not st["sent"] and FX - 50 <= bx <= FX + 1050 and FY - 50 <= by <= FY + 550:
            aim_to(bx, by); send_aim()
    def on_wheel(e):
        m = st["m"]
        if not m or not (m["phase"] == "aim" and mine()) or st["sent"]: return
        d = e.delta if hasattr(e, "delta") and e.delta else (120 if e.num == 4 else -120)
        st["ang"] += math.radians(0.2) * (1 if d > 0 else -1); send_aim(True)
    def in_box(bx, by, x1, y1, x2, y2): return x1 <= bx <= x2 and y1 <= by <= y2
    def on_press(e):
        bx, by = to_base(e); m = st["m"]
        if not m: return
        st["mx"], st["my"] = bx, by
        if in_box(bx, by, 1176, 402, 1288, 438): cfg["poker_mute"] = not cfg.get("poker_mute", False); save_config(cfg); pok_snd("clack"); draw_hud(); return
        if in_box(bx, by, 1176, 452, 1288, 488): invite_dialog(); return
        if in_box(bx, by, 1176, 502, 1288, 538): rules(); return
        if m["phase"] == "over" and in_box(bx, by, FX + 370, FY + 348, FX + 630, FY + 412): send({"a": "rematch"}); return
        if m["phase"] == "aim" and mine() and not st["sent"]:
            if in_box(bx, by, 28, FY - 20, 96, FY + 520): st["drag"] = True; st["pw"] = max(0.0, min(1.0, (by - FY - 6) / 488)); draw_hud(); return
            if (bx - 1232) ** 2 + (by - 300) ** 2 <= 62 * 62:
                vx, vy = (bx - 1232) / 40, -(by - 300) / 40; d = math.hypot(vx, vy)
                if d > 1: vx, vy = vx / d, vy / d
                st["sx"], st["sy"] = round(vx, 2), round(vy, 2); draw_hud(); return
        if m["phase"] == "place" and mine() and in_box(bx, by, FX, FY, FX + 1000, FY + 500):
            send({"a": "place", "x": round(bx - FX, 1), "y": round(by - FY, 1)})
    def on_release(e):
        if not st["drag"]: return
        st["drag"] = False
        m = st["m"]
        if m and m["phase"] == "aim" and mine() and not st["sent"] and st["pw"] > 0.04:
            st["sent"] = True; send({"a": "shot", "ang": round(st["ang"], 4), "pw": round(st["pw"], 3), "sx": st["sx"], "sy": st["sy"]})
            st["pw"] = 0.0
        else: st["pw"] = 0.0
        draw_hud()
    cv.bind("<Motion>", on_motion); cv.bind("<ButtonPress-1>", on_press); cv.bind("<B1-Motion>", on_motion); cv.bind("<ButtonRelease-1>", on_release)
    cv.bind("<MouseWheel>", on_wheel); cv.bind("<Button-4>", on_wheel); cv.bind("<Button-5>", on_wheel)
    # Space: กดค้างเพื่อชาร์จแรง ปล่อยเพื่อยิง (ถ้ากำลังลากแถบแรงอยู่ กด Space = ยิงด้วยแรงที่ลากไว้)
    SP = {"t0": 0.0, "on": False, "rel": None}
    def can_shoot():
        m = st["m"]; return bool(m) and m["phase"] == "aim" and mine() and not st["sent"]
    def fire():
        SP["rel"] = None
        if not (SP["on"] or st["drag"]): return
        SP["on"] = False; st["drag"] = False
        if can_shoot() and st["pw"] > 0.04:
            st["sent"] = True; send({"a": "shot", "ang": round(st["ang"], 4), "pw": round(st["pw"], 3), "sx": st["sx"], "sy": st["sy"]})
        st["pw"] = 0.0; draw_hud()
    def charge():
        if st["dead"] or not SP["on"]: return
        st["pw"] = min(1.0, (time.time() - SP["t0"]) / 1.4); draw_hud(); send_aim(); win.after(40, charge)
    def sp_down(e):
        if SP["rel"]:  # คีย์ซ้ำของระบบ (ปล่อย+กดซ้ำทันที) ไม่นับเป็นการปล่อยจริง
            win.after_cancel(SP["rel"]); SP["rel"] = None; return
        if st["drag"]: fire(); return
        if SP["on"] or not can_shoot(): return
        SP["on"] = True; SP["t0"] = time.time(); charge()
    def sp_up(e):
        if SP["on"]: SP["rel"] = win.after(45, fire)
    win.bind("<KeyPress-space>", sp_down); win.bind("<KeyRelease-space>", sp_up)
    win.focus_set()

    def rules():
        w = tk.Toplevel(win); w.title("วิธีเล่น"); w.configure(bg="#16294a")
        tk.Label(w, text=POOL_RULES, bg="#16294a", fg="white", font=(RFONT(), 12), justify="left", wraplength=640, padx=18, pady=14).pack()
    def invite_dialog():
        d = tk.Toplevel(win); d.title("เชิญเพื่อนเล่นพูล"); d.configure(bg="#16294a"); d.resizable(False, False)
        tk.Label(d, text="เลือกเครื่องที่จะเชิญ (ต้องเป็นรุ่น 9.0.0 ขึ้นไป)", bg="#16294a", fg="white", font=(RFONT(), 11)).pack(padx=16, pady=(14, 6))
        lb = tk.Listbox(d, width=34, height=8, font=(RFONT(), 11), bg="#0b1626", fg="white", selectbackground="#2e7d32", relief="flat", highlightthickness=0, exportselection=False); lb.pack(padx=16)
        rows = []; now = time.time()
        with peers_lock:
            for uid, v in peers.items():
                if now - v.get("last", 0) > 9 or v.get("stealth"): continue
                try: okv = ver_tuple(v.get("ver", "")) >= (9, 0, 0)
                except Exception: okv = False
                ips = sorted(set(v.get("ips", ())) | ({v["ip"]} if v.get("ip") else set()))
                rows.append((ips, okv, (v.get("code") or v.get("host") or "?") + ("" if okv else "  (รุ่นเก่า)")))
        for r_ in rows: lb.insert("end", r_[2])
        msg = tk.Label(d, text="", bg="#16294a", fg="#ffe082", font=(RFONT(), 10)); msg.pack(pady=4)
        def go():
            i = lb.curselection()
            if not i: msg.config(text="คลิกเลือกชื่อก่อน"); return
            ips, okv, _t = rows[i[0]]
            if not okv: msg.config(text="เครื่องนี้ยังเป็นรุ่นเก่า ต้องอัปเดตก่อน"); return
            me_nm = st["me"] or myname or username() or HOSTNAME; host_ip = "" if ip == "127.0.0.1" else ip
            def work():
                err = None
                for tip in ips:
                    err = poker_invite_send(tip, me_nm, host_ip, "pool")
                    if err is None: break
                root.after(0, lambda: msg.config(text="ส่งคำเชิญแล้ว" if err is None else "ส่งไม่ได้: " + err[:50]))
            threading.Thread(target=work, daemon=True).start()
        tk.Button(d, text="เชิญ", bg="#2e9e3a", fg="white", font=(RFONT(), 12, "bold"), relief="flat", padx=20, pady=4, command=go).pack(pady=(2, 14))

    # ---------- ลูปเฟรม / ปรับขนาด ----------
    def frame():
        if st["dead"]: return
        now = time.time()
        if st["m"] and st["balls"]:
            for n in st["balls"]:
                x, y = ball_pos(n, now); place_ball(n, x, y)
            cv.tag_raise("ball", "bg")
        draw_dyn()
        cv.tag_raise("dyn"); cv.tag_raise("sink"); cv.tag_raise("hud"); cv.tag_raise("pop")
        if st["popt"] and now > st["popt"]: cv.delete("pop"); st["popt"] = 0.0
        win.after(16, frame)
    RZ = {"j": None}
    def do_resize():
        RZ["j"] = None
        if st["dead"]: return
        k = max(0.4, min(mid.winfo_width() / W, mid.winfo_height() / H))
        if abs(k - KK["k"]) < 0.01: return
        KK["k"] = k; cv.config(width=int(W * k), height=int(H * k))
        clear_balls(); build_bg(); draw_hud()
    def on_cfg(e):
        if e.widget is mid:
            if RZ["j"]: win.after_cancel(RZ["j"])
            RZ["j"] = win.after(90, do_resize)
    mid.bind("<Configure>", on_cfg)
    win.bind("<F11>", lambda e: win.attributes("-fullscreen", not win.attributes("-fullscreen")))
    def close():
        if not st["dead"]: POOL_ACTIVE[0] = max(0, POOL_ACTIVE[0] - 1)
        st["dead"] = True
        try: st["sock"].close()
        except Exception: pass
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", close)
    POOL_ACTIVE[0] += 1
    threading.Thread(target=reader, daemon=True).start()
    build_bg(); draw_hud(); frame()

POOL_RULES = ("วิธีเล่นพูล 8-ball (เมาส์ + Space)\n"
              "1) เลื่อนเมาส์บนโต๊ะ — เส้นเล็งจะชี้ไปทางเมาส์ (ล้อเมาส์ = ปรับองศาละเอียด)\n"
              "2) เอาเมาส์ไปจับแถบ 'แรง' ด้านซ้าย ลากลงแล้วปล่อยเพื่อยิง ยิ่งลากลงมากยิ่งแรง — หรือกดค้างปุ่ม Space (แรงค่อยๆ เพิ่ม) แล้วปล่อยเพื่อยิง\n"
              "3) วงขวา 'หมุนลูก': คลิกจุดบนลูกขาว บน = ลูกตาม ล่าง = ลูกดึง ซ้าย/ขวา = เบี่ยงตอนชนขอบ\n\n"
              "กติกา: หลังเปิดเกม ลูกแรกที่คุณยิงลงจะกำหนดกลุ่ม (เต็ม 1-7 / ครึ่ง 9-15) ลงลูกกลุ่มตัวเองได้ยิงต่อ\n"
              "ต้องตีโดนลูกกลุ่มตัวเองก่อน ถ้าลูกขาวลงหลุม/ไม่โดนลูก/โดนผิดกลุ่ม/ไม่มีลูกชนขอบ = ฟาวล์ อีกฝ่ายวางลูกขาวได้เอง\n"
              "ลงลูกกลุ่มตัวเองหมดแล้วค่อยลูก 8 (ลงหลุมไหนก็ได้) ลูก 8 ลงก่อนเวลา/ฟาวล์ตอนลง = แพ้\n"
              "แต่ละตามีเวลา 40 วินาที หมดเวลา = ฟาวล์")


def desktop_dir():
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)
    return buf.value or os.path.join(os.environ["USERPROFILE"], "Desktop")

def unique_path(name, d=None):  # d = โฟลเดอร์ปลายทาง (ไม่ระบุ = เดสก์ท็อป เหมือนเดิม)
    name = ntpath.basename(name) or "file"
    base, ext = os.path.splitext(name)
    dd = d or desktop_dir()
    p, i = os.path.join(dd, name), 1
    while os.path.exists(p):
        p = os.path.join(dd, f"{base} ({i}){ext}")
        i += 1
    return p

def dest_blocked(d):  # โฟลเดอร์ที่ห้ามวางไฟล์ลง: โฟลเดอร์ระบบ + Startup ของผู้ใช้ (กันฝังโปรแกรมให้เปิดเอง)
    if blocked(d): return True
    ap, appdata = os.path.abspath(d).lower(), os.environ.get("APPDATA")
    if appdata:
        st = os.path.abspath(os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")).lower()
        if ap == st or ap.startswith(st + os.sep): return True
    return False

def dest_ok(d):
    return os.path.isabs(d) and os.path.isdir(d) and not dest_blocked(d)

DIR_LOCK = threading.Lock()  # เด้งหน้าต่างเลือกโฟลเดอร์ทีละเครื่อง (ส่งหลายเครื่องพร้อมกัน)

def build_dir_chooser(parent, col, request, on_pick):  # วิดเจ็ตเลือกโฟลเดอร์ของเครื่องปลายทาง (แสดงเฉพาะโฟลเดอร์) คืนฟังก์ชัน fill(info) ไว้ให้ผู้เรียกป้อนรายการที่ปลายทางส่งมา
    cur = {"path": "", "parent": None, "items": {}}
    top = tk.Frame(parent, bg=col["bg"]); top.pack(fill="x", padx=20, pady=(4, 6))
    lbl = tk.Label(top, text="กำลังโหลด ...", bg=col["bg"], fg=col["acc"], anchor="w", justify="left", font=FNT(12), wraplength=520)
    ttk.Button(top, text="↑ ขึ้นไป", style=col["ghost"], command=lambda: request(cur["parent"] or "")).pack(side="left")
    lbl.pack(side="left", padx=10, fill="x", expand=True)
    mid = tk.Frame(parent, bg=col["bg"]); mid.pack(fill="both", expand=True, padx=20)
    tv = ttk.Treeview(mid, show="tree", selectmode="browse", height=9)
    sb = ttk.Scrollbar(mid, orient="vertical", command=tv.yview); tv.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y"); tv.pack(side="left", fill="both", expand=True)
    tk.Label(parent, text="ดับเบิลคลิกโฟลเดอร์เพื่อเปิด แล้วกด 'วางที่นี่' (วางลงโฟลเดอร์ที่เปิดอยู่)", bg=col["bg"], fg=col["sub"], font=FNT(10), anchor="w").pack(fill="x", padx=20, pady=(6, 0))
    def fill(info):
        try:
            if info.get("error"):
                lbl.config(text=info["error"], fg=col["bad"])
                return
            cur.update(path=info["path"], parent=info["parent"], items={})
            lbl.config(text=info["path"] or "เครื่องนี้ (เลือกไดรฟ์หรือโฟลเดอร์ด้านล่าง)", fg=col["acc"])
            tv.delete(*tv.get_children())
            for i, it in enumerate(x for x in info["items"] if x["d"]):
                cur["items"][str(i)] = it.get("p") or ntpath.join(info["path"], it["n"])
                tv.insert("", "end", iid=str(i), text="▸ " + it["n"])
        except tk.TclError:
            pass  # หน้าต่างถูกปิดไปแล้ว
    def open_sel(e=None):
        sel = tv.selection()
        if sel: request(cur["items"][sel[0]])
    def here():
        if not cur["path"]:
            lbl.config(text="เปิดไดรฟ์หรือโฟลเดอร์ก่อน แล้วกด 'วางที่นี่'", fg=col["bad"])
            return
        on_pick(cur["path"])
    tv.bind("<Double-1>", open_sel)
    row = tk.Frame(parent, bg=col["bg"]); row.pack(fill="x", padx=20, pady=(10, 16))
    ttk.Button(row, text="วางที่นี่", style=col["go"], command=here).pack(side="right")
    ttk.Button(row, text="ยกเลิก", style=col["ghost"], command=lambda: on_pick(None)).pack(side="right", padx=10)
    return fill

def monitor_count():  # จำนวนจอจริงของเครื่องนี้ (ไม่รวม index 0 ที่ mss ใช้แทน "ทุกจอรวมกัน")
    try:
        import mss
        with mss.mss() as sct:
            return max(1, min(250, len(sct.monitors) - 1))
    except Exception:
        return 1

def make_grabber(mon_idx=1):
    try:
        import mss
        sct = mss.mss()
        mon = sct.monitors[mon_idx] if 1 <= mon_idx < len(sct.monitors) else sct.monitors[1]
        st = {"prev": None, "n": 0}
        def raw():  # คืน (ขนาด, bytes BGRA) ไม่แปลงเป็นภาพ PIL (แปลงช้า); เทียบกับเฟรมก่อนด้วย memcmp
            sh = sct.grab(mon)
            b = sh.raw
            if b != st["prev"]:
                st["n"] += 1
                st["prev"] = b
            g.sig = st["n"]
            return sh.size, b
        def g():
            size, b = raw()
            return Image.frombytes("RGB", size, b, "raw", "BGRX")
        g.raw = raw
        g.rect = (mon["left"], mon["top"], mon["width"], mon["height"])
        return g
    except Exception as e:
        log_err(e)
        return ImageGrab.grab

def blocked(p):  # โฟลเดอร์ระบบ ไม่ให้เรียกดู/ดึงไฟล์
    p = os.path.abspath(p).lower()
    for k in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        v = os.environ.get(k)
        if v and (p == os.path.abspath(v).lower() or p.startswith(os.path.abspath(v).lower() + os.sep)): return True
    return False

def list_dir(path):  # path ว่าง = ราก (ไดรฟ์ + Desktop/Documents/Downloads ของผู้ใช้)
    if not path:
        items, home = [], os.path.expanduser("~")
        for nm in ("Desktop", "Documents", "Downloads"):
            q = os.path.join(home, nm)
            if os.path.isdir(q): items.append({"n": nm, "p": q, "d": True, "s": 0, "m": 0})
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if mask >> i & 1:
                q = f"{chr(65 + i)}:\\"
                items.append({"n": q, "p": q, "d": True, "s": 0, "m": 0})
        return {"path": "", "parent": None, "items": items}
    ap = os.path.abspath(path)
    if blocked(ap): raise PermissionError("โฟลเดอร์ระบบ (Windows / Program Files / ProgramData) ไม่เปิดให้เรียกดู")
    items = []
    with os.scandir(ap) as it:
        for e in it:
            try:
                st = e.stat(follow_symlinks=False)
                if getattr(st, "st_file_attributes", 0) & 6: continue  # ไฟล์ซ่อน/ระบบ (เช่น desktop.ini)
                d = e.is_dir(follow_symlinks=False)
                items.append({"n": e.name, "d": d, "s": 0 if d else st.st_size, "m": int(st.st_mtime)})
            except OSError:
                continue
    items.sort(key=lambda x: (not x["d"], x["n"].lower()))
    par = os.path.dirname(ap)
    return {"path": ap, "parent": "" if par == ap else par, "items": items[:4000]}

def send_listing(client, lock, path):
    try:
        try: body = json.dumps(list_dir(path), ensure_ascii=False).encode("utf-8")
        except Exception as e: body = json.dumps({"path": path, "error": str(e)}, ensure_ascii=False).encode("utf-8")
        p = b"L" + body
        with lock:
            client.sendall((len(p) | 0x80000000).to_bytes(4, "little") + p)
    except Exception as e:
        log_err(e)

def send_file_to_client(client, lock, path, cancel=None):  # แพ็กเก็ตไฟล์ = ความยาว|0x80000000 แล้วตามด้วย S ขนาด / N ชื่อ / D ข้อมูล / E จบ / X ข้อผิดพลาด / L รายการไฟล์
    def pkt(t, d=b""):
        p = t + d
        with lock:
            client.sendall((len(p) | 0x80000000).to_bytes(4, "little") + p)
    tmp = None
    try:
        if blocked(path):
            pkt(b"X", "โฟลเดอร์ระบบ ดึงไฟล์ไม่ได้".encode("utf-8"))
            return
        src, name = path, os.path.basename(path)
        if os.path.isdir(path):  # โฟลเดอร์ -> บีบเป็น zip ก่อนส่ง
            if len(path.rstrip("\\/")) <= 2:
                pkt(b"X", "ดึงทั้งไดรฟ์ไม่ได้ เลือกโฟลเดอร์ย่อย".encode("utf-8"))
                return
            tmp = zip_folder(path)
            if tmp is None:
                pkt(b"X", "บีบโฟลเดอร์ไม่ได้ หรือใหญ่เกิน 2 GB".encode("utf-8"))
                return
            src, name = tmp, (os.path.basename(path.rstrip("\\/")) or "folder") + ".zip"
        if not os.path.isfile(src):
            pkt(b"X", f"ไม่พบไฟล์บนเครื่องปลายทาง: {path}".encode("utf-8"))
            return
        pkt(b"S", os.path.getsize(src).to_bytes(8, "little"))
        pkt(b"N", name.encode("utf-8"))
        with open(src, "rb") as f:
            while True:
                if cancel is not None and cancel.is_set():
                    pkt(b"X", "ยกเลิกการดึงไฟล์แล้ว".encode("utf-8"))
                    return
                b = f.read(131072)
                if not b: break
                pkt(b"D", b)
        pkt(b"E")
    except Exception as e:
        log_err(e)
        try: pkt(b"X", f"ส่งไฟล์ไม่สำเร็จ: {e}".encode("utf-8"))
        except Exception: pass
    finally:
        if tmp:
            try: os.remove(tmp)
            except OSError: pass

def bgra_to_vf(size, b):  # BGRA -> VideoFrame ตรง ๆ (เร็วกว่าผ่าน PIL หลายเท่า); บางความกว้าง (เช่น 1366) แถวถูกเติมให้ยาวขึ้น ต้องก๊อปทีละแถว
    w, h = size
    vf = av.VideoFrame(w, h, "bgra")
    pl = vf.planes[0]
    ls, rw = pl.line_size, w * 4
    if ls == rw:
        pl.update(b)
    else:
        buf, mv = bytearray(ls * h), memoryview(b)
        for y in range(h):
            buf[y * ls:y * ls + rw] = mv[y * rw:(y + 1) * rw]
        pl.update(buf)
    return vf

def stream_h264(client, grab, gone, lock, maxw, fps, br):  # คุณภาพคงที่ตามที่ผู้ใช้เลือก ไม่ปรับเองระหว่างใช้งาน
    from fractions import Fraction
    raw = getattr(grab, "raw", None)
    enc, size, n = None, None, 0
    iv = 1 / fps
    nxt = time.time()
    prev_sig = None
    while not gone.is_set():
        try:
            if raw: sz, b = raw()
            else:
                im = grab(); sz = im.size
        except Exception:
            time.sleep(1); continue
        sg = getattr(grab, "sig", None)
        if sg is not None and sg == prev_sig:
            time.sleep(0.004); continue
        prev_sig = sg
        mw = max(min(maxw, sz[0]) // 2 * 2, 320)
        mh = max(sz[1] * mw // sz[0] // 2 * 2, 240)
        if enc is None or size != (mw, mh):
            enc = av.CodecContext.create("libx264", "w")
            enc.width, enc.height, enc.pix_fmt = mw, mh, "yuv420p"
            enc.framerate, enc.time_base = fps, Fraction(1, fps)
            enc.options = {"preset": "ultrafast", "tune": "zerolatency", "bf": "0",
                           "x264-params": f"crf=20:keyint={fps * 2}:intra-refresh=1:vbv-maxrate={br}:vbv-bufsize={max(br // 4, 200)}"}
            enc.open()
            size = (mw, mh)
        vf = bgra_to_vf(sz, b) if raw else av.VideoFrame.from_image(im.convert("RGB"))
        vf = vf.reformat(width=mw, height=mh, format="yuv420p")
        vf.pts = n; n += 1
        for pk in enc.encode(vf):
            d = bytes(pk)
            with lock:  # ส่งตรง ไม่ทิ้งเฟรม (P-frame ทิ้งไม่ได้) เน็ตช้า TCP จะชะลอรอบจับภาพเอง
                client.sendall((len(d) | 0x40000000).to_bytes(4, "little") + d)
        nxt += iv  # นับจังหวะแบบสะสม ไม่ใช่ sleep เท่ากันทุกรอบ
        now = time.time()
        if nxt > now: time.sleep(nxt - now)
        elif now - nxt > iv: nxt = now

def stream_rects(client, grab, gone, lock, fps):  # โหมดเอกสาร/Excel: ส่งเฉพาะกรอบที่เปลี่ยน ขนาดจริง ไม่ย่อ ไม่ผ่านการบีบแบบ video
    raw = getattr(grab, "raw", None)
    iv = 1 / fps
    prev, prev_sig, lossy = None, None, None
    last_change = nxt = time.time()

    def send(box, img, fmt):  # fmt 0 = PNG (ไม่สูญเสีย), 1 = JPEG 4:4:4 (ตัวอักษรสีไม่เพี้ยน)
        buf = io.BytesIO()
        if fmt == 0: img.save(buf, "PNG", compress_level=1)
        else: img.save(buf, "JPEG", quality=DOC_JPEG_Q, subsampling=0)
        d = struct.pack("<HHHHB", box[0], box[1], box[2] - box[0], box[3] - box[1], fmt) + buf.getvalue()
        with lock:
            client.sendall((len(d) | 0x20000000).to_bytes(4, "little") + d)

    while not gone.is_set():
        try:
            if raw: sz, b = raw()
            else:
                cur = grab(); sz = cur.size
        except Exception:
            time.sleep(1); continue
        sg = getattr(grab, "sig", None)
        now = time.time()
        if sg is not None and sg == prev_sig:  # จอไม่เปลี่ยน
            if lossy and now - last_change > 0.4:  # จอนิ่งแล้ว -> ส่งส่วนที่เคยบีบแบบ JPEG ซ้ำแบบคมชัดไม่สูญเสีย
                send(lossy, prev.crop(lossy), 0)
                lossy = None
            time.sleep(0.01)
            continue
        prev_sig, last_change = sg, now
        if raw: cur = Image.frombytes("RGB", sz, b, "raw", "BGRX")
        if prev is None or prev.size != cur.size:
            rects = [(0, 0, cur.width, cur.height)]
        else:
            diff = ImageChops.difference(prev, cur)
            rects = []
            for y in range(0, cur.height, 64):  # หาขอบเขตที่เปลี่ยนทีละแถบ 64 แถว แล้วรวมแถบที่ติดกัน
                bb = diff.crop((0, y, cur.width, min(y + 64, cur.height))).getbbox()
                if not bb: continue
                r = (bb[0], y + bb[1], bb[2], y + bb[3])
                if rects and rects[-1][3] == y:
                    q = rects[-1]; r = (min(q[0], r[0]), q[1], max(q[2], r[2]), r[3]); rects[-1] = r
                else:
                    rects.append(r)
        for r in rects:
            if (r[2] - r[0]) * (r[3] - r[1]) > DOC_LOSSY_AREA:
                send(r, cur.crop(r), 1)
                lossy = r if lossy is None else (min(lossy[0], r[0]), min(lossy[1], r[1]), max(lossy[2], r[2]), max(lossy[3], r[3]))
            else:
                send(r, cur.crop(r), 0)
        prev = cur
        nxt += iv
        now = time.time()
        if nxt > now: time.sleep(nxt - now)
        elif now - nxt > iv: nxt = now

def secure_desktop_active():  # True = หน้าจอปลายทางอยู่บน Secure Desktop (UAC/ล็อกจอ) ซึ่งโปรแกรมนี้จับภาพไม่ได้ (จอดำ)
    try:
        u = ctypes.windll.user32
        u.OpenInputDesktop.restype = ctypes.c_void_p
        h = u.OpenInputDesktop(0, False, 0x0001)
        if not h: return True  # เปิดเดสก์ท็อปที่รับอินพุตอยู่ไม่ได้ = ไม่ใช่เดสก์ท็อปของผู้ใช้
        try:
            buf = ctypes.create_unicode_buffer(256)
            n = ctypes.c_ulong(0)
            if u.GetUserObjectInformationW(ctypes.c_void_p(h), 2, buf, 512, ctypes.byref(n)):
                return buf.value.lower() != "default"
            return False
        finally:
            u.CloseDesktop(ctypes.c_void_p(h))
    except Exception:
        return False

class SysLink:  # ฝั่งโปรแกรมหลัก: คุยกับส่วน SYSTEM (ใช้เฉพาะตอนปลายทางอยู่บน Secure Desktop)
    def __init__(s):
        s.sock, s.lk, s.fail, s.t, s.v = {"g": None, "i": None}, {"g": threading.Lock(), "i": threading.Lock()}, 0.0, 0.0, False
    def _open(s):
        with open(SYS_FILE, encoding="utf-8") as f: d = json.load(f)
        c = socket.create_connection(("127.0.0.1", int(d["port"])), timeout=3)
        try:
            c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            c.sendall(str(d["token"]).encode("latin1"))
            n = recv_exact(c, 1)
            ver = recv_exact(c, n[0]).decode() if n else ""
            if ver != APP_VER: raise RuntimeError("ส่วน SYSTEM คนละรุ่น: " + ver)
            c.settimeout(5)
            return c
        except Exception:
            c.close(); raise
    def _get(s, k):
        if s.sock[k] is None:
            if time.time() - s.fail < 3: raise ConnectionError("ส่วน SYSTEM ยังไม่พร้อม")
            try: s.sock[k] = s._open()
            except Exception:
                s.fail = time.time(); raise
        return s.sock[k]
    def _drop(s, k):
        try: s.sock[k].close()
        except Exception: pass
        s.sock[k], s.fail = None, time.time()
    def close(s):
        for k in ("g", "i"):
            try: s.sock[k].close()
            except Exception: pass
            s.sock[k] = None
    def usable(s):
        try:
            with s.lk["g"]: s._get("g")
            return True
        except Exception:
            return False
    def route(s):  # ส่วน SYSTEM พร้อมไหม -> ส่งอินพุตผ่านส่วน SYSTEM ตลอด (UAC บนจอปกติก็กดได้) ไม่พร้อมก็ใช้ทางเดิม
        try:
            with s.lk["i"]: s._get("i")
            return True
        except Exception:
            return False
    def active(s):  # ปลายทางอยู่บน Secure Desktop ตอนนี้ไหม (แคช 0.1 วินาที)
        n = time.time()
        if n - s.t > 0.1: s.v, s.t = secure_desktop_active(), n
        return s.v
    def grab(s, rect):
        with s.lk["g"]:
            try:
                c = s._get("g")
                c.sendall(b"G" + struct.pack("<iiii", *rect))
                h = recv_exact(c, 4)
                d = recv_exact(c, int.from_bytes(h, "little")) if h else None
                if not d: raise ConnectionError("ส่วน SYSTEM ไม่ตอบ")
                im = Image.open(io.BytesIO(d)); im.load()
                return im.convert("RGB")
            except Exception:
                s._drop("g"); raise
    def inp(s, data):
        with s.lk["i"]:
            try: s._get("i").sendall(data)
            except Exception: s._drop("i")

def sys_wrap(grab, sl):  # ตอนอยู่บน Secure Desktop ใช้ภาพจากส่วน SYSTEM นอกนั้นใช้ตัวจับภาพเดิมทุกอย่าง (ไม่กระทบความเร็วปกติ)
    rect = getattr(grab, "rect", None)
    if not rect: return grab
    st = {"n": 0, "prev": None}
    def sec():
        im = sl.grab(rect)
        b = im.tobytes()
        if b != st["prev"]: st["n"] += 1; st["prev"] = b
        return im
    def wg():
        if sl.active():
            try:
                im = sec(); wg.sig = ("s", st["n"]); return im
            except Exception as e:
                log_err(e)
        r = grab(); wg.sig = getattr(grab, "sig", None); return r
    def wr():
        if sl.active():
            try:
                im = sec(); wg.sig = ("s", st["n"]); return im.size, im.tobytes("raw", "BGRX")
            except Exception as e:
                log_err(e)
        r = grab.raw(); wg.sig = getattr(grab, "sig", None); return r
    wg.rect = rect
    if hasattr(grab, "raw"): wg.raw = wr
    return wg

def uac_notifier(client, gone, lock, sl=None):  # แจ้งฝั่งผู้คุม (แพ็กเก็ต B) เมื่อปลายทางเข้า/ออกจากหน้าต่าง UAC รุ่นเก่าข้ามแพ็กเก็ตนี้เอง
    cur, cnt = False, 0
    while not gone.wait(0.4):
        now = secure_desktop_active() and not (sl is not None and sl.usable())  # ส่วน SYSTEM พร้อม = ภาพมาตามปกติ ไม่ต้องขึ้นข้อความ
        if now == cur: cnt = 0; continue
        cnt += 1
        if cnt < 2: continue  # ต้องเห็นซ้ำ 2 รอบกันกะพริบ
        cur, cnt = now, 0
        try:
            with lock:
                client.sendall((2 | 0x80000000).to_bytes(4, "little") + b"B" + (b"1" if cur else b"0"))
        except Exception:
            return

def handle_control_client(client, q=1, h264=False, mon_idx=1, who=""):
    maxw, fps, _ = QUALITY[q]
    if maxw == 0: maxw = 1 << 16
    lock = threading.Lock()
    watcher_add(who)
    sl = SysLink() if cfg.get("sys_on") and is_admin() else None
    try:
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)  # เล็กไว้: ภาพที่ค้างในบัฟเฟอร์คือภาพเก่า (512KB ทำให้หน่วงเพิ่ม 2-3 เท่าบนลิงก์ช้า ความเร็วเท่าเดิม)
        grab = make_grabber(mon_idx)
        if sl is not None: grab = sys_wrap(grab, sl)
        w, h = grab().size
        client.sendall(w.to_bytes(4, "little") + h.to_bytes(4, "little"))
        gone = threading.Event()
        threading.Thread(target=apply_input_loop, args=(client, gone, lock), kwargs={"sysl": sl}, daemon=True).start()
        threading.Thread(target=uac_notifier, args=(client, gone, lock, sl), daemon=True).start()
        if q == 3:  # โหมดเอกสาร
            stream_rects(client, grab, gone, lock, fps)
            return
        if h264:
            try:
                stream_h264(client, grab, gone, lock, maxw, fps, H264_KBPS[q])
                return
            except Exception as e:
                log_err(e)
                # ยังไม่เคยส่งข้อมูลวิดีโอสำเร็จ (encoder พังตั้งแต่เฟรมแรก) -> ไม่ตัดสาย ส่ง JPEG ต่อในสายเดิมแทน
                if gone.is_set():
                    return
        slot = queue.Queue(maxsize=1)  # เก็บแค่เฟรมล่าสุด เน็ตช้าก็ทิ้งเฟรมเก่า ภาพไม่ค้างสะสม
        st = {"send": 0.0}
        def sender():
            try:
                while not gone.is_set():
                    try: data = slot.get(timeout=0.2)
                    except queue.Empty: continue
                    t = time.time()
                    with lock:
                        client.sendall(len(data).to_bytes(4, "little") + data)
                    st["send"] = time.time() - t
            except Exception as e:
                log_err(e)
                gone.set()
        threading.Thread(target=sender, daemon=True).start()
        prev, prev_sig, qual, scl, iv = None, None, JPEG_Q, 1.0, 1 / fps  # คุณภาพคงที่ ไม่ปรับเอง
        while not gone.is_set():
            t0 = time.time()
            try:
                frame = grab()
            except Exception:  # เซิร์ฟเวอร์: RDP ถูกตัด/จอล็อก จับภาพไม่ได้ชั่วคราว
                time.sleep(1)
                continue
            sg = getattr(grab, "sig", None)
            if sg is not None and sg == prev_sig:
                time.sleep(0.005)
                continue
            prev_sig = sg
            mw = max(int(maxw * scl), 320)
            if frame.width > mw:
                frame = frame.resize((mw, frame.height * mw // frame.width), Image.BILINEAR)
            if sg is None:  # ไม่มี mss -> เทียบภาพแบบช้า
                if prev is not None and prev.size == frame.size and ImageChops.difference(prev, frame).getbbox() is None:
                    time.sleep(0.01)
                    continue
                prev = frame
            buf = io.BytesIO()
            frame.save(buf, format="JPEG", quality=qual)
            data = buf.getvalue()
            try: slot.put_nowait(data)
            except queue.Full:
                try: slot.get_nowait()
                except queue.Empty: pass
                slot.put_nowait(data)
            dt = time.time() - t0
            if dt < iv:
                time.sleep(iv - dt)
    except Exception as e:
        log_err(e)
    finally:
        watcher_remove(who)
        if sl is not None: sl.close()
        try: client.close()
        except Exception: pass

def apply_input_loop(client, gone, lock, files_only=False, sysl=None):
    fh, rem, fp = None, 0, None
    cancel = threading.Event()
    def reply(t, d):  # ตอบกลับฝั่งส่ง (W วางแล้ว / R ปฏิเสธ) รุ่นเก่าไม่รู้จัก ข้ามไปเฉยๆ
        try:
            with lock: client.sendall((len(t + d) | 0x80000000).to_bytes(4, "little") + t + d)
        except Exception: pass
    try: peer = client.getpeername()[0]
    except Exception: peer = "?"
    try:
        while True:
            t = recv_exact(client, 1)
            if not t: break
            t = t.decode("latin1")
            if files_only and t in "MDUWKJ": break  # โหมดไฟล์: ห้ามคุมเมาส์/คีย์บอร์ด ตัดการเชื่อมต่อทันที
            if t == "M":
                b = recv_exact(client, 8)
                x = int.from_bytes(b[0:4], "little", signed=True)
                y = int.from_bytes(b[4:8], "little", signed=True)
                if sysl is not None and sysl.route(): sysl.inp(b"M" + b)  # Secure Desktop: ส่งให้ส่วน SYSTEM
                else: set_cursor(x, y)
            elif t == "D":
                b = recv_exact(client, 1)[0]
                if sysl is not None and sysl.route(): sysl.inp(b"D" + bytes([b]))
                else: mouse_event(MOUSE_FLAGS_DOWN.get(b, 0x0002))
            elif t == "U":
                b = recv_exact(client, 1)[0]
                if sysl is not None and sysl.route(): sysl.inp(b"U" + bytes([b]))
                else: mouse_event(MOUSE_FLAGS_UP.get(b, 0x0004))
            elif t == "W":
                b = recv_exact(client, 4)
                delta = int.from_bytes(b, "little", signed=True)
                if sysl is not None and sysl.route(): sysl.inp(b"W" + b)
                else: mouse_event(0x0800, ctypes.c_uint32(delta).value)
            elif t == "K":
                b = recv_exact(client, 4)
                vk = int.from_bytes(b, "little", signed=True)
                if sysl is not None and sysl.route(): sysl.inp(b"K" + b)
                else: keybd_event(vk, False)
            elif t == "J":
                b = recv_exact(client, 4)
                vk = int.from_bytes(b, "little", signed=True)
                if sysl is not None and sysl.route(): sysl.inp(b"J" + b)
                else: keybd_event(vk, True)
            elif t == "F":  # เริ่มรับไฟล์: ชื่อ(2+n) ขนาด(8) ชื่อมีพาธโฟลเดอร์นำหน้าได้ (3.2.0+) ไม่มี/ใช้ไม่ได้ = เดสก์ท็อป (รุ่นเก่าตัดเหลือชื่อไฟล์ วางที่เดสก์ท็อปเสมอ)
                n = int.from_bytes(recv_exact(client, 2), "little")
                name = recv_exact(client, n).decode("utf-8", "replace")
                rem = int.from_bytes(recv_exact(client, 8), "little")
                if fh: fh.close(); fh = None
                dest = ntpath.dirname(name)
                if dest and not dest_ok(dest):  # โฟลเดอร์ระบบ/Startup/ไม่มีอยู่ -> ไม่รับ ข้อมูล C ที่ตามมาจะถูกทิ้ง
                    conn_log(f"{peer} | ปฏิเสธไฟล์เข้ามา (โฟลเดอร์ไม่อนุญาต): {name}")
                    reply(b"R", "โฟลเดอร์ปลายทางไม่อนุญาตหรือไม่มีอยู่".encode("utf-8"))
                    continue
                fp = unique_path(name, dest or None)
                conn_log(f"{peer} | ส่งไฟล์เข้ามา: {name} ({rem} ไบต์) -> {fp}")
                fh = open(fp, "wb")
                if rem == 0:
                    fh.close(); fh = None
                    reply(b"W", fp.encode("utf-8"))
            elif t == "C":  # ข้อมูลไฟล์ทีละก้อน
                n = int.from_bytes(recv_exact(client, 4), "little")
                if n > (1 << 20): break
                d = recv_exact(client, n)
                if fh:
                    fh.write(d); rem -= n
                    if rem <= 0:
                        fh.close(); fh = None
                        reply(b"W", fp.encode("utf-8"))
            elif t == "G":  # ขอดึงไฟล์จากเครื่องนี้
                n = int.from_bytes(recv_exact(client, 2), "little")
                path = recv_exact(client, n).decode("utf-8", "replace")
                cancel.clear()
                conn_log(f"{peer} | ดึงไฟล์/โฟลเดอร์: {path}")
                threading.Thread(target=send_file_to_client, args=(client, lock, path, cancel), daemon=True).start()
            elif t == "Z":  # ขอยกเลิกการดึงไฟล์
                cancel.set()
            elif t == "Y":  # ยกเลิกการส่งไฟล์เข้ามา: ลบไฟล์ที่ได้ไม่ครบ
                if fh:
                    fh.close(); fh = None
                    try: os.remove(fp)
                    except OSError: pass
            elif t == "L":  # ขอรายการไฟล์ในโฟลเดอร์
                n = int.from_bytes(recv_exact(client, 2), "little")
                path = recv_exact(client, n).decode("utf-8", "replace")
                threading.Thread(target=send_listing, args=(client, lock, path), daemon=True).start()
    except Exception as e:
        log_err(e)
    finally:
        if fh: fh.close()
        gone.set()

def handle_files_client(client):
    lock = threading.Lock()
    try:
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 524288)
        client.sendall((1).to_bytes(4, "little") * 2)  # ขนาดจอหลอก 1x1 (ฝั่งดูจอใช้หารขนาด ห้ามเป็น 0)
        apply_input_loop(client, threading.Event(), lock, True)
    except Exception as e:
        log_err(e)
    finally:
        try: client.close()
        except Exception: pass

# ---------- viewer (client side) ----------
ROOT = [None]
STATUS = [None]
STATUS2 = [None]  # แถบสถานะในหน้าตั้งค่า (หน้าตั้งค่าทับแถบสถานะหลัก)
START = time.time()

def notify(msg, bad=False):
    log_err(msg) if bad else None
    def f():
        for lb in (STATUS[0], STATUS2[0]):
            if lb:
                lb.config(text=msg, fg=("#ff5252" if bad else "#2ecc71") if ADMIN[0] else ("#c62828" if bad else "#1b7f3b"))
    if ROOT[0]:
        ROOT[0].after(0, f)

def open_viewer(ips, q=1, auto=None, files_only=False, mon=1):  # auto: None ปกติ, "send"/"pull" = เปิดแล้วเด้งกล่องส่ง/ดึงไฟล์ให้เลย (โหมดแอดมิน); mon: จอปลายทางที่เลือก (1=จอหลัก)
    sock, fail = None, ""
    for ip in ips:
        notify(f"กำลังเชื่อมต่อ {ip} ...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.settimeout(5)
        try:
            s.connect((ip, CTRL_PORT))
            s.sendall(b"T" if files_only else b"V" + bytes([q]) + (b"H" if av is not None else b"-") + bytes([max(1, min(250, mon))]))
            sock = s
            break
        except socket.timeout:
            fail = f"หมดเวลา: {ip} ไม่ตอบ (Firewall บล็อก / NetBird ยังไม่ต่อ / ปลายทางปิดอยู่)"
        except ConnectionRefusedError:
            fail = f"{ip} ปฏิเสธ: โปรแกรมปลายทางไม่ได้เปิด หรือเปิดพอร์ต {CTRL_PORT} ไม่ได้"
        except Exception as e:
            fail = f"เชื่อมต่อ {ip} ไม่ได้: {e}"
        s.close()
    if sock is None:
        notify(f"{fail} (ลอง {len(ips)} ที่อยู่)", True)
        return
    notify(f"รอปลายทาง {ip} กดอนุญาต (สูงสุด 60 วินาที) ...")
    try:
        sock.settimeout(60)
        hdr = recv_exact(sock, 8)
        sock.settimeout(None)
    except socket.timeout:
        notify(f"ปลายทาง {ip} ไม่กดอนุญาตภายใน 60 วินาที", True)
        sock.close()
        return
    except Exception as e:
        notify(f"การเชื่อมต่อ {ip} ขาด: {e}", True)
        return
    if not hdr:
        notify(f"ปลายทาง {ip} ไม่อนุญาตให้ควบคุม", True)
        sock.close()
        return
    rw = int.from_bytes(hdr[0:4], "little")
    rh = int.from_bytes(hdr[4:8], "little")
    notify(f"เชื่อมต่อ {ip} สำเร็จ")
    ROOT[0].after(0, lambda: viewer_window(sock, ip, rw, rh, QUALITY[q][2], q == 3, auto, files_only))

def viewer_window(sock, ip, remote_w, remote_h, qlabel="", sharp=False, auto=None, files_only=False):
    from PIL import ImageTk
    bar_bg, bar_fg = ("#2a0808", "#ff6b6b") if ADMIN[0] else ("#101a2e", "#3ddc84")
    win = tk.Toplevel(ROOT[0])
    win.title(f"ส่ง/ดึงไฟล์: {ip}" if files_only else f"ควบคุม: {ip}   (F11 = เต็มจอ)")
    win.geometry("760x96" if files_only else "1100x700")
    bar = tk.Frame(win, bg=bar_bg)
    bar.pack(fill="x")
    lbl_v = tk.Label(bar, text=(f"● ไฟล์ {ip}" if files_only else f"● เชื่อมต่อ {ip} • {qlabel}"), bg=bar_bg, fg=bar_fg, font=FNT(9, "bold"))
    lbl_v.pack(side="left", padx=10, pady=4)
    canvas = tk.Canvas(win, bg="black", highlightthickness=0)
    if not files_only: canvas.pack(fill="both", expand=True)
    latest = {"d": None}
    g = {"ox": 0, "oy": 0, "dw": 1, "dh": 1, "item": None, "photo": None}
    alive = [True]
    fs = [False]

    rf = {"fh": None, "path": "", "size": 0, "got": 0, "t0": 0.0, "last": 0.0, "name": ""}
    slock = threading.Lock()
    xf = {"w": None}
    cancel_up = threading.Event()
    pull = {"q": [], "n": 0, "i": 0, "dir": None}
    br = {"fill": None}
    acks = {"n": 0}

    def say(text, color="#3ddc84"):
        win.after(0, lambda: lbl_v.config(text=text, fg=color))

    def fmt_size(n):
        for u in ("B", "KB", "MB", "GB"):
            if n < 1024 or u == "GB": return f"{n:.0f} B" if u == "B" else f"{n:.1f} {u}"
            n /= 1024

    def xfer_ui(title, done, total, t0):  # หน้าต่างความคืบหน้า (เรียกในเธรด Tk)
        if not (xf["w"] and xf["w"].winfo_exists()):
            w = tk.Toplevel(win)
            w.title("โอนไฟล์"); w.configure(bg=tc("#101a2e")); w.resizable(False, False); w.transient(win)
            lbl = tk.Label(w, bg=tc("#101a2e"), fg=tc("#e7f0ff"), anchor="w", width=62); lbl.pack(padx=14, pady=(12, 4))
            bar = ttk.Progressbar(w, length=440, maximum=100); bar.pack(padx=14)
            info = tk.Label(w, bg=tc("#101a2e"), fg=tc("#8fa3c4"), anchor="w", width=62); info.pack(padx=14, pady=4)
            ttk.Button(w, text="ยกเลิก", command=xfer_cancel).pack(pady=(4, 12))
            w.protocol("WM_DELETE_WINDOW", xfer_cancel)
            xf.update(w=w, lbl=lbl, bar=bar, info=info)
        pct = 100 * done / total if total else 0
        xf["lbl"].config(text=title)
        xf["bar"]["value"] = pct
        xf["info"].config(text=f"{fmt_size(done)} / {fmt_size(total)}  ({pct:.0f}%)   {fmt_size(done / max(time.time() - t0, 0.001))}/วินาที")

    def xfer_close():
        if xf["w"] and xf["w"].winfo_exists(): xf["w"].destroy()
        xf["w"] = None

    def xfer_cancel():
        cancel_up.set()
        pull["q"].clear()
        send(b"Z"); send(b"Y")
        xfer_close()
        say("ยกเลิกการโอนไฟล์แล้ว", "#ff6b6b")

    def pull_next():
        if pull["q"]:
            pull["i"] += 1
            pb = pull["q"].pop(0).encode("utf-8")
            send(b"G", len(pb).to_bytes(2, "little"), pb)
        else:
            win.after(0, xfer_close)
            if pull["n"]:
                say(f"ดึงไฟล์เสร็จ {pull['n']} ไฟล์ ที่ {pull.get('dir') or 'เดสก์ท็อปเครื่องนี้'}")
                pull["n"] = 0

    def start_pull(paths):  # ดึงทีละไฟล์ตามลำดับ (ฝั่งนี้ส่งคำขอถัดไปเมื่อไฟล์ก่อนหน้าเสร็จ)
        if rf["fh"] or pull["q"]:
            say("กำลังโอนไฟล์อยู่ รอให้เสร็จก่อน", "#ff6b6b")
            return
        d = filedialog.askdirectory(parent=win, title="เลือกโฟลเดอร์ที่จะวางไฟล์ที่ดึงมา", initialdir=cfg.get("last_recv_dir") or desktop_dir())
        if not d: return
        cfg["last_recv_dir"] = d; save_config(cfg)
        pull.update(q=list(paths), n=len(paths), i=0, dir=d)
        pull_next()

    def on_file_packet(p):
        t, d = p[:1], p[1:]
        if t == b"S":
            rf["size"] = int.from_bytes(d[:8], "little")
        elif t == b"N":
            if rf["fh"]: rf["fh"].close()
            rf["path"] = unique_path(d.decode("utf-8", "replace"), pull.get("dir"))
            rf["fh"] = open(rf["path"], "wb")
            rf.update(got=0, t0=time.time(), last=0.0, name=os.path.basename(rf["path"]))
        elif t == b"D" and rf["fh"]:
            rf["fh"].write(d)
            rf["got"] += len(d)
            if time.time() - rf["last"] > 0.12:
                rf["last"] = time.time()
                title, got, size, t0 = f"ดึงไฟล์ {pull['i']}/{pull['n']}: {rf['name']}", rf["got"], rf["size"], rf["t0"]
                win.after(0, lambda: xfer_ui(title, got, size, t0))
        elif t == b"E" and rf["fh"]:
            rf["fh"].close(); rf["fh"] = None
            say(f"รับไฟล์แล้ว: {rf['path']}")
            pull_next()
        elif t == b"X":
            if rf["fh"]:  # ยกเลิก/ผิดพลาดกลางทาง ลบไฟล์ที่ได้ไม่ครบ
                rf["fh"].close(); rf["fh"] = None
                try: os.remove(rf["path"])
                except OSError: pass
            say(d.decode("utf-8", "replace"), "#ff6b6b")
            pull_next()
        elif t == b"W":  # ปลายทาง (3.2.0+) ยืนยันว่าวางไฟล์ที่ส่งไปแล้ว
            acks["n"] += 1
        elif t == b"R":  # ปลายทางไม่รับโฟลเดอร์ที่เลือก -> หยุดส่ง
            cancel_up.set()
            say(d.decode("utf-8", "replace"), "#ff6b6b")
            win.after(0, xfer_close)
        elif t == b"B":  # ปลายทางกำลังแสดงหน้าต่าง UAC/ล็อกจอ (จับภาพไม่ได้) -> ขึ้นข้อความแทนภาพดำ
            on = d[:1] == b"1"
            def _uac():
                if on:
                    if g.get("uac") is None:
                        g["uac"] = tk.Label(canvas, text="ปลายทางกำลังแสดงหน้าต่างขออนุญาต (UAC)\nให้คนหน้าเครื่องกดอนุญาต แล้วภาพจะกลับมาเอง",
                                            bg="#10192b", fg="#ffd166", font=(RFONT(), 16, "bold"), padx=24, pady=16, justify="center")
                    g["uac"].place(relx=0.5, rely=0.5, anchor="center"); g["uac"].lift()
                elif g.get("uac") is not None:
                    g["uac"].place_forget()
            win.after(0, _uac)
        elif t == b"L" and br["fill"]:
            try: info = json.loads(d.decode("utf-8"))
            except ValueError: return
            win.after(0, lambda: br["fill"](info))

    dec = [None]
    fb, fb_lock = [None], threading.Lock()
    flt = Image.LANCZOS if sharp else Image.BILINEAR  # โหมดเอกสาร: ย่อภาพให้คมกว่า (ช้ากว่าเล็กน้อยแต่อัปเดตไม่ถี่)
    slot = {"f": None}
    ev = threading.Event()

    def recv_frames():  # รับ+ถอดรหัสทุกเฟรมตามลำดับ (จำเป็นต่อ H.264) แต่ไม่แปลงภาพ ปล่อยให้ render_loop ทำเฉพาะเฟรมล่าสุด
        try:
            while alive[0]:
                lb = recv_exact(sock, 4)
                if not lb: break
                n = int.from_bytes(lb, "little")
                data = recv_exact(sock, n & 0x1FFFFFFF)
                if not data: break
                if n & 0x80000000:
                    on_file_packet(data)
                    continue
                if n & 0x40000000:
                    if dec[0] is None: dec[0] = av.CodecContext.create("h264", "r")
                    fr = dec[0].decode(av.Packet(data))
                    if not fr: continue
                    slot["f"] = fr[-1]
                elif n & 0x20000000:  # โหมดเอกสาร: กรอบที่เปลี่ยน (x,y,w,h,ชนิด) วางลงภาพเต็มที่เก็บไว้
                    x, y, _w, _h, _f = struct.unpack("<HHHHB", data[:9])
                    im = Image.open(io.BytesIO(data[9:]))
                    im.load()
                    with fb_lock:
                        if fb[0] is None: fb[0] = Image.new("RGB", (remote_w, remote_h))
                        fb[0].paste(im if im.mode == "RGB" else im.convert("RGB"), (x, y))
                    slot["f"] = fb[0]
                else:
                    im = Image.open(io.BytesIO(data))
                    im.load()
                    slot["f"] = im
                ev.set()
        except Exception as e:
            log_err(e)
        if rf["fh"]: rf["fh"].close()
        alive[0] = False
        ev.set()

    def render_loop():  # ย่อเป็นขนาดที่แสดงจริงด้วย swscale (เร็วกว่า PIL ย่อ ~4 เท่า) และวาดใหม่เมื่อหน้าต่างเปลี่ยนขนาดแม้จอปลายทางนิ่ง
        last, dims = None, None
        while alive[0]:
            ev.wait(0.1)
            ev.clear()
            f = slot["f"]
            slot["f"] = None
            want = g.get("want")
            if f is None and (last is None or want == dims):
                continue
            if f is not None: last = f
            dims = want
            try:
                if isinstance(last, Image.Image):
                    with fb_lock:  # ภาพเต็มของโหมดเอกสารถูกแก้ในเธรดรับ ต้องล็อกตอนย่อ
                        im = last.resize(want, flt) if want and want[0] > 1 else last.copy()
                elif want and want[0] > 1:
                    im = last.reformat(width=want[0], height=want[1], format="rgb24").to_image()
                else:
                    im = last.to_image()
                latest["d"] = im
            except Exception as e:
                log_err(e)

    def poll():
        cw, ch = canvas.winfo_width() or 1, canvas.winfo_height() or 1
        sc = min(cw / remote_w, ch / remote_h)
        dw, dh = max(int(remote_w * sc), 1), max(int(remote_h * sc), 1)
        g.update(ox=(cw - dw) // 2, oy=(ch - dh) // 2, dw=dw, dh=dh, want=(dw, dh))
        im = latest["d"]
        latest["d"] = None
        if im is not None:
            try:
                if im.size != (dw, dh): im = im.resize((dw, dh), flt)
                ph = g["photo"]
                if ph is not None and ph.width() == dw and ph.height() == dh:
                    ph.paste(im)  # ใช้ภาพ Tk เดิม ไม่สร้างใหม่ทุกเฟรม
                else:
                    g["photo"] = ImageTk.PhotoImage(im)
                    if g["item"] is None:
                        g["item"] = canvas.create_image(g["ox"], g["oy"], anchor="nw", image=g["photo"])
                    else:
                        canvas.itemconfig(g["item"], image=g["photo"])
                canvas.coords(g["item"], g["ox"], g["oy"])
            except Exception as e:
                log_err(e)
        if alive[0]:
            win.after(8, poll)
        else:
            win.title(f"ตัดการเชื่อมต่อ: {ip}")
            lbl_v.config(text=f"● ตัดการเชื่อมต่อ {ip}", fg="#ff6b6b")

    def scaled(e):
        x = int((e.x - g["ox"]) * remote_w / g["dw"])
        y = int((e.y - g["oy"]) * remote_h / g["dh"])
        return max(0, min(remote_w - 1, x)), max(0, min(remote_h - 1, y))

    def send(*parts):
        try:
            with slock:
                sock.sendall(b"".join(parts))
        except Exception as e:
            log_err(e)

    def ask_remote_dir(cb):  # เลือกโฟลเดอร์ปลายทางบนเครื่องที่ต่ออยู่ ทุกครั้งก่อนส่ง (วางทับในหน้าต่างนี้ ไม่เปิดหน้าต่างใหม่) cb(พาธ) หรือไม่เรียกถ้ายกเลิก
        if files_only: win.geometry("760x520")
        dim = tk.Frame(win, bg=tc("#2c3e5c")); dim.place(x=0, y=0, relwidth=1, relheight=1)
        box = tk.Frame(dim, bg=tc("#101a2e"), highlightbackground=tc("#2fa8ff"), highlightthickness=3); box.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(box, text="ส่งไฟล์ไปวางที่โฟลเดอร์ไหนของเครื่องปลายทาง", bg=tc("#101a2e"), fg=tc("#e7f0ff"), font=FNT(14, "bold")).pack(anchor="w", padx=20, pady=(16, 6))
        saved = br["fill"]
        def request(path):
            pb = path.encode("utf-8"); send(b"L", len(pb).to_bytes(2, "little"), pb)
        def done(path):
            br["fill"] = saved
            try: dim.destroy()
            except tk.TclError: pass
            if path is not None: cb(path)
        col = dict(bg=tc("#101a2e"), acc=tc("#2fa8ff"), fg=tc("#e7f0ff"), sub=tc("#8fa3c4"), bad="#ff6b6b", go="Accent.TButton", ghost="Ghost.TButton")
        br["fill"] = build_dir_chooser(box, col, request, done)  # ผลรายการจากปลายทางเข้าที่นี่ชั่วคราว (คืนให้หน้าต่างเรียกดูไฟล์เมื่อปิด)
        dim.lift(); request("")

    def send_files(paths, dest=None):
        paths = [x for x in paths if os.path.isfile(x)]
        if not paths: return
        cancel_up.clear()
        acks["n"] = 0
        def run():
            for k, x in enumerate(paths, 1):
                name, size = os.path.basename(x), os.path.getsize(x)
                t0, last, done = time.time(), 0.0, 0
                try:
                    nb = (ntpath.join(dest, name) if dest else name).encode("utf-8")
                    send(b"F", len(nb).to_bytes(2, "little"), nb, size.to_bytes(8, "little"))
                    with open(x, "rb") as f:
                        while alive[0] and not cancel_up.is_set():
                            b = f.read(131072)
                            if not b: break
                            send(b"C", len(b).to_bytes(4, "little"), b)
                            done += len(b)
                            if time.time() - last > 0.12:
                                last = time.time()
                                win.after(0, lambda d=done: xfer_ui(f"ส่งไฟล์ {k}/{len(paths)}: {name}", d, size, t0))
                except Exception as e:
                    log_err(e)
                    say(f"ส่ง {name} ไม่สำเร็จ: {e}", "#ff6b6b")
                    win.after(0, xfer_close)
                    return
                if cancel_up.is_set(): return
            win.after(0, xfer_close)
            where = "เดสก์ท็อปเครื่องปลายทาง"
            if dest:  # รอคำยืนยัน W จากปลายทางรุ่นใหม่ (รุ่นเก่าไม่ตอบ = วางที่เดสก์ท็อป)
                end = time.time() + 3
                while acks["n"] < len(paths) and time.time() < end and alive[0] and not cancel_up.is_set(): time.sleep(0.1)
                if cancel_up.is_set(): return
                where = dest if acks["n"] >= len(paths) else "เดสก์ท็อปเครื่องปลายทาง (ปลายทางเป็นรุ่นเก่า ยังไม่รองรับการเลือกโฟลเดอร์)"
            say(f"ส่งไฟล์แล้ว {len(paths)} ไฟล์ ไปที่ {where}")
        threading.Thread(target=run, daemon=True).start()

    def pick_send():
        ps = filedialog.askopenfilenames(parent=win)
        if ps: ask_remote_dir(lambda d: send_files(list(ps), d))

    def open_browser():  # เรียกดูไฟล์ในเครื่องปลายทาง
        b = tk.Toplevel(win)
        b.title("เรียกดูไฟล์ในเครื่องปลายทาง"); b.geometry("700x500"); b.configure(bg=tc("#101a2e"))
        cur = {"parent": None, "items": {}}
        top = tk.Frame(b, bg=tc("#101a2e")); top.pack(fill="x", padx=10, pady=8)
        lbl = tk.Label(top, text="กำลังโหลด ...", bg=tc("#101a2e"), fg=tc("#2fa8ff"), anchor="w")
        def go(path):
            lbl.config(text="กำลังโหลด ...", fg=tc("#2fa8ff"))
            pb = path.encode("utf-8")
            send(b"L", len(pb).to_bytes(2, "little"), pb)
        ttk.Button(top, text="↑ ขึ้นไป", style="Ghost.TButton", command=lambda: go(cur["parent"] or "")).pack(side="left")
        lbl.pack(side="left", padx=10, fill="x", expand=True)
        bot = tk.Frame(b, bg=tc("#101a2e")); bot.pack(side="bottom", fill="x", padx=10, pady=8)
        mid = tk.Frame(b, bg=tc("#101a2e")); mid.pack(fill="both", expand=True, padx=10)
        tree = ttk.Treeview(mid, columns=("size", "mod"), selectmode="extended")
        tree.heading("#0", text="ชื่อ"); tree.heading("size", text="ขนาด"); tree.heading("mod", text="แก้ไขล่าสุด")
        tree.column("#0", width=360); tree.column("size", width=90, anchor="e"); tree.column("mod", width=150, anchor="center")
        sb = ttk.Scrollbar(mid, orient="vertical", command=tree.yview); tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); tree.pack(side="left", fill="both", expand=True)

        def fill(info):
            if not b.winfo_exists(): return
            if info.get("error"):
                lbl.config(text=info["error"], fg="#ff6b6b")
                return
            cur.update(parent=info["parent"], items={})
            lbl.config(text=info["path"] or "เครื่องนี้ (ไดรฟ์และโฟลเดอร์ผู้ใช้)", fg=tc("#2fa8ff"))
            tree.delete(*tree.get_children())
            for i, it in enumerate(info["items"]):
                cur["items"][str(i)] = (it.get("p") or ntpath.join(info["path"], it["n"]), it["d"])
                tree.insert("", "end", iid=str(i), text=("▸ " if it["d"] else "") + it["n"],
                            values=("" if it["d"] else fmt_size(it["s"]), time.strftime("%Y-%m-%d %H:%M", time.localtime(it["m"])) if it["m"] else ""))

        def do_pull():
            files = [cur["items"][i][0] for i in tree.selection() if len(cur["items"][i][0].rstrip("\\/")) > 2]
            if not files:
                messagebox.showinfo("ดึงไฟล์", "เลือกไฟล์หรือโฟลเดอร์ก่อน (โฟลเดอร์จะถูกบีบเป็น zip / ดึงทั้งไดรฟ์ไม่ได้)", parent=b)
                return
            start_pull(files)

        def open_sel(e=None):
            sel = tree.selection()
            if len(sel) == 1 and cur["items"][sel[0]][1]: go(cur["items"][sel[0]][0])
            elif sel: do_pull()

        def close_b():
            br["fill"] = None
            b.destroy()
        ttk.Button(bot, text="ดึงที่เลือก (โฟลเดอร์=zip)", style="Accent.TButton", command=do_pull).pack(side="right")
        ttk.Button(bot, text="ปิด", style="Ghost.TButton", command=close_b).pack(side="right", padx=8)
        tk.Label(bot, text="ดับเบิลคลิกโฟลเดอร์เพื่อเปิด / เลือกหลายไฟล์ได้ (Ctrl, Shift) / ไฟล์ไปอยู่บนเดสก์ท็อปเครื่องนี้", bg=tc("#101a2e"), fg=tc("#8fa3c4")).pack(side="left")
        tree.bind("<Double-1>", open_sel)
        b.protocol("WM_DELETE_WINDOW", close_b)
        br["fill"] = fill
        go("")

    mv = {"p": None, "t": None}
    def flush_move():  # ส่งตำแหน่งล่าสุดที่ค้างอยู่ (ถ้ามี)
        if mv["t"] is not None:
            try: win.after_cancel(mv["t"])
            except Exception: pass
            mv["t"] = None
        p, mv["p"] = mv["p"], None
        if p: send(b"M", p[0].to_bytes(4, "little", signed=True), p[1].to_bytes(4, "little", signed=True))
    def on_move(e, now=False):
        mv["p"] = scaled(e)  # เก็บแค่ตำแหน่งล่าสุด ไม่ส่งทุกการขยับ (เดิมส่งเป็นร้อยแพ็กเก็ตต่อวินาที เมาส์ค้างสะสมบนลิงก์ช้า)
        if now: flush_move()
        elif mv["t"] is None: mv["t"] = win.after(16, flush_move)
    def on_down(e, btn):
        on_move(e, True)
        send(b"D", bytes([btn]))
    def on_up(e, btn):
        flush_move()  # ปล่อยปุ่มที่ตำแหน่งสุดท้ายที่ลากถึง
        send(b"U", bytes([btn]))
    def on_wheel(e):
        send(b"W", int(e.delta).to_bytes(4, "little", signed=True))
    def on_key(e, up):
        if e.keysym == "F11": return
        send(b"J" if up else b"K", e.keycode.to_bytes(4, "little", signed=True))
    def toggle_fs(e=None):
        fs[0] = not fs[0]
        win.attributes("-fullscreen", fs[0])
        if fs[0]: bar.pack_forget()
        else: bar.pack(fill="x", before=canvas)
        return "break"

    canvas.bind("<Motion>", on_move)
    canvas.bind("<Button-1>", lambda e: on_down(e, 0))
    canvas.bind("<ButtonRelease-1>", lambda e: on_up(e, 0))
    canvas.bind("<Button-3>", lambda e: on_down(e, 1))
    canvas.bind("<ButtonRelease-3>", lambda e: on_up(e, 1))
    canvas.bind("<Button-2>", lambda e: on_down(e, 2))
    canvas.bind("<ButtonRelease-2>", lambda e: on_up(e, 2))
    canvas.bind("<MouseWheel>", on_wheel)
    win.bind("<F11>", toggle_fs)
    if not files_only:
        win.bind("<KeyPress>", lambda e: on_key(e, False))
        win.bind("<KeyRelease>", lambda e: on_key(e, True))

    def close():
        alive[0] = False
        try: sock.close()
        except Exception: pass
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", close)
    def vbtn(text, cmd):
        tk.Button(bar, text=text, command=lambda: (cmd(), canvas.focus_set()), bg=tc("#16233d"), fg=tc("#e7f0ff"),
                  activebackground=tc("#20314f"), activeforeground="#ffffff", relief="flat", padx=10, pady=2,
                  font=FNT(9)).pack(side="right", padx=4, pady=4)
    vbtn("ตัดการเชื่อมต่อ", close)
    if not files_only: vbtn("เต็มจอ (F11)", toggle_fs)
    vbtn("ดึงไฟล์มา", open_browser)
    vbtn("ส่งไฟล์ไปเครื่องนั้น", pick_send)
    if DND[0]:
        try:
            canvas.drop_target_register(DND_FILES)
            canvas.dnd_bind("<<Drop>>", lambda e: (lambda fl: ask_remote_dir(lambda d: send_files(fl, d)))(list(win.tk.splitlist(e.data))))
        except Exception as e:
            log_err(e)
    if not files_only: canvas.focus_set()
    threading.Thread(target=recv_frames, daemon=True).start()
    threading.Thread(target=render_loop, daemon=True).start()
    if auto == "send": win.after(300, pick_send)
    elif auto == "pull": win.after(300, open_browser)
    poll()

# ---------- GUI ----------
def main():
    threading.Thread(target=listener, daemon=True).start()
    threading.Thread(target=broadcaster, daemon=True).start()
    threading.Thread(target=control_server, daemon=True).start()
    threading.Thread(target=ping_worker, daemon=True).start()
    threading.Thread(target=nb_poll, daemon=True).start()
    threading.Thread(target=ensure_firewall, daemon=True).start()
    threading.Thread(target=ensure_startup_task, daemon=True).start()
    threading.Thread(target=sys_ensure, daemon=True).start()

    if not cfg.get("nb_mgmt_url"):
        cfg["nb_mgmt_url"] = DEFAULT_NB_URL
        save_config(cfg)
    threading.Thread(target=ensure_netbird, daemon=True).start()

    BG      = "#f4f7fb"   # ธีมสว่าง ตัวใหญ่ อ่านง่าย
    PANEL   = "#ffffff"
    PANEL2  = "#eaf0f9"
    ACCENT  = "#0b4f9c"
    ACCENT2 = "#083c78"
    TEXT    = "#1a1a1a"
    SUBTEXT = "#4a5668"
    OK_C    = "#1b7f3b"
    DUP_C   = "#c62828"

    root = None
    if TkinterDnD:
        try: root = TkinterDnD.Tk()
        except Exception as e: log_err(e)
    DND[0] = root is not None
    if root is None: root = tk.Tk()
    ROOT[0] = root
    try:
        FONT[0] = next((f for f in ("Leelawadee UI", "Tahoma") if f in tkfont.families(root)), "Tahoma")
    except Exception as e:
        log_err(e)
    S = lambda v: int(v * root.winfo_fpixels("1i") / 96)
    root.title(f"ZAIA Remote Desktop v{APP_VER}")
    root.geometry("1100x700")
    root.configure(bg=BG)
    root.minsize(640, 420)
    try: root.state("zoomed")
    except Exception: pass
    try: root.iconbitmap(ICON_PATH)
    except Exception: pass

    LIGHT2DARK = {BG: "#1a0505", PANEL: "#260808", PANEL2: "#3a0d0d", ACCENT: "#e0243f",
                  ACCENT2: "#8a0d20", TEXT: "#f5d9d9", SUBTEXT: "#d79a9a", OK_C: "#2ecc71", DUP_C: "#ff5252",
                  "#223354": "#4a1515", "#2a3c5e": "#5a1b1b", "#2c3e5c": "#2a0a0a",
                  "#1b7f3b": "#b3122b", "#146030": "#7d0c1e", "#20314f": "#6b1f1f"}
    DARK2LIGHT = {v: k for k, v in LIGHT2DARK.items()}
    assert len(DARK2LIGHT) == len(LIGHT2DARK)
    RETRO_PAL = {BG: "#12102b", PANEL: "#1d1a45", PANEL2: "#2b2766", ACCENT: "#ffd400", ACCENT2: "#ff3b6b", TEXT: "#f2f2ff", SUBTEXT: "#9fa6ff",
                 OK_C: "#3dff8a", DUP_C: "#ff5a5a", "#223354": "#3a3480", "#2a3c5e": "#473fa0", "#2c3e5c": "#0b0a1f",
                 "#1b7f3b": "#0fa843", "#146030": "#0a7a30", "#20314f": "#4c43b8"}
    assert set(RETRO_PAL) == set(LIGHT2DARK) and len(set(RETRO_PAL.values())) == len(RETRO_PAL)
    ADRETRO_PAL = {BG: "#1a0000", PANEL: "#2b0606", PANEL2: "#4a0f0f", ACCENT: "#ffb000", ACCENT2: "#ff3b3b", TEXT: "#ffe9e0", SUBTEXT: "#ff9a8a",
                   OK_C: "#3dff8a", DUP_C: "#ff7a3a", "#223354": "#5c1a1a", "#2a3c5e": "#6e2222", "#2c3e5c": "#120000",
                   "#1b7f3b": "#c4162a", "#146030": "#8f0f1f", "#20314f": "#7a2a2a"}
    assert set(ADRETRO_PAL) == set(LIGHT2DARK) and len(set(ADRETRO_PAL.values())) == len(ADRETRO_PAL)
    PALS = {(False, False): {}, (True, False): LIGHT2DARK, (False, True): RETRO_PAL, (True, True): ADRETRO_PAL}  # (แอดมิน, retro) -> สีของแต่ละบทบาท
    def cmap(): return PALS[(bool(ADMIN[0]), bool(RETRO[0]))]
    def trans(old, new): return {old.get(r, r).lower(): new.get(r, r) for r in LIGHT2DARK}  # สีเดิมของธีมเก่า -> สีธีมใหม่
    style = ttk.Style(root)
    style.theme_use("clam")
    root.option_add("*TCombobox*Listbox.font", FNT(13))
    def apply_styles(dark=False):  # ตั้งสไตล์ ttk ใหม่ทั้งชุดจากค่าตรงๆ (ไม่อ่านค่าเก่ากลับมา)
        c = lambda x: cmap().get(x, x)
        style.configure(".", background=c(BG), foreground=c(TEXT), fieldbackground=c(PANEL2), font=FNT(13))
        style.configure("TFrame", background=c(BG))
        style.configure("Panel.TFrame", background=c(PANEL))
        style.configure("TLabel", background=c(PANEL), foreground=c(TEXT), font=FNT(13))
        style.configure("Header.TLabel", background=c(BG), foreground=c(TEXT), font=FNT(22, "bold"))
        style.configure("Sub.TLabel", background=c(BG), foreground=c(SUBTEXT), font=FNT(12))
        style.configure("Section.TLabel", background=c(PANEL), foreground=c(ACCENT), font=FNT(14, "bold"))
        style.configure("TCombobox", fieldbackground=c(PANEL2), background=c(PANEL2), foreground=c(TEXT), arrowcolor=c(TEXT))
        style.map("TCombobox", fieldbackground=[("readonly", c(PANEL2))], foreground=[("readonly", c(TEXT))])
        style.configure("Accent.TButton", background=c(ACCENT), foreground="#ffffff", font=FNT(13, "bold"), padding=14, borderwidth=0)
        style.map("Accent.TButton", background=[("active", c(ACCENT2))])
        style.configure("Go.TButton", background=c("#1b7f3b"), foreground="#ffffff", font=FNT(15, "bold"), padding=16, borderwidth=0)
        style.map("Go.TButton", background=[("active", c("#146030"))])
        style.configure("Ghost.TButton", background=c(PANEL2), foreground=c(TEXT), font=FNT(12), padding=14, borderwidth=0)
        style.configure("Vertical.TScrollbar", arrowsize=S(28))
        style.map("Ghost.TButton", background=[("active", c("#20314f"))])
        if RETRO[0]:  # ปุ่มนูนขอบดำหนา แบบเครื่องเกมเก่า + ตัวอักษรเข้มบนปุ่มเหลือง
            for nm, lt, dk in (("Go.TButton", "#7dffa8", "#056b25"), ("Accent.TButton", "#fff29a", "#a98600"), ("Ghost.TButton", "#7a72e8", "#161240")):
                style.configure(nm, borderwidth=3, relief="raised", bordercolor="#000000", lightcolor=lt, darkcolor=dk)
            style.configure("Accent.TButton", foreground="#12102b")
            style.configure("Treeview.Heading", borderwidth=2, relief="raised", bordercolor="#000000")
        style.configure("Treeview", background=c(PANEL2), fieldbackground=c(PANEL2), foreground=c(TEXT), rowheight=int(S(46) * SCALE[0]), borderwidth=0, font=FNT(12))
        style.configure("Treeview.Heading", background=c(PANEL), foreground=c(ACCENT), font=FNT(12, "bold"), borderwidth=0)
        style.map("Treeview", background=[("selected", c(ACCENT2))], foreground=[("selected", "#ffffff")])
    apply_styles(False)

    def popup(title):  # ป็อปอัปกลางหน้าต่างหลัก (ไม่สร้างหน้าต่างแยก) คืน (พื้นหลัง, กล่อง, ฟังก์ชันแปลงสี)
        c = lambda x: cmap().get(x, x)
        dim = tk.Frame(root, bg=c("#2c3e5c"))
        dim.place(x=0, y=0, relwidth=1, relheight=1)
        w = tk.Frame(dim, bg=c(PANEL), highlightbackground=c(ACCENT), highlightthickness=4)
        w.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(w, text=title, bg=c(PANEL), fg=c(TEXT), font=FNT(18, "bold"), justify="left",
                 wraplength=max(min(S(620), root.winfo_width() - S(120)), S(240))).pack(anchor="w", padx=S(24), pady=(S(20), S(8)))
        dim.lift()
        return dim, w, c

    def ask_yes(title, msg, yes, no=None):  # กล่องยืนยันในโปรแกรม แทน messagebox (ไม่เปิดหน้าต่างแยก)
        dim, w, c = popup(title)
        tk.Label(w, text=msg, bg=c(PANEL), fg=c(SUBTEXT), font=FNT(13), justify="left",
                 wraplength=max(min(S(620), root.winfo_width() - S(120)), S(240))).pack(anchor="w", padx=S(24), pady=(0, S(8)))
        def go(f):
            dim.destroy()
            if f: f()
        row = tk.Frame(w, bg=c(PANEL)); row.pack(fill="x", padx=S(24), pady=(S(8), S(20)))
        ttk.Button(row, text="ตกลง", style="Go.TButton", command=lambda: go(yes)).pack(side="right")
        ttk.Button(row, text="ยกเลิก", style="Ghost.TButton", command=lambda: go(no)).pack(side="right", padx=10)

    flows, flow_w = {}, {}  # แถวปุ่มที่ตัดบรรทัดเองตามความกว้างจอ (แท็บเล็ต/จอแคบ)
    def reflow(fr):
        ws = [w for w, a in flows[fr] if ADMIN[0] or not a]
        for w, a in flows[fr]: w.grid_forget()
        cw = fr.winfo_width()
        mx = max([w.winfo_reqwidth() for w in ws] or [1]) + 8
        per = max(1, min(len(ws) or 1, cw // mx if cw > 1 else len(ws)))
        for i in range(12): fr.columnconfigure(i, weight=0, uniform="")
        for i in range(per): fr.columnconfigure(i, weight=1, uniform="b")
        for i, w in enumerate(ws): w.grid(row=i // per, column=i % per, padx=4, pady=4, sticky="ew")
    def add_flow(fr, w, admin=False):
        if fr not in flows:
            flows[fr] = []
            def on_cfg(e, fr=fr):
                if flow_w.get(fr) != e.width:
                    flow_w[fr] = e.width
                    reflow(fr)
            fr.bind("<Configure>", on_cfg, add="+")
        flows[fr].append((w, admin))
        return w

    header = ttk.Frame(root, style="TFrame")
    header.pack(fill="x", padx=20, pady=(14, 6))
    try:
        logo_img = Image.open(LOGO_PATH).convert("RGB").resize((S(64), S(64)), Image.LANCZOS)
        from PIL import ImageTk as _ImageTk
        logo_photo = _ImageTk.PhotoImage(logo_img)
        tk.Label(header, image=logo_photo, bg=BG).pack(side="left", padx=(0, 12))
        header.logo_ref = logo_photo
    except Exception:
        pass
    titlebox = ttk.Frame(header, style="TFrame")
    titlebox.pack(side="left")
    ttk.Label(titlebox, text="ZAIA Remote Desktop", style="Header.TLabel").pack(anchor="w")
    ttk.Label(titlebox, text=f"เครื่อง: {HOSTNAME}   •   v{APP_VER}", style="Sub.TLabel").pack(anchor="w")

    body = ttk.Frame(root, style="TFrame")
    body.pack(fill="both", expand=True, padx=20, pady=(6, 16))
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)

    right = tk.Frame(body, bg=PANEL, highlightbackground="#223354", highlightthickness=1)
    right.grid(row=0, column=0, sticky="nsew")

    # หน้าตั้งค่า: เต็มจอทับหน้าหลักในหน้าต่างเดียว (เหมือนเมนูพักเกม ไม่ใช่หน้าต่างแยก) แบ่งเป็นการ์ดตามหัวข้อ เลื่อนด้วยนิ้ว/ล้อเมาส์ได้
    sett = tk.Frame(root, bg=BG)
    sbar = tk.Frame(sett, bg=BG); sbar.pack(fill="x", padx=20, pady=(14, 6))
    ttk.Button(sbar, text="← กลับ", style="Ghost.TButton", command=lambda: sett.place_forget()).pack(side="left")
    ttk.Label(sbar, text="ตั้งค่า", style="Header.TLabel").pack(side="left", padx=16)
    lbl_sset = tk.Label(sett, text="", bg=BG, fg=SUBTEXT, anchor="w", justify="left", font=FNT(12), wraplength=S(700))
    lbl_sset.pack(side="bottom", fill="x", padx=24, pady=(0, 10))
    STATUS2[0] = lbl_sset
    scv = tk.Canvas(sett, bg=BG, highlightthickness=0)
    ssb = ttk.Scrollbar(sett, orient="vertical", command=scv.yview)
    scv.configure(yscrollcommand=ssb.set)
    ssb.pack(side="right", fill="y"); scv.pack(side="left", fill="both", expand=True)
    left = tk.Frame(scv, bg=BG)  # ที่รวมการ์ดทั้งหมด
    swin = scv.create_window(0, 0, window=left, anchor="nw")
    def sfit(e=None):
        cw = scv.winfo_width(); w_ = min(cw, S(820))
        scv.itemconfigure(swin, width=w_); scv.coords(swin, (cw - w_) // 2, 0)
        scv.configure(scrollregion=(0, 0, cw, max(left.winfo_reqheight(), scv.winfo_height())))
    scv.bind("<Configure>", sfit); left.bind("<Configure>", sfit)
    def sbind(w):  # ลากนิ้ว/เมาส์บนพื้นที่ว่างเพื่อเลื่อน ล้อเมาส์เลื่อนได้ทุกจุด
        if not isinstance(w, (ttk.Button, tk.Checkbutton, ttk.Combobox, tk.Entry)):
            w.bind("<ButtonPress-1>", lambda e: scv.scan_mark(0, e.y_root), add="+")
            w.bind("<B1-Motion>", lambda e: scv.scan_dragto(0, e.y_root, gain=1), add="+")
        w.bind("<MouseWheel>", lambda e: scv.yview_scroll(-1 if e.delta > 0 else 1, "units"), add="+")
        for ch in w.winfo_children(): sbind(ch)
    def open_settings():
        sett.place(x=0, y=0, relwidth=1, relheight=1); sett.lift(); sfit()
    ttk.Button(header, text="ตั้งค่า", style="Ghost.TButton", command=open_settings).pack(side="right")
    def card(title):
        f = tk.Frame(left, bg=PANEL, highlightbackground="#223354", highlightthickness=1)
        f.pack(fill="x", padx=16, pady=(8, 4))
        ttk.Label(f, text=title, style="Section.TLabel").pack(anchor="w", padx=16, pady=(14, 6))
        return f

    sec_user = card("ผู้ใช้งานเครื่องนี้")
    active_card = tk.Frame(sec_user, bg=PANEL2, highlightbackground="#2a3c5e", highlightthickness=1)
    active_card.pack(fill="x", padx=16, pady=(0, 4))
    lbl_active = tk.Label(active_card, bg=PANEL2, fg=OK_C, justify="left", font=FNT(13, "bold"), anchor="w", wraplength=S(300))
    lbl_active.pack(fill="x", padx=12, pady=14)
    def refresh_active_label():
        lbl_active.config(text=f"● {username()}")
    refresh_active_label()

    def ask_user(first=False):  # ป๊อปอัปกลางหน้าต่างหลัก (เหมือนเมนูพักเกม) ไม่สร้างหน้าต่างแยก
        if ADMIN[0]:  # โหมดแอดมิน: พิมพ์ชื่อเอง (ธีมแดงดำ) แทนเลือกตำแหน่ง/หน่วย
            set_admin_name(); return
        dim = tk.Frame(root, bg="#2c3e5c")
        dim.place(x=0, y=0, relwidth=1, relheight=1)
        w = tk.Frame(dim, bg=PANEL, highlightbackground=ACCENT, highlightthickness=4)
        w.place(relx=0.5, rely=0.5, anchor="center")
        FB = FNT(14)
        tk.Label(w, text="เลือกผู้ใช้งาน", bg=PANEL, fg=TEXT, font=FNT(22, "bold")).pack(anchor="w", padx=32, pady=(26, 4))
        tk.Label(w, text="เลือกครั้งเดียว โปรแกรมจะจำไว้ เปลี่ยนได้ภายหลัง", bg=PANEL, fg=SUBTEXT, font=FB).pack(anchor="w", padx=32)
        v_role, v_unit = tk.StringVar(value=cfg.get("role", "")), tk.StringVar(value=cfg.get("unit", ""))
        for label, var, vals in (("ตำแหน่ง", v_role, ROLES), ("หน่วย", v_unit, UNITS)):
            tk.Label(w, text=label, bg=PANEL, fg=SUBTEXT, font=FB).pack(anchor="w", padx=32, pady=(14, 4))
            ttk.Combobox(w, textvariable=var, values=vals, state="readonly", width=30, font=FNT(16)).pack(padx=32)
        pv = tk.Label(w, bg=PANEL2, fg=OK_C, font=FNT(16, "bold"), anchor="w")
        pv.pack(fill="x", padx=32, pady=18, ipady=8)
        def upd(*a): pv.config(text="  " + ((v_role.get() + v_unit.get()) or "-"))
        v_role.trace_add("write", upd); v_unit.trace_add("write", upd); upd()
        def ok():
            if not v_role.get() or not v_unit.get():
                notify("เลือกให้ครบทั้งตำแหน่งและหน่วย", True)
                return
            cfg["role"], cfg["unit"] = v_role.get(), v_unit.get()
            save_config(cfg)
            dim.destroy()
            refresh_active_label()
            threading.Thread(target=send_presence, daemon=True).start()
        row = tk.Frame(w, bg=PANEL); row.pack(fill="x", padx=32, pady=(0, 26))
        ttk.Button(row, text="ยืนยัน", style="Go.TButton", command=ok).pack(side="right")
        if not first: ttk.Button(row, text="ยกเลิก", style="Ghost.TButton", command=dim.destroy).pack(side="right", padx=10)
        dim.lift(); w.grab_set(); w.focus_set(); root.wait_window(dim)

    def probe_monitors(ip):  # ถามจำนวนจอของปลายทางแบบเงียบๆ (ไม่เข้าจอ ไม่ต้องขออนุญาต) ก่อนเปิดกล่องเลือกคุณภาพ
        v = peer_ver(ip)
        if not (v[:1].isdigit() and ver_tuple(v) >= (3, 1, 0)): return 1  # รุ่นเก่ากว่า 3.1.0 ไม่รู้จักคำสั่ง M จะเด้งกล่องขออนุญาตเอง / ไม่รู้รุ่น (ต่อด้วย IP) ก็ไม่ถาม
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((ip, CTRL_PORT))
            s.sendall(b"M")
            n = s.recv(1)
            s.close()
            return max(1, min(n[0], 16)) if n else 1
        except Exception:
            return 1

    def ask_quality(who, go, ip=None):
        n_mon = probe_monitors(ip) if ip else 1
        w = tk.Toplevel(root)
        w.title("เลือกคุณภาพภาพ")
        w.configure(bg=PANEL)
        w.resizable(False, False)
        tk.Label(w, text="เลือกคุณภาพภาพ", bg=PANEL, fg=TEXT, font=FNT(17, "bold")).pack(anchor="w", padx=20, pady=(16, 2))
        tk.Label(w, text=f"เชื่อมต่อกับ {who}", bg=PANEL, fg=SUBTEXT).pack(anchor="w", padx=20, pady=(0, 8))
        v = tk.IntVar(value=cfg.get("quality", 3))  # จำค่าที่เลือกครั้งก่อน
        for val, txt in ((3, "เอกสาร / Excel  คมชัด ไม่ย่อภาพ (แนะนำสำหรับงานเอกสาร)"), (0, "ประหยัด  720p 30fps (วิดีโอ)"),
                         (1, "กลาง  1080p 30fps (วิดีโอ)"), (2, "สูงสุด  1080p 60fps (วิดีโอ ใช้เน็ตและเครื่องแรง)")):
            tk.Radiobutton(w, text=txt, variable=v, value=val, bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL,
                           activeforeground=TEXT, anchor="w").pack(fill="x", padx=20, pady=2)
        mv = tk.IntVar(value=1)
        if n_mon > 1:  # ปลายทางมีหลายจอ -> เลือกจอครั้งเดียวตอนนี้เลย (เปลี่ยนจอกลางทางไม่รองรับ ต้องตัดต่อใหม่)
            tk.Frame(w, bg=PANEL2, height=1).pack(fill="x", padx=20, pady=8)
            tk.Label(w, text=f"ปลายทางมี {n_mon} จอ เลือกจอที่จะดู", bg=PANEL, fg=TEXT, font=FNT(13, "bold")).pack(anchor="w", padx=20)
            for i in range(1, n_mon + 1):
                tk.Radiobutton(w, text=f"จอหลัก" if i == 1 else f"จอที่ {i}", variable=mv, value=i, bg=PANEL, fg=TEXT,
                               selectcolor=PANEL2, activebackground=PANEL, activeforeground=TEXT, anchor="w").pack(fill="x", padx=20, pady=2)
        def ok():
            q = v.get(); cfg["quality"] = q; save_config(cfg); w.destroy(); go(q, mv.get())
        row = tk.Frame(w, bg=PANEL); row.pack(fill="x", padx=20, pady=16)
        ttk.Button(row, text="เชื่อมต่อ", style="Accent.TButton", command=ok).pack(side="right")
        ttk.Button(row, text="ยกเลิก", style="Ghost.TButton", command=w.destroy).pack(side="right", padx=8)
        if cmap(): recolor_widget(w)
        w.transient(root); w.grab_set()

    def ask_link(err):
        def cb(v):
            cfg["update_url"] = v
            save_config(cfg)
            do_update()
        ask_text("ลิงก์อัปเดต", f"ดึงจากลิงก์เดิมไม่ได้ ({err})\nวางลิงก์ดาวน์โหลดตรงของไฟล์ ZaiaRemote.py ที่ต้องการใช้แทน", cb)

    def do_update(auto=False):
        if not auto: notify("กำลังตรวจสอบรุ่นใหม่ ...")
        def work():
            try:
                v, m, staged = check_update()
                what = changed_files(m) if m else ["ZaiaRemote.py"]
            except Exception as e:
                log_err(e)
                if not auto:
                    msg = str(e)
                    notify(f"ตรวจรุ่นใหม่ไม่สำเร็จ: {msg}", True)
                    root.after(0, lambda: ask_link(msg[:150]))
                return
            if ver_tuple(v) <= ver_tuple(APP_VER):
                if not auto: notify(f"เป็นรุ่นล่าสุดแล้ว (v{APP_VER})")
                return
            if m and int(m.get("setup_rev", 0)) > SETUP_REV:
                notify(f"รุ่น v{v} ต้องลงด้วยตัวติดตั้งใหม่ (ไลบรารี/ตัวหลักเปลี่ยน) อัปเดตจากปุ่มไม่ได้", True)
                return
            if auto:
                notify(f"มีรุ่นใหม่ v{v} — เข้า 'ตั้งค่า' แล้วกด 'ตรวจหารุ่นใหม่'")
                return
            nb_note = "\nอัปเดตค่าเชื่อมต่อ NetBird (เซิร์ฟเวอร์/Setup Key)" if m and nb_changed(m) else ""
            def ask():
                def go():
                    try:
                        notify("กำลังดาวน์โหลดรุ่นใหม่ ...")
                        apply_staged(m or {}, staged if staged is not None else stage_update(m))
                    except Exception as e:
                        log_err(e)
                        notify(f"อัปเดตไม่สำเร็จ: {e} (ลองเปิดแบบ admin)", True)
                ask_yes("อัปเดต", f"มีรุ่นใหม่ v{v} (ตอนนี้ v{APP_VER})\nไฟล์ที่จะเปลี่ยน: {', '.join(what) or '-'}{nb_note}\nอัปเดตและเปิดโปรแกรมใหม่ไหม",
                        lambda: threading.Thread(target=go, daemon=True).start())
            root.after(0, ask)
        threading.Thread(target=work, daemon=True).start()

    urow = tk.Frame(sec_user, bg=PANEL)
    urow.pack(fill="x", padx=16, pady=10)
    add_flow(urow, ttk.Button(urow, text="เปลี่ยนข้อมูล", style="Ghost.TButton", command=lambda: ask_user(False)))
    sec_upd = card("อัปเดต")
    tk.Label(sec_upd, text=f"รุ่นที่ใช้อยู่ v{APP_VER}", bg=PANEL, fg=SUBTEXT, font=FNT(13), anchor="w").pack(fill="x", padx=16)
    uprow = tk.Frame(sec_upd, bg=PANEL)
    uprow.pack(fill="x", padx=16, pady=10)
    add_flow(uprow, ttk.Button(uprow, text="ตรวจหารุ่นใหม่", style="Ghost.TButton", command=do_update))
    root.after(8000, lambda: do_update(True))

    sec_zt = card("การเชื่อมต่อเครือข่าย (NetBird)")
    lbl_zt = tk.Label(sec_zt, text=f"เซิร์ฟเวอร์: {cfg.get('nb_mgmt_url') or DEFAULT_NB_URL}", bg=PANEL, fg=SUBTEXT, justify="left", anchor="w", wraplength=S(320), font=FNT(13))
    lbl_zt.pack(fill="x", padx=16)
    def change_zt():
        def cb(v):
            cfg["nb_setup_key"] = v
            save_config(cfg)
            notify("กำลังเชื่อมต่อ NetBird ใหม่ ...")
            threading.Thread(target=ensure_netbird, daemon=True).start()
        ask_text("NetBird", "ใส่ NetBird Setup Key", cb, "")
    def rejoin():
        notify("กำลังเชื่อมต่อ NetBird ใหม่ ...")
        threading.Thread(target=ensure_netbird, daemon=True).start()
    def copy_node():
        if NB["ip"]:
            root.clipboard_clear()
            root.clipboard_append(NB["ip"].split("/")[0])
            notify("คัดลอก IP แล้ว")
    lbl_ztst = tk.Label(sec_zt, text="", bg=PANEL, fg=SUBTEXT, justify="left", anchor="w", wraplength=S(320), font=FNT(12))
    lbl_ztst.pack(fill="x", padx=16, pady=(4, 0))
    nrow = tk.Frame(sec_zt, bg=PANEL)
    nrow.pack(fill="x", padx=16)
    lbl_node = tk.Label(nrow, text="", bg=PANEL, fg=SUBTEXT, anchor="w", font=FNT(12))
    lbl_node.pack(side="left")
    ttk.Button(nrow, text="คัดลอก", style="Ghost.TButton", command=copy_node).pack(side="left", padx=8)
    zrow = tk.Frame(sec_zt, bg=PANEL)
    zrow.pack(fill="x", padx=16, pady=10)
    add_flow(zrow, ttk.Button(zrow, text="ตั้งค่า Setup Key", style="Ghost.TButton", command=change_zt))
    add_flow(zrow, ttk.Button(zrow, text="เชื่อมต่อใหม่", style="Ghost.TButton", command=rejoin))

    sec_srv = card("โหมดเซิร์ฟเวอร์")
    auto_var = tk.BooleanVar(value=bool(cfg.get("auto_allow", False)))
    def toggle_auto():
        def commit(v):
            cfg["auto_allow"] = v
            save_config(cfg)
        if auto_var.get():
            ask_yes("อนุญาตอัตโนมัติ", "ทุกเครื่องในเครือข่าย NetBird จะควบคุมจอเครื่องนี้ได้ทันที โดยไม่ถามก่อน\nเปิดโหมดนี้ไหม",
                    lambda: commit(True), lambda: auto_var.set(False))
        else:
            commit(False)
    tk.Checkbutton(sec_srv, text="อนุญาตเชื่อมต่ออัตโนมัติ (ไม่มีคนนั่งหน้าเครื่อง)", variable=auto_var, command=toggle_auto,
                   bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL, activeforeground=TEXT, font=FNT(13),
                   anchor="w", justify="left", wraplength=S(520)).pack(fill="x", padx=16, pady=(0, 6))
    uac_var = tk.BooleanVar(value=not uac_secure_on())
    def toggle_uac():
        want_off = uac_var.get()  # True = ให้ UAC ขึ้นบนจอปกติ
        def commit(off):
            try:
                set_uac_secure(not off)
                notify("UAC ขึ้นบนจอปกติแล้ว ผู้คุมเห็นและลองกดได้" if off else "คืนค่า UAC เป็นแบบ Secure Desktop (ค่าเดิมของ Windows) แล้ว")
            except Exception as e:
                log_err(e)
                uac_var.set(not off)
                notify("แก้ไม่ได้: ต้องเปิดโปรแกรมแบบ admin (" + str(e)[:60] + ")", True)
        if want_off:
            ask_yes("UAC บนจอปกติ", "หน้าต่างขออนุญาต (UAC) จะขึ้นบนจอปกติ ผู้คุมเห็นภาพและลองกดได้ แต่ความปลอดภัยของเครื่องนี้ลดลง (โปรแกรมอื่นอาจเห็น/ควบคุมหน้าต่าง UAC ได้ง่ายขึ้น) และอาจกดจากเครื่องผู้คุมไม่ได้ในบางเครื่อง ยืนยันหรือไม่?",
                    lambda: commit(True), lambda: uac_var.set(False))
        else:
            commit(False)
    tk.Checkbutton(sec_srv, text="ให้ UAC ขึ้นบนจอปกติ (ผู้คุมเห็น/ลองกดอนุญาตได้ ลดความปลอดภัยเครื่องนี้)", variable=uac_var, command=toggle_uac,
                   bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL, activeforeground=TEXT, font=FNT(13),
                   anchor="w", justify="left", wraplength=S(520)).pack(fill="x", padx=16, pady=(0, 14))
    sys_var = tk.BooleanVar(value=bool(cfg.get("sys_on", False)))
    def toggle_sys():
        want = sys_var.get()
        def commit(on):
            def work():
                err = sys_task_set(on)
                def done():
                    if err:
                        sys_var.set(not on)
                        notify("ตั้งค่าส่วน SYSTEM ไม่สำเร็จ: " + err, True)
                    else:
                        cfg["sys_on"] = on; save_config(cfg)
                        notify("เปิดส่วน SYSTEM แล้ว ผู้คุมกด UAC ได้" if on else "ปิดส่วน SYSTEM แล้ว")
                root.after(0, done)
            if not is_admin():
                sys_var.set(not on); notify("ต้องเปิดโปรแกรมแบบ admin ก่อน", True); return
            notify("กำลังตั้งค่า ...")
            threading.Thread(target=work, daemon=True).start()
        if want:
            ask_yes("เปิดส่วน SYSTEM", "จะติดตั้งงานเบื้องหลังที่รันด้วยสิทธิ์ SYSTEM เพื่อให้ผู้คุมที่ได้รับอนุญาตเห็นและกดหน้าต่าง UAC หรือหน้าจอล็อกของเครื่องนี้ได้ (ผู้คุมต้องผ่านการอนุญาตเชื่อมต่อตามปกติก่อน) ความเสี่ยง: ผู้คุมจะทำงานระดับ admin ได้ทันที ปิดได้ทุกเมื่อด้วยการเอาติ๊กออก ยืนยันหรือไม่?",
                    lambda: commit(True), lambda: sys_var.set(False))
        else:
            commit(False)
    tk.Checkbutton(sec_srv, text="ให้ผู้คุมกด UAC / ใช้หน้าจอล็อกได้ (ส่วน SYSTEM ปิดไว้เป็นค่าเริ่มต้น)", variable=sys_var, command=toggle_sys,
                   bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL, activeforeground=TEXT, font=FNT(13),
                   anchor="w", justify="left", wraplength=S(520)).pack(fill="x", padx=16, pady=(0, 6))
    retro_var = tk.BooleanVar(value=bool(cfg.get("retro", False)))
    tk.Checkbutton(sec_srv, text="ธีม Retro 8-bit (หน้าตาแบบเกมเก่า: ทั้งหน้าหลัก ป๊อก และพูล)", variable=retro_var, command=lambda: toggle_retro(),
                   bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL, activeforeground=TEXT, font=FNT(13),
                   anchor="w", justify="left", wraplength=S(520)).pack(fill="x", padx=16, pady=(0, 6))
    def rollback():
        bak = os.path.abspath(__file__) + ".bak"
        if not os.path.exists(bak):
            notify("ไม่มีไฟล์รุ่นเก่า (.bak) ให้ย้อนกลับ ต้องเคยอัปเดตมาก่อน", True); return
        def go():
            try:
                with open(bak, "rb") as f: data = f.read()
                compile(data.decode("utf-8-sig"), "bak", "exec")
                if cfg.get("sys_on") and is_admin(): sys_task_set(False)  # รุ่นเก่าไม่รู้จักส่วน SYSTEM
                cfg["sys_on"] = False; save_config(cfg)
                apply_update(data)
            except Exception as e:
                log_err(e); notify("ย้อนกลับไม่สำเร็จ: " + str(e)[:120], True)
        ask_yes("ย้อนกลับรุ่นเก่า", "ย้อนกลับเป็นรุ่นก่อนหน้า (ไฟล์สำรอง .bak จากการอัปเดตครั้งล่าสุด) และปิดส่วน SYSTEM แล้วเปิดโปรแกรมใหม่ ยืนยันหรือไม่? (ถ้ามีรุ่นใหม่กว่าบน GitHub จะแจ้งเตือนอีกครั้งตอนเปิดโปรแกรม แต่ไม่โหลดเอง)", go)
    ttk.Button(sec_srv, text="ย้อนกลับเป็นรุ่นก่อนหน้า", style="Ghost.TButton", command=rollback).pack(anchor="w", padx=16, pady=(0, 14))
    sbind(left)

    rhead = tk.Frame(right, bg=PANEL)
    rhead.pack(fill="x", padx=16, pady=(14, 6))
    lbl_peers = ttk.Label(rhead, text="เครื่องที่เปิดใช้งานอยู่", style="Section.TLabel")
    lbl_peers.pack(side="left")
    ttk.Button(rhead, text="รีเฟรชรายชื่อ", style="Ghost.TButton", command=lambda: refresh_now()).pack(side="right")
    ttk.Button(rhead, text="ต่อไม่ได้? กดตรงนี้", style="Ghost.TButton", command=lambda: diag()).pack(side="right", padx=6)

    ttk.Label(right, text="ดับเบิลคลิกชื่อเครื่อง หรือคลิกเลือกแล้วกดปุ่มสีเขียวด้านล่าง", style="Sub.TLabel", background=PANEL).pack(anchor="w", padx=16, pady=(0, 6))

    def do_connect():
        sel_item = tree.selection()
        if not sel_item:
            notify("คลิกเลือกเครื่องในรายการก่อน แล้วกดปุ่มสีเขียว", True)
            return
        uid = sel_item[0]
        if uid == MY_ID:
            notify("เลือกเครื่องอื่น ไม่ใช่เครื่องตัวเอง", True)
            return
        ip = str(tree.item(uid)["values"][3])
        if ip == "-":
            notify("เครื่องนี้ซ่อนอยู่ (โหมดแอดมิน) เชื่อมต่อจากรายการนี้ไม่ได้", True)
            return
        with peers_lock:
            ips = [ip] + sorted(peers.get(uid, {}).get("ips", set()) - {ip})
        who = str(tree.item(uid)["values"][1]).replace("♠ ", "", 1).replace("◉ ", "", 1)
        ask_quality(who, lambda q, mon: threading.Thread(target=open_viewer, args=(ips, q, None, False, mon), daemon=True).start(), ip=ip)
    lbl_status = tk.Label(right, text="พร้อมใช้งาน", bg=PANEL, fg=SUBTEXT, anchor="w", justify="left", wraplength=S(340))
    lbl_status.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
    STATUS[0] = lbl_status
    def connect_ip():
        ask_text("เชื่อมต่อด้วย IP", "ใส่ IP ของเครื่องปลายทาง (IP NetBird)",
                 lambda v: ask_quality(v, lambda q, mon: threading.Thread(target=open_viewer, args=([v], q, None, False, mon), daemon=True).start(), ip=v), DEFAULT_PEER_IP)
    crow = tk.Frame(right, bg=PANEL)
    crow.pack(side="bottom", fill="x", padx=16, pady=12)
    add_flow(crow, ttk.Button(crow, text="ดูจอเครื่องที่เลือก", style="Go.TButton", command=do_connect))
    add_flow(crow, ttk.Button(crow, text="ต่อด้วยเลข IP", style="Ghost.TButton", command=connect_ip))
    def play_poker():
        dim, w, c = popup("Play poker (ป๊อกเด้ง)")
        tk.Label(w, text="เจ้ามือเป็นบอท เหรียญเสมือน เล่นเอาสนุก ไม่ใช่เงินจริง\nเปิดโต๊ะที่เครื่องนี้ หรือเข้าร่วมโต๊ะของเครื่องที่เลือกในรายการ", bg=c(PANEL), fg=c(SUBTEXT), font=FNT(13), justify="left",
                 wraplength=max(min(S(620), root.winfo_width() - S(120)), S(240))).pack(anchor="w", padx=S(24), pady=(0, S(8)))
        def host():
            dim.destroy()
            poker_start("127.0.0.1", True)
        def join():
            sel_item = tree.selection()
            if not sel_item:
                dim.destroy(); notify("คลิกเลือกเครื่องของเจ้าของโต๊ะในรายการก่อน", True); return
            uid = sel_item[0]
            ip = str(tree.item(uid)["values"][3])
            if uid == MY_ID or ip == "-":
                dim.destroy(); notify("เลือกเครื่องอื่นที่เปิดโต๊ะไว้ (ไม่ใช่เครื่องตัวเอง/เครื่องที่ซ่อนอยู่)", True); return
            dim.destroy()
            poker_start(ip)
        row = tk.Frame(w, bg=c(PANEL)); row.pack(fill="x", padx=S(24), pady=(S(8), S(20)))
        ttk.Button(row, text="เปิดโต๊ะที่เครื่องนี้", style="Go.TButton", command=host).pack(side="right")
        ttk.Button(row, text="เข้าร่วมโต๊ะของเครื่องที่เลือก", style="Go.TButton", command=join).pack(side="right", padx=10)
        ttk.Button(row, text="ยกเลิก", style="Ghost.TButton", command=dim.destroy).pack(side="right")
    add_flow(crow, ttk.Button(crow, text="Play poker", style="Go.TButton", command=play_poker))
    def play_pool():
        dim, w, c = popup("Play pool (8-ball)")
        tk.Label(w, text="พูล 8-ball ใช้เมาส์อย่างเดียว เล่นกับบอท หรือเพื่อน 1 คน (2 คน)\nเปิดโต๊ะที่เครื่องนี้ (บอทเล่นด้วยจนกว่าเพื่อนจะเข้า) หรือเข้าร่วมโต๊ะของเครื่องที่เลือกในรายการ", bg=c(PANEL), fg=c(SUBTEXT), font=FNT(13), justify="left",
                 wraplength=max(min(S(620), root.winfo_width() - S(120)), S(240))).pack(anchor="w", padx=S(24), pady=(0, S(8)))
        def host():
            dim.destroy()
            poker_start("127.0.0.1", True, "pool")
        def join():
            sel_item = tree.selection()
            if not sel_item:
                dim.destroy(); notify("คลิกเลือกเครื่องของเจ้าของโต๊ะในรายการก่อน", True); return
            uid = sel_item[0]
            ip = str(tree.item(uid)["values"][3])
            if uid == MY_ID or ip == "-":
                dim.destroy(); notify("เลือกเครื่องอื่นที่เปิดโต๊ะไว้ (ไม่ใช่เครื่องตัวเอง/เครื่องที่ซ่อนอยู่)", True); return
            dim.destroy()
            poker_start(ip, False, "pool")
        row = tk.Frame(w, bg=c(PANEL)); row.pack(fill="x", padx=S(24), pady=(S(8), S(20)))
        ttk.Button(row, text="เปิดโต๊ะที่เครื่องนี้", style="Go.TButton", command=host).pack(side="right")
        ttk.Button(row, text="เข้าร่วมโต๊ะของเครื่องที่เลือก", style="Go.TButton", command=join).pack(side="right", padx=10)
        ttk.Button(row, text="ยกเลิก", style="Ghost.TButton", command=dim.destroy).pack(side="right")
    add_flow(crow, ttk.Button(crow, text="Play pool", style="Go.TButton", command=play_pool))

    cols = ("host", "user", "status", "ip", "ping", "ver", "ips")
    COLS_N = ("host", "user", "status", "ver")  # โหมดธรรมดาไม่แสดง IP (ยังเก็บค่าไว้ใช้เชื่อมต่อ); โหมดแอดมินแสดง IP และ ping
    COLS_A = ("host", "user", "status", "ip", "ping", "ver")
    HEADS = {"host": "เครื่อง", "user": "ผู้ใช้", "status": "สถานะ", "ip": "IP", "ping": "ping", "ver": "รุ่น", "ips": ""}
    COLW = {"host": 26, "user": 26, "status": 13, "ip": 18, "ping": 9, "ver": 10}   # สัดส่วนความกว้าง
    COLMIN = {"host": 90, "user": 90, "status": 84, "ip": 112, "ping": 62, "ver": 66}  # ขั้นต่ำ (ก่อนคูณขนาดจอ)
    tree = ttk.Treeview(right, columns=cols, show="headings", displaycolumns=COLS_N)
    for c in cols:
        tree.heading(c, text=HEADS[c])
        tree.column(c, width=S(COLMIN.get(c, 60)), minwidth=S(COLMIN.get(c, 60)), anchor="w" if c in ("host", "user") else "center", stretch=False)
    def fit_cols(e=None):  # แบ่งความกว้างตามสัดส่วนทุกครั้งที่ตารางเปลี่ยนขนาด ไม่ให้คอลัมน์ท้ายหลุดขอบ
        shown = list(tree["displaycolumns"])
        tot = tree.winfo_width() - S(6)
        if tot < S(200): return
        wsum = sum(COLW[c] for c in shown)
        for c in shown:
            tree.column(c, width=max(int(tot * COLW[c] / wsum), S(COLMIN[c])))
    def update_cols():
        tree["displaycolumns"] = COLS_A if ADMIN[0] else COLS_N
        fit_cols()
    tree.bind("<Configure>", fit_cols, add="+")
    tree.pack(fill="both", expand=True, padx=16)
    tree.tag_configure("dup", foreground="#b36200")
    tree.tag_configure("stealth", foreground="#8fa3c4")
    tree.tag_configure("ok", foreground=OK_C)
    tree.tag_configure("me", foreground=ACCENT)
    tree.bind("<Double-1>", lambda e: do_connect())
    v_filter = tk.StringVar()

    hint = [True]
    def refresh_loop(loop=True):
        now = time.time()
        with peers_lock:
            for k in list(peers.keys()):
                if now - peers[k]["last"] > 9:
                    del peers[k]
            all_m = {MY_ID: {"host": HOSTNAME, "code": username(), "ip": "127.0.0.1", "ver": APP_VER, "poker": POK_ACTIVE[0] > 0, "pool": POOL_ACTIVE[0] > 0}}
            all_m.update({k: dict(v) for k, v in peers.items()})

        old_sel = tree.selection()
        flt = v_filter.get().strip().lower() if ADMIN[0] else ""
        n_behind = 0
        tree.delete(*tree.get_children())
        def sort_key(x):
            vv = all_m[x]
            stealth = vv.get("stealth") and x != MY_ID
            return ((vv["code"] if stealth else vv["host"]).lower(), x)
        for k in sorted(all_m, key=sort_key):
            v = all_m[k]
            stealth = bool(v.get("stealth")) and k != MY_ID  # เครื่องตัวเอง (MY_ID) ไม่ถูกบังข้อมูลเด็ดขาด
            ips_txt = "127.0.0.1" if k == MY_ID else ("-" if stealth else ", ".join(sorted(v.get("ips") or {v["ip"]})))
            old = (not stealth) and is_old(v["ver"])
            behind = (not stealth) and (not old) and ver_tuple(v["ver"]) < ver_tuple(APP_VER)
            n_behind += 1 if (old or behind) else 0
            if flt and flt not in f'{v["host"]} {v["code"]} {ips_txt}'.lower(): continue
            tag = "me" if k == MY_ID else "stealth" if stealth else "dup" if (old or behind) else "ok"
            who = f"(รุ่นเก่า รหัส {v['code']})" if old else v["code"]
            if v.get("poker") and not stealth: who = "♠ " + who
            elif v.get("pool") and not stealth: who = "◉ " + who  # ไอคอนลูกพูล = กำลังเล่น Play pool  # ไอคอนไพ่ = กำลังเล่น Play poker อยู่
            status = "รุ่นเก่า" if old else "ควรอัปเดต" if behind else "ผู้ดูแลระบบ" if stealth else "ปกติ"
            host_disp = "•" if stealth else v["host"]
            ip_disp = "-" if stealth else v["ip"]
            ver_disp = "-" if stealth else v["ver"]
            pg = PING.get(v["ip"])
            ptxt = "-" if (k == MY_ID or stealth or pg is None) else (f"{pg} ms" if pg >= 0 else "✗")
            tree.insert("", "end", iid=k, values=(host_disp, who, status, ip_disp, ptxt, ver_disp, ips_txt), tags=(tag,))

        keep = [i for i in old_sel if tree.exists(i)]
        if keep:
            tree.selection_set(keep)
        lbl_peers.config(text=f"เครื่องที่เปิดใช้งานอยู่ ({len(all_m)})" + (f" • ควรอัปเดต {n_behind}" if ADMIN[0] and n_behind else ""))
        lbl_ztst.config(text=NB["msg"], fg=OK_C if NB["ok"] else DUP_C)
        lbl_node.config(text=f"IP เครื่องนี้: {NB['ip'].split('/')[0] or '-'}")
        state = len(all_m) > 1 or time.time() - START < 15
        if state != hint[0]:
            hint[0] = state
            notify("พร้อมใช้งาน" if state else "ยังไม่พบเครื่องอื่น — กด 'ต่อไม่ได้? กดตรงนี้' เพื่อดูว่าติดที่ไหน", not state)
        if loop:
            root.after(1000, refresh_loop)
    root.after(1000, refresh_loop)

    def diag():
        notify("กำลังตรวจปัญหา ...")
        L = []
        def run():
            L[:] = [f"โปรแกรม v{APP_VER}   สิทธิ์ admin: {'ใช่' if is_admin() else 'ไม่ใช่ (ใช้งานได้ตามปกติ)'}"]
            good = lambda t: L.append("✔ " + t)
            bad = lambda t: L.append("✘ " + t)
            try: nb_update()
            except Exception as e: log_err(e)
            if not nb_cli():
                bad("ไม่พบ NetBird → ติดตั้งโปรแกรมใหม่ด้วยตัวติดตั้ง")
            elif not NB["ip"]:
                bad("NetBird ใช้ไม่ได้: " + NB["msg"])
            else:
                (good if NB["ok"] else bad)("NetBird: " + NB["msg"])
                up = [d for d in NB["det"] if d.get("status") == "Connected"]
                if up:
                    good(f"เห็นเครื่อง NetBird อื่นออนไลน์ {len(up)}/{len(NB['det'])} เครื่อง")
                    nd = len([d for d in up if str(d.get("connectionType", "")).lower() == "p2p"])
                    (good if nd else bad)(f"เส้นทางตรง (P2P) {nd}/{len(up)} เครื่อง" + ("" if nd else " → ตอนนี้อ้อมผ่าน Relay ภาพจะช้า/กระตุก เช็ก NAT/Firewall ของ router"))
                else: bad("ไม่เห็นเครื่อง NetBird อื่นออนไลน์ → อีกเครื่องปิดอยู่ / NetBird ไม่ทำงาน / ติด Policy (ACL) ใน Dashboard")
            if PORT_OK["udp"]: good(f"พอร์ตค้นหา UDP {PORT} เปิดรับได้")
            else: bad(f"เปิดพอร์ต UDP {PORT} ไม่ได้ → มีโปรแกรมนี้เปิดซ้ำ/โปรแกรมอื่นใช้พอร์ต")
            if PORT_OK["tcp"]: good(f"พอร์ตรับสาย TCP {CTRL_PORT} เปิดรับได้")
            else: bad(f"เปิดพอร์ต TCP {CTRL_PORT} ไม่ได้ → มีโปรแกรมนี้เปิดซ้ำ/โปรแกรมอื่นใช้พอร์ต")
            def fw_ok():
                try:
                    o = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", "name=ZAIA Remote"],
                                       capture_output=True, text=True, creationflags=0x08000000, timeout=15).stdout or ""
                    return str(PORT) in o and str(CTRL_PORT) in o
                except Exception:
                    return False
            if fw_ok():
                good("Firewall: มีกฎ ZAIA Remote แล้ว")
            elif is_admin():
                for proto, port in (("UDP", PORT), ("TCP", CTRL_PORT)):
                    subprocess.run(["netsh", "advfirewall", "firewall", "add", "rule", "name=ZAIA Remote", "dir=in",
                                    "action=allow", f"protocol={proto}", f"localport={port}", "profile=any"],
                                   capture_output=True, creationflags=0x08000000)
                (good if fw_ok() else bad)("Firewall: ไม่พบกฎ จึงสร้างให้แล้ว" if fw_ok() else "Firewall: สร้างกฎไม่สำเร็จ (อาจมี Firewall/Antivirus ตัวอื่นคุมอยู่)")
            else:
                bad("Firewall: ไม่พบกฎ ZAIA Remote และไม่ได้เป็น admin สร้างให้ไม่ได้")
            with peers_lock:
                others = {k: dict(v) for k, v in peers.items()}
            if not others:
                bad("โปรแกรมยังไม่พบเครื่องอื่น (ต้องเปิดโปรแกรมรุ่นนี้ค้างไว้ทั้งสองเครื่อง)")
            for v in others.values():
                t = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                t.settimeout(3)
                try:
                    t.connect((v["ip"], CTRL_PORT))
                    t.sendall(b"P")
                    good(f"{v['host']} ({v['ip']}) พอร์ต {CTRL_PORT} เชื่อมได้, รุ่น {v['ver']}" + ("" if v["ver"] == APP_VER else "  ← ควรอัปเดตเป็น v" + APP_VER))
                except Exception:
                    bad(f"{v['host']} ({v['ip']}) เชื่อมพอร์ต {CTRL_PORT} ไม่ได้ → Firewall ฝั่งนั้นบล็อก หรือโปรแกรมฝั่งนั้นไม่ได้เปิดพอร์ต")
                finally:
                    t.close()
            root.after(0, lambda: show_diag(L))
        def work():
            try:
                run()
            except Exception as e:
                log_err(e)
                L.append(f"✘ ตรวจไม่สำเร็จ: {e}")
                root.after(0, lambda: show_diag(L))
        threading.Thread(target=work, daemon=True).start()

    def show_diag(L):
        w = tk.Toplevel(root)
        w.title("ผลการตรวจปัญหา")
        w.configure(bg=BG)
        w.geometry(f"{S(660)}x{S(440)}")
        t = tk.Text(w, bg=PANEL2, fg=TEXT, font=FNT(13), wrap="word", relief="flat", padx=12, pady=10, spacing3=S(4))
        t.pack(fill="both", expand=True, padx=12, pady=12)
        t.tag_configure("ok", foreground=OK_C)
        t.tag_configure("bad", foreground=DUP_C)
        for line in L:
            t.insert("end", line + "\n", "ok" if line.startswith("✔") else "bad" if line.startswith("✘") else "")
        t.config(state="disabled")
        notify("ตรวจปัญหาเสร็จแล้ว")

    def refresh_now(e=None):
        threading.Thread(target=send_presence, daemon=True).start()
        nb_wake.set()
        refresh_loop(False)
        notify("รีเฟรชแล้ว")
    root.bind("<F5>", refresh_now)

    # ---------- โหมดแอดมิน (ซ่อน) ----------
    # พิมพ์ "god" (แป้นอังกฤษ) หรือ "เนก" (แป้นไทย) ที่ไหนในโปรแกรมก็ได้เพื่อสลับเปิด/ปิด
    # ปุ่มส่ง/ดึงไฟล์ที่เพิ่มมายังต้องขอเชื่อมต่อแล้วให้อีกฝั่งกดอนุญาตเหมือนเดิมทุกครั้ง ไม่ข้ามขั้นตอนนี้
    BG_OPTS = ("bg", "background", "activebackground", "highlightbackground", "selectcolor")
    FG_OPTS = ("fg", "foreground", "activeforeground", "insertbackground")
    admin_only = {}

    def recolor_widget(w, m=None):
        if m is None: m = trans({}, cmap())
        for opt in BG_OPTS + FG_OPTS:
            try: cur = str(w.cget(opt)).lower()
            except Exception: continue
            if opt in FG_OPTS and cur == "#ffffff": continue  # ตัวอักษรขาวบนปุ่ม ไม่แปลง
            n = m.get(cur)
            if n:
                try: w.config(**{opt: n})
                except Exception: pass
        for c in w.winfo_children():
            recolor_widget(c, m)

    def recolor_misc():  # แท็กสีในตาราง + ธีมพื้นฐานของกล่องมาตรฐาน (simpledialog)
        d, r_ = ADMIN[0], RETRO[0]; P = cmap()
        tree.tag_configure("ok", foreground=P.get(OK_C, OK_C))
        tree.tag_configure("me", foreground=P[ACCENT] if r_ else "#ff6b81" if d else ACCENT)
        tree.tag_configure("dup", foreground="#ff9f43" if d else "#ffb347" if r_ else "#b36200")
        if P:
            dflt = {"Toplevel.background": P[PANEL], "Frame.background": P[PANEL], "Label.background": P[PANEL],
                    "Label.foreground": P[TEXT], "Entry.background": P[PANEL2], "Entry.foreground": P[TEXT],
                    "Entry.insertBackground": P[TEXT], "Button.background": P[PANEL2], "Button.foreground": P[TEXT]}
        else:
            dflt = {"Toplevel.background": "SystemButtonFace", "Frame.background": "SystemButtonFace",
                    "Label.background": "SystemButtonFace", "Label.foreground": "SystemButtonText",
                    "Entry.background": "SystemWindow", "Entry.foreground": "SystemWindowText",
                    "Entry.insertBackground": "SystemWindowText",
                    "Button.background": "SystemButtonFace", "Button.foreground": "SystemButtonText"}
        for k, v in dflt.items():
            root.option_add("*" + k, v, 80)

    FONT_ORIG = [FONT[0]]
    def set_retro(on, quiet=False):  # ธีม Retro 8-bit: จานสีเครื่องเกม ปุ่มนูนขอบดำ ฟอนต์ตัวหนาแบบจอเก่า (ใช้ได้ทั้งปกติและโหมดแอดมิน)
        if on == RETRO[0]: return
        old = cmap()
        errs = []
        def step(fn):
            try: fn()
            except Exception as e: errs.append(str(e)); log_err(f"set_retro {e}")
        RETRO[0] = on
        FONT[0] = "Courier New" if on else FONT_ORIG[0]
        def fonts():
            for ft in _FONTS.values(): ft.configure(family=FONT[0])
        step(fonts)
        step(lambda: apply_styles(ADMIN[0]))
        step(lambda: recolor_widget(root, trans(old, cmap())))
        step(recolor_misc)
        step(update_cols)
        if errs and not quiet: notify("ธีม Retro มีข้อผิดพลาด: " + errs[0][:80], True)
    def toggle_retro():
        want = retro_var.get(); cfg["retro"] = want; save_config(cfg)
        set_retro(want)
        notify("เปิดธีม Retro 8-bit แล้ว (หน้าต่างเกมที่เปิดใหม่จะเป็นธีมนี้ด้วย)" if want else "กลับธีมเดิมแล้ว")
    def toggle_admin():  # แต่ละขั้นแยก try: ขั้นไหนพัง ปุ่มกับขั้นอื่นยังทำงาน และแจ้งข้อผิดพลาดบนหน้าจอ
        old = cmap()
        ADMIN[0] = not ADMIN[0]
        errs = []
        def step(fn):
            try: fn()
            except Exception as e:
                errs.append(f"{getattr(fn, '__name__', 'step')}: {e}"); log_err(f"toggle_admin {errs[-1]}")
        for w, kw in admin_only.items():  # ปุ่มก่อนเสมอ
            step(lambda w=w, kw=kw: w.pack(**kw) if ADMIN[0] else w.pack_forget())
        step(update_cols)
        step(lambda: [reflow(f) for f in list(flows)])
        step(lambda: apply_styles(ADMIN[0]))
        step(lambda: recolor_widget(root, trans(old, cmap())))
        step(recolor_misc)
        step(refresh_active_label)
        threading.Thread(target=send_presence, daemon=True).start()
        if ADMIN[0] and not cfg.get("username"): root.after(200, set_admin_name)
        if errs: notify("โหมดแอดมินมีข้อผิดพลาด: " + " | ".join(errs[:2]), True)
        else: notify("เปิดโหมดแอดมินแล้ว (พิมพ์ god ซ้ำเพื่อปิด)" if ADMIN[0] else "ปิดโหมดแอดมินแล้ว")

    _godbuf = [""]
    def on_any_key(e):
        ch = e.char
        if not ch or isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)): return
        _godbuf[0] = (_godbuf[0] + ch)[-3:]
        if _godbuf[0].lower() == "god" or _godbuf[0] == "เนก":
            _godbuf[0] = ""
            toggle_admin()
    root.bind_all("<Key>", on_any_key, add="+")
    root.bind_class("Toplevel", "<Map>", lambda e: recolor_widget(e.widget) if cmap() else None, add="+")

    def set_admin_name():  # กล่องธีมเอง (ไม่ใช้ simpledialog ของ Windows ที่เป็นสีขาวตายตัว ขัดธีมแดงดำ)
        pc, pc2 = LIGHT2DARK[PANEL], LIGHT2DARK[PANEL2]
        tc, sc, ac = LIGHT2DARK[TEXT], LIGHT2DARK[SUBTEXT], LIGHT2DARK[ACCENT]
        dim = tk.Frame(root, bg=LIGHT2DARK["#2c3e5c"])
        dim.place(x=0, y=0, relwidth=1, relheight=1)
        w = tk.Frame(dim, bg=pc, highlightbackground=ac, highlightthickness=4)
        w.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(w, text="ตั้งชื่อผู้ใช้ (โหมดแอดมิน)", bg=pc, fg=tc, font=FNT(20, "bold")).pack(anchor="w", padx=28, pady=(24, 4))
        tk.Label(w, text="พิมพ์ชื่อเอง โปรแกรมจำไว้ เปลี่ยนได้ภายหลัง", bg=pc, fg=sc, font=FNT(13)).pack(anchor="w", padx=28)
        v_name = tk.StringVar(value=cfg.get("username", ""))
        ent = tk.Entry(w, textvariable=v_name, width=28, font=FNT(15), bg=pc2, fg=tc,
                        insertbackground=tc, relief="flat")
        ent.pack(padx=28, pady=16, ipady=6)
        def ok():
            if v_name.get().strip():
                cfg["username"] = v_name.get().strip()
                save_config(cfg)
                refresh_active_label()
                threading.Thread(target=send_presence, daemon=True).start()
            dim.destroy()
        row = tk.Frame(w, bg=pc); row.pack(fill="x", padx=28, pady=(0, 22))
        ttk.Button(row, text="ตกลง", style="Go.TButton", command=ok).pack(side="right")
        ttk.Button(row, text="ยกเลิก", style="Ghost.TButton", command=dim.destroy).pack(side="right", padx=10)
        ent.bind("<Return>", lambda e: ok())
        dim.lift(); w.grab_set(); ent.focus_set()

    def selected_targets():  # [(uid, [ip ...], ชื่อเครื่อง, รุ่นจริง, ซ่อนอยู่ไหม)] ไม่รวมเครื่องตัวเอง
        out = []
        for uid in tree.selection():
            if uid == MY_ID: continue
            vals = tree.item(uid)["values"]
            with peers_lock:
                p = peers.get(uid, {})
                stealth = bool(p.get("stealth"))
                # โหมดแอดมิน (god mode) บัง IP/รุ่นในตารางเป็น "-" ไว้เพื่อความเป็นส่วนตัว -> ต้องอ่านค่าจริงจาก peers ไม่ใช่จากตารางที่โชว์ ไม่งั้นเช็กรุ่น/ต่อ IP ผิดเสมอ
                ip = p.get("ip") or str(vals[3])
                ips = [ip] + sorted(p.get("ips", set()) - {ip})
                ver = p.get("ver") or str(vals[5])
                # ตารางโชว์ชื่อเครื่องเป็น "•" ตอนซ่อนอยู่ (ไม่มีประโยชน์ในข้อความแจ้งเตือน) -> ใช้ชื่อคน (code) แทนถ้าซ่อนอยู่
                name = p.get("code") or str(vals[0]) if stealth else str(vals[0])
            out.append((uid, ips, name, ver, stealth))
        return out

    def new_only(ts):  # เครื่องซ่อนอยู่ (god mode): ติดต่อได้เฉพาะตอนเราก็เปิด god mode เหมือนกัน (คนละ god mode ขวางไว้เหมือนเดิม) + ตัดเครื่องที่ยังไม่รองรับฟีเจอร์ใหม่ (รุ่นต่ำกว่า 1.13.0) ออก พร้อมแจ้งแยกกัน
        blocked = [t for t in ts if t[4] and not ADMIN[0]]
        if blocked:
            notify("ข้ามเครื่องที่ซ่อนอยู่ (โหมดแอดมิน) ต้องเปิด god mode ก่อนถึงจะส่ง/ดึงไฟล์ได้: " + ", ".join(t[2] for t in blocked), True)
        rest = [t for t in ts if not (t[4] and not ADMIN[0])]
        old = [t for t in rest if not supports_new(t[3])]
        if old: notify("ข้ามเครื่องที่ยังไม่รองรับ (ต้องอัปเดตเป็น 1.13.0): " + ", ".join(t[2] for t in old), True)
        return [t for t in rest if supports_new(t[3])]

    def pick_remote_dir_sync(sock, who):  # เรียกในเธรดเชื่อมต่อหลังปลายทางกดอนุญาต: เด้งป็อปอัปเลือกโฟลเดอร์ของเครื่อง who คืนพาธ (None = ยกเลิก/สายขาด)
        res, ev, holder = [None], threading.Event(), {"ready": threading.Event()}
        slk = threading.Lock()
        def request(path):
            pb = path.encode("utf-8")
            try:
                with slk: sock.sendall(b"L" + len(pb).to_bytes(2, "little") + pb)
            except Exception as e: log_err(e)
        def build():
            dim, w, c = popup(f"เลือกโฟลเดอร์ปลายทางบน {who}")
            col = dict(bg=c(PANEL), acc=c(ACCENT), fg=c(TEXT), sub=c(SUBTEXT), bad=c(DUP_C), go="Go.TButton", ghost="Ghost.TButton")
            def done(p):
                res[0] = p; ev.set()
                if dim.winfo_exists(): dim.destroy()
            holder["fill"] = build_dir_chooser(w, col, request, done); holder["dim"] = dim; holder["ready"].set()
        with DIR_LOCK:
            root.after(0, build)
            if not holder["ready"].wait(5): return None
            request("")
            try:
                while not ev.is_set():
                    r, _, _ = select.select([sock], [], [], 0.2)
                    if not r: continue
                    lb = recv_exact(sock, 4)
                    if not lb: break
                    n = int.from_bytes(lb, "little"); data = recv_exact(sock, n & 0x1FFFFFFF)
                    if not data: break
                    if n & 0x80000000 and data[:1] == b"L":
                        try: info = json.loads(data[1:].decode("utf-8"))
                        except ValueError: continue
                        root.after(0, lambda i=info: holder["fill"](i))
            finally:
                def kill():
                    if holder["dim"].winfo_exists(): holder["dim"].destroy()
                root.after(0, kill)
        return res[0]

    def run_multi_send(ts, paths):  # ป็อปอัปในโปรแกรม: ส่งไปหลายเครื่องพร้อมกัน แต่ละเครื่องรอกดอนุญาตเอง ปิดเองเมื่อสำเร็จครบ
        dim, w, c = popup(f"ส่ง {len(paths)} ไฟล์ ไป {len(ts)} เครื่อง")
        box = tk.Label(w, bg=c(PANEL2), fg=c(TEXT), font=FNT(13), justify="left", anchor="nw", width=44, height=min(len(ts), 8) + 1)
        box.pack(padx=S(24), pady=S(6), fill="x", ipady=S(6))
        stop, status = threading.Event(), {t[0]: "รอปลายทางกดอนุญาต ..." for t in ts}
        def close():
            stop.set()
            if dim.winfo_exists(): dim.destroy()
        def render():
            if dim.winfo_exists(): box.config(text="\n".join(f"{t[2]}:  {status[t[0]]}" for t in ts))
        def upd(uid, text):
            def f():
                status[uid] = text; render()
                if all(v.startswith("✓") for v in status.values()): root.after(1500, close)
            try: root.after(0, f)
            except Exception: pass
        ttk.Button(w, text="ปิด / ยกเลิก", style="Ghost.TButton", command=close).pack(side="right", padx=S(24), pady=(S(4), S(20)))
        def worker(t):
            uid, ips = t[0], t[1]
            got = {}
            def work(sock):
                upd(uid, "เลือกโฟลเดอร์ปลายทาง ...")
                dest = pick_remote_dir_sync(sock, t[2])
                if dest is None: raise RuntimeError("ยกเลิกการเลือกโฟลเดอร์")
                if stop.is_set(): raise RuntimeError("ยกเลิก")
                upd(uid, "กำลังส่ง ...")
                got["dest"] = dest
                got["acks"] = push_files(sock, paths, lambda pc: upd(uid, f"กำลังส่ง {pc}%"), stop, dest)
            ok, msg = files_session(ips, work)
            upd(uid, (f"✓ ส่งเสร็จ ที่ {got.get('dest')}" if got.get("acks", 0) >= len(paths) else "✓ ส่งเสร็จ (ปลายทางรุ่นเก่า วางที่เดสก์ท็อป)") if ok else "✗ " + msg)
        for t in ts: threading.Thread(target=worker, args=(t,), daemon=True).start()
        render()

    def open_pull(t):  # ป็อปอัปในโปรแกรม: เรียกดูโฟลเดอร์เครื่องปลายทางแล้วดึงไฟล์ (โฟลเดอร์ = zip) ไม่ดูจอ ไม่มีหน้าต่างแยก
        ips, name = t[1], t[2]
        dim, w, c = popup(f"ดึงไฟล์จาก {name}")
        lbl = tk.Label(w, text="รอปลายทางกดอนุญาต (สูงสุด 60 วินาที) ...", bg=c(PANEL), fg=c(ACCENT), anchor="w", justify="left",
                       font=FNT(12), wraplength=max(min(S(620), root.winfo_width() - S(120)), S(240)))
        lbl.pack(fill="x", padx=S(24))
        mid = tk.Frame(w, bg=c(PANEL)); mid.pack(fill="both", expand=True, padx=S(24), pady=S(8))
        tv = ttk.Treeview(mid, columns=("size", "mod"), selectmode="extended", height=8)
        tv.heading("#0", text="ชื่อ"); tv.heading("size", text="ขนาด"); tv.heading("mod", text="แก้ไขล่าสุด")
        tv.column("#0", width=S(280)); tv.column("size", width=S(90), anchor="e"); tv.column("mod", width=S(140), anchor="center")
        sb = ttk.Scrollbar(mid, orient="vertical", command=tv.yview); tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); tv.pack(side="left", fill="both", expand=True)
        pb = ttk.Progressbar(w, maximum=100); pb.pack(fill="x", padx=S(24))
        row = tk.Frame(w, bg=c(PANEL)); row.pack(fill="x", padx=S(24), pady=S(12))
        st = {"sock": None, "lock": threading.Lock(), "alive": True, "parent": None, "items": {}, "fh": None, "path": "",
              "size": 0, "got": 0, "t0": 0.0, "last": 0.0, "nm": "", "q": [], "n": 0, "i": 0, "dir": None}
        def ui(fn):
            def f():
                if dim.winfo_exists(): fn()
            try: root.after(0, f)
            except Exception: pass
        def send(*p):
            try:
                with st["lock"]: st["sock"].sendall(b"".join(p))
            except Exception as e: log_err(e)
        def go(path):
            lbl.config(text="กำลังโหลด ...", fg=c(ACCENT))
            pbts = path.encode("utf-8"); send(b"L", len(pbts).to_bytes(2, "little"), pbts)
        def pull_next(ok=True):
            if st["q"]:
                st["i"] += 1
                pbts = st["q"].pop(0).encode("utf-8"); send(b"G", len(pbts).to_bytes(2, "little"), pbts)
            else:
                n = st["n"]; st["n"] = 0
                ui(lambda: pb.config(value=0))
                if n and ok: ui(lambda: lbl.config(text=f"ดึงเสร็จ {n} ไฟล์ ที่ {st.get('dir') or 'เดสก์ท็อปเครื่องนี้'}", fg=c(OK_C)))
        def fill(info):
            if info.get("error"):
                lbl.config(text=info["error"], fg=c(DUP_C)); return
            st.update(parent=info["parent"], items={})
            lbl.config(text=info["path"] or "เครื่องนี้ (ไดรฟ์และโฟลเดอร์ผู้ใช้)", fg=c(ACCENT))
            tv.delete(*tv.get_children())
            for i, it in enumerate(info["items"]):
                st["items"][str(i)] = (it.get("p") or ntpath.join(info["path"], it["n"]), it["d"])
                tv.insert("", "end", iid=str(i), text=("▸ " if it["d"] else "") + it["n"],
                          values=("" if it["d"] else fmt_size(it["s"]), time.strftime("%Y-%m-%d %H:%M", time.localtime(it["m"])) if it["m"] else ""))
        def on_packet(p):
            tt, d = p[:1], p[1:]
            if tt == b"S": st["size"] = int.from_bytes(d[:8], "little")
            elif tt == b"N":
                if st["fh"]: st["fh"].close()
                st["path"] = unique_path(d.decode("utf-8", "replace"), st.get("dir")); st["fh"] = open(st["path"], "wb")
                st.update(got=0, t0=time.time(), last=0.0, nm=os.path.basename(st["path"]))
            elif tt == b"D" and st["fh"]:
                st["fh"].write(d); st["got"] += len(d)
                if time.time() - st["last"] > 0.12:
                    st["last"] = time.time(); g_, s_ = st["got"], max(st["size"], 1)
                    txt = f"ดึง {st['i']}/{st['n']}: {st['nm']}   {fmt_size(g_)} / {fmt_size(s_)}   {fmt_size(g_ / max(time.time() - st['t0'], 0.001))}/วินาที"
                    ui(lambda: (pb.config(value=100 * g_ / s_), lbl.config(text=txt, fg=c(ACCENT))))
            elif tt == b"E" and st["fh"]:
                st["fh"].close(); st["fh"] = None; pull_next()
            elif tt == b"X":
                if st["fh"]:
                    st["fh"].close(); st["fh"] = None
                    try: os.remove(st["path"])
                    except OSError: pass
                msg = d.decode("utf-8", "replace")
                ui(lambda: lbl.config(text=msg, fg=c(DUP_C)))
                pull_next(False)
            elif tt == b"L":
                try: info = json.loads(d.decode("utf-8"))
                except ValueError: return
                ui(lambda: fill(info))
        def work(sock):
            st["sock"] = sock
            if not st["alive"]: return
            ui(lambda: lbl.config(text="เชื่อมต่อแล้ว", fg=c(OK_C)))
            send(b"L", (0).to_bytes(2, "little"))
            try:
                while st["alive"]:
                    lb = recv_exact(sock, 4)
                    if not lb: break
                    n = int.from_bytes(lb, "little")
                    data = recv_exact(sock, n & 0x1FFFFFFF)
                    if not data: break
                    if n & 0x80000000: on_packet(data)
            finally:
                if st["fh"]:
                    st["fh"].close(); st["fh"] = None
                    try: os.remove(st["path"])
                    except OSError: pass
        def run():
            ok, msg = files_session(ips, work)
            if st["alive"]: ui(lambda: lbl.config(text="ตัดการเชื่อมต่อแล้ว" if ok else msg, fg=c(DUP_C)))
        def close():
            st["alive"] = False
            st["q"].clear()
            send(b"Z")
            try: st["sock"].close()
            except Exception: pass
            if dim.winfo_exists(): dim.destroy()
        def do_pull():
            files = [st["items"][i][0] for i in tv.selection() if len(st["items"][i][0].rstrip("\\/")) > 2]
            if not files:
                lbl.config(text="เลือกไฟล์หรือโฟลเดอร์ก่อน (โฟลเดอร์จะถูกบีบเป็น zip / ดึงทั้งไดรฟ์ไม่ได้)", fg=c(DUP_C)); return
            if st["fh"] or st["q"]:
                lbl.config(text="กำลังโอนไฟล์อยู่ รอให้เสร็จก่อน", fg=c(DUP_C)); return
            d = filedialog.askdirectory(parent=root, title="เลือกโฟลเดอร์ที่จะวางไฟล์ที่ดึงมา", initialdir=cfg.get("last_recv_dir") or desktop_dir())
            if not d: return
            cfg["last_recv_dir"] = d; save_config(cfg)
            st.update(q=list(files), n=len(files), i=0, dir=d)
            pull_next()
        def open_sel(e=None):
            sel = tv.selection()
            if len(sel) == 1 and st["items"][sel[0]][1]: go(st["items"][sel[0]][0])
            elif sel: do_pull()
        tv.bind("<Double-1>", open_sel)
        ttk.Button(row, text="ดึงที่เลือก", style="Go.TButton", command=do_pull).pack(side="right")
        ttk.Button(row, text="ปิด", style="Ghost.TButton", command=close).pack(side="right", padx=8)
        ttk.Button(row, text="เปิดโฟลเดอร์", style="Ghost.TButton", command=open_sel).pack(side="left")
        ttk.Button(row, text="↑ ขึ้นไป", style="Ghost.TButton", command=lambda: go(st["parent"] or "")).pack(side="left", padx=8)
        threading.Thread(target=run, daemon=True).start()

    def quick_admin_action(kind):  # ส่งไฟล์ (หลายเครื่องได้) / ดึงไฟล์ (ทีละเครื่อง) แบบไม่ดูจอ เป็นป็อปอัปในโปรแกรม ปลายทางยังต้องอนุญาต เว้นเครื่องที่เปิดรับอัตโนมัติ
        if not tree.selection():
            notify("คลิกเลือกเครื่องอื่นในรายการก่อน (เลือกหลายเครื่องได้ด้วย Ctrl/Shift)", True)
            return
        ts = new_only(selected_targets())
        if not ts: return
        if kind == "pull":
            if len(ts) > 1:
                notify("ดึงไฟล์เลือกได้ทีละเครื่อง", True)
                return
            open_pull(ts[0])
            return
        ps = filedialog.askopenfilenames(parent=root, title="เลือกไฟล์ที่จะส่ง")
        if ps: run_multi_send(ts, [x for x in ps if os.path.isfile(x)])

    def ask_text(title, label, cb, initial=""):  # กล่องพิมพ์ข้อความ เป็นป็อปอัปในโปรแกรม ขนาดตามเนื้อหา ปุ่มไม่โดนตัด
        dim, w, c = popup(title)
        tk.Label(w, text=label, bg=c(PANEL), fg=c(SUBTEXT), font=FNT(13), justify="left",
                 wraplength=max(min(S(620), root.winfo_width() - S(120)), S(240))).pack(anchor="w", padx=S(24))
        ent = tk.Entry(w, bg=c(PANEL2), fg=c(TEXT), insertbackground=c(TEXT), relief="flat", font=FNT(15), width=30)
        ent.pack(fill="x", padx=S(24), pady=S(14), ipady=S(8))
        ent.insert(0, initial)
        def ok():
            t = ent.get().strip()
            dim.destroy()
            if t: cb(t)
        row = tk.Frame(w, bg=c(PANEL)); row.pack(fill="x", padx=S(24), pady=(0, S(20)))
        ttk.Button(row, text="ส่ง", style="Go.TButton", command=ok).pack(side="right")
        ttk.Button(row, text="ยกเลิก", style="Ghost.TButton", command=dim.destroy).pack(side="right", padx=10)
        ent.bind("<Return>", lambda e: ok())
        ent.focus_set()

    def do_message():
        if not tree.selection():
            notify("คลิกเลือกเครื่องอื่นในรายการก่อน", True)
            return
        ts = new_only(selected_targets())
        if not ts: return
        def go(text):
            def bulk():
                okn = [t[2] for t in ts if send_message(t[1], text)]
                bad = [t[2] for t in ts if t[2] not in okn]
                notify(f"ส่งข้อความแล้ว {len(okn)}/{len(ts)} เครื่อง" + (f" • ไม่สำเร็จ: {', '.join(bad)}" if bad else ""), bool(bad))
            threading.Thread(target=bulk, daemon=True).start()
        ask_text("ส่งข้อความแจ้งเตือน", f"พิมพ์ข้อความถึง {len(ts)} เครื่อง (ไม่เกิน 300 ตัวอักษร) ปลายทางจะเห็นเป็นกล่องเด้งพร้อมชื่อผู้ส่ง", go)

    def show_history():
        w = tk.Toplevel(root)
        w.title("ประวัติการเชื่อมต่อเข้าเครื่องนี้"); w.geometry("820x480"); w.configure(bg=PANEL)
        bar = tk.Frame(w, bg=PANEL); bar.pack(side="bottom", fill="x", padx=12, pady=10)
        txt = tk.Text(w, bg=PANEL2, fg=TEXT, font=FNT(11), relief="flat", wrap="none", state="disabled")
        sbv = ttk.Scrollbar(w, orient="vertical", command=txt.yview); txt.configure(yscrollcommand=sbv.set)
        sbv.pack(side="right", fill="y", pady=(12, 0)); txt.pack(fill="both", expand=True, padx=(12, 0), pady=(12, 0))
        def load():
            txt.config(state="normal"); txt.delete("1.0", "end")
            txt.insert("end", read_conn_log() or "(ยังไม่มีประวัติ — บันทึกเฉพาะการเชื่อมต่อที่เข้ามาที่เครื่องนี้)")
            txt.see("end"); txt.config(state="disabled")
        ttk.Button(bar, text="ปิด", style="Ghost.TButton", command=w.destroy).pack(side="right")
        ttk.Button(bar, text="รีเฟรช", style="Accent.TButton", command=load).pack(side="right", padx=8)
        load()

    def copy_ips():
        ips = [str(tree.item(i)["values"][3]) for i in tree.selection()]
        if not ips:
            notify("คลิกเลือกเครื่องในรายการก่อน", True)
            return
        root.clipboard_clear(); root.clipboard_append("\n".join(ips))
        notify(f"คัดลอก IP แล้ว {len(ips)} รายการ")

    btn_qsend = ttk.Button(crow, text="ส่งไฟล์ (ไม่ดูจอ)", style="Ghost.TButton",
                            command=lambda: quick_admin_action("send"))
    btn_qpull = ttk.Button(crow, text="ดึงไฟล์ (ไม่ดูจอ)", style="Ghost.TButton",
                            command=lambda: quick_admin_action("pull"))
    add_flow(crow, btn_qsend, True)
    add_flow(crow, btn_qpull, True)

    frm_filter = tk.Frame(right, bg=PANEL)  # ช่องค้นหา (ชื่อเครื่อง/ผู้ใช้/IP) เหนือตาราง
    tk.Label(frm_filter, text="ค้นหา:", bg=PANEL, fg=SUBTEXT, font=FNT(12)).pack(side="left")
    tk.Entry(frm_filter, textvariable=v_filter, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat", font=FNT(12)).pack(side="left", fill="x", expand=True, padx=8, ipady=4)
    v_filter.trace_add("write", lambda *a: refresh_loop(False))
    lbl_detail = tk.Label(right, text="", bg=PANEL, fg=SUBTEXT, anchor="w", justify="left", wraplength=S(500), font=FNT(11))
    def update_detail(e=None):
        sel = tree.selection()
        if len(sel) == 1 and tree.exists(sel[0]):
            vals = [str(x) for x in tree.item(sel[0])["values"]]
            lbl_detail.config(text=f"IP ทั้งหมด: {vals[6]}   •   รุ่น {vals[5]}   •   รหัสเครื่อง: {sel[0]}")
        else:
            lbl_detail.config(text=f"เลือกไว้ {len(sel)} เครื่อง" if sel else "")
    tree.bind("<<TreeviewSelect>>", update_detail, add="+")
    arow = tk.Frame(right, bg=PANEL)
    add_flow(arow, ttk.Button(arow, text="คัดลอก IP", style="Ghost.TButton", command=copy_ips))
    add_flow(arow, ttk.Button(arow, text="ส่งข้อความแจ้งเตือน", style="Ghost.TButton", command=do_message))
    add_flow(arow, ttk.Button(arow, text="ประวัติการเชื่อมต่อ", style="Ghost.TButton", command=show_history))
    admin_only[frm_filter] = {"fill": "x", "padx": 16, "pady": (0, 6), "before": tree}
    admin_only[lbl_detail] = {"side": "bottom", "fill": "x", "padx": 16, "pady": (0, 4), "after": crow}
    admin_only[arow] = {"side": "bottom", "fill": "x", "padx": 16, "pady": (0, 2), "after": crow}

    def fit_wrap(e=None):
        try:
            lw, rw_ = max(left.winfo_width() - S(110), S(180)), max(right.winfo_width() - S(60), S(180))
            lbl_active.config(wraplength=lw); lbl_ztst.config(wraplength=lw); lbl_status.config(wraplength=rw_); lbl_detail.config(wraplength=rw_)
        except Exception as ex:
            log_err(ex)
    left.bind("<Configure>", fit_wrap, add="+"); right.bind("<Configure>", fit_wrap, add="+")
    _rs = [None]
    def do_rescale():
        f = max(0.6, min(1.3, min(root.winfo_width() / S(1280), root.winfo_height() / S(720))))
        if abs(f - SCALE[0]) < 0.04: return
        rescale_fonts(f)
        style.configure("Treeview", rowheight=int(S(46) * f))
    def on_resize(e):
        if e.widget is not root: return
        if _rs[0]: root.after_cancel(_rs[0])
        _rs[0] = root.after(250, do_rescale)
    root.bind("<Configure>", on_resize, add="+")
    root.after(400, do_rescale)
    root.after(300, lambda: [reflow(f) for f in list(flows)])

    # ---------- tray ----------
    def show_window(icon=None, item=None):
        root.after(0, root.deiconify)
    def quit_app(icon=None, item=None):
        tray_icon.stop()
        root.after(0, root.destroy)
        os._exit(0)
    try:
        tray_image = Image.open(ICON_PATH)
    except Exception:
        tray_image = Image.new("RGB", (64, 64), "blue")
    menu = pystray.Menu(
        pystray.MenuItem("เปิดหน้าต่าง", show_window, default=True),
        pystray.MenuItem("ออกจากโปรแกรม", quit_app),
    )
    tray_icon = pystray.Icon("ZaiaRemote", tray_image, "ZAIA Remote Desktop", menu)
    threading.Thread(target=tray_icon.run, daemon=True).start()

    def on_close():
        root.withdraw()
        tray_icon.notify("ทำงานอยู่พื้นหลัง ดับเบิลคลิกไอคอนเพื่อเปิด", "ZAIA Remote Desktop")
    root.protocol("WM_DELETE_WINDOW", on_close)
    if cfg.get("retro"): set_retro(True, True)

    if not (cfg.get("role") and cfg.get("unit")):
        root.deiconify()
        ask_user(True)
    elif "--silent" in sys.argv:
        root.withdraw()
    root.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_err(e)
        try:
            ctypes.windll.user32.MessageBoxW(0, f"ZAIA Remote เจอข้อผิดพลาด:\n{e}\n\nดูไฟล์ {ERRLOG}", "ZAIA Remote - Error", 0)
        except Exception:
            pass
