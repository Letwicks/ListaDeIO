# -*- coding: utf-8 -*-
import os
from pathlib import Path

from PyQt6.QtCore import Qt, QThread
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QCheckBox,
    QProgressBar, QTextEdit, QTabWidget, QFileDialog, QMessageBox,
)

import brand
from gui.worker import Worker

APP_TITLE = "Lista de I/O — Rockwell / Studio 5000"
APP_TAGLINE = "Lista de I/O a partir de L5X — módulos e rastreamento por rotina"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(920, 760)

        self.current_folder = None
        self.thread = None
        self.worker = None
        self.last_output_path = None

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_header())

        tabs = QTabWidget()
        tabs.addTab(self._build_main_tab(), "Gerar Lista de IO")
        tabs.addTab(self._build_instructions_tab(), "Instruções")
        root_layout.addWidget(tabs, 1)

    # ------------------------------------------------------------------ UI

    def _build_header(self):
        header = QWidget()
        header.setObjectName("brandHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 7, 16, 7)
        layout.setSpacing(10)

        ratio = self.devicePixelRatioF()
        logo = QLabel()
        logo.setPixmap(brand.logo_pixmap(30, ratio))
        logo.setToolTip(brand.AUTOLINX_SLOGAN)
        layout.addWidget(logo)

        nome = QLabel(brand.AUTOLINX_NOME)
        nome.setObjectName("brandName")
        layout.addWidget(nome)
        layout.addStretch(1)

        tagline = QLabel(APP_TAGLINE)
        tagline.setObjectName("brandTagline")
        layout.addWidget(tagline)

        return header

    def _build_main_tab(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setSpacing(12)

        # 1. Pasta
        box_folder = QGroupBox("1. Pasta com os arquivos L5X")
        fl = QHBoxLayout(box_folder)
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("Nenhuma pasta selecionada")
        btn_folder = QPushButton("Selecionar pasta...")
        btn_folder.clicked.connect(self.on_select_folder)
        btn_refresh = QPushButton("Atualizar")
        btn_refresh.clicked.connect(self.on_refresh_folder)
        fl.addWidget(self.folder_edit, 1)
        fl.addWidget(btn_folder)
        fl.addWidget(btn_refresh)
        layout.addWidget(box_folder)

        # 2. Lista de arquivos
        box_files = QGroupBox("2. Arquivos L5X encontrados (marque os que quer processar)")
        vl = QVBoxLayout(box_files)
        self.file_list = QListWidget()
        vl.addWidget(self.file_list)
        row_btns = QHBoxLayout()
        btn_all = QPushButton("Marcar todos")
        btn_all.clicked.connect(lambda: self._set_all_checked(True))
        btn_none = QPushButton("Desmarcar todos")
        btn_none.clicked.connect(lambda: self._set_all_checked(False))
        row_btns.addWidget(btn_all)
        row_btns.addWidget(btn_none)
        row_btns.addStretch(1)
        vl.addLayout(row_btns)
        layout.addWidget(box_files, 1)

        # 3. Opções
        box_opts = QGroupBox("3. Opções")
        ol = QVBoxLayout(box_opts)
        self.chk_infra = QCheckBox("Incluir aba \"Infraestrutura e Outros\" na planilha final")
        self.chk_infra.setChecked(True)
        ol.addWidget(self.chk_infra)
        layout.addWidget(box_opts)

        # 4. Ação
        action_row = QHBoxLayout()
        self.btn_generate = QPushButton("Gerar Lista de IO...")
        self.btn_generate.setMinimumHeight(38)
        self.btn_generate.setProperty("accent", True)
        self.btn_generate.clicked.connect(self.on_generate)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.on_cancel)
        self.btn_open_folder = QPushButton("Abrir pasta de destino")
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self.on_open_folder)
        action_row.addWidget(self.btn_generate, 1)
        action_row.addWidget(self.btn_cancel)
        action_row.addWidget(self.btn_open_folder)
        layout.addLayout(action_row)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # Log
        box_log = QGroupBox("Progresso")
        ll = QVBoxLayout(box_log)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        ll.addWidget(self.log_view)
        layout.addWidget(box_log, 1)

        return root

    def _build_instructions_tab(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml(INSTRUCTIONS_HTML)
        layout.addWidget(text)
        return root

    # ------------------------------------------------------------- ações

    def on_select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta com os arquivos L5X")
        if not folder:
            return
        self.current_folder = folder
        self.folder_edit.setText(folder)
        self._scan_folder()

    def on_refresh_folder(self):
        if self.current_folder:
            self._scan_folder()

    def _scan_folder(self):
        self.file_list.clear()
        folder = Path(self.current_folder)
        files = sorted(
            {p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".l5x"},
            key=lambda p: p.name.lower(),
        )
        if not files:
            self.log_view.append(f"Nenhum arquivo .L5X encontrado em: {folder}")
            return
        for p in files:
            size_mb = p.stat().st_size / (1024 * 1024)
            item = QListWidgetItem(f"{p.name}   ({size_mb:.1f} MB)")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, str(p))
            self.file_list.addItem(item)
        self.log_view.append(f"{len(files)} arquivo(s) .L5X encontrado(s) em: {folder}")

    def _set_all_checked(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.file_list.count()):
            self.file_list.item(i).setCheckState(state)

    def _checked_files(self):
        result = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                path = item.data(Qt.ItemDataRole.UserRole)
                key = Path(path).stem
                result.append((key, path))
        return result

    def on_generate(self):
        files = self._checked_files()
        if not files:
            QMessageBox.warning(self, APP_TITLE, "Selecione uma pasta e marque ao menos um arquivo L5X.")
            return

        default_name = "Lista_IO_Completa.xlsx"
        default_path = str(Path(self.current_folder) / default_name) if self.current_folder else default_name
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar planilha como", default_path, "Excel (*.xlsx)"
        )
        if not out_path:
            return
        if not out_path.lower().endswith(".xlsx"):
            out_path += ".xlsx"

        self.log_view.clear()
        self.progress.setValue(0)
        self.progress.setMaximum(len(files) + 1)
        self.btn_generate.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_open_folder.setEnabled(False)

        self.thread = QThread()
        self.worker = Worker(files, out_path, self.chk_infra.isChecked())
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.log_view.append)
        self.worker.progress.connect(lambda cur, total: self.progress.setValue(cur))
        self.worker.finished.connect(self.on_finished)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_cancel(self):
        if self.worker:
            self.worker.cancel()
            self.log_view.append("Cancelando após a etapa atual...")

    def on_finished(self, success, message, stats):
        self.btn_generate.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        if success:
            self.last_output_path = message
            self.btn_open_folder.setEnabled(True)
            n_conf = stats.get("linhas_conflito", 0)
            aviso_conflito = (
                f"\n\n⚠ {n_conf} linha(s) com CONFLITO de endereço físico encontrada(s) "
                f"— veja a aba \"Conflitos de Endereço\"."
                if n_conf else ""
            )
            QMessageBox.information(
                self, APP_TITLE,
                f"Planilha gerada com sucesso!\n\n{message}\n\n"
                f"Total: {stats.get('total_linhas', 0)} linhas em {stats.get('plcs', 0)} PLC(s)."
                f"{aviso_conflito}"
            )
        else:
            QMessageBox.critical(self, APP_TITLE, f"Não foi possível gerar a planilha:\n\n{message}")

    def on_open_folder(self):
        if self.last_output_path:
            os.startfile(os.path.dirname(self.last_output_path))


INSTRUCTIONS_HTML = """
<h2>Lista de I/O — instruções de uso</h2>

<p>Este programa gera uma planilha Excel com a lista de I/O (entradas e saídas) de PLCs
Rockwell/Allen-Bradley, a partir de arquivos <b>.L5X</b> exportados do Studio 5000 / RSLogix5000.</p>

<h3>O que o programa faz</h3>
<ol>
<li>Lê <b>todos os módulos de rede</b> (I/O remoto) configurados na árvore de I/O de cada arquivo L5X selecionado.</li>
<li>Para cada tag do tipo <i>Alias</i> (que aponta para o endereço físico de um módulo), rastreia
<b>em quais rotinas de programa (RLL)</b> essa tag é referenciada. Alias criados no programa mas nunca
usados em nenhuma rotina são <b>desconsiderados</b> — não representam um sinal realmente em uso.</li>
<li>Determina a estação de cada ponto de I/O pelo nome dessas rotinas
(padrão observado: <code>L022_CIC_OP005T01</code>, <code>L301_READ_OP047T01</code> etc.
— a estação é o trecho final após o último "_", começando com "OP").</li>
<li>Quando não encontra a estação por rotina, usa como alternativa o nome do próprio módulo de rede.</li>
<li>Separa numa aba própria ("Infraestrutura e Outros") tudo que não é uma estação de produção:
racks de segurança, switches Ethernet, HMIs, quadros de comando, links entre controladores, fontes etc.</li>
<li><b>Endereço físico é SEMPRE um endereço de módulo</b>, nunca o nome de uma tag. Em Logix, endereço de
módulo usa <b>dois-pontos</b> (<code>_005T02BM01:I1.Data[0].1</code>); um caminho com <b>ponto</b>
(<code>_005T02BM01.DI01.1</code>) é uma tag de programa — mesmo quando tem o mesmo nome do módulo. Essas
tags são espelhos, preenchidas por COP/CPS/MOV nas rotinas de atualização de entrada/saída ("ATUALIZA" ou
"AGGIORNA"), e o programa calcula o endereço de módulo real a partir dessa cópia, usando a posição do
membro dentro do tipo (UDT). Se não houver cópia que cubra o ponto, a linha fica com "(nao localizado)"
e destacada em amarelo — o nome da tag interna nunca aparece nessa coluna.</li>
</ol>

<h3>Como usar</h3>
<ol>
<li><b>Selecionar pasta:</b> clique em "Selecionar pasta..." e escolha a pasta que contém os arquivos
.L5X dos PLCs que você quer processar (todos os L5X da pasta são listados automaticamente).</li>
<li><b>Marcar os arquivos:</b> desmarque os que não quiser incluir nessa geração (por padrão todos
vêm marcados). Use "Marcar todos" / "Desmarcar todos" para agilizar.</li>
<li><b>Opções:</b> decida se quer incluir a aba "Infraestrutura e Outros" na planilha final.</li>
<li><b>Gerar:</b> clique em "Gerar Lista de IO...", escolha onde salvar o arquivo .xlsx e aguarde —
o progresso de cada arquivo aparece na área de log, junto com o número de módulos/tags encontrados.</li>
<li>Ao concluir, uma mensagem mostra o total de linhas geradas. Use "Abrir pasta de destino" para
localizar o arquivo rapidamente.</li>
</ol>

<h3>Estrutura da planilha gerada</h3>
<ul>
<li><b>Lista Completa</b>: todas as linhas de todos os PLCs processados (estações + infraestrutura).</li>
<li><b>Uma aba por PLC</b> (nome = nome do arquivo L5X, sem a extensão): só as linhas de estação
daquele PLC.</li>
<li><b>Infraestrutura e Outros</b> (se marcada a opção): módulos/tags que não pertencem a uma
estação de produção.</li>
<li><b>Conflitos de Endereço</b> (só aparece se algum conflito for encontrado): todas as linhas em
que duas tags Alias diferentes apontam para o mesmo endereço físico — erro de configuração no PLC.</li>
<li><b>Notas</b>: metodologia completa, explicação de colunas e limitações conhecidas.</li>
</ul>

<h3>Colunas</h3>
<ul>
<li><b>Categoria</b>: "Estacao" ou "Infraestrutura/Outros".</li>
<li><b>Estação</b>: código da estação (ex.: OP005T01). Se houver mais de um separado por " / ",
significa que a mesma tag foi encontrada em rotinas de estações diferentes (caso ambíguo).</li>
<li><b>Módulo (rede)</b>: nome do dispositivo de rede (bloco remoto) na árvore de I/O.</li>
<li><b>Endereço IP</b>: IP Ethernet do módulo, quando aplicável.</li>
<li><b>Tag (alias)</b> / <b>Endereço físico</b>: a tag de programa e o endereço físico ao qual ela aponta.</li>
<li><b>Descrição</b>: descrição cadastrada na tag no Studio 5000.</li>
<li><b>Rotina(s) rastreada(s)</b>: em quais rotinas RLL a tag foi encontrada — auditoria do rastreamento.</li>
<li><b>Conflito</b>: "Sim" quando o Endereço físico dessa linha também é usado por outra tag (duas tags
diferentes no mesmo ponto de I/O — erro de fiação/configuração).</li>
<li><b>Tags conflitantes</b>: nome da(s) outra(s) tag(s) que usam o mesmo Endereço físico desta linha.</li>
</ul>

<h3>Cores</h3>
<ul>
<li><b>Vermelho</b>: conflito de endereço físico — duas tags diferentes apontando para o mesmo ponto
de I/O. Tem prioridade sobre qualquer outro destaque e deve ser revisado no projeto.</li>
<li><b>Amarelo</b>: estação ambígua (múltiplas rotinas) ou inferida só pelo nome do módulo, sem
confirmação por rotina — vale a pena conferir manualmente.</li>
<li><b>Cinza</b>: linhas de infraestrutura/outros.</li>
</ul>

<h3>Limitações conhecidas</h3>
<ul>
<li>O rastreamento por rotina localiza o nome da tag no texto da lógica ladder (RLL) — cobre o caso
de instruções diretas (XIC, OTE, MOV, COP etc.) referenciando a tag pelo nome, que é o padrão do projeto.
Referências indiretas (endereçamento indexado, arrays acessados por variável) não são capturadas.</li>
<li>Arquivos L5X muito grandes (dezenas de MB) podem levar alguns segundos para processar — acompanhe
pelo log.</li>
<li>Os arquivos L5X e os dados neles contidos são informações de cliente: evite compartilhar ou
versionar esses arquivos fora do ambiente de trabalho autorizado.</li>
</ul>
"""
