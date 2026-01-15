"""
Know Your Doses - PyQt6 GUI Application
For Windows 10+ and macOS 15+

Required pip installations:
pip3 install PyQt6
pip3 install python-dateutil
pip3 install pillow
"""

import sqlite3
import sys
from datetime import datetime, date, timedelta
from typing import List

from PyQt6.QtCore import Qt, QDate, QModelIndex
from PyQt6.QtGui import QFont, QBrush, QColor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLayoutItem,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QDialog, QFormLayout, QComboBox, QSpinBox, QGroupBox,
    QGridLayout, QFrame, QDateEdit, QHeaderView, QDialogButtonBox, QLayout
)
# from dateutil.relativedelta import relativedelta

# noinspection PyMethodMayBeStatic


GLOBAL_TIME_DELTA_DAYS = 0
FUTURE_DOSES_DAYS_AHEAD = 30


# ==========================
# ==================================================
# CENTRALIZED DATE FUNCTION FOR DEBUGGING
# ============================================================================
def get_today():
    """Centralized function to get today's date. Modify this for testing."""
    right_now = date.today()
    if GLOBAL_TIME_DELTA_DAYS != 0:
        return right_now + timedelta(days=GLOBAL_TIME_DELTA_DAYS)
    return right_now
    # For testing future dates, uncomment and modify:
    # return date(2025, 11, 10)


def is_showing_future_date():
    global GLOBAL_TIME_DELTA_DAYS
    return GLOBAL_TIME_DELTA_DAYS > 0
# ============================================================================
# DATABASE SETUP
# ============================================================================
class Database:
    def __init__(self, db_path="know_your_doses.db"):
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        # Person table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Person (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date_added TEXT NOT NULL
            )
        """)

        # Prescription table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Prescription (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                date_first_prescribed TEXT NOT NULL,
                date_last_modified TEXT NOT NULL,
                date_last_administered TEXT,
                compound_name TEXT NOT NULL,
                amount INTEGER NOT NULL,
                unit TEXT NOT NULL,
                frequency TEXT NOT NULL,
                cycling_days_on INTEGER,
                cycling_days_off INTEGER,
                icon_type TEXT NOT NULL DEFAULT '💊',
                FOREIGN KEY (person_id) REFERENCES Person(id)
            )
        """)

        # Historical Dose table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS HistoricalDose (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                prescription_id INTEGER,
                date_administered TEXT NOT NULL,
                compound_name TEXT NOT NULL,
                amount INTEGER NOT NULL,
                unit TEXT NOT NULL,
                dose_number INTEGER DEFAULT 1,
                FOREIGN KEY (person_id) REFERENCES Person(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity >= 0),
                vial_size INTEGER NOT NULL CHECK(vial_size >= 1),
                unit TEXT NOT NULL,
                reorder_code TEXT NOT NULL)
        """)

        self.conn.commit()

    def close(self):
        self.conn.close()

def is_weekday() -> List[int]:
    return [0, 1, 2, 3, 4]

def monday_wednesday_friday() -> List[int]:
    return [0, 2, 4]

def monday_thursday() -> List[int]:
    return [0, 3]

def all_frequencies() -> List[str]:
    return ['daily', 'twice-daily', 'weekly', 'M,W,F', 'M,TH', 'MTWTHF', 'monthly', 'quarterly']

def weekly_frequencies() -> List[str]:
    return ['weekly', 'M,W,F', 'M,TH', 'MTWTHF']

# ============================================================================
# CYCLING LOGIC
# ============================================================================
def is_dose_due_on_date(prescription, check_date):
    """
    Determine if a dose is due on a specific date based on prescription rules.
    Returns the number of doses expected (0, 1, or 2 for twice-daily).
    """
    freq = prescription['frequency']
    date_first = datetime.strptime(prescription['date_first_prescribed'], '%Y-%m-%d').date()

    # Check if we're in an ON phase for cycling
    cycling_on = prescription.get('cycling_days_on')
    cycling_off = prescription.get('cycling_days_off')

    if cycling_on and cycling_off:
        if freq in ['daily', 'twice-daily']:
            cycle_length = cycling_on + cycling_off
            days_since_start = (check_date - date_first).days
            position_in_cycle = days_since_start % cycle_length

            if position_in_cycle >= cycling_on:
                return 0  # In OFF phase
        elif freq in weekly_frequencies():
            # need to know when theoretical first dose was
            days_since_start = (check_date - date_first).days
            weeks_since_start = days_since_start // 7
            cycle_duration_in_weeks = cycling_on + cycling_off
            weeks_into_cycle = weeks_since_start % cycle_duration_in_weeks
            if weeks_into_cycle >= cycling_on:
                return 0 # in OFF phase

    # Check frequency
    if freq == 'daily':
        if check_date >= date_first:
            return 1
    elif freq == 'twice-daily':
        if check_date >= date_first:
            return 2
    elif freq == 'M,W,F':  # weekday() == 0, 2, 4
        # Monday Wednesday Friday
        if check_date >= date_first and check_date.weekday() in monday_wednesday_friday():
            return 1
    elif freq == 'MTWTHF': # weekday() == 0, 2, 4
        # Monday Wednesday Friday
        if check_date >= date_first and check_date.weekday() in is_weekday():
            return 1
    elif freq == 'M,TH': # weekday() == 0, 2, 4
        # Monday Wednesday Friday
        if check_date >= date_first and check_date.weekday() in monday_thursday():
            return 1
    elif freq == 'weekly':
        # Weekly on same day of week
        if check_date >= date_first and check_date.weekday() == date_first.weekday():
            return 1
    elif freq == 'monthly':
        # Monthly on same day of month
        if check_date >= date_first:
            target_day = date_first.day
            if check_date.day == target_day or (check_date.day == last_day_of_month(check_date) and target_day > check_date.day):
                return 1
    elif freq == 'quarterly':
        # Quarterly on same day of month
        if check_date >= date_first:
            months_diff = (check_date.year - date_first.year) * 12 + check_date.month - date_first.month
            if months_diff % 3 == 0:
                target_day = date_first.day
                if check_date.day == target_day or (check_date.day == last_day_of_month(check_date) and target_day > check_date.day):
                    return 1

    return 0

def last_day_of_month(dt):
    """Get the last day of the month for a given date."""
    next_month = dt.replace(day=28) + timedelta(days=4)
    return (next_month - timedelta(days=next_month.day)).day

# ============================================================================
# SCREEN 1: NEW PERSON
# ============================================================================
class NewPersonDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.name_input = None
        self.db = db
        self.setWindowTitle("New Person")
        self.setModal(True)
        self.setup_new_person_ui()

    def setup_new_person_ui(self):
        layout = QVBoxLayout()

        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        form_layout.addRow("Name:", self.name_input)
        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.save_person)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def save_person(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Name cannot be empty.")
            return

        cursor = self.db.conn.cursor()
        date_added = get_today().isoformat()
        cursor.execute("INSERT INTO Person (name, date_added) VALUES (?, ?)", (name, date_added))
        self.db.conn.commit()
        self.accept()

# ============================================================================
# SCREEN 5: DOSE HISTORY EDIT
# ============================================================================
class DoseHistoryEditDialog(QDialog):
    def __init__(self, db, person_id, dose_id=None, parent=None):
        super().__init__(parent)
        self.dose_number_input = None
        self.amount_input = None
        self.unit_input = None
        self.compound_input = None
        self.date_input = None
        self.db = db
        self.person_id = person_id
        self.dose_id = dose_id
        self.setWindowTitle("Edit Dose History")
        self.setModal(True)
        self.changed = False
        self.setup_dose_ui()
        if dose_id:
            self.load_dose()

    def setup_dose_ui(self):
        layout = QVBoxLayout()

        form_layout = QFormLayout()

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.dateChanged.connect(self.mark_dose_changed)
        form_layout.addRow("Date Administered:", self.date_input)

        self.compound_input = QLineEdit()
        self.compound_input.textChanged.connect(self.mark_dose_changed)
        form_layout.addRow("Name:", self.compound_input)

        self.amount_input = QSpinBox()
        self.amount_input.setMinimum(0)
        self.amount_input.setMaximum(10000)
        self.amount_input.valueChanged.connect(self.mark_dose_changed)
        form_layout.addRow("Amount:", self.amount_input)

        self.unit_input = QComboBox()
        self.unit_input.addItems(["mg", "mcg", "ml", "set"])
        self.unit_input.currentTextChanged.connect(self.mark_dose_changed)
        form_layout.addRow("Unit:", self.unit_input)

        self.dose_number_input = QSpinBox()
        self.dose_number_input.setMinimum(1)
        self.dose_number_input.setMaximum(2)
        self.dose_number_input.valueChanged.connect(self.mark_dose_changed)
        form_layout.addRow("Dose Number:", self.dose_number_input)

        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Close")
        save_btn.clicked.connect(self.save_dose)
        cancel_btn.clicked.connect(self.cancel_edit)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def mark_dose_changed(self):
        self.changed = True

    def load_dose(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM HistoricalDose WHERE id = ? order by date_administered DESC", (self.dose_id,))
        dose = cursor.fetchone()
        if dose:
            self.date_input.setDate(QDate.fromString(dose[3], "yyyy-MM-dd"))
            self.compound_input.setText(dose[4])
            self.amount_input.setValue(dose[5])
            self.unit_input.setCurrentText(dose[6])
            self.dose_number_input.setValue(dose[7] if dose[7] else 1)
        self.changed = False

    def save_dose(self):
        compound = self.compound_input.text().strip()
        if not compound:
            QMessageBox.warning(self, "Validation Error", "Name cannot be empty.")
            return

        date_admin = self.date_input.date().toString("yyyy-MM-dd")
        amount = self.amount_input.value()
        unit = self.unit_input.currentText()
        dose_number = self.dose_number_input.value()

        cursor = self.db.conn.cursor()
        if self.dose_id:
            cursor.execute("""
                UPDATE HistoricalDose 
                SET date_administered = ?, compound_name = ?, amount = ?, unit = ?, dose_number = ?
                WHERE id = ?
            """, (date_admin, compound, amount, unit, dose_number, self.dose_id))
        else:
            cursor.execute("""
                INSERT INTO HistoricalDose (person_id, date_administered, compound_name, amount, unit, dose_number)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (self.person_id, date_admin, compound, amount, unit, dose_number))

        self.db.conn.commit()
        self.accept()

    def cancel_edit(self):
        if self.changed:
            reply = QMessageBox.question(self, "Unsaved Changes",
                                        "You have unsaved changes. Are you sure you want to cancel?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        self.reject()

# ============================================================================
# SCREEN 4: HISTORY Window
# ============================================================================
class HistoryWindow(QDialog):
    def __init__(self, db, person_id, parent=None):
        super().__init__(parent)
        self.history_table = None
        self.compound_filter = None
        self.db = db
        self.person_id = person_id
        self.setWindowTitle("Dosage History")
        self.setModal(True)
        self.resize(600, 600)
        self.setup_history_ui()
        self.load_history()

    def setup_history_ui(self):
        layout = QVBoxLayout()

        # Filter section
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.compound_filter = QComboBox()
        self.compound_filter.addItem("All")
        self.compound_filter.currentTextChanged.connect(self.load_history)
        filter_layout.addWidget(self.compound_filter)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["Date", "Name", "Amount", "Edit", "Delete"])
        self.history_table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # disables all editing
        layout.addWidget(self.history_table)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)
        self.load_compounds()

    def load_compounds(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT DISTINCT compound_name FROM HistoricalDose WHERE person_id = ?", (self.person_id,))
        compounds = cursor.fetchall()
        for compound in compounds:
            self.compound_filter.addItem(compound[0])

    def load_history(self):
        cursor = self.db.conn.cursor()

        filter_compound = self.compound_filter.currentText()
        if filter_compound == "All":
            cursor.execute("""
                SELECT id, date_administered, compound_name, amount, unit, dose_number
                FROM HistoricalDose 
                WHERE person_id = ?
                ORDER BY date_administered DESC
            """, (self.person_id,))
        else:
            cursor.execute("""
                SELECT id, date_administered, compound_name, amount, unit, dose_number
                FROM HistoricalDose 
                WHERE person_id = ? AND compound_name = ?
                ORDER BY date_administered DESC
            """, (self.person_id, filter_compound))

        doses = cursor.fetchall()
        self.history_table.setRowCount(len(doses))
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # disables all editing

        for row, dose in enumerate(doses):
            dose_id, date_admin, compound, amount, unit, dose_number = dose
            self.history_table.setItem(row, 0, QTableWidgetItem(date_admin))
            self.history_table.setItem(row, 1, QTableWidgetItem(compound))
            self.history_table.setItem(row, 2, QTableWidgetItem(f"{str(amount)} {unit}"))

            edit_btn = QPushButton("✏️")
            edit_btn.clicked.connect(lambda checked, d_id=dose_id: self.edit_dose(d_id))
            self.history_table.setCellWidget(row, 3, edit_btn)

            delete_btn = QPushButton("❌️")
            delete_btn.clicked.connect(lambda checked, d_id=dose_id: self.delete_dose(row, d_id))
            self.history_table.setCellWidget(row, 4, delete_btn)

    def edit_dose(self, dose_id):
        dialog = DoseHistoryEditDialog(self.db, self.person_id, dose_id, self)
        if dialog.exec():
            self.load_history()
            self.load_compounds()

    def delete_dose(self, row, dose_id):
        reply = QMessageBox.question(self, "Delete Dose",
                                     "Are you sure you want to delete this dose?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            cursor = self.db.conn.cursor()
            cursor.execute("DELETE FROM HistoricalDose WHERE id = ?", (dose_id,))
            self.db.conn.commit()
            self.history_table.removeRow(row)


# ============================================================================
# SCREEN 3: PERSON CONFIGURATION
# ============================================================================
class PrescriptionList(QDialog):
    def __init__(self, db, person_id, parent=None):
        super().__init__(parent)
        self.prescription_table = None
        self.db = db
        self.person_id = person_id
        self.setWindowTitle("Prescriptions")
        self.setModal(True)
        self.resize(1000, 600)
        self.changed = False
        self.date_modified_manually = set()
        self.modified_rows = set()
        self.setup_config_ui()
        self.load_prescriptions()

    def _reset_modified_state(self):
        self.changed = False # start out in unchanged-state
        self.modified_rows = set() # start out in unchanged-state
        self.date_modified_manually = set()

    def setup_config_ui(self):
        layout = QVBoxLayout()

        # Table
        self.prescription_table = QTableWidget()
        self.prescription_table.setColumnCount(11)
        self.prescription_table.setHorizontalHeaderLabels([
            "Name", "Amount", "Unit", "Frequency",
            "Cycle On", "Cycle Off", "Date First", "Last Modified", "Last Admin", "Icon", ""
        ])
        self.prescription_table.cellChanged.connect(self.mark_changed)

        self.prescription_table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        self.prescription_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.prescription_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.prescription_table)

        # Add button
        add_btn = QPushButton("+ Add Prescription")
        add_btn.clicked.connect(self.add_prescription_row)
        layout.addWidget(add_btn)

        # Save/Cancel buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Close")
        save_btn.clicked.connect(self.save_changes)
        cancel_btn.clicked.connect(self.cancel_changes)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def mark_changed(self, row, _, is_date_modified = False):
        self.changed = True
        if is_date_modified:
            self.date_modified_manually.add(row)
        self.modified_rows.add(row)

    def load_prescriptions(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM Prescription WHERE person_id = ? order by compound_name ASC, date_last_administered DESC", (self.person_id,))
        prescriptions = cursor.fetchall()

        self.prescription_table.setRowCount(len(prescriptions))
        for row, presc in enumerate(prescriptions):
            self.populate_row(row, presc)
        # populate_row winds up marking everything as modified
        self._reset_modified_state()

    def _make_date_edit(self, iso_str, col, row):
        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd")

        # Define a sentinel "minimum" date to represent "no date"
        NO_DATE = QDate(2024, 1, 1)
        edit.setMinimumDate(NO_DATE)
        edit.setMaximumDate(QDate.currentDate().addDays(365))
        edit.setSpecialValueText(" ") # Allow the special value (blank) to be shown when date == minimumDate

        if iso_str:
            date_local = QDate.fromString(iso_str, "yyyy-MM-dd")
            if date_local.isValid():
                edit.setDate(date_local)
            else:
                edit.setDate(NO_DATE)  # fallback
        else:
            edit.setDate(NO_DATE)  # shows as blank

        # Connect signal
        edit.dateChanged.connect(lambda: self.mark_changed(row, col, True))
        return edit

    def _get_date_from_cell(self, row, col):
        """
        Return ISO string (or None) from column that may contain:
          • a QDateEdit (cellWidget)
          • a QTableWidgetItem (plain text)
        """
        widget = self.prescription_table.cellWidget(row, col)
        if widget:  # QDateEdit
            return widget.date().toString("yyyy-MM-dd")
        item = self.prescription_table.item(row, col)
        txt = item.text().strip() if item else ""
        return txt if txt else None

    def populate_row(self, row, presc=None):
        if presc:
            prescription_id, person_id, date_first, date_modified, date_last_admin, compound, amount, unit, freq, cycle_on, cycle_off, icon_str = presc
        else:
            prescription_id = None
            compound, amount, unit, freq = "", 0, "mg", "daily"
            cycle_on, cycle_off = None, None
            date_first = get_today().isoformat()
            date_modified = get_today().isoformat()
            date_last_admin = None
            icon_str = '💊'

        self.prescription_table.setItem(row, 0, QTableWidgetItem(compound))
        self.prescription_table.setItem(row, 1, QTableWidgetItem(str(amount)))

        unit_combo = QComboBox()
        unit_combo.addItems(["mg", "mcg", "ml", "set"])
        unit_combo.setCurrentText(unit)
        unit_combo.currentTextChanged.connect(lambda: self.mark_changed(row, 2))
        self.prescription_table.setCellWidget(row, 2, unit_combo)

        freq_combo = QComboBox()
        freq_combo.addItems(all_frequencies())
        freq_combo.setCurrentText(freq)
        freq_combo.currentTextChanged.connect(lambda: self.mark_changed(row, 3))
        self.prescription_table.setCellWidget(row, 3, freq_combo)

        self.prescription_table.setItem(row, 4, QTableWidgetItem(str(cycle_on) if cycle_on else ""))
        self.prescription_table.setItem(row, 5, QTableWidgetItem(str(cycle_off) if cycle_off else ""))
        # ---------- DATE COLUMNS (6,7,8) ----------
        self.prescription_table.setCellWidget(row, 6, self._make_date_edit(date_first, 6, row))
        self.prescription_table.setCellWidget(row, 7, self._make_date_edit(date_modified, 7, row))
        self.prescription_table.setCellWidget(row, 8, self._make_date_edit(date_last_admin, 8, row))
        # self.table.setItem(row, 6, QTableWidgetItem(date_first))
        # self.table.setItem(row, 7, QTableWidgetItem(date_modified))
        # self.table.setItem(row, 8, QTableWidgetItem(date_last_admin if date_last_admin else ""))

        self.prescription_table.setItem(row, 9, QTableWidgetItem(str(icon_str) if icon_str else "💊"))

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.delete_prescription(row, prescription_id))
        self.prescription_table.setCellWidget(row, 10, delete_btn)

        # Store prescription_id in row
        if prescription_id:
            self.prescription_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, prescription_id)

    def add_prescription_row(self):
        row = self.prescription_table.rowCount()
        self.prescription_table.insertRow(row)
        self.populate_row(row)
        self.changed = True

    def delete_prescription(self, row, prescription_id):
        reply = QMessageBox.question(self, "Delete Prescription",
                                     "Are you sure you want to delete this prescription?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if prescription_id:
                cursor = self.db.conn.cursor()
                cursor.execute("DELETE FROM Prescription WHERE id = ?", (prescription_id,))
                self.db.conn.commit()
            self.prescription_table.removeRow(row)
            self.changed = True

    def save_changes(self):
        # stop any editing
        self.prescription_table.setCurrentIndex(QModelIndex())

        cursor = self.db.conn.cursor()

        for row in range(self.prescription_table.rowCount()):
            compound = self.prescription_table.item(row, 0).text().strip()
            if not compound:
                QMessageBox.warning(self, "Validation Error", f"Row {row+1}: Compound name cannot be empty.")
                return

            try:
                amount = int(self.prescription_table.item(row, 1).text())
                if amount < 0:
                    raise ValueError()
            except:
                QMessageBox.warning(self, "Validation Error", f"Row {row+1}: Amount must be a positive integer.")
                return

            unit = self.prescription_table.cellWidget(row, 2).currentText()
            freq = self.prescription_table.cellWidget(row, 3).currentText()

            cycle_on_text = self.prescription_table.item(row, 4).text().strip()
            cycle_off_text = self.prescription_table.item(row, 5).text().strip()

            cycle_on = int(cycle_on_text) if cycle_on_text else None
            cycle_off = int(cycle_off_text) if cycle_off_text else None

            if cycle_on and cycle_on < 1:
                QMessageBox.warning(self, "Validation Error", f"Row {row+1}: cycle on must be greater than 0.")
                return
            if cycle_off and cycle_off < 1:
                QMessageBox.warning(self, "Validation Error", f"Row {row+1}: cycle off must be greater than 0.")
                return

            date_first = self._get_date_from_cell(row, 6)
            date_modified = self._get_date_from_cell(row, 7)
            date_last_admin = self._get_date_from_cell(row, 8)  # returns None if empty
            # date_first = self.table.item(row, 6).text()
            # date_modified = self.table.item(row, 7).text()
            # date_last_admin = self.table.item(row, 8).text() if self.table.item(row, 8).text() else None

            item = self.prescription_table.item(row, 9)
            icon_str = item.text() if item is not None else "💊"

            prescription_id = self.prescription_table.item(row, 0).data(Qt.ItemDataRole.UserRole)

            # Update date_last_modified if row was modified
            if row in self.modified_rows and row not in self.date_modified_manually:
                # update only if we didn't modify a date on this row
                date_modified = get_today().isoformat()

            if prescription_id:
                if row in self.date_modified_manually:
                    # we update all dates
                    cursor.execute("""
                        UPDATE Prescription 
                        SET compound_name = ?, amount = ?, unit = ?, frequency = ?,
                            cycling_days_on = ?, cycling_days_off = ?, 
                            date_first_prescribed = ?, date_last_modified = ?, date_last_administered = ?,
                            icon_type = ?
                        WHERE id = ?
                    """, (compound, amount, unit, freq, cycle_on, cycle_off, date_first, date_modified, date_last_admin, icon_str, prescription_id))
                else:
                    cursor.execute("""
                        UPDATE Prescription 
                        SET compound_name = ?, amount = ?, unit = ?, frequency = ?,
                            cycling_days_on = ?, cycling_days_off = ?, date_last_modified = ?, icon_type = ?
                        WHERE id = ?
                    """, (compound, amount, unit, freq, cycle_on, cycle_off, date_modified, icon_str, prescription_id))
            else:
                cursor.execute("""
                    INSERT INTO Prescription 
                    (person_id, date_first_prescribed, date_last_modified, compound_name, amount, unit, frequency, cycling_days_on, cycling_days_off, icon_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (self.person_id, date_first, date_modified, compound, amount, unit, freq, cycle_on, cycle_off, icon_str))

        self.db.conn.commit()
        self.accept()

    def cancel_changes(self):
        if self.changed:
            reply = QMessageBox.question(self, "Unsaved Changes",
                                        "You have unsaved changes. Are you sure you want to cancel?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        self.reject()

# ============================================================================
# SCREEN 2: PERSON DASHBOARD
# ============================================================================
class PersonDashboard(QMainWindow):
    def __init__(self, db, person_id, parent=None):
        super().__init__(parent)
        self.details_layout = None
        self.weekly_grid = None
        self.person_name = None
        self.future_layout = None
        self.future_group = None
        self.db = db
        self.person_id = person_id
        self.selected_prescription = None
        self.load_person()
        self.resize(900, 800)
        self.setup_person_ui()
        self.refresh_dashboard()

    def load_person(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT name FROM Person WHERE id = ?", (self.person_id,))
        result = cursor.fetchone()
        self.person_name = result[0] if result else "Unknown"

    def setup_window_title(self):
        global GLOBAL_TIME_DELTA_DAYS
        today_str = get_today().strftime("%m-%d-%Y (%A)")
        if GLOBAL_TIME_DELTA_DAYS > 0:
            today_str += f" : [+{GLOBAL_TIME_DELTA_DAYS} days]"
        elif GLOBAL_TIME_DELTA_DAYS < 0:
            today_str += f" : [{GLOBAL_TIME_DELTA_DAYS} days]"

        self.setWindowTitle(f"Dashboard - {today_str}")

    def _add_horizontal_separator(self, main_layout: QLayoutItem):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

    def _add_vertical_separator(self, main_layout: QLayoutItem):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

    def _add_header(self, main_layout: QLayoutItem):
        # Header
        header_layout = QHBoxLayout()

        name_layout = QVBoxLayout()
        header_label = QLabel(self.person_name)
        header_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        name_layout.addWidget(header_label, alignment=Qt.AlignmentFlag.AlignCenter)

        edit_btn = QPushButton("Prescriptions 💊")
        edit_btn.clicked.connect(self.open_config)
        name_layout.addWidget(edit_btn, stretch=1)

        history_btn = QPushButton("History 📜")
        history_btn.clicked.connect(self.open_history)
        name_layout.addWidget(history_btn, stretch=1)

        header_layout.addLayout(name_layout)

        self._add_horizontal_separator(header_layout)
        self._add_date_bar(header_layout)

        header_layout.addStretch()

        header_widget = QWidget()
        header_widget.setStyleSheet("")
        header_widget.setLayout(header_layout)
        header_widget.setMaximumHeight(125)
        main_layout.addWidget(header_widget)

        # main_layout.addLayout(header_layout)

    def _add_date_bar(self, main_layout: QLayoutItem):
        # Change Date Label
        date_box = QGroupBox("Change Date")
        date_box.setFlat(False)
        date_box.setStyleSheet("QGroupBox { font-weight: bold; }")

        date_control_layout = QHBoxLayout()
        week_back_btn = QPushButton("⬅️ Week")
        week_back_btn.clicked.connect(lambda: self.change_date(-7))
        date_control_layout.addWidget(week_back_btn)

        day_back_btn = QPushButton("◀️ Day")
        day_back_btn.clicked.connect(lambda: self.change_date(-1))
        date_control_layout.addWidget(day_back_btn)

        today_btn = QPushButton("🏠 Today")
        today_btn.clicked.connect(lambda: self.change_date(0))
        date_control_layout.addWidget(today_btn)


        day_fwd_btn = QPushButton("Day ▶️")
        day_fwd_btn.clicked.connect(lambda: self.change_date(1))
        date_control_layout.addWidget(day_fwd_btn)

        week_fwd_btn = QPushButton("Week ➡️")
        week_fwd_btn.clicked.connect(lambda: self.change_date(7))
        date_control_layout.addWidget(week_fwd_btn)
        # primary_layout.addLayout(date_control_layout)

        # main_layout.addLayout(primary_layout)
        date_box.setLayout(date_control_layout)
        main_layout.addWidget(date_box, 0, Qt.AlignmentFlag.AlignTop)

    def setup_person_ui(self):
        self.setup_window_title()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self._add_header(main_layout)
        self._add_vertical_separator(main_layout)

        # Weekly grid
        self.weekly_grid = QGridLayout()
        self.weekly_grid.setSpacing(10)

        today = get_today().strftime("%A")  # e.g. "Wednesday"
        unordered_days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        idx = unordered_days.index(today)  # index of today
        ordered_days = unordered_days[idx:] + unordered_days[:idx]  # rotate so today is first

        for col, day in enumerate(ordered_days):
            label = QLabel(day)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFont(QFont("Arial", 13, QFont.Weight.Bold))
            label.setStyleSheet("QLabel { background-color: #555555; color: white; }")
            self.weekly_grid.addWidget(label, 0, col)

        main_layout.addLayout(self.weekly_grid)

        # Details frame
        global FUTURE_DOSES_DAYS_AHEAD
        details_section = QHBoxLayout()
        future_frame = QGroupBox(f"Next {FUTURE_DOSES_DAYS_AHEAD} days")
        future_frame.setStyleSheet("QGroupBox { font-weight: bold; }")
        future_frame.setMinimumHeight(250)
        future_frame.setFlat(False)

        self.future_group = future_frame
        self.future_layout = QVBoxLayout(future_frame)

        if not is_showing_future_date():
            details_frame = QGroupBox("Due Today")
        else:
            details_frame = QGroupBox("On This Day")
        details_frame.setStyleSheet("QGroupBox { font-weight: bold; }")
        details_frame.setMinimumHeight(250)
        future_frame.setFlat(False)
        self.details_layout = QVBoxLayout(details_frame)

        # main_layout.addWidget(details_frame)
        details_section.addWidget(details_frame)
        details_section.addWidget(future_frame)

        main_layout.addLayout(details_section)

    def refresh_dashboard(self):
        self.clear_weekly_grid()
        self.populate_weekly_grid()
        self.update_details_area()
        self.populate_future_doses()

    def clear_weekly_grid(self):
        # Clear all widgets except day labels (row 0)
        for row in range(1, self.weekly_grid.rowCount()):
            for col in range(self.weekly_grid.columnCount()):
                item = self.weekly_grid.itemAtPosition(row, col)
                if item:
                    widget = item.widget()
                    if widget:
                        widget.deleteLater()

    def populate_weekly_grid(self):
        today = get_today()

        # Find the Sunday of this week
        # days_since_sunday = (today.weekday() + 1) % 7
        # sunday = today - timedelta(days=days_since_sunday)

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM Prescription WHERE person_id = ? ORDER BY compound_name ASC, date_last_administered DESC", (self.person_id,))
        prescriptions = cursor.fetchall()

        # Build icon grid
        for col in range(7):
            # current_date = sunday + timedelta(days=col)
            current_date = today + timedelta(days=col)

            # Only show current and future dates
            if current_date < today:
                continue

            icons_for_day = []

            for presc in prescriptions:
                prescription = {
                    'id': presc[0],
                    'date_first_prescribed': presc[2],
                    'date_last_administered': presc[4],
                    'compound_name': presc[5],
                    'amount': presc[6],
                    'unit': presc[7],
                    'frequency': presc[8],
                    'cycling_days_on': presc[9],
                    'cycling_days_off': presc[10],
                    'icon_type': presc[11]
                }

                expected_doses = is_dose_due_on_date(prescription, current_date)

                if expected_doses > 0:
                    # Check how many doses already administered
                    cursor.execute("""
                        SELECT COUNT(*) FROM HistoricalDose 
                        WHERE person_id = ? AND prescription_id = ? AND date_administered = ? AND amount > 0
                    """, (self.person_id, prescription['id'], current_date.isoformat()))

                    administered_count = cursor.fetchone()[0]
                    remaining_doses = expected_doses - administered_count

                    if remaining_doses > 0:
                        icons_for_day.append((prescription, remaining_doses, expected_doses))

            # Display icons
            row = 1
            for prescription, remaining, total in icons_for_day:
                icon_widget = QWidget()
                icon_layout = QHBoxLayout(icon_widget)
                icon_layout.setContentsMargins(0, 0, 0, 0)

                if total == 2:  # Twice daily
                    # Show pills side by side
                    for _ in range(remaining):
                        pill_btn = QPushButton(f"{prescription['compound_name']} {prescription['icon_type']}")
                        # pill_btn.setFixedSize(30, 30)
                        pill_btn.clicked.connect(lambda checked, p=prescription: self.select_prescription(p))
                        icon_layout.addWidget(pill_btn)
                else:
                    pill_btn = QPushButton(f"{prescription['compound_name']} {prescription['icon_type']}")
                    # pill_btn.setFixedSize(30, 30)
                    pill_btn.clicked.connect(lambda checked, p=prescription: self.select_prescription(p))
                    icon_layout.addWidget(pill_btn)

                self.weekly_grid.addWidget(icon_widget, row, col)
                row += 1

    def _clear_layout(self, layout: QLayout):
        for _ in reversed(range(layout.count())):
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Recursively clear sub-layout
                sub = item.layout()
                while sub.count():
                    child = sub.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                sub.deleteLater()

    def alternate_days_ahead_value(self ):
        global FUTURE_DOSES_DAYS_AHEAD
        if FUTURE_DOSES_DAYS_AHEAD == 30:
            return 14
        else:
            return 30

    def change_days_ahead(self):
        global FUTURE_DOSES_DAYS_AHEAD
        FUTURE_DOSES_DAYS_AHEAD = self.alternate_days_ahead_value()
        self.refresh_dashboard()

    def populate_future_doses(self):
        global FUTURE_DOSES_DAYS_AHEAD
        # Clear current layout
        self._clear_layout(self.future_layout)

        self.future_group.setTitle(f"Next {FUTURE_DOSES_DAYS_AHEAD} days")
        days_ahead_button = QPushButton(f"See {self.alternate_days_ahead_value()} Days")
        days_ahead_button.clicked.connect(lambda: self.change_days_ahead())
        self.future_layout.addWidget(days_ahead_button)

        future_doses = self.upcoming_doses(FUTURE_DOSES_DAYS_AHEAD)

        if len(future_doses) > 0:
            dose_row = 0
            future_compounds = sorted(future_doses.keys())

            future_grid = QGridLayout()
            future_grid.setSpacing(10)
            future_grid.setVerticalSpacing(15)

            for compound_name in future_compounds:
                prescription = future_doses[compound_name]

                if prescription['unit'] == 'mcg' and prescription['amount'] > 1000:
                    to_milligrams = prescription['amount'] / 1000.0
                    prescription['unit'] = 'mg'
                    prescription['amount'] = to_milligrams

                name_label = QLabel(f"{prescription['compound_name']} {prescription['icon_type']}")
                amount_label = QLabel(f"{prescription['amount']} {prescription['unit']}")
                count_label = QLabel(f"{prescription['doses']} doses")

                future_grid.addWidget(name_label, dose_row, 0)
                future_grid.addWidget(amount_label, dose_row, 1)
                future_grid.addWidget(count_label, dose_row, 2)
                dose_row += 1

            self.future_layout.addLayout(future_grid, stretch=0)
        else:
            label = QLabel("No Pending Doses")
            self.future_layout.addWidget(label, stretch=0)

        self.future_layout.addStretch()


    def upcoming_doses(self, days_ahead: int):
        today = get_today()

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM Prescription WHERE person_id = ? ORDER BY compound_name ASC, date_last_administered DESC", (self.person_id,))
        prescriptions = cursor.fetchall()

        future_doses = {}

        for day_delta in range(days_ahead):
            check_date = today + timedelta(days=day_delta)

            # Only show current and future dates
            if check_date < today:
                continue

            for presc in prescriptions:
                prescription = {
                    'id': presc[0],
                    'date_first_prescribed': presc[2],
                    'date_last_administered': presc[4],
                    'compound_name': presc[5],
                    'amount': presc[6],
                    'unit': presc[7],
                    'frequency': presc[8],
                    'cycling_days_on': presc[9],
                    'cycling_days_off': presc[10],
                    'icon_type': presc[11]
                }

                expected_doses = is_dose_due_on_date(prescription, check_date)
                if expected_doses > 0:
                    dose_amount = int(prescription['amount']) * expected_doses
                    compound_name = prescription['compound_name']
                    future_dose = future_doses.get(compound_name, None)
                    if future_dose is None:
                        future_dose = { 'compound_name': compound_name,
                                        'amount': dose_amount,
                                        'doses': expected_doses,
                                        'unit': prescription['unit'],
                                        'icon_type': prescription['icon_type'],
                                        }
                    else:
                        future_dose_count = future_dose['doses']
                        future_dose_amount = future_dose['amount']
                        future_dose_count += expected_doses
                        future_dose_amount += dose_amount
                        future_dose['doses'] = future_dose_count
                        future_dose['amount'] = future_dose_amount
                    future_doses[compound_name] = future_dose

        return future_doses

    def select_prescription(self, prescription):
        self.selected_prescription = prescription
        self.update_details_area()

    def update_details_area(self):
        # Clear current layout
        self._clear_layout(self.details_layout)

        if self.selected_prescription:
            # Show selected prescription details
            presc = self.selected_prescription

            details_text = f"""
            <b>Compound:</b> {presc['compound_name']}<br>
            <b>Amount:</b> {presc['amount']} {presc['unit']}<br>
            <b>Frequency:</b> {presc['frequency']}<br>
            <b>First Prescribed:</b> {presc['date_first_prescribed']}<br>
            """

            if presc.get('cycling_days_on') and presc.get('cycling_days_off'):
                cycle_units = "days"
                # days on, days off
                if presc['frequency'] in weekly_frequencies():
                    # weeks on, weeks off
                    cycle_units = "weeks"
                details_text += f"<b>Cycling:</b> {presc['cycling_days_on']} {cycle_units} on, {presc['cycling_days_off']} {cycle_units} off<br>"

            label = QLabel(details_text)
            self.details_layout.addWidget(label)

            # Check if dose is due today
            today = get_today()
            expected_today = is_dose_due_on_date(presc, today)

            if expected_today > 0:
                cursor = self.db.conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM HistoricalDose 
                    WHERE person_id = ? AND prescription_id = ? AND date_administered = ? AND amount > 0
                """, (self.person_id, presc['id'], today.isoformat()))

                administered_count = cursor.fetchone()[0]
                remaining = expected_today - administered_count

                if remaining > 0 and not is_showing_future_date():
                    administer_btn = QPushButton(f"Administer Dose ({remaining} remaining)")
                    administer_btn.clicked.connect(lambda: self.administer_selected_dose(remaining))
                    self.details_layout.addWidget(administer_btn)
            self.details_layout.addStretch()
        else:
            # Show doses due today
            today = get_today()
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT * FROM Prescription WHERE person_id = ? order by compound_name ASC, date_last_administered DESC", (self.person_id,))
            prescriptions = cursor.fetchall()

            due_today = []
            for presc in prescriptions:
                prescription = {
                    'id': presc[0],
                    'date_first_prescribed': presc[2],
                    'date_last_administered': presc[4],
                    'compound_name': presc[5],
                    'amount': presc[6],
                    'unit': presc[7],
                    'frequency': presc[8],
                    'cycling_days_on': presc[9],
                    'cycling_days_off': presc[10],
                    'icon_type': presc[11]
                }

                expected_today = is_dose_due_on_date(prescription, today)

                if expected_today > 0:
                    cursor.execute("""
                        SELECT COUNT(*) FROM HistoricalDose 
                        WHERE person_id = ? AND prescription_id = ? AND date_administered = ? AND amount > 0
                    """, (self.person_id, prescription['id'], today.isoformat()))

                    administered_count = cursor.fetchone()[0]
                    remaining = expected_today - administered_count

                    if remaining > 0:
                        due_today.append((prescription, remaining))

            if due_today:
                for prescription, remaining in due_today:
                    dose_layout = QHBoxLayout()

                    info_label = QLabel(f"{prescription['compound_name']} {prescription['icon_type']} - {prescription['amount']} {prescription['unit']} ({remaining} remaining)")
                    dose_layout.addWidget(info_label)

                    if not is_showing_future_date():
                        administer_btn = QPushButton("Administer")
                        administer_btn.setMaximumWidth(100)
                        administer_btn.clicked.connect(lambda checked, p=prescription, r=remaining: self.administer_dose_quick(p, r))
                        dose_layout.addWidget(administer_btn)

                    self.details_layout.addLayout(dose_layout, stretch=0)
            else:
                if not is_showing_future_date():
                    label = QLabel("No doses due today.")
                else:
                    label = QLabel("No doses.")
                self.details_layout.addWidget(label, stretch=0)

            self.details_layout.addStretch()

    def administer_selected_dose(self, remaining):
        if not self.selected_prescription:
            return

        presc = self.selected_prescription
        today = get_today()

        cursor = self.db.conn.cursor()

        # Determine which dose number to use
        expected_today = is_dose_due_on_date(presc, today)
        dose_number = expected_today - remaining + 1

        # Add the dose
        cursor.execute("""
            INSERT INTO HistoricalDose 
            (person_id, prescription_id, date_administered, compound_name, amount, unit, dose_number)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (self.person_id, presc['id'], today.isoformat(),
              presc['compound_name'], presc['amount'], presc['unit'], dose_number))

        # Update last_administered
        cursor.execute("""
            UPDATE Prescription SET date_last_administered = ? WHERE id = ?
        """, (today.isoformat(), presc['id']))

        self.db.conn.commit()

        # Refresh
        self.selected_prescription = None
        self.refresh_dashboard()

    def administer_dose_quick(self, prescription, remaining):
        today = get_today()
        cursor = self.db.conn.cursor()

        # Determine which dose number to use
        expected_today = is_dose_due_on_date(prescription, today)
        dose_number = expected_today - remaining + 1

        # Add the dose
        cursor.execute("""
            INSERT INTO HistoricalDose 
            (person_id, prescription_id, date_administered, compound_name, amount, unit, dose_number)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (self.person_id, prescription['id'], today.isoformat(),
              prescription['compound_name'], prescription['amount'], prescription['unit'], dose_number))

        # Update last_administered
        cursor.execute("""
            UPDATE Prescription SET date_last_administered = ? WHERE id = ?
        """, (today.isoformat(), prescription['id']))

        self.db.conn.commit()

        # Refresh
        self.refresh_dashboard()

    def edit_selected_prescription(self):
        self.open_config()

    def delete_selected_prescription(self):
        if not self.selected_prescription:
            return

        reply = QMessageBox.question(self, "Delete Prescription",
                                     "Are you sure you want to delete this prescription?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            cursor = self.db.conn.cursor()
            cursor.execute("DELETE FROM Prescription WHERE id = ?", (self.selected_prescription['id'],))
            self.db.conn.commit()
            self.selected_prescription = None
            self.refresh_dashboard()

    def open_config(self):
        dialog = PrescriptionList(self.db, self.person_id, self)
        if dialog.exec():
            self.refresh_dashboard()

    def change_date(self, day_delta: int):
        global GLOBAL_TIME_DELTA_DAYS
        if day_delta == 0:
            GLOBAL_TIME_DELTA_DAYS = 0
        else:
            GLOBAL_TIME_DELTA_DAYS += day_delta
        self.setup_person_ui()
        self.selected_prescription = None # nothing selected when we move forward through time
        self.refresh_dashboard()

    def open_history(self):
        dialog = HistoryWindow(self.db, self.person_id, self)
        dialog.exec()
        self.refresh_dashboard()

# ============================================================================
# SCREEN 6: HOME
# ============================================================================
class HomeWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.person_list = None
        self.db = db
        self.setWindowTitle("")
        self.resize(600, 400)
        self.setup_home_ui()
        self.load_persons()

    def setup_home_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        title = QLabel("Know Your Doses")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Person list
        self.person_list = QTableWidget()
        self.person_list.setColumnCount(2)
        self.person_list.setHorizontalHeaderLabels(["Name", "Date Added"])
        self.person_list.horizontalHeader().setStretchLastSection(True)
        self.person_list.cellDoubleClicked.connect(self.open_person_dashboard)
        self.person_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # disables all editing
        layout.addWidget(self.person_list)

        # New person button
        new_person_btn = QPushButton("+ New Person")
        new_person_btn.clicked.connect(self.new_person)
        layout.addWidget(new_person_btn)

        inv_btn = QPushButton("Inventory")
        inv_btn.clicked.connect(self.open_inventory)
        layout.addWidget(inv_btn)

    def open_inventory(self):
        dialog = InventoryWindow(self.db, self)
        if dialog.exec():
            self.refresh_dashboard()

    def load_persons(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, name, date_added FROM Person ORDER BY name")
        persons = cursor.fetchall()

        self.person_list.setRowCount(len(persons))
        for row, person in enumerate(persons):
            person_id, name, date_added = person
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, person_id)
            self.person_list.setItem(row, 0, name_item)
            self.person_list.setItem(row, 1, QTableWidgetItem(date_added))

    def new_person(self):
        dialog = NewPersonDialog(self.db, self)
        if dialog.exec():
            self.load_persons()

    def open_person_dashboard(self, row, _):
        person_id = self.person_list.item(row, 0).data(Qt.ItemDataRole.UserRole)
        dashboard = PersonDashboard(self.db, person_id, self)
        dashboard.show()



class ItemDialog(QDialog):
    def __init__(self, parent=None):
        UNITS = ["mg", "mcg", "ml", "set"]

        super().__init__(parent)
        self.setWindowTitle("New Item")
        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(255)
        self.name_edit.setMinimumWidth(160)
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setMinimum(0)
        self.quantity_spin.setMinimumWidth(60)
        self.vial_spin = QSpinBox()
        self.vial_spin.setMinimum(1)
        self.vial_spin.setMinimumWidth(60)
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(UNITS)
        self.reorder_edit = QLineEdit()
        self.reorder_edit.setMaxLength(255)
        self.reorder_edit.setMinimumWidth(160)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addRow("Name:", self.name_edit)
        layout.addRow("Quantity:", self.quantity_spin)
        layout.addRow("Vial Size:", self.vial_spin)
        layout.addRow("Unit:", self.unit_combo)
        layout.addRow("Reorder:", self.reorder_edit)
        layout.addRow(buttons)

    def get_data(self):
        return (
            self.name_edit.text().strip(),
            self.quantity_spin.value(),
            self.vial_spin.value(),
            self.unit_combo.currentText(),
            self.reorder_edit.text().strip()
        )

class InventoryWindow(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.table = None
        self.name_input = None
        self.db = db
        self.setModal(True)
        self.setWindowTitle("Inventory")
        self.setup_inventory_ui()
        self.resize(800, 600)

    def setup_inventory_ui(self):
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Name", "Quantity", "Vial Size", "Unit", "Add", "Subtract", "Reorder"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        new_btn = QPushButton("New")
        new_btn.clicked.connect(self.add_item)

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addWidget(new_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.setLayout(layout)
        self.load_data()

    def load_data(self):
        cur = self.db.conn.cursor()
        cur.execute("SELECT id, name, quantity, vial_size, unit, reorder_code FROM Inventory ORDER BY name, vial_size")
        rows = cur.fetchall()

        self.table.setRowCount(0)
        for row_data in rows:
            self.add_table_row(row_data)

    def add_table_row(self, data):
        row = self.table.rowCount()
        self.table.insertRow(row)
        item_id, name, qty, vial, unit, reorder_code = data

        self.table.setItem(row, 0, QTableWidgetItem(name))
        qty_item = QTableWidgetItem(str(qty))
        qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        qty_item.setData(Qt.ItemDataRole.UserRole, item_id)
        if qty == 0:
            qty_item.setBackground(QBrush(QColor("yellow")))
        self.table.setItem(row, 1, qty_item)
        self.table.setItem(row, 2, QTableWidgetItem(str(vial)))
        self.table.setItem(row, 3, QTableWidgetItem(unit))
        self.table.setItem(row, 6, QTableWidgetItem(reorder_code))

        plus_btn = QPushButton("➕")
        plus_btn.clicked.connect(lambda: self.modify_qty(item_id, 1))
        self.table.setCellWidget(row, 4, plus_btn)

        minus_btn = QPushButton("➖")
        minus_btn.clicked.connect(lambda: self.modify_qty(item_id, -1))
        minus_btn.setEnabled(qty > 0)
        self.table.setCellWidget(row, 5, minus_btn)

    def add_item(self):
        dialog = ItemDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, qty, vial, unit, reorder_code = dialog.get_data()
            if not name:
                return
            cur = self.db.conn.cursor()
            try:
                cur.execute("INSERT INTO Inventory (name, quantity, vial_size, unit, reorder_code) VALUES (?, ?, ?, ?, ?)",
                            (name, qty, vial, unit, reorder_code))
                self.db.conn.commit()
                item_id = cur.lastrowid
                self.add_table_row((item_id, name, qty, vial, unit, reorder_code))
            except sqlite3.IntegrityError:
                pass  # duplicate name

    def modify_qty(self, item_id, delta):
        cur = self.db.conn.cursor()
        cur.execute("SELECT quantity FROM Inventory WHERE id=?", (item_id,))
        current = cur.fetchone()[0]
        new_qty = max(0, current + delta)
        # not going to delete when quantity goes to zero, to keep the reorder information handy
        if new_qty >= 0:
            cur.execute("UPDATE Inventory SET quantity=? WHERE id=?", (new_qty, item_id))
            self.db.conn.commit()
            for row in range(self.table.rowCount()):
                if self.table.item(row, 1).data(Qt.ItemDataRole.UserRole) == item_id:
                    self.table.item(row, 1).setText(str(new_qty))
                    self.table.cellWidget(row, 5).setEnabled(new_qty > 0)
                    break

# ============================================================================
# MAIN APPLICATION
# ============================================================================
def main():
    app = QApplication(sys.argv)

    # Initialize database
    db = Database()

    # Show home window
    home = HomeWindow(db)
    home.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()