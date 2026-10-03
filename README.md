# TUI-llama-server 🚀

> **Interface Terminal Premium & Gestionnaire GPU/ROCm pour `llama-server` dédié aux Agents IA.**  
> *Sober, high-performance terminal dashboard & model orchestrator for local LLM inference with zero web overhead.*

[![Build & Package](https://github.com/Chomiam/TUI-llama-server/actions/workflows/build-packages.yml/badge.svg)](https://github.com/Chomiam/TUI-llama-server/actions/workflows/build-packages.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-orange.svg)](https://github.com/Chomiam/TUI-llama-server)
[![Packaging: .deb | .rpm](https://img.shields.io/badge/Packages-.deb%20%7C%20.rpm-success.svg)](https://github.com/Chomiam/TUI-llama-server/releases)

---

## 📸 Aperçu / Overview

```text
┌── λ TUI-LLAMA-SERVER ────────────────────────────────────────────────────────┐
│ [ROCm 7.15 · gfx1201]  AMD Radeon RX 9070 XT   ● ONLINE   http://127.0.0.1:8080/v1 [Copy URL]│
├──────────────────────────────────────────────────────────────────────────────┤
│ [F1] Models & Engine  │  [F2] Live Monitor  │  [F3] Logs  │  [F4] Flags & ROCm│
├──────────────────────────────────────┬───────────────────────────────────────┤
│ Discovered Models (~/models)         │ Model Characteristics                 │
│ ┌──────────────────────────────────┐ │ • Qwen 2.5 Coder 7B Instruct          │
│ │ qwen2.5-coder-7b...  Q8_0  7.5GB │ │   Arch: qwen2 | Context: 131,072 tok  │
│ │ deepseek-r1-14b...   Q4    8.4GB │ │   Layers: 28  | Quant: Q8_0           │
│ │ DeepSeek-Coder-V2... Q4_K  8.9GB │ │   Template: ChatML | Tools: ✓ Enabled │
│ │ Qwen3.8-27B-UD...    Q2_K  9.2GB │ │   Est. VRAM Needed: 9.5 GB (16 GB max)│
│ └──────────────────────────────────┘ │ Auto-Tuned Flags: -ngl 99 --no-webui  │
├──────────────────────────────────────┴───────────────────────────────────────┤
│ GPU: [████░░░░░░] 28%  •  VRAM: 9.5/15.9 GB (60%)  •  RAM: 14.1/30.5 GB (46%) │
│ CPU: [██░░░░░░░░] 12%  •  Swap: 1.7/8.0 GB (21%)                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ ▶ Launch Server [Space]                  [F1] Models  [F2] Monitor  [Q] Quit │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Fonctionnalités Clés / Key Features

1. **Détection Matérielle & Auto-Tuning ROCm / GPU** :
   - Détection native des GPU **AMD (ROCm)**, **NVIDIA (CUDA)** et repli **CPU**.
   - Extraction de la version exacte de ROCm (via `hipconfig`, `rocm-smi`, `/opt/rocm`, `/sys/class/kfd`).
   - Détection de l'architecture GFX cible (`gfx1201` RDNA4, `gfx1100` RDNA3, `gfx1030` RDNA2, `gfx90a` CDNA).
   - Dérivation automatique des drapeaux optimaux :
     - `HSA_OVERRIDE_GFX_VERSION` auto-ajusté selon l'architecture.
     - `HIP_VISIBLE_DEVICES=0`, `ROCR_VISIBLE_DEVICES=0`.
     - `GPU_MAX_HW_QUEUES=8`.
     - `--flash-attn` auto/on selon support GPU.
     - `-ngl 99` (offload GPU total ou calculé).

2. **Scanner & Inspecteur GGUF Intégré (`~/models`)** :
   - Découverte automatique des modèles dans `/home/{user}/models`.
   - Parsing direct des métadonnées GGUF sans charger les poids en mémoire (cache instantané).
   - Affichage complet des caractéristiques :
     - Architecture (`llama`, `qwen2`, `deepseek2`, etc.)
     - Quantization (`Q8_0`, `Q4_K_M`, `Q2_K_XL`, etc.)
     - Fenêtre de contexte (`context_length`, ex: 131 072 tokens)
     - Nombre de blocs / layers, têtes d'attention et dimension d'embedding
     - Détection des **capacités de Tool-Calling / Function-Calling** (`<tools>`, `<tool_call>`)
     - Empreinte VRAM estimée vs VRAM disponible avec avertissement en cas de dépassement.

3. **Conçu Exclusivement pour les Agents IA (Sans WebUI)** :
   - Lance `llama-server` avec `--no-webui` pour économiser la mémoire et les cycles CPU/GPU.
   - Fournit les points de terminaison standard OpenAI :
     - Base URL : `http://127.0.0.1:8080/v1`
     - Chat Completions : `/v1/chat/completions`
     - Modèles : `/v1/models`
     - Embeddings : `/v1/embeddings`
   - Bouton et raccourci clavier pour **copier l'URL de base** en un clic pour vos agents.

4. **Monitoring des Performances en Temps Réel** :
   - Jauges haute fréquence à zéro surcharge (via sysfs Linux direct et sondes SMI) :
     - Utilisation GPU (%)
     - VRAM Utilisée / Totale (GB & %)
     - RAM Système Utilisée / Totale (GB & %)
     - Utilisation CPU (%)
     - Mémoire Swap (%)

5. **Console de Logs Interactive & Copie Système** :
   - Flux en direct de la sortie standard et d'erreur de `llama-server`.
   - Colorisation intelligente des logs (vert = écoute/prêt, jaune = warning, rouge = erreur).
   - Filtre de recherche temps réel.
   - Bouton et raccourci (`Ctrl+L`) pour **copier l'intégralité ou une sélection des logs** dans le presse-papier système (`xclip`, `wl-copy` ou protocole terminal OSC 52).

6. **Design Sobre & Produit Premium** :
   - Thème sombre graphite/ardoise avec touches subtiles cyan et émeraude.
   - Police et bordures terminal Unicode raffinées.
   - Navigation intuitive au clavier et à la souris.

---

## 📦 Installation & Paquets (.deb & .rpm)

Les paquets `.deb` et `.rpm` sont automatiquement compilés et publiés via **GitHub Actions** à chaque version.

### Option 1 : Debian / Ubuntu / Pop!_OS / Linux Mint (`.deb`)

Téléchargez le paquet depuis les [Releases](https://github.com/Chomiam/TUI-llama-server/releases) ou installez-le :
```bash
sudo dpkg -i tui-llama-server_1.0.0-1_amd64.deb
```

### Option 2 : Fedora / RHEL / Rocky / openSUSE (`.rpm`)

```bash
sudo rpm -i tui-llama-server-1.0.0-1.x86_64.rpm
# ou
sudo dnf install ./tui-llama-server-1.0.0-1.x86_64.rpm
```

### Option 3 : Installation Python / Pipx (Universelle)

```bash
pipx install git+https://github.com/Chomiam/TUI-llama-server.git
# ou clonez et installez localement :
git clone https://github.com/Chomiam/TUI-llama-server.git
cd TUI-llama-server
pip install --user .
```

---

## ⌨️ Raccourcis Clavier / Keybindings

| Touche | Action |
|---|---|
| `F1` | Aller à l'onglet **Modèles & Moteur** |
| `F2` | Aller à l'onglet **Monitoring & Agents** |
| `F3` | Aller à l'onglet **Logs & Console** |
| `F4` | Aller à l'onglet **Flags & Configuration** |
| `Espace` | **Démarrer / Arrêter** le serveur |
| `Ctrl+Y` | **Copier la Base URL** (`http://127.0.0.1:8080/v1`) |
| `Ctrl+L` | **Copier tous les logs** dans le presse-papier |
| `Q` | Quitter l'application |

---

## 🤖 Utilisation avec vos Agents IA

Une fois le serveur démarré dans le TUI, configurez votre agent favori avec les paramètres suivants :

### Configuration Cline / Roo-Code
- **API Provider** : `OpenAI Compatible`
- **Base URL** : `http://127.0.0.1:8080/v1`
- **API Key** : `ignored` (ou laissez vide)
- **Model ID** : Le nom du modèle chargé (ex: `qwen2.5-coder-7b-instruct`)

### Configuration Python (OpenAI SDK)
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8080/v1",
    api_key="none"
)

response = client.chat.completions.create(
    model="local-model",
    messages=[{"role": "user", "content": "Bonjour, comment vas-tu ?"}]
)
print(response.choices[0].message.content)
```

---

## 🛠️ Compilation Locale des Paquets

Vous pouvez exécuter le script de packaging complet localement :

```bash
./build-packages.sh
```

Cela génèrera dans le dossier `dist/` :
- `tui-llama-server` (Binaire autonome CArchive d'environ ~32 Mo)
- `tui-llama-server_1.0.0-1_amd64.deb`
- `tui-llama-server-1.0.0-1.x86_64.rpm`

---

## 📜 Licence

Ce projet est sous licence [MIT](LICENSE).
