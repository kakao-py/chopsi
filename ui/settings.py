import os
import json
import tempfile
import re
import inspect
from datetime import date, datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QSpinBox, QDoubleSpinBox, QPushButton, QGridLayout, 
    QComboBox, QGroupBox, QTableWidget, QHeaderView,
    QAbstractItemView, QScrollArea, QWidget, QInputDialog,
    QCheckBox, QApplication
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap, QPainter, QColor, QPolygon, QPen

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "state.json")
TASKS_FILE = os.path.join(BASE_DIR, "tasks.json")
PROFILES_FILE = os.path.join(BASE_DIR, "profiles.json")

DNY_V_TYDNU = [
    ("0", "Pondělí"),
    ("1", "Úterý"),
    ("2", "Středa"),
    ("3", "Čtvrtek"),
    ("4", "Pátek"),
    ("5", "Sobota"),
    ("6", "Neděle"),
]

VYCHOZI_INTERVALY = [
    [1, 5.0, 0.02, "pomer"],
    [5.01, 7.95, 0.10, "pomer"],
    [7.95, 24.0, 10.0, "pevna"],
    [7.95, 9.0, 0.10, "pomer"],
    [9.0, 24.0, 0.30, "pomer"],
]

VYCHOZI_NASOBITEL_PONOCOVANI = 1.0

DEFAULT_BEDTIMES = {
    "0": 22.0, "1": 22.0, "2": 22.0, "3": 22.0,
    "4": 23.0, "5": 23.0, "6": 22.0
}


def nacti_state() -> dict:
    vychozi_stav = {
        "bedtimes": DEFAULT_BEDTIMES.copy(),
        "rezerva": 10,
        "pravidla_intervaly": VYCHOZI_INTERVALY,
        "nasobitel_ponocovani": VYCHOZI_NASOBITEL_PONOCOVANI,
        "bot_typ": "k",
        "queue_interval": 10,
        "bonus_aktivni": True,
        "bonus_procenta": 30,
        "ukoly": [],
        "profily": ["Kaja (k)", "Danda (d)", "Rudik (r)"]
    }

    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "intervaly" in data and "pravidla_intervaly" not in data:
                    data["pravidla_intervaly"] = data["intervaly"]
                vychozi_stav.update(data)
        except Exception as e:
            print(f"❌ Chyba při načítání {STATE_FILE}: {e}")

    return vychozi_stav


def uloz_state(data: dict):
    try:
        stav = nacti_state()
        stav.update(data)
        if "pravidla_intervaly" in stav:
            stav["intervaly"] = stav["pravidla_intervaly"]
            
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(stav, f, ensure_ascii=False, indent=4)
        print(f"✅ Úspěšně uloženo do: {STATE_FILE}")
    except Exception as e:
        print(f"❌ Chyba při ukládání do {STATE_FILE}: {e}")


def nacti_seznam_profilu():
    stav = nacti_state()
    return stav.get("profily", ["Kaja (k)", "Danda (d)"])


def uloz_seznam_profilu(seznam):
    uloz_state({"profily": seznam})


def vygeneruj_ikony_a_fajfku():
    temp_dir = tempfile.gettempdir()
    up_path = os.path.join(temp_dir, "qt_spinbox_arrow_up.png").replace("\\", "/")
    down_path = os.path.join(temp_dir, "qt_spinbox_arrow_down.png").replace("\\", "/")
    check_path = os.path.join(temp_dir, "qt_checkbox_check.png").replace("\\", "/")

    pix_up = QPixmap(12, 10)
    pix_up.fill(Qt.transparent)
    p = QPainter(pix_up)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#0d5c56"))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygon([QPoint(6, 2), QPoint(10, 8), QPoint(2, 8)]))
    p.end()
    pix_up.save(up_path, "PNG")

    pix_down = QPixmap(12, 10)
    pix_down.fill(Qt.transparent)
    p = QPainter(pix_down)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#0d5c56"))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygon([QPoint(2, 2), QPoint(10, 2), QPoint(6, 8)]))
    p.end()
    pix_down.save(down_path, "PNG")

    pix_check = QPixmap(14, 14)
    pix_check.fill(Qt.transparent)
    p = QPainter(pix_check)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#ffffff"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(3, 7, 6, 10)
    p.drawLine(6, 10, 11, 4)
    p.end()
    pix_check.save(check_path, "PNG")

    return up_path, down_path, check_path


def parsuj_a_najdi_vecerku(combo, val):
    val_float = None
    if isinstance(val, (int, float)):
        val_float = float(val)
    elif isinstance(val, str):
        val_str = val.strip()
        if ":" in val_str:
            try:
                parts = val_str.split(":")
                val_float = float(parts[0]) + float(parts[1]) / 60.0
            except ValueError:
                pass
        else:
            try:
                val_float = float(val_str)
            except ValueError:
                pass

    if val_float is None:
        val_float = 22.0

    val_float = round(val_float * 2) / 2.0

    kandidati = [val_float]
    if val_float < 18.0:
        kandidati.append(val_float + 24.0)
    if val_float >= 24.0:
        kandidati.append(val_float - 24.0)

    for k in kandidati:
        idx = combo.findData(k)
        if idx >= 0:
            return idx

    idx_def = combo.findData(22.0)
    return idx_def if idx_def >= 0 else 0


class SettingsPanel:
    def __init__(self, parent_widget, bedtimes=None, on_save_callback=None):
        self.parent = parent_widget
        self.on_save_callback = on_save_callback
        self.dialog = None
        self.combo_vecerky = {}
        self.combo_rezerva = None
        self.table_intervaly = None
        self.spin_nasobitel = None
        self.combo_bot_typ = None
        self.spin_queue_interval = None
        self.ukoly_inputs = []
        self.check_bonus = None
        self.spin_bonus_procent = None
        self.layout_seznam_ukolu = None

    @staticmethod
    def spocitej_hodnotu_ukolu(ukol, bonus_aktivni, bonus_procenta, splneno_v_prvni_polovine=True):
        zakladni_minuty = ukol.get("minuty", 0)
        dni = ukol.get("dni", 0)
        if bonus_aktivni and dni >= 3 and splneno_v_prvni_polovine:
            celkem = zakladni_minuty * (1 + bonus_procenta / 100)
            return round(celkem)
        return zakladni_minuty

    def otvrit_panel(self, bedtimes=None, aktualni_rezerva=None, pravidla_intervaly=None, 
                     nasobitel_ponocovani=None, ukoly=None, bot_typ_filtru=None, 
                     bonus_aktivni=None, bonus_procenta=None, queue_interval_sekund=None):
        
        stav = nacti_state()
        
        if bedtimes is None:
            bedtimes = stav.get("bedtimes", DEFAULT_BEDTIMES)
        if aktualni_rezerva is None:
            aktualni_rezerva = stav.get("rezerva", 10)
        if pravidla_intervaly is None:
            pravidla_intervaly = stav.get("pravidla_intervaly", VYCHOZI_INTERVALY)
        if nasobitel_ponocovani is None:
            nasobitel_ponocovani = stav.get("nasobitel_ponocovani", VYCHOZI_NASOBITEL_PONOCOVANI)
        
        # Načteme primárně z tasks.json, abychom neztratili úkoly nastavené v hlavním okně
        if os.path.exists(TASKS_FILE):
            try:
                with open(TASKS_FILE, "r", encoding="utf-8") as f:
                    ukoly = json.load(f)
            except Exception:
                pass
        if ukoly is None:
            ukoly = stav.get("ukoly", [])

        if bot_typ_filtru is None:
            bot_typ_filtru = stav.get("bot_typ", "k")
        if bonus_aktivni is None:
            bonus_aktivni = stav.get("bonus_aktivni", True)
        if bonus_procenta is None:
            bonus_procenta = stav.get("bonus_procenta", 30)
        if queue_interval_sekund is None:
            queue_interval_sekund = stav.get("queue_interval", 10)

        self.dialog = QDialog(self.parent)
        self.dialog.setWindowTitle("Nastavení")
        self.dialog.resize(560, 780)
        self.dialog.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        up_arrow_path, down_arrow_path, check_icon_path = vygeneruj_ikony_a_fajfku()

        self.dialog.setStyleSheet(f"""
            QDialog {{ background-color: #f4fbfb; }}
            QLabel {{ font-size: 13px; color: #1a4d48; font-weight: 500; }}
            QLabel#title {{ font-size: 18px; font-weight: bold; color: #17d1c6; padding-bottom: 2px; }}
            QGroupBox {{ font-size: 13px; font-weight: bold; color: #0d5c56; border: 1.5px solid #17d1c6; border-radius: 8px; margin-top: 10px; padding-top: 10px; background-color: #ffffff; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; background-color: #f4fbfb; }}
            QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {{ background-color: #ffffff; border: 1.5px solid #17d1c6; border-radius: 6px; padding: 3px 6px; font-size: 13px; font-weight: bold; color: #0d5c56; }}
            QComboBox::drop-down {{ border: none; width: 18px; }}
            QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {{ border: 2px solid #12b3a9; }}
            QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: padding; subcontrol-position: top right; width: 18px; background-color: #e0f8f6; border: none; border-top-right-radius: 5px; image: url("{up_arrow_path}"); }}
            QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: padding; subcontrol-position: bottom right; width: 18px; background-color: #e0f8f6; border: none; border-bottom-right-radius: 5px; image: url("{down_arrow_path}"); }}
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{ background-color: #17d1c6; }}
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background-color: #17d1c6; }}
            QCheckBox {{ font-size: 13px; font-weight: bold; color: #0d5c56; spacing: 8px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border: 1.5px solid #17d1c6; border-radius: 4px; background-color: #ffffff; }}
            QCheckBox::indicator:checked {{ background-color: #17d1c6; image: url("{check_icon_path}"); }}
            QTableWidget {{ background-color: #ffffff; border: 1.5px solid #17d1c6; border-radius: 6px; gridline-color: #e2eceb; }}
            QHeaderView::section {{ background-color: #e0f8f6; color: #0d5c56; font-weight: bold; border: none; border-bottom: 1.5px solid #17d1c6; padding: 4px; }}
            QPushButton#btn_add {{ background-color: #e0f8f6; color: #0d5c56; font-weight: bold; border: 1px solid #17d1c6; border-radius: 6px; padding: 4px 10px; }}
            QPushButton#btn_add:hover {{ background-color: #17d1c6; color: white; }}
            QPushButton#btn_del {{ background-color: #fde8e8; color: #c53030; font-weight: bold; border: 1px solid #f8b4b4; border-radius: 6px; padding: 4px 10px; }}
            QPushButton#btn_del:hover {{ background-color: #f8b4b4; }}
            QPushButton#save_btn {{ background-color: #17d1c6; color: white; font-weight: bold; border: none; border-radius: 8px; padding: 8px 16px; font-size: 13px; }}
            QPushButton#save_btn:hover {{ background-color: #12b3a9; }}
            QPushButton#cancel_btn {{ background-color: #e2eceb; color: #4a6361; font-weight: bold; border: none; border-radius: 8px; padding: 8px 16px; font-size: 13px; }}
            QPushButton#cancel_btn:hover {{ background-color: #d1dedd; }}
            QScrollArea {{ background-color: transparent; border: none; }}
            QScrollBar:vertical {{ border: none; background: #e0f8f6; width: 8px; border-radius: 4px; }}
            QScrollBar::handle:vertical {{ background: #17d1c6; border-radius: 4px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: #12b3a9; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)

        dialog_layout = QVBoxLayout(self.dialog)
        dialog_layout.setContentsMargins(12, 12, 12, 12)
        dialog_layout.setSpacing(10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(12)
        scroll_layout.setContentsMargins(6, 0, 10, 0)

        title = QLabel("⚙ Nastavení")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        scroll_layout.addWidget(title)

        moznosti_vecerky = []
        for h in range(18, 24):
            moznosti_vecerky.append((f"{h:02d}:00", float(h)))
            moznosti_vecerky.append((f"{h:02d}:30", h + 0.5))
        for h in range(0, 3):
            moznosti_vecerky.append((f"{h:02d}:00", float(h)))
            if h < 2:
                moznosti_vecerky.append((f"{h:02d}:30", h + 0.5))

        group_vecerky = QGroupBox("Večerky po dnech")
        grid_vecerky = QGridLayout()
        grid_vecerky.setSpacing(6)

        self.combo_vecerky = {}
        for idx, (den_id, den_nazev) in enumerate(DNY_V_TYDNU):
            lbl = QLabel(f"{den_nazev}:")
            combo = QComboBox()
            for label, val in moznosti_vecerky:
                combo.addItem(label, val)

            aktualni_val = bedtimes.get(den_id)
            if aktualni_val is None:
                try:
                    aktualni_val = bedtimes.get(int(den_id), 22.0)
                except (ValueError, TypeError):
                    aktualni_val = 22.0

            idx_combo = parsuj_a_najdi_vecerku(combo, aktualni_val)
            combo.setCurrentIndex(idx_combo)

            grid_vecerky.addWidget(lbl, idx // 2, (idx % 2) * 2)
            grid_vecerky.addWidget(combo, idx // 2, (idx % 2) * 2 + 1)
            self.combo_vecerky[den_id] = combo

        group_vecerky.setLayout(grid_vecerky)
        scroll_layout.addWidget(group_vecerky)

        group_bot = QGroupBox("🤖 Discord bot – Nastavení")
        layout_bot_main = QVBoxLayout()
        layout_bot_main.setSpacing(8)

        layout_bot_profil = QHBoxLayout()
        lbl_bot = QLabel("Profil:")
        
        self.combo_bot_typ = QComboBox()
        dostupne_profily = nacti_seznam_profilu()
        self.combo_bot_typ.addItems(dostupne_profily)
        
        found = False
        for i in range(self.combo_bot_typ.count()):
            item_text = self.combo_bot_typ.itemText(i).lower()
            if f"({bot_typ_filtru})" in item_text or bot_typ_filtru in item_text:
                self.combo_bot_typ.setCurrentIndex(i)
                found = True
                break
        if not found and self.combo_bot_typ.count() > 0:
            self.combo_bot_typ.setCurrentIndex(0)

        btn_pridat_profil = QPushButton("+ Přidat")
        btn_pridat_profil.setObjectName("btn_add")
        btn_pridat_profil.clicked.connect(self._pridat_novy_profil)

        btn_smazat_profil = QPushButton("- Smazat")
        btn_smazat_profil.setObjectName("btn_del")
        btn_smazat_profil.clicked.connect(self._smazat_profil)

        layout_bot_profil.addWidget(lbl_bot)
        layout_bot_profil.addWidget(self.combo_bot_typ, stretch=1)
        layout_bot_profil.addWidget(btn_pridat_profil)
        layout_bot_profil.addWidget(btn_smazat_profil)
        layout_bot_main.addLayout(layout_bot_profil)

        layout_interval_bot = QHBoxLayout()
        lbl_interval_bot = QLabel("Frekvence kontroly fronty:")
        self.spin_queue_interval = QSpinBox()
        self.spin_queue_interval.setRange(2, 300)
        self.spin_queue_interval.setSingleStep(1)
        self.spin_queue_interval.setValue(int(queue_interval_sekund))
        self.spin_queue_interval.setSuffix(" s")

        layout_interval_bot.addWidget(lbl_interval_bot)
        layout_interval_bot.addWidget(self.spin_queue_interval)
        layout_bot_main.addLayout(layout_interval_bot)

        group_bot.setLayout(layout_bot_main)
        scroll_layout.addWidget(group_bot)

        group_intervaly = QGroupBox("Pravidla spánku (intervaly a odměny)")
        layout_intervaly = QVBoxLayout()
        layout_intervaly.setSpacing(8)

        rezerva_layout = QHBoxLayout()
        lbl_rezerva = QLabel("Toleranční rezerva:")
        self.combo_rezerva = QComboBox()
        self.combo_rezerva.addItems(["5 minut", "10 minut", "15 minut"])
        
        if aktualni_rezerva == 5:
            self.combo_rezerva.setCurrentIndex(0)
        elif aktualni_rezerva == 15:
            self.combo_rezerva.setCurrentIndex(2)
        else:
            self.combo_rezerva.setCurrentIndex(1)

        rezerva_layout.addWidget(lbl_rezerva)
        rezerva_layout.addWidget(self.combo_rezerva)
        layout_intervaly.addLayout(rezerva_layout)

        self.table_intervaly = QTableWidget()
        self.table_intervaly.setColumnCount(4)
        self.table_intervaly.setHorizontalHeaderLabels(["Od (h)", "Do (h)", "Typ", "Odměna"])
        self.table_intervaly.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_intervaly.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_intervaly.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_intervaly.setFixedHeight(160)

        for polozka in pravidla_intervaly:
            od_h = polozka[0]
            do_h = polozka[1]
            hodnota = polozka[2]
            if len(polozka) > 3:
                typ_odmeny = polozka[3]
            else:
                typ_odmeny = "pomer" if hodnota <= 5.0 else "pevna"
            
            self._pridat_radek_tabulky_intervaly(od_h, do_h, hodnota, typ_odmeny)

        layout_intervaly.addWidget(self.table_intervaly)

        btn_table_layout = QHBoxLayout()
        btn_add = QPushButton("+ Přidat rozmezí")
        btn_add.setObjectName("btn_add")
        btn_add.clicked.connect(lambda: self._pridat_radek_tabulky_intervaly(9.0, 10.0, 1.0, "pomer"))

        btn_del = QPushButton("- Smazat vybrané")
        btn_del.setObjectName("btn_del")
        btn_del.clicked.connect(lambda: self._smazat_vybrany_radek(self.table_intervaly))

        btn_table_layout.addWidget(btn_add)
        btn_table_layout.addWidget(btn_del)
        layout_intervaly.addLayout(btn_table_layout)

        group_intervaly.setLayout(layout_intervaly)
        scroll_layout.addWidget(group_intervaly)

        group_ponocovani = QGroupBox("Ponocování (přetažení večerky)")
        layout_ponocovani = QVBoxLayout()
        layout_ponocovani.setSpacing(8)

        nasobitel_layout = QHBoxLayout()
        lbl_nasobitel = QLabel("Násobitel strženého času:")
        
        self.spin_nasobitel = QDoubleSpinBox()
        self.spin_nasobitel.setRange(0.1, 10.0)
        self.spin_nasobitel.setSingleStep(0.1)
        self.spin_nasobitel.setDecimals(2)
        self.spin_nasobitel.setSuffix("×")
        self.spin_nasobitel.setValue(float(nasobitel_ponocovani))

        nasobitel_layout.addWidget(lbl_nasobitel)
        nasobitel_layout.addWidget(self.spin_nasobitel)
        layout_ponocovani.addLayout(nasobitel_layout)

        group_ponocovani.setLayout(layout_ponocovani)
        scroll_layout.addWidget(group_ponocovani)

        self.box_ukoly = QGroupBox("📋 Správa denních úkolů a bonusů")
        layout_ukoly_main = QVBoxLayout(self.box_ukoly)

        self.check_bonus = QCheckBox("Bonus za splnění úkolu (> 3 dny) v 1. polovině času")
        self.check_bonus.setChecked(bonus_aktivni)
        layout_ukoly_main.addWidget(self.check_bonus)

        bonus_procent_layout = QHBoxLayout()
        lbl_bonus_procent = QLabel("Výše bonusu:")
        
        self.spin_bonus_procent = QSpinBox()
        self.spin_bonus_procent.setRange(0, 200)
        self.spin_bonus_procent.setSingleStep(5)
        self.spin_bonus_procent.setValue(bonus_procenta)
        self.spin_bonus_procent.setSuffix(" %")

        bonus_procent_layout.addWidget(lbl_bonus_procent)
        bonus_procent_layout.addWidget(self.spin_bonus_procent)
        bonus_procent_layout.addStretch()
        
        layout_ukoly_main.addLayout(bonus_procent_layout)

        container_seznam = QWidget()
        self.layout_seznam_ukolu = QVBoxLayout(container_seznam)
        self.layout_seznam_ukolu.setContentsMargins(0, 0, 0, 0)
        self.layout_seznam_ukolu.setSpacing(6)
        
        self.ukoly_inputs = []
        for ukol in ukoly:
            self._pridat_ukol_vstup(ukol)

        layout_ukoly_main.addWidget(container_seznam)

        btn_add_ukol = QPushButton("+ Přidat úkol")
        btn_add_ukol.setObjectName("btn_add")
        btn_add_ukol.clicked.connect(lambda: self._pridat_ukol_vstup())
        layout_ukoly_main.addWidget(btn_add_ukol)

        scroll_layout.addWidget(self.box_ukoly)

        scroll_area.setWidget(scroll_widget)
        dialog_layout.addWidget(scroll_area)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_save = QPushButton("Uložit")
        btn_save.setObjectName("save_btn")
        btn_save.clicked.connect(self._ulozi_nastaveni)

        btn_cancel = QPushButton("Zrušit")
        btn_cancel.setObjectName("cancel_btn")
        btn_cancel.clicked.connect(self.dialog.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)

        dialog_layout.addLayout(btn_layout)

        self.dialog.exec()

    def _pridat_novy_profil(self):
        jmeno, ok = QInputDialog.getText(self.dialog, "Nový profil", "Zadejte název profilu (např. Jméno (j)):")
        if ok and jmeno.strip():
            jmeno = jmeno.strip()
            profily = nacti_seznam_profilu()
            if jmeno not in profily:
                profily.append(jmeno)
                uloz_seznam_profilu(profily)
                self.combo_bot_typ.addItem(jmeno)
                self.combo_bot_typ.setCurrentText(jmeno)

    def _smazat_profil(self):
        idx = self.combo_bot_typ.currentIndex()
        if idx >= 0 and self.combo_bot_typ.count() > 1:
            text = self.combo_bot_typ.currentText()
            self.combo_bot_typ.removeItem(idx)
            profily = nacti_seznam_profilu()
            if text in profily:
                profily.remove(text)
                uloz_seznam_profilu(profily)

    def _pridat_radek_tabulky_intervaly(self, od_h, do_h, hodnota, typ_odmeny):
        row = self.table_intervaly.rowCount()
        self.table_intervaly.insertRow(row)

        spin_od = QDoubleSpinBox()
        spin_od.setRange(0.0, 24.0)
        spin_od.setSingleStep(0.5)
        spin_od.setValue(float(od_h))

        spin_do = QDoubleSpinBox()
        spin_do.setRange(0.0, 24.0)
        spin_do.setSingleStep(0.5)
        spin_do.setValue(float(do_h))

        combo_typ = QComboBox()
        combo_typ.addItem("Poměr", "pomer")
        combo_typ.addItem("Pevná", "pevna")
        if str(typ_odmeny).lower() == "pevna":
            combo_typ.setCurrentIndex(1)
        else:
            combo_typ.setCurrentIndex(0)

        spin_val = QDoubleSpinBox()
        spin_val.setRange(0.0, 300.0)
        spin_val.setSingleStep(0.1)
        spin_val.setValue(float(hodnota))

        self.table_intervaly.setCellWidget(row, 0, spin_od)
        self.table_intervaly.setCellWidget(row, 1, spin_do)
        self.table_intervaly.setCellWidget(row, 2, combo_typ)
        self.table_intervaly.setCellWidget(row, 3, spin_val)

    def _smazat_vybrany_radek(self, table):
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)

    def _pridat_ukol_vstup(self, ukol_data=None):
        if ukol_data is None:
            ukol_data = {"nazev": "", "minuty": 30, "dni": 1}

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        inp_nazev = QLineEdit(ukol_data.get("nazev", ""))
        inp_nazev.setPlaceholderText("Název úkolu")

        spin_minuty = QSpinBox()
        spin_minuty.setRange(1, 1440)
        spin_minuty.setValue(int(ukol_data.get("minuty", 30)))
        spin_minuty.setSuffix(" min")

        spin_dni = QSpinBox()
        spin_dni.setRange(1, 30)
        spin_dni.setValue(int(ukol_data.get("dni", 1)))
        spin_dni.setSuffix(" dní")

        btn_del = QPushButton("-")
        btn_del.setObjectName("btn_del")
        btn_del.setFixedWidth(28)
        
        # Uchováme plná původní data úkolu (včetně deadline) pro zpětné uložení
        item_ref = {
            "widget": row_widget,
            "nazev": inp_nazev,
            "minuty": spin_minuty,
            "dni": spin_dni,
            "original_data": ukol_data
        }
        self.ukoly_inputs.append(item_ref)

        btn_del.clicked.connect(lambda: self._smazat_ukol_vstup(item_ref))

        row_layout.addWidget(inp_nazev, stretch=2)
        row_layout.addWidget(spin_minuty, stretch=1)
        row_layout.addWidget(spin_dni, stretch=1)
        row_layout.addWidget(btn_del)

        self.layout_seznam_ukolu.addWidget(row_widget)

    def _smazat_ukol_vstup(self, item_ref):
        if item_ref in self.ukoly_inputs:
            self.ukoly_inputs.remove(item_ref)
            item_ref["widget"].deleteLater()

    def _ulozi_nastaveni(self):
        if QApplication.focusWidget():
            QApplication.focusWidget().clearFocus()

        nove_bedtimes = {}
        for den_id, combo in self.combo_vecerky.items():
            nove_bedtimes[den_id] = combo.currentData()

        idx_rez = self.combo_rezerva.currentIndex()
        nova_rezerva = 5 if idx_rez == 0 else (15 if idx_rez == 2 else 10)

        nove_intervaly = []
        for r in range(self.table_intervaly.rowCount()):
            od_v = self.table_intervaly.cellWidget(r, 0).value()
            do_v = self.table_intervaly.cellWidget(r, 1).value()
            typ_v = self.table_intervaly.cellWidget(r, 2).currentData()
            val_v = self.table_intervaly.cellWidget(r, 3).value()
            nove_intervaly.append([od_v, do_v, val_v, typ_v])

        novy_nasobitel = self.spin_nasobitel.value()

        profil_text = self.combo_bot_typ.currentText()
        match = re.search(r"\((.*?)\)", profil_text)
        bot_typ = match.group(1) if match else profil_text[:1].lower()

        queue_int = self.spin_queue_interval.value()

        bonus_aktivni = self.check_bonus.isChecked()
        bonus_procenta = self.spin_bonus_procent.value()

        # Načtení stávajících úkolů z obou souborů pro zachování kompletních dat
        stare_ukoly = []
        if os.path.exists(TASKS_FILE):
            try:
                with open(TASKS_FILE, "r", encoding="utf-8") as f:
                    stare_ukoly = json.load(f)
            except Exception:
                pass
        
        if not stare_ukoly:
            stary_stav = nacti_state()
            stare_ukoly = stary_stav.get("ukoly", [])

        stare_ukoly_dict = {u.get("id") or u.get("nazev"): u for u in stare_ukoly if isinstance(u, dict)}

        nove_ukoly = []
        for inp in self.ukoly_inputs:
            nazev = inp["nazev"].text().strip()
            if nazev:
                orig = inp.get("original_data", {})
                existujici = stare_ukoly_dict.get(orig.get("id") or nazev, orig)
                
                ukol_data = {
                    "id": existujici.get("id", f"task_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"),
                    "nazev": nazev,
                    "minuty": inp["minuty"].value(),
                    "dni": inp["dni"].value(),
                    "rezim": existujici.get("rezim", "jednorazovy"),
                    "frekvence": existujici.get("frekvence"),
                    "reset_cas": existujici.get("reset_cas", "00:00"),
                    "deadline": existujici.get("deadline"),  # Zachová původní deadline
                    "datum_vytvoreni": existujici.get("datum_vytvoreni", date.today().strftime("%Y-%m-%d")),
                    "posledni_reset": existujici.get("posledni_reset", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    "hotovo": existujici.get("hotovo", False)
                }
                nove_ukoly.append(ukol_data)

        # 1. Uložíme přímo do tasks.json
        try:
            with open(TASKS_FILE, "w", encoding="utf-8") as f:
                json.dump(nove_ukoly, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Chyba při ukládání do {TASKS_FILE}: {e}")

        # 2. Uložíme globální stav do state.json
        data_ke_ulozovani = {
            "bedtimes": nove_bedtimes,
            "rezerva": nova_rezerva,
            "pravidla_intervaly": nove_intervaly,
            "nasobitel_ponocovani": novy_nasobitel,
            "bot_typ": bot_typ,
            "queue_interval": queue_int,
            "bonus_aktivni": bonus_aktivni,
            "bonus_procenta": bonus_procenta,
            "ukoly": nove_ukoly
        }

        uloz_state(data_ke_ulozovani)

        if self.on_save_callback:
            sig = inspect.signature(self.on_save_callback)
            if len(sig.parameters) == 0:
                self.on_save_callback()
            else:
                self.on_save_callback(
                    nove_bedtimes,
                    nova_rezerva,
                    nove_intervaly,
                    novy_nasobitel,
                    nove_ukoly,
                    bot_typ,
                    bonus_aktivni,
                    bonus_procenta,
                    queue_int
                )

        self.dialog.accept()