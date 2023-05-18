# Copyright (c) farm-ng, inc. Amiga Development Kit License, Version 0.1

#----------------------------------- Imports & Setup -----------------------------------
# System Imports
import argparse
import asyncio
import os
import datetime
import math
from typing import List
from typing import Optional

# Farm-Ng resources/ CAN Imports
import grpc
from farm_ng.canbus import canbus_pb2
from farm_ng.canbus.canbus_client import CanbusClient
from farm_ng.service import service_pb2
from farm_ng.service.service_client import ClientConfig
from load_cell_reader.load_cell_packet import LoadCellTpdo1
from load_cell_reader.load_cell_packet import parse_load_cell_tpdo1_proto

# Must come before kivy imports
os.environ["KIVY_NO_ARGS"] = "1"
# gui configs must go before any other kivy import
from kivy.config import Config  # noreorder # noqa: E402
Config.set("graphics", "resizable", False)
Config.set("graphics", "width", "1280")
Config.set("graphics", "height", "800")
Config.set("graphics", "fullscreen", "false")
Config.set("input", "mouse", "mouse,disable_on_activity")
Config.set("kivy", "keyboard_mode", "systemanddock")

# Kivy Imports
from kivy.app import App  # noqa: E402
from kivy.lang.builder import Builder  # noqa: E402
#from kivy.graphics.texture import Texture  # noqa: E402
from kivy.properties import StringProperty, NumericProperty  # noqa: E402
from kivy_garden.graph import MeshLinePlot # noqa: E402

# DARLING GranuStem Imports
from load_cell_reader.Datapoint import Datapoint
from load_cell_reader.BaseScreen import BaseScreen
from res.elements import *


#--------------------------------- Load Cell Class & Execution ---------------------------------

INTERVAL = .01
SECOND_CAP = 1/INTERVAL

class LoadCellApp(App, BaseScreen):
    """Base class for the main Kivy app."""

    # Kivy variables
    test_time = NumericProperty(0)
    x_max = NumericProperty(0)
    y_max = NumericProperty(0)
    x_major = NumericProperty(0)
    y_major = NumericProperty(0)

    def __init__(self, address: str, canbus_port: int, stream_every_n: int) -> None:
        super().__init__()
        self.address: str = address
        self.canbus_port: int = canbus_port
        self.stream_every_n: int = stream_every_n

        # Received values
        self.load_cell_tpdo1: LoadCellTpdo1 = LoadCellTpdo1()

        self.async_tasks: List[asyncio.Task] = []

        # Test Start/Stop
        self.test_started = False

        # Plotter Parameters
        self.meas_val: float = 0.0
        self.test_time = 0
        self.second_counter = 0
        self.double_counter = 0
        self.start_time = datetime.datetime.now()
        self.datapoints = []
        self.x_max= 5
        self.y_max= 5
        self.x_major = int(self.x_max/5)
        self.y_major = int(self.y_max/5)
        self.plot = MeshLinePlot(color=[1, 1, 1, 1])
        
    def find_max_meas_val(self):
        max = 0
        for datapoint in self.datapoints:
            if(datapoint.meas_val > max):
                max = datapoint.meas_val
        return max

    def build(self):
        return Builder.load_file("res/main.kv")

    def on_exit_btn(self) -> None:
        """Kills the running kivy application."""
        App.get_running_app().stop()

    def on_start_btn(self) -> None:
        """Starts the data collection."""
        self.test_started = True
        if self.datapoints == []:
            self.start_time = datetime.datetime.now()
        
    def on_stop_btn(self) -> None:
        """Stops the data collection."""
        self.test_started = False

    def on_reset_btn(self) -> None:
        """Resets the test parameters."""
        self.test_started = False
        self.datapoints = []
        self.test_time = 0
        self.start_time = datetime.datetime.now()
        self.second_counter = 0
        self.double_counter = 0
        self.graph.remove_plot(self.plot)
        self.graph._clear_buffer()

    async def app_func(self):
        async def run_wrapper() -> None:
            # we don't actually need to set asyncio as the lib because it is
            # the default, but it doesn't hurt to be explicit
            await self.async_run(async_lib="asyncio")
            for task in self.async_tasks:
                task.cancel()

        # configure the canbus client
        canbus_config: ClientConfig = ClientConfig(
            address=self.address, port=self.canbus_port
        )
        canbus_client: CanbusClient = CanbusClient(canbus_config)

        # Canbus task(s)For Kivy labels I guess? 
        self.async_tasks.append(
            asyncio.ensure_future(self.stream_canbus(canbus_client))
        )
        # self.async_tasks.append(
        #     asyncio.ensure_future(self.send_can_msgs(canbus_client))
        # )

        return await asyncio.gather(run_wrapper(), *self.async_tasks)

    async def stream_canbus(self, client: CanbusClient) -> None:
        """This task:

        - listens to the canbus client's stream
        - filters for LoadCellTpdo1 messages
        - extracts useful values from LoadCellTx messages
        """
        while self.root is None:
            await asyncio.sleep(0.01)

        response_stream = None

        while True:
            # check the state of the service
            state = await client.get_state()

            if state.value not in [
                service_pb2.ServiceState.IDLE,
                service_pb2.ServiceState.RUNNING,
            ]:
                if response_stream is not None:
                    response_stream.cancel()
                    response_stream = None

                print("Canbus service is not streaming or ready to stream")
                await asyncio.sleep(0.1)
                continue

            if (
                response_stream is None
                and state.value != service_pb2.ServiceState.UNAVAILABLE
            ):
                # get the streaming object
                response_stream = client.stream_raw()

            try:
                # try/except so app doesn't crash on killed service
                response: canbus_pb2.StreamCanbusReply = await response_stream.read()
                assert response and response != grpc.aio.EOF, "End of stream"
            except Exception as e:
                print(e)
                response_stream.cancel()
                response_stream = None
                continue

            for proto in response.messages.messages:
                load_cell_tpdo1: Optional[LoadCellTpdo1] = parse_load_cell_tpdo1_proto(proto)
                self.load_cell_tpdo1 = load_cell_tpdo1
                
                if self.test_started and load_cell_tpdo1:
                    # Update the Label values as they are received
                    # self.root.ids.force_label.text = (
                    #     f"{'Force from Load Cell'}: {str(load_cell_tpdo1.meas_val[0])}"
                    # )

                    # Update plot every XXX datapoints
                    self.second_counter += 1
                    time_delta = datetime.datetime.now() - self.start_time
                    total_time_passed = time_delta.seconds + (time_delta.microseconds * .000001)
                    self.test_time = time_delta.seconds
                    if self.second_counter >= SECOND_CAP/2:
                        self.double_counter += 1
                        self.second_counter = 0
                        self.graph = self.root.ids['graph_test']
                        self.graph.remove_plot(self.plot)
                        self.graph._clear_buffer()
                        self.plot = MeshLinePlot(color=[1, 1, 1, 1])
                        last_index = len(self.datapoints) - 1
                        self.x_max = math.ceil(self.datapoints[last_index].timestamp / 5) * 5
                        self.y_max = max(self.y_max, math.ceil(self.datapoints[last_index].meas_val / 5) * 5)

                        self.x_major = int(self.x_max/5)
                        self.y_major = int(self.y_max/5)

                        self.plot.points = [(self.datapoints[i].timestamp, self.datapoints[i].meas_val) for i in range(0, len(self.datapoints), 5)]
                        
                        self.graph.add_plot(self.plot)
                    
                    # Parse last value recieved
                    self.meas_val = load_cell_tpdo1.meas_val[0]
                    new_datapoint = Datapoint(total_time_passed, self.meas_val)
                    self.datapoints.append(new_datapoint)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="load_cell_reader_app")
    parser.add_argument(
        "--address", type=str, default="localhost", help="The server address"
    )
    parser.add_argument(
        "--canbus-port",
        type=int,
        required=True,
        help="The grpc port where the canbus service is running.",
    )
    parser.add_argument(
        "--stream-every-n",
        type=int,
        default=1,
        help="Streaming frequency (used to skip frames)",
    )
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(LoadCellApp(args.address, args.canbus_port, args.stream_every_n).app_func())
    except asyncio.CancelledError:
        pass
    loop.close()
