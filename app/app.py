from datetime import datetime
import json
import logging

import falcon

from db_helpers import blaster_db, command_db

_LOGGER = logging.getLogger(__name__)

## Generic helper functions


def get_blaster(attr, value):
    if attr.lower() == "name":
        blaster = blaster_db.get_blaster_by_name(value)
    elif attr.lower() == "ip":
        blaster = blaster_db.get_blaster_by_ip(value)
    elif attr.lower() == "mac":
        blaster = blaster_db.get_blaster_by_mac(value)
    else:
        raise falcon.HTTPBadRequest(
            description="Invalid blaster attribute. Use attribute of name, ip, or mac for Blaster."
        )

    if blaster:
        return blaster
    else:
        raise falcon.HTTPBadRequest(
            description="Value of '"
            + value
            + "' not found for Blaster '"
            + attr
            + "' attribute"
        )


def get_target(target_name):
    target = command_db.get_target(target_name)

    if target:
        return target
    else:
        raise falcon.HTTPBadRequest(
            description="Target '" + target_name + "' not found"
        )


def get_command(target_name, command_name):
    command = get_target(target_name).get_command(command_name)

    if command:
        return command
    else:
        raise falcon.HTTPBadRequest(
            description="Command '"
            + command_name
            + "' not found for Target '"
            + target_name
            + "'"
        )


## REST Server block

## Middleware Class to open and close DB properly
class MiddlewareDatabaseHandler(object):
    def process_request(self, req, resp):
        command_db.commands_db.connect()
        command_db.Command.create_table(safe=True)
        command_db.Target.create_table(safe=True)

        blaster_db.blasters_db.connect()
        blaster_db.Blaster.create_table(safe=True)

    def process_response(self, req, resp, resource, req_succeeded):
        command_db.commands_db.close()
        blaster_db.blasters_db.close()


# Resource to discover devices
# /discoverblasters
# GET adds all newly discovered devices to DB and returns number of new RM devices found, required when adding a new device to the network
# NOTE: Only retains devices of type RM


class DiscoverRESTResource(object):
    def on_get(self, req, resp):
        resp.body = json.dumps(blaster_db.get_new_blasters(at_ip=req.get_param("at_ip", required=False)))


# Resource to interact with all discovered Blasters
# /blasters
# GET returns Blasters list
# POST sends command to all Blasters


class BlastersRESTResource(object):
    def on_get(self, req, resp):
        resp.body = json.dumps({"blasters": blaster_db.get_all_blasters_as_dict()})

    def on_post(self, req, resp):
        target_name = req.get_param("target_name", required=True)
        command_name = req.get_param("command_name", required=True)

        target = command_db.get_target(target_name)

        if target:
            command = target.get_command(command_name)

            if command:
                blaster_db.send_command_to_all_blasters(command)
            else:
                raise falcon.HTTPInvalidParam(
                    "Command of '"
                    + command_name
                    + "' does not exist for Target '"
                    + target_name
                    + "'.",
                    "command_name",
                )

        else:
            raise falcon.HTTPInvalidParam(
                "Target of '" + target_name + "' does not exist.", "target_name"
            )


# Resource to return all Targets
# /targets
# GET returns all Targets


class TargetsRESTResource(object):
    def on_get(self, req, resp):
        resp.body = json.dumps({"targets": command_db.get_all_targets_as_dict()})


# Resource to return all Commands
# /commands
# GET returns all Commands


class CommandsRESTResource(object):
    def on_get(self, req, resp):
        targets = command_db.get_all_targets()
        targets_to_ret = command_db.get_all_targets_as_dict()
        for x in range(len(targets)):
            targets_to_ret[x]["commands"] = targets[x].get_all_commands_as_dict()

        resp.body = json.dumps({"targets": targets_to_ret})


# Resource to interact with a specific Blaster
# /blasters/{attr}/{value}
# GET returns Blaster info
# PUT creates/updates Blaster name
# POST sends command to Blaster
# DELETE deletes Blaster


class BlasterRESTResource(object):
    def on_get(self, req, resp, attr, value):
        resp.body = json.dumps(get_blaster(attr, value).to_dict())

    def on_put(self, req, resp, attr, value):
        new_name = req.get_param("new_name", required=True)

        if not get_blaster(attr, value).put_name(new_name):
            raise falcon.HTTPConflict(
                description="Blaster '" + new_name + "' already exists"
            )

    def on_post(self, req, resp, attr, value):
        target_name = req.get_param("target_name", required=True)
        command_name = req.get_param("command_name", required=True)

        blaster = get_blaster(attr, value)
        target = command_db.get_target(target_name)

        if target:
            command = target.get_command(command_name)

            if command:
                blaster.send_command(command)
            else:
                raise falcon.HTTPBadRequest(
                    description="Command '"
                    + command_name
                    + "' not found for Target '"
                    + target_name
                    + "'"
                )
        else:
            raise falcon.HTTPBadRequest(
                description="Target '" + target_name + "' not found"
            )

    def on_delete(self, req, resp, attr, value):
        get_blaster(attr, value).delete_instance()


# Resource to get status of a specific Blaster
# /blasters/{attr}/{value}/status
# GET returns Blaster status


class BlasterStatusRESTResource(object):
    def on_get(self, req, resp, attr, value):
        if not get_blaster(attr, value).available():
            raise falcon.HTTPGatewayTimeout(
                "Blaster with attribute '"
                + attr
                + "' of value '"
                + value
                + "' did not respond to availability check within timeout window"
            )


# Resource to interact with a specific Target
# /targets/{target_name}
# PUT creates target
# PATCH updates target
# DELETE deletes target and associated commands


class TargetRESTResource(object):
    def on_put(self, req, resp, target_name):
        if not command_db.add_target(target_name):
            raise falcon.HTTPConflict(
                description="Target '" + target_name + "' already exists"
            )

    def on_patch(self, req, resp, target_name):
        new_name = req.get_param("new_name", required=True)

        if not get_target(target_name).update_name(new_name):
            raise falcon.HTTPConflict(
                description="Target '" + new_name + "' already exists"
            )

    def on_delete(self, req, resp, target_name):
        if not command_db.delete_target(target_name):
            raise falcon.HTTPBadRequest(
                description="Target '" + target_name + "' not found"
            )


# Resource to get Target specific Commands
# /targets/{target_name}/commands
# GET returns all Commands for Target 'target_name'


class TargetCommandsRESTResource(object):
    def on_get(self, req, resp, target_name):
        target = command_db.get_target(target_name)

        if target:
            resp.body = json.dumps({"commands": target.get_all_commands_as_dict()})
        else:
            raise falcon.HTTPBadRequest(
                description="Target '" + target_name + "' not found"
            )


# Resource to interact with Target specific Command
# /targets/{target_name}/commands/{command_name}
# GET returns command value
# PUT creates/updates command value - uses "value" param if exists otherwise learns command from blaster with blaster_attr/blaster_value pair
# PATCH updates command name to new_name
# DELETE deletes command


class TargetCommandRESTResource(object):
    def on_get(self, req, resp, target_name, command_name):
        resp.body = json.dumps(get_command(target_name, command_name).to_dict())

    def on_put(self, req, resp, target_name, command_name):
        value = req.get_param("value")
        blaster_attr = req.get_param("blaster_attr")
        blaster_value = req.get_param("blaster_value")

        target = get_target(target_name)

        if value:
            target.put_command(command_name, value)
        else:
            if blaster_attr is None or blaster_value is None:
                raise falcon.HTTPBadRequest(
                    description="If attempting to learn a command, you must specify blaster_attr of ip, mac, or name and corresponding blaster_value. You can also specify the IR sequence directly with the value parameter"
                )
            else:
                blaster = get_blaster(blaster_attr, blaster_value)
                value = blaster.get_command()
                if value:
                    target.put_command(command_name, value)
                else:
                    raise falcon.HTTPGatewayTimeout(
                        description="Blaster did not receive any IR signals to learn"
                    )

    def on_patch(self, req, resp, target_name, command_name):
        new_name = req.get_param("new_name", required=True)

        if not get_command(target_name, new_name).update_name(new_name):
            raise falcon.HTTPConflict(
                description="Command '"
                + new_name
                + "' already exists for Target'"
                + target_name
                + "'"
            )

    def on_delete(self, req, resp, target_name, command_name):
        get_command(target_name, command_name).delete_instance()


# falcon.API instances are callable WSGI apps
app = falcon.API(middleware=MiddlewareDatabaseHandler())
app.req_options.auto_parse_form_urlencoded = True

# Resources are represented by long-lived class instances
discover = DiscoverRESTResource()
blasters = BlastersRESTResource()
blaster = BlasterRESTResource()
blaster_status = BlasterStatusRESTResource()
targets = TargetsRESTResource()
target = TargetRESTResource()
target_commands = TargetCommandsRESTResource()
target_command = TargetCommandRESTResource()
commands = CommandsRESTResource()

# All supported routes.
app.add_route("/discoverblasters", discover)
app.add_route("/blasters", blasters)
app.add_route("/targets", targets)
app.add_route("/commands", commands)
app.add_route("/blasters/{attr}/{value}", blaster)
app.add_route("/blasters/{attr}/{value}/status", blaster_status)
app.add_route("/targets/{target_name}/commands/{command_name}", target_command)
app.add_route("/targets/{target_name}/commands", target_commands)
app.add_route("/targets/{target_name}", target)

# Initialize blasters DB by discovering blasters
blaster_db.blasters_db.connect()
blaster_db.Blaster.create_table(safe=True)
blaster_db.get_new_blasters(timeout=3)
blaster_db.blasters_db.close()

### Data migrations

### Command DB Migrations

command_db.commands_db.connect()
if not command_db.Command.table_exists():
    command_db.Command.create_table(safe=True)

# Migrate from hex to base64 for IR values
if not command_db.Encoding.table_exists():
    for command in command_db.Command.select():
        try:
            _bytes = blaster_db.dec_hex(command.value)
            command.value = blaster_db.enc_b64(_bytes)
            command.save()
        except ValueError:
            command_db.commands_db.close()
            break

    command_db.Encoding.create_table(safe=True)
    command_db.Encoding.create(encoding="base64", active_since=datetime.utcnow())

if not command_db.commands_db.is_closed():
    command_db.commands_db.close()

### Blaster DB Migrations

# blaster_db.blasters_db.connect()

# blaster_db.blasters_db.close()
