#!/usr/bin/perl
#Finds percent Hydrophobicity of different DNA Sequences from NCIB Blast Database
#Programmed by Scott Ouellette

use Bio::Tools::CodonTable;  
use Text::Wrap;
use strict;
use warnings;

my $CodonTable = Bio::Tools::CodonTable->new();

my $NUC_WIDTH = 75; # 70 nucleotides per line 
my $AA_WIDTH  = 40; # 40 amino acids per line 
my $firstline;
$Text::Wrap::columns = $NUC_WIDTH;

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# read in sequence file and merge it into one string
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------

my $filename = "NC_007445.fna";
my @DNA_Seq;
my $DNA_String;

&SequenceFromFile;

print "************************************\n";
print "*           DNA SEQUENCE           *\n";
print "************************************\n\n";

foreach my $nucleotide (@DNA_Seq){$nucleotide =~ s/\r//; $nucleotide =~ s/\n//; $nucleotide =~ s/\t//; $DNA_String = $DNA_String . $nucleotide;}
print "Length of Sequence:> " . length $DNA_String;
print "\n";
print wrap('', '', $DNA_String);

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# read in the ranges from the ptt file as well as strand + or -
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------

my $pttfilename = "NC_007445.ptt";
my @pttfile;
my @ptt_plusminus;
my @ptt_Ranges;
my $ptt_String;
my @ptt_strand_PLUS_MINUS;

open(my $fh, '<:encoding(UTF-8)', $pttfilename)
      or die "Could not open file '$pttfilename' $!";
    my $firstline_ptt = <$fh>; 
    $firstline_ptt =~ s/\,.*//; 
    #print "$firstline_ptt\n";
    while (my $row = <$fh>) {chomp $row;push @pttfile, $row;}

foreach my $item (@pttfile){if($item =~ m/(\d+\.\.\d+)/g){push (@ptt_Ranges,$&);}}
push (@ptt_plusminus, @pttfile);
foreach my $finder (@ptt_plusminus){if($finder =~ m/(\d+\.\.\d+.*[+])/g){push (@ptt_strand_PLUS_MINUS,"+");}elsif($finder =~ m/(\d+\.\.\d+.*[-])/g){push (@ptt_strand_PLUS_MINUS,"-");}}

print "\n\n************************************\n";
print "*         RANGES FROM PTT          *\n";
print "************************************\n";

my $count = 0;
foreach my $range (@ptt_Ranges){ print "\nRANGE$count: $range";$count++;}

print"\n\n";

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# break sequence into genes using the ranges from the protein translation table file
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------

my @genes;
my @lengths;
my $length;
my $start;
my $first;
my $second; 
my $length_iterator = 0;

print "************************************\n";
print "*        LENGTHS FROM RANGES       *\n";
print "************************************\n\n";
foreach my $range (@ptt_Ranges) {
    $range =~ /(\d{1,5}\.\.)/;
    $first = $&;
    $first =~ s/\.\.//;
    $first = $first - 1;
    $range =~ /(\.\.\d{1,5})/;
    $second = $&;
    $second =~ s/\.\.//;
    $second = $second - 1;    
    $length = $second - $first +1;
    #print "\n$first\n$second\n";
    push (@lengths,$length);
    print "LENGTH$length_iterator: $lengths[$length_iterator]\n";
    push (@genes,substr($DNA_String,$first,$lengths[$length_iterator]));
    $length_iterator = $length_iterator + 1;
}
print "\n************************************\n";
print "*               GENES              *\n";
print "************************************";
my $x = 0;
foreach my $gene (@genes){ print "\n\nGene $x of length: $lengths[$x] >:\n";print wrap('', '', $gene); $x++;}

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# if any of the genes are a - strand then Transliterate them and flip em
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
my @minus_strands;
my $minus_count = 0;
my $minus_None = 0;
print "\n\n************************************\n";
print "*       MINUS STRAND CHECK XC      *\n";
print "************************************\n";
foreach my $pm (@ptt_strand_PLUS_MINUS)
{
    if ($pm eq "-")
    {
        my $temp = $genes[$minus_count];
        $temp =~ tr/ATCG/TAGC/;
        $temp = reverse $temp;
        push(@minus_strands,$temp);
        print "\n\nMINUS STRAND FOUND!\n\n";
        print "Strand:$minus_count Translated and Flipped: \n\n";
        print wrap('', '', $minus_strands[$minus_count]);
        $minus_None = 1;
    }
    else{
        push(@minus_strands,"None");
    }
    $minus_count++;
}
if ($minus_None == 0){
    print "No Minus(-) strands found!\n";
}
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# transcribe the genes into amino acids and in @proteins
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------

# my %AAhash = ("GCT" => 'A',"GCC" => 'A',"GCA" => 'A',"GCG" => 'A',"CGT" => 'R',"CGC" => 'R',"CGA" => 'R',"CGG" => 'R',"AGA" => 'R',"AGG" => 'R',"AAT" => 'N',"AAC" => 'N',"GAT" => 'D',"GAC" => 'D',"TGT" => 'C',"TGC" => 'C',"CAA" => 'Q',"CAG" => 'Q',"GAA" => 'E',"GAG" => 'E',"GGT" => 'G',"GGC" => 'G',"GGA" => 'G',"GGG" => 'G',"CAT" => 'H',"CAC" => 'H',"ATT" => 'I',"ATC" => 'I',"ATA" => 'I',"TTA" => 'L',"TTG" => 'L',"CTT" => 'L',"CTC" => 'L',"CTA" => 'L',"CTG" => 'L',"AAA" => 'K',"AAG" => 'K',"ATG" => 'M',"TTT" => 'F',"TTC" => 'F',"CCT" => 'P',"CCC" => 'P',"CCA" => 'P',"CCG" => 'P',"TCT" => 'S',"TCC" => 'S',"TCA" => 'S',"TCG" => 'S',"AGT" => 'S',"AGC" => 'S',"ACT" => 'T',"ACC" => 'T',"ACA" => 'T',"ACG" => 'T',"TGG" => 'W',"TAT" => 'Y',"TAC" => 'Y',"GTT" => 'V',"GTC" => 'V',"GTA" => 'V',"GTG" => 'V',"TAA" => '.',"TAG" => '.',"TGA" => '.',);
my @proteins;
my $index = 0;
my $codon_length = 3;
my $codon;
my $result;
my $gene_Length;
my $gene_number = 0;
print "\n";
foreach my $gene (@genes)
{

 if($minus_strands[$gene_number] eq "None")
 {
    #print"+\n";
    my $gene_String;
    $gene_Length = length $gene;

    while ($index <= $gene_Length)
    { 
        $codon = substr $gene, $index, $codon_length;
        #print "\n$codon\n"; working
        $result = $CodonTable->translate($codon);
        #$result = $AAhash{$codon};
        #print "$result\n";
        $codon = '';
        #print $result; working
        $gene_String = $gene_String . $result;
        $index = $index + 3;
    }
    push @proteins, $gene_String;
    $index = 0;
    $gene_number++;
  }
  else{
    #print"-\n";
    my $gene_String;
    $gene_Length = length $minus_strands[$gene_number];

    while ($index <= $gene_Length)
    { 
        $codon = substr $minus_strands[$gene_number], $index, $codon_length;
        #print "\n$codon\n"; working
        $result = $CodonTable->translate($codon);
        #$result = $AAhash{$codon};
        #print "$result\n";
        $codon = '';
        #print $result; working
        $gene_String = $gene_String . $result;
        $index = $index + 3;
    }
    push @proteins, $gene_String;
    $index = 0;
    $gene_number++;
  }
}

$Text::Wrap::columns = $AA_WIDTH;

print "\n************************************\n";
print "*        PROTEINS FROM GENES       *\n";
print "************************************";
my $num = 0;
foreach my $amino_acid (@proteins){print "\n\nProtein from GENE$num:\n";print wrap('', '', $amino_acid);$num++;}

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# calculate the percentage of hydrophobicity of each protein
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------

my %protein_hydro_hash;
my $protein_count = 0;

print "\n\n************************************\n";
print "*          HYDRO MATCHES           *\n";
print "************************************";

foreach my $protein (@proteins)
{
    my @hydro_matches;
    my @hydro_match_start;
    my @hydro_match_end;
    my $hydro_match_length;
    my $hydro_match;
    my $protein_length = length $protein;
    my $hydro_string;
    my $hydro_string_length;
    my $hydro_percentage;

    push (@hydro_matches,$&) while($protein =~ m/[WAVLIMFY]{1,}/g);
    push (@hydro_match_start,@-) while($protein =~ m/[WAVLIMFY]{1,}/g);
    push (@hydro_match_end,@+) while($protein =~ m/[WAVLIMFY]{1,}/g);

    print "\n\nHydrophobic Matches for Protein> $protein_count:\n";
    print scalar @hydro_matches . " matches";
    foreach (@hydro_matches) {$hydro_string = $hydro_string. $_;}

    my $i = 0;
    my $arrSize = @hydro_matches;
    if ($arrSize == 0)
    {
        print "No hydrophobic regions found!\n\n"
    }
    else
    {
        foreach $hydro_match (@hydro_matches)
        {
             $hydro_match_length = length $hydro_match;
             #print "FOUND hydrophobic region: $hydro_match of size : $hydro_match_length from location: $hydro_match_start[$i] to $hydro_match_end[$i].\n";
             $i = $i + 1;
        }
    }
    $hydro_string_length = length $hydro_string;
    #print "\n\n\n\n\n\n\n$hydro_string_length\n$protein_length\n\n\n\n\n";
    $hydro_percentage = int(($hydro_string_length / $protein_length) * 100);
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# put the protein and hydro% into a hash as a key value pair respectively
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------

    $protein_hydro_hash{"Protein_$protein_count "} = "$hydro_percentage";
    $protein_count++;

}
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Sort the proteins in the hash table by hydrophobicity with most hydrophobic at the top first
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
print "\n\n************************************\n";
print "*   PROTEINS W/ % HYDROPHOBICITY   *\n";
print "************************************\n\n";

foreach my $name (sort { $protein_hydro_hash{$b} <=> $protein_hydro_hash{$a} } keys %protein_hydro_hash) {
    printf "%-8s\t%s%s", $name, $protein_hydro_hash{$name},"%\n";
}

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# print the filename into the spreadsheet
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------

my $outputFileName = "output.xls";
open (OUTPUT, ">", $outputFileName) or die "Cannot open the file: $outputFileName: $!";

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# print the species name from top of .fna file and .ptt fie to the output file as: 
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------

print (OUTPUT "\n\nProtein Hydrophobicity\n");
print (OUTPUT "\n.fna for $firstline\n");
print (OUTPUT ".ptt for $firstline_ptt\n");
print (OUTPUT "Protein #\t\%Hydrophobic\n");

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# print tab delimeted results for the proteins and their percent hydrophobicity into the excel output file
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
foreach my $name (sort { $protein_hydro_hash{$b} <=> $protein_hydro_hash{$a} } keys %protein_hydro_hash) {
    printf(OUTPUT "%-8s\t%s%s", $name, $protein_hydro_hash{$name},"%\n");
}
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------
#foreach my $plusminus (@ptt_strand_PLUS_MINUS){print "$plusminus\n";}  

sub SequenceFromFile
{
    open(my $fh, '<:encoding(UTF-8)', $filename)
      or die "Could not open file '$filename' $!";
    $firstline = <$fh>;  
    $firstline =~ /([|]\s{1}.*)\,/; 
    $firstline = $&;
    $firstline =~ s/[|]\s{1}//;
    $firstline =~ s/\,//;
    #print "$firstline\n";

    while (my $row = <$fh>) {
      chomp $row;
      push @DNA_Seq, uc $row;
    }
}