"""UC-02: календарь интервалов и выбор перемещений за период."""

import argparse
import calendar
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
NO_INTERVALS = "Временные интервалы отсутствуют."


def parse_time(value: str, label: str) -> datetime:
    if not isinstance(value, str) or not TIMESTAMP.fullmatch(value):
        raise ValueError(f"{label} должно быть временем ISO 8601 со смещением.")
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{label} содержит недопустимую дату или время.") from error


def read_records(data: dict, key: str) -> dict[int, dict]:
    records = data.get(key) if isinstance(data, dict) else None
    if not isinstance(records, list):
        raise ValueError(f"Ожидается объект JSON с массивом {key}.")

    index = {}
    for record in records:
        identifier = record.get("id") if isinstance(record, dict) else None
        if type(identifier) is not int or identifier < 1 or identifier in index:
            raise ValueError(f"В массиве {key} ожидаются уникальные положительные целые ID.")
        index[identifier] = record
    return index


def list_intervals(data: dict) -> list[dict]:
    intervals = []
    for identifier, interval in read_records(data, "intervals").items():
        start = parse_time(interval.get("start"), f"Начало интервала {identifier}")
        end = parse_time(interval.get("end"), f"Окончание интервала {identifier}")
        if start > end:
            raise ValueError(f"У интервала {identifier} начало позднее окончания.")
        intervals.append((start, identifier, interval))

    return [interval for _, _, interval in sorted(intervals)]


def get_interval_movements(data: dict, interval_id: int) -> dict | None:
    if type(interval_id) is not int or interval_id < 1:
        raise ValueError("ID интервала должен быть положительным целым числом.")

    interval = next((item for item in list_intervals(data) if item["id"] == interval_id), None)
    if interval is None:
        return None

    start = datetime.fromisoformat(interval["start"])
    end = datetime.fromisoformat(interval["end"])
    movements = []
    for identifier, movement in read_records(data, "movements").items():
        timestamp = parse_time(movement.get("occurred_at"), f"Время события {identifier}")
        if not start <= timestamp <= end:
            continue

        species = movement.get("species")
        if not isinstance(species, str) or not species.strip():
            raise ValueError(f"У записи {identifier} отсутствует вид рыбы.")
        for field in ("count", "destination_pool_id"):
            value = movement.get(field)
            if type(value) is not int or value < 1:
                raise ValueError(f"У записи {identifier} поле {field} должно быть положительным целым.")
        summary = {
            "id": identifier,
            "occurred_at": movement["occurred_at"],
            "species": species,
            "count": movement["count"],
            "destination_pool_id": movement["destination_pool_id"],
        }
        movements.append((timestamp, identifier, summary))

    result = {"interval": interval, "movements": [item for _, _, item in sorted(movements)]}
    if not movements:
        result["message"] = "Перемещения за выбранный интервал отсутствуют."
    return result


def show_calendar(intervals: list[dict]) -> None:
    if not intervals:
        print(NO_INTERVALS)
        return
    months = {interval["start"][:7] for interval in intervals}
    for month in sorted(months):
        year, number = map(int, month.split("-"))
        print(calendar.month(year, number))
    for interval in intervals:
        print(f'{interval["id"]}. {interval["start"]} → {interval["end"]}')


def read_selection(prompt: str) -> int | None:
    try:
        value = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if not value or value.casefold() == "отмена":
        return None
    if not value.isascii() or not value.isdecimal():
        raise ValueError("Введите положительный целый ID или «отмена».")
    identifier = int(value)
    if identifier < 1:
        raise ValueError("Введите положительный целый ID или «отмена».")
    return identifier


def browse_calendar(data: dict) -> None:
    intervals = list_intervals(data)
    show_calendar(intervals)
    if not intervals:
        return

    interval_id = read_selection("ID интервала или «отмена»: ")
    if interval_id is not None:
        result = get_interval_movements(data, interval_id)
        if result is None:
            raise LookupError(f"Интервал {interval_id} не найден.")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["movements"]:
            movement_id = read_selection("ID перемещения для UC-03 или «отмена»: ")
            if movement_id is not None:
                if not any(item["id"] == movement_id for item in result["movements"]):
                    raise LookupError(f"В выбранном интервале нет перемещения {movement_id}.")
                print(json.dumps({"movement_id": movement_id}))
                return

    print("Просмотр завершён. Календарь доступных интервалов.")
    show_calendar(intervals)


def main() -> int:
    parser = argparse.ArgumentParser(description="Просмотр интервалов и перемещений.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("interval_id", nargs="?", type=int, help="ID интервала")
    mode.add_argument("--interactive", action="store_true", help="показать текстовый календарь")
    parser.add_argument("--data", type=Path, default=DEMO_DATA, help="путь к файлу JSON")
    args = parser.parse_args()

    try:
        with args.data.open(encoding="utf-8") as source:
            data = json.load(source)
        if args.interactive:
            browse_calendar(data)
            return 0
        if args.interval_id is None:
            intervals = list_intervals(data)
            result = {"intervals": intervals}
            if not intervals:
                result["message"] = NO_INTERVALS
        else:
            result = get_interval_movements(data, args.interval_id)
            if result is None:
                raise LookupError(f"Интервал {args.interval_id} не найден.")
    except LookupError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, RecursionError) as error:
        print(f"Ошибка. {error}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
