"""
Build the Section Timetable workbook.

The output mirrors the registrar's own file (BSIT-Final.xlsx): one stacked block
per section, a caption line, the SUBJECTS banner, the eight columns and a
"Total — N subjects" line. It is generated from the exact context the page
renders, so the download can never drift from what is on screen.
"""

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HEADERS = ('Code', 'Description', 'Faculty', 'Day', 'Time', 'Room', 'Units', 'Hrs/Wk')
COLUMN_WIDTHS = (12, 46, 28, 8, 21, 22, 7, 8)

THIN = Side(style='thin', color='B7B7B7')
CELL_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

TITLE_FONT = Font(name='Calibri', size=14, bold=True, color='111111')
BANNER_FONT = Font(name='Calibri', size=11, bold=True, color='111111')
HEADER_FONT = Font(name='Calibri', size=10, bold=True, color='111111')
BODY_FONT = Font(name='Calibri', size=10, color='111111')
TOTAL_FONT = Font(name='Calibri', size=10, bold=True, color='111111')

BANNER_FILL = PatternFill('solid', fgColor='F2F2F2')
HEADER_FILL = PatternFill('solid', fgColor='FAFAFA')
TOTAL_FILL = PatternFill('solid', fgColor='F7F7F7')

LEFT = Alignment(horizontal='left', vertical='center', wrap_text=True)
CENTER = Alignment(horizontal='center', vertical='center')
RIGHT = Alignment(horizontal='right', vertical='center')


def _write_caption(sheet, row, text):
    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(HEADERS))
    cell = sheet.cell(row=row, column=1, value=text)
    cell.font = TITLE_FONT
    cell.alignment = Alignment(horizontal='left', vertical='center')
    sheet.row_dimensions[row].height = 22


def _write_section_row(sheet, row, text):
    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(HEADERS))
    cell = sheet.cell(row=row, column=1, value=text)
    cell.font = Font(name='Calibri', size=12, bold=True, color='111111')
    cell.alignment = Alignment(horizontal='left', vertical='center')
    sheet.row_dimensions[row].height = 20


def _write_banner(sheet, row, text):
    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(HEADERS))
    cell = sheet.cell(row=row, column=1, value=text)
    cell.font = BANNER_FONT
    cell.fill = BANNER_FILL
    cell.alignment = Alignment(horizontal='left', vertical='center')
    cell.border = CELL_BORDER


def _write_headers(sheet, row):
    for index, title in enumerate(HEADERS, start=1):
        cell = sheet.cell(row=row, column=index, value=title)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = CELL_BORDER
    sheet.row_dimensions[row].height = 18


def _write_rows(sheet, start_row, rows):
    row_index = start_row
    for data in rows:
        room = data['room_main']
        if data.get('room_building'):
            room = f"{data['room_main']} · {data['room_building']}"
        values = (
            data['code'],
            data['description'],
            data['faculty'],
            data['days'],
            data['time'],
            room,
            data['units'],
            data['hours_label'],
        )
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=row_index, column=column, value=value)
            cell.font = BODY_FONT
            cell.border = CELL_BORDER
            if column == 1:
                cell.alignment = LEFT
            elif column in (2, 3):
                cell.alignment = LEFT
            elif column == 6:
                cell.alignment = CENTER
            else:
                cell.alignment = CENTER
        row_index += 1
    return row_index


def _write_total(sheet, row, sheet_data):
    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(HEADERS) - 2)
    label = sheet.cell(row=row, column=1, value=f"Total — {sheet_data['subject_count']} subjects")
    label.font = TOTAL_FONT
    label.fill = TOTAL_FILL
    label.alignment = RIGHT
    label.border = CELL_BORDER

    units = sheet.cell(row=row, column=len(HEADERS) - 1, value=sheet_data['total_units'])
    units.font = TOTAL_FONT
    units.fill = TOTAL_FILL
    units.alignment = CENTER
    units.border = CELL_BORDER

    hours = sheet.cell(row=row, column=len(HEADERS), value=float(sheet_data['total_hours']))
    hours.font = TOTAL_FONT
    hours.fill = TOTAL_FILL
    hours.alignment = CENTER
    hours.border = CELL_BORDER


def build_timetable_workbook(context):
    """Return the .xlsx bytes for the current filter selection."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = (context['program'].code if context['program'] else 'Timetable')[:31]

    for index, width in enumerate(COLUMN_WIDTHS, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width

    program_name = context['program'].name if context['program'] else 'Degree Program'
    semester = context['semester_label'] or 'Semester'
    year_label = context['academic_year_label'] or '—'

    row = 1
    if not context['sheets']:
        _write_caption(sheet, row, f'{program_name} | {semester}, A.Y. {year_label}')
        sheet.merge_cells(start_row=row + 1, start_column=1, end_row=row + 1, end_column=len(HEADERS))
        message = sheet.cell(row=row + 1, column=1, value=context.get('no_data_reason') or 'No timetable on file.')
        message.font = BODY_FONT
        message.alignment = LEFT
        sheet.freeze_panes = 'A3'
        return _to_bytes(workbook)

    for sheet_data in context['sheets']:
        caption = (
            f'{program_name} | {semester}, A.Y. {year_label} | '
            f"{sheet_data['total_units']} units, {sheet_data['subject_count']} subjects"
        )
        _write_caption(sheet, row, caption)
        row += 1
        _write_section_row(sheet, row, sheet_data['section'])
        row += 1
        _write_banner(sheet, row, 'SUBJECTS')
        row += 1
        _write_headers(sheet, row)
        row += 1
        row = _write_rows(sheet, row, sheet_data['rows'])
        _write_total(sheet, row, sheet_data)
        row += 3  # blank spacer between sections

    sheet.freeze_panes = 'A4'
    return _to_bytes(workbook)


def _to_bytes(workbook):
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
