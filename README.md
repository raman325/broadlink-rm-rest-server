# Broadlink RM REST Server

## Purpose
This Python based web server provides REST interactivity with any local [Broadlink RM*](http://www.ibroadlink.com/rm/) type IR/RF blasters.

NOTE: To connect your RM devices to your network without downloading the Broadlink mobile app, refer to the [python-broadlink Example Use](https://github.com/mjg59/python-broadlink#example-use) instructions.

Please read the [Notes](#notes) section before using. Refer to the [API](#api) section to learn how this server can be used.

## Intro
There are three objects that this application manages:
- *Blasters* are the Broadlink devices on your network which can transmit IR/RF signals
- *Targets* are aliases for the devices you want to control using *blasters*
- *Commands* are aliases for raw IR/RF commands

The basic process to use this app is:
1. Discover all *blasters* on your network by making a `GET` request on the `/discoverblasters` endpoint (this is done on app initialization so it's only required if the initial discovery failed or a new device gets added to the network). This will add them to the application's database. You can assign a friendly name to each one or use MAC/IP addresses to reference them after they have been discovered.
2. Create a *target* for every device you want to control using your *blasters* by making a `PUT` request on the `/targets/<target_name>` endpoint
3. For each *target*, you can either use a specific *blaster* to learn a *command* by making a `PUT` request on the `/targets/<target_name>/commands/<command_name>?blaster_attr=<blaster_attr>&blaster_value=<blaster_value>` endpoint and pressing the corresponding key on your remote while pointing at the *blaster* specified, or you can create a *command* from a base64 value if you already know the raw *command* by making a `PUT` request on the `/targets/<target_name>/commands/<command_name>?value=<value>` endpoint
4. Repeat 2 + 3 until all *targets* and *commands* have been added to the database.
5. From now on, you can reference *blasters*, *targets*, and *commands* by the aliases you created.

## Setup

### Docker Instructions

To create and start container:
```docker run -d --name broadlink_rm_rest --restart unless-stopped -p 8000:8000 -v </local/path/to/data>:/app/data raman325/broadlink-rm-rest```

> I have tested this on my Synology Diskstation NAS and have run into problems with my network configuration that prevented python-broadlink from being able to discover blasters. To resolve this problem, I switched from bridged network mode to host network mode by changing `-p 8000:8000` in the above command to `--network host`.

### Local Setup
1. Clone this repo.
2. `cd broadlink-rm-rest/`
2. Install dependencies via pip: `pip3 install -r requirements.txt`
3. `cd app/`
5. `gunicorn -b 0.0.0.0:8000 app:app`

Your databases will be available in the app/data folder.

#### Environment Variables
To override the default values, add `-e <NAME>=<VALUE>` for each corresponding parameter name and value.

Parameter Name | Default Value | Description
-------------- | ------- | -----------
`HOST` | `0.0.0.0` | Specifies the HOST that will be used to access the REST server. Default exposes the server to the entire network. To provide local access only, use `127.0.0.1` or `localhost` instead.
`PORT` | `8000` | Specifies the port that the container will listen on. Note that if this is changed, the `create` command should be updated accordingly (e.g. `-p <Public Port>:<PORT>`).
`DISCOVERY_TIMEOUT` | `5` | Specifies the number of seconds (supports floats) that the application will wait for blasters to respond to discovery requests.
`HEALTH_TIMEOUT` | `1` | Specifies the number of seconds (supports floats) that the application will wait for the specified Broadlink blaster to confirm availability before timing out.

#### Persist DB files
In the `docker run` command listed above, the DB files (commands.db and blasters.db) will be persisted in /local/path/to/data on your host server.

## API
- An `HTTP 200 OK` will be returned if the call was successful.
- An `HTTP 400 BAD REQUEST` will be returned if a request was malformed or if a given resource was not found.
- An `HTTP 409 CONFLICT ` will be returned if a request attempted to create/update a resource that conflicts with an existing resource.
- All responses are in JSON format.

Endpoint | HTTP Method | Description
-------- | ----------- | -----------
`/discoverblasters` | `GET` | Discovers all new Broadlink RM blasters and adds them to the database (Note: blasters must be in the database before they can be used by the application, and they must be on and connected to the local network to be discoverable. You can add the Broadlink devices to your network using the instructions [here](https://github.com/mjg59/python-broadlink#example-use)). Blasters will be added to the database unnamed, so it's recommended to use `PUT /blasters/<attr>/<value>?new_name=<new_name>` to set a friendly name for each blaster.<br><br>NOTE: Discovery will also update blaster IP addresses when applicable.
`/blasters` | `GET` | Gets all blasters (only returns blasters that have already been discovered once). | 
`/blasters?target_name=<target_name>&command_name=<command_name>` | `POST` | Sends command `<command_name>` for target `<target_name>` to all blasters.
`/blasters/<attr>/<value>` | `GET` | Gets specified blaster. `<attr>` should be either `ip`, `mac`, or `name`, and `<value>` should be the corresponding value.
`/blasters/<attr>/<value>` | `DELETE` | Deletes specified blaster. `<attr>` should be either `ip`, `mac`, or `name`, and `<value>` should be the corresponding value.
`/blasters/<attr>/<value>?new_name=<new_name>` | `PUT` | Sets blasters name to `<new_name>`, replacing an existing name if it already exists. `<attr>` should be either `ip`, `mac`, or `name`, and `<value>` should be the corresponding value.<br><br>NOTE: If blaster lookup via IP isn't working, try to rediscover blasters using /discoverblasters which will update IP addresses to their latest.
`/blasters/<attr>/<value>?target_name=<target_name>&command_name=<command_name>` | `POST` | Sends command `<command_name>` for target `<target_name>` via specified blaster. `<attr>` should be either `ip`, `mac`, or `name`, and `<value>` should be the corresponding value.<br><br>NOTE: If blaster lookup via IP isn't working, try to rediscover blasters using /discoverblasters which will update IP addresses to their latest.
`/blasters/<attr>/<value>/status` | `GET` | Verifies availability of specified blaster. `<attr>` should be either `ip`, `mac`, or `name`, and `<value>` should be the corresponding value. Returns an `HTTP 200 OK` if the blaster responds to status check within the `BROADLINK_STATUS_TIMEOUT` timeout window, else returns an `HTTP 408 GATEWAY TIMEOUT`.
`/commands` | `GET` | Gets all commands.
`/targets` | `GET` | Gets all targets.
`/targets/<target_name>` | `PUT` | Creates target `<target_name>`.
`/targets/<target_name>` | `DELETE` | Deletes target `<target_name>` and all of its associated commands.
`/targets/<target_name>?new_name=<new_name>` | `PATCH` | Updates the name of `<target_name>` to `<new_name>`.
`/targets/<target_name>/commands` | `GET` | Gets all commands for target `<target_name>`.
`/targets/<target_name>/commands/<command_name>` | `GET` | Gets command `<command_name>` for target `<target_name>`.
`/targets/<target_name>/commands/<command_name>` | `DELETE` | Deletes command `<command_name>` for target `<target_name>`.
`/targets/<target_name>/commands/<command_name>?new_name=<new_name>` | `PATCH` | Updates command name of  `<command_name>` for target `<target_name>` to `<new_name>`.
`/targets/<target_name>/commands/<command_name>?blaster_attr=<blaster_attr>&blaster_value=<blaster_value>` | `PUT` | Learns command `<command_name>` for target `<target_name>` using specified blaster. `<blaster_attr>` should be either `ip`, `mac`, or `name` and `<blaster_value>` should be the corresponding value. If `<command_name>` already exists, it will be replaced with the new value. Waits for ~10 seconds to detect an input signal from the blaster specified before timing out and consequently returning an `HTTP 408 GATEWAY TIMEOUT`.<br><br>NOTE: If blaster lookup via IP isn't working, try to rediscover blasters using /discoverblasters which will update IP addresses to their latest.
`/targets/<target_name>/commands/<command_name>?value=<value>` | `PUT` | Sets the value command `<command_name>` for target `<target_name>` to `<value>`. If `<command_name>` already exists, it will be replaced with the new value. If you plan to use this method, you should look at the code to see how values are encoded, or use existing command values in the database.

## Notes
1. The blasters and target/commands databases, blasters.db and commands.db, are independent files because  they are completely unrelated. As long as you are using Broadlink RM* blasters, you can use the same commands.db for every instance of the application.
2. The database files are in SQLite3 format and can be hand edited if needed. I use [SQLiteStudio](https://sqlitestudio.pl/index.rvt).
3. To reset all settings/data, simply stop the container/app, delete the two .db files, and restart.
4. This was tested on an RM3 Mini but should theoretically support any RM device that [python-broadlink](https://github.com/mjg59/python-broadlink) does.

## Shout outs
1. @mjg59 for [python-broadlink](https://github.com/mjg59/python-broadlink)
2. @falconry for [falcon](https://github.com/falconry/falcon). This is my first REST app and [falcon](https://github.com/falconry/falcon) made it a breeze.
3. @coleifer for [peewee](https://github.com/coleifer/peewee) which made persisting the data simple.
4. My wife for putting up with my late night/weekend experimentation.


## TODO
1. Test cases
2. Authentication
3. Mechanism to export/import commands
4. Mechanism to share commands
