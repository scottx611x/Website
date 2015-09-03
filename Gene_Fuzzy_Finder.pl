use strict;
use warnings;
use List::Util 'shuffle';
use Bio::Tools::CodonTable; 
use Text::Wrap;

print "Fuzzy Finder\n";
my $filename = "humanXM_000000.fna";
open(my $fh, '<:encoding(UTF-8)', $filename)
      or die "Could not open file '$filename' $!";
my $firstline = <$fh>;  
print "HEADER LINE:\n";
print "$firstline\n";
print "********************************************************************************\n";

print "Sucessfully opened the file $filename\n";

my $NUC_WIDTH = 70; # 70 nucleotides per line 
my $AA_WIDTH  = 40; # 40 amino acids per line 
my @DNA_Seq;
my @Rand_DNA_Seq;
my @newAA_Seq;
my @newAA_Seq_Rand;
my $checker = 0;

$Text::Wrap::columns = $NUC_WIDTH;

@DNA_Seq = &SequenceFromFile;
my @newDNA_Seq = grep(s/\s*//g, @DNA_Seq);
@newDNA_Seq = grep(s/[0-9]//g, @DNA_Seq);
my $big_Sequence_String = $newDNA_Seq[0];
my $length = (length $big_Sequence_String);
#print "$length\n";
#print "big_Sequence_String: $big_Sequence_String\n";
print "\n\n********************************************************************************\n";
print "*********************************DNA Sequence***********************************\n";
print "********************************************************************************\n\n";
print wrap('', '', @DNA_Seq);
&to_Amino_Acid(@newDNA_Seq);
&get_Hydrophobicity(@newAA_Seq);
print "\n\n********************************************************************************\n";
print "***************************Randomized DNA Sequence:*****************************\n";
print "********************************************************************************\n";
$Text::Wrap::columns = $NUC_WIDTH;
@Rand_DNA_Seq = &useRandomSequence($big_Sequence_String);   
my @new_Rand_DNA_Seq = grep(s/\s*//g, @Rand_DNA_Seq); 
print wrap('', '', @Rand_DNA_Seq);
&to_Amino_Acid(@new_Rand_DNA_Seq);
&get_Hydrophobicity(@newAA_Seq_Rand);

sub to_Amino_Acid 
{
    # Amino acid hash table
    my $CodonTable = Bio::Tools::CodonTable->new();
    #my %AAhash = ("GCT" => 'A',"GCC" => 'A',"GCA" => 'A',"GCG" => 'A',"CGT" => 'R',"CGC" => 'R',"CGA" => 'R',"CGG" => 'R',"AGA" => 'R',"AGG" => 'R',"AAT" => 'N',"AAC" => 'N',"GAT" => 'D',"GAC" => 'D',"TGT" => 'C',"TGC" => 'C',"CAA" => 'Q',"CAG" => 'Q',"GAA" => 'E',"GAG" => 'E',"GGT" => 'G',"GGC" => 'G',"GGA" => 'G',"GGG" => 'G',"CAT" => 'H',"CAC" => 'H',"ATT" => 'I',"ATC" => 'I',"ATA" => 'I',"TTA" => 'L',"TTG" => 'L',"CTT" => 'L',"CTC" => 'L',"CTA" => 'L',"CTG" => 'L',"AAA" => 'K',"AAG" => 'K',"ATG" => 'M',"TTT" => 'F',"TTC" => 'F',"CCT" => 'P',"CCC" => 'P',"CCA" => 'P',"CCG" => 'P',"TCT" => 'S',"TCC" => 'S',"TCA" => 'S',"TCG" => 'S',"AGT" => 'S',"AGC" => 'S',"ACT" => 'T',"ACC" => 'T',"ACA" => 'T',"ACG" => 'T',"TGG" => 'W',"TAT" => 'Y',"TAC" => 'Y',"GTT" => 'V',"GTC" => 'V',"GTA" => 'V',"GTG" => 'V',"TAA" => '.',"TAG" => '.',"TGA" => '.',);
    if ($checker == 0)
    {
        $Text::Wrap::columns = $AA_WIDTH;
        my @AA_Seq;
        my $DNA_Seq_String;
        foreach my $nucleotide (@_){ $DNA_Seq_String = $DNA_Seq_String . $nucleotide;}

        my $index = 0;
        my $length = 3;
        my $codon;
        my $result;
        while ($index != length $DNA_Seq_String)
        {
        $codon = substr $DNA_Seq_String, $index, $length;
        #print "\n$codon\n"; working 
        $result = $CodonTable->translate($codon);
        $codon = '';
        #print $result;
        push @AA_Seq, $result;
        $index = $index + 3;

        }
        @newAA_Seq = grep(s/\s*//g, @AA_Seq);

        print "\n\nAmino Acid Sequence:\n";
        print wrap('', '', @newAA_Seq);
        $checker++;
    }
    else{
        $Text::Wrap::columns = $AA_WIDTH;
        my @AA_Seq;
        my $DNA_Seq_String;
        foreach my $nucleotide (@_){ $DNA_Seq_String = $DNA_Seq_String . $nucleotide;}

        my $index = 0;
        my $length = 3;
        my $codon;
        my $result;
        print "\n";
        while ($index != length $DNA_Seq_String)
        {
        $codon = substr $DNA_Seq_String, $index, $length;
        #print "$codon "; 
        $result = $CodonTable->translate($codon);
        $codon = '';
        #print $result;
        push @AA_Seq, $result;
        $index = $index + 3;

        }
        @newAA_Seq_Rand = grep(s/\s*//g, @AA_Seq);

        print "\n\nAmino Acid Sequence:\n";
        print wrap('', '', @newAA_Seq_Rand);
        $checker++;
        }

}
sub get_Hydrophobicity
{
    my $AA_Seq_String;
    foreach my $amino_acid (@_){ $AA_Seq_String = $AA_Seq_String . $amino_acid;}

    my @matches;
    my @match_start;
    my @match_end;
    my $match_length;
    my $match;

    push (@matches,$&) while($AA_Seq_String =~ m/[WAVLIMFY]{5,}/g);
    push (@match_start,@-) while($AA_Seq_String =~ m/[WAVLIMFY]{5,}/g);
    push (@match_end,@+) while($AA_Seq_String =~ m/[WAVLIMFY]{5,}/g);

    print "\n\nRegex used to find hydrophobic matches: m/[WAVLIMFY]{5,}/g\n";
    print "This regex finds regions where 5 or more hydrophobic amino acids are found adjacent to each other.\n\n";

    print "Hydrophobic Matches:\n";

    foreach (@matches) {
      print "$_\n";
    }
    print "\n";

    my $i = 0;
    my $arrSize = @matches;
    if ($arrSize == 0)
    {
        print "No hydrophobic regions found!\n\n"
    }
    else
    {
        foreach $match (@matches)
        {
             $match_length = length $match;
             print "I found hydrophobic region: $match of size : $match_length from location: $match_start[$i] to $match_end[$i].\n";
             $i = $i + 1;
        }
    }
}
sub useRandomSequence
{   
    my $NUC_STR;
    foreach my $nuc (@_){ $NUC_STR = $NUC_STR . $nuc;}
    #print "$NUC_STR\n";
    my $countA = ($NUC_STR =~ tr/A/A/);
    my $countT = ($NUC_STR =~ tr/T/T/);
    my $countC = ($NUC_STR =~ tr/C/C/);
    my $countG = ($NUC_STR =~ tr/G/G/);
    #print "$length\n";
    #print "$countA  $countC  $countT  $countG\n";
    #print $countA + $countC + $countT + $countG;
    #print "\n";


    #Calling subroutine with Sequence length and nucleotide percentages
    &generateRandomSequence($length,$countA,$countC,$countT,$countG);
}
sub generateRandomSequence
{
    #assigning arguments to variables
    my ($sequenceLength) = @_; 
    
    #getting the percentage of each nucleotide
    my $numAs = $_[1];
    my $numCs = $_[2];
    my $numTs = $_[3];
    my $numGs = $_[4];


    print "\nNucleotide Percentages: \n";
    my $perA = $numAs / $length * 100;
    my $perC = $numCs / $length * 100;
    my $perT = $numTs / $length * 100;
    my $perG = $numGs / $length * 100;

    $perA = sprintf "%.2f" ,$perA;
    $perC = sprintf "%.2f" ,$perC;
    $perT = sprintf "%.2f" ,$perT;
    $perG = sprintf "%.2f" ,$perG;

    print "%As -> $perA\n";
    print "%Cs -> $perC\n";
    print "%Ts -> $perT\n";
    print "%Gs -> $perG\n";
    print "$numAs A's, $numCs C's, $numTs T's, and $numGs G's \n\n";

    #Filling 4 arrays with their respective amount of nucleotides
    my @Nucleotides = ();
    @Nucleotides = (@Nucleotides, ('A') x $numAs);
    @Nucleotides = (@Nucleotides, ('C') x $numCs);
    @Nucleotides = (@Nucleotides, ('T') x $numTs);
    @Nucleotides = (@Nucleotides, ('G') x $numGs);
    #Shuffle array order
    

    my $randomSequence = "";
    #While array isnt empty, pop a letter and concatenate that to the new DNA sequence
    while (@Nucleotides)
    {
        @Nucleotides = shuffle(@Nucleotides);
        my $nucleotide = pop @Nucleotides;
        $randomSequence = $randomSequence . $nucleotide;
    }
    #print "Randomized DNA string is: \n";
    #print "$randomSequence\n";
    $randomSequence =~ s/TAA|TAG|TGA/TGG/g;
    $randomSequence = $randomSequence . "TAA";
    #print "$randomSequence\n";

    my @DNA_Seq;
    @DNA_Seq = split /\s+/, $randomSequence;
    
    return @DNA_Seq;
}
sub SequenceFromFile
{

    open(my $fh, '<:encoding(UTF-8)', $filename)
      or die "Could not open file '$filename' $!";
    my $firstline = <$fh>;  
    #print "$firstline\n";

    my @DNA_Seq;

    while (my $row = <$fh>) {
      chomp $row;
      push @DNA_Seq, uc $row;
    }
    
    return @DNA_Seq ;
}

