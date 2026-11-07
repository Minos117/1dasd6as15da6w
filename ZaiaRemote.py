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
    import av  # H.264: ลื่นและคมกว่า JPEG ใช้เน็ตน้อยกว่า ~10 เท่า (ไม่มี -> ใช้ JPEG เหมือนเดิม)
except Exception:
    av = None

APP_NAME = "ZaiaRemoteDesktop"
APP_VER = "1.13.0"
SETUP_REV = 1  # เลขรุ่นของตัวติดตั้ง/ไลบรารีใน python\ ถ้า update.json ระบุ setup_rev สูงกว่านี้ ต้องลงด้วยตัวติดตั้งใหม่
UPDATE_URL = "https://raw.githubusercontent.com/Minos117/ZaiaRemote.py/refs/heads/main/ZaiaRemote.py"  # ต้องเป็นลิงก์ดาวน์โหลดตรง (repo public)
DEFAULT_ZT_NETWORK_ID = "b103a835d26ef7ce"
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
    return {"autostart": True, "zt_network_id": DEFAULT_ZT_NETWORK_ID}

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
E_LIGHT = {"panel": "#ffffff", "panel2": "#eaf0f9", "accent": "#0b4f9c", "text": "#1a1a1a", "sub": "#4a5668", "ok": "#1b7f3b", "bad": "#c62828"}
E_DARK = {"panel": "#260808", "panel2": "#3a0d0d", "accent": "#e0243f", "text": "#f5d9d9", "sub": "#d79a9a", "ok": "#2ecc71", "bad": "#ff5252"}
def ecol(k):  # สีของแท็บไฟล์ (ใช้ค่าเดียวกับธีมหลัก เพื่อให้ recolor_widget สลับธีมตาม god ได้)
    return (E_DARK if ADMIN[0] else E_LIGHT)[k]
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

def fetch_manifest():  # update.json = {"version","files":{ชื่อไฟล์:sha256},"zt_network_id"?,"zt_leave_old"?,"setup_rev"?}
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
    zt = m.get("zt_network_id")
    if zt and zt != cfg.get("zt_applied"):  # ปรับ ZeroTier เฉพาะตอนค่าใน update.json เปลี่ยน (ไม่ทับที่ผู้ใช้ตั้งเองถ้าค่าไม่ได้ถูกแก้)
        old = cfg.get("zt_network_id")
        cfg["zt_network_id"], cfg["zt_applied"] = zt, zt
        save_config(cfg)
        if m.get("zt_leave_old") and old and old != zt:
            zt_run("leave", old)
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

# ควบคุมหน้าต่าง admin/UAC และสั่ง zerotier-cli ได้ต้องเป็น admin; ถ้าไม่ใช่ ขอสิทธิ์ 1 ครั้ง (ปฏิเสธก็ใช้ต่อได้)
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

# ---------- ZeroTier ----------
ZT = {"ok": False, "node": "", "cidrs": [], "msg": "กำลังตรวจสอบ ZeroTier ..."}
zt_wake = threading.Event()
NET_MSG = {
    "OK": "เชื่อมต่อเครือข่ายแล้ว",
    "ACCESS_DENIED": "รอแอดมิน approve เครื่องนี้ใน ZeroTier Central (ใช้ Node ID ด้านล่าง)",
    "REQUESTING_CONFIGURATION": "กำลังขอค่าเครือข่าย ...",
    "NOT_FOUND": "ไม่พบ Network ID นี้",
}

def zt_cli():
    for env, dflt in (("ProgramFiles", r"C:\Program Files"), ("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        p = os.path.join(os.environ.get(env, dflt), "ZeroTier", "One", "zerotier-cli.bat")
        if os.path.exists(p):
            return p
    return None

def zt_run(*args):
    cli = zt_cli()
    if not cli:
        return None
    try:
        r = subprocess.run([cli, *args], capture_output=True, text=True, timeout=15,
                           cwd=os.path.dirname(cli), creationflags=0x08000000)
        return ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:
        log_err(e)
        return ""

def zt_update():
    info = zt_run("info")
    if info is None:
        ZT.update(ok=False, node="", msg="ไม่พบ ZeroTier — ติดตั้งโปรแกรมใหม่ด้วยตัวติดตั้ง")
        return
    p = info.split()
    if len(p) < 5 or p[0] != "200":
        hint = "" if is_admin() else " (ต้องให้ admin ปลดสิทธิ์ไฟล์ ZeroTier 1 ครั้ง: ติดตั้งทับด้วยรุ่น 1.8.2 หรือดูวิธีใน README)"
        first = info.splitlines()[0][:80] if info else "ไม่มีผลตอบกลับ"
        ZT.update(ok=False, node="", msg=f"ZeroTier ใช้ไม่ได้: {first}{hint}")
        return
    online = p[4] == "ONLINE"
    st, ips, net_ok, cidrs = "ยังไม่ได้เข้าร่วมเครือข่าย", "", False, []
    for line in (zt_run("listnetworks") or "").splitlines():
        m = re.match(r"200 listnetworks (\w{16}) .* (?:[0-9a-f]{2}:){5}[0-9a-f]{2} (\w+) \w+ \S+ (\S+)", line)
        if m and m.group(1) == cfg.get("zt_network_id", ""):
            st = NET_MSG.get(m.group(2), m.group(2))
            ips = "" if m.group(3) == "-" else "  IP " + m.group(3)
            net_ok = m.group(2) == "OK"
            cidrs = [x for x in m.group(3).split(",") if "." in x]
    ZT.update(ok=online and net_ok, node=p[2], cidrs=cidrs,
              msg=("" if online else "ZeroTier ออฟไลน์ (เช็กอินเทอร์เน็ต) — ") + st + ips)

def zt_poll():
    while True:
        try: zt_update()
        except Exception as e: log_err(e)
        zt_wake.wait(10)
        zt_wake.clear()

def zt_grant():  # ให้ user ธรรมดาอ่าน authtoken.secret ได้ zerotier-cli จะได้ไม่ต้องใช้สิทธิ์ admin (ทำได้เฉพาะตอนเป็น admin)
    try:
        f = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "ZeroTier", "One", "authtoken.secret")
        if os.path.exists(f):
            subprocess.run(["icacls", f, "/grant", "*S-1-5-32-545:R"], capture_output=True, creationflags=0x08000000, timeout=15)
    except Exception as e:
        log_err(e)

def ensure_zerotier(network_id):
    if not network_id:
        return
    if is_admin():
        zt_grant()
    if not zt_cli():
        notify("ยังไม่ได้ติดตั้ง ZeroTier — ติดตั้งโปรแกรมใหม่ด้วยตัวติดตั้ง", True)
        return
    for _ in range(6):  # service อาจยังไม่ขึ้นหลังติดตั้งใหม่
        if (zt_run("join", network_id) or "").startswith("200"):
            break
        time.sleep(5)
    zt_wake.set()

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

def send_presence():
    msg = f"{HOSTNAME}|{username()}|{APP_VER}|{MY_ID}".encode("utf-8")
    try:
        ips = socket.gethostbyname_ex(HOSTNAME)[2]
    except Exception:
        ips = []
    for c in ZT["cidrs"]:  # IP ของ ZeroTier เอง (hostname อาจไม่คืนมาถ้าเครื่องมีการ์ดเสมือนเยอะ)
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
            sweep = []  # ส่งตรงหาทุก IP ในวง ไม่พึ่ง broadcast (ZeroTier อาจปิด/จำกัด broadcast)
            for c in ZT["cidrs"]:
                try:
                    n = ipaddress.ip_network(c, strict=False)
                    if ipaddress.ip_address(ip) in n:
                        dsts.append(str(n.broadcast_address))
                        if n.num_addresses <= 1024:
                            sweep += [str(h) for h in n.hosts() if str(h) != ip]
                except Exception:
                    pass
            if not ZT["cidrs"]:  # อ่านสถานะ ZeroTier ไม่ได้ -> เดาเป็น /24
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
            if uid == MY_ID:
                continue
            with peers_lock:
                p = peers.setdefault(uid, {"ips": set()})
                p.update(host=host, code=code, ver=ver, last=time.time(), ip=addr[0])
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
            q, h264 = 1, False
            if hello == b"V":  # 1.6 ส่งระดับคุณภาพต่อท้าย (0-2); รุ่น 1.5 ไม่ส่ง ใช้ค่ากลาง
                try:
                    client.settimeout(0.5)
                    qb = client.recv(1)
                    if qb and qb[0] < len(QUALITY): q = qb[0]
                    h264 = client.recv(1) == b"H"  # 1.8.4 ขึ้นไปบอกว่าถอดรหัส H.264 ได้
                except Exception:
                    pass
            client.settimeout(None)
            if hello == b"P" or hello == b"":
                client.close()
                continue
            ans = 6 if cfg.get("auto_allow") else ctypes.windll.user32.MessageBoxW(0, (peer_name(addr[0]) + "\n" if peer_name(addr[0]) else "") + f"IP {addr[0]}\n\n" + ("ขอส่ง/ดึงไฟล์ในเครื่องนี้ (ไม่ดูจอ) อนุญาตไหม" if hello == b"T" else "ขอเข้ามาดูและควบคุมจอเครื่องนี้ อนุญาตไหม") + "\n(ถ้าไม่รู้จัก ให้กดไม่อนุญาต)", "มีคนขอส่ง/ดึงไฟล์" if hello == b"T" else "มีคนขอเข้ามาช่วยดูจอ", 0x04 | 0x20 | 0x100 | 0x40000)
            if ans != 6:  # IDYES
                client.close()
                continue
            if hello == b"T":  # โหมดไฟล์อย่างเดียว (ไม่จับภาพ ไม่รับเมาส์/คีย์บอร์ด) ยังต้องผ่านกล่องอนุญาตเหมือนเดิม
                threading.Thread(target=handle_files_client, args=(client,), daemon=True).start()
            else:
                threading.Thread(target=handle_control_client, args=(client, q, h264 and av is not None), daemon=True).start()
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

def make_grabber():
    try:
        import mss
        sct = mss.mss()
        mon = sct.monitors[1]
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
    try:
        if blocked(path):
            pkt(b"X", "โฟลเดอร์ระบบ ดึงไฟล์ไม่ได้".encode("utf-8"))
            return
        if not os.path.isfile(path):
            pkt(b"X", f"ไม่พบไฟล์บนเครื่องปลายทาง: {path}".encode("utf-8"))
            return
        pkt(b"S", os.path.getsize(path).to_bytes(8, "little"))
        pkt(b"N", os.path.basename(path).encode("utf-8"))
        with open(path, "rb") as f:
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

def handle_control_client(client, q=1, h264=False):
    maxw, fps, _ = QUALITY[q]
    if maxw == 0: maxw = 1 << 16
    lock = threading.Lock()
    try:
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 524288)  # BDP ของ ZeroTier สูง buffer ส่งเล็กเกินทำให้ความเร็วตก (ใหญ่เกินจะหน่วง)
        grab = make_grabber()
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
            except Exception as e:  # encoder ใช้ไม่ได้ (ไม่มี libx264) -> สาย TCP อาจเสียแล้ว ปิดแล้วให้ฝั่งดูต่อใหม่ (ได้ JPEG)
                log_err(e)
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
        try: client.close()
        except Exception: pass

def apply_input_loop(client, gone, lock, files_only=False):
    fh, rem, fp = None, 0, None
    cancel = threading.Event()
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
START = time.time()

def notify(msg, bad=False):
    log_err(msg) if bad else None
    def f():
        if STATUS[0]:
            STATUS[0].config(text=msg, fg=("#ff5252" if bad else "#2ecc71") if ADMIN[0] else ("#c62828" if bad else "#1b7f3b"))
    if ROOT[0]:
        ROOT[0].after(0, f)

def open_viewer(ips, q=1, auto=None, files_only=False, host=None, on_close=None):  # auto: None ปกติ, "send"/"pull" = เปิดแล้วเด้งกล่องส่ง/ดึงไฟล์ให้เลย (โหมดแอดมิน)
    def bad(msg):
        notify(msg, True)
        if on_close: ROOT[0].after(0, lambda: on_close(msg))
    sock, fail = None, ""
    for ip in ips:
        notify(f"กำลังเชื่อมต่อ {ip} ...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)  # ต้องตั้งก่อน connect
        s.settimeout(5)
        try:
            s.connect((ip, CTRL_PORT))
            s.sendall(b"T" if files_only else b"V" + bytes([q]) + (b"H" if av is not None else b"-"))
            sock = s
            break
        except socket.timeout:
            fail = f"หมดเวลา: {ip} ไม่ตอบ (Firewall บล็อก / ZeroTier ยังไม่ต่อ / ปลายทางปิดอยู่)"
        except ConnectionRefusedError:
            fail = f"{ip} ปฏิเสธ: โปรแกรมปลายทางไม่ได้เปิด หรือเปิดพอร์ต {CTRL_PORT} ไม่ได้"
        except Exception as e:
            fail = f"เชื่อมต่อ {ip} ไม่ได้: {e}"
        s.close()
    if sock is None:
        bad(f"{fail} (ลอง {len(ips)} ที่อยู่)")
        return
    notify(f"รอปลายทาง {ip} กดอนุญาต (สูงสุด 60 วินาที) ...")
    try:
        sock.settimeout(60)
        hdr = recv_exact(sock, 8)
        sock.settimeout(None)
    except socket.timeout:
        bad(f"ปลายทาง {ip} ไม่กดอนุญาตภายใน 60 วินาที")
        sock.close()
        return
    except Exception as e:
        bad(f"การเชื่อมต่อ {ip} ขาด: {e}")
        return
    if not hdr:
        bad(f"ปลายทาง {ip} ไม่อนุญาตให้ควบคุม")
        sock.close()
        return
    rw = int.from_bytes(hdr[0:4], "little")
    rh = int.from_bytes(hdr[4:8], "little")
    notify(f"เชื่อมต่อ {ip} สำเร็จ")
    ROOT[0].after(0, lambda: viewer_window(sock, ip, rw, rh, QUALITY[q][2], q == 3, auto, files_only, host, on_close))

def viewer_window(sock, ip, remote_w, remote_h, qlabel="", sharp=False, auto=None, files_only=False, host=None, on_close=None):
    from PIL import ImageTk
    embedded = host is not None  # โหมดไฟล์ในแท็บของหน้าต่างหลัก (ไม่เปิดหน้าต่างแยก)
    bar_bg, bar_fg = (ecol("panel2"), ecol("ok")) if embedded else ("#2a0808", "#ff6b6b") if ADMIN[0] else ("#101a2e", "#3ddc84")
    if embedded:
        win = host
        for c_ in win.winfo_children(): c_.destroy()  # ล้างข้อความ "กำลังเชื่อมต่อ" ก่อนวางหน้าไฟล์
    else:
        win = tk.Toplevel(ROOT[0])
        win.title(f"ส่ง/ดึงไฟล์: {ip}" if files_only else f"ควบคุม: {ip}   (F11 = เต็มจอ)")
        win.geometry("760x96" if files_only else "1100x700")
    done = [False]
    def finish(msg=""):  # แท็บไฟล์: คืนสภาพเป็นหน้ารอเชื่อมต่อ (เรียกครั้งเดียว)
        if embedded and not done[0]:
            done[0] = True
            if on_close: on_close(msg)
    bar = tk.Frame(win, bg=bar_bg)
    bar.pack(fill="x")
    lbl_v = tk.Label(bar, text=(f"● ไฟล์ {ip}" if files_only else f"● เชื่อมต่อ {ip} • {qlabel}"), bg=bar_bg, fg=bar_fg, font=FNT(12 if embedded else 9, "bold"))
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
    xb = {"f": None}
    cancel_up = threading.Event()
    pull = {"q": [], "n": 0, "i": 0}
    br = {"fill": None}

    def ec(c):
        return {"#3ddc84": ecol("ok"), "#ff6b6b": ecol("bad"), "#2fa8ff": ecol("accent")}.get(c, c) if embedded else c

    def say(text, color="#3ddc84"):
        def f():
            try: lbl_v.config(text=text, fg=ec(color))
            except tk.TclError: pass
        win.after(0, f)

    def fmt_size(n):
        for u in ("B", "KB", "MB", "GB"):
            if n < 1024 or u == "GB": return f"{n:.0f} B" if u == "B" else f"{n:.1f} {u}"
            n /= 1024

    def xfer_ui(title, done, total, t0):  # ความคืบหน้า: แท็บไฟล์ = แถบด้านล่าง / โหมดดูจอ = หน้าต่างเล็ก (เรียกในเธรด Tk)
        if embedded and not (xf["w"] and xf["w"].winfo_exists()):
            w = tk.Frame(win, bg=ecol("panel2"))
            w.pack(side="bottom", fill="x", padx=10, pady=(0, 8), before=xb["f"])
            lbl = tk.Label(w, bg=ecol("panel2"), fg=ecol("text"), anchor="w"); lbl.pack(fill="x", padx=10, pady=(8, 2))
            bar = ttk.Progressbar(w, maximum=100); bar.pack(fill="x", padx=10)
            info = tk.Label(w, bg=ecol("panel2"), fg=ecol("sub"), anchor="w"); info.pack(side="left", padx=10, pady=(2, 8))
            ttk.Button(w, text="ยกเลิก", style="Ghost.TButton", command=xfer_cancel).pack(side="right", padx=10, pady=(0, 8))
            xf.update(w=w, lbl=lbl, bar=bar, info=info)
        elif not (xf["w"] and xf["w"].winfo_exists()):
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
        if files_only:  # ไม่มีภาพ ตรวจแค่ว่าการเชื่อมต่อยังอยู่
            if alive[0]: win.after(200, poll)
            elif embedded: finish("ตัดการเชื่อมต่อ")
            else:
                win.title(f"ตัดการเชื่อมต่อ: {ip}")
                lbl_v.config(text=f"● ตัดการเชื่อมต่อ {ip}", fg="#ff6b6b")
            return
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

    def open_browser(parent=None):  # เรียกดูไฟล์ในเครื่องปลายทาง (parent = วางในแท็บ ไม่เปิดหน้าต่างใหม่)
        b = parent if parent is not None else tk.Toplevel(win)
        cb, ca, cs = (ecol("panel"), ecol("accent"), ecol("sub")) if parent is not None else (tc("#101a2e"), tc("#2fa8ff"), tc("#8fa3c4"))
        if parent is None:
            b.title("เรียกดูไฟล์ในเครื่องปลายทาง"); b.geometry("700x500"); b.configure(bg=cb)
        cur = {"parent": None, "items": {}}
        top = tk.Frame(b, bg=cb); top.pack(fill="x", padx=10, pady=8)
        lbl = tk.Label(top, text="กำลังโหลด ...", bg=cb, fg=ca, anchor="w")
        def go(path):
            lbl.config(text="กำลังโหลด ...", fg=ca)
            pb = path.encode("utf-8")
            send(b"L", len(pb).to_bytes(2, "little"), pb)
        ttk.Button(top, text="↑ ขึ้นไป", style="Ghost.TButton", command=lambda: go(cur["parent"] or "")).pack(side="left")
        lbl.pack(side="left", padx=10, fill="x", expand=True)
        bot = tk.Frame(b, bg=cb); bot.pack(side="bottom", fill="x", padx=10, pady=8)
        mid = tk.Frame(b, bg=cb); mid.pack(fill="both", expand=True, padx=10)
        tree = ttk.Treeview(mid, columns=("size", "mod"), selectmode="extended")
        tree.heading("#0", text="ชื่อ"); tree.heading("size", text="ขนาด"); tree.heading("mod", text="แก้ไขล่าสุด")
        tree.column("#0", width=360); tree.column("size", width=90, anchor="e"); tree.column("mod", width=150, anchor="center")
        sb = ttk.Scrollbar(mid, orient="vertical", command=tree.yview); tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); tree.pack(side="left", fill="both", expand=True)

        def fill(info):
            if not b.winfo_exists(): return
            if info.get("error"):
                lbl.config(text=info["error"], fg=(ecol("bad") if parent is not None else "#ff6b6b"))
                return
            cur.update(parent=info["parent"], items={})
            lbl.config(text=info["path"] or "เครื่องนี้ (ไดรฟ์และโฟลเดอร์ผู้ใช้)", fg=ca)
            tree.delete(*tree.get_children())
            for i, it in enumerate(info["items"]):
                cur["items"][str(i)] = (it.get("p") or ntpath.join(info["path"], it["n"]), it["d"])
                tree.insert("", "end", iid=str(i), text=("▸ " if it["d"] else "") + it["n"],
                            values=("" if it["d"] else fmt_size(it["s"]), time.strftime("%Y-%m-%d %H:%M", time.localtime(it["m"])) if it["m"] else ""))

        def do_pull():
            files = [cur["items"][i][0] for i in tree.selection() if not cur["items"][i][1]]
            if not files:
                messagebox.showinfo("ดึงไฟล์", "เลือกไฟล์ก่อน (โฟลเดอร์ดึงไม่ได้ ดับเบิลคลิกเพื่อเปิดดู)", parent=b)
                return
            start_pull(files)

        def open_sel(e=None):
            sel = tree.selection()
            if len(sel) == 1 and cur["items"][sel[0]][1]: go(cur["items"][sel[0]][0])
            elif sel: do_pull()

        def close_b():
            br["fill"] = None
            b.destroy()
        ttk.Button(bot, text="ดึงไฟล์ที่เลือก", style="Accent.TButton", command=do_pull).pack(side="right")
        if parent is None: ttk.Button(bot, text="ปิด", style="Ghost.TButton", command=close_b).pack(side="right", padx=8)
        else: ttk.Button(bot, text="ส่งไฟล์ไปเครื่องนั้น", style="Ghost.TButton", command=pick_send).pack(side="right", padx=8)
        hint_txt = "ดับเบิลคลิกโฟลเดอร์เพื่อเปิด / เลือกหลายไฟล์ได้ (Ctrl, Shift) / ไฟล์ไปอยู่บนเดสก์ท็อปเครื่องนี้"
        if parent is None: tk.Label(bot, text=hint_txt, bg=cb, fg=cs).pack(side="left")
        else: tk.Label(b, text=hint_txt, bg=cb, fg=cs, anchor="w").pack(side="bottom", fill="x", padx=10, before=bot)
        tree.bind("<Double-1>", open_sel)
        if parent is None: b.protocol("WM_DELETE_WINDOW", close_b)
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
    if not embedded: win.bind("<F11>", toggle_fs)
    if not files_only:
        win.bind("<KeyPress>", lambda e: on_key(e, False))
        win.bind("<KeyRelease>", lambda e: on_key(e, True))

    def close():
        alive[0] = False
        try: sock.close()
        except Exception: pass
        if embedded: finish("")
        else: win.destroy()
    if embedded: host.close_session = close
    else: win.protocol("WM_DELETE_WINDOW", close)
    def vbtn(text, cmd):
        tk.Button(bar, text=text, command=lambda: (cmd(), canvas.focus_set()),
                  bg=ecol("panel") if embedded else tc("#16233d"), fg=ecol("text") if embedded else tc("#e7f0ff"),
                  activebackground=ecol("panel2") if embedded else tc("#20314f"), activeforeground="#ffffff" if not embedded else ecol("text"),
                  relief="flat", padx=14 if embedded else 10, pady=6 if embedded else 2, font=FNT(12 if embedded else 9)).pack(side="right", padx=4, pady=4)
    vbtn("ตัดการเชื่อมต่อ", close)
    if not files_only: vbtn("เต็มจอ (F11)", toggle_fs)
    if not embedded:
        vbtn("ดึงไฟล์มา", open_browser)
        vbtn("ส่งไฟล์ไปเครื่องนั้น", pick_send)
    else:
        xb["f"] = tk.Frame(win, bg=ecol("panel"))
        xb["f"].pack(fill="both", expand=True)
        open_browser(xb["f"])
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
    elif auto == "pull" and not embedded: win.after(300, open_browser)
    poll()

# ---------- GUI ----------
def main():
    threading.Thread(target=listener, daemon=True).start()
    threading.Thread(target=broadcaster, daemon=True).start()
    threading.Thread(target=control_server, daemon=True).start()
    threading.Thread(target=zt_poll, daemon=True).start()
    threading.Thread(target=ensure_firewall, daemon=True).start()

    if not cfg.get("zt_network_id"):
        cfg["zt_network_id"] = DEFAULT_ZT_NETWORK_ID
        save_config(cfg)
    if cfg.get("zt_network_id"):
        threading.Thread(target=ensure_zerotier, args=(cfg["zt_network_id"],), daemon=True).start()

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
    root.minsize(900, 560)
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
        style.configure("Ghost.TButton", background=c(PANEL2), foreground=c(TEXT), font=FNT(12), padding=10, borderwidth=0)
        style.map("Ghost.TButton", background=[("active", c("#20314f"))])
        style.configure("Treeview", background=c(PANEL2), fieldbackground=c(PANEL2), foreground=c(TEXT), rowheight=int(S(46) * SCALE[0]), borderwidth=0, font=FNT(12))
        style.configure("Treeview.Heading", background=c(PANEL), foreground=c(ACCENT), font=FNT(12, "bold"), borderwidth=0)
        style.map("Treeview", background=[("selected", c(ACCENT2))], foreground=[("selected", "#ffffff")])
    apply_styles(False)

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
    body.columnconfigure(0, weight=2, minsize=S(400))
    body.columnconfigure(1, weight=3)
    body.rowconfigure(0, weight=1)

    left = tk.Frame(body, bg=PANEL, highlightbackground="#223354", highlightthickness=1)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    right = tk.Frame(body, bg=PANEL, highlightbackground="#223354", highlightthickness=1)
    right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    def toggle_settings():
        if left.winfo_ismapped():
            left.grid_remove()
            right.grid(row=0, column=0, columnspan=2, padx=0)
        else:
            left.grid()
            right.grid(row=0, column=1, columnspan=1, padx=(8, 0))
    ttk.Button(header, text="ตั้งค่า", style="Ghost.TButton", command=toggle_settings).pack(side="right")
    left.grid_remove()
    right.grid(row=0, column=0, columnspan=2, padx=0)

    ttk.Label(left, text="ผู้ใช้งานเครื่องนี้", style="Section.TLabel").pack(anchor="w", padx=16, pady=(14, 6))
    active_card = tk.Frame(left, bg=PANEL2, highlightbackground="#2a3c5e", highlightthickness=1)
    active_card.pack(fill="x", padx=16)
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
                messagebox.showwarning("เลือกผู้ใช้งาน", "เลือกให้ครบทั้งตำแหน่งและหน่วย", parent=root)
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

    def ask_quality(who, go):
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
        def ok():
            q = v.get(); cfg["quality"] = q; save_config(cfg); w.destroy(); go(q)
        row = tk.Frame(w, bg=PANEL); row.pack(fill="x", padx=20, pady=16)
        ttk.Button(row, text="เชื่อมต่อ", style="Accent.TButton", command=ok).pack(side="right")
        ttk.Button(row, text="ยกเลิก", style="Ghost.TButton", command=w.destroy).pack(side="right", padx=8)
        if ADMIN[0]: recolor_widget(w)
        w.transient(root); w.grab_set()

    def ask_link(err):
        v = simpledialog.askstring("ลิงก์อัปเดต", f"ดึงจากลิงก์เดิมไม่ได้\n({err})\n\nวางลิงก์ดาวน์โหลดตรงของไฟล์ ZaiaRemote.py ที่ต้องการใช้แทน", parent=root)
        if v and v.strip():
            cfg["update_url"] = v.strip()
            save_config(cfg)
            do_update()

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
            zt_note = f"\nเปลี่ยนเครือข่าย ZeroTier เป็น {m['zt_network_id']}" if m and m.get("zt_network_id") and m["zt_network_id"] != cfg.get("zt_applied") else ""
            def ask():
                if not messagebox.askyesno("อัปเดต", f"มีรุ่นใหม่ v{v} (ตอนนี้ v{APP_VER})\nไฟล์ที่จะเปลี่ยน: {', '.join(what) or '-'}{zt_note}\nอัปเดตและเปิดโปรแกรมใหม่ไหม"):
                    return
                def go():
                    try:
                        notify("กำลังดาวน์โหลดรุ่นใหม่ ...")
                        apply_staged(m or {}, staged if staged is not None else stage_update(m))
                    except Exception as e:
                        log_err(e)
                        notify(f"อัปเดตไม่สำเร็จ: {e} (ลองเปิดแบบ admin)", True)
                threading.Thread(target=go, daemon=True).start()
            root.after(0, ask)
        threading.Thread(target=work, daemon=True).start()

    urow = tk.Frame(left, bg=PANEL)
    urow.pack(anchor="w", padx=16, pady=10)
    urow2 = tk.Frame(left, bg=PANEL)  # แถวที่สอง: ปุ่มของโหมดแอดมิน (แถวแรกกว้างพอแค่ 2 ปุ่ม ปุ่มที่สามโดนตัด)
    urow2.pack(anchor="w", padx=16)
    ttk.Button(urow, text="เปลี่ยนข้อมูล", style="Ghost.TButton", command=lambda: ask_user(False)).pack(side="left")
    ttk.Button(urow, text="ตรวจหารุ่นใหม่", style="Ghost.TButton", command=do_update).pack(side="left", padx=6)
    root.after(8000, lambda: do_update(True))

    def gap():  # ตัวคั่นยืดได้ + เส้นแบ่ง: แบ่งพื้นที่ว่างฝั่งซ้ายให้เท่ากันระหว่างหัวข้อ
        f_ = tk.Frame(left, bg=PANEL); f_.pack(fill="both", expand=True)
        tk.Frame(f_, bg="#223354", height=1).place(relx=0.04, rely=0.5, relwidth=0.92)
    gap()
    ttk.Label(left, text="การเชื่อมต่อเครือข่าย (ZeroTier)", style="Section.TLabel").pack(anchor="w", padx=16, pady=(14, 6))
    lbl_zt = tk.Label(left, text=f"Network ID: {cfg.get('zt_network_id','') or 'ยังไม่ตั้งค่า'}", bg=PANEL, fg=SUBTEXT, justify="left", anchor="w")
    lbl_zt.pack(fill="x", padx=16)
    def change_zt():
        v = simpledialog.askstring("ZeroTier", "ใส่ ZeroTier Network ID", initialvalue=cfg.get("zt_network_id",""))
        if v:
            cfg["zt_network_id"] = v
            save_config(cfg)
            lbl_zt.config(text=f"Network ID: {v}")
            threading.Thread(target=ensure_zerotier, args=(v,), daemon=True).start()
    def rejoin():
        notify("กำลังเชื่อมต่อ ZeroTier ใหม่ ...")
        threading.Thread(target=ensure_zerotier, args=(cfg.get("zt_network_id", ""),), daemon=True).start()
    def copy_node():
        if ZT["node"]:
            root.clipboard_clear()
            root.clipboard_append(ZT["node"])
            notify("คัดลอก Node ID แล้ว")
    lbl_ztst = tk.Label(left, text="", bg=PANEL, fg=SUBTEXT, justify="left", anchor="w", wraplength=S(320))
    lbl_ztst.pack(fill="x", padx=16, pady=(4, 0))
    nrow = tk.Frame(left, bg=PANEL)
    nrow.pack(fill="x", padx=16)
    lbl_node = tk.Label(nrow, text="", bg=PANEL, fg=SUBTEXT, anchor="w")
    lbl_node.pack(side="left")
    ttk.Button(nrow, text="คัดลอก", style="Ghost.TButton", command=copy_node).pack(side="left", padx=8)
    zrow = tk.Frame(left, bg=PANEL)
    zrow.pack(fill="x", padx=16, pady=10)
    ttk.Button(zrow, text="ตั้งค่า Network ID", style="Ghost.TButton", command=change_zt).pack(side="left")
    ttk.Button(zrow, text="เชื่อมต่อใหม่", style="Ghost.TButton", command=rejoin).pack(side="left", padx=6)

    gap()
    ttk.Label(left, text="โหมดเซิร์ฟเวอร์", style="Section.TLabel").pack(anchor="w", padx=16, pady=(10, 6))
    auto_var = tk.BooleanVar(value=bool(cfg.get("auto_allow", False)))
    def toggle_auto():
        if auto_var.get() and not messagebox.askyesno("อนุญาตอัตโนมัติ", "ทุกเครื่องในเครือข่าย ZeroTier จะควบคุมจอเครื่องนี้ได้ทันที โดยไม่ถามก่อน\nเปิดโหมดนี้ไหม", icon="warning"):
            auto_var.set(False)
        cfg["auto_allow"] = auto_var.get()
        save_config(cfg)
    tk.Checkbutton(left, text="อนุญาตเชื่อมต่ออัตโนมัติ (ไม่มีคนนั่งหน้าเครื่อง)", variable=auto_var, command=toggle_auto,
                   bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL, activeforeground=TEXT,
                   anchor="w", justify="left", wraplength=S(320)).pack(fill="x", padx=16, pady=(0, 14))

    tabbar = tk.Frame(right, bg=PANEL)  # แท็บ รายการเครื่อง / ไฟล์ : แสดงเฉพาะโหมดแอดมิน
    page_list = tk.Frame(right, bg=PANEL)
    page_list.pack(fill="both", expand=True)
    page_files = tk.Frame(right, bg=PANEL)
    files_body = tk.Frame(page_files, bg=PANEL)
    files_body.pack(fill="both", expand=True)
    files_state = {"tok": None}
    tab_btns = {}
    def show_page(name):
        page_list.pack_forget(); page_files.pack_forget()
        (page_list if name == "list" else page_files).pack(fill="both", expand=True)
        for k, b_ in tab_btns.items(): b_.config(style="Accent.TButton" if k == name else "Ghost.TButton")
    tab_btns["list"] = ttk.Button(tabbar, text="รายการเครื่อง", style="Accent.TButton", command=lambda: show_page("list"))
    tab_btns["files"] = ttk.Button(tabbar, text="ไฟล์ (ไม่ดูจอ)", style="Ghost.TButton", command=lambda: show_page("files"))
    tab_btns["list"].pack(side="left"); tab_btns["files"].pack(side="left", padx=6)

    rhead = tk.Frame(page_list, bg=PANEL)
    rhead.pack(fill="x", padx=16, pady=(14, 6))
    lbl_peers = ttk.Label(rhead, text="เครื่องที่เปิดใช้งานอยู่", style="Section.TLabel")
    lbl_peers.pack(side="left")
    ttk.Button(rhead, text="รีเฟรชรายชื่อ", style="Ghost.TButton", command=lambda: refresh_now()).pack(side="right")
    ttk.Button(rhead, text="ต่อไม่ได้? กดตรงนี้", style="Ghost.TButton", command=lambda: diag()).pack(side="right", padx=6)

    ttk.Label(page_list, text="ดับเบิลคลิกชื่อเครื่อง หรือคลิกเลือกแล้วกดปุ่มสีเขียวด้านล่าง", style="Sub.TLabel", background=PANEL).pack(anchor="w", padx=16, pady=(0, 6))

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
        with peers_lock:
            ips = [ip] + sorted(peers.get(uid, {}).get("ips", set()) - {ip})
        who = str(tree.item(uid)["values"][1])
        ask_quality(who, lambda q: threading.Thread(target=open_viewer, args=(ips, q), daemon=True).start())
    lbl_status = tk.Label(page_list, text="พร้อมใช้งาน", bg=PANEL, fg=SUBTEXT, anchor="w", justify="left", wraplength=S(340))
    lbl_status.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
    STATUS[0] = lbl_status
    def connect_ip():
        v = simpledialog.askstring("เชื่อมต่อด้วย IP", "ใส่ IP ของเครื่องปลายทาง (IP ZeroTier)")
        if v and v.strip():
            ask_quality(v.strip(), lambda q: threading.Thread(target=open_viewer, args=([v.strip()], q), daemon=True).start())
    crow = tk.Frame(page_list, bg=PANEL)
    crow.pack(side="bottom", fill="x", padx=16, pady=12)
    ttk.Button(crow, text="ดูจอเครื่องที่เลือก", style="Go.TButton", command=do_connect).pack(side="left")
    ttk.Button(crow, text="ต่อด้วยเลข IP", style="Ghost.TButton", command=connect_ip).pack(side="left", padx=8)

    cols = ("host", "user", "status", "ip", "ver")
    tree = ttk.Treeview(page_list, columns=cols, show="headings")
    for c in cols:
        tree.heading(c, text={"host":"เครื่อง","user":"ผู้ใช้","status":"สถานะ","ip":"IP","ver":"รุ่น"}[c])
        tree.column(c, width=S(200), minwidth=S(80), anchor="w" if c in ("host", "user") else "center", stretch=(c in ("host", "user")))
    def fit_cols():  # คอลัมน์ตัวเลขกว้างตามฟอนต์จริง (เดิมกว้างคงที่ พอฟอนต์ขยายแล้วโดนตัด)
        f = FNT(12, "bold")
        for c_, sample in (("status", "รุ่นเก่า"), ("ip", "255.255.255.255"), ("ver", "10.10.10")):
            w_ = f.measure(sample) + S(36)
            tree.column(c_, width=w_, minwidth=w_, stretch=False)
    fit_cols()
    tree.pack(fill="both", expand=True, padx=16)
    tree.tag_configure("dup", foreground="#b36200")
    tree.tag_configure("ok", foreground=OK_C)
    tree.tag_configure("me", foreground=ACCENT)
    tree.bind("<Double-1>", lambda e: do_connect())

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
        tree.delete(*tree.get_children())
        for k in sorted(all_m, key=lambda x: (all_m[x]["host"].lower(), x)):
            v = all_m[k]
            old = is_old(v["ver"])
            tag = "me" if k == MY_ID else "dup" if old else "ok"
            who = f"(รุ่นเก่า รหัส {v['code']})" if old else v["code"]
            tree.insert("", "end", iid=k, values=(v["host"], who, "รุ่นเก่า" if old else "ปกติ", v["ip"], v["ver"]), tags=(tag,))

        keep = [i for i in old_sel if tree.exists(i)]
        if keep:
            tree.selection_set(keep)
        lbl_peers.config(text=f"เครื่องที่เปิดใช้งานอยู่ ({len(all_m)})")
        lbl_ztst.config(text=ZT["msg"], fg=OK_C if ZT["ok"] else DUP_C)
        lbl_node.config(text=f"Node ID: {ZT['node'] or '-'}")
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
            L[:] = [f"โปรแกรม v{APP_VER}   สิทธิ์ admin: {'ใช่' if is_admin() else 'ไม่ใช่ (ใช้ได้ ถ้า ZeroTier ปลดสิทธิ์ไฟล์แล้ว)'}"]
            good = lambda t: L.append("✔ " + t)
            bad = lambda t: L.append("✘ " + t)
            try: zt_update()
            except Exception as e: log_err(e)
            if not zt_cli():
                bad("ไม่พบ ZeroTier → ติดตั้งโปรแกรมใหม่ด้วยตัวติดตั้ง")
            elif not ZT["node"]:
                bad("ZeroTier ใช้ไม่ได้: " + ZT["msg"])
            else:
                (good if ZT["ok"] else bad)("ZeroTier: " + ZT["msg"])
                leaf = [l for l in (zt_run("peers") or "").splitlines() if " LEAF " in l]
                if leaf:
                    good(f"เห็นเครื่อง ZeroTier อื่น {len(leaf)} เครื่อง")
                    nd = len([l for l in leaf if " DIRECT " in l])
                    (good if nd else bad)(f"เส้นทางตรง (DIRECT) {nd}/{len(leaf)} เครื่อง" + ("" if nd else " → ตอนนี้อ้อมผ่านเซิร์ฟเวอร์ ภาพจะช้า/กระตุก เช็ก NAT/Firewall ของ router"))
                else: bad("ไม่เห็นเครื่อง ZeroTier อื่นเลย → อีกเครื่องปิดอยู่ / ZeroTier ไม่ทำงาน / ยังไม่ติ๊ก Auth ใน Central")
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
        zt_wake.set()
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
        if not ADMIN[0]:  # ปิด god: ตัดเซสชันไฟล์และกลับหน้ารายการ (เดิมหน้าต่างไฟล์ค้างอยู่)
            files_state["tok"] = None
            step(files_stop)
            step(lambda: show_page("list"))
        for w, kw in admin_only.items():  # ปุ่มก่อนเสมอ
            step(lambda w=w, kw=kw: w.pack(**kw) if ADMIN[0] else w.pack_forget())
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
    btn_admin_name = ttk.Button(urow2, text="ตั้งชื่อแอดมิน", style="Ghost.TButton", command=set_admin_name)
    admin_only[btn_admin_name] = {"side": "left"}

    def files_idle(msg=""):  # หน้ารอเชื่อมต่อของแท็บไฟล์
        for c_ in files_body.winfo_children(): c_.destroy()
        tk.Label(files_body, text="ส่ง/ดึงไฟล์ (ไม่ดูจอ)", bg=ecol("panel"), fg=ecol("accent"), font=FNT(16, "bold")).pack(anchor="w", padx=20, pady=(20, 4))
        tk.Label(files_body, text="เลือกเครื่องในแท็บ 'รายการเครื่อง' แล้วกดปุ่มด้านล่าง ปลายทางต้องกดอนุญาตก่อน", bg=ecol("panel"), fg=ecol("sub"), font=FNT(12),
                 justify="left", anchor="w", wraplength=S(520)).pack(anchor="w", padx=20)
        if msg: tk.Label(files_body, text=msg, bg=ecol("panel"), fg=ecol("bad"), font=FNT(12), justify="left", anchor="w", wraplength=S(520)).pack(anchor="w", padx=20, pady=(10, 0))
        ttk.Button(files_body, text="เชื่อมต่อเครื่องที่เลือก", style="Go.TButton", command=lambda: files_open()).pack(anchor="w", padx=20, pady=16)

    def files_stop():  # ปิดเซสชันไฟล์ที่ค้างอยู่ (ถ้ามี)
        fn = getattr(files_body, "close_session", None)
        files_body.close_session = None
        if fn:
            try: fn()
            except Exception as e: log_err(e)

    def files_open(auto=None):  # เซสชันไฟล์ในแท็บ ยังต้องรอปลายทางกดอนุญาตเหมือนเดิมทุกครั้ง
        sel_item = tree.selection()
        if not sel_item:
            show_page("list")
            notify("คลิกเลือกเครื่องในรายการก่อน", True)
            return
        uid = sel_item[0]
        if uid == MY_ID:
            show_page("list")
            notify("เลือกเครื่องอื่น ไม่ใช่เครื่องตัวเอง", True)
            return
        ip = str(tree.item(uid)["values"][3])
        who = str(tree.item(uid)["values"][1])
        with peers_lock:
            ips = [ip] + sorted(peers.get(uid, {}).get("ips", set()) - {ip})
        files_stop()
        tok = object()
        files_state["tok"] = tok
        def on_close(msg="", tok=tok):
            if files_state["tok"] is tok: files_idle(msg)
        for c_ in files_body.winfo_children(): c_.destroy()
        tk.Label(files_body, text=f"กำลังเชื่อมต่อ {who} ({ip}) ... รอปลายทางกดอนุญาต (สูงสุด 60 วินาที)", bg=ecol("panel"), fg=ecol("accent"), font=FNT(13),
                 justify="left", anchor="w", wraplength=S(520)).pack(anchor="w", padx=20, pady=20)
        show_page("files")
        threading.Thread(target=open_viewer, args=(ips, 1, auto, True, files_body, on_close), daemon=True).start()
    files_idle()
    btn_qfiles = ttk.Button(crow, text="ส่ง/ดึงไฟล์ (ไม่ดูจอ)", style="Ghost.TButton", command=lambda: files_open())
    admin_only[btn_qfiles] = {"side": "left", "padx": 8}
    admin_only[tabbar] = {"fill": "x", "padx": 16, "pady": (10, 0), "before": page_list}

    def fit_wrap(e=None):
        try:
            lw, rw_ = max(left.winfo_width() - S(60), S(180)), max(right.winfo_width() - S(60), S(180))
            lbl_active.config(wraplength=lw); lbl_ztst.config(wraplength=lw); lbl_status.config(wraplength=rw_)
        except Exception as ex:
            log_err(ex)
    left.bind("<Configure>", fit_wrap, add="+"); right.bind("<Configure>", fit_wrap, add="+")
    _rs = [None]
    def do_rescale():
        f = max(0.85, min(1.3, min(root.winfo_width() / 1280, root.winfo_height() / 720)))
        if abs(f - SCALE[0]) < 0.04: return
        rescale_fonts(f)
        style.configure("Treeview", rowheight=int(S(46) * f))
        fit_cols()
    def on_resize(e):
        if e.widget is not root: return
        if _rs[0]: root.after_cancel(_rs[0])
        _rs[0] = root.after(250, do_rescale)
    root.bind("<Configure>", on_resize, add="+")
    root.after(400, do_rescale)

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
