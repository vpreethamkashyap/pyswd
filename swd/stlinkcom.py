"""ST-Link/V2 USB communication"""

import logging as _logging
import usb.core as _usb
import swd._log as _log


class StlinkComException(Exception):
    """Exception"""


class StlinkComNotFound(Exception):
    """Exception"""


class StlinkComMoreDevices(Exception):
    """Exception"""

    def __init__(self, devices):
        super().__init__("More than one device found.")
        self._serial_numbers = [dev.serial_no for dev in devices]

    @property
    def serial_numbers(self):
        """return list of serial numbers"""
        return self._serial_numbers


class StlinkComBase():
    """ST link comm base class"""
    ID_VENDOR = None
    ID_PRODUCT = None
    PIPE_OUT = None
    PIPE_IN = None

    """ST-Link/V2 USB communication class"""
    def __init__(self, dev):
        self._dev = dev

    @classmethod
    def find_all(cls):
        """return all devices with this idVendor and idProduct"""
        devices = []
        try:
            for device in _usb.find(idVendor=cls.ID_VENDOR, idProduct=cls.ID_PRODUCT, find_all=True):
                devices.append(cls(device))
        except _usb.NoBackendError as err:
            raise StlinkComException("USB Error: %s" % err)
        return devices


    @property
    def serial_no(self):
        """Return device serial number"""
        return ''.join(['%02X' % ord(c) for c in self._dev.serial_number])

    def compare_serial_no(self, serial_no):
        """Compare device serial no with selected serial number"""
        return self.serial_no.startswith(serial_no) or self.serial_no.endswith(serial_no)

    @_log.log(_log.DEBUG4)
    def write(self, data, tout=200):
        """Write data to USB pipe"""
        _logging.log(_log.DEBUG4, "%s", ', '.join(['0x%02x' % i for i in data]))
        try:
            count = self._dev.write(self.PIPE_OUT, data, tout)
        except _usb.USBError as err:
            self._dev = None
            raise StlinkComException("USB Error: %s" % err)
        _logging.log(_log.DEBUG4, "count=%d", count)
        if count != len(data):
            raise StlinkComException("Error Sending data")

    @_log.log(_log.DEBUG4)
    def read(self, size, tout=200):
        """Read data from USB pipe"""
        read_size = size
        _logging.log(_log.DEBUG4, "size=%d, read_size=%d", size, read_size)
        try:
            data = self._dev.read(self.PIPE_IN, read_size, tout).tolist()[:size]
        except _usb.USBError as err:
            self._dev = None
            raise StlinkComException("USB Error: %s" % err)
        _logging.log(_log.DEBUG4, "%s", ', '.join(['0x%02x' % i for i in data]))
        return data

    def __del__(self):
        if self._dev is not None:
            self._dev.finalize()


class StlinkComV2Usb(StlinkComBase):
    """ST-Link/V2 USB communication class"""
    ID_VENDOR = 0x0483
    ID_PRODUCT = 0x3748
    PIPE_OUT = 0x02
    PIPE_IN = 0x81
    DEV_NAME = "V2"


class StlinkComV21Usb(StlinkComBase):
    """ST-Link/V2-1 USB communication"""
    ID_VENDOR = 0x0483
    ID_PRODUCT = 0x374b
    PIPE_OUT = 0x01
    PIPE_IN = 0x81
    DEV_NAME = "V2-1"


class StlinkCom():
    """ST-Link communication class"""
    _STLINK_CMD_SIZE = 16
    _COM_CLASSES = [StlinkComV2Usb, StlinkComV21Usb]

    @classmethod
    def _find_all_devices(cls):
        devices = []
        for com_cls in cls._COM_CLASSES:
            devices.extend(com_cls.find_all())
        return devices

    @staticmethod
    def _filter_devices(devices, serial_no):
        filtered_devices = []
        for dev in devices:
            serial = dev.serial_no
            if serial.startswith(serial_no) or serial.endswith(serial_no):
                filtered_devices.append(dev)
        return filtered_devices

    def __init__(self, serial_no=''):
        self._dev = None
        devices = StlinkCom._find_all_devices()
        if serial_no:
            devices = StlinkCom._filter_devices(devices, serial_no)
        if not devices:
            raise StlinkComNotFound()
        if len(devices) > 1:
            raise StlinkComMoreDevices(devices)
        self._dev = devices[0]

    @property
    def version(self):
        """property with device version"""
        return self._dev.DEV_NAME

    @_log.log(_log.DEBUG3)
    def xfer(self, command, data=None, rx_length=0, tout=200):
        """Transfer command between ST-Link

        Arguments:
            command: is an list of bytes with command (max 16 bytes)
            data: data will be sent after command
            rx_length: number of expected data to receive after command and data transfer
            tout: maximum waiting time for received data

        Return:
            received data

        Raises:
            StlinkComException
        """
        if len(command) > self._STLINK_CMD_SIZE:
            raise StlinkComException(
                "Error too many Bytes in command (maximum is %d Bytes)"
                % self._STLINK_CMD_SIZE)
        # pad to _STLINK_CMD_SIZE
        command += [0] * (self._STLINK_CMD_SIZE - len(command))
        self._dev.write(command, tout)
        if data:
            self._dev.write(data, tout)
        if rx_length:
            return self._dev.read(rx_length)
        return None
