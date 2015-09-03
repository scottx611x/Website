import sys,os

BAC = str(sys.argv[1])
os.system("wget -P %s/ ftp://ftp.ncbi.nih.gov/genomes/Bacteria/%s/*.ptt" % (BAC,BAC))
os.system("wget -P %s/ ftp://ftp.ncbi.nih.gov/genomes/Bacteria/%s/*.fna" % (BAC,BAC))
with open("DL_TESTER","w") as DL:
	DL.write("wget -P %s/ ftp://ftp.ncbi.nih.gov/genomes/Bacteria/%s/*.ptt" % (BAC,BAC))

