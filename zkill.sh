#! /bin/sh

#set -e

for f in ~/pid/*.pid; do
  if test -f "$f"; then
    echo "killing $f"
    kill "`cat $f`"
  fi
done

pkill -f cc.daemon
pkill -f cc.server

#rm -rf ./var/log ./var/run ./var/info* ./infodir/info*
#mkdir -p var/log var/run

sleep 1

ps aux|grep '[p]ython'
