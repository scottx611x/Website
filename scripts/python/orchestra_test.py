import re
from subprocess import check_output

parklab = {}
with open("test.txt", "r") as t:
    for line in t:
        x = re.split('\s+', line) 
        parklab[x[2]] =  x[1]

print [parklab[item] for item in parklab]