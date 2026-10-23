"""
小深 · DeepSeek 桌宠
常驻 Windows 桌面的 Q 版鲸鱼娘女仆桌宠：
- 透明无边框窗口、始终置顶、可拖动、滚轮调大小
- 10 种表情（常驻 / 开心 / 生气 / 无语 / 委屈 / 惊讶 / 害羞 / 舒服 / 饥饿 / 吃饭），
  全部共用常驻的身体与发型，只换脸，切换自然
- 摸摸：按住不动即进入摸摸模式，动一动就是一下，会切到舒服表情
- 底部偷窥：把她拖到屏幕最底下松手，她会变成一颗小脑袋趴在任务栏上，
  带糯叽叽的 Q 弹落座动画；抓着脑袋往上拽或点一下就弹回全身
- 饭点感应：到点自动饥饿，右键「喂饭」喂一碗大米饭
- 冒气泡说话、双击呼出输入框，接入 DeepSeek API 真聊天
- 右键菜单：聊天 / 说句话 / 摸摸 / 喂饭 / 表情 / 大小 / 设置 / 退出
"""

import sys
import os
import json
import math
import time
import random
from pathlib import Path

from PySide6.QtCore import (
    Qt, QTimer, QPoint, QRect, QRectF, QThread, Signal, QSize,
)
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPainterPath, QFont, QFontMetrics,
    QIcon, QRegion, QPen, QBrush, QGuiApplication,
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QLineEdit, QPushButton, QFrame,
    QVBoxLayout, QHBoxLayout, QMenu, QSystemTrayIcon, QDialog,
    QLabel, QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout,
    QToolButton,
)

APP_NAME = "小深 · DeepSeek 桌宠"
PET_NAME = "小深"

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
ASSETS = ROOT / "assets"
EXPR_DIR = ASSETS / "expr"


def asset(name):
    """优先用 WebP（体积小 6 倍），没有就退回 PNG。"""
    for ext in (".webp", ".png"):
        p = ASSETS / (name + ext)
        if p.exists():
            return p
    return ASSETS / (name + ".png")


SPRITE_FILE = asset("sprite")

CFG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "DeepSeekPet"
CFG_FILE = CFG_DIR / "config.json"

# ---------------------------------------------------------------- 表情表
EXPRESSIONS = [
    ("idle", "常驻"),
    ("happy", "开心"),
    ("angry", "生气"),
    ("speechless", "无语"),
    ("sad", "委屈"),
    ("surprised", "惊讶"),
    ("shy", "害羞"),
    ("comfy", "舒服"),
    ("hungry", "饥饿"),
    ("eating", "吃饭"),
]
EXPR_LABEL = dict(EXPRESSIONS)

# 头部在整张立绘里的位置（用于偷窥时只露出脑袋）
HEAD_FRAC = 0.5
PEEK_HEAD_H = 96
PEEK_PAD = 3
PEEK_TRIGGER = 26

DEFAULT_CFG = {
    "api_key": "",
    "model": "deepseek-chat",
    "scale": 1.0,
    "x": None,
    "y": None,
    "peek": False,
    "autostart": False,
    "always_top": True,
    "chat_history": [],
    "meal_times": ["08:00", "12:00", "18:00"],
    "meal_window": 45,
    "fed_slots": {},
}

API_URL = "https://api.deepseek.com/chat/completions"

SYSTEM_PROMPT = (
    "你是一只住在主人 Windows 桌面上的 Q 版女仆桌宠，名字叫「小深」，形象是深蓝紫色长卷发、"
    "白色蕾丝女仆头饰、鲸鱼鳍耳朵、藏青色女仆裙、带着一条鲸鱼尾巴的二次元小人，设定上爱吃白米饭。\n"
    "性格：傲娇、毒舌、嘴硬心软，但其实非常关心主人。\n"
    "说话规则：\n"
    "1. 每次只回 1~2 句话，总长不超过 45 个字，口语化，像粘在桌面上随口吐槽。\n"
    "2. 可以用「哼」「呐」和颜文字，但不要用 Markdown、不要列表、不要长篇大论。\n"
    "3. 绝不输出色情、暴力、政治等违规内容；遇到这类要求就用别的话题岔开。\n"
    "4. 主人常常熬夜写代码，可以顺手关心他的眼睛、颈椎、吃饭、喝水。\n"
    "5. 回答里不要自称 AI，也不要提「作为语言模型」。\n"
    "6. 绝对不要提和电、电击、闪电、静电有关的话或拟声词。"
)

IDLE_LINES = [
    ("又在写 bug？我帮你看一眼，这循环嵌套了三层。", "angry"),
    ("主人，眼睛该休息啦，看我三秒。", "happy"),
    ("这个功能……你确定它跑得起来？哼。", "speechless"),
    ("写注释！现在！就现在！", "angry"),
    ("要不要喝口水？我才不是特意提醒你呢。", "shy"),
    ("我就在这儿盯着你，摸鱼的人要挨罚。", "angry"),
    ("屏幕擦一擦吧，好脏，我看着都难受。", "speechless"),
    ("今天也要好好吃饭，不然我要生气了。", "sad"),
    ("哼，才不是在关心你，只是怕你倒在我旁边。", "shy"),
    ("代码能跑就别动它了……虽然我想这么说，但它好丑。", "speechless"),
    ("呐，窗外天都黑了，你还在写啊？", "sad"),
    ("主人主人！这段代码跑通了哦，夸你一下。", "happy"),
]

PETTING_LINES = [
    ("呼……好舒服，再摸一下也可以。", "comfy"),
    ("别、别摸那里……哼，只是有点痒。", "comfy"),
    ("呼噜噜……主人的手好暖。", "comfy"),
    ("再摸我就要睡着了……", "comfy"),
    ("才、才没有很开心呢。", "comfy"),
    ("尾巴！……算了，今天就允许你摸一下。", "comfy"),
]

HUNGRY_LINES = [
    ("咕……肚子在叫了，主人你看不见吗？", "hungry"),
    ("到饭点了到饭点了到饭点了！", "hungry"),
    ("我、我不是在要饭，只是顺便问问……", "hungry"),
    ("碗已经洗干净了，就等主食了。", "hungry"),
]

FED_LINES = [
    ("呜……终于吃饭了！白米饭最香了。", "eating"),
    ("咕噜咕噜……嗝。多谢主人。", "eating"),
    ("这一碗白米饭，我原谅你三分钟前的bug。", "eating"),
]

NO_KEY_LINES = [
    ("我还没拿到脑子的钥匙呢（右键 → 设置里填 API Key）", "sad"),
    ("现在的我只能靠背台词活着……给我个 Key 吧。", "sad"),
    ("没钥匙，打不开脑袋哦。右键 → 设置。", "speechless"),
]

PEEK_LINES = [
    ("……趴在这里看你写代码，视野最好。", "shy"),
    ("只、只露一个头也是可以的吧？", "shy"),
    ("唔，桌沿好舒服，我先趴一会儿。", "comfy"),
    ("嘘——我在偷看你哦。", "happy"),
]

PEEK_BYE_LINES = [
    ("呀！被、被抓住了……", "surprised"),
    ("呜，正趴得舒服呢。", "speechless"),
    ("哼，想让我出来直说嘛。", "angry"),
]

EXPR_KEYWORDS = {
    "angry": ["生气", "讨厌", "笨蛋", "蠢", "烦", "哼", "闭嘴", "欠揍", "讨打"],
    "sad": ["呜", "哭", "难过", "委屈", "对不起", "别走", "孤单", "呜哇"],
    "surprised": ["诶", "咦", "什么", "竟然", "居然", "真的", "！", "!", "吓"],
    "speechless": ["……", "...", "无语", "呵", "行吧", "随便", "算了", "呃"],
    "shy": ["脸红", "害羞", "才不是", "喜欢", "抱", "摸头", "笨"],
    "happy": ["哈", "开心", "好耶", "棒", "赞", "谢谢", "可爱", "厉害", "嘻嘻"],
}


def guess_expr(text):
    """根据一句话猜表情。"""
    t = text or ""
    best, score = ("idle", 0)
    for name, kws in EXPR_KEYWORDS.items():
        s = sum(t.count(k) for k in kws)
        if s > score:
            best, score = name, s
    if score == 0:
        if "？" in t or "?" in t:
            return "speechless"
        if "！" in t or "!" in t:
            return "happy"
        return "idle"
    return best


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        if CFG_FILE.exists():
            data = json.loads(CFG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update(data)
    except Exception:
        pass
    return cfg


def save_cfg(cfg):
    try:
        CFG_DIR.mkdir(parents=True, exist_ok=True)
        CFG_FILE.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def exe_path():
    return sys.executable if getattr(sys, "frozen", False) else ""


def set_autostart(enable: bool):
    if not exe_path():
        return False
    try:
        import winreg
        key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE
        ) as k:
            if enable:
                winreg.SetValueEx(
                    k, "DeepSeekPet", 0, winreg.REG_SZ, '"%s"' % exe_path()
                )
            else:
                try:
                    winreg.DeleteValue(k, "DeepSeekPet")
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


class Bubble(QWidget):
    PADX, PADY, TAIL, MAXW = 15, 11, 11, 290

    def __init__(self, pet):
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.pet = pet
        self.text = ""
        f = QFont("Microsoft YaHei UI", 10)
        f.setStyleStrategy(QFont.PreferAntialias)
        self.setFont(f)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text, hold=0):
        text = (text or "").strip()
        if not text:
            return
        self.text = text
        fm = QFontMetrics(self.font())
        inner_w = self.MAXW - 2 * self.PADX
        br = fm.boundingRect(
            QRect(0, 0, inner_w, 6000),
            Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop,
            text,
        )
        w = max(br.width() + 2 * self.PADX, 96)
        h = br.height() + 2 * self.PADY
        self.setFixedSize(w, h + self.TAIL)
        self._place()
        self.show()
        self.raise_()
        self.update()
        ms = hold or int(2400 + len(text) * 130)
        self._hide_timer.start(ms)

    def _place(self):
        pet = self.pet
        g = pet.frameGeometry()
        scr = (
            QGuiApplication.screenAt(g.center())
            or QGuiApplication.primaryScreen()
        ).availableGeometry()
        cb = getattr(pet, "chatbox", None)
        chat_open = bool(cb and cb.isVisible())
        x = g.center().x() - self.width() // 2
        y = g.top() - self.height() - 4
        if chat_open:
            y = cb.y() - self.height() - 6
            if y < scr.top() + 4:
                y = max(scr.top() + 4, cb.y() - self.height() - 6)
        x = max(scr.left() + 4, min(x, scr.right() - self.width() - 4))
        if y < scr.top() + 4:
            y = g.bottom() + 4
        self.move(x, y)

    def hideEvent(self, e):
        super().hideEvent(e)
        self.pet._on_bubble_hidden()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        body = QRectF(1.5, 1.5, w - 3, h - self.TAIL - 3)
        path = QPainterPath()
        path.addRoundedRect(body, 15, 15)
        cx = w / 2.0
        tail = QPainterPath()
        tail.moveTo(cx - 8, h - self.TAIL - 1.5)
        tail.lineTo(cx + 1, h - 2)
        tail.lineTo(cx + 8, h - self.TAIL - 1.5)
        tail.closeSubpath()
        path = path.united(tail)
        p.setPen(QPen(QColor(206, 217, 238), 1.4))
        p.setBrush(QBrush(QColor(255, 255, 255, 247)))
        p.drawPath(path)
        p.setPen(QColor(42, 46, 58))
        p.drawText(
            QRectF(
                self.PADX,
                self.PADY,
                w - 2 * self.PADX,
                h - self.TAIL - 2 * self.PADY,
            ),
            Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop,
            self.text,
        )


class ChatWorker(QThread):
    done = Signal(str)

    def __init__(self, key, model, messages):
        super().__init__()
        self.key, self.model, self.messages = key, model, messages

    def run(self):
        try:
            import requests

            r = requests.post(
                API_URL,
                headers={
                    "Authorization": "Bearer %s" % self.key,
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": self.messages,
                    "temperature": 1.15,
                    "max_tokens": 220,
                    "stream": False,
                },
                timeout=60,
            )
            if r.status_code != 200:
                try:
                    err = r.json().get("error", {}).get("message", "")
                except Exception:
                    err = ""
                self.done.emit(
                    f"唔……接口不听话了（{r.status_code!s}）{err[:60]!s}"
                )
                return
            data = r.json()
            msg = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            self.done.emit(msg or "……我一时语塞了。")
        except Exception as e:
            self.done.emit("连不上 DeepSeek 了：%s" % str(e)[:60])


class ChatBox(QWidget):
    def __init__(self, on_send, on_close):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.on_send, self.on_close = on_send, on_close
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(
            """
            QFrame#card { background: rgba(255,255,255,252);
                          border: 1.4px solid #c9d6f0; border-radius: 16px; }
            QLineEdit { border: none; background: transparent;
                        font-family: "Microsoft YaHei UI"; font-size: 14px;
                        color: #21252f; padding: 4px 2px; }
            QPushButton { border: none; border-radius: 11px;
                          background: #3b6ef5; color: white;
                          font-family: "Microsoft YaHei UI"; font-size: 13px;
                          padding: 6px 14px; }
            QPushButton:hover { background: #2a58d8; }
        """
        )
        outer.addWidget(card)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 8, 8, 8)
        lay.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("和我说点什么…（Enter 发送，Esc 收起）")
        self.edit.setMinimumWidth(196)
        self.edit.returnPressed.connect(self._send)
        btn = QPushButton("发送")
        btn.clicked.connect(self._send)
        lay.addWidget(self.edit, 1)
        lay.addWidget(btn)
        self.adjustSize()

    def _send(self):
        t = self.edit.text().strip()
        if not t:
            return
        self.edit.clear()
        self.on_send(t)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.on_close()
            return
        super().keyPressEvent(e)

    def focus(self):
        self.edit.setFocus()
        self.activateWindow()


class SettingsDialog(QDialog):
    def __init__(self, cfg, pet):
        super().__init__(None)
        self.cfg, self.pet = cfg, pet
        self.setWindowTitle("小深 · 设置")
        self.setWindowIcon(QIcon(str(SPRITE_FILE)))
        self.setMinimumWidth(430)
        self.setStyleSheet(
            """
            QDialog { background: #f7f9fd; }
            QLabel { font-family: "Microsoft YaHei UI"; font-size: 13px;
                     color: #2a2f3a; }
            QLineEdit, QComboBox, QDoubleSpinBox {
                font-family: "Microsoft YaHei UI"; font-size: 13px;
                border: 1.2px solid #ccd8ee; border-radius: 8px;
                padding: 6px 8px; background: white; color: #21252f; }
            QPushButton { font-family: "Microsoft YaHei UI"; font-size: 13px;
                border: none; border-radius: 9px; padding: 8px 20px;
                background: #3b6ef5; color: white; }
            QPushButton:hover { background: #2a58d8; }
            QPushButton#ghost { background: #e8eefb; color: #3559b8; }
            QCheckBox { font-family: "Microsoft YaHei UI"; font-size: 13px;
                        color: #2a2f3a; }
        """
        )
        g = QGridLayout(self)
        g.setContentsMargins(22, 20, 22, 18)
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(12)

        title = QLabel("小深 · 设置")
        f = title.font()
        f.setPointSize(13)
        f.setBold(True)
        title.setFont(f)
        g.addWidget(title, 0, 0, 1, 2)

        tip = QLabel("API Key 在 platform.deepseek.com 申请，只保存在本机。")
        tip.setStyleSheet("color:#7a869c; font-size:12px;")
        g.addWidget(tip, 1, 0, 1, 2)

        self.key_edit = QLineEdit(cfg.get("api_key", ""))
        self.key_edit.setPlaceholderText("sk-…")
        self.key_edit.setEchoMode(QLineEdit.Password)
        g.addWidget(QLabel("API Key"), 2, 0)
        g.addWidget(self.key_edit, 2, 1)

        self.model_box = QComboBox()
        self.model_box.addItems(["deepseek-chat", "deepseek-reasoner"])
        self.model_box.setCurrentText(cfg.get("model", "deepseek-chat"))
        g.addWidget(QLabel("模型"), 3, 0)
        g.addWidget(self.model_box, 3, 1)

        self.size_box = QDoubleSpinBox()
        self.size_box.setRange(0.6, 2.2)
        self.size_box.setSingleStep(0.1)
        self.size_box.setValue(float(cfg.get("scale", 1.0)))
        g.addWidget(QLabel("大小倍率"), 4, 0)
        g.addWidget(self.size_box, 4, 1)

        self.meal_edit = QLineEdit(
            ",".join(
                cfg.get("meal_times")
                or ["08:00", "12:00", "18:00"]
            )
        )
        self.meal_edit.setPlaceholderText("08:00,12:00,18:00")
        g.addWidget(QLabel("饭点"), 5, 0)
        g.addWidget(self.meal_edit, 5, 1)

        self.win_box = QDoubleSpinBox()
        self.win_box.setRange(10, 180)
        self.win_box.setSingleStep(5)
        self.win_box.setValue(float(cfg.get("meal_window") or 45))
        self.win_box.setSuffix(" 分钟")
        g.addWidget(QLabel("饭点前后"), 6, 0)
        g.addWidget(self.win_box, 6, 1)

        self.auto_cb = QCheckBox("开机自动启动（仅打包版可用）")
        self.auto_cb.setChecked(bool(cfg.get("autostart", False)))
        self.auto_cb.setEnabled(bool(exe_path()))
        g.addWidget(self.auto_cb, 7, 1)

        meal_tip = QLabel(
            "到饭点没人喂，她就会摆出饥饿表情；右键「喂饭」即可喂一碗大米饭。"
        )
        meal_tip.setStyleSheet("color:#7a869c; font-size:12px;")
        g.addWidget(meal_tip, 8, 0, 1, 2)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("保存")
        ok.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(ok)
        g.addLayout(row, 9, 0, 1, 2)

    def _save(self):
        self.cfg["api_key"] = self.key_edit.text().strip()
        self.cfg["model"] = self.model_box.currentText()
        sc = round(float(self.size_box.value()), 2)
        if sc != float(self.cfg.get("scale", 1.0)):
            self.cfg["scale"] = sc
            self.pet.apply_scale(sc)
        times = []
        for part in self.meal_edit.text().replace("，", ",").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                hh, mm = (int(v) for v in part.split(":")[:2])
                if 0 <= hh < 24 and 0 <= mm < 60:
                    times.append("%02d:%02d" % (hh, mm))
            except Exception:
                continue
        self.cfg["meal_times"] = times or ["08:00", "12:00", "18:00"]
        self.cfg["meal_window"] = int(self.win_box.value())
        want_auto = self.auto_cb.isChecked()
        if bool(self.cfg.get("autostart")) != want_auto:
            if set_autostart(want_auto):
                self.cfg["autostart"] = want_auto
        save_cfg(self.cfg)
        self.accept()


class Pet(QWidget):
    PAD = 6
    PEEK_PAD = PEEK_PAD

    def __init__(self, cfg):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowTitle(PET_NAME)
        self.cfg = cfg
        self.frames = {}
        self.cur = "idle"
        self._expr_token = 0
        self.scale = float(cfg.get("scale") or 1.0)
        self.bubble = Bubble(self)
        self.chatbox = None
        self.worker = None
        self.history = list(cfg.get("chat_history") or [])[-10:]

        # 抖动 / 拖动
        self.t = 0.0
        self.bob = 0.0
        self.shake = 0.0
        self.ox = 0.0
        self.press_g = None
        self.press_w = QPoint()
        self.moved = False

        # 摸摸
        self.petting = False
        self.pet_count = 0
        self._last_stroke = 0.0
        self._pet_hold = QTimer(self)
        self._pet_hold.setSingleShot(True)
        self._pet_hold.timeout.connect(self._begin_petting)

        # 偷窥
        self.peek = False
        self.head_frames = {}
        self.squish = 1.0
        self._peek_t0 = 0.0
        self._peek_anim = QTimer(self)
        self._peek_anim.setInterval(16)
        self._peek_anim.timeout.connect(self._peek_tick)

        # 饥饿
        self._hungry = False
        self.fed_slots = dict(cfg.get("fed_slots") or {})

        self.apply_scale(self.scale)
        self._restore_pos()

        self.anim = QTimer(self)
        self.anim.timeout.connect(self._tick)

        self.idle = QTimer(self)
        self.idle.timeout.connect(self._maybe_idle_chat)
        self.idle.start(75000)

        self.meal = QTimer(self)
        self.meal.timeout.connect(self._check_meal)
        self.meal.start(30000)
        QTimer.singleShot(2500, self._check_meal)

        QTimer.singleShot(900, self._welcome)

    def apply_scale(self, sc):
        self.scale = max(0.6, min(2.2, float(sc)))
        h = max(130, min(620, int(300 * self.scale)))

        sprite = QPixmap(str(SPRITE_FILE))
        if sprite.isNull():
            return
        idle = sprite.scaledToHeight(h, Qt.SmoothTransformation)

        # 表情差分：等比缩到同样高度，再垫到统一画布上
        raws = {}
        for name, _label in EXPRESSIONS:
            if name == "idle":
                continue
            q = QPixmap(str(asset("expr/%s" % name)))
            if q.isNull():
                continue
            raws[name] = q
        k = 1.0
        if raws:
            k = float(h) / max(p.height() for p in raws.values())

        scaled = {
            n: p.scaled(
                max(1, int(p.width() * k)),
                max(1, int(p.height() * k)),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation,
            )
            for n, p in raws.items()
        }
        cw = max([idle.width()] + [p.width() for p in scaled.values()])
        chh = h
        frames = {"idle": idle}
        for name, sp in scaled.items():
            canvas = QPixmap(cw, chh)
            canvas.fill(Qt.transparent)
            pp = QPainter(canvas)
            pp.setRenderHint(QPainter.SmoothPixmapTransform, True)
            pp.setRenderHint(QPainter.Antialiasing, True)
            # 底对齐 + 水平居中
            pp.drawPixmap((cw - sp.width()) // 2, chh - sp.height(), sp)
            pp.end()
            frames[name] = canvas
        self.frames = frames
        if self.cur not in frames:
            self.cur = "idle" if "idle" in frames else next(iter(frames))

        heads = {}
        for name, pm in frames.items():
            hh = max(8, int(pm.height() * HEAD_FRAC))
            hp = pm.copy(0, 0, pm.width(), hh)
            heads[name] = hp.scaledToHeight(PEEK_HEAD_H, Qt.SmoothTransformation)
        self.head_frames = heads

        self._relayout()

        self.cfg["scale"] = round(self.scale, 2)
        save_cfg(self.cfg)

    def _cur_frames(self):
        return self.head_frames if self.peek else self.frames

    def _relayout(self):
        """按当前模式（全身 / 偷窥脑袋）重设窗口尺寸与遮罩，并归位。"""
        frames = self._cur_frames()
        if not frames:
            return
        cw = max(p.width() for p in frames.values())
        ch = max(p.height() for p in frames.values())
        pad = self.PEEK_PAD if self.peek else self.PAD
        self.setFixedSize(cw + 2 * pad, ch + 2 * pad)
        self._apply_mask()
        if self.peek:
            self._dock_bottom()

    def _apply_mask(self):
        frames = self._cur_frames()
        pad = self.PEEK_PAD if self.peek else self.PAD
        reg = QRegion()
        for pm in frames.values():
            base = pm.mask()
            for dx in range(-pad, pad + 1, 6):
                for dy in range(-pad, pad + 1, 6):
                    reg = reg.united(QRegion(base).translated(dx, dy))
        self.setMask(reg)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.Antialiasing, True)
        pm = self._cur_frames().get(self.cur) or self._cur_frames().get("idle")
        if pm is None:
            return
        pad = self.PEEK_PAD if self.peek else self.PAD
        if self.peek:
            # Q 弹落座时压扁 / 拉长
            sy = max(0.05, self.squish)
            sx = 1.0 + (1.0 - sy) * 0.38
            dw, dh = pm.width() * sx, pm.height() * sy
            x = pad + (self.width() - 2 * pad - dw) / 2.0 + self.ox
            y = pad + (self.height() - 2 * pad) - dh
            p.drawPixmap(
                QRectF(x, y, dw, dh),
                pm,
                QRectF(0, 0, pm.width(), pm.height()),
            )
            return
        p.drawPixmap(int(pad + self.ox), int(pad), pm)

    def set_expr(self, name, hold=0):
        if name not in self.frames:
            name = "idle"
        if self.cur != name:
            self.cur = name
            self.update()
        self._expr_token += 1
        tok = self._expr_token
        if name != "idle":
            # hold 毫秒后回到常驻（除非期间又切了别的表情）
            QTimer.singleShot(
                int(hold if hold else 45000),
                lambda: self._revert(tok),
            )
            return
        self.shake = 0.0

    def _on_bubble_hidden(self):
        if self.cur == "idle":
            return
        self._expr_token += 1
        tok = self._expr_token
        QTimer.singleShot(700, lambda: self._revert(tok))

    def _revert(self, tok):
        if tok == self._expr_token:
            self.cur = (
                "hungry"
                if getattr(self, "_hungry", False) and "hungry" in self.frames
                else "idle"
            )
            self.update()

    def _tick(self):
        # 被戳之后的衰减抖动
        if abs(self.shake) > 0.2:
            self.shake *= 0.8
            self.ox = random.uniform(-1, 1) * self.shake
            self.update()
            return
        self.shake = 0.0
        self.ox = 0.0
        self.update()
        self.anim.stop()

    def _kick(self, amp):
        self.shake = max(self.shake, amp)
        if not self.anim.isActive():
            self.anim.start(33)

    def _peek_tick(self):
        t = time.monotonic() - self._peek_t0
        if t < 0.7:
            # 阻尼振荡：先压扁再回弹
            s = 1.0 - 0.45 * math.exp(-7.0 * t) * math.cos(20.0 * t)
        else:
            # 静止后极轻微的呼吸
            s = 1.0 + 0.022 * math.sin((t - 0.7) * 2.4)
        self.squish = s
        self.update()

    def _dock_bottom(self):
        """把小脑袋贴着任务栏顶边放（脚丫藏在栏后的感觉）。"""
        scr = (
            QGuiApplication.screenAt(self.frameGeometry().center())
            or QGuiApplication.primaryScreen()
        )
        av = scr.availableGeometry()
        w = self.width()
        cx = self.x() + self.width() // 2
        x = max(av.left() + 4, min(cx - w // 2, av.right() - w - 4))
        y = av.bottom() - self.height() + 1 + self.PEEK_PAD
        self.move(x, y)
        self.cfg["x"], self.cfg["y"] = x, y
        save_cfg(self.cfg)

    def enter_peek(self, silent=False):
        if not self.head_frames:
            return
        was = self.peek
        self.peek = True
        self._relayout()
        if was:
            return
        self.squish = 0.55
        self._peek_t0 = time.monotonic()
        self._peek_anim.start()
        self.cfg["peek"] = True
        save_cfg(self.cfg)
        if not silent:
            text, expr = random.choice(PEEK_LINES)
            self.say(text, hold=4200, expr=expr)

    def exit_peek(self, silent=False):
        if not self.peek:
            return
        cx = self.x() + self.width() // 2
        self.peek = False
        self._peek_anim.stop()
        self.squish = 1.0
        self._relayout()
        scr = (
            QGuiApplication.screenAt(QPoint(cx, self.y() + 10))
            or QGuiApplication.primaryScreen()
        )
        av = scr.availableGeometry()
        x = max(av.left() + 4, min(cx - self.width() // 2, av.right() - self.width() - 4))
        y = max(
            av.top() + 4,
            min(self.y(), av.bottom() - self.height() + 4),
        )
        self.move(x, y)
        self.cfg["peek"] = False
        self.cfg["x"], self.cfg["y"] = x, y
        save_cfg(self.cfg)
        self.update()
        if not silent:
            text, expr = random.choice(PEEK_BYE_LINES)
            self.say(text, hold=2600, expr=expr)

    def _after_drag_release(self):
        """拖动松手：够贴近屏幕底部就变小脑袋，否则照常记录位置。"""
        scr = (
            QGuiApplication.screenAt(self.frameGeometry().center())
            or QGuiApplication.primaryScreen()
        )
        av = scr.availableGeometry()
        if self.y() + self.height() >= av.bottom() - PEEK_TRIGGER:
            self.enter_peek()
            return
        self.cfg["x"], self.cfg["y"] = self.x(), self.y()
        save_cfg(self.cfg)

    def _restore_pos(self):
        x, y = self.cfg.get("x"), self.cfg.get("y")
        scr = QGuiApplication.primaryScreen().availableGeometry()
        dx = scr.right() - self.width() - 50
        dy = scr.bottom() - self.height() + 6
        if x is None or y is None:
            self.move(dx, dy)
            return
        nx = max(scr.left(), min(int(x), scr.right() - self.width()))
        ny = max(scr.top(), min(int(y), scr.bottom() - self.height()))
        if abs(nx - int(x)) > 200 or abs(ny - int(y)) > 200:
            self.move(dx, dy)
        else:
            self.move(nx, ny)
        if self.cfg.get("peek"):
            self.enter_peek(silent=True)

    def ensure_on_screen(self):
        """确保整只小人都落在屏幕可见区域内。"""
        scr = (
            QGuiApplication.screenAt(self.frameGeometry().center())
            or QGuiApplication.primaryScreen()
        )
        av = scr.availableGeometry()
        g = scr.geometry()
        w, h = self.width(), self.height()
        x, y = self.x(), self.y()

        def clamp(v, lo, hi):
            return max(lo, min(v, hi))

        # 先按可用区域（任务栏之上）收一次
        x = clamp(x, av.left() + 4, av.right() - w - 4)
        y = clamp(y, av.top() + 4, av.bottom() - h + 4)
        # 再兜底到整块屏幕
        if x + w > g.right() or y + h > g.bottom() or x < g.left() or y < g.top():
            x = clamp(x, g.left(), g.right() - w)
            y = clamp(y, g.top(), g.bottom() - h)
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)
            self.cfg["x"], self.cfg["y"] = x, y
            save_cfg(self.cfg)

    def moveEvent(self, e):
        super().moveEvent(e)
        if getattr(self, "bubble", None) and self.bubble.isVisible():
            self.bubble._place()

    def say(self, text, hold=0, expr=None):
        self.bubble.show_text(text, hold)
        e = expr or guess_expr(text)
        self.set_expr(e)
        if abs(self.shake) < 1.0:
            self._kick(2.5)
        if self.chatbox and self.chatbox.isVisible():
            self._place_chatbox()

    def say_random_idle(self):
        text, expr = random.choice(IDLE_LINES)
        self.say(text, expr=expr)

    def _welcome(self):
        if self.bubble.isVisible():
            return
        if self.cfg.get("api_key"):
            self.say("哼，开机了。主人，今天也要好好活着哦。", expr="happy")
            return
        self.say(
            "哼，我醒啦。右键点我 → 设置，填个 API Key，我就能真说话了。",
            hold=7000,
            expr="happy",
        )

    def _maybe_idle_chat(self):
        if self.bubble.isVisible() or (self.chatbox and self.chatbox.isVisible()):
            return
        if random.random() < 0.45:
            self.say_random_idle()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.press_g = e.globalPosition().toPoint()
            self.press_w = self.pos()
            self.moved = False
            self.petting = False
            self.pet_count = 0
            self._pet_hold.start(420)
            e.accept()

    def mouseMoveEvent(self, e):
        if self.press_g is not None:
            if e.buttons() & Qt.LeftButton:
                if self.petting:
                    # 摸摸模式下随便动一动就是一下
                    self._stroke()
                    e.accept()
                    return
                d = e.globalPosition().toPoint() - self.press_g
                if abs(d.x()) + abs(d.y()) > 4:
                    self.moved = True
                    self._pet_hold.stop()
                if self.moved:
                    if self.peek:
                        # 从偷窥状态被往上拽：先弹回全身再跟着走
                        gp = e.globalPosition().toPoint()
                        self.exit_peek()
                        self.press_g = gp
                        self.press_w = self.pos()
                        e.accept()
                        return
                    self.move(self.press_w + d)
                    e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        self._pet_hold.stop()
        if self.petting:
            self.petting = False
            n, self.pet_count = self.pet_count, 0
            if n >= 5:
                self.say("哼……勉强舒服。下次再摸要收钱了。", hold=3400, expr="comfy")
            else:
                self.say("摸、摸够了没……", hold=2600, expr="shy")
            self.press_g = None
            return
        if self.moved:
            if self.peek:
                self.cfg["x"], self.cfg["y"] = self.x(), self.y()
                save_cfg(self.cfg)
                return
            self._after_drag_release()
            return
        if self.peek:
            # 点一下就弹回全身
            self.exit_peek()
            self.press_g = None
            return
        self._kick(5.0)
        if self.bubble.isVisible():
            self.bubble.hide()
            self.set_expr("idle")
        else:
            text, expr = random.choice(IDLE_LINES)
            self.say(text, expr=expr)
        self.press_g = None

    def _begin_petting(self):
        if self.press_g is None or self.moved:
            return
        self.petting = True
        self.pet_count = 0
        self.say("……可以摸摸，但不许多摸。", hold=4200, expr="comfy")
        self._stroke()

    def _stroke(self):
        import time

        now = time.monotonic()
        if now - self._last_stroke < 0.35:
            return
        self._last_stroke = now
        self.pet_count += 1
        if self.pet_count >= 8:
            self.say("呼……睡着了，不许吵。", hold=5000, expr="comfy")
            self.pet_count = 0
            return
        text, expr = random.choice(PETTING_LINES)
        self.say(text, hold=2800, expr=expr)
        self._kick(1.2)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.open_chat()

    def wheelEvent(self, e):
        step = 0.08 if e.angleDelta().y() > 0 else -0.08
        self.apply_scale(self.scale + step)
        if self.bubble.isVisible():
            self.bubble._place()

    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.setStyleSheet(
            """
            QMenu { background: white; border: 1px solid #d5deee;
                    border-radius: 10px; padding: 6px;
                    font-family: "Microsoft YaHei UI"; font-size: 13px;
                    color: #23283a; }
            QMenu::item { padding: 6px 22px 6px 16px; border-radius: 6px; }
            QMenu::item:selected { background: #eaf0ff; }
        """
        )
        m.addAction("和我聊天（双击我也可以）", self.open_chat)
        m.addAction("说句话", self.say_random_idle)
        m.addAction("摸摸（按住她不动再动一动）", self.begin_petting)
        m.addAction("喂饭（大米饭）", self.feed)
        sub = m.addMenu("表情")
        for name, label in EXPRESSIONS:
            a = sub.addAction(label)
            a.triggered.connect(lambda _=False, n=name: self.set_expr(n, 12000))
        size_menu = m.addMenu("大小")
        for label, sc in (("小", 0.75), ("中", 1.0), ("大", 1.35), ("巨大", 1.8)):
            a = size_menu.addAction(label)
            a.triggered.connect(lambda _=False, s=sc: self.apply_scale(s))
        m.addSeparator()
        m.addAction("设置…", self.open_settings)
        m.addAction("藏到托盘", self.hide)
        m.addSeparator()
        m.addAction("退出", QApplication.instance().quit)
        m.exec(e.globalPos())

    def _today(self):
        import datetime

        return datetime.date.today().isoformat()

    def _meal_slot(self):
        """当前是否在某个饭点的时间窗内，返回该饭点标签或 None。"""
        import datetime

        now = datetime.datetime.now()
        win = max(5, int(self.cfg.get("meal_window") or 45))
        for t in self.cfg.get("meal_times") or []:
            try:
                hh, mm = (int(v) for v in str(t).split(":")[:2])
                start = now.replace(
                    hour=hh, minute=mm, second=0, microsecond=0
                )
            except Exception:
                continue
            if abs((now - start).total_seconds()) <= win * 60:
                return "%02d:%02d" % (hh, mm)
        return None

    def _check_meal(self):
        slot = self._meal_slot()
        if slot and self.fed_slots.get(self._today()) != slot:
            if not self._hungry:
                self._set_hungry(True)
                text, expr = random.choice(HUNGRY_LINES)
                self.say(text, hold=9000, expr=expr)
            return
        if self._hungry:
            self._set_hungry(False)

    def _set_hungry(self, on):
        if on == self._hungry:
            return
        self._hungry = on
        self._expr_token += 1
        if on:
            self.cur = "hungry" if "hungry" in self.frames else "idle"
        else:
            self.cur = "idle" if "idle" in self.frames else self.cur
        self.update()

    def feed(self):
        slot = self._meal_slot()
        if slot:
            self.fed_slots[self._today()] = slot
            self.cfg["fed_slots"] = self.fed_slots
            save_cfg(self.cfg)
        self._set_hungry(False)
        text, expr = random.choice(FED_LINES)
        self.say(text, hold=6500, expr=expr)
        self._kick(3.0)

    def begin_petting(self):
        if self.petting:
            return
        self.petting = True
        self.pet_count = 0
        self._last_stroke = 0.0
        self.say("……可以摸摸，但不许多摸。", hold=4200, expr="comfy")
        self._stroke()
        QTimer.singleShot(4200, self._end_petting)

    def _end_petting(self):
        if not self.petting:
            return
        self.petting = False
        self.say("哼……勉强舒服。", hold=3000, expr="comfy")

    def _place_chatbox(self):
        if not self.chatbox:
            return
        self.chatbox.adjustSize()
        g = self.frameGeometry()
        scr = (
            QGuiApplication.screenAt(g.center())
            or QGuiApplication.primaryScreen()
        ).availableGeometry()
        w = self.chatbox.width()
        x = max(
            scr.left() + 6,
            min(g.center().x() - w // 2, scr.right() - w - 6),
        )
        y = g.top() - self.chatbox.height() - 6
        if y < scr.top() + 6:
            y = g.bottom() + 6
        self.chatbox.move(x, y)

    def open_chat(self):
        if not self.chatbox:
            self.chatbox = ChatBox(self.send, self.close_chat)
        self._place_chatbox()
        self.chatbox.show()
        self.chatbox.raise_()
        if self.bubble.isVisible():
            self.bubble._place()
            self.bubble.raise_()
        self.chatbox.focus()
        self.set_expr("happy", 4000)

    def close_chat(self):
        if self.chatbox:
            self.chatbox.hide()
        self.setFocus()

    def send(self, text):
        self._place_chatbox()
        key = (self.cfg.get("api_key") or "").strip()
        if not key:
            t, ex = random.choice(NO_KEY_LINES)
            self.say(t, hold=5200, expr=ex)
            return
        self.say("……让我想想……（思考中）", hold=90000, expr="speechless")
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        for item in self.history[-8:]:
            if isinstance(item, dict):
                if item.get("role") in ("user", "assistant"):
                    msgs.append(item)
        msgs.append({"role": "user", "content": text})
        self.worker = ChatWorker(key, self.cfg.get("model", "deepseek-chat"), msgs)
        self.worker.done.connect(lambda r, q=text: self._on_reply(r, q))
        self.worker.start()

    def _on_reply(self, reply, question):
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": reply})
        self.history = self.history[-10:]
        self.cfg["chat_history"] = self.history
        save_cfg(self.cfg)
        self.say(reply)
        if self.chatbox and self.chatbox.isVisible():
            self._place_chatbox()

    def open_settings(self):
        SettingsDialog(self.cfg, self).exec()
        if self.chatbox and self.chatbox.isVisible():
            self._place_chatbox()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(str(SPRITE_FILE)))

    cfg = load_cfg()
    pet = Pet(cfg)

    tray = QSystemTrayIcon(QIcon(str(SPRITE_FILE)), app)
    tray.setToolTip(PET_NAME)
    menu = QMenu()
    menu.addAction("呼出小深", lambda: (pet.show(), pet.raise_()))
    menu.addAction("聊天", pet.open_chat)
    menu.addAction("摸摸", pet.begin_petting)
    menu.addAction("喂饭", pet.feed)
    menu.addAction("设置", pet.open_settings)
    menu.addSeparator()
    menu.addAction("退出", app.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: pet.show() if reason == QSystemTrayIcon.Trigger else None
    )
    tray.show()

    pet.show()
    pet.raise_()
    QTimer.singleShot(0, pet.ensure_on_screen)

    if "--diag" in sys.argv:
        try:
            s = QGuiApplication.primaryScreen()
            CFG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CFG_DIR / "diag.txt", "w", encoding="utf-8") as fh:
                fh.write(
                    f"screen geom={s.geometry()!s} "
                    f"avail={s.availableGeometry()!s} "
                    f"dpr={s.devicePixelRatio()!s} "
                    f"dpi={s.logicalDotsPerInch()!s}\n"
                )
                fh.write(
                    "pet geom=%s size=%s screens=%d\n"
                    % (pet.geometry(), pet.size(), len(QGuiApplication.screens()))
                )
        except Exception as e:
            pass

    if "--demo" in sys.argv:
        cfg["x"] = cfg["y"] = None
        pet._restore_pos()
        QTimer.singleShot(
            500,
            lambda: pet.say(
                "喂！又在写 bug 吗？让我看看你这段三层循环……嘶，好丑。",
                hold=20000,
                expr="angry",
            ),
        )
        QTimer.singleShot(1200, pet.open_chat)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
