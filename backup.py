from datetime import datetime
from pathlib import Path
import shutil

from config import DATABASE_PATH


BACKUP_DIR = Path("backups")


def garantir_pasta_backup():
    BACKUP_DIR.mkdir(exist_ok=True)


def caminho_banco():
    return Path(DATABASE_PATH)


def criar_backup_manual():
    garantir_pasta_backup()

    origem = caminho_banco()

    if not origem.exists():
        return False, "Banco de dados não encontrado."

    agora = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    destino = BACKUP_DIR / f"backup_manual_airesbella_{agora}.db"

    shutil.copy2(origem, destino)

    return True, f"Backup manual criado: {destino.name}"


def criar_backup_automatico_diario():
    garantir_pasta_backup()

    origem = caminho_banco()

    if not origem.exists():
        return False, "Banco de dados não encontrado."

    hoje = datetime.now().strftime("%Y_%m_%d")
    destino = BACKUP_DIR / f"backup_auto_airesbella_{hoje}.db"

    if destino.exists():
        return True, "Backup automático de hoje já existe."

    shutil.copy2(origem, destino)

    return True, f"Backup automático criado: {destino.name}"