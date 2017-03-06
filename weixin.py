import http
import json
import logging
import mimetypes
import multiprocessing
import os
import platform
import random
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib
import xml.dom.minidom

import qrcode
import requests
from lxml import html
from requests_toolbelt.multipart.encoder import MultipartEncoder


class dbHelper:
    def __init__(self, dbName):
        self.db = sqlite3.connect(dbName, check_same_thread=False)
        self.cx = self.db.cursor()
        self.cx.execute(
            "CREATE TABLE IF NOT EXISTS friends  (userid TEXT PRIMARY KEY, state INT,message TEXT,updatetime INT)")
        self.commit()

    def insertFriend(self, friendid, state=0, updatetime=int(time.time())):
        if self.isFriend(friendid):
            # self.setFriendState(friendid, state)
            return
        self.cx.execute("INSERT INTO friends VALUES (?,?,?,?)",
                        (friendid, state, '', updatetime))

    def isFriend(self, friendid):
        raws = self.cx.execute(
            "select * from friends where userid='%s'" % (friendid))
        for r in raws:
            return True
        return False

    def getFriendState(self, friendid):
        raws = self.cx.execute(
            "select state from friends WHERE userid='%s'" % (friendid))
        for raw in raws:
            return raw[0]

    def setFriendState(self, friendid, state):
        self.cx.execute(
            "update friends set state=%d where userid='%s'" % (state, friendid))

    def addFriendState(self, friendid):
        self.cx.execute(
            "update friends set state=state+1 WHERE userid='%s'" % (friendid))

    def getFriendTime(self, friendid):
        raws = self.cx.execute(
            "select updatetime from friends WHERE userid='%s'" % (friendid))
        for raw in raws:
            return raw[0]

    def setFriendTime(self, friendid, t=int(time.time())):
        self.cx.execute(
            "update friends set updatetime=%d WHERE userid='%s'" % (t, friendid))

    def getRandomFriend(self):
        now = int(time.time())
        raws = self.cx.execute(
            "select userid from friends where updatetime<=%d and state==0" % (now - 2 * 24 * 60 * 60))
        for raw in raws:
            return raw[0]

    def updatedb(self):
        now = int(time.time())
        self.cx.execute(
            'update friends set state=0 where updatetime<=%d and state=5' % (now - 7 * 24 * 60 * 60))
        self.cx.execute('UPDATE friends SET state =0 WHERE state=-2')
        self.commit()

    # def enterGame(self, friendid):
    #     self.cx.execute("update friends set game=1 where userid='%s'" % (friendid))
    #
    # def getFriendGameState(self, friendid):
    #     raws = self.cx.execute("select game from friends WHERE userid='%d'" % (friendid))
    #     for raw in raws:
    #         return raw[0]
    #
    # def leaveGame(self, friendid):
    #     self.cx.execute("update friends set game=0 where userid='%s'" % (friendid))

    def commit(self):
        self.db.commit()

    def __del__(self):
        self.commit()
        self.cx.close()
        self.db.close()


def catchKeyboardInterrupt(fn):
    def wrapper(*args):
        try:
            return fn(*args)
        except KeyboardInterrupt:
            print('\n[*] 强制退出程序')
            logging.debug('[*] 强制退出程序')

    return wrapper


def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, str):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv


def _decode_dict(data):
    rv = {}
    for key, value in data.items():
        if isinstance(key, str):
            key = key.encode('utf-8')
        if isinstance(value, str):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv


class WebWeixin(object):
    def __str__(self):
        description = \
            "=========================\n" + \
            "[#] Web Weixin\n" + \
            "[#] Debug Mode: " + str(self.DEBUG) + "\n" + \
            "[#] Uuid: " + self.uuid + "\n" + \
            "[#] Uin: " + str(self.uin) + "\n" + \
            "[#] Sid: " + self.sid + "\n" + \
            "[#] Skey: " + self.skey + "\n" + \
            "[#] DeviceId: " + self.deviceId + "\n" + \
            "[#] PassTicket: " + self.pass_ticket + "\n" + \
            "========================="
        return description

    def __init__(self):
        self.DEBUG = False
        self.uuid = ''
        self.base_uri = ''
        self.redirect_uri = ''
        self.uin = ''
        self.sid = ''
        self.skey = ''
        self.pass_ticket = ''
        self.deviceId = 'e' + repr(random.random())[2:17]
        self.BaseRequest = {}
        self.synckey = ''
        self.SyncKey = []
        self.User = []
        self.MemberList = []
        self.ContactList = []  # 好友
        self.GroupList = []  # 群
        self.GroupMemeberList = []  # 群友
        self.PublicUsersList = []  # 公众号／服务号
        self.SpecialUsersList = []  # 特殊账号
        self.autoReplyMode = False
        self.syncHost = ''
        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.109 Safari/537.36'
        self.interactive = False
        self.autoOpen = False
        self.saveFolder = os.path.join(os.getcwd(), 'saved')
        self.saveSubFolders = {'webwxgeticon': 'icons', 'webwxgetheadimg': 'headimgs', 'webwxgetmsgimg': 'msgimgs',
                               'webwxgetvideo': 'videos', 'webwxgetvoice': 'voices', '_showQRCodeImg': 'qrcodes'}
        self.appid = 'wx782c26e4c19acffb'
        self.lang = 'zh_CN'
        self.lastCheckTs = time.time()
        self.memberCount = 0
        self.SpecialUsers = ['newsapp', 'fmessage', 'filehelper', 'weibo', 'qqmail', 'fmessage', 'tmessage', 'qmessage',
                             'qqsync', 'floatbottle', 'lbsapp', 'shakeapp', 'medianote', 'qqfriend', 'readerapp',
                             'blogapp', 'facebookapp', 'masssendapp', 'meishiapp', 'feedsapp',
                             'voip', 'blogappweixin', 'weixin', 'brandsessionholder', 'weixinreminder',
                             'wxid_novlwrv3lqwv11', 'gh_22b87fa7cb3c', 'officialaccounts', 'notification_messages',
                             'wxid_novlwrv3lqwv11', 'gh_22b87fa7cb3c', 'wxitil', 'userexperience_alarm',
                             'notification_messages']
        self.TimeOut = 20  # 同步最短时间间隔（单位：秒）
        self.media_count = -1

        self.cookie = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie))
        opener.addheaders = [('User-agent', self.user_agent)]
        urllib.request.install_opener(opener)

    def loadConfig(self, config):
        if config['DEBUG']:
            self.DEBUG = config['DEBUG']
        if config['autoReplyMode']:
            self.autoReplyMode = config['autoReplyMode']
        if config['user_agent']:
            self.user_agent = config['user_agent']
        if config['interactive']:
            self.interactive = config['interactive']
        if config['autoOpen']:
            self.autoOpen = config['autoOpen']

    def getUUID(self):
        url = 'https://login.weixin.qq.com/jslogin'
        params = {
            'appid': self.appid,
            'fun': 'new',
            'lang': self.lang,
            '_': int(time.time()),
        }
        # r = requests.get(url=url, params=params)
        # r.encoding = 'utf-8'
        # data = r.text
        data = self._post(url, params, False).decode("utf-8")
        if data == '':
            return False
        regx = r'window.QRLogin.code = (\d+); window.QRLogin.uuid = "(\S+?)"'
        pm = re.search(regx, data)
        if pm:
            code = pm.group(1)
            self.uuid = pm.group(2)
            return code == '200'
        return False

    def genQRCode(self):
        # return self._showQRCodeImg()
        if sys.platform.startswith('win'):
            self._showQRCodeImg('win')
        elif sys.platform.find('darwin') >= 0:
            self._showQRCodeImg('macos')
        else:
            self._str2qr('https://login.weixin.qq.com/l/' + self.uuid)

    def _showQRCodeImg(self, str):
        url = 'https://login.weixin.qq.com/qrcode/' + self.uuid
        params = {
            't': 'webwx',
            '_': int(time.time())
        }

        data = self._post(url, params, False)
        if data == '':
            return
        QRCODE_PATH = self._saveFile('qrcode.jpg', data, '_showQRCodeImg')
        if str == 'win':
            os.startfile(QRCODE_PATH)
        elif str == 'macos':
            subprocess.call(["open", QRCODE_PATH])
        else:
            return

    def waitForLogin(self, tip=1):
        time.sleep(tip)
        url = 'https://login.weixin.qq.com/cgi-bin/mmwebwx-bin/login?tip=%s&uuid=%s&_=%s' % (
            tip, self.uuid, int(time.time()))
        data = self._get(url)
        if data == '':
            return False
        pm = re.search(r"window.code=(\d+);", data)
        code = pm.group(1)

        if code == '201':
            return True
        elif code == '200':
            pm = re.search(r'window.redirect_uri="(\S+?)";', data)
            r_uri = pm.group(1) + '&fun=new'
            self.redirect_uri = r_uri
            self.base_uri = r_uri[:r_uri.rfind('/')]
            return True
        elif code == '408':
            self._echo('[登陆超时] \n')
        else:
            self._echo('[登陆异常] \n')
        return False

    def login(self):
        data = self._get(self.redirect_uri)
        if data == '':
            return False
        doc = xml.dom.minidom.parseString(data)
        root = doc.documentElement

        for node in root.childNodes:
            if node.nodeName == 'skey':
                self.skey = node.childNodes[0].data
            elif node.nodeName == 'wxsid':
                self.sid = node.childNodes[0].data
            elif node.nodeName == 'wxuin':
                self.uin = node.childNodes[0].data
            elif node.nodeName == 'pass_ticket':
                self.pass_ticket = node.childNodes[0].data

        if '' in (self.skey, self.sid, self.uin, self.pass_ticket):
            return False

        self.BaseRequest = {
            'Uin': int(self.uin),
            'Sid': self.sid,
            'Skey': self.skey,
            'DeviceID': self.deviceId,
        }
        self.db = dbHelper(self.uin)

        return True

    def webwxinit(self):
        url = self.base_uri + '/webwxinit?pass_ticket=%s&skey=%s&r=%s' % (
            self.pass_ticket, self.skey, int(time.time()))
        params = {
            'BaseRequest': self.BaseRequest
        }
        dic = self._post(url, params)
        if dic == '':
            return False
        self.SyncKey = dic['SyncKey']
        self.User = dic['User']
        # synckey for synccheck
        self.synckey = '|'.join(
            [str(keyVal['Key']) + '_' + str(keyVal['Val']) for keyVal in self.SyncKey['List']])

        return dic['BaseResponse']['Ret'] == 0

    def mywebwxstatusnotify(self):
        url = self.base_uri + \
              '/webwxstatusnotify?lang=zh_CN&pass_ticket=%s' % (self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            "Code": 3,
            "FromUserName": self.User['UserName'],
            "ToUserName": 'fmessage',
            "ClientMsgId": int(time.time())
        }
        dic = self._post(url, params)
        if dic == '':
            return False

        return dic['BaseResponse']['Ret'] == 0

    def webwxstatusnotify(self):
        url = self.base_uri + \
              '/webwxstatusnotify?lang=zh_CN&pass_ticket=%s' % (self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            "Code": 3,
            "FromUserName": self.User['UserName'],
            "ToUserName": self.User['UserName'],
            "ClientMsgId": int(time.time())
        }
        dic = self._post(url, params)
        if dic == '':
            return False

        return dic['BaseResponse']['Ret'] == 0

    def webwxgetcontact(self):

        # self.ContactList = []  # 好友
        # self.GroupList = []  # 群
        # self.PublicUsersList = []  # 公众号／服务号
        # self.SpecialUsersList = []  # 特殊账号

        SpecialUsers = self.SpecialUsers
        url = self.base_uri + '/webwxgetcontact?pass_ticket=%s&skey=%s&r=%s' % (
            self.pass_ticket, self.skey, int(time.time()))
        dic = self._post(url, {})
        if dic == '':
            return False

        self.MemberCount = dic['MemberCount']
        self.MemberList = dic['MemberList']

        # with open('contact.json', 'w', encoding='utf-8') as fout:
        #     json.dump(dic, fout)

        ContactList = self.MemberList[:]
        GroupList = self.GroupList[:]
        PublicUsersList = self.PublicUsersList[:]
        SpecialUsersList = self.SpecialUsersList[:]

        for i in range(len(ContactList) - 1, -1, -1):
            Contact = ContactList[i]
            if Contact['VerifyFlag'] & 8 != 0:  # 公众号/服务号
                ContactList.remove(Contact)
                self.PublicUsersList.append(Contact)
            elif Contact['UserName'] in SpecialUsers:  # 特殊账号
                ContactList.remove(Contact)
                self.SpecialUsersList.append(Contact)
            elif '@@' in Contact['UserName']:  # 群聊
                ContactList.remove(Contact)
                self.GroupList.append(Contact)
            elif Contact['UserName'] == self.User['UserName']:  # 自己
                ContactList.remove(Contact)
        self.ContactList = ContactList

        for contact in self.ContactList:
            key = contact['Alias']
            if key == '':
                key = contact['NickName']

            if not self.db.isFriend(key):
                self.db.insertFriend(key)
        self.db.commit()
        return True

    def webwxbatchgetcontact(self):
        url = self.base_uri + \
              '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' % (
                  int(time.time()), self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            "Count": len(self.GroupList),
            "List": [{"UserName": g['UserName'], "EncryChatRoomId": ""} for g in self.GroupList]
        }
        dic = self._post(url, params)
        if dic == '':
            return False

        # blabla ...
        ContactList = dic['ContactList']
        ContactCount = dic['Count']
        self.GroupList = ContactList

        for i in range(len(ContactList) - 1, -1, -1):
            Contact = ContactList[i]
            MemberList = Contact['MemberList']
            for member in MemberList:
                self.GroupMemeberList.append(member)
        return True

    def getNameById(self, id):
        url = self.base_uri + \
              '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' % (
                  int(time.time()), self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            "Count": 1,
            "List": [{"UserName": id, "EncryChatRoomId": ""}]
        }
        dic = self._post(url, params)
        if dic == '':
            return None

        # blabla ...
        return dic['ContactList']

    def testsynccheck(self):
        SyncHost = ['wx2.qq.com',
                    'webpush.wx2.qq.com',
                    'wx8.qq.com',
                    'webpush.wx8.qq.com',
                    'qq.com',
                    'webpush.wx.qq.com',
                    'web2.wechat.com',
                    'webpush.web2.wechat.com',
                    'wechat.com',
                    'webpush.web.wechat.com',
                    'webpush.weixin.qq.com',
                    'webpush.wechat.com',
                    'webpush1.wechat.com',
                    'webpush2.wechat.com',
                    'webpush.wx.qq.com',
                    'webpush2.wx.qq.com']
        for host in SyncHost:
            self.syncHost = host
            [retcode, selector] = self.synccheck()
            if retcode == '0':
                return True
        return False

    def synccheck(self):
        params = {
            'r': int(time.time()),
            'sid': self.sid,
            'uin': self.uin,
            'skey': self.skey,
            'deviceid': self.deviceId,
            'synckey': self.synckey,
            '_': int(time.time()),
        }
        url = 'https://' + self.syncHost + \
              '/cgi-bin/mmwebwx-bin/synccheck?' + \
              urllib.parse.urlencode(params)
        data = self._get(url)
        if data == '':
            return [-1, -1]

        pm = re.search(
            r'window.synccheck={retcode:"(\d+)",selector:"(\d+)"}', data)
        retcode = pm.group(1)
        selector = pm.group(2)
        return [retcode, selector]

    def webwxsync(self):
        url = self.base_uri + \
              '/webwxsync?sid=%s&skey=%s&pass_ticket=%s' % (
                  self.sid, self.skey, self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            'SyncKey': self.SyncKey,
            'rr': ~int(time.time())
        }
        dic = self._post(url, params)
        if dic == '':
            return None
        if self.DEBUG:
            print(json.dumps(dic, indent=4))
            (json.dumps(dic, indent=4))

        if dic['BaseResponse']['Ret'] == 0:
            self.SyncKey = dic['SyncKey']
            self.synckey = '|'.join(
                [str(keyVal['Key']) + '_' + str(keyVal['Val']) for keyVal in self.SyncKey['List']])
        return dic

    def webwxsendmsg(self, word, to='filehelper'):
        url = self.base_uri + \
              '/webwxsendmsg?pass_ticket=%s' % (self.pass_ticket)
        clientMsgId = str(int(time.time() * 1000)) + \
                      str(random.random())[:5].replace('.', '')
        params = {
            'BaseRequest': self.BaseRequest,
            'Msg': {
                "Type": 1,
                "Content": self._transcoding(word),
                "FromUserName": self.User['UserName'],
                "ToUserName": to,
                "LocalID": clientMsgId,
                "ClientMsgId": clientMsgId
            }
        }
        headers = {'content-type': 'application/json; charset=UTF-8'}
        data = json.dumps(params, ensure_ascii=False).encode('utf8')
        r = requests.post(url, data=data, headers=headers)
        dic = r.json()
        return dic['BaseResponse']['Ret'] == 0

    def webwxuploadmedia(self, image_name):
        url = 'https://file2.wx.qq.com/cgi-bin/mmwebwx-bin/webwxuploadmedia?f=json'
        # 计数器
        self.media_count = self.media_count + 1
        # 文件名
        file_name = image_name
        # MIME格式
        # mime_type = application/pdf, image/jpeg, image/png, etc.
        mime_type = mimetypes.guess_type(image_name, strict=False)[0]
        # 微信识别的文档格式，微信服务器应该只支持两种类型的格式。pic和doc
        # pic格式，直接显示。doc格式则显示为文件。
        media_type = 'pic' if mime_type.split('/')[0] == 'image' else 'doc'
        # 上一次修改日期
        lastModifieDate = 'Thu Mar 17 2016 00:55:10 GMT+0800 (CST)'
        # 文件大小
        file_size = os.path.getsize(file_name)
        # PassTicket
        pass_ticket = self.pass_ticket
        # clientMediaId
        client_media_id = str(int(time.time() * 1000)) + \
                          str(random.random())[:5].replace('.', '')
        # webwx_data_ticket
        webwx_data_ticket = ''
        for item in self.cookie:
            if item.name == 'webwx_data_ticket':
                webwx_data_ticket = item.value
                break
        if (webwx_data_ticket == ''):
            return "None Fuck Cookie"

        uploadmediarequest = json.dumps({
            "BaseRequest": self.BaseRequest,
            "ClientMediaId": client_media_id,
            "TotalLen": file_size,
            "StartPos": 0,
            "DataLen": file_size,
            "MediaType": 4
        }, ensure_ascii=False).encode('utf8')

        multipart_encoder = MultipartEncoder(
            fields={
                'id': 'WU_FILE_' + str(self.media_count),
                'name': file_name,
                'type': mime_type,
                'lastModifieDate': lastModifieDate,
                'size': str(file_size),
                'mediatype': media_type,
                'uploadmediarequest': uploadmediarequest,
                'webwx_data_ticket': webwx_data_ticket,
                'pass_ticket': pass_ticket,
                'filename': (file_name, open(file_name, 'rb'), mime_type.split('/')[1])
            },
            boundary='-----------------------------1575017231431605357584454111'
        )

        headers = {
            'Host': 'file2.wx.qq.com',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:42.0) Gecko/20100101 Firefox/42.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'https://wx2.qq.com/',
            'Content-Type': multipart_encoder.content_type,
            'Origin': 'https://wx2.qq.com',
            'Connection': 'keep-alive',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }

        r = requests.post(url, data=multipart_encoder, headers=headers)
        response_json = r.json()
        if response_json['BaseResponse']['Ret'] == 0:
            return response_json
        return None

    def webwxsendmsgimg(self, user_id, media_id):
        url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsgimg?fun=async&f=json&pass_ticket=%s' % self.pass_ticket
        clientMsgId = str(int(time.time() * 1000)) + \
                      str(random.random())[:5].replace('.', '')
        data_json = {
            "BaseRequest": self.BaseRequest,
            "Msg": {
                "Type": 3,
                "MediaId": media_id,
                "FromUserName": self.User['UserName'],
                "ToUserName": user_id,
                "LocalID": clientMsgId,
                "ClientMsgId": clientMsgId
            }
        }
        headers = {'content-type': 'application/json; charset=UTF-8'}
        data = json.dumps(data_json, ensure_ascii=False).encode('utf8')
        r = requests.post(url, data=data, headers=headers)
        dic = r.json()
        return dic['BaseResponse']['Ret'] == 0

    def webwxsendmsgemotion(self, user_id, media_id):
        url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendemoticon?fun=sys&f=json&pass_ticket=%s' % self.pass_ticket
        clientMsgId = str(int(time.time() * 1000)) + \
                      str(random.random())[:5].replace('.', '')
        data_json = {
            "BaseRequest": self.BaseRequest,
            "Msg": {
                "Type": 47,
                "EmojiFlag": 2,
                "MediaId": media_id,
                "FromUserName": self.User['UserName'],
                "ToUserName": user_id,
                "LocalID": clientMsgId,
                "ClientMsgId": clientMsgId
            }
        }
        headers = {'content-type': 'application/json; charset=UTF-8'}
        data = json.dumps(data_json, ensure_ascii=False).encode('utf8')
        r = requests.post(url, data=data, headers=headers)
        dic = r.json()
        if self.DEBUG:
            print(json.dumps(dic, indent=4))
            logging.debug(json.dumps(dic, indent=4))
        return dic['BaseResponse']['Ret'] == 0

    def _saveFile(self, filename, data, api=None):
        fn = filename
        if self.saveSubFolders[api]:
            dirName = os.path.join(self.saveFolder, self.saveSubFolders[api])
            if not os.path.exists(dirName):
                os.makedirs(dirName)
            fn = os.path.join(dirName, filename)
            logging.debug('Saved file: %s' % fn)
            with open(fn, 'wb') as f:
                f.write(data)
                f.close()
        return fn

    def webwxgeticon(self, id):
        url = self.base_uri + \
              '/webwxgeticon?username=%s&skey=%s' % (id, self.skey)
        data = self._get(url)
        if data == '':
            return ''
        fn = 'img_' + id + '.jpg'
        return self._saveFile(fn, data, 'webwxgeticon')

    def webwxgetheadimg(self, id):
        url = self.base_uri + \
              '/webwxgetheadimg?username=%s&skey=%s' % (id, self.skey)
        data = self._get(url)
        if data == '':
            return ''
        fn = 'img_' + id + '.jpg'
        return self._saveFile(fn, data, 'webwxgetheadimg')

    def webwxgetmsgimg(self, msgid):
        url = self.base_uri + \
              '/webwxgetmsgimg?MsgID=%s&skey=%s' % (msgid, self.skey)
        data = self._get(url)
        if data == '':
            return ''
        fn = 'img_' + msgid + '.jpg'
        return self._saveFile(fn, data, 'webwxgetmsgimg')

    # Not work now for weixin haven't support this API
    def webwxgetvideo(self, msgid):
        url = self.base_uri + \
              '/webwxgetvideo?msgid=%s&skey=%s' % (msgid, self.skey)
        data = self._get(url, api='webwxgetvideo')
        if data == '':
            return ''
        fn = 'video_' + msgid + '.mp4'
        return self._saveFile(fn, data, 'webwxgetvideo')

    def webwxgetvoice(self, msgid):
        url = self.base_uri + \
              '/webwxgetvoice?msgid=%s&skey=%s' % (msgid, self.skey)
        data = self._get(url)
        if data == '':
            return ''
        fn = 'voice_' + msgid + '.mp3'
        return self._saveFile(fn, data, 'webwxgetvoice')

    def getGroupName(self, id):
        name = '未知群'
        for member in self.GroupList:
            if member['UserName'] == id:
                name = member['NickName']
        if name == '未知群':
            # 现有群里面查不到
            GroupList = self.getNameById(id)
            for group in GroupList:
                self.GroupList.append(group)
                if group['UserName'] == id:
                    name = group['NickName']
                    MemberList = group['MemberList']
                    for member in MemberList:
                        self.GroupMemeberList.append(member)
        return name

    def getUserRemarkName(self, id):
        name = '未知群' if id[:2] == '@@' else '陌生人'
        if id == self.User['UserName']:
            return self.User['NickName']  # 自己

        if id[:2] == '@@':
            # 群
            name = self.getGroupName(id)
        else:
            # 特殊账号
            for member in self.SpecialUsersList:
                if member['UserName'] == id:
                    name = member['RemarkName'] if member[
                        'RemarkName'] else member['NickName']

            # 公众号或服务号
            for member in self.PublicUsersList:
                if member['UserName'] == id:
                    name = member['RemarkName'] if member[
                        'RemarkName'] else member['NickName']

            # 直接联系人
            for member in self.ContactList:
                if member['UserName'] == id:
                    name = member['RemarkName'] if member['RemarkName'] else member['NickName']
            # 群友
            for member in self.GroupMemeberList:
                if member['UserName'] == id:
                    name = member['DisplayName'] if member[
                        'DisplayName'] else member['NickName']

        if name == '未知群' or name == '陌生人':
            logging.debug(id)
        return name

    def getUSerID(self, name):
        for member in self.MemberList:
            if name == member['RemarkName'] or name == member['NickName']:
                return member['UserName']
        return None

    def getUserAlias(self, name):
        for member in self.ContactList:
            if name == member['RemarkName'] or name == member['NickName']:
                return member['Alias'] if member['Alias'] != '' else None
        return None

    def _showMsg(self, message):

        srcName = None
        dstName = None
        groupName = None
        content = None

        msg = message
        logging.debug(msg)

        if msg['raw_msg']:
            srcName = self.getUserRemarkName(msg['raw_msg']['FromUserName'])
            dstName = self.getUserRemarkName(msg['raw_msg']['ToUserName'])
            content = msg['raw_msg']['Content'].replace(
                '&lt;', '<').replace('&gt;', '>')
            message_id = msg['raw_msg']['MsgId']

            if content.find('http://weixin.qq.com/cgi-bin/redirectforward?args=') != -1:
                # 地理位置消息
                data = self._get(content)
                if data == '':
                    return
                data.decode('gbk').encode('utf-8')
                pos = self._searchContent('title', data, 'xml')
                temp = self._get(content)
                if temp == '':
                    return
                tree = html.fromstring(temp)
                url = tree.xpath('//html/body/div/img')[0].attrib['src']

                for item in urlparse(url).query.split('&'):
                    if item.split('=')[0] == 'center':
                        loc = item.split('=')[-1:]

                content = '%s 发送了一个 位置消息 - 我在 [%s](%s) @ %s]' % (
                    srcName, pos, url, loc)

            if msg['raw_msg']['ToUserName'] == 'filehelper':
                # 文件传输助手
                dstName = '文件传输助手'

            if msg['raw_msg']['FromUserName'][:2] == '@@':
                # 接收到来自群的消息
                if ":<br/>" in content:
                    [people, content] = content.split(':<br/>', 1)
                    groupName = srcName
                    srcName = self.getUserRemarkName(people)
                    dstName = 'GROUP'
                else:
                    groupName = srcName
                    srcName = 'SYSTEM'
            elif msg['raw_msg']['ToUserName'][:2] == '@@':
                # 自己发给群的消息
                groupName = dstName
                dstName = 'GROUP'

            # 收到了红包
            if content == '收到红包，请在手机上查看':
                self.webwxsendmsg("[色][色][色]哇哦～谢谢宝宝，thankssss[鼓掌]", msg[
                    'raw_msg']["FromUserName"])
                msg['message'] = content

            # 指定了消息内容
            if 'message' in list(msg.keys()):
                content = msg['message']

        if groupName != None:
            print('%s |%s| %s -> %s: %s' % (
                message_id, groupName.strip(), srcName.strip(), dstName.strip(), content.replace('<br/>', '\n')))
            logging.info('%s |%s| %s -> %s: %s' % (message_id, groupName.strip(),
                                                   srcName.strip(), dstName.strip(), content.replace('<br/>', '\n')))
        else:
            print('%s %s -> %s: %s' % (message_id, srcName.strip(),
                                       dstName.strip(), content.replace('<br/>', '\n')))
            logging.info('%s %s -> %s: %s' % (message_id, srcName.strip(),
                                              dstName.strip(), content.replace('<br/>', '\n')))

    def handleMsg(self, r):
        for msg in r['AddMsgList']:
            print('[*] 你有新的消息，请注意查收')
            logging.debug('[*] 你有新的消息，请注意查收')

            if self.DEBUG:
                fn = 'msg' + str(int(random.random() * 1000)) + '.json'
                with open(fn, 'w') as f:
                    f.write(json.dumps(msg))
                print('[*] 该消息已储存到文件: ' + fn)
                logging.debug('[*] 该消息已储存到文件: %s' % (fn))

            msgType = msg['MsgType']

            content = msg['Content'].replace(
                '&lt;', '<').replace('&gt;', '>')

            # 判断msgType=1000

            if content == '收到红包，请在手机上查看':
                self.webwxsendmsg("[色][色][色]哇哦～谢谢宝宝，thankssss[鼓掌]", msg[
                    'raw_msg']["FromUserName"])
                return

            if msgType == 37:

                def add_friend_thread(userName, VerifyUserTicket='', status=3, autoUpdate=True):

                    key = msg['RecommendInfo']['Alias']
                    if key == '':
                        key = msg['RecommendInfo']['NickName']

                    # for member in self.ContactList:
                    #     if key == member['Alias'] if member['Alias'] != '' else member['NickName']:
                    #         return

                    print('[*] 添加好友申请', key)
                    url = '%s/webwxverifyuser?r=%s&pass_ticket=%s' % (
                        self.base_uri, int(time.time()), self.pass_ticket)
                    data = {
                        'BaseRequest': self.BaseRequest,
                        'Opcode': status,
                        'VerifyUserListSize': 1,
                        'VerifyUserList': [{
                            'Value': userName,
                            'VerifyUserTicket': VerifyUserTicket, }],
                        'VerifyContent': '',
                        'SceneListCount': 1,
                        'SceneList': [33],
                        'skey': self.skey, }

                    time.sleep(random.randint(60, 5 * 60))
                    self.mywebwxstatusnotify()
                    time.sleep(random.randint(5, 10))

                    r = self._post(url, data)
                    if r['BaseResponse']['Ret'] != 0:
                        print('[*] 添加失败,请联系管理员', r)
                    else:
                        print('[*] 添加成功', key)
                        if self.db.isFriend(key):
                            return

                        self.db.insertFriend(key, -1)
                        self.db.commit()
                        # self.webwxgetcontact()
                        msg['RecommendInfo']['RemarkName'] = msg['RecommendInfo']['NickName']
                        self.ContactList.append(msg['RecommendInfo'])
                        self.MemberList.append(msg['RecommendInfo'])
                        self.MemberCount += 1

                        name = msg['RecommendInfo']['UserName']

                        with open("./myJson/AfterAddFriendToReply.json", encoding='utf-8') as fin:
                            msgs = json.load(fin)
                            msgIndex = random.randint(0, len(msgs) - 1)
                            for i, m in enumerate(msgs):
                                if i == msgIndex:
                                    replyKey = m
                                    break
                        time.sleep(random.randint(10, 30))
                        if self.db.getFriendState(key) != -1:
                            return
                        self.webwxsendmsg(msgs[replyKey], name)
                        time.sleep(5 * 60)
                        with open("./myJson/AddwaitFive.json", encoding='utf-8') as fin:
                            msgs = json.load(fin)
                            msgIndex = random.randint(0, len(msgs) - 1)
                            for i, m in enumerate(msgs):
                                if i == msgIndex:
                                    replyKey = m
                                    break
                        if self.db.getFriendState(key) != -1:
                            return
                        self.webwxsendmsg(msgs[replyKey], name)
                        time.sleep(5 * 60)

                        with open('./myJson/AddSecWaitFive.json') as fin:
                            msgs = json.load(fin)
                            for i, m in enumerate(msgs):
                                if i == msgIndex:
                                    replyKey = m
                                    break
                        if self.db.getFriendState(key) != -1:
                            return
                        # self.sendMsg(name, msgs[replyKey])
                        self.webwxsendmsg(msgs[replyKey], name)
                        self.db.addFriendState(key)
                        self.db.commit()

                threading.Thread(target=add_friend_thread,
                                 args=(msg['RecommendInfo']['UserName'], msg['RecommendInfo']['Ticket'])).start()
                return

            def isTextMsg(msgType):
                return msgType == 1

            def isImgMsg(msgType):
                return msgType == 3

            def isKey(content):
                f = open("myJson/keyToCodeKey.json", encoding='utf-8')
                keyToCodeKey = json.load(f)
                f.close()
                myKeyContent = content
                iskey = False
                for key in keyToCodeKey:
                    if key in myKeyContent:
                        iskey = True
                        print('[*]  识别的是关键词！')
                        break
                return iskey

            name = self.getUserRemarkName(msg['FromUserName'])
            # name = msg['FromUserName']
            # content = msg['Content'].replace('&lt;', '<').replace('&gt;', '>')
            msgid = msg['MsgId']

            alias = self.getUserAlias(name)
            if alias is None:
                alias = name

            if not self.db.isFriend(alias):
                # self.db.insertFriend(name, 100)
                # self.db.commit()
                print(alias, name, 'not firend')
                continue

            state = self.db.getFriendState(alias)

            if state == -1:
                if not isTextMsg(msgType) and not isImgMsg(msgType):
                    return
                self.db.addFriendState(alias)
                self.db.addFriendState(alias)
                self.db.commit()
                state += 2

            if state == 0:
                if isTextMsg(msgType) and isKey(content):
                    print('[*] 收到关键字')
                    self.db.addFriendState(alias)

                    self.db.commit()
                    state += 1

            if state == 1:
                def tfun0(name, alias):
                    with open("./myJson/FmsgAndImg.json", encoding='utf-8') as fin:
                        msgs = json.load(fin)
                    index = random.randint(0, len(msgs) - 1)
                    for i, key in enumerate(msgs):
                        if i == index:
                            replyKey = key
                            break
                    msg = msgs[replyKey]
                    index = random.randint(0, len(msg['img']) - 1)
                    for i, img in enumerate(msg['img']):
                        if i == index:
                            replyImg = msg['img'][img]
                            break
                    msgText = msg['msg']

                    # r = self.webwxuploadmedia(replyImg)
                    # mediaId = r['MediaId']
                    # self.webwxsendmsgimg(name, mediaId)
                    self.db.setFriendState(alias, -2)
                    self.db.commit()
                    time.sleep(random.randint(60, 60 * 2))
                    # self.db.setFriendState(alias, 1)
                    # self.db.commit()
                    self.sendImg(name, replyImg)
                    time.sleep(1)
                    # self.webwxsendmsg(msgText, name)
                    self.sendMsg(name, msgText)
                    self.db.setFriendState(alias, 2)
                    self.db.commit()

                    time.sleep(30 * 60)
                    if self.db.getFriendState(alias) > 2:
                        return
                    self.db.setFriendState(alias, 0)
                    self.db.commit()

                threading.Thread(target=tfun0, args=(name, alias)).start()

            elif state == 2:  # 等待图图片
                if not isImgMsg(msgType):
                    return
                self.db.addFriendState(alias)
                self.db.commit()
                state = 3
            if state == 3:  # 收到图片后
                def fun3(name, alias):

                    self.db.setFriendState(alias, -2)
                    self.db.commit()
                    with open('./myJson/MsgFour.json', encoding='utf-8') as fin:
                        msgs = json.load(fin)
                        index = random.randint(0, len(msgs) - 1)
                        for i, key in enumerate(msgs):
                            if i == index:
                                replyMsg = msgs[key]
                                break
                    time.sleep(random.randint(10, 30))
                    self.sendMsg(name, replyMsg)

                    time.sleep(random.randint(60, 60 * 2))

                    with open('./myJson/SmsgAndImg.json', encoding='utf-8') as fin:
                        msgs = json.load(fin)
                        index = random.randint(0, len(msgs) - 1)
                        for i, k in enumerate(msgs):
                            if index == i:
                                replyMsg = msgs[k]
                    self.sendImg(name, replyMsg['img'])
                    time.sleep(1)
                    self.sendMsg(name, replyMsg['msg'])

                    self.db.setFriendState(alias, 4)
                    self.db.commit()

                    time.sleep(5 * 60)
                    if self.db.getFriendState(alias) == 4:
                        with open('./myJson/noMsgTips.json', encoding='utf-8') as fin:
                            msgs = json.load(fin)
                            index = random.randint(0, len(msgs))
                            for i, k in enumerate(msgs):
                                if index == i:
                                    replyMsg = msgs[k]
                                    break
                        self.sendMsg(name, replyMsg)
                        time.sleep(60 * 60)  # 超过一小时重置
                        if self.db.getFriendState(alias) == 4:
                            self.db.setFriendState(alias, 0)
                            self.db.commit()

                threading.Thread(target=fun3, args=(name, alias)).start()
            elif state == 4:  # 等待数字
                if not isTextMsg(msgType):
                    return
                num = -1
                try:
                    print(content)
                    num = int(content)
                except:
                    print('[*] 转化失败', content)
                if num < 1 or num > 22:
                    with open('./myJson/NotNumTips.json', encoding='utf-8') as fin:
                        msgs = json.load(fin)
                        index = random.randint(0, len(msgs) - 1)
                        for i, k in enumerate(msgs):
                            if i == index:
                                replyMsg = msgs[k]
                                break
                    self.sendMsg(name, replyMsg)
                    return

                def fun4(name, alias):

                    self.db.setFriendState(alias, -2)
                    self.db.commit()

                    with open('./myJson/TenSecMsg.json', encoding='utf-8') as fin:
                        msgs = json.load(fin)
                    index = random.randint(0, len(msgs) - 1)
                    for i, k in enumerate(msgs):
                        if i == index:
                            replyMsg = msgs[k]
                            break
                    index = random.randint(0, len(replyMsg) - 1)
                    for i, k in enumerate(replyMsg):
                        if i == index:
                            m = replyMsg[k]
                            break
                    replyImg = m['img']
                    replyMsgs = m['msg']
                    time.sleep(random.randint(10, 30))
                    self.sendImg(name, replyImg)
                    time.sleep(1)
                    for i in range(1, len(replyMsgs)):
                        k = 'msg' + str(i)
                        if k in replyMsgs.keys():
                            if replyMsgs[k] != "":
                                self.sendMsg(name, replyMsgs[k])
                                time.sleep(random.randint(20, 30))
                    self.db.setFriendTime(alias)
                    self.db.setFriendState(alias, 5)
                    self.db.commit()

                threading.Thread(target=fun4, args=(name, alias)).start()
            elif state == 5:
                if isKey(content):
                    self.sendMsg(name, '宝宝才占卜过吧，我记得应该没到一周吧，连续占卜可是对运势无益的')

            print(name, 'state :', state)

    def startDomean(self):

        def tfun(self):
            while True:
                time.sleep(random.randint(10, 60))
                index = random.randint(0, len(self.ContactList) - 1)
                string = time.strftime('%Y-%m-%d %H-%M-%S', time.localtime(time.time()))

                if self.webwxsendmsg(string):
                    print(string, 'aliving')
                else:
                    print(string, 'died !')

        threading.Thread(target=tfun, args=(self,)).start()
        print('[*] 伪装线程启动')

    def startDailyThread(self):
        def fun(self):
            time.sleep(24 * 60 * 60)
            self.db.updatedb()

        threading.Thread(target=fun, args=(self,)).start()
        print('[*] 日常清理线程启动')

    def startRandomSelectThread(self):
        with open('./myJson/AfterAddFriendToReply.json', encoding='utf-8') as fin:
            msgs = json.load(fin)

        def tfun(self):
            time.sleep(60 * 60)
            index = random.randint(0, len(msgs) - 1)
            for i, m in enumerate(msgs):
                if i == index:
                    msg = msgs[m]
            name = self.db.getRandomFriend()
            self.db.setFriendTime(name)
            self.sendMsg(name, msg)

        threading.Thread(target=tfun, args=(self,)).start()
        print('[*] 随机发送线程启动')

    def listenMsgMode(self):
        print('[*] 进入消息监听模式 ... 成功')
        logging.debug('[*] 进入消息监听模式 ... 成功')
        self._run('[*] 进行同步线路测试 ... ', self.testsynccheck)
        playWeChat = 0
        redEnvelope = 0
        while True:
            self.lastCheckTs = time.time()
            [retcode, selector] = self.synccheck()
            if self.DEBUG:
                print('retcode: %s, selector: %s' % (retcode, selector))
            logging.debug('retcode: %s, selector: %s' % (retcode, selector))
            if retcode == '1100':
                print('[*] 你在手机上登出了微信，债见')
                logging.debug('[*] 你在手机上登出了微信，债见')
                break
            if retcode == '1101':
                print('[*] 你在其他地方登录了 WEB 版微信，债见')
                logging.debug('[*] 你在其他地方登录了 WEB 版微信，债见')

                del self.db

                break
            elif retcode == '0':
                if selector == '2':
                    r = self.webwxsync()
                    if r is not None:
                        self.handleMsg(r)
                elif selector == '6':
                    # TODO
                    redEnvelope += 1
                    print('[*] 收到疑似红包消息 %d 次' % redEnvelope)
                    logging.debug('[*] 收到疑似红包消息 %d 次' % redEnvelope)
                    r = self.webwxsync()
                    if r is not None:
                        self.handleMsg(r)

            elif selector == '7':
                playWeChat += 1
                print('[*] 你在手机上玩微信被我发现了 %d 次' % playWeChat)
                logging.debug('[*] 你在手机上玩微信被我发现了 %d 次' % playWeChat)
                r = self.webwxsync()
            elif selector == '0':
                time.sleep(1)
            if (time.time() - self.lastCheckTs) <= 20:
                time.sleep(time.time() - self.lastCheckTs)

    def sendMsg(self, name, word, isfile=False):
        id = self.getUSerID(name)
        if id:
            if isfile:
                with open(word, 'r') as f:
                    for line in f.readlines():
                        line = line.replace('\n', '')
                        self._echo('-> ' + name + ': ' + line)
                        if self.webwxsendmsg(line, id):
                            print(' [成功]')
                        else:
                            print(' [失败]')
                        time.sleep(1)
            else:
                if self.webwxsendmsg(word, id):
                    print('[*] 消息发送成功')
                    logging.debug('[*] 消息发送成功')
                else:
                    print('[*] 消息发送失败')
                    logging.debug('[*] 消息发送失败')
        else:
            print('[*] 此用户不存在')
            logging.debug('[*] 此用户不存在')

    def mySendMsg(self, name, word, isfile=False):
        id = name
        if id:
            if isfile:
                with open(word, 'r') as f:
                    for line in f.readlines():
                        line = line.replace('\n', '')
                        self._echo('-> ' + name + ': ' + line)
                        if self.webwxsendmsg(line, id):
                            print(' [成功]')
                        else:
                            print(' [失败]')
                        time.sleep(1)
            else:
                if self.webwxsendmsg(word, id):
                    print('[*] 消息发送成功')
                    logging.debug('[*] 消息发送成功')
                else:
                    print('[*] 消息发送失败')
                    logging.debug('[*] 消息发送失败')
        else:
            print('[*] 此用户不存在')
            logging.debug('[*] 此用户不存在')

    def sendMsgToAll(self, word):
        for contact in self.ContactList:
            name = contact['RemarkName'] if contact[
                'RemarkName'] else contact['NickName']
            id = contact['UserName']
            self._echo('-> ' + name + ': ' + word)
            if self.webwxsendmsg(word, id):
                print(' [成功]')
            else:
                print(' [失败]')
            time.sleep(1)

    def sendImg(self, name, file_name):
        response = self.webwxuploadmedia(file_name)
        media_id = ""
        if response is not None:
            media_id = response['MediaId']
        user_id = self.getUSerID(name)
        response = self.webwxsendmsgimg(user_id, media_id)

    def mySendImg(self, name, file_name):
        response = self.webwxuploadmedia(file_name)
        media_id = ""
        if response is not None:
            media_id = response['MediaId']
        response = self.webwxsendmsgimg(name, media_id)

    def sendEmotion(self, name, file_name):
        response = self.webwxuploadmedia(file_name)
        media_id = ""
        if response is not None:
            media_id = response['MediaId']
        user_id = self.getUSerID(name)
        response = self.webwxsendmsgemotion(user_id, media_id)

    @catchKeyboardInterrupt
    def start(self):
        self._echo('[*] 微信网页版 ... 开动')
        print()
        logging.debug('[*] 微信网页版 ... 开动')
        while True:
            self._run('[*] 正在获取 uuid ... ', self.getUUID)
            self._echo('[*] 正在获取二维码 ... 成功')
            print()
            logging.debug('[*] 微信网页版 ... 开动')
            self.genQRCode()
            print('[*] 请使用微信扫描二维码以登录 ... ')
            if not self.waitForLogin():
                continue
                print('[*] 请在手机上点击确认以登录 ... ')
            if not self.waitForLogin(0):
                continue
            break

        self._run('[*] 正在登录 ... ', self.login)
        self._run('[*] 微信初始化 ... ', self.webwxinit)
        self._run('[*] 开启状态通知 ... ', self.webwxstatusnotify)
        self._run('[*] 获取联系人 ... ', self.webwxgetcontact)
        self._echo('[*] 应有 %s 个联系人，读取到联系人 %d 个' %
                   (self.MemberCount, len(self.MemberList)))

        print()
        self._echo('[*] 共有 %d 个群 | %d 个直接联系人 | %d 个特殊账号 ｜ %d 公众号或服务号' % (len(self.GroupList),
                                                                         len(self.ContactList),
                                                                         len(self.SpecialUsersList),
                                                                         len(self.PublicUsersList)))
        print()
        self._run('[*] 获取群 ... ', self.webwxbatchgetcontact)
        logging.debug('[*] 微信网页版 ... 开动')
        if self.DEBUG:
            print(self)
        logging.debug(self)

        if self.interactive and input('[*] 是否开启自动回复模式(y/n): ') == 'y':
            self.autoReplyMode = True
            print('[*] 自动回复模式 ... 开启')
            logging.debug('[*] 自动回复模式 ... 开启')
        else:
            print('[*] 自动回复模式 ... 关闭')
            logging.debug('[*] 自动回复模式 ... 关闭')

        self.startDomean()
        self.startDailyThread()
        self.startRandomSelectThread()

        if sys.platform.startswith('win'):
            import _thread
            _thread.start_new_thread(self.listenMsgMode())
        else:
            listenProcess = multiprocessing.Process(target=self.listenMsgMode)
            listenProcess.start()

        print(self.uin)

        while True:
            text = input('')
            if text == 'quit':
                listenProcess.terminate()
                print('[*] 退出微信')
                logging.debug('[*] 退出微信')
                exit()
            elif text[:2] == '->':
                [name, word] = text[2:].split(':')
                if name == 'all':
                    self.sendMsgToAll(word)
                else:
                    self.sendMsg(name, word)
            elif text[:3] == 'm->':
                [name, file] = text[3:].split(':')
                self.sendMsg(name, file, True)
            elif text[:3] == 'f->':
                print('发送文件')
                logging.debug('发送文件')
            elif text[:3] == 'i->':
                print('发送图片')
                [name, file_name] = text[3:].split(':')
                self.sendImg(name, file_name)
                logging.debug('发送图片')
            elif text[:3] == 'e->':
                print('发送表情')
                [name, file_name] = text[3:].split(':')
                self.sendEmotion(name, file_name)
                logging.debug('发送表情')

    def _safe_open(self, path):
        if self.autoOpen:
            if platform.system() == "Linux":
                os.system("xdg-open %s &" % path)
            else:
                os.system('open %s &' % path)

    def _run(self, str, func, *args):
        self._echo(str)
        if func(*args):
            print('成功')
            logging.debug('%s... 成功' % (str))
        else:
            print('失败\n[*] 退出程序')
            logging.debug('%s... 失败' % (str))
            logging.debug('[*] 退出程序')
            exit()

    def _echo(self, str):
        sys.stdout.write(str)
        sys.stdout.flush()

    def _printQR(self, mat):
        for i in mat:
            BLACK = '\033[40m  \033[0m'
            WHITE = '\033[47m  \033[0m'
            print(''.join([BLACK if j else WHITE for j in i]))

    def _str2qr(self, str):
        print(str)
        qr = qrcode.QRCode()
        qr.border = 1
        qr.add_data(str)
        qr.make()
        # img = qr.make_image()
        # img.save("qrcode.png")
        # mat = qr.get_matrix()
        # self._printQR(mat)  # qr.print_tty() or qr.print_ascii()
        qr.print_ascii(invert=True)

    def _transcoding(self, data):
        if not data:
            return data
        result = None
        if type(data) == str:
            result = data
        elif type(data) != str:
            result = data.decode('utf-8')
        return result

    def _get(self, url: object, api: object = None) -> object:
        request = urllib.request.Request(url=url)
        request.add_header('Referer', 'https://wx.qq.com/')
        if api == 'webwxgetvoice':
            request.add_header('Range', 'bytes=0-')
        if api == 'webwxgetvideo':
            request.add_header('Range', 'bytes=0-')
        try:
            response = urllib.request.urlopen(request)
            data = response.read().decode('utf-8')
            logging.debug(url)
            return data
        except urllib.error.HTTPError as e:
            logging.error('HTTPError = ' + str(e.code))
        except urllib.error.URLError as e:
            logging.error('URLError = ' + str(e.reason))
        except http.client.HTTPException as e:
            logging.error('HTTPException')
        except Exception:
            import traceback
            logging.error('generic exception: ' + traceback.format_exc())
        return ''

    def _post(self, url: object, params: object, jsonfmt: object = True) -> object:
        if jsonfmt:
            data = (json.dumps(params)).encode()

            request = urllib.request.Request(url=url, data=data)
            request.add_header(
                'ContentType', 'application/json; charset=UTF-8')
        else:
            request = urllib.request.Request(
                url=url, data=urllib.parse.urlencode(params).encode(encoding='utf-8'))

        try:
            response = urllib.request.urlopen(request)
            data = response.read()
            if jsonfmt:
                # object_hook=_decode_dict)
                return json.loads(data.decode('utf-8'))
            return data
        except urllib.error.HTTPError as e:
            logging.error('HTTPError = ' + str(e.code))
        except urllib.error.URLError as e:
            logging.error('URLError = ' + str(e.reason))
        except http.client.HTTPException as e:
            logging.error('HTTPException')
        except Exception:
            import traceback
            logging.error('generic exception: ' + traceback.format_exc())

        return ''

    def _xiaodoubi(self, word):
        if word == 'test':
            return "nihao ma?"

        url = 'http://www.xiaodoubi.com/bot/chat.php'
        try:
            r = requests.post(url, data={'chat': word})
            return r.content
        except:
            return "让我一个人静静 T_T..."

    def _simsimi(self, word):
        key = ''
        url = 'http://sandbox.api.simsimi.com/request.p?key=%s&lc=ch&ft=0.0&text=%s' % (
            key, word)
        r = requests.get(url)
        ans = r.json()
        if ans['result'] == '100':
            return ans['response']
        else:
            return '你在说什么，风太大听不清列'

    def _searchContent(self, key, content, fmat='attr'):
        if fmat == 'attr':
            pm = re.search(key + '\s?=\s?"([^"<]+)"', content)
            if pm:
                return pm.group(1)
        elif fmat == 'xml':
            pm = re.search('<{0}>([^<]+)</{0}>'.format(key), content)
            if not pm:
                pm = re.search(
                    '<{0}><\!\[CDATA\[(.*?)\]\]></{0}>'.format(key), content)
            if pm:
                return pm.group(1)
        return '未知'


class UnicodeStreamFilter:
    def __init__(self, target):
        self.target = target
        self.encoding = 'utf-8'
        self.errors = 'replace'
        self.encode_to = self.target.encoding

    def write(self, s):
        #        if type(s) == str:
        #            s = s.decode('utf-8')
        s = s.encode(self.encode_to, self.errors).decode(self.encode_to)
        self.target.write(s)

    def flush(self):
        self.target.flush()


if sys.stdout.encoding == 'cp936':
    sys.stdout = UnicodeStreamFilter(sys.stdout)

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    if not sys.platform.startswith('win'):
        import coloredlogs

        coloredlogs.install(level='DEBUG')

    webwx = WebWeixin()
    webwx.start()
