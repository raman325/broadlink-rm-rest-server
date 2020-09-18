# dependencies - peewee

from peewee import (
    AutoField,
    DateTimeField,
    ForeignKeyField,
    Model,
    SqliteDatabase,
    TextField,
)


commands_db_path = "data/commands.db"

commands_db = SqliteDatabase(commands_db_path)

## Commands DB classes and functions


class BaseCommandsModel(Model):
    class Meta:
        database = commands_db


class Encoding(BaseCommandsModel):
    encoding = TextField(unique=True)
    active_since = DateTimeField()

    def to_dict(self):
        return {"encoding": self.encoding, "active_since": self.active_since}


class Target(BaseCommandsModel):
    uid = AutoField()
    name = TextField(unique=True)

    def to_dict(self):
        return {"name": self.name}

    def get_command(self, name):
        return Command.get_or_none((Command.target == self) & (Command.name % name))

    def get_all_commands(self):
        try:
            return [command for command in self.commands]
        except:
            return []

    def get_all_commands_as_dict(self):
        return [command.to_dict() for command in self.commands]

    def add_command(self, name, value):

        if Command.get_or_none((Command.target == self) & (Command.name % name)):
            return False
        else:
            Command.create(target=self, name=name, value=value)
            return True

    def put_command(self, name, value):
        command = Command.get_or_none((Command.target == self) & (Command.name % name))

        if command:
            command.value = value
            command.save()
        else:
            Command.create(target=self, name=name, value=value)

    def delete_command(self, name):
        command = Command.get_or_none((Command.target == self) & (Command.name % name))

        if command:
            return bool(command.delete_instance())
        else:
            return False

    def update_name(self, new_name):
        check_target = Target.get_or_none(Target.name % new_name)

        if check_target:
            return False
        else:
            self.name = new_name
            self.save()
            return True


class Command(BaseCommandsModel):
    uid = AutoField()
    target = ForeignKeyField(Target, backref="commands")
    name = TextField()
    value = TextField()

    def to_dict(self):
        return {"name": self.name, "value": self.value}

    def get_value(self):
        return self.value

    def update_name(self, new_name):
        check_command = Command.get_or_none(Command.name % new_name)

        if check_command:
            return False
        else:
            self.name = new_name
            self.save()
            return True

    class Meta:
        indexes = ((("target", "name"), True),)


def get_all_targets():
    try:
        return [target for target in Target.select()]
    except Target.DoesNotExist:
        return []


def get_all_targets_as_dict():
    try:
        return [target.to_dict() for target in Target.select()]
    except Target.DoesNotExist:
        return []


def get_target(name):
    return Target.get_or_none(Target.name % name)


def add_target(name):
    if Target.get_or_none(Target.name % name):
        return False
    else:
        Target.create(name=name)
        return True


def delete_target(name):
    target = Target.get_or_none(Target.name % name)

    if target:
        target.delete_instance(recursive=True, delete_nullable=True)
        return True
    else:
        return False
