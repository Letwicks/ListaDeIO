# -*- coding: utf-8 -*-
"""
Monta as linhas da lista de I/O de um PLC a partir do resultado de extractor.extract_l5x.

Regra de atribuição de estação (validada em campo):
  1. Para cada tag Alias, olha em quais rotinas (RLL) o nome dela foi encontrado.
  2. Se alguma dessas rotinas termina em "_OP<algo>" (ex.: L022_CIC_OP005T01), a
     estação é esse sufixo ("OP005T01"). Se houver mais de uma estação distinta
     entre as rotinas, todas entram (separadas por " / "), sinalizado como ambíguo.
  3. Se nenhuma rotina indicar uma estação, cai no fallback: procura um padrão do
     tipo "005T01" / "010TT01" no nome do próprio módulo de rede.
  4. Se nada disso resolver, a tag/módulo vai para a categoria "Infraestrutura/Outros".

Além disso, é feita uma checagem de integridade: duas tags Alias diferentes nunca
deveriam apontar para o mesmo endereço físico (mesmo bit do mesmo módulo) — isso é
um erro de configuração no PLC (dois sinais lógicos amarrados na mesma fiação).
Quando isso acontece, as linhas envolvidas são marcadas como conflito.

Alias criados no programa mas nunca referenciados em nenhuma rotina (nem em CIC/SERV/READ,
nem nas rotinas de atualização) são desconsiderados — não entram na lista, pois não
representam um sinal realmente em uso na lógica do PLC.

O time de elétrica só precisa do sinal físico do módulo, nunca de uma tag
intermediária interna do programa. Quando o Alias não aponta direto para um
módulo, tentamos resolver o endereço físico real por trás dele via
core.copy_resolver (ver esse módulo para os detalhes e limitações).
"""
import re
from collections import defaultdict

from core.copy_resolver import build_copy_ranges, resolve_physical

STATION_FALLBACK_RE = re.compile(r'(\d{2,3}T{1,2}\d{0,2})')
OP_SUFFIX_RE = re.compile(r'^OP\d')


def op_code_from_routine(routine_name):
    last = routine_name.split("_")[-1]
    if OP_SUFFIX_RE.match(last):
        return last
    return None


def find_module_for_alias(alias_for, module_names_sorted_desc):
    """Só conta como endereço de módulo o caminho com DOIS-PONTOS ('Mod:I1.Data[0]').
    Com ponto ('Mod.DI01') é tag de programa — mesmo quando tem o nome do módulo."""
    for mod in module_names_sorted_desc:
        if alias_for.startswith(mod + ":"):
            return mod
    return None


def build_rows(plc_key, modules, tags, tag_routines, update_routines_text=None,
               datatypes=None, base_tags=None):
    """Retorna (rows, n_desconsiderados) — as linhas desse PLC e quantos alias
    criados mas nunca referenciados em nenhuma rotina foram descartados."""
    rows = []
    module_names_desc = sorted(modules.keys(), key=len, reverse=True)
    matched_modules = set()
    datatypes = datatypes or {}
    base_tags = base_tags or {}
    copy_ranges = build_copy_ranges(update_routines_text or {}, tags, base_tags)
    n_desconsiderados = 0

    for tag_name, tinfo in tags.items():
        routines = sorted(set(tag_routines.get(tag_name, [])))
        if not routines:
            # alias criado mas nunca usado em nenhuma rotina do programa - desconsiderar
            n_desconsiderados += 1
            continue

        alias_for = tinfo.get("AliasFor", "")
        desc = (tinfo.get("Description") or "").replace("\n", " / ")
        module_name = find_module_for_alias(alias_for, module_names_desc) if alias_for else None
        endereco_exibido = alias_for if module_name else ""

        if module_name is None and alias_for:
            resolvido = resolve_physical(alias_for, copy_ranges, datatypes, base_tags)
            if resolvido:
                endereco_exibido = resolvido
                module_name = find_module_for_alias(resolvido, module_names_desc)
                if module_name is None:
                    # resolve_physical devolveu algo, mas nao bate com nenhum modulo conhecido -
                    # nao arrisca mostrar como se fosse endereco fisico
                    endereco_exibido = ""

        if module_name:
            matched_modules.add(module_name)
        mod_info = modules.get(module_name, {}) if module_name else {}

        op_codes = sorted({oc for r in routines if (oc := op_code_from_routine(r))})

        if len(op_codes) == 1:
            station = op_codes[0]
            metodo = "Rotina"
            categoria = "Estacao"
        elif len(op_codes) > 1:
            station = " / ".join(op_codes)
            metodo = "Rotina (multiplas estacoes)"
            categoria = "Estacao"
        else:
            station = ""
            if module_name:
                m = STATION_FALLBACK_RE.search(module_name)
                if m:
                    station = "OP" + m.group(1)
                    metodo = "Nome do modulo (sem rotina)"
                    categoria = "Estacao"
                else:
                    metodo = "Rotina sem codigo de estacao"
                    categoria = "Infraestrutura/Outros"
            else:
                metodo = "Rotina sem codigo de estacao"
                categoria = "Infraestrutura/Outros"

        rows.append({
            "PLC": plc_key,
            "Categoria": categoria,
            "Estacao": station,
            "Modulo": module_name or "(nao localizado)",
            "CatalogNumber": mod_info.get("CatalogNumber", ""),
            "VendorID": mod_info.get("Vendor", ""),
            "IP": mod_info.get("IP") or "",
            "RedePai": mod_info.get("ParentModule", ""),
            "Tag": tag_name,
            "EnderecoFisico": endereco_exibido or "(nao localizado)",
            "Descricao": desc,
            "Metodo": metodo,
            "Rotinas": "; ".join(routines),
            "Conflito": "",
            "TagsConflitantes": "",
        })

    for mod_name, mod_info in modules.items():
        if mod_name in matched_modules:
            continue
        rows.append({
            "PLC": plc_key,
            "Categoria": "Infraestrutura/Outros",
            "Estacao": "",
            "Modulo": mod_name,
            "CatalogNumber": mod_info.get("CatalogNumber", ""),
            "VendorID": mod_info.get("Vendor", ""),
            "IP": mod_info.get("IP") or "",
            "RedePai": mod_info.get("ParentModule", ""),
            "Tag": "",
            "EnderecoFisico": "",
            "Descricao": "(sem tags alias associadas)",
            "Metodo": "Modulo sem tags alias",
            "Rotinas": "",
            "Conflito": "",
            "TagsConflitantes": "",
        })

    _marcar_conflitos_de_endereco(rows)

    rows.sort(key=lambda r: (0 if r["Categoria"] == "Estacao" else 1, r["Estacao"], r["Modulo"], r["Tag"]))
    return rows, n_desconsiderados


def _marcar_conflitos_de_endereco(rows):
    """Marca linhas cujo Endereço físico é usado por mais de uma tag (mesmo bit,
    duas tags Alias diferentes) — sinal de erro de configuração no PLC."""
    por_endereco = defaultdict(list)
    for r in rows:
        if r["EnderecoFisico"] and r["Tag"] and r["EnderecoFisico"] != "(nao localizado)":
            por_endereco[r["EnderecoFisico"]].append(r)

    for endereco, grupo in por_endereco.items():
        if len(grupo) < 2:
            continue
        for r in grupo:
            outras = sorted(x["Tag"] for x in grupo if x["Tag"] != r["Tag"])
            r["Conflito"] = "Sim"
            r["TagsConflitantes"] = "; ".join(outras)
