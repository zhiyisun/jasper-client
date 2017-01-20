import json
import logging
import urllib
import urlparse
import wave
import requests
from jasper import plugin


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
        plugin.STTPlugin.__init__(self, *args, **kwargs)
        # FIXME: get init args from config

        self._logger = logging.getLogger(__name__)
        self._request_url = None
        self._http = requests.Session()
        self._api_key = None
        try:
            language = self.profile['language']
        except KeyError:
            language = 'en'

        self.language = language.lower()
        self.app_key = self.profile['baidu']['app_key']
        self.secret_key = self.profile['baidu']['secret_key']
        self.set_api_key(self.app_key, self.secret_key)

    @property
    def request_url(self):
        return self._request_url

    @property
    def language(self):
        return self._language

    @language.setter
    def language(self, value):
        self._language = value
        self._regenerate_request_url()

    @property
    def api_key(self):
        return self._api_key

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
            self._regenerate_request_url()

    def _regenerate_request_url(self):
        if self.api_key and self.language:
            query = urllib.urlencode({'cuid': 'JASPER',
                                      'token': self.api_key,
                                      'lan': self.language })
            self._request_url = urlparse.urlunparse(
                ('http', 'vop.baidu.com', '/server_api', '',
                 query, ''))
        else:
            self._request_url = None

    def transcribe(self, fp):
        """
        Performs STT via the Google Speech API, transcribing an audio file and
        returning an English string.

        Arguments:
        audio_file_path -- the path to the .wav file to be transcribed
        """
        if not self.api_key:
            self._logger.critical('API key missing, transcription request ' +
                                  'aborted.')
            return []
        elif not self.language:
            self._logger.critical('Language info missing, transcription ' +
                                  'request aborted.')
            return []

        wav = wave.open(fp, 'rb')
        frame_rate = wav.getframerate()
        wav.close()
        data = fp.read()

        headers = {'content-type': 'audio/wav; rate=%s' % frame_rate}
        r = self._http.post(self.request_url, data=data, headers=headers)
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            self._logger.critical('Request failed with http status %d',
                                  r.status_code)
            if r.status_code == requests.codes['forbidden']:
                self._logger.warning('Status 403 is probably caused by an ' +
                                     'invalid Baidu API key.')
            return []
        r.encoding = 'utf-8'
        try:
            # We cannot simply use r.json() because Google sends invalid json
            # (i.e. multiple json objects, seperated by newlines. We only want
            # the last one).
            response = json.loads(list(r.text.strip().split('\n', 1))[-1])
            if len(response['result']) == 0:
                # Response result is empty
                raise ValueError('Nothing has been transcribed.')
            results = [result for result in response['result']]
        except ValueError as e:
            self._logger.warning('Empty response: %s', e.args[0])
            results = []
        except (KeyError, IndexError):
            self._logger.warning('Cannot parse response.', exc_info=True)
            results = []
        else:
            # Convert all results to uppercase
            results = tuple(result.upper() for result in results)
            self._logger.info('Transcribed: %r', results)
        return results
