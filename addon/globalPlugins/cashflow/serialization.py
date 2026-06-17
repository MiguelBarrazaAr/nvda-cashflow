from __future__ import annotations

import csv
import json
import zipfile
from dataclasses import asdict
from html import escape
from io import StringIO
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape


CSV_FIELDS = [
	"id",
	"orden",
	"tipo",
	"nombre",
	"importe",
	"categoria",
	"anio",
	"mes",
	"dia",
	"recurrencia",
	"duracion_meses",
]


def export_rows_to_csv(rows: list[dict], path: str) -> None:
	with open(path, "w", encoding="utf-8-sig", newline="") as file:
		writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
		writer.writeheader()
		for row in rows:
			writer.writerow(_row_for_csv(row))


def export_rows_to_json(rows: list[dict], path: str) -> None:
	payload = {
		"formato": "cashflow-items",
		"version": 1,
		"items": rows,
	}
	with open(path, "w", encoding="utf-8") as file:
		json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)


def export_rows_to_xlsx(rows: list[dict], path: str) -> None:
	header = CSV_FIELDS
	sheet_rows = [header] + [[_string_value(_row_for_csv(row).get(column, "")) for column in header] for row in rows]
	_content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
	<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
	<Default Extension="xml" ContentType="application/xml"/>
	<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
	<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
	_root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
	<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
	_workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
	<sheets>
		<sheet name="Cashflow" sheetId="1" r:id="rId1"/>
	</sheets>
</workbook>"""
	_workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
	<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
	_sheet = _build_sheet_xml(sheet_rows)
	with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
		archive.writestr("[Content_Types].xml", _content_types)
		archive.writestr("_rels/.rels", _root_rels)
		archive.writestr("xl/workbook.xml", _workbook)
		archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels)
		archive.writestr("xl/worksheets/sheet1.xml", _sheet)


def import_rows_from_csv(path: str) -> list[dict]:
	with open(path, "r", encoding="utf-8-sig", newline="") as file:
		reader = csv.DictReader(file)
		return [dict(row) for row in reader]


def import_rows_from_json(path: str) -> list[dict]:
	with open(path, "r", encoding="utf-8") as file:
		payload = json.load(file)
	if isinstance(payload, list):
		return [dict(row) for row in payload]
	if isinstance(payload, dict):
		items = payload.get("items", [])
		if isinstance(items, list):
			return [dict(row) for row in items]
	return []


def _row_for_csv(row: dict) -> dict:
	normalized = {
		"id": row.get("id", ""),
		"orden": row.get("orden", ""),
		"tipo": row.get("tipo", ""),
		"nombre": row.get("nombre", ""),
		"importe": row.get("importe", ""),
		"categoria": row.get("categoria", ""),
		"anio": "",
		"mes": "",
		"dia": "",
		"recurrencia": "",
		"duracion_meses": "",
	}
	if row.get("fecha_inicio"):
		try:
			year, month, day = row["fecha_inicio"].split("-")
			normalized["anio"] = year
			normalized["mes"] = month
			normalized["dia"] = day
		except Exception:
			pass
	recurrence = row.get("recurrencia")
	if isinstance(recurrence, dict):
		normalized["recurrencia"] = recurrence.get("tipo", "")
		normalized["duracion_meses"] = recurrence.get("duracion_meses", "")
	else:
		normalized["recurrencia"] = recurrence or ""
		normalized["duracion_meses"] = row.get("duracion_meses", "")
	for field in CSV_FIELDS:
		normalized.setdefault(field, row.get(field, ""))
	return normalized


def _string_value(value) -> str:
	if value is None:
		return ""
	return str(value)


def _build_sheet_xml(rows: list[list[str]]) -> str:
	xml_rows = []
	for row_index, row in enumerate(rows, start=1):
		cells = []
		for col_index, value in enumerate(row, start=1):
			ref = f"{_column_name(col_index)}{row_index}"
			if row_index == 1:
				cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(value)}</t></is></c>')
			elif _is_integer(value):
				cells.append(f'<c r="{ref}"><v>{xml_escape(value)}</v></c>')
			else:
				cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(value)}</t></is></c>')
		xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
	return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
	<sheetData>
		{rows}
	</sheetData>
</worksheet>""".format(rows="".join(xml_rows))


def _column_name(index: int) -> str:
	name = ""
	while index:
		index, rem = divmod(index - 1, 26)
		name = chr(65 + rem) + name
	return name


def _is_integer(value: str) -> bool:
	try:
		int(str(value))
		return True
	except Exception:
		return False
