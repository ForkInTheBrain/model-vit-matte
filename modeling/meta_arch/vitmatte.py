import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision
import os

from detectron2.structures import ImageList

class ViTMatte(nn.Module):
    def __init__(self,
                 *,
                 backbone,
                 criterion,
                 pixel_mean,
                 pixel_std,
                 input_format,
                 size_divisibility,
                 decoder,
                 ):
        super(ViTMatte, self).__init__()
        self.backbone = backbone
        self.criterion = criterion
        self.input_format = input_format
        self.size_divisibility = size_divisibility
        self.decoder = decoder
        self.register_buffer(
            "pixel_mean", torch.tensor(pixel_mean).view(-1, 1, 1), False
        )
        self.register_buffer("pixel_std", torch.tensor(pixel_std).view(-1, 1, 1), False)
        assert (
            self.pixel_mean.shape == self.pixel_std.shape
        ), f"{self.pixel_mean} and {self.pixel_std} have different shapes!"
    
    @property
    def device(self):
        return self.pixel_mean.device

    def forward(self, image, trimap):
        # images, trimap, targets, H, W = self.preprocess_inputs(batched_inputs)
        images = torch.concat([image, trimap], dim=1)
        features = self.backbone(images)
        outputs = self.decoder(features, images)  

        
        # outputs['phas'] = outputs['phas'][:,:,:H,:W]
        return outputs



    def preprocess_inputs(self, batched_inputs):
        """
        Normalize, pad and batch the input images.
        """
        images = batched_inputs["image"].to(self.device)
        trimap = batched_inputs['trimap'].to(self.device)
        images = (images - self.pixel_mean) / self.pixel_std

        if 'fg' in batched_inputs.keys():
            trimap[trimap < 85] = 0
            trimap[trimap >= 170] = 1
            trimap[trimap >= 85] = 0.5

        # images = torch.cat((images, trimap), dim=1)
        
        B, C, H, W = images.shape
        if images.shape[-1]%32!=0 or images.shape[-2]%32!=0:
            new_H = (32-images.shape[-2]%32) + H
            new_W = (32-images.shape[-1]%32) + W
            new_images = torch.zeros((images.shape[0], images.shape[1], new_H, new_W)).to(self.device)
            new_images[:,:,:H,:W] = images[:,:,:,:]

            new_trimap = torch.zeros((trimap.shape[0], trimap.shape[1], new_H, new_W)).to(self.device)
            new_trimap[:,:,:H,:W] = trimap[:,:,:,:]
            del trimap
            del images
            images = new_images
            trimap = new_trimap

        if "alpha" in batched_inputs:
            phas = batched_inputs["alpha"].to(self.device)
        else:
            phas = None

        return images, trimap, dict(phas=phas), H, W