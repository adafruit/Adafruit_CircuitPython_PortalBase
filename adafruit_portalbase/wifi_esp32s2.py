# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2021 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_portalbase.wifi_esp32s2`
================================================================================

WiFi Helper module for the ESP32-S2 based boards.


* Author(s): Melissa LeBlanc-Williams

Implementation Notes
--------------------

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""

import gc
import ssl
import wifi
import socketpool
import adafruit_requests

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_PortalBase.git"


class WiFi:
    """Class representing the WiFi portion of the ESP32-S2.

    :param status_led: The initialized object for status DotStar, NeoPixel, or RGB LED. Defaults
                       to ``None``, to not use the status LED

    """

    def __init__(self, *, status_led=None):
        if status_led:
            self.neopix = status_led
        else:
            self.neopix = None
        self.neo_status(0)
        self.requests = None
        self.pool = None
        self._connected = False

        gc.collect()

    def connect(self, ssid, password):
        """
        Connect to the WiFi Network using the information provided

        :param ssid: The WiFi name
        :param password: The WiFi password

        """
        wifi.radio.connect(ssid, password)
        self.pool = socketpool.SocketPool(wifi.radio)
        self.requests = adafruit_requests.Session(
            self.pool, ssl.create_default_context()
        )
        self._connected = True

    def neo_status(self, value):
        """The status DotStar.

        :param value: The color to change the DotStar.

        """
        if self.neopix:
            self.neopix.fill(value)

    @property
    def is_connected(self):
        """
        Return whether we have already connected since reconnections are handled automatically.

        """
        return self._connected

    @property
    def ip_address(self):
        """
        Return the IP Version 4 Address

        """
        return wifi.radio.ipv4_address

    @property
    def enabled(self):
        """
        Return whether the WiFi Radio is enabled

        """
        return wifi.radio.enabled
