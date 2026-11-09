#!/bin/sh
# Donne a Haretool le droit de lire le reseau (capture), sans le lancer en root.
cd "$(dirname "$0")"
sudo setcap cap_net_raw,cap_net_admin=eip ./Haretool/Haretool && echo "OK : lance ./Haretool/Haretool"
