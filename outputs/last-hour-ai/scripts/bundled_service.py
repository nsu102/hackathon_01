"""Entry point for the standalone macOS service. No dependency on Homebrew."""
import argparse
import json
import multiprocessing
import os
import sys


def main():
    multiprocessing.freeze_support()
    if getattr(sys, 'frozen', False):
        import certifi
        os.environ.setdefault('SSL_CERT_FILE', certifi.where())
    from last_hour.config import load_env, DEFAULT_MODEL
    load_env()
    if sys.argv[1:] == ['--startup-config']:
        print(json.dumps(dict(token=os.getenv('LAST_HOUR_TOKEN', ''),
                              gaze_model=os.getenv('STUDY_GAZE_MODEL', 'unigaze_l16_joint'),
                              key_configured=bool(os.getenv('OPENROUTER_API_KEY', '').strip()),
                              model=os.getenv('STUDY_MODEL_ID', '').strip() or os.getenv('OPENROUTER_MODEL', DEFAULT_MODEL))))
        return 0
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    serve = sub.add_parser('serve');serve.add_argument('--port', type=int, required=True)
    neural = sub.add_parser('neural');neural.add_argument('--model', default='unigaze_l16_joint')
    sub.add_parser('self-check')
    material=sub.add_parser('extract-material');material.add_argument('path')
    args = parser.parse_args()
    if args.command == 'serve':
        from last_hour.api import serve as serve_api
        serve_api(os.getenv('LAST_HOUR_DATA', './data'), args.port)
    elif args.command == 'neural':
        from last_hour.neural_gaze import worker
        return worker(args.model)
    elif args.command=='extract-material':
        from last_hour.materials import main as material_main
        sys.argv=[sys.argv[0],args.path]
        return material_main()
    else:
        import torch
        import timm
        import cv2
        import numpy
        import safetensors.torch
        from last_hour.study import StudyService
        print(json.dumps(dict(ok=True, frozen=bool(getattr(sys, 'frozen', False)),
                              python=sys.version.split()[0], mps=torch.backends.mps.is_available(),
                              torch=torch.__version__, timm=timm.__version__, opencv=cv2.__version__)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
