"""
GUI Module - Графический интерфейс приложения (PySide6)
"""
import os
from typing import List, Dict

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLineEdit, QComboBox, QLabel, QGroupBox,
    QMessageBox, QFileDialog, QStatusBar, QMenuBar, QMenu,
    QFrame, QSplitter, QSpinBox, QDoubleSpinBox, QDialog, QCheckBox, QDialogButtonBox,
    QProgressBar, QTextEdit, QPlainTextEdit, QInputDialog, QFormLayout
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QPainter, QBrush, QAction, QColor

import csv
import pandas as pd
from PIL import Image
from PIL.ImageQt import ImageQt

from promo_sheets_client import PromoSheetsClient
from config import DARK_THEME, WINDOW_TITLE, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT, WAREHOUSES
from data import DatabaseManager
from image import BackgroundManager
from refstate_repository import RefStateRepository
from refstate_dialog import RefStateProcessDialog
from smartshell_api import (
    create_good_multiple_warehouses,
    create_promocode_multiple_warehouses_v2
)


class AddProductDialog(QDialog):
    """Диалоговое окно добавления товара на несколько точек (в БД)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить товар в БД")
        self.setMinimumWidth(500)
        self.checkboxes = {}

        layout = QVBoxLayout(self)

        title = QLabel("<h3>Добавление нового товара</h3>")
        layout.addWidget(title)

        layout.addWidget(QLabel("Название товара:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Например: Кола 0.5л")
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Поставщик (необязательно):"))
        self.supplier_input = QLineEdit()
        self.supplier_input.setPlaceholderText("Например: Владбир")
        layout.addWidget(self.supplier_input)

        layout.addWidget(QLabel("Начальный остаток:"))
        self.stock_input = QSpinBox()
        self.stock_input.setMinimum(-10000)
        self.stock_input.setMaximum(10000)
        self.stock_input.setValue(0)
        layout.addWidget(self.stock_input)

        layout.addWidget(QLabel("<hr>"))

        points_label = QLabel("<b>Выберите точки для добавления:</b>")
        layout.addWidget(points_label)

        select_buttons = QHBoxLayout()
        select_all_btn = QPushButton("✅ Выбрать все")
        select_all_btn.clicked.connect(self.select_all)
        select_buttons.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("⬜ Снять все")
        deselect_all_btn.clicked.connect(self.deselect_all)
        select_buttons.addWidget(deselect_all_btn)
        select_buttons.addStretch()
        layout.addLayout(select_buttons)

        points_group = QGroupBox("Точки")
        points_layout = QVBoxLayout(points_group)

        for point in WAREHOUSES:
            cb = QCheckBox(point)
            cb.setChecked(True)
            self.checkboxes[point] = cb
            points_layout.addWidget(cb)

        layout.addWidget(points_group)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def select_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(True)

    def deselect_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(False)

    def get_data(self) -> dict:
        selected_points = [name for name, cb in self.checkboxes.items() if cb.isChecked()]
        return {
            "name": self.name_input.text().strip(),
            "supplier": self.supplier_input.text().strip() or None,
            "stock": self.stock_input.value(),
            "points": selected_points
        }


class AddPromoCodeDialog(QDialog):
    """Диалоговое окно создания промокодов в SmartShell (v2) с поддержкой Google Sheets"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Создание промокодов (v2)")
        self.setMinimumWidth(900)
        self.setMinimumHeight(700)
        self.checkboxes = {}
        self.promo_list = []
        self.sheets_client = PromoSheetsClient()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h3>🎟️ Массовое создание промокодов</h3>"))

        # === ПАНЕЛЬ РУЧНОГО ВВОДА ===
        manual_group = QGroupBox("➕ Добавить один промокод вручную")
        manual_layout = QVBoxLayout(manual_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Код *:"))
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("VIP2026")
        row1.addWidget(self.code_input)
        manual_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Тип *:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["BONUS", "DISCOUNT", "DEPOSIT"])
        row2.addWidget(self.type_combo)

        row2.addWidget(QLabel("Значение *:"))
        self.value_input = QSpinBox()
        self.value_input.setMinimum(0)
        self.value_input.setMaximum(9999999)
        self.value_input.setValue(1000)
        row2.addWidget(self.value_input)

        row2.addWidget(QLabel("Активаций:"))
        self.amount_input = QSpinBox()
        self.amount_input.setMinimum(1)
        self.amount_input.setMaximum(99999)
        self.amount_input.setValue(1)
        row2.addWidget(self.amount_input)
        manual_layout.addLayout(row2)

        add_single_btn = QPushButton("➕ Добавить в список")
        add_single_btn.setStyleSheet("QPushButton { background-color: #a6e3a1; color: #1e1e2e; font-weight: bold; }")
        add_single_btn.clicked.connect(self.add_single_to_list)
        manual_layout.addWidget(add_single_btn)

        layout.addWidget(manual_group)

        # === ПАНЕЛЬ ИМПОРТА ===
        import_layout = QHBoxLayout()

        import_sheets_btn = QPushButton("📊 Загрузить из Google Таблицы")
        import_sheets_btn.setStyleSheet("QPushButton { background-color: #89b4fa; color: #1e1e2e; font-weight: bold; padding: 8px; }")
        import_sheets_btn.clicked.connect(self.import_from_google_sheets)
        import_layout.addWidget(import_sheets_btn)

        import_csv_btn = QPushButton("📥 Загрузить из CSV")
        import_csv_btn.setStyleSheet("QPushButton { background-color: #94e2d5; color: #1e1e2e; font-weight: bold; padding: 8px; }")
        import_csv_btn.clicked.connect(self.import_from_csv)
        import_layout.addWidget(import_csv_btn)

        clear_list_btn = QPushButton("🗑️ Очистить список")
        clear_list_btn.setStyleSheet("QPushButton { background-color: #f38ba8; color: #1e1e2e; font-weight: bold; padding: 8px; }")
        clear_list_btn.clicked.connect(self.clear_list)
        import_layout.addWidget(clear_list_btn)

        layout.addLayout(import_layout)

        # === ТАБЛИЦА ПРОМОКОДОВ ===
        self.promo_table = QTableWidget()
        self.promo_table.setColumnCount(5)
        self.promo_table.setHorizontalHeaderLabels(["Код", "Тип", "Значение", "Активаций", "Статус"])
        self.promo_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.promo_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.promo_table)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # === ВЫБОР ТОЧЕК ===
        points_group = QGroupBox("Точки SmartShell (применить ко всем промокодам)")
        points_layout = QVBoxLayout(points_group)
        for point in WAREHOUSES:
            cb = QCheckBox(point)
            cb.setChecked(True)
            self.checkboxes[point] = cb
            points_layout.addWidget(cb)
        layout.addWidget(points_group)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("🚀 Создать все промокоды")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def add_single_to_list(self):
        code = self.code_input.text().strip()
        if not code:
            QMessageBox.warning(self, "Ошибка", "Введите код промокода")
            return

        promo = {
            "code": code,
            "value_type": self.type_combo.currentText(),
            "value_amount": float(self.value_input.value()),
            "amount": self.amount_input.value()
        }
        self.promo_list.append(promo)
        self._refresh_table()
        self.code_input.clear()

    def import_from_google_sheets(self):
        QApplication.processEvents()
        result = self.sheets_client.read_promocodes_from_sheet()

        if result["success"]:
            self.promo_list.extend(result["promocodes"])
            self._refresh_table()

            msg = f"✅ Загружено: {result['total']} промокодов из листа '{self.sheets_client.worksheet_name}'"
            if result["errors"]:
                msg += f"\n\n⚠️ Ошибок: {len(result['errors'])}\n" + "\n".join(result["errors"][:10])
            QMessageBox.information(self, "Импорт из Google Sheets", msg)
        else:
            error_msg = "\n".join(result["errors"])
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные:\n{error_msg}")

    def import_from_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите CSV файл", "", "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return

        try:
            imported_count = 0
            errors = []

            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)

                required_cols = {'code', 'type', 'value'}
                if not required_cols.issubset(set(col.lower() for col in reader.fieldnames or [])):
                    QMessageBox.warning(
                        self, "Ошибка формата",
                        f"В CSV должны быть колонки: code, type, value\n"
                        f"Найдены: {reader.fieldnames}"
                    )
                    return

                for row_num, row in enumerate(reader, start=2):
                    try:
                        code = row.get('code', '').strip()
                        type_val = row.get('type', 'BONUS').strip().upper()
                        value = float(row.get('value', '0').replace(',', '.'))
                        amount = int(row.get('amount', '1').replace(',', '.'))

                        if not code:
                            errors.append(f"Строка {row_num}: пустой код")
                            continue
                        if type_val not in ['BONUS', 'DISCOUNT', 'DEPOSIT']:
                            errors.append(f"Строка {row_num}: неверный тип '{type_val}'")
                            continue

                        self.promo_list.append({
                            "code": code,
                            "value_type": type_val,
                            "value_amount": value,
                            "amount": amount
                        })
                        imported_count += 1
                    except Exception as e:
                        errors.append(f"Строка {row_num}: {str(e)}")

            self._refresh_table()

            msg = f"✅ Импортировано: {imported_count} промокодов"
            if errors:
                msg += f"\n\n⚠️ Ошибок: {len(errors)}\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    msg += f"\n... и ещё {len(errors) - 5}"
            QMessageBox.information(self, "Импорт CSV", msg)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать файл:\n{str(e)}")

    def clear_list(self):
        if self.promo_list and QMessageBox.question(
            self, "Подтверждение", "Очистить весь список промокодов?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.promo_list.clear()
            self._refresh_table()

    def _refresh_table(self):
        self.promo_table.setRowCount(len(self.promo_list))
        for i, promo in enumerate(self.promo_list):
            self.promo_table.setItem(i, 0, QTableWidgetItem(promo["code"]))
            self.promo_table.setItem(i, 1, QTableWidgetItem(promo["value_type"]))
            self.promo_table.setItem(i, 2, QTableWidgetItem(str(promo["value_amount"])))
            self.promo_table.setItem(i, 3, QTableWidgetItem(str(promo["amount"])))
            self.promo_table.setItem(i, 4, QTableWidgetItem("⏳ Ожидает"))

    def get_promo_list(self) -> list:
        selected_points = [name for name, cb in self.checkboxes.items() if cb.isChecked()]
        return self.promo_list, selected_points


class CSVProcessorDialog(QDialog):
    """Диалог обработки промокодов из Google Sheets"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Обработка промокодов из Google Sheets")
        self.setMinimumSize(700, 500)

        self.sheets_client = None
        self.promocodes = []

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<h3>📊 Обработка промокодов из Google Sheets</h3>"))

        self.info_label = QLabel("Нажмите 'Загрузить данные' для подключения к таблице")
        layout.addWidget(self.info_label)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Строка", "Код", "Тип", "Значение", "Активаций", "Статус"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()

        self.load_btn = QPushButton("🔄 Загрузить данные")
        self.load_btn.clicked.connect(self.load_data)
        btn_layout.addWidget(self.load_btn)

        self.process_btn = QPushButton("▶️ Обработать необработанные")
        self.process_btn.clicked.connect(self.process_unprocessed)
        self.process_btn.setEnabled(False)
        btn_layout.addWidget(self.process_btn)

        self.process_all_btn = QPushButton("⚡ Обработать ВСЕ")
        self.process_all_btn.clicked.connect(self.process_all)
        self.process_all_btn.setEnabled(False)
        btn_layout.addWidget(self.process_all_btn)

        btn_layout.addStretch()

        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)

    def log(self, message: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        QApplication.processEvents()

    def load_data(self):
        self.log("Подключение к Google Sheets...")

        try:
            self.sheets_client = PromoSheetsClient()
            success, message, self.promocodes = self.sheets_client.get_all_promocodes()

            if not success:
                self.log(f"❌ {message}")
                QMessageBox.critical(self, "Ошибка", message)
                return

            self.log(f"✅ Загружено {len(self.promocodes)} промокодов")

            self.table.setRowCount(len(self.promocodes))

            for idx, promo in enumerate(self.promocodes):
                self.table.setItem(idx, 0, QTableWidgetItem(str(promo["row"])))
                self.table.setItem(idx, 1, QTableWidgetItem(promo["code"]))
                self.table.setItem(idx, 2, QTableWidgetItem(promo["type"]))
                self.table.setItem(idx, 3, QTableWidgetItem(str(promo["value"])))
                self.table.setItem(idx, 4, QTableWidgetItem(str(promo["amount"])))

                status = "✅ Обработан" if promo["is_processed"] else "⏳ Ожидает"
                status_item = QTableWidgetItem(status)

                if promo["is_processed"]:
                    for col in range(6):
                        self.table.item(idx, col).setBackground(QColor(166, 227, 161))

                self.table.setItem(idx, 5, status_item)

            unprocessed_count = sum(1 for p in self.promocodes if not p["is_processed"])
            self.info_label.setText(f"Всего: {len(self.promocodes)} | Необработанных: {unprocessed_count}")

            self.process_btn.setEnabled(unprocessed_count > 0)
            self.process_all_btn.setEnabled(len(self.promocodes) > 0)

        except Exception as e:
            self.log(f"❌ Ошибка: {str(e)}")
            QMessageBox.critical(self, "Ошибка", str(e))

    def process_unprocessed(self):
        unprocessed = [p for p in self.promocodes if not p["is_processed"]]
        self._process_promocodes(unprocessed)

    def process_all(self):
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Обработать ВСЕ {len(self.promocodes)} промокодов?\n"
            "(Уже обработанные будут созданы повторно)",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._process_promocodes(self.promocodes)

    def _process_promocodes(self, promocodes: List[Dict]):
        if not promocodes:
            self.log("Нет промокодов для обработки")
            return

        parent_dialog = self.parent()
        selected_points = [name for name, cb in parent_dialog.checkboxes.items() if cb.isChecked()]

        if not selected_points:
            QMessageBox.warning(self, "Ошибка", "Выберите хотя бы одну точку в основном диалоге")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(promocodes))
        self.progress_bar.setValue(0)

        success_count = 0
        error_count = 0

        for idx, promo in enumerate(promocodes):
            self.log(f"Обработка: {promo['code']}...")

            result = create_promocode_multiple_warehouses_v2(
                warehouse_names=selected_points,
                code=promo["code"],
                value_type=promo["type"],
                value_amount=promo["value"],
                amount=promo["amount"]
            )

            if result["success"]:
                success_count += len(result["success"])
                self.log(f"✅ {promo['code']}: создано на {len(result['success'])} точках")

                if self.sheets_client:
                    mark_success, mark_msg = self.sheets_client.mark_as_processed(promo["row"])
                    if mark_success:
                        for col in range(6):
                            self.table.item(idx, col).setBackground(QColor(166, 227, 161))
                        self.table.item(idx, 5).setText("✅ Обработан")
                    else:
                        self.log(f"⚠️ Не удалось отметить в таблице: {mark_msg}")
            else:
                error_count += len(result["errors"])
                self.log(f"❌ {promo['code']}: ошибки на {len(result['errors'])} точках")
                for wh, err in result["errors"]:
                    self.log(f"   • {wh}: {err}")

            self.progress_bar.setValue(idx + 1)
            QApplication.processEvents()

        self.progress_bar.setVisible(False)
        self.log(f"\n{'='*60}")
        self.log(f"Итого: ✅ {success_count} успешно | ❌ {error_count} ошибок")
        self.log(f"{'='*60}\n")

        QMessageBox.information(
            self, "Результат",
            f"Обработка завершена!\n\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Ошибок: {error_count}"
        )


class PromoCodeListDialog(QDialog):
    """Диалог просмотра и управления списком промокодов из Google Sheets"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Список промокодов")
        self.setMinimumSize(800, 600)

        self.sheets_client = None
        self.promocodes = []

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<h3>📋 Управление промокодами</h3>"))

        self.info_label = QLabel("Нажмите 'Обновить' для загрузки данных")
        layout.addWidget(self.info_label)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Строка", "Код", "Тип", "Значение", "Активаций", "Статус", "Действия"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_data)
        btn_layout.addWidget(self.refresh_btn)

        btn_layout.addStretch()

        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def load_data(self):
        try:
            self.sheets_client = PromoSheetsClient()
            success, message, self.promocodes = self.sheets_client.get_all_promocodes()

            if not success:
                QMessageBox.critical(self, "Ошибка", message)
                return

            self.table.setRowCount(len(self.promocodes))

            for idx, promo in enumerate(self.promocodes):
                self.table.setItem(idx, 0, QTableWidgetItem(str(promo["row"])))
                self.table.setItem(idx, 1, QTableWidgetItem(promo["code"]))
                self.table.setItem(idx, 2, QTableWidgetItem(promo["type"]))
                self.table.setItem(idx, 3, QTableWidgetItem(str(promo["value"])))
                self.table.setItem(idx, 4, QTableWidgetItem(str(promo["amount"])))

                status = "✅ Обработан" if promo["is_processed"] else "⏳ Ожидает"
                status_item = QTableWidgetItem(status)

                if promo["is_processed"]:
                    for col in range(6):
                        self.table.item(idx, col).setBackground(QColor(166, 227, 161))

                self.table.setItem(idx, 5, status_item)

                delete_btn = QPushButton("🗑️ Удалить")
                delete_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f38ba8;
                        color: #1e1e2e;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #eba0ac;
                    }
                """)
                delete_btn.clicked.connect(lambda checked, row=promo["row"], idx=idx: self.delete_row(row, idx))
                self.table.setCellWidget(idx, 6, delete_btn)

            processed_count = sum(1 for p in self.promocodes if p["is_processed"])
            unprocessed_count = len(self.promocodes) - processed_count
            self.info_label.setText(f"Всего: {len(self.promocodes)} | ✅ Обработанных: {processed_count} | ⏳ Ожидает: {unprocessed_count}")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def delete_row(self, row: int, table_idx: int):
        reply = QMessageBox.question(
            self, "Подтверждение удаления",
            f"Удалить промокод из строки {row}?\n"
            "Данные ниже сдвинутся вверх.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                success, message = self.sheets_client.delete_row(row)
                if success:
                    QMessageBox.information(self, "Успех", f"Строка {row} удалена")
                    self.load_data()
                else:
                    QMessageBox.critical(self, "Ошибка", message)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", str(e))

class AddToSmartShellDialog(QDialog):
    """Диалоговое окно добавления товара в SmartShell"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить товар в SmartShell")
        self.setMinimumWidth(700)
        self.setMinimumHeight(800)
        self.checkboxes = {}

        layout = QVBoxLayout(self)

        # Заголовок
        title = QLabel("<h3>Создание товара в SmartShell</h3>")
        layout.addWidget(title)

        # === ОБЯЗАТЕЛЬНЫЕ ПОЛЯ ===
        mandatory_group = QGroupBox("Обязательные параметры *")
        mandatory_layout = QVBoxLayout(mandatory_group)

        # Название
        mandatory_layout.addWidget(QLabel("Название товара (title) *:"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Например: Кола 0.5л")
        mandatory_layout.addWidget(self.title_input)

        # Стоимость и оптовая стоимость в одну строку
        costs_layout = QHBoxLayout()

        costs_layout.addWidget(QLabel("Стоимость (cost) *:"))
        self.cost_input = QSpinBox()
        self.cost_input.setMinimum(0)
        self.cost_input.setMaximum(999999)
        self.cost_input.setValue(100)
        self.cost_input.setSuffix(" ₽")
        costs_layout.addWidget(self.cost_input)

        costs_layout.addWidget(QLabel("Оптовая (wholesale) *:"))
        self.wholesale_input = QSpinBox()
        self.wholesale_input.setMinimum(0)
        self.wholesale_input.setMaximum(999999)
        self.wholesale_input.setValue(80)
        self.wholesale_input.setSuffix(" ₽")
        costs_layout.addWidget(self.wholesale_input)

        mandatory_layout.addLayout(costs_layout)

        # Глобальные скидки
        self.use_discounts_cb = QCheckBox("Использовать глобальные скидки (use_global_discounts)")
        mandatory_layout.addWidget(self.use_discounts_cb)

        layout.addWidget(mandatory_group)

        # === ДОПОЛНИТЕЛЬНЫЕ ПОЛЯ (раскрывающиеся) ===
        optional_btn = QPushButton("▼ Показать дополнительные параметры")
        optional_btn.setCheckable(True)
        optional_btn.clicked.connect(self.toggle_optional)
        layout.addWidget(optional_btn)

        self.optional_group = QGroupBox("Дополнительные параметры")
        self.optional_group.setVisible(False)
        optional_layout = QVBoxLayout(self.optional_group)

        # Подзаголовок
        optional_layout.addWidget(QLabel("Подзаголовок (subtitle):"))
        self.subtitle_input = QLineEdit()
        optional_layout.addWidget(self.subtitle_input)

        # Комментарий
        optional_layout.addWidget(QLabel("Комментарий (comment):"))
        self.comment_input = QLineEdit()
        optional_layout.addWidget(self.comment_input)

        # Количество и цена
        amount_price_layout = QHBoxLayout()

        amount_price_layout.addWidget(QLabel("Начальный остаток (amount):"))
        self.amount_input = QSpinBox()
        self.amount_input.setMinimum(0)
        self.amount_input.setMaximum(99999)
        self.amount_input.setValue(0)
        amount_price_layout.addWidget(self.amount_input)

        amount_price_layout.addWidget(QLabel("Цена (price):"))
        self.price_input = QSpinBox()
        self.price_input.setMinimum(0)
        self.price_input.setMaximum(999999)
        self.price_input.setValue(0)
        self.price_input.setSuffix(" ₽")
        amount_price_layout.addWidget(self.price_input)

        optional_layout.addLayout(amount_price_layout)

        # Штрих-коды
        optional_layout.addWidget(QLabel("Штрих-коды (eans, через запятую):"))
        self.eans_input = QLineEdit()
        self.eans_input.setPlaceholderText("4600000000001, 4600000000002")
        optional_layout.addWidget(self.eans_input)

        # Чекбоксы
        self.show_in_shell_cb = QCheckBox("Показывать в Shell (show_in_shell)")
        self.show_in_shell_cb.setChecked(True)
        optional_layout.addWidget(self.show_in_shell_cb)

        self.is_excise_cb = QCheckBox("Акцизный товар (is_excise)")
        optional_layout.addWidget(self.is_excise_cb)

        self.use_fair_sign_cb = QCheckBox("Использовать Честный знак (use_fair_sign)")
        optional_layout.addWidget(self.use_fair_sign_cb)

        # Уведомление о низком остатке
        low_stock_layout = QHBoxLayout()
        self.low_stock_cb = QCheckBox("Уведомление о низком остатке")
        low_stock_layout.addWidget(self.low_stock_cb)

        low_stock_layout.addWidget(QLabel("Порог:"))
        self.low_stock_threshold = QSpinBox()
        self.low_stock_threshold.setMinimum(1)
        self.low_stock_threshold.setMaximum(9999)
        self.low_stock_threshold.setValue(5)
        low_stock_layout.addWidget(self.low_stock_threshold)

        optional_layout.addLayout(low_stock_layout)

        layout.addWidget(self.optional_group)

        # === ВЫБОР ТОЧЕК ===
        layout.addWidget(QLabel("<hr>"))
        points_label = QLabel("<b>Выберите точки для создания товара:</b>")
        layout.addWidget(points_label)

        select_buttons = QHBoxLayout()
        select_all_btn = QPushButton("✅ Выбрать все")
        select_all_btn.clicked.connect(self.select_all)
        select_buttons.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("⬜ Снять все")
        deselect_all_btn.clicked.connect(self.deselect_all)
        select_buttons.addWidget(deselect_all_btn)
        select_buttons.addStretch()
        layout.addLayout(select_buttons)

        points_group = QGroupBox("Точки SmartShell")
        points_layout = QVBoxLayout(points_group)

        for point in WAREHOUSES:
            cb = QCheckBox(point)
            cb.setChecked(True)
            self.checkboxes[point] = cb
            points_layout.addWidget(cb)

        layout.addWidget(points_group)

        # Кнопки OK/Cancel
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def toggle_optional(self, checked):
        """Показать/скрыть дополнительные параметры"""
        self.optional_group.setVisible(checked)
        btn = self.sender()
        if checked:
            btn.setText("▲ Скрыть дополнительные параметры")
        else:
            btn.setText("▼ Показать дополнительные параметры")

    def select_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(True)

    def deselect_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(False)

    def get_data(self) -> dict:
        """Возвращает заполненные данные"""
        selected_points = [name for name, cb in self.checkboxes.items() if cb.isChecked()]

        # Парсим штрих-коды
        eans_text = self.eans_input.text().strip()
        eans_list = [ean.strip() for ean in eans_text.split(",") if ean.strip()] if eans_text else None

        return {
            "title": self.title_input.text().strip(),
            "cost": self.cost_input.value(),
            "wholesale_cost": self.wholesale_input.value(),
            "use_global_discounts": self.use_discounts_cb.isChecked(),
            "points": selected_points,
            # Опциональные
            "subtitle": self.subtitle_input.text().strip() or None,
            "comment": self.comment_input.text().strip() or None,
            "amount": self.amount_input.value() if self.amount_input.value() > 0 else None,
            "price": self.price_input.value() if self.price_input.value() > 0 else None,
            "eans": eans_list,
            "show_in_shell": self.show_in_shell_cb.isChecked(),
            "is_excise": self.is_excise_cb.isChecked(),
            "use_fair_sign": self.use_fair_sign_cb.isChecked(),
            "low_stock_enabled": self.low_stock_cb.isChecked(),
            "low_stock_threshold": self.low_stock_threshold.value()
        }

class MainWindow(QMainWindow):
    """Главное окно приложения"""

    def __init__(self):
        super().__init__()

        self.db_manager = DatabaseManager()
        self.bg_manager = BackgroundManager()

        self.gif_timer = QTimer(self)
        self.gif_timer.timeout.connect(self.update_gif_frame)

        self._cached_pixmap = None
        self._cached_size = None

        self.current_products_df = pd.DataFrame()

        self.init_ui()
        self.load_initial_data()

    def init_ui(self):
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(1400, 900)
        self.setStyleSheet(DARK_THEME)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        filter_panel = self.create_filter_panel()
        main_layout.addWidget(filter_panel)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setDocumentMode(True)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        self.create_products_tab()
        self.create_operations_tab()
        self.create_statistics_tab()
        self.create_penalties_tab()
        self.create_invoices_tab()
        self.create_missing_items_tab()
        self.create_refstate_tab()
        main_layout.addWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готово к работе")

        self.create_menu()

    def create_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Файл")

        export_csv = QAction("Экспорт в CSV", self)
        export_csv.triggered.connect(self.export_to_csv)
        file_menu.addAction(export_csv)

        export_excel = QAction("Экспорт в Excel", self)
        export_excel.triggered.connect(self.export_to_excel)
        file_menu.addAction(export_excel)

        file_menu.addSeparator()

        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        bg_menu = menubar.addMenu("Фон")

        load_bg = QAction("Загрузить фон (JPG/GIF)", self)
        load_bg.triggered.connect(self.load_background)
        bg_menu.addAction(load_bg)

        clear_bg = QAction("Очистить фон", self)
        clear_bg.triggered.connect(self.clear_background)
        bg_menu.addAction(clear_bg)

        bg_menu.addSeparator()

        save_default = QAction("Сохранить как дефолтный", self)
        save_default.triggered.connect(self.save_default_background)
        bg_menu.addAction(save_default)

        load_default = QAction("Загрузить дефолтный", self)
        load_default.triggered.connect(self.load_default_background)
        bg_menu.addAction(load_default)

        data_menu = menubar.addMenu("Данные")

        refresh_action = QAction("Обновить данные", self)
        refresh_action.triggered.connect(self.refresh_all_data)
        data_menu.addAction(refresh_action)

        reconnect_action = QAction("Переподключить БД", self)
        reconnect_action.triggered.connect(self.reconnect_database)
        data_menu.addAction(reconnect_action)

        help_menu = menubar.addMenu("Справка")

        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_filter_panel(self) -> QGroupBox:
        group = QGroupBox("Фильтры")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Точка:"))
        self.warehouse_filter = QComboBox()
        self.warehouse_filter.addItem("Все")
        self.warehouse_filter.addItems(WAREHOUSES)
        self.warehouse_filter.setMinimumWidth(150)
        self.warehouse_filter.currentTextChanged.connect(self.apply_filters)
        layout.addWidget(self.warehouse_filter)

        layout.addWidget(QLabel("Поставщик:"))
        self.supplier_filter = QComboBox()
        self.supplier_filter.setMinimumWidth(150)
        self.supplier_filter.currentTextChanged.connect(self.apply_filters)
        layout.addWidget(self.supplier_filter)

        layout.addWidget(QLabel("Остаток от:"))
        self.min_stock_filter = QSpinBox()
        self.min_stock_filter.setMinimum(-10000)
        self.min_stock_filter.setMaximum(10000)
        self.min_stock_filter.setSpecialValueText("—")
        self.min_stock_filter.valueChanged.connect(self.apply_filters)
        layout.addWidget(self.min_stock_filter)

        layout.addWidget(QLabel("до:"))
        self.max_stock_filter = QSpinBox()
        self.max_stock_filter.setMinimum(-10000)
        self.max_stock_filter.setMaximum(10000)
        self.max_stock_filter.setSpecialValueText("—")
        self.max_stock_filter.valueChanged.connect(self.apply_filters)
        layout.addWidget(self.max_stock_filter)

        layout.addWidget(QLabel("Поиск:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите текст для поиска...")
        self.search_input.textChanged.connect(self.apply_filters)
        layout.addWidget(self.search_input)

        reset_btn = QPushButton("Сбросить")
        reset_btn.clicked.connect(self.reset_filters)
        layout.addWidget(reset_btn)

        layout.addStretch()
        return group

    def create_products_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.products_table = QTableWidget()
        self.products_table.setAlternatingRowColors(True)
        self.products_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.products_table.setEditTriggers(QTableWidget.DoubleClicked)
        self.products_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.products_table.horizontalHeader().setStretchLastSection(True)
        self.products_table.verticalHeader().setVisible(False)
        self.products_table.setSortingEnabled(True)

        layout.addWidget(self.products_table)

        actions_layout = QHBoxLayout()

        save_btn = QPushButton("💾 Сохранить изменения")
        save_btn.clicked.connect(self.save_products_changes)
        actions_layout.addWidget(save_btn)

        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.clicked.connect(self.load_products)
        actions_layout.addWidget(refresh_btn)

        add_btn = QPushButton("➕ Добавить товар")
        add_btn.clicked.connect(self.open_add_product_dialog)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e2e;
                font-weight: bold;
                border: 1px solid #40a02b;
            }
            QPushButton:hover {
                background-color: #94d88a;
            }
        """)
        actions_layout.addWidget(add_btn)

        add_shell_btn = QPushButton("☁️ Добавить в SmartShell")
        add_shell_btn.clicked.connect(self.open_add_to_smartshell_dialog)
        add_shell_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-weight: bold;
                border: 1px solid #7287fd;
            }
            QPushButton:hover {
                background-color: #74c7ec;
            }
        """)
        actions_layout.addWidget(add_shell_btn)

        add_promo_btn = QPushButton("🎟️ Создать промокод")
        add_promo_btn.clicked.connect(self.open_add_promocode_dialog)
        add_promo_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9e2af;
                color: #1e1e2e;
                font-weight: bold;
                border: 1px solid #fab387;
            }
            QPushButton:hover {
                background-color: #f5c277;
            }
        """)
        actions_layout.addWidget(add_promo_btn)

        actions_layout.addStretch()

        self.products_stats_label = QLabel("Всего: 0 | Отрицательных: 0 | Нулевых: 0")
        actions_layout.addWidget(self.products_stats_label)

        layout.addLayout(actions_layout)
        self.tabs.addTab(tab, "📦 Товары")

    def create_operations_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        ops_filter_layout = QHBoxLayout()
        ops_filter_layout.addWidget(QLabel("Тип операции:"))
        self.operation_type_filter = QComboBox()
        self.operation_type_filter.addItem("Все")
        self.operation_type_filter.addItems([
            "взял", "пришёл", "взял_периферию",
            "пришла_периферию", "убрал_периферию"
        ])
        self.operation_type_filter.currentTextChanged.connect(self.load_operations)
        ops_filter_layout.addWidget(self.operation_type_filter)
        ops_filter_layout.addStretch()
        layout.addLayout(ops_filter_layout)

        self.operations_table = QTableWidget()
        self.operations_table.setAlternatingRowColors(True)
        self.operations_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.operations_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.operations_table.verticalHeader().setVisible(False)
        self.operations_table.setSortingEnabled(True)

        layout.addWidget(self.operations_table)
        self.tabs.addTab(tab, "📋 Операции")

    def create_statistics_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        splitter = QSplitter(Qt.Vertical)

        warehouse_group = QGroupBox("Статистика по точкам")
        warehouse_layout = QVBoxLayout(warehouse_group)
        self.warehouse_stats_table = QTableWidget()
        self.warehouse_stats_table.setAlternatingRowColors(True)
        self.warehouse_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        warehouse_layout.addWidget(self.warehouse_stats_table)
        splitter.addWidget(warehouse_group)

        supplier_group = QGroupBox("Статистика по поставщикам")
        supplier_layout = QVBoxLayout(supplier_group)
        self.supplier_stats_table = QTableWidget()
        self.supplier_stats_table.setAlternatingRowColors(True)
        self.supplier_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        supplier_layout.addWidget(self.supplier_stats_table)
        splitter.addWidget(supplier_group)

        layout.addWidget(splitter)
        self.tabs.addTab(tab, "📊 Статистика")

    def create_penalties_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.penalties_table = QTableWidget()
        self.penalties_table.setAlternatingRowColors(True)
        self.penalties_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.penalties_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.penalties_table.verticalHeader().setVisible(False)
        self.penalties_table.setSortingEnabled(True)
        layout.addWidget(self.penalties_table)
        self.tabs.addTab(tab, "⚠️ Штрафы")

    def create_invoices_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        header = QLabel("<h3>📄 Переданные фактуры</h3>")
        layout.addWidget(header)

        hint = QLabel(
            "Список фактур, которые были обработаны и переданы в систему.\n"
            "Данные берутся из таблицы <b>processed_invoices</b>."
        )
        hint.setStyleSheet("color: #a6adc8;")
        layout.addWidget(hint)

        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Дата с:"))
        self.invoice_date_from = QLineEdit()
        self.invoice_date_from.setPlaceholderText("ГГГГ-ММ-ДД")
        self.invoice_date_from.setMaximumWidth(120)
        filter_layout.addWidget(self.invoice_date_from)

        filter_layout.addWidget(QLabel("по:"))
        self.invoice_date_to = QLineEdit()
        self.invoice_date_to.setPlaceholderText("ГГГГ-ММ-ДД")
        self.invoice_date_to.setMaximumWidth(120)
        filter_layout.addWidget(self.invoice_date_to)

        filter_layout.addWidget(QLabel("Поиск по номеру:"))
        self.invoice_search = QLineEdit()
        self.invoice_search.setPlaceholderText("Номер фактуры...")
        self.invoice_search.setMaximumWidth(200)
        filter_layout.addWidget(self.invoice_search)

        apply_btn = QPushButton("🔍 Применить")
        apply_btn.clicked.connect(self.load_invoices)
        filter_layout.addWidget(apply_btn)

        reset_btn = QPushButton("🔄 Сбросить")
        reset_btn.clicked.connect(self.reset_invoices_filters)
        filter_layout.addWidget(reset_btn)

        reload_btn = QPushButton("⚡ Перечитать из БД")
        reload_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9e2af;
                color: #1e1e2e;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #f5d78e; }
        """)
        reload_btn.clicked.connect(self.reload_invoices_from_db)
        filter_layout.addWidget(reload_btn)

        filter_layout.addStretch()

        self.invoices_stats_label = QLabel("Всего: 0")
        filter_layout.addWidget(self.invoices_stats_label)

        layout.addLayout(filter_layout)

        self.invoices_table = QTableWidget()
        self.invoices_table.setAlternatingRowColors(True)
        self.invoices_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.invoices_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.invoices_table.verticalHeader().setVisible(False)
        self.invoices_table.setSortingEnabled(True)
        layout.addWidget(self.invoices_table)

        self.tabs.addTab(tab, "📄 Переданные фактуры")

    def reset_invoices_filters(self):
        self.invoice_date_from.clear()
        self.invoice_date_to.clear()
        self.invoice_search.clear()
        self.load_invoices()

    def reload_invoices_from_db(self):
        self.invoice_date_from.clear()
        self.invoice_date_to.clear()
        self.invoice_search.clear()

        if not self.db_manager.connection or not self.db_manager.connection.open:
            self.db_manager.reconnect()

        self.load_invoices()
        self.status_bar.showMessage("✅ Фактуры перечитаны из БД")

    def create_missing_items_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.missing_items_table = QTableWidget()
        self.missing_items_table.setAlternatingRowColors(True)
        self.missing_items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.missing_items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.missing_items_table.verticalHeader().setVisible(False)
        layout.addWidget(self.missing_items_table)
        self.tabs.addTab(tab, "❓ Нет в SmartShell")

    # === ЗАГРУЗКА ДАННЫХ ===

    def load_initial_data(self):
        self.status_bar.showMessage("Загрузка данных...")
        suppliers = self.db_manager.get_unique_suppliers()
        self.supplier_filter.blockSignals(True)
        self.supplier_filter.clear()
        self.supplier_filter.addItems(suppliers)
        self.supplier_filter.blockSignals(False)

        self.load_products()
        self.load_operations()
        self.load_statistics()
        self.load_penalties()
        self.load_invoices()
        self.load_missing_items()
        self.status_bar.showMessage("Данные загружены")

    def on_tab_changed(self, index):
        if index == 0:
            self.load_products()
        elif index == 1:
            self.load_operations()
        elif index == 2:
            self.load_statistics()
        elif index == 3:
            self.load_penalties()
        elif index == 4:
            self.load_invoices()
        elif index == 5:
            self.load_missing_items()
        elif index == 6:
            self.load_refstate_admins()

    def load_products(self):
        warehouse = self.warehouse_filter.currentText()
        supplier = self.supplier_filter.currentText()
        min_stock = self.min_stock_filter.value() if self.min_stock_filter.value() != 0 else None
        max_stock = self.max_stock_filter.value() if self.max_stock_filter.value() != 0 else None
        search_text = self.search_input.text()

        df = self.db_manager.get_all_products(
            warehouse=warehouse,
            supplier=supplier,
            min_stock=min_stock,
            max_stock=max_stock,
            search_text=search_text
        )

        self.current_products_df = df
        self.display_products_table(df)

    def load_operations(self):
        warehouse = self.warehouse_filter.currentText()
        operation_type = self.operation_type_filter.currentText()
        search_text = self.search_input.text()
        df = self.db_manager.get_operations(
            warehouse=warehouse,
            operation_type=operation_type,
            search_text=search_text
        )
        self.display_table(self.operations_table, df)

    def load_statistics(self):
        warehouse_stats = self.db_manager.get_warehouse_stats()
        self.display_table(self.warehouse_stats_table, warehouse_stats)
        supplier_stats = self.db_manager.get_supplier_stats()
        self.display_table(self.supplier_stats_table, supplier_stats)

    def load_penalties(self):
        df = self.db_manager.get_penalties()
        self.display_table(self.penalties_table, df)

    def load_invoices(self):
        date_from = self.invoice_date_from.text().strip() or None
        date_to = self.invoice_date_to.text().strip() or None
        search_text = self.invoice_search.text().strip() or None

        df = self.db_manager.get_processed_invoices(
            date_from=date_from,
            date_to=date_to,
            search_text=search_text
        )

        total = len(df)
        self.invoices_stats_label.setText(f"Всего: {total}")

        self.display_table(self.invoices_table, df)

    def load_missing_items(self):
        df = self.db_manager.get_missing_smartshell_items()
        self.display_table(self.missing_items_table, df)

    # === ОТОБРАЖЕНИЕ ===

    def display_products_table(self, df: pd.DataFrame):
        self.products_table.setSortingEnabled(False)

        if df.empty:
            self.products_table.setRowCount(0)
            self.products_stats_label.setText("Нет данных")
            self.products_table.setSortingEnabled(True)
            return

        self.products_table.setRowCount(len(df))
        self.products_table.setColumnCount(len(df.columns))
        self.products_table.setHorizontalHeaderLabels(df.columns)

        for row_idx, row in df.iterrows():
            for col_idx, (col_name, value) in enumerate(row.items()):
                item = QTableWidgetItem(str(value))

                if col_name == "stock":
                    try:
                        stock_val = int(value) if value is not None else 0
                        if stock_val < 0:
                            item.setBackground(QBrush(QColor(255, 100, 100, 100)))
                            item.setForeground(QBrush(QColor(255, 200, 200)))
                        elif stock_val == 0:
                            item.setBackground(QBrush(QColor(255, 200, 0, 80)))
                    except (ValueError, TypeError):
                        pass

                self.products_table.setItem(row_idx, col_idx, item)

        if not df.empty and "stock" in df.columns:
            total = len(df)
            negative = len(df[df["stock"] < 0])
            zero = len(df[df["stock"] == 0])
            self.products_stats_label.setText(
                f"Всего: {total} | Отрицательных: {negative} | Нулевых: {zero}"
            )

        self.products_table.setSortingEnabled(True)

    def display_table(self, table: QTableWidget, df: pd.DataFrame):
        table.setSortingEnabled(False)

        table.clear()
        table.setRowCount(0)

        if df.empty:
            table.setSortingEnabled(True)
            return

        df = df.reset_index(drop=True)

        table.setRowCount(len(df))
        table.setColumnCount(len(df.columns))
        table.setHorizontalHeaderLabels(df.columns)

        for row_idx, (_, row) in enumerate(df.iterrows()):
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                table.setItem(row_idx, col_idx, item)

        table.setSortingEnabled(True)

    def apply_filters(self):
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:
            self.load_products()
        elif current_tab == 1:
            self.load_operations()

    def reset_filters(self):
        self.warehouse_filter.blockSignals(True)
        self.supplier_filter.blockSignals(True)
        self.min_stock_filter.blockSignals(True)
        self.max_stock_filter.blockSignals(True)
        self.search_input.blockSignals(True)
        self.operation_type_filter.blockSignals(True)

        self.warehouse_filter.setCurrentIndex(0)
        self.supplier_filter.setCurrentIndex(0)
        self.min_stock_filter.setValue(0)
        self.max_stock_filter.setValue(0)
        self.search_input.clear()
        self.operation_type_filter.setCurrentIndex(0)

        self.warehouse_filter.blockSignals(False)
        self.supplier_filter.blockSignals(False)
        self.min_stock_filter.blockSignals(False)
        self.max_stock_filter.blockSignals(False)
        self.search_input.blockSignals(False)
        self.operation_type_filter.blockSignals(False)

        self.apply_filters()

    # === СОХРАНЕНИЕ ИЗМЕНЕНИЙ В БД ===

    def save_products_changes(self):
        changes = []
        headers = []
        for i in range(self.products_table.columnCount()):
            header_item = self.products_table.horizontalHeaderItem(i)
            if header_item:
                headers.append(header_item.text())

        try:
            id_col = headers.index("id")
            stock_col = headers.index("stock")
            name_col = headers.index("name")
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Не найдены нужные колонки")
            return

        original_stocks = {}
        if not self.current_products_df.empty and "id" in self.current_products_df.columns:
            for _, row in self.current_products_df.iterrows():
                original_stocks[row["id"]] = row.get("stock", 0)

        for row in range(self.products_table.rowCount()):
            id_item = self.products_table.item(row, id_col)
            stock_item = self.products_table.item(row, stock_col)
            name_item = self.products_table.item(row, name_col)

            if id_item and stock_item:
                try:
                    product_id = int(id_item.text())
                    new_stock = int(stock_item.text())
                    old_stock = original_stocks.get(product_id, 0)

                    if new_stock != old_stock:
                        changes.append({
                            "id": product_id,
                            "new_stock": new_stock,
                            "name": name_item.text() if name_item else "—"
                        })
                except (ValueError, TypeError):
                    continue

        if not changes:
            QMessageBox.information(self, "Информация", "Нет изменений для сохранения")
            return

        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Сохранить {len(changes)} изменений остатков?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success_count = 0
            for change in changes:
                if self.db_manager.update_product_stock(change["id"], change["new_stock"]):
                    success_count += 1

            QMessageBox.information(
                self, "Результат",
                f"✅ Сохранено: {success_count} из {len(changes)}"
            )
            self.load_products()

    # === ДОБАВЛЕНИЕ В БД ===

    def open_add_product_dialog(self):
        dialog = AddProductDialog(self)

        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()

            if not data["name"]:
                QMessageBox.warning(self, "Ошибка", "Введите название товара")
                return

            if not data["points"]:
                QMessageBox.warning(self, "Ошибка", "Выберите хотя бы одну точку")
                return

            points_list = "\n".join([f"• {p}" for p in data["points"]])
            confirm_msg = (
                f"Добавить товар <b>{data['name']}</b> на {len(data['points'])} точек?\n\n"
                f"📦 Точки:\n{points_list}\n\n"
                f"📊 Начальный остаток: {data['stock']}\n"
            )
            if data["supplier"]:
                confirm_msg += f"🏭 Поставщик: {data['supplier']}"

            reply = QMessageBox.question(
                self, "Подтверждение", confirm_msg,
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            try:
                wh_names = ", ".join(["%s"] * len(data["points"]))
                query = f"SELECT id, name FROM warehouses WHERE name IN ({wh_names})"
                rows = self.db_manager.execute_query(query, tuple(data["points"]))
                wh_ids = [row["id"] for row in rows]
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось получить ID точек: {e}")
                return

            self.status_bar.showMessage("Добавление товара...")
            result = self.db_manager.add_product_to_warehouses(
                product_name=data["name"],
                warehouse_ids=wh_ids,
                supplier=data["supplier"],
                initial_stock=data["stock"]
            )

            report = []
            if result["success"]:
                report.append(f"✅ Добавлено на {len(result['success'])} точек:\n" +
                            "\n".join([f"   • {p}" for p in result["success"]]))
            if result["skipped"]:
                report.append(f"⚠️ Уже существует ({len(result['skipped'])}):\n" +
                            "\n".join([f"   • {p}" for p in result["skipped"]]))
            if result["errors"]:
                report.append(f"❌ Ошибки ({len(result['errors'])}):\n" +
                            "\n".join([f"   • {e}" for e in result["errors"]]))

            QMessageBox.information(self, "Результат добавления", "\n\n".join(report))
            self.load_initial_data()
            self.status_bar.showMessage(f"Добавлено: {len(result['success'])} товаров")

    # === ДОБАВЛЕНИЕ В SMARTSHELL ===

    def open_add_to_smartshell_dialog(self):
        """Открывает диалог добавления товара в SmartShell"""
        dialog = AddToSmartShellDialog(self)

        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()

            if not data["title"]:
                QMessageBox.warning(self, "Ошибка", "Введите название товара (title)")
                return

            if not data["points"]:
                QMessageBox.warning(self, "Ошибка", "Выберите хотя бы одну точку")
                return

            points_list = "\n".join([f"• {p}" for p in data["points"]])
            confirm_msg = (
                f"Создать товар <b>{data['title']}</b> в SmartShell?\n\n"
                f"🏪 Точки ({len(data['points'])}): \n{points_list}\n\n"
                f"💰 Стоимость: {data['cost']} ₽\n"
                f"📦 Оптовая: {data['wholesale_cost']} ₽\n"
            )

            if data["amount"]:
                confirm_msg += f"📊 Начальный остаток: {data['amount']}\n"
            if data["eans"]:
                confirm_msg += f"🏷️ Штрих-коды: {', '.join(data['eans'])}\n"

            reply = QMessageBox.question(
                self, "Подтверждение", confirm_msg,
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            self.status_bar.showMessage("Создание товара в SmartShell...")

            kwargs = {}
            if data["subtitle"]:
                kwargs["subtitle"] = data["subtitle"]
            if data["comment"]:
                kwargs["comment"] = data["comment"]
            if data["amount"]:
                kwargs["amount"] = data["amount"]
            if data["price"]:
                kwargs["price"] = data["price"]
            if data["eans"]:
                kwargs["eans"] = data["eans"]
            if data["show_in_shell"] is not None:
                kwargs["show_in_shell"] = data["show_in_shell"]
            if data["is_excise"]:
                kwargs["is_excise"] = data["is_excise"]
            if data["use_fair_sign"]:
                kwargs["use_fair_sign"] = data["use_fair_sign"]
            if data["low_stock_enabled"]:
                kwargs["low_stock_enabled"] = data["low_stock_enabled"]
                kwargs["low_stock_threshold"] = data["low_stock_threshold"]

            result = create_good_multiple_warehouses(
                warehouse_names=data["points"],
                title=data["title"],
                cost=data["cost"],
                wholesale_cost=data["wholesale_cost"],
                use_global_discounts=data["use_global_discounts"],
                **kwargs
            )

            report = []
            if result["success"]:
                report.append(f"✅ Создано на {len(result['success'])} точках:\n" +
                            "\n".join([f"   • {wh} (ID: {gid})" for wh, gid in result["success"]]))
            if result["errors"]:
                report.append(f"❌ Ошибки ({len(result['errors'])}):\n" +
                            "\n".join([f"   • {wh}: {err}" for wh, err in result["errors"]]))

            QMessageBox.information(self, "Результат создания", "\n\n".join(report))

            success_count = len(result["success"])
            self.status_bar.showMessage(f"Создано в SmartShell: {success_count} товаров")

    def open_add_promocode_dialog(self):
        """Открывает диалог массового создания промокодов с поддержкой Google Sheets"""
        dialog = AddPromoCodeDialog(self)

        if dialog.exec() == QDialog.Accepted:
            promo_list, selected_points = dialog.get_promo_list()

            if not promo_list:
                QMessageBox.warning(self, "Ошибка", "Список промокодов пуст. Добавьте вручную или загрузите из Google Sheets.")
                return

            if not selected_points:
                QMessageBox.warning(self, "Ошибка", "Выберите хотя бы одну точку")
                return

            points_list = "\n".join([f"• {p}" for p in selected_points])
            confirm_msg = (
                f"Создать <b>{len(promo_list)}</b> промокодов в SmartShell?\n\n"
                f"🏪 Точки ({len(selected_points)}): \n{points_list}\n\n"
                f"Промокоды будут действовать в BILLING, MOBILE_APP, SHELL.\n"
                f"После создания ячейки в Google Sheets будут помечены зелёным."
            )

            reply = QMessageBox.question(
                self, "Подтверждение", confirm_msg,
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            self.status_bar.showMessage(f"Создание {len(promo_list)} промокодов...")
            QApplication.processEvents()

            progress_dialog = QDialog(self)
            progress_dialog.setWindowTitle("Создание промокодов")
            progress_dialog.setMinimumWidth(600)
            progress_dialog.setMinimumHeight(400)
            progress_layout = QVBoxLayout(progress_dialog)

            progress_label = QLabel(f"Создано 0 из {len(promo_list)}")
            progress_layout.addWidget(progress_label)

            progress_bar = QProgressBar()
            progress_bar.setMaximum(len(promo_list))
            progress_bar.setValue(0)
            progress_layout.addWidget(progress_bar)

            log_text = QPlainTextEdit()
            log_text.setReadOnly(True)
            progress_layout.addWidget(log_text)

            progress_dialog.show()

            total_success = 0
            total_errors = 0

            sheets_client = PromoSheetsClient()
            worksheet_name = getattr(dialog, 'current_worksheet_name', None)

            for i, promo in enumerate(promo_list):
                progress_label.setText(f"Создание {i+1} из {len(promo_list)}: {promo['code']}...")
                progress_bar.setValue(i)
                QApplication.processEvents()

                result = create_promocode_multiple_warehouses_v2(
                    warehouse_names=selected_points,
                    code=promo["code"],
                    value_type=promo["value_type"],
                    value_amount=promo["value_amount"],
                    amount=promo["amount"]
                )

                if result["success"]:
                    total_success += len(result["success"])
                    log_text.appendPlainText(f"✅ {promo['code']}: создано на {len(result['success'])} точках")

                    if "row" in promo:
                        if sheets_client.mark_cell_green(promo["row"], column="A", worksheet_name=worksheet_name):
                            log_text.appendPlainText(f"   🟢 Ячейка A{promo['row']} помечена зелёным")
                        else:
                            log_text.appendPlainText(f"   ⚠️ Не удалось пометить ячейку A{promo['row']}")
                if result["errors"]:
                    total_errors += len(result["errors"])
                    for wh, err in result["errors"]:
                        log_text.appendPlainText(f"❌ {promo['code']} ({wh}): {err}")

            progress_bar.setValue(len(promo_list))
            progress_label.setText("✅ Готово!")

            QMessageBox.information(
                self, "Результат",
                f"Успешно создано: {total_success}\nОшибок: {total_errors}\n\n"
                f"Ячейки успешно созданных промокодов помечены зелёным в Google Sheets."
            )
            self.status_bar.showMessage("Готово", 3000)

    # === ФОНОВЫЕ ИЗОБРАЖЕНИЯ ===

    def load_background(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите фоновое изображение", "",
            "Изображения (*.jpg *.jpeg *.png *.gif)"
        )

        if file_path:
            success, message = self.bg_manager.load_background(file_path)

            if success:
                self.status_bar.showMessage(message)
                self._cached_pixmap = None
                self._cached_size = None

                if self.bg_manager.is_gif:
                    self.gif_timer.start(150)
                else:
                    self.gif_timer.stop()

                self.update()
            else:
                QMessageBox.warning(self, "Ошибка", message)

    def clear_background(self):
        self.bg_manager.clear_background()
        self.gif_timer.stop()
        self._cached_pixmap = None
        self._cached_size = None
        self.update()
        self.status_bar.showMessage("Фон очищен")

    def save_default_background(self):
        success, message = self.bg_manager.save_as_default()
        if success:
            QMessageBox.information(self, "Успех", message)
        else:
            QMessageBox.warning(self, "Ошибка", message)

    def load_default_background(self):
        success, message = self.bg_manager.load_default()
        if success:
            self.status_bar.showMessage(message)
            self._cached_pixmap = None
            self._cached_size = None

            if self.bg_manager.is_gif:
                self.gif_timer.start(150)
            else:
                self.gif_timer.stop()
            self.update()
        else:
            QMessageBox.warning(self, "Ошибка", message)

    def update_gif_frame(self):
        if self.bg_manager.next_frame():
            self._cached_pixmap = None
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        bg_path = self.bg_manager.get_background_path()
        if not bg_path:
            return

        current_size = self.size()

        if (self._cached_pixmap is not None and
            self._cached_size == current_size and
            not self.bg_manager.is_gif):
            pixmap = self._cached_pixmap
        else:
            if self.bg_manager.is_gif:
                frame = self.bg_manager.get_current_frame()
                if frame:
                    try:
                        qimage = ImageQt(frame.copy())
                        pixmap = QPixmap.fromImage(qimage)
                    except Exception as e:
                        print(f"⚠️ Ошибка конвертации GIF кадра: {e}")
                        return
                else:
                    return
            else:
                pixmap = QPixmap(bg_path)

            if pixmap.isNull():
                return

            pixmap = pixmap.scaled(
                current_size,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )

            if not self.bg_manager.is_gif:
                self._cached_pixmap = pixmap
                self._cached_size = current_size

        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        x = (self.width() - pixmap.width()) // 2
        y = (self.height() - pixmap.height()) // 2

        painter.setOpacity(0.15)
        painter.drawPixmap(x, y, pixmap)
        painter.end()

    # === ЭКСПОРТ ===

    def get_current_table_df(self) -> pd.DataFrame:
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:
            return self.current_products_df
        elif current_tab == 1:
            return self.db_manager.get_operations(
                warehouse=self.warehouse_filter.currentText(),
                operation_type=self.operation_type_filter.currentText(),
                search_text=self.search_input.text()
            )
        elif current_tab == 3:
            return self.db_manager.get_penalties()
        elif current_tab == 4:
            return self.db_manager.get_processed_invoices()
        elif current_tab == 5:
            return self.db_manager.get_missing_smartshell_items()
        return pd.DataFrame()

    def export_to_csv(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в CSV", "", "CSV файлы (*.csv)"
        )
        if file_path:
            df = self.get_current_table_df()
            if df.empty:
                QMessageBox.warning(self, "Ошибка", "Нет данных для экспорта")
                return
            try:
                df.to_csv(file_path, index=False, encoding="utf-8-sig")
                QMessageBox.information(self, "Успех", f"Экспортировано в {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось экспортировать: {e}")

    def export_to_excel(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в Excel", "", "Excel файлы (*.xlsx)"
        )
        if file_path:
            df = self.get_current_table_df()
            if df.empty:
                QMessageBox.warning(self, "Ошибка", "Нет данных для экспорта")
                return
            try:
                df.to_excel(file_path, index=False, engine="openpyxl")
                QMessageBox.information(self, "Успех", f"Экспортировано в {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось экспортировать: {e}")

    # === ОБНОВЛЕНИЕ ===

    def refresh_all_data(self):
        self.status_bar.showMessage("Обновление данных...")
        self.load_initial_data()
        self.status_bar.showMessage("Данные обновлены")

    def reconnect_database(self):
        if self.db_manager.reconnect():
            QMessageBox.information(self, "Успех", "Подключение восстановлено")
            self.refresh_all_data()
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось подключиться к базе данных")

    def show_about(self):
        QMessageBox.about(
            self, "О программе",
            "<h2>CyberMG - Система учёта склада</h2>"
            "<p><b>Версия 1.1</b></p>"
            "<p>Десктопное приложение для управления складским учётом</p>"
            "<p><b>Возможности:</b></p>"
            "<ul>"
            "<li>Просмотр и редактирование товаров</li>"
            "<li>Массовое добавление товаров в БД</li>"
            "<li>Массовое создание товаров в SmartShell</li>"
            "<li>Журнал операций</li>"
            "<li>Статистика по точкам и поставщикам</li>"
            "<li>Гибкая система фильтров и сортировки</li>"
            "<li>Экспорт в CSV/Excel</li>"
            "<li>Поддержка фоновых изображений (JPG/GIF)</li>"
            "</ul>"
            "<p>© 2026 CyberMG</p>"
        )

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Вы уверены, что хотите выйти?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db_manager.disconnect()
            self.gif_timer.stop()
            event.accept()
        else:
            event.ignore()

    def create_refstate_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        header = QLabel("<h3>📋 Проверка расхождений администраторов</h3>")
        layout.addWidget(header)

        hint = QLabel(
            "Выберите администратора и нажмите 'Начать обработку'. "
            "Перед обработкой рекомендуется создать бэкап."
        )
        hint.setStyleSheet("color: #a6adc8;")
        layout.addWidget(hint)

        controls_layout = QHBoxLayout()

        controls_layout.addWidget(QLabel("Администратор:"))
        self.refstate_admin_combo = QComboBox()
        self.refstate_admin_combo.setMinimumWidth(250)
        controls_layout.addWidget(self.refstate_admin_combo)

        self.refstate_refresh_btn = QPushButton("🔄 Обновить список")
        self.refstate_refresh_btn.clicked.connect(self.load_refstate_admins)
        controls_layout.addWidget(self.refstate_refresh_btn)

        controls_layout.addStretch()

        self.refstate_backup_btn = QPushButton("💾 Бэкап БД")
        self.refstate_backup_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9e2af;
                color: #1e1e2e;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #f5d78e; }
        """)
        self.refstate_backup_btn.clicked.connect(self.create_refstate_backup)
        controls_layout.addWidget(self.refstate_backup_btn)

        self.refstate_process_btn = QPushButton("▶️ Начать обработку")
        self.refstate_process_btn.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e2e;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton:hover { background-color: #94d88a; }
        """)
        self.refstate_process_btn.clicked.connect(self.start_refstate_processing)
        controls_layout.addWidget(self.refstate_process_btn)

        layout.addLayout(controls_layout)

        self.refstate_table = QTableWidget()
        self.refstate_table.setAlternatingRowColors(True)
        self.refstate_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.refstate_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.refstate_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.refstate_table.verticalHeader().setVisible(False)
        layout.addWidget(self.refstate_table)

        self.refstate_stats_label = QLabel("Всего записей: 0 | Администраторов: 0 | Сумма: 0.00₽")
        layout.addWidget(self.refstate_stats_label)

        self.tabs.addTab(tab, "🔍 Проверка расхождений")

    # === REFSTATE: ЗАГРУЗКА И ОБРАБОТКА ===

    def load_refstate_admins(self):
        repo = RefStateRepository()

        if not repo.connect():
            QMessageBox.critical(self, "Ошибка", "Не удалось подключиться к базе данных")
            return

        admins = repo.get_administrators_summary()
        stats = repo.get_total_stats()

        self.refstate_admin_combo.blockSignals(True)
        self.refstate_admin_combo.clear()
        for admin in admins:
            self.refstate_admin_combo.addItem(
                f"{admin['administrator']} ({admin['records_count']} записей)"
            )
        self.refstate_admin_combo.blockSignals(False)

        self.refstate_table.setRowCount(len(admins))
        self.refstate_table.setColumnCount(4)
        self.refstate_table.setHorizontalHeaderLabels(
            ["Администратор", "Записей", "Сумма", "Последняя запись"]
        )

        for row_idx, admin in enumerate(admins):
            self.refstate_table.setItem(row_idx, 0, QTableWidgetItem(admin["administrator"]))
            self.refstate_table.setItem(row_idx, 1, QTableWidgetItem(str(admin["records_count"])))
            self.refstate_table.setItem(row_idx, 2, QTableWidgetItem(f"{admin['total_value']:.2f}₽"))
            last_created = admin["last_created"].strftime("%d.%m.%Y %H:%M") if admin["last_created"] else "—"
            self.refstate_table.setItem(row_idx, 3, QTableWidgetItem(last_created))

        self.refstate_table.resizeColumnsToContents()

        self.refstate_stats_label.setText(
            f"Всего записей: {stats['total_records']} | "
            f"Администраторов: {stats['total_admins']} | "
            f"Сумма: {stats['total_value']:.2f}₽"
        )

        repo.disconnect()

    def start_refstate_processing(self):
        current_text = self.refstate_admin_combo.currentText()
        if not current_text:
            QMessageBox.warning(self, "Ошибка", "Выберите администратора из списка")
            return

        administrator = current_text.split(" (")[0].strip()

        reply = QMessageBox.question(
            self,
            "Подтверждение обработки",
            f"Начать обработку записей администратора:\n"
            f"<b>{administrator}</b>?\n\n"
            f"Рекомендуется создать бэкап перед обработкой.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        dialog = RefStateProcessDialog(administrator, parent=self)
        dialog.exec()

        self.load_refstate_admins()

    def create_refstate_backup(self):
        repo = RefStateRepository()

        if not repo.connect():
            QMessageBox.critical(self, "Ошибка", "Не удалось подключиться к базе данных")
            return

        result = repo.backup_table()

        if result["success"]:
            QMessageBox.information(
                self, "Бэкап создан",
                f"✅ {result['message']}\n\n"
                f"Файл: {result['file_path']}"
            )
        else:
            QMessageBox.warning(
                self, "Ошибка бэкапа",
                f"❌ {result['message']}"
            )

        repo.disconnect()