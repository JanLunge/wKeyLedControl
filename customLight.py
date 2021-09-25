import sys
import struct
import random
import math
import time
import datetime
import json
hostName = "localhost"
serverPort = 8080
if sys.platform.startswith("linux"):
    import hidraw as hid
else:
    import hid

import asyncio
from aiohttp import web

import win32api
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from global_hotkeys import *
from ulid import ULID
from datetime import datetime, timedelta
MSG_LEN = 32
VIAL_SERIAL_NUMBER_MAGIC = "vial:f64c2b3c"

VIALRGB_EFFECT_DIRECT = 1

CMD_VIA_DYNAMIC_KEYMAP_GET_KEYCODE = 0x04
CMD_VIA_LIGHTING_SET_VALUE = 0x07
CMD_VIA_LIGHTING_GET_VALUE = 0x08

VIALRGB_GET_INFO = 0x40
VIALRGB_GET_MODE = 0x41
VIALRGB_GET_SUPPORTED = 0x42
VIALRGB_GET_NUMBER_LEDS = 0x43
VIALRGB_GET_LED_INFO = 0x44

VIALRGB_SET_MODE = 0x41
VIALRGB_DIRECT_FASTSET = 0x42

BASIC_QMK_KEYCODES = {
    4: "A",
    5: "B",
    6: "C",
    7: "D",
    8: "E",
    9: "F",
    10: "G",
    11: "H",
    12: "I",
    13: "J",
    14: "K",
    15: "L",
    16: "M",
    17: "N",
    18: "O",
    19: "P",
    20: "Q",
    21: "R",
    22: "S",
    23: "T",
    24: "U",
    25: "V",
    26: "W",
    27: "X",
    28: "Y",
    29: "Z",
    30: "!1",
    31: "@2",
    32: "#3",
    33: "$4",
    34: "%5",
    35: "^6",
    36: "&7",
    37: "*8",
    38: "(9",
    39: ")0",
    40: "Enter",
    41: "Esc",
    42: "Bksp",
    43: "Tab",
    44: "Space",
    45: "_-",
    46: "+=",
    47: "{[",
    48: "}]",
    49: "|\\",
    51: ":;",
    52: "\"'",
    53: "~`",
    54: "<,",
    55: ">.",
    56: "?/",
    57: "Caps",
    58: "F1",
    59: "F2",
    60: "F3",
    61: "F4",
    62: "F5",
    63: "F6",
    64: "F7",
    65: "F8",
    66: "F9",
    67: "F10",
    68: "F11",
    69: "F12",
    70: "PrintScreen",
    71: "ScrollLock",
    72: "Pause",
    73: "Insert",
    74: "Home",
    75: "PageUp",
    76: "Del",
    77: "End",
    78: "PageDown",
    79: "Right",
    80: "Left",
    81: "Down",
    82: "Up",
    83: "NumLock",
    84: "/",
    85: "*",
    86: "-",
    87: "+",
    88: "NumEnter",
    89: "1",
    90: "2",
    91: "3",
    92: "4",
    93: "5",
    94: "6",
    95: "7",
    96: "8",
    97: "9",
    98: "0",
    99: ".",
    101: "Menu",
    103: "=",
    133: ",",
    224: "LCtrl",
    225: "LShift",
    226: "LAlt",
    227: "LGui",
    228: "RCtrl",
    229: "RShift",
    230: "RAlt",
    231: "RGui",
}


class VialRGBLed:

    def __init__(self, idx, x, y, flags, row, col, keycode):
        self.idx = idx
        self.x = x
        self.y = y
        self.flags = flags
        self.row = row
        self.col = col
        self.keycode = keycode


        self.h = self.s = self.v = 0

    def __repr__(self):
        return "VialRGBLed(idx={}, x={}, y={}, flags={}, row={}, col={})".format(
            self.idx, self.x, self.y, self.flags, self.row, self.col)


def hid_send(dev, msg, retries=1):
    if len(msg) > MSG_LEN:
        raise RuntimeError("message must be less than 32 bytes")
    msg += b"\x00" * (MSG_LEN - len(msg))

    data = b""
    first = True

    while retries > 0:
        retries -= 1
        if not first:
            time.sleep(0.5)
        first = False
        try:
            # add 00 at start for hidapi report id
            if dev.write(b"\x00" + msg) != MSG_LEN + 1:
                continue

            data = bytes(dev.read(MSG_LEN))
            if not data:
                continue
        except OSError:
            continue
        break

    if not data:
        raise RuntimeError("failed to communicate with the device")
    return data


def is_rawhid(desc):
    """ Check that this device (and specifically, the usage_page) implements Vial protocol """
    if desc["usage_page"] != 0xFF60 or desc["usage"] != 0x61:
        return False

    try:
        dev = hid.Device(path= desc["path"])
    except OSError as e:
        return False

    # probe VIA version and ensure it is supported
    data = b""
    try:
        data = hid_send(dev, b"\x01", retries=3)
    except RuntimeError as e:
        pass
    dev.close()

    # must have VIA protocol version = 9
    if data[0:3] != b"\x01\x00\x09":
        return False

    return True


def is_vialrgb(desc):
    """ Check that this device implements VialRGB protocol """
    print("checking for rgb support")

    try:
        dev = hid.Device(path=desc["path"])
    except OSError as e:
        return False

    # probe Vial version and ensure it is supported
    data = b""
    try:
        data = hid_send(dev, b"\xFE\x00", retries=3)
    except RuntimeError as e:
        pass
    dev.close()

    if len(data) != MSG_LEN:
        return False

    vial_protocol, keyboard_uid, flags = struct.unpack("<IQB", data[0:13])

    # must be Vial protocl 4 or later
    if vial_protocol < 4:
        return False

    # must have VialRGB flag set
    return (flags & 1) == 1


def find_vial_devices():
    for desc in hid.enumerate():
        if desc["serial_number"]:
            if VIAL_SERIAL_NUMBER_MAGIC in desc["serial_number"] and is_rawhid(desc) and is_vialrgb(desc):
                return desc


def vialrgb_get_modes(dev):
    """ Retrieve list of supported modes from the keyboard """

    data = hid_send(dev, struct.pack("BB", CMD_VIA_LIGHTING_GET_VALUE, VIALRGB_GET_INFO), retries=20)[2:]
    rgb_version = data[0] | (data[1] << 8)
    if rgb_version != 1:
        raise RuntimeError("Unsupported VialRGB protocol ({})".format(rgb_version))

    rgb_supported_effects = {0}
    max_effect = 0
    while max_effect < 0xFFFF:
        data = hid_send(dev, struct.pack("<BBH", CMD_VIA_LIGHTING_GET_VALUE, VIALRGB_GET_SUPPORTED, max_effect))[2:]
        for x in range(0, len(data), 2):
            value = int.from_bytes(data[x:x+2], byteorder="little")
            if value != 0xFFFF:
                rgb_supported_effects.add(value)
            max_effect = max(max_effect, value)
    return rgb_supported_effects


def vialrgb_get_leds(dev):
    """ Retrieve RGB LEDs positions and flags from the keyboard """

    data = hid_send(dev, struct.pack("BB", CMD_VIA_LIGHTING_GET_VALUE, VIALRGB_GET_NUMBER_LEDS))
    num_leds = struct.unpack("<H", data[2:4])[0]

    leds = []
    for idx in range(num_leds):
        data = hid_send(dev, struct.pack("<BBH", CMD_VIA_LIGHTING_GET_VALUE, VIALRGB_GET_LED_INFO, idx))
        x, y, flags, row, col = struct.unpack("BBBBB", data[2:7])
        if row == 0xFF:
            row = None
        if col == 0xFF:
            col = None
        keycode = None
        # retrieve which keycode it's mapped to on first layer
        if row is not None and col is not None:
            data = hid_send(dev, struct.pack("BBBB", CMD_VIA_DYNAMIC_KEYMAP_GET_KEYCODE, 0, row, col))
            keycode = int.from_bytes(data[4:6], byteorder="big")
        leds.append(VialRGBLed(idx, x, y, flags, row, col, keycode))
    return leds


def vialrgb_set_mode(dev, mode):
    """ Set mode (note this specifically should be used with direct, it ignores speed and hsv) """

    hid_send(dev, struct.pack("BBHBBBB", CMD_VIA_LIGHTING_SET_VALUE, VIALRGB_SET_MODE,
                  mode, 128, 128, 128, 128), retries=20)


def vialrgb_send_leds(dev, leds):
    """ Send leds to the keyboard """

    SEND_PER_PACKET = 9

    for x, led in enumerate(leds):
        if x != led.idx:
            raise RuntimeError("leds got reordered")

    num_leds = len(leds)
    sent = 0
    while sent < num_leds:
        start_led = sent
        buffer = []
        leds_to_send = leds[start_led:start_led+SEND_PER_PACKET]
        for led in leds_to_send:
            buffer += [led.h, led.s, led.v]

        payload = struct.pack("BBHB", CMD_VIA_LIGHTING_SET_VALUE, VIALRGB_DIRECT_FASTSET, start_led, len(leds_to_send))
        payload += b"".join(x.to_bytes(1, byteorder="little") for x in buffer)

        hid_send(dev, payload)

        sent += len(leds_to_send)


def clamp(value):
    value = int(value)
    if value < 0:
        return 0
    if value >= 255:
        return 255
    return value


def update_leds(leds):
    """ Update the animation """

    for led in leds:
        t = time.time() * 50
        if led.row is not None:
            led.h = 0
        else:
            # for underglow, set them all to a static color
            led.h = int(t) % 256
        # set the led status here with time etc
        
        led.s = 255
        led.v = 0

        # sample static color
        if led.row == 1 and led.col == 0:
            led.v = 200
            led.h = 15

        # sample notification that expires
        if led.row == 1 and led.col == 1:
            now = datetime.datetime.now()
            notification_done = now + datetime.timedelta(seconds=15)
            if now < notification_done:
                speed = 0.05
                value = int(t*speed)%2
                sin = int(math.sin(value)*128+128)
                print(value,sin)
                led.v =  254 if value == 1 else 50
                led.h = 0


def main():
    desc = find_vial_devices()
    if desc is None:
        print("failed to find any VialRGB devices!")
        return 1
    print("Trying {} {}".format(desc["manufacturer_string"], desc["product_string"]))

    global dev
    global leds
    global ledstack
    global ledstate
    global animated_mode
    ledstack = [] # stack of all widgets on the display
    ledstate = [] # state of all leds on the display
    animated_mode = False

    dev = hid.Device(path=desc["path"])

    # Check this keyboard supports direct control mode
    modes = vialrgb_get_modes(dev)
    if VIALRGB_EFFECT_DIRECT not in modes:
        print("The keyboard doesn't support direct LED control")
        return 1

    # Retrieve leds positions
    leds = vialrgb_get_leds(dev)

    # Set keyboard to direct control mode
    vialrgb_set_mode(dev, VIALRGB_EFFECT_DIRECT)

    done = False

    for led in leds:
        led.render_x = (led.x + 50) * 2
        led.render_y = (led.y + 50) * 2

        # update_leds(leds)
        vialrgb_send_leds(dev, leds)
    

    def update_volume():
        global animated_mode
        now = datetime.now()
        date_timeout = now + timedelta(seconds=5)
        has_volume_widget = False
        animated_mode = True
        for widget in ledstack:
            if widget["type"] == "volume":
                has_volume_widget = True
                widget["config"]["date_timeout"] = date_timeout
                return
        if not has_volume_widget:
            ledstack.append({
                "id": "01FGCZT88GZB61P13ANXR03131", 
                "indexes": [0,1,2,3,4,5],
                "config":{ 
                    "date_timeout": date_timeout, 
                    "color": {"h": 255, "s": 0, "v": 255}
                    }, 
                "type": "volume"
                })
        asyncio.run(small_animation_loop()) 

    async def small_animation_loop():
        global animated_mode
        while animated_mode:
            for idx,widget in enumerate(ledstack):
                if widget["type"] == "volume":
                    now = datetime.now()
                    then = widget["config"]["date_timeout"]
                    if now > then:
                        animated_mode = False
                        del ledstack[idx]
            asyncio.create_task(update_display())
            await asyncio.sleep(1/60) 



    # These take the format of [<key list>, <keydown handler callback>, <keyup handler callback>]
    bindings = [
        #[['volume_Down'], lower_volume, None],
        [[ "volume_up"], update_volume, None],
    ]
    register_hotkeys(bindings)
    start_checking_hotkeys()


    webserver = WebServer()

    webserver.run()



class WebServer:
    def __init__(self, **kwargs: dict):
        self.app = web.Application()
        self.host = 'localhost'
        self.port = 8080

    async def initializer(self) -> web.Application:
        # Setup routes and handlers
        self.app.router.add_get('/notification', self.get_notification_handler)
        self.app.router.add_get('/volume', self.get_volume_handler)
        
        return self.app
    def run(self):
        web.run_app(self.initializer(), host=self.host, port=self.port)

    async def post_notification_handler(self, request: web.Request) -> web.Response:
        data = await request.json()
        indexes = data["leds"]
        color = data["color"]
        timeout = data["timeout"] 
        asyncio.create_task(set_notification_led(indexes=indexes,  timeout=timeout, color=color))
    
    async def animation_loop(self):
        print("animaitin")
        await asyncio.sleep(5)  

    async def get_notification_handler(self, request: web.Request) -> web.Response:
        color = {
            "h":int(request.query["h"]),
            "s":int(request.query["s"]),
            "v":int(request.query["v"])
            }
        indexes = list(map(int,request.query["indexes"].split(',')))
        timeout = int(request.query["timeout"])
        ulid = ULID()
        ledstack.append({"id": str(ulid) , "indexes": indexes, "config":{ "timeout": timeout, "color": color}, "type": "notification"})
        asyncio.create_task(update_display())
       
    async def get_volume_handler(self, request: web.Request) -> web.Response:
        incr = request.query["incr"]
        print("volume")
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        print("volume.GetMute(): %s" % volume.GetMute())
        vol = volume.GetMasterVolumeLevelScalar()
        print("volume.GetMasterVolume(): %s" % vol)
    
        if incr:
            volume.SetMasterVolumeLevelScalar(vol+0.05, None)
        else:
            volume.SetMasterVolumeLevelScalar(vol-0.05, None)
        update_volume()
        
async def update_display():
    #reset leds
    for led in leds:
        led.h = 0
        led.v = 0
        led.s = 0
    # generate led state here
    for widget in ledstack:
        if widget["type"] == "notification":
            await set_notification_led(widget)
            asyncio.create_task(reset_leds(widget))
        if widget["type"] == "volume":
            await set_volume_bar(widget)
            asyncio.create_task(reset_leds(widget))
    vialrgb_send_leds(dev, leds)

async def set_notification_led(widget):
    for led in leds:
        if led.idx in widget["indexes"]:
            led.v = int(widget["config"]["color"]["v"])
            led.h = int(widget["config"]["color"]["h"])
            led.s = int(widget["config"]["color"]["s"])
async def reset_leds(widget):
    timeout = widget["config"].get("timeout")
    date_timeout = widget["config"].get("date_timeout")
    if timeout:
        await asyncio.sleep(timeout)
        # store states in layers?
        for idx, search_widget in enumerate(ledstack):
            if widget["id"] == search_widget["id"]:
                del ledstack[idx]
        await update_display()

async def set_volume_bar(widget):
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    mute = volume.GetMute()
    vol = volume.GetMasterVolumeLevelScalar()
    ledslit = 6 * vol
    for led in leds:
        led.v = 0
        if led.idx < int(ledslit):
            led.v = 255 
            led.h = 0 
            led.s = 0 
        if led.idx == int(ledslit):
            led.v= int((ledslit%1)*255)
            led.s = 0

 
if __name__ == "__main__":
    main()