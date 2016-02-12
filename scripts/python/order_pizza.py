# -*- coding: utf-8 -*-
# Scott Ouellette 2-12-1016
# Pizza ordering script
# Send a 🍕  and order your pizza for ParkLab meetings automatically

from __future__ import print_function
import os
import re
import sys
import urllib2
import smtplib
from flask import Flask, request, redirect
import twilio.twiml
from twilio.rest import TwilioRestClient
from flask_phantom_emoji import PhantomEmoji

with open('/var/www/html/Website/scripts/python/config') as f:
      credentials = [x.strip() for x in f.readlines()]
      account = credentials[3]
      token = credentials[4]
      client = TwilioRestClient(account, token)

app = Flask(__name__)
PhantomEmoji(app)

@app.route("/", methods=['GET', 'POST'])
def order_pizza():
    """Orders pizza based on sender's "user" status and if the GET body has a pizza emoji"""
    
    users = {"+12075136000": "Scott Ouellette"}
    from_number = request.values.get('From')
    body = unicode(request.values.get("Body"))
    
    if from_number in users:
        name = users[from_number]
        
        if u"\U0001F355" in body:    
            try:
                fromaddr = 'scottx611x@gmail.com'
                toaddrs  = 'scottx611x@gmail.com'
                msg = 'Pizza please?'

                username = 'scottx611x@gmail.com'
                password = credentials[5]

                # Send an email
                server = smtplib.SMTP('smtp.gmail.com:587')
                server.starttls()
                server.login(username,password)
                server.sendmail(fromaddr, toaddrs, msg)
                server.quit()
                message = "Thanks %s, your Pizza Order has been sent! :)" % name
                client.messages.create(to="+12075136000", from_="+15106626969", body=message)
            
            except Exception as e:
                with open("srv_log", "w+") as f:
                    print("Something bad happened", e, file=f)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
