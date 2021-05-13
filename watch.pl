#!/usr/bin/perl

use strict;
use warnings FATAL => 'all';
use Data::Dumper;

use Math::Random::Discrete;
use Term::ANSIColor;
use UI::Dialog;
use Capture::Tiny ':all';
use Data::Dumper;
use Tie::File;
use Memoize;

my %cache;
memoize 'get_time_priorisation_staffel', SCALAR_CACHE => [HASH => \%cache];
memoize 'touch_dbfile';

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
	dbfile => undef,
	zufall => 0
);

my $d = new UI::Dialog ( backtitle => 'SerienWatcher', title => 'SerienWatcher',
	height => 35, width => 65 , listheight => 25,
	order => [ 'whiptail', 'gdialog', 'zenity', 'whiptail' ] );

sub error ($;$) {
	my $message = shift;
	my $no_exit = shift // 1;
	debug 0, "error($message, $no_exit)";
	warn color("red").$message.color("reset")."\n";
	if($no_exit != 1) {
		exit 1;
	}
}

sub debug ($$) {
	my $debuglevel = shift;
	my $text = shift;
	if($options{debug} && $options{debuglevel} >= $debuglevel) {
		warn "DEBUG ($debuglevel): ".color("blue on_white").$text.color("reset")."\n";
	}
}

sub input {
	my ($text, $entry) = @_;
	debug 0, "input($text, $entry)";
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
	debug 0, "radiolist($text, \$list)";
	my $chosen = $d->radiolist(text => $text, list => $list);
	if($d->rv()) {
		exit;
	}

	return $chosen;
}

sub msg {
	my $text = shift;
	debug 0, "msg($text)";
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
--zufall                                                      Random Staffel
EOF
	exit $exit;
}

sub get_subfolders_and_files {
	my %par = (
		dir => undef,
		grep => sub { !m#^\.#i },
		@_
	);

	debug 0, "get_subfolders_and_files(".Dumper(\%par).")";

	opendir my $dirhandle, $par{dir} or error "Cannot open directory: $!";
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
		} elsif(m#^--zufall$#) {
			$options{zufall} = 1;
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
	debug 0, "choose_serie()";
	if(defined $options{serie}) {
		$options{seriendir} = "$options{maindir}/$options{serie}";
	}

	if(!defined $options{serie} || !-d $options{seriendir}) {
		my @serien = get_subfolders_and_files(dir => $options{maindir}, grep => sub { !m#^\.# && -d "$options{maindir}/$_" && (defined $options{serie} ? m#\Q$options{serie}\E#i : 1) });
		my $first = 0;
		if(@serien == 1) {
			$options{serie} = $serien[0];
		} elsif (@serien == 0) {
			if(defined $options{serie}) {
				msg "Mit dem Regex /$options{serie}/ konnten keine Serien gefunden werden.";
			} else {
				error "Es konnten keine Serien gefunden werden", 1;
			}
			@serien = get_subfolders_and_files(dir => $options{maindir} && sub { !m#^\.# } );
			$options{serie} = radiolist("Waehle Serie: ", [map { $_ => [$_ => !$first++] } @serien ]);
		} else {
			$options{serie} = radiolist("Waehle Serie: ", [map { $_ => [$_ => !$first++] } @serien ]);
		}
	}

	$options{seriendir} = "$options{maindir}/$options{serie}";
}

sub get_weighted_random {
	debug 0, "get_weighted_random(\@list)";
	my @list = @_;
	my @weight = ();
	foreach (@list) {
		push @weight, get_time_priorisation_staffel("$options{seriendir}/$_");
	}
	my $thing = Math::Random::Discrete->new(\@weight, \@list);
	return $thing->rand;
}

sub choose_staffel {
	debug 0, "choose_staffel()";
	my @staffeln = ();
	my $first = 0;

	if($options{rechoose_staffel}) {
		$options{staffel} = undef;
	}

	%cache = ();

	if(!defined($options{staffel}) && !defined $options{min_staffel} && !defined($options{max_staffel})) {
		@staffeln = get_subfolders_and_files(dir => $options{seriendir}, grep => sub { !m#^\.# && -d "$options{seriendir}/$_" });
		my $selection = $options{zufall} == 1 ? 'Zufall' : radiolist("Waehle Staffel fuer $options{serie}: ", [
				"Zufall unter" => ["Zufall unter", 0], 
				"Zufall" => ["Zufall", 0], 
				map { $_ => [$_ => !$first++] } @staffeln 
			]
		);

		if($selection eq "Zufall unter") {
			$options{min_staffel} = [sort { $a <=> $b } @staffeln]->[0];
			$options{max_staffel} = input("Staffel unter:");
			$options{rechoose_staffel} = 1;
			choose_staffel();
		} elsif($selection eq "Zufall") {
			$options{staffel} = get_weighted_random(@staffeln);
			$options{rechoose_staffel} = 1;
			$options{zufall} = 1;
		} else {
			$options{staffel} = $selection;
		}
	} elsif (!defined($options{staffel}) && defined($options{min_staffel}) && !defined($options{max_staffel})) {
		@staffeln = get_subfolders_and_files(dir => $options{seriendir}, grep => sub { !m#^\.# && -d "$options{seriendir}/$_" && $_ >= $options{min_staffel} });
		$options{rechoose_staffel} = 1;
		$options{staffel} = get_weighted_random(@staffeln);
	} elsif (!defined($options{staffel}) && !defined($options{min_staffel}) && defined($options{max_staffel})) {
		@staffeln = get_subfolders_and_files(dir => $options{seriendir}, grep => sub { !m#^\.# && -d "$options{seriendir}/$_" && $_ <= $options{max_staffel} });
		$options{rechoose_staffel} = 1;
		$options{staffel} = get_weighted_random(@staffeln);
	} elsif (!defined($options{staffel}) && defined($options{min_staffel}) && defined($options{max_staffel})) {
		@staffeln = get_subfolders_and_files(dir => $options{seriendir}, grep => sub { !m#^\.# && -d "$options{seriendir}/$_" && $_ >= $options{min_staffel} && $_ <= $options{max_staffel} });
		$options{rechoose_staffel} = 1;
		$options{staffel} = get_weighted_random(@staffeln);
	} elsif(defined($options{staffel}) && !defined $options{min_staffel} && !defined($options{max_staffel})) {
		# do nothing, staffel already specified
	} else {
		error "Cannot choose specific staffel and then use --max_staffel and/or --min_staffel at the same time", 0;
	}

	debug 1, "Chose staffel $options{staffel}, time prio: ".get_time_priorisation_staffel("$options{seriendir}/$options{staffel}");
	debug 2, Dumper \%options;

	$options{staffeldir} = "$options{seriendir}/$options{staffel}";

	if(!-d $options{staffeldir}) {
		error "$options{staffeldir} is not a directory";
	}
}

sub get_time_priorisation ($) {
	my $episode_file = shift;
	debug 0, "get_time_priorisation($episode_file)";
	$episode_file =~ s#"##g;
	
	my @db = ();
	touch_dbfile();

	tie @db, 'Tie::File', $options{dbfile} or error "Error accessing the file $options{dbfile}: $!"; 
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
	debug 0, "add_to_db($episode_file)";

	my @db = ();
	touch_dbfile();

	tie @db, 'Tie::File', $options{dbfile} or error "Error accessing the file $options{dbfile}: $!"; 
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

sub get_media_runtime () {
	debug 0, "get_media_runtime";
	if(-e $options{current_file}) {
		my $mediainfo = qq#mediainfo --Inform="Video;%Duration%" "$options{current_file}"#;
		debug 1, $mediainfo;
		my $media_runtime_string = qx($mediainfo);
		chomp $media_runtime_string;
		my $media_runtime = int($media_runtime_string / 1000);
		return $media_runtime;
	} else {
		error "$options{current_file} is not a file";
	}
}

sub play_media () {
	debug 0, "play_media";
	choose_staffel();
	choose_random_file();
	if(defined $options{current_file} && -e $options{current_file}) {
		my $media_runtime = get_media_runtime;
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
			if($runtime >= ($options{min_percentage_runtime_to_count} * $media_runtime) || ($media_runtime >= 120 && $runtime > 30) || exists $ENV{FORCECOUNT}) {
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

sub choose_random_file {
	debug 0, "choose_random_file()";
	my @list = map { "$options{staffeldir}/$_" } get_subfolders_and_files(dir => $options{staffeldir}, grep => sub { m#\.mp4$# });
	my @weight = ();
	foreach (@list) {
		push @weight, get_time_priorisation("$options{seriendir}/$_");
	}
	my $thing = Math::Random::Discrete->new(\@weight, \@list);
	$options{current_file} = $thing->rand;
	debug 1, "Chose $options{current_file} (prio: ".get_time_priorisation("$options{current_file}").")";
}

sub get_time_priorisation_staffel {
	my $dir = shift;
	debug 0, "get_time_priorisation($dir)";
	my @files = ();

	touch_dbfile();

	my $sum = 0;

	my @db = ();
	tie @db, 'Tie::File', $options{dbfile} or error "Error accessing the file $options{dbfile}: $!"; 
	my $i = 0;
	foreach my $line (@db) {
		if($line =~ m#(.*):::(.*)#) {
			my ($filename, $time) = ($1, $2);
			my $re_string = $dir =~ s#/#/+#gr;
			if($filename =~ $re_string) {
				push @files, $filename;

				my $current_time = scalar time();
				my $watched_seconds_ago = int($current_time - $time);
				$sum += $watched_seconds_ago;
			}
		} elsif(!$line) {
			warn "Empty line in $options{dbfile}";
		} elsif($line) {
			warn "Invalid line $line in $options{dbfile}";
		}
		$i++;
	}

	if(!@files) {
		$sum = 10**20;
	} else {
		$sum = int($sum / scalar(@files));
	}

	debug 1, "get_time_priorisation_staffel($dir) = $sum";

	return $sum;
}

sub touch_dbfile {
	debug 0, "touch_dbfile()";
	my $command = "touch $options{dbfile}";
	debug 1, $command;
	system($command);
}

sub main () {
	debug 0, "main()";
	choose_serie;

	while (!-d $options{seriendir}) {
		choose_serie;
	}

	play_media while(1);
}

analyze_args(@ARGV);

main;
