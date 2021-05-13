#!/usr/bin/perl

use strict;
use warnings FATAL => 'all';
use Data::Dumper;

use Term::ANSIColor;
use UI::Dialog;
use Capture::Tiny ':all';
use Data::Dumper;
use Tie::File;

sub error ($;$);
sub debug ($$);

my %options = (
	debug => 0,
	play => 1,
	debuglevel => 1,
	maindir => undef,
	serie => undef,
	staffel => undef,
	min_staffel => undef,
	max_staffel => undef,
	seriendir => undef,
	staffeldir => undef,
	min_percentage_runtime_to_count => 0.8,
	current_file => undef,
	dbfile => undef
);

my $d = new UI::Dialog ( backtitle => 'SerienWatcher', title => 'SerienWatcher',
	height => 35, width => 65 , listheight => 25,
	order => [ 'whiptail', 'gdialog', 'zenity', 'whiptail' ] );

sub error ($;$) {
	my $message = shift;
	my $no_exit = shift // 1;
	warn color("red").$message.color("reset")."\n";
	if($no_exit != 1) {
		exit 1;
	}
}

sub debug ($$) {
	my $debuglevel = shift;
	my $text = shift;
	if($options{debug} && $options{debuglevel} >= $debuglevel) {
		warn "DEBUG: ".color("blue on_white").$text.color("reset")."\n";
	}
}

sub input {
	my ($text, $entry) = @_;
	my $result = $d->inputbox( text => $text, entry => $entry);
	if($d->rv()) {
		debug 1, "You chose cancel. Exiting.";
		exit();
	}
	return $result;
}

sub radiolist {
	my $text = shift;
	my $list = shift;
	my $chosen = $d->radiolist(text => $text, list => $list);
	if($d->rv()) {
		exit;
	}

	return $chosen;
}

sub msg {
	my $text = shift;
	$d->msgbox(text => $text);
}

sub _help {
	my $exit = shift // 0;
	my $message = shift // undef;
	error $message if(defined($message));

	my ($green, $reset) = (color("green"), color("reset"));

	print <<EOF;
Example call:
${green}perl watch.pl --maindir=/home/norman/mailserver/serien/ --serie=Die-Simpsons --min_staffel=1 --max_staffel=14 --min_percentage_runtime_to_count=0.8${reset}
--debug                                                       Enable debug
--debuglevel=4                                                Level of debug messages
--noplay                                                      Disable VLC starting (only useful for debugging)
--maindir=/path/to/maindir                                    Maindir
--serie=Serienregex                                           Serienname
--staffel=1                                                   Staffel
--min_staffel=0                                               Minimal staffel to choose from (cannot be combined with --staffel)
--max_staffel=10                                              Maximal staffel to choose from (cannot be combined with --staffel)
--min_percentage_runtime_to_count=$options{min_percentage_runtime_to_count}                           Minimal percentage for the play to be counted (between 0 and 1)
EOF
	exit $exit;
}

sub get_subfolders_and_files {
	my %par = (
		dir => undef,
		grep => sub { !m#^\.#i },
		@_
	);

	opendir my $dirhandle, $par{dir} or die "Cannot open directory: $!";
	my @result = grep { $par{grep}->($_) } readdir $dirhandle;
	closedir $dirhandle;
	return sort { ($a =~ m#^\d$# && $b =~ m#^\d$# ) ? $a <=> $b : $a cmp $b } @result;
}

sub analyze_args {
	foreach (@_) {
		if(m#^--debug$#) {
			$options{debug} = 1;
		} elsif(m#^--debuglevel=(.*)$#) {
			$options{debuglevel} = $1;
		} elsif(m#^--noplay$#) {
			$options{play} = 0;
		} elsif(m#^--maindir=(.*)$#) {
			my $maindir = $1;
			if(-d $maindir) {
				$options{maindir} = $maindir;
			} else {
				error "--maindir $maindir not found", 0;
			}
		} elsif(m#^--serie=(.*)$#) {
			$options{serie} = $1;
		} elsif(m#^--staffel=(.*)$#) {
			$options{staffel} = $1;
		} elsif(m#^--min_staffel=(.*)$#) {
			$options{min_staffel} = $1;
		} elsif(m#^--max_staffel=(.*)$#) {
			$options{max_staffel} = $1;
		} elsif(m#^--min_percentage_runtime_to_count=(.*)$#) {
			$options{min_percentage_runtime_to_count} = $1;
		} elsif (m#^--help$#) {
			_help(0);
		} else {
			_help(1, "Unknown parameter: $_");				
		}
	}

	if(!defined($options{maindir})) {
		error "--maindir cannot stay empty", 0;
	}

	$options{dbfile} = "$options{maindir}/.db.txt";
}

sub choose_serie () {
	$options{seriendir} = "$options{maindir}/$options{serie}";

	if(!$options{serie} || !-d $options{seriendir}) {
		my @serien = get_subfolders_and_files(dir => $options{maindir}, grep => sub { m#\Q$options{serie}\E#i });
		my $first = 0;
		if(@serien == 1) {
			$options{serie} = $serien[0];
		} elsif (@serien == 0) {
			msg "Mit dem Regex /$options{serie}/ konnten keine Serien gefunden werden.";
			@serien = get_subfolders_and_files(dir => $options{maindir});
			$options{serie} = radiolist("Waehle Serie: ", [map { $_ => [$_ => !$first++] } @serien ]);
		} else {
			$options{serie} = radiolist("Waehle Serie: ", [map { $_ => [$_ => !$first++] } @serien ]);
		}
	}

	$options{seriendir} = "$options{maindir}/$options{serie}";
}

sub choose_staffel {
	my @staffeln = ();
	my $first = 0;

	if($options{rechoose_staffel}) {
		$options{staffel} = undef;
	}

	if(!defined($options{staffel}) && !defined $options{min_staffel} && !defined($options{max_staffel})) {
		@staffeln = get_subfolders_and_files(dir => $options{seriendir}, grep => sub { !m#^\.# && -d "$options{seriendir}/$_" });
		my $selection = radiolist("Waehle Staffel fuer $options{serie}: ", [ "Zufall unter" => ["Zufall unter", 0], map { $_ => [$_ => !$first++] } @staffeln ]);
		if($selection eq "Zufall unter") {
			$options{min_staffel} = [sort { $a <=> $b } @staffeln]->[0];
			$options{max_staffel} = input("Staffel unter:");
			choose_staffel();
		} else {
			$options{staffel} = $selection;
		}
	} elsif (!defined($options{staffel}) && defined($options{min_staffel}) && !defined($options{max_staffel})) {
		@staffeln = get_subfolders_and_files(dir => $options{seriendir}, grep => sub { !m#^\.# && -d "$options{seriendir}/$_" && $_ >= $options{min_staffel} });
		$options{rechoose_staffel} = 1;
		$options{staffel} = [sort { rand() <=> rand() } @staffeln]->[0];
	} elsif (!defined($options{staffel}) && !defined($options{min_staffel}) && defined($options{max_staffel})) {
		@staffeln = get_subfolders_and_files(dir => $options{seriendir}, grep => sub { !m#^\.# && -d "$options{seriendir}/$_" && $_ <= $options{max_staffel} });
		$options{rechoose_staffel} = 1;
		$options{staffel} = [sort { rand() <=> rand() } @staffeln]->[0];
	} elsif (!defined($options{staffel}) && defined($options{min_staffel}) && defined($options{max_staffel})) {
		@staffeln = get_subfolders_and_files(dir => $options{seriendir}, grep => sub { !m#^\.# && -d "$options{seriendir}/$_" && $_ >= $options{min_staffel} && $_ <= $options{max_staffel} });
		$options{rechoose_staffel} = 1;
		$options{staffel} = [sort { rand() <=> rand() } @staffeln]->[0];
	} elsif(defined($options{staffel}) && !defined $options{min_staffel} && !defined($options{max_staffel})) {
		# do nothing, staffel already specified
	} else {
		error "Cannot choose specific staffel and then use --max_staffel and/or --min_staffel at the same time", 0;
	}

	debug 2, Dumper \%options;

	$options{staffeldir} = "$options{seriendir}/$options{staffel}";

	if(!-d $options{staffeldir}) {
		error "$options{staffeldir} is not a directory";
	}
}

sub get_time_priorisation ($) {
	my $episode_file = shift;
	$episode_file =~ s#"##g;
	
	my @db = ();
	system("touch $options{dbfile}");

	tie @db, 'Tie::File', $options{dbfile} or die "Error accessing the file $options{dbfile}: $!"; 
	my $prio = 10 ** 20;
	my $found = 0;
	foreach my $i (0 .. $#db) {
		last if $found;
		my $line = $db[$i];
		if($line =~ m#(.*):::(.*)#) {
			my ($filename, $time) = ($1, $2);
			if($episode_file =~ m#$filename#) {
				my $current_time = scalar time();
				my $watched_seconds_ago = int($current_time - $time);
				$prio = $watched_seconds_ago;
				$found = 1;
			}
		}
	}

	return $prio;
}

sub add_to_db ($) {
	my $episode_file = shift;

	my @db = ();
	system("touch $options{dbfile}");

	tie @db, 'Tie::File', $options{dbfile} or die "Error accessing the file $options{dbfile}: $!"; 
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
			warn "Empty line in $options{dbfile}";
		} elsif($line) {
			warn "Invalid line $line in $options{dbfile}";
		}
		$i++;
	}

	if(!$found) {
		$db[$#db + 1] = $episode_file.":::".(scalar time())."\n";
	}
}

sub get_media_runtime ($) {
	my $episode_file = shift;
	my $mediainfo = qq#mediainfo --Inform="Video;%Duration%" "$episode_file"#;
	debug 1, $mediainfo;
	my $media_runtime_string = qx($mediainfo);
	chomp $media_runtime_string;
	my $media_runtime = int($media_runtime_string / 1000);
}

sub play_media () {
	if(defined $options{current_file} && -e $options{current_file}) {
		my $media_runtime = get_media_runtime $options{current_file};
		my $play = qq#vlc --no-random --play-and-exit "$options{current_file}" /dev/NONEXISTANTFILE#;
		debug 1, $play;

		my $starttime = scalar time();
		my ($stdout, $stderr, $exit) = ('', 'NONEXISTANTFILE', '');

		if($options{play}) {
			($stdout, $stderr, $exit) = capture {
				system($play);
			};
		} else {
			print "Press enter to continue";
			<STDIN>;
		}
		my $endtime = scalar time();
		my $runtime = $endtime - $starttime;

		if($stderr =~ m#NONEXISTANTFILE#) {
			if($runtime >= $options{min_percentage_runtime_to_count} * $media_runtime) {
				add_to_db($options{current_file});
			} else {
				warn "$options{current_file} will not be counted as it only ran $runtime seconds. The file itself is $media_runtime seconds long.\n";
			}
			main();
		} else {
			debug 1, "You closed the window, as the file NONEXISTANTFILE was not found in stderr. Exiting.";
			exit;
		}
	} else {
		error "Invalid current file";
	}
}

sub choose_random_file () {
	my @episodes = get_subfolders_and_files(dir => $options{staffeldir}, grep => sub { m#\.mp4$# });
	my @serien_sorted = sort { $b->{prio} <=> $a->{prio} || rand() <=> rand() } map { +{file => $_, prio => get_time_priorisation("$options{staffeldir}/$_")} } @episodes;
	debug 3, Dumper @serien_sorted;
	$options{current_file} = $options{staffeldir}.'/'.[@serien_sorted]->[0]->{file};
	debug 1, "Chose $options{current_file} (prio: ".get_time_priorisation("$options{current_file}").")";
}

sub main () {
	choose_serie;

	while (!-d $options{seriendir}) {
		choose_serie;
	}
	
	choose_staffel();

	choose_random_file;

	play_media while(1);
}

analyze_args(@ARGV);

main;
