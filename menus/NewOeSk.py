#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Free-Panel Plugin

# rewritten by Emi Nabil at 20250421
#

from __future__ import absolute_import
from __future__ import print_function
from os.path import isfile
from re import search
__author__ = "Emil"
__email__ = "zoka900zoka@yahoo.com"
__copyright__ = 'Copyright (c) 2025 tarek'
__license__ = "GPL-v2"
__version__ = "1.0.0"


def newOE():
	'''
	'''
	# 
	boo = False
	try:
		from enigma import PACKAGE_VERSION
		major, minor, patch = [int(n) for n in PACKAGE_VERSION.split('.')]
		if major > 4 or (major == 4 and minor >= 2):  
			boo = True  # 
	except Exception:
		pass
	try:
		from Components.SystemInfo import SystemInfo
		if 'MachineBrand' in SystemInfo.keys and 'TeamBlue' in SystemInfo['MachineBrand']:
			boo = False
	except Exception:
		pass
	try:
		from boxbranding import getOEVersion
		if getOEVersion().find('OE-Alliance') >= 0:
			boo = False
	except Exception:
		pass
	return boo


patterns_to_remove = [
	r'scrollbarWidth="[^"]*"',
	r'scrollbarSliderBorderWidth="[^"]*"',
	r'textoffsets\s*="[^"]*"',
	r'secondfont\s*="[^"]*"',
	r'scrollbarBorderWidth="[^"]*"',
	r'scrollbarForegroundColor="[^"]*"',
	r'scrollbarBorderColor="[^"]*"'
]

#
patterns_to_remove = [
	r'scrollbarWidth="[^"]*"',
	r'scrollbarSliderBorderWidth="[^"]*"',
	r'textoffsets\s*="[^"]*"',
	r'secondfont\s*="[^"]*"',
	r'scrollbarBorderWidth="[^"]*"',
	r'scrollbarForegroundColor="[^"]*"',
	r'scrollbarBorderColor="[^"]*"'
]


scrollbar_keywords_patterns = [
	r'scrollbarMode="list"',
	r'scrollbarMode="text"',
	r'scrollbarMode="menu"',
	r'scrollbarMode="config"',
	r'scrollbarMode="tasklist"',
	r'scrollbarMode="menulist"',
	r'scrollbarMode="menu_list"',
	r'scrollbarMode="filelist"',
	r'scrollbarMode="file_list"',
	r'scrollbarMode="entries"',
	r'scrollbarMode="Listbox"',
	r'scrollbarMode="list_left"',
	r'scrollbarMode="list_right"',
	r'scrollbarMode="streamlist"',
	r'scrollbarMode="tablist"',
	r'scrollbarMode="HelpScrollLabel"',
]


# 
def ctrlSkin(pank, skin):
	from re import sub
	print('ctrlSkin panel=%s' % pank)
	# 
	if newOE() or isfile('/etc/opkg/nn2-feed.conf') or isfile("/usr/bin/apt-get"):
		for pattern in patterns_to_remove:
			skin = sub(pattern, '', skin)
		# 
		for pattern in scrollbar_keywords_patterns:
			if search(pattern, skin):  # 
				skin = sub(r'font="[^"]*"', '', skin)  #
	else:
		print('No Skin modifications applied.')
	return skin

"""
# 
	# return skin
"""
