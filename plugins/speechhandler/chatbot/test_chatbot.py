# -*- coding: utf-8 -*-
import unittest
from jasper import testutils
from . import chatbot


class TestChatCleverbotPlugin(unittest.TestCase):
    def setUp(self):
        self.plugin = testutils.get_plugin_instance(cleverbot.CleverbotPlugin)

    def test_is_valid_method(self):
        self.assertTrue(self.plugin.is_valid("Talk to cleverbot."))
        self.assertTrue(self.plugin.is_valid("Rleverbot"))
        self.assertFalse(self.plugin.is_valid("What time is it?"))

    def test_handle_method(self):
        mic = testutils.TestMic(inputs=["How are you?", "Random response"])
        self.plugin.handle("Talk to cleverbot", mic)
        self.assertEqual(len(mic.outputs), 3)
        self.assertIn((mic.outputs[1], mic.outputs[2]), cleverbot)
