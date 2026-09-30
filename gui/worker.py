# -*- coding: utf-8 -*-
import os
from PyQt6.QtCore import QObject, pyqtSignal

from core.extractor import extract_l5x
from core.builder import build_rows
from core.excel_writer import write_workbook


class Worker(QObject):
    log = pyqtSignal(str)
    progress = pyqtSignal(int, int)          # etapa atual, total de etapas
    finished = pyqtSignal(bool, str, dict)    # sucesso, mensagem/caminho, estatisticas

    def __init__(self, files, out_path, include_infra):
        """files: lista de tuplas (chave_plc, caminho_l5x)."""
        super().__init__()
        self.files = files
        self.out_path = out_path
        self.include_infra = include_infra
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            total_steps = len(self.files) + 1
            all_rows = []
            total_desconsiderados = 0

            for i, (key, path) in enumerate(self.files, start=1):
                if self._cancelled:
                    self.finished.emit(False, "Cancelado pelo usuário.", {})
                    return

                fname = os.path.basename(path)
                self.log.emit(f"Processando {key} ({fname})...")

                def _progress(n, k=key):
                    self.log.emit(f"    ... {n:,} linhas lidas")

                modules, tags, tag_routines, update_routines_text, datatypes, base_tags = extract_l5x(
                    path, progress_cb=_progress, log_cb=self.log.emit
                )
                rows, n_desc = build_rows(key, modules, tags, tag_routines,
                                          update_routines_text, datatypes, base_tags)
                total_desconsiderados += n_desc
                if n_desc:
                    self.log.emit(f"    {n_desc} alias desconsiderado(s) (criado(s), nunca usado(s) em nenhuma rotina)")
                all_rows.append(rows)
                self.progress.emit(i, total_steps)

            self.log.emit("Gerando planilha Excel...")
            stats = write_workbook(all_rows, self.out_path, include_infra=self.include_infra)
            self.progress.emit(total_steps, total_steps)
            self.log.emit(
                f"Concluído: {stats['total_linhas']} linhas "
                f"({stats['linhas_estacao']} de estação, {stats['linhas_infra']} de infraestrutura/outros) "
                f"em {stats['plcs']} PLC(s)."
                + (f" {total_desconsiderados} alias desconsiderado(s) no total (nunca usados em nenhuma rotina)."
                   if total_desconsiderados else "")
            )
            n_conf = stats.get("linhas_conflito", 0)
            if n_conf:
                self.log.emit(
                    f"ATENÇÃO: {n_conf} linha(s) com conflito de endereço físico (duas tags no mesmo ponto de I/O) "
                    f"— veja a aba 'Conflitos de Endereço', destacada em vermelho."
                )
            self.finished.emit(True, self.out_path, stats)

        except Exception as e:
            self.log.emit(f"ERRO: {e}")
            self.finished.emit(False, str(e), {})
