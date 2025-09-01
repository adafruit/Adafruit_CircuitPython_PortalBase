# SPDX-FileCopyrightText: 2025 Mikey Sklar for Adafruit Industries
#
# SPDX-License-Identifier: MIT

from adafruit_pyportal import PyPortal

portal = PyPortal(status_neopixel=None)
now = portal.network.time_sync()
print(now)
