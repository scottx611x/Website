import sys, subprocess

sys.stdout.write("FUCK")
USER_ID = str(sys.argv[0])
ACCESS_TOKEN = str(sys.argv[1])

print USER_ID, "\n"
print ACCESS_TOKEN, "\n"
p = subprocess.Popen('curl -X GET "https://api.spotify.com/v1/me" -H "Authorization: Bearer %s' % ACCESS_TOKEN,stdout=subprocess.PIPE)
p.communicate()