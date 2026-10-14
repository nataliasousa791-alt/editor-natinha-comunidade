#!/usr/bin/env python3
"""Verificação heurística local: imprime somente categoria e localização, nunca senhas."""
import argparse
import os
import re
import sys
from pathlib import Path

SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "jobs", "logs", "saidas", "outputs", "cache", "entrada", "prontos", "publicados"}
SENSITIVE = {"config.json", "credentials.json", "token.json", "client_secret.json", "rclone.conf", "secrets.json", "cookies.json", "oauth.json"}
MEDIA = {".mp4", ".mov", ".mkv", ".avi", ".wav", ".mp3", ".aac", ".jpg", ".jpeg", ".png", ".webp", ".srt", ".ass"}
CODE = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".json", ".yaml", ".yml", ".md", ".txt", ".toml", ".ini", ".cfg", ".env", ".ps1", ".sh", ".bat", ".css"}
RULES = {
    "possível token": re.compile(r"(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|AIza)[A-Za-z0-9_-]{16,}"),
    "chave privada": re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    "possível credencial": re.compile(r"""(?ix)\b(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret)\b\s*[:=]\s*["']?(?!placeholder|example|exemplo|change_me|your_|none|null|os\.environ|os\.getenv)[A-Za-z0-9_+/-]{12,}"""),
    "caminho Windows pessoal": re.compile(r"(?i)C:\\Users\\[^\\\s]+\\")
}

def scan(root):
    root = Path(root)
    findings = []
    stats = {"files_seen": 0, "code_files_checked": 0}
    for here, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP and not (Path(here)/d).is_symlink())
        for name in sorted(files):
            path = Path(here) / name
            if path.is_symlink():
                continue
            rel = path.relative_to(root).as_posix()
            stats["files_seen"] += 1
            n = name.lower()
            if (n.startswith(".env") and n != ".env.example") or n in SENSITIVE or path.suffix.lower() in {".key", ".pem", ".p12", ".pfx", ".sqlite", ".db"}:
                findings.append((rel, 0, "arquivo confidencial"))
                continue
            if path.suffix.lower() in MEDIA:
                findings.append((rel, 0, "mídia: revisar antes de publicar"))
                continue
            if path.suffix.lower() not in CODE:
                continue
            if path.stat().st_size > 1_000_000:
                findings.append((rel, 0, "arquivo grande não analisado"))
                continue
            stats["code_files_checked"] += 1
            for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                for label, pattern in RULES.items():
                    if pattern.search(line):
                        findings.append((rel, i, label))
    return findings, stats

def main():
    parser = argparse.ArgumentParser(description="Verificador local de riscos antes de publicar")
    parser.add_argument("pasta", type=Path)
    root = parser.parse_args().pasta.resolve()
    if not root.is_dir():
        parser.error("Pasta não encontrada")
    issues, stats = scan(root)
    print("Arquivos vistos:", stats["files_seen"], "| verificados:", stats["code_files_checked"])
    for path, line, label in issues:
        print("ALERTA:", path, line, label)
    print("Total de alertas:", len(issues))
    print("Aviso: não verifica histórico Git, segredos ofuscados, malware ou licenças.")
    return 2 if issues else 0

if __name__ == "__main__":
    sys.exit(main())
