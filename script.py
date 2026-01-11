import subprocess
import sys
from pathlib import Path
import yaml


# ============================================================
# Configurazione percorsi
# ============================================================

SOURCE_DIR = Path(
    r"C:\Users\samue\Desktop\Uni\Stage\TEST FINALI\diagrams2ai\presi da eclipse\dfi\Output0\en" + "\\"
)
DATA_DIR = SOURCE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


# ============================================================
# Utility generiche
# ============================================================

def run_command(cmd, cwd) -> None:
    print("Eseguo:", " ".join(map(str, cmd)))
    subprocess.run(cmd, cwd=cwd, check=True)


def rename_if_present(old_name: str, new_name: str, folder: Path = DATA_DIR) -> None:
    """
    Se il file esiste già, lo sovrascrive.
    """
    old_path = folder / old_name
    new_path = folder / new_name

    if not old_path.exists():
        return

    new_path.unlink(missing_ok=True)
    old_path.rename(new_path)
    print(f"Rinominato: {old_name} → {new_name}")


def ensure_version_header(file_path: Path, version: str = "3.1") -> None:
    """
    Inserisce o aggiorna l'header `version: "<x>"` all'inizio del file YAML.
    """
    if not file_path.exists():
        return

    with file_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if line.strip().startswith("version:"):
            lines[i] = f'version: "{version}"\n'
            break
    else:
        lines.insert(0, f'version: "{version}"\n')

    with file_path.open("w", encoding="utf-8") as f:
        f.writelines(lines)


# ============================================================
# Conversione domain.yml
# ============================================================

def convert_domain(source: Path, target: Path) -> None:
    """
    Converte un domain Rasa legacy in formato compatibile con Rasa 3.x:
    - slot `unfeaturized` → `text`
    - aggiunge `mappings` se mancanti
    - normalizza la definizione dei form
    """
    with source.open("r", encoding="utf-8") as f:
        domain = yaml.safe_load(f)

    # Slot
    for slot_name, slot_info in domain.get("slots", {}).items():
        if slot_info.get("type") == "unfeaturized":
            slot_info["type"] = "text"

        if "mappings" not in slot_info:
            slot_info["mappings"] = [
                {"type": "from_entity", "entity": slot_name}
            ]

    # Forms
    forms = domain.get("forms", [])
    if isinstance(forms, list):
        forms_dict = {}
        for form_name in forms:
            prefix = form_name.split("_form")[0]
            required = [
                s for s in domain["slots"].keys()
                if s.startswith(prefix)
            ]
            forms_dict[form_name] = {"required_slots": required}

        domain["forms"] = forms_dict

    with target.open("w", encoding="utf-8") as f:
        yaml.dump(domain, f, sort_keys=False, allow_unicode=True)

    print(f"Domain convertito: {target}")


# ============================================================
# Utility Rasa
# ============================================================


def remove_legacy_md_files(folder: Path = DATA_DIR) -> None:
    """Elimina i vecchi file Markdown non più usati da Rasa 3.x"""
    for name in ("nlu.md", "stories.md"):
        path = folder / name
        if path.exists():
            path.unlink()
            print(f"Cancellato: {name}")

def update_rasa_config(config_file: Path) -> None:
    """Rimuove FormPolicy da config.yml (obsoleta in Rasa 3.x)"""
    with config_file.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if "policies" in config:
        config["policies"] = [
            p for p in config["policies"]
            if p.get("name") != "FormPolicy"
        ]

    with config_file.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f)

    print("FormPolicy rimossa da config.yml")


# ============================================================
# Workflow principale
# ============================================================

def main() -> None:
    print("Conversione progetto Rasa")

    # 1. Dati (NLU + Stories)
    run_command(
        [ sys.executable, "-m", "rasa", "data", "convert", "nlu",
          "-f", "yaml", f"--data={SOURCE_DIR}", f"--out={DATA_DIR}"],
        SOURCE_DIR
    )
    run_command(
        [sys.executable, "-m", "rasa", "data", "convert", "core",
            "-f", "yaml", f"--data={SOURCE_DIR}", f"--out={DATA_DIR}"],
        SOURCE_DIR
    )
    rename_if_present("nlu_converted.yml", "nlu.yml")
    rename_if_present("stories_converted.yml", "stories.yml")

    # 2. Domain
    source_domain = SOURCE_DIR / "domain.yml"
    temp_domain = DATA_DIR / "domain_converted.yml"
    convert_domain(source_domain, temp_domain)

    final_domain = SOURCE_DIR / "domain.yml"
    final_domain.unlink(missing_ok=True)
    temp_domain.rename(final_domain)
    print(f"Domain aggiornato: {final_domain}")

    # 3. Header di versione
    ensure_version_header(DATA_DIR / "nlu.yml")
    ensure_version_header(DATA_DIR / "stories.yml")
    ensure_version_header(final_domain)

    # 4. Pulizia file obsoleti
    remove_legacy_md_files()

    # 5. Config Rasa
    run_command(
        [sys.executable, "-m", "rasa", "data", "convert", "config"],
        SOURCE_DIR
    )

    rules_file = DATA_DIR / "rules.yml"
    ensure_version_header(rules_file)

    update_rasa_config(SOURCE_DIR / "config.yml")

    print("Conversione completata ")


if __name__ == "__main__":
    main()
