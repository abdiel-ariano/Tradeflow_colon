#!/usr/bin/env python3
"""Generate looped login wave WebM from the original multicolor PNG.

Development-only tool. The Django app serves the finished video asset.

Displacement model: slow ribbon-aligned band breathing (Stripe-like swell),
not whole-image translation or high-frequency ripples.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'static' / 'images' / 'login-figma' / 'bg-wave.png'
DEFAULT_OUTPUT = ROOT / 'static' / 'images' / 'login-figma' / 'login-wave.webm'
DIAG_DIR = Path('/opt/cursor/artifacts/wave-diagnosis')

WIDTH = 1920
HEIGHT = 1200
FPS = 30
DURATION_SECONDS = 12
TOTAL_FRAMES = FPS * DURATION_SECONDS
MINIMUM_VISIBLE_DIFFERENCE = 10.0
MINIMUM_MID_CYCLE_DIFFERENCE = 7.0
MAX_LOOP_SEAM_DIFFERENCE = 4.0
MAX_FRAME_TO_FRAME_SPIKE = 2.1
MAX_BYTES = 4 * 1024 * 1024

# Ribbon orientation for TradeFlow wave (diagonal top-left → bottom-right)
ALONG_X = 0.72
ALONG_Y = 0.68
CROSS_X = -0.68
CROSS_Y = 0.72
EDGE_FADE_PX = 56.0
EDGE_MIN_STRENGTH = 0.35


def load_original_on_white(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Composite RGBA source on white; return BGR uint8 and alpha for edge fade."""
    rgba = np.array(Image.open(path).convert('RGBA'))
    if rgba.shape[1] != WIDTH or rgba.shape[0] != HEIGHT:
        rgba = np.array(
            Image.open(path).convert('RGBA').resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        )
    rgb = rgba[..., :3].astype(np.float32)
    alpha = rgba[..., 3].astype(np.float32) / 255.0
    white = np.full_like(rgb, 255.0)
    composited = np.clip(rgb * alpha[..., None] + white * (1.0 - alpha[..., None]), 0, 255).astype(np.uint8)
    return cv2.cvtColor(composited, cv2.COLOR_RGB2BGR), alpha


def build_edge_attenuation(alpha: np.ndarray) -> np.ndarray:
    """Keep the outer silhouette stable; deform more in the ribbon interior."""
    mask = (alpha > 0.08).astype(np.uint8)
    distance = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    return np.clip(distance / EDGE_FADE_PX, EDGE_MIN_STRENGTH, 1.0).astype(np.float32)


def displacement_fields(
    frame_index: int,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    attenuation: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Ribbon-aligned swell: bands change width/curvature, not global translation."""
    phase = 2.0 * math.pi * frame_index / TOTAL_FRAMES
    envelope = 0.5 * (1.0 - math.cos(phase))

    along = ALONG_X * grid_x + ALONG_Y * grid_y
    cross = CROSS_X * grid_x + CROSS_Y * grid_y

    # Primary: broad cross-ribbon breathing (band width / curvature)
    d_cross = (
        50.0 * envelope * np.sin(cross / 760.0 + 0.35 * phase)
        + 14.0 * envelope * np.sin(cross / 520.0 - phase + along / 2800.0)
        + 11.0 * envelope * np.sin(cross / 1040.0 + 0.12 * phase)
    )
    # Secondary: gentle along-ribbon internal shear (very low amplitude)
    d_along = (
        6.0 * envelope * np.sin(along / 1600.0 - 0.25 * phase)
        + 3.5 * envelope * np.cos(along / 1180.0 + 0.5 * phase)
    )

    dx = CROSS_X * d_cross + ALONG_X * d_along
    dy = CROSS_Y * d_cross + ALONG_Y * d_along

    # Ultra-long subtle undulation (no lateral pan)
    dx += 3.0 * envelope * np.sin(grid_y / 1600.0 + 0.2 * phase) * np.cos(grid_x / 2200.0)
    dy += 2.5 * envelope * np.cos(grid_x / 1700.0 - 0.2 * phase) * np.sin(grid_y / 2000.0)

    return dx * attenuation, dy * attenuation


def render_frame(
    original_bgr: np.ndarray,
    frame_index: int,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    attenuation: np.ndarray,
) -> np.ndarray:
    dx, dy = displacement_fields(frame_index, grid_x, grid_y, attenuation)
    map_x = (grid_x + dx).astype(np.float32)
    map_y = (grid_y + dy).astype(np.float32)
    return cv2.remap(
        original_bgr,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
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
    if process.wait() != 0:
        raise RuntimeError(f'ffmpeg failed: {stderr[-2000:]}')


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


def validate_frames(frames: list[np.ndarray]) -> dict:
    frame_at_0 = frames[0]
    frame_at_3s = frames[3 * FPS]
    frame_at_6s = frames[6 * FPS]
    frame_at_9s = frames[9 * FPS]
    wave_peak_difference = wave_region_difference(frame_at_0, frame_at_6s)
    wave_mid_difference = wave_region_difference(frame_at_3s, frame_at_9s)
    loop_difference = frame_difference(frame_at_0, frames[-1])

    frame_diffs = [
        frame_difference(frames[i - 1], frames[i])
        for i in range(1, len(frames))
    ]
    mean_step = float(np.mean(frame_diffs))
    max_step = float(np.max(frame_diffs))
    spike_ratio = max_step / max(mean_step, 1e-6)

    if wave_peak_difference <= MINIMUM_VISIBLE_DIFFERENCE:
        raise AssertionError(
            f'Wave motion too subtle: 0s vs 6s wave diff {wave_peak_difference:.4f} '
            f'(threshold {MINIMUM_VISIBLE_DIFFERENCE})'
        )
    if wave_mid_difference <= MINIMUM_MID_CYCLE_DIFFERENCE:
        raise AssertionError(
            f'Mid-cycle motion too subtle: 3s vs 9s wave diff {wave_mid_difference:.4f} '
            f'(threshold {MINIMUM_MID_CYCLE_DIFFERENCE})'
        )
    if loop_difference >= MAX_LOOP_SEAM_DIFFERENCE:
        raise AssertionError(
            f'Loop seam too large: {loop_difference:.4f} (max {MAX_LOOP_SEAM_DIFFERENCE})'
        )
    if spike_ratio > MAX_FRAME_TO_FRAME_SPIKE:
        raise AssertionError(
            f'Frame-to-frame spike too high: ratio {spike_ratio:.2f} (max {MAX_FRAME_TO_FRAME_SPIKE})'
        )

    return {
        'wave_diff_0_vs_3': wave_region_difference(frame_at_0, frame_at_3s),
        'wave_diff_0_vs_6': wave_peak_difference,
        'wave_diff_3_vs_9': wave_mid_difference,
        'loop_seam': loop_difference,
        'mean_frame_step': mean_step,
        'max_frame_step': max_step,
        'spike_ratio': spike_ratio,
    }


def save_diagnostic_artifacts(frames: list[np.ndarray], output_path: Path, metrics: dict) -> dict:
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    sample_seconds = [0, 3, 6, 9, 12]
    saved_frames: dict[int, Path] = {}

    for second in sample_seconds:
        index = 0 if second == 12 else second * FPS
        frame_path = DIAG_DIR / f'stripe-ref-frame-{second:02d}.png'
        rgb = cv2.cvtColor(frames[index], cv2.COLOR_BGR2RGB)
        Image.fromarray(rgb).save(frame_path)
        saved_frames[second] = frame_path

    side = Image.new('RGB', (WIDTH * len(sample_seconds), HEIGHT))
    for i, second in enumerate(sample_seconds):
        side.paste(Image.open(saved_frames[second]), (i * WIDTH, 0))
    side.save(DIAG_DIR / 'stripe-ref-frames-side-by-side.png')

    gif_path = DIAG_DIR / 'stripe-ref-preview-6s.gif'
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

    report = {
        'output': str(output_path),
        'size_bytes': output_path.stat().st_size,
        'metrics': metrics,
        'frames': {str(k): str(v) for k, v in saved_frames.items()},
        'side_by_side': str(DIAG_DIR / 'stripe-ref-frames-side-by-side.png'),
        'gif_6s': str(gif_path),
    }
    (DIAG_DIR / 'stripe-ref-generation-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate login wave WebM')
    parser.add_argument(
        '--output',
        type=Path,
        default=DEFAULT_OUTPUT,
        help='Output WebM path (default: production asset)',
    )
    args = parser.parse_args()

    if not SOURCE.exists():
        print(f'Missing source image: {SOURCE}', file=sys.stderr)
        return 1

    original_bgr, alpha = load_original_on_white(SOURCE)
    attenuation = build_edge_attenuation(alpha)
    grid_y, grid_x = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)

    frames = [
        render_frame(original_bgr, frame_index, grid_x, grid_y, attenuation)
        for frame_index in range(TOTAL_FRAMES)
    ]

    metrics = validate_frames(frames)
    print(
        'Validation OK: '
        f'wave 0↔6s={metrics["wave_diff_0_vs_6"]:.2f}, '
        f'3↔9s={metrics["wave_diff_3_vs_9"]:.2f}, '
        f'loop={metrics["loop_seam"]:.2f}, '
        f'spike={metrics["spike_ratio"]:.2f}'
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    encode_webm(frames, args.output)

    if args.output.stat().st_size > MAX_BYTES:
        raise RuntimeError(f'Output exceeds 4 MB: {args.output.stat().st_size / 1024 / 1024:.2f} MB')

    report = save_diagnostic_artifacts(frames, args.output, metrics)
    print(json.dumps(report, indent=2))
    print(f'Wrote {args.output} ({args.output.stat().st_size / 1024 / 1024:.2f} MB)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
