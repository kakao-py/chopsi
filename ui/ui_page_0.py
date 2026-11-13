import pyvisual as pv
from PySide6.QtWidgets import QWidget, QPushButton
from PySide6.QtCore import Qt



def create_page_0_ui(window, ui):
    """
    Create and return UI elements for Page 0.
    """
    ui_page = {}

    ui_page["Image_0"] = pv.PvImage(
        container=window,
        x=-1,
        y=-13,
        image_path='assets/images/5cfc3090ba.png',
        scale=1.0642857142857143,
        corner_radius=0,
        flip_v=False,
        flip_h=False,
        rotate=0,
        border_color=None,
        border_hover_color=None,
        on_hover=None,
        on_click=None,
        on_release=None,
        border_thickness=0,
        border_style="solid",
        is_visible=True,
        opacity=1,
        tag=None,
    )

    # Nadpis úkolů
    ui_page["tasks_title"] = pv.PvText(
        container=window,
        x=25,
        y=13,
        width=270,
        height=28,
        idle_color=(0, 0, 0, 0),
        text='📋 Denní úkoly:',
        is_visible=True,
        text_alignment='left',
        paddings=(0, 0, 0, 0),
        font='assets/fonts/Poppins/Poppins.ttf',
        font_size=15,
        font_color=(13, 92, 86, 255),
        bold=True,
        italic=False,
        underline=False,
        strikethrough=False,
        opacity=1,
        border_color=None,
        corner_radius=0,
        on_hover=None,
        on_click=None,
        on_release=None,
        tag=None,
    )

    # Hlavní kontejner pro úkoly (vlevo, ještě o kousek užší)
    container_ukolu = QWidget(window)
    container_ukolu.setGeometry(25, 48, 310, 320)
    container_ukolu.setStyleSheet("""
        QWidget {
            background-color: rgba(255, 255, 255, 160);
            border-radius: 10px;
        }
    """)
    ui_page["tasks_container"] = container_ukolu

    # Tlačítko pro přidání úkolu (+)
    add_task_btn = QPushButton("+", window)
    add_task_btn.setGeometry(290, 18, 26, 26)
    add_task_btn.setStyleSheet("""
        QPushButton {
            font-size: 15px;
            font-weight: bold;
            color: white;
            background-color: #17d1c6;
            border: none;
            border-radius: 13px;
            padding-bottom: 2px;
        }
        QPushButton:hover {
            background-color: #12b3a9;
        }
    """)
    ui_page["add_task_btn"] = add_task_btn

    # --- PRAVÁ ČÁST: Rámeček pro ponocování  ---
    container_ponocovani = QWidget(window)
    container_ponocovani.setGeometry(375, 48, 310, 320)
    container_ponocovani.setStyleSheet("""
        QWidget {
            background-color: rgba(255, 255, 255, 160);
            border-radius: 10px;
        }
    """)
    ui_page["ponocovani_container"] = container_ponocovani

    # Vizuální pozadí (tyrkysový rámeček pro progress bar + text)
    ui_page["Rectangle_2"] = pv.PvRectangle(
        container=window,
        x=385,
        y=62,
        width=290,
        height=92,
        idle_color=(23, 245, 218, 1),
        border_color=None,
        border_thickness=0,
        corner_radius=8,
        border_style="solid",
        opacity=0.27,
        is_visible=True,
        on_hover=None,
        on_click=None,
        on_release=None,
        tag=None,
    )

    # Progress bar
    ui_page["night_progress"] = pv.PvProgressBar(
        container=window,
        x=397,
        y=70,
        width=266,
        height=38,
        min_value=0,
        max_value=100,
        value=0,
        track_color=(23, 253, 6, 1),
        track_border_color=(0, 0, 0, 1),
        fill_color=(246, 10, 10, 1),
        track_corner_radius=7,
        opacity=0.84,
        idle_color=(255, 255, 255, 0),
        track_border_thickness=0,
        scale=1,
        track_height=28,
        is_circular=False,
        border_thickness=0,
        suffix='%',
        font='assets/fonts/Poppins/Poppins.ttf',
        font_size=12,
        font_color=(0, 0, 0, 1),
        font_color_hover=None,
        bold=False,
        italic=False,
        underline=False,
        strikeout=False,
        is_visible=True,
        is_disabled=False,
        on_hover=None,
        on_click=None,
        on_release=None,
        tag=None,
    )

    # Popisek zbývajícího času
    ui_page["Text_4"] = pv.PvText(
        container=window,
        x=398,
        y=118,
        width=195,
        height=28,
        idle_color=(198, 118, 245, 0),
        text='Zbývající čas pro ponocování:',
        is_visible=True,
        text_alignment='left',
        paddings=(0, 0, 0, 0),
        font='assets/fonts/CrimsonText/CrimsonText.ttf',
        font_size=15,
        font_color=(0, 0, 1, 1),
        bold=False,
        italic=False,
        underline=False,
        strikethrough=False,
        opacity=1,
        border_color=None,
        corner_radius=0,
        on_hover=None,
        on_click=None,
        on_release=None,
        tag=None,
    )

    # Čas ponocování
    ui_page["night_time"] = pv.PvText(
        container=window,
        x=590,
        y=120,
        width=80,
        height=25,
        idle_color=(151, 94, 181, 0),
        text='00:00',
        is_visible=True,
        text_alignment='left',
        paddings=(0, 0, 0, 0),
        font='assets/fonts/SourceCodePro/SourceCodePro.ttf',
        font_size=20,
        font_color=(1, 5, 5, 1),
        bold=False,
        italic=False,
        underline=False,
        strikethrough=False,
        opacity=1,
        border_color=None,
        corner_radius=0,
        on_hover=None,
        on_click=None,
        on_release=None,
        tag=None,
    )

    # Vstup pro čas spánku
    ui_page["sleep_time"] = pv.PvTextInput(
        container=window,
        x=385,
        y=168,
        width=290,
        height=40,
        background_color=(146, 249, 245, 1),
        is_visible=True,
        placeholder='Zde vypište čas spánku',
        text_alignment='left',
        default_text='',
        paddings=(12, 0, 10, 0),
        font='assets/fonts/Ubuntu/Ubuntu.ttf',
        font_size=15,
        font_color=(119, 119, 119, 255),
        border_color=(141, 64, 189, 255),
        border_thickness=1,
        border_style="solid",
        corner_radius=6,
        box_shadow='1px 2px 4px 0px rgba(0,0,0,0.2)',
        icon_path=None,
        icon_scale=0.7,
        icon_position='right',
        icon_spacing=0,
        icon_color=(161, 161, 161, 255),
        text_type='text',
        max_length=None,
        on_hover=None,
        on_click=None,
        on_release=None,
        tag=None,
    )

    # Tlačítko nastavení (⚙) - v dolním pravém rohu pravého rámečku
    settings_btn = QPushButton("⚙", window)
    settings_btn.setGeometry(640, 322, 30, 30)
    settings_btn.setStyleSheet("""
        QPushButton {
            font-size: 15px;
            color: white;
            background-color: #17d1c6;
            border: none;
            border-radius: 15px;
            text-align: center;
        }
        QPushButton:hover {
            background-color: #12b3a9;
        }
    """)
    ui_page["settings_btn"] = settings_btn

    return ui_page