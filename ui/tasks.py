from datetime import date, datetime
import json
import os

from PySide6.QtCore import QByteArray, QDate, QTime, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTimeEdit,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TASKS_FILE = os.path.join(BASE_DIR, "tasks.json")


def vytvor_sipky_png():
    """Vytvoří PNG ikony šipek a fajfky pro Qt prvky."""
    up_svg = b"<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24'><path fill='none' stroke='#0d5c56' stroke-width='3.5' stroke-linecap='round' stroke-linejoin='round' d='M18 15l-6-6-6 6'/></svg>"
    down_svg = b"<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24'><path fill='none' stroke='#0d5c56' stroke-width='3.5' stroke-linecap='round' stroke-linejoin='round' d='M6 9l6 6 6-6'/></svg>"
    check_svg = b"<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24'><path fill='none' stroke='white' stroke-width='4' stroke-linecap='round' stroke-linejoin='round' d='M20 6L9 17l-5-5'/></svg>"

    up_path = os.path.join(BASE_DIR, "assets", "images", "temp_up_arrow.png").replace("\\", "/")
    down_path = os.path.join(BASE_DIR, "assets", "images", "temp_down_arrow.png").replace("\\", "/")
    check_path = os.path.join(BASE_DIR, "assets", "images", "temp_check.png").replace("\\", "/")

    pix_up = QPixmap(12, 12)
    pix_up.fill(Qt.transparent)
    r_up = QSvgRenderer(QByteArray(up_svg))
    p_up = QPainter(pix_up)
    r_up.render(p_up)
    p_up.end()
    pix_up.save(up_path, "PNG")

    pix_down = QPixmap(12, 12)
    pix_down.fill(Qt.transparent)
    r_down = QSvgRenderer(QByteArray(down_svg))
    p_down = QPainter(pix_down)
    r_down.render(p_down)
    p_down.end()
    pix_down.save(down_path, "PNG")

    pix_check = QPixmap(12, 12)
    pix_check.fill(Qt.transparent)
    r_check = QSvgRenderer(QByteArray(check_svg))
    p_check = QPainter(pix_check)
    r_check.render(p_check)
    p_check.end()
    pix_check.save(check_path, "PNG")

    return up_path, down_path


def zmeni_stav_ukolu(ukol: dict, hotovo: bool):
    """Pomocná funkce pro přepnutí stavu úkolu.
    Při splnění aktualizuje timestamp, aby se vědělo, kdy byl úkol dokončen.
    """
    ukol["hotovo"] = hotovo
    ukol["posledni_reset"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def nacti_ukoly() -> list:
    if not os.path.exists(TASKS_FILE):
        return []

    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            ukoly = json.load(f)

        dnes = date.today()
        nynajsi_dt = datetime.now()
        dnes_str = dnes.strftime("%Y-%m-%d")
        aktivni_ukoly = []
        zmeneno = False

        for u in ukoly:
            if "datum_vytvoreni" not in u:
                u["datum_vytvoreni"] = dnes_str
                zmeneno = True
            if "rezim" not in u:
                u["rezim"] = "jednorazovy"
                zmeneno = True
            if "frekvence" not in u:
                u["frekvence"] = None
                zmeneno = True
            if "reset_cas" not in u:
                u["reset_cas"] = "00:00"
                zmeneno = True
            if "posledni_reset" not in u:
                u["posledni_reset"] = nynajsi_dt.strftime("%Y-%m-%d %H:%M:%S")
                zmeneno = True
            if "hotovo" not in u:
                u["hotovo"] = False
                zmeneno = True

            # -------------------------------------------------------------
            # 1. Logika pro Jednorázové úkoly
            # -------------------------------------------------------------
            if u["rezim"] == "jednorazovy":
                if u.get("hotovo"):
                    p_reset = u.get("posledni_reset", u.get("datum_vytvoreni", dnes_str))
                    try:
                        p_reset_date = datetime.strptime(p_reset[:10], "%Y-%m-%d").date()
                        if p_reset_date < dnes:
                            zmeneno = True
                            continue  
                    except Exception:
                        pass

                deadline = u.get("deadline")
                if deadline:
                    try:
                        dl_date = datetime.strptime(deadline, "%Y-%m-%d").date()
                        if dl_date < dnes:
                            zmeneno = True
                            continue
                    except ValueError:
                        pass

            # -------------------------------------------------------------
            # 2. Logika pro Opakující se úkoly
            # -------------------------------------------------------------
            elif u["rezim"] == "opakujici":
                p_reset = u.get("posledni_reset", nynajsi_dt.strftime("%Y-%m-%d %H:%M:%S"))
                freq = u.get("frekvence", "denne")
                if freq:
                    freq = freq.lower().replace("ě", "e").replace("ý", "y")
                else:
                    freq = "denne"

                reset_cas_str = u.get("reset_cas", "00:00")

                try:
                    if len(p_reset) == 10:
                        p_reset += " 00:00:00"
                    p_reset_dt = datetime.strptime(p_reset, "%Y-%m-%d %H:%M:%S")

                    try:
                        hod, min_ = map(int, reset_cas_str.split(":"))
                    except Exception:
                        hod, min_ = 0, 0

                    dnesni_reset_dt = datetime.combine(dnes, datetime.min.time()).replace(hour=hod, minute=min_)

                    if nynajsi_dt >= dnesni_reset_dt and p_reset_dt < dnesni_reset_dt:
                        is_denne = (freq == "denne")
                        is_tydne = (freq == "tydne" and (dnes - p_reset_dt.date()).days >= 7)

                        if is_denne or is_tydne:
                            u["hotovo"] = False
                            u["posledni_reset"] = nynajsi_dt.strftime("%Y-%m-%d %H:%M:%S")
                            zmeneno = True

                    elif freq == "denne" and (dnes - p_reset_dt.date()).days >= 1:
                        u["hotovo"] = False
                        u["posledni_reset"] = nynajsi_dt.strftime("%Y-%m-%d %H:%M:%S")
                        zmeneno = True

                except Exception:
                    pass

            aktivni_ukoly.append(u)

        if zmeneno:
            uloz_ukoly(aktivni_ukoly)
        return aktivni_ukoly
    except Exception:
        return []


def uloz_ukoly(ukoly: list):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(ukoly, f, indent=4, ensure_ascii=False)


def spocitej_hodnotu_ukolu(ukol: dict, bonus_aktivni: bool = True, bonus_procenta: int = 30) -> int:
    zakladni_minuty = ukol.get("minuty", 5)
    ziskane_minuty = zakladni_minuty

    if bonus_aktivni:
        dl_str = ukol.get("deadline")
        dnes = date.today()
        if dl_str and ukol.get("rezim", "jednorazovy") == "jednorazovy":
            try:
                dl_date = datetime.strptime(dl_str, "%Y-%m-%d").date()
                if (dl_date - dnes).days >= 3:
                    ziskane_minuty += int(zakladni_minuty * (bonus_procenta / 100))
            except Exception:
                pass
    return ziskane_minuty


class AddTaskDialog(QDialog):
    def __init__(self, parent=None, task_data=None):
        super().__init__(parent)
        self.task_data = task_data or {}
        is_edit = task_data is not None
        self.setWindowTitle("Upravit úkol" if is_edit else "Nový úkol")
        self.setFixedSize(300, 320)

        up_path, down_path = vytvor_sipky_png()
        check_path = os.path.join(BASE_DIR, "assets", "images", "temp_check.png").replace("\\", "/")

        self.setStyleSheet(f"""
            QDialog {{
                background-color: #f0fcfb;
                color: #0d5c56;
                font-family: 'Poppins', sans-serif;
            }}
            QLabel {{
                font-weight: bold;
                color: #0d5c56;
                background: transparent;
            }}
            QLineEdit, QComboBox, QAbstractSpinBox {{
                background-color: white;
                border: 1.5px solid #17d1c6;
                border-radius: 4px;
                padding: 4px;
                color: #0d5c56;
            }}
            QCheckBox {{
                color: #0d5c56;
                font-weight: bold;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                background: white;
                border: 1.5px solid #17d1c6;
                border-radius: 3px;
            }}
            QCheckBox::indicator:checked {{
                background: #17d1c6;
                image: url("{check_path}");
            }}
            QAbstractSpinBox {{
                padding-right: 22px;
            }}
            QAbstractSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 18px;
                background-color: #d1f5f2;
                border-left: 1px solid #17d1c6;
                border-bottom: 1px solid #17d1c6;
                border-top-right-radius: 3px;
            }}
            QAbstractSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 18px;
                background-color: #d1f5f2;
                border-left: 1px solid #17d1c6;
                border-bottom-right-radius: 3px;
            }}
            QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
                background-color: #17d1c6;
            }}
            QAbstractSpinBox::up-arrow {{
                image: url("{up_path}");
                width: 10px;
                height: 10px;
            }}
            QAbstractSpinBox::down-arrow {{
                image: url("{down_path}");
                width: 10px;
                height: 10px;
            }}
            QPushButton {{
                background-color: #17d1c6;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: #12b3a9;
            }}
        """)

        layout = QFormLayout(self)

        self.nazev_input = QLineEdit()
        self.nazev_input.setPlaceholderText("např. Vyřídit úřad")
        layout.addRow("Název:", self.nazev_input)

        self.minuty_spin = QSpinBox()
        self.minuty_spin.setRange(1, 180)
        self.minuty_spin.setValue(10)
        layout.addRow("Odměna (min):", self.minuty_spin)

        self.rezim_combo = QComboBox()
        self.rezim_combo.addItems(["Jednorázový", "Opakovaný"])
        self.rezim_combo.currentIndexChanged.connect(self.zmenit_rezim)
        layout.addRow("Typ úkolu:", self.rezim_combo)

        self.frekvence_combo = QComboBox()
        self.frekvence_combo.addItems(["Denně", "Týdně"])
        self.frekvence_label = QLabel("Frekvence:")
        layout.addRow(self.frekvence_label, self.frekvence_combo)

        self.reset_time_edit = QTimeEdit()
        self.reset_time_edit.setTime(QTime(0, 0))
        self.reset_time_label = QLabel("Čas resetu:")
        layout.addRow(self.reset_time_label, self.reset_time_edit)

        self.bez_deadlinu_cb = QCheckBox("Bez deadlinu")
        self.bez_deadlinu_cb.toggled.connect(self.zmenit_bez_deadlinu)
        layout.addRow("", self.bez_deadlinu_cb)

        self.deadline_date = QDateEdit()
        self.deadline_date.setCalendarPopup(True)
        self.deadline_date.setDate(QDate.currentDate())
        self.deadline_date.setDisplayFormat("dd. MM. yyyy")

        kalendar = self.deadline_date.calendarWidget()
        kalendar.setStyleSheet("""
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #f0fcfb;
                border-bottom: 1.5px solid #17d1c6;
            }
            QCalendarWidget QToolButton {
                color: #0d5c56;
                background-color: transparent;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px;
                margin: 2px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: rgba(23, 209, 198, 40);
            }
            QCalendarWidget QAbstractItemView:enabled {
                background-color: white;
                color: #0d5c56;
                selection-background-color: #17d1c6;
                selection-color: white;
                border: none;
            }
            QCalendarWidget QAbstractItemView:disabled {
                color: #b0c4c3;
            }
            QCalendarWidget QMenu, QCalendarWidget QSpinBox {
                background-color: white;
                color: #0d5c56;
                border: 1px solid #17d1c6;
            }
        """)

        self.deadline_label = QLabel("Platí do:")
        layout.addRow(self.deadline_label, self.deadline_date)

        self.puvodni_datum_vytvoreni = date.today().strftime("%Y-%m-%d")

        if is_edit:
            self.nazev_input.setText(task_data.get("nazev", ""))
            self.minuty_spin.setValue(task_data.get("minuty", 10))
            self.puvodni_datum_vytvoreni = task_data.get("datum_vytvoreni", date.today().strftime("%Y-%m-%d"))

            rezim = task_data.get("rezim", "jednorazovy")
            if rezim == "opakujici":
                self.rezim_combo.setCurrentIndex(1)
                freq = task_data.get("frekvence", "denne")
                if freq:
                    freq = freq.lower().replace("ě", "e").replace("ý", "y")
                self.frekvence_combo.setCurrentIndex(1 if freq == "tydne" else 0)
                r_cas = task_data.get("reset_cas", "00:00")
                try:
                    self.reset_time_edit.setTime(QTime.fromString(r_cas, "HH:mm"))
                except Exception:
                    pass
            else:
                self.rezim_combo.setCurrentIndex(0)
                dl = task_data.get("deadline")
                if dl:
                    try:
                        self.deadline_date.setDate(QDate.fromString(dl, "yyyy-MM-dd"))
                        self.bez_deadlinu_cb.setChecked(False)
                    except Exception:
                        self.bez_deadlinu_cb.setChecked(True)
                else:
                    self.bez_deadlinu_cb.setChecked(True)

        self.zmenit_rezim(self.rezim_combo.currentIndex())

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def zmenit_rezim(self, index: int):
        is_recurring = (index == 1)
        self.frekvence_label.setVisible(is_recurring)
        self.frekvence_combo.setVisible(is_recurring)
        self.reset_time_label.setVisible(is_recurring)
        self.reset_time_edit.setVisible(is_recurring)

        is_one_time = not is_recurring
        self.bez_deadlinu_cb.setVisible(is_one_time)
        
        show_deadline = is_one_time and not self.bez_deadlinu_cb.isChecked()
        self.deadline_label.setVisible(show_deadline)
        self.deadline_date.setVisible(show_deadline)

    def zmenit_bez_deadlinu(self, checked: bool):
        is_one_time = (self.rezim_combo.currentIndex() == 0)
        show_deadline = is_one_time and not checked
        self.deadline_label.setVisible(show_deadline)
        self.deadline_date.setVisible(show_deadline)

    def get_data(self) -> dict:
        rezim = "opakujici" if self.rezim_combo.currentIndex() == 1 else "jednorazovy"
        frekvence = ("denne" if self.frekvence_combo.currentIndex() == 0 else "tydne") if rezim == "opakujici" else None
        
        if rezim == "jednorazovy" and not self.bez_deadlinu_cb.isChecked():
            deadline = self.deadline_date.date().toString("yyyy-MM-dd")
        else:
            deadline = None

        reset_cas = self.reset_time_edit.time().toString("HH:mm") if rezim == "opakujici" else "00:00"

        return {
            "nazev": self.nazev_input.text().strip(),
            "minuty": self.minuty_spin.value(),
            "rezim": rezim,
            "frekvence": frekvence,
            "reset_cas": reset_cas,
            "deadline": deadline,
            "datum_vytvoreni": self.puvodni_datum_vytvoreni,
            "posledni_reset": self.task_data.get("posledni_reset", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "hotovo": self.task_data.get("hotovo", False),
        }