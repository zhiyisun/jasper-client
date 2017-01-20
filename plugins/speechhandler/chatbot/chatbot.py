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

        mic.say('Yes, sir.')
        questions = ['Hello!']
        question = ''.join(questions)
        cleverbot = Cleverbot('Jasper')
        answer = cleverbot.ask(question);

        while True:
            mic.say(answer)
            if any(self.gettext('BYE').upper() in question.upper() for question in questions):
                break
            while True:
                questions = mic.active_listen()
                #question = ''.join(questions)
                if questions:
                    break
            answer = cleverbot.ask(questions[0]);

    def is_valid(self, text):
        """
        Returns True if the input is related to jokes/humor.

        Arguments:
        text -- user-input, typically transcribed speech
        """
        return any(phrase in text.upper() for phrase in self.get_phrases())
