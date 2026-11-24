"""Select the files, geometries and object types to put on the map."""

from collections import Counter, defaultdict
from pathlib import Path

from qgis.PyQt.QtCore import QSignalBlocker, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)
from qgis.gui import QgsColorButton


ICON_PATH = str(Path(__file__).with_name("icon.png"))
CHECKED = Qt.CheckState.Checked
UNCHECKED = Qt.CheckState.Unchecked


class ImportDialog(QDialog):
    def __init__(self, parent, sources, errors, to_geopackage):
        super().__init__(parent)
        self.setWindowTitle("Vel innhald · SOSI og KOF")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(680, 560)
        self.leaves = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame()
        header.setStyleSheet("QFrame {background:#104744; color:#f4f9f3; border:0;}")
        head = QHBoxLayout(header)
        head.setContentsMargins(18, 12, 20, 12)
        logo = QLabel()
        logo.setPixmap(QIcon(ICON_PATH).pixmap(52, 52))
        head.addWidget(logo)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        titles.addWidget(QLabel("SOSI og KOF"))
        title = QLabel("Vel innhald til GeoPackage" if to_geopackage else "Vel innhald til kartet")
        font = title.font()
        font.setPointSize(15)
        font.setBold(True)
        title.setFont(font)
        titles.addWidget(title)
        head.addLayout(titles, 1)
        outer.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(18, 14, 18, 14)
        body.setSpacing(9)
        outer.addLayout(body, 1)
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Søk etter fil, lag eller objekttype")
        self.search.setAccessibleName("Søk etter fil, lag eller objekttype")
        self.search.setClearButtonEnabled(True)
        tools.addWidget(self.search, 1)
        for label, state in (("Vel synlege", CHECKED), ("Fjern synlege", UNCHECKED)):
            button = QPushButton(label)
            button.setAutoDefault(False)
            button.clicked.connect(lambda _, value=state: self._mark_visible(value))
            tools.addWidget(button)
        body.addLayout(tools)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Fil, lag og objekttype", "Objekt"])
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setUniformRowHeights(True)
        self.tree.setStyleSheet("QTreeView::item {padding:2px 1px;}")
        self.tree.setAlternatingRowColors(True)
        body.addWidget(self.tree, 1)
        filenames = Counter(path.name.casefold() for path in (*sources, *errors))
        for path, source in sources.items():
            name = path.name if filenames[path.name.casefold()] == 1 else str(path)
            root = self._row(self.tree, name, sum(source.counts.values()))
            root.setToolTip(0, str(path))
            font = root.font(0)
            font.setBold(True)
            root.setFont(0, font)
            grouped = defaultdict(list)
            for key, count in sorted(source.counts.items()):
                grouped[key[0]].append((key, count))
            for label, entries in grouped.items():
                group = self._row(root, label, sum(count for _, count in entries))
                for key, count in entries:
                    item = group if key[1] is None else self._row(group, key[1] or "Utan objekttype", count)
                    self.leaves.append((item, path, key, count))
            root.setExpanded(True)
        for path, reason in errors.items():
            item = QTreeWidgetItem(self.tree, [path.name, "Lesefeil"])
            item.setToolTip(0, f"{path}\n{reason}")
            item.setToolTip(1, reason)
            item.setDisabled(True)

        style_row = QHBoxLayout()
        style_label = QLabel("&Kartstil")
        style_row.addWidget(style_label)
        self.style_box = QComboBox()
        style_label.setBuddy(self.style_box)
        for text, value in (("Standard for filtypen", "default"), ("Grått bakgrunnskart", "grey"),
                            ("Eigen farge", "color")):
            self.style_box.addItem(text, value)
        style_row.addWidget(self.style_box)
        self.color_button = QgsColorButton(self)
        self.color_button.setColor(QColor("#176f77"))
        self.color_button.setColorDialogTitle("Vel kartfarge")
        self.color_button.setAccessibleName("Kartfarge")
        self.color_button.setFixedWidth(70)
        self.color_button.hide()
        self.style_box.currentIndexChanged.connect(
            lambda: self.color_button.setVisible(self.style_box.currentData() == "color"))
        style_row.addWidget(self.color_button)
        style_row.addStretch()
        body.addLayout(style_row)
        footer = QHBoxLayout()
        self.total = QLabel()
        footer.addWidget(self.total, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Avbryt")
        self.confirm = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.confirm.setText("Importer valde")
        self.confirm.setStyleSheet(
            "QPushButton:enabled {background:#175f58;color:white;border:0;border-radius:4px;padding:6px 14px;}"
            "QPushButton:hover:enabled {background:#104744;}")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        body.addLayout(footer)
        self.total_timer = QTimer(self)
        self.total_timer.setSingleShot(True)
        self.total_timer.timeout.connect(self._update_total)
        self.tree.itemChanged.connect(lambda: self.total_timer.start(0))
        self.search.textChanged.connect(self._filter)
        self._update_total()

    def _row(self, parent, text, count):
        row = QTreeWidgetItem(parent, [text, f"{count:,}".replace(",", " ")])
        row.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.setFlags(row.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
        row.setCheckState(0, CHECKED)
        return row

    def _filter(self, text):
        query = text.casefold().strip()

        def visit(item, parent_matches=False):
            matches = parent_matches or query in item.text(0).casefold()
            descendant = False
            for index in range(item.childCount()):
                if visit(item.child(index), matches):
                    descendant = True
            item.setHidden(not (matches or descendant))
            if item.childCount():
                item.setExpanded(item.parent() is None or bool(query and descendant))
            return matches or descendant

        for index in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(index))

    def _mark_visible(self, state):
        with QSignalBlocker(self.tree):
            for item, _, _, _ in self.leaves:
                if not item.isHidden():
                    item.setCheckState(0, state)
        self._update_total()

    def selection(self):
        selected = defaultdict(set)
        for item, path, key, _ in self.leaves:
            if item.checkState(0) == CHECKED:
                selected[path].add(key)
        return selected

    def _update_total(self):
        chosen = [(path, key[0], count) for item, path, key, count in self.leaves
                  if item.checkState(0) == CHECKED]
        layers = len({(path, label) for path, label, _ in chosen})
        count = sum(n for _, _, n in chosen)
        self.total.setText(f"Valt · {layers} lag · {count:,} objekt".replace(",", " "))
        self.confirm.setEnabled(bool(chosen))

    def style_color(self):
        mode = self.style_box.currentData()
        if mode == "grey":
            return QColor("#778187")
        if mode == "color":
            return self.color_button.color()
        return None
