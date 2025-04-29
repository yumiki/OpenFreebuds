import asyncio
import platform
import socket
from contextlib import suppress

from openfreebuds.driver.generic import OfbDriverGeneric
from openfreebuds.exceptions import FbStartupError
from openfreebuds.utils.logger import create_logger

log = create_logger("OfbDriverSppGeneric")


class OfbDriverSppGeneric(OfbDriverGeneric):
    def __init__(self, address):
        super().__init__(address)
        self.__task_recv: asyncio.Task | None = None

        self._spp_service_port: int = 16
        self._spp_connect_delay: int = 0
        self._writer: asyncio.StreamWriter | None = None

    async def get_health_report(self):
        return {
            **(await super().get_health_report()),
            "recv_task_alive": not self.__task_recv.done(),
        }

    async def start(self):
        if platform.system() == "Darwin":  # macOS
            await self._start_macos()
        else:  # Linux, Windows
            await self._start_standard()
        self.started = True
        log.info("Started")

    async def _start_standard(self):
        try:
            sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            sock.settimeout(2)
            await asyncio.sleep(self._spp_connect_delay)

            sock.connect((self.device_address, self._spp_service_port))
            reader, writer = await asyncio.open_connection(sock=sock)
        except (ConnectionResetError, ConnectionRefusedError, ConnectionAbortedError, OSError, ValueError):
            raise FbStartupError("Driver startup failed")

        self.__task_recv = asyncio.create_task(self._loop_recv(reader))
        self._writer = writer
        self.started = True
        log.info("Started")

    async def _start_macos(self):
        try:
            import objc
            from CoreBluetooth import CBCentralManager
            from openfreebuds_backend.macos.macos_bt import BluetoothManager, bt_connect, bt_is_connected, PYOBJC_AVAILABLE
            from openfreebuds_backend.exception import OfbBackendDependencyMissingError, BackendException
        except ImportError:
            PYOBJC_AVAILABLE = False
        
        if not PYOBJC_AVAILABLE:
            raise OfbBackendDependencyMissingError("PyObjC is required for macOS Bluetooth support", 
                                                   "pip install pyobjc-framework-CoreBluetooth")
        
        log.info(f"Connecting to device: {self.device_address}")
        
        try:
            # Initialize the Bluetooth manager
            self.bt_manager = BluetoothManager.alloc().init()
            
            # Wait until the Bluetooth manager is powered on
            while not self.bt_manager.is_powered_on:
                await asyncio.sleep(0.1)
            
            # Connect to the device using its MAC address
            await asyncio.sleep(self._spp_connect_delay)
            
            # Format the MAC address if needed
            formatted_address = self.device_address
            if ':' not in formatted_address and len(formatted_address) == 12:
                formatted_address = ':'.join(formatted_address[i:i+2] for i in range(0, 12, 2)).upper()
            
            # Check if the device is already connected before attempting to connect
            is_connected = await bt_is_connected(self.device_address)
            log.info(f"Device connection status: {'Connected' if is_connected else 'Disconnected'}")
            
            # Only attempt to connect if not already connected
            if not is_connected:
                log.info(f"Attempting to connect to device: {formatted_address}")
                success = await bt_connect(formatted_address)
                if not success:
                    raise FbStartupError(f"Failed to connect to device: {formatted_address}")
                log.info(f"Successfully connected to {formatted_address}")
            else:
                log.info(f"Device {formatted_address} is already connected, skipping connection step")
            
            # Create a virtual reader/writer pair for communication
            # This is a placeholder - actual implementation would depend on how
            # data is exchanged with the device on macOS
            reader, writer = await self._create_macos_io_streams(formatted_address)
            
            # Set up the receive task
            self.__task_recv = asyncio.create_task(self._loop_recv(reader))
            self._writer = writer
            
            log.info(f"Successfully connected to {formatted_address}")
            
        except (BackendException, Exception) as e:
            log.error(f"Connection error: {str(e)}")
            raise FbStartupError(f"Driver startup failed: {str(e)}")
    async def _create_macos_io_streams(self, device_address):
        """
        Create reader and writer streams for macOS Bluetooth communication.
        
        This is a placeholder implementation. The actual implementation would depend
        on how data is exchanged with the device on macOS.
        """
        # This is where you would implement the actual communication channel
        # with the Bluetooth device on macOS.
        # 
        # Options might include:
        # 1. Using IOBluetooth framework to create an RFCOMM channel
        # 2. Using CoreBluetooth to communicate via GATT characteristics
        # 3. Creating a custom protocol adapter
        
        # For now, we'll create a mock implementation that can be replaced later
        class MacOSBluetoothReader:
            async def read(self, n=-1):
                # Placeholder for actual read implementation
                await asyncio.sleep(1)
                return b''
                
            async def readuntil(self, separator=b'\n'):
                # Placeholder for actual readuntil implementation
                await asyncio.sleep(1)
                return b''
        
        class MacOSBluetoothWriter:
            def write(self, data):
                # Placeholder for actual write implementation
                log.debug(f"Would write to device {device_address}: {data}")
                return len(data)
                
            async def drain(self):
                # Placeholder for actual drain implementation
                await asyncio.sleep(0.1)
                
            def close(self):
                # Placeholder for actual close implementation
                log.debug(f"Closing connection to {device_address}")
        
        return MacOSBluetoothReader(), MacOSBluetoothWriter()
    async def stop(self):
        await super().stop()
        if not self.started:
            return

        if self.__task_recv:
            self.__task_recv.cancel()
            with suppress(Exception):
                await self.__task_recv
            self.__task_recv = None

        if self._writer is not None:
            self._writer.close()

        self._writer = None
        self.started = False
        log.info("Stopped")

    def healthy(self):
        return self.started and not self.__task_recv.done()

    async def _loop_recv(self, reader):
        log.debug(f"Init recv task with {reader}")
        await asyncio.sleep(60)
