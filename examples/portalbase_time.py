# SPDX-FileCopyrightText: 2025 Mikey Sklar for Adafruit Industries
#
# SPDX-License-Identifier: MIT

# Uncomment ONE board setup:

# --- PyPortal ---
# from adafruit_pyportal import PyPortal
# portal = PyPortal(status_neopixel=None)
# net = portal.network

# --- MatrixPortal M4 ---
# from adafruit_matrixportal.matrixportal import MatrixPortal
# portal = MatrixPortal(status_neopixel=None)
# net = portal.network

# --- MagTag (ESP32-S2 native WiFi) ---
# from adafruit_magtag.magtag import MagTag
# magtag = MagTag(status_neopixel=None)
# net = magtag.network

# --- Fruit Jam (wrap its WiFi) ---
from adafruit_fruitjam import FruitJam

jam = FruitJam(status_neopixel=None)
net = jam.network


# --- shared output ---
print(net.time_sync())
