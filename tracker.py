#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tracker unifié — Souris + Clavier
http://localhost:5000
"""
import json, time, math, os, sys, threading, webbrowser
from datetime import datetime, date
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Dépendances optionnelles ───────────────────────────────────────────
for pkg in ["pynput"]:
    try: __import__(pkg)
    except ImportError: os.system(f"{sys.executable} -m pip install {pkg} --quiet")

from pynput import mouse as pmouse, keyboard as pkeyboard

try:
    import ctypes, ctypes.wintypes as wt
    WINDOWS = True
except ImportError:
    WINDOWS = False

# pystray + PIL pour l'icône tray (optionnel)
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# Stemmer Snowball FR via nltk (optionnel — fallback sur mot brut)
try:
    from nltk.stem.snowball import SnowballStemmer
    _stemmer_fr = SnowballStemmer("french")
    _stemmer_en = SnowballStemmer("english")
    HAS_STEMMER = True
except ImportError:
    HAS_STEMMER = False

# ── Stopwords FR + EN (hardcodés, zéro dépendance) ─────────────────
STOPWORDS = {
    # Articles / déterminants FR
    "le","la","les","l","un","une","des","du","de","d","au","aux",
    # Pronoms FR
    "je","tu","il","elle","on","nous","vous","ils","elles",
    "me","te","se","lui","leur","y","en","ce","ci","là",
    "mon","ton","son","ma","ta","sa","mes","tes","ses","nos","vos","leurs",
    "moi","toi","soi","eux",
    # Prépositions / conjonctions FR
    "à","a","et","ou","ni","mais","donc","or","car","si","que","qui","quoi",
    "dont","où","par","pour","sur","sous","dans","avec","sans","entre",
    "vers","chez","contre","depuis","pendant","avant","après","lors",
    "comme","plus","moins","très","bien","aussi","encore","déjà","toujours",
    "jamais","ici","là","voici","voilà","même","tout","tous","toute","toutes",
    "autre","autres","quel","quelle","quels","quelles","ça","cela","ceci",
    "cette","ces","est","été","être","avoir","faire","dit","fait","va","vais",
    "peu","pas","non","oui","ne","n","je","j","qu","c","m","s","t",
    # Articles / déterminants EN
    "the","a","an","this","that","these","those","my","your","his","her",
    "its","our","their","some","any","no","each","every","both","few","more",
    # Pronoms EN
    "i","you","he","she","it","we","they","me","him","us","them",
    "who","which","what","whose","whom","where","when","why","how",
    # Prépositions / conjonctions EN
    "in","on","at","to","for","of","with","by","from","as","into","onto",
    "about","above","below","between","through","during","before","after",
    "and","or","but","so","yet","nor","if","then","than","that","because",
    "while","although","though","until","unless","since","whether",
    # Verbes courants EN
    "is","are","was","were","be","been","being","have","has","had","do",
    "does","did","will","would","could","should","may","might","shall",
    "must","can","get","got","go","went","come","came","make","made",
    "say","said","know","think","see","look","want","use","find","give",
    # Divers
    "ok","yeah","yes","no","not","just","also","too","very","really",
    "already","still","now","then","here","there","up","down","out","off",
    "re","ll","ve","don","doesn","didn","isn","aren","wasn","weren","wouldn",
    "couldn","shouldn","hasn","hadn","won","can",
}

def stem(word):
    """Retourne la racine du mot (stemming bilingue FR/EN)."""
    if not HAS_STEMMER: return word
    # Heuristique : si le mot contient des caractères accentués → FR
    if any(c in word for c in "àâäéèêëîïôöùûüç"):
        return _stemmer_fr.stem(word)
    # Sinon on essaie FR puis EN (le stemmer FR marche bien sur l'anglais aussi)
    return _stemmer_fr.stem(word)

def is_stopword(word):
    return word.lower() in STOPWORDS or len(word) < 3


# ── Constantes ─────────────────────────────────────────────────────────
BASE_DIR           = os.path.dirname(os.path.abspath(__file__))
MOUSE_FILE         = os.path.join(BASE_DIR, "mouse_data.json")
KB_FILE            = os.path.join(BASE_DIR, "keyboard_data.json")
DASH_FILE          = os.path.join(BASE_DIR, "dashboard.html")
PORT               = 5000
SAVE_INTERVAL      = 10       # secondes entre sauvegardes
GRID_SIZE          = 20       # px grille heatmap
DOUBLE_CLICK_MS    = 250
DOUBLE_CLICK_PX    = 20
DRAG_MIN_MS        = 180
DRAG_MIN_PX        = 8
SCROLL_PX_PER_TICK = 100
SCREEN_POLL_SEC    = 5
PAUSE_THRESHOLD    = 300      # 5 min sans activité = pause
APP_POLL_SEC       = 2        # fréquence détection fenêtre active

# ══════════════════════════════════════════════════════════════════════
#  DÉMARRAGE AUTOMATIQUE WINDOWS
# ══════════════════════════════════════════════════════════════════════

def setup_autostart():
    """Ajoute le tracker au démarrage Windows via le registre."""
    if not WINDOWS: return
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        script = os.path.abspath(__file__)
        cmd    = f'"{sys.executable}" "{script}"'
        winreg.SetValueEx(key, "ActivityTracker", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        print("[Autostart] Entrée registre créée.")
    except Exception as e:
        print(f"[Autostart] Erreur : {e}")

def remove_autostart():
    if not WINDOWS: return
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, "ActivityTracker")
        winreg.CloseKey(key)
        print("[Autostart] Entrée registre supprimée.")
    except: pass

def check_autostart():
    if not WINDOWS: return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_READ)
        winreg.QueryValueEx(key, "ActivityTracker")
        winreg.CloseKey(key)
        return True
    except: return False

# ══════════════════════════════════════════════════════════════════════
#  DÉTECTION ÉCRANS
# ══════════════════════════════════════════════════════════════════════

def get_monitors():
    monitors = []
    if not WINDOWS: return monitors
    PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong, ctypes.c_ulong,
                               ctypes.POINTER(wt.RECT), ctypes.c_double)
    def cb(hM, hdcM, lpr, d):
        r = lpr.contents
        monitors.append({"left":r.left,"top":r.top,"right":r.right,"bottom":r.bottom,
                         "width":r.right-r.left,"height":r.bottom-r.top})
        return True
    ctypes.windll.user32.EnumDisplayMonitors(None, None, PROC(cb), 0)
    return monitors

def build_screen_info(monitors=None):
    if monitors is None: monitors = get_monitors()
    if not monitors:
        return {"screens":[{"id":"laptop","label":"Laptop","left":0,"top":0,
                            "right":1920,"bottom":1080,"width":1920,"height":1080}],
                "virtual_left":0,"virtual_top":0,"virtual_width":1920,"virtual_height":1080}
    ms = sorted(monitors, key=lambda m: (m["top"], m["left"]))
    screens = []
    for i, m in enumerate(ms):
        ext = i==0 and len(ms)>1
        screens.append({"id":"external" if ext else "laptop",
                        "label":"Moniteur externe" if ext else "Laptop",
                        **{k:m[k] for k in ("left","top","right","bottom","width","height")}})
    vl=min(m["left"] for m in monitors); vt=min(m["top"] for m in monitors)
    return {"screens":screens,"virtual_left":vl,"virtual_top":vt,
            "virtual_width":max(m["right"] for m in monitors)-vl,
            "virtual_height":max(m["bottom"] for m in monitors)-vt}

def screens_fingerprint(si):
    return tuple((s["id"],s["left"],s["top"],s["width"],s["height"]) for s in si["screens"])

screen_info = build_screen_info()

def watch_screens():
    global screen_info
    last_fp = screens_fingerprint(screen_info)
    while True:
        time.sleep(SCREEN_POLL_SEC)
        try:
            new_si = build_screen_info()
            new_fp = screens_fingerprint(new_si)
            if new_fp != last_fp:
                with mlock:
                    screen_info = new_si
                    mdata["screen_info"] = new_si
                last_fp = new_fp
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Ecrans : "
                      f"{[s['label']+' '+str(s['width'])+'x'+str(s['height']) for s in new_si['screens']]}")
        except Exception as e:
            print(f"[ERREUR watch_screens] {e}")

# ══════════════════════════════════════════════════════════════════════
#  DÉTECTION FENÊTRE ACTIVE
# ══════════════════════════════════════════════════════════════════════

current_app   = "unknown"
app_lock      = threading.Lock()

def get_active_window():
    """Retourne le nom de l'exe de la fenêtre au premier plan."""
    if not WINDOWS: return "unknown"
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd: return "unknown"
        pid = wt.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = ctypes.windll.kernel32.OpenProcess(0x0410, False, pid.value)
        if not h: return "unknown"
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.psapi.GetModuleFileNameExW(h, None, buf, 260)
        ctypes.windll.kernel32.CloseHandle(h)
        exe = os.path.basename(buf.value) if buf.value else "unknown"
        return exe.lower().replace(".exe","") if exe else "unknown"
    except:
        return "unknown"

def watch_app():
    """Thread : met à jour current_app toutes les APP_POLL_SEC s."""
    global current_app
    while True:
        try:
            app = get_active_window()
            with app_lock:
                current_app = app
        except: pass
        time.sleep(APP_POLL_SEC)

# ══════════════════════════════════════════════════════════════════════
#  DÉTECTION PAUSES
# ══════════════════════════════════════════════════════════════════════

last_activity_ts = time.time()
activity_lock    = threading.Lock()
in_pause         = False

def register_activity():
    """Appelé à chaque événement souris/clavier."""
    global last_activity_ts, in_pause
    now = time.time()
    with activity_lock:
        if in_pause:
            # Fin de pause
            pause_dur = int(now - last_activity_ts)
            today = datetime.now().strftime("%Y-%m-%d")
            with mlock:
                day = ensure_mouse_day(today)
                day.setdefault("pauses",[]).append({
                    "start": datetime.fromtimestamp(last_activity_ts).isoformat(),
                    "end":   datetime.fromtimestamp(now).isoformat(),
                    "dur_s": pause_dur
                })
                day["pause_total_s"] = day.get("pause_total_s",0) + pause_dur
            in_pause = False
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Reprise après {pause_dur//60}m{pause_dur%60:02d}s de pause")
        last_activity_ts = now

def watch_pauses():
    """Thread : détecte les pauses d'inactivité."""
    global in_pause
    while True:
        time.sleep(10)
        with activity_lock:
            idle = time.time() - last_activity_ts
            if idle >= PAUSE_THRESHOLD and not in_pause:
                in_pause = True
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Pause détectée (>{PAUSE_THRESHOLD//60} min)")

# ══════════════════════════════════════════════════════════════════════
#  HOOK VEILLE / RÉVEIL
# ══════════════════════════════════════════════════════════════════════

def watch_power():
    if not WINDOWS: return
    try:
        WM_POWERBROADCAST      = 0x0218
        PBT_APMRESUMEAUTOMATIC = 0x0012
        PBT_APMSUSPEND         = 0x0004

        # WNDCLASSW n'est pas dans ctypes.wintypes sur toutes les versions — on le definit manuellement
        WNDPROCTYPE = ctypes.WINFUNCTYPE(ctypes.c_long, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style",         ctypes.c_uint),
                ("lpfnWndProc",   WNDPROCTYPE),
                ("cbClsExtra",    ctypes.c_int),
                ("cbWndExtra",    ctypes.c_int),
                ("hInstance",     wt.HINSTANCE),
                ("hIcon",         ctypes.c_void_p),
                ("hCursor",       ctypes.c_void_p),
                ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName",  wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR),
            ]

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_POWERBROADCAST:
                if wparam == PBT_APMSUSPEND:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Veille -- sauvegarde...")
                    global in_pause, last_activity_ts
                    with activity_lock:
                        in_pause = True
                        last_activity_ts = time.time()
                    with mlock: save_mouse()
                    with klock: save_kb()
                elif wparam == PBT_APMRESUMEAUTOMATIC:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Reveil -- re-detection ecrans...")
                    time.sleep(2)
                    new_si = build_screen_info()
                    with mlock:
                        global screen_info
                        screen_info = new_si
                        mdata["screen_info"] = new_si
                    register_activity()
            return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        wc               = WNDCLASSW()
        wc.lpfnWndProc   = WNDPROCTYPE(wnd_proc)
        wc.hInstance     = ctypes.windll.kernel32.GetModuleHandleW(None)
        wc.lpszClassName = "TrackerPowerWatcher"
        ctypes.windll.user32.RegisterClassW(ctypes.byref(wc))
        hwnd = ctypes.windll.user32.CreateWindowExW(
            0, "TrackerPowerWatcher", None, 0, 0, 0, 0, 0,
            -3, None, wc.hInstance, None)
        print(f"[watch_power] Hook veille actif")
        msg = wt.MSG()
        while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), hwnd, 0, 0) != 0:
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
    except Exception as e:
        print(f"[ERREUR watch_power] {e}")


# ══════════════════════════════════════════════════════════════════════
#  ICÔNE TRAY
# ══════════════════════════════════════════════════════════════════════

tray_icon = None

def make_tray_image():
    img = Image.new("RGB", (64,64), "#1e1b4b")
    d   = ImageDraw.Draw(img)
    d.ellipse([8,8,56,56], fill="#4f46e5")
    d.ellipse([20,20,44,44], fill="#1e1b4b")
    d.ellipse([28,28,36,36], fill="#a5b4fc")
    return img

def run_tray():
    global tray_icon
    if not HAS_TRAY: return
    try:
        def open_dash(icon, item): webbrowser.open(f"http://localhost:{PORT}")
        def quit_app(icon, item):
            icon.stop()
            with mlock: save_mouse()
            with klock: save_kb()
            os._exit(0)
        def toggle_autostart(icon, item):
            if check_autostart(): remove_autostart()
            else: setup_autostart()

        tray_icon = pystray.Icon(
            "tracker",
            make_tray_image(),
            "Activity Tracker",
            menu=pystray.Menu(
                pystray.MenuItem("📊 Ouvrir dashboard", open_dash, default=True),
                pystray.MenuItem("🚀 Démarrage auto",
                    toggle_autostart,
                    checked=lambda item: check_autostart()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("❌ Quitter", quit_app),
            )
        )
        tray_icon.run()
    except Exception as e:
        print(f"[ERREUR tray] {e}")

# ══════════════════════════════════════════════════════════════════════
#  SOURIS
# ══════════════════════════════════════════════════════════════════════

def mouse_empty_day():
    return {
        "left_clicks":0,"right_clicks":0,"middle_clicks":0,"double_clicks":0,
        "total_clicks":0,"drags":0,"drag_distance_px":0,"drag_duration_ms":0,
        "scroll_up":0,"scroll_down":0,"scroll_dist_px":0,
        "hours":{},"per_screen":{},
        "heatmap":{},"heatmap_right":{},"heatmap_middle":{},
        "pauses":[],"pause_total_s":0,
        "apps":{}         # {app_name: click_count}
    }

def load_mouse():
    if os.path.exists(MOUSE_FILE):
        try:
            with open(MOUSE_FILE, encoding="utf-8") as f: return json.load(f)
        except: pass
    return {"clicks":[],"drags":[],"daily_stats":{},
            "heatmap":{},"heatmap_per_screen":{},
            "heatmap_right":{},"heatmap_right_per_screen":{},
            "heatmap_middle":{},"heatmap_middle_per_screen":{},
            "total":{"left_clicks":0,"right_clicks":0,"middle_clicks":0,"double_clicks":0,
                     "scroll_up":0,"scroll_down":0,"scroll_dist_px":0,"distance_px":0,
                     "drags":0,"drag_distance_px":0,"drag_duration_ms":0}}

def save_mouse():
    with open(MOUSE_FILE,"w",encoding="utf-8") as f:
        json.dump(mdata,f,indent=2,ensure_ascii=False)

def ensure_mouse_day(today):
    if today not in mdata["daily_stats"]: mdata["daily_stats"][today]=mouse_empty_day()
    d=mdata["daily_stats"][today]
    for k,v in mouse_empty_day().items():
        if k not in d: d[k]=v
    return d

mdata=load_mouse()
mdata["screen_info"]=screen_info
for k in ["heatmap_per_screen","heatmap","drags","heatmap_right","heatmap_right_per_screen",
          "heatmap_middle","heatmap_middle_per_screen"]:
    if k not in mdata: mdata[k]={}if k!="drags"else[]
for k in ["double_clicks","drags","drag_distance_px","drag_duration_ms","scroll_dist_px"]:
    if k not in mdata["total"]: mdata["total"][k]=0

mlock=threading.Lock()
m_last_click_ts=None; m_click_intervals=[]; m_total_dist=0.0
m_last_x=m_last_y=0; m_prev_left_ts=m_prev_left_x=m_prev_left_y=None
m_press_state={}

print(f"Ecrans : {len(screen_info['screens'])}")
for s in screen_info["screens"]:
    print(f"  [{s['label']}] {s['width']}x{s['height']} @ ({s['left']},{s['top']})")

def screen_for(x,y):
    for s in screen_info["screens"]:
        if s["left"]<=x<s["right"] and s["top"]<=y<s["bottom"]: return s
    def dr(s): cx=max(s["left"],min(x,s["right"]-1)); cy=max(s["top"],min(y,s["bottom"]-1)); return (x-cx)**2+(y-cy)**2
    return min(screen_info["screens"],key=dr)

def record_heatmap(x,y,screen,btn,day_dict):
    rx=max(0,min(((x-screen["left"])//GRID_SIZE)*GRID_SIZE,screen["width"]-GRID_SIZE))
    ry=max(0,min(((y-screen["top"]) //GRID_SIZE)*GRID_SIZE,screen["height"]-GRID_SIZE))
    rk=f"{screen['id']}:{rx},{ry}"
    hk="heatmap"if btn=="left"else("heatmap_right"if btn=="right"else"heatmap_middle")
    day_dict[hk][rk]=day_dict[hk].get(rk,0)+1

def on_mouse_move(x,y):
    global m_last_x,m_last_y,m_total_dist
    dist=math.hypot(x-m_last_x,y-m_last_y)
    m_total_dist+=dist; m_last_x,m_last_y=x,y
    with mlock:
        for st in m_press_state.values(): st["move_dist"]+=dist
    register_activity()

def on_mouse_click(x,y,button,pressed):
    global m_last_click_ts,m_prev_left_ts,m_prev_left_x,m_prev_left_y
    register_activity()
    now=datetime.now(); ts=now.timestamp()
    today=now.strftime("%Y-%m-%d"); hour=now.strftime("%H")
    btn=str(button).replace("Button.","")
    with app_lock: app=current_app
    with mlock:
        scr=screen_for(x,y); sid=scr["id"]
        if pressed:
            m_press_state[btn]={"time":ts,"x":x,"y":y,"screen_id":sid,"move_dist":0.0}
            interval=None
            if m_last_click_ts:
                interval=ts-m_last_click_ts
                if interval<300: m_click_intervals.append(round(interval,3))
            m_last_click_ts=ts
            bk={"left":"left_clicks","right":"right_clicks"}.get(btn,"middle_clicks")
            mdata["total"][bk]+=1
            day=ensure_mouse_day(today)
            day[bk]+=1; day["total_clicks"]+=1
            day["hours"][hour]=day["hours"].get(hour,0)+1
            day["per_screen"][sid]=day["per_screen"].get(sid,0)+1
            # App tracking
            day["apps"][app]=day["apps"].get(app,0)+1
            record_heatmap(x,y,scr,btn,day)
            mdata["clicks"].append({"t":now.isoformat(),"x":x,"y":y,"btn":btn,"screen":sid,"interval":interval,"app":app})
            if len(mdata["clicks"])>1000: mdata["clicks"]=mdata["clicks"][-1000:]
        else:
            st=m_press_state.pop(btn,None)
            if not st: return
            held_ms=(ts-st["time"])*1000; move_dist=st["move_dist"]
            if btn=="left":
                if(m_prev_left_ts and(ts-m_prev_left_ts)*1000<=DOUBLE_CLICK_MS
                        and math.hypot(x-m_prev_left_x,y-m_prev_left_y)<=DOUBLE_CLICK_PX):
                    mdata["total"]["double_clicks"]+=1
                    ensure_mouse_day(today)["double_clicks"]+=1
                    m_prev_left_ts=None
                else: m_prev_left_ts=ts; m_prev_left_x=x; m_prev_left_y=y
            if held_ms>=DRAG_MIN_MS and move_dist>=DRAG_MIN_PX:
                day=ensure_mouse_day(today)
                mdata["total"]["drags"]+=1; mdata["total"]["drag_distance_px"]+=int(move_dist)
                mdata["total"]["drag_duration_ms"]+=int(held_ms)
                day["drags"]+=1; day["drag_distance_px"]+=int(move_dist); day["drag_duration_ms"]+=int(held_ms)
                mdata["drags"].append({"t":now.isoformat(),"btn":btn,"screen":sid,
                    "x0":st["x"],"y0":st["y"],"x1":x,"y1":y,
                    "duration_ms":round(held_ms,1),"dist_px":round(move_dist,1),
                    "displacement":round(math.hypot(x-st["x"],y-st["y"]),1)})
                if len(mdata["drags"])>2000: mdata["drags"]=mdata["drags"][-2000:]

def on_mouse_scroll(x,y,dx,dy):
    register_activity()
    with mlock:
        today=datetime.now().strftime("%Y-%m-%d")
        day=ensure_mouse_day(today)
        ticks=abs(dy); dist_px=int(ticks*SCROLL_PX_PER_TICK)
        if dy>0: mdata["total"]["scroll_up"]+=ticks; day["scroll_up"]+=ticks
        else:    mdata["total"]["scroll_down"]+=ticks; day["scroll_down"]+=ticks
        mdata["total"]["scroll_dist_px"]+=dist_px; day["scroll_dist_px"]+=dist_px

# ══════════════════════════════════════════════════════════════════════
#  CLAVIER
# ══════════════════════════════════════════════════════════════════════

SHORTCUTS_MAP={
    frozenset(["ctrl","c"]):"Ctrl+C",   frozenset(["ctrl","v"]):"Ctrl+V",
    frozenset(["ctrl","x"]):"Ctrl+X",   frozenset(["ctrl","z"]):"Ctrl+Z",
    frozenset(["ctrl","y"]):"Ctrl+Y",   frozenset(["ctrl","s"]):"Ctrl+S",
    frozenset(["ctrl","a"]):"Ctrl+A",   frozenset(["ctrl","f"]):"Ctrl+F",
    frozenset(["ctrl","w"]):"Ctrl+W",   frozenset(["ctrl","t"]):"Ctrl+T",
    frozenset(["ctrl","n"]):"Ctrl+N",   frozenset(["ctrl","p"]):"Ctrl+P",
    frozenset(["ctrl","d"]):"Ctrl+D",   frozenset(["ctrl","r"]):"Ctrl+R",
    frozenset(["ctrl","l"]):"Ctrl+L",   frozenset(["ctrl","k"]):"Ctrl+K",
    frozenset(["alt","tab"]):"Alt+Tab", frozenset(["alt","f4"]):"Alt+F4",
    frozenset(["ctrl","shift","esc"]):"Ctrl+Shift+Esc",
    frozenset(["ctrl","shift","n"]):"Ctrl+Shift+N",
    frozenset(["ctrl","shift","v"]):"Ctrl+Shift+V",
    frozenset(["win","d"]):"Win+D",     frozenset(["win","l"]):"Win+L",
    frozenset(["win","e"]):"Win+E",
}
MODIFIER_KEYS={"shift","ctrl","alt","cmd","win","meta","altgr"}
SPECIAL_DISPLAY={
    "space":"Space","backspace":"Backspace","delete":"Delete","enter":"Enter",
    "tab":"Tab","escape":"Esc","shift":"Shift","ctrl":"Ctrl","alt":"Alt",
    "win":"Win","cmd":"Cmd","caps_lock":"CapsLock",
    "up":"Up","down":"Down","left":"Left","right":"Right",
    "page_up":"PageUp","page_down":"PageDown","home":"Home","end":"End",
    "f1":"F1","f2":"F2","f3":"F3","f4":"F4","f5":"F5","f6":"F6",
    "f7":"F7","f8":"F8","f9":"F9","f10":"F10","f11":"F11","f12":"F12",
}
CAT_TO_KEY={
    "letter":"letters","digit":"digits","space":"spaces","delete":"deletes",
    "enter":"enters","modifier":"modifiers","navigation":"navigations",
    "symbol":"symbols","tab":"symbols","function":"other","other":"other",
}

def categorize_key(k):
    if len(k)==1:
        if k.isalpha(): return "letter"
        if k.isdigit(): return "digit"
        return "symbol"
    if k=="space":               return "space"
    if k in("backspace","delete"):return "delete"
    if k in("enter","return"):   return "enter"
    if k in MODIFIER_KEYS:       return "modifier"
    if k=="tab":                 return "tab"
    if k in("up","down","left","right","page_up","page_down","home","end"): return "navigation"
    if k.startswith("f") and k[1:].isdigit(): return "function"
    return "other"

def norm_key(key):
    try:
        c=key.char
        if c:
            if len(c)==1 and ord(c)<32: return chr(ord(c)+96)
            return c.lower()
    except AttributeError: pass
    name=str(key).replace("Key.","").replace("KeyCode.","").lower()
    for base in("shift","ctrl","alt","cmd"):
        if name.startswith(base): return base
    if any(x in name for x in("cmd","super","win")): return "win"
    if name in("altgr","alt_gr","alt_r"): return "altgr"
    return name

def disp_key(k):
    if k in SPECIAL_DISPLAY: return SPECIAL_DISPLAY[k]
    return k.upper()if len(k)==1 else k.capitalize()

def kb_empty_day():
    return {"keystrokes":0,"letters":0,"digits":0,"spaces":0,"deletes":0,
            "enters":0,"modifiers":0,"navigations":0,"symbols":0,"other":0,
            "words_typed":0,"words_content":0,"shortcuts":{},"hours":{},"apps":{},
            # {stem: {"canonical": mot_le_plus_frequent, "count": N, "forms": {forme: count}}}
            "vocab_stems":{}}

def load_kb():
    if os.path.exists(KB_FILE):
        try:
            with open(KB_FILE,encoding="utf-8") as f: return json.load(f)
        except: pass
    return{"keystrokes_log":[],"words_log":[],"daily_stats":{},"top_keys":{},"shortcuts":{},
           "total":{"keystrokes":0,"letters":0,"digits":0,"spaces":0,"deletes":0,
                    "enters":0,"modifiers":0,"navigations":0,"symbols":0,"other":0,
                    "words_typed":0,"words_content":0,"shortcuts":0}}

def save_kb():
    with open(KB_FILE,"w",encoding="utf-8") as f:
        json.dump(kdata,f,indent=2,ensure_ascii=False)

def ensure_kb_day(today):
    if today not in kdata["daily_stats"]: kdata["daily_stats"][today]=kb_empty_day()
    d=kdata["daily_stats"][today]
    for k,v in kb_empty_day().items():
        if k not in d: d[k]=v
    return d

kdata=load_kb()
if "words_log" not in kdata: kdata["words_log"]=[]
klock=threading.Lock()
k_held=set(); k_modifiers=set(); k_word_buf=[]
k_keystroke_ts=deque(); k_intervals=[]; k_last_ts=None

def on_key_press(key):
    global k_last_ts
    register_activity()
    now=datetime.now(); ts=time.time()
    today=now.strftime("%Y-%m-%d"); hour=now.strftime("%H")
    kn=norm_key(key)
    with app_lock: app=current_app
    with klock:
        if kn in k_held: return
        k_held.add(kn)
        cat=categorize_key(kn)
        if cat=="modifier":
            k_modifiers.add(kn)
            kdata["total"]["keystrokes"]+=1; kdata["total"]["modifiers"]+=1
            day=ensure_kb_day(today)
            day["keystrokes"]+=1; day["modifiers"]+=1
            day["hours"][hour]=day["hours"].get(hour,0)+1
            day["apps"][app]=day["apps"].get(app,0)+1
            dk=disp_key(kn)
            kdata["top_keys"][dk]=kdata["top_keys"].get(dk,0)+1
            kdata["keystrokes_log"].append({"t":now.isoformat(),"key":dk,"cat":cat,"app":app})
            if len(kdata["keystrokes_log"])>10000: kdata["keystrokes_log"]=kdata["keystrokes_log"][-10000:]
            if k_last_ts:
                iv=ts-k_last_ts
                if iv<5: k_intervals.append(round(iv,4))
            k_last_ts=ts; return
        if k_modifiers:
            combo=frozenset(k_modifiers|{kn})
            matched=SHORTCUTS_MAP.get(combo)
            if matched:
                kdata["shortcuts"][matched]=kdata["shortcuts"].get(matched,0)+1
                kdata["total"]["shortcuts"]+=1
                d=ensure_kb_day(today)
                if "shortcuts" not in d: d["shortcuts"]={}
                d["shortcuts"][matched]=d["shortcuts"].get(matched,0)+1
                dk="+".join(sorted(k_modifiers))+"+"+disp_key(kn)
                kdata["keystrokes_log"].append({"t":now.isoformat(),"key":dk,"cat":"shortcut","app":app})
                if len(kdata["keystrokes_log"])>10000: kdata["keystrokes_log"]=kdata["keystrokes_log"][-10000:]
                if k_last_ts:
                    iv=ts-k_last_ts
                    if iv<5: k_intervals.append(round(iv,4))
                k_last_ts=ts; return
        if "altgr" in k_modifiers: cat="symbol"
        day_key=CAT_TO_KEY.get(cat,"other")
        kdata["total"]["keystrokes"]+=1; kdata["total"][day_key]+=1
        day=ensure_kb_day(today)
        day["keystrokes"]+=1; day[day_key]+=1
        day["hours"][hour]=day["hours"].get(hour,0)+1
        day["apps"][app]=day["apps"].get(app,0)+1
        dk=disp_key(kn)
        kdata["top_keys"][dk]=kdata["top_keys"].get(dk,0)+1
        kdata["keystrokes_log"].append({"t":now.isoformat(),"key":dk,"cat":cat,"app":app})
        if len(kdata["keystrokes_log"])>10000: kdata["keystrokes_log"]=kdata["keystrokes_log"][-10000:]
        if cat in("letter","space"): k_keystroke_ts.append(ts)
        if cat in("space","enter"):
            if k_word_buf:
                word="".join(k_word_buf).strip().lower()
                if 2<=len(word)<=30:
                    kdata["total"]["words_typed"]+=1; day["words_typed"]+=1
                    stop = is_stopword(word)
                    # Log avec flag stopword
                    kdata["words_log"].append({"t":now.isoformat(),"w":word,"app":app,"s":int(stop)})
                    if len(kdata["words_log"])>20000: kdata["words_log"]=kdata["words_log"][-20000:]
                    if not stop:
                        # Mot de contenu : incrémenter compteur et vocab
                        kdata["total"]["words_content"]=kdata["total"].get("words_content",0)+1
                        day["words_content"]=day.get("words_content",0)+1
                        # Stemming pour regrouper les variantes
                        s=stem(word)
                        vs=day.setdefault("vocab_stems",{})
                        if s not in vs:
                            vs[s]={"canonical":word,"count":1,"forms":{word:1}}
                        else:
                            vs[s]["count"]+=1
                            vs[s]["forms"][word]=vs[s]["forms"].get(word,0)+1
                            # Mettre à jour le mot canonique (le plus fréquent)
                            best=max(vs[s]["forms"],key=vs[s]["forms"].get)
                            vs[s]["canonical"]=best
            k_word_buf.clear()
        elif cat=="letter": k_word_buf.append(kn)
        elif cat=="delete" and k_word_buf: k_word_buf.pop()
        elif cat in("navigation","function"): k_word_buf.clear()
        if k_last_ts:
            iv=ts-k_last_ts
            if iv<5: k_intervals.append(round(iv,4))
        k_last_ts=ts

def on_key_release(key):
    kn=norm_key(key)
    with klock: k_held.discard(kn); k_modifiers.discard(kn)

def compute_wpm_1h():
    now=time.time(); cutoff=now-3600
    while k_keystroke_ts and k_keystroke_ts[0]<cutoff: k_keystroke_ts.popleft()
    if not k_keystroke_ts: return 0.0
    elapsed_min=min(60.0,max(1.0,(now-k_keystroke_ts[0])/60.0))
    return round(len(k_keystroke_ts)/5.0/elapsed_min,1)

# ══════════════════════════════════════════════════════════════════════
#  SAUVEGARDE PÉRIODIQUE
# ══════════════════════════════════════════════════════════════════════

def periodic_save():
    global m_total_dist
    while True:
        time.sleep(SAVE_INTERVAL)
        now=datetime.now().isoformat()
        try:
            with mlock:
                if m_click_intervals:
                    mdata["avg_click_interval_sec"]=round(sum(m_click_intervals)/len(m_click_intervals),3)
                mdata["total"]["distance_px"]+=int(m_total_dist); m_total_dist=0.0
                mdata["current_session"]={"start":session_start,"last_save":now}
                save_mouse()
        except Exception as e: print(f"[ERREUR mouse] {e}")
        try:
            with klock:
                if k_intervals:
                    kdata["avg_key_interval_sec"]=round(sum(k_intervals)/len(k_intervals),4)
                kdata["current_wpm"]=compute_wpm_1h()
                kdata["current_session"]={"start":session_start,"last_save":now}
                save_kb()
        except Exception as e: print(f"[ERREUR kb] {e}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Sauvegarde OK")

# ══════════════════════════════════════════════════════════════════════
#  SERVEUR HTTP
# ══════════════════════════════════════════════════════════════════════

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        p=self.path.split("?")[0]
        if   p=="/":         self._file(DASH_FILE,"text/html; charset=utf-8")
        elif p=="/mouse":
            with mlock: payload=json.dumps(mdata,ensure_ascii=False).encode("utf-8")
            self._json(payload)
        elif p=="/keyboard":
            with klock:
                kdata["current_wpm"]=compute_wpm_1h()
                payload=json.dumps(kdata,ensure_ascii=False).encode("utf-8")
            self._json(payload)
        elif p=="/status":
            with activity_lock:
                idle=int(time.time()-last_activity_ts); paused=in_pause
            payload=json.dumps({"idle_s":idle,"in_pause":paused,
                "current_app":current_app,"autostart":check_autostart()},
                ensure_ascii=False).encode("utf-8")
            self._json(payload)
        else: self.send_response(404); self.end_headers()

    def do_POST(self):
        p=self.path.split("?")[0]
        if p=="/autostart":
            length=int(self.headers.get("Content-Length",0))
            body=json.loads(self.rfile.read(length)) if length else {}
            if body.get("enable"): setup_autostart()
            else: remove_autostart()
            self._json(json.dumps({"ok":True,"autostart":check_autostart()}).encode())
        else: self.send_response(404); self.end_headers()

    def _json(self,payload):
        self.send_response(200)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(payload)))
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers(); self.wfile.write(payload)
    def _file(self,path,ct):
        try:
            c=open(path,"rb").read()
            self.send_response(200)
            self.send_header("Content-Type",ct)
            self.send_header("Content-Length",str(len(c)))
            self.end_headers(); self.wfile.write(c)
        except FileNotFoundError: self.send_response(404); self.end_headers()

def start_server():
    HTTPServer(("127.0.0.1",PORT),Handler).serve_forever()

# ══════════════════════════════════════════════════════════════════════
#  MINI WIDGET BARRE DES TÂCHES
# ══════════════════════════════════════════════════════════════════════

def run_widget():
    """
    Petite fenêtre flottante always-on-top affichant clics + frappes du jour.
    - Clic gauche  : ouvre le dashboard
    - Clic droit   : menu (position, quitter)
    - Drag         : déplaçable librement
    """
    try:
        import tkinter as tk
        from tkinter import font as tkfont
    except ImportError:
        print("[Widget] tkinter non disponible")
        return

    root = tk.Tk()
    root.title("Tracker")
    root.overrideredirect(True)          # sans bordure ni barre de titre
    root.attributes("-topmost", True)    # toujours au premier plan
    root.attributes("-alpha", 0.92)      # légère transparence
    root.configure(bg="#1e1b4b")

    # ── Couleurs ────────────────────────────────────────────────────
    BG      = "#1e1b4b"
    BG2     = "#2d2a5e"
    ACCENT1 = "#a5b4fc"   # violet clair — clics
    ACCENT2 = "#f9a8d4"   # rose clair  — frappes
    MUTED   = "#6b7280"
    WHITE   = "#f1f5f9"

    # ── Layout ──────────────────────────────────────────────────────
    frame = tk.Frame(root, bg=BG, padx=10, pady=6)
    frame.pack()

    # Colonne clics
    f_clicks = tk.Frame(frame, bg=BG)
    f_clicks.pack(side=tk.LEFT, padx=(0,8))
    lbl_clicks_val = tk.Label(f_clicks, text="—", fg=ACCENT1, bg=BG,
                               font=("Segoe UI", 14, "bold"), width=6, anchor="e")
    lbl_clicks_val.pack()
    lbl_clicks_lbl = tk.Label(f_clicks, text="🖱 clics", fg=MUTED, bg=BG,
                               font=("Segoe UI", 7), anchor="e")
    lbl_clicks_lbl.pack()

    # Séparateur
    tk.Label(frame, text="│", fg=BG2, bg=BG, font=("Segoe UI", 16)).pack(side=tk.LEFT, padx=2)

    # Colonne frappes
    f_keys = tk.Frame(frame, bg=BG)
    f_keys.pack(side=tk.LEFT, padx=(8,0))
    lbl_keys_val = tk.Label(f_keys, text="—", fg=ACCENT2, bg=BG,
                             font=("Segoe UI", 14, "bold"), width=6, anchor="w")
    lbl_keys_val.pack()
    lbl_keys_lbl = tk.Label(f_keys, text="⌨ touches", fg=MUTED, bg=BG,
                             font=("Segoe UI", 7), anchor="w")
    lbl_keys_lbl.pack()

    # ── Position initiale : coin bas-droit ──────────────────────────
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    ww = root.winfo_reqwidth()
    wh = root.winfo_reqheight()
    root.geometry(f"+{sw - ww - 8}+{sh - wh - 48}")

    # ── Drag ────────────────────────────────────────────────────────
    drag_data = {"x":0,"y":0}
    def on_drag_start(e): drag_data["x"]=e.x; drag_data["y"]=e.y
    def on_drag(e):
        dx=e.x-drag_data["x"]; dy=e.y-drag_data["y"]
        x=root.winfo_x()+dx; y=root.winfo_y()+dy
        root.geometry(f"+{x}+{y}")
    for w in (frame, f_clicks, f_keys, lbl_clicks_val, lbl_clicks_lbl, lbl_keys_val, lbl_keys_lbl):
        w.bind("<Button-1>",   on_drag_start)
        w.bind("<B1-Motion>",  on_drag)

    # ── Clic gauche = dashboard, clic droit = menu ──────────────────
    def open_dash(e=None):
        # Détection drag vs clic simple
        if abs(e.x-drag_data["x"])<5 and abs(e.y-drag_data["y"])<5:
            webbrowser.open(f"http://localhost:{PORT}")
    def show_menu(e):
        m = tk.Menu(root, tearoff=0, bg=BG, fg=WHITE, activebackground=BG2,
                    activeforeground=ACCENT1, font=("Segoe UI",9))
        m.add_command(label="📊 Ouvrir dashboard", command=lambda:webbrowser.open(f"http://localhost:{PORT}"))
        m.add_separator()
        m.add_command(label="📌 Épingler en haut à droite",
                      command=lambda:root.geometry(f"+{sw-ww-8}+8"))
        m.add_command(label="📌 Épingler en bas à droite",
                      command=lambda:root.geometry(f"+{sw-ww-8}+{sh-wh-48}"))
        m.add_command(label="📌 Épingler en bas à gauche",
                      command=lambda:root.geometry(f"+8+{sh-wh-48}"))
        m.add_separator()
        # Toggle opacité
        m.add_command(label="🔆 Opacité 100%",  command=lambda:root.attributes("-alpha",1.0))
        m.add_command(label="🔅 Opacité 80%",   command=lambda:root.attributes("-alpha",0.8))
        m.add_command(label="🌑 Opacité 50%",   command=lambda:root.attributes("-alpha",0.5))
        m.add_separator()
        m.add_command(label="❌ Quitter le tracker",
                      command=lambda:(save_mouse(), save_kb(), os._exit(0)))
        try: m.tk_popup(e.x_root, e.y_root)
        finally: m.grab_release()

    for w in (frame, f_clicks, f_keys, lbl_clicks_val, lbl_clicks_lbl, lbl_keys_val, lbl_keys_lbl):
        w.bind("<ButtonRelease-1>", open_dash)
        w.bind("<Button-3>",        show_menu)

    # ── Hover effet ─────────────────────────────────────────────────
    def on_enter(e): root.configure(bg="#2d2a5e"); frame.configure(bg="#2d2a5e")
    def on_leave(e): root.configure(bg=BG);        frame.configure(bg=BG)
    frame.bind("<Enter>", on_enter); frame.bind("<Leave>", on_leave)

    # ── Mise à jour des valeurs ─────────────────────────────────────
    def update_vals():
        today = datetime.now().strftime("%Y-%m-%d")
        # Clics du jour
        with mlock:
            md = mdata.get("daily_stats",{}).get(today,{})
            clicks = md.get("total_clicks",0)
        # Frappes du jour
        with klock:
            kd = kdata.get("daily_stats",{}).get(today,{})
            keys = kd.get("keystrokes",0)

        # Format : 1 234
        def fmt(n): return f"{n:,}".replace(",","\u202f")  # espace fine

        lbl_clicks_val.config(text=fmt(clicks))
        lbl_keys_val.config(text=fmt(keys))

        # Couleur selon intensité (vert si au-dessus de la moyenne, normal sinon)
        root.after(3000, update_vals)  # refresh toutes les 3s

    update_vals()
    root.mainloop()


session_start=datetime.now().isoformat()

if __name__=="__main__":
    print(f"\nActivity Tracker — http://localhost:{PORT}")
    print(f"Autostart : {'OUI' if check_autostart() else 'NON'}")
    print(f"Tray      : {'OUI' if HAS_TRAY else 'NON (pip install pystray pillow)'}\n")

    save_mouse(); save_kb()

    threading.Thread(target=periodic_save, daemon=True).start()
    threading.Thread(target=start_server,  daemon=True).start()
    threading.Thread(target=watch_screens, daemon=True).start()
    threading.Thread(target=watch_power,   daemon=True).start()
    threading.Thread(target=watch_pauses,  daemon=True).start()
    threading.Thread(target=watch_app,     daemon=True).start()

    ml=pmouse.Listener(on_click=on_mouse_click,on_move=on_mouse_move,on_scroll=on_mouse_scroll)
    kl=pkeyboard.Listener(on_press=on_key_press,on_release=on_key_release)
    ml.start(); kl.start()

    if HAS_TRAY:
        # Tray dans un thread dédié
        threading.Thread(target=run_tray, daemon=True).start()

    # Widget tkinter — tourne dans le thread principal (obligatoire sur Windows)
    run_widget()

