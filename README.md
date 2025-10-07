# 3xF1ltR4T0r

## 🧩 Description rapide

Lors d'un projet récent en cours de cybersécurité physique et matérielle, j'ai dû créer un projet avec le **PicoUSB** : 

En branchant mon **PicoUSB** sur un ordinateur victime, j'exportais des données sur la configuration logicielle et matérielle de la victime **ainsi que sur sa connexion wifi** vers un serveur hébergé sur un RaspberryPi 4. Pour le cours de détection, j'ai choisi de créer une image docker qui puisse être lancée directement sur un PC ou un RaspberryPi doté de docker, afin que n'importe qui puisse répliquer mon attaque facilement.

Le projet Exfiltrator met en place un petit service **Flask** tournant dans un conteneur **Docker** sur un **Raspberry Pi**.
Le conteneur héberge un serveur web simple permettant d’uploader des fichiers dans `/share/uploads`.
Lorsqu’un fichier nommé `export.json` est détecté, le service :

- Extrait les valeurs `wifi.ssid` et `wifi.password` du fichier.
- Tente (si autorisé) de se connecter au réseau Wi‑Fi correspondant.
- Lance un scan réseau **(nmap)** sur `localhost` pour des raisons de sécurité.
- Enregistre les résultats dans `/share/scan_results`.
<br>
<br>

> 💡 Pour limiter les risques, le scan `nmap` est effectué **uniquement sur localhost** tant qu’aucune autorisation n’est donnée.

---

## 📄 Exemple de fichier `export.json`

```json
{
  "wifi": {
    "ssid": "EntrepriseWifi",
    "password": "supersecret"
  }
}
```
<br>
Uploadez ce fichier via la page web du conteneur. Le watcher le détectera automatiquement et lancera le traitement.
<br>


## 🛠️ Commandes principales

### 1. Construire l’image

```bash
docker build -t [nom_de_votre_image] .
```

### 2. Lancer le conteneur

```bash
docker run -it --rm --user root --network host --privileged \
  -v /etc/wpa_supplicant:/etc/wpa_supplicant:rw \
  -v /run/dbus:/run/dbus \
  -e CONFIRM_CONNECT="yes" \
  [nom_de_votre_image]
```

### Explication rapide des options

* `--user root` : nécessaire si le conteneur doit écrire dans `/etc/wpa_supplicant`.
* `--network host` : le conteneur partage le réseau de la Raspberry Pi (utile pour connexions & scans).
* `--privileged` (ou `--cap-add=NET_ADMIN --cap-add=NET_RAW`) : droits nécessaires pour opérations réseau et captures.
* `-v /etc/wpa_supplicant:/etc/wpa_supplicant:rw` : monte la config Wi‑Fi du système pour pouvoir l’éditer.
* `-v /run/dbus:/run/dbus` : permet à `nmcli` d’accéder au bus D‑Bus du host (NetworkManager).
* `-e CONFIRM_CONNECT="yes"` : autorise la connexion automatique au SSID extrait.

