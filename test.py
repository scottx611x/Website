from __future__ import division
import glob
import sys
import re
import operator
from Bio.Seq import translate
from Bio.Alphabet import generic_dna
import plotly.plotly as py
import plotly.tools as tls
from plotly.graph_objs import *
from random import shuffle


#tls.set_credentials_file(username='scottx611x1c74', api_key='v76exesqe2', stream_ids=['sokp9nh6a1', 'o4y2l5r063'])
py.sign_in('scottx611x1c74','v76exesqe2')

BAC = str(sys.argv[1])
protein_Num = int(sys.argv[2])

fna = sorted(glob.glob("%s/*.fna" % BAC))
ptt = sorted(glob.glob("%s/*.ptt" % BAC))

filename = fna[0]
pttfilename = ptt[0]

with open(filename) as FileObj0, open("BACID","w+") as BACID:
	first = FileObj0.next()
	BACID.write(".Fna file: %s\n" % filename)
	BACID.write("%s\n" % "<br><br>")
	BACID.write(".Ptt file: %s\n" % pttfilename)
	BACID.write("%s\n" % "<br><br>")
	BACID.write("%s\n" % first)

DNA = ""
PTT = ""

#----------------------------------------------------
# read in sequence file and merge it into one string
#----------------------------------------------------

with open(filename) as FileObj, open("DNA","w+") as D:
	D.write("<b style=\"font-size:24px;\">DNA SEQUENCE</b><br><br>")
	first = FileObj.next()
	for line0 in FileObj:
		line0 = line0.replace("\t","")
		line0 = line0.replace("\n","")
		line0 = line0.replace("\r","")
		DNA = DNA + line0
		D.write(line0 + "\n")

pttfile = []
pttfileforregex = []
with open(pttfilename) as FileObj1 ,open("PTT","w+") as P:
	first1 = FileObj1.next()
	next1 = FileObj1.next()
	next2 = FileObj1.next()
	for line1 in FileObj1:
		pttfileforregex.append(line1)
		line1 = line1.replace("\n","")
		line1 = line1.replace("\r","")
		line1 = line1.replace("\t","")
		PTT = PTT + line1
		pttfile.append(line1)
		P.write(line1 + "\n")

#------------------------------------------------------------------
# read in the ranges from the ptt file as well as strand + or - as well as protein name!
#------------------------------------------------------------------

ptt_plusminus = []
ptt_Ranges = []
ptt_strand_plusminus = []
ptt_dict = {}
ptt_String = PTT
regexp1 = re.compile(r'\d+\.\.\d+')
regexpPlus = re.compile(r'\d+\.\.\d+.*[+]')
regexpMinus = re.compile(r'\d+\.\.\d+.*[-]')
regexpName = re.compile(r'-\t-\t.*')
regexpName1 = re.compile(r'-\tCOG.*\s')

with open("RANGES","w+") as R, open("PLUSMINUS","w+") as PM:
	R.write("<b style=\"font-size:24px;\">PTT RANGES</b><br><br>")
	PM.write("<b style=\"font-size:24px;\">+/-</b><br><br>")
	for line1 in pttfile:
		if regexp1.search(line1) is not None:
			match = regexp1.findall(line1)
			ptt_Ranges.append(str(match))
			R.write(str(match) + "&emsp;")
		if regexpPlus.search(str(line1)) is not None:
			matchP = regexpPlus.findall(str(line1))
			ptt_strand_plusminus.append("+")
			PM.write("+\n")
		elif regexpMinus.search(str(line1)) is not None:
			matchM = regexpMinus.findall(str(line1))
			ptt_strand_plusminus.append("-")
			PM.write("-\n")

count = 0
bad_Proteins = []
for line1 in pttfileforregex:
	if "hypothetical protein" in str(line1):
		bad_Proteins.append('Protein_%d' % count)
		count = count + 1
	else:
		if regexpName.search(line1) is not None:
			matchN = regexpName.findall(line1)
			matchN = re.sub(r"\[\'-\\t-\\t","",str(matchN))
			matchN = re.sub(r"\'\]","",str(matchN))
			ptt_dict.update({'Protein_%d' % count : str(matchN)})
		elif regexpName1.search(line1) is not None:
			matchN1 = regexpName1.findall(line1)
			matchN1 = re.sub(r"\[\'-\\tCOG.*\\t","",str(matchN1))
			matchN1 = re.sub(r"\\n\'\]","",str(matchN1))
			ptt_dict.update({'Protein_%d' % count : str(matchN1)})
		count = count + 1

	

#------------------------------------------------------------------
# get gene lengths from ranges and split DNA Sequence into genes 
#------------------------------------------------------------------

genes = []
lengths = []
length = ""
start = ""
first = ""
second = "" 
length_iterator = 0

regexpFirst = re.compile(r'\d{1,}\.\.')
regexpSecond = re.compile(r'\.\.\d{1,}')

with open("GENES","w+") as G, open("LENGTHS","w+") as L:
	G.write("<b style=\"font-size:24px;\">GENES</b><br><br>")
	L.write("<b style=\"font-size:24px;\">GENE LENGTHS</b><br><br>")
	for rng in ptt_Ranges:
		if regexpFirst.search(rng) is not None:
			match = regexpFirst.findall(rng)
			first = match
			first = str(first).replace(".","")
			first = str(first).replace("'","")
			first = str(first).replace("[","")
			first = str(first).replace("]","")
			first = int(str(first))
		if regexpSecond.search(rng) is not None:
			match2 = regexpSecond.findall(rng)
			second = match2
			second = str(second).replace(".","")
			second = str(second).replace("'","")
			second = str(second).replace("[","")
			second = str(second).replace("]","")
			second = int(str(second))
		first = first - 1
		second = second -1
		length = (second - first) + 1
		lengths.append(length)
		L.write(str(length) + "\n")
		genes.append(DNA[first:second+1])
		G.write("<br><br><b>GENE %d:</b><br>" % length_iterator  + str(DNA[first:second+1]) + "<br>")
		length_iterator = length_iterator + 1

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# if any of the genes are a - strand then Transliterate them and flip em
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
minus_strands =[]
minus_count = 0
minus_None = 0

TR = {'A':'T','T':'A','C':'G','G':'C'}

with open("MINUSSTRANDS","w+") as MS:
	MS.write("<b style=\"font-size:24px;\">MINUS STRANDS</b><br><br>")
	for pm in ptt_strand_plusminus:
		if pm == "-":
			temp = genes[minus_count]
			new_minus = ""
			for i in temp:
				if i != "A" and i != "T" and i != "C" and i != "G":
					new_minus = new_minus + i
				else:
					new_minus = new_minus + TR[i]
			MS.write("<br><b>Strand%d Before:</b><br><br>" % minus_count)
			MS.write(temp + "<br>")
			
			new_minus = new_minus[::-1]

			minus_strands.append(new_minus)

			MS.write("<br><b>Strand%d Translated and Flipped:</b><br><br>" % minus_count)
			MS.write(minus_strands[minus_count] + "<br>")
			minus_None = 1
		else:
			minus_strands.append("None")
			MS.write("<br>Strand%d is not a minus strand!<br><br>" % minus_count)

		minus_count = minus_count + 1

	if minus_None == 0:
		MS.write("No Minus(-) strands found!")

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# transcribe the genes into amino acids and in @proteins
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
proteins = []
p_count = 0
with open("PROTEINS","w+") as P:
	P.write("<b style=\"font-size:24px;\">PROTEINS</b><br><br>")
	for gene in genes:
		protein = translate(gene)
		proteins.append(protein)
		P.write("Protein%d:<br>%s<br><br>" % (p_count, protein))
		p_count = p_count +1


#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# calculate the percentage of hydrophobicity of each protein
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
protein_hydro_hash = {}
protein_count = 0
hydro_string = ""
regexpHydro= re.compile(r'[WAVLIMFY]{1,}')

for prtn in proteins:
	hydro_string = ""

	hydro_matches = regexpHydro.findall(prtn)

	for h in hydro_matches: 
		hydro_string = hydro_string + h

	protein_length = len(prtn)
	hydro_string_length = len(hydro_string)
	hydro_percentage = float((hydro_string_length / protein_length) * 100)

	#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
	# put the protein and hydro% into a hash as a key value pair respectively
	#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
	protein_hydro_hash['Protein_%d' % protein_count] = "%.2f" % hydro_percentage;
	protein_count = protein_count + 1

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Sort the proteins in the hash table by hydrophobicity with most hydrophobic at the top first
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
for bad in bad_Proteins:
	del protein_hydro_hash[bad]

sorted_proteins = reversed(sorted(protein_hydro_hash.items(), key=operator.itemgetter(1)))
stuff = []
y = []
bottom = []

with open("HASH","w+") as H:
	H.write("<b style=\"font-size:24px;\">SORTED PROTEIN HASH</b><br><br>")
	for thing in sorted_proteins:
		H.write("%s<br><br>" % ("(" + ptt_dict.get(str(tuple(thing)[0])) + " : " + str(tuple(thing)[1])+")"))
		stuff.append(tuple(thing))
for tup in stuff[:protein_Num]:
	y.append(tuple(tup)[1])
	bottom.append(ptt_dict.get(str(tuple(tup)[0])))

seen_indexs = []
unique = []
for idx, item in enumerate(bottom):
	if item not in unique:
		unique.append(item)
	else:
		seen_indexs.append(idx)

count = 1
for idx, item in enumerate(bottom):
	if idx in seen_indexs:
		bottom[idx] = bottom[idx] + str(count)
		count = count + 1
	
#colors = ['#072A24', '#119DA4', '#31393C', '#C97064', '#FCD0A1','#42F2F7', '#14CB22', '#A49E8D', '#88CCF1', '#D0DB97','#FFCEBA', '#4E4A59', '#A1CCA5', '#AEC5EB', '#CAD2C5','#192433', '#03571B', '#DDFCAD', '#DDFCAD', '#72A98F','#3D7BA0', '#ECBA82', '#BBBDF6', '#3AC292', '#B3989B']
colors = ['#0B1D2F', '#0B213C', '#0E2849', '#112F56', '#143663','#173D70', '#1A447D', '#1F5197', '#245EB1', '#296BCB','#2E78E5', '#3385FF', '#4791FF', '#5B9DFF', '#6FA9FF','#83B5FF', '#97C1FF', '#A1C7FF', '#ABCDFF', '#B5D3FF','#BFD9FF', '#C9DFFF', '#D3E5FF','#DDEBFF', '#E7F1FF']
#shuffle(colors)

data = Data([
	Bar(
		x=bottom,
		y=y,
		text = bottom,
		marker=Marker(
			#color=['#001a1a','#002929','#003d3d','#005252','#006666','#007a7a','#008f8f','#00a3a3','#00b8b8','#00cccc','#00e0e0','#00f5f5','#0affff','#1fffff','#33ffff','#47ffff','#5cffff','#70ffff','#85ffff','#99ffff','#adffff','#c2ffff','#d6ffff','#ebffff','#f5ffff']
			color = colors
		)
	)
])
layout = Layout(
	title='Top Hydrophobic Proteins %s' % BAC,
	autosize=False,
	width=800,
	height=600,
	margin=Margin(
		b=200,
	),
	font=Font(
		family='Raleway, sans-serif',
		size=12
	),
	xaxis=XAxis(
		tickfont=Font(
			size=10,
		),
		tickangle=45,
	),
	yaxis=YAxis(
		title="%s Hydrophobicity" % "%",
	),
	bargap=0.05
)

fig = Figure(data=data, layout=layout)
plot_url = py.plot(fig, filename='p_Hydro')
#py.image.save_as(fig, 'p_Hydro.png')



