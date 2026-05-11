import json
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError as exc:
    raise SystemExit("openpyxl is required to rebuild UCS data JSON") from exc


SHEET_NAME = "UCS v8.2.1"
HEADER_ROW = 3
DATA_ROW = 4
FIELDS = [
    "Category",
    "SubCategory",
    "CatID",
    "CatShort",
    "Explanations",
    "Synonyms - Comma Separated",
    "Category_zh",
    "SubCategory_zh",
    "Synonyms_zh",
]


def split_terms(value):
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    pieces = []
    for part in text.replace("、", ",").replace("，", ",").split(","):
        term = part.strip()
        if term and term not in pieces:
            pieces.append(term)
    return pieces


def main():
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: python build_ucs_data.py <UCS translations xlsx> <output json>"
        )

    xlsx_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    workbook = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    worksheet = workbook[SHEET_NAME]

    headers = [cell.value for cell in worksheet[HEADER_ROW]]
    indexes = {}
    for field in FIELDS:
        if field not in headers:
            raise SystemExit(f"Missing expected field: {field}")
        indexes[field] = headers.index(field)

    entries = []
    seen_cat_ids = set()
    for row in worksheet.iter_rows(min_row=DATA_ROW, values_only=True):
        cat_id = row[indexes["CatID"]]
        if not cat_id:
            continue
        cat_id = str(cat_id).strip()
        if cat_id in seen_cat_ids:
            raise SystemExit(f"Duplicate CatID: {cat_id}")
        seen_cat_ids.add(cat_id)

        entries.append(
            {
                "category": str(row[indexes["Category"]] or "").strip(),
                "subcategory": str(row[indexes["SubCategory"]] or "").strip(),
                "cat_id": cat_id,
                "cat_short": str(row[indexes["CatShort"]] or "").strip(),
                "explanation": str(row[indexes["Explanations"]] or "").strip(),
                "en_synonyms": split_terms(row[indexes["Synonyms - Comma Separated"]]),
                "zh_category": str(row[indexes["Category_zh"]] or "").strip(),
                "zh_subcategory": str(row[indexes["SubCategory_zh"]] or "").strip(),
                "zh_synonyms": split_terms(row[indexes["Synonyms_zh"]]),
            }
        )

    payload = {
        "source": "UCS v8.2.1 Full Translations.xlsx",
        "sheet": SHEET_NAME,
        "entry_count": len(entries),
        "entries": entries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(entries)} UCS entries to {output_path}")


if __name__ == "__main__":
    main()
