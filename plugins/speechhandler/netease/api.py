# -*- coding: utf-8 -*-
import re
import json
import binascii
import os
import time
import base64
import random
import requests
import logging
import hashlib
from Crypto.Cipher import AES
from http.cookiejar import LWPCookieJar
from jasper import paths
from . import database

COOKIE_PATH = os.path.join(paths.PLUGIN_PATH, 'speechhandler/netease/cookie')

default_timeout = 10

modulus = ('00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7'
           'b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280'
           '104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932'
           '575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b'
           '3ece0462db0a22b8e7')
nonce = '0CoJUm6Qyw8W8jud'
pubKey = '010001'


def encrypted_id(id):
    magic = bytearray('3go8&$8*3*3h0k(2)2', 'u8')
    song_id = bytearray(id, 'u8')
    magic_len = len(magic)
    for i, sid in enumerate(song_id):
        song_id[i] = sid ^ magic[i % magic_len]
    m = hashlib.md5(song_id)
    result = m.digest()
    result = base64.b64encode(result)
    result = result.replace(b'/', b'_')
    result = result.replace(b'+', b'-')
    return result.decode('utf-8')


def encrypted_request(text):
    text = json.dumps(text)
    secKey = createSecretKey(16)
    encText = aesEncrypt(aesEncrypt(text, nonce), secKey)
    encSecKey = rsaEncrypt(secKey, pubKey, modulus)
    data = {'params': encText, 'encSecKey': encSecKey}
    return data

def aesEncrypt(text, secKey):
    pad = 16 - len(text) % 16
    text = text + chr(pad) * pad
    encryptor = AES.new(secKey, 2, '0102030405060708')
    ciphertext = encryptor.encrypt(text)
    ciphertext = base64.b64encode(ciphertext).decode('utf-8')
    return ciphertext

def rsaEncrypt(text, pubKey, modulus):
    text = text[::-1]
    rs = pow(int(binascii.hexlify(text), 16), int(pubKey, 16)) % int(modulus, 16)
    return format(rs, 'x').zfill(256)

def createSecretKey(size):
    return binascii.hexlify(os.urandom(size))[:16]

def geturl(song):
    if song['hMusic']:
        music = song['hMusic']
        quality = 'HD'
    elif song['mMusic']:
        music = song['mMusic']
        quality = 'MD'
    elif song['lMusic']:
        music = song['lMusic']
        quality = 'LD'
    else:
        return song['mp3Url'], ''

    quality = quality + ' {0}k'.format(music['bitrate'] // 1000)
    song_id = str(music['dfsId'])
    enc_id = encrypted_id(song_id)
    url = 'http://m%s.music.126.net/%s/%s.mp3' % (random.randrange(1, 3),
                                                  enc_id, song_id)
    return url, quality


class Api(object):
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self.header = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip,deflate,sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,gl;q=0.6,zh-TW;q=0.4',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Host': 'music.163.com',
            'Referer': 'http://music.163.com/search/',
            'User-Agent':
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/33.0.1750.152 Safari/537.36'  # NOQA
        }
        self.cookies = {'appver': '1.5.2'}
        self.session = requests.Session()
        self.session.cookies = LWPCookieJar(COOKIE_PATH)
        self._database = database.Database()
        self._database.load()
        try:
            self.session.cookies.load()
            cookie = ''
            if os.path.isfile(COOKIE_PATH):
                self.file = open(COOKIE_PATH, 'r')
                cookie = self.file.read()
                self.file.close()
            expire_time = re.compile(r'\d{4}-\d{2}-\d{2}').findall(cookie)
            if expire_time:
                if expire_time[0] < time.strftime('%Y-%m-%d', time.localtime(time.time())):
                    self._database.setUserId('')
                    os.remove(COOKIE_PATH)
        except IOError as e:
            self._logger.error(e)
            self.session.cookies.save()

    def login(self, username, password):
        action = 'https://music.163.com/weapi/login/cellphone'
        text = {
            'phone': username.decode('utf-8'),
            'password': hashlib.md5(password.encode('utf-8')).hexdigest(),
            'rememberLogin': 'true'
        }
        data = encrypted_request(text)
        try:
            return self.httpRequest('Login_POST', action, data)
        except requests.exceptions.RequestException as e:
            self._logger.error(e)
            return {'code': 501}

    def httpRequest(self,
                    method,
                    action,
                    query=None,
                    urlencoded=None,
                    callback=None,
                    timeout=None):
        connection = json.loads(
            self.rawHttpRequest(method, action, query, urlencoded, callback, timeout)
        )
        return connection

    def rawHttpRequest(self,
                       method,
                       action,
                       query=None,
                       urlencoded=None,
                       callback=None,
                       timeout=None):
        if method == 'GET':
            url = action if query is None else action + '?' + query
            connection = self.session.get(url,
                                          headers=self.header,
                                          timeout=default_timeout)

        elif method == 'POST':
            connection = self.session.post(action,
                                           data=query,
                                           headers=self.header,
                                           timeout=default_timeout)

        elif method == 'Login_POST':
            connection = self.session.post(action,
                                           data=query,
                                           headers=self.header,
                                           timeout=default_timeout)
            self.session.cookies.save()

        connection.encoding = 'UTF-8'
        return connection.text

    def user_playlist(self, uid, offset=0, limit=100):
        action = 'http://music.163.com/api/user/playlist/?offset={}&limit={}&uid={}'.format(  # NOQA
            offset, limit, uid)
        try:
            data = self.httpRequest('GET', action)
            return data['playlist']
        except (requests.exceptions.RequestException, KeyError) as e:
            log.error(e)
            return -1

    def dig_info(self, data, dig_type):
        temp = []
        if dig_type == 'songs' or dig_type == 'fmsongs':
            for i in range(0, len(data)):
                url, quality = geturl(data[i])

                if data[i]['album'] is not None:
                    album_name = data[i]['album']['name']
                    album_id = data[i]['album']['id']
                else:
                    album_name = 'unknow album'
                    album_id = ''

                song_info = {
                    'song_id': data[i]['id'],
                    'artist': [],
                    'song_name': data[i]['name'],
                    'album_name': album_name,
                    'album_id': album_id,
                    'mp3_url': url,
                    'quality': quality
                }
                if 'artist' in data[i]:
                    song_info['artist'] = data[i]['artist']
                elif 'artists' in data[i]:
                    for j in range(0, len(data[i]['artists'])):
                        song_info['artist'].append(data[i]['artists'][j][
                            'name'])
                    song_info['artist'] = ', '.join(song_info['artist'])
                else:
                    song_info['artist'] = 'unknow artist'

                temp.append(song_info)

        elif dig_type == 'artists':
            artists = []
            for i in range(0, len(data)):
                artists_info = {
                    'artist_id': data[i]['id'],
                    'artists_name': data[i]['name'],
                    'alias': ''.join(data[i]['alias'])
                }
                artists.append(artists_info)

            return artists

        elif dig_type == 'albums':
            for i in range(0, len(data)):
                albums_info = {
                    'album_id': data[i]['id'],
                    'albums_name': data[i]['name'],
                    'artists_name': data[i]['artist']['name']
                }
                temp.append(albums_info)

        elif dig_type == 'top_playlists':
            for i in range(0, len(data)):
                playlists_info = {
                    'playlist_id': data[i]['id'],
                    'playlists_name': data[i]['name'],
                    'creator_name': data[i]['creator']['nickname']
                }
                temp.append(playlists_info)

        elif dig_type == 'channels':
            url, quality = geturl(data)
            channel_info = {
                'song_id': data['id'],
                'song_name': data['name'],
                'artist': data['artists'][0]['name'],
                'album_name': 'podcast',
                'mp3_url': url,
                'quality': quality
            }
            temp = channel_info

        return temp

    def playlist_detail(self, playlist_id):
        action = 'http://music.163.com/api/playlist/detail?id={}'.format(
            playlist_id)
        try:
            data = self.httpRequest('GET', action)
            return data['result']['tracks']
        except requests.exceptions.RequestException as e:
            self._logger.error(e)
            return []

    def songs_detail_new_api(self, music_ids, bit_rate=320000):
        action = 'http://music.163.com/weapi/song/enhance/player/url?csrf_token='  # NOQA
        self.session.cookies.load()
        csrf = ''
        for cookie in self.session.cookies:
            if cookie.name == '__csrf':
                csrf = cookie.value
        if csrf == '':
            notify('You Need Login', 1)
        action += csrf
        data = {'ids': music_ids, 'br': bit_rate, 'csrf_token': csrf}
        connection = self.session.post(action,
                                       data=encrypted_request(data),
                                       headers=self.header, )
        result = json.loads(connection.text)
        return result['data']


