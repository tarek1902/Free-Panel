#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
sys.path.append('/usr/lib/enigma2/python/Plugins/Extensions/Free-Panel')
from Screens.Console import Console
import codecs
import io
from enigma import getDesktop
from datetime import datetime as dt
from json import loads
from re import compile, search, DOTALL
from shutil import copy2
from subprocess import CalledProcessError, check_output
from sys import version_info

from os import R_OK, access, chmod, makedirs, system, walk
from os.path import exists, join

import six
import requests
from six.moves.urllib.error import URLError
from six.moves.urllib.request import Request, urlopen
from Components.VideoWindow import VideoWindow

from Components.ActionMap import ActionMap
from Components.AVSwitch import AVSwitch
from Components.config import config
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from Components.Pixmap import MovingPixmap, Pixmap
from Components.PluginComponent import plugins
from Components.ScrollLabel import ScrollLabel
from Components.Sources.StaticText import StaticText
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from Tools.Directories import SCOPE_PLUGINS, fileExists, resolveFilename
from enigma import (
    RT_HALIGN_RIGHT,
    RT_VALIGN_CENTER,
    eListboxPythonMultiContent,
    ePicLoad,
    eTimer,
    gFont,
    loadPNG,
)

from . import (
    _,
    AgentRequest,
    CheckConn,
    add_skin_fonts,
    b64decoder,
    checkGZIP,
    check_version,
    developer_url,
    freespace,
    installer_url,
    isWQHD,
    isFHD,
    isHD,
    RequestUrl,
    make_request,
    refreshPlugins,
    xmlurl,
    HALIGN,
)
from .menus.NewOeSk import ctrlSkin
from .Console import Console

PLUGIN_VERSION = "2.0.0"
VERSION_URL = "https://gitlab.com/hanfy1971/plugin/-/raw/main/EMAILPANEL/version.tx"
UPDATE_SCRIPT_URL = "https://gitlab.com/hanfy1971/plugin/-/raw/main/EMAILPANEL/Free-Panel.sh"

currversion = PLUGIN_VERSION
descplug = "Enigma2 Tools)"

plugin_path = resolveFilename(SCOPE_PLUGINS, "Extensions/Free-Panel")
skin_path = ""
_session = None
has_dpkg = False
setx = 0

if exists("/usr/bin/apt-get"):
    has_dpkg = True

if isWQHD() or isFHD():
    skin_path = plugin_path + "/skins/fhd"
    picfold = plugin_path + "/images/"
    nss_pic = picfold + "noplugin.png"
else:
    skin_path = plugin_path + "/skins/hd"
    picfold = plugin_path + "/images/"
    nss_pic = picfold + "noplugin.png"

class MultiSelectList(MenuList):
    def __init__(self, listdata):
        self.listdata = listdata
        MenuList.__init__(self, self.build_list())

    def build_list(self):
        return [(self.getText(entry), entry) for entry in self.listdata]

    def getText(self, entry):
        name = entry.get("name", "")
        selected = entry.get("selected", False)
        icon = "[✓]" if selected else "[ ]"
        return "{}  {}".format(icon, name)

    def toggleSelection(self):
        index = self.getSelectedIndex()
        if 0 <= index < len(self.listdata):
            self.listdata[index]["selected"] = not self.listdata[index].get("selected", False)
            self.setList(self.build_list())

    def getSelectedItems(self):
        return [item for item in self.listdata if item.get("selected", False)]

    def updateList(self):
        self.setList(self.build_list())

class LPSlist(MenuList):
    def __init__(self, list):
        MenuList.__init__(self, list, True, eListboxPythonMultiContent)
        if isWQHD() or isFHD():
            self.l.setItemHeight(50)
            textfont = 40
            self.l.setFont(0, gFont("Regular", textfont))
        elif isHD():
            self.l.setItemHeight(35)
            textfont = 28
            self.l.setFont(0, gFont("Regular", textfont))

def LPListEntry(name, item):
    res = [(name, item)]
    pngx = plugin_path + "/images/link.png"
    if not fileExists(pngx):
        return res
    png = loadPNG(pngx)
    if isWQHD() or isFHD():
        icon_size = (40, 40)
        text_size = (930, 50)
        icon_x_right = 940
        icon_x_left = 5
        text_x_left = 55
    else:
        icon_size = (30, 30)
        text_size = (590, 35)
        icon_x_right = 640
        icon_x_left = 5
        text_x_left = 45
    if HALIGN == RT_HALIGN_RIGHT:
        res.append(MultiContentEntryPixmapAlphaTest(pos=(icon_x_right, 5), size=icon_size, png=png))
        res.append(MultiContentEntryText(pos=(5, 0), size=text_size, font=0, text=name, flags=HALIGN | RT_VALIGN_CENTER))
    else:
        res.append(MultiContentEntryPixmapAlphaTest(pos=(icon_x_left, 5), size=icon_size, png=png))
        res.append(MultiContentEntryText(pos=(text_x_left, 0), size=text_size, font=0, text=name, flags=HALIGN | RT_VALIGN_CENTER))
    return res

def LPshowlist(data, list):
    plist = [LPListEntry(name, index) for index, name in enumerate(data)]
    list.setList(plist)

class ListSortUtility:
    @staticmethod
    def list_sort(names, titles, pics, urls):
        combined_data = zip(names, titles, pics, urls)
        sorted_data = sorted(combined_data, key=lambda x: x[0])
        return zip(*sorted_data)

def get_positions(resolution):
    return [
        [100, 210], [310, 210], [525, 210], [735, 210], [940, 210],
        [100, 420], [310, 420], [525, 420], [735, 420], [940, 420],
        [100, 635], [310, 635], [525, 635], [735, 635], [940, 635],
        [100, 835], [310, 835], [525, 835], [735, 835], [940, 835]
    ] if resolution == "FHD" else [
        [65, 135], [200, 135], [345, 135], [485, 135], [620, 135],
        [65, 270], [200, 270], [345, 270], [485, 270], [620, 270],
        [65, 405], [200, 405], [345, 405], [485, 405], [620, 405],
        [65, 540], [200, 540], [345, 540], [485, 540], [620, 540]
    ]

class BaseScreen(Screen):
    def __init__(self, session, title, panels):
        Screen.__init__(self, session)
        desktop = getDesktop(0)
        screenwidth = desktop.size().width()
        
        if screenwidth >= 1920:
            self.skin = """
            <screen position="center,center" size="1800,1000" title="">
                <ePixmap position="0,0" size="1800,1000" pixmap="%s/images/back.png" zPosition="-1" />
                <widget source="title" render="Label" position="center,30" size="1600,60" font="Regular;60" halign="center" valign="center" foregroundColor="#ffffff" backgroundColor="#000000" />
                <ePixmap position="1100,500" zPosition="1" size="500,500" pixmap="%s/images/Free-Panel.png" alphatest="on" />
                <widget name="list" position="50,100" size="850,820" itemHeight="82" font="Regular;60" scrollbarMode="showOnDemand" foregroundColor="#ffffff" backgroundColor="#000000" />
                <widget source="session.CurrentService" render="Pig" position="950,100" size="800,450" zPosition="10" backgroundColor="transparent" />
                <widget source="key_red" render="Label" position="150,930" size="400,40" backgroundColor="#9f1313" transparent="0" halign="center" valign="center" font="Regular;35" foregroundColor="#ffffff" zPosition="1"/>
                <widget source="key_green" render="Label" position="700,930" size="400,40" backgroundColor="#1f771f" transparent="0" halign="center" valign="center" font="Regular;35" foregroundColor="#ffffff" zPosition="1"/>
                <widget source="key_blue" render="Label" position="1250,930" size="400,40" backgroundColor="#18188b" transparent="0" halign="center" valign="center" font="Regular;35" foregroundColor="#ffffff" zPosition="1"/>
                <ePixmap position="150,930" size="40,40" pixmap="skin_default/buttons/red.png" zPosition="0" />
                <ePixmap position="700,930" size="40,40" pixmap="skin_default/buttons/green.png" zPosition="0" />
                <ePixmap position="1250,930" size="40,40" pixmap="skin_default/buttons/blue.png" zPosition="0" />
            </screen>""" % (plugin_path, plugin_path)
        else:
            self.skin = """
            <screen position="center,center" size="1200,700" title="">
                <ePixmap position="0,0" size="1200,700" pixmap="%s/images/back.png" zPosition="-1" />
                <widget source="title" render="Label" position="center,20" size="1000,40" font="Regular;32" halign="center" valign="center" foregroundColor="#ffffff" backgroundColor="#000000" />
                <ePixmap position="720,400" zPosition="1" size="200,200" pixmap="%s/images-hd/Free-Panel.png" alphatest="on" />
                <widget name="list" position="30,80" size="550,520" itemHeight="52" font="Regular;28" scrollbarMode="showOnDemand" foregroundColor="#ffffff" backgroundColor="#000000" />
                <widget source="session.CurrentService" render="Pig" position="610,80" size="550,309" zPosition="10" backgroundColor="transparent" />
                <widget source="key_red" render="Label" position="100,640" size="300,35" backgroundColor="#9f1313" transparent="0" halign="center" valign="center" font="Regular;25" foregroundColor="#ffffff" zPosition="1"/>
                <widget source="key_green" render="Label" position="450,640" size="300,35" backgroundColor="#1f771f" transparent="0" halign="center" valign="center" font="Regular;25" foregroundColor="#ffffff" zPosition="1"/>
                <widget source="key_blue" render="Label" position="800,640" size="300,35" backgroundColor="#18188b" transparent="0" halign="center" valign="center" font="Regular;25" foregroundColor="#ffffff" zPosition="1"/>
                <ePixmap position="100,640" size="35,35" pixmap="skin_default/buttons/red.png" zPosition="0" />
                <ePixmap position="450,640" size="35,35" pixmap="skin_default/buttons/green.png" zPosition="0" />
                <ePixmap position="800,640" size="35,35" pixmap="skin_default/buttons/blue.png" zPosition="0" />
            </screen>""" % (plugin_path, plugin_path)
        
        self["title"] = StaticText(title)
        self["key_red"] = StaticText(_("Exit"))
        self["key_green"] = StaticText(_("Install"))
        self["key_blue"] = StaticText(_("Restart"))
        self["list"] = LPSlist([])
        self.panels = panels
        self.update_list()
        
        self["actions"] = ActionMap(["ColorActions", "OkCancelActions"], {
            "ok": self.run_script,
            "green": self.run_script,
            "red": self.close,
            "blue": self.restart_enigma,
            "cancel": self.close
        }, -2)
    
    def update_list(self):
        LPshowlist([name for name, script in self.panels], self["list"])
    
    def run_script(self):
        idx = self["list"].getSelectedIndex()
        if idx is not None and 0 <= idx < len(self.panels):
            self.session.open(Console, _("Installing..."), [self.panels[idx][1]])
    
    def restart_enigma(self):
        self.session.open(TryQuitMainloop, 3)

class Panels(BaseScreen):
    def __init__(self, session):
        panels = [
            ("Ajpanel", "wget http://dreambox4u.com/emilnabil237/plugins/ajpanel/installer1.sh -O - | /bin/sh"),
            ("AjPanel Custom Menu All Panels", "wget https://dreambox4u.com/emilnabil237/plugins/ajpanel/emil-panel-all.sh -O - | /bin/sh"),
            ("smartpanelfree", "wget https://gitlab.com/hanfy1971/panel-free/-/raw/main/smartpanelfree/smartpanelfree.sh -O - | /bin/sh"),
            ("EnigmaPlay-Repo", "wget https://raw.githubusercontent.com/Ahmadarjan1/EnigmaPlay-Repo/main/install.sh -O - | /bin/sh"),
            ("Free-Panel", "wget https://gitlab.com/hanfy1971/plugin/-/raw/main/EMAILPANEL/Free-Panel.sh -O - | /bin/sh"),
            ("tarek-panel", "wget https://gitlab.com/hanfy1971/plugin/-/raw/main/MohamedStore-panel/tarek-panel.sh -O - | /bin/sh"),
            ("Ciefp-Panel", "wget https://github.com/ciefp/CiefpsettingsPanel/raw/main/installer.sh -O - | /bin/sh"),
            ("Ciefp-Panel mod Emil Nabil", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/Ciefp-Panel/Ciefp-Panel.sh -O - | /bin/sh"),
            ("dreamosat-downloader", "wget https://dreambox4u.com/emilnabil237/plugins/dreamosat-downloader/installer.sh -O - | /bin/sh"),
            ("EmilPanel", "wget https://dreambox4u.com/emilnabil237/plugins/emilpanelpro/emilpanelpro.sh -O - | /bin/sh"),
            ("EmilPanelpro", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/EmilPanelPro/emilpanelpro.sh -O - | /bin/sh"),
            ("EliesatPanel", "wget https://raw.githubusercontent.com/eliesat/eliesatpanel/main/installer.sh -O - | /bin/sh"),
            ("Epanel", "wget https://dreambox4u.com/emilnabil237/plugins/epanel/installer.sh -O - | /bin/sh"),
            ("linuxsat-panel", "wget https://raw.githubusercontent.com/Belfagor2005/LinuxsatPanel/main/installer.sh -O - | /bin/sh"),
            ("levi45emulator", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/levi45emulator/installer.sh -O - | /bin/sh"),
            ("levi45-AddonsManager", "wget https://dreambox4u.com/emilnabil237/plugins/levi45-addonsmanager/installer.sh -O - | /bin/sh"),
            ("Levi45MulticamManager", "wget https://dreambox4u.com/emilnabil237/plugins/levi45multicammanager/installer.sh -O - | /bin/sh"),
            ("MagicPanel-HAMDY_AHMED", "wget https://gitlab.com/h-ahmed/Panel/-/raw/main/MagicPanel_install.sh -O - | /bin/sh"),
            ("SatVenusPanel", "wget https://dreambox4u.com/emilnabil237/plugins/satvenuspanel/installer.sh -O - | /bin/sh"),
            ("Tspanel", "wget https://dreambox4u.com/emilnabil237/plugins/tspanel/installer.sh -O - | /bin/sh"),
            ("SmartAddonspanel", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/SmartAddonspanel/smart-Panel.sh -O - | /bin/sh"),
            ("TvAddon-Panel", "wget https://dreambox4u.com/emilnabil237/plugins/tvaddon/installer.sh -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("Panels Manager"), panels)

class PluginsPanel(BaseScreen):
    def __init__(self, session):
        panels = [
            ("ArabicSavior", "wget http://dreambox4u.com/emilnabil237/plugins/ArabicSavior/installer.sh -O - | /bin/sh"),
            ("serviceapp", "wget https://raw.githubusercontent.com/tarekzoka/serviceapp/refs/heads/main/serviceapp.sh -O - | /bin/sh"),
            ("Acherone", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/acherone/installer.sh -O - | /bin/sh"),
            ("AdvancedBootLogoSwapper", "wget https://raw.githubusercontent.com/popking159/abls/main/installer.sh -O - | /bin/sh"),
            ("Advanced-Screen-Shot", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/advancedscreenshot/advancedscreenshot.sh -O - | /bin/sh"),
            ("Alajre", "wget https://dreambox4u.com/emilnabil237/plugins/alajre/installer.sh -O - | /bin/sh"),
            ("Ansite", "wget https://raw.githubusercontent.com/emil237/ansite/refs/heads/main/installer.sh -O - | /bin/sh"),
            ("Apod", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/apod/installer.sh -O - | /bin/sh"),
            ("Apsattv", "wget https://raw.githubusercontent.com/Belfagor2005/Apsattv/main/installer.sh -O - | /bin/sh"),
            ("Astronomy", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/astronomy/installer.sh -O - | /bin/sh"),
            ("Athan Times", "wget https://dreambox4u.com/emilnabil237/plugins/athantimes/installer.sh -O - | /bin/sh"),
            ("Atilehd", "wget https://dreambox4u.com/emilnabil237/plugins/atilehd/installer.sh -O - | /bin/sh"),
            ("automatic-fullbackup", "wget https://dreambox4u.com/emilnabil237/plugins/automatic-fullbackup/installer.sh -O - | /bin/sh"),
            ("Auto-Dcw-Key-Add", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/auto-dcw-key-add/auto-dcw-key-add.sh -O - | /bin/sh"),
            ("Azkar Almuslim", "wget https://dreambox4u.com/emilnabil237/plugins/azkar-almuslim/installer.sh -O - | /bin/sh"),
            ("BissFeedAutoKey", "wget https://raw.githubusercontent.com/emilnabil/bissfeed-autokey/main/installer.sh -O - | /bin/sh"),
            ("Bitrate", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/bitrate/bitrate.sh -O - | /bin/sh"),
            ("Bitrate-mod-ariad", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/bitrate/bitrate-mod-ariad.sh -O - | /bin/sh"),
            ("Bundesliga-Permanent-Clock", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/bundesliga-permanent-clock/bundesliga-permanent-clock.sh -O - | /bin/sh"),
            ("CacheFlush", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/cacheflush/cacheflush.sh -O - | /bin/sh"),
            ("CCcaminfo-py2", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/cccaminfo/cccaminfo_py2.sh -O - | /bin/sh"),
            ("CCcaminfo-py3", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/cccaminfo/cccaminfo_py3.sh -O - | /bin/sh"),
            ("CrondManager", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/crondmanager/installer.sh -O - | /bin/sh"),
            ("CFG_ZOOM_FINAL", "wget https://dreambox4u.com/emilnabil237/plugins/cfg_Zoom_Final_FIX7x/installer.sh -O - | /bin/sh"),
            ("CiefpBouquetUpdater", "wget https://raw.githubusercontent.com/ciefp/CiefpBouquetUpdater/main/installer.sh -O - | /bin/sh"),
            ("CiefpChannelManager", "wget https://raw.githubusercontent.com/ciefp/CiefpChannelManager/main/installer.sh -O - | /bin/sh"),
            ("CiefpE2Converter", "wget https://raw.githubusercontent.com/ciefp/CiefpE2Converter/main/installer.sh -O - | /bin/sh"),
            ("CiefpEPGshare", "wget https://raw.githubusercontent.com/ciefp/CiefpEPGshare/main/installer.sh -O - | /bin/sh"),
            ("CiefpIPTVBouquets", "wget https://raw.githubusercontent.com/ciefp/CiefpIPTVBouquets/main/installer.sh -O - | /bin/sh"),
            ("CiefpMojTvEPG", "wget https://raw.githubusercontent.com/ciefp/CiefpMojTvEPG/main/installer.sh -O - | /bin/sh"),
            ("CiefpOscamEditor", "wget https://raw.githubusercontent.com/ciefp/CiefpOscamEditor/main/installer.sh -O - | /bin/sh"),
            ("CiefpPlugins", "wget https://raw.githubusercontent.com/ciefp/CiefpPlugins/main/installer.sh -O - | /bin/sh"),
            ("CiefpSatelliteAnalyzer", "wget https://raw.githubusercontent.com/ciefp/CiefpSatelliteAnalyzer/main/installer.sh -O - | /bin/sh"),
            ("CiefpSatellitesXmlEditor", "wget https://raw.githubusercontent.com/ciefp/CiefpSatelliteXmlEditor/main/installer.sh -O - | /bin/sh"),
            ("CiefpScreenGrab", "wget https://raw.githubusercontent.com/ciefp/CiefpScreenGrab/main/installer.sh -O - | /bin/sh"),
            ("CiefpSelectSatellite", "wget https://raw.githubusercontent.com/ciefp/CiefpSelectSatellite/main/installer.sh -O - | /bin/sh"),
            ("CiefpSettingsDownloader", "wget https://raw.githubusercontent.com/ciefp/CiefpSettingsDownloader/main/installer.sh -O - | /bin/sh"),
            ("CiefpSettingsPanel", "wget https://raw.githubusercontent.com/ciefp/CiefpsettingsPanel/main/installer.sh -O - | /bin/sh"),
            ("CiefpSettingsStreamrelay PY2", "wget https://raw.githubusercontent.com/ciefp/CiefpSettingsStreamrelayPY2/main/installer.sh -O - | /bin/sh"),
            ("CiefpSettingsStreamrelay PY3", "wget https://raw.githubusercontent.com/ciefp/CiefpSettingsStreamrelay/main/installer.sh -O - | /bin/sh"),
            ("CiefpSettingsT2miAbertis", "wget https://raw.githubusercontent.com/ciefp/CiefpSettingsT2miAbertis/main/installer.sh -O - | /bin/sh"),
            ("CiefpSettingsT2miAbertisOpenPLi", "wget https://raw.githubusercontent.com/ciefp/CiefpSettingsT2miAbertisOpenPLi/main/installer.sh -O - | /bin/sh"),
            ("CiefpsettingsMotor", "wget https://raw.githubusercontent.com/ciefp/CiefpsettingsMotor/main/installer.sh -O - | /bin/sh"),
            ("CiefpTvProgram", "wget https://raw.githubusercontent.com/ciefp/CiefpTvProgram/main/installer.sh -O - | /bin/sh"),
            ("CiefpTvProgramA1HR", "wget https://raw.githubusercontent.com/ciefp/CiefpTvProgramA1HR/main/installer.sh -O - | /bin/sh"),
            ("CiefpTvProgramSBB", "wget https://raw.githubusercontent.com/ciefp/CiefpTvProgramSBB/main/installer.sh -O - | /bin/sh"),
            ("CiefpTvProgramSK", "wget https://raw.githubusercontent.com/ciefp/CiefpTvProgramSK/main/installer.sh -O - | /bin/sh"),
            ("CiefpTvTodayDE", "wget https://raw.githubusercontent.com/ciefp/CiefpTvTodayDE/main/installer.sh -O - | /bin/sh"),
            ("CiefpWhitelistStreamrelay", "wget https://raw.githubusercontent.com/ciefp/CiefpWhitelistStreamrelay/main/installer.sh -O - | /bin/sh"),
            ("chocholousek-picons", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/chocholousek-picons.sh -O - | /bin/sh"),
            ("CHLogoChanger", "wget https://dreambox4u.com/emilnabil237/plugins/CHLogoChanger/ChLogoChanger.sh -O - | /bin/sh"),
            ("CrashLogoViewer", "wget https://dreambox4u.com/emilnabil237/plugins/crashlogviewer/install-CrashLogViewer.sh -O - | /bin/sh"),
            ("CrondManger", "wget https://github.com/emil237/download-plugins/raw/main/cronmanager.sh -O - | /bin/sh"),
            ("Ddrss Reader", "wget https://raw.githubusercontent.com/Belfagor2005/DDRSSReader/main/installer.sh -O - | /bin/sh"),
            ("Easy-Cccam", "wget https://raw.githubusercontent.com/emil237/plugins/refs/heads/main/easy-cccam/easy-cccam.sh -O - | /bin/sh"),
            ("enigma2readeradder", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/enigma2readeradder.sh -O - | /bin/sh"),
            ("Epg Grabber", "wget https://dreambox4u.com/emilnabil237/plugins/Epg-Grabber/installer.sh -O - | /bin/sh"),
            ("EPGImport", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/epgimport.sh -O - | /bin/sh"),
            ("EPGImport-99", "wget https://raw.githubusercontent.com/Belfagor2005/EPGImport-99/main/installer.sh -O - | /bin/sh"),
            ("EPGTranslator", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/epgtranslator.sh -O - | /bin/sh"),
            ("EvgQuickSignal", "wget https://raw.githubusercontent.com/biko-73/EvgQuickSignal/main/installer.sh -O - | /bin/sh"),
            ("Estalker", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/EStalker/EStalker.sh -O - | /bin/sh"),
            ("EstalkerWebControl", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/EstalkerWebControl/estalkerwebcontrol.sh -O - | /bin/sh"),
            ("Feeds-Finder", "wget https://dreambox4u.com/emilnabil237/plugins/feeds-finder/installer.sh -O - | /bin/sh"),
            ("Filmxy", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/filmxy/filmxy.sh -O - | /bin/sh"),
            ("Footonsat", "wget https://dreambox4u.com/emilnabil237/plugins/FootOnsat/installer.sh -O - | /bin/sh"),
            ("Freearhey", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/freearhey/freearhey.sh -O - | /bin/sh"),
            ("FreeCCcamServer", "wget https://ia803104.us.archive.org/0/items/freecccamserver/installer.sh -O - | /bin/sh"),
            ("GeminiPatcher", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/GeminiPatcher/geminipatcher.sh -O - | /bin/sh"),
            ("gioppygio", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/gioppygio/gioppygio.sh -O - | /bin/sh"),
            ("hardwareinfo", "wget https://dreambox4u.com/emilnabil237/plugins/hardwareinfo/installer.sh -O - | /bin/sh"),
            ("HasBahCa", "wget https://dreambox4u.com/emilnabil237/plugins/HasBahCa/installer.sh -O - | /bin/sh"),
            ("HistoryZapSelector", "wget https://dreambox4u.com/emilnabil237/plugins/historyzap/installer1.sh -O - | /bin/sh"),
            ("horoscope", "wget https://raw.githubusercontent.com/emilnabil/horoscope/refs/heads/main/horoscope.sh -O - | /bin/sh"),
            ("HolidayCountdown", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/HolidayCountdown/installer.sh -O - | /bin/sh"),
            ("Internet-Speedtest", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/internet-speedtest.sh -O - | /bin/sh"),
            ("IP_Checker", "wget https://raw.githubusercontent.com/emil237/plugins/refs/heads/main/IP_Checker.sh -O - | /bin/sh"),
            ("Iptv-Org-Playlists", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/iptv-org-playlists/iptv-org-playlists.sh -O - | /bin/sh"),
            ("iptvdream", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/main/iptvdream/iptvdream.sh -O - | /bin/sh"),
            ("IptvPlayer", "wget https://raw.githubusercontent.com/emil237/iptvplayer/main/iptvinstaller.sh -O - | /bin/sh"),
            ("KeyAdder", "wget https://raw.githubusercontent.com/fairbird/KeyAdder/main/installer.sh -O - | /bin/sh"),
            ("levi45-freeserver", "wget https://raw.githubusercontent.com/emil237/plugins/refs/heads/main/levi45-freeserver/levi45-freeserver.sh -O - | /bin/sh"),
            ("levi45-settings", "wget https://dreambox4u.com/emilnabil237/plugins/levi45-settings/levi45-settings.sh -O - | /bin/sh"),
            ("M3uConverter", "wget https://raw.githubusercontent.com/Belfagor2005/Archimede-M3UConverter/main/installer.sh -O - | /bin/sh"),
            ("MmPicons", "wget https://raw.githubusercontent.com/Belfagor2005/mmPicons/main/installer.sh -O - | /bin/sh"),
            ("MoviesManager", "wget http://dreambox4u.com/emilnabil237/plugins/Transmission/MoviesManager.sh -O - | /bin/sh"),
            ("MyCam-Plugin", "wget https://dreambox4u.com/emilnabil237/plugins/mycam/installer.sh -O - | /bin/sh"),
            ("MultiCamAdder", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/MultiCamAdder/installer.sh -O - | /bin/sh"),
            ("Multi-Iptv-Adder", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/MultiIptvAdder/installer.sh -O - | /bin/sh"),
            ("NewVirtualkeyBoard", "wget https://dreambox4u.com/emilnabil237/plugins/NewVirtualKeyBoard/installer.sh -O - | /bin/sh"),
            ("ONEupdater", "wget https://raw.githubusercontent.com/Sat-Club/ONEupdaterE2/main/installer.sh -O - | /bin/sh"),
            ("OrangeAudioPlugin", "wget https://raw.githubusercontent.com/popking159/OrangeAudio/refs/heads/main/installer.sh -O - | /bin/sh"),
            ("Ozeta-Skins-Setup", "wget https://raw.githubusercontent.com/emil237/skins-enigma2/main/PLUGIN_Skin-ozeta.sh -O - | /bin/sh"),
            ("Plutotv", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/main/plutotv/plutotv.sh -O - | /bin/sh"),
            ("Quran-karem", "wget https://dreambox4u.com/emilnabil237/plugins/quran/installer.sh -O - | /bin/sh"),
            ("Quran-karem_v2.2", "wget https://raw.githubusercontent.com/emil237/quran/main/installer.sh -O - | /bin/sh"),
            ("Radio-80-s", "wget https://raw.githubusercontent.com/Belfagor2005/Radio-80-s/main/installer.sh -O - | /bin/sh"),
            ("RadioGit", "wget https://dreambox4u.com/emilnabil237/plugins/radiogit/radiogit.sh -O - | /bin/sh"),
            ("Radio-Stream-Relay", "wget https://raw.githubusercontent.com/angelheart150/RadioRelay/main/installer.sh -O - | /bin/sh"),
            ("Radiom", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/main/radiom/radiom.sh -O - | /bin/sh"),
            ("Rakutentv", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/main/rakutentv/rakutentv.sh -O - | /bin/sh"),
            ("RaedQuickSignal", "wget https://dreambox4u.com/emilnabil237/plugins/RaedQuickSignal/installer.sh -O - | /bin/sh"),
            ("Rss Reader", "wget https://raw.githubusercontent.com/Belfagor2005/RSSReader/main/installer.sh -O - | /bin/sh"),
            ("PiconsRename", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/PiconsRename/PiconsRename.sh -O - | /bin/sh"),
            ("pluginmover", "wget http://dreambox4u.com/emilnabil237/plugins/pluginmover/installer.sh -O - | /bin/sh"),
            ("pluginskinmover", "wget http://dreambox4u.com/emilnabil237/plugins/pluginskinmover/installer.sh -O - | /bin/sh"),
            ("ScreenNames", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/screennames/screennames.sh -O - | /bin/sh"),
            ("Screen-Recorder", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/screenrecorder/installer.sh -O - | /bin/sh"),
            ("ServiceScanUpdates", "wget https://dreambox4u.com/emilnabil237/plugins/servicescanupdates/servicescanupdates.sh -O - | /bin/sh"),
            ("SetPicon", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/setpicon/installer.sh -O - | /bin/sh"),
            ("scriptexecuter", "wget http://dreambox4u.com/emilnabil237/plugins/scriptexecuter/installer.sh -O - | /bin/sh"),
            ("showclock", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/showclock/showclock.sh -O - | /bin/sh"),
            ("Sherlockmod", "wget https://raw.githubusercontent.com/emil237/sherlockmod/main/installer.sh -O - | /bin/sh"),
            ("Simple-Zoom-Panel", "wget https://dreambox4u.com/emilnabil237/plugins/simple-zoom-panel/installer.sh -O - | /bin/sh"),
            ("StalkerPortalConverter", "wget https://raw.githubusercontent.com/Belfagor2005/StalkerPortalConverter/main/installer.sh -O - | /bin/sh"),
            ("SubsSupport_1.5.8-r9", "wget https://dreambox4u.com/emilnabil237/plugins/SubsSupport/installer1.sh -O - | /bin/sh"),
            ("SubsSupport_by-m.nasr", "wget https://github.com/popking159/ssupport/raw/main/subssupport-install.sh -O - | /bin/sh"),
            ("SubsSupport_2.1", "wget https://dreambox4u.com/emilnabil237/plugins/SubsSupport/subssupport_2.1.sh -O - | /bin/sh"),
            ("TheWeather", "wget https://raw.githubusercontent.com/biko-73/TheWeather/main/installer.sh -O - | /bin/sh"),
            ("TMBD", "wget https://raw.githubusercontent.com/biko-73/TMBD/main/installer.sh -O - | /bin/sh"),
            ("Tmdb", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/tmdb.sh -O - | /bin/sh"),
            ("TvDream", "wget https://raw.githubusercontent.com/Belfagor2005/tvDream/main/installer.sh -O - | /bin/sh"),
            ("Transmission", "wget http://dreambox4u.com/dreamarabia/Transmission_e2/Transmission_e2.sh -O - | /bin/sh"),
            ("TvManager", "wget https://raw.githubusercontent.com/Belfagor2005/tvManager/main/installer.sh -O - | /bin/sh"),
            ("TvParsa", "wget https://raw.githubusercontent.com/Belfagor2005/tvParsa/main/installer.sh -O - | /bin/sh"),
            ("TvRaiPreview", "wget https://raw.githubusercontent.com/Belfagor2005/tvRaiPreview/main/installer.sh -O - | /bin/sh"),
            ("TvSettings", "wget https://raw.githubusercontent.com/Belfagor2005/tvSettings/main/installer.sh -O - | /bin/sh"),
            ("uninstaller-Plugins", "wget http://dreambox4u.com/emilnabil237/plugins/unstaller-plugins/installer.sh -O - | /bin/sh"),
            ("vavoo_1.15", "wget https://dreambox4u.com/emilnabil237/plugins/vavoo/installer.sh -O - | /bin/sh"),
            ("xtraevent_3.3", "wget https://raw.githubusercontent.com/emil237/download-plugins/main/xtraevent_3.3.sh -O - | /bin/sh"),
            ("xtraevent_4.2", "wget https://raw.githubusercontent.com/emil237/download-plugins/main/xtraEvent_4.2.sh -O - | /bin/sh"),
            ("xtraevent_4.5", "wget https://raw.githubusercontent.com/emil237/download-plugins/main/xtraEvent_4.5.sh -O - | /bin/sh"),
            ("Xtraevent_4.6", "wget https://github.com/emil237/download-plugins/raw/main/Xtraevent-v4.6.sh -O - | /bin/sh"),
            ("xtraevent_6.798", "wget https://dreambox4u.com/emilnabil237/plugins/xtraevent/xtraevent_6.798.sh -O - | /bin/sh"),
            ("xtraevent_6.805", "wget https://dreambox4u.com/emilnabil237/plugins/xtraevent/xtraevent-6.805.sh -O - | /bin/sh"),
            ("xtraevent_6.820_All-Python", "wget https://dreambox4u.com/emilnabil237/plugins/xtraevent/xtraevent-6.820.sh -O - | /bin/sh"),
            ("xtraevent_6.840_PY3", "wget https://dreambox4u.com/emilnabil237/plugins/xtraevent/xtraevent-6.840.sh -O - | /bin/sh"),
            ("WeatherPlugin", "wget https://raw.githubusercontent.com/fairbird/WeatherPlugin/master/installer.sh -O - | /bin/sh"),
            ("Wireguard-Vpn", "wget https://raw.githubusercontent.com/m4dhouse/Wireguard-Vpn/refs/heads/python-3.12/WireGuard.sh -O - | /bin/sh"),
            ("WorldCam", "wget https://raw.githubusercontent.com/Belfagor2005/WorldCam/main/installer.sh -O - | /bin/sh"),
            ("Youtube", "wget https://raw.githubusercontent.com/fairbird/Youtube-Opensource-DreamOS/master/installer.sh -O - | /bin/sh"),
            ("Zip2Pkg-Converter", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/Zip2Pkg/installer.sh -O - | /bin/sh"),
            ("ZapTimer", "wget https://dreambox4u.com/emilnabil237/plugins/zaptimer/zaptimer.sh -O - | /bin/sh"),
            ("Zoom_1.1.2-Py3", "wget https://dreambox4u.com/emilnabil237/plugins/zoom/installer.sh -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("Plugins Manager"), panels)

class ToolsPanel(BaseScreen):
    def __init__(self, session):
        panels = [
            ("Wget", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/wget.sh -O - | /bin/sh"),
            ("Curl", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/curl.sh -O - | /bin/sh"),
            ("Update Enigma2 All Python", "wget https://raw.githubusercontent.com/emil237/updates-enigma/main/update-all-python.sh -O - | /bin/sh"),
            ("Opkg tools", "wget http://dreambox4u.com/emilnabil237/script/opkg.sh -O - | /bin/sh"),
            ("Super Script", "wget https://dreambox4u.com/emilnabil237/script/Super_Script.sh -O - | /bin/sh"),
            ("Delete-password", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/scripts-servise/delete-password.sh -O - | /bin/sh"),
            ("Change-Password-To-root", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/scripts-servise/change-password-to-root.sh -O - | /bin/sh"),
            ("CAM-abertis-astra-sm", "wget https://dreambox4u.com/emilnabil237/script/CAM-abertis-astra.sh -O - | /bin/sh"),
            ("Epg-Khaled", "wget https://raw.githubusercontent.com/emilnabil/epg-khaled/main/EPG-khaled.sh -O - | /bin/sh"),
            ("FORMAT_HDD_TO-Ext4", "wget https://raw.githubusercontent.com/emil237/scripts/refs/heads/main/format-hdd.sh -O - | /bin/sh"),
            ("Repair-Inodes-From-Hdd", "wget https://raw.githubusercontent.com/emil237/scripts/refs/heads/main/repair-hdd.sh -O - | /bin/sh"),
            ("FIX-ipk-installation", "wget https://dreambox4u.com/emilnabil237/script/fix-ipk-package-installation.sh -O - | /bin/sh"),
            ("Fix-Xtraevent-Download", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/fix-xtraevent-download.sh -O - | /bin/sh"),
            ("Set_Time_NTP-Google", "wget https://dreambox4u.com/emilnabil237/script/set_time.sh -O - | /bin/sh"),
            ("Fix Softcam Atv", "wget http://updates.mynonpublic.com/oea/feed -O - | /bin/sh"),
            ("Fix Softcam OpenPli", "wget https://raw.githubusercontent.com/emil237/download-plugins/main/softcam-support-pli.sh -O - | /bin/sh"),
            ("Wget package Vti", "wget https://raw.githubusercontent.com/emil237/download-plugins/refs/heads/main/tool_vti-wget_1.16.3.sh -O - | /bin/sh"),
            ("UpdateSatellitesOealliance", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/Satellites-Oealliance.sh -O - | /bin/sh"),
            ("UpdateSatellitesOpenPli", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/satellites-openpli.sh -O - | /bin/sh"),
            ("Zip2ipk", "wget http://dreambox4u.com/emilnabil237/script/zip2ipk.sh -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("Tools Manager"), panels)

class MultibootPluginsPanel(BaseScreen):
    def __init__(self, session):
        panels = [
            ("EgamiBoot 10.5", "wget https://raw.githubusercontent.com/emil237/egamiboot/refs/heads/main/installer.sh -O - | /bin/sh"),
            ("EgamiBoot 10.6", "wget https://raw.githubusercontent.com/emil237/egamiboot/refs/heads/main/egamiboot-10.6.sh -O - | /bin/sh"),
            ("Neoboot 9.65", "wget https://dreambox4u.com/emilnabil237/plugins/neoboot-v9.65/iNB.sh -O - | /bin/sh"),
            ("Neoboot 9.65 Mod-ElSafty", "wget https://raw.githubusercontent.com/emil237/neoboot_v9.65/main/iNB_9.65_mod-elsafty.sh -O - | /bin/sh"),
            ("Neoboot 9.60", "wget https://dreambox4u.com/emilnabil237/plugins/neoboot-v9.60/iNB.sh -O - | /bin/sh"),
            ("Neoboot 9.58", "wget https://dreambox4u.com/emilnabil237/plugins/neoboot-v9.58/iNB.sh -O - | /bin/sh"),
            ("Neoboot 9.54", "wget https://raw.githubusercontent.com/emil237/neoboot_9.54/main/installer.sh -O - | /bin/sh"),
            ("OpenMultiboot 1.3", "wget https://raw.githubusercontent.com/emil237/openmultiboot/main/installer.sh -O - | /bin/sh"),
            ("OpenMultiboot-E2turk", "wget https://raw.githubusercontent.com/e2TURK/omb-enhanced/main/install.sh -O - | /bin/sh"),
            ("Multiboot-FlashOnline", "wget https://raw.githubusercontent.com/emil237/download-plugins/main/multiboot-flashonline.sh -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("Multiboot Manager"), panels)

class FeedsPanels(BaseScreen):
    def __init__(self, session):
        panels = [
            ("Eliesat", "wget https://gitlab.com/eliesat/scripts/-/raw/main/feed/eliesat-feed.sh -O - | /bin/sh"),
            ("Emil", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/FEED-emil-feed.sh -O - | /bin/sh"),
            ("Jungle", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/FEED-jungle-feed.sh -O - | /bin/sh"),
            ("Libraries_3.12.4", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/FEED-libraries-3.12.4.sh -O - | /bin/sh"),
            ("Libraries_3.12.6", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/FEED-libraries-3.12.sh -O - | /bin/sh"),
            ("Oe-alliance-Picons", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/FEED-oe-picons.sh -O - | /bin/sh"),
            ("Oe-alliance-Settings", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/FEED-oe-settings.sh -O - | /bin/sh"),
            ("Openatv-Deval", "wget -O - -q https://feeds2.mynonpublic.com/devel-feed | bash"),
            ("OpenPicons", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/FEED-openpicons.sh -O - | /bin/sh"),
            ("Softcams-Feed-Openatv", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/FEED-OpenAtv-softcam-ALL-Python.sh -O - | /bin/sh"),
            ("OpenDroid-softcam", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/FEED-OpenDroid-softcam.sh -O - | /bin/sh"),
            ("OpenEight-softcam", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/FEED-OpenEight-softcam.sh -O - | /bin/sh"),
            ("TeamBlue-softcam", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/FEED-TeamBlue-softcam.sh -O - | /bin/sh"),
            ("Softcams-Feed-Pure2", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/FEED-pure2-softcam.sh -O - | /bin/sh"),
            ("Tarek-Hanfy", "wget https://github.com/emilnabil/download-plugins/raw/refs/heads/main/FEED-Tarek.sh -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("Feeds Manager"), panels)

class MediaPanel(BaseScreen):
    def __init__(self, session):
        panels = [
            ("BouquetMakerXtream", "wget http://dreambox4u.com/emilnabil237/plugins/BouquetMakerXtream/installer.sh -O - | /bin/sh"),
            ("E2m3u2Bouquet", "wget https://dreambox4u.com/emilnabil237/plugins/e2m3u2bouquet/installer.sh -O - | /bin/sh"),
            ("E2Player-MAXBAMBY", "wget https://gitlab.com/maxbambi/e2iplayer/-/raw/master/install-e2iplayer.sh -O - | /bin/sh"),
            ("E2Player-ZADMARIO", "wget https://gitlab.com/zadmario/e2iplayer/-/raw/master/install-e2iplayer.sh -O - | /bin/sh"),
            ("IptoSat", "wget https://dreambox4u.com/emilnabil237/plugins/iptosat/installer.sh -O - | /bin/sh"),
            ("IpAudio 6.7 py2", "wget https://dreambox4u.com/emilnabil237/plugins/ipaudio/installer.sh -O - | /bin/sh"),
            ("IpAudio 7.4 py3", "wget https://dreambox4u.com/emilnabil237/plugins/ipaudio/ipaudio-7.4-ffmpeg.sh -O - | /bin/sh"),
            ("IpAudioPro", "wget https://dreambox4u.com/emilnabil237/plugins/ipaudiopro/installer.sh -O - | /bin/sh"),
            ("JediEpgExtream", "wget https://dreambox4u.com/emilnabil237/plugins/jediepgextream/installer.sh -O - | /bin/sh"),
            ("Jedimakerxtream", "wget https://dreambox4u.com/emilnabil237/plugins/jedimakerxtream/installer.sh -O - | /bin/sh"),
            ("Multistalker", "wget https://dreambox4u.com/emilnabil237/plugins/multistalker/installer.sh -O - | /bin/sh"),
            ("MultiStalkerPro", "wget https://raw.githubusercontent.com/emilnabil/multi-stalkerpro/main/installer.sh -O - | /bin/sh"),
            ("Quarter pounder", "wget http://dreambox4u.com/emilnabil237/script/quarterpounder.sh -O - | /bin/sh"),
            ("Suptv", "wget https://raw.githubusercontent.com/emil237/suptv/main/installer.sh -O - | /bin/sh"),
            ("YouTube", "wget https://dreambox4u.com/emilnabil237/plugins/YouTube/installer.sh -O - | /bin/sh"),
            ("xklass-iptv", "wget https://dreambox4u.com/emilnabil237/plugins/xklass/installer.sh -O - | /bin/sh"),
            ("Xtreamty", "wget https://dreambox4u.com/emilnabil237/plugins/xtreamity/installer.sh -O - | /bin/sh"),
            ("Xcpluginforever", "wget https://raw.githubusercontent.com/Belfagor2005/xc_plugin_forever/main/installer.sh -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("Media Manager"), panels)

class SoftcamsPanel(BaseScreen):
    def __init__(self, session):
        panels = [
            ("Cccam", "wget https://dreambox4u.com/emilnabil237/emu/installer-cccam.sh -O - | /bin/sh"),
            ("gosatplus-ncam", "wget https://dreambox4u.com/emilnabil237/emu/installer-gosatplus-ncam.sh -O - | /bin/sh"),
            ("gosatplus-oscam", "wget https://dreambox4u.com/emilnabil237/emu/installer-gosatplus-oscam.sh -O - | /bin/sh"),
            ("gosatplus_v3_arm", "wget http://e2.gosatplus.com/Plugin/V3/arm-openpli-installer_py3_v3.sh -O - | /bin/sh"),
            ("gosatplus_v3_mips", "wget http://e2.gosatplus.com/Plugin/V3/mips-openpli-installer_py3_v3.sh -O - | /bin/sh"),
            ("gosatplus_v3_Fix", "wget http://e2.gosatplus.com/Plugin/V3/GosatPlusPluginFixPy.sh -O - | /bin/sh"),
            ("Hold-flag-ncam", "wget https://dreambox4u.com/emilnabil237/script/Hold-flag-ncam.sh -O - | /bin/sh"),
            ("Hold-flag-Oscam", "wget https://dreambox4u.com/emilnabil237/script/Hold-flag-Oscam.sh -O - | /bin/sh"),
            ("Ncam", "wget https://dreambox4u.com/emilnabil237/emu/installer-ncam.sh -O - | /bin/sh"),
            ("Oscam", "wget https://dreambox4u.com/emilnabil237/emu/installer-oscam.sh -O - | /bin/sh"),
            ("Oscam-11.726-by-lenuxsat", "wget https://dreambox4u.com/emilnabil237/emu/oscam-by-lenuxsat/installer.sh -O - | /bin/sh"),
            ("oscamicam", "wget https://dreambox4u.com/emilnabil237/emu/installer-oscamicam.sh -O - | /bin/sh"),
            ("powercam_v2-icam-arm", "wget https://dreambox4u.com/emilnabil237/emu/powercam/installer.sh -O - | /bin/sh"),
            ("powercam-Ncam", "wget https://dreambox4u.com/emilnabil237/emu/installer-powercam-ncam.sh -O - | /bin/sh"),
            ("powercam-Oscam", "wget https://dreambox4u.com/emilnabil237/emu/installer-powercam-oscam.sh -O - | /bin/sh"),
            ("Restore-flag-ncam", "wget https://dreambox4u.com/emilnabil237/script/Restore-flag-ncam.sh -O - | /bin/sh"),
            ("Restore-flag-oscam", "wget https://dreambox4u.com/emilnabil237/script/Restore-flag-Oscam.sh -O - | /bin/sh"),
            ("Revcam-Ncam", "wget https://dreambox4u.com/emilnabil237/emu/installer-revcam-ncam.sh -O - | /bin/sh"),
            ("Revcam-Oscam", "wget https://dreambox4u.com/emilnabil237/emu/installer-revcam-oscam.sh  -O - | /bin/sh"),
            ("Revcam", "wget https://dreambox4u.com/emilnabil237/emu/installer-revcam.sh -O - | /bin/sh"),
            ("Supcam-Ncam", "wget https://dreambox4u.com/emilnabil237/emu/installer-supcam-ncam.sh -O - | /bin/sh"),
            ("Supcam-Oscam", "wget https://dreambox4u.com/emilnabil237/emu/installer-supcam-oscam.sh  -O - | /bin/sh"),
            ("Ultracam-Ncam", "wget https://dreambox4u.com/emilnabil237/emu/installer-ultracam-ncam.sh -O - | /bin/sh"),
            ("Ultracam-Oscam", "wget https://dreambox4u.com/emilnabil237/emu/installer-ultracam-oscam.sh -O - | /bin/sh"),
            ("Ultracam", "wget https://dreambox4u.com/emilnabil237/emu/installer-ultracam.sh -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("Softcams Manager"), panels)

class SystemPluginsPanel(BaseScreen):
    def __init__(self, session):
        panels = [
            ("3gmodemmanager", "wget https://dreambox4u.com/emilnabil237/plugins/3gmodemmanager/3gmodemmanager.sh -O - | /bin/sh"),
            ("Disk_and_CPU_Temperature", "wget https://raw.githubusercontent.com/emilnabil/dreambox/refs/heads/main/disk_and_cpu_temperature.sh -O - | /bin/sh"),
            ("devicemanager", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/devicemanager.sh -O - | /bin/sh"),
            ("extnumberzap", "wget https://dreambox4u.com/emilnabil237/plugins/extnumberzap/extnumberzap.sh -O - | /bin/sh"),
            ("mountmanager", "wget https://dreambox4u.com/emilnabil237/plugins/mountmanager/installer.sh -O - | /bin/sh"),
            ("setpasswd", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/setpasswd.sh -O - | /bin/sh"),
            ("Signalfinder", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/signalfinder.sh -O - | /bin/sh"),
            ("softwaremanager", "wget https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/softwaremanager.sh -O - | /bin/sh"),
            ("Ts-Sateditor", "wget https://dreambox4u.com/emilnabil237/plugins/ts-sateditor/ts-sateditor.sh -O - | /bin/sh"),
            ("Xmlupdate", "wget https://dreambox4u.com/emilnabil237/plugins/xmlupdate/xmlupdate.sh -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("SystemPlugins Manager"), panels)

class PiconsPanel(BaseScreen):
    def __init__(self, session):
        panels = [
            ("intelsat_31.5w", "wget https://dreambox4u.com/emilnabil237/picons/intelsat_31.5w/installer.sh -O - | /bin/sh"),
            ("hispasat_30.0w", "wget https://dreambox4u.com/emilnabil237/picons/hispasat_30.0w/installer.sh -O - | /bin/sh"),
            ("intelsat_27.5w", "wget https://dreambox4u.com/emilnabil237/picons/intelsat_27.5w/installer.sh -O - | /bin/sh"),
            ("intelsat_24.5w", "wget https://dreambox4u.com/emilnabil237/picons/intelsat_24.5w/installer.sh -O - | /bin/sh"),
            ("ses4_22.0w", "wget https://dreambox4u.com/emilnabil237/picons/ses4_22.0w/installer.sh -O - | /bin/sh"),
            ("nss7_20.0w", "wget https://dreambox4u.com/emilnabil237/picons/nss7_20.0w/installer.sh -O - | /bin/sh"),
            ("telstar_15.0w", "wget https://dreambox4u.com/emilnabil237/picons/telstar_15.0w/installer.sh -O - | /bin/sh"),
            ("express_14w", "wget https://dreambox4u.com/emilnabil237/picons/express_14w/installer.sh -O - | /bin/sh"),
            ("express_11.0w-14.0w", "wget https://dreambox4u.com/emilnabil237/picons/express_11.0w-14.0w/installer.sh -O - | /bin/sh"),
            ("Nilesat_7W-8W", "wget https://dreambox4u.com/emilnabil237/picons/nilesat/installer.sh -O - | /bin/sh"),
            ("eutelsat_5.0w", "wget https://dreambox4u.com/emilnabil237/picons/eutelsat_5.0w/installer.sh -O - | /bin/sh"),
            ("Amos_4.0W", "wget https://dreambox4u.com/emilnabil237/picons/amos_4.0w/installer.sh -O - | /bin/sh"),
            ("abs_3.0w", "wget https://dreambox4u.com/emilnabil237/picons/abs_3.0w/installer.sh -O - | /bin/sh"),
            ("thor_0.8w", "wget https://dreambox4u.com/emilnabil237/picons/thor_0.8w/installer.sh -O - | /bin/sh"),
            ("bulgariasat_1.9e", "wget https://dreambox4u.com/emilnabil237/picons/bulgariasat_1.9e/installer.sh -O - | /bin/sh"),
            ("eutelsat_3.0e", "wget https://dreambox4u.com/emilnabil237/picons/eutelsat_3.0e/installer.sh -O - | /bin/sh"),
            ("astra_4.8e", "wget https://dreambox4u.com/emilnabil237/picons/astra_4.8e/installer.sh -O - | /bin/sh"),
            ("eutelsat_7.0e", "wget https://dreambox4u.com/emilnabil237/picons/eutelsat_7.0e/installer.sh -O - | /bin/sh"),
            ("eutelsat_9.0e", "wget https://dreambox4u.com/emilnabil237/picons/eutelsat_9.0e/installer.sh -O - | /bin/sh"),
            ("eutelsat_10.0e", "wget https://dreambox4u.com/emilnabil237/picons/eutelsat_10.0e/installer.sh -O - | /bin/sh"),
            ("hotbird_13.0e", "wget https://dreambox4u.com/emilnabil237/picons/hotbird_13.0e/installer.sh -O - | /bin/sh"),
            ("eutelsat_16.0e", "wget https://dreambox4u.com/emilnabil237/picons/eutelsat_16.0e/installer.sh -O - | /bin/sh"),
            ("astra_19.2e", "wget https://dreambox4u.com/emilnabil237/picons/astra_19.2e/installer.sh -O - | /bin/sh"),
            ("eutelsat_21.6e", "wget https://dreambox4u.com/emilnabil237/picons/eutelsat_21.6e/installer.sh -O - | /bin/sh"),
            ("astra_23.5e", "wget https://dreambox4u.com/emilnabil237/picons/astra_23.5e/installer.sh -O - | /bin/sh"),
            ("eshail_25.5e", "wget https://dreambox4u.com/emilnabil237/picons/eshail_25.5e/installer.sh -O - | /bin/sh"),
            ("badr_26.0e", "wget https://dreambox4u.com/emilnabil237/picons/badr_26.0e/installer.sh -O - | /bin/sh"),
            ("astra_28.2e", "wget https://dreambox4u.com/emilnabil237/picons/astra_28.2e/installer.sh -O - | /bin/sh"),
            ("arabsat_30.5e", "wget https://dreambox4u.com/emilnabil237/picons/arabsat_30.5e/installer.sh -O - | /bin/sh"),
            ("astra_31.5e", "wget https://dreambox4u.com/emilnabil237/picons/astra_31.5e/installer.sh -O - | /bin/sh"),
            ("intelsat_33.0e", "wget https://dreambox4u.com/emilnabil237/picons/eutelsat-intelsat_33.0e/installer.sh -O - | /bin/sh"),
            ("eutelsat_36.0e", "wget https://dreambox4u.com/emilnabil237/picons/eutelsat_36.0e/installer.sh -O - | /bin/sh"),
            ("hellas-sat_39.0e", "wget https://dreambox4u.com/emilnabil237/picons/hellas-sat_39.0e/installer.sh -O - | /bin/sh"),
            ("turksat_42.0e", "wget https://dreambox4u.com/emilnabil237/picons/turksat_42.0e/installer.sh -O - | /bin/sh"),
            ("azerspace_45.0e", "wget https://dreambox4u.com/emilnabil237/picons/azerspace_45.0e/installer.sh -O - | /bin/sh"),
            ("azerspace_46.0e", "wget https://dreambox4u.com/emilnabil237/picons/azerspace_46.0e/installer.sh -O - | /bin/sh"),
            ("turksat_50.0e_56.0e_57e", "wget https://dreambox4u.com/emilnabil237/picons/turksat_50.0e_56.0e_57e/installer.sh -O - | /bin/sh"),
            ("belintersat_51.5e", "wget https://dreambox4u.com/emilnabil237/picons/belintersat_51.5e/installer.sh -O - | /bin/sh"),
            ("turkmenalem_52.0e", "wget https://dreambox4u.com/emilnabil237/picons/turkmenalem_52.0e/installer.sh -O - | /bin/sh"),
            ("alyahsat_52.5e", "wget https://dreambox4u.com/emilnabil237/picons/alyahsat_52.5e/installer.sh -O - | /bin/sh"),
            ("express_53.0e", "wget https://dreambox4u.com/emilnabil237/picons/express_53.0e/installer.sh -O - | /bin/sh"),
            ("yamal_54.9e", "wget https://dreambox4u.com/emilnabil237/picons/gsat-yamal_54.9e/installer.sh -O - | /bin/sh"),
            ("intelsat_60.0e_66.0e_68.0e", "wget https://dreambox4u.com/emilnabil237/picons/intelsat_60.0e_66.0e_68.0e/installer.sh -O - | /bin/sh"),
            ("intelsat_62.0e", "wget https://dreambox4u.com/emilnabil237/picons/intelsat_62.0e/installer.sh -O - | /bin/sh"),
            ("eutelsat_70.0e_74.9e_75.0e", "wget https://dreambox4u.com/emilnabil237/picons/eutelsat_70.0e_74.9e_75.0e/installer.sh -O - | /bin/sh"),
            ("Intelsat_72.1e", "wget https://dreambox4u.com/emilnabil237/picons/Intelsat_72.1e/installer.sh -O - | /bin/sh"),
            ("abs_75.0e", "wget https://dreambox4u.com/emilnabil237/picons/abs_75.0e/installer.sh -O - | /bin/sh"),
            ("picons-other", "wget https://raw.githubusercontent.com/emil237/picon-other/main/installer.sh -O - | /bin/sh"),
            ("Chocholousek-Picons", "wget https://github.com/s3n0/e2plugins/raw/master/ChocholousekPicons/online-setup -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("Picons Manager"), panels)

class BootlogosPanel(BaseScreen):
    def __init__(self, session):
        panels = [
            ("BootlogoSwapper Atv", "wget http://dreambox4u.com/emilnabil237/script/bootlogoswapper-Atv.sh  -O - | /bin/sh"),
            ("Bootlogo-PURE2", "wget http://dreambox4u.com/emilnabil237/script/bootLogoswapper-Pure2.sh  -O - | /bin/sh"),
            ("BootlogoSwapper Christmas", "wget http://dreambox4u.com/emilnabil237/script/bootlogoswapper-christmas.sh -O - | /bin/sh"),
            ("BootlogoSwapper Pli", "wget http://dreambox4u.com/emilnabil237/script/bootlogoswapper-pli.sh -O - | /bin/sh"),
            ("BootlogoSwapper OpenBH", "wget http://dreambox4u.com/emilnabil237/script/bootlogoswapper-OpenBH.sh  -O - | /bin/sh"),
            ("BootlogoSwapper Egami", "wget http://dreambox4u.com/emilnabil237/script/bootLogoswapper-Egami.sh -O - | /bin/sh"),
            ("BootlogoSwapper OpenVix", "wget http://dreambox4u.com/emilnabil237/script/bootlogoswapper-OpenVix.sh  -O - | /bin/sh"),
            ("BootlogoSwapper Kids", "wget http://dreambox4u.com/emilnabil237/script/bootlogoswapper-kids.sh -O - | /bin/sh"),
            ("BootlogoSwapper Ramadan", "wget http://dreambox4u.com/emilnabil237/script/bootlogo-swapper-ramadan.sh  -O - | /bin/sh"),
            ("BootlogoSwapper Eid-Aldha", "wget http://dreambox4u.com/emilnabil237/script/bootlogoswaper-Eid-Aldha.sh -O - | /bin/sh"),
            ("BootlogoSwapper V2.1", "wget http://dreambox4u.com/emilnabil237/script/BootlogoSwapper_v2.1.sh  -O - | /bin/sh"),
            ("BootlogoSwapper V2.3", "wget http://dreambox4u.com/emilnabil237/script/BootlogoSwapper_v2.3.sh  -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("Bootlogos Manager"), panels)

class ImagesPanel(BaseScreen):
    def __init__(self, session):
        panels = [
            ("BlackHole-3.1.0", "wget https://dreambox4u.com/emilnabil237/images/BlackHole-3.1.0.sh -O - | /bin/sh"),
            ("Egami-10.4", "wget https://dreambox4u.com/emilnabil237/images/egami-10.4.sh -O - | /bin/sh"),
            ("Openatv-6.4", "wget https://dreambox4u.com/emilnabil237/images/openatv-6.4.sh -O - | /bin/sh"),
            ("Openatv-7.0", "wget https://dreambox4u.com/emilnabil237/images/openatv-7.0.sh -O - | /bin/sh"),
            ("Openatv-7.1", "wget https://dreambox4u.com/emilnabil237/images/openatv-7.1.sh -O - | /bin/sh"),
            ("Openatv-7.2", "wget https://dreambox4u.com/emilnabil237/images/openatv-7.2.sh -O - | /bin/sh"),
            ("Openatv-7.3", "wget https://dreambox4u.com/emilnabil237/images/openatv-7.3.sh -O - | /bin/sh"),
            ("Openatv-7.4", "wget https://dreambox4u.com/emilnabil237/images/openatv-7.4.sh -O - | /bin/sh"),
            ("Openatv-7.5", "wget https://dreambox4u.com/emilnabil237/images/openatv-7.5.sh -O - | /bin/sh"),
            ("Openatv-7.5.1", "wget https://dreambox4u.com/emilnabil237/images/openatv-7.5.1.sh -O - | /bin/sh"),
            ("Openatv-7.6", "wget https://dreambox4u.com/emilnabil237/images/openatv-7.6.sh -O - | /bin/sh"),
            ("OpenBlackHole-4.4", "wget https://dreambox4u.com/emilnabil237/images/openblackhole-4.4-for-vuplus-only.sh -O - | /bin/sh"),
            ("OpenBlackHole-5.0", "wget https://dreambox4u.com/emilnabil237/images/openblackhole-5.0.sh -O - | /bin/sh"),
            ("OpenBlackHole-5.1", "wget https://dreambox4u.com/emilnabil237/images/openblackhole-5.1.sh -O - | /bin/sh"),
            ("OpenBlackHole-5.2", "wget https://dreambox4u.com/emilnabil237/images/openblackhole-5.2.sh -O - | /bin/sh"),
            ("OpenBlackHole-5.3", "wget https://dreambox4u.com/emilnabil237/images/openblackhole-5.3.sh -O - | /bin/sh"),
            ("OpenBlackHole-5.4", "wget https://dreambox4u.com/emilnabil237/images/openblackhole-5.4.sh -O - | /bin/sh"),
            ("OpenBlackHole-5.5.1", "wget https://dreambox4u.com/emilnabil237/images/openblackhole-5.5.1.sh -O - | /bin/sh"),
            ("OpenDroid-7.1", "wget https://dreambox4u.com/emilnabil237/images/opendroid-7.1.sh -O - | /bin/sh"),
            ("Openpli-7.3", "wget https://dreambox4u.com/emilnabil237/images/openpli-7.3.sh -O - | /bin/sh"),
            ("OpenPli-8.3", "wget https://dreambox4u.com/emilnabil237/images/openpli-8.3.sh -O - | /bin/sh"),
            ("OpenPli-8.3-Time-Shift", "wget https://dreambox4u.com/emilnabil237/images/openpli-8.3-py2-TimeShift.sh -O - | /bin/sh"),
            ("OpenPli-9.0-Time-Shift", "wget https://dreambox4u.com/emilnabil237/images/openpli-9.0-py3-TimeShift.sh -O - | /bin/sh"),
            ("OpenPli-9.0", "wget https://dreambox4u.com/emilnabil237/images/openpli-9.0.sh -O - | /bin/sh"),
            ("OpenPli-9.1", "wget https://dreambox4u.com/emilnabil237/images/openpli-9.1.sh -O - | /bin/sh"),
            ("OpenPli-develop", "wget https://dreambox4u.com/emilnabil237/images/openpli-develop.sh -O - | /bin/sh"),
            ("openspa-7.5.xxx", "wget https://dreambox4u.com/emilnabil237/images/openspa-7.5.xxx.sh -O - | /bin/sh"),
            ("openspa-8.0.xxx", "wget https://dreambox4u.com/emilnabil237/images/openspa-8.0.xxx.sh -O - | /bin/sh"),
            ("openspa-8.1.xxx", "wget https://dreambox4u.com/emilnabil237/images/openspa-8.1.xxx.sh -O - | /bin/sh"),
            ("openspa-8.3.xxx", "wget https://dreambox4u.com/emilnabil237/images/openspa-8.3.xxx.sh -O - | /bin/sh"),
            ("openspa-8.4.xxx", "wget https://dreambox4u.com/emilnabil237/images/openspa-8.4.xxx.sh -O - | /bin/sh"),
            ("Openvix-6.6.004", "wget https://dreambox4u.com/emilnabil237/images/openvix-6.6.004.sh -O - | /bin/sh"),
            ("openvix_latest-version", "wget https://dreambox4u.com/emilnabil237/images/openvix_latest-version.sh -O - | /bin/sh"),
            ("OpenVision-py2-10.3-r395", "wget https://dreambox4u.com/emilnabil237/images/openvision/OpenVision-py2-10.3-r395.sh -O - | /bin/sh"),
            ("pure2-6.5", "wget https://dreambox4u.com/emilnabil237/images/pure2-6.5.sh -O - | /bin/sh"),
            ("pure2-7.3", "wget https://dreambox4u.com/emilnabil237/images/pure2-7.3.sh -O - | /bin/sh"),
            ("pure2-7.4", "wget https://dreambox4u.com/emilnabil237/images/pure2-7.4.sh -O - | /bin/sh"),
            ("VTI-15.0.02", "wget https://dreambox4u.com/emilnabil237/images/vti-15.0.02.sh -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("Images Manager"), panels)

class BackupSettingsPanels(BaseScreen):
    def __init__(self, session):
        panels = [
            ("Backup-my-Channels", "wget http://dreambox4u.com/emilnabil237/script/Create-My-backup-shannels.sh -O - | /bin/sh"),
            ("Backup-hotkey", "wget http://dreambox4u.com/emilnabil237/script/backup-hotkey.sh -O - | /bin/sh"),
            ("Backup-network", "wget http://dreambox4u.com/emilnabil237/script/backup-network.sh -O - | /bin/sh"),
            ("Backup-softcams", "wget http://dreambox4u.com/emilnabil237/script/backup-softcams.sh -O - | /bin/sh"),
            ("Backup-tuner", "wget http://dreambox4u.com/emilnabil237/script/backup-tuner.sh -O - | /bin/sh"),
            ("Backup-my-bouquetmakerxtream", "wget http://dreambox4u.com/emilnabil237/script/backup-my-bouquetmakerxtream.sh -O - | /bin/sh"),
            ("Backup-my-ip2sat-server", "wget http://dreambox4u.com/emilnabil237/script/backup-my-ip2sat-server.sh -O - | /bin/sh"),
            ("Backup-my-ipaudio-server", "wget http://dreambox4u.com/emilnabil237/script/backup-my-ipaudio-server.sh -O - | /bin/sh"),
            ("Backup-my-ipaudiopro-server", "wget http://dreambox4u.com/emilnabil237/script/backup-my-ipaudiopro-server.sh -O - | /bin/sh"),
            ("Backup-my-jediplaylists", "wget http://dreambox4u.com/emilnabil237/script/backup-my-jediplaylists.sh -O - | /bin/sh"),
            ("Backup-my-multistalkerpro", "wget http://dreambox4u.com/emilnabil237/script/backup-my-multistalkerpro.sh -O - | /bin/sh"),
            ("Backup-my-Subtitle-Setting", "wget http://dreambox4u.com/emilnabil237/script/backup_my-subtitle-setting.sh -O - | /bin/sh"),
            ("Backup-my-xstreamity-servers", "wget http://dreambox4u.com/emilnabil237/script/backup-my-xstreamity-servers.sh -O - | /bin/sh"),
            ("Backup-sittings-xtraevent", "wget http://dreambox4u.com/emilnabil237/script/backup-sittings-xtraevent.sh -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("BackupSettings Manager"), panels)

class RestoreSettingsPanels(BaseScreen):
    def __init__(self, session):
        panels = [
            ("Restore-my-Channels", "wget http://dreambox4u.com/emilnabil237/script/Restore-My-backup-shannels.sh -O - | /bin/sh"),
            ("Restore-hotkey", "wget http://dreambox4u.com/emilnabil237/script/resore-hotkey.sh -O - | /bin/sh"),
            ("Restore-network", "wget http://dreambox4u.com/emilnabil237/script/restore-network.sh -O - | /bin/sh"),
            ("Restore-softcams", "wget http://dreambox4u.com/emilnabil237/script/restore-softcams.sh -O - | /bin/sh"),
            ("Restore-tuner", "wget http://dreambox4u.com/emilnabil237/script/restore-tuner.sh -O - | /bin/sh"),
            ("Restore-my-bouquetmakerxtream", "wget http://dreambox4u.com/emilnabil237/script/restore-my-bouquetmakerxtream.sh -O - | /bin/sh"),
            ("Restore-my-ip2sat-server", "wget http://dreambox4u.com/emilnabil237/script/restore-my-ip2sat-server.sh -O - | /bin/sh"),
            ("Restore-my-ipaudio-server", "wget http://dreambox4u.com/emilnabil237/script/restore-my-ipaudio-server.sh -O - | /bin/sh"),
            ("Restore-my-ipaudiopro-server", "wget http://dreambox4u.com/emilnabil237/script/restore-my-ipaudiopro-server.sh -O - | /bin/sh"),
            ("Restore-my-jediplaylists", "wget http://dreambox4u.com/emilnabil237/script/restore-my-jediplaylists.sh -O - | /bin/sh"),
            ("Restore-my-multistalkerpro", "wget http://dreambox4u.com/emilnabil237/script/restore-my-multistalkerpro.sh -O - | /bin/sh"),
            ("Restore-My-Subtitle-Setting", "wget http://dreambox4u.com/emilnabil237/script/Restore_my-subtitle-setting.sh -O - | /bin/sh"),
            ("Restore-my-xstreamity-servers", "wget http://dreambox4u.com/emilnabil237/script/restore-my-xstreamity-servers.sh -O - | /bin/sh"),
            ("Restore-sittings-xtraevent", "wget http://dreambox4u.com/emilnabil237/script/restore-sittings-xtraevent.sh -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("RestoreSettings Manager"), panels)

class RemovePanel(BaseScreen):
    def __init__(self, session):
        panels = [
            ("Remove all_Crashlogs", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL_all_Crashlogs.sh -O - | /bin/sh"),
            ("Remove CCcamFinder", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-CCcamFinder.sh -O - | /bin/sh"),
            ("Remove-Channels", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-channels.sh -O - | /bin/sh"),
            ("Remove-E2iplayer", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-e2iplayer.sh -O - | /bin/sh"),
            ("Remove-Emu-All", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-emus.sh -O - | /bin/sh"),
            ("Remove-Emu-Ncam", "wget https://dreambox4u.com/emilnabil237/script/remove/del-emu-ncam.sh -O - | /bin/sh"),
            ("Remove-Emu-Oscam", "wget https://dreambox4u.com/emilnabil237/script/remove/del-emu-oscam.sh -O - | /bin/sh"),
            ("Remove-Emus-Config-Files", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-emus-config-files.sh -O - | /bin/sh"),
            ("Remove-Jedimaker-playlists", "wget https://dreambox4u.com/emilnabil237/script/remove/del-Jedimaker-playlists.sh -O - | /bin/sh"),
            ("Remove-Plugin-mediaplayer2", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-mediaplayer2.sh -O - | /bin/sh"),
            ("Remove-Plugin-NetSpeedTest", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-NetSpeedTest.sh -O - | /bin/sh"),
            ("Remove-Plugin-OscamFinder", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-OscamFinder.sh -O - | /bin/sh"),
            ("Remove-Plugin-alternativesoftcammanager", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-plugin-alternativesoftcammanager.sh -O - | /bin/sh"),
            ("Remove-Plugin-Plugin-FreeServer", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-Plugin-FreeServer.sh -O - | /bin/sh"),
            ("Remove-Plugin-levi45-addonsmanager", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-plugin-levi45-addonsmanager.sh -O - | /bin/sh"),
            ("Remove-Plugin-m3u-converter", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-plugin-m3u-converter.sh -O - | /bin/sh"),
            ("Remove-Plugin-SatVenusPANEL", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-plugin-SatVenusPANEL.sh -O - | /bin/sh"),
            ("Remove-Plugin-tvpanel", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-plugin-tvpanel.sh -O - | /bin/sh"),
            ("Remove-Plugin-XCplugin", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-Plugin-XCplugin.sh -O - | /bin/sh"),
            ("Remove-Plugin-Xstreamity", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-plugin-xstreamity.sh -O - | /bin/sh"),
            ("Remove-Plugin-youtube", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-plugin-youtube.sh -O - | /bin/sh"),
            ("Remove-Plugin-SoftCam_Manager", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-SoftCam_Manager.sh -O - | /bin/sh"),
            ("Remove-Plugin-Subssupport", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-subssupport.sh -O - | /bin/sh"),
            ("Remove-Plugin-Tvpanel", "wget https://dreambox4u.com/emilnabil237/script/remove/DEL-tvpanel.sh -O - | /bin/sh"),
            ("Remove-Tuner-Settings", "wget https://dreambox4u.com/emilnabil237/script/remove/del-Tuner-Settings.sh -O - | /bin/sh"),
            ("Remove-Xstreamity-playlists", "wget https://dreambox4u.com/emilnabil237/script/remove/del-Xstreamity-playlists.sh -O - | /bin/sh")
        ]
        BaseScreen.__init__(self, session, _("Remove Manager"), panels)

class ChannelsPanel(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        try:
            Screen.setTitle(self, _("%s") % descplug + " V." + currversion)
        except:
            pass
            
        with codecs.open(join(skin_path, "EmilPanel.xml"), "r", encoding="utf-8") as f:
            self.skin = f.read()

        self.pos = get_positions("FHD" if isWQHD() or isFHD() else "HD")
        self.name = "Channels"
        menu_list = []
        self.titles = []
        self.pics = []
        self.urls = []

        self.skin_data = {
            "Other": {
                "icon": picfold + "channels.png",
                "channels": [
                    ("Ahmed Romeh", "https://raw.githubusercontent.com/emilnabil/channel-romeh/main/installer.sh"),
                    ("Hazem-Wahba", "https://raw.githubusercontent.com/emilnabil/channel-hazem-wahba/main/installer.sh"),
                    ("Khaled Ali", "https://raw.githubusercontent.com/emilnabil/channel-khaled/main/installer.sh"),
                    ("Mohamed Goda", "https://raw.githubusercontent.com/emilnabil/channel-mohamed-goda/main/installer.sh"),
                    ("Mohamed-Nasr", "https://raw.githubusercontent.com/emilnabil/channel-mnasr/main/installer.sh"),
                    ("Tarek Ashry", "https://raw.githubusercontent.com/emilnabil/channel-tarek-ashry/main/installer.sh"),
                    ("Elsafty-Tv-Radio-Steaming", "https://dreambox4u.com/emilnabil237/settings/elsafty/installer.sh"),
                    ("Tuner_Backup_By-Emil-Nabil", "https://github.com/emilnabil/download-plugins/raw/refs/heads/main/restore-tuner-emil.sh"),
                    ("Tuner_Backup_By-M-Goda", "https://github.com/emilnabil/download-plugins/raw/refs/heads/main/restore-tuner-goda.sh")
                ]
            },
            "Ciefp": {
                "icon": picfold + "ciefp.png",
                "channels": [
                    ("ciefp-channels-e2-75e-34w", "https://raw.githubusercontent.com/emilnabil/download-plugins/main/ciefp-channels-e2/ciefp-channels-e2-75e-34w.sh"),
                    ("1sat-19E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-1sat-19E.sh"),
                    ("2satA-19E-13E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-2satA-19E-13E.sh"),
                    ("2satB-19E-16E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-2satB-19E-16E.sh"),
                    ("3satA-9E-10E-13E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-3satA-9E-10E-13E.sh"),
                    ("3satB-19E-16E-13E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-3satB-19E-16E-13E.sh"),
                    ("4satA-28E-19E-13E-30W", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-4satA-28E-19E-13E-30W.sh"),
                    ("4satB-19E-16E-13E-0.8W", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-4satB-19E-16E-13E-0.8W.sh"),
                    ("5sat-19E-16E-13E-1.9E-0.8W", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-5sat-19E-16E-13E-1.9E-0.8W.sh"),
                    ("6sat-23E-19E-16E-13E-1.9E-0.8W", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-6sat-23E-19E-16E-13E-1.9E-0.8W.sh"),
                    ("7sat-23E-19E-16E-13E-4.8E-1.9E-0.8W", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-7sat-23E-19E-16E-13E-4.8E-1.9E-0.8W.sh"),
                    ("8sat-28E-23E-19E-16E-13E-4.8E-1.9E-0.8W", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-8sat-28E-23E-19E-16E-13E-4.8E-1.9E-0.8W.sh"),
                    ("9sat-28E-23E-19E-16E-13E-9E-1.9E-0.8W-5W", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-9sat-28E-23E-19E-16E-13E-9E-1.9E-0.8W-5W.sh"),
                    ("10sat-39E-28E-23E-19E-16E-13E-9E-4.8E-1.9E-0.8W", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-10sat.sh"),
                    ("13sat-42E-39E-28E-23E-19E-16E-13E-9E-7E-4.8E-1.9E-0.8w-5w", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-13sat.sh"),
                    ("16sat-42E-39E-28E-26E-23E-19E-16E-13E-10E-9E-7E-4.8E-1.9E-0.8w-4W-5w", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-16sat.sh"),
                    ("18sat-42E-39E-36E-33E-28E-26E-23E-19E-16E-13E-10E-9E-7E-4.8E-1.9E-0.8w-4w-5w", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/ciefp-channels-e2/ciefp-E2-18sat.sh")
                ]
            },
            "morph883": {
                "icon": picfold + "morpheus883.png",
                "channels": [
                    ("Morph883_0.8W-4.8E-13E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_0.8W-4.8E-13E.sh"),
                    ("Morph883_0.8W-13E-19.2E-28.2E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_0.8W-13E-19.2E-28.2E.sh"),
                    ("Morph883_0.8W-13E-19.2E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_0.8W-13E-19.2E.sh"),
                    ("Morph883_0.8W-13E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_0.8W-13E.sh"),
                    ("Morph883_4.8E-13E-19.2E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_4.8E-13E-19.2E.sh"),
                    ("Morph883_4.8E-13E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_4.8E-13E.sh"),
                    ("Morph883_9E-13E-19.2E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_9E-13E-19.2E.sh"),
                    ("Morph883_9E-13E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_9E-13E.sh"),
                    ("Morph883_13E-16E-19.2E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_13E-16E-19.2E.sh"),
                    ("Morph883_13E-16E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_13E-16E.sh"),
                    ("Morph883_13E-19.2E-23.5E-28.2E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_13E-19.2E-23.5E-28.2E.sh"),
                    ("Morph883_13E-19.2E-23.5E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_13E-19.2E-23.5E.sh"),
                    ("Morph883_13E-19.2E-28.2E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_13E-19.2E-28.2E.sh"),
                    ("Morph883_13E-19.2E-42E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_13E-19.2E-42E.sh"),
                    ("Morph883_13E-19.2E.sh", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_13E-19.2E.sh"),
                    ("Morph883_13E-23.5E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_13E-23.5E.sh"),
                    ("Morph883_13E-28.2E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_13E-28.2E.sh"),
                    ("Morph883_13E-42E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_13E-42E.sh"),
                    ("Morph883_13E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_13E.sh"),
                    ("Morph883_30W-13E-19.2E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_30W-13E-19.2E.sh"),
                    ("Morph883_30W-13E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_30W-13E.sh"),
                    ("Morph883_Motor", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_Motor.sh"),
                    ("Morph883_Settings", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/morpheus883-channels/E2_Morph883_Settings.sh")
                ]
            },
            "vaninbal": {
                "icon": picfold + "vhannibal.png",
                "channels": [
                    ("Vhaninibal-Dual-13-19E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Dual-13-19E.sh"),
                    ("Vhaninbal-Dual-DTT-Campania", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Dual-DTT-Campania.sh"),
                    ("Vhaninbal-Dual-DTT-Italia", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Dual-DTT-Italia.sh"),
                    ("Vhaninbal-Dual-DTT-Lazio", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Dual-DTT-Lazio.sh"),
                    ("Vhaninbal-Dual-DTT-Lombardia", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Dual-DTT-Lombardia.sh"),
                    ("Vhaninbal-Dual-DTT-Piemonte", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Dual-DTT-Piemonte.sh"),
                    ("Vhaninbal-HotBird-13E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-HotBird-13E.sh"),
                    ("Vhaninbal-HotBird-DTT-Campania", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-HotBird-DTT-Campania.sh"),
                    ("Vhaninbal-HotBird-DTT-Italia", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-HotBird-DTT-Italia.sh"),
                    ("Vhaninbal-HotBird-DTT-Lazio", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-HotBird-DTT-Lazio.sh"),
                    ("Vhaninbal-HotBird-DTT-Lombardia", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-HotBird-DTT-Lombardia.sh"),
                    ("Vhaninbal-HotBird-DTT-Piemonte", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-HotBird-DTT-Piemonte.sh"),
                    ("Vhaninbal-Motor-70E-45W", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Motor-70E-45W.sh"),
                    ("Vhaninbal-Motor-DTT-Campania", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Motor-DTT-Campania.sh"),
                    ("Vhaninbal-Motor-DTT-Italia", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Motor-DTT-Italia.sh"),
                    ("Vhaninbal-Motor-DTT-Lazio", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Motor-DTT-Lazio.sh"),
                    ("Vhaninbal-Motor-DTT-Lombardia", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Motor-DTT-Lombardia.sh"),
                    ("Vhaninbal-Motor-DTT-Piemonte", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Motor-DTT-Piemonte.sh"),
                    ("Vhaninbal-Motor-DTT-Romagna", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Motor-DTT-Romagna.sh"),
                    ("Vhaninbal-Motor-DTT-Sardegna", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Motor-DTT-Sardegna.sh"),
                    ("Vhaninbal-Motor-DTT-Sicilia", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Motor-DTT-Sicilia.sh"),
                    ("Vhaninbal-Quadri-9-13-16-19-23E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Quadri-9-13-16-19-23E.sh"),
                    ("Vhaninbal-Quadri-13-19-5E-1W", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Quadri-13-19-5E-1W.sh"),
                    ("Vhaninbal-Quadri-13-19-9E-5W", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Quadri-13-19-9E-5W.sh"),
                    ("Vhaninbal-Quadri-13-19-23-28E", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Quadri-13-19-23-28E.sh"),
                    ("Vhaninbal-Trial-13-19E-5W", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Trial-13-19E-5W.sh"),
                    ("Vhaninbal-Trial-13-19E-30W", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/vanenbal-channels/Vhannibal-Trial-13-19E-30W.sh")
                ]
            }
        }

        for category, data in self.skin_data.items():
            menu_list.append(category)
            self.titles.append(category.strip())
            self.pics.append(data["icon"])
            self.urls.append(category.lower())

        self.names = menu_list
        self.sorted = False

        self["frame"] = MovingPixmap()
        self["info"] = Label()
        self["info"].setText(_("Please Wait..."))
        self["sort"] = Label(_("Sort A-Z"))
        self["key_red"] = Label(_("Exit"))
        self["pixmap"] = Pixmap()
        self["actions"] = ActionMap(
            ["OkCancelActions", "MenuActions", "DirectionActions", "NumberActions", "ColorActions", "EPGSelectActions"],
            {
                "ok": self.okbuttonClick,
                "cancel": self.closeNonRecursive,
                "exit": self.closeRecursive,
                "back": self.closeNonRecursive,
                "red": self.closeNonRecursive,
                "0": self.list_sort,
                "left": self.key_left,
                "right": self.key_right,
                "up": self.key_up,
                "down": self.key_down,
                "menu": self.closeRecursive
            }, -1)

        self.PIXMAPS_PER_PAGE = 20
        for i in range(self.PIXMAPS_PER_PAGE):
            self["label" + str(i + 1)] = StaticText()
            self["pixmap" + str(i + 1)] = Pixmap()

        self.npics = len(self.names)
        self.npage = (self.npics // self.PIXMAPS_PER_PAGE) + 1
        self.index = 0
        self.maxentry = len(menu_list) - 1
        self.ipage = 1
        self.onLayoutFinish.append(self.openTest)

    def paintFrame(self):
        try:
            self.idx = min(self.index, self.maxentry)
            name = self.names[self.idx]
            self["info"].setText(str(name))
            ifr = self.index - (self.PIXMAPS_PER_PAGE * (self.ipage - 1))
            self["frame"].moveTo(self.pos[ifr][0], self.pos[ifr][1], 1)
            self["frame"].startMoving()
        except Exception as e:
            print("PaintFrame Error:", e)

    def openTest(self):
        if self.ipage < self.npage:
            self.maxentry = (self.PIXMAPS_PER_PAGE * self.ipage) - 1
            self.minentry = (self.ipage - 1) * self.PIXMAPS_PER_PAGE
        else:
            self.maxentry = len(self.pics) - 1
            self.minentry = (self.ipage - 1) * self.PIXMAPS_PER_PAGE
            for i1 in range(self.PIXMAPS_PER_PAGE):
                self["label" + str(i1 + 1)].setText(" ")
                self["pixmap" + str(i1 + 1)].instance.setPixmapFromFile(nss_pic)

        for i in range(min(self.maxentry - self.minentry + 1, len(self.pics) - self.minentry)):
            idx = self.minentry + i
            pic = self.pics[idx] if exists(self.pics[idx]) else nss_pic
            self["pixmap" + str(i + 1)].instance.setPixmapFromFile(pic)
            self["pixmap" + str(i + 1)].instance.setPixmap(None) if idx >= len(self.pics) else None

        self.index = self.minentry
        self.paintFrame()

    def key_left(self):
        self.index = max(self.index - 1, 0)
        if self.index < self.minentry:
            self.ipage = max(self.ipage - 1, 1)
            self.openTest()
        else:
            self.paintFrame()

    def key_right(self):
        self.index = min(self.index + 1, self.npics - 1)
        if self.index > self.maxentry:
            self.ipage = min(self.ipage + 1, self.npage)
            self.openTest()
        else:
            self.paintFrame()

    def key_up(self):
        if self.index == 0 and self.ipage == 1:
            self.ipage = self.npage
            self.index = self.minentry
            self.openTest()
        elif self.index >= 5:
            self.index -= 5
            self.paintFrame()

    def key_down(self):
        if self.index <= self.maxentry - 5:
            self.index += 5
        else:
            self.ipage = 1 if self.ipage == self.npage else self.ipage + 1
            self.index = self.minentry
            self.openTest()
        self.paintFrame()

    def list_sort(self):
        if not hasattr(self, "original_data"):
            self.original_data = (self.names[:], self.titles[:], self.pics[:], self.urls[:])
            self.sorted = False

        if self.sorted:
            self.names, self.titles, self.pics, self.urls = self.original_data
            self["sort"].setText(_("Sort A-Z"))
        else:
            self.names, self.titles, self.pics, self.urls = ListSortUtility.list_sort(self.names, self.titles, self.pics, self.urls)
            self["sort"].setText(_("Sort Default"))
        self.sorted = not self.sorted
        self.openTest()

    def closeNonRecursive(self):
        self.close(False)

    def closeRecursive(self):
        self.close(True)

    def okbuttonClick(self):
        category = self.names[self.index]
        channels = self.skin_data.get(category, {}).get("channels", [])
        self.session.open(ChannelSubMenu, category, channels)

class ChannelSubMenu(Screen):
    def __init__(self, session, category, channels):
        Screen.__init__(self, session)
        self.skin = """
        <screen position="center,center" size="1200,700" title="%s">
            <widget name="list" position="50,50" size="1100,600" itemHeight="60" scrollbarMode="showOnDemand"/>
            <widget source="key_red" render="Label" position="150,650" size="400,45" backgroundColor="#ff0000" halign="center" valign="center" transparent="0" font="Bold;35"/>
            <widget source="key_green" render="Label" position="650,650" size="400,45" backgroundColor="#008000" halign="center" valign="center" transparent="0" font="Bold;35"/>
        </screen>""" % category

        self.category = category
        self.channels = channels
        self["list"] = LPSlist([])
        self["key_red"] = StaticText(_("Back"))
        self["key_green"] = StaticText(_("Install"))
        
        self["actions"] = ActionMap(["ColorActions", "OkCancelActions"], {
            "ok": self.install_channel,
            "green": self.install_channel,
            "red": self.close,
            "cancel": self.close
        }, -2)

        self.channel_names = [name for name, url in self.channels]
        self.channel_scripts = [url for name, url in self.channels]
        
        LPshowlist(self.channel_names, self["list"])

    def install_channel(self):
        idx = self["list"].getSelectedIndex()
        if idx is not None and 0 <= idx < len(self.channel_scripts):
            self.session.open(Console, _("Installing Channel"), ["wget %s -O - | /bin/sh" % self.channel_scripts[idx]])

class SkinsPanel(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        try:
            Screen.setTitle(self, _("%s") % descplug + " V." + currversion)
        except:
            pass
            
        with codecs.open(join(skin_path, "EmilPanel.xml"), "r", encoding="utf-8") as f:
            self.skin = f.read()

        self.pos = get_positions("FHD" if isWQHD() or isFHD() else "HD")
        self.name = "Skins"
        menu_list = []
        self.titles = []
        self.pics = []
        self.urls = []

        self.skin_data = {
            "OpenATV": {
                "icon": picfold + "openatv_icon.png",
                "skins": [
                    ("Aglare-FHD", "https://raw.githubusercontent.com/popking159/skins/refs/heads/main/aglareatv/installer.sh"),
                    ("Areadeltasat_fhd", "https://github.com/emil237/skins-enigma2/raw/refs/heads/main/ATV/skins_areadeltasat_fhd_dragon_1_9_Poster_Backdrop.sh"),
                    ("Barby-Black-py3-FHD", "https://dreambox4u.com/emilnabil237/script/SKIN-Barby-Black-py3-fhd.sh"),
                    ("Barby-Green-py3-FHD", "https://dreambox4u.com/emilnabil237/script/SKIN-Barby-Green-py3-FHD.sh"),
                    ("Barby-purple-py3-FHD", "https://dreambox4u.com/emilnabil237/script/SKIN-Barby-purple-py3-fhd.sh"),
                    ("Barby-py3-FHD", "https://dreambox4u.com/emilnabil237/script/SKIN-Barby-py3-fhd.sh"),
                    ("Fury-FHD", "https://raw.githubusercontent.com/islam-2412/IPKS/refs/heads/main/fury/installer.sh"),
                    ("Gradient-fhd", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/skins-gradient-fhd.sh"),
                    ("Maxy-FHD", "https://raw.githubusercontent.com/popking159/skins/refs/heads/main/maxyatv/installer.sh"),
                    ("Full HD Glass17", "http://dreambox4u.com/emilnabil237/skins/skin-fullhdglass17/installer.sh"),
                    ("MyMetrixLiteBackup", "https://raw.githubusercontent.com/emilnabil/download-plugins/refs/heads/main/MyMetrixLiteBackup.sh"),
                    ("MetrixFHD-Extraevent-PosterXD", "https://dreambox4u.com/emilnabil237/skins/openatv/SKIN-MetrixFHD-OpenATV-Extraevent-PosterX.sh"),
                    ("malek-fhd", "https://raw.githubusercontent.com/emil237/skins-enigma2/main/ATV/skins-malek-fhd_2.2_py3.11.2-py3.12.1.sh"),
                    ("Nacht_1.7.3", "http://dreambox4u.com/emilnabil237/script/SKIN-ATV-nacht_1.7.3.sh"),
                    ("Op-Artkoala-FHD", "https://dreambox4u.com/emilnabil237/skins/openatv/skins-op-artkoala.sh"),
                    ("Ozeta-Xtra", "http://dreambox4u.com/emilnabil237/script/SKIN-ATV-ozeta-xtra.sh"),
                    ("XDreamy-FHD", "https://raw.githubusercontent.com/Insprion80/Skins/main/xDreamy/installer.sh")
                ]
            },
            "TeamNitro": {
                "icon": picfold + "teamnitro.png",
                "skins": [
                    ("TeamNitro Control", "https://gitlab.com/emilnabil1/teamnitro/-/raw/main/SKIN-teamnitro.sh"),
                    ("AlAyam-FHD", "https://raw.githubusercontent.com/biko-73/TeamNitro/main/script/installerAL.sh"),
                    ("Desert-FHD", "https://gitlab.com/emilnabil1/teamnitro/-/raw/main/installer-skin-desert.sh"),
                    ("BoHLALA-FHD", "https://gitlab.com/emilnabil1/teamnitro/-/raw/main/installer.sh"),
                    ("Dragon-FHD", "https://raw.githubusercontent.com/biko-73/TeamNitro/main/script/installerD.sh"),
                    ("NitroAdvance-FHD", "https://raw.githubusercontent.com/biko-73/TeamNitro/main/script/installerN.sh"),
                    ("Klll-Pro-FHD", "https://raw.githubusercontent.com/biko-73/zelda77/main/installer.sh")
                ]
            },
            "OpenBH": {
                "icon": picfold + "openbh_icon.png",
                "skins": [
                    ("Aglare-fhd", "https://raw.githubusercontent.com/popking159/skins/refs/heads/main/aglarepli/installer.sh"),
                    ("Fury-FHD", "https://raw.githubusercontent.com/islam-2412/IPKS/refs/heads/main/fury/installer.sh"),
                    ("MX_BlackSea", "https://dreambox4u.com/emilnabil237/skins/obh/skins-MX_BlackSea.sh"),
                    ("MX-Sline-Black-Red-Gradient", "https://dreambox4u.com/emilnabil237/skins/obh/mx-sline-black-red-gradient_py3.12.sh"),
                    ("MX_Sline-Blue", "https://dreambox4u.com/emilnabil237/skins/obh/MX_Sline-Blue_OBH_5.4_py3.12_py3.12.sh"),
                    ("Mx-Sline-Glass-Gradient", "https://github.com/emilnabil/skins-obh/raw/refs/heads/main/skins-mx-sline-glass-gradient.sh"),
                    ("MX_Sline-Red_X2", "https://dreambox4u.com/emilnabil237/skins/obh/MX_Sline-Red_X2_py3.12.sh"),
                    ("OpenBhGreenFHD", "https://dreambox4u.com/emilnabil237/skins/obh/skin_OpenBhGreenFHD.sh"),
                    ("XDreamy-FHD", "https://raw.githubusercontent.com/Insprion80/Skins/main/xDreamy/installer.sh"),
                    ("Youchie-OBH-FHD", "https://raw.githubusercontent.com/emilnabil/skins-obh/refs/heads/main/skin-Youchie-OBH-FHD.sh")
                ]
            },
            "Egami": {
                "icon": picfold + "egami_icon.png",
                "skins": [
                    ("Aglare-FHD", "https://raw.githubusercontent.com/popking159/skins/refs/heads/main/aglareatv/installer.sh"),
                    ("Fury-FHD", "https://raw.githubusercontent.com/islam-2412/IPKS/refs/heads/main/fury/installer.sh"),
                    ("Premium-Fhd", "https://dreambox4u.com/emilnabil237/skins/script/SKIN-egami-premium-fhd-py3.sh"),
                    ("Premium-Black-Fhd", "https://dreambox4u.com/emilnabil237/skins/script/SKIN-egami-premium--black-fhd-py3.sh"),
                    ("Premium-Blue-Fhd", "https://dreambox4u.com/emilnabil237/skins/script/SKIN-egami-premium--blue-fhd-py3.sh"),
                    ("XDreamy-FHD", "https://raw.githubusercontent.com/Insprion80/Skins/main/xDreamy/installer.sh")
                ]
            },
            "OpenPli_py3": {
                "icon": picfold + "openpli.png",
                "skins": [
                    ("Aglare-FHD", "https://raw.githubusercontent.com/popking159/skins/refs/heads/main/aglareatv/installer.sh"),
                    ("BARDO-FHD", "https://raw.githubusercontent.com/emil237/skins-enigma2/refs/heads/main/pli/Skin-bardo-fhd_3.7.2.sh"),
                    ("BLACKNEON-XP_Mod_M-Nasr", "https://dreambox4u.com/emilnabil237/skins/pli9x/Skin-BLACKNEON-XP_mod_mnasr-pli9x.sh"),
                    ("malek-fhd", "https://raw.githubusercontent.com/emil237/skins-enigma2/main/pli/Skin-malek-fhd_1.2.sh"),
                    ("Ozeta-Xtra", "http://dreambox4u.com/emilnabil237/script/SKIN-PLI-ozeta-xtra.sh"),
                    ("XDreamy-FHD", "https://raw.githubusercontent.com/Insprion80/Skins/main/xDreamy/installer.sh"),
                    ("Youchie-PLI-FHD", "https://raw.githubusercontent.com/emilnabil/skins-openpli-9x/refs/heads/main/skin-Youchie-PLI-FHD.sh")
                ]
            },
            "OpenSpa": {
                "icon": picfold + "openspa.png",
                "skins": [
                    ("Aglare-FHD", "https://raw.githubusercontent.com/popking159/skins/refs/heads/main/aglareatv/installer.sh"),
                    ("Fury-FHD", "https://raw.githubusercontent.com/islam-2412/IPKS/refs/heads/main/fury/installer.sh"),
                    ("estuary-1080-FHD", "https://gitlab.com/elbrins/skins/-/raw/main/Spa/Skin-estuary-1080.sh"),
                    ("Skyline", "https://github.com/emilnabil/skins-spa/raw/refs/heads/main/skin-Skyline.sh")
                ]
            },
            "OpenVix": {
                "icon": picfold + "openvix.png",
                "skins": [
                    ("Aglare-FHD", "https://raw.githubusercontent.com/popking159/skins/refs/heads/main/aglarepli/installer.sh"),
                    ("E2-darkos-FHD", "https://dreambox4u.com/emilnabil237/skins/openvix/skins-e2-darkos.sh"),
                    ("Fury-FHD", "https://raw.githubusercontent.com/islam-2412/IPKS/refs/heads/main/fury/installer.sh"),
                    ("Magic-FHD", "https://dreambox4u.com/emilnabil237/skins/openvix/skins-openvix-magic-fhd.sh"),
                    ("Vixbmc-1080-Confluence-FHD", "https://dreambox4u.com/emilnabil237/skins/openvix/skins-openvix-vixbmc-1080-confluence.sh"),
                    ("XDreamy-FHD", "https://raw.githubusercontent.com/Insprion80/Skins/main/xDreamy/installer.sh"),
                    ("Youchie-OpenVix-FHD", "https://raw.githubusercontent.com/emilnabil/skins-obh/refs/heads/main/skin-Youchie-OBH-FHD.sh")
                ]
            },
            "OpenPli_py2": {
                "icon": picfold + "openpli.png",
                "skins": [
                    ("Bluemetal-FHD", "https://raw.githubusercontent.com/emil237/skins-enigma2/refs/heads/main/pli/Skin-bluemetal-fhd.sh"),
                    ("CH.LEAGUE-FHD", "http://dreambox4u.com/emilnabil237/script/SKIN-PLI-CH.LEAGUE-FHD.sh"),
                    ("Maxy-FHD", "https://dreambox4u.com/emilnabil237/skins/script/skins-Maxy-FHD.sh"),
                    ("Ozeta-Xtra", "http://dreambox4u.com/emilnabil237/script/SKIN-PLI-ozeta-xtra.sh"),
                    ("QATAR-2022-V3-FHD", "http://dreambox4u.com/emilnabil237/script/SKIN-PLI-QATAR-2022-V3-FHD.sh"),
                    ("SPIDERMAN-FHD", "http://dreambox4u.com/emilnabil237/script/SKIN-PLI-SPIDERMAN-FHD.sh"),
                    ("WAR-S-FHD", "http://dreambox4u.com/emilnabil237/script/SKIN-PLI-WAR-S-FHD.sh"),
                    ("BLACKSKY-S-HD", "https://raw.githubusercontent.com/emil237/skins-enigma2/main/pli/SKIN-BLACKSKY-S-HD-MOD-By-Muaath.sh"),
                    ("BATMAN-MP-HD", "https://raw.githubusercontent.com/emil237/skins-enigma2/main/pli/SKIN-BATMAN-MP-HD-By-Muaath.sh"),
                    ("TOKYO2020-FHD", "https://raw.githubusercontent.com/emil237/skins-enigma2/main/pli/SKIN-TOKYO2020-FHD-By-Muaath.sh")
                ]
            },
            "Skins-Plugin-Xtreamity": {
                "icon": picfold + "xstreamity.png",
                "skins": [
                    ("Abstract", "https://dreambox4u.com/emilnabil237/plugins/xtreamity/installer-skin-abstract.sh"),
                    ("qatar2022", "https://dreambox4u.com/emilnabil237/plugins/xtreamity/installer-skin-qatar.sh"),
                    ("Toys", "https://dreambox4u.com/emilnabil237/plugins/xtreamity/installer-skin-toys.sh")
                ]
            },
        }

        for category, data in self.skin_data.items():
            menu_list.append(category)
            self.titles.append(category.strip())
            self.pics.append(data["icon"])
            self.urls.append(category.lower())

        self.names = menu_list
        self.sorted = False

        self["frame"] = MovingPixmap()
        self["info"] = Label()
        self["info"].setText(_("Please Wait..."))
        self["sort"] = Label(_("Sort A-Z"))
        self["key_red"] = Label(_("Exit"))
        self["pixmap"] = Pixmap()
        self["actions"] = ActionMap(
            ["OkCancelActions", "MenuActions", "DirectionActions", "NumberActions", "ColorActions", "EPGSelectActions"],
            {
                "ok": self.okbuttonClick,
                "cancel": self.closeNonRecursive,
                "exit": self.closeRecursive,
                "back": self.closeNonRecursive,
                "red": self.closeNonRecursive,
                "0": self.list_sort,
                "left": self.key_left,
                "right": self.key_right,
                "up": self.key_up,
                "down": self.key_down,
                "menu": self.closeRecursive
            }, -1)

        self.PIXMAPS_PER_PAGE = 20
        for i in range(self.PIXMAPS_PER_PAGE):
            self["label" + str(i + 1)] = StaticText()
            self["pixmap" + str(i + 1)] = Pixmap()

        self.npics = len(self.names)
        self.npage = (self.npics // self.PIXMAPS_PER_PAGE) + 1
        self.index = 0
        self.maxentry = len(menu_list) - 1
        self.ipage = 1
        self.onLayoutFinish.append(self.openTest)

    def paintFrame(self):
        try:
            self.idx = min(self.index, self.maxentry)
            name = self.names[self.idx]
            self["info"].setText(str(name))
            ifr = self.index - (self.PIXMAPS_PER_PAGE * (self.ipage - 1))
            self["frame"].moveTo(self.pos[ifr][0], self.pos[ifr][1], 1)
            self["frame"].startMoving()
        except Exception as e:
            print("PaintFrame Error:", e)

    def openTest(self):
        if self.ipage < self.npage:
            self.maxentry = (self.PIXMAPS_PER_PAGE * self.ipage) - 1
            self.minentry = (self.ipage - 1) * self.PIXMAPS_PER_PAGE
        else:
            self.maxentry = len(self.pics) - 1
            self.minentry = (self.ipage - 1) * self.PIXMAPS_PER_PAGE
            for i1 in range(self.PIXMAPS_PER_PAGE):
                self["label" + str(i1 + 1)].setText(" ")
                self["pixmap" + str(i1 + 1)].instance.setPixmapFromFile(nss_pic)

        for i in range(min(self.maxentry - self.minentry + 1, len(self.pics) - self.minentry)):
            idx = self.minentry + i
            pic = self.pics[idx] if exists(self.pics[idx]) else nss_pic
            self["pixmap" + str(i + 1)].instance.setPixmapFromFile(pic)
            self["pixmap" + str(i + 1)].instance.setPixmap(None) if idx >= len(self.pics) else None

        self.index = self.minentry
        self.paintFrame()

    def key_left(self):
        self.index = max(self.index - 1, 0)
        if self.index < self.minentry:
            self.ipage = max(self.ipage - 1, 1)
            self.openTest()
        else:
            self.paintFrame()

    def key_right(self):
        self.index = min(self.index + 1, self.npics - 1)
        if self.index > self.maxentry:
            self.ipage = min(self.ipage + 1, self.npage)
            self.openTest()
        else:
            self.paintFrame()

    def key_up(self):
        if self.index == 0 and self.ipage == 1:
            self.ipage = self.npage
            self.index = self.minentry
            self.openTest()
        elif self.index >= 5:
            self.index -= 5
            self.paintFrame()

    def key_down(self):
        if self.index <= self.maxentry - 5:
            self.index += 5
        else:
            self.ipage = 1 if self.ipage == self.npage else self.ipage + 1
            self.index = self.minentry
            self.openTest()
        self.paintFrame()

    def list_sort(self):
        if not hasattr(self, "original_data"):
            self.original_data = (self.names[:], self.titles[:], self.pics[:], self.urls[:])
            self.sorted = False

        if self.sorted:
            self.names, self.titles, self.pics, self.urls = self.original_data
            self["sort"].setText(_("Sort A-Z"))
        else:
            self.names, self.titles, self.pics, self.urls = ListSortUtility.list_sort(self.names, self.titles, self.pics, self.urls)
            self["sort"].setText(_("Sort Default"))
        self.sorted = not self.sorted
        self.openTest()

    def closeNonRecursive(self):
        self.close(False)

    def closeRecursive(self):
        self.close(True)

    def okbuttonClick(self):
        category = self.names[self.index]
        skins = self.skin_data.get(category, {}).get("skins", [])
        self.session.open(SkinSubMenu, category, skins)

class SkinSubMenu(Screen):
    def __init__(self, session, category, skins):
        Screen.__init__(self, session)
        self.skin = """
        <screen position="center,center" size="1200,700" title="%s">
            <widget name="list" position="50,50" size="1100,600" itemHeight="60" scrollbarMode="showOnDemand"/>
            <widget source="key_red" render="Label" position="150,650" size="400,45" backgroundColor="#ff0000" halign="center" valign="center" transparent="0" font="Bold;35"/>
            <widget source="key_green" render="Label" position="650,650" size="400,45" backgroundColor="#008000" halign="center" valign="center" transparent="0" font="Bold;35"/>
        </screen>""" % category

        self.category = category
        self.skins = skins
        self["list"] = LPSlist([])
        self["key_red"] = StaticText(_("Back"))
        self["key_green"] = StaticText(_("Install"))
        
        self["actions"] = ActionMap(["ColorActions", "OkCancelActions"], {
            "ok": self.install_skin,
            "green": self.install_skin,
            "red": self.close,
            "cancel": self.close
        }, -2)

        self.skin_names = [name for name, url in self.skins]
        self.skin_scripts = [url for name, url in self.skins]
        
        LPshowlist(self.skin_names, self["list"])

    def install_skin(self):
        idx = self["list"].getSelectedIndex()
        if idx is not None and 0 <= idx < len(self.skin_scripts):
            self.session.open(Console, _("Installing Skin"), ["wget %s -O - | /bin/sh" % self.skin_scripts[idx]])

class EmilPanel(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        try:
            Screen.setTitle(self, _("%s") % descplug + " V." + currversion)
        except:
            pass
            
        with codecs.open(join(skin_path, "Free-Panel.xml"), "r", encoding="utf-8") as f:
            self.skin = f.read()

        self.pos = get_positions("FHD" if isWQHD() or isFHD() else "HD")
        menu_list = []
        self.titles = []
        self.pics = []
        self.urls = []

        add_menu = [
            ("Panels", "panels.png"),
            ("Plugins", "plugins.png"),
            ("Tools", "tools.png"),
            ("SystemPlugins", "system.png"),
            ("Channels", "channels.png"),
            ("Media", "media.png"),
            ("Feeds", "feeds.png"),
            ("MultibootPlugins", "multiboot.png"),
            ("Softcams", "emu.png"),
            ("BackupSettings", "backup.png"),
            ("RestoreSettings", "backup.png"),
            ("Images", "images.png"),
            ("Picons", "picon.png"),
            ("Bootlogos", "bootlogo.png"),
            ("Skins", "skins.png"),
            ("Remove", "remove.png")
        ]
        
        for name, pic in add_menu:
            menu_list.append(name)
            self.titles.append(name.strip())
            self.pics.append(picfold + pic)
            self.urls.append("")

        self.names = menu_list
        self.sorted = False

        self["frame"] = MovingPixmap()
        self["info"] = Label()
        self["info"].setText(_("Please Wait..."))
        self["sort"] = Label(_("Sort A-Z"))
        self["key_red"] = Label(_("Exit"))
        self["key_yellow"] = Label(_("Update"))
        self["pixmap"] = Pixmap()
        
        self["actions"] = ActionMap(
            ["OkCancelActions", "MenuActions", "DirectionActions", "NumberActions", "ColorActions", "EPGSelectActions"],
            {
                "ok": self.okbuttonClick,
                "cancel": self.closeNonRecursive,
                "exit": self.closeRecursive,
                "back": self.closeNonRecursive,
                "red": self.closeNonRecursive,
                "yellow": self.updatePlugin,
                "0": self.list_sort,
                "left": self.key_left,
                "right": self.key_right,
                "up": self.key_up,
                "down": self.key_down,
                "menu": self.closeRecursive
            }, -1)

        self.PIXMAPS_PER_PAGE = 20
        for i in range(self.PIXMAPS_PER_PAGE):
            self["label" + str(i + 1)] = StaticText()
            self["pixmap" + str(i + 1)] = Pixmap()
            self["name_label" + str(i + 1)] = Label()

        self.npics = len(self.names)
        self.npage = (self.npics // self.PIXMAPS_PER_PAGE) + 1
        self.index = 0
        self.ipage = 1
        
        self.update_timer = eTimer()
        self.update_timer.callback.append(self.check_for_updates)
        self.onLayoutFinish.append(self.openTest)

    def updatePlugin(self):
        self.session.open(
            Console, 
            _("Updating EmilPanelPro"), 
            ["wget %s -O - | /bin/sh" % UPDATE_SCRIPT_URL]
        )

    def paintFrame(self):
        try:
            self.idx = min(self.index, len(self.names)-1)
            name = self.names[self.idx]
            self["info"].setText(str(name))
            ifr = self.index - (self.PIXMAPS_PER_PAGE * (self.ipage - 1))
            self["frame"].moveTo(self.pos[ifr][0], self.pos[ifr][1], 1)
            self["frame"].startMoving()
        except Exception as e:
            print("PaintFrame Error:", e)

    def openTest(self):
        if self.ipage < self.npage:
            self.maxentry = (self.PIXMAPS_PER_PAGE * self.ipage) - 1
            self.minentry = (self.ipage - 1) * self.PIXMAPS_PER_PAGE
        else:
            self.maxentry = len(self.pics) - 1
            self.minentry = (self.ipage - 1) * self.PIXMAPS_PER_PAGE
            for i1 in range(self.PIXMAPS_PER_PAGE):
                self["label" + str(i1 + 1)].setText(" ")
                self["pixmap" + str(i1 + 1)].instance.setPixmapFromFile(nss_pic)
                self["name_label" + str(i1 + 1)].setText(" ")

        for i in range(min(self.maxentry - self.minentry + 1, len(self.pics) - self.minentry)):
            idx = self.minentry + i
            pic = self.pics[idx] if exists(self.pics[idx]) else nss_pic
            self["pixmap" + str(i + 1)].instance.setPixmapFromFile(pic)
            self["name_label" + str(i + 1)].setText(self.names[idx])
            self["pixmap" + str(i + 1)].instance.setPixmap(None) if idx >= len(self.pics) else None

        self.index = self.minentry
        self.paintFrame()
        self.update_timer.start(3600000, True)

    def check_for_updates(self):
        try:
            response = requests.get(VERSION_URL, timeout=5)
            response.raise_for_status()
            latest_version = response.text.strip()
            if self.compare_versions(PLUGIN_VERSION, latest_version) < 0:
                self.session.openWithCallback(
                    self.update_confirmed,
                    MessageBox,
                    _("A new version %s is available!\nUpdate now?") % latest_version,
                    MessageBox.TYPE_YESNO
                )
        except Exception as e:
            print("Update check failed:", str(e))

    def compare_versions(self, current, latest):
        current_parts = list(map(int, current.split('.')))
        latest_parts = list(map(int, latest.split('.')))
        max_len = max(len(current_parts), len(latest_parts))
        current_parts += [0] * (max_len - len(current_parts))
        latest_parts += [0] * (max_len - len(latest_parts))
        for c, l in zip(current_parts, latest_parts):
            if c < l:
                return -1
            elif c > l:
                return 1
        return 0

    def update_confirmed(self, result):
        if result:
            self.session.openWithCallback(
                self.update_complete,
                Console,
                _("Updating EmilPanelPro to version %s") % PLUGIN_VERSION,
                ["wget -O /tmp/Free-Panel.sh %s && chmod 755 /tmp/Free-Panel.sh && /tmp/Free-Panel.sh" % UPDATE_SCRIPT_URL]
            )

    def update_complete(self):
        self.session.openWithCallback(
            self.restart_gui,
            MessageBox,
            _("Update completed successfully!\nRestart GUI now?"),
            MessageBox.TYPE_YESNO
        )

    def restart_gui(self, result):
        if result:
            self.session.open(TryQuitMainloop, 3)

    def key_left(self):
        self.index = max(self.index - 1, 0)
        if self.index < self.minentry:
            self.ipage = max(self.ipage - 1, 1)
            self.openTest()
        else:
            self.paintFrame()

    def key_right(self):
        self.index = min(self.index + 1, self.npics - 1)
        if self.index > self.maxentry:
            self.ipage = min(self.ipage + 1, self.npage)
            self.openTest()
        else:
            self.paintFrame()

    def key_up(self):
        if self.index == 0 and self.ipage == 1:
            self.ipage = self.npage
            self.index = self.minentry
            self.openTest()
        elif self.index >= 5:
            self.index -= 5
            self.paintFrame()

    def key_down(self):
        if self.index <= self.maxentry - 5:
            self.index += 5
        else:
            self.ipage = 1 if self.ipage == self.npage else self.ipage + 1
            self.index = self.minentry
            self.openTest()
        self.paintFrame()

    def list_sort(self):
        if not hasattr(self, "original_data"):
            self.original_data = (self.names[:], self.titles[:], self.pics[:], self.urls[:])
            self.sorted = False

        if self.sorted:
            self.names, self.titles, self.pics, self.urls = self.original_data
            self["sort"].setText(_("Sort A-Z"))
        else:
            self.names, self.titles, self.pics, self.urls = ListSortUtility.list_sort(self.names, self.titles, self.pics, self.urls)
            self["sort"].setText(_("Sort Default"))
        self.sorted = not self.sorted
        self.openTest()

    def closeNonRecursive(self):
        self.close(False)

    def closeRecursive(self):
        self.close(True)

    def okbuttonClick(self):
        name = self.names[self.index]
        if name == "Panels":
            self.session.open(Panels)
        elif name == "Skins":
            self.session.open(SkinsPanel)
        elif name == "Plugins":
            self.session.open(PluginsPanel)
        elif name == "Tools":
            self.session.open(ToolsPanel)
        elif name == "Remove":
            self.session.open(RemovePanel)
        elif name == "SystemPlugins":
            self.session.open(SystemPluginsPanel)
        elif name == "Softcams":
            self.session.open(SoftcamsPanel)
        elif name == "BackupSettings":
            self.session.open(BackupSettingsPanels)
        elif name == "RestoreSettings":
            self.session.open(RestoreSettingsPanels)
        elif name == "Images":
            self.session.open(ImagesPanel)
        elif name == "Media":
            self.session.open(MediaPanel)
        elif name == "Feeds":
            self.session.open(FeedsPanels)
        elif name == "MultibootPlugins":
            self.session.open(MultibootPluginsPanel)
        elif name == "Picons":
            self.session.open(PiconsPanel)
        elif name == "Bootlogos":
            self.session.open(BootlogosPanel)
        elif name == "Channels":
            self.session.open(ChannelsPanel)

def main(session, **kwargs):
    global _session
    _session = session
    session.open(Free-Panel)

def menu(menuid, **kwargs):
    return [(_("Free-Panel"), main, descplug, 44)] if menuid == "mainmenu" else []

def Plugins(**kwargs):
    add_skin_fonts()
    return [
        PluginDescriptor(
            name="Free-Pnael",
            description=descplug,
            icon="EmilPanel.png",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            fnc=main
        ),
        PluginDescriptor(
            name="Free-Pnael",
            description=descplug,
            where=PluginDescriptor.WHERE_MENU,
            fnc=menu
        )
    ]
