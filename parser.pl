#!usr/bin/perl
#Perl parser for NCBI Bacteria Directory listing

my $filename = "listing";

open(my $fh, "<", $filename)
    or die "Failed to open file: $!\n";
while(<$fh>) { 
    chomp; 
    if ($_ =~ /(dr-xr-xr-x   2.*[A-Z]{1}[a-z]{2}\s\d\d\s\s\d{4}\s)/){ my @bac = split /(dr-xr-xr-x   2.*[A-Z]{1}[a-z]{2}\s\d\d\s\s\d{4}\s)/, $_; push @array, $bac[2];}  
} 
close $fh; 

for my $item (@array){print "$item\n"};
