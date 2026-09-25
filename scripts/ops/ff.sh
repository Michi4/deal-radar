#!/bin/bash
# deploy deal-radar on homeserver via jump host. usage: ./ff-deploy.sh [command...]
export SSHPASS='Michael23'
sshpass -e ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 home@10.8.1.2 "$@"
