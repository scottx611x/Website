"""
    orchestra_data_usage.py: 

    Creates interactive Plotly graph based on our home 
    directory on Orchestra and posts this info to our 
    Slack Channel.

"""
__author__ = "Scott Ouellette"
__email__ = "Scott_Ouellette@hms.harvard.edu"

import re
import time
import smtplib
import paramiko
from slacker import Slacker
import plotly.plotly as py
import plotly.graph_objs as go
from plotly.graph_objs import Figure
import humanfriendly

# --- Return file size in human readable format --- 
def sizeof_fmt(num, suffix=''):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)

with open('/var/www/Website/scripts/python/config') as f:
  credentials = [x.strip() for x in f.readlines()]

# --- Your Slack creds --- 
# slack = Slacker(credentials[1])

# --- ParkLab Slack creds --- 
slack = Slacker(credentials[2])

ssh = paramiko.SSHClient()
ssh.load_system_host_keys()

data = []
park_lab = {}
park_lab_home = {}

# --- SSH into Orchestra and run quota command --- 
ssh.connect("orchestra.med.harvard.edu", username="so108", password=credentials[0])
stdin, stdout, stderr = ssh.exec_command("quota /n/data1/hms/dbmi/park")
stdin.close()
for line in stdout.read().splitlines():
    data.append(line)

for index, line in enumerate(data):
    if "/n/data1/hms/dbmi/park [g]" in line:
        things = re.findall(r'[/].+[/]{0,}\s', line)
        if things:
            park_lab[things[0].split("]")[0] + "]"] = {'usage':re.split('\s+',data[index + 3])[2], 'warning':re.split('\s+',data[index + 3])[3], 'limit':re.split('\s+',data[index + 3])[4]}

# --- Fetch the sample data given from HMS-RC --- 
with open("test.txt", "r") as t:
    for line in t:
        x = re.split('\s+', line) 
        park_lab_home[x[2]] =  x[1]

# --- Populate and create plotly graph --- 
figure = {
    'data': [{
                'labels': ["%s:%s" % (item, park_lab_home[item]) for item in park_lab_home],
                'values': [humanfriendly.parse_size(park_lab_home[item]) for item in park_lab_home],
                "hoverinfo":"label+percent",
                'textinfo':'label+percent',
                'textposition':"inside",
                "hole": .5,
                'showlegend':False,
                'marker':{
                    'line':{
                        'width':2
                        },
                    },
                'type': 'pie'
            }],
    'layout': {
        'title': 'ORCHESTRA DATA USAGE FOR PARKLAB WEEK OF: ' + time.strftime("%m/%d/%Y"),
    }
}
# --- Plot graph --- 
url = py.plot(figure, filename='DataUsage' + time.strftime("%m/%d/%Y"))

# --- Post Message to slack channel ---

# --- ParkLab Slack --- 
slack.chat.post_message('#orchestra_data_usage', url, as_user=True)

# --- Your Slack --- 
# slack.chat.post_message('#general', url, as_user=True)
