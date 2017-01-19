# -*- coding: utf-8 -*-
import logging
from cleverbot import Cleverbot
from jasper import plugin

class ChatbotPlugin(plugin.SpeechHandlerPlugin):
    def __init__(self, *args, **kwargs):
        super(ChatbotPlugin, self).__init__(*args, **kwargs)

        self._logger = logging.getLogger(__name__)

        try:
            language = self.profile['language']
        except KeyError:
            language = 'en-US'

    def get_phrases(self):
        #Set wit.ai to make "CLEVER BOT" as "CLEVERBOT"
        return [self.gettext("CLEVERBOT"), self.gettext("BOT"), self.gettext("CHAT")]

    def handle(self, text, mic):
        """
        Launch a chatbot conversation.

        Arguments:
        text -- user-input, typically transcribed speech
        mic -- used to interact with the user (for both input and output)
        """
        questions = ['Hello!']
        question = ''.join(questions)
        cleverbot = Cleverbot()
        answer = cleverbot.ask(question);

        while True:
            mic.say(answer)
            if self.gettext('BYE').upper() in question.upper():
                break
            while True:
                questions = mic.active_listen()
                question = ''.join(questions)
                if question:
                    break
            answer = cleverbot.ask(question);

    def is_valid(self, text):
        """
        Returns True if the input is related to jokes/humor.

        Arguments:
        text -- user-input, typically transcribed speech
        """
        return any(phrase in text.upper() for phrase in self.get_phrases())
