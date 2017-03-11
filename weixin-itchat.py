import json
import random
import sqlite3
import threading
import time

import itchat
import requests

db = None


class dbHelper:
    def __init__(self, dbName):
        self.lock = threading.Lock()
        self.db = sqlite3.connect(dbName, check_same_thread=False)
        self.cx = self.db.cursor()
        self.cx.execute(
            "CREATE TABLE IF NOT EXISTS friends  (userid TEXT PRIMARY KEY, state INT,message TEXT,updatetime INT)")
        self.commit()

    def insertFriend(self, friendid, state=0, message='', updatetime=int(time.time())):

        if self.isFriend(friendid):
            # self.setFriendState(friendid, state)
            return

        self.lock.acquire()
        self.cx.execute("INSERT INTO friends VALUES (?,?,?,?)",
                        (friendid, state, message, updatetime))
        self.lock.release()

    def isFriend(self, friendid):
        self.lock.acquire()
        raws = self.cx.execute(
            "select * from friends where userid='%s'" % (friendid))
        self.lock.release()

        for r in raws:
            return True
        return False

    def getFriendState(self, friendid):
        self.lock.acquire()
        raws = self.cx.execute(
            "select state from friends WHERE userid='%s'" % (friendid))
        self.lock.release()

        for raw in raws:
            return raw[0]

    def setFriendState(self, friendid, state):
        self.lock.acquire()
        self.cx.execute(
            "update friends set state=%d where userid='%s'" % (state, friendid))
        self.lock.release()

    def addFriendState(self, friendid):
        self.lock.acquire()
        self.cx.execute(
            "update friends set state=state+1 WHERE userid='%s'" % (friendid))
        self.lock.release()

    def getFriendTime(self, friendid):
        self.lock.acquire()
        raws = self.cx.execute(
            "select updatetime from friends WHERE userid='%s'" % (friendid))
        self.lock.release()

        for raw in raws:
            return raw[0]

    def setFriendTime(self, friendid, t=int(time.time())):
        self.lock.acquire()
        self.cx.execute(
            "update friends set updatetime=%d WHERE userid='%s'" % (t, friendid))
        self.lock.release()

    def getRandomFriend(self):
        now = int(time.time())
        self.lock.acquire()
        raws = self.cx.execute(
            "select userid from friends where updatetime<=%d and state==0" % (now - 24 * 60 * 60))
        self.lock.release()

        users = []
        for raw in raws:
            users.append(raw)

        if len(users) > 0:
            index = random.randint(0, len(users) - 1)
            for i, raw in enumerate(users):
                if i == index:
                    return raw[0]
        else:
            return None

    def getWeekFriend(self):
        now = int(time.time())
        self.lock.acquire()
        raws = self.cx.execute(
            "select userid from friends where updatetime<=%d and state==5" % (now - 7 * 24 * 60 * 60))
        self.lock.release()
        users = []
        for raw in raws:
            users.append(raw)

        if len(users) > 0:
            index = random.randint(0, len(users) - 1)
            for i, raw in enumerate(users):
                if i == index:
                    return raw[0]
        else:
            return None

    def updatedb(self):
        self.lock.acquire()
        now = int(time.time())
        self.cx.execute(
            'update friends set state=0 where updatetime<=%d and state=5' % (now - 7 * 24 * 60 * 60))
        self.cx.execute('UPDATE friends SET state =0 WHERE state=-2')
        self.lock.release()

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


    def getAddFriendsFailed(self):
        self.lock.acquire()
        raws = self.cx.execute("SELECT message FROM friends WHERE state=-3")
        self.lock.release()

        ret = []
        for raw in raws:
            ret.append(raw[0])
        return ret

    def commit(self):
        self.lock.acquire()
        self.db.commit()
        self.lock.release()

    def __del__(self):
        self.commit()
        self.cx.close()
        self.db.close()


def add_friend_thread(msg):
    key = msg['RecommendInfo']['Alias']
    if key == '':
        key = msg['RecommendInfo']['NickName']
    # msg['RecommendInfo']['RemarkName'] = key

    print('[*] 添加好友申请', key)

    #
    # if flag == 0:
    #     tmsg = json.dumps(msg)
    # db.insertFriend(key, -3)
    # db.commit()

    time.sleep(random.randint(60, 5 * 60))

    itchat.add_friend(**msg['Text'])

    if db.isFriend(key):
        return

    db.insertFriend(key, -1)
    db.commit()

    name = msg['RecommendInfo']['UserName']
    with open("./myJson/AfterAddFriendToReply.json", encoding='utf-8') as fin:
        msgs = json.load(fin)
        msgIndex = random.randint(0, len(msgs) - 1)
        for i, m in enumerate(msgs):
            if i == msgIndex:
                replyKey = m
                break

    time.sleep(random.randint(5, 10))
    if db.getFriendState(key) != -1:
        return

    itchat.send(msgs[replyKey], name)

    with open('con.json', 'w', encoding='utf-8') as fout:
        json.dump(itchat.get_friends(), fout)

    time.sleep(random.randint(5 * 60, 60 * 10))
    with open("./myJson/AddwaitFive.json", encoding='utf-8') as fin:
        msgs = json.load(fin)
        msgIndex = random.randint(0, len(msgs) - 1)
        for i, m in enumerate(msgs):
            if i == msgIndex:
                replyKey = m
                break
    if db.getFriendState(key) != -1:
        return
    itchat.send(msgs[replyKey], name)

    time.sleep(random.randint(5 * 60, 10 * 60))
    with open('./myJson/AddSecWaitFive.json', encoding='utf-8') as fin:
        msgs = json.load(fin)
        for i, m in enumerate(msgs):
            if i == msgIndex:
                replyKey = m
                break
    if db.getFriendState(key) != -1:
        return
    itchat.send(msgs[replyKey], name)
    db.addFriendState(key)
    db.commit()


@itchat.msg_register(itchat.content.FRIENDS)
def add_friend(msg):
    threading.Thread(target=add_friend_thread,
                     args=(msg,)).start()


def isKey(content):
    f = open("myJson/keyToCodeKey.json", encoding='utf-8')
    keyToCodeKey = json.load(f)
    f.close()
    myKeyContent = content
    iskey = False
    for key in keyToCodeKey:
        if key in myKeyContent:
            iskey = True
            # print('[*] 识别的是关键词！')
            break
    return iskey


def startDomean():
    def tfun():
        while True:
            time.sleep(random.randint(60 * 5, 60 * 8))
            string = time.strftime('%Y-%m-%d %H-%M-%S', time.localtime(time.time()))
            if itchat.send(string, 'filehelper'):
                print(string, 'aliving')
            else:
                print(string, 'died !')

    threading.Thread(target=tfun).start()
    print('[*] 伪装线程启动')


# def startDailyThread():
#     def fun():
#         time.sleep(24 * 60 * 60)
#         db.updatedb()
#
#     threading.Thread(target=fun).start()
#     print('[*] 日常清理线程启动')


def eachWeekCheck():
    with open('./myJson/eachWeekTips.json', encoding='utf-8') as fin:
        msgs = json.load(fin)

    def tfun():
        while True:
            time.sleep(60 * 60)
            index = random.randint(0, len(msgs) - 1)
            for i, m in enumerate(msgs):
                if i == index:
                    msg = msgs[m]
            name = db.getWeekFriend()
            if name == None:
                continue
            db.setFriendTime(name)
            db.setFriendState(name, 0)
            db.commit()
            name = itchat.search_friends(name=name)
            try:
                if type(name) == list:
                    if len(name) != 0:
                        name = name[0]
                        itchat.send(msg, name['UserName'])
                elif type(name) == dict:
                    itchat.send(msg, name['UserName'])
            except Exception as e:
                print(e)

    threading.Thread(target=tfun).start()
    print('[*] 每周发送线程启动')


def dailyCheck():
    with open('./myJson/AfterAddFriendToReply.json', encoding='utf-8') as fin:
        msgs = json.load(fin)

    def tfun():
        while True:
            time.sleep(60 * 60)
            index = random.randint(0, len(msgs) - 1)
            for i, m in enumerate(msgs):
                if i == index:
                    msg = msgs[m]
            name = db.getRandomFriend()
            if name == None:
                continue
            db.setFriendTime(name)
            db.commit()
            name = itchat.search_friends(name=name)
            try:
                if type(name) == list:
                    if len(name) != 0:
                        name = name[0]
                        itchat.send(msg, name['UserName'])
                elif type(name) == dict:
                    itchat.send(msg, name['UserName'])
            except Exception as e:
                print(e)

    threading.Thread(target=tfun).start()
    print('[*] 随机发送线程启动')


def tulingReply(msg, key):
    apiUrl = 'http://www.tuling123.com/openapi/api'
    data = {
        'key': 'b1219f3a0fef4562a1d4bba2db76eb9c',  # 如果这个Tuling Key不能用，那就换一个
        'info': msg,  # 这是我们发出去的消息
        'userid': key,  # 这里你想改什么都可以
    }
    r = requests.post(apiUrl, data).json()
    return r.get('text', '我好像出了些问题')


@itchat.msg_register([itchat.content.NOTE])
def receiveHB(msg):
    if msg['Text'] == '收到红包，请在手机上查看':
        def fun():
            time.sleep(random.randint(2, 5))
            itchat.send('[色][色][色]哇哦～谢谢宝宝，thankssss[鼓掌]', msg['FromUserName'])

        threading.Thread(target=fun).start()


robotReply = False


@itchat.msg_register([itchat.content.TEXT, itchat.content.PICTURE])
def fun(msg):
    global robotReply

    if msg['ToUserName'] == 'filehelper':
        if msg['Text'] == 'shutdown robot':
            robotReply = False
            print('关闭robot')
        elif msg['Text'] == 'turn on robot':
            robotReply = True
            print('打开robot')
        return

    user = msg['FromUserName']

    user = itchat.search_friends(userName=user)

    if user == []:
        print(user, 'not found!1')
        t
        return

    key = user['Alias'] if user['Alias'] != '' else user['NickName']
    userid = user['UserName']
    content = msg['Content']

    if not db.isFriend(key):
        db.insertFriend(key, 0)
        db.commit()
        print('添加', key)

    state = db.getFriendState(key)

    if state == -1:
        db.addFriendState(key)
        db.addFriendState(key)
        db.commit()
        state += 2

    if state == 0:
        if isKey(content):
            print('[*] 收到关键字')
            db.addFriendState(key)
            db.commit()
            state += 1
        elif robotReply:
            def ttfun(userid):
                r = tulingReply(msg['Text'], key)
                time.sleep(random.randint(1, 5))
                itchat.send(r, userid)

            threading.Thread(target=ttfun, args=(userid,)).start()
    if state == 1:
        def tfun0(name, key):
            db.setFriendState(key, -2)
            db.commit()

            with open("./myJson/FmsgAndImg.json", encoding='utf-8') as fin:
                msgs = json.load(fin)

            index = random.randint(0, len(msgs) - 1)
            for i, keyi in enumerate(msgs):
                if i == index:
                    replyKey = keyi
                    break

            msg = msgs[replyKey]
            index = random.randint(0, len(msg['img']) - 1)

            for i, img in enumerate(msg['img']):
                if i == index:
                    replyImg = msg['img'][img]
                    break
            msgText = msg['msg']

            time.sleep(random.randint(10, 30))

            itchat.send_image(replyImg, name)
            time.sleep(1)
            itchat.send(msgText, name)

            db.setFriendState(key, 2)
            db.commit()

            # time.sleep(30 * 60)
            #
            # if db.getFriendState(key) > 2:
            #     return
            #
            # db.setFriendState(key, 0)
            # db.commit()

        threading.Thread(target=tfun0, args=(userid, key)).start()
    elif state == 2:  # 等待图图片
        if msg['Type'] != 'Picture':
            return
        db.addFriendState(key)
        db.commit()
        state = 3
    if state == 3:  # 收到图片后
        def fun3(name, key):
            db.setFriendState(key, -2)
            db.commit()
            with open('./myJson/MsgFour.json', encoding='utf-8') as fin:
                msgs = json.load(fin)
                index = random.randint(0, len(msgs) - 1)
                for i, keyi in enumerate(msgs):
                    if i == index:
                        replyMsg = msgs[keyi]
                        break
            time.sleep(random.randint(10, 20))
            itchat.send(replyMsg, name)
            time.sleep(random.randint(30, 60))
            with open('./myJson/SmsgAndImg.json', encoding='utf-8') as fin:
                msgs = json.load(fin)
                index = random.randint(0, len(msgs) - 1)
                for i, k in enumerate(msgs):
                    if index == i:
                        replyMsg = msgs[k]
            itchat.send_image(replyMsg['img'], name)
            time.sleep(1)
            itchat.send(replyMsg['msg'], name)

            db.setFriendState(key, 4)
            db.commit()

            print(key, '等待数字')

            time.sleep(5 * 60)
            if db.getFriendState(key) == 4:
                with open('./myJson/noMsgTips.json', encoding='utf-8') as fin:
                    msgs = json.load(fin)
                    index = random.randint(0, len(msgs))
                    for i, k in enumerate(msgs):
                        if index == i:
                            replyMsg = msgs[k]
                            break
                itchat.send(replyMsg, name)
                # time.sleep(60 * 60)  # 超过一小时重置
                # if db.getFriendState(key) == 4:
                #     db.setFriendState(key, 0)
                #     db.commit()

        threading.Thread(target=fun3, args=(userid, key)).start()
    elif state == 4:  # 等待数字
        if msg['Type'] != 'Text':
            return
        num = -1
        try:
            print(key, content)
            num = int(content)
        except:
            print(key, '[*] 转化失败', content)
        if num < 1 or num > 22:
            with open('./myJson/NotNumTips.json', encoding='utf-8') as fin:
                msgs = json.load(fin)
                index = random.randint(0, len(msgs) - 1)
                for i, k in enumerate(msgs):
                    if i == index:
                        replyMsg = msgs[k]
                        break
            itchat.send(replyMsg, userid)
            return

        def fun4(name, key):

            db.setFriendState(key, -2)
            db.commit()

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
            itchat.send_image(replyImg, name)
            time.sleep(1)
            for i in range(1, len(replyMsgs)):
                k = 'msg' + str(i)
                if k in replyMsgs.keys():
                    if replyMsgs[k] != "":
                        itchat.send(replyMsgs[k], name)
                        time.sleep(random.randint(20, 30))
            db.setFriendTime(key)
            db.setFriendState(key, 5)
            db.commit()

        threading.Thread(target=fun4, args=(userid, key)).start()
    elif state == 5:
        if isKey(content):
            itchat.send('宝宝才占卜过吧，我记得应该没到一周吧，连续占卜可是对运势无益的', userid)
        elif robotReply:
            def ttfun(userid):
                r = tulingReply(msg['Text'], key)
                time.sleep(random.randint(1, 5))
                itchat.send(r, userid)

            threading.Thread(target=ttfun, args=(userid,)).start()


def myQRCallback(uuid, status, qrcode):
    try:
        with open('server.ini', encoding='utf-8') as fin:
            serverPath = fin.readline()
    except:
        serverPath = ''
    picDir = serverPath + 'qr.png'
    # itchat.utils.print_cmd_qr(qrcode.text(1), enableCmdQR=2)
    with open(picDir, 'wb') as f:
        f.write(qrcode)
        # itchat.utils.print_qr(picDir)


def setProcessInfo():
    try:
        with open('server.ini', encoding='utf-8') as fin:
            serverPath = fin.readline()
    except:
        serverPath = ''
    print('serverPath:', serverPath)
    with open(serverPath + 'pinfo.ini', 'w', encoding='utf-8') as fout:
        import os
        # print(os.getcwd())
        fout.write(str(os.getpid()) + '\n')
        # with open(serverPath + 'path.ini', 'w', encoding='utf-8') as fout:
        #     import sys
        #     print(sys.argv[0])
        #     fout.write(sys.argv[0] + '\n')


def reAddFriends():
    friendlist = db.getAddFriendsFailed()

    if len(friendlist) == 0:
        return
    msgs = []
    for message in friendlist:
        msgs.append(json.loads(message))

    for msg in msgs:
        threading.Thread(target=add_friend_thread, args=(msg, 1)).start()


if __name__ == '__main__':

    robotReply = False

    setProcessInfo()

    itchat.auto_login(hotReload=False, qrCallback=myQRCallback)
    # time.sleep(10)
    friendsList = itchat.get_friends(update=False)
    # with open('contacts.json', 'w', encoding='utf-8') as fout:
    #     json.dump(friendsList, fout)
    myself = friendsList[0]

    db = dbHelper(str(myself['Uin']))
    for contact in friendsList[1:]:
        key = contact['Alias']
        if key == '':
            key = contact['NickName']
        if not db.isFriend(key):
            db.insertFriend(key)
    db.commit()

    # reAddFriends()
    startDomean()
    # dailyCheck()
    eachWeekCheck()

    itchat.run()
