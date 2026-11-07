# -*- coding: utf-8 -*-
# สร้าง update.json จากไฟล์ในโฟลเดอร์นี้ (รันทุกครั้งหลังแก้ไฟล์ แล้วอัปโหลด update.json + ไฟล์ที่เปลี่ยนขึ้น GitHub)
#   python MakeRelease.py                      -> ตัวอย่างพื้นฐาน
#   python MakeRelease.py --zt b103a835d26ef7ce [--leave-old]   -> ให้เครื่องที่อัปเดตย้ายไป Network ID นี้
#   python MakeRelease.py --setup-rev 2        -> รุ่นนี้ต้องลงตัวติดตั้งใหม่ (ไลบรารีเปลี่ยน) ปุ่มอัปเดตจะไม่ทำ
import hashlib, json, os, re, sys
d = os.path.dirname(os.path.abspath(__file__))
FILES = ["ZaiaRemote.py", "ZaiaRemote.exe", "zaia.ico", "zaia_logo.png"]  # ไฟล์ที่ตัวติดตั้งวางใน {app}
a = sys.argv[1:]
src = open(os.path.join(d, "ZaiaRemote.py"), encoding="utf-8").read()
m = {"version": re.search(r'^APP_VER = "([\d.]+)"', src, re.M).group(1), "files": {}}
for f in FILES:
    m["files"][f] = hashlib.sha256(open(os.path.join(d, f), "rb").read()).hexdigest()
if "--zt" in a: m["zt_network_id"] = a[a.index("--zt") + 1]
if "--leave-old" in a: m["zt_leave_old"] = True
if "--setup-rev" in a: m["setup_rev"] = int(a[a.index("--setup-rev") + 1])
open(os.path.join(d, "update.json"), "w", encoding="utf-8", newline="\n").write(json.dumps(m, ensure_ascii=False, indent=1) + "\n")
print("update.json:", m["version"], len(m["files"]), "files")
