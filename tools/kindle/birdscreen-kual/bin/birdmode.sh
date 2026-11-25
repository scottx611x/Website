#!/bin/sh
# KUAL > Bird screen > Bird mode: start KOReader straight into Bird mode.
# The flag tells the KOReader plugin to open Bird mode at once and to quit
# KOReader when it is closed, which returns to Amazon's home screen.
touch /mnt/us/extensions/birdscreen/birdmode.launch
exec /mnt/us/koreader/koreader.sh --kual
