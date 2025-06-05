#!/bin/bash
#SBATCH --job-name=meaningful_memories
#SBATCH --partition=gpu_a100
#SBATCH --time=1:00:00
#SBATCH --gpus=1

module load 2023 FFmpeg/6.0-GCCcore-12.3.0

source ~/Code/Sandbox/venv/bin/activate

input_dir=~/Code/2025_meaningful_memories/in_het_diepe_op_bureau_warmoesstraat/

python -m meaningful_memories.pipeline --input-dir input_dir
