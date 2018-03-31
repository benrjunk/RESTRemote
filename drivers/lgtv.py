import json
from threading import Event
from ws4py.client.threadedclient import WebSocketClient


class LGTV(WebSocketClient):

    def __init__(self, config):
        self.config = config
        self.isOpened = False
        self.curID = 0
        self.callbacks = {}
        super(LGTV, self).__init__("ws://" + config['hostName'] + ':' +
            str(config['port']),  exclude_headers=["Origin"])
        print 'Loaded ', __name__, 'driver'

    def opened(self):
        self.isOpened = True
        self.sendCommand('register', 'register', None,
            self.config['registerCommand'], False)

    def closed(self, code, reason=None):
        self.isOpened = False
        print "LG TV Connection closed", code, reason

    def received_message(self, data):
        message = json.loads(str(data))
        callback = self.callbacks.get(message['id'])
        if callback:
            callback['data'] = message
            callback['event'].set()

    def sendCommand(self, prefix, type, uri, payload=None, shouldWait=True):
        if not self.isOpened:
            try:
                self.connect()
            except:
                raise Exception('Driver ' + __name__ +
                    ' cannot connect to device')

        id = prefix + str(self.curID)
        message = {
            'type': type,
            'id': id
        }

        if payload:
            message['payload'] = payload

        if uri:
            message['uri'] = 'ssap://' + uri

        self.send(json.dumps(message))
        self.curID += 1
        event = Event()
        callback = {
            'event': event,
            'data': {}
        }

        self.callbacks[id] = callback

        if shouldWait:
            event.wait(self.config['timeout'])
            return callback['data']

        return ''

    def getData(self, commandName, args=None):
        if commandName == 'commands':
            commandList = []
            for commandName, command in self.config['commands'].iteritems():
                commandList.append({
                    'name': commandName,
                    'method': 'GET' if command.get('result', False) else 'PUT'
                })
            return {
                'driver': __name__,
                'commands': commandList
                }

        command = self.config['commands'][commandName]
        if not command.get('result'):
            raise Exception('Invalid command for ' + __name__ +
                ' and method: ' + commandName)

        return {
            'driver': __name__,
            'command': commandName,
            'output': self.sendCommand('', 'request', command['uri'])
        }

    def executeCommand(self, commandName, args=None):
        if commandName == 'toggle_mute':
            output = self.getData('status')

            if 'error' in output['output']:
                return output

            return self.executeCommand('mute',
                'off' if output['output']['payload']['mute'] else 'on')

        command = self.config['commands'][commandName]
        if command.get('result'):
            raise Exception('Invalid command for ' + __name__ +
                ' and method: ' + commandName)

        argKey = command.get('argKey')
        argData = None
        if args:
            if not argKey:
                raise Exception('Command in ' + __name__ +
                    ': ' + commandName + ' isn''t configured for arguments')

            if command.get('acceptsBool'):
                argData = { argKey: args == 'true' or args == 'on' }
            else:
                argData = { argKey: args }
        elif argKey:
            raise Exception('Command in ' + __name__ +
                ': ' + commandName + ' expects for arguments')

        result = {
            'driver': __name__,
            'command': commandName,
            'output': self.sendCommand('', 'request', command['uri'], argData),
            'args': argData
        }

        return result