"""UC-01: подсчёт рыб по бассейну, периоду и видам."""

import argparse
from collections import Counter
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


def list_pools(data: dict) -> dict[int, str]:
    pools = {}
    for identifier, pool in read_records(data, "pools").items():
        name = pool.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"У бассейна {identifier} отсутствует название.")
        pools[identifier] = name
    return pools


def count_fish(data: dict, pool_id: int, start: str, end: str) -> dict:
    if type(pool_id) is not int or pool_id < 1:
        raise ValueError("ID бассейна должен быть положительным целым числом.")
    first = parse_time(start, "Начало интервала")
    last = parse_time(end, "Окончание интервала")
    if first > last:
        raise ValueError("Начало интервала не может быть позднее окончания.")

    pools = list_pools(data)
    if pool_id not in pools:
        raise ValueError(f"Бассейн {pool_id} не найден.")

    counts = Counter()
    for identifier, movement in read_records(data, "movements").items():
        destination = movement.get("destination_pool_id")
        species = movement.get("species")
        quantity = movement.get("count")
        timestamp = parse_time(movement.get("occurred_at"), f"Время события {identifier}")
        if type(destination) is not int or destination not in pools:
            raise ValueError(f"У записи {identifier} неизвестный бассейн назначения.")
        if not isinstance(species, str) or not species.strip():
            raise ValueError(f"У записи {identifier} отсутствует вид рыбы.")
        if type(quantity) is not int or quantity < 1:
            raise ValueError(f"У записи {identifier} ожидается положительное целое количество.")
        if destination == pool_id and first <= timestamp <= last:
            counts[species] += quantity

    result = {
        "pool_id": pool_id,
        "pool_name": pools[pool_id],
        "start": start,
        "end": end,
        "counts_by_species": dict(sorted(counts.items())),
        "total": counts.total(),
    }
    if not counts:
        result["message"] = "За выбранный период перемещения не зарегистрированы."
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Подсчёт рыб по видам в бассейне назначения.")
    parser.add_argument("pool_id", nargs="?", type=int, help="ID бассейна назначения")
    parser.add_argument("start", nargs="?", help="начало периода в ISO 8601 со смещением")
    parser.add_argument("end", nargs="?", help="конец периода в ISO 8601 со смещением")
    parser.add_argument("--data", type=Path, default=DEMO_DATA, help="путь к файлу JSON")
    args = parser.parse_args()
    query = (args.pool_id, args.start, args.end)
    if any(value is not None for value in query) and None in query:
        parser.error("Укажите ID бассейна, начало и окончание периода.")

    try:
        with args.data.open(encoding="utf-8") as source:
            data = json.load(source)
        if args.pool_id is None:
            pools = list_pools(data)
            result = {"pools": [{"id": key, "name": pools[key]} for key in sorted(pools)]}
        else:
            result = count_fish(data, args.pool_id, args.start, args.end)
    except (OSError, ValueError, RecursionError) as error:
        print(f"Ошибка. {error}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
