#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@author = 'wyx'
@time = 16/7/29 11:08
@annotation = '' 
"""

encoding = 'utf8'
pool_size = (3, 10)
db_config = {
    "db_reader": {"host": "127.0.0.1", "port": 3306, "db": "android_push",
                  "user": "root", "passwd": "wuyuxi08", "charset": encoding},
    "db_writer": {"host": "127.0.0.1", "port": 3306, "db": "android_push",
                  "user": "root", "passwd": "wuyuxi08", "charset": encoding},
}
FCM_CONFIG = {
    'URL': 'https://fcm.googleapis.com/fcm/send',
    'API_KEY': 'AIzaSyAk7t-GDiMyUYGC_5oxwoAoVAjSzs_afqc',
    'MAX_REGIDS': 1000,
    'LOW_PRIORITY': 'normal',
    'HIGH_PRIORITY': 'high',
    'MAX_SIZE_BODY': 2048,
    'TIME_TO_LIVE': (0, 2419200)
}

fcm_log = 'fcm-log'
query_log = 'query-log'
query_echo = True
LOG_CONFIG = [
    ['aiohttp.access', 'access.log', 'debug'],
    ['web-error', 'web-error.log', 'debug'],
    [fcm_log, 'fcm-service.log', 'debug'],
    [query_log, 'query.log', 'debug'],
]

app_path = ''
static_path = '/static'
