#!/usr/bin/env python3
import os
import json
import time
import subprocess
import threading
from flask import Flask, request, redirect, send_from_directory, render_template_string
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/share/uploads")
WHITELIST = [s.strip() for s in os.environ.get("WHITELIST", "").split(",") if s.strip()]
CONFIRM_CONNECT = os.environ.get("CONFIRM_CONNECT", "no").lower() == "yes"
SCAN_ON_CONNECT = os.environ.get("SCAN_ON_CONNECT", "yes").lower() == "yes"

app = Flask(__name__)

INDEX_HTML = """
<!doctype html>
<title>Upload</title>
<h1>Upload file</h1>
<form method=post enctype=multipart/form-data>
  <input type=file name=file>
  <input type=submit value=Upload>
</form>
<p>Uploaded files:</p>
<ul>
{% for f in files %}
  <li><a href="/files/{{f}}">{{f}}</a></li>
{% endfor %}
</ul>
"""

@app.route('/', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        f = request.files.get('file')
        if not f:
            return "No file", 400
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        path = os.path.join(UPLOAD_DIR, f.filename)
        f.save(path)
        return redirect('/')
    files = os.listdir(UPLOAD_DIR) if os.path.exists(UPLOAD_DIR) else []
    return render_template_string(INDEX_HTML, files=files)

@app.route('/files/<path:filename>')
def serve_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

class UploadHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        fname = os.path.basename(event.src_path)
        print(f"[watcher] New file: {fname}")
        if fname == "export.json":
            try:
                handle_export(event.src_path)
            except Exception as e:
                print("[error] handling export.json:", e)

def run_command(cmd, check=False, capture_output=False):
    print("[cmd]", cmd)
    return subprocess.run(cmd, shell=True, check=check, capture_output=capture_output, text=True)

def parse_export(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    ssid = data.get("wifi", {}).get("ssid")
    pwd = data.get("wifi", {}).get("password")
    return ssid, pwd

def safe_to_connect(ssid):
    if not ssid:
        return False
    if WHITELIST:
        return ssid in WHITELIST
    # if no whitelist, require explicit CONFIRM_CONNECT
    return CONFIRM_CONNECT

def connect_with_nmcli(ssid, password):
    # add a connection (works if NetworkManager is installed and running)
    run_command(f"nmcli dev wifi connect '{ssid}' password '{password}'", check=False)

def connect_with_wpa_supplicant(ssid, password):
    conf = f"""
network={{
    ssid="{ssid}"
    psk="{password}"
}}
"""
    # requires /etc/wpa_supplicant to be writeable in container (mount from host)
    wpa_conf_path = "/etc/wpa_supplicant/wpa_supplicant.conf"
    try:
        with open(wpa_conf_path, "a") as fh:
            fh.write("\n" + conf)
        # send SIGHUP to wpa_supplicant or restart service (host-dependent)
        run_command("killall -HUP wpa_supplicant || true")
    except Exception as e:
        print("[wpa] failed to write wpa_supplicant.conf:", e)

def perform_scans(target_if=None):
    # Non exhaustive set of scans. Do NOT scan hosts/networks without permission.
    outdir = "/share/scan_results"
    os.makedirs(outdir, exist_ok=True)
    timestamp = int(time.time())
    nmap_file = os.path.join(outdir, f"nmap_{timestamp}.txt")
    tshark_file = os.path.join(outdir, f"tshark_{timestamp}.pcap")
    # nmap quick scan of the local network (example: 192.168.1.0/24). We try to infer network.
    try:
        # derive local prefix from ip route
        proc = run_command("ip -o -4 addr show | awk '{print $4}' | head -n1", capture_output=True)
        cidr = proc.stdout.strip()
        if cidr:
            network = cidr.split('/')[0].rsplit('.',1)[0] + ".0/24"
        else:
            network = "192.168.1.0/24"
    except Exception:
        network = "192.168.1.0/24"

    print("[scan] running nmap on", network)
    run_command(f"nmap -sn {network} -oN {nmap_file}")

    if target_if:
        # capture a small pcap (requires permissions)
        print("[scan] running tshark on", target_if)
        run_command(f"timeout 15 tshark -i {target_if} -w {tshark_file}")

def handle_export(path):
    ssid, pwd = parse_export(path)
    print("[export] parsed:", ssid, pwd is not None)
    if not ssid or not pwd:
        print("[export] invalid export.json content")
        return

    print("[export] candidate SSID:", ssid)
    allowed = safe_to_connect(ssid)
    if not allowed:
        print("[export] Connection blocked: not whitelisted and CONFIRM_CONNECT not set.")
        print("Credentials (printed for manual action):")
        print("SSID:", ssid)
        print("PASSWORD:", pwd)
        return

    print("[export] Connecting to SSID (allowed).")
    # Prefer nmcli if available
    try:
        which = subprocess.run("which nmcli", shell=True, capture_output=True, text=True)
        if which.returncode == 0:
            connect_with_nmcli(ssid, pwd)
        else:
            connect_with_wpa_supplicant(ssid, pwd)
    except Exception as e:
        print("[error] connecting:", e)

    # small delay for connection to settle
    time.sleep(5)
    # attempt scans
    if SCAN_ON_CONNECT:
        # try to detect wireless interface
        try:
            out = subprocess.run("iw dev | awk '$1==\"Interface\"{print $2; exit}'", shell=True, capture_output=True, text=True)
            iface = out.stdout.strip() or None
        except Exception:
            iface = None
        perform_scans(target_if=iface)

def start_watcher():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    event_handler = UploadHandler()
    observer = Observer()
    observer.schedule(event_handler, UPLOAD_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    # start watcher in background
    t = threading.Thread(target=start_watcher, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=80)
