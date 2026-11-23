"""UC-04: контроль доступа и имитация запроса управления."""

import argparse
import json
from pathlib import Path
import sys


DEMO_DATA = Path(__file__).with_name("demo.json")
ACTION = "simulate"


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


def get_control_options(data: dict, user_id: int) -> dict:
    if type(user_id) is not int or user_id < 1:
        raise ValueError("ID пользователя должен быть положительным целым числом.")
    user = read_records(data, "users").get(user_id)
    if user is None or user.get("role") != "technical_admin":
        raise PermissionError("Управление доступно только техническому администратору.")

    pools = {}
    for identifier, pool in read_records(data, "pools").items():
        name = pool.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"У бассейна {identifier} отсутствует название.")
        pools[identifier] = name
    return {
        "pools": [{"id": key, "name": pools[key]} for key in sorted(pools)],
        "actions": [ACTION],
    }


def select_pool(options: dict, pool_id: int) -> dict:
    if type(pool_id) is not int or pool_id < 1:
        raise ValueError("ID бассейна должен быть положительным целым числом.")
    for pool in options["pools"]:
        if pool["id"] == pool_id:
            return pool
    raise ValueError(f"Бассейн {pool_id} не найден.")


def process_request(
    data: dict,
    user_id: int,
    pool_id: int,
    action: str,
    confirmed: bool,
    simulate_failure: bool = False,
) -> dict:
    options = get_control_options(data, user_id)
    pool = select_pool(options, pool_id)
    if action not in options["actions"]:
        raise ValueError(f"Действие {action!r} не поддерживается.")
    if type(confirmed) is not bool or type(simulate_failure) is not bool:
        raise ValueError("Подтверждение и режим имитации ошибки должны быть логическими значениями.")

    result = {"user_id": user_id, "pool_id": pool_id, "pool_name": pool["name"], "action": action}
    if not confirmed:
        return dict(result, status="cancelled", message="Запрос отменён, операция не выполнялась.")
    if simulate_failure:
        return dict(result, status="failed", message="Операция не выполнена. Имитирована ошибка.")
    return dict(result, status="simulated", message="Имитационный запрос обработан.")


def ask_confirmation(options: dict, pool_id: int, action: str) -> bool:
    pool = select_pool(options, pool_id)
    if action not in options["actions"]:
        raise ValueError(f"Действие {action!r} не поддерживается.")
    try:
        reply = input(f'Подтвердить действие {action} для «{pool["name"]}»? [да/нет] ').strip().casefold()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if reply not in {"", "да", "нет"}:
        raise ValueError("Для подтверждения введите «да» или «нет».")
    return reply == "да"


def main() -> int:
    parser = argparse.ArgumentParser(description="Имитация управления перемещениями рыб.")
    parser.add_argument("user_id", type=int, help="ID пользователя в демонстрационном справочнике")
    parser.add_argument("--pool-id", type=int, help="ID бассейна, без него выводится список действий")
    parser.add_argument("--action", help=f"имитационное действие, по умолчанию {ACTION}")
    parser.add_argument("--data", type=Path, default=DEMO_DATA, help="путь к файлу JSON")
    parser.add_argument("--simulate-error", action="store_true", help="имитировать ошибку операции")
    decision = parser.add_mutually_exclusive_group()
    decision.add_argument("--confirm", action="store_true", help="подтвердить запрос")
    decision.add_argument("--cancel", action="store_true", help="отменить запрос")
    args = parser.parse_args()
    if args.pool_id is None and (args.action is not None or args.confirm or args.cancel or args.simulate_error):
        parser.error("Для обработки действия укажите --pool-id.")

    try:
        with args.data.open(encoding="utf-8") as source:
            data = json.load(source)
        if args.pool_id is None:
            result = get_control_options(data, args.user_id)
        else:
            action = ACTION if args.action is None else args.action
            confirmed = args.confirm
            if not args.confirm and not args.cancel:
                options = get_control_options(data, args.user_id)
                confirmed = ask_confirmation(options, args.pool_id, action)
            result = process_request(data, args.user_id, args.pool_id, action, confirmed, args.simulate_error)
    except PermissionError as error:
        if error.errno is not None:
            print(f"Ошибка чтения данных. {error}", file=sys.stderr)
            return 2
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, RecursionError) as error:
        print(f"Ошибка. {error}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
