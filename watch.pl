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
use LWP::UserAgent;

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
	current_file => undef,
	dbfile => undef,
	zufall => 0,
	fullscreen => 1,
	controlport => 9332,
	controlpassword => rand(),
	controlhost => "localhost",
	next_in_order => 0
);

my $finished_playing = 0;

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

$SIG{USR1} = sub { 
	debug 3, "Received USR1, setting Zufall to 0";
	$options{zufall} = 0;
	$options{next_in_order} = 1;
};

$SIG{USR2} = sub {
	debug 3, "Received USR2, setting Zufall to 1";
	$options{zufall} = 1;
	$options{next_in_order} = 0;
};

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
${green}perl watch.pl --maindir=/home/norman/mailserver/serien/ --serie=Die-Simpsons --min_staffel=1 --max_staffel=14
--debug								Enable debug
--debuglevel=4							Level of debug messages
--controlpassword=password					Password for controlling VLC via https (default random-pw)
--controlport=port						Port for controlling VLC via https (default 9332)
--controlhost=IP						Port for controlling VLC via https (default localhost)
--dont_detect_changes_in_vlc					Do not detect changes in the VLC gui (e.g. pressing or unpressing the 'random' button)
--no_fullscreen							Don't use fullscreen automatically
--maindir=/path/to/maindir					Maindir
--serie=Serienregex						Serienname
--staffel=1							Staffel
--min_staffel=0							Minimal staffel to choose from (cannot be combined with --staffel)
--max_staffel=10						Maximal staffel to choose from (cannot be combined with --staffel)
--zufall							Random Staffel
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
		} elsif(m#^--controlpassword=(.*)$#) {
			$options{controlpassword} = $1;
		} elsif(m#^--controlport=(.*)$#) {
			$options{controlport} = $1;
		} elsif(m#^--controlhost=(.*)$#) {
			$options{controlhost} = $1;
		} elsif(m#^--no_fullscreen$#) {
			$options{fullscreen} = 0;
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
	debug 6, Dumper \%options;

	$options{staffeldir} = "$options{seriendir}/$options{staffel}";

	if(!-d $options{staffeldir}) {
		error "$options{staffeldir} is not a directory";
	}
}

sub get_time_priorisation ($) {
	my $episode_file = shift;
	debug 5, "get_time_priorisation($episode_file)";
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

		my $starttime_command = '';

		my $folder_current_file = $options{current_file};
		my $file_current_file = $options{current_file};

		$folder_current_file =~ s#(.*)/.*#$1/#g;
		$file_current_file =~ s#.*/##g;

		my $intro_endtime = "$folder_current_file/.intro_endtime";

		# https://github.com/NormanTUD/IntroCutter
		if(-e $intro_endtime ) {
			my @lines = qx(cat $intro_endtime);
			foreach my $line (@lines) {
				if($line =~ m#$file_current_file ::: (\d+)$#) {
					$starttime_command = "--start-time=$1";
				}
			}
		}

		my $fullscreen_command = "";
		if($options{fullscreen}) {
			$fullscreen_command = " --fullscreen ";
		}

		my $http_command = " --http-port $options{controlport} --http-password $options{controlpassword} --http-host $options{controlhost} ";

		$finished_playing = 0;
		my $play = qq#vlc $http_command $fullscreen_command --no-random --play-and-stop --no-repeat --loop $starttime_command "$options{current_file}"#;
		debug 1, $play;

		my $original_pid = $$;
		my $pid = $$;

		$pid = fork();

		if(not $pid) {
			system($play);
			my $exit_system = $?;
			my $exit = $exit_system >> 8;
			my $signal = $exit_system & 127;
			debug 0, "VLC Exit-Code: $exit, Signal: $signal";
			if($exit != 0) {
				exit $exit;
			}

			if(finished_playing()) {
				add_to_db($options{current_file});
			} else {
				debug 1, "You closed the window. Exiting";
				exit;
			}
		} else {
			sleep 2;

			quit_vlc_after_current();

			if($options{zufall}) {
				set_random_on($original_pid, 1);
			} else {
				set_random_off($original_pid, 1);
			}

			while (1) {
				my $randombutton_value = randombutton_is_pressed();
				if($randombutton_value ne $options{zufall}) {
					if($options{zufall}) {
						set_random_off($original_pid);
					} else {
						set_random_on($original_pid);
					}
				} else {
					debug 4, "Not changing random status";
				}
				sleep 1;
				if(finished_playing()) {
					quit_vlc();
					goto START;
				}
			}
		}
	} else {
		error "Invalid current file";
	}
}


sub quit_vlc_after_current {
	debug 0, "quit_vlc_after_current()";
	add_to_playlist("vlc://quit");
}

sub quit_vlc {
	debug 0, "quit_vlc()";
	set_http_info("pl_empty");
	set_http_info("in_play&input=vlc://quit");
}

sub set_random_on {
	my $original_pid = shift;
	my $in_player = shift // 0;
	debug 0, "set_random_on($original_pid, $in_player)";
	kill 'USR2', $original_pid;
	kill 'USR2', $$;
	if($in_player && !randombutton_is_pressed()) {
		toggle_player_random();
	}
}

sub set_random_off {
	my $original_pid = shift;
	my $in_player = shift // 0;
	debug 0, "set_random_off($original_pid, $in_player)";
	kill 'USR1', $original_pid;
	kill 'USR1', $$;
	if($in_player && randombutton_is_pressed()) {
		toggle_player_random();
	}
}

sub add_to_playlist {
	my $file = shift;
	debug 0, "add_to_playlist($file)";
	set_http_info("in_enqueue&input=file://$file");
}

sub set_playlist_to_default_order {
	debug 0, "set_playlist_to_default_order()";
	set_http_info("command=pl_sort&id=0&val=0");
}

sub toggle_player_random {
	debug 0, "toggle_player_random()";
	set_http_info("pl_random");
	set_playlist_to_default_order();
}

sub set_http_info {
	my $command = shift;
	debug 0, "set_http_info($command)";
	my $browser = LWP::UserAgent->new;
	my $url = "http://$options{controlhost}:$options{controlport}/requests/status.xml?command=$command";
	my $req =  HTTP::Request->new( GET => $url);
	$req->authorization_basic( "", "$options{controlpassword}" );
	debug 6, qq#curl -s -u $options{controlpassword} "$url"#;
	my $page = $browser->request( $req );
	if ($page->is_success) {
		return $page->decoded_content;
	} else {
		warn "Could not set $command";
	}
}

sub get_playlist {
	debug 0, "get_playlist()";
	my $browser = LWP::UserAgent->new;
	my $url = "http://$options{controlhost}:$options{controlport}/requests/playlist.xml";
	my $req =  HTTP::Request->new( GET => $url);
	$req->authorization_basic( "", "$options{controlpassword}" );
	debug 6, qq#curl -s -u $options{controlpassword} "$url"#;
	my $page = $browser->request( $req );
	if ($page->is_success) {
		my $p = $page->decoded_content;
		die $p;
		return $p;
	} else {
		die "not available";
	}
}

sub get_full_info_http {
	debug 0, "get_full_info_http()";
	my $browser = LWP::UserAgent->new;
	my $url = "http://$options{controlhost}:$options{controlport}/requests/status.xml";
	my $req =  HTTP::Request->new( GET => $url);
	$req->authorization_basic( "", "$options{controlpassword}" );
	debug 6, qq#curl -s -u $options{controlpassword} "$url"#;
	my $page = $browser->request( $req );
	if ($page->is_success) {
		return $page->decoded_content;
	} else {
		exit;
	}
}

sub finished_playing {
	debug 0, "finished_playing()";

	return $finished_playing if $finished_playing;

	my $full_info = get_full_info_http();
	warn $full_info;

	if($full_info =~ m#<currentplid>(.*)</currentplid>#) {
		if($1 eq "-1") {
			$finished_playing = 1;
			return 1;
		} else {
			return 0;
		}
	}
	return undef;
}

sub randombutton_is_pressed {
	my $full_info = get_full_info_http();
	warn $full_info;

	if($full_info =~ m#<random>(false|true)</random>#) {
		if($1 eq "true") {
			return 1;
		} else {
			return 0;
		}
	}
	return undef;
}

sub is_integer {
	my $str = shift;
	return 1 if $str =~ m#^\d+$#;
	return 0;
}

sub get_episode_nr_from_filename {
	my $filename = shift;
	debug 0, "get_episode_nr_from_filename($filename)";

	my $nr = $filename;
	$nr =~ s#^(\d+).*#$1#g;

	return $nr;
}

sub get_next_file {
	my $staffel = shift;
	my $last_file_nr = shift;
	debug 0, "get_next_file($staffel, $last_file_nr)";

	my $seriendir = $options{seriendir};

	my $basedir = "$options{seriendir}/$staffel/";

	my @files_in_seriendir_staffel = sort { get_episode_nr_from_filename($a) <=> get_episode_nr_from_filename($b) || $a cmp $b } get_subfolders_and_files(dir => $basedir, grep => sub { m#\.mp4$# });
	my $index = undef;
	my $i = 0;
	GETNEXTFILEFOREACH: foreach (@files_in_seriendir_staffel) {
		if(m#^$last_file_nr #) {
			$index = $i;
			last GETNEXTFILEFOREACH;
		}
		$i++;
	}

	if($index == $#files_in_seriendir_staffel) {
		$staffel++;
		$basedir = "$options{seriendir}/$staffel/";
		if(-d "$options{seriendir}/$staffel/") {
			my @files_in_seriendir_next_staffel = sort { get_episode_nr_from_filename($a) <=> get_episode_nr_from_filename($b) || $a cmp $b } get_subfolders_and_files(dir => $basedir, grep => sub { m#\.mp4$# });
			$options{staffel} = $staffel;
			$options{current_file} = $basedir.$files_in_seriendir_next_staffel[0];
		} else {
			$options{current_file} = undef;
		}
	} else {
		$options{current_file} = $basedir.$files_in_seriendir_staffel[$index + 1];
	}
}

sub choose_random_file {
	debug 0, "choose_random_file()";
	my $chosen_properly = 0;
	if($options{current_file} && $options{next_in_order}) {
		my $current_file = $options{current_file};
		my $current_staffel_dir = $current_file;

		my $staffel_nr = $current_staffel_dir;
		$staffel_nr =~ s#.*/(\d+)/.*?$#$1#g;

		my $current_filename = $current_file;
		$current_filename =~ s#.*/(.*?)$#$1#g;

		my $current_file_nr = $current_filename;
		$current_file_nr =~ s#(\d+) -.*#$1#g;

		debug 0, "=>=>=>=>=>=>=>=>=>=>=>=>=>staffelnr: $staffel_nr";
		debug 0, ">>>>>>>>>>>>>>>>>>>>>>>>>>get_next_file($staffel_nr, $current_file_nr);";
		get_next_file($staffel_nr, $current_file_nr);
		if(defined $options{current_file}) {
			$chosen_properly = 1;
		}
	}

	if(!$chosen_properly) {
		my @list = map { "$options{staffeldir}/$_" } get_subfolders_and_files(dir => $options{staffeldir}, grep => sub { m#\.mp4$# });
		my @weight = ();
		foreach (@list) {
			push @weight, get_time_priorisation("$options{seriendir}/$_");
		}
		my $thing = Math::Random::Discrete->new(\@weight, \@list);
		$options{current_file} = $thing->rand;
		debug 1, "Chose $options{current_file} (prio: ".get_time_priorisation("$options{current_file}").")";
	}
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

	debug 5, "get_time_priorisation_staffel($dir) = $sum";

	return $sum;
}

sub touch_dbfile {
	debug 0, "touch_dbfile()";
	my $command = "touch $options{dbfile}";
	debug 1, $command;
	system($command);
}

sub program_installed {
	my $program = shift;
	debug 0, "program_installed($program)";

	my $exists = 0;
	my $ret = system(qq#which $program > /dev/null 2> /dev/null#);

	if($ret == 0) {
		debug 4, "$program already installed";
		$exists = 1;
	} else {
		warn "$program does not seem to be installed. Please install it!";
	}

	return $exists;
}


sub check_installed_programs {
	debug 0, "check_installed_programs()";

	foreach (qw/vlc mediainfo whiptail/) {
		if(!program_installed($_)) {
			exit(1);
		}
	}
}

sub main () {
	debug 0, "main()";
	check_installed_programs();
	choose_serie;

	while (!-d $options{seriendir}) {
		choose_serie;
	}

	play_media while(1);
}

analyze_args(@ARGV);

START:
main;
