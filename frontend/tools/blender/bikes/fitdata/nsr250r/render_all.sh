#!/bin/bash
# final check renders for the NSR (two streams)
B=~/.local/opt/carfit/blender.sh
S=/home/dev/Desktop/service/internal/webgame-by-claude/frontend/tools/blender/bikes/nsr250r.py
cd ~/.local/opt/carfit/bikes/nsr250r
(
$B -t 6 -b --factory-startup --python $S -- --norider --render cy_nr --views photo:r01 --cams fit/cams.json --sun -45,22 --samples 24 --size 1920x1080 > /tmp/claude-1000/nsr_s1.log 2>&1
$B -t 6 -b --factory-startup --python $S -- --norider --render cy_nr --views photo:r05,photo:r02 --cams fit/cams.json --sun 30,40 --samples 20 --size 1440x1080 >> /tmp/claude-1000/nsr_s1.log 2>&1
$B -t 6 -b --factory-startup --python $S -- --norider --night --render cy_nr --views photo:r01 --cams fit/cams.json --samples 24 --size 1920x1080 >> /tmp/claude-1000/nsr_s1.log 2>&1
) &
(
$B -t 6 -b --factory-startup --python $S -- --out nsr250r.glb --render cy --views side,front34,rear34,metal,metal_f,lamp,tail --samples 24 --size 1280x720 > /tmp/claude-1000/nsr_s2.log 2>&1
$B -t 6 -b --factory-startup --python $S -- --night --render cy --views front34,lamp --samples 24 --size 1280x720 >> /tmp/claude-1000/nsr_s2.log 2>&1
) &
wait
echo DONE
