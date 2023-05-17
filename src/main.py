# Copyright (c) farm-ng, inc. Amiga Development Kit License, Version 0.1
import argparse
import asyncio
import os
from typing import List
from typing import Optional

import grpc
from farm_ng.canbus import canbus_pb2
from farm_ng.canbus.canbus_client import CanbusClient
from load_cell_reader.load_cell_packet import LoadCellTpdo1
from load_cell_reader.load_cell_packet import parse_load_cell_tpdo1_proto

#Not sure if I need these yet
from farm_ng.service import service_pb2
from farm_ng.service.service_client import ClientConfig

# import internal libs

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

# kivy imports
from kivy.app import App  # noqa: E402
from kivy.lang.builder import Builder  # noqa: E402
from kivy.graphics.texture import Texture  # noqa: E402
from kivy.properties import StringProperty  # noqa: E402


class LoadCellApp(App):
    """Base class for the main Kivy app."""

    # For Kivy labels I guess? 
    load_cell_force = StringProperty("???")

    def __init__(self, address: str, canbus_port: int, stream_every_n: int) -> None:
        super().__init__()
        self.address: str = address
        self.canbus_port: int = canbus_port
        self.stream_every_n: int = stream_every_n

        # Received values
        self.load_cell_tx: LoadCellTpdo1 = LoadCellTpdo1()

        # Parameters
        self.meas_force: float = 0.0

        self.async_tasks: List[asyncio.Task] = []

    def build(self):
        return Builder.load_file("res/main.kv")

    def on_exit_btn(self) -> None:
        """Kills the running kivy application."""
        App.get_running_app().stop()

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

        # Canbus task(s)
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
                if load_cell_tpdo1:
                    # Store the value for possible other uses
                    #self.load_cell_tpdo1 = load_cell_tpdo1

                    # Update the Label values as they are received
                    self.load_cell_force = load_cell_tpdo1.meas_force
                    self.root.ids.force_label.text = (
                        f"{'Force from Load Cell'}: {self.load_cell_force}"
                    )


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
