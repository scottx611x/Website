import sys,subprocess
from subprocess import Popen

USER_ID = str(sys.argv[1])
ACCESS_TOKEN = str(sys.argv[2])

print ACCESS_TOKEN  ,"<br>"

p = Popen(['curl', '-X', 'GET', 'https://api.spotify.com/v1/me', '-H', 'Authorization: Bearer %s' % ACCESS_TOKEN], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#p = Popen(['ls', '-a'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out,err = p.communicate()

print "<div align='center'><h1>USERS DATA</h1></div>"
print out ,"<br>"
print err ,"<br>"

p1 = Popen(['curl', '-X', 'GET', 'https://api.spotify.com/v1/users/%s/playlists' % USER_ID, '-H', 'Authorization: Bearer %s' % ACCESS_TOKEN], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#p = Popen(['ls', '-a'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out1,err1 = p1.communicate()

print "<div align='center'><h1>PLAYLISTS</h1></div>"
print out1 ,"<br>"
print err1 ,"<br>"