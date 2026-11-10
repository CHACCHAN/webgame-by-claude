#!/bin/bash
# final check renders for the H2 (two streams)
B=~/.local/opt/carfit/blender.sh
S=/home/dev/Desktop/service/internal/webgame-by-claude/frontend/tools/blender/bikes/ninjah2.py
cd ~/.local/opt/carfit/bikes/ninjah2
(
$B -t 6 -b --factory-startup --python $S -- --norider --render cy_nr --views photo:r01,photo:r02 --cams fit/cams.json --samples 20 --size 1440x1080 > /tmp/claude-1000/h2_s1.log 2>&1
$B -t 6 -b --factory-startup --python $S -- --norider --night --render cy_nr --views photo:r02 --cams fit/cams.json --samples 20 --size 1440x1080 >> /tmp/claude-1000/h2_s1.log 2>&1
$B -t 6 -b --factory-startup --python $S -- --norider --render cy_nr --views metal,metal_f,lamp,tail --samples 24 --size 1280x720 >> /tmp/claude-1000/h2_s1.log 2>&1
) &
(
$B -t 6 -b --factory-startup --python $S -- --out ninjah2.glb --render cy --views side,front34,rear34 --samples 24 --size 1280x720 > /tmp/claude-1000/h2_s2.log 2>&1
$B -t 6 -b --factory-startup --python $S -- --night --render cy --views front34 --samples 24 --size 1280x720 >> /tmp/claude-1000/h2_s2.log 2>&1
$B -t 6 -b --factory-startup --python $S -- --norider --night --render cy_nr --views lamp,tail --samples 24 --size 1280x720 >> /tmp/claude-1000/h2_s2.log 2>&1
) &
wait
echo DONE
