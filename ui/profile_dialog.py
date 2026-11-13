import os
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, 
    QLineEdit, QPushButton, QFormLayout
)

# Nastavení cesty k profiles.json (v kořenovém adresáři o úroveň výš)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_FILE = os.path.join(BASE_DIR, "profiles.json")


def nacti_profily():
    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("profily", [])
        except Exception:
            pass
    return []


def uloz_novy_profil(nazev, zkratka):
    profily = nacti_profily()
    polozka = f"{nazev} ({zkratka})"
    if polozka not in profily:
        profily.append(polozka)
        with open(PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump({"profily": profily}, f, indent=4, ensure_ascii=False)
    return zkratka


def smazat_profil_ze_souboru(identifikator):
    if not os.path.exists(PROFILES_FILE):
        return False
    
    try:
        with open(PROFILES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        profily = data.get("profily", [])
        nove_profily = []
        smazano = False
        
        for p in profily:
            if identifikator.lower() in p.lower():
                smazano = True
                continue
            nove_profily.append(p)
            
        if smazano:
            data["profily"] = nove_profily
            with open(PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
    except Exception as e:
        print(f"[CHYBA] Nepodařilo se smazat profil: {e}")
        
    return False


class ProfileSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Výběr profilu")
        self.setFixedSize(320, 270)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.selected_profile_code = ""

        self.setStyleSheet("""
            QDialog {
                background-color: #f0fcfb;
                color: #0d5c56;
                font-family: 'Poppins', sans-serif;
            }
            QLabel {
                font-weight: bold;
                color: #0d5c56;
            }
            QComboBox, QLineEdit {
                background-color: white;
                border: 1.5px solid #17d1c6;
                border-radius: 4px;
                padding: 4px;
                color: #0d5c56;
            }
            QPushButton {
                background-color: #17d1c6;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #12b3a9;
            }
        """)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Vyberte stávající profil:"))
        self.combo = QComboBox()
        self.profily = nacti_profily()
        for p in self.profily:
            self.combo.addItem(p)
        layout.addWidget(self.combo)

        layout.addWidget(QLabel("— NEBO vytvořte nový profil —"))

        form_layout = QFormLayout()
        self.new_name_input = QLineEdit()
        self.new_name_input.setPlaceholderText("např. Karel")
        self.new_code_input = QLineEdit()
        self.new_code_input.setPlaceholderText("např. k")
        self.new_code_input.setMaxLength(3)

        form_layout.addRow("Jméno:", self.new_name_input)
        form_layout.addRow("Zkratka/Kód:", self.new_code_input)
        layout.addLayout(form_layout)

        btn_confirm = QPushButton("Potvrdit a vstoupit")
        btn_confirm.clicked.connect(self.potvrdit)
        layout.addWidget(btn_confirm)

    def potvrdit(self):
        novne_jmeno = self.new_name_input.text().strip()
        nova_zkratka = self.new_code_input.text().strip().lower()

        if novne_jmeno and nova_zkratka:
            uloz_novy_profil(novne_jmeno, nova_zkratka)
            self.selected_profile_code = nova_zkratka
            self.accept()
        elif self.combo.count() > 0:
            vybrana_polozka = self.combo.currentText()
            if "(" in vybrana_polozka and ")" in vybrana_polozka:
                self.selected_profile_code = vybrana_polozka.split("(")[-1].replace(")", "").strip().lower()
            else:
                self.selected_profile_code = vybrana_polozka.strip().lower()[:1]
            self.accept()