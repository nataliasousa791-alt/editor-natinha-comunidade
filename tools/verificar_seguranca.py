#!/usr/bin/env python3
"""Verificador heurístico LOCAL. Não envia arquivos nem imprime os valores encontrados."""
import argparse
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "jobs", "logs", "saidas", "outputs", "cache", "entrada", "prontos", "publicados"}
SENSITIVE = {"config.json", "credentials.json", "token.json", "client_secret.json", "rclone.conf", "secrets.json", "cookies.json", "oauth.json"}
MEDIA = {".mp4", ".mov", ".mkv", ".avi", ".wav", ".mp3", ".aac", ".jpg", ".jpeg", ".png", ".webp", ".srt", ".ass"}
CODE = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".json", ".yaml", ".yml", ".md", ".txt", ".toml", ".ini", ".cfg", ".env", ".ps1", ".sh", ".bat", ".css"}
RULES = {
 "possível token": re.compile(r"(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|AIza)[A-Za-z0-9_\\-]{16,}"),
 "chave privada": re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
 "possível credencial": re.compile(r"""(?ix)\\b(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret)\\b\\s*[:=]\\s*["']?(?!placeholder|example|exemplo|change_me|your_|none|null|os\\.environ|os\\.getenv)[A-Za-z0-9_+/\\-]{12,}"""),
 "caminho Windows pessoal": re.compile(r"(?i)C:\\\\Users\\\\[^\\\\\\s]+\\\\")
}

def scan(root):
    root = Path(root)
    findings = []
    stats = {"files_seen": 0, "code_files_checked": 0}
    for here, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(x for x in dirs if x.lower() not in SKIP_DIRS and not (Path(here)/x).is_symlink())
        for name in sorted(files):
            p = Path(here) / name
            if p.is_symlink():
                continue
            rel = str(p.relative_to(root)).replace("\\\\", "/")
            stats["files_seen"] += 1
            n = name.lower()
            if (n.startswith(".env") and n != ".env.example") or n in SENSITIVE or p.suffix.lower() in {".key", ".pem", ".p12", ".pfx", ".sqlite", ".db"}:
                findings.append((rel, 0, "arquivo confidencial"))
                continue
            if p.suffix.lower() in MEDIA:
                findings.append((rel, 0, "mídia: revisão necessária"))
                continue
            if p.suffix.lower() not in CODE:
                continue
            if p.stat().st_size > 1000000:
                findings.append((rel, 0, "arquivo grande não analisado"))
                continue
            stats["code_files_checked"] += 1
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                for label, pattern in RULES.items():
                    if pattern.search(line):
                        findings.append((rel, i, label))
    return findings, stats

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pasta", type=Path)
    root = parser.parse_args().pasta.resolve()
    if not root.is_dir():
        parser.error("Pasta não encontrada")
    findings, stats = scan(root)
    print(f"Arquivos vistos: {stats['files_seen']}; arquivos de texto verificados: {stats['code_files_checked']}")
    for path, line, label in findings:
        print(f"ALERTA: {path}:{line} - {label}")
    print(f"Total de alertas: {len(findings)}")
    print("Aviso: não verifica histórico, segredos ofuscados, malware ou licenças.")
    return 2 if findings else 0

if __name__ == "__main__":
    sys.exit(main())
