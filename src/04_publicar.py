"""Etapa 4: copia os JSON processados para docs/data, de onde o painel (GitHub Pages) lê."""
import shutil

from config import DOCS_DATA, PROCESSED


def main():
    for f in sorted(PROCESSED.glob("*.json")):
        shutil.copy2(f, DOCS_DATA / f.name)
        print(f"  ok  docs/data/{f.name}")


if __name__ == "__main__":
    main()
