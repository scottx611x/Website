import re
import time
import smtplib
import paramiko
from slacker import Slacker
import plotly.plotly as py
import plotly.graph_objs as go
from plotly.graph_objs import Figure
import humanfriendly

# Return file size in human readable format
def sizeof_fmt(num, suffix=''):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)

with open('config') as f:
  credentials = [x.strip() for x in f.readlines()]

slack = Slacker(credentials[1])
ssh = paramiko.SSHClient()
ssh.load_system_host_keys()

data = []
park_lab = {}

# SSH into Orchestra and run quota command
try:
    ssh.connect("orchestra.med.harvard.edu", username="so108", password=credentials[0])
    stdin, stdout, stderr = ssh.exec_command("quota /n/data1/hms/dbmi/park")
    stdin.close()
    for line in stdout.read().splitlines():
        data.append(line)

except Exception as e:
    print "Something went wrong", e

for index, line in enumerate(data):
    if "/n/data1/hms/dbmi/park [g]" in line:
        things = re.findall(r'[/].+[/]{0,}\s', line)
        if things:
            park_lab[things[0].split("]")[0] + "]"] = {'usage':re.split('\s+',data[index + 3])[2], 'warning':re.split('\s+',data[index + 3])[3], 'limit':re.split('\s+',data[index + 3])[4]}

# Populate and create plotly graph
figure = {
    'data': [{'labels': [
                    'Used Space: ' + park_lab['/n/data1/hms/dbmi/park [g]']['usage'],
                    'Free Space: ' + sizeof_fmt(humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['limit']) - humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['usage']))
                ],
              'values': [
                    humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['usage']),  
                    humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['limit']) - humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['usage'])
                ],
              'type': 'pie'}],
    'layout': {'title': 'ORCHESTRA DATA USAGE FOR PARK LAB: ' + time.strftime("%m/%d/%Y")}
}

# Plot graph
url = py.plot(figure, filename='DataUsage' + time.strftime("%m/%d/%Y"))

# Post Message to slack channel
slack.chat.post_message('#orchestra_data_usage', url, as_user=True)