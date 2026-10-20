"""
LAN Gamepad Server for Songoku 7
- Run this script on the PC that is running the game.
- Open the displayed LAN URL on phones/tablets connected to the same Wi-Fi.
- Select Player 1 or Player 2. Hold buttons to hold keys; release to release keys.
- Bấm ⚙ trên điện thoại để tự thêm/xóa nút, cần di chuyển, đổi phím, đổi kích cỡ và kéo vị trí.

Install:
    py -m pip install flask flask-socketio pynput

Run:
    py gamepad.py
"""

from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
from pynput.keyboard import Controller, Key, KeyCode
import socket
import threading

app = Flask(__name__)
app.config["SECRET_KEY"] = "lan-gamepad-local"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
keyboard = Controller()
key_lock = threading.Lock()

# Phím cho phép. Trình duyệt chỉ được gửi các tên phím có trong danh sách này.
# Người dùng tự tạo nút trên điện thoại và chọn phím trong danh sách (giữ đồng bộ với KEY_GROUPS trong PAGE).
KEY_MAP = {}
for _c in "abcdefghijklmnopqrstuvwxyz":
    KEY_MAP[_c] = _c
for _d in range(10):
    # Phím số: gửi cả phím số hàng trên lẫn bàn phím số (Numpad) để game nào cũng nhận.
    KEY_MAP[str(_d)] = (str(_d), KeyCode.from_vk(0x60 + _d))
    # "numN": chỉ gửi Numpad.
    KEY_MAP[f"num{_d}"] = KeyCode.from_vk(0x60 + _d)
for _n in range(1, 13):
    KEY_MAP[f"f{_n}"] = getattr(Key, f"f{_n}")
KEY_MAP.update({
    "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
    "space": Key.space, "enter": Key.enter, "tab": Key.tab, "esc": Key.esc,
    "shift": Key.shift, "ctrl": Key.ctrl, "alt": Key.alt, "backspace": Key.backspace,
    "shift_r": Key.shift_r, "ctrl_r": Key.ctrl_r, "alt_r": Key.alt_r,
    # Điều hướng / chỉnh sửa
    "delete": Key.delete, "insert": Key.insert, "home": Key.home, "end": Key.end,
    "pageup": Key.page_up, "pagedown": Key.page_down, "capslock": Key.caps_lock,
    # Ký tự đặc biệt (dấu câu trên bàn phím chính)
    "minus": "-", "equals": "=", "lbracket": "[", "rbracket": "]", "backslash": "\\",
    "semicolon": ";", "quote": "'", "comma": ",", "period": ".", "slash": "/", "grave": "`",
    # Numpad: phép tính và dấu chấm
    "nummul": KeyCode.from_vk(0x6A), "numadd": KeyCode.from_vk(0x6B), "numsub": KeyCode.from_vk(0x6D),
    "numdec": KeyCode.from_vk(0x6E), "numdiv": KeyCode.from_vk(0x6F),
})


def hw_press(key_name):
    keys = KEY_MAP[key_name]
    for k in keys if isinstance(keys, tuple) else (keys,):
        keyboard.press(k)


def hw_release(key_name):
    keys = KEY_MAP[key_name]
    for k in keys if isinstance(keys, tuple) else (keys,):
        keyboard.release(k)

# Track pressed keys by socket so disconnecting a phone cannot leave keys stuck.
pressed_by_sid = {}


def get_lan_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def press_key(key_name):
    if key_name not in KEY_MAP:
        return
    with key_lock:
        hw_press(key_name)


def release_key(key_name):
    if key_name not in KEY_MAP:
        return
    with key_lock:
        hw_release(key_name)


@app.route("/")
def index():
    return render_template_string(PAGE)


@socketio.on("key_down")
def on_key_down(data):
    key_name = str((data or {}).get("key", "")).lower()
    if key_name not in KEY_MAP:
        return
    sid = request.sid
    with key_lock:
        already_pressed = key_name in pressed_by_sid.setdefault(sid, set())
        if not already_pressed:
            pressed_by_sid[sid].add(key_name)
            hw_press(key_name)
            print(f"[key_down] {key_name}")
    emit("status", {"text": "Đã kết nối · đang điều khiển"}, to=sid)


@socketio.on("key_up")
def on_key_up(data):
    key_name = str((data or {}).get("key", "")).lower()
    if key_name not in KEY_MAP:
        return
    sid = request.sid
    with key_lock:
        # Release the physical key only if no other phone/socket is holding it.
        if sid in pressed_by_sid:
            pressed_by_sid[sid].discard(key_name)
        still_held = any(key_name in keys for keys in pressed_by_sid.values())
        if not still_held:
            hw_release(key_name)
            print(f"[key_up]   {key_name}")


@socketio.on("release_all")
def on_release_all():
    sid = request.sid
    with key_lock:
        keys = pressed_by_sid.pop(sid, set())
        for key_name in keys:
            if not any(key_name in other for other in pressed_by_sid.values()):
                hw_release(key_name)


@socketio.on("disconnect")
def on_disconnect():
    on_release_all()


PAGE = r"""
<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#000000">
<title>Controller</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<style>
:root { color-scheme: dark; --bg:#000; --fg:#fff; --panel:#111; --vh:100dvh; --vw:100vw; }
* { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
html,body { -webkit-touch-callout:none; -webkit-user-select:none; user-select:none; width:100%; height:100%; margin:0; background:var(--bg); color:var(--fg); font-family:Arial,sans-serif; overflow:hidden; touch-action:manipulation; }
body { min-height:100dvh; }
#choose { width:100%; height:100%; display:flex; flex-direction:column; gap:12px; align-items:center; justify-content:center; }
.choice { width:min(260px,80vw); padding:14px 20px; text-align:center; border:1px solid #777; color:#fff; background:#111; font-size:18px; font-weight:600; user-select:none; cursor:pointer; }
.choice:active { background:#fff; color:#000; }
#controller { position:relative; display:none; width:100%; height:var(--vh); }
#controller.active { display:block; }
/* Toàn bộ màn hình là khung tự do: nút và cần di chuyển đặt theo toạ độ % */
#free { position:absolute; inset:max(8px, env(safe-area-inset-top)) max(8px, env(safe-area-inset-right)) max(8px, env(safe-area-inset-bottom)) max(8px, env(safe-area-inset-left)); }
#controller.editing #free { outline:2px dashed #444; background:repeating-linear-gradient(0deg,transparent 0 31px,#161616 31px 32px),repeating-linear-gradient(90deg,transparent 0 31px,#161616 31px 32px); }
#status { pointer-events:none; opacity:.6; color:#f33; font-size:clamp(16px,calc(var(--vh) * 0.06),28px); font-weight:700; line-height:1; text-align:center; user-select:none; }
#status.ok { color:#2e6; }
.key { min-width:0; min-height:0; border:1px solid #777; background:var(--panel); color:#fff; border-radius:0; font-weight:600; touch-action:none; user-select:none; }
.key:active,.key.down { background:#fff; color:#000; }
.item { position:absolute; z-index:1; transform:translate(-50%,-50%); touch-action:none; }
.key.item { padding:0; overflow:hidden; }
.joy { border-radius:50%; border:2px solid #777; background:radial-gradient(circle, rgba(255,255,255,.07), rgba(255,255,255,.015) 70%); }
.knob { position:absolute; left:50%; top:50%; width:40%; height:40%; border-radius:50%; background:rgba(255,255,255,.3); border:2px solid #bbb; transform:translate(-50%,-50%); pointer-events:none; }
#controller.editing .item { border:2px dashed #fa0; }
#controller.editing .item.sel { border:2px solid #fa0; box-shadow:0 0 0 3px rgba(255,170,0,.35); }
#handle { display:none; position:absolute; z-index:8; width:28px; height:28px; border-radius:50%; background:#fa0; border:3px solid #000; transform:translate(-50%,-50%); touch-action:none; }
#handle.show { display:block; }
#hint { display:none; position:absolute; left:50%; transform:translateX(-50%); top:calc(max(6px, env(safe-area-inset-top)) + 40px); z-index:3; width:max-content; max-width:90%; font-size:12px; line-height:1.4; color:#999; text-align:center; pointer-events:none; }
#controller.editing #hint { display:block; }
/* P1/P2 và nút ⚙ nằm giữa phía trên để không cản vùng chơi */
#toolbar { position:absolute; top:max(6px, env(safe-area-inset-top)); left:50%; transform:translateX(-50%); z-index:5; display:flex; gap:6px; align-items:center; width:max-content; max-width:96%; }
#toolbar button, #editbar button { min-width:34px; height:34px; padding:0 8px; border:1px solid #777; background:#111; color:#fff; font-size:15px; }
#toolbar button { opacity:.45; }
#controller.editing #toolbar button { opacity:1; }
#editTools { display:none; gap:6px; }
#controller.editing #editTools { display:flex; }
#editbar { display:none; position:absolute; left:50%; bottom:max(6px, env(safe-area-inset-bottom)); transform:translateX(-50%); z-index:6; width:max-content; max-width:96%; flex-wrap:wrap; gap:6px; align-items:center; justify-content:center; padding:6px 8px; background:rgba(17,17,17,.96); border:1px solid #888; }
#editbar.open { display:flex; }
#editbar input[type=text] { height:34px; font-size:15px; background:#000; color:#fff; border:1px solid #777; padding:0 6px; }
#ebKeys { display:flex; gap:6px; align-items:center; }
#ebKeys span { font-size:13px; color:#bbb; }
#editbar .kbtn { min-width:52px; border-color:#fa0; font-weight:700; }
#editbar .kbtn.empty { color:#fa0; font-weight:400; }
#keypicker { display:none; position:absolute; inset:0; z-index:20; background:rgba(0,0,0,.9); }
#keypicker.open { display:flex; flex-direction:column; }
#pkHead { flex:none; display:flex; justify-content:space-between; align-items:center; padding:8px 12px; font-size:15px; color:#bbb; }
#pkHead button { height:34px; padding:0 14px; border:1px solid #777; background:#111; color:#fff; font-size:15px; }
/* pan-x pan-y: khi giao diện xoay 90° thì vuốt dọc trong giao diện là vuốt ngang trên màn hình thật */
#pkBody { flex:1; min-height:0; overflow-y:auto; padding:0 12px 12px; touch-action:pan-x pan-y; -webkit-overflow-scrolling:touch; overscroll-behavior:contain; }
#pkTabs { flex:none; display:flex; flex-wrap:wrap; gap:6px; padding:0 12px 6px; }
#pkTabs button { height:30px; padding:0 10px; border:1px solid #fa0; background:#111; color:#fa0; font-size:13px; }
.pkTitle { margin:12px 0 6px; font-size:13px; color:#888; }
.pkWrap { display:flex; flex-wrap:wrap; gap:6px; }
.pk { min-width:48px; height:44px; padding:0 8px; border:1px solid #666; background:#151515; color:#fff; font-size:16px; font-weight:600; line-height:1.1; white-space:pre-line; }
.pk small { font-size:10px; font-weight:400; }
.pk.cur { background:#fa0; color:#000; border-color:#fa0; }
.pk.wide { width:100%; }
#ebSize { width:80px; }
#editbar .sep { width:1px; height:24px; background:#555; }
#ebDel { color:#f66; }
#ebClose { background:#fff !important; color:#000 !important; }
/* Máy đang cầm dọc: xoay giao diện 90° để luôn hiển thị nằm ngang */
@media (orientation:portrait) {
  :root { --vh:100vw; --vw:100dvh; }
  #controller.active { position:fixed; top:0; left:0; width:100dvh; height:100vw; transform-origin:top left; transform:translateX(100vw) rotate(90deg); }
}
</style>
</head>
<body>
<div id="choose">
  <button class="choice" data-player="1">Người chơi 1</button>
  <button class="choice" data-player="2">Người chơi 2</button>
</div>
<div id="controller">
  <div id="free"><div id="handle"></div></div>
  <div id="hint">Kéo để di chuyển · chạm để chọn · kéo chấm cam để đổi cỡ</div>
  <div id="toolbar">
    <div id="status">P1</div>
    <span id="editTools">
      <button id="btnAdd">+ Nút</button>
      <button id="btnAddJoy">+ Cần</button>
      <button id="btnReset">Đặt lại</button>
    </span>
    <button id="btnEdit" title="Chỉnh bố cục nút">⚙</button>
  </div>
  <div id="editbar">
    <span id="ebKeys"></span>
    <span class="sep"></span>
    <button id="ebMinus">−</button>
    <input id="ebSize" type="range" step="1">
    <button id="ebPlus">+</button>
    <span class="sep"></span>
    <button id="ebDel">Xóa</button>
    <button id="ebClose">OK</button>
  </div>
  <div id="keypicker">
    <div id="pkHead"><span>Chọn phím cho nút</span><button id="pkClose">Đóng</button></div>
    <div id="pkTabs"></div>
    <div id="pkBody"></div>
  </div>
</div>
<script>
const socket = io();
const statusEl = document.getElementById('status');
let player = 1;
let connected = false;
function updateStatus() {
  statusEl.textContent = 'P' + player;
  statusEl.classList.toggle('ok', connected);
}
socket.on('connect', () => { connected = true; updateStatus(); });
socket.on('disconnect', () => { connected = false; updateStatus(); });
const free = document.getElementById('free');
const handle = document.getElementById('handle');
const controllerEl = document.getElementById('controller');
const activeButtons = new Map();
const resetters = [];
let editMode = false;
let layout = [];
let selected = null;

// Danh sách phím chọn được (khớp KEY_MAP phía server)
const ARROW_LABEL = {up:'↑', down:'↓', left:'←', right:'→'};
const SHORT_LABEL = {
  space:'␣', enter:'⏎', backspace:'⌫', shift:'⇧', ctrl:'Ctl', alt:'Alt', tab:'Tab', esc:'Esc',
  shift_r:'⇧R', ctrl_r:'CtlR', alt_r:'AltR',
  delete:'Del', insert:'Ins', home:'Home', end:'End', pageup:'PgUp', pagedown:'PgDn', capslock:'Caps',
  minus:'-', equals:'=', lbracket:'[', rbracket:']', backslash:'\\', semicolon:';', quote:"'", comma:',', period:'.', slash:'/', grave:'`',
  nummul:'N×', numadd:'N+', numsub:'N−', numdec:'N.', numdiv:'N÷',
};
const KEY_GROUPS = [
  ['Chữ cái', 'abcdefghijklmnopqrstuvwxyz'.split('')],
  ['Số', '0123456789'.split('')],
  ['Mũi tên', ['up','down','left','right']],
  ['Đặc biệt', ['space','enter','shift','ctrl','alt','tab','esc','backspace','shift_r','ctrl_r','alt_r']],
  ['Ký tự đặc biệt', ['minus','equals','lbracket','rbracket','backslash','semicolon','quote','comma','period','slash','grave']],
  ['Điều hướng', ['delete','insert','home','end','pageup','pagedown','capslock']],
  ['F1–F12', Array.from({length:12}, (_, i) => 'f' + (i + 1))],
  ['Numpad (chỉ bàn phím số)', [...Array.from({length:10}, (_, i) => 'num' + i), 'nummul','numadd','numsub','numdec','numdiv']],
];
const VALID_KEYS = new Set(KEY_GROUPS.flatMap(g => g[1]));
function keyLabel(key) { return !key ? '?' : ARROW_LABEL[key] || SHORT_LABEL[key] || (key.startsWith('num') ? 'N' + key.slice(3) : key.toUpperCase()); }
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const portraitRot = () => window.matchMedia('(orientation:portrait)').matches;
// Giao diện xoay 90° khi cầm dọc: đổi trục của vector kéo cho khớp
const localDelta = (dx, dy) => portraitRot() ? [dy, -dx] : [dx, dy];
const SIZE_RANGE = {btn:[10, 40], joy:[30, 90]};

async function enterFullscreenLandscape() {
  try {
    if (screen.orientation && screen.orientation.lock) {
      await screen.orientation.lock('landscape');
    }
  } catch (_) {}
  try {
    if (!document.fullscreenElement && document.documentElement.requestFullscreen) {
      await document.documentElement.requestFullscreen();
    }
  } catch (_) {}
}
function releaseAllLocal() {
  socket.emit('release_all');
  activeButtons.clear();
  document.querySelectorAll('.key.down').forEach(b => b.classList.remove('down'));
  resetters.forEach(f => f());
}
// Đếm số nguồn đang giữ cùng một phím (nhiều ngón / nút + cần cùng phím)
function holdKey(key) {
  if (!key) return;
  const count = (activeButtons.get(key) || 0) + 1;
  activeButtons.set(key, count);
  if (count === 1) socket.emit('key_down', {key});
}
function unholdKey(key) {
  if (!key) return;
  const count = Math.max(0, (activeButtons.get(key) || 1) - 1);
  if (!count) {
    activeButtons.delete(key);
    socket.emit('key_up', {key});
  } else activeButtons.set(key, count);
}
function makeButton(label, key) {
  const b = document.createElement('button');
  b.className = 'key';
  b.textContent = label;
  b.dataset.key = key;
  const down = e => {
    e.preventDefault();
    if (editMode || b.classList.contains('down')) return;
    b.classList.add('down');
    try { b.setPointerCapture(e.pointerId); } catch (_) {}
    holdKey(key);
  };
  const up = e => {
    e.preventDefault();
    if (!b.classList.contains('down')) return;
    b.classList.remove('down');
    unholdKey(key);
  };
  b.addEventListener('pointerdown', down);
  ['pointerup','pointercancel','lostpointercapture'].forEach(ev => b.addEventListener(ev, up));
  // Giữ lâu trên điện thoại sinh contextmenu: chỉ chặn menu, không nhả phím
  b.addEventListener('contextmenu', e => e.preventDefault());
  return b;
}

// Cần di chuyển tròn (kiểu Liên Quân): kéo núm, hướng kéo ↔ phím [trên, trái, phải, dưới], hỗ trợ chéo (giữ 2 phím)
function makeJoystick(it) {
  const base = document.createElement('div');
  base.className = 'joy item';
  const knob = document.createElement('div');
  knob.className = 'knob';
  base.append(knob);
  let pid = null;
  let held = new Set();
  const centerKnob = () => { knob.style.transform = 'translate(-50%,-50%)'; };
  const setHeld = next => {
    held.forEach(k => { if (!next.has(k)) unholdKey(k); });
    next.forEach(k => { if (!held.has(k)) holdKey(k); });
    held = next;
  };
  const update = e => {
    const r = base.getBoundingClientRect();
    const [dx, dy] = localDelta(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2));
    const R = base.offsetWidth / 2;
    const dist = Math.hypot(dx, dy);
    const k = dist > R * 0.6 ? R * 0.6 / dist : 1;
    knob.style.transform = 'translate(calc(-50% + ' + dx * k + 'px), calc(-50% + ' + dy * k + 'px))';
    const next = new Set();
    if (dist > R * 0.2) {
      const nx = dx / dist, ny = dy / dist;
      if (ny < -0.38) next.add(it.keys[0]);
      if (nx < -0.38) next.add(it.keys[1]);
      if (nx > 0.38) next.add(it.keys[2]);
      if (ny > 0.38) next.add(it.keys[3]);
    }
    setHeld(next);
  };
  const release = () => { pid = null; setHeld(new Set()); centerKnob(); };
  base.addEventListener('pointerdown', e => {
    e.preventDefault();
    if (editMode || pid !== null) return;
    pid = e.pointerId;
    try { base.setPointerCapture(pid); } catch (_) {}
    update(e);
  });
  base.addEventListener('pointermove', e => {
    if (editMode || e.pointerId !== pid) return;
    e.preventDefault();
    update(e);
  });
  ['pointerup','pointercancel','lostpointercapture'].forEach(ev => base.addEventListener(ev, e => {
    if (e.pointerId === pid) release();
  }));
  base.addEventListener('contextmenu', e => e.preventDefault());
  // releaseAllLocal đã báo server nhả hết phím: chỉ cần quên trạng thái cục bộ
  resetters.push(() => { held = new Set(); pid = null; centerKnob(); });
  return base;
}

// ---- Bố cục (lưu theo từng người chơi) ----
const storeKey = () => 'gp_layout_v2_p' + player;
// Mặc định chỉ có cần di chuyển; các nút bên phải do người dùng tự tạo
function defaultLayout() {
  const keys = player === 1 ? ['w','a','d','s'] : ['up','left','right','down'];
  return [{type:'joy', keys, x:17, y:60, s:55}];
}
function loadLayout() {
  try {
    const arr = JSON.parse(localStorage.getItem(storeKey()) || 'null');
    if (Array.isArray(arr)) {
      const out = [];
      arr.forEach(it => {
        if (!it) return;
        const type = it.type === 'joy' ? 'joy' : 'btn';
        const [lo, hi] = SIZE_RANGE[type];
        const base = {type, x:clamp(Number(it.x) || 0, 0, 100), y:clamp(Number(it.y) || 0, 0, 100), s:clamp(Number(it.s) || 18, lo, hi)};
        if (type === 'joy') {
          if (Array.isArray(it.keys) && it.keys.length === 4 && it.keys.every(k => VALID_KEYS.has(k))) out.push({...base, keys:it.keys.slice()});
        } else if (it.key === '' || VALID_KEYS.has(it.key)) {
          out.push({...base, key:it.key, label:''});
        }
      });
      return out;
    }
  } catch (_) {}
  return defaultLayout();
}
function saveLayout() {
  try {
    localStorage.setItem(storeKey(), JSON.stringify(layout.map(it => {
      const o = {type:it.type, x:it.x, y:it.y, s:it.s};
      if (it.type === 'joy') o.keys = it.keys; else { o.key = it.key; o.label = it.label; }
      return o;
    })));
  } catch (_) {}
}
function place(it) {
  const el = it.el;
  el.style.left = it.x + '%';
  el.style.top = it.y + '%';
  const size = 'calc(var(--vh) * ' + (it.s / 100) + ')';
  el.style.width = size;
  el.style.height = size;
  if (it.type === 'btn') {
    el.style.fontSize = 'calc(var(--vh) * ' + (it.s / 100 * 0.38) + ')';
    el.textContent = it.label || keyLabel(it.key);
  }
}

// ---- Chỉnh sửa: chọn, kéo, đổi cỡ ----
function positionHandle() {
  const show = editMode && selected && selected.el;
  handle.classList.toggle('show', !!show);
  if (!show) return;
  const el = selected.el;
  const off = el.offsetWidth / 2 * (selected.type === 'joy' ? 0.7071 : 1);
  handle.style.left = (selected.x / 100 * free.offsetWidth + off) + 'px';
  handle.style.top = (selected.y / 100 * free.offsetHeight + off) + 'px';
}
function applySelection() {
  layout.forEach(it => it.el && it.el.classList.toggle('sel', it === selected));
  positionHandle();
  fillBar();
}
function select(it) { selected = it; applySelection(); }
function attachEdit(it) {
  const el = it.el;
  let drag = null;
  el.addEventListener('pointerdown', e => {
    if (!editMode) return;
    e.preventDefault();
    try { el.setPointerCapture(e.pointerId); } catch (_) {}
    drag = {id:e.pointerId, sx:e.clientX, sy:e.clientY, x:it.x, y:it.y, moved:false};
    if (selected !== it) select(it);
  });
  el.addEventListener('pointermove', e => {
    if (!editMode || !drag || e.pointerId !== drag.id) return;
    const [dx, dy] = localDelta(e.clientX - drag.sx, e.clientY - drag.sy);
    if (!drag.moved && Math.hypot(dx, dy) < 6) return;
    drag.moved = true;
    it.x = clamp(drag.x + dx / free.offsetWidth * 100, 0, 100);
    it.y = clamp(drag.y + dy / free.offsetHeight * 100, 0, 100);
    place(it);
    positionHandle();
  });
  const end = e => {
    if (!drag || e.pointerId !== drag.id) return;
    const moved = drag.moved;
    drag = null;
    if (moved) saveLayout();
  };
  el.addEventListener('pointerup', end);
  el.addEventListener('pointercancel', end);
}
let hDrag = null;
handle.addEventListener('pointerdown', e => {
  if (!editMode || !selected) return;
  e.preventDefault();
  e.stopPropagation();
  try { handle.setPointerCapture(e.pointerId); } catch (_) {}
  hDrag = e.pointerId;
});
handle.addEventListener('pointermove', e => {
  if (e.pointerId !== hDrag || !selected) return;
  const it = selected, el = it.el;
  const r = el.getBoundingClientRect();
  const [dx, dy] = localDelta(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2));
  const half = it.type === 'joy' ? Math.hypot(dx, dy) : Math.max(Math.abs(dx), Math.abs(dy));
  const vhPx = el.offsetWidth / (it.s / 100);
  const [lo, hi] = SIZE_RANGE[it.type];
  it.s = Math.round(clamp(2 * half / vhPx * 100, lo, hi) * 10) / 10;
  place(it);
  positionHandle();
  ebSize.value = it.s;
});
['pointerup','pointercancel'].forEach(ev => handle.addEventListener(ev, e => {
  if (e.pointerId !== hDrag) return;
  hDrag = null;
  saveLayout();
}));
free.addEventListener('pointerdown', e => { if (editMode && e.target === free) select(null); });

// ---- Thanh chỉnh sửa (thay đổi áp dụng ngay) ----
const bar = document.getElementById('editbar');
const ebKeys = document.getElementById('ebKeys');
const ebSize = document.getElementById('ebSize');
// Bảng chọn phím tự vẽ (không dùng <select> gốc vì hộp chọn của hệ điều hành không xoay theo giao diện)
const picker = document.getElementById('keypicker');
const pkBody = document.getElementById('pkBody');
const pkTabs = document.getElementById('pkTabs');
function closePicker() { picker.classList.remove('open'); }
function openPicker(current, onPick) {
  pkBody.innerHTML = '';
  pkTabs.innerHTML = '';
  const choose = k => { closePicker(); onPick(k); };
  const mk = (k, text) => {
    const b = document.createElement('button');
    b.className = 'pk' + (k === current ? ' cur' : '');
    b.textContent = text;
    b.addEventListener('click', () => choose(k));
    return b;
  };
  const none = mk('', 'Không gán phím');
  none.classList.add('wide');
  pkBody.append(none);
  KEY_GROUPS.forEach(([name, keys]) => {
    const t = document.createElement('div');
    t.className = 'pkTitle';
    t.textContent = name;
    const wrap = document.createElement('div');
    wrap.className = 'pkWrap';
    keys.forEach(k => {
      const label = keyLabel(k);
      wrap.append(mk(k, k.length > 1 && label.toLowerCase() !== k ? label + '\n' + k : label));
    });
    pkBody.append(t, wrap);
    // Nút nhảy nhanh tới nhóm phím (phòng khi không cuộn được)
    const tab = document.createElement('button');
    tab.textContent = name;
    tab.addEventListener('click', () => { pkBody.scrollTop = t.offsetTop - pkBody.offsetTop - 4; });
    pkTabs.append(tab);
  });
  picker.classList.add('open');
  const cur = pkBody.querySelector('.cur');
  if (cur) cur.scrollIntoView({block:'center'});
}
document.getElementById('pkClose').addEventListener('click', closePicker);
picker.addEventListener('pointerdown', e => { if (e.target === picker) closePicker(); });
// Nút hiện phím đang gán; chạm để mở bảng chọn
function keyButton(value, onChange) {
  const b = document.createElement('button');
  b.className = 'kbtn';
  const show = v => { b.textContent = v ? keyLabel(v) : '? chọn'; b.classList.toggle('empty', !v); };
  show(value);
  b.addEventListener('click', () => openPicker(value, v => { value = v; show(v); onChange(v); }));
  return b;
}
function fillBar() {
  const it = selected;
  bar.classList.toggle('open', !!(editMode && it));
  if (!(editMode && it)) return;
  const joy = it.type === 'joy';
  ebKeys.innerHTML = '';
  if (joy) {
    ['↑','←','→','↓'].forEach((arrow, i) => {
      const t = document.createElement('span');
      t.textContent = arrow;
      ebKeys.append(t, keyButton(it.keys[i], v => { it.keys[i] = v; saveLayout(); }));
    });
  } else {
    const t = document.createElement('span');
    t.textContent = 'Phím';
    ebKeys.append(t, keyButton(it.key, v => { it.key = v; saveLayout(); renderFree(); }));
  }
  const [lo, hi] = SIZE_RANGE[it.type];
  ebSize.min = lo; ebSize.max = hi;
  ebSize.value = it.s;
}
function setSize(v) {
  if (!selected) return;
  const [lo, hi] = SIZE_RANGE[selected.type];
  selected.s = clamp(Number(v), lo, hi);
  ebSize.value = selected.s;
  place(selected);
  positionHandle();
  saveLayout();
}
ebSize.addEventListener('input', () => setSize(ebSize.value));
document.getElementById('ebMinus').addEventListener('click', () => setSize((selected ? selected.s : 0) - 2));
document.getElementById('ebPlus').addEventListener('click', () => setSize((selected ? selected.s : 0) + 2));
document.getElementById('ebDel').addEventListener('click', () => {
  if (!selected) return;
  layout = layout.filter(x => x !== selected);
  selected = null;
  saveLayout();
  renderFree();
});
document.getElementById('ebClose').addEventListener('click', () => select(null));

function renderFree() {
  free.querySelectorAll('.item').forEach(el => el.remove());
  resetters.length = 0;
  layout.forEach(it => {
    it.el = it.type === 'joy' ? makeJoystick(it) : makeButton(it.label || keyLabel(it.key), it.key);
    it.el.classList.add('item');
    place(it);
    attachEdit(it);
    free.append(it.el);
  });
  applySelection();
}
function render() {
  updateStatus();
  layout = loadLayout();
  selected = null;
  renderFree();
}
function setEditMode(on) {
  editMode = on;
  releaseAllLocal();
  controllerEl.classList.toggle('editing', on);
  document.getElementById('btnEdit').textContent = on ? 'Xong' : '⚙';
  if (!on) selected = null;
  applySelection();
}
document.getElementById('btnEdit').addEventListener('click', () => setEditMode(!editMode));
function addItem(it) {
  // Lệch dần khỏi các item đã có để nút mới không đè kín nút cũ
  for (let i = 0; i < 20 && layout.some(o => Math.abs(o.x - it.x) < 3 && Math.abs(o.y - it.y) < 4); i++) {
    it.x = it.x > 85 ? 40 : it.x + 4;
    it.y = it.y > 80 ? 40 : it.y + 6;
  }
  layout.push(it);
  selected = it;
  saveLayout();
  renderFree();
}
document.getElementById('btnAdd').addEventListener('click', () => addItem({type:'btn', label:'', key:'', x:50, y:50, s:18}));
document.getElementById('btnAddJoy').addEventListener('click', () => addItem({type:'joy', keys:['w','a','d','s'], x:50, y:50, s:50}));
// Xác nhận ngay trên nút (confirm() gốc không xoay theo giao diện): bấm lần 2 trong 3 giây để đặt lại
let resetTimer = null;
document.getElementById('btnReset').addEventListener('click', e => {
  const btn = e.currentTarget;
  if (resetTimer === null) {
    btn.textContent = 'Chắc chắn?';
    resetTimer = setTimeout(() => { resetTimer = null; btn.textContent = 'Đặt lại'; }, 3000);
    return;
  }
  clearTimeout(resetTimer);
  resetTimer = null;
  btn.textContent = 'Đặt lại';
  layout = defaultLayout();
  selected = null;
  saveLayout();
  renderFree();
});
document.querySelectorAll('.choice').forEach(btn => btn.addEventListener('click', async () => {
  player = Number(btn.dataset.player);
  document.getElementById('choose').style.display = 'none';
  document.getElementById('controller').classList.add('active');
  render();
  await enterFullscreenLandscape();
}));
// Đã thoát toàn màn hình: chạm vào bất kỳ đâu sẽ vào lại toàn màn hình
document.addEventListener('pointerup', () => {
  if (document.getElementById('controller').classList.contains('active') && !document.fullscreenElement) {
    enterFullscreenLandscape();
  }
});
window.addEventListener('resize', positionHandle);
window.addEventListener('blur', releaseAllLocal);
document.addEventListener('visibilitychange', () => { if (document.hidden) releaseAllLocal(); });
window.addEventListener('pagehide', releaseAllLocal);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    ip = get_lan_ip()
    print("\nMo tren PC:  http://127.0.0.1:5000")
    print(f"Mo tren dien thoai cung Wi-Fi: http://{ip}:5000")
    print("Nhan Ctrl+C de dung server.\n")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
