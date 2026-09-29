"""
RefState Dialog Module - Диалог обработки записей расхождений
Оператор просматривает ссылки, помечает оправдано/не оправдано
"""
import webbrowser
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QProgressBar, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QBrush

from refstate_repository import RefStateRepository
from google_sheets_client import GoogleSheetsClient


class RefStateProcessDialog(QDialog):
    """Диалог обработки записей конкретного администратора"""

    def __init__(self, administrator: str, parent=None):
        super().__init__(parent)
        self.administrator = administrator
        self.repository = RefStateRepository()
        self.sheets_client = GoogleSheetsClient()
        self.records = []
        self.current_index = 0
        
        # Статистика обработки
        self.processed_count = 0
        self.approved_count = 0
        self.rejected_count = 0
        self.total_approved_value = 0.0
        self.total_disputed_value = 0.0
        
        self.init_ui()
        self.load_records()

    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle(f"Обработка расхождений — {self.administrator}")
        self.setMinimumSize(900, 650)
        self.resize(1000, 700)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # === ШАПКА ===
        header = QLabel(f"📋 Обработка расхождений: {self.administrator}")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        layout.addWidget(header)
        
        hint = QLabel(
            "Просмотрите каждую запись, проверьте ссылку в Телеграм.\n"
            "Если причина оправдана — нажмите ✓ Оправдано.\n"
            "Если не оправдана — нажмите ✗ Не оправдано."
        )
        hint.setStyleSheet("color: #a6adc8; font-size: 12px;")
        layout.addWidget(hint)

        # === ПРОГРЕСС ===
        progress_group = QGroupBox("Прогресс обработки")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_label = QLabel("Записей: 0 / 0")
        self.progress_label.setFont(QFont("Segoe UI", 11))
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        # Статистика
        stats_layout = QHBoxLayout()
        self.approved_label = QLabel("✅ Оправдано: 0 (0.00₽)")
        self.approved_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        stats_layout.addWidget(self.approved_label)
        
        stats_layout.addStretch()
        
        self.rejected_label = QLabel("❌ Не оправдано: 0")
        self.rejected_label.setStyleSheet("color: #f38ba8; font-weight: bold;")
        stats_layout.addWidget(self.rejected_label)
        
        progress_layout.addLayout(stats_layout)
        layout.addWidget(progress_group)

        # === ТЕКУЩАЯ ЗАПИСЬ ===
        self.current_group = QGroupBox("Текущая запись")
        current_layout = QVBoxLayout(self.current_group)
        
        # Товар и сумма
        self.product_label = QLabel("Товар: —")
        self.product_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        current_layout.addWidget(self.product_label)
        
        details_layout = QHBoxLayout()
        
        self.quantity_label = QLabel("Количество: —")
        self.quantity_label.setStyleSheet("font-size: 13px;")
        details_layout.addWidget(self.quantity_label)
        
        self.value_label = QLabel("Сумма: —")
        self.value_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #f9e2af;")
        details_layout.addWidget(self.value_label)
        
        self.reason_label = QLabel("Причина: —")
        self.reason_label.setStyleSheet("font-size: 13px; color: #89b4fa;")
        details_layout.addWidget(self.reason_label)
        
        details_layout.addStretch()
        current_layout.addLayout(details_layout)
        
        # Ссылка
        link_layout = QHBoxLayout()
        self.reference_label = QLabel("Ссылка: —")
        self.reference_label.setStyleSheet("font-size: 13px; color: #74c7ec;")
        self.reference_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        link_layout.addWidget(self.reference_label)
        
        open_link_btn = QPushButton("🔗 Открыть ссылку")
        open_link_btn.clicked.connect(self.open_reference)
        open_link_btn.setStyleSheet("""
            QPushButton {
                background-color: #74c7ec;
                color: #1e1e2e;
                font-weight: bold;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #89dceb; }
        """)
        link_layout.addWidget(open_link_btn)
        
        current_layout.addLayout(link_layout)
        layout.addWidget(self.current_group)

        # === КНОПКИ РЕШЕНИЯ ===
        decision_layout = QHBoxLayout()
        
        self.approve_btn = QPushButton("✓  Оправдано")
        self.approve_btn.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.approve_btn.setMinimumHeight(60)
        self.approve_btn.setCursor(Qt.PointingHandCursor)
        self.approve_btn.clicked.connect(self.on_approve)
        self.approve_btn.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e2e;
                border: 2px solid #40a02b;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #94d88a; }
            QPushButton:pressed { background-color: #8bd882; }
        """)
        decision_layout.addWidget(self.approve_btn)
        
        self.reject_btn = QPushButton("✗  Не оправдано")
        self.reject_btn.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.reject_btn.setMinimumHeight(60)
        self.reject_btn.setCursor(Qt.PointingHandCursor)
        self.reject_btn.clicked.connect(self.on_reject)
        self.reject_btn.setStyleSheet("""
            QPushButton {
                background-color: #f38ba8;
                color: #1e1e2e;
                border: 2px solid #d20f39;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #eb6f92; }
            QPushButton:pressed { background-color: #e64553; }
        """)
        decision_layout.addWidget(self.reject_btn)
        
        layout.addLayout(decision_layout)

        # === ТАБЛИЦА ВСЕХ ЗАПИСЕЙ ===
        table_group = QGroupBox("Все записи администратора")
        table_layout = QVBoxLayout(table_group)
        
        self.records_table = QTableWidget()
        self.records_table.setAlternatingRowColors(True)
        self.records_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.records_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.records_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.records_table.verticalHeader().setVisible(False)
        table_layout.addWidget(self.records_table)
        
        layout.addWidget(table_group)

        # === КНОПКА ЗАКРЫТИЯ ===
        bottom_layout = QHBoxLayout()
        
        self.backup_btn = QPushButton("💾 Создать бэкап")
        self.backup_btn.clicked.connect(self.create_backup)
        bottom_layout.addWidget(self.backup_btn)
        
        bottom_layout.addStretch()
        
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(close_btn)
        
        layout.addLayout(bottom_layout)

    def load_records(self):
        """Загружает записи администратора"""
        if not self.repository.connect():
            QMessageBox.critical(self, "Ошибка", "Не удалось подключиться к базе данных")
            self.reject()
            return
        
        self.records = self.repository.get_records_by_admin(self.administrator)
        
        if not self.records:
            QMessageBox.information(
                self, "Нет записей",
                f"Для администратора '{self.administrator}' нет записей для обработки"
            )
            self.reject()
            return
        
        # Заполняем таблицу
        self.records_table.setRowCount(len(self.records))
        self.records_table.setColumnCount(5)
        self.records_table.setHorizontalHeaderLabels(
            ["Товар", "Кол-во", "Сумма", "Причина", "Ссылка"]
        )
        
        for row_idx, record in enumerate(self.records):
            self.records_table.setItem(row_idx, 0, QTableWidgetItem(record["product_title"]))
            self.records_table.setItem(row_idx, 1, QTableWidgetItem(str(record["quantity"])))
            self.records_table.setItem(row_idx, 2, QTableWidgetItem(f"{record['value']:.2f}₽"))
            self.records_table.setItem(row_idx, 3, QTableWidgetItem(record["reason"] or "—"))
            self.records_table.setItem(row_idx, 4, QTableWidgetItem(record["reference"]))
        
        self.records_table.resizeColumnsToContents()
        
        # Показываем первую запись
        self.show_record(0)

    def show_record(self, index: int):
        """Показывает запись по индексу"""
        if index >= len(self.records):
            self.finish_processing()
            return
        
        self.current_index = index
        record = self.records[index]
        
        # Обновляем UI
        self.product_label.setText(f"Товар: {record['product_title']}")
        self.quantity_label.setText(f"Количество: {record['quantity']} шт")
        self.value_label.setText(f"Сумма: {record['value']:.2f}₽")
        self.reason_label.setText(f"Причина: {record['reason'] or '—'}")
        self.reference_label.setText(f"Ссылка: {record['reference']}")
        
        # Прогресс
        self.progress_label.setText(
            f"Записей: {self.processed_count} / {len(self.records)}"
        )
        progress_percent = int((self.processed_count / len(self.records)) * 100)
        self.progress_bar.setValue(progress_percent)
        
        # Выделяем текущую строку в таблице
        self.records_table.selectRow(index)

    def open_reference(self):
        """Открывает ссылку в браузере"""
        record = self.records[self.current_index]
        reference = record["reference"]
        
        if not reference:
            QMessageBox.warning(self, "Нет ссылки", "У этой записи нет ссылки")
            return
        
        # Добавляем протокол если его нет
        if not reference.startswith("http://") and not reference.startswith("https://"):
            reference = "https://" + reference
        
        try:
            webbrowser.open(reference)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть ссылку: {e}")

    def on_approve(self):
        """Оператор подтверждает: причина оправдана"""
        self.process_record(approved=True)

    def on_reject(self):
        """Оператор отклоняет: причина не оправдана"""
        self.process_record(approved=False)

    def process_record(self, approved: bool):
        """Обрабатывает текущую запись"""
        record = self.records[self.current_index]
        record_id = record["id"]
        value = record["value"]
        
        # Определяем на сколько уменьшать поля
        minus_decrease = value if approved else 0.0
        disputed_decrease = value  # Спорный уменьшается всегда
        
        # Обновляем Google Sheets
        sheets_result = self.sheets_client.decrease_values(
            admin_name=self.administrator,
            minus_decrease=minus_decrease,
            disputed_decrease=disputed_decrease,
        )
        
        if not sheets_result["success"]:
            reply = QMessageBox.warning(
                self,
                "Ошибка Google Sheets",
                f"Не удалось обновить таблицу:\n{results['message']}\n\n"
                f"Продолжить обработку без обновления таблицы?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        # Удаляем запись из БД
        if not self.repository.delete_record(record_id):
            QMessageBox.warning(
                self, "Ошибка БД",
                f"Не удалось удалить запись {record_id} из базы данных"
            )
            return
        
        # Обновляем статистику
        self.processed_count += 1
        self.total_disputed_value += value
        
        if approved:
            self.approved_count += 1
            self.total_approved_value += value
            self.records_table.item(self.current_index, 0).setBackground(
                QBrush(QColor(166, 227, 161, 100))
            )
        else:
            self.rejected_count += 1
            self.records_table.item(self.current_index, 0).setBackground(
                QBrush(QColor(243, 139, 168, 100))
            )
        
        # Обновляем статистику в UI
        self.approved_label.setText(
            f"✅ Оправдано: {self.approved_count} ({self.total_approved_value:.2f}₽)"
        )
        self.rejected_label.setText(
            f"❌ Не оправдано: {self.rejected_count}"
        )
        
        # Переходим к следующей записи
        self.show_record(self.current_index + 1)

    def finish_processing(self):
        """Завершение обработки всех записей"""
        self.progress_bar.setValue(100)
        self.progress_label.setText(
            f"Записей: {self.processed_count} / {len(self.records)}"
        )
        
        # Итоговое сообщение
        msg = (
            f"🎉 Все записи обработаны!\n\n"
            f"📊 Статистика:\n"
            f"   ✅ Оправдано: {self.approved_count} ({self.total_approved_value:.2f}₽)\n"
            f"   ❌ Не оправдано: {self.rejected_count}\n"
            f"   💰 Общая сумма спорных: {self.total_disputed_value:.2f}₽\n\n"
            f"📋 Google Sheets обновлён:\n"
            f"   • 'Минуса' уменьшен на {self.total_approved_value:.2f}₽\n"
            f"   • 'Спорный' уменьшен на {self.total_disputed_value:.2f}₽"
        )
        
        QMessageBox.information(self, "Обработка завершена", msg)
        self.accept()

    def create_backup(self):
        """Создаёт бэкап таблицы"""
        result = self.repository.backup_table()
        
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

    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.processed_count > 0 and self.processed_count < len(self.records):
            reply = QMessageBox.question(
                self,
                "Незавершённая обработка",
                f"Обработано {self.processed_count} из {len(self.records)} записей.\n"
                f"Закрыть диалог?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return
        
        self.repository.disconnect()
        event.accept()