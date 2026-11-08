"""Local-only UniGaze worker. JSON lines over owned child stdio; no media logs/files.

Official model: ut-vision/UniGaze (WACV 2026). Checkpoint license and attribution
are included in neural_assets. Precise screen calibration is separate; coarse direction monitoring does not require it.
"""
from __future__ import annotations
import argparse
import base64
import json
import math
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    'unigaze_l16_joint': ('vit_large_patch16_224', 1024),
    'unigaze_b16_joint': ('vit_base_patch16_224', 768),
}
# UniGaze's distributed six-point face template: eye corners and nose wings (mm).
FACE_POINTS = [
    [-46.5094986, -38.3270950, 36.4160042], [-17.7607212, -32.5851974, 29.0761566],
    [18.0439110, -30.9568233, 29.0629673], [44.7375870, -34.1078720, 36.7324371],
    [-10.6116648, 12.9583492, 21.6227646], [11.2896299, 13.8642445, 21.8379002],
]


def validate_request(data):
    if not isinstance(data, dict) or set(data) != {'image', 'points', 'bbox'}:
        raise ValueError('Invalid local neural input')
    if not isinstance(data['image'], str) or not 20 <= len(data['image']) <= 2_000_000:
        raise ValueError('Invalid camera image')
    points, box = data['points'], data['bbox']
    if (not isinstance(points, list) or len(points) != 6
        or any(not isinstance(p, list) or len(p) != 2 for p in points)
        or not isinstance(box, list) or len(box) != 4
        or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 8192 for row in [*points, box] for v in row)):
        raise ValueError('Invalid face geometry')
    return data


def normalize_face(image, points, bbox):
    """ETRA-2018/UniGaze normalization: 224 square, focal 960, distance 600mm.

    Six observed points are paired with the official eye/nose template. As in
    the official video demo, use a dummy intrinsic matrix; personal screen
    calibration accounts for device geometry. No uncalibrated screen projection.
    """
    import cv2
    import numpy as np
    height, width = image.shape[:2]
    points = np.asarray(points, dtype=np.float64)
    left, top, right, bottom = bbox
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError('Face box outside frame')
    if right-left < 60 or bottom-top < 60:
        raise ValueError('Face too small')
    # Match the official webcam/video example's 2x face-region preparation.
    cx, cy = (left+right)/2, (top+bottom)/2
    x0, y0 = max(0, int(cx-(right-left))), max(0, int(cy-(bottom-top)))
    x1, y1 = min(width, int(cx+(right-left))), min(height, int(cy+(bottom-top)))
    crop = image[y0:y1, x0:x1]
    obs = points - np.array([x0, y0])
    h, w = crop.shape[:2]
    camera = np.array([[w*4., 0., w/2], [0., w*4., h/2], [0., 0., 1.]])
    template = np.asarray(FACE_POINTS, dtype=np.float64)
    ok, rvec, tvec = cv2.solvePnP(template, obs, camera, np.zeros(5), flags=cv2.SOLVEPNP_EPNP)
    if not ok:
        raise ValueError('Head pose unavailable')
    ok, rvec, tvec = cv2.solvePnP(template, obs, camera, np.zeros(5), rvec, tvec, True)
    rotation = cv2.Rodrigues(rvec)[0]
    projected, _ = cv2.projectPoints(template, rvec, tvec, camera, np.zeros(5))
    residual = float(np.median(np.linalg.norm(projected.reshape(6, 2)-obs, axis=1)))
    if not ok or not np.isfinite(tvec).all() or tvec[2, 0] <= 0 or residual > max(12, (right-left)*.08):
        raise ValueError('Head pose quality insufficient')
    camera_points = (rotation @ template.T + tvec).T
    center = (camera_points[:4].mean(axis=0) + camera_points[4:].mean(axis=0))/2
    distance = np.linalg.norm(center)
    forward = center/distance
    down = np.cross(forward, rotation[:, 0]); down /= np.linalg.norm(down)
    right_axis = np.cross(down, forward); right_axis /= np.linalg.norm(right_axis)
    normalizing = np.stack([right_axis, down, forward])
    normalized_camera = np.array([[960., 0., 112.], [0., 960., 112.], [0., 0., 1.]])
    warp = normalized_camera @ np.diag([1., 1., 600./distance]) @ normalizing @ np.linalg.inv(camera)
    patch = cv2.warpPerspective(crop, warp, (224, 224), flags=cv2.INTER_LINEAR)
    if not np.isfinite(warp).all():
        raise ValueError('Invalid normalization')
    return patch, normalizing, rotation, residual


class UniGaze:
    def __init__(self, name='unigaze_l16_joint'):
        import torch
        import timm
        from torch import nn
        from functools import partial
        from safetensors.torch import load_file
        if name not in MODELS:
            raise ValueError('Unsupported neural gaze model')
        path = Path(os.getenv('STUDY_GAZE_WEIGHTS', str(ROOT/'data/models/unigaze')))/f'{name}.safetensors'
        if not path.is_file():
            raise ValueError('신경망 모델 설치가 필요해요. 신경망 시선 설치.command를 실행해주세요.')
        backbone, dim = MODELS[name]
        class Network(nn.Module):
            def __init__(self):
                super().__init__()
                self.vit = timm.create_model(backbone, pretrained=False, num_classes=1000,
                    norm_layer=partial(nn.LayerNorm, eps=1e-6))
                self.gaze_fc = nn.Linear(dim, 2)
            def forward(self, x):
                return self.gaze_fc(self.vit.forward_features(x)[:, 0])
        self.torch = torch
        self.device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        self.dtype = torch.float16 if self.device == 'mps' else torch.float32
        if self.device == 'cpu':
            torch.set_num_threads(4)
        with torch.device('meta'):
            self.net = Network()
        state = load_file(str(path))
        self.net.load_state_dict(state, strict=True, assign=True)
        self.net = self.net.eval().to(device=self.device, dtype=self.dtype)
        del state
        self.mean = torch.tensor([.485, .456, .406], device=self.device, dtype=self.dtype).reshape(1, 3, 1, 1)
        self.std = torch.tensor([.229, .224, .225], device=self.device, dtype=self.dtype).reshape(1, 3, 1, 1)
        with torch.inference_mode():
            image = torch.zeros(1, 3, 224, 224, device=self.device, dtype=self.dtype)
            for _ in range(2):
                self.net(image)
        if self.device == 'mps':
            torch.mps.synchronize()
        self.info = {'model': name, 'device': self.device,
                     'precision': 'float16' if self.dtype == torch.float16 else 'float32',
                     'source': 'https://github.com/ut-vision/UniGaze', 'screen_calibration_required': True}

    def predict(self, data):
        import cv2
        import numpy as np
        torch = self.torch
        data = validate_request(data)
        raw = base64.b64decode(data['image'], validate=True)
        if len(raw) > 1_500_000:
            raise ValueError('Camera image too large')
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or max(image.shape[:2]) > 1920:
            raise ValueError('Invalid camera image')
        started = time.monotonic()
        patch, normalizing, rotation, residual = normalize_face(image, data['points'], data['bbox'])
        rgb = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
        value = torch.from_numpy(rgb.transpose(2, 0, 1).copy()).unsqueeze(0).to(device=self.device, dtype=self.dtype)/255.
        with torch.inference_mode():
            prediction = self.net((value-self.mean)/self.std)[0].float().cpu().numpy()
        if not np.isfinite(prediction).all():
            raise ValueError('Non-finite neural prediction')
        pitch, yaw = map(float, prediction)
        # UniGaze convention: +Z target-to-eye vector, then inverse-normalize.
        direction = normalizing.T @ np.array([math.cos(pitch)*math.sin(yaw), math.sin(pitch), math.cos(pitch)*math.cos(yaw)])
        if direction[2] < .2:
            raise ValueError('Gaze direction outside reliable projection domain')
        sx, sy = float(direction[0]/direction[2]), float(direction[1]/direction[2])
        head_yaw = float(math.atan2(rotation[0, 2], rotation[2, 2]))
        head_pitch = float(math.asin(float(np.clip(rotation[1, 2], -1, 1))))
        return {'features': [sx, sy, sx*sy, head_yaw, head_pitch],
                'inference_ms': round((time.monotonic()-started)*1000, 1), 'pose_residual_px': round(residual, 2)}


def worker(name):
    def reply(value):
        print(json.dumps(value, allow_nan=False), flush=True)
    try:
        model = UniGaze(name)
        reply({'ready': True, **model.info})
    except Exception:
        reply({'ready': False, 'error': 'UniGaze 모델을 준비하지 못했어요. 신경망 시선 설치.command와 모델 파일을 확인해주세요.'})
        return 1
    for line in sys.stdin:
        try:
            if len(line) > 2_100_000:
                raise ValueError('Input limit exceeded')
            data = json.loads(line)
            result = model.predict(data)
            reply({'ok': True, **result})
        except Exception:
            # No image/landmark/exception repr in logs or saved output.
            reply({'ok': False, 'error': '시선 신경망 입력 품질 확인 필요'})
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--model', choices=list(MODELS), default='unigaze_l16_joint')
    args = parser.parse_args()
    raise SystemExit(worker(args.model) if args.worker else 0)
