UniGaze (WACV 2026), Jiawei Qin, Xucong Zhang, Yusuke Sugano.
Official implementation: https://github.com/ut-vision/UniGaze
Reviewed commit: 9c240fbe33f3d6146970a77b7c8fa06a7e60019e
Weights: https://huggingface.co/UniGaze/UniGaze-models
ModelGo Attribution-NonCommercial-ResponsibleAI 2.0: see UniGaze-LICENSE.txt.
This integration is a noncommercial research/development prototype; commercial
redistribution of these weights requires rights from the model authors.

The model architecture/strict checkpoint names match the official MAE_Gaze and
VisionTransformer token-pooling path. Inference uses timm's equivalent ViT.
Normalization follows the official video demo and Zhang et al., Revisiting Data
Normalization for Appearance-Based Gaze Estimation (ETRA 2018). The 6-point face
coordinates are the corresponding subset of the official distributed face model.
No training videos, user images or learned personal calibration are stored.
