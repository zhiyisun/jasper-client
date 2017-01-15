import snowboydetect
import logging
from jasper import plugin
from jasper import paths

class SnowboySTTPlugin(plugin.STTPlugin):
    """
    Speech-To-Text passive mode implementation which relies on the Snowboy hotword detection.

    The hotword detection model is located in ./resources/*.pmdl or *umdl

    The name of the model is defined in ~/.jasper/profile.yml

    Excerpt from sample profile.yml:

        ...
        snowboy:
          model: [modle_a, model_b]
          sensitivity: 0.5
          audio_gain: 1

    """

    def __init__(self, *args, **kwargs):
        plugin.STTPlugin.__init__(self, *args, **kwargs)

        self._logger = logging.getLogger(__name__)

        try:
            decoder_model = self.profile['snowboy']['model']
            tm = type(decoder_model)
            if tm is not list:
                decoder_model = [decoder_model]
            decoder_model = [paths.PLUGIN_PATH + "/stt/snowboy-stt/resources/" + model_name for model_name in decoder_model]
        except KeyError:
            decoder_model = [paths.PLUGIN_PATH + "/stt/snowboy-stt/resources/Jasper.pmdl"]

        try:
            sensitivity = self.profile['snowboy']['sensitivity']
            ts = type(sensitivity)
            if ts is not list:
                sensitivity = [sensitivity]
        except KeyError:
            sensitivity = [0.5]

        model_str = ",".join(decoder_model)

        resource = paths.PLUGIN_PATH + "/stt/snowboy-stt/resources/common.res"

        self.detector = snowboydetect.SnowboyDetect(
            resource_filename=resource.encode(), model_str=model_str.encode())

        try:
            audio_gain = self.profile['snowboy']["audio_gain"]
        except KeyError:
            audio_gain = 1

        self.detector.SetAudioGain(audio_gain)
        self.num_hotwords = self.detector.NumHotwords()

        if len(decoder_model) > 1 and len(sensitivity) == 1:
            sensitivity = sensitivity*self.num_hotwords
        if len(sensitivity) != 0:
            if self.num_hotwords != len(sensitivity):
                self._logger.critical('number of hotwords in decoder_model (%d) ' \
                                        'and sensitivity (%d) does not match' \
                                        % (self.num_hotwords, len(sensitivity)))
        sensitivity_str = ",".join([str(t) for t in sensitivity])
        if len(sensitivity) != 0:
            self.detector.SetSensitivity(sensitivity_str.encode())

    def transcribe(self, fp):
        fp.seek(44)
        data = fp.read()

        ans = self.detector.RunDetection(data)

        self._logger.debug('Snowboy detection result: (%d)' % ans)

        if ans == -1:
            self._logger.warning('Error initializing streams or reading audio data')
        elif ans > 0:
            return [self._vocabulary_phrases[-1]]

        return []
