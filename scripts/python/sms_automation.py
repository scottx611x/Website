# -*- coding: utf-8 -*-
# Scott Ouellette 2-14-1016
# Automate various tasks by sending text messages to a Flask server

# For Example: Send a 🍕  and order your pizza for ParkLab meetings automatically

from __future__ import print_function
import os
import re
import sys
import urllib2
import smtplib
import datetime
import twilio.twiml
from twilio.rest import TwilioRestClient
from flask import Flask, request, redirect
from flask_phantom_emoji import PhantomEmoji

# Read in credentials from config file
with open('/var/www/html/Website/scripts/python/config') as f:
      credentials = [x.strip() for x in f.readlines()]
      account = credentials[3]
      token = credentials[4]
      client = TwilioRestClient(account, token)

# Instantiate Flask app and allow handling of emojis
app = Flask(__name__)
PhantomEmoji(app)

@app.route("/", methods=['GET', 'POST'])
def handle_request():
    users = {"+12075136000": "Scott Ouellette"}
    from_number = request.values.get('From')
    body = unicode(request.values.get("Body"))
    
    if from_number in users:
        name = users[from_number]
        
        # If theres a pizza emoji in the HTTP request
        if u"\U0001F355" in body:    
            try:
                d = datetime.date.today()

                while d.weekday() != 4:                                                                                  d += datetime.timedelta(1)

                fromaddr = 'scottx611x@gmail.com'
                toaddrs  = 'scottx611x@gmail.com'
                cc = ['Scott_Ouellette@hms.harvard.edu']
		
		msg = "Subject: Pizza Order" 
                msg +=  "CC: %s\r\n" % ",".join(cc)
                msg += '''
Hello,

I’d like to place an order to be delivered between 11:30-11:45 to the 4th floor of Countway Library at Harvard Medical School on Friday, {}:
  
1 Large Cheese
1 Large Buffalo Chicken & Bacon w/ blue cheese
1 Large Veggie
1 Large Supreme
1 Large Margarita
1 2-liter diet Pepsi
 
You should have Aimee Smith’s (cc’d) credit card information on file.
 
If you have any questions please let me know!
 
Best,
Scott Ouellette
'''.format(d.strftime('%m/%d'))

                username = 'scottx611x@gmail.com'
                password = credentials[5]

                # Send an email
                server = smtplib.SMTP('smtp.gmail.com:587')
                server.starttls()
                server.login(username,password)
                server.sendmail(fromaddr, toaddrs, msg)
                server.quit()
                message = "Thanks %s, your Pizza Order has been sent! %s%s%s" % (name, u"\U0001F355", u"\U0001F355", u"\U0001F355")
                client.messages.create(to=from_number, from_="+15106626969", body=message)
            
            except Exception as e:
                with open("srv_log", "w+") as f:
                    print("Something bad happened", e, file=f)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
