import asyncio
import ctypes
from datetime import date, datetime, timedelta, timezone
import json
import os
import sys
import threading
import glob
import random
import urllib.request

import discord
from discord import app_commands
from PySide6.QtCore import QByteArray, QEvent, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
    QDialog
)

from tasks import (
    AddTaskDialog,
    nacti_ukoly,
    uloz_ukoly,
    spocitej_hodnotu_ukolu,
    vytvor_sipky_png
)
from ui.profile_dialog import ProfileSelectionDialog, nacti_profily
from ui.settings import SettingsPanel, VYCHOZI_INTERVALY, VYCHOZI_NASOBITEL_PONOCOVANI, DEFAULT_BEDTIMES
from ui.ui import create_ui

# --- Nastavení AppUserModelID pro zobrazení ikony ve Windows ---
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Chopsi.App")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

STATE_FILE = os.path.join(BASE_DIR, "state.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

QUEUE_CHANNEL_ID = 1545914426639786015

# --- Nastavení pro automatické aktualizace z GitHubu ---
AKTUALNI_VERZE = "1.0.5"
VERSION_URL = "https://raw.githubusercontent.com/kakao-py/chopsi/refs/heads/main/version.json"
APP_URL = "https://raw.githubusercontent.com/kakao-py/chopsi/refs/heads/main/app.py"


def nacti_token() -> str:
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("bot_token", "").strip()
        except Exception as e:
            print(f"[CHYBA] Nelze načíst token.json: {e}")
    return ""


def zkontrolovat_aktualizace():
    try:
        with urllib.request.urlopen(VERSION_URL, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
            cloudu_verze = data.get("version")
            
            if cloudu_verze and cloudu_verze != AKTUALNI_VERZE:
                print(f"[UPDATE] Nalezena nová verze: {cloudu_verze} (máte: {AKTUALNI_VERZE})")
                
                with urllib.request.urlopen(APP_URL, timeout=5) as app_resp:
                    novy_kod = app_resp.read().decode("utf-8")
                    
                    starý_radek = f'AKTUALNI_VERZE = "{AKTUALNI_VERZE}"'
                    nový_radek = f'AKTUALNI_VERZE = "{cloudu_verze}"'
                    
                    if starý_radek in novy_kod:
                        novy_kod = novy_kod.replace(starý_radek, nový_radek)
                    
                    cesta_k_app = os.path.abspath(__file__)
                    with open(cesta_k_app, "w", encoding="utf-8") as f:
                        f.write(novy_kod)
                
                print("[UPDATE] Aktualizace stažena a verze aktualizována. Restartuji aplikaci...")
                os.execv(sys.executable, [sys.executable] + sys.argv)
                
    except Exception as e:
        print(f"[UPDATE] Kontrola aktualizací selhala (offline?): {e}")


# --- Komunikační můstek pro bezpečné předávání úkolů z vlákna bota do GUI ---
class DiscordBridge(QObject):
    ukol_pridat = Signal(dict)

discord_bridge = DiscordBridge()


def vytvor_fajfku_png() -> str:
    svg_data = b"<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24'><path fill='none' stroke='white' stroke-width='3.5' stroke-linecap='round' stroke-linejoin='round' d='M20 6L9 17l-5-5'/></svg>"
    pixmap = QPixmap(15, 15)
    pixmap.fill(Qt.transparent)

    renderer = QSvgRenderer(QByteArray(svg_data))
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    img_dir = os.path.join(BASE_DIR, "assets", "images")
    os.makedirs(img_dir, exist_ok=True)
    path = os.path.join(img_dir, "temp_check.png")
    pixmap.save(path, "PNG")
    return path.replace("\\", "/")


# ===================================================
# ============== Globální stav aplikace =============
# ===================================================

celkovy_cas_sekund = 0
max_cas_sekund = 0
rezerva_minut = 10
timer = None
nasobitel_ponocovani = VYCHOZI_NASOBITEL_PONOCOVANI
queue_interval_sekund = 10

posledni_kontrolovany_den = None
uz_byl_5min_pred_vecerkou = False
uz_bila_vecerka = False
uz_byl_5min_pred_koncem = False
uz_vyprsel_cas = False

RANNI_HRANICE = 5
jednorazova_vecerka = None

nastaveni_vecerky = DEFAULT_BEDTIMES.copy()
bot_typ_filtru = ""
bonus_aktivni = True
bonus_procenta = 30
pravidla_intervaly = VYCHOZI_INTERVALY

zpracovane_zpravy_ids = set()


def nacti_stav() -> dict:
    global bot_typ_filtru, bonus_aktivni, bonus_procenta, nasobitel_ponocovani, queue_interval_sekund, zpracovane_zpravy_ids, pravidla_intervaly
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                bot_typ_filtru = data.get("bot_typ_filtru", "")
                bonus_aktivni = data.get("bonus_aktivni", True)
                bonus_procenta = data.get("bonus_procenta", 30)
                nasobitel_ponocovani = data.get("nasobitel_ponocovani", 1.0)
                queue_interval_sekund = data.get("queue_interval_sekund", 10)
                zpracovane_zpravy_ids = set(data.get("zpracovane_zpravy_ids", []))
                pravidla_intervaly = data.get("pravidla_intervaly", data.get("intervaly", VYCHOZI_INTERVALY))
                return data
        except Exception:
            pass
    return {
        "last_date": "",
        "celkovy_cas_sekund": 0,
        "max_cas_sekund": 0,
        "bedtimes": DEFAULT_BEDTIMES,
        "rezerva_minut": 10,
        "bot_typ_filtru": "",
        "bonus_aktivni": True,
        "bonus_procenta": 30,
        "nasobitel_ponocovani": 1.0,
        "queue_interval_sekund": 10,
        "zpracovane_zpravy_ids": list(zpracovane_zpravy_ids),
        "pravidla_intervaly": VYCHOZI_INTERVALY
    }


def uloz_stav(dnes_str: str, sekund: float, max_sekund: float, bedtimes: dict, rezerva: int):
    global bot_typ_filtru, bonus_aktivni, bonus_procenta, nasobitel_ponocovani, queue_interval_sekund, zpracovane_zpravy_ids, pravidla_intervaly
    data = {
        "last_date": dnes_str,
        "celkovy_cas_sekund": sekund,
        "max_cas_sekund": max_sekund,
        "bedtimes": bedtimes,
        "rezerva_minut": rezerva,
        "bot_typ_filtru": bot_typ_filtru,
        "bonus_aktivni": bonus_aktivni,
        "bonus_procenta": bonus_procenta,
        "nasobitel_ponocovani": nasobitel_ponocovani,
        "queue_interval_sekund": queue_interval_sekund,
        "zpracovane_zpravy_ids": list(zpracovane_zpravy_ids),
        "pravidla_intervaly": pravidla_intervaly
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def generuj_task_id() -> str:
    return f"task_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def formatuj_cas(sekundy: float) -> str:
    zaporne = sekundy < 0
    celkove_minuty = abs(int(sekundy)) // 60
    hodiny = celkove_minuty // 60
    minuty = celkove_minuty % 60
    s = f"{hodiny:02d}:{minuty:02d}"
    return f"-{s}" if zaporne else s


def aktualizuj_cas_display(night_time_label, sekundy: float):
    vysledek = formatuj_cas(sekundy)
    if hasattr(night_time_label, "setText") and callable(night_time_label.setText):
        night_time_label.setText(vysledek)
    elif hasattr(night_time_label, "set_text") and callable(night_time_label.set_text):
        night_time_label.set_text(vysledek)
    else:
        night_time_label.text = vysledek

    target = night_time_label
    for attr in ["widget", "_widget", "label", "_label"]:
        if hasattr(night_time_label, attr):
            candidate = getattr(night_time_label, attr)
            if candidate is not None:
                target = candidate

    parent = target.parent() if hasattr(target, "parent") else None
    if parent:
        for lbl in parent.findChildren(QLabel):
            txt = lbl.text() if callable(getattr(lbl, "text", None)) else str(getattr(lbl, "text", ""))
            if "čas pro ponocování" in txt.lower() or "dluh" in txt.lower():
                novy_text = "Zbývající dluh:" if sekundy < 0 else "Zbývající čas pro ponocování:"
                if callable(getattr(lbl, "setText", None)):
                    lbl.setText(novy_text)
                else:
                    lbl.text = novy_text


def nacti_sekundy_z_hhmm(text: str) -> int:
    text = text.strip()
    if ":" in text:
        casti = text.split(":")
        return (int(casti[0]) * 3600) + (int(casti[1]) * 60)
    return int(text) * 3600


def vypocitej_cas_ponocovani(sekundy_spanku: float, rezerva: int = 10, pravidla_intervaly: list = None) -> int:
    minuty_spanku = (sekundy_spanku / 60.0) + rezerva
    hodiny_spanku = minuty_spanku / 60.0

    if pravidla_intervaly is None:
        pravidla_intervaly = VYCHOZI_INTERVALY if 'VYCHOZI_INTERVALY' in globals() else [
            {"od": 4.0, "do": 7.0, "typ": "pevna", "odmena": 10},
            {"od": 7.0, "do": 8.0, "typ": "pevna", "odmena": 12},
            {"od": 8.0, "do": 9.0, "typ": "pevna", "odmena": 30},
            {"od": 9.0, "do": 24.0, "typ": "pomer", "odmena": 0.05},
        ]

    posledni_pevna_odmena = 0
    pomerova_odmena_minut = 0.0

    for pravidlo in pravidla_intervaly:
        if isinstance(pravidlo, dict):
            od_h = pravidlo.get("od", 0.0)
            do_h = pravidlo.get("do", 0.0)
            odmena = pravidlo.get("odmena", 0.0)
            typ = pravidlo.get("typ", "pevna")
        else:
            od_h = pravidlo[0]
            do_h = pravidlo[1]
            odmena = pravidlo[2]
            typ = pravidlo[3] if len(pravidlo) > 3 else ("pomer" if odmena <= 5.0 else "pevna")

        if hodiny_spanku >= od_h:
            if typ == "pevna":
                posledni_pevna_odmena = odmena
            elif typ == "pomer":
                cas_v_intervalu_h = min(hodiny_spanku, do_h) - od_h
                if cas_v_intervalu_h > 0:
                    pomerova_odmena_minut += (cas_v_intervalu_h * 60.0) * odmena

    celkova_odmena_minut = posledni_pevna_odmena + pomerova_odmena_minut
    return int(celkova_odmena_minut * 60)


def ziskej_rozmer(obj, atribute_name: str, default: int) -> int:
    val = getattr(obj, atribute_name, default)
    return val() if callable(val) else val


def aktualizuj_progress_bar(ui: dict, aktualni: float, max_val: float):
    pb = ui["page_0"].get("night_progress")
    if not pb:
        return

    is_debt = aktualni < 0

    if is_debt:
        procenta = 100
        text_html = f"zbývající dluh: <b>{formatuj_cas(aktualni)}</b>"
        chunk_color = "#d9534f"
    else:
        procenta = 0 if max_val <= 0 else int(((max_val - aktualni) / max_val) * 100)
        procenta = max(0, min(100, procenta))
        text_html = f"využito: <b>{procenta}%</b>"
        chunk_color = "#00ff22"

    targets = [pb]
    for attr in ["widget", "_widget", "progress_bar", "bar"]:
        if hasattr(pb, attr):
            targets.append(getattr(pb, attr))

    for t in targets:
        q_pbs = []
        if isinstance(t, QProgressBar):
            q_pbs.append(t)
        elif hasattr(t, "findChildren"):
            q_pbs.extend(t.findChildren(QProgressBar))

        for q_pb in q_pbs:
            q_pb.setRange(0, 100)
            q_pb.setValue(procenta)
            q_pb.setTextVisible(False)
            q_pb.setStyleSheet(f"""
                QProgressBar {{
                    background-color: #e0e0e0;
                    border: none;
                    border-radius: 10px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: {chunk_color};
                    border-radius: 10px;
                }}
            """)

            overlay_label = q_pb.findChild(QLabel, "pb_overlay_label")
            if not overlay_label:
                overlay_label = QLabel(q_pb)
                overlay_label.setObjectName("pb_overlay_label")
                overlay_label.setStyleSheet("background: transparent; color: #000000; font-size: 13px;")
                overlay_label.setAlignment(Qt.AlignCenter)
                overlay_label.show()

            w = ziskej_rozmer(q_pb, "width", 200)
            h = ziskej_rozmer(q_pb, "height", 30)
            overlay_label.setGeometry(0, 0, w, h)
            overlay_label.setText(text_html)
            overlay_label.raise_()


# ===================================================
# ============== INTERNÍ DISCORD BOT ===============
# ===================================================

def spustit_discord_bota():
    nacti_stav()
    token = nacti_token()
    if not token:
        print("[BOT CHYBA] Chybí bot_token v souboru token.json!")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    async def vycisti_stare_zadosti(channel):
        nyni_utc = datetime.now(timezone.utc)
        dnes_date = date.today()

        try:
            async for msg in channel.history(limit=100):
                treba_smazat = False
                ma_deadline = False

                if msg.content.startswith("PENDING_CMD:"):
                    try:
                        raw_data = msg.content.replace("PENDING_CMD:", "").strip()
                        data = json.loads(raw_data)
                        
                        deadline_str = data.get("deadline")
                        if not deadline_str and isinstance(data.get("ukol_data"), dict):
                            deadline_str = data.get("ukol_data").get("deadline")

                        if deadline_str:
                            ma_deadline = True
                            try:
                                if "T" in deadline_str or " " in deadline_str:
                                    dl_dt = datetime.fromisoformat(deadline_str)
                                    if dl_dt.tzinfo is None:
                                        dl_dt = dl_dt.replace(tzinfo=timezone.utc)
                                    if nyni_utc > dl_dt:
                                        treba_smazat = True
                                else:
                                    dl_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
                                    if dnes_date > dl_date:
                                        treba_smazat = True
                            except ValueError:
                                pass
                    except Exception:
                        pass

                if not ma_deadline:
                    stari_zpravy = nyni_utc - msg.created_at
                    if stari_zpravy > timedelta(hours=48):
                        treba_smazat = True

                if treba_smazat:
                    try:
                        await msg.delete()
                        print(f"[BOT CLEANUP] Smazána vypršená/stará žádost ID {msg.id}")
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                        print(f"[BOT CLEANUP] Nelze smazat zprávu {msg.id}: {e}")
        except Exception as e:
            print(f"[BOT CLEANUP CHYBA] Nelze projít historii kanálu: {e}")

    async def zkontroluj_frontu_prikazu():
        global celkovy_cas_sekund, max_cas_sekund, bot_typ_filtru, nastaveni_vecerky, rezerva_minut, zpracovane_zpravy_ids

        if not QUEUE_CHANNEL_ID:
            return

        channel = client.get_channel(QUEUE_CHANNEL_ID)
        if not channel:
            try:
                channel = await client.fetch_channel(QUEUE_CHANNEL_ID)
            except Exception:
                return

        if not channel:
            return

        try:
            async for msg in channel.history(limit=50, oldest_first=True):
                if msg.id in zpracovane_zpravy_ids:
                    continue

                if msg.content.startswith("PENDING_CMD:"):
                    try:
                        raw_data = msg.content.replace("PENDING_CMD:", "").strip()
                        data = json.loads(raw_data)
                        target = data.get("target")

                        if target == "v" or target == bot_typ_filtru or data.get("type") == "vypis_ukolu":
                            if target == "v" or data.get("type") == "vypis_ukolu":
                                zpracovane_zpravy_ids.add(msg.id)
                                dnes_str = date.today().strftime("%Y-%m-%d")
                                uloz_stav(dnes_str, celkovy_cas_sekund, max_cas_sekund, nastaveni_vecerky, rezerva_minut)
                            else:
                                try:
                                    await msg.delete()
                                except (discord.NotFound, discord.Forbidden):
                                    zpracovane_zpravy_ids.add(msg.id)
                                    continue

                                zpracovane_zpravy_ids.add(msg.id)
                                dnes_str = date.today().strftime("%Y-%m-%d")
                                uloz_stav(dnes_str, celkovy_cas_sekund, max_cas_sekund, nastaveni_vecerky, rezerva_minut)

                            cmd_type = data.get("type")

                            if cmd_type == "odmena":
                                minuty = data.get("minuty", 0)
                                pridane_sekundy = minuty * 60
                                celkovy_cas_sekund += pridane_sekundy
                                max_cas_sekund += pridane_sekundy

                                dnes_str = date.today().strftime("%Y-%m-%d")
                                uloz_stav(dnes_str, celkovy_cas_sekund, max_cas_sekund, nastaveni_vecerky, rezerva_minut)
                                print(f"[FRONTA] Přijata a uplatněna odměna: +{minuty} minut pro profil {target}.")

                            elif cmd_type == "ukol":
                                ukoly = nacti_ukoly()
                                novy_ukol = data.get("ukol_data")
                                if novy_ukol:
                                    if not any(u.get("id") == novy_ukol.get("id") for u in ukoly):
                                        ukoly.append(novy_ukol)
                                        uloz_ukoly(ukoly)
                                        print(f"[FRONTA] Přijat nový úkol z Discordu: {novy_ukol.get('nazev')} (profil: {target})")
                                        discord_bridge.ukol_pridat.emit(novy_ukol)

                            elif cmd_type == "smazat_ukol":
                                hovory_nazev = data.get("nazev", "").lower()
                                ukoly = nacti_ukoly()
                                
                                nove_ukoly = []
                                smazano = False
                                for u in ukoly:
                                    u_nazev = u.get("nazev", "").lower()
                                    if hovory_nazev in u_nazev or u_nazev in hovory_nazev:
                                        smazano = True
                                        print(f"[FRONTA] Smazán úkol na základě Discord příkazu: {u.get('nazev')}")
                                    else:
                                        nove_ukoly.append(u)
                                        
                                if smazano:
                                    uloz_ukoly(nove_ukoly)
                                    discord_bridge.ukol_pridat.emit({"nazev": "__reload__"})

                            elif cmd_type == "vypis_ukolu":
                                reply_channel_id = data.get("reply_channel_id")
                                cilovy_profil = data.get("target", "v")
                                
                                aktualni_ukoly = nacti_ukoly()
                                
                                vyfiltrovane = []
                                for u in aktualni_ukoly:
                                    u_typ = u.get("typ", "v").lower()
                                    if cilovy_profil == "v" or u_typ == "v" or u_typ == cilovy_profil:
                                        vyfiltrovane.append(u)

                                if not vyfiltrovane:
                                    text_vypisu = f"📋 **Seznam úkolů pro profil: {cilovy_profil.upper()}** *(žádné aktivní úkoly)*"
                                else:
                                    text_vypisu = f"📋 **Seznam úkolů pro profil: {cilovy_profil.upper()}**:\n"
                                    for i, u in enumerate(vyfiltrovane, 1):
                                        nazev = u.get("nazev", "Bez názvu")
                                        minuty = u.get("minuty", 0)
                                        rezim = u.get("rezim", "jednorazovy")
                                        if rezim == "opakujici":
                                            info = f"🔁 Opakující se ({u.get('frekvence', 'denne')})"
                                        else:
                                            dl = u.get("deadline")
                                            info = f"📅 Deadline: {dl}" if dl else "📌 Bez deadlinu"
                                        stav = "✅" if u.get("hotovo", False) else "⏳"
                                        text_vypisu += f"{i}. {stav} **{nazev}** (+{minuty} min) — *{info}*\n"

                                if len(text_vypisu) > 2000:
                                    text_vypisu = text_vypisu[:1997] + "..."

                                target_channel = client.get_channel(reply_channel_id)
                                if not target_channel and reply_channel_id:
                                    try:
                                        target_channel = await client.fetch_channel(reply_channel_id)
                                    except Exception:
                                        target_channel = None

                                if target_channel:
                                    sent_msg = await target_channel.send(text_vypisu)
                                    
                                    try:
                                        await msg.delete()
                                    except Exception:
                                        pass

                                    async def smaz_vypis_po_deseti_minutach(msg_to_del):
                                        await asyncio.sleep(600)
                                        try:
                                            await msg_to_del.delete()
                                        except Exception:
                                            pass

                                    asyncio.create_task(smaz_vypis_po_deseti_minutach(sent_msg))

                    except Exception as e:
                        print(f"[BOT CHYBA QUEUE] Chyba při zpracování zprávy: {e}")
        except Exception as e:
            print(f"[BOT CHYBA QUEUE] Nelze přečíst historii: {e}")

    async def periodicka_kontrola_fronty():
        while True:
            try:
                await zkontroluj_frontu_prikazu()
            except Exception as e:
                print(f"[BOT CHYBA QUEUE] Chyba v periodické kontrole: {e}")

            stav = nacti_stav()
            pauza = max(1, stav.get("queue_interval_sekund", 10))
            await asyncio.sleep(pauza)

    @client.event
    async def on_ready():
        print(f"[BOT] Klient aplikace připojen k Discordu jako {client.user.name}!")
        
        if QUEUE_CHANNEL_ID:
            channel = client.get_channel(QUEUE_CHANNEL_ID)
            if not channel:
                try:
                    channel = await client.fetch_channel(QUEUE_CHANNEL_ID)
                except Exception:
                    channel = None
            if channel:
                print("[BOT] Provádím startovní úklid vypršených a starých žádostí...")
                await vycisti_stare_zadosti(channel)

        if not getattr(client, "task_started", False):
            client.task_started = True
            asyncio.create_task(periodicka_kontrola_fronty())

    try:
        client.run(token)
    except Exception as e:
        print(f"[BOT CHYBA] Klienta se nepodařilo spustit: {e}")


# ===================================================
# ============== EVENT BINDINGS & LOGIC =============
# ===================================================

class TrayEventFilter(QObject):
    def __init__(self, window, tray_icon):
        super().__init__()
        self.window = window
        self.tray_icon = tray_icon

    def eventFilter(self, obj, event):
        if obj == self.window and event.type() == QEvent.Close:
            self.window.hide()
            event.ignore()
            return True
        return super().eventFilter(obj, event)


def attach_events(ui: dict):
    global timer, celkovy_cas_sekund, max_cas_sekund, nastaveni_vecerky, rezerva_minut
    global bot_typ_filtru, bonus_aktivni, bonus_procenta, nasobitel_ponocovani, queue_interval_sekund, uz_vyprsel_cas, pravidla_intervaly
    global jednorazova_vecerka

    check_png_path = vytvor_fajfku_png()

    sleep_input = ui["page_0"]["sleep_time"]
    night_time_label = ui["page_0"]["night_time"]

    win = ui["window"]
    qt_win = getattr(win, "widget", win)

    media_player = QMediaPlayer(qt_win)
    audio_output = QAudioOutput(qt_win)
    media_player.setAudioOutput(audio_output)

    def prehraj_nahodnou_pisen():
        audio_dir = os.path.join(BASE_DIR, "assets", "audio")
        if os.path.exists(audio_dir):
            mp3_soubory = glob.glob(os.path.join(audio_dir, "*.mp3"))
            if mp3_soubory:
                vybrana_pisen = random.choice(mp3_soubory)
                audio_output.setVolume(0.05)
                media_player.setSource(QUrl.fromLocalFile(vybrana_pisen))
                media_player.play()

    dnes = date.today()
    dnes_str = str(dnes)
    stav = nacti_stav()

    nastaveni_vecerky = stav.get("bedtimes", DEFAULT_BEDTIMES)
    rezerva_minut = stav.get("rezerva_minut", 10)
    bot_typ_filtru = stav.get("bot_typ_filtru", "")
    bonus_aktivni = stav.get("bonus_aktivni", True)
    bonus_procenta = stav.get("bonus_procenta", 30)
    nasobitel_ponocovani = stav.get("nasobitel_ponocovani", VYCHOZI_NASOBITEL_PONOCOVANI)
    queue_interval_sekund = stav.get("queue_interval_sekund", 10)
    pravidla_intervaly = stav.get("pravidla_intervaly", stav.get("intervaly", VYCHOZI_INTERVALY))

    if not bot_typ_filtru:
        dialog = ProfileSelectionDialog(qt_win)
        if dialog.exec() == QDialog.Accepted:
            bot_typ_filtru = dialog.selected_profile_code
            uloz_stav(dnes_str, celkovy_cas_sekund, max_cas_sekund, nastaveni_vecerky, rezerva_minut)

    tray_icon = QSystemTrayIcon(qt_win)
    tray_icon.setIcon(QIcon("assets/icons/night-cloud-fog-color-icon.ico"))

    tray_menu = QMenu()

    def show_window():
        qt_win.show()
        qt_win.raise_()
        qt_win.activateWindow()

    def quit_app():
        tray_icon.hide()
        sys.exit(0)

    action_show = tray_menu.addAction("Otevřít")
    action_show.triggered.connect(show_window)
    tray_menu.addSeparator()
    action_quit = tray_menu.addAction("Ukončit")
    action_quit.triggered.connect(quit_app)

    tray_icon.setContextMenu(tray_menu)

    def tray_activated(reason):
        if reason == QSystemTrayIcon.Trigger:
            if qt_win.isVisible():
                qt_win.hide()
            else:
                show_window()

    tray_icon.activated.connect(tray_activated)
    tray_icon.show()

    tray_filter = TrayEventFilter(qt_win, tray_icon)
    qt_win.installEventFilter(tray_filter)

    posledni_datum = stav.get("last_date", "")
    ukoly = nacti_ukoly()

    celkovy_cas_sekund = stav.get("celkovy_cas_sekund", 0)
    max_cas_sekund = max(stav.get("max_cas_sekund", celkovy_cas_sekund), celkovy_cas_sekund)
    uz_vyprsel_cas = celkovy_cas_sekund <= 0

    if posledni_datum != dnes_str:
        uloz_stav(dnes_str, celkovy_cas_sekund, max_cas_sekund, nastaveni_vecerky, rezerva_minut)

    aktualizuj_cas_display(night_time_label, celkovy_cas_sekund)
    aktualizuj_progress_bar(ui, celkovy_cas_sekund, max_cas_sekund)

    container_ukolu = ui["page_0"]["tasks_container"]
    container_ponocovani = ui["page_0"].get("ponocovani_container") or sleep_input.parentWidget()
    add_task_btn = ui["page_0"]["add_task_btn"]
    settings_btn = ui["page_0"]["settings_btn"]

    main_layout = QVBoxLayout(container_ukolu)
    main_layout.setContentsMargins(4, 8, 4, 4)

    # --- ZCELA ODDĚLENÝ BLOK VEČERKY ---
    vecerka_widget = QWidget()
    vecerka_vlayout = QVBoxLayout(vecerka_widget)
    vecerka_vlayout.setContentsMargins(0, 160, 0, 0)
    vecerka_vlayout.setSpacing(0)

    dnesni_vecerka_label = QLabel("Dnešní večerka: --:--")
    dnesni_vecerka_label.setStyleSheet("font-weight: bold; color: #0d5c56; font-size: 15px;")
    dnesni_vecerka_label.setAlignment(Qt.AlignCenter)
    
    vecerka_row2 = QWidget()
    vecerka_hlayout = QHBoxLayout(vecerka_row2)
    vecerka_hlayout.setContentsMargins(0, 0, 0, 100)
    vecerka_hlayout.setSpacing(6)

    jednorazova_input = QLineEdit()
    jednorazova_input.setPlaceholderText("HH:MM")
    jednorazova_input.setFixedWidth(60)
    jednorazova_input.setStyleSheet("background: white; border: 1.5px solid #17d1c6; border-radius: 4px; color: #0d5c56; font-weight: bold; padding: 3px; font-size: 11px;")

    nastavit_vecerku_btn = QPushButton("Nastavit")
    nastavit_vecerku_btn.setStyleSheet("background-color: #17d1c6; color: white; font-weight: bold; border-radius: 4px; padding: 4px 10px; font-size: 11px;")
    
    zacit_vecerku_btn = QPushButton("Začít večerku")
    zacit_vecerku_btn.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold; border-radius: 4px; padding: 4px 10px; font-size: 11px;")

    vecerka_hlayout.addStretch()
    vecerka_hlayout.addWidget(jednorazova_input)
    vecerka_hlayout.addWidget(nastavit_vecerku_btn)
    vecerka_hlayout.addWidget(zacit_vecerku_btn)
    vecerka_hlayout.addStretch()

    vecerka_vlayout.addWidget(dnesni_vecerka_label)
    vecerka_vlayout.addWidget(vecerka_row2)

    pouzity_layout = container_ponocovani.layout()
    if pouzity_layout is None:
        pouzity_layout = QVBoxLayout(container_ponocovani)
        pouzity_layout.setContentsMargins(0, 0, 0, 0)

    pouzity_layout.addWidget(vecerka_widget)

    def aktualizuj_label_vecerky():
        nyni = datetime.now()
        logicky_den = (nyni - timedelta(hours=RANNI_HRANICE)).date()
        dnesni_den_idx = str(logicky_den.weekday())
        
        h = jednorazova_vecerka if jednorazova_vecerka is not None else float(nastaveni_vecerky.get(dnesni_den_idx, 22))
        
        hodiny = int(h)
        minuty = int((h - hodiny) * 60)
        dnesni_vecerka_label.setText(f"Dnešní večerka: {hodiny:02d}:{minuty:02d}")

    globals()['aktualizuj_label_vecerky'] = aktualizuj_label_vecerky
    aktualizuj_label_vecerky()

    def nastavit_jednorazovou():
        global jednorazova_vecerka
        txt = jednorazova_input.text().strip()
        if not txt:
            jednorazova_vecerka = None
        else:
            try:
                if ":" in txt:
                    parts = txt.split(":")
                    jednorazova_vecerka = int(parts[0]) + int(parts[1]) / 60.0
                else:
                    jednorazova_vecerka = float(txt)
            except ValueError:
                pass
        aktualizuj_label_vecerky()

    nastavit_vecerku_btn.clicked.connect(nastavit_jednorazovou)

    def vynutit_vecerku():
        global uz_bila_vecerka, uz_byl_5min_pred_vecerkou, jednorazova_vecerka
        nyni = datetime.now()
        jednorazova_vecerka = nyni.hour + nyni.minute / 60.0
        uz_bila_vecerka = False
        uz_byl_5min_pred_vecerkou = True
        aktualizuj_label_vecerky()

    zacit_vecerku_btn.clicked.connect(vynutit_vecerku)

    def otevrit_dialog_pridani():
        dialog = AddTaskDialog(qt_win)
        if dialog.exec() == QDialog.Accepted:
            novy_ukol = dialog.get_data()
            if novy_ukol["nazev"]:
                novy_ukol["id"] = generuj_task_id()
                novy_ukol["hotovo"] = False
                ukoly.append(novy_ukol)
                uloz_ukoly(ukoly)
                vytvor_checkboxy()

    add_task_btn.clicked.connect(otevrit_dialog_pridani)

    scroll_area = QScrollArea(container_ukolu)
    scroll_area.setWidgetResizable(True)
    scroll_area.setStyleSheet("""
        QScrollArea {
            background: transparent;
            border: none;
        }
        QScrollArea > QWidget > QWidget {
            background: transparent;
        }
        QScrollBar:vertical {
            background: transparent;
            width: 6px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: rgba(13, 92, 86, 120);
            border-radius: 3px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
    """)

    content_widget = QWidget()
    content_widget.setStyleSheet("background: transparent;")
    layout_ukolu = QVBoxLayout(content_widget)
    layout_ukolu.setContentsMargins(4, 4, 4, 4)
    layout_ukolu.setSpacing(3)

    scroll_area.setWidget(content_widget)
    main_layout.addWidget(scroll_area)

    def vytvor_checkboxy():
        nonlocal ukoly
        ukoly = nacti_ukoly()

        while layout_ukolu.count() > 0:
            item = layout_ukolu.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                layout_ukolu.removeItem(item)

        for u in ukoly:
            row_widget = QWidget()
            row_widget.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            left_container = QWidget()
            left_container.setFixedWidth(65)
            left_container.setStyleSheet("background: transparent;")
            left_layout = QVBoxLayout(left_container)
            left_layout.setContentsMargins(0, 0, 0, 0)
            left_layout.setSpacing(0)

            celkova_hodnota = spocitej_hodnotu_ukolu(u, bonus_aktivni, bonus_procenta)
            time_label = QLabel(f"+{celkova_hodnota} min")
            time_label.setAlignment(Qt.AlignCenter)
            time_label.setStyleSheet("color: #17d1c6; font-size: 11px; font-weight: bold; background: transparent;")
            left_layout.addWidget(time_label, 0, Qt.AlignCenter)

            rezim = u.get("rezim", "jednorazovy")
            if rezim == "opakujici":
                freq = u.get("frekvence", "denne")
                freq_str = "(denně)" if freq == "denne" else "(týdně)"
                freq_label = QLabel(freq_str)
                freq_label.setAlignment(Qt.AlignCenter)
                freq_label.setStyleSheet("color: #0d5c56; font-size: 11px; font-weight: bold; background: transparent;")
                left_layout.addWidget(freq_label, 0, Qt.AlignCenter)
            else:
                deadline = u.get("deadline")
                if deadline:
                    try:
                        dl_date = datetime.strptime(deadline, "%Y-%m-%d").date()
                        rozdil_dni = (dl_date - dnes).days

                        if rozdil_dni == 0:
                            zbyva_str = "(dnes)"
                        elif rozdil_dni == 1:
                            zbyva_str = "(1 den)"
                        elif 1 < rozdil_dni < 5:
                            zbyva_str = f"({rozdil_dni} dny)"
                        else:
                            zbyva_str = f"({rozdil_dni} dní)"

                        if zbyva_str:
                            zbyva_label = QLabel(zbyva_str)
                            zbyva_label.setAlignment(Qt.AlignCenter)
                            zbyva_label.setStyleSheet("color: #0d5c56; font-size: 11px; font-weight: bold; background: transparent;")
                            left_layout.addWidget(zbyva_label, 0, Qt.AlignCenter)
                    except ValueError:
                        pass

            row_layout.addWidget(left_container)

            cb = QCheckBox()
            is_done = u.get("hotovo", False)
            cb.setChecked(is_done)
            cb.setStyleSheet(f"""
                QCheckBox {{
                    spacing: 0px;
                    margin: 0px;
                    padding: 2px 0px;
                }}
                QCheckBox::indicator {{
                    width: 15px;
                    height: 15px;
                    border: 1.5px solid #17d1c6;
                    border-radius: 4px;
                    background: transparent;
                }}
                QCheckBox::indicator:checked {{
                    background-color: rgb(30, 218, 98);
                    border-color: rgb(20, 180, 80);
                    image: url("{check_png_path}");
                }}
            """)
            row_layout.addWidget(cb)

            text_label = QLabel(u['nazev'])
            text_label.setWordWrap(True)
            if is_done:
                text_label.setStyleSheet("color: #888888; text-decoration: line-through; font-size: 11px; font-weight: bold; background: transparent;")
            else:
                text_label.setStyleSheet("color: #0d5c56; font-size: 11px; font-weight: bold; background: transparent;")

            text_label.mousePressEvent = lambda event, c=cb: c.setChecked(not c.isChecked())
            row_layout.addWidget(text_label, 1)

            right_buttons_container = QWidget()
            right_buttons_container.setFixedWidth(22)
            right_buttons_container.setStyleSheet("background: transparent;")
            right_buttons_layout = QVBoxLayout(right_buttons_container)
            right_buttons_layout.setContentsMargins(0, 0, 0, 0)
            right_buttons_layout.setSpacing(1)

            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(20, 18)
            edit_btn.setToolTip("Upravit úkol")
            edit_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #0d5c56;
                    font-weight: bold;
                    font-size: 11px;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: rgba(23, 209, 198, 40);
                }
            """)

            del_btn = QPushButton("×")
            del_btn.setFixedSize(20, 18)
            del_btn.setToolTip("Smazat úkol")
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #d9534f;
                    font-weight: bold;
                    font-size: 13px;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: rgba(217, 83, 79, 30);
                }
            """)

            right_buttons_layout.addWidget(edit_btn, 0, Qt.AlignCenter)
            right_buttons_layout.addWidget(del_btn, 0, Qt.AlignCenter)

            row_layout.addWidget(right_buttons_container)

            def make_handler(ukol_ref, checkbox_ref, label_ref):
                def on_change(state):
                    global celkovy_cas_sekund, max_cas_sekund
                    je_hotovo = checkbox_ref.isChecked()

                    if ukol_ref["hotovo"] != je_hotovo:
                        ukol_ref["hotovo"] = je_hotovo

                        ziskane_minuty = spocitej_hodnotu_ukolu(ukol_ref, bonus_aktivni, bonus_procenta)
                        pridano_sekund = ziskane_minuty * 60

                        if je_hotovo:
                            celkovy_cas_sekund += pridano_sekund
                            max_cas_sekund += pridano_sekund
                            label_ref.setStyleSheet("color: #888888; text-decoration: line-through; font-size: 11px; font-weight: bold; background: transparent;")
                        else:
                            celkovy_cas_sekund -= pridano_sekund
                            max_cas_sekund -= pridano_sekund
                            label_ref.setStyleSheet("color: #0d5c56; font-size: 11px; font-weight: bold; background: transparent;")

                        aktualizuj_cas_display(night_time_label, celkovy_cas_sekund)
                        aktualizuj_progress_bar(ui, celkovy_cas_sekund, max_cas_sekund)

                        uloz_stav(dnes_str, celkovy_cas_sekund, max_cas_sekund, nastaveni_vecerky, rezerva_minut)
                        uloz_ukoly(ukoly)
                return on_change

            cb.stateChanged.connect(make_handler(u, cb, text_label))

            def make_edit_handler(ukol_ref):
                def on_click():
                    global celkovy_cas_sekund, max_cas_sekund
                    dialog = AddTaskDialog(qt_win, task_data=ukol_ref)
                    if dialog.exec() == QDialog.Accepted:
                        nova_data = dialog.get_data()

                        stare_minuty = spocitej_hodnotu_ukolu(ukol_ref, bonus_aktivni, bonus_procenta) if ukol_ref.get("hotovo", False) else 0

                        ukol_ref["nazev"] = nova_data["nazev"]
                        ukol_ref["minuty"] = nova_data["minuty"]
                        ukol_ref["rezim"] = nova_data["rezim"]
                        ukol_ref["frekvence"] = nova_data["frekvence"]
                        ukol_ref["reset_cas"] = nova_data["reset_cas"]
                        ukol_ref["deadline"] = nova_data["deadline"]

                        nove_minuty = spocitej_hodnotu_ukolu(ukol_ref, bonus_aktivni, bonus_procenta) if ukol_ref.get("hotovo", False) else 0
                        rozdil = nove_minuty - stare_minuty

                        if rozdil != 0 and ukol_ref.get("hotovo", False):
                            celkovy_cas_sekund += rozdil * 60
                            max_cas_sekund += rozdil * 60
                            aktualizuj_cas_display(night_time_label, celkovy_cas_sekund)
                            aktualizuj_progress_bar(ui, celkovy_cas_sekund, max_cas_sekund)
                            uloz_stav(dnes_str, celkovy_cas_sekund, max_cas_sekund, nastaveni_vecerky, rezerva_minut)

                        uloz_ukoly(ukoly)
                        vytvor_checkboxy()
                return on_click

            edit_btn.clicked.connect(make_edit_handler(u))

            def make_del_handler(ukol_ref):
                def on_click():
                    ukoly.remove(ukol_ref)
                    uloz_ukoly(ukoly)
                    vytvor_checkboxy()
                return on_click

            del_btn.clicked.connect(make_del_handler(u))

            layout_ukolu.addWidget(row_widget)

        layout_ukolu.addStretch(1)

    vytvor_checkboxy()
    container_ukolu.show()

    def on_discord_task_received(novy_ukol):
        nonlocal ukoly
        ukoly = nacti_ukoly()
        vytvor_checkboxy()
        if novy_ukol.get("nazev") != "__reload__":
            zobraz_toast("Přijat úkol z Discordu!", typ="success")
        else:
            zobraz_toast("Úkol smazán z Discordu!", typ="error")

    discord_bridge.ukol_pridat.connect(on_discord_task_received)

    targets = [sleep_input]
    for attr in ["widget", "_widget", "input", "_input"]:
        if hasattr(sleep_input, attr):
            targets.append(getattr(sleep_input, attr))

    if hasattr(sleep_input, "findChildren"):
        targets.extend(sleep_input.findChildren(QLineEdit))

    for target in targets:
        if isinstance(target, QLineEdit):
            target.setValidator(None)
            target.setInputMask("")
            target.returnPressed.connect(lambda: potvrdit())

    def callback_ulozeni_nastaveni(nove_vecerky, nova_rezerva, nove_intervaly, novy_nasobitel_ponocovani, nove_ukoly, novy_bot_typ, novy_bonus_aktivni, novy_bonus_procenta, novy_queue_interval):
        global nastaveni_vecerky, rezerva_minut, bot_typ_filtru, bonus_aktivni, bonus_procenta, nasobitel_ponocovani, queue_interval_sekund, pravidla_intervaly
        nastaveni_vecerky.update(nove_vecerky)
        rezerva_minut = nova_rezerva
        bot_typ_filtru = novy_bot_typ
        bonus_aktivni = novy_bonus_aktivni
        bonus_procenta = novy_bonus_procenta
        nasobitel_ponocovani = novy_nasobitel_ponocovani
        queue_interval_sekund = novy_queue_interval
        pravidla_intervaly = nove_intervaly

        uloz_stav(dnes_str, celkovy_cas_sekund, max_cas_sekund, nastaveni_vecerky, rezerva_minut)
        
        nonlocal ukoly
        vytvor_checkboxy()
        aktualizuj_label_vecerky()

    settings_panel = SettingsPanel(qt_win, nastaveni_vecerky, callback_ulozeni_nastaveni)

    def otvrit_nastaveni():
        aktualni_ukoly = nacti_ukoly()
        settings_panel.otvrit_panel(
            bedtimes=nastaveni_vecerky,
            aktualni_rezerva=rezerva_minut,
            pravidla_intervaly=pravidla_intervaly,
            nasobitel_ponocovani=nasobitel_ponocovani,
            ukoly=aktualni_ukoly,
            bot_typ_filtru=bot_typ_filtru,
            bonus_aktivni=bonus_aktivni,
            bonus_procenta=bonus_procenta,
            queue_interval_sekund=queue_interval_sekund
        )

    settings_btn.clicked.connect(otvrit_nastaveni)

    def zobraz_toast(text="Zapsáno!", trvani_ms=2000, typ="success"):
        bg_color = "#2ecc71" if typ == "success" else "#d9534f"

        toast = QLabel(text, qt_win)
        toast.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 16px;
                border-radius: 12px;
            }}
        """)
        toast.adjustSize()

        win_w = ziskej_rozmer(qt_win, "width", 300)
        win_h = ziskej_rozmer(qt_win, "height", 400)
        toast_w = ziskej_rozmer(toast, "width", 100)
        toast_h = ziskej_rozmer(toast, "height", 30)

        x = (win_w - toast_w) // 2
        y = win_h - toast_h - 25
        toast.move(x, y)
        toast.show()
        toast.raise_()

        QTimer.singleShot(trvani_ms, toast.deleteLater)

    def potvrdit(*args):
        global celkovy_cas_sekund, max_cas_sekund

        hodnota_text = str(getattr(sleep_input, "text", "")).strip()
        if not hodnota_text and hasattr(sleep_input, "get_text"):
            hodnota_text = str(sleep_input.get_text()).strip()

        if not hodnota_text:
            for t in targets:
                if isinstance(t, QLineEdit) and t.text().strip():
                    hodnota_text = t.text().strip()
                    break

        if hodnota_text:
            try:
                sekundy_spanku = nacti_sekundy_z_hhmm(hodnota_text)
                
                stav_app = nacti_stav()
                aktualni_intervaly = stav_app.get("pravidla_intervaly", stav_app.get("intervaly", VYCHOZI_INTERVALY))
                
                pridane_sekundy = vypocitej_cas_ponocovani(
                    sekundy_spanku, 
                    rezerva=rezerva_minut, 
                    pravidla_intervaly=aktualni_intervaly
                )

                celkovy_cas_sekund += pridane_sekundy
                max_cas_sekund = celkovy_cas_sekund

                aktualizuj_cas_display(night_time_label, celkovy_cas_sekund)
                aktualizuj_progress_bar(ui, celkovy_cas_sekund, max_cas_sekund)

                uloz_stav(dnes_str, celkovy_cas_sekund, max_cas_sekund, nastaveni_vecerky, rezerva_minut)

                if hasattr(sleep_input, "setText"):
                    sleep_input.setText("")
                if hasattr(sleep_input, "clear"):
                    sleep_input.clear()
                for t in targets:
                    if isinstance(t, QLineEdit):
                        t.clear()

                zobraz_toast("Zapsáno!", typ="success")

            except (ValueError, IndexError):
                zobraz_toast("Neplatný formát!", typ="error")
        else:
            zobraz_toast("Zadejte čas!", typ="error")

    def tik_odpocitavani():
        global posledni_kontrolovany_den, uz_byl_5min_pred_vecerkou, uz_bila_vecerka
        global uz_byl_5min_pred_koncem, uz_vyprsel_cas, jednorazova_vecerka
        global celkovy_cas_sekund, max_cas_sekund

        nyni = datetime.now()
        logicky_den = (nyni - timedelta(hours=RANNI_HRANICE)).date()
        dnes_str_lokal = str(logicky_den)

        if posledni_kontrolovany_den != logicky_den:
            posledni_kontrolovany_den = logicky_den
            uz_byl_5min_pred_vecerkou = False
            uz_bila_vecerka = False
            uz_byl_5min_pred_koncem = False
            uz_vyprsel_cas = False
            
            jednorazova_vecerka = None
            if 'aktualizuj_label_vecerky' in globals():
                globals()['aktualizuj_label_vecerky']()

        dnesni_den_idx = str(logicky_den.weekday())
        
        if jednorazova_vecerka is not None:
            hodina_vecerky = float(jednorazova_vecerka)
        else:
            hodina_vecerky = float(nastaveni_vecerky.get(dnesni_den_idx, 22))

        vecerka_datum = logicky_den
        if hodina_vecerky < RANNI_HRANICE:
            vecerka_datum = logicky_den + timedelta(days=1)

        vecerka_dt = datetime.combine(vecerka_datum, datetime.min.time()) + timedelta(hours=hodina_vecerky)
        pred_vecerkou_dt = vecerka_dt - timedelta(minutes=5)
        konec_logickeho_dne_dt = datetime.combine(logicky_den + timedelta(days=1), datetime.min.time()) + timedelta(hours=RANNI_HRANICE)

        if not uz_byl_5min_pred_vecerkou and pred_vecerkou_dt <= nyni < vecerka_dt:
            uz_byl_5min_pred_vecerkou = True

        if not uz_bila_vecerka and vecerka_dt <= nyni < vecerka_dt + timedelta(minutes=1):
            uz_bila_vecerka = True
            prehraj_nahodnou_pisen()

        je_po_vecerce = vecerka_dt <= nyni < konec_logickeho_dne_dt

        aktualizuj_cas_display(night_time_label, celkovy_cas_sekund)
        aktualizuj_progress_bar(ui, celkovy_cas_sekund, max_cas_sekund)

        if je_po_vecerce:
            ubytek = nasobitel_ponocovani if celkovy_cas_sekund <= 0 else 1.0
            celkovy_cas_sekund = round(celkovy_cas_sekund - ubytek, 2)

            if not uz_byl_5min_pred_koncem and 0 < celkovy_cas_sekund <= 300:
                uz_byl_5min_pred_koncem = True

            if not uz_vyprsel_cas and celkovy_cas_sekund <= 0:
                uz_vyprsel_cas = True

            if int(celkovy_cas_sekund) % 60 == 0:
                uloz_stav(dnes_str_lokal, celkovy_cas_sekund, max_cas_sekund, nastaveni_vecerky, rezerva_minut)

    timer = QTimer(qt_win)
    timer.timeout.connect(tik_odpocitavani)
    timer.start(1000)


# ===================================================
# ============== MAIN FUNCTION ======================
# ===================================================

def main():
    zkontrolovat_aktualizace()

    bot_thread = threading.Thread(target=spustit_discord_bota, daemon=True)
    bot_thread.start()

    q_app = QApplication.instance()
    if not q_app:
        q_app = QApplication(sys.argv)

    q_app.setQuitOnLastWindowClosed(False)
    q_app.setWindowIcon(QIcon("assets/icons/night-cloud-fog-color-icon.ico"))

    up_path, down_path = vytvor_sipky_png()

    q_app.setStyleSheet(f"""
        QAbstractSpinBox {{
            background-color: white;
            border: 1.5px solid #17d1c6;
            border-radius: 4px;
            padding: 4px;
            padding-right: 22px;
            color: #0d5c56;
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
    """)

    ui = create_ui()
    attach_events(ui)

    win = ui["window"]
    qt_win = getattr(win, "widget", win)
    qt_win.show()

    sys.exit(q_app.exec())


if __name__ == '__main__':
    main()
