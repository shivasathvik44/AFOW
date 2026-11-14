#!/bin/bash
# Nautilus script to organize selected directories with AFOW
for target in "$@"; do
    if [ -d "$target" ]; then
        python3 -m afow "$target"
    fi
done
