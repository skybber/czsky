#!/bin/bash

for i in *.jpg; do
    printf "Resize $i\n"
    replacement="__400.jpg"
    ii=${i/.jpg/$replacement}
    convert "$i" -trim -resize 400 "${ii}"
done
