import re
import time
import smtplib
import paramiko
from slacker import Slacker
import plotly.plotly as py
import plotly.graph_objs as go
from plotly.graph_objs import Figure
import humanfriendly
"""
SAMPLE DATA FROM HMS-rcops <rcops@hms.harvard.edu>
  310T    tcga
  188T    semin
  66T     hongkong_stomach
  63T     alee
  37T     single_neuron
  33T     parklab
  29T     niklas
  25T     jluquette
  19T     Project_WAL_10690
  18T     wx21
  14T     sl325
  12T     luca
  11T     esophageal_data
  9.6T    dsday
  9.3T    francesco
  8.8T    jfan
  7.8T    lucy
  7.2T    INTEGER
  6.9T    daniel
  6.1T    Project_LOD_10206_WGS
  4.9T    jyoon
  4.6T    hccgp
  4.5T    me
  4.4T    single_cell_breast
  3.9T    alver
  3.2T    kamil
  2.9T    sgaynor
  2.7T    icgc-tcga-pancan
  2.5T    SRP017546
  2.0T    lchao
  1.9T    lxyang
  1.6T    Project_N_GRID
  1.5T    jia
  1.3T    tmkim
  1.1T    pdac
  1.1T    jl535
  1011G   psm
  906G    alice_liver
  847G    tmp
  808G    primate
  796G    refinery
  772G    scott
  717G    rebeca
  619G    mattia
  506G    UMB1932
  483G    N_Naka
  462G    hapmap
  435G    mult_myeloma
  423G    maness_data
  369G    babyseq
  243G    ffpe_alee
  231G    broad_crc
  229G    triple_neg_breast_cancer
  210G    rpark
  190G    soo_sra
  150G    carroll-exomes
  136G    gilad_wgs
  126G    genemapster
  115G    single_cell_kidney
  109G    hongwei_yang
  93G     nclement
  85G     sidizhang
  75G     csf
  51G     hlxue
  38G     prostate
  30G     glioma.stem
  26G     INTEGER_CNLV
  17G     bch_gene_partnership
  8.2G    rxi
  2.4G    mEn
  1.9G    nils
  62M     peterk
  32M     IGVTools
  2.6M    cbohrson
  466K    refinery-vm
  459K    shouyong
  341K    so108
  3.0K    soo_data
"""

# Return file size in human readable format
def sizeof_fmt(num, suffix=''):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)

with open('/var/www/Website/scripts/python/config') as f:
  credentials = [x.strip() for x in f.readlines()]

slack = Slacker(credentials[1])
# slack_parlab = Slacker(credentials[2])

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
