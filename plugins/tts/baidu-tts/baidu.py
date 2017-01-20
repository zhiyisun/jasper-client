import os
import tempfile
import requests
import logging
from jasper import plugin


class BaiduTTSPlugin(plugin.TTSPlugin):
    """
    Uses the Baidu TTS online translator
    Requires pymad and gTTS to be available
    """

    def __init__(self, *args, **kwargs):
        plugin.TTSPlugin.__init__(self, *args, **kwargs)
        self._logger = logging.getLogger(__name__)
        try:
            orig_language = self.profile['language']
        except:
            orig_language = 'zh'

        language = orig_language.lower()
        self.language = language

        self.app_key = self.profile['baidu']['app_key']
        self.secret_key = self.profile['baidu']['secret_key']
        self._http = requests.Session()
        self.set_api_key(self.app_key, self.secret_key)

    def set_api_key(self, app_key, secret_key):
        """
        Sets property token
        """
        data = {'grant_type': 'client_credentials', 'client_id': app_key, 'client_secret': secret_key}
        r = self._http.post("https://openapi.baidu.com/oauth/2.0/token", data=data)
        try:
            r.raise_for_status()
            text = r.json()['access_token']
        except requests.exceptions.HTTPError:
            self._logger.critical('Request failed with response: %r',
                                  r.text,
                                  exc_info=True)
            return
        except requests.exceptions.RequestException:
            self._logger.critical('Request failed.', exc_info=True)
            return
        except ValueError as e:
            self._logger.critical('Cannot parse response: %s',
                                  e.args[0])
            return
        except KeyError:
            self._logger.critical('Cannot parse response.',
                                  exc_info=True)
            return
        else:
            self._api_key = text

    def say(self, phrase):
        if len(phrase) > 1024:
            raise KeyError("Text length must less than 1024 bytes")
        url = "http://tsn.baidu.com/text2audio"

        data = {
                "tex": phrase,
                "lan": self.language,
                "tok": self._api_key,
                "ctp": 1,
                "cuid": 'Jasper',
                "spd": 5,
                "pit": 5,
                "vol": 9,
                "per": 0,
                }

        r = self._http.post(url, data=data)
        try:
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                tmpfile = f.name
                with open(tmpfile, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024):
                        f.write(chunk)
                    f.close()
                data = self.mp3_to_wave(tmpfile)
                os.remove(tmpfile)
                return data
        except requests.exceptions.HTTPError:
            self._logger.critical('Request failed with response: %r',
                                  r.text,
                                  exc_info=True)
            return
        except requests.exceptions.RequestException:
            self._logger.critical('Request failed.', exc_info=True)
            return
        except ValueError as e:
            self._logger.critical('Cannot parse response: %s',
                                  e.args[0])
            return
        except KeyError:
            self._logger.critical('Cannot parse response.',
                                  exc_info=True)
            return

