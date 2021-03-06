from tornado.websocket import WebSocketHandler
import string_to_date as std
import requests
from summarize import summarizeArr
from rasa.rasa import OSState, RasaResult
from rasa.Intents import IntentLookup

DURATION_CONST = 20

VOICEOSURL = "http://voiceos.localtunnel.me/parse"

class WebSocket(WebSocketHandler):

    eventLoop = None
    countDown = None
    uuid = None
    appInstance = None

    state = "greeting"
    osstate = None

    '''
    Crucial methods to WebSocket class
    '''
    def check_origin(self, origin):
        return True

    def open(self):
        print("SERVER: On new connection!")
        self.sayGreetingsAndOptions()

    def on_message(self, str):
        print("on_message: ", str)
        intentFromRasa = self.getIntent(str)

        if intentFromRasa.intent is "home":
            self.comebackhome()
        elif self.appInstance is not None:
            self.appInstance.handle(str)
        elif self.canLaunchAppFromIntent(intentFromRasa):
            self.launchAppFromIntent(intentFromRasa)
        else:
            self.speakMessage("I dont understand what you are talking about, ask my creator for options")

    def canLaunchAppFromIntent(self, intentFromRasa):
        return intentFromRasa.confidence > 0.4

    def launchAppFromIntent(self, intentFromRasa):
        print("launcAppFromIntent")
        self.appInstance = self.instanceFromIntent(intentFromRasa.intent)
        self.appInstance.onStart()


    def instanceFromIntent(self, intent):
        print("instanceFromIntent(): " + intent)
        module_name, class_name = IntentLookup[intent]
        module = __import__(module_name)
        class_ = getattr(module, class_name)
        return class_()

    def comebackhome(self):
        self.osstate = OSState.Home
        self.speakMessage("We are home now")
        self.appInstance = None

    def speakMessage(self, str):
        self.write_message(str)

    def getIntent(self, str):
        print("getIntent(): " + str)
        r = requests.post(VOICEOSURL, json={"q": str})
        response = r.json()
        print(response)
        rasaResponse = RasaResult(msg=str, intent=response['intent']['name'],
                                  confidence=response['intent']['confidence'])
        print("rasaResponse intent: " + rasaResponse.intent)
        return rasaResponse

    def handleWritingState(self, str):
        print("writing: ", str)
        if "endnote" in str:
            # self.write_message(note.lastNote)
            self.write_message("noted.")
            self.signalReady()
            return
        success = self.saveNote(str)
        print("writing success: ", success)
        if not success:
            self.write_message("could not write that last bit")

    def handleReadingState(self, str):
        print("reading: ", str)
        if str == "just now":
            summary = summarizeArr(self.notes.lastBunchofNotes())
            self.write_message(summary)
            self.signalReady()
            return
        dateRange = std.getDateUnix(str)
        if dateRange is None:
            self.write_message("Could not recognize that timeframe")
            return

        begin, end = dateRange
        print(begin, end)
        notes = self.notes.findInRange(begin, end)

        if not notes:
            self.write_message("Could not find notes in that time")
            return

        print(notes)
        self.write_message(summarizeArr(list(notes.values() ) ) )
        # expect str to be date time
        # when done reading, go to ready
        self.signalReady()

    def handleReadyState(self, str):
        if str == "read" or str == "read read":
            self.write_message("When would you like me to read?")
            self.state = "reading"
        elif str == "write" or str == "right" or str == "right right":
            self.write_message("What would you like to note?")
            self.state = "writing"
        else:
            self.write_message("say reed or write")
        return

    def on_close(self):

        print("Socket closed.")

    def sayGreetingsAndOptions(self):
        self.write_message("Hello! I am home")
        self.state = "ready"

    def signalReady(self):
        self.write_message("Would you like to read or would you like to write?")
        self.state = "ready"

    def saveNote(self, str):
        if not self.isValid(str):
            print("saveNote isLongEnough")
            return False
        self.notes.pushNote(str)
        print("saveNote pushedNote")
        return True

    def isValid(self, str):
        return len(str) > 10

    def clearEventLoop(self):
        self.eventLoop.stop()
        self.eventLoop = None

    def clearCountDown(self, socket):
        socket.countDown.stop()
        socket.countDown = None
