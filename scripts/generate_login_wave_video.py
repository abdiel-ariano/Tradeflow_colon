#!/usr/bin/env python3
"""Generate looped login wave WebM from the original multicolor PNG.

Development-only tool. The Django app serves the finished video asset.
"""
from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'static' / 'images' / 'login-figma' / 'bg-wave.png'
OUTPUT = ROOT / 'static' / 'images' / 'login-figma' / 'login-wave.webm'

WIDTH = 1920
HEIGHT = 1200
FPS = 30
DURATION_SECONDS = 12
TOTAL_FRAMES = FPS * DURATION_SECONDS
MAX_BYTES = 4 * 1024 * 1024


def bilinear_remap(image: np.ndarray, map_x: np.ndarray, map_y: np.ndarray) -> np.ndarray:
    height, width, channels = image.shape
    x = np.clip(map_x, 0.0, width - 1.001)
    y = np.clip(map_y, 0.0, height - 1.001)

    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.minimum(x0 + 1, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)

    wx = (x - x0)[..., None]
    wy = (y - y0)[..., None]

    top = (1.0 - wx) * image[y0, x0] + wx * image[y0, x1]
    bottom = (1.0 - wx) * image[y1, x0] + wx * image[y1, x1]
    return np.clip((1.0 - wy) * top + wy * bottom, 0, 255).astype(np.uint8)


def displacement_fields(frame: int, y_grid: np.ndarray, x_grid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    phase = 2.0 * math.pi * frame / TOTAL_FRAMES
    dx = 4.0 * np.sin(y_grid / 180.0 + phase) + 2.0 * np.sin(y_grid / 90.0 - phase)
    dy = 3.0 * np.sin(x_grid / 220.0 - phase) + 2.0 * np.cos(x_grid / 140.0 + phase)
    return dx, dy


def render_frame(source: np.ndarray, frame: int, y_grid: np.ndarray, x_grid: np.ndarray) -> np.ndarray:
    dx, dy = displacement_fields(frame, y_grid, x_grid)
    return bilinear_remap(source, x_grid + dx, y_grid + dy)


def encode_webm(frames: list[np.ndarray], output_path: Path) -> None:
    command = [
        'ffmpeg',
        '-y',
        '-f', 'rawvideo',
        '-pix_fmt', 'rgba',
        '-s', f'{WIDTH}x{HEIGHT}',
        '-r', str(FPS),
        '-i', '-',
        '-an',
        '-c:v', 'libvpx-vp9',
        '-pix_fmt', 'yuv420p',
        '-crf', '38',
        '-b:v', '0',
        '-row-mt', '1',
        '-cpu-used', '4',
        '-deadline', 'good',
        str(output_path),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdin is not None
    for frame in frames:
        process.stdin.write(frame.tobytes())
    process.stdin.close()
    stderr = process.stderr.read().decode('utf-8', errors='replace') if process.stderr else ''
    code = process.wait()
    if code != 0:
        raise RuntimeError(f'ffmpeg failed ({code}): {stderr[-2000:]}')


def main() -> int:
    if not SOURCE.exists():
        print(f'Missing source image: {SOURCE}', file=sys.stderr)
        return 1

    source_rgba = np.array(Image.open(SOURCE).convert('RGBA'))
    if source_rgba.shape[1] != WIDTH or source_rgba.shape[0] != HEIGHT:
        source_rgba = np.array(
            Image.open(SOURCE).convert('RGBA').resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        )

    y_grid, x_grid = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
    frames = [render_frame(source_rgba, frame, y_grid, x_grid) for frame in range(TOTAL_FRAMES)]

    loop_delta = np.mean(np.abs(frames[0].astype(np.int16) - frames[-1].astype(np.int16)))
    print(f'Loop seam mean delta: {loop_delta:.4f}')

    encode_webm(frames, OUTPUT)
    size = OUTPUT.stat().st_size
    print(f'Wrote {OUTPUT} ({size / 1024 / 1024:.2f} MB)')

    if size > MAX_BYTES:
        print('Warning: output exceeds 4 MB target; consider raising CRF slightly.', file=sys.stderr)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
