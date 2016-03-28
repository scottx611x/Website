"""
    orchestra_data_usage.py: 

    Creates interactive Plotly graph based on our home 
    directory on Orchestra and posts this info to our 
    Slack Channel.

"""
__author__ = "Scott Ouellette"
__email__ = "Scott_Ouellette@hms.harvard.edu"

import re
import os
import time
import collections
import datetime
from datetime import date, timedelta
import pickle
import colorsys
import smtplib
import paramiko
from slacker import Slacker
import plotly.plotly as py
import plotly.graph_objs as go
from plotly.graph_objs import Figure
import humanfriendly
from datadiff import diff

# --- Return file size in human readable format --- 
def sizeof_fmt(num, suffix=''):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)

with open('/var/www/html/Website/scripts/python/config') as f:
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

# Add ssh host if missing
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# --- SSH into Orchestra and run quota command --- 
ssh.connect("orchestra.med.harvard.edu", username="so108", password=credentials[0])
stdin, stdout, stderr = ssh.exec_command("quota /n/data1/hms/dbmi/park")
stdin.close()
for line in stdout.read().splitlines():
    data.append(line)

# --- SSH into Orchestra and find all real names for users ---
def get_full_names(orchestra_usernames):
    ssh.connect("orchestra.med.harvard.edu", username="so108", password=credentials[0])
    new_dict = {}
    for name, value in orchestra_usernames.items():
	stdin, stdout, stderr = ssh.exec_command("getent passwd {} | cut -d: -f5 | cut -d, -f1".format(name))
        stdin.close()
        for line in stdout.read().splitlines():
    	    if line:
                new_dict[line] = value
    return new_dict

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

today = date.today() + timedelta(days=1)

# --- Create file with user data ---
with open("/var/www/html/Website/scripts/python/%s_user_data.txt" % today, "w+") as f:
    for index, line in enumerate(data2):
        if "user" in line:
            try:
                x = re.split('\s+', line) 
                f.write("{1}    {0}{2}".format(x[2],line.split(")")[1].strip(), "\n"))
            except IndexError:
                pass
                
# --- Use the created data --- 
with open("/var/www/html/Website/scripts/python/%s_user_data.txt" % today, "r") as f:
    for line in f:
        x = re.split('\s+', line)
        park_lab_home[x[1]] =  x[0]

this_week = {}
last_week = {}
two_weeks_ago = {}
three_weeks_ago = {}

with open("/var/www/html/Website/scripts/python/%s_user_data.txt" % today) as f:
    for line in f:        
        x = re.split('\s+', line)
        this_week[x[1]] =  x[0]

seven_days = today - timedelta(days=7)
two_weeks = today - timedelta(days=14)
three_weeks = today - timedelta(days=21)

# Try opening last weeks file
try:
    with open("/var/www/html/Website/scripts/python/%s_user_data.txt" % seven_days, "r") as f:
        for line in f:
            x = re.split('\s+', line)   
	    last_week[x[1]] =  x[0]
except Exception as e:
    print "Could not open last week's data. It may not exist!", e

# Two weeks ago
try:
    with open("/var/www/html/Website/scripts/python/%s_user_data.txt" % two_weeks, "r") as f:
        for line in f:
            x = re.split('\s+', line)
            two_weeks_ago[x[1]] =  x[0]
except Exception as e:
    print "Could not open two week ago's data. It may not exist!", e

# Three weeks ago
try:
    with open("/var/www/html/Website/scripts/python/%s_user_data.txt" % three_weeks, "r") as f:
        for line in f:
            x = re.split('\s+', line)
            three_weeks_ago[x[1]] =  x[0]
except Exception as e:
    print "Could not open three week ago's data. It may not exist!", e

# Log differences in directories week to week 
with open("/var/www/html/Website/scripts/python/%s_data_diff.txt" % today, "w+") as f:
    f.write(diff(this_week,last_week).stringify())

# --- Sort the dicts ---
park_lab_home = sorted(park_lab_home.items(), key=lambda x:x[1], reverse=True)
park_lab_home = collections.OrderedDict(park_lab_home)
last_week = sorted(last_week.items(), key=lambda x:x[1], reverse=True)
last_week = collections.OrderedDict(last_week)
two_weeks_ago = sorted(two_weeks_ago.items(), key=lambda x:x[1], reverse=True)
two_weeks_ago = collections.OrderedDict(two_weeks_ago)
three_weeks_ago = sorted(three_weeks_ago.items(), key=lambda x:x[1], reverse=True)
three_weeks_ago = collections.OrderedDict(three_weeks_ago)

# --- Remove items that havent changed since last week ---
def remove_dups(dict1, dict2, dict3, dict4):
    for key, value in dict1.items():
        try:
            if dict1[key] == dict2[key] and dict1[key] == dict2[key] and dict1[key] == dict4[key]:
                dict1.pop(key)
                dict2.pop(key)
                dict3.pop(key)
                dict4.pop(key)
        except KeyError:
	    pass
remove_dups(park_lab_home, last_week, two_weeks_ago, three_weeks_ago)

# --- Populate and create plotly graph --- 
free_0 = 'Free Space:' + sizeof_fmt(humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['limit']) - humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['usage']))

park_lab_home = get_full_names(park_lab_home)
last_week = get_full_names(last_week)

labels_1 = ["%s:%s" % (item, last_week[item]) for item in last_week]
labels_1.append(free_0)
labels_1 = sorted(labels_1, key=lambda item: humanfriendly.parse_size(item.split(":")[1]), reverse=True)

two_weeks_ago = get_full_names(two_weeks_ago)
three_weeks_ago = get_full_names(three_weeks_ago)

free_space0 = humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['limit']) - humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['usage'])

values = [humanfriendly.parse_size(park_lab_home[item]) for item in park_lab_home]
values.append(free_space0)
values = sorted(values, reverse=True)

values_1 = [humanfriendly.parse_size(last_week[item]) for item in last_week]
values_1.append(free_space0)
values_1 = sorted(values_1, reverse=True)

values_2 = [humanfriendly.parse_size(two_weeks_ago[item]) for item in two_weeks_ago]
values_2.append(free_space0)
values_2 = sorted(values_2, reverse=True)

values_3 = [humanfriendly.parse_size(three_weeks_ago[item]) for item in three_weeks_ago]
values_3.append(free_space0)
values_3 = sorted(values_3, reverse=True)

N = len(values)

rgb = (9, 4, 70)
rgb_1 = (35, 57, 91)
rgb_2 = (64, 110, 142)
rgb_3 = (142, 168, 195)

special_num = (255 - rgb[2])/(N/.5)
special_num_1 = (255 - rgb[2])/(N/.5)
special_num_2 = (255 - rgb[2])/(N/.5)
special_num_3 = (255 - rgb[2])/(N/.5)

colors = []
colors_1 = []
colors_2 = []
colors_3 = []

for item in range(0,N):
    colors.append("rgba" + str(rgb).replace(")", ", 1)"))
    colors_1.append("rgba" + str(rgb_1).replace(")", ", 1)"))
    colors_2.append("rgba" + str(rgb_2).replace(")", ", 1)"))
    colors_3.append("rgba" + str(rgb_3).replace(")", ", 1)"))

    rgb = list(rgb)
    rgb_1 = list(rgb_1)
    rgb_2 = list(rgb_2)
    rgb_3 = list(rgb_3)

    for idx, item in enumerate(rgb):
        rgb[idx] = item+special_num
    for idx, item in enumerate(rgb_1):
        rgb_1[idx] = item+special_num_1
    for idx, item in enumerate(rgb_2):
        rgb_2[idx] = item+special_num_2
    for idx, item in enumerate(rgb_3):
        rgb_3[idx] = item+special_num_3

    rgb = tuple(rgb)
    rgb_1 = tuple(rgb_1)
    rgb_2 = tuple(rgb_2)
    rgb_3 = tuple(rgb_3)

figure = {
    'data': [{
                'x': [item.split(":")[0] for item in labels_1],
                'y': values,
                "name": date.today(),
                'showlegend':True,
                'marker':{
                    'line':{
                        'width':2
                        },
                    'color': colors,
                    },
                'type': 'bar'
            },
            {
                'x': [item.split(":")[0] for item in labels_1],
                'y': values_1,
                "name": seven_days,
                'showlegend':True,
                'marker':{
                    'line':{
                        'width':2
                        },
                    'color': colors_1,
                    },
                'type': 'bar'
            },
            {
                'x': [item.split(":")[0] for item in labels_1],
                'y': values_2,
                "name": two_weeks,
                'showlegend':True,
                'marker':{
                    'line':{
                        'width':2
                        },
                    'color': colors_2,
                    },
                'type': 'bar'
            },
            {
                'x': [item.split(":")[0] for item in labels_1],
                'y': values_3,
                "name": three_weeks,
                'showlegend':True,
                'marker':{
                    'line':{
                        'width':2
                        },
                    'color': colors_3,
                    },
                'type': 'bar'
            }],
    'layout': {
        'xaxis': {'tickangle': "auto"},
        'barmode': 'overlay',
            'title': 'ORCHESTRA DATA USAGE FOR PARKLAB (Limit:%s) %s\n%s' % (sizeof_fmt(humanfriendly.parse_size(park_lab['/n/data1/hms/dbmi/park [g]']['limit'])), time.strftime("%m/%d/%Y"), "\nShowing users who have been active in the past month"),
    }
}

# --- Plot graph --- 
try:
    url = py.plot(figure, filename='DataUsage' + str(date.today()))
except Exception as e:
    print e
# --- Save Static Image ---
os.remove('DataUsageParkLab.png')
py.image.save_as(figure, 'DataUsageParkLab.png')

# --- Post Message to slack channel ---
# --- ParkLab Slack --- 
# slack.chat.post_message('#orchestra_data_usage', "Interactive Graph -> "+url+".embed", as_user=True)

# --- Your Slack --- 
slack.chat.post_message('#general', "Interactive Graph -> "+url+".embed", as_user=True)

