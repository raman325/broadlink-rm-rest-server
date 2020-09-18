# dependencies - peewee, broadlink

import codecs
import os
from time import sleep

import broadlink
from peewee import AutoField, IntegerField, Model, SqliteDatabase, TextField

STATUS_TIMEOUT = float(os.environ.get("BROADLINK_STATUS_TIMEOUT", "1"))
DISCOVERY_TIMEOUT = float(os.environ.get("BROADLINK_DISCOVERY_TIMEOUT", "5"))

blasters_db_path = "data/blasters.db"

blasters_db = SqliteDatabase(blasters_db_path)

#### Blaster DB classes and functions


class BaseBlastersModel(Model):
    class Meta:
        database = blasters_db


class Blaster(BaseBlastersModel):
    uid = AutoField()
    ip = TextField()
    port = IntegerField()
    devtype = IntegerField()
    mac = TextField(unique=True)
    mac_hex = TextField(unique=True)
    name = TextField(unique=True, null=True)

    def get_device(self):
        device = broadlink.rm(
            host=(self.ip, self.port), mac=dec_hex(self.mac_hex), devtype=self.devtype
        )
        device.auth()
        return device

    def to_dict(self):
        return {
            "name": self.name,
            "ip": self.ip,
            "mac": self.mac,
            "available": self.available(),
        }

    def put_name(self, name):
        check_blaster = Blaster.get_or_none(Blaster.name % name)

        if check_blaster:
            return False
        else:
            self.name = name
            self.save()
            return True

    def send_command(self, command):
        device = self.get_device()
        device.send_data(dec_b64(command.value))

    def send_raw(self, value):
        device = self.get_device()
        device.send_data(dec_b64(value))

    def get_command(self):
        device = self.get_device()
        device.enter_learning()

        sleep(2)
        value = device.check_data()
        x = 0

        while not value and x < 5:
            x += 1
            sleep(2)
            value = device.check_data()

        if value and value.replace(b"\x00", b"") != b"":
            try:
                return enc_b64(value)
            except:
                return None
        else:
            return None

    def available(self):
        return (
            len(
                list(
                    filter(
                        lambda blaster: enc_hex(blaster.mac) == self.mac_hex,
                        discover_blasters(timeout=STATUS_TIMEOUT),
                    )
                )
            )
            > 0
        )


def friendly_mac_from_hex(raw):
    return (
        raw[10:12]
        + ":"
        + raw[8:10]
        + ":"
        + raw[6:8]
        + ":"
        + raw[4:6]
        + ":"
        + raw[2:4]
        + ":"
        + raw[0:2]
    )


def enc_hex(raw):
    return codecs.encode(raw, encoding="hex").decode()


def dec_hex(raw):
    return bytearray(codecs.decode(raw, encoding="hex"))


def enc_b64(raw):
    return codecs.encode(raw, encoding="base64").decode()


def dec_b64(raw):
    return bytearray(codecs.decode(raw.encode(), encoding="base64"))


def discover_blasters(timeout):
    return [
        blaster
        for blaster in broadlink.discover(timeout=timeout)
        if blaster.get_type().lower() in ("rm2", "rm4")
    ]


def get_new_blasters(timeout=DISCOVERY_TIMEOUT):
    cnt = 0

    for blaster in discover_blasters(timeout=timeout):
        mac_hex = enc_hex(blaster.mac)
        check_blaster = Blaster.get_or_none(Blaster.mac_hex % mac_hex)

        if check_blaster:
            check_blaster.ip = blaster.host[0]
            check_blaster.port = blaster.host[1]
            check_blaster.save()
        else:
            Blaster.create(
                ip=blaster.host[0],
                port=blaster.host[1],
                devtype=blaster.devtype,
                mac_hex=mac_hex,
                mac=friendly_mac_from_hex(mac_hex),
                name=None,
            )
            cnt += 1

    return {"new_devices": cnt}


def get_all_blasters():
    try:
        return [blaster for blaster in Blaster.select()]
    except Blaster.DoesNotExist:
        return []


def get_all_blasters_as_dict():
    try:
        return [blaster.to_dict() for blaster in Blaster.select()]
    except Blaster.DoesNotExist:
        return []


def get_blaster_by_name(name):
    return Blaster.get_or_none(Blaster.name % name)


def get_blaster_by_ip(ip):
    return Blaster.get_or_none(Blaster.ip % ip)


def get_blaster_by_mac(mac):
    return Blaster.get_or_none(Blaster.mac % mac)


def send_command_to_all_blasters(command):
    for blaster in get_all_blasters():
        blaster.send_command(command)
