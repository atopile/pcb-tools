#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2015 Garret Fick <garret@ficksworkshop.com>

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Excellon Tool Definition File module
====================
**Excellon file classes**

This module provides Excellon file classes and parsing utilities
"""

import re

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

from .excellon_statements import ExcellonTool


def loads(data, settings=None):
    """Read tool file information and return a map of tools
    Parameters
    ----------
    data : string
        string containing Excellon Tool Definition file contents

    Returns
    -------
    dict tool name: ExcellonTool

    """
    return ExcellonToolDefinitionParser(settings).parse_raw(data)


class ExcellonToolDefinitionParser(object):
    """Excellon File Parser

    Parameters
    ----------
    None
    """

    allegro_tool = re.compile(
        r"(?P<size>[0-9/.]+)\s+(?P<plated>P|N)\s+T(?P<toolid>[0-9]{2})\s+(?P<xtol>[0-9/.]+)\s+(?P<ytol>[0-9/.]+)"
    )
    allegro_comment_mils = re.compile(
        "Holesize (?P<toolid>[0-9]{1,2})\. = (?P<size>[0-9/.]+) Tolerance = \+(?P<xtol>[0-9/.]+)/-(?P<ytol>[0-9/.]+) (?P<plated>(PLATED)|(NON_PLATED)|(OPTIONAL)) MILS Quantity = [0-9]+"
    )
    allegro2_comment_mils = re.compile(
        "T(?P<toolid>[0-9]{1,2}) Holesize (?P<toolid2>[0-9]{1,2})\. = (?P<size>[0-9/.]+) Tolerance = \+(?P<xtol>[0-9/.]+)/-(?P<ytol>[0-9/.]+) (?P<plated>(PLATED)|(NON_PLATED)|(OPTIONAL)) MILS Quantity = [0-9]+"
    )
    allegro_comment_mm = re.compile(
        "Holesize (?P<toolid>[0-9]{1,2})\. = (?P<size>[0-9/.]+) Tolerance = \+(?P<xtol>[0-9/.]+)/-(?P<ytol>[0-9/.]+) (?P<plated>(PLATED)|(NON_PLATED)|(OPTIONAL)) MM Quantity = [0-9]+"
    )
    allegro2_comment_mm = re.compile(
        "T(?P<toolid>[0-9]{1,2}) Holesize (?P<toolid2>[0-9]{1,2})\. = (?P<size>[0-9/.]+) Tolerance = \+(?P<xtol>[0-9/.]+)/-(?P<ytol>[0-9/.]+) (?P<plated>(PLATED)|(NON_PLATED)|(OPTIONAL)) MM Quantity = [0-9]+"
    )

    matchers = [
        (allegro_tool, "mils"),
        (allegro_comment_mils, "mils"),
        (allegro2_comment_mils, "mils"),
        (allegro_comment_mm, "mm"),
        (allegro2_comment_mm, "mm"),
    ]

    def __init__(self, settings=None) -> None:
        self.tools = {}
        self.settings = settings

    def parse_raw(self, data):
        for line in StringIO(data):
            self._parse(line.strip())

        return self.tools

    def _parse(self, line) -> None:

        for matcher in ExcellonToolDefinitionParser.matchers:
            m = matcher[0].match(line)
            if m:
                unit = matcher[1]

                size = float(m.group("size"))
                platedstr = m.group("plated")
                toolid = int(m.group("toolid"))
                xtol = float(m.group("xtol"))
                ytol = float(m.group("ytol"))

                size = self._convert_length(size, unit)
                xtol = self._convert_length(xtol, unit)
                ytol = self._convert_length(ytol, unit)

                if platedstr == "PLATED":
                    plated = ExcellonTool.PLATED_YES
                elif platedstr == "NON_PLATED":
                    plated = ExcellonTool.PLATED_NO
                elif platedstr == "OPTIONAL":
                    plated = ExcellonTool.PLATED_OPTIONAL
                else:
                    plated = ExcellonTool.PLATED_UNKNOWN

                tool = ExcellonTool(None, number=toolid, diameter=size, plated=plated)

                self.tools[tool.number] = tool

                break

    def _convert_length(self, value, unit):

        # Convert the value to mm
        if unit == "mils":
            value /= 39.3700787402

        # Now convert to the settings unit
        if self.settings.units == "inch":
            return value / 25.4
        else:
            # Already in mm
            return value


def loads_rep(data, settings=None):
    """Read tool report information generated by PADS and return a map of tools
    Parameters
    ----------
    data : string
        string containing Excellon Report file contents

    Returns
    -------
    dict tool name: ExcellonTool

    """
    return ExcellonReportParser(settings).parse_raw(data)


class ExcellonReportParser(object):

    # We sometimes get files with different encoding, so we can't actually
    # match the text - the best we can do it detect the table header
    header = re.compile(r"====\s+====\s+====\s+====\s+=====\s+===")

    def __init__(self, settings=None) -> None:
        self.tools = {}
        self.settings = settings

        self.found_header = False

    def parse_raw(self, data):
        for line in StringIO(data):
            self._parse(line.strip())

        return self.tools

    def _parse(self, line) -> None:

        # skip empty lines and "comments"
        if not line.strip():
            return

        if not self.found_header:
            # Try to find the heaader, since we need that to  be sure we
            # understand the contents correctly.
            if ExcellonReportParser.header.match(line):
                self.found_header = True

        elif line[0] != "=":
            # Already found the header, so we know to to map the contents
            parts = line.split()
            if len(parts) == 6:
                toolid = int(parts[0])
                size = float(parts[1])
                if parts[2] == "x":
                    plated = ExcellonTool.PLATED_YES
                elif parts[2] == "-":
                    plated = ExcellonTool.PLATED_NO
                else:
                    plated = ExcellonTool.PLATED_UNKNOWN
                feedrate = int(parts[3])
                speed = int(parts[4])
                int(parts[5])

                tool = ExcellonTool(
                    None,
                    number=toolid,
                    diameter=size,
                    plated=plated,
                    feed_rate=feedrate,
                    rpm=speed,
                )

                self.tools[tool.number] = tool
