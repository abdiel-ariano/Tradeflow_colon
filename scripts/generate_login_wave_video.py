#!/usr/bin/env python3
"""Generate looped login wave WebM from the original multicolor PNG.

Development-only tool. The Django app serves the finished video asset.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'static' / 'images' / 'login-figma' / 'bg-wave.png'
OUTPUT = ROOT / 'static' / 'images' / 'login-figma' / 'login-wave.webm'
DIAG_DIR = Path('/opt/cursor/artifacts/wave-diagnosis')

WIDTH = 1920
HEIGHT = 1200
FPS = 30
DURATION_SECONDS = 12
TOTAL_FRAMES = FPS * DURATION_SECONDS
MINIMUM_VISIBLE_DIFFERENCE = 11.0
MAX_LOOP_SEAM_DIFFERENCE = 4.0
MAX_BYTES = 4 * 1024 * 1024


def load_original_on_white(path: Path) -> np.ndarray:
    """Composite RGBA source on white; return BGR uint8 for OpenCV."""
    rgba = np.array(Image.open(path).convert('RGBA'))
    if rgba.shape[1] != WIDTH or rgba.shape[0] != HEIGHT:
        rgba = np.array(
            Image.open(path).convert('RGBA').resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        )
    rgb = rgba[..., :3].astype(np.float32)
    alpha = rgba[..., 3:4].astype(np.float32) / 255.0
    white = np.full_like(rgb, 255.0)
    composited = np.clip(rgb * alpha + white * (1.0 - alpha), 0, 255).astype(np.uint8)
    return cv2.cvtColor(composited, cv2.COLOR_RGB2BGR)


def render_frame(original_bgr: np.ndarray, frame_index: int, grid_x: np.ndarray, grid_y: np.ndarray) -> np.ndarray:
    phase = 2.0 * math.pi * frame_index / TOTAL_FRAMES
    dx = (
        32.0 * np.sin((grid_y / 600.0) + phase)
        + 10.0 * np.sin((grid_y / 280.0) - phase)
    )
    dy = (
        22.0 * np.sin((grid_x / 720.0) - phase)
        + 8.0 * np.cos((grid_x / 340.0) + phase)
    )
    map_x = (grid_x + dx).astype(np.float32)
    map_y = (grid_y + dy).astype(np.float32)
    return cv2.remap(
        original_bgr,
        map_x,
        map_y,
        interpolation=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def encode_webm(frames: list[np.ndarray], output_path: Path) -> None:
    command = [
        'ffmpeg',
        '-y',
        '-f', 'rawvideo',
        '-pix_fmt', 'bgr24',
        '-s', f'{WIDTH}x{HEIGHT}',
        '-r', str(FPS),
        '-i', '-',
        '-an',
        '-c:v', 'libvpx-vp9',
        '-pix_fmt', 'yuv420p',
        '-crf', '32',
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


def wave_region_mask(rgb: np.ndarray) -> np.ndarray:
    return np.any(rgb < 245, axis=2) & (np.arange(rgb.shape[1])[None, :] >= rgb.shape[1] // 3)


def frame_difference(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    return float(np.mean(np.abs(frame_a.astype(np.float32) - frame_b.astype(np.float32))))


def wave_region_difference(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    rgb_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2RGB)
    rgb_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2RGB)
    mask = wave_region_mask(rgb_a)
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs(rgb_a[mask].astype(np.float32) - rgb_b[mask].astype(np.float32))))


def save_diagnostic_artifacts(frames: list[np.ndarray], output_path: Path) -> dict:
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    sample_seconds = [0, 3, 6, 9]
    sample_indices = [second * FPS for second in sample_seconds]
    saved_frames: dict[int, Path] = {}

    for second, index in zip(sample_seconds, sample_indices):
        frame_path = DIAG_DIR / f'frame-{second:02d}.png'
        rgb = cv2.cvtColor(frames[index], cv2.COLOR_BGR2RGB)
        Image.fromarray(rgb).save(frame_path)
        saved_frames[second] = frame_path

    frame0 = cv2.cvtColor(frames[0], cv2.COLOR_BGR2RGB)
    frame3 = cv2.cvtColor(frames[sample_indices[1]], cv2.COLOR_BGR2RGB)
    diff = np.abs(frame3.astype(np.int16) - frame0.astype(np.int16)).astype(np.uint8)
    diff_scaled = np.clip(diff * 8, 0, 255).astype(np.uint8)
    Image.fromarray(diff_scaled).save(DIAG_DIR / 'diff-map-0-vs-3.png')

    side = Image.new('RGB', (WIDTH * 4, HEIGHT))
    for i, second in enumerate(sample_seconds):
        side.paste(Image.open(saved_frames[second]), (i * WIDTH, 0))
    side.save(DIAG_DIR / 'frames-side-by-side.png')

    gif_path = DIAG_DIR / 'login-wave-6s.gif'
    subprocess.run(
        [
            'ffmpeg', '-y', '-i', str(output_path), '-t', '6',
            '-vf',
            'fps=15,scale=960:-1:flags=lanczos,split[s0][s1];'
            '[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer',
            str(gif_path),
        ],
        check=True,
        capture_output=True,
    )

    demo_path = Path('/opt/cursor/artifacts/screenshots/login-wave-video-demo-12s.webm')
    demo_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.resolve() != demo_path.resolve():
        demo_path.write_bytes(output_path.read_bytes())

    probe = subprocess.run(
        [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,avg_frame_rate,nb_frames,duration',
            '-show_entries', 'format=duration,size',
            '-of', 'json',
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    metadata = json.loads(probe.stdout)

    report = {
        'output': str(output_path),
        'size_bytes': output_path.stat().st_size,
        'metadata': metadata,
        'frame_differences_seconds': {
            '0_vs_3': frame_difference(frames[0], frames[sample_indices[1]]),
            '0_vs_6': frame_difference(frames[0], frames[sample_indices[2]]),
            '0_vs_9': frame_difference(frames[0], frames[sample_indices[3]]),
        },
        'wave_region_differences_seconds': {
            '0_vs_3': wave_region_difference(frames[0], frames[sample_indices[1]]),
            '0_vs_6': wave_region_difference(frames[0], frames[sample_indices[2]]),
        },
        'loop_seam_difference': frame_difference(frames[0], frames[-1]),
        'validation': {
            'minimum_visible_difference': MINIMUM_VISIBLE_DIFFERENCE,
            'frame_0_vs_3_passes': wave_region_difference(frames[0], frames[sample_indices[1]]) > MINIMUM_VISIBLE_DIFFERENCE,
            'loop_seam_passes': frame_difference(frames[0], frames[-1]) < MAX_LOOP_SEAM_DIFFERENCE,
        },
        'frames': {str(k): str(v) for k, v in saved_frames.items()},
        'diff_map': str(DIAG_DIR / 'diff-map-0-vs-3.png'),
        'side_by_side': str(DIAG_DIR / 'frames-side-by-side.png'),
        'gif_6s': str(gif_path),
        'demo_webm': str(demo_path),
    }
    (DIAG_DIR / 'generation-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def validate_frames(frames: list[np.ndarray]) -> None:
    frame_at_0 = frames[0]
    frame_at_3s = frames[3 * FPS]
    difference = frame_difference(frame_at_0, frame_at_3s)
    wave_difference = wave_region_difference(frame_at_0, frame_at_3s)
    loop_difference = frame_difference(frame_at_0, frames[-1])

    if wave_difference <= MINIMUM_VISIBLE_DIFFERENCE:
        raise AssertionError(
            f'Wave motion too subtle: 0s vs 3s wave diff {wave_difference:.4f} '
            f'(threshold {MINIMUM_VISIBLE_DIFFERENCE})'
        )
    if loop_difference >= MAX_LOOP_SEAM_DIFFERENCE:
        raise AssertionError(
            f'Loop seam too large: {loop_difference:.4f} (max {MAX_LOOP_SEAM_DIFFERENCE})'
        )
    print(f'Validation OK: full diff 0s vs 3s = {difference:.4f}, wave diff = {wave_difference:.4f}, loop seam = {loop_difference:.4f}')


def main() -> int:
    if not SOURCE.exists():
        print(f'Missing source image: {SOURCE}', file=sys.stderr)
        return 1

    original_bgr = load_original_on_white(SOURCE)
    grid_y, grid_x = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)

    frames = [
        render_frame(original_bgr, frame_index, grid_x, grid_y)
        for frame_index in range(TOTAL_FRAMES)
    ]

    validate_frames(frames)
    encode_webm(frames, OUTPUT)

    size = OUTPUT.stat().st_size
    if size > MAX_BYTES:
        raise RuntimeError(f'Output exceeds 4 MB: {size / 1024 / 1024:.2f} MB')

    report = save_diagnostic_artifacts(frames, OUTPUT)
    print(json.dumps(report, indent=2))
    print(f'Wrote {OUTPUT} ({size / 1024 / 1024:.2f} MB, {TOTAL_FRAMES} frames)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
