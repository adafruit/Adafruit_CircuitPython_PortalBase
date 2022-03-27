# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

from setuptools import setup, find_packages

# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="adafruit-circuitpython-portalbase",
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    description="Base Library for the Portal-style libraries.",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    # The project's main homepage.
    url="https://github.com/adafruit/Adafruit_CircuitPython_PortalBase",
    # Author details
    author="Adafruit Industries",
    author_email="circuitpython@adafruit.com",
    install_requires=[
        "Adafruit-Blinka",
        "adafruit-blinka-displayio",
        "adafruit-circuitpython-bitmap-font",
        "adafruit-circuitpython-display-text",
        "adafruit-circuitpython-neopixel",
        "adafruit-circuitpython-requests",
        "adafruit-circuitpython-adafruitio",
        "adafruit-circuitpython-simpleio",
        "adafruit-circuitpython-fakerequests",
        "adafruit-circuitpython-miniqr",
    ],
    # Choose your license
    license="MIT",
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Topic :: System :: Hardware",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    # What does your project relate to?
    keywords="adafruit blinka circuitpython micropython portalbase PyPortal MatrixPortal "
    "MagTag Portal base",
    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=["adafruit_portalbase"],
)
