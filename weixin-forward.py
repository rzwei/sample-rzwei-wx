import itchat
import requests


def tulingReply(msg, key):
    apiUrl = 'http://www.tuling123.com/openapi/api'
    data = {
        'key': 'b1219f3a0fef4562a1d4bba2db76eb9c',  # 如果这个Tuling Key不能用，那就换一个
        'info': msg,  # 这是我们发出去的消息
        'userid': key,  # 这里你想改什么都可以
    }
    r = requests.post(apiUrl, data).json()
    return r.get('text', '我好像出了些问题')


@itchat.msg_register(itchat.content.TEXT)
def fun(msg):
    key = itchat.search_friends(userName=msg['FromUserName'])

    if type(key) is list:
        key = key[0]['NickName']
    elif type(key) is dict:
        key = key['NickName']
    else:
        return
    reply = tulingReply(msg['Text'], key)
    return reply


if __name__ == '__main__':
    itchat.auto_login(hotReload=True)
    itchat.run()
