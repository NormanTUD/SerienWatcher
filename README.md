# SerienWatcher

This script allows to watch series and logs when a specific episode has last been watched. When starting it, it looks into it's logs and choses episodes that have not been seen for the longest time.

# Example

```console
perl watch.pl --maindir=/home/norman/mailserver/serien/ --serie=Die-Simpsons --min_staffel=1 --max_staffel=14 --min_percentage_runtime_to_count=0.8
```

Check `--help` for all options.

# Dependencies

```console
sudo aptitude install vlc whiptail
sudo cpan -i Term::ANSIColor
sudo cpan -i UI::Dialog
sudo cpan -i Capture::Tiny ':all'
sudo cpan -i Data::Dumper
sudo cpan -i Tie::File
sudo cpan -i Math::Random::Discrete
```
