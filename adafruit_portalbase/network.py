# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_portalbase.network`
================================================================================

Base Library for the Portal-style libraries.


* Author(s): Melissa LeBlanc-Williams

Implementation Notes
--------------------

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""

import gc
import os
import time
import warnings

from adafruit_fakerequests import Fake_Requests
from adafruit_io.adafruit_io import IO_HTTP, AdafruitIO_RequestError
from micropython import const

try:
    import rtc
except ImportError:
    rtc = None

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_PortalBase.git"

# you'll need to pass in an io username and key
TIME_SERVICE = "https://io.adafruit.com/api/v2/%s/integrations/time/strftime?x-aio-key=%s"
# our strftime is %Y-%m-%d %H:%M:%S.%L %j %u %z %Z see http://strftime.net/ for decoding details
# See https://apidock.com/ruby/DateTime/strftime for full options
TIME_SERVICE_FORMAT = "%Y-%m-%d %H:%M:%S.%L %j %u %z %Z"
LOCALFILE = "local.txt"

STATUS_NO_CONNECTION = (100, 0, 0)  # Red
STATUS_CONNECTING = (0, 0, 100)  # Blue
STATUS_FETCHING = (150, 100, 0)  # Orange
STATUS_DOWNLOADING = (0, 100, 100)  # Cyan
STATUS_CONNECTED = (0, 0, 100)  # Blue
STATUS_DATA_RECEIVED = (0, 100, 0)  # Green
STATUS_HTTP_ERROR = (100, 0, 0)  # Red
STATUS_OFF = (0, 0, 0)  # Off

CONTENT_TEXT = const(1)
CONTENT_JSON = const(2)
CONTENT_IMAGE = const(3)

OLD_SECRETS = {
    "ADAFRUIT_AIO_KEY": "aio_key",
    "ADAFRUIT_AIO_USERNAME": "aio_username",
    "AIO_KEY": "aio_key",
    "AIO_USERNAME": "aio_username",
    "CIRCUITPY_WIFI_SSID": "ssid",
    "CIRCUITPY_WIFI_PASSWORD": "password",
}

OLD_SETTINGS = {
    "ADAFRUIT_AIO_KEY": "AIO_KEY",
    "ADAFRUIT_AIO_USERNAME": "AIO_USERNAME",
}


class HttpError(Exception):
    """HTTP Specific Error"""

    def __init__(self, message="", response=None):
        if message != "":
            super().__init__(message)
        else:
            super().__init__()
        self.response = response


class NetworkBase:
    """Network Base Class for the Portal-style libraries.

    :param wifi_module: An initialized WiFi Module that encapsulates the WiFi communications
    :param bool extract_values: If true, single-length fetched values are automatically extracted
                                from lists and tuples. Defaults to ``True``.
    :param debug: Turn on debug print outs. Defaults to False.

    """

    def __init__(  # noqa: PLR0912,PLR0913 Too many branches,Too many arguments in function definition
        self, wifi_module, *, extract_values=True, debug=False
    ):
        self._wifi = wifi_module
        self._debug = debug
        self.json_transform = []
        self._extract_values = extract_values
        self._json_types = [
            "application/json",
            "application/javascript",
            "application/geo+json",
        ]

        self._settings = {}
        self._wifi_credentials = None

        self.requests = None

        try:
            os.stat(LOCALFILE)
            self.uselocal = True
        except OSError:
            self.uselocal = False

        self._io_client = None

        gc.collect()

    def _get_setting(self, setting_name):
        # if setting is has already been found, return it
        if setting_name in self._settings:
            return self._settings[setting_name]

        # if setting is in settings.toml return it
        env_value = os.getenv(setting_name)
        if env_value is not None:
            self._settings[setting_name] = env_value
            return env_value

        # if setting old name is in settings.toml return it
        if setting_name in OLD_SETTINGS:
            old_setting_name = OLD_SETTINGS.get(setting_name)
            env_value = os.getenv(old_setting_name)
            if env_value is not None:
                self._settings[setting_name] = env_value
                return env_value

        try:
            from secrets import secrets
        except ImportError:
            return None

        # if setting is in legacy secrets.py return it
        secrets_setting_name = setting_name
        if setting_name in OLD_SECRETS:
            # translate common names
            secrets_setting_name = OLD_SECRETS.get(setting_name)
        env_value = secrets.get(secrets_setting_name)
        if env_value is not None:
            warnings.warn(
                "Using secrets.py for network settings is deprecated."
                " Put your settings in settings.toml."
            )
            self._settings[setting_name] = env_value
            return env_value

        return None

    def neo_status(self, value):
        """The status NeoPixel.

        :param value: The color to change the NeoPixel.

        """
        self._wifi.neo_status(value)

    @staticmethod
    def json_traverse(json, path):
        """
        Traverse down the specified JSON path and return the value or values

        :param json: JSON data to traverse
        :param list path: The path that we want to follow

        """
        value = json
        if not isinstance(path, (list, tuple)):
            raise ValueError("The json_path parameter should be enclosed in a list or tuple.")
        for x in path:
            try:
                value = value[x]
            except (TypeError, KeyError, IndexError) as error:
                raise ValueError("The specified json_path was not found in the results.") from error
            gc.collect()
        return value

    def add_json_transform(self, json_transform):
        """Add a function that is applied to JSON data when data is fetched

        :param json_transform: A function or a list of functions to call with the parsed JSON.
                               Changes and additions are permitted for the ``dict`` object.
        """
        if callable(json_transform):
            self.json_transform.append(json_transform)
        else:
            self.json_transform.extend(filter(callable, json_transform))

    @staticmethod
    def url_encode(url):
        """
        A function to perform minimal URL encoding
        """
        return url.replace(" ", "+").replace("%", "%25").replace(":", "%3A")

    def get_strftime(self, time_format, location=None, max_attempts=10):
        """
        Fetch a custom strftime relative to your location.

        :param str location: Your city and country, e.g. ``"America/New_York"``.
        :param max_attempts: The maximum number of attempts to connect to WiFi before
                             failing or use None to disable. Defaults to 10.

        """
        self.connect(max_attempts=max_attempts)
        api_url = None
        reply = None
        try:
            aio_username = self._get_setting("ADAFRUIT_AIO_USERNAME")
            aio_key = self._get_setting("ADAFRUIT_AIO_KEY")
        except KeyError:
            raise KeyError(
                "\nThe Adafruit IO time service requires a login and password. "
                "Rgister for a free adafruit.io account and put the username and key in "
                "your settings.toml file under 'ADAFRUIT_AIO_USERNAME' and 'ADAFRUIT_AIO_KEY'"
            ) from KeyError

        if location is None:
            location = self._get_setting("timezone")
        if location:
            print("Getting time for timezone", location)
            api_url = (TIME_SERVICE + "&tz=%s") % (aio_username, aio_key, location)
        else:  # we'll try to figure it out from the IP address
            print("Getting time from IP address")
            api_url = TIME_SERVICE % (aio_username, aio_key)
        api_url += "&fmt=" + self.url_encode(time_format)

        try:
            self.neo_status(STATUS_FETCHING)
            response = self._wifi.requests.get(api_url, timeout=10)
            self.neo_status(STATUS_DATA_RECEIVED)
            if response.status_code != 200:
                print(response)
                error_message = (
                    "Error connecting to Adafruit IO. The response was: " + response.text
                )
                self.neo_status(STATUS_HTTP_ERROR)
                raise RuntimeError(error_message)
            if self._debug:
                print("Time request: ", api_url)
                print("Time reply: ", response.text)
            reply = response.text
        except KeyError:
            raise KeyError(
                "Unable to lookup the time, try setting 'timezone' in your settings.toml"
                "according to http://worldtimeapi.org/timezones"
            ) from KeyError
        # now clean up
        response.close()
        response = None
        gc.collect()

        return reply

    def get_local_time(self, location=None, max_attempts=10):
        """
        Fetch and "set" the local time of this microcontroller to the local time at the location,
        using an internet time API.

        :param str location: Your city and country, e.g. ``"America/New_York"``.
        :param max_attempts: The maximum number of attempts to connect to WiFi before
                             failing or use None to disable. Defaults to 10.

        """
        reply = self.get_strftime(TIME_SERVICE_FORMAT, location=location, max_attempts=max_attempts)
        if reply:
            times = reply.split(" ")
            the_date = times[0]
            the_time = times[1]
            year_day = int(times[2])
            week_day = int(times[3])
            is_dst = None  # no way to know yet
            year, month, mday = (int(x) for x in the_date.split("-"))
            the_time = the_time.split(".")[0]
            hours, minutes, seconds = (int(x) for x in the_time.split(":"))
            now = time.struct_time(
                (year, month, mday, hours, minutes, seconds, week_day, year_day, is_dst)
            )

            if rtc is not None:
                rtc.RTC().datetime = now

        return reply

    def wget(self, url, filename, *, chunk_size=12000, headers=None):
        """Download a url and save to filename location, like the command wget.

        :param url: The URL from which to obtain the data.
        :param filename: The name of the file to save the data to.
        :param chunk_size: how much data to read/write at a time.
        :param headers: a dict of headers to send along in the request.

        """
        print("Fetching stream from", url)

        self.neo_status(STATUS_FETCHING)
        response = self._wifi.requests.get(url, headers=headers, stream=True)

        # we re-use this variable, now dealing with response headers
        headers = {}
        for title, content in response.headers.items():
            headers[title.lower()] = content

        if response.status_code == 200:
            print("Reply is OK!")
            self.neo_status((0, 0, 100))  # green = got data
        else:
            if self._debug:
                if "content-length" in headers:
                    print("Content-Length: {}".format(int(headers["content-length"])))
                if "date" in headers:
                    print("Date: {}".format(headers["date"]))
            self.neo_status(STATUS_HTTP_ERROR)  # red = http error
            raise HttpError(
                "Code {}: {}".format(response.status_code, response.reason.decode("utf-8")),
                response,
            )

        if self._debug:
            print(response.headers)
        if "content-length" in headers:
            content_length = int(headers["content-length"])
        else:
            raise RuntimeError("Content-Length missing from headers")
        remaining = content_length
        print("Saving data to ", filename)
        stamp = time.monotonic()
        with open(filename, "wb") as file:
            for i in response.iter_content(min(remaining, chunk_size)):  # huge chunks!
                self.neo_status(STATUS_DOWNLOADING)
                remaining -= len(i)
                file.write(i)
                if self._debug:
                    print("Read %d bytes, %d remaining" % (content_length - remaining, remaining))
                else:
                    print(".", end="")
                if not remaining:
                    break
                self.neo_status(STATUS_FETCHING)

        response.close()
        stamp = time.monotonic() - stamp
        print("Created file of %d bytes in %0.1f seconds" % (os.stat(filename)[6], stamp))
        self.neo_status(STATUS_OFF)
        if not content_length == os.stat(filename)[6]:
            raise RuntimeError

    def connect(self, max_attempts=10):
        """
        Connect to WiFi using the settings found in settings.toml

        :param max_attempts: The maximum number of attempts to connect to WiFi before
                             failing or use None to disable. Defaults to 10.

        """

        if not self._wifi_credentials:
            self._wifi_credentials = [
                {
                    "ssid": self._get_setting("CIRCUITPY_WIFI_SSID"),
                    "password": self._get_setting("CIRCUITPY_WIFI_PASSWORD"),
                }
            ]

            networks = self._get_setting("networks")
            if networks is not None:
                if isinstance(networks, (list, tuple)):
                    self._wifi_credentials = networks
                else:
                    raise TypeError(
                        "'networks' must be a list/tuple of dicts of 'ssid' and 'password'"
                    )

        for credentials in self._wifi_credentials:
            self._wifi.neo_status(STATUS_CONNECTING)
            attempt = 1

            while not self._wifi.is_connected:
                # credentials must contain 'CIRCUITPY_WIFI_SSID' and 'CIRCUITPY_WIFI_PASSWORD'
                print("Connecting to AP", credentials["ssid"])
                if credentials["ssid"] == "CHANGE ME" or credentials["password"] == "CHANGE ME":
                    change_me = "\n" + "*" * 45
                    change_me += "\nPlease update the 'settings.toml' file on your\n"
                    change_me += "CIRCUITPY drive to include your local WiFi\n"
                    change_me += "access point SSID name in 'CIRCUITPY_WIFI_SSID' and SSID\n"
                    change_me += "password in 'CIRCUITPY_WIFI_PASSWORD'. Then save to reload!\n"
                    change_me += "*" * 45
                    raise OSError(change_me)
                self._wifi.neo_status(STATUS_NO_CONNECTION)  # red = not connected
                try:
                    self._wifi.connect(credentials["ssid"], credentials["password"])
                    self.requests = self._wifi.requests
                    self._wifi.neo_status(STATUS_CONNECTED)
                    break
                except (RuntimeError, ConnectionError) as error:
                    if max_attempts is not None and attempt >= max_attempts:
                        break
                    print("Could not connect to internet", error)
                    print("Retrying in 3 seconds...")
                    attempt += 1
                    time.sleep(3)
                gc.collect()

            if self._wifi.is_connected:
                return

        raise OSError("Maximum number of attempts reached when trying to connect to WiFi")

    def _get_io_client(self):
        if self._io_client is not None:
            return self._io_client

        self.connect()

        try:
            aio_username = self._get_setting("ADAFRUIT_AIO_USERNAME")
            aio_key = self._get_setting("ADAFRUIT_AIO_KEY")
        except KeyError:
            raise KeyError(
                "Adafruit IO settings are kept in settings.toml, please add them there!\n\n"
            ) from KeyError

        self._io_client = IO_HTTP(aio_username, aio_key, self._wifi.requests)
        return self._io_client

    def push_to_io(self, feed_key, data, metadata=None, precision=None):
        """Push data to an adafruit.io feed

        :param str feed_key: Name of feed key to push data to.
        :param data: data to send to feed
        :param dict metadata: Optional metadata associated with the data
        :param int precision: Optional amount of precision points to send with floating point data

        """

        io_client = self._get_io_client()

        while True:
            try:
                feed_id = io_client.get_feed(feed_key)
            except AdafruitIO_RequestError:
                # If no feed exists, create one
                feed_id = io_client.create_new_feed(feed_key)
            except RuntimeError as exception:
                print("An error occured, retrying! 1 -", exception)
                continue
            break

        while True:
            try:
                io_client.send_data(feed_id["key"], data, metadata, precision)
            except RuntimeError as exception:
                print("An error occured, retrying! 2 -", exception)
                continue
            except NameError as exception:
                print(feed_id["key"], data, exception)
                continue
            break

    def get_io_feed(self, feed_key, detailed=False):
        """Return the Adafruit IO Feed that matches the feed key

        :param str feed_key: Name of feed key to match.
        :param bool detailed: Whether to return additional detailed information

        """
        io_client = self._get_io_client()

        while True:
            try:
                return io_client.get_feed(feed_key, detailed=detailed)
            except RuntimeError as exception:
                print("An error occured, retrying! 1 -", exception)
                continue

    def get_io_group(self, group_key):
        """Return the Adafruit IO Group that matches the group key

        :param str group_key: Name of group key to match.

        """
        io_client = self._get_io_client()

        while True:
            try:
                return io_client.get_group(group_key)
            except RuntimeError as exception:
                print("An error occured, retrying! 1 -", exception)
                continue

    def get_io_data(self, feed_key):
        """Return all values from Adafruit IO Feed Data that matches the feed key

        :param str feed_key: Name of feed key to receive data from.

        """
        io_client = self._get_io_client()

        while True:
            try:
                return io_client.receive_all_data(feed_key)
            except RuntimeError as exception:
                print("An error occured, retrying! 1 -", exception)
                continue

    def delete_io_data(self, feed_key: str, data_id: str):
        """Return all values from Adafruit IO Feed Data that matches the feed key

        :param str feed_key: Name of feed key to receive data from.

        """
        io_client = self._get_io_client()

        while True:
            try:
                return io_client.delete_data(feed_key, data_id)
            except RuntimeError as exception:
                print("An error occured, retrying! 1 -", exception)
                continue

    def fetch(self, url, *, headers=None, timeout=10):
        """Fetch data from the specified url and return a response object

        :param str url: The URL to fetch from.
        :param dict headers: Extra headers to include in the request.
        :param int timeout: The timeout period in seconds.

        """
        gc.collect()

        response = None
        if self.uselocal:
            print("*** USING LOCALFILE FOR DATA - NOT INTERNET!!! ***")
            response = Fake_Requests(LOCALFILE)

        if not response:
            self.connect()
            # great, lets get the data
            print("Retrieving data...", end="")
            self.neo_status(STATUS_FETCHING)  # yellow = fetching data
            gc.collect()
            response = self._wifi.requests.get(url, headers=headers, timeout=timeout)
            gc.collect()

        return response

    def add_json_content_type(self, content_type):
        """
        Add a JSON content type

        :param str type: The content JSON type like 'application/json'

        """
        if isinstance(content_type, str):
            self._json_types.append(content_type)

    def _detect_content_type(self, headers):
        if "content-type" in headers:
            if "image/" in headers["content-type"]:
                return CONTENT_IMAGE
            for json_type in self._json_types:
                if json_type in headers["content-type"]:
                    return CONTENT_JSON
        return CONTENT_TEXT

    def check_response(self, response):
        """
        Check the response object status code, change the lights, and return content type

        :param response: The response object from a network call

        """
        headers = self._get_headers(response)

        if self._debug:
            print("Headers:", headers)
        if response.status_code == 200:
            print("Reply is OK!")
            self.neo_status(STATUS_DATA_RECEIVED)  # green = got data
            content_type = self._detect_content_type(headers)
        else:
            if self._debug:
                if "content-length" in headers:
                    print("Content-Length: {}".format(int(headers["content-length"])))
                if "date" in headers:
                    print("Date: {}".format(headers["date"]))
            self.neo_status((100, 0, 0))  # red = http error
            raise HttpError(
                "Code {}: {}".format(response.status_code, response.reason.decode("utf-8")),
                response,
            )

        return content_type

    @staticmethod
    def _get_headers(response):
        headers = {}
        for title, content in response.headers.items():
            headers[title.lower()] = content
        gc.collect()
        return headers

    def fetch_data(  # noqa: PLR0913 Too many arguments in function definition
        self,
        url,
        *,
        headers=None,
        json_path=None,
        regexp_path=None,
        timeout=10,
    ):
        """Fetch data from the specified url and perfom any parsing

        :param str url: The URL to fetch from.
        :param dict headers: Extra headers to include in the request.
        :param json_path: The path to drill down into the JSON data.
        :param regexp_path: The path formatted as a regular expression to search
                            the text data.
        :param int timeout: The timeout period in seconds.

        """
        response = self.fetch(url, headers=headers, timeout=timeout)
        return self._parse_data(response, json_path=json_path, regexp_path=regexp_path)

    def _parse_data(
        self,
        response,
        *,
        json_path=None,
        regexp_path=None,
    ):
        json_out = None
        content_type = self.check_response(response)

        if content_type == CONTENT_JSON:
            if json_path is not None:
                # Drill down to the json path and set json_out as that node
                if isinstance(json_path, (list, tuple)) and (
                    not json_path or not isinstance(json_path[0], (list, tuple))
                ):
                    json_path = (json_path,)
            try:
                gc.collect()
                json_out = response.json()
                if self._debug:
                    print(json_out)
                gc.collect()
            except ValueError:  # failed to parse?
                print("Couldn't parse json: ", response.text)
                raise
            except MemoryError as error:
                raise MemoryError(f"{error} (data is likely too large)") from error

        if content_type == CONTENT_JSON:
            values = self.process_json(json_out, json_path)
        elif content_type == CONTENT_TEXT:
            values = self.process_text(response.text, regexp_path)

        # Clean up
        json_out = None
        response = None
        if self._extract_values and len(values) == 1:
            values = values[0]

        gc.collect()

        return values

    @staticmethod
    def process_text(text, regexp_path):
        """
        Process text content

        :param str text: The entire text content
        :param regexp_path: The path formatted as a regular expression to search
                            the text data.

        """
        values = []
        if regexp_path:
            import re

            for regexp in regexp_path:
                values.append(re.search(regexp, text).group(1))
        else:
            values.append(text)
        return values

    def process_json(self, json_data, json_path):
        """
        Process JSON content

        :param dict json_data: The JSON data as a dict
        :param json_path: The path to drill down into the JSON data.

        """
        values = []

        # optional JSON post processing, apply any transformations
        # these MAY change/add element
        for idx, json_transform in enumerate(self.json_transform):
            try:
                json_transform(json_data)
            except Exception as error:
                print("Exception from json_transform: ", idx, error)
                raise

        # extract desired text/values from json
        if json_data is not None and json_path:
            for path in json_path:
                try:
                    values.append(self.json_traverse(json_data, path))
                except KeyError:
                    print(json_data)
                    raise
        else:
            # No path given, so return JSON as string for compatibility
            import json

            values = json.dumps(json_data)
        return values

    @property
    def is_connected(self):
        """Return whether we are connected."""
        return self._wifi.is_connected

    @property
    def io_client(self):
        """Return the Adafruit IO Client."""
        return self._get_io_client()
