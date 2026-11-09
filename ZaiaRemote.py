# -*- coding: utf-8 -*-
import sys, os, json, socket, threading, time, io, ctypes, subprocess, winreg, re, ipaddress, uuid, urllib.request, zlib, queue, hashlib, struct, ntpath
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
APP_VER = "3.1.2"
SETUP_REV = 3  # เลขรุ่นของตัวติดตั้ง/ไลบรารีใน python\ ถ้า update.json ระบุ setup_rev สูงกว่านี้ ต้องลงด้วยตัวติดตั้งใหม่
UPDATE_URL = "https://raw.githubusercontent.com/Minos117/ZaiaRemote.py/refs/heads/main/ZaiaRemote.py"  # ต้องเป็นลิงก์ดาวน์โหลดตรง (repo public)
DEFAULT_NB_URL = "https://api.netbird.io:443"
DEFAULT_NB_KEY = "8D691314-64C7-458B-9F4E-F6A5E8CC2FC8"  # Setup Key ฝังไว้ให้เชื่อมต่ออัตโนมัติ (ถ้าเปลี่ยนใน update.json หรือหน้าตั้งค่า จะใช้ค่าใหม่แทน)
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

def push_files(sock, paths, progress=None, stop=None):
    total = sum(os.path.getsize(x) for x in paths) or 1
    done, last = 0, 0.0
    for x in paths:
        nb = os.path.basename(x).encode("utf-8")
        size = os.path.getsize(x)
        sock.sendall(b"F" + len(nb).to_bytes(2, "little") + nb + size.to_bytes(8, "little"))
        with open(x, "rb") as f:
            while True:
                if stop is not None and stop.is_set(): raise RuntimeError("ยกเลิก")
                b = f.read(131072)
                if not b: break
                sock.sendall(b"C" + len(b).to_bytes(4, "little") + b)
                done += len(b)
                if progress and time.time() - last > 0.3:
                    last = time.time(); progress(int(done * 100 / total))

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
    msg = f"{HOSTNAME}|{username()}|{APP_VER}|{MY_ID}|{'S' if ADMIN[0] else ''}".encode("utf-8")
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
            if uid == MY_ID:
                continue
            with peers_lock:
                p = peers.setdefault(uid, {"ips": set()})
                p.update(host=host, code=code, ver=ver, last=time.time(), ip=addr[0], stealth=stealth)
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

def desktop_dir():
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)
    return buf.value or os.path.join(os.environ["USERPROFILE"], "Desktop")

def unique_path(name):
    name = os.path.basename(name) or "file"
    base, ext = os.path.splitext(name)
    p, i = os.path.join(desktop_dir(), name), 1
    while os.path.exists(p):
        p = os.path.join(desktop_dir(), f"{base} ({i}){ext}")
        i += 1
    return p

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

def handle_control_client(client, q=1, h264=False, mon_idx=1, who=""):
    maxw, fps, _ = QUALITY[q]
    if maxw == 0: maxw = 1 << 16
    lock = threading.Lock()
    watcher_add(who)
    try:
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 524288)  # BDP ของ NetBird สูง buffer ส่งเล็กเกินทำให้ความเร็วตก (ใหญ่เกินจะหน่วง)
        grab = make_grabber(mon_idx)
        w, h = grab().size
        client.sendall(w.to_bytes(4, "little") + h.to_bytes(4, "little"))
        gone = threading.Event()
        threading.Thread(target=apply_input_loop, args=(client, gone, lock), daemon=True).start()
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
        try: client.close()
        except Exception: pass

def apply_input_loop(client, gone, lock, files_only=False):
    fh, rem, fp = None, 0, None
    cancel = threading.Event()
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
                set_cursor(x, y)
            elif t == "D":
                b = recv_exact(client, 1)[0]
                mouse_event(MOUSE_FLAGS_DOWN.get(b, 0x0002))
            elif t == "U":
                b = recv_exact(client, 1)[0]
                mouse_event(MOUSE_FLAGS_UP.get(b, 0x0004))
            elif t == "W":
                b = recv_exact(client, 4)
                delta = int.from_bytes(b, "little", signed=True)
                mouse_event(0x0800, ctypes.c_uint32(delta).value)
            elif t == "K":
                b = recv_exact(client, 4)
                vk = int.from_bytes(b, "little", signed=True)
                keybd_event(vk, False)
            elif t == "J":
                b = recv_exact(client, 4)
                vk = int.from_bytes(b, "little", signed=True)
                keybd_event(vk, True)
            elif t == "F":  # เริ่มรับไฟล์: ชื่อ(2+n) ขนาด(8) -> เก็บบนเดสก์ท็อป
                n = int.from_bytes(recv_exact(client, 2), "little")
                name = recv_exact(client, n).decode("utf-8", "replace")
                rem = int.from_bytes(recv_exact(client, 8), "little")
                if fh: fh.close()
                fp = unique_path(name)
                conn_log(f"{peer} | ส่งไฟล์เข้ามา: {name} ({rem} ไบต์)")
                fh = open(fp, "wb")
                if rem == 0:
                    fh.close(); fh = None
            elif t == "C":  # ข้อมูลไฟล์ทีละก้อน
                n = int.from_bytes(recv_exact(client, 4), "little")
                if n > (1 << 20): break
                d = recv_exact(client, n)
                if fh:
                    fh.write(d); rem -= n
                    if rem <= 0:
                        fh.close(); fh = None
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
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)  # ต้องตั้งก่อน connect
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
    pull = {"q": [], "n": 0, "i": 0}
    br = {"fill": None}

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
                say(f"ดึงไฟล์เสร็จ {pull['n']} ไฟล์ (อยู่บนเดสก์ท็อปเครื่องนี้)")
                pull["n"] = 0

    def start_pull(paths):  # ดึงทีละไฟล์ตามลำดับ (ฝั่งนี้ส่งคำขอถัดไปเมื่อไฟล์ก่อนหน้าเสร็จ)
        if rf["fh"] or pull["q"]:
            say("กำลังโอนไฟล์อยู่ รอให้เสร็จก่อน", "#ff6b6b")
            return
        pull.update(q=list(paths), n=len(paths), i=0)
        pull_next()

    def on_file_packet(p):
        t, d = p[:1], p[1:]
        if t == b"S":
            rf["size"] = int.from_bytes(d[:8], "little")
        elif t == b"N":
            if rf["fh"]: rf["fh"].close()
            rf["path"] = unique_path(d.decode("utf-8", "replace"))
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

    def send_files(paths):
        paths = [x for x in paths if os.path.isfile(x)]
        if not paths: return
        cancel_up.clear()
        def run():
            for k, x in enumerate(paths, 1):
                name, size = os.path.basename(x), os.path.getsize(x)
                t0, last, done = time.time(), 0.0, 0
                try:
                    nb = name.encode("utf-8")
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
            say(f"ส่งไฟล์แล้ว {len(paths)} ไฟล์ (อยู่บนเดสก์ท็อปเครื่องปลายทาง)")
        threading.Thread(target=run, daemon=True).start()

    def pick_send():
        ps = filedialog.askopenfilenames(parent=win)
        if ps: send_files(list(ps))

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

    def on_move(e):
        x, y = scaled(e)
        send(b"M", x.to_bytes(4, "little", signed=True), y.to_bytes(4, "little", signed=True))
    def on_down(e, btn):
        on_move(e)
        send(b"D", bytes([btn]))
    def on_up(e, btn):
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
            canvas.dnd_bind("<<Drop>>", lambda e: send_files(list(win.tk.splitlist(e.data))))
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
    style = ttk.Style(root)
    style.theme_use("clam")
    root.option_add("*TCombobox*Listbox.font", FNT(13))
    def apply_styles(dark=False):  # ตั้งสไตล์ ttk ใหม่ทั้งชุดจากค่าตรงๆ (ไม่อ่านค่าเก่ากลับมา)
        c = (lambda x: LIGHT2DARK.get(x, x)) if dark else (lambda x: x)
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
        style.configure("Treeview", background=c(PANEL2), fieldbackground=c(PANEL2), foreground=c(TEXT), rowheight=int(S(46) * SCALE[0]), borderwidth=0, font=FNT(12))
        style.configure("Treeview.Heading", background=c(PANEL), foreground=c(ACCENT), font=FNT(12, "bold"), borderwidth=0)
        style.map("Treeview", background=[("selected", c(ACCENT2))], foreground=[("selected", "#ffffff")])
    apply_styles(False)

    def popup(title):  # ป็อปอัปกลางหน้าต่างหลัก (ไม่สร้างหน้าต่างแยก) คืน (พื้นหลัง, กล่อง, ฟังก์ชันแปลงสี)
        c = (lambda x: LIGHT2DARK.get(x, x)) if ADMIN[0] else (lambda x: x)
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
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((ip, CTRL_PORT))
            s.sendall(b"M")
            n = s.recv(1)
            s.close()
            return max(1, n[0]) if n else 1
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
        if ADMIN[0]: recolor_widget(w)
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
                   anchor="w", justify="left", wraplength=S(520)).pack(fill="x", padx=16, pady=(0, 14))
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
        who = str(tree.item(uid)["values"][1])
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
            all_m = {MY_ID: {"host": HOSTNAME, "code": username(), "ip": "127.0.0.1", "ver": APP_VER}}
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

    def recolor_widget(w):
        m = LIGHT2DARK if ADMIN[0] else DARK2LIGHT
        for opt in BG_OPTS + FG_OPTS:
            try: cur = str(w.cget(opt)).lower()
            except Exception: continue
            if opt in FG_OPTS and cur == "#ffffff": continue  # ตัวอักษรขาวบนปุ่ม ไม่แปลง
            n = m.get(cur)
            if n:
                try: w.config(**{opt: n})
                except Exception: pass
        for c in w.winfo_children():
            recolor_widget(c)

    def recolor_misc():  # แท็กสีในตาราง + ธีมพื้นฐานของกล่องมาตรฐาน (simpledialog)
        d = ADMIN[0]
        tree.tag_configure("ok", foreground=LIGHT2DARK[OK_C] if d else OK_C)
        tree.tag_configure("me", foreground="#ff6b81" if d else ACCENT)
        tree.tag_configure("dup", foreground="#ff9f43" if d else "#b36200")
        dflt = {"Toplevel.background": "SystemButtonFace", "Frame.background": "SystemButtonFace",
                "Label.background": "SystemButtonFace", "Label.foreground": "SystemButtonText",
                "Entry.background": "SystemWindow", "Entry.foreground": "SystemWindowText",
                "Entry.insertBackground": "SystemWindowText",
                "Button.background": "SystemButtonFace", "Button.foreground": "SystemButtonText"}
        dark = {"Toplevel.background": "#260808", "Frame.background": "#260808", "Label.background": "#260808",
                "Label.foreground": "#f5d9d9", "Entry.background": "#3a0d0d", "Entry.foreground": "#f5d9d9",
                "Entry.insertBackground": "#f5d9d9", "Button.background": "#3a0d0d", "Button.foreground": "#f5d9d9"}
        for k, v in (dark if d else dflt).items():
            root.option_add("*" + k, v, 80)

    def toggle_admin():  # แต่ละขั้นแยก try: ขั้นไหนพัง ปุ่มกับขั้นอื่นยังทำงาน และแจ้งข้อผิดพลาดบนหน้าจอ
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
        step(lambda: recolor_widget(root))
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
    root.bind_class("Toplevel", "<Map>", lambda e: recolor_widget(e.widget) if ADMIN[0] else None, add="+")

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

    def new_only(ts):  # ตัดเครื่องที่ซ่อนอยู่ (เข้าไม่ได้อยู่แล้ว) และเครื่องที่ยังไม่รองรับฟีเจอร์ใหม่ (รุ่นต่ำกว่า 1.13.0) ออก พร้อมแจ้งแยกกัน
        hidden = [t for t in ts if t[4]]
        if hidden:
            notify("ข้ามเครื่องที่ซ่อนอยู่ (โหมดแอดมิน) ส่ง/ดึงไฟล์แบบนี้ไม่ได้: " + ", ".join(t[2] for t in hidden), True)
        rest = [t for t in ts if not t[4]]
        old = [t for t in rest if not supports_new(t[3])]
        if old: notify("ข้ามเครื่องที่ยังไม่รองรับ (ต้องอัปเดตเป็น 1.13.0): " + ", ".join(t[2] for t in old), True)
        return [t for t in rest if supports_new(t[3])]

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
            def work(sock):
                upd(uid, "กำลังส่ง ...")
                push_files(sock, paths, lambda pc: upd(uid, f"กำลังส่ง {pc}%"), stop)
            ok, msg = files_session(ips, work)
            upd(uid, "✓ ส่งเสร็จ (อยู่บนเดสก์ท็อปปลายทาง)" if ok else "✗ " + msg)
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
              "size": 0, "got": 0, "t0": 0.0, "last": 0.0, "nm": "", "q": [], "n": 0, "i": 0}
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
                if n and ok: ui(lambda: lbl.config(text=f"ดึงเสร็จ {n} ไฟล์ (อยู่บนเดสก์ท็อปเครื่องนี้)", fg=c(OK_C)))
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
                st["path"] = unique_path(d.decode("utf-8", "replace")); st["fh"] = open(st["path"], "wb")
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
            st.update(q=list(files), n=len(files), i=0)
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
