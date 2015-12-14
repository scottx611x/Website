import re
import time
import smtplib
import paramiko

ssh = paramiko.SSHClient()
ssh.load_system_host_keys()

with open('config') as f:
  credentials = [x.strip() for x in f.readlines()]

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

# SMTP SETUP
SERVER = "smtp.gmail.com"
FROM = "scottx611x@gmail.com"
TO = ["Scott_Ouellette@hms.harvard.edu"]

SUBJECT = "ORCHESTRA DATA USAGE FOR PARK LAB: %s" % time.strftime("%m/%d/%Y")

TEXT = ""
TEXT += '\n/n/data1/hms/dbmi/park [g]   USAGE: ' + park_lab['/n/data1/hms/dbmi/park [g]']['usage']
TEXT += '\n/n/data1/hms/dbmi/park [g] WARNING: ' + park_lab['/n/data1/hms/dbmi/park [g]']['warning']
TEXT += '\n/n/data1/hms/dbmi/park [g]   LIMIT: ' + park_lab['/n/data1/hms/dbmi/park [g]']['limit']

# Prepare actual message
message = """\
From: %s
To: %s
Subject: %s

%s
""" % (FROM, ", ".join(TO), SUBJECT, TEXT)

# Send the mail
s = smtplib.SMTP(SERVER, 587)
s.starttls()
s.ehlo() 
s.login('scottx611x@gmail.com', credentials[0]) 
s.sendmail(FROM, TO, message)
s.quit()
