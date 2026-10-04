#!/bin/bash
cd /tmp/claude-0/-home-user-Fieldops-Nexus/1ba6107a-6b9a-53da-8cac-e5015134fb36/scratchpad
. ./env.sh
python "$1.py" > "$1.out" 2>&1
echo done > "$1.done"
