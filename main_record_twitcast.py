import os
import sys
import time
import json
import requests
import websocket

# record_status : status's description
# 0 : Nothing had Happened
# 1 : Internet Connection OK
# 2 : Twitcast API Connection OK
# 3 : Stream Status is True
# 4 : Stream Information Got
# 5 : WebSocket Long-lived Connection Start
# 6 : WebSocket Message Receive
# 7 : WebSocket Connection Closed

class Requester:
    def __init__(self, target_url):
        self.target = target_url
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
            (KHTML, like Gecko) Chrome/80.0.3987.122 Safari/537.36 Edg/80.0.361.62", 
            "Referer": ""
            }
        self.response = ""

    def _get_response(self):
        self.response = requests.get(self.target, headers=self.headers)
        self._response_status_check()
        return self.response

    def _response_status_check(self):
        if self.response.status_code != requests.codes.ok:
            # if response status is abnormal, return boolean false.
            return 0
    
    def get_text(self):
        return self._get_response().text

    def get_content(self):
        return self._get_response().content

class WebSocketLogConnection:
    def __init__(self,url,path,name):
        self.url = url
        self.path = path
        self.name = name
        self.ts_file = ""
        self.message_count = 0
        self.record_status = 4

    def on_message(self, message):
        self.record_status = 6
        if isinstance(message,str):
            print("[{0}] StatusCode: {2} {1}".format(get_time(),message,self.record_status))
            return 1
        self.ts_file.write(message)
        self.message_count += 1
        if not self.message_count % 100:
            con="[{0}] StatusCode: {1} WebSocket Message Receiving [MessageCount {2}].".format(get_time(),self.record_status,self.message_count)
            sys.stdout.write(con+'\r')

    def on_error(self, error):
        print("[{0}] {1}".format(get_time(),error))

    def on_close(self):
        self.ts_file.close()
        self.record_status = 7
        print("[{0}] StatusCode: {1} WebSocket Connection Closed.".format(get_time(),self.record_status))

    def start(self):
        if not os.path.exists('record_video/{0}'.format(self.name)): os.makedirs('record_video/{0}'.format(self.name))
        self.ts_file = open(self.path, 'wb')
        websocket.enableTrace(False)
        ws = websocket.WebSocketApp(self.url,
                                on_message = self.on_message,
                                on_error = self.on_error,
                                on_close = self.on_close)
        self.record_status = 5
        print("[{0}] StatusCode: {1} WebSocket Connection Start.".format(get_time(),self.record_status))
        ws.run_forever(origin="https://twitcasting.tv/")
        self.ts_file.close()

class TwitcastRecorder:

    def __init__(self, target_id):
        self.STREAM_API = "https://twitcasting.tv/streamserver.php?target={0}&mode=client".format(target_id)
        self.NAME = target_id
        self.record_status = 0
        self.host = ""
        self.id = ""

    def _get_host(self, response):
        if self.record_status<3: return 0
        response_dict = json.loads(response)
        host = response_dict.get('fmp4').get('host')
        id = response_dict.get('movie').get('id')
        if host and id:
            self.host, self.id = host, id
            self.record_status=4; return 1
        else: return 0

    def check_proxy_status(self):
        # testing if google is connectable.
        requester = Requester("https://www.google.com")
        requester._get_response()
        if requester._response_status_check(): return 0
        else: self.record_status=1; return 1

    def check_stream_status(self):
        if self.record_status<1: return 0
        requester = Requester(self.STREAM_API)
        response_text = requester.get_text()
        if requester._response_status_check(): self.record_status=2; return 0
        live_status = response_text.find("\"live\":true")
        if live_status != -1:
            self.record_status=3
            if not self._get_host(response_text): return 0
            return 1
        else: return 0

    def get_stream(self):
        if self.record_status!=4: return 0
        STREAM_URL = "wss://{0}/ws.app/stream/{1}/fmp4/bd/1/1500?mode=source".format(self.host, self.id)
        DIR = "record_video/{0}/{0}_{1}_{2}.ts".format(self.NAME,get_pure_time(),self.id)
        ws = WebSocketLogConnection(STREAM_URL, DIR, self.NAME)
        ws.start()

def get_time():
    return time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
def get_pure_time():
    return time.strftime('%Y%m%d_%H%M%S',time.localtime(time.time()))

def main():
    if len(sys.argv) == 1: print("[{0} Please input USER_ID]".format(get_time()))
    if len(sys.argv) == 2: USER_ID = sys.argv[1]; INTERVAL=60
    if len(sys.argv) == 3: INTERVAL = sys.argv[2]
    
    t = TwitcastRecorder(USER_ID)
    while True:
        if not t.check_proxy_status(): print("[{0}] StatusCode: {1} ProxyError, retry after {2}.".format(get_time(),t.record_status,INTERVAL));time.sleep(INTERVAL);continue
        if not t.check_stream_status(): print("[{0}] StatusCode: {1} Live has NOT started, retry after {2}.".format(get_time(),t.record_status,INTERVAL));time.sleep(INTERVAL);continue
        elif t.record_status == 4: print("[{0}] StatusCode: {1} Live has started, try to record.".format(get_time(),t.record_status)); t.get_stream()

if __name__ == "__main__":
    main()