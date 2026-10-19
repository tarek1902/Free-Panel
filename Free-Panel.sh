#!/bin/sh
#

wget -O /tmp/Free-Panel.tar.gz "https://github.com/tarek1902/Free-Panel/raw/main/Free-Panel.tar.gz"

tar -xzf /tmp/Free-Panel.tar.gz -C /

wait

rm -f /tmp/Free-Panel.tar.gz
echo "   UPLOADED BY  >>>>   TAREK_HANFY "   
sleep 4;                                                                                                                  
echo ". >>>>         RESTARING     <<<<"
"**********************************************************************************"
wait
killall -9 enigma2
exit 0
