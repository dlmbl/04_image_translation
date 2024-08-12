#!/usr/bin/env bash

### TO DO ###
# Change back the environment name and run pip install dominate

# Exit immediately if a command exits with a non-zero status
set -e
# Save current directory.
START_DIR=$(pwd)
echo "Starting directory: $START_DIR"
# Create and navigate to GAN_code directory
mkdir -p ~/data/06_image_translation/part2/GAN_code
cd ~/data/06_image_translation/part2/GAN_code
echo "Current directory after creating and navigating to GAN_code: $(pwd)"
# Clone the Git repository
git clone git@github.com:Tonks684/GANs_MI2I.git
echo "Repository cloned. Current directory: $(pwd)"
# Create conda environment from yml
cd ~/data/06_image_translation/part2/GAN_code/GANs_MI2I
echo "Current directory after navigating to GANs_MI2I: $(pwd)"

# # Find path to the environment - conda activate doesn't work from within shell scripts.
ENV_PATH=$(conda info --envs | grep 06_image_translation | awk "{print $NF}")
$ENV_PATH/bin/pip install "dominate"

# Define and create the output directory
output_dir=~/data/06_image_translation/part2/tiff_files
mkdir -p "$output_dir"
echo "Output directory created at: $output_dir"

# Download the weights
mkdir -p ~/data/06_image_translation/part2/model_tensorboard
cd ~/data/06_image_translation/part2/model_tensorboard
wget -O dlmbl_requisites.zip "https://zenodo.org/record/13173900/files/dlmbl_requisites.zip?download=1"
unzip dlmbl_requisites.zip

# Move the weights to the correct directory
mkdir -p ~/data/06_image_translation/part2/model_weights
mv ~/data/06_image_translation/part2/model_tensorboard/dlmbl_vsnuclei/dlmbl_vsnuclei ~/data/06_image_translation/part2/model_weights
mv ~/data/06_image_translation/part2/model_tensorboard/dlmbl_vscyto/dlmbl_vscyto ~/data/06_image_translation/part2/model_weights

# Download and split the dataset
cd ~/data/06_image_translation/part2/GAN_code/GANs_MI2I
python download_and_split_dataset.py --output_image_folder $output_dir --crop_size 512
echo "Dataset downloaded and split."
# Return to the starting directory
cd "$START_DIR"
echo "Returned to the starting directory: $START_DIR"


