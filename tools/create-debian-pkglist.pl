#!/usr/bin/perl

#this is some setup that I have to do to make everything more localized below
#get all the packages/versions from security.debian.org. this is kinda hacky since we don't locally mirror that. I would like to for speed
#issues but since we are low on disk space I am not going to bother. 
#these are the files that I will need to use to get the right info.

system( "wget http://security.debian.org/dists/stable/updates/main/binary-i386/Packages -O /tmp/main.Packages -q" );
system( "wget http://security.debian.org/dists/stable/updates/contrib/binary-i386/Packages -O /tmp/contrib.Packages -q" );
system( "wget http://security.debian.org/dists/stable/updates/non-free/binary-i386/Packages -O /tmp/nonfree.Packages -q" );

#i now have all the files I need locally so I can do my opens properly.

open( MAIN, "/cluster/distro/debian/dists/stable/main/binary-i386/Packages" );
open( CONTRIB, "/cluster/distro/debian/dists/stable/contrib/binary-i386/Packages");
open( NONFREE, "/cluster/distro/debian/dists/stable/non-free/binary-i386/Packages");
open( NONMAIN, "/cluster/distro/debian-non-US/dists/stable/non-US/main/binary-i386/Packages" );
open( NONCONTRIB, "/cluster/distro/debian-non-US/dists/stable/non-US/contrib/binary-i386/Packages");
open( NONNONFREE, "/cluster/distro/debian-non-US/dists/stable/non-US/non-free/binary-i386/Packages");
open( SECMAIN, "/tmp/main.Packages");
open( SECCONTRIB, "/tmp/contrib.Packages");
open( SECNONFREE, "/tmp/nonfree.Packages");

open( LOCAL, "/cluster/debian/woody/Packages");
open( OUTFILE, ">/cluster/bcfg/images/debian-3.0/pkglist.xml" );

print OUTFILE "<PackageList image='debian-stable'>\n";
print OUTFILE "<Location uri='http://grandpoobah.mcs.anl.gov:8080/disks/cluster/disto/debian'>\n";

@mypackages = [];

#get all the data from the local repo that we maintain. This is the highest precedence in package priority                                                                                                                                                 
while( $line = <LOCAL> ){
    if( $line =~ /^Package:/ ){
        ($filler,$basename)=split( ' ', $line );
        push @mypackages, $basename;
	$found=0;
        while( !$found ){
            $line = <LOCAL>;
            if( $line =~ /^Version:/ ){
                ($filler,$version)=split( ' ', $line );
		
                print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
                $found =1;
            }
        }
    }
}

#now i will do all the security packages and add them to the my packages if they aren't already there. If that makes sense. 
#basically i am enforceing the priority by processing the package lists inorder.

$known_package=0;
while( $line = <SECMAIN> ){
	if( $line =~ /^Package:/ ){
		($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
		foreach $package ( @mypackages ){
			if( $basename eq $package ){	
				#print "I already saw: $basename\n";
				$known_package =1;
			}
		}
		$found = 0;
		while( !$found ){
			$line = <SECMAIN>;
			if( $line =~ /^Version:/ ){
                		($filler,$version)=split( ' ', $line );
				
				#print $version."\n";
				if ( ! $known_package ){
					print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
					push @mypackages, $basename;
				}
				$known_package = 0;
				$found =1;
			}
		}
	}
}

$known_package=0;
while( $line = <SECCONTRIB> ){
	if( $line =~ /^Package:/ ){
		($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
		foreach $package ( @mypackages ){
			if( $basename eq $package ){	
				#print "I already saw: $basename\n";
				$known_package =1;
			}
		}
		$found = 0;
		while( !$found ){
			$line = <SECCONTRIB>;
			if( $line =~ /^Version:/ ){
                		($filler,$version)=split( ' ', $line );
				
				#print $version."\n";
				if ( ! $known_package ){
					print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
					push @mypackages, $basename;
				}
				$known_package = 0;
				$found =1;
			}
		}
	}
}

$known_package=0;
while( $line = <SECNONFREE> ){
	if( $line =~ /^Package:/ ){
		($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
		foreach $package ( @mypackages ){
			if( $basename eq $package ){	
				#print "I already saw: $basename\n";
				$known_package =1;
			}
		}
		$found = 0;
		while( !$found ){
			$line = <SECNONFREE>;
			if( $line =~ /^Version:/ ){
                		($filler,$version)=split( ' ', $line );
				
				#print $version."\n";
				if ( ! $known_package ){
					print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
					push @mypackages, $basename;
				}
				$known_package = 0;
				$found =1;
			}
		}
	}
}


#now for all the regular packages in the mirrored repos

$known_package=0;
while( $line = <MAIN> ){
	if( $line =~ /^Package:/ ){
		($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
		foreach $package ( @mypackages ){
			if( $basename eq $package ){	
				#print "I already saw: $basename\n";
				$known_package =1;
			}
		}
		$found = 0;
		while( !$found ){
			$line = <MAIN>;
			if( $line =~ /^Version:/ ){
                		($filler,$version)=split( ' ', $line );
				
				if ( ! $known_package ){
					print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
				}
				$known_package = 0;
				$found =1;
			}
		}
	}
}

$known_package=0;
while( $line = <CONTRIB> ){
        if( $line =~ /^Package:/ ){
                ($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
		foreach $package ( @mypackages ){
                        if( $basename eq $package ){
                                $known_package =1;
				#print "I already saw: $basename\n";
                        }
                }
		$found=0;
                while( !$found ){
                        $line = <CONTRIB>;
                        if( $line =~ /^Version:/ ){
                                ($filler,$version)=split( ' ', $line );
				
				 if ( ! $known_package ){
                                        print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
                                }
				$known_package = 0;
                                $found =1;
                        }
                }
        }
}

$known_package=0;
while( $line = <NONFREE> ){
        if( $line =~ /^Package:/ ){
                ($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
                foreach $package ( @mypackages ){
                        if( $basename eq $package ){
                                $known_package =1;
				#print "I already saw: $basename\n";
                        }
                }
		$found=0;
		while( !$found ){
                        $line = <NONFREE>;
                        if( $line =~ /^Version:/ ){
                                ($filler,$version)=split( ' ', $line );
				
				if ( ! $known_package ){
                                        print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
                                }
				$known_package = 0;
                                $found =1;
                        }
                }
        }
}

$known_package=0;
while( $line = <NONMAIN> ){
	if( $line =~ /^Package:/ ){
		($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
		foreach $package ( @mypackages ){
			if( $basename eq $package ){	
				#print "I already saw: $basename\n";
				$known_package =1;
			}
		}
		$found = 0;
		while( !$found ){
			$line = <NONMAIN>;
			if( $line =~ /^Version:/ ){
                		($filler,$version)=split( ' ', $line );
				
				if ( ! $known_package ){
					print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
				}
				$known_package = 0;
				$found =1;
			}
		}
	}
}

$known_package=0;
while( $line = <NONCONTRIB> ){
        if( $line =~ /^Package:/ ){
                ($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
		foreach $package ( @mypackages ){
                        if( $basename eq $package ){
                                $known_package =1;
				#print "I already saw: $basename\n";
                        }
                }
		$found=0;
                while( !$found ){
                        $line = <NONCONTRIB>;
                        if( $line =~ /^Version:/ ){
                                ($filler,$version)=split( ' ', $line );
				
				 if ( ! $known_package ){
                                        print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
                                }
				$known_package = 0;
                                $found =1;
                        }
                }
        }
}

$known_package=0;
while( $line = <NONNONFREE> ){
        if( $line =~ /^Package:/ ){
                ($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
                foreach $package ( @mypackages ){
                        if( $basename eq $package ){
                                $known_package =1;
				#print "I already saw: $basename\n";
                        }
                }
		$found=0;
		while( !$found ){
                        $line = <NONNONFREE>;
                        if( $line =~ /^Version:/ ){
                                ($filler,$version)=split( ' ', $line );
				
				if ( ! $known_package ){
                                        print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
                                }
				$known_package = 0;
                                $found =1;
                        }
                }
        }
}

print OUTFILE "</Location>\n</PackageList>\n";



close(OUTFILE);
close(MAIN);
close(CONTRIB);
close(NONFREE);
close(NONMAIN);
close(NONCONTRIB);
close(NONNONFREE);
close(SECMAIN);
close(SECCONTRIB);
close(SECNONFREE);
close(LOCAL);


#now i will do the same thing but for the sarge build
 #i now have all the files I need locally so I can do my opens properly.

open( MAIN, "/cluster/distro/debian/dists/sarge/main/binary-i386/Packages" );
open( CONTRIB, "/cluster/distro/debian/dists/sarge/contrib/binary-i386/Packages");
open( NONFREE, "/cluster/distro/debian/dists/sarge/non-free/binary-i386/Packages");
open( NONMAIN, "/cluster/distro/debian-non-US/dists/sarge/non-US/main/binary-i386/Packages" );
open( NONCONTRIB, "/cluster/distro/debian-non-US/dists/sarge/non-US/contrib/binary-i386/Packages");
open( NONNONFREE, "/cluster/distro/debian-non-US/dists/sarge/non-US/non-free/binary-i386/Packages");

open( LOCAL, "/cluster/debian/sarge/Packages");
open( OUTFILE, ">/cluster/bcfg/images/debian-sarge/pkglist.xml" );

print OUTFILE "<PackageList image='debian-sarge'>\n";
print OUTFILE "<Location uri='http://grandpoobah.mcs.anl.gov:8080/disks/cluster/disto/debian'>\n";

@mypackages = [];

#get all the data from the local repo that we maintain. This is the highest precedence in package priority                                                                                                                                                 
while( $line = <LOCAL> ){
    if( $line =~ /^Package:/ ){
        ($filler,$basename)=split( ' ', $line );
        push @mypackages, $basename;
	$found=0;
        while( !$found ){
            $line = <LOCAL>;
            if( $line =~ /^Version:/ ){
                ($filler,$version)=split( ' ', $line );
                print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
                $found =1;
            }
        }
    }
}



#now for all the regular packages in the mirrored repos

$known_package=0;
while( $line = <MAIN> ){
	if( $line =~ /^Package:/ ){
		($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
		foreach $package ( @mypackages ){
			if( $basename eq $package ){	
				#print "I already saw: $basename\n";
				$known_package =1;
			}
		}
		$found = 0;
		while( !$found ){
			$line = <MAIN>;
			if( $line =~ /^Version:/ ){
                		($filler,$version)=split( ' ', $line );
				
				if ( ! $known_package ){
					print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
					push @mypackages, $basename;
				}
				$known_package = 0;
				$found =1;
			}
		}
	}
}

$known_package=0;
while( $line = <CONTRIB> ){
        if( $line =~ /^Package:/ ){
                ($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
		foreach $package ( @mypackages ){
                        if( $basename eq $package ){
                                $known_package =1;
				#print "I already saw: $basename\n";
                        }
                }
		$found=0;
                while( !$found ){
                        $line = <CONTRIB>;
                        if( $line =~ /^Version:/ ){
                                ($filler,$version)=split( ' ', $line );
				
				 if ( ! $known_package ){
                                        print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
                                }
				$known_package = 0;
                                $found =1;
                        }
                }
        }
}

$known_package=0;
while( $line = <NONFREE> ){
        if( $line =~ /^Package:/ ){
                ($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
                foreach $package ( @mypackages ){
                        if( $basename eq $package ){
                                $known_package =1;
				#print "I already saw: $basename\n";
                        }
                }
		$found=0;
		while( !$found ){
                        $line = <NONFREE>;
                        if( $line =~ /^Version:/ ){
                                ($filler,$version)=split( ' ', $line );
				
				if ( ! $known_package ){
                                        print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
                                }
				$known_package = 0;
                                $found =1;
                        }
                }
        }
}

$known_package=0;
while( $line = <NONMAIN> ){
	if( $line =~ /^Package:/ ){
		($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
		foreach $package ( @mypackages ){
			if( $basename eq $package ){	
				#print "I already saw: $basename\n";
				$known_package =1;
			}
		}
		$found = 0;
		while( !$found ){
			$line = <NONMAIN>;
			if( $line =~ /^Version:/ ){
                		($filler,$version)=split( ' ', $line );
				
				if ( ! $known_package ){
					print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
				}
				$known_package = 0;
				$found =1;
			}
		}
	}
}

$known_package=0;
while( $line = <NONCONTRIB> ){
        if( $line =~ /^Package:/ ){
                ($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
		foreach $package ( @mypackages ){
                        if( $basename eq $package ){
                                $known_package =1;
				#print "I already saw: $basename\n";
                        }
                }
		$found=0;
                while( !$found ){
                        $line = <NONCONTRIB>;
                        if( $line =~ /^Version:/ ){
                                ($filler,$version)=split( ' ', $line );
				
				 if ( ! $known_package ){
                                        print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
                                }
				$known_package = 0;
                                $found =1;
                        }
                }
        }
}

$known_package=0;
while( $line = <NONNONFREE> ){
        if( $line =~ /^Package:/ ){
                ($filler,$basename)=split( ' ', $line );
		#print $basename."\n";
                foreach $package ( @mypackages ){
                        if( $basename eq $package ){
                                $known_package =1;
				#print "I already saw: $basename\n";
                        }
                }
		$found=0;
		while( !$found ){
                        $line = <NONNONFREE>;
                        if( $line =~ /^Version:/ ){
                                ($filler,$version)=split( ' ', $line );
				
				if ( ! $known_package ){
                                        print OUTFILE "\t<Package name=\"".$basename."\" version=\"".$version."\"/>\n" ;
                                }
				$known_package = 0;
                                $found =1;
                        }
                }
        }
}

print OUTFILE "</Location>\n</PackageList>\n";



close(OUTFILE);
close(MAIN);
close(CONTRIB);
close(NONFREE);
close(NONMAIN);
close(NONCONTRIB);
close(NONNONFREE);
close(LOCAL);
	
