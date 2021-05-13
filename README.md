# SerienWatcher

This script allows to watch series and logs when a specific episode has last been watched. When starting it, it looks into it's logs and choses episodes that have not been seen for the longest time.

# --maindir Structure

Your `maindir` must be structured like this:

```console
ls -1 $maindir/
Die-Simpsons
Futurama
...
```

```console
ls -1 $maindir/Die-Simpsons
1
2
3
...
```


```console
ls -1 $maindir/Die-Simpsons/1
'01 - Es-Weihnachtet-Schwer.mp4'
'02 - Bart-wird-ein-Genie.mp4'
'03 - Der-Versager.mp4'
'04 - Eine-Ganz-normale-Familie.mp4'
'05 - Bart-schlaegt-eine-Schlacht.mp4'
...
```

# Example

```console
perl watch.pl --maindir=/home/norman/mailserver/serien/ --serie=Die-Simpsons --min_staffel=1 --max_staffel=14 --min_percentage_runtime_to_count=0.8
```

Check `--help` for all options.

# Dependencies

```console
sudo aptitude install vlc whiptail mediainfo
sudo cpan -i Term::ANSIColor
sudo cpan -i UI::Dialog
sudo cpan -i Capture::Tiny ':all'
sudo cpan -i Data::Dumper
sudo cpan -i Tie::File
sudo cpan -i Math::Random::Discrete
```

