#!/usr/bin/env python3
"""MVP LOCAL do Editor Natinha. NÃO é o editor de produção nem seleciona cortes por IA."""
import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    if p.returncode:
        raise RuntimeError("Falha FFmpeg/FFprobe: " + p.stderr[-1800:])
    return p.stdout

def media_info(path):
    data = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("Vídeo não encontrado no arquivo")
    dur = float(data.get("format", {}).get("duration") or video.get("duration") or 0)
    if not math.isfinite(dur) or dur <= 0:
        raise ValueError("Duração inválida")
    return {"duration": dur, "width": int(video.get("width", 0)),
            "height": int(video.get("height", 0)),
            "audio": any(s.get("codec_type") == "audio" for s in data.get("streams", []))}

def auto_segments(total, count=3, target=70):
    """Divide temporalmente, sem selecionar ideias por IA."""
    if count < 1 or total <= 0:
        raise ValueError("Duração e quantidade devem ser positivas")
    span = total / count
    length = min(float(target), span)
    return [(round(i*span + (span-length)/2, 3), round(length, 3)) for i in range(count)]

def ffmpeg_export(src, dest, filt, start=None, duration=None, has_audio=True):
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(src)]
    if start is not None:
        cmd += ["-ss", str(start)]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd += ["-map", "0:v:0"]
    if has_audio:
        cmd += ["-map", "0:a:0?"]
    cmd += ["-vf", filt, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
    if has_audio:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", str(dest)]
    run(cmd)
    if not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError("Arquivo de saída não gerado: " + dest.name)

def even_dimension(value):
    n = int(value)
    if n < 64 or n % 2:
        raise argparse.ArgumentTypeError("Dimensão deve ser par e >= 64")
    return n

def main(argv=None):
    parser = argparse.ArgumentParser(description="Editor local demonstrativo: master e cortes verticais, sem IA.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="saidas")
    parser.add_argument("--cuts", type=int, default=3)
    parser.add_argument("--target-seconds", type=int, default=70)
    parser.add_argument("--vertical-width", type=even_dimension, default=720)
    parser.add_argument("--vertical-height", type=even_dimension, default=1280)
    parser.add_argument("--master-width", type=even_dimension, default=1280)
    parser.add_argument("--master-height", type=even_dimension, default=720)
    args = parser.parse_args(argv)
    source = Path(args.input).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in {".mp4", ".mov", ".mkv", ".m4v"}:
        parser.error("Entrada deve ser MP4/MOV/MKV/M4V")
    if not 1 <= args.cuts <= 12 or not 1 <= args.target_seconds <= 600:
        parser.error("Limites: --cuts 1..12; --target-seconds 1..600")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        parser.error("FFmpeg e FFprobe precisam estar no PATH")
    info = media_info(source)
    root = Path(args.output).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    target_dir = Path(tempfile.mkdtemp(prefix="natinha_comunidade_", dir=root))
    w, h = args.master_width, args.master_height
    master_filter = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    master = target_dir / "master_horizontal.mp4"
    ffmpeg_export(source, master, master_filter, has_audio=info["audio"])
    w, h = args.vertical_width, args.vertical_height
    filt = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    cuts = auto_segments(info["duration"], args.cuts, args.target_seconds)
    files = []
    for i, (start, dur) in enumerate(cuts, 1):
        dest = target_dir / f"corte_{i:02d}_vertical.mp4"
        ffmpeg_export(source, dest, filt, start=start, duration=dur, has_audio=info["audio"])
        check = media_info(dest)
        if (check["width"], check["height"]) != (w, h) or abs(check["duration"]-dur) > 1.1:
            raise RuntimeError("QA de resolução/duração falhou para " + dest.name)
        files.append({"file": dest.name, "source_start": start, "duration": check["duration"]})
    manifest = {"edition": "MVP local independente, SEM IA", "source_file": source.name,
                "master": master.name, "input_duration_seconds": info["duration"],
                "cuts": files, "limitations": ["sem IA", "sem legendas", "sem Remotion", "sem Google Drive"]}
    (target_dir / "relatorio.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Arquivos gerados em:", target_dir)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print("ERRO:", exc, file=sys.stderr)
        sys.exit(1)
