import sys
import struct
import random
import math
import time

if sys.platform.startswith("linux"):
    import hidraw as hid
else:
    import hid

import pygame


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
    print("checking device for raw_hid")
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
        print("probing vial")
        print(data)
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
    print("checking devices")
    # print(hid.enumerate())
    print(type(hid.enumerate()))
    for desc in hid.enumerate():
        print("checking one device entry ")
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
            led.h = int(led.x + led.y + t) % 256
        else:
            # for underglow, set them all to a static color
            led.h = int(t) % 256
        led.s = 255
        led.v = 50


def find_next_led(leds, active_led, checker):
    next_led = active_led
    next_distance = 1e6
    for led in leds:
        if led == active_led:
            continue
        if led.row is not None and checker(active_led, led):
            distance = (active_led.x - led.x) ** 2 + (active_led.y - led.y) ** 2
            if distance < next_distance:
                next_led = led
                next_distance = distance

    return next_led


def go_left(leds, active_led):
    return find_next_led(leds, active_led, lambda a, b: a.y == b.y and b.x < a.x)


def go_right(leds, active_led):
    return find_next_led(leds, active_led, lambda a, b: a.y == b.y and b.x > a.x)


def go_up(leds, active_led):
    return find_next_led(leds, active_led, lambda a, b: a.y > b.y)


def go_down(leds, active_led):
    return find_next_led(leds, active_led, lambda a, b: a.y < b.y)


def main():
    desc = find_vial_devices()
    if desc is None:
        print("failed to find any VialRGB devices!")
        return 1
    print("Trying {} {}".format(desc["manufacturer_string"], desc["product_string"]))

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

    pygame.init()

    pygame.display.set_caption("VialRGB Direct Control Demo")
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.Font(None, 30)
    keycode_font = pygame.font.Font(None, 15)
    clock = pygame.time.Clock()
    done = False

    # set up active_led as the first keyboard matrix led
    for led in leds:
        if led.row is not None:
            active_led = led
            break

    for led in leds:
        led.render_x = (led.x + 50) * 2
        led.render_y = (led.y + 50) * 2

        if led.keycode is not None:
            display = BASIC_QMK_KEYCODES.get(led.keycode, hex(led.keycode))
            led.rendered_keycode = keycode_font.render(display, True, pygame.Color("cyan"))

    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True

            if event.type == pygame.KEYUP:
                if event.key in [pygame.K_LEFT, ord("a")]:
                    active_led = go_left(leds, active_led)
                elif event.key in [pygame.K_RIGHT, ord("d")]:
                    active_led = go_right(leds, active_led)
                elif event.key in [pygame.K_UP, ord("w")]:
                    active_led = go_up(leds, active_led)
                elif event.key in [pygame.K_DOWN, ord("s")]:
                    active_led = go_down(leds, active_led)

        screen.fill(pygame.Color("black"))

        for led in leds:
            color = (0, 255, 0)

            # keyboard matrix is green, underglow/sidebar/etc is red
            color = (0, 128, 0)
            if led.row is None:
                color = (128, 0, 0)
            if led == active_led:
                color = (255, 255, 255)
            pygame.draw.circle(screen, color=color, center=(led.render_x+4, led.render_y+4), radius=10)

        for led in leds:
            if led.keycode is not None:
                screen.blit(led.rendered_keycode, (led.render_x, led.render_y))

        fps = font.render("{:6d} fps".format(int(clock.get_fps())), True, pygame.Color('white'))
        screen.blit(fps, (20, 20))

        update_leds(leds)
        active_led.h = active_led.s = 0
        active_led.v = 255
        vialrgb_send_leds(dev, leds)

        pygame.display.flip()
        clock.tick()

    return 0


if __name__ == "__main__":
    sys.exit(main())