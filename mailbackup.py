#!/usr/bin/env python3
"""mailbackup -- gzip (and optionally gpg-encrypt) a folder or file and
email it to yourself as a backup, split into <25MB parts (Gmail's real
attachment limit, not the 400MB Gabe first guessed). Runs entirely
from Termux via plain smtplib -- no Claude needed at runtime, same
self-sufficient shape as csync-auto.py/memguard.sh.

Built 2026-10-30 after the claude-sync repo's own session transcript
crossed GitHub's 50MB warning line -- this is a second, independent
backup channel, not a replacement for git sync.

SECRET HANDLING -- READ THIS BEFORE USING:
This needs a Gmail "App Password" for the FROM address (Google
disables plain-password SMTP login). That password must NEVER be
typed into a Claude conversation -- ~/.claude's own transcripts get
pushed to GitHub, so anything typed to Claude becomes permanent git
history. Generate it yourself at
https://myaccount.google.com/apppasswords (needs 2FA on first), then
save it yourself, from your own Termux session, never through Claude:

    echo 'xxxx xxxx xxxx xxxx' > ~/.mailbackup_secret
    chmod 600 ~/.mailbackup_secret

Usage:
    mailbackup.py <folder-or-file> [--to ADDR] [--from ADDR] [--encrypt]
"""
import argparse
import getpass
import shutil
import smtplib
import subprocess
import sys
import tarfile
import tempfile
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from pathlib import Path

SECRET_FILE = Path.home() / ".mailbackup_secret"
DEFAULT_FROM = "lewisgabe33@gmail.com"
DEFAULT_TO = "lewisgabe23@gmail.com"
CHUNK_SIZE = 24 * 1024 * 1024  # stay under Gmail's 25MB attachment cap


def load_password():
    if not SECRET_FILE.exists():
        sys.exit(
            "no app password at %s -- generate one at "
            "https://myaccount.google.com/apppasswords and save it yourself "
            "(never paste it to Claude):\n"
            "  echo 'xxxx xxxx xxxx xxxx' > %s && chmod 600 %s"
            % (SECRET_FILE, SECRET_FILE, SECRET_FILE)
        )
    mode = SECRET_FILE.stat().st_mode & 0o777
    if mode & 0o077:
        print("warning: %s is readable by others -- chmod 600 it" % SECRET_FILE, file=sys.stderr)
    return SECRET_FILE.read_text().strip()


def make_archive(src, workdir):
    src = Path(src)
    archive = workdir / (src.name + ".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(src, arcname=src.name)
    return archive


def encrypt(archive, workdir):
    gpg = shutil.which("gpg")
    if not gpg:
        print("gpg not found -- sending UNENCRYPTED (install gnupg for encryption)", file=sys.stderr)
        return archive
    passphrase = getpass.getpass("encryption passphrase (not saved anywhere): ")
    if passphrase != getpass.getpass("confirm passphrase: "):
        sys.exit("passphrases didn't match -- aborting")
    out = workdir / (archive.name + ".gpg")
    subprocess.run(
        [gpg, "--batch", "--yes", "--passphrase", passphrase, "--symmetric",
         "--cipher-algo", "AES256", "-o", str(out), str(archive)],
        check=True,
    )
    return out


def split(path):
    size = path.stat().st_size
    if size <= CHUNK_SIZE:
        return [path]
    parts = []
    with path.open("rb") as f:
        i = 0
        while True:
            data = f.read(CHUNK_SIZE)
            if not data:
                break
            i += 1
            part = path.with_name(path.name + ".part%03d" % i)
            part.write_bytes(data)
            parts.append(part)
    return parts


def send(part, from_addr, to_addr, password, index, total):
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = "mailbackup: %s (%d/%d)" % (part.name, index, total)
    att = MIMEApplication(part.read_bytes(), Name=part.name)
    att["Content-Disposition"] = 'attachment; filename="%s"' % part.name
    msg.attach(att)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(from_addr, password)
        s.send_message(msg)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("target", help="folder or file to back up")
    p.add_argument("--to", default=DEFAULT_TO)
    p.add_argument("--from", dest="from_addr", default=DEFAULT_FROM)
    p.add_argument("--encrypt", action="store_true", help="gpg-encrypt before sending (needs gnupg)")
    args = p.parse_args()

    password = load_password()
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        archive = make_archive(args.target, workdir)
        print("archived: %.1fMB" % (archive.stat().st_size / 1e6))
        if args.encrypt:
            archive = encrypt(archive, workdir)
            print("encrypted: %.1fMB" % (archive.stat().st_size / 1e6))
        parts = split(archive)
        for i, part in enumerate(parts, 1):
            print("sending part %d/%d (%.1fMB)..." % (i, len(parts), part.stat().st_size / 1e6))
            send(part, args.from_addr, args.to, password, i, len(parts))
    print("done -- %d part(s) sent to %s" % (len(parts), args.to))


if __name__ == "__main__":
    main()
