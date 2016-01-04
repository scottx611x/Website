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

# --- ParkLab Slack creds --- 
# slack = Slacker(credentials[2])

# --- Your Slack creds --- 
slack = Slacker(credentials[1])

ssh = paramiko.SSHClient()
ssh.load_system_host_keys()

data = []
data2 = []
park_lab = {}
park_lab_home = {}

# --- SSH into Orchestra and run quota command --- 
ssh.connect("orchestra.med.harvard.edu", username="so108", password=credentials[0])
stdin, stdout, stderr = ssh.exec_command("quota /n/data1/hms/dbmi/park")
stdin.close()
for line in stdout.read().splitlines():
    data.append(line)

# --- Execute command to find individual users data usage ---
stdin, stdout, stderr = ssh.exec_command("less /groups/shared_databases/rcbio/report/report_for_so108.txt")
stdin.close()
for line in stdout.read().splitlines():
    data2.append(line)

for index, line in enumerate(data):
    if "/n/data1/hms/dbmi/park [g]" in line:
        things = re.findall(r'[/].+[/]{0,}\s', line)
        if things:
            park_lab[things[0].split("]")[0] + "]"] = {'usage':re.split('\s+',data[index + 3])[2], 'warning':re.split('\s+',data[index + 3])[3], 'limit':re.split('\s+',data[index + 3])[4]}

# --- Create file with user data ---
with open("/var/www/Website/scripts/python/user_data.txt", "w+") as f:
    for index, line in enumerate(data2):
        if "user" in line:
            try:
                x = re.split('\s+', line) 
                f.write("{1}    {0}{2}".format(x[2],line.split(")")[1].strip(), "\n"))
            except IndexError:
                pass
                
# --- Use the created data --- 
with open("/var/www/Website/scripts/python/user_data.txt", "r") as f:
    for line in f:
        x = re.split('\s+', line)
        park_lab_home[x[1]] =  x[0]

# --- Populate and create plotly graph --- 
labels = ["%s:%s" % (item, park_lab_home[item]) for item in park_lab_home]
labels.append('Free Space:' + sizeof_fmt(humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['limit']) - humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['usage'])))

values = [humanfriendly.parse_size(park_lab_home[item]) for item in park_lab_home]
values.append(humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['limit']) - humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['usage']))

figure = {
    'data': [{
                'labels': labels,
                'values': values, 
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
        'title': 'ORCHESTRA DATA USAGE FOR PARKLAB (Limit:%s) %s' % (sizeof_fmt(humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['limit'])), time.strftime("%m/%d/%Y"))
    }
}
# --- Plot graph --- 
url = py.plot(figure, filename='DataUsage' + time.strftime("%m/%d/%Y"))

# --- Save Static Image ---
py.image.save_as(figure, 'DataUsageParkLab.png')

# --- Post Message to slack channel ---
# --- ParkLab Slack --- 
# slack.chat.post_message('#orchestra_data_usage', "Interactive Graph -> "+url+".embed", as_user=True)

# --- Your Slack --- 
slack.chat.post_message('#general', "Interactive Graph -> "+url+".embed", as_user=True)
