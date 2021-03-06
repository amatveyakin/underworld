import sys
import time
import subprocess
import threading
import config
import gameengine
import playerstate as PlayerState
import json
from options import parseOptions
import importlib
import io

class Unbuffered:
    ''' Unbuffered output wrapper '''
    def __init__(self, stream):
        self.stream = stream
    def write(self, data):
        try:
            self.stream.write(data)
            self.stream.flush()
        except Exception:
            pass
    def __getattr__(self, attr):
        return getattr(self.stream, attr)

class IO:
    __slots__ = ["stdin", "stdout"]


class MutexLocker:
    ''' Simple mutex lock object '''
    def __init__(self, mutex):
        self.mutex = mutex
    def __enter__(self):
        self.mutex.acquire()
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self.mutex.release()

def log_function(f):
    ''' A decorator to log general function calls '''
    def decorator(*args, **kwargs):
        print(f.__name__, " ", args, ", ", kwargs)
        return f(*args, **kwargs)
    return decorator


class Client:
    ''' Represents the Player object in underworld server '''
    @property
    def state(self):
        ''' state property setter ''' 
        return self._state

    @state.setter
    def state(self, value):
        ''' state property getter ''' 
        assert(not PlayerState.isFinal(self._state) or self._state == value)
        if PlayerState.isFinal(value):
            if self._state != value:
                print("Player ", self.iPlayer + 1, " reaches his destiny: ", value)
                if value == PlayerState.KICKED and self.reason:
                    print(" Reason: ", self.reason)
                self.cleanup( )
        if value != self.state:
            if value == PlayerState.THINKING:
                self.startThinkingEvent.set( )
            else:
                self.startThinkingEvent.clear( )
                if callable(self.onReady):
                    self.onReady(self)
        self._state = value

    def __init__(self, playerDesc, iPlayer, onReady=None):
        ''' Initialize a player 
                Args:
                    exeName - the executable name ( should not spawn new processes )
                    iPlayer - player's unique ID
                    onReady - the callback which is called when the player is ready
                        onReady(player): player is a Client object
        '''
        self.thread = threading.Thread(target=self.playerLoop)
        self.thread.setDaemon(True)
        self.lock = threading.RLock()
        self.onReady = onReady
        self._state = PlayerState.NOT_INITIATED
        self.startThinkingEvent = threading.Event( )
        self.iPlayer = iPlayer
        self.messageFromPlayer = ""
        self.receivedLinesNo = 0
        self.reason = ""
        self.playerDesc = playerDesc
        self.initIO( )
    def initIO(self):
        self.io = IO( )
        self.process = None
        self.sock = None
        if self.playerDesc["type"] == "process":
            stderrDesc = None
            try:
                stderrDesc = open(self.playerDesc["stderr"], "wt");
            except Exception:
                pass
            self.process = subprocess.Popen(self.playerDesc["exeName"].split(), 
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,stderr=stderrDesc)
            self.io.stdin = io.TextIOWrapper(self.process.stdin)
            self.io.stdout = io.TextIOWrapper(self.process.stdout)
            self.io.stdin = Unbuffered(self.io.stdin)
        elif self.playerDesc["type"] == "socket":
            import socket
            supprotedFamilies = { "inet": (socket.AF_INET, tuple),
                                  "unix": (socket.AF_UNIX, lambda x: x) }
            familyDesc = supprotedFamilies[self.playerDesc["family"]]
            self.sock = socket.socket(familyDesc[0], socket.SOCK_STREAM)
            self.sock.connect(familyDesc[1](self.playerDesc["addr"]))
            self.io.stdin = Unbuffered(self.sock.makefile("w"))
            self.io.stdout = self.sock.makefile("r")
        else:
            assert False, "Player type should be one of [process, socket]"
            
    def handshake(self):
        ''' Perform handshake. If it fails, kick the player '''
        answer = self.io.stdout.readline().strip()
        with MutexLocker(self.lock):
            if answer != config.handshakeAck:
                self.reason = "Handshake failed"
            if self.state == PlayerState.NOT_INITIATED:
                if answer == config.handshakeAck:
                    self.state = PlayerState.READY
                else:
                    self.state = PlayerState.KICKED
    def playerLoop(self):
        ''' Player's thread main function.
            Handshakes, then repeatedly performs the IO while player is in play.
        '''
        try:
            self.handshake()
            while not self.io.stdout.closed:
                if not PlayerState.inPlay(self.state):
                    break
                self.startThinkingEvent.wait( )
                receivedMessage = self.io.stdout.readline(config.maxRecvLineLen)
                with MutexLocker(self.lock):
                    if receivedMessage.strip() == "end":
                        self.state = PlayerState.READY
                    else:
                        if not self._isMessageSecure(receivedMessage):
                            print(recievedMessage)
                            self.kick("Spam protection")
                            break
                        self.messageFromPlayer += receivedMessage
                        self.receivedLinesNo += 1
        except Exception:
            pass
        self.kick("Disconnected")
    def _isMessageSecure(self, message):
        return self.receivedLinesNo < config.maxRecvLinesNo and \
            len(self.messageFromPlayer) + len(message) < config.maxRecvSize and \
            ( message[-1:] == "\n" or not message )

    def run(self):
        ''' Start player's IO '''
        self.thread.start()

    def kick(self, reason="for nothing"):
        ''' Kick the player '''
        with MutexLocker(self.lock):
            if self.state != PlayerState.KICKED:
                self.reason = reason
            self.state = PlayerState.KICKED
    def __repr__(self):
        ''' String representation - just the player's id '''
        return str(self.iPlayer + 1)
    def cleanup(self):
        if self.process:
            self.process.terminate( )
        if self.sock:
            self.sock.close( )

def runGame(game, playerList, options):
    thinkingSetLock = threading.RLock( )
    thinkingSet = set( )
    everyoneReadyEvent = threading.Event( )
    def onClientStopThinking(client):
        with MutexLocker(thinkingSetLock):
           if client in thinkingSet:
               thinkingSet.remove(client)
           if thinkingSet == set( ):
               everyoneReadyEvent.set( )

    thinkingSet = set(playerList)
    for player in playerList:
        player.onReady = onClientStopThinking
        player.io.stdin.write(config.handshakeSyn + "\n")
        player.run()

    initialMessages = game.initialMessages()
    everyoneReadyEvent.wait(config.turnDurationInSec)
    with MutexLocker(thinkingSetLock):
        thinkingSet = set( )
        for (player, message) in zip(playerList, initialMessages):
            with MutexLocker(player.lock):
                if player.state == PlayerState.READY:
                    player.state = PlayerState.THINKING
                    thinkingSet.add(player)
                    player.io.stdin.write(message)
                else:
                    player.kick("Handshake timeout")
        everyoneReadyEvent.clear( )

    while True:
        everyoneReadyEvent.wait(config.turnDurationInSec)
        playerMoves = []
        for player in playerList:
            with MutexLocker(player.lock):
                if player.state == PlayerState.THINKING:
                    player.kick("Timeout")
                    playerMoves.append(None)
                else:
                    playerMoves.append(player.messageFromPlayer)
                    player.messageFromPlayer = ""
                    player.receivedLinesNo = 0

        engineReply = game.processTurn(playerMoves)
        #print("Let the turn ", game.turn, " end!")
        somebodyStillPlays = False
        with MutexLocker(thinkingSetLock):
            thinkingSet = set( )
            for (player, reply) in zip(playerList, engineReply):
                with MutexLocker(player.lock):
                    if not PlayerState.isFinal(player.state):
                        player.state = reply[0]
                        somebodyStillPlays |=  PlayerState.inPlay(player.state)
                        if player.state == PlayerState.THINKING:
                            thinkingSet.add(player)
                            player.io.stdin.write(reply[1])
            everyoneReadyEvent.clear( )
        if not somebodyStillPlays:
            if options.results:
                game.saveResults(options.results)
            return
def main():
    game = gameengine.Game()
    options = parseOptions( )
    fGame = open(options.game)
    gameDesc = json.load(fGame)
    fGame.close( )

    playerList = []
    playerDescs = gameDesc["players"]
    playerNum = len(playerDescs)

    for (playerDesc, iPlayer) in zip(playerDescs, range(playerNum)):
        playerList.append(Client(playerDesc, iPlayer))

    game.setClients(playerList, gameDesc)
    plugin = None
    try:
        if options.plugin != "":
            pluginModule = importlib.import_module("plugins." + options.plugin)
            plugin = pluginModule.Plugin(game, options.plugin_args)
        if hasattr(plugin, "__enter__"):
            with plugin:
                runGame(game, playerList, options)
        else:
            runGame(game, playerList, options)
    except:
        # this should not happen in real life, but if you hit Ctrl+C, you probably get here
        for player in playerList:
            player.cleanup( )
        print("Game stopped!")
        raise
if __name__ == "__main__":
    main()
