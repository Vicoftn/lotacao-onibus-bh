import json


def salvar_json(obj, caminho):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  ok  {caminho.name}")


def ler_json(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)
