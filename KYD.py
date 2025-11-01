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

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QDialog, QFormLayout, QComboBox, QSpinBox,
    QGridLayout, QFrame, QDateEdit, QHeaderView
)
# from dateutil.relativedelta import relativedelta


# ============================================================================
# CENTRALIZED DATE FUNCTION FOR DEBUGGING
# ============================================================================
def get_today():
    """Centralized function to get today's date. Modify this for testing."""
    return date.today()
    # For testing future dates, uncomment and modify:
    # return date(2025, 11, 10)

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

        self.conn.commit()

    def close(self):
        self.conn.close()

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

    if cycling_on and cycling_off and freq in ['daily', 'weekly']:
        cycle_length = cycling_on + cycling_off
        days_since_start = (check_date - date_first).days
        position_in_cycle = days_since_start % cycle_length

        if position_in_cycle >= cycling_on:
            return 0  # In OFF phase

    # Check frequency
    if freq == 'daily':
        if check_date >= date_first:
            return 1
    elif freq == 'twice-daily':
        if check_date >= date_first:
            return 2
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

# def get_next_due_date(prescription, db):
#     """Calculate the next due date for a prescription."""
#     freq = prescription['frequency']
#     date_first = datetime.strptime(prescription['date_first_prescribed'], '%Y-%m-%d').date()
#     date_last_admin = prescription.get('date_last_administered')
#
#     if date_last_admin:
#         last_admin = datetime.strptime(date_last_admin, '%Y-%m-%d').date()
#     else:
#         last_admin = None
#
#     today = get_today()
#
#     # Start from last administered or first prescribed
#     start_date = last_admin if last_admin else date_first
#
#     if freq in ['daily', 'twice-daily']:
#         # For daily, check cycling
#         cycling_on = prescription.get('cycling_days_on')
#         cycling_off = prescription.get('cycling_days_off')
#
#         if cycling_on and cycling_off:
#             cycle_length = cycling_on + cycling_off
#             check_date = start_date + timedelta(days=1) if last_admin else start_date
#
#             while check_date <= today + timedelta(days=365):  # Search up to a year
#                 days_since_start = (check_date - date_first).days
#                 position_in_cycle = days_since_start % cycle_length
#
#                 if position_in_cycle < cycling_on:
#                     return check_date
#                 check_date += timedelta(days=1)
#         else:
#             return start_date + timedelta(days=1) if last_admin else start_date
#
#     elif freq == 'weekly':
#         next_date = start_date + timedelta(days=7) if last_admin else start_date
#         return next_date
#
#     elif freq == 'monthly':
#         if last_admin:
#             next_date = last_admin + relativedelta(months=1)
#         else:
#             next_date = date_first
#
#         # Adjust for end of month
#         target_day = date_first.day
#         if target_day > last_day_of_month(next_date):
#             next_date = next_date.replace(day=last_day_of_month(next_date))
#         else:
#             next_date = next_date.replace(day=target_day)
#         return next_date
#
#     elif freq == 'quarterly':
#         if last_admin:
#             next_date = last_admin + relativedelta(months=3)
#         else:
#             next_date = date_first
#
#         # Adjust for end of month
#         target_day = date_first.day
#         if target_day > last_day_of_month(next_date):
#             next_date = next_date.replace(day=last_day_of_month(next_date))
#         else:
#             next_date = next_date.replace(day=target_day)
#         return next_date
#
#     return today

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
        self.unit_input.addItems(["mg", "mcg", "ml"])
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
        cursor.execute("SELECT * FROM HistoricalDose WHERE id = ?", (self.dose_id,))
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
        cursor.execute("SELECT * FROM Prescription WHERE person_id = ?", (self.person_id,))
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
        edit.setMaximumDate(QDate.currentDate().addDays(31))
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
        unit_combo.addItems(["mg", "mcg", "ml"])
        unit_combo.setCurrentText(unit)
        unit_combo.currentTextChanged.connect(lambda: self.mark_changed(row, 2))
        self.prescription_table.setCellWidget(row, 2, unit_combo)

        freq_combo = QComboBox()
        freq_combo.addItems(["daily", "twice-daily", "weekly", "monthly", "quarterly"])
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
        cursor = self.db.conn.cursor()

        for row in range(self.prescription_table.rowCount()):
            compound = self.prescription_table.item(row, 0).text().strip()
            compound = re.sub(r'\s+', ' ', compound).strip()
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

            if cycle_on and (cycle_on < 1 or cycle_on > 30):
                QMessageBox.warning(self, "Validation Error", f"Row {row+1}: Days on must be 1-30.")
                return
            if cycle_off and (cycle_off < 1 or cycle_off > 180):
                QMessageBox.warning(self, "Validation Error", f"Row {row+1}: Days off must be 1-180.")
                return

            date_first = self._get_date_from_cell(row, 6)
            date_modified = self._get_date_from_cell(row, 7)
            date_last_admin = self._get_date_from_cell(row, 8)  # returns None if empty
            # date_first = self.table.item(row, 6).text()
            # date_modified = self.table.item(row, 7).text()
            # date_last_admin = self.table.item(row, 8).text() if self.table.item(row, 8).text() else None

            icon_str = self._get_date_from_cell(row, 9)
            if icon_str is None:
                icon_str = "💊"

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
        self.details_frame = None
        self.weekly_grid = None
        self.person_name = None
        self.db = db
        self.person_id = person_id
        self.selected_prescription = None
        self.load_person()
        self.add_missed_doses_yesterday()
        self.setup_person_ui()
        self.refresh_dashboard()

    def load_person(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT name FROM Person WHERE id = ?", (self.person_id,))
        result = cursor.fetchone()
        self.person_name = result[0] if result else "Unknown"

    def add_missed_doses_yesterday(self):
        """Add zero-amount doses for yesterday if they were missed."""
        yesterday = get_today() - timedelta(days=1)
        cursor = self.db.conn.cursor()

        # Get all prescriptions
        cursor.execute("SELECT * FROM Prescription WHERE person_id = ?", (self.person_id,))
        prescriptions = cursor.fetchall()

        for presc in prescriptions:
            prescription = {
                'id': presc[0],
                'date_first_prescribed': presc[2],
                'frequency': presc[7],
                'cycling_days_on': presc[8],
                'cycling_days_off': presc[9],
                'compound_name': presc[5],
                'unit': presc[6],
                'icon_type': presc[11]
            }

            expected_doses = is_dose_due_on_date(prescription, yesterday)

            if expected_doses > 0:
                # Check how many doses were actually administered
                cursor.execute("""
                    SELECT COUNT(*) FROM HistoricalDose 
                    WHERE person_id = ? AND prescription_id = ? AND date_administered = ?
                """, (self.person_id, prescription['id'], yesterday.isoformat()))

                actual_count = cursor.fetchone()[0]

                if actual_count == 0:
                    # Add missed dose records
                    for dose_num in range(1, expected_doses + 1):
                        cursor.execute("""
                            INSERT INTO HistoricalDose 
                            (person_id, prescription_id, date_administered, compound_name, amount, unit, dose_number)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (self.person_id, prescription['id'], yesterday.isoformat(),
                              prescription['compound_name'], 0, prescription['unit'], dose_num))

        self.db.conn.commit()

    def setup_person_ui(self):
        self.setWindowTitle(f"Dashboard - {self.person_name}")
        self.resize(900, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel(self.person_name)
        header_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        header_layout.addWidget(header_label)
        edit_btn = QPushButton("Prescriptions")
        edit_btn.clicked.connect(self.open_config)
        header_layout.addWidget(edit_btn)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

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
            label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.weekly_grid.addWidget(label, 0, col)

        main_layout.addLayout(self.weekly_grid)

        # Details frame
        self.details_frame = QFrame()
        self.details_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.details_layout = QVBoxLayout(self.details_frame)
        main_layout.addWidget(self.details_frame)

        # History button
        history_btn = QPushButton("History")
        history_btn.clicked.connect(self.open_history)
        main_layout.addWidget(history_btn)

    def refresh_dashboard(self):
        self.clear_weekly_grid()
        self.populate_weekly_grid()
        self.update_details_area()

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
        cursor.execute("SELECT * FROM Prescription WHERE person_id = ?", (self.person_id,))
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

    def select_prescription(self, prescription):
        self.selected_prescription = prescription
        self.update_details_area()

    def update_details_area(self):
        # Clear current layout
        for _ in reversed(range(self.details_layout.count())):
            item = self.details_layout.takeAt(0)
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
                details_text += f"<b>Cycling:</b> {presc['cycling_days_on']} days on, {presc['cycling_days_off']} days off<br>"

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

                if remaining > 0:
                    administer_btn = QPushButton(f"Administer Dose ({remaining} remaining)")
                    administer_btn.clicked.connect(lambda: self.administer_selected_dose(remaining))
                    self.details_layout.addWidget(administer_btn)

            # Edit and delete buttons
            # button_layout = QHBoxLayout()
            # edit_btn = QPushButton(f"✏️ Edit {presc['compound_name']} Prescription")
            # delete_btn = QPushButton(f"❌ Delete {presc['compound_name']} Prescription")
            # edit_btn.clicked.connect(self.edit_selected_prescription)
            # delete_btn.clicked.connect(self.delete_selected_prescription)
            # button_layout.addWidget(edit_btn)
            # button_layout.addWidget(delete_btn)
            # self.details_layout.addLayout(button_layout)

        else:
            # Show doses due today
            today = get_today()
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT * FROM Prescription WHERE person_id = ?", (self.person_id,))
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
                    'cycling_days_off': presc[10]
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
                title = QLabel("<b>Doses Due Today:</b>")
                self.details_layout.addWidget(title)

                for prescription, remaining in due_today:
                    dose_widget = QWidget()
                    dose_layout = QHBoxLayout(dose_widget)

                    info_label = QLabel(f"{prescription['compound_name']} - {prescription['amount']} {prescription['unit']} ({remaining} remaining)")
                    dose_layout.addWidget(info_label)

                    administer_btn = QPushButton("Administer")
                    administer_btn.clicked.connect(lambda checked, p=prescription, r=remaining: self.administer_dose_quick(p, r))
                    dose_layout.addWidget(administer_btn)

                    self.details_layout.addWidget(dose_widget)
            else:
                label = QLabel("No doses due today.")
                self.details_layout.addWidget(label)

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
        layout.addWidget(self.person_list)

        # New person button
        new_person_btn = QPushButton("+ New Person")
        new_person_btn.clicked.connect(self.new_person)
        layout.addWidget(new_person_btn)

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