"""
Bluetooth functionality for macOS
"""
import asyncio
import logging
import subprocess
from contextlib import suppress

# Import PyObjC modules for macOS Bluetooth functionality
try:
    import objc
    from Foundation import NSObject, NSArray
    from PyObjCTools import AppHelper
    from CoreBluetooth import (
        CBCentralManager, CBPeripheralManager,
        CBManagerStatePoweredOn, CBManagerStatePoweredOff
    )
    PYOBJC_AVAILABLE = True
except ImportError:
    PYOBJC_AVAILABLE = False

from openfreebuds_backend.exception import BackendException, OfbBackendDependencyMissingError

log = logging.getLogger("OfbMacOSBackend")

# Path to blueutil command-line tool
BLUEUTIL_PATH = "blueutil"
BLUEUTIL_URL = "https://github.com/toy/blueutil"


class BluetoothManager(NSObject):
    """
    Wrapper for CoreBluetooth functionality
    """
    def init(self):
        self = objc.super(BluetoothManager, self).init()
        if self is None:
            return None
        self.central_manager = CBCentralManager.alloc().initWithDelegate_queue_(self, None)
        self.devices = []
        self.is_powered_on = False
        self.scan_complete = asyncio.Event()
        return self
    
    def centralManagerDidUpdateState_(self, central):
        if central.state() == CBManagerStatePoweredOn:
            self.is_powered_on = True
        else:
            self.is_powered_on = False
            
    def centralManager_didDiscoverPeripheral_advertisementData_RSSI_(self, central, peripheral, data, rssi):
        device_info = {
            "name": peripheral.name() or "Unknown",
            "address": str(peripheral.identifier().UUIDString()),
            "connected": False  # We'll update this later
        }
        self.devices.append(device_info)


class BluetoothBackend:
    """
    macOS Bluetooth backend implementation
    """
    def __init__(self):
        self.devices = []
        self.bt_manager = None
        if PYOBJC_AVAILABLE:
            self.bt_manager = BluetoothManager.alloc().init()
        
    async def get_devices(self):
        """
        Get list of paired Bluetooth devices
        """
        if not PYOBJC_AVAILABLE:
            raise OfbBackendDependencyMissingError("PyObjC is required for macOS Bluetooth support", 
                                                  "pip install pyobjc-framework-CoreBluetooth")
        
        # Check if blueutil is installed for command-line operations
        try:
            result = await self._run_blueutil_command(["--paired"])
            devices = []
            
            for line in result.strip().split('\n'):
                if line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        address = parts[0].strip()
                        name = parts[1].strip()
                        
                        # Check if device is connected
                        connected = False
                        with suppress(Exception):
                            connected_result = await self._run_blueutil_command(["--is-connected", address])
                            connected = "1" in connected_result.strip()
                        
                        devices.append({
                            "name": name,
                            "address": address,
                            "connected": connected
                        })
            
            return devices
        except (subprocess.SubprocessError, FileNotFoundError):
            raise OfbBackendDependencyMissingError("blueutil is required for macOS Bluetooth support", BLUEUTIL_URL)
        
    async def connect(self, address):
        """
        Connect to a Bluetooth device
        """
        if not PYOBJC_AVAILABLE:
            raise OfbBackendDependencyMissingError("PyObjC is required for macOS Bluetooth support", 
                                                  "pip install pyobjc-framework-CoreBluetooth")
        
        try:
            result = await self._run_blueutil_command(["--connect", address])
            await asyncio.sleep(1)  # Give some time for the connection to establish
            
            # Verify connection was successful
            connected_result = await self._run_blueutil_command(["--is-connected", address])
            return "1" in connected_result.strip()
        except subprocess.SubprocessError as e:
            log.exception(f"Failed to connect to device {address}")
            return False
        except FileNotFoundError:
            raise OfbBackendDependencyMissingError("blueutil is required for macOS Bluetooth support", BLUEUTIL_URL)
        
    async def disconnect(self, address):
        """
        Disconnect from a Bluetooth device
        """
        if not PYOBJC_AVAILABLE:
            raise OfbBackendDependencyMissingError("PyObjC is required for macOS Bluetooth support", 
                                                  "pip install pyobjc-framework-CoreBluetooth")
        
        try:
            result = await self._run_blueutil_command(["--disconnect", address])
            await asyncio.sleep(1)  # Give some time for the disconnection to complete
            
            # Verify disconnection was successful
            connected_result = await self._run_blueutil_command(["--is-connected", address])
            return "0" in connected_result.strip()
        except subprocess.SubprocessError:
            log.exception(f"Failed to disconnect from device {address}")
            return False
        except FileNotFoundError:
            raise OfbBackendDependencyMissingError("blueutil is required for macOS Bluetooth support", BLUEUTIL_URL)
    
    async def is_connected(self, address):
        """
        Check if a device is connected
        """
        if not PYOBJC_AVAILABLE:
            raise OfbBackendDependencyMissingError("PyObjC is required for macOS Bluetooth support", 
                                                  "pip install pyobjc-framework-CoreBluetooth")
        
        try:
            connected_result = await self._run_blueutil_command(["--is-connected", address])
            return "1" in connected_result.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            log.info("Got error checking connection status, assuming not connected")
            return False
    
    async def _run_blueutil_command(self, args):
        """
        Run a blueutil command and return the output
        """
        cmd = [BLUEUTIL_PATH] + args
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise subprocess.SubprocessError(f"blueutil command failed: {stderr.decode()}")
        
        return stdout.decode()


# Create module-level functions to match the API of the other backends
async def bt_is_connected(address):
    backend = BluetoothBackend()
    return await backend.is_connected(address)

async def bt_connect(address):
    backend = BluetoothBackend()
    return await backend.connect(address)

async def bt_disconnect(address):
    backend = BluetoothBackend()
    return await backend.disconnect(address)

async def bt_list_devices():
    backend = BluetoothBackend()
    return await backend.get_devices()