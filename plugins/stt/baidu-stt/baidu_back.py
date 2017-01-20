import logging
import requests
import wave
import json
from jasper import plugin

try: # try to use python2 module
    from urllib import urlencode
    from urllib2 import Request, urlopen, URLError
except ImportError: # otherwise, use python3 module
    from urllib.request import Request, urlopen
    from urllib.error import URLError
    from urllib.parse import urlencode


# There seems to be no way to get language setting of the defined app
# Last updated: April 06, 2016
SUPPORTED_LANG = (
    'de',
    'en',
    'es',
    'et',
    'fr',
    'it',
    'nl',
    'pl',
    'pt',
    'ru',
    'sv'
)


class BaiduSTTPlugin(plugin.STTPlugin):
    """
    Speech-To-Text implementation which relies on the Baidu Speech API.

    This implementation requires an Baidu Access Token to be present in
    profile.yml. Please sign up at https://yuyin.baidu.com and copy your instance
    token, which can be found under Settings in the Wit console to your
    profile.yml:
        ...
        stt_engine: baidu-stt
        baidu-stt:
          app_key:    xxxxxxxxxx
          secret_key: yyyyyyyyyy
    """

    def __init__(self, *args, **kwargs):
        """
        Create Plugin Instance
        """
        plugin.STTPlugin.__init__(self, *args, **kwargs)
        self._logger = logging.getLogger(__name__)
        self.app_key = self.profile['baidu-stt']['app_key']
        self.secret_key = self.profile['baidu-stt']['secret_key']

        try:
            language = self.profile['language']
        except KeyError:
            language = 'en-US'
        if language.split('-')[0] not in SUPPORTED_LANG:
            raise ValueError('Language %s is not supported.',
                             language.split('-')[0])

    @property
    def language(self):
        """
        Returns selected language
        """
        return self._language

    def token(self, app_key, secret_key):
        """
        Sets property token
        """
        data = {'grant_type': 'client_credentials', 'client_id': app_key, 'client_secret': secret_key}
        r = requests.post("https://openapi.baidu.com/oauth/2.0/token", data=json.dumps(data))
        try:
            r.raise_for_status()
            text = r.json()['access_token']
        except requests.exceptions.HTTPError:
            self._logger.critical('Request failed with response: %r',
                                  r.text,
                                  exc_info=True)
            return []
        except requests.exceptions.RequestException:
            self._logger.critical('Request failed.', exc_info=True)
            return []
        except ValueError as e:
            self._logger.critical('Cannot parse response: %s',
                                  e.args[0])
            return []
        except KeyError:
            self._logger.critical('Cannot parse response.',
                                  exc_info=True)
            return []
        else:
            return text

    def transcribe(self, fp):
        """
        transcribes given audio file by uploading to wit.ai and returning
        received text from json answer.
        """
        wav_fp = wave.open(fp, 'rb')

        data = {
                   "format":"wav",
                   "rate":wav_fp.getframerate(),
                   "channel":wav_fp.getnchannels(),
                   "token":self.token(self.app_key, self.secret_key),
                   "cuid":"Jasper",
                   "len":wav_fp.getnframes()/float(wav_fp.getframerate()),
               }
        wav_fp.close()

        data = fp.read()
        r = requests.post('http://vop.baidu.com/server_api',
                          data=json.dumps(data),
                          headers={"Content-Type": "application/json"})
        try:
            r.raise_for_status()
            text = r.json()['_text']
        except requests.exceptions.HTTPError:
            self._logger.critical('Request failed with response: %r',
                                  r.text,
                                  exc_info=True)
            return []
        except requests.exceptions.RequestException:
            self._logger.critical('Request failed.', exc_info=True)
            return []
        except ValueError as e:
            self._logger.critical('Cannot parse response: %s',
                                  e.args[0])
            return []
        except KeyError:
            self._logger.critical('Cannot parse response.',
                                  exc_info=True)
            return []
        else:
            transcribed = [text.upper()]
            self._logger.info('Transcribed: %r', transcribed)
            return transcribed
