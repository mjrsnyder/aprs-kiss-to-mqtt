###########################################################
# Copyright (C) 2025 Charles Snyder
#
#TODO:
# - logging
# - Reconnect to tnc on failure/disconnect
# - paho warning
# - get rid of the queue thing or at least make it threaded
###########################################################

import kiss
import ax25
import datetime
import queue
import json
from decouple import config
from paho.mqtt.client import Client
from time import sleep

# MQTT settings
MQTT_BROKER = config('MQTT_BROKER', default='127.0.0.1')
MQTT_PORT = config('MQTT_PORT', default=1884, cast=int)
MQTT_TOPIC = config('MQTT_TOPIC', default='aprs/packets')

# KISS TNC settings
KISS_TNC_HOST = config('KISS_TNC_HOST', default='127.0.0.1')
KISS_TNC_PORT = config('KISS_TNC_PORT', default='8001', cast=int) 

_frame_queue = queue.Queue()

def on_connect(client, userdata, flags, rc):
    """ MQTT connection callback """
    print('Connected to MQTT broker (rc={})'.format(rc))
    client.subscribe(MQTT_TOPIC)

def on_publish(client, userdata, mid):
    """ MQTT publish callback """
    print('Published message: {}'.format(mid))

def receive_callback(kiss_port, data):
    try:
        frame = ax25.Frame.unpack(data)
        _frame_queue.put((frame, datetime.datetime.now()))
    except:
        print('Failed to unpack packet')
    
def rebuild_callsign(callsign, ssid):
    full_callsign = callsign
    if ssid > 0:
        full_callsign += '-' + str(ssid)
    return full_callsign

def main():
    # Create an MQTT client instance
    mqtt_client = Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_publish = on_publish

    # Connect to the MQTT broker
    # TODO: try/except, reconnect logic, etc
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)

    # Connect to the TNC
    # TODO: try/except, reconnect logic, etc
    kiss_conn = kiss.Connection(receive_callback)
    kiss_conn.connect_to_server(KISS_TNC_HOST, int(KISS_TNC_PORT))

    mqtt_client.loop_start()

    try:
        while True:
            if not _frame_queue.empty():
                (frame, timestamp) = _frame_queue.get()
                
                msg = {
                    'src' : {
                        'call' : frame.src.call,
                        'ssid' : frame.src.ssid,
                        'is_repeater' : frame.src.repeater
                    },

                    'dst' : {
                        'call' : frame.dst.call,
                        'ssid' : frame.dst.ssid,
                        'is_repeater' : frame.dst.repeater
                    },

                    'via' : [

                    ],
                    'data' : None,
                    'timestamp' : '{:%Y-%m-%d %H:%M:%S}'.format(timestamp)
                }

                # I can't find a way to get the full ascii packet data to feed to mqtt so we have to put it back together
                header = rebuild_callsign(frame.src.call, frame.src.ssid)
                header += '>'
                header += rebuild_callsign(frame.dst.call, frame.dst.ssid)
                
                raw_data = None
                try:
                    raw_data = frame.data.decode('ascii')
                except:
                    raw_data = ''
                    print('Error parsing packet comment data')

                if frame.via is not None:
                    for repeater in frame.via:
                        via_hop = {
                            'call' : repeater.call,
                            'ssid' : repeater.ssid,
                            'has_been_repeated' : repeater.has_been_repeated,
                            'is_repeater' : repeater.repeater
                        }
                        msg['via'].append(via_hop)

                        # While we're here finish building the APRS header
                        header += ',' + rebuild_callsign(repeater.call, repeater.ssid)

                msg['data'] = header + ':' + raw_data

                mqtt_client.publish(MQTT_TOPIC, json.dumps(msg))

                print(msg)
    except KeyboardInterrupt:
        print('Exiting loop')

    mqtt_client.loop_stop()

if __name__ == '__main__':
    main()
