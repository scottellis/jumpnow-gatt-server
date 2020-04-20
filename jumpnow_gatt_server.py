#!/usr/bin/env python3

import sys
import dbus, dbus.mainloop.glib
from gi.repository import GLib
from ble_advertisement import Advertisement
from ble_gatt_server import Application, Service, Characteristic
 
BLUEZ_SERVICE_NAME           = 'org.bluez'
DBUS_OM_IFACE                = 'org.freedesktop.DBus.ObjectManager'
LE_ADVERTISING_MANAGER_IFACE = 'org.bluez.LEAdvertisingManager1'
GATT_MANAGER_IFACE           = 'org.bluez.GattManager1'
GATT_CHRC_IFACE              = 'org.bluez.GattCharacteristic1'

JUMPNOW_LOCAL_NAME                 = 'jumpnow'
JUMPNOW_SERVICE_UUID               = 'bc5f3500-fc8e-4704-a4c9-7311da5d6a9b'
JUMPNOW_NOTIFY_CHARACTERISTIC_UUID = 'bc5f3501-fc8e-4704-a4c9-7311da5d6a9b'
JUMPNOW_WRITE_CHARACTERISTIC_UUID  = 'bc5f3502-fc8e-4704-a4c9-7311da5d6a9b'
JUMPNOW_READ_CHARACTERISTIC_UUID   = 'bc5f3503-fc8e-4704-a4c9-7311da5d6a9b'
JUMPNOW_RW_CHARACTERISTIC_UUID     = 'bc5f3504-fc8e-4704-a4c9-7311da5d6a9b'

debug = False
mainloop = None
 
class NotifyCharacteristic(Characteristic):
    """ Handle a read/notify characteristic """

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, JUMPNOW_NOTIFY_CHARACTERISTIC_UUID,
                                ['read', 'notify'], service)
        self.notifying = False
        self.delay_secs = 5
        self.z = 0


    def timer_cb(self, args):
        if not self.notifying:
            # this kills the timer
            return False

        if self.z > 0xff:
            self.z = 0
        else:
            self.z = self.z + 1

        self.PropertiesChanged(GATT_CHRC_IFACE, { 'Value': [ dbus.Byte(self.z) ] }, [])

        return True


    def ReadValue(self, options):
        return [ dbus.Byte(self.z) ] 


    def StartNotify(self):
        if self.notifying:
            return

        self.notifying = True
        GLib.timeout_add_seconds(self.delay_secs, self.timer_cb, None)


    def StopNotify(self):
        self.notifying = False


class ReadOnlyCharacteristic(Characteristic):
    """ Handle a read only characteristic """

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, JUMPNOW_READ_CHARACTERISTIC_UUID,
                                ['read'], service)

    def ReadValue(self, options):
        if debug:
            print('ReadCharacteristic read: ' + repr(self.service.x))

        return [ dbus.Byte(self.service.x) ] 

 
class WriteOnlyCharacteristic(Characteristic):
    """ Handle a write only characteristic """

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, JUMPNOW_WRITE_CHARACTERISTIC_UUID,
                                ['write'], service)


    def WriteValue(self, value, options):
        if debug:
            print('WriteCharacteristic write: ' + repr(value))
        
        if len(value) != 1:
            raise InvalidValueLengthException()

        data = value[0]

        if debug:
            print('New value: ' + repr(data))

        self.service.x = data


class RWCharacteristic(Characteristic):
    """ Handle a read/write characteristic """

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, JUMPNOW_RW_CHARACTERISTIC_UUID,
                                ['read', 'write'], service)


    def ReadValue(self, options):
        if debug:
            print('RWCharacteristic read: ' + repr(self.service.y))

        return [ dbus.Byte(self.service.y) ] 


    def WriteValue(self, value, options):
        if debug:
            print('RWCharacteristic write: ' + repr(value))
        
        if len(value) != 1:
            raise InvalidValueLengthException()

        data = value[0]

        if debug:
            print('New value: ' + repr(data))

        self.service.y = data


class JumpnowService(Service):
    def __init__(self, bus, index):
        Service.__init__(self, bus, index, JUMPNOW_SERVICE_UUID, True)

        # some variables to work with via Read/Write characteristics
        self.x = 10 
        self.y = 20

        self.add_characteristic(NotifyCharacteristic(bus, 0, self))
        self.add_characteristic(ReadOnlyCharacteristic(bus, 1, self))
        self.add_characteristic(WriteOnlyCharacteristic(bus, 2, self))
        self.add_characteristic(RWCharacteristic(bus, 3, self))

 
class JumpnowApplication(Application):
    def __init__(self, bus, index):
        Application.__init__(self, bus)
        self.add_service(JumpnowService(bus, index))

 
class JumpnowAdvertisement(Advertisement):
    def __init__(self, bus, index):
        Advertisement.__init__(self, bus, index, 'peripheral')
        self.add_service_uuid(JUMPNOW_SERVICE_UUID)        
        self.add_local_name(JUMPNOW_LOCAL_NAME)
        self.include_tx_power = True

 
def find_adapter(bus):
    remote_om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'),
                               DBUS_OM_IFACE)

    objects = remote_om.GetManagedObjects()

    for o, props in objects.items():
        if LE_ADVERTISING_MANAGER_IFACE in props and GATT_MANAGER_IFACE in props:
            return o

        if debug:
            print('Skipping adapter:', o)

    return None


def register_adv_cb():
    print('Advertisement registered')


def register_adv_error_cb(error):
    print(str(error))
    mainloop.quit()


def register_app_cb():
    print('Application registered')


def register_app_error_cb(error):
    print(str(error))
    mainloop.quit()

 
def main():
    global mainloop

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    bus = dbus.SystemBus()

    adapter = find_adapter(bus)
    if not adapter:
        print('BLE adapter not found')
        return

    service_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter),
                                     GATT_MANAGER_IFACE)

    ad_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter),
                                LE_ADVERTISING_MANAGER_IFACE)
 
    app = JumpnowApplication(bus, 0)

    adv = JumpnowAdvertisement(bus, 0)
 
    mainloop = GLib.MainLoop()
 
    service_manager.RegisterApplication(app.get_path(), {},
                                        reply_handler=register_app_cb,
                                        error_handler=register_app_error_cb)

    ad_manager.RegisterAdvertisement(adv.get_path(), {},
                                     reply_handler=register_adv_cb,
                                     error_handler=register_adv_error_cb)

    try:
        mainloop.run()

    except KeyboardInterrupt:
        adv.Release()

 
if __name__ == '__main__':
    main()
