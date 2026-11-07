# -*- coding: utf-8 -*-
import sys, os, json, socket, threading, time, io, ctypes, subprocess, winreg, re, ipaddress, uuid, urllib.request, zlib, queue, hashlib
import tkinter as tk
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
APP_VER = "1.10.0"
SETUP_REV = 1  # เลขรุ่นของตัวติดตั้ง/ไลบรารีใน python\ ถ้า update.json ระบุ setup_rev สูงกว่านี้ ต้องลงด้วยตัวติดตั้งใหม่
UPDATE_URL = "https://raw.githubusercontent.com/Minos117/ZaiaRemote.py/refs/heads/main/ZaiaRemote.py"  # ต้องเป็นลิงก์ดาวน์โหลดตรง (repo public)
DEFAULT_ZT_NETWORK_ID = "b103a835d26ef7ce"
PORT = 47101
JPEG_Q = 60
JPEG_MIN, JPEG_MAX = 35, 82  # ปรับคุณภาพ JPEG อัตโนมัติตามความเร็วเน็ต
QUALITY = [(1280, 30, "720p 30fps"), (1920, 30, "1080p 30fps"), (1920, 60, "1080p 60fps")]  # (กว้างสูงสุด, fps, ชื่อ)
CTRL_PORT = 47102
APPDIR = os.path.join(os.environ["APPDATA"], "ZaiaRemote")
CONFIG_PATH = os.path.join(APPDIR, "config.json")
ERRLOG = os.path.join(APPDIR, "error.log")
os.makedirs(APPDIR, exist_ok=True)
SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
ICON_PATH = os.path.join(SCRIPT_DIR, "zaia.ico")
LOGO_PATH = os.path.join(SCRIPT_DIR, "zaia_logo.png")

ROLES = ["สัสดีจังหวัด", "สัสดีอำเภอ", "เสมียนจังหวัด", "เสมียนหน่วยสัสดี"]
UNITS = ["สกลนคร", "เมืองสกลนคร", "บ้านม่วง", "คำตากล้า", "วานรนิวาส", "กุสุมาลย์", "กุดบาก",
         "ส่องดาว", "เจริญศิลป์", "วาริชภูมิ", "สว่างแดนดิน", "โพนนาแก้ว", "ภูพาน",
         "พังโคน", "พรรณานิคม", "อากาศอำนวย", "เต่างอย", "โคกศรีสุพรรณ", "นิคมน้ำอูน", "จังหวัดอื่นๆ"]

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

def username():
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
            ans = 6 if cfg.get("auto_allow") else ctypes.windll.user32.MessageBoxW(0, (peer_name(addr[0]) + "\n" if peer_name(addr[0]) else "") + f"IP {addr[0]}\n\nขอเข้ามาดูและควบคุมจอเครื่องนี้ อนุญาตไหม\n(ถ้าไม่รู้จัก ให้กดไม่อนุญาต)", "มีคนขอเข้ามาช่วยดูจอ", 0x04 | 0x20 | 0x100 | 0x40000)
            if ans != 6:  # IDYES
                client.close()
                continue
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

def send_file_to_client(client, lock, path):  # แพ็กเก็ตไฟล์ = ความยาว|0x80000000 แล้วตามด้วย N ชื่อ / D ข้อมูล / E จบ / X ข้อผิดพลาด
    def pkt(t, d=b""):
        p = t + d
        with lock:
            client.sendall((len(p) | 0x80000000).to_bytes(4, "little") + p)
    try:
        if not os.path.isfile(path):
            pkt(b"X", f"ไม่พบไฟล์บนเครื่องปลายทาง: {path}".encode("utf-8"))
            return
        pkt(b"N", os.path.basename(path).encode("utf-8"))
        with open(path, "rb") as f:
            while True:
                b = f.read(65536)
                if not b: break
                pkt(b"D", b)
        pkt(b"E")
    except Exception as e:
        log_err(e)
        try: pkt(b"X", f"ส่งไฟล์ไม่สำเร็จ: {e}".encode("utf-8"))
        except Exception: pass

# (สเกลภาพ, บิตเรต kbps) เรียงจากดีสุดไปประหยัดสุด ขยับทีละขั้น ไม่เกินทุก 1.5 วินาที (ทุกครั้งที่ขยับ encoder ถูกสร้างใหม่ = มีเฟรมเต็มหนึ่งเฟรม)
LEVELS = [(1.0, 12000), (1.0, 8000), (1.0, 5000), (0.75, 3500), (0.75, 2500), (0.5, 1800), (0.5, 1000)]

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

def stream_h264(client, grab, gone, lock, maxw, fps):
    from fractions import Fraction
    raw = getattr(grab, "raw", None)
    enc, size, n = None, None, 0
    lv = 1  # เริ่มที่ 8 Mbps แล้วค่อยขยับขึ้นเมื่อเน็ตไหว ไม่เริ่มสุดแล้วค้าง
    ema_enc = ema_send = 0.0
    up_wait, t_change, t_bad, t_up = 6.0, 0.0, time.time(), 0.0
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
        t_cap = time.time()
        scl, br = LEVELS[lv]
        mw = max(min(int(maxw * scl), sz[0]) // 2 * 2, 320)
        mh = max(sz[1] * mw // sz[0] // 2 * 2, 240)
        if enc is None or size != (mw, mh):
            enc = av.CodecContext.create("libx264", "w")
            enc.width, enc.height, enc.pix_fmt = mw, mh, "yuv420p"
            enc.framerate, enc.time_base = fps, Fraction(1, fps)
            # intra-refresh: ไม่มีเฟรมเต็ม (I-frame) ก้อนใหญ่ทุก 2 วินาที ที่ทำให้ภาพสะดุดบนเน็ตช้า / vbv-bufsize เล็ก = ขนาดแต่ละเฟรมไม่พุ่ง
            enc.options = {"preset": "ultrafast", "tune": "zerolatency", "bf": "0",
                           "x264-params": f"crf=23:keyint={fps * 2}:intra-refresh=1:vbv-maxrate={br}:vbv-bufsize={max(br // fps * 3, 200)}"}
            enc.open()
            size = (mw, mh)
        vf = bgra_to_vf(sz, b) if raw else av.VideoFrame.from_image(im.convert("RGB"))
        vf = vf.reformat(width=mw, height=mh, format="yuv420p")
        vf.pts = n; n += 1
        pks = [bytes(pk) for pk in enc.encode(vf)]
        t_enc = time.time()
        for d in pks:
            with lock:  # ส่งตรง ไม่ทิ้งเฟรม (P-frame ทิ้งไม่ได้) เน็ตช้า TCP จะชะลอรอบจับภาพเอง
                client.sendall((len(d) | 0x40000000).to_bytes(4, "little") + d)
        t_end = time.time()
        ema_enc = ema_enc * 0.8 + (t_enc - t_cap) * 0.2    # CPU: แปลง+เข้ารหัส (ไม่รวมเวลาจับภาพ)
        ema_send = ema_send * 0.8 + (t_end - t_enc) * 0.2  # เน็ต: เวลาที่ sendall ค้างรอเพราะส่งไม่ทัน
        good = ema_send < iv * 0.3 and ema_enc < iv * 0.6
        if not good: t_bad = t_end
        if t_end - t_change > 1.5:
            if (ema_send > iv * 0.9 or ema_enc > iv * 1.2) and lv < len(LEVELS) - 1:
                if t_end - t_up < 20: up_wait = min(up_wait * 2, 60)  # เพิ่งขยับขึ้นแล้วตกลงมาอีก -> รอนานขึ้นก่อนลองใหม่ กันภาพแกว่ง
                lv += 1; enc = None; t_change = t_bad = t_end
            elif good and lv > 0 and t_end - t_bad > up_wait:
                lv -= 1; enc = None; t_change = t_bad = t_up = t_end
        nxt += iv  # นับจังหวะแบบสะสม ไม่ใช่ sleep เท่ากันทุกรอบ (กันเฟรมเรตค่อย ๆ เพี้ยน)
        now = time.time()
        if nxt > now: time.sleep(nxt - now)
        elif now - nxt > iv: nxt = now

def handle_control_client(client, q=1, h264=False):
    maxw, fps, _ = QUALITY[q]
    lock = threading.Lock()
    try:
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 524288)  # BDP ของ ZeroTier สูง buffer ส่งเล็กเกินทำให้ความเร็วตก (ใหญ่เกินจะหน่วง)
        grab = make_grabber()
        w, h = grab().size
        client.sendall(w.to_bytes(4, "little") + h.to_bytes(4, "little"))
        gone = threading.Event()
        threading.Thread(target=apply_input_loop, args=(client, gone, lock), daemon=True).start()
        if h264:
            try:
                stream_h264(client, grab, gone, lock, maxw, fps)
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
        prev, prev_sig, qual, scl, iv = None, None, JPEG_Q, 1.0, 1 / fps
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
            s_t = st["send"]  # ส่งช้ากว่าเฟรมเรต -> ลดคุณภาพก่อน แล้วลดขนาด / ส่งเร็ว -> คืนขนาดก่อน แล้วเพิ่มคุณภาพ
            if s_t > iv * 1.3:
                if qual > JPEG_MIN: qual = max(JPEG_MIN, qual - 7)
                elif scl > 0.5: scl = max(0.5, scl - 0.15)
            elif s_t < iv * 0.5:
                if scl < 1.0: scl = min(1.0, scl + 0.05)
                elif qual < JPEG_MAX: qual = min(JPEG_MAX, qual + 2)
            dt = time.time() - t0
            if dt < iv:
                time.sleep(iv - dt)
    except Exception as e:
        log_err(e)
    finally:
        try: client.close()
        except Exception: pass

def apply_input_loop(client, gone, lock):
    fh, rem = None, 0
    try:
        while True:
            t = recv_exact(client, 1)
            if not t: break
            t = t.decode("latin1")
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
                fh = open(unique_path(name), "wb")
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
                threading.Thread(target=send_file_to_client, args=(client, lock, path), daemon=True).start()
    except Exception as e:
        log_err(e)
    finally:
        if fh: fh.close()
        gone.set()

# ---------- viewer (client side) ----------
ROOT = [None]
STATUS = [None]
START = time.time()

def notify(msg, bad=False):
    log_err(msg) if bad else None
    def f():
        if STATUS[0]:
            STATUS[0].config(text=msg, fg="#c62828" if bad else "#1b7f3b")
    if ROOT[0]:
        ROOT[0].after(0, f)

def open_viewer(ips, q=1):
    sock, fail = None, ""
    for ip in ips:
        notify(f"กำลังเชื่อมต่อ {ip} ...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)  # ต้องตั้งก่อน connect
        s.settimeout(5)
        try:
            s.connect((ip, CTRL_PORT))
            s.sendall(b"V" + bytes([q]) + (b"H" if av is not None else b"-"))
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
    ROOT[0].after(0, lambda: viewer_window(sock, ip, rw, rh, QUALITY[q][2]))

def viewer_window(sock, ip, remote_w, remote_h, qlabel=""):
    from PIL import ImageTk
    win = tk.Toplevel(ROOT[0])
    win.title(f"ควบคุม: {ip}   (F11 = เต็มจอ)")
    win.geometry("1100x700")
    bar = tk.Frame(win, bg="#101a2e")
    bar.pack(fill="x")
    lbl_v = tk.Label(bar, text=f"● เชื่อมต่อ {ip} • {qlabel}", bg="#101a2e", fg="#3ddc84", font=("Segoe UI", 9, "bold"))
    lbl_v.pack(side="left", padx=10, pady=4)
    canvas = tk.Canvas(win, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    latest = {"d": None}
    g = {"ox": 0, "oy": 0, "dw": 1, "dh": 1, "item": None, "photo": None}
    alive = [True]
    fs = [False]

    rf = {"fh": None, "path": ""}
    slock = threading.Lock()

    def say(text, color="#3ddc84"):
        win.after(0, lambda: lbl_v.config(text=text, fg=color))

    def on_file_packet(p):
        t, d = p[:1], p[1:]
        if t == b"N":
            if rf["fh"]: rf["fh"].close()
            rf["path"] = unique_path(d.decode("utf-8", "replace"))
            rf["fh"] = open(rf["path"], "wb")
        elif t == b"D" and rf["fh"]:
            rf["fh"].write(d)
        elif t == b"E" and rf["fh"]:
            rf["fh"].close(); rf["fh"] = None
            say(f"รับไฟล์แล้ว: {rf['path']}")
        elif t == b"X":
            say(d.decode("utf-8", "replace"), "#ff6b6b")

    dec = [None]
    slot = {"f": None}
    ev = threading.Event()

    def recv_frames():  # รับ+ถอดรหัสทุกเฟรมตามลำดับ (จำเป็นต่อ H.264) แต่ไม่แปลงภาพ ปล่อยให้ render_loop ทำเฉพาะเฟรมล่าสุด
        try:
            while alive[0]:
                lb = recv_exact(sock, 4)
                if not lb: break
                n = int.from_bytes(lb, "little")
                data = recv_exact(sock, n & 0x3FFFFFFF)
                if not data: break
                if n & 0x80000000:
                    on_file_packet(data)
                    continue
                if n & 0x40000000:
                    if dec[0] is None: dec[0] = av.CodecContext.create("h264", "r")
                    fr = dec[0].decode(av.Packet(data))
                    if not fr: continue
                    slot["f"] = fr[-1]
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
                    im = last.resize(want, Image.BILINEAR) if want and want[0] > 1 else last
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
                if im.size != (dw, dh): im = im.resize((dw, dh), Image.BILINEAR)
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
        def run():
            for x in paths:
                name = os.path.basename(x)
                say(f"กำลังส่ง {name} ...", "#2fa8ff")
                try:
                    nb = name.encode("utf-8")
                    send(b"F", len(nb).to_bytes(2, "little"), nb, os.path.getsize(x).to_bytes(8, "little"))
                    with open(x, "rb") as f:
                        while alive[0]:
                            b = f.read(65536)
                            if not b: break
                            send(b"C", len(b).to_bytes(4, "little"), b)
                except Exception as e:
                    log_err(e)
                    say(f"ส่ง {name} ไม่สำเร็จ: {e}", "#ff6b6b")
                    return
            say(f"ส่งไฟล์แล้ว {len(paths)} ไฟล์ (อยู่บนเดสก์ท็อปเครื่องปลายทาง)")
        threading.Thread(target=run, daemon=True).start()

    def pick_send():
        ps = filedialog.askopenfilenames(parent=win)
        if ps: send_files(list(ps))

    def pick_pull():
        v = simpledialog.askstring("ดึงไฟล์", "ใส่ที่อยู่ไฟล์บนเครื่องปลายทาง\n(เช่น C:\\Users\\Public\\file.pdf) ไฟล์จะมาอยู่บนเดสก์ท็อปเครื่องนี้", parent=win)
        if v and v.strip():
            pb = v.strip().strip('"').encode("utf-8")
            send(b"G", len(pb).to_bytes(2, "little"), pb)
            say("ขอไฟล์จากเครื่องปลายทางแล้ว ...", "#2fa8ff")

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
    win.bind("<KeyPress>", lambda e: on_key(e, False))
    win.bind("<KeyRelease>", lambda e: on_key(e, True))

    def close():
        alive[0] = False
        try: sock.close()
        except Exception: pass
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", close)
    def vbtn(text, cmd):
        tk.Button(bar, text=text, command=lambda: (cmd(), canvas.focus_set()), bg="#16233d", fg="#e7f0ff",
                  activebackground="#20314f", activeforeground="#ffffff", relief="flat", padx=10, pady=2,
                  font=("Segoe UI", 9)).pack(side="right", padx=4, pady=4)
    vbtn("ตัดการเชื่อมต่อ", close)
    vbtn("เต็มจอ (F11)", toggle_fs)
    vbtn("ดึงไฟล์มา", pick_pull)
    vbtn("ส่งไฟล์ไปเครื่องนั้น", pick_send)
    if DND[0]:
        try:
            canvas.drop_target_register(DND_FILES)
            canvas.dnd_bind("<<Drop>>", lambda e: send_files(list(win.tk.splitlist(e.data))))
        except Exception as e:
            log_err(e)
    canvas.focus_set()
    threading.Thread(target=recv_frames, daemon=True).start()
    threading.Thread(target=render_loop, daemon=True).start()
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
    S = lambda v: int(v * root.winfo_fpixels("1i") / 96)
    root.title(f"ZAIA Remote Desktop v{APP_VER}")
    root.geometry("1100x700")
    root.configure(bg=BG)
    root.minsize(900, 560)
    try: root.state("zoomed")
    except Exception: pass
    try: root.iconbitmap(ICON_PATH)
    except Exception: pass

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL2, font=("Tahoma", 13))
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("TLabel", background=PANEL, foreground=TEXT, font=("Tahoma", 13))
    style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Tahoma", 22, "bold"))
    style.configure("Sub.TLabel", background=BG, foreground=SUBTEXT, font=("Tahoma", 12))
    style.configure("Section.TLabel", background=PANEL, foreground=ACCENT, font=("Tahoma", 14, "bold"))
    style.configure("TCombobox", fieldbackground=PANEL2, background=PANEL2, foreground=TEXT, arrowcolor=TEXT)
    style.map("TCombobox", fieldbackground=[("readonly", PANEL2)], foreground=[("readonly", TEXT)])
    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", font=("Tahoma", 13, "bold"), padding=14, borderwidth=0)
    style.map("Accent.TButton", background=[("active", ACCENT2)])
    style.configure("Go.TButton", background="#1b7f3b", foreground="#ffffff", font=("Tahoma", 15, "bold"), padding=16, borderwidth=0)
    style.map("Go.TButton", background=[("active", "#146030")])
    root.option_add("*TCombobox*Listbox.font", ("Tahoma", 13))
    style.configure("Ghost.TButton", background=PANEL2, foreground=TEXT, font=("Tahoma", 12), padding=10, borderwidth=0)
    style.map("Ghost.TButton", background=[("active", "#20314f")])
    style.configure("Treeview", background=PANEL2, fieldbackground=PANEL2, foreground=TEXT, rowheight=S(46), borderwidth=0, font=("Tahoma", 12))
    style.configure("Treeview.Heading", background=PANEL, foreground=ACCENT, font=("Tahoma", 12, "bold"), borderwidth=0)
    style.map("Treeview", background=[("selected", ACCENT2)], foreground=[("selected", "#ffffff")])

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
    body.columnconfigure(0, weight=2)
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
    lbl_active = tk.Label(active_card, bg=PANEL2, fg=OK_C, justify="left", font=("Tahoma", 13, "bold"), anchor="w", wraplength=S(300))
    lbl_active.pack(fill="x", padx=12, pady=14)
    def refresh_active_label():
        lbl_active.config(text=f"● {username()}")
    refresh_active_label()

    def ask_user(first=False):  # ป๊อปอัปกลางหน้าต่างหลัก (เหมือนเมนูพักเกม) ไม่สร้างหน้าต่างแยก
        dim = tk.Frame(root, bg="#2c3e5c")
        dim.place(x=0, y=0, relwidth=1, relheight=1)
        w = tk.Frame(dim, bg=PANEL, highlightbackground=ACCENT, highlightthickness=4)
        w.place(relx=0.5, rely=0.5, anchor="center")
        FB = ("Tahoma", 14)
        tk.Label(w, text="เลือกผู้ใช้งาน", bg=PANEL, fg=TEXT, font=("Tahoma", 22, "bold")).pack(anchor="w", padx=32, pady=(26, 4))
        tk.Label(w, text="เลือกครั้งเดียว โปรแกรมจะจำไว้ เปลี่ยนได้ภายหลัง", bg=PANEL, fg=SUBTEXT, font=FB).pack(anchor="w", padx=32)
        v_role, v_unit = tk.StringVar(value=cfg.get("role", "")), tk.StringVar(value=cfg.get("unit", ""))
        for label, var, vals in (("ตำแหน่ง", v_role, ROLES), ("หน่วย", v_unit, UNITS)):
            tk.Label(w, text=label, bg=PANEL, fg=SUBTEXT, font=FB).pack(anchor="w", padx=32, pady=(14, 4))
            ttk.Combobox(w, textvariable=var, values=vals, state="readonly", width=30, font=("Tahoma", 16)).pack(padx=32)
        pv = tk.Label(w, bg=PANEL2, fg=OK_C, font=("Tahoma", 16, "bold"), anchor="w")
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
        tk.Label(w, text="เลือกคุณภาพภาพ", bg=PANEL, fg=TEXT, font=("Tahoma", 17, "bold")).pack(anchor="w", padx=20, pady=(16, 2))
        tk.Label(w, text=f"เชื่อมต่อกับ {who}", bg=PANEL, fg=SUBTEXT).pack(anchor="w", padx=20, pady=(0, 8))
        v = tk.IntVar(value=cfg.get("quality", 2))  # จำค่าที่เลือกครั้งก่อน
        for i, txt in enumerate(("ประหยัด  720p 30fps", "กลาง  1080p 30fps", "สูงสุด  1080p 60fps (ลื่นสุด ปรับตามเน็ตอัตโนมัติ)")):
            tk.Radiobutton(w, text=txt, variable=v, value=i, bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL,
                           activeforeground=TEXT, anchor="w").pack(fill="x", padx=20, pady=2)
        def ok():
            q = v.get(); cfg["quality"] = q; save_config(cfg); w.destroy(); go(q)
        row = tk.Frame(w, bg=PANEL); row.pack(fill="x", padx=20, pady=16)
        ttk.Button(row, text="เชื่อมต่อ", style="Accent.TButton", command=ok).pack(side="right")
        ttk.Button(row, text="ยกเลิก", style="Ghost.TButton", command=w.destroy).pack(side="right", padx=8)
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
    ttk.Button(urow, text="เปลี่ยนข้อมูล", style="Ghost.TButton", command=lambda: ask_user(False)).pack(side="left")
    ttk.Button(urow, text="ตรวจหารุ่นใหม่", style="Ghost.TButton", command=do_update).pack(side="left", padx=6)
    root.after(8000, lambda: do_update(True))

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

    ttk.Label(left, text="โหมดเซิร์ฟเวอร์", style="Section.TLabel").pack(anchor="w", padx=16, pady=(10, 6))
    auto_var = tk.BooleanVar(value=bool(cfg.get("auto_allow", False)))
    def toggle_auto():
        if auto_var.get() and not messagebox.askyesno("อนุญาตอัตโนมัติ", "ทุกเครื่องในเครือข่าย ZeroTier จะควบคุมจอเครื่องนี้ได้ทันที โดยไม่ถามก่อน\nเปิดโหมดนี้ไหม", icon="warning"):
            auto_var.set(False)
        cfg["auto_allow"] = auto_var.get()
        save_config(cfg)
    tk.Checkbutton(left, text="อนุญาตเชื่อมต่ออัตโนมัติ (ไม่มีคนนั่งหน้าเครื่อง)", variable=auto_var, command=toggle_auto,
                   bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL, activeforeground=TEXT,
                   anchor="w", justify="left", wraplength=S(320)).pack(fill="x", padx=16)

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
        with peers_lock:
            ips = [ip] + sorted(peers.get(uid, {}).get("ips", set()) - {ip})
        who = str(tree.item(uid)["values"][1])
        ask_quality(who, lambda q: threading.Thread(target=open_viewer, args=(ips, q), daemon=True).start())
    lbl_status = tk.Label(right, text="พร้อมใช้งาน", bg=PANEL, fg=SUBTEXT, anchor="w", justify="left", wraplength=S(340))
    lbl_status.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
    STATUS[0] = lbl_status
    def connect_ip():
        v = simpledialog.askstring("เชื่อมต่อด้วย IP", "ใส่ IP ของเครื่องปลายทาง (IP ZeroTier)")
        if v and v.strip():
            ask_quality(v.strip(), lambda q: threading.Thread(target=open_viewer, args=([v.strip()], q), daemon=True).start())
    crow = tk.Frame(right, bg=PANEL)
    crow.pack(side="bottom", fill="x", padx=16, pady=12)
    ttk.Button(crow, text="ดูจอเครื่องที่เลือก", style="Go.TButton", command=do_connect).pack(side="left")
    ttk.Button(crow, text="ต่อด้วยเลข IP", style="Ghost.TButton", command=connect_ip).pack(side="left", padx=8)

    cols = ("host", "user", "status", "ip", "ver")
    tree = ttk.Treeview(right, columns=cols, show="headings")
    for c, w in zip(cols, (140, 270, 70, 140, 60)):
        tree.heading(c, text={"host":"เครื่อง","user":"ผู้ใช้","status":"สถานะ","ip":"IP","ver":"รุ่น"}[c])
        tree.column(c, width=S(w), anchor="w" if c in ("host", "user") else "center", stretch=(c == "user"))
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
        t = tk.Text(w, bg=PANEL2, fg=TEXT, font=("Tahoma", 13), wrap="word", relief="flat", padx=12, pady=10, spacing3=S(4))
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
