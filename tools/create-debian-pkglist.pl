#!/usr/bin/perl

#some quicksetup to make sure everything is in place
system('mkdir -p /disks/tmp/bcfg2-packagelists' );


#pull the correct package lists from the security sites. 
#this needs to be abstracted better
system( "wget http://security.debian.org/dists/stable/updates/main/binary-i386/Packages -O /disks/tmp/bcfg2-packagelists/security-main.Packages -q" );
system( "wget http://security.debian.org/dists/stable/updates/contrib/binary-i386/Packages -O /disks/tmp/bcfg2-packagelists/security-contrib.Packages -q" );
system( "wget http://security.debian.org/dists/stable/updates/non-free/binary-i386/Packages -O /disks/tmp/bcfg2-packagelists/security-nonfree.Packages -q" );

system('cat /disks/tmp/bcfg2-packagelists/security-main.Packages /disks/tmp/bcfg2-packagelists/security-contrib.Packages /disks/tmp/bcfg2-packagelists/security-nonfree.Packages > /disks/tmp/bcfg2-packagelists/debian-stable-security.Packages');
system('rm /disks/tmp/bcfg2-packagelists/security-main.Packages /disks/tmp/bcfg2-packagelists/security-contrib.Packages /disks/tmp/bcfg2-packagelists/security-nonfree.Packages');

#pull the correct package lists from the security sites. 
#this needs to be abstracted better
system( "wget http://volatile.debian.net/debian-volatile/dists/stable/volatile/main/binary-i386/Packages -O /disks/tmp/bcfg2-packagelists/volatile-main.Packages -q" );
system( "wget http://volatile.debian.net/debian-volatile/dists/stable/volatile/contrib/binary-i386/Packages -O /disks/tmp/bcfg2-packagelists/volatile-contrib.Packages -q" );
system( "wget http://volatile.debian.net/debian-volatile/dists/stable/volatile/non-free/binary-i386/Packages -O /disks/tmp/bcfg2-packagelists/volatile-nonfree.Packages -q" );

system('cat /disks/tmp/bcfg2-packagelists/volatile-main.Packages /disks/tmp/bcfg2-packagelists/volatile-contrib.Packages /disks/tmp/bcfg2-packagelists/volatile-nonfree.Packages > /disks/tmp/bcfg2-packagelists/debian-stable-volatile.Packages');
system('rm /disks/tmp/bcfg2-packagelists/volatile-main.Packages /disks/tmp/bcfg2-packagelists/volatile-contrib.Packages /disks/tmp/bcfg2-packagelists/volatile-nonfree.Packages');

#pull the correct package lists from the security sites. 
#this needs to be abstracted better
system( "wget ftp://ftp.nerim.net/debian-marillat/dists/sarge/main/binary-i386/Packages -O /disks/tmp/bcfg2-packagelists/debian-sarge-mplayer.Packages -q" );

#this is to fix local files so that my naming hack thing will playout.
system('cp /disks/debian/sarge/Packages /disks/tmp/bcfg2-packagelists/debian-sarge-local.Packages');

system('cat /disks/distro/debian/dists/sarge/main/binary-i386/Packages /disks/distro/debian/dists/sarge/contrib/binary-i386/Packages /disks/distro/debian/dists/sarge/non-free/binary-i386/Packages > /disks/tmp/bcfg2-packagelists/debian-sarge-distro.Packages');

system('cat /disks/distro/debian-non-US/dists/sarge/non-US/main/binary-i386/Packages /disks/distro/debian-non-US/dists/sarge/non-US/contrib/binary-i386/Packages /disks/distro/debian-non-US/dists/sarge/non-US/non-free/binary-i386/Packages > /disks/tmp/bcfg2-packagelists/debian-sarge-nonUS.Packages');

#this is currently still a hack, because ordering is important.
#for future refernce you must do security and then local.. then the rest.. 

@files = ( 
  "/disks/tmp/bcfg2-packagelists/debian-stable-volatile.Packages",
  "/disks/tmp/bcfg2-packagelists/debian-stable-security.Packages", 
  "/disks/tmp/bcfg2-packagelists/debian-sarge-local.Packages",
  "/disks/tmp/bcfg2-packagelists/debian-sarge-mplayer.Packages",
  "/disks/tmp/bcfg2-packagelists/debian-sarge-distro.Packages", 
  "/disks/tmp/bcfg2-packagelists/debian-sarge-nonUS.Packages",
);

$priority = 89;
@tmpfiles = ();

#first come the security fixes
foreach $file ( @files ){

  push( @tmpfiles, $file );  
  #first we open up the imput file
  open( INFILE, "$file" ) or die("could not open $file\n");
  
  #then we change the name and open the output file.
  $file =~ s/Packages/xml/ ;
  #print "Opening $file for writing\n";
  open( OUTFILE, ">$file" );


  #start by putting in the default stuff 
  print OUTFILE "<PackageList uri='http://netzero.mcs.anl.gov:8080/' type='deb' priority='".$priority."'>\n";
  print OUTFILE "<Group name='debian-sarge'>\n";

  #decrement the priority since we are going highest to lowest
  $priority = $priority - 10;

  
  #the loop that builds the actually file.
  $known_package=0;
  while( $line = <INFILE> ){
    if( $line =~ /^Package:/ ){
      ($filler,$basename)=split( ' ', $line );
      
      #Now to find the version of the package.
      $found = 0;
      while( !$found ){
	$line = <INFILE>;
	if( $line =~ /^Version:/ ){
	  ($filler,$version)=split( ' ', $line );
	  if ( ! $known_package ){
	    print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
	    push @mypackages, $basename;	  }
	  $found =1;
	}
      }
    }
    #end of file builder loop

  }
  close( INFILE );
  print OUTFILE "</Group>\n</PackageList>\n";
  close( OUTFILE );
}


#this is where I do clean up and set up for distributing the files to other
#servers.

#clean up the temp files
foreach $file (@tmpfiles){
  #print "removing file: $file\n";
  system("rm -f $file");
}

#get rid of old tarball
#print "Removing old tarball\n";
system('rm -f /disks/debian/pkglists/bcfg2-packagelists.tgz');

#create new tarball for distribution
#print "Creating new tarball\n";
system('cd /disks/tmp/ ; tar czf /disks/debian/pkglists/bcfg2-packagelists.tgz bcfg2-packagelists 2&>1 >/dev/null' );

#move the files into place on the local machine
#for testing purposes and also until we get netzero converted to 0.8
#system('mv /disks/tmp/bcfg2-packagelists/*.xml /disks/tmp/bcfg2/Pkgmgr/');
#for real
system('mv /disks/tmp/bcfg2-packagelists/*.xml /disks/bcfg2/Pkgmgr/');

#final clean up
system('rmdir /disks/tmp/bcfg2-packagelists' );
