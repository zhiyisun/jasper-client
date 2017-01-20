import hashlib
import logging
import re
import subprocess
import threading
import time
import difflib
import os
import signal
from . import api
from . import database
from random import randint


DEFAULT_VOLUME = 70

class Player(object):
    def __init__(self, *args, **kwargs):
        self._logger = logging.getLogger(__name__)
        self._api = api.Api()
        self._database = database.Database()
        self._database.load()
        self._userid = ''
        self._playlists = []
        self._playlist_idx = -1
        self._song_idx = 0
        self._playing_flag = True
        self._song_list = []
        self._state = 'stop'
        self._volume = 30
        self.popen_handler = None

    def connect(self, username, password):
        if self._database.getUserId() != '':
            self._userid = self._database.getUserId()
            self._logger.debug('You have already log in Netease Music before')
            return True
        else:
            user_info = {}
            user_info = self._api.login(username, password)

            if user_info['code'] != 200:
                self._logger.warning('Failed to log in Netease Music.')
                return False

            self._userid = user_info['account']['id']
            self._database.setUserId(self._userid)
            return True

    def close(self):
        self.stop(self)

    def listplaylists(self):
        if self._userid and not self._playlists:
                rawlists = self._api.user_playlist(self._userid)
                self._playlists = self._api.dig_info(rawlists, 'top_playlists')
        return self._playlists

    def status(self):
        return  { 'playlist_index': self._playlist_idx,
                  'state': self._state, #play/pause/stop
                  'volume': self._volume
                }

    def playlistinfo(self, idx):
        if self._playlists and idx < len(self._playlists):
            songs = self._api.playlist_detail(self._playlists[idx]['playlist_id'])
            songs_info = self._api.dig_info(songs, 'songs')
            listinfo = []
            for s in songs_info:
                song_info = {
                        'id': s['song_id'],
                        'tittle': s['song_name'],
                        'artist': s['artist'],
                        'album': s['album_name']
                        }
                listinfo.append(song_info)
            return listinfo
        else:
            return []

    def _get_playlist_idx(self):
        if not self._playlists:
            self._playlists = self.listplaylists()
            if not self._playlists:
                self._logger.warning('Playlists is null')
                return self._playlist_idx #still -1

        if not self._playlist_idx in range(0, len(self._playlists)):
            #Match playlist Jasper
            playlists_upper = [pl['playlists_name'].upper() for pl in self._playlists]
            matches = difflib.get_close_matches('JASPER', playlists_upper)
            if len(matches) > 0:
                self._playlist_idx = playlists_upper.index(matches[0])
            else:
                #If failed to get 'Jasper', use the random one
                self._playlist_idx = randint(0,(len(self._playlists) - 1))

        return self._playlist_idx

    def _is_idx_valid(self):
        return 0 <= self._song_idx < len(self._song_list)

    def _next_idx(self):
        if not self._is_idx_valid():
            self.stop()
            return
        self._song_idx = (self._song_idx + 1) % len(self._song_list)

    def _prev_idx(self):
        if not self._is_idx_valid():
            self.stop()
            return
        self._song_idx = (self._song_idx - 1) % len(self._song_list)
        
    def popen_recall(self, onExit, popenArgs):
        '''
        Runs the given args in subprocess.Popen, and then calls the function
        onExit when the subprocess completes.
        onExit is a callable object, and popenArgs is a lists/tuple of args
        that would give to subprocess.Popen.
        '''

        def runInThread(onExit, arg):
            self._logger.debug('start to playing......')
            para = ['mpg123', '-R']
            self.popen_handler = subprocess.Popen(para,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
            self.popen_handler.stdin.write(b'V ' + str(DEFAULT_VOLUME).encode('utf-8') + b'\n')
            if arg:
                self.popen_handler.stdin.write(b'L ' + arg.encode('utf-8') + b'\n')
            else:
                self._next_idx()
                onExit()
                return

            self.popen_handler.stdin.flush()

            self.process_first = True
            while True:
                if self._playing_flag is False:
                    break

                strout = self.popen_handler.stdout.readline().decode('utf-8')

                if re.match('^\@F.*$', strout):
                    process_data = strout.split(' ')
                    process_location = float(process_data[4])
                    if self.process_first:
                        self.process_length = process_location
                        self.process_first = False
                        self.process_location = 0
                    else:
                        self.process_location = self.process_length - process_location  # NOQA
                    continue
                elif strout[:2] == '@E':
                    # get a alternative url from new api
                    sid = popenArgs['song_id']
                    new_url = self._api.songs_detail_new_api([sid])[0]['url']
                    if new_url is None:

                        self._logger.warning(('Song {} is unavailable '
                            'due to copyright issue.').format(sid))
                        break
                    self._logger.warning(
                            'Song {} is not compatible with old api.'.format(sid))
                    popenArgs['mp3_url'] = new_url

                    self.popen_handler.stdin.write(b'\nL ' + new_url.encode('utf-8') + b'\n')
                    self.popen_handler.stdin.flush()
                    self.popen_handler.stdout.readline()
                elif strout == '@P 0\n':
                    self.popen_handler.stdin.write(b'Q\n')
                    self.popen_handler.stdin.flush()
                    self.popen_handler.kill()
                    break

            if self._playing_flag:
                self._next_idx()
                onExit()
            return

        thread = threading.Thread(target=runInThread,
                args=(onExit, popenArgs['mp3_url']))
        thread.start()
        # returns immediately after the thread starts
        return thread

    def play(self):
        self._state = 'play'
        index = self._get_playlist_idx()
        if index == -1:
            self._state = 'stop'
            return
        songs = self._api.playlist_detail(self._playlists[index]['playlist_id'])
        songs_info = self._api.dig_info(songs, 'songs')
        if not songs_info:
            return
        self._song_list = []
        for song in songs_info:
            self._song_list.append(str(song['song_id']))
        self._playing_flag = True
        self.popen_recall(self.play, songs_info[self._song_idx])

    def pause(self,flag): #0 is resume, 1 is pause
        if not self._playing_flag and not self.popen_handler:
            return
        if flag == 1:
            self._state = 'pause'
        else:
            self._state = 'play'
        self.popen_handler.stdin.write(b'P\n')
        self.popen_handler.stdin.flush()

    def stop(self):
        self._state = 'stop'
        if self._playing_flag and self.popen_handler:
            self.popen_handler.stdin.write(b'Q\n')
            self.popen_handler.stdin.flush()
            self._playing_flag = False
            try:
                self.popen_handler.kill()
            except OSError as e:
                self._logger.error(e)
                return

    def next(self):
        self.stop()
        time.sleep(0.01)
        self._next_idx()
        self.play()

    def previous(self):
        self.stop()
        time.sleep(0.01)
        self._prev_idx()
        self.play()

    def clear(self):
        self.stop()
        self._playlist_idx = -1
        self._song_idx = 0
        self._song_list = []

    def load(self, playlist):
        self._playlist_idx = self._playlists.index(playlist)

    def setvol(self, volume):
        self._volume = volume
        if self.popen_handler:
            self.popen_handler.stdin.write(b'V ' + str(volume).encode('utf-8') + b'\n')
            self.popen_handler.stdin.flush()
