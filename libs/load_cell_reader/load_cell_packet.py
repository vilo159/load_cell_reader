# Copyright (c) farm-ng, inc.
#
# Licensed under the Amiga Development Kit License (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/farm-ng/amiga-dev-kit/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import time
from enum import IntEnum
from struct import pack
from struct import unpack
from farm_ng.canbus import canbus_pb2
from farm_ng.core.stamp import timestamp_from_monotonic
from farm_ng.core.timestamp_pb2 import Timestamp

# TODO: add some comments about the CAN bus protocol
DASHBOARD_NODE_ID = 0xE
PENDANT_NODE_ID = 0xF
BRAIN_NODE_ID = 0x1F
SDK_NODE_ID = 0x2A


class Packet:
    """Base class inherited by all CAN message data structures."""

    @classmethod
    def from_can_data(cls, data, stamp: float):
        """Unpack CAN data directly into CAN message data structure."""
        obj = cls()  # Does not call __init__
        obj.decode(data)
        obj.stamp_packet(stamp)
        return obj

    def stamp_packet(self, stamp: float):
        """Time most recent message was received."""
        self.stamp: Timestamp = timestamp_from_monotonic("canbus/packet", stamp)

    def fresh(self, thresh_s: float = 0.5):
        """Returns False if the most recent message is older than ``thresh_s`` in seconds."""
        return self.age() < thresh_s

    def age(self):
        """Age of the most recent message."""
        return time.monotonic() - self.stamp.stamp

class LoadCellRpdo1(Packet):
    """Load Cell voltage and/or force?."""

    def __init__(self, meas_force: float = 0.0):
        self.format = "<d"
        self.meas_force = meas_force
        self.stamp(time.monotonic())

    def encode(self):
        """Returns the data contained by the class encoded as CAN message data."""
        return pack(self.format, self.meas_force)

    def decode(self, data):
        """Decodes CAN message data and populates the values of the class."""
        self.meas_force = unpack(self.format, data)[0]

    def __str__(self):
        return "LOAD CELL RPDO1 Force {:0.3f} @ time {}".format(self.meas_force, self.stamp.stamp) 

class LoadCellTpdo1(Packet):
    """Load Cell voltage and/or force?."""

    cob_id = 0x180

    def __init__(self, meas_force: float = 0.0):
        self.format = "<d" 
        self.meas_force = meas_force
        self.stamp_packet(time.monotonic())

    def encode(self):
        """Returns the data contained by the class encoded as CAN message data."""
        return pack(self.format, self.meas_force)

    def decode(self, data):
        """Decodes CAN message data and populates the values of the class."""
        self.meas_force = unpack(self.format, data)

    def __str__(self):
        return "LOAD CELL TPDO1 Force {:0.3f} @ time {}".format(self.meas_force, self.stamp.stamp) 


def parse_load_cell_tpdo1_proto(message: canbus_pb2.RawCanbusMessage) -> LoadCellTpdo1 | None: #TODO Annotate with message type?
    """Parses a canbus message from the Feather microcontroller.
    IFF the message came from the microcontrollerand contains LoadCellTx structure, formatting, and cobid.

    Args:
        message: The raw canbus message to parse.
    Returns:
        The parsed LoadcellTx message, or None if the message is not a valid LoadcellTx message.
    """
    # TODO: add some checkers, or make python CHECK_API
    # TODO: Need to add check for data type back in, right now it'll accept anything coming in ad might crash if the data type is wrong.
    if message.id != LoadCellTpdo1.cob_id + SDK_NODE_ID:
        return None
    return LoadCellTpdo1.from_can_data(message.data, stamp=message.stamp)
