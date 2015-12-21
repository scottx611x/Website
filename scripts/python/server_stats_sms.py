#!/usr/bin/python
import urllib2
import os, re
from twilio.rest import TwilioRestClient

with open('/var/www/Website/scripts/python/config') as f:
  credentials = [x.strip() for x in f.readlines()]

account = credentials[3]
token = credentials[4]
client = TwilioRestClient(account, token)

msg = "www.scott-ouellette.com " + u'\U0001F4BB'
msg += "\r\n\r\nAPACHE2:\r\n"
apache = urllib2.urlopen('http://www.scott-ouellette.com/server-status?auto').read()
apache = re.sub(r"Scoreboard:.*", "", apache)
msg += apache
def getDiskSpace():
    p = os.popen("df -h /")
    i = 0
    while 1:
        i = i +1
        line = p.readline()
        if i==2:
            return(line.split()[1:5])

# Disk information
DISK_stats = getDiskSpace()[3]
msg += "DISK USAGE:\r\n"
msg += str(100 - int(DISK_stats[:2])) + "% Free disk space on RPi."

message = client.messages.create(to="+12075136000", from_="+15106626969",
                                 body=msg)
