#!/bin/bash
# deploy deal-radar on app host via jump host. usage: ./ff-deploy.sh [command...]
export PASSWORD-VAR='**ROTATED-CHANGE-ME**'
sshpass -e ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 home@10.9.9.2 "$@"
