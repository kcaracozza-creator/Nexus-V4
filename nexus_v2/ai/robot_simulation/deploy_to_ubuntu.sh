#!/bin/bash
# Deploy NEXUS Robot Simulation to Ubuntu Server
# Usage: ./deploy_to_ubuntu.sh [user@host]

SERVER="${1:-anielson@192.168.1.159}"
REMOTE_DIR="/home/anielson/nexus_robot_sim"

echo "==================================="
echo "NEXUS Robot Simulation Deployment"
echo "Server: $SERVER"
echo "==================================="

# Create remote directory
ssh $SERVER "mkdir -p $REMOTE_DIR"

# Copy files
echo "Copying simulation files..."
scp -r ./*.py $SERVER:$REMOTE_DIR/
scp -r ./*.urdf $SERVER:$REMOTE_DIR/
scp requirements.txt $SERVER:$REMOTE_DIR/

# Install dependencies
echo "Installing dependencies..."
ssh $SERVER "cd $REMOTE_DIR && pip3 install -r requirements.txt"

# Test simulation
echo "Testing simulation (headless)..."
ssh $SERVER "cd $REMOTE_DIR && python3 -c 'from arm_sim import NexusArmSim; s=NexusArmSim(gui=False); print(\"OK\"); s.close()'"

echo ""
echo "==================================="
echo "Deployment complete!"
echo ""
echo "To train the model, run:"
echo "  ssh $SERVER"
echo "  cd $REMOTE_DIR"
echo "  python3 arm_sim.py train 100000"
echo ""
echo "To view TensorBoard:"
echo "  tensorboard --logdir=$REMOTE_DIR/nexus_arm_tb"
echo "==================================="
