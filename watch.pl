#!/usr/bin/perl

use strict;
use warnings;
use UI::Dialog;
use Data::Dumper;

my $d = new UI::Dialog ( backtitle => 'SerienWatcher', title => 'SerienWatcher',
	height => 35, width => 65 , listheight => 25,
	order => [ 'zenity', 'whiptail' ] );

my $nas_dir = "$ENV{HOME}/mailserver";
my $seriendir = "$nas_dir/serien/";
my $serie = shift @ARGV // $d->inputbox( text => "Serienname:" );
my $staffel = shift @ARGV // '';
my $episode = shift @ARGV // '';

sub main {
	if (-d $nas_dir) {
		if(-d $seriendir) {
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

			if(!$staffel) {
				opendir my $staffeldir, $serienordner or die "Cannot open directory: $!";
				my @staffeln = grep { /^\d+$/i } readdir $staffeldir;
				closedir $staffeldir;

				my $zufall_unter = 0;
				if($serie =~ m#die-simpsons#i) {
					$zufall_unter = 1;
				}

				$staffel = $d->radiolist( text => "Staffel von $serie:",
					list => [ 
						"Zufall unter" => ["Zufall unter" => $zufall_unter],
						"Zufall" => ["Zufall" => !$zufall_unter],
						map { my $t = $_; $t => [ $t => 0 ] } sort { $a <=> $b } @staffeln
					]
				);

				if($staffel eq "Zufall") {
					$staffel = splice(@staffeln, rand @staffeln, 1);
				} elsif($staffel eq "Zufall unter") {
					my $unter = $d->inputbox( text => "Waehle zufaellige Staffeln unter dieser Zahl:",
						   entry => int(int(@staffeln) / 2) );
					@staffeln = grep { $_ <= $unter } @staffeln;
					$staffel = splice(@staffeln, rand @staffeln, 1);
				}
				$staffel_ordner = "$serienordner/$staffel";
			}

			$staffel_ordner = "$serienordner/$staffel";

			opendir my $folgendir, $staffel_ordner or die "Cannot open directory: $!";
			my @folgen = grep { /\.mp4$/i } readdir $folgendir;
			closedir $folgendir;

			my $episode_file = undef;

			if($episode) {
				$episode_file = "$staffel_ordner/".([grep { /^0+$episode\s/ } @folgen]->[0]);
			} else {
				$episode_file = qq#"$staffel_ordner/#.splice(@folgen, rand @folgen, 1).q#"#;
			}

			system("vlc --no-random --play-and-exit $episode_file");

			if ($d->yesno(text => 'Weitere Folge?')) {
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

main();
