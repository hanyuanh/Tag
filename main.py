# 0. The phone(my tag) builds up a wifi connection with AP
# 1. The phone(my tag) sends out a FTM request to one access point
# 2. AP sends out FTM, the phone receives it and send back ACK to AP
# 3. AP receives ACK and calculates the round-trip time
import network
import time
import socket
import _thread
import select
# from awscrt import io, mqtt, auth, http
# from awsiot import mqtt_connection_builder
import time as t
import json
import machine
from umqtt.simple import MQTTClient

AP_SERVER_IP = '192.168.4.1'
AP_SERVER_PORT = 8088
TAG_SERVER_IP = '192.168.4.2'
TAG_SERVER_PORT = 8088
PINGPONG_INTERVAL_MS = 1000
# AWS endpoint parameters.
HOST = b'a1bj2v10qb7sqi-ats'    # ex: b'abcdefg1234567'
REGION = b'us-west-1'  # ex: b'us-east-1'

CLIENT_ID = "testDevice"  # Should be unique for each device connected.
AWS_ENDPOINT = b'%s.iot.%s.amazonaws.com' % (HOST, REGION)

# open('/certs/private.pem.key', 'r') as f
keyfile = '/private.pem.key'
try:
    with open(keyfile, 'r') as f:
        key = f.read()
except:
    print('failed to load private.pem.key')

certfile = "/certificate.pem.crt"
with open(certfile, 'r') as f:
    cert = f.read()

# SSL certificates.
SSL_PARAMS = {'key': key,'cert': cert, 'server_side': False}

# (ssid, pwd, port)
myaps = [('MicroPython-AP1', '123456789', 8088, '192.168.4.1'), 
('MicroPython-AP2', '123456789', 8088, '192.168.4.1')]
myap_to_data = {} # my_ap: (rssi, time_of_arrival)

def tag_setup():
    nic = network.WLAN(network.STA_IF)
    nic.active(True)
    # 0. The phone(my tag) builds up a wifi connection with AP
    nic.connect('MicroPython-AP', '123456789')
    while(nic.isconnected() == False):
        # print('.')
        time.sleep(1)
    # print("nic.ifconfig(): {}".format(nic.ifconfig()))

# def aws_setup():
#     pass

def send_to_aws(pptime):
    wlan = network.WLAN( network.STA_IF )
    wlan.active( True )
    wlan.connect( "204cv", "xiaopeng" )
    print('try to connect wifi')
    while not wlan.isconnected():
        machine.idle()
    # Connect to MQTT broker.
    print('wifi connected')
    mqtt = MQTTClient( CLIENT_ID, AWS_ENDPOINT, port = 8883, keepalive = 10000, ssl = True, ssl_params = SSL_PARAMS )
    mqtt.connect()
    # Publish a test MQTT message.
    m = 'hello AWS, pingpongtime = {}'.format(pptime)
    mqtt.publish( topic = 'test/tag', msg = m, qos = 0 )
    mqtt.disconnect()
    wlan.disconnect()

# tag_server receives 2 commands:
# 1. "ping": send back a 'pong'
# 2. 'pingpongtime': update pingpong time, and send to AWS
# data from recvfrom(): 
# 1. Ping!
# 2. pingpongtime!microsecs

# import select

# mysocket.setblocking(0)

# ready = select.select([mysocket], [], [], timeout_in_seconds)
# if ready[0]:
#     data = mysocket.recv(4096)

def recvfrom_with_timeout(start_time_ms, tag_server, tag_client, ap, nic, rssi):
    while time.ticks_ms() - start_time_ms < PINGPONG_INTERVAL_MS:
        data, addr = tag_server.recvfrom(1024)
        data_str = data.decode("utf-8").split('!')
        # print('data_str: {}'.format(data_str))
        if data_str[0] == 'Ping':
            # print('Ping received')
            # print('send pong')
            tag_client.sendto(bytes("Pong", "utf-8"), (ap[3], ap[2]))
        elif data_str[0] == 'pingpongtime':
            # print('Ping pong time received')
            pingpong_time = data_str[1]
            print('ppt:{}'.format(pingpong_time))
            print('rssi:{}'.format(rssi))
            if nic.isconnected():
                nic.disconnect()
            send_to_aws(pingpong_time)
            return
        else:
            # print(time.ticks_ms() - start_time_ms)
            print('Error')
    print('timeout')
    return

def update_toa(start_time, nic, ap, tag_server):
    if tag_server: #     if tag_server.type == 'SocketKind.SOCK_STREAM':
        nic.connect(ap[0], ap[1])
        while not nic.isconnected() and time.time() - start_time <= 1:
            print('.', end = '')
            time.sleep(0.1)
        if not nic.isconnected():
            print("{} NOT connected".format(ap[0]))
            nic.disconnect()
            return
        else:
            print('{} connected'.format(ap[0]))
            # 1. build up TCP connection
            tag_server.connect((AP_SERVER_IP, AP_SERVER_PORT))
            while True:
                start_time_toa = time.ticks_us()
                tag_server.send('send me back TOA')
                data = tag_server.recv(1024)
                if not data:
                    break
                else:
                    time_of_arrival = time.ticks_us() - start_time_toa
                    print("time_of_arrival: {}".format(time_of_arrival))
        return
    rssi = 0
    # ap = (ssid, pwd, port, ipaddr)
    nic.connect(ap[0], ap[1])
    # print(myap)
    # print('myap[0]: {} myap[1]: {}'.format(myap[0], myap[1]))
    while not nic.isconnected() and time.time() - start_time <= 1:
        print('.', end = '')
        time.sleep(0.1)
    if not nic.isconnected():
        print("{} NOT connected".format(ap[0]))
        nic.disconnect()
        return
    else:
        print('{} connected'.format(ap[0]))
        wifis = nic.scan()
        # wifi = (ssid, bssid, channel, RSSI, authmode, hidden)
        for wifi in wifis:
            if wifi[0] == ap[0].encode('utf-8'):
                rssi = wifi[3]
        tag_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tag_client.sendto(bytes("FTMRequest!from xxx", "utf-8"), (ap[3], ap[2]))
        # print("before tag_server.recvfrom()")
        # if recvfrom() > 1s:
        #   close nic connection
        #   return overtime
        # elif recvfrom() == have sth returned
        recvfrom_with_timeout(time.ticks_ms(), tag_server, tag_client, ap, nic, rssi)
        # print('Out of recvfrom()')
        tag_client.close()
    if nic.isconnected():
        nic.disconnect()

def scanWifi(nic):
    tmp = nic.scan()
    return tmp

def main():
    print('main')
    # setup
    nic = network.WLAN(network.STA_IF)
    nic.active(True)
    # udp server
    # tag_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # tag_server.bind((TAG_SERVER_IP, TAG_SERVER_PORT))
    
    # TCP Client: the tag should try to connect to ap (server)
    tag_server_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # tag_server_tcp.bind((TAG_SERVER_IP, TAG_SERVER_PORT))
    # tag_server_tcp.listen()

    # main magic
    while True:
        networks = scanWifi(nic)
        network_names = [networks[i][0] for i in range(len(networks))]
        # print(network_names)
        for myap in myaps:
            if myap[0].encode('utf-8') in network_names:
                print("found: {}".format(myap[0]))
                # use 1s to try to connect and get time of arrival
                # otherwise treat it as not reachable
                update_toa(time.time(), nic, myap, tag_server_tcp)

main()