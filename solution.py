# %% [markdown] tags=["pix2pixGAN_explainer"]
"""
# Generative Modelling Approaches to Image translation
---

Written by Samuel Tonks, Krull Lab, University of Birmingham, UK.<br><br>

In this part of the exercise, we will approach the same supervised image-to-image translation task as in the previous parts, but using a different model architecture. Here we will explore a generative modelling approach; a conditional Generative Adversarial Network (cGAN). <br><br>

In contrast to formulating the task as a regression problem where the model produces a single deterministic output, cGANs learn to map from the source domain to a target domain distribution. This learnt distribution can then be sampled from to produce virtual staining predictions that are no longer a compromise between possible solutions which can lead to improved sharpness and realism in the generated images.<br><br>

At a high-level a cGAN has two networks; a generator and a discriminator. The generator is a fully convolutional network that takes the source image as input and outputs the target image. The discriminator is also a fully convolutional network that takes as input the source image concatentated with a real or fake image and outputs the probabilities of whether the image is real or fake as shown in the Figure below: 
[cGAN](https://github.com/Tonks684/image_translation/tree/main/imgs/GAN.svg)
<br><br>
The generator is trained to fool the discriminator into predicting a high probability that its generated outputs are real, and the discriminator is trained to distinguish between real and fake images. Both networks are trained using an adversarial loss in a min-max game, where the generator tries to minimize the probability of the discriminator correctly classifying its outputs as fake, and the discriminator tries to maximize this probability. It is typically trained until the discriminator can no longer determine whether or not the generated images are real or fake better than a random guess (p(0.5)).<br><br>

We will be exploring [Pix2PixHD GAN](https://arxiv.org/abs/1711.11585) architecture, a high-resolution extension of a traditional cGAN adapted for our recent [virtual staining works](https://ieeexplore.ieee.org/abstract/document/10230501?casa_token=NEyrUDqvFfIAAAAA:tklGisf9BEKWVjoZ6pgryKvLbF6JyurOu5Jrgoia1QQLpAMdCSlP9gMa02f3w37PvVjdiWCvFhA). Pix2PixHD GAN improves upon the traditional cGAN by using a coarse-to-fine generator, a multi-scale discrimator and additional loss terms. The "coarse-to-fine" generator is composed of two sub-networks, both ResNet architectures that operate at different scales. The first sub-network (G1) generates a low-resolution image, which is then upsampled and concatenated with the source image to produce a higher resolution image. The multi-scale discriminator is composed of 3 networks that operate at different scales, each network is trained to distinguish between real and fake images at that scale. The generator is trained to fool the discriminator at each scale. The additional loss terms include a feature matching loss, which encourages the generator to produce images that are similar to the real images at each scale. <br><br>
[1](https://github.com/Tonks684/image_translation/tree/main/imgs/Pix2PixHD_1.svg)
[1](https://github.com/Tonks684/image_translation/tree/main/imgs/Pix2PixHD_2.svg)
"""


# %% [markdown]
"""
Today, we will train a 2D image translation model using the Pix2PixHD GAN. We will use the same dataset of 301 fields of view (FOVs) of Human Embryonic Kidney (HEK) cells, each FOV has 3 channels (phase, membrane, and nuclei) as used in the previous section.<br><br>
"""
# %% [markdown]
"""
<div class="alert alert-warning">
This part of the exercise is organized in 3 parts.<br><br>

As you have already explored the data in the previous parts, we will focus on training and evaluating Pix2PixHD GAN. The parts are as follows:<br><br>

* **Part 1** - Define dataloaders & walk through steps to train a Pix2PixHD GAN.<br><br>
* **Part 2** - Load and assess a pre-trained Pix2PixGAN using tensorboard, discuss the different loss components and how new hyper-parameter configurations could impact performance.<br><br>
* **Part 3** - Evaluate performance of pre-trained Pix2PixGAN using pixel-level and instance-level metrics.<br><br>
* **Part 4** - Compare the performance of Viscy (regression-based) with Pix2PixHD GAN (generative modelling approach)<br><br>
* **Part 5** - BONUS: Sample different virtual staining solutions from the GAN using MC-Dropout and explore the uncertainty in the virtual stain predictions.<br><br>
</div>
"""
# %% [markdown]
"""
Our guesstimate is that each of the parts will take ~1 hour. A reasonable Pix2PixHD GAN can be trained in ~1.5 hours on a typical AWS node, this notebook is designed to walk you through the training steps but load a pre-trained model and tensorboard session to ensure we can complete the exercise in the time allocated. During Part 2, you're free to train your own model using the steps we outline in part 1.<br><br>

The focus of this part of the exercise is on understanding a generative modelling approach to image translation, how to train and evaluate a cGAN, and explore some hyperparameters of the cGAN. <br><br>
"""
# %% [markdown]
"""
<div class="alert alert-danger">
Set your python kernel to <span style="color:black;">04_image_translation</span>
</div>
"""
# %% <a [markdown] id="1_phase2fluor"></a>
"""
# Part 1: Define dataloaders & walk through steps to train a Pix2PixHD GAN.
---------
The focus of this part of the exercise is on understanding a generative modelling approach to image translation, how to train and evaluate a cGAN, and explore some hyperparameters of the cGAN. 

Learning goals:

- Load dataset and configure dataloader.
- Configure Pix2PixHD GAN and train to predict nuclei from phase.
"""

# %% Imports and paths
from pathlib import Path
import os
import torch
import numpy as np
import pandas as pd
from tqdm import tqdm
from skimage import metrics
from tifffile import imread, imsave
import matplotlib.pyplot as plt

# Import all the necessary hyperparameters and configurations for training.
from GANs_MI2I.pix2pixHD.options.train_options import TrainOptions
from GANs_MI2I.pix2pixHD.options.test_options import TestOptions

# Import Pytorch dataloader and transforms.
from GANs_MI2I.pix2pixHD.data.data_loader_dlmbl import CreateDataLoader

# Import the model architecture.
from GANs_MI2I.pix2pixHD.models import create_model

# Import helper functions for visualization and processing.
from GANs_MI2I.pix2pixHD.util.visualizer import Visualizer
from GANs_MI2I.pix2pixHD.util import util

# Import train script.
from GANs_MI2I.pix2pixHD.train_dlmbl import train as train_model
from GANs_MI2I.pix2pixHD.test_dlmbl import inference as inference_model, sampling

# Import the function to compute segmentation scores.
from GANs_MI2I.segmentation_scores import gen_segmentation_scores
# pytorch lightning wrapper for Tensorboard.
from torch.utils.tensorboard import SummaryWriter


# Initialize the default options and parse the arguments.
opt = TrainOptions().parse()
# Set the seed for reproducibility.
util.set_seed(int(opt.seed))
# Set the experiment folder name.
opt.name = "dlmbl_vsnuclei"
# Path to store all the logs.
opt.checkpoints_dir = Path(f"~/data/04_image_translation/{opt.name}/logs/").expanduser()
output_image_folder = Path("~/data/04_image_translation/tiff_files/").expanduser()
# Initalize the tensorboard writer.
writer = SummaryWriter(log_dir=opt.checkpoints_dir)

# %% [markdown tags=[dataloading]]
"""
## 1.1 Load Dataset & Configure Dataloaders.
Having already downloaded and split our training, validation and test sets we now need to load the data into the model. We will use the Pytorch DataLoader class to load the data in batches. The DataLoader class is an iterator that provides a consistent way to load data in batches. We will also use the CreateDataLoader class to load the data in the correct format for the Pix2PixHD GAN.
"""
# %%
# Initialize the Dataset and Dataloaders.

## Define Dataset & Dataloader options.
dataset_opt = {}
dataset_opt["--dataroot"] = output_image_folder
dataset_opt["--data_type"] = "16"  # Data type of the images.
dataset_opt["--loadSize"] = "512"  # Size of the loaded phase image.
dataset_opt["--input_nc"] = "1"  # Number of input channels.
dataset_opt["--output_nc"] = "1"  # Number of output channels.
dataset_opt["--resize_or_crop"] = "none"  # Scaling and cropping of images at load time [resize_and_crop|crop|scale_width|scale_width_and_crop|none].
dataset_opt["--target"] = "nuclei"  # or "cyto" depending on your choice of target for virtual stain.


# Update opt with key value pairs from dataset_opt.
opt.__dict__.update(dataset_opt)

# Load Training Set for input into model
train_dataloader = CreateDataLoader(opt)
dataset_train = train_dataloader.load_data()
print(f"Total Training Images = {len(train_dataloader)}")

# Load Val Set
opt.phase = "val"
val_dataloader = CreateDataLoader(opt)
dataset_val = val_dataloader.load_data()
print(f"Total Validation Images = {len(val_dataloader)}")

# %% [markdown]
"""
## Configure Pix2PixHD GAN and train to predict nuclei from phase.
Having loaded the data into the model we can now train the Pix2PixHD GAN to predict nuclei from phase. We will use the following hyperparameters to train the model:

"""
# %%
model_opt = {}

# Define the parameters for the Generator.
model_opt["--ngf"] = "64"  # Number of filters in the generator.
model_opt["--n_downsample_global"] = "4"  # Number of downsampling layers in the generator.
model_opt["--n_blocks_global"] = "9"  # Number of residual blocks in the generator.
model_opt["--n_blocks_local"] = "3"  # Number of residual blocks in the generator.
model_opt["--n_local_enhancers"] = "1"  # Number of local enhancers in the generator.

# Define the parameters for the Discriminators.
model_opt["--num_D"] = "3"  # Number of discriminators.
model_opt["--n_layers_D"] = "3"  # Number of layers in the discriminator.
model_opt["--ndf"] = "32"  # Number of filters in the discriminator.

# Define general training parameters.
model_opt["--gpu_ids"] = "0"  # GPU ids to use.
model_opt["--norm"] = "instance"  # Normalization layer in the generator.
model_opt["--use_dropout"] = ""  # Use dropout in the generator (fixed at 0.2).
model_opt["--batchSize"] = "8"  # Batch size.

# Update opt with key value pairs from model_opt
opt.__dict__.update(model_opt)

# Initialize the model
phase2nuclei_model = create_model(opt)
# Define Optimizers for G and D
optimizer_G, optimizer_D = (
    phase2nuclei_model.module.optimizer_G,
    phase2nuclei_model.module.optimizer_D,
)
# Create a visualizer to perform image processing and visualization
visualizer = Visualizer(opt)


# Here will first start training a model from scrach however we can continue to train from a previously trained model by setting the following parameters.
opt.continue_train = False
if opt.continue_train:
    iter_path = os.path.join(opt.checkpoints_dir, opt.name, "iter.txt")
    try:
        start_epoch, epoch_iter = np.loadtxt(iter_path, delimiter=",", dtype=int)
    except:
        start_epoch, epoch_iter = 1, 0
    print("Resuming from epoch %d at iteration %d" % (start_epoch, epoch_iter))
else:
    start_epoch, epoch_iter = 1, 0

train_model(
    opt,
    phase2nuclei_model,
    visualizer,
    dataset_train,
    dataset_val,
    optimizer_G,
    optimizer_D,
    start_epoch,
    epoch_iter,
    iter_path,
    writer,
)

# %% [markdown]
"""
<div class="alert alert-warning">

## A heads up of what to expect from the training (more detail about this in the following section)...

The train_model function has been designed so you can see the different Pix2PixHD GAN loss components discussed in the first part of the exercise as well as additional performance measurements. As previously mentioned, Pix2PixHD GAN has two networks; a generator and a discriminator. The generator is trained to fool the discriminator into predicting a high probability that its generated outputs are real, and the discriminator is trained to distinguish between real and fake images. Both networks are trained using an adversarial loss in a min-max game, where the generator tries to minimize the probability of the discriminator correctly classifying its outputs as fake, and the discriminator tries to maximize this probability. It is typically trained until the discriminator can no longer determine whether or not the generated images are real or fake better than a random guess (p(0.5)). After a we have iterated through all the training data, we validate the performance of the network on the validation dataset. 

In light of this, we plot the discriminator probabilities of real (D_real) and fake (D_fake) images, for the training and validation datasets.

Both networks are also trained using the feature matching loss (Generator_GAN_Loss_Feat), which encourages the generator to produce images that contain similar statistics to the real images at each scale. We also plot the feature matching L1 loss for the training and validation sets together to observe the performance and how the model is fitting the data.

In our implementation, in addition to the Pix2PixHD GAN loss components already described we stabalize the GAN training by additing an additional least-square loss term. This term stabalizes the training of the GAN by penalizing the generator for producing images that the discriminator is very confident (high probability) are fake. This loss term is added to the generator loss and is used to train the generator to produce images that are similar to the real images.
We plot the least-square loss (Generator_Loss_GAN) for the training and validation sets together to observe the performance and how the model is fitting the data.
This implementation allows for the turning on/off of the least-square loss term by setting the --no_lsgan flag to the model options. As well as the turning off of the feature matching loss term by setting the --no_ganFeat_loss flag to the model options and the turning off of the VGG loss term by setting the --no_vgg_loss flag to the model options. Something you might want to explore in the next section!

Finally, we also plot the Peak-Signal-to-Noise-Ratio (PSNR) and the Structural Similarity Index Measure (SSIM) for the training and validation sets together to observe the performance and how the model is fitting the data.

[PSNR](https://en.wikipedia.org/wiki/Peak_signal-to-noise_ratio), is a widely used metric to assess the quality of the generated image compared to the target image. Formally. it measures the ratio between the maximum possible power of a signal and the power of the corrupting noise that affects the fidelity of its representation. Essentially, PSNR provides a quantitative measurement of the quality of an image after compression or other processing such as image translation. Unlike the Pearson-Coeffecient, when measuring how much the pixel values of the virtual stain deviate from the target nuceli stain the score is sensitive to changes in brightness and contrast which is required for necessary for evaluating virtual staining. PSNR values range from 0dB to upper bounds that rarely exceed 60 dB. Extremely high PSNR values (above 50 dB) typically indicate almost negligible differences between the images.


[SSIM](https://en.wikipedia.org/wiki/Structural_similarity), is a perceptual metric used to measure the similarity between two images. Unlike PSNR, which focuses on pixel-wise differences, SSIM evaluates image quality based on perceived changes in structural information, luminance, and contrast. SSIM values range from -1 to 1, where 1 indicates perfect similarity between the images. SSIM is a more robust metric than PSNR, as it takes into account the human visual system"s sensitivity to structural information and contrast. SSIM is particularly useful for evaluating the quality of image translation models, as it provides a more accurate measure of the perceptual similarity between the generated and target images.

</div>
"""
# %% [markdown]
"""
# Part 2: Load & Assess trained Pix2PixGAN using tensorboard, discuss performance of the model.
--------------------------------------------------
Learning goals:
- Understand the loss components of Pix2PixHD GAN and how they are used to train the model.
- Evaluate the fit of the model on the train and validation datasets.

In this part, we will evaluate the performance of the pre-trained model as shown in the previous part. We will begin by looking qualitatively at the model predictions, then dive into the different loss curves, as well as the SSIM and PSNR scores achieves on the validation set. We will also train another model to see if we can improve the performance of the model.

"""
translation_task = "nuclei"  # or "cyto" depending on your choice of target for virtual stain.
# %% Imports and paths tags=[]
log_dir = f"~/data/04_image_translation/pretrained_GAN/{opt.name}/"
%reload_ext tensorboard
%tensorboard --logdir {$log_dir}

# %% [markdown]
"""
<div class="alert alert-info">
## Qualitative evaluation:

##### Should I add answers to the questions below? Make it an exercise?
We have visualised the model output for an unseen phase contrast image and the target, nuclei stain.

- What do you notice about the virtual staining predictions? Are they realistic? How does the sharpness and visual representation compare to the regression-based approach?

- What do you notice about the translation of the background pixels compared the translation of the instance pixels?

## Quantitative evaluation:

- What do you notice about the probabilities (real vs fake) of the discriminators? How do the values compare during training compared to validation?

- What do you notice about the feature matching L1 loss?

- What do you notice about the least-square loss?

- What do you notice about the PSNR and SSIM scores? Are we over or underfitting at all?

</div>
"""
"""
<div class="alert alert-success">
    
## Checkpoint 1

Congratulations! You should now have a better understanding of how a conditional generative model works! Please feel in your own time to train your own Pix2PixHD GAN model and evaluate the performance of the training of the model.

</div>
"""
# %% [markdown]
"""
# Part 3: Evaluate performance of the virtual staining on unseen data.
--------------------------------------------------
## Evaluate the performance of the model.
We now look at the same metrics of performance of the previous model. We typically evaluate the model performance on a held out test data. 

Steps:
- Define our model parameters for the pre-trained model (these are the same parameters as shown in earlier cells but copied here for clarity).
- Load the test data.

We will first load the test data using the same format as the training and validation data. We will then use the model to predict the nuclei channel from the phase image. We will then evaluate the performance of the model using the following metrics:

Pixel-level metrics:
- [Peak-Signal-to-Noise-Ratio (PSNR)](https://en.wikipedia.org/wiki/Peak_signal-to-noise_ratio).
- [Structural Similarity Index Measure (SSIM)](https://en.wikipedia.org/wiki/Structural_similarity).

Instance-level metrics:
- [F1 score](https://en.wikipedia.org/wiki/F1_score). via [Cellpose](https://cellpose.org/).
"""
# %% <a [markdown]> </a>

opt = TestOptions().parse(save=False)
dataset_opt = {}
# Define the parameters for the dataset.
dataset_opt["--dataroot"] = output_image_folder
dataset_opt["--data_type"] = "16"  # Data type of the images.
dataset_opt["--loadSize"] = "512"  # Size of the loaded phase image.
dataset_opt["--input_nc"] = "1"  # Number of input channels.
dataset_opt["--output_nc"] = "1"  # Number of output channels.
dataset_opt["--resize_or_crop"] = "none"  # Scaling and cropping of images at load time [resize_and_crop|crop|scale_width|scale_width_and_crop|none].
dataset_opt["--target"] = translation_task  # "nuclei" or "cyto" depending on your choice of target for virtual stain.

# Update opt with key value pairs from dataset_opt.
opt.__dict__.update(dataset_opt)

# Define the model parameters for the pre-trained model.
model_opt = {}
# Define the parameters for the Generator.
model_opt["--ngf"] = "64"  # Number of filters in the generator.
model_opt["--n_downsample_global"] = "4"  # Number of downsampling layers in the generator.
model_opt["--n_blocks_global"] = "9"  # Number of residual blocks in the generator.
model_opt["--n_blocks_local"] = "3"  # Number of residual blocks in the generator.
model_opt["--n_local_enhancers"] = "1"  # Number of local enhancers in the generator.
# Define the parameters for the Discriminators.
model_opt["--num_D"] = "3"  # Number of discriminators.
model_opt["--n_layers_D"] = "3"  # Number of layers in the discriminator.
model_opt["--ndf"] = "32"  # Number of filters in the discriminator.
# Define general training parameters.
model_opt["--gpu_ids"] = "0"  # GPU ids to use.
model_opt["--norm"] = "instance"  # Normalization layer in the generator.
model_opt["--use_dropout"] = ""  # Use dropout in the generator (fixed at 0.2).
model_opt["--batchSize"] = "8"  # Batch size.
# Define loss functions.
model_opt["--no_vgg_loss"] = ""  # Turn off VGG loss
model_opt["--no_ganFeat_loss"] = ""  # Turn off feature matching loss
model_opt["--no_lsgan"] = ""  # Turn off least square loss
# Update opt with key value pairs from model_opt
opt.__dict__.update(model_opt)


# Additional Inference parameters
inference_opt = {}
opt.name = f"dlmbl_vs{translation_task}"
inference_opt["--how_many"] = "144"  # Number of images to generate.
inference_opt["--checkpoints_dir"] = f"~/data/04_image_translation/pretrained_GAN/{opt.name}/"  # Path to the model checkpoints.
inference_opt["--results_dir"] = f"~/data/04_image_translation/pretrained_GAN/{opt.name}/results/"  # Path to store the results.
inference_opt["--which_epoch"] = "latest"  # or specify the epoch number "40"
inference_opt["--phase"] = "test"
opt.__dict__.update(inference_opt)

opt.nThreads = 1  # test code only supports nThreads = 1
opt.batchSize = 1  # test code only supports batchSize = 1
opt.serial_batches = True  # no shuffle
opt.no_flip = True  # no flip
Path(opt.results_dir).mkdir(parents=True, exist_ok=True)

# Load the test data.
test_data_loader = CreateDataLoader(opt)
test_dataset = test_data_loader.load_data()
visualizer = Visualizer(opt)

# Load pre-trained model
model = create_model(opt)

# Generate & save predictions in the results directory.
inference_model(test_dataset, opt, model)

# Gather results for evaluation
virtual_stain_paths = sorted([i for i in Path(opt.results_dir).glob("**/*.tiff")])
target_stain_paths = sorted(
    [
        i
        for i in Path(f"{output_image_folder}/{translation_task}/test/").glob(
            "**/*.tiff"
        )
    ]
)
phase_paths = sorted(
    [i for i in Path(f"{output_image_folder}/input/test/").glob("**/*.tiff")]
)
assert (
    len(virtual_stain_paths) == len(target_stain_paths) == len(phase_paths)
), "Number of images do not match."

# Create arrays to store the images.
virtual_stains = np.zeros((len(virtual_stain_paths), 512, 512))
target_stains = virtual_stains.copy()
phase_images = virtual_stains.copy()
# Load the images and store them in the arrays.
for index, (v_path, t_path, p_path) in tqdm(
    enumerate(zip(virtual_stain_paths, target_stain_paths, phase_paths))
):
    virtual_stain = imread(v_path)
    phase_image = imread(p_path)
    target_stain = imread(t_path)
    # Append the images to the arrays.
    phase_images[index] = phase_image
    target_stains[index] = target_stain
    virtual_stains[index] = virtual_stain

# %% [markdown] tags=[]
"""
<div class="alert alert-info">

### Task 3.1 Visualise the results of the model on the test set.

Create a matplotlib plot that visalises random samples of the phase images, target stains, and virtual stains.
</div>
"""
# %% tags=["task"]
##########################
######## TODO ########
##########################


def visualise_results():
    # Your code here
    pass


# %% tags=["solution"]

##########################
######## Solution ########
##########################


def visualise_results(
    phase_images: np.array, target_stains: np.array, virtual_stains: np.array
):
    """
    Visualizes the results of the staining process by displaying the phase images, target stains, and virtual stains.

    Args:
        phase_images (np.array): Array of phase images with shape (N, H, W).
        target_stains (np.array): Array of target stains with shape (N, H, W).
        virtual_stains (np.array): Array of virtual stains with shape (N, H, W).

    Returns:
        None
    """
    fig, axes = plt.subplots(5, 3, figsize=(15, 15))
    sample_indices = np.random.choice(len(phase_images), 5)
    for i, idx in enumerate(sample_indices):
        axes[i, 0].imshow(phase_images[idx], cmap="gray")
        axes[i, 0].set_title("Phase")
        axes[i, 0].axis("off")
        axes[i, 1].imshow(
            target_stains[idx],
            cmap="gray",
            vmin=np.percentile(target_stains[idx], 1),
            vmax=np.percentile(target_stains[idx], 99),
        )
        axes[i, 1].set_title("Nuclei")
        axes[i, 1].axis("off")
        axes[i, 2].imshow(
            virtual_stains[idx],
            cmap="gray",
            vmin=np.percentile(target_stains[idx], 1),
            vmax=np.percentile(target_stains[idx], 99),
        )
        axes[i, 2].set_title("Virtual Stain")
        axes[i, 2].axis("off")
    plt.tight_layout()
    plt.show()


test_metrics = pd.DataFrame(columns=["pearson_nuc", "SSIM_nuc", "psnr_nuc"])
# %% [markdown] tags=[]
"""
<div class="alert alert-info">

### Task 3.2 Compute pixel-level metrics

Compute the pixel-level metrics for the virtual stains and target stains. The metrics include Pearson correlation, SSIM, and PSNR.
</div>
"""
# Pixel-level metrics
for i, (target_image, predicted_image) in enumerate(zip(target_stains, virtual_stains)):
    # Compute SSIM and pearson correlation.
    ssim_score = metrics.structural_similarity(
        target_image, predicted_image, data_range=1
    )
    pearson_score = np.corrcoef(target_image.flatten(), predicted_image.flatten())[0, 1]
    psnr_score = metrics.peak_signal_noise_ratio(
        target_image, predicted_image, data_range=1
    )
    test_metrics.loc[i] = {
        "pearson_nuc": pearson_score,
        "SSIM_nuc": ssim_score,
        "psnr_nuc": psnr_score,
    }

test_metrics.boxplot(
    column=["pearson_nuc", "SSIM_nuc", "psnr_nuc"],
    rot=30,
)


"""
<div class="alert alert-info">

### Task 3.3 Compute instance-level metrics

- Use Cellpose to segment the nuclei or  membrane channels of the fluorescence and virtual staining images.
- Compute the F1 score for the segmentation masks.


</div>
"""
# %% [markdown] tags=[]

# Run cellpose to generate masks for the virtual stains
path_to_virtual_stain = Path(opt.results_dir)
path_to_targets = Path(f"{output_image_folder}/test/")
cellpose_model = "nuclei"  # or "cyto" depending on your choice of target for virtual stain.
# Run for virtual stain
!python -m cellpose --dir $path_to_virtual_stain --pretrained_model $cellpose_model --chan 0 --save_tiff
# Run for fluorescence stain
!python -m cellpose --dir $path_to_virtual_stain --pretrained_model $cellpose_model --chan 0 --save_tiff
predicted_masks = sorted([i for i in path_to_predictions.glob("**/*_cp_masks.tif*")])
target_masks = sorted([ifor i in Path(path_to_targets).glob("**/*_cp_masks.tif*")])
assert len(predicted_masks) == len(target_masks), "Number of masks do not match."

# Use a predefined function to compute F1 score and its component parts.
# %% [markdown] tags=[]
# Generate dataframe to store the outputs
results = pd.DataFrame(
    columns=[
        'Model', 'Image', 'GT_Cell_Count','Threshold', 'F1', 'IoU',
        'TP', 'FP', 'FN', 'Precision', 'Recall'
    ],
) 
# Create inputs to function
image_sets = []
for i in range(len(predicted_masks)):
    name = str(predicted_masks[i]).split("/")[-1] 
    virtual_stain_mask = imread(predicted_masks[i])
    fluorescence_mask = imread(target_masks[i])  
    image_sets.append(
        {
            "Image": name,
            "Model": "Pix2PixHD",
            "Virtual_Stain_Mask": virtal_stain_mask,
            "Fluorescence_Mask": fluorescence_mask,
        }
    )
# Compute the segmentation scores
results, _, _ = \
    gen_segmentation_scores(
        image_sets, results, final_score_output=f"~/data/04_image_translation/pretrained_GAN/{opt.name}/results/")

results.head()

# Get Mean F1 results
mean_f1 = results["F1"].mean()
std_f1 = results["F1"].std()
print(f"Mean F1 Score: {np.round(mean_f1,2)}")

plt.hist(results["F1"], bins=10)
plt.xlabel("F1 Score")
plt.ylabel("Frequency")
plt.title(f"F1 Score: Mu {mean_f1}+-{std_f1}")
"""
<div class="alert alert-success">
    
## Checkpoint 3

Congratulations! You have trained several image translation models now!
Please document hyperparameters, snapshots of predictions on validation set, and loss curves for your models and add the final perforance in [this google doc](https://docs.google.com/document/d/1hZWSVRvt9KJEdYu7ib-vFBqAVQRYL8cWaP_vFznu7D8/edit#heading=h.n5u485pmzv2z). We"ll discuss our combined results as a group.
</div>
"""
# %% [markdown]
"""
# Part 4: BONUS: Sample different virtual staining solutions from the GAN using MC-Dropout and explore the uncertainty in the virtual stain predictions.
--------------------------------------------------
Steps:
- Load the pre-trained model.
- Generate multiple predictions for the same input image.
- Compute the pixel-wise variance across the predictions.
- Visualise the pixel-wise variance to explore the uncertainty in the virtual stain predictions.

"""
# Use the same model and dataloaders as before.
# Load the test data.
test_data_loader = CreateDataLoader(opt)
test_dataset = test_data_loader.load_data()
visualizer = Visualizer(opt)

# Load pre-trained model
opt.variational_inf_runs = 100 # Number of samples per phase input
opt.variation_inf_path = f"~/data/04_image_translation/pretrained_GAN/{opt.name}/results/samples/"  # Path to store the samples.
opt.dropout_variation_inf = True  # Use dropout during inference.
model = create_model(opt)
# Generate & save predictions in the variation_inf_path directory.
sampling(test_dataset, opt, model)


# %% <a [markdown]> </a>
