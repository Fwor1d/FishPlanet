"""UC-03: просмотр сведений о перемещении из локального JSON."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys


DEMO_DATA = Path(__file__).with_name("demo.json")
TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)


def find_record(data: dict, collection: str, record_id: int) -> dict | None:
    records = data.get(collection)
    if not isinstance(records, list):
        raise ValueError(f"Поле {collection} должно быть массивом.")

    seen = set()
    selected = None
    for record in records:
        identifier = record.get("id") if isinstance(record, dict) else None
        if type(identifier) is not int or identifier < 1:
            raise ValueError(f"В массиве {collection} есть некорректный ID.")
        if identifier in seen:
            raise ValueError(f"В массиве {collection} повторяется ID {identifier}.")
        seen.add(identifier)
        if identifier == record_id:
            selected = record
    return selected


def get_movement_details(data: dict, movement_id: int) -> dict | None:
    if type(movement_id) is not int or movement_id < 1:
        raise ValueError("ID перемещения должен быть положительным целым числом.")
    if not isinstance(data, dict):
        raise ValueError("Ожидается объект JSON.")

    movement = find_record(data, "movements", movement_id)
    if movement is None:
        return None

    for field, minimum in (("count", 1), ("destination_pool_id", 1), ("duration_seconds", 0)):
        value = movement.get(field)
        if type(value) is not int or value < minimum:
            raise ValueError(f"Поле {field} должно быть целым числом от {minimum}.")

    species = movement.get("species")
    if not isinstance(species, str) or not species.strip():
        raise ValueError("Поле species должно содержать название вида.")

    occurred_at = movement.get("occurred_at")
    if not isinstance(occurred_at, str) or not TIMESTAMP.fullmatch(occurred_at):
        raise ValueError("Поле occurred_at должно содержать дату и время ISO 8601 со смещением.")
    try:
        datetime.fromisoformat(occurred_at)
    except ValueError as error:
        raise ValueError("Поле occurred_at содержит недопустимую дату или время.") from error

    pool = find_record(data, "pools", movement["destination_pool_id"])
    name = pool.get("name") if pool is not None else None
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Не удалось определить название бассейна назначения.")

    return {
        "id": movement_id,
        "species": species,
        "count": movement["count"],
        "destination_pool_id": movement["destination_pool_id"],
        "destination_pool_name": name,
        "occurred_at": occurred_at,
        "duration_seconds": movement["duration_seconds"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Детали перемещения рыб по ID.")
    parser.add_argument("movement_id", nargs="?", help="положительный целый ID")
    parser.add_argument("--data", type=Path, default=DEMO_DATA, help="путь к файлу JSON")
    args = parser.parse_args()

    try:
        raw_id = args.movement_id
        if raw_id is None:
            raw_id = input("Введите ID перемещения: ")
        raw_id = raw_id.strip()
        if not raw_id.isascii() or not raw_id.isdecimal():
            raise ValueError
        movement_id = int(raw_id)
        if movement_id < 1:
            raise ValueError
    except (EOFError, ValueError):
        print("ID перемещения должен быть положительным целым числом.", file=sys.stderr)
        return 2

    try:
        with args.data.open(encoding="utf-8") as source:
            details = get_movement_details(json.load(source), movement_id)
    except (OSError, ValueError, RecursionError) as error:
        print(f"Не удалось загрузить сведения о перемещении. {error}", file=sys.stderr)
        return 2

    if details is None:
        print(f"Запись о перемещении недоступна (ID {movement_id}).", file=sys.stderr)
        return 1

    print(json.dumps(details, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
