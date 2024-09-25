import time
import codecs
from logging import getLogger
import os

import broadlink
from peewee import AutoField, IntegerField, Model, SqliteDatabase, TextField

STATUS_TIMEOUT = float(os.environ.get("BROADLINK_STATUS_TIMEOUT", "1"))
DISCOVERY_TIMEOUT = float(os.environ.get("BROADLINK_DISCOVERY_TIMEOUT", "5"))
LEARNING_TIMEOUT = float(os.environ.get("BROADLINK_LEARNING_TIMEOUT", "30"))

_LOGGER = getLogger(__name__)

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

    @property
    def available(self):
        return self.device is not None

    @property
    def device(self):
        device = broadlink.rm(
            host=(self.ip, self.port), mac=dec_hex(self.mac_hex), devtype=self.devtype
        )
        try:
            device.auth()
        except broadlink.exceptions.NetworkTimeoutError:
            _LOGGER.error(
                "Can't connect to device %s (IP: %s MAC: %s)",
                self.name,
                self.ip,
                self.mac,
            )
            return None
        return device

    def to_dict(self):
        return {
            "name": self.name,
            "ip": self.ip,
            "mac": self.mac,
            "available": self.available,
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
        device = self.device
        if device:
            device.send_data(dec_b64(command.value))
            return True
        return False

    def send_raw(self, value):
        device = self.device
        if device:
            device.send_data(dec_b64(value))
            return True
        else:
            return False

    def get_command(self):
        device = self.device
        if device:
            device.enter_learning()

            start = time.time()
            while time.time() - start < LEARNING_TIMEOUT:
                time.sleep(1)
                try:
                    value = device.check_data()
                except (broadlink.exceptions.ReadError, broadlink.exceptions.StorageError):
                    continue
                else:
                    break
            else:
                return None

            if value and value.replace(b"\x00", b"") != b"":
                try:
                    return enc_b64(value)
                except:
                    return None
            else:
                return None
        return False


def friendly_mac_from_hex(raw):
    return ":".join([raw[(x * 2) : ((x + 1) * 2)] for x in range(0, 6)])


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


def get_new_blasters(at_ip=None, timeout=DISCOVERY_TIMEOUT):
    cnt = 0
    discovered = []

    if at_ip:
        d = broadlink.hello(at_ip)
        if d:
            discovered.append(d)
    else:
        discovered = discover_blasters(timeout=timeout)

    for blaster in discovered:
        mac_hex = enc_hex(blaster.mac)
        mac = friendly_mac_from_hex(mac_hex)
        check_blaster = Blaster.get_or_none(
            Blaster.mac_hex % mac_hex
        ) or Blaster.get_or_none(Blaster.mac % mac)

        if check_blaster:
            check_blaster.ip = blaster.host[0]
            check_blaster.port = blaster.host[1]
            check_blaster.mac = mac
            check_blaster.mac_hex = mac_hex
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
