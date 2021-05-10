#!/usr/bin/perl

use strict;
use warnings;
use UI::Dialog;
use Capture::Tiny ':all';
use Data::Dumper;
use Tie::File;

my $d = new UI::Dialog ( backtitle => 'SerienWatcher', title => 'SerienWatcher',
	height => 35, width => 65 , listheight => 25,
	order => [ 'whiptail', 'gdialog', 'zenity', 'whiptail' ] );

my $nas_dir = "$ENV{HOME}/mailserver";
my $seriendir = "$nas_dir/serien/";
my $dbfile = "$seriendir/.db.txt";
my $serie = shift @ARGV // $d->inputbox( text => "Serienname:" );
my $staffel = shift @ARGV // '';
my $episode = shift @ARGV // '';
my $staffel_unter = undef;

sub main {
	if (-d $nas_dir) {
		if(-d $seriendir) {
			my $original_staffel = $staffel;
			opendir my $dir, $seriendir or die "Cannot open directory: $!";
			my @files = grep { -d "$seriendir/$_" && !/^\./ && (!$serie || /$serie/i )} readdir $dir;
			closedir $dir;

			my $choose_first = 0;

			if (@files > 1) {
				$serie = $d->radiolist( text => 'Serie waehlen:',
					list => [ 
						map { my $t = $_; $t => [ $t => ++$choose_first == 1 ] } @files
					]
				);
			} elsif (@files == 1) {
				$serie = $files[0];
			} else {
				$d->msgbox( text => 'Serie nicht gefunden' );
			}

			my $serienordner = "$seriendir/$serie";
			my $staffel_ordner = undef;

			my @staffeln = ();
			opendir my $staffeldir, $serienordner or die "Cannot open directory: $!";
			@staffeln = grep { /^\d+$/i } readdir $staffeldir;
			closedir $staffeldir;

			if(!$staffel) {
				my $zufall_unter = 0;
				if($serie =~ m#die-simpsons#i) {
					$zufall_unter = 1;
				}

				if(!$staffel) {
					$staffel = $d->radiolist( text => "Staffel von $serie:",
						list => [ 
							"Zufall unter" => ["Zufall unter" => $zufall_unter],
							"Zufall" => ["Zufall" => !$zufall_unter],
							map { my $t = $_; $t => [ $t => 0 ] } sort { $a <=> $b } @staffeln
						]
					);
					if($d->rv()) {
						exit;
					}
					$original_staffel = $staffel;
				}

				if($staffel eq "Zufall") {
					$staffel = splice(@staffeln, rand @staffeln, 1);
				} elsif($staffel eq "Zufall unter" && !$staffel_unter) {
					$staffel_unter = $d->inputbox( text => "Waehle zufaellige Staffeln <= dieser Zahl (a):",
						   entry => int(int(@staffeln) / 2) );
					@staffeln = grep { $_ <= $staffel_unter } @staffeln;
					$staffel = splice(@staffeln, rand @staffeln, 1);
				} elsif($staffel eq "Zufall unter" && $staffel_unter) {
					@staffeln = grep { $_ <= $staffel_unter } @staffeln;
					$staffel = splice(@staffeln, rand @staffeln, 1);
				}
				$staffel_ordner = "$serienordner/$staffel";
			}

			if($staffel =~ m"Zufall unter"i) {
				if(!$staffel_unter) {
					$staffel_unter = $d->inputbox( text => "Waehle zufaellige Staffeln <= dieser Zahl (b):",
						entry => int(int(@staffeln) / 2) );
					if($d->rv()) {
						exit;
					}
				}
				@staffeln = grep { $_ <= $staffel_unter } @staffeln;
				$staffel = splice(@staffeln, rand @staffeln, 1);
			}

			$staffel_ordner = "$serienordner/$staffel";

			opendir my $folgendir, $staffel_ordner or die "Cannot open directory: $!";
			my @folgen = grep { /\.mp4$/i } readdir $folgendir;
			closedir $folgendir;

			my $episode_file = undef;

			if($episode) {
				$episode_file = "$staffel_ordner/".([grep { /^0+$episode\s/ } @folgen]->[0]);
			} else {
				@folgen = sort { get_time_priorisation(qq#$staffel_ordner/$b#) <=> get_time_priorisation(qq#$staffel_ordner/$a#) || rand() <=> rand() } sort { rand() <=> rand() } @folgen;
				#die Dumper @folgen;
				warn Dumper +{map { $_ => get_time_priorisation("$staffel_ordner/$_") } @folgen};
				$episode_file = qq#"$staffel_ordner/#.$folgen[0].q#"#;
				print "Chose $episode_file with prio ".get_time_priorisation(qq#$episode_file#)."\n";
			}


			my $media_runtime = int(qx(mediainfo --Inform="Video;%Duration%" $episode_file) / 1000);

			my @args = (qq#vlc --no-random --play-and-exit $episode_file /dev/NONEXISTANTFILE#);
			my $starttime = scalar time();
			my ($stdout, $stderr, $exit) = capture {
				system(@args);
			};
			my $endtime = scalar time();
			my $runtime = $endtime - $starttime;

			print $stderr;

			if($stderr =~ m#NONEXISTANTFILE#) {
				if($runtime >= 0.8 * $media_runtime) {
					add_to_db($episode_file);
				} else {
					warn "$episode_file will not be counted as it only ran $runtime seconds. The file itself is $media_runtime seconds long.";
				}
				$staffel = $original_staffel;
				main();
			} else {
				exit;
			}
		} else {
			die "$seriendir not found";
		}
	} else {
		die "$nas_dir not found";
	}
}

sub get_time_priorisation {
	my $episode_file = shift;
	$episode_file =~ s#"##g;
	
	my @db = ();
	system("touch $dbfile");

	tie @db, 'Tie::File', $dbfile or die "Error accessing the file $dbfile: $!"; 
	my $prio = 10 ** 20;
	my $found = 0;
	foreach my $i (0 .. $#db) {
		last if $found;
		my $line = $db[$i];
		if($line =~ m#(.*):::(.*)#) {
			my ($filename, $time) = ($1, $2);
			if($filename eq qq#"$episode_file"#) {
				my $current_time = scalar time();
				my $watched_seconds_ago = int($current_time - $time);
				$prio = $watched_seconds_ago;
				$found = 1;
			}
		}
	}

	#die "$episode_file not found" unless $found;

	return $prio;
}

sub add_to_db {
	my $episode_file = shift;

	my @db = ();
	system("touch $dbfile");

	tie @db, 'Tie::File', $dbfile or die "Error accessing the file $dbfile: $!"; 
	my $found = 0;
	my $i = 0;
	foreach my $line (@db) {
		last if $found;
		if($line =~ m#(.*):::(.*)#) {
			my ($filename, $time) = ($1, $2);
			if($filename eq $episode_file) {
				$found = 1;
				$db[$i] = $episode_file.":::".(scalar time())."\n";
			}
		} elsif(!$line) {
			warn "Empty line in $dbfile";
		} elsif($line) {
			warn "Invalid line $line in $dbfile";
		}
		$i++;
	}

	if(!$found) {
		$db[$#db + 1] = $episode_file.":::".(scalar time())."\n";
	}
}

main();
