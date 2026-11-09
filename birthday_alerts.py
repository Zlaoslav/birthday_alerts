"""
Birthday Alerts
Эта программа позволяет отслеживать дни рождения и получать уведомления о них.
Использование:
    python3 birthday_alerts.py [all|add|edit|next|check|remove|add_to_autorun|remove_from_autorun]
Команды:
    all: Показать все дни рождения (с сортировкой от ближайщего).
    add: Добавить новый день рождения.
    edit: Редактировать существующий день рождения.
    next: Показать следующий день рождения.
    check: Проверить дни рождения и отправить уведомления (используется в autorun для фоновой проверки при входе в систему).
    remove: Удалить день рождения.
    add_to_autorun: Добавить программу в автозапуск.
    remove_from_autorun: Удалить программу из автозапуска.
"""
# source: https://github.com/Zlaoslav/birthday_alerts
from pathlib import Path
import json
import datetime
import sys
import subprocess
import base64
import textwrap
import xml.etree.ElementTree as ET

root_dir = Path(__file__).parent
data_file = root_dir / "birthdays.json"

if sys.platform == "win32":
    REG_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
    REG_NAME = "BirthdayAlerts"

else:
    SERVICE_NAME = "birthday-alerts.service"
    SERVICE_DIR = Path.home() / ".config/systemd/user"
    SERVICE_FILE = SERVICE_DIR / SERVICE_NAME

    LINUX_SERVICE = textwrap.dedent(f"""\
        [Unit]
        Description=Birthday Alerts Service

        [Service]
        Type=oneshot
        ExecStart={Path("/usr/bin/python3").resolve()} {Path(__file__).resolve()} check

        [Install]
        WantedBy=default.target
    """)


def add_to_autorun():
    if sys.platform == "win32":

        startup_command = subprocess.list2cmdline([
            sys.executable,
            str(Path(__file__).resolve()),
            "check"
        ])

        subprocess.run([
            "reg", "add", REG_KEY,
            "/v", REG_NAME,
            "/t", "REG_SZ",
            "/d", startup_command,
            "/f"
        ], check=True)

        print("Программа добавлена в автозапуск Windows.")

    else:
        SERVICE_DIR.mkdir(parents=True, exist_ok=True)

        SERVICE_FILE.write_text(
            LINUX_SERVICE,
            encoding="utf-8"
        )

        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=True
        )

        subprocess.run([
            "systemctl", "--user",
            "enable", "--now", SERVICE_NAME
        ], check=True)

        print("Программа добавлена в автозапуск systemd.")


def remove_from_autorun():
    if sys.platform == "win32":

        subprocess.run([
            "reg", "delete", REG_KEY,
            "/v", REG_NAME,
            "/f"
        ], stdout=subprocess.DEVNULL,
           stderr=subprocess.DEVNULL)

        print("Программа удалена из автозапуска Windows.")

    else:
        subprocess.run([
            "systemctl", "--user",
            "disable", "--now", SERVICE_NAME
        ], stdout=subprocess.DEVNULL,
           stderr=subprocess.DEVNULL)

        if SERVICE_FILE.exists():
            SERVICE_FILE.unlink()

        subprocess.run([
            "systemctl", "--user", "daemon-reload"
        ], check=True)

        print("Программа удалена из автозапуска systemd.")

if not data_file.exists():
    # first run
    data_file.write_text("[]")
    print(f"birthdays.json не найден, создан файл {data_file}.")
    confirm = input("Хотите установить программу в автозапуск, это необходимо для ежедневной автоматической проверки дней рожденья? (y/n): ")
    if confirm.lower() == "y":
        add_to_autorun()


def send_windows_notification(title, message):
    if sys.platform != "win32":
        raise RuntimeError("send_windows_notification can only be used on Windows.")
    # Формируем XML и корректно экранируем текст уведомления
    toast = ET.Element("toast", duration="long")
    visual = ET.SubElement(toast, "visual")
    binding = ET.SubElement(visual, "binding", template="ToastGeneric")
    ET.SubElement(binding, "text").text = title
    ET.SubElement(binding, "text").text = message

    xml = ET.tostring(toast, encoding="unicode")
    xml_b64 = base64.b64encode(xml.encode("utf-8")).decode("ascii")

    ps_script = f"""
    $null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
    $null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]

    $xml = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{xml_b64}'))
    $doc = [Windows.Data.Xml.Dom.XmlDocument]::new()
    $doc.LoadXml($xml)

    $appId = '{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\WindowsPowerShell\\v1.0\\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($doc)
    """

    encoded_command = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")

    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_command],
        check=True,
    )

def load_birthdays():
    with data_file.open("r") as f:
        return json.load(f)

def add_birthday(name, date_str):
    birthdays = load_birthdays()
    birthdays.append({"name": name, "date_str": date_str})
    with data_file.open("w") as f:
        json.dump(birthdays, f)

def edit_birthday(name, new_date_str):
    birthdays = load_birthdays()
    for birthday in birthdays:
        if birthday["name"] == name:
            birthday["date_str"] = new_date_str
            with data_file.open("w") as f:
                json.dump(birthdays, f)
            return
    else:
        print(f"День рождения для {name} не найден.")

def get_next_birthdays():
    upcoming = load_birthdays()

    if not upcoming:
        raise ValueError("Нет предстоящих дней рождения.")

    today = datetime.date.today()

    def sort_key(item):
        birthday = datetime.datetime.strptime(
            item["date_str"], "%Y-%m-%d"
        ).date()

        # Сначала будущие даты, затем прошедшие
        is_past = (birthday.month, birthday.day) < (today.month, today.day)

        return (is_past, birthday.month, birthday.day)

    upcoming.sort(key=sort_key)
    return upcoming

def show_all_birthdays():
    birthdays = get_next_birthdays()
    if birthdays:
        print("Все дни рождения:")
        for birthday in birthdays:
            print(f"{birthday['name']}: {birthday['date_str']}")
    else:
        print("Нет сохраненных дней рождения.")

def input_birthday():
    name = input("Введите имя: ")
    date_str = input("Введите день рождения (ГГГГ-ММ-ДД или ДД.ММ.ГГГГ или ДД ММ ГГГГ): ")
    date_formats = ["%Y-%m-%d", "%d.%m.%Y", "%d %m %Y"]
    date = None
    for fmt in date_formats:
        try:
            date = datetime.datetime.strptime(date_str, fmt).date()
            break
        except ValueError:
            continue
    if not date:
        print("Неверный формат даты.")
        return
    normalized_date_str = date.strftime("%Y-%m-%d")
    add_birthday(name, normalized_date_str)
    print(f"День рождения для {name} успешно добавлен. ({normalized_date_str})")

def background_check():
    try:
        upcoming = get_next_birthdays()
    except ValueError:
        return

    today = datetime.date.today()

    today_birthdays = []
    soon_birthdays = []

    for birthday in upcoming:
        birth_date = datetime.datetime.strptime(
            birthday["date_str"], "%Y-%m-%d"
        ).date()

        # Переносим дату рождения на текущий год
        next_birthday_date = birth_date.replace(year=today.year)

        # Если день рождения уже прошёл: берём следующий год
        if next_birthday_date < today:
            next_birthday_date = birth_date.replace(year=today.year + 1)

        days_until = (next_birthday_date - today).days

        if days_until == 0:
            today_birthdays.append(birthday)

        elif 1 <= days_until <= 7:
            soon_birthdays.append(birthday)

    # Дни рождения сегодня
    if today_birthdays:
        message = "Сегодня день рождения:\n" + "\n".join(
            f"{b['name']}: {b['date_str']}"
            for b in today_birthdays[:3]
        )
        if sys.platform == "win32":
            send_windows_notification("Напоминание о днях рождения", message)
        else:    
            subprocess.run([
                "notify-send",
                "--urgency=critical",
                "Напоминание о днях рождения",
                message
            ])

    # Дни рождения в ближайшие 7 дней
    if soon_birthdays:
        message = "Скоро дни рождения:\n" + "\n".join(
            f"{b['name']}: {b['date_str']}"
            for b in soon_birthdays[:3]
        )
        if sys.platform == "win32":
            send_windows_notification("Напоминание о днях рождения", message)
        else:
            subprocess.run([
                "notify-send",
                "--urgency=normal",
                "--expire-time=15000",
                "Напоминание о днях рождения",
                message
            ])

def remove_birthday(name):
    birthdays = load_birthdays()
    
    for birthday in birthdays:
        if birthday["name"] == name:
            birthdays.remove(birthday)
            with data_file.open("w") as f:
                json.dump(birthdays, f)
            print(f"День рождения для {name} удален.")
            return
    else:
        print(f"День рождения для {name} не найден.")

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if not arg:
        arg = input("Введите команду (all, add, edit, next, check, remove, add_to_autorun, remove_from_autorun): ").strip().lower()
    if arg not in ["all", "list", "add", "edit", "next", "check", "remove", "add_to_autorun", "remove_from_autorun"]:
        raise ValueError("Использование: python birthday_alerts.py [all|add|edit|next|check|remove|add_to_autorun|remove_from_autorun]")
    if not data_file.exists():
        raise FileNotFoundError(f"Файл {data_file} не найден. Создайте его и добавьте дни рождения в формате JSON.")
    match arg:
        case "all":
            show_all_birthdays()
        case "list":
            show_all_birthdays()
        case "add":
            input_birthday()
        case "edit":
            name = input("Введите имя для редактирования: ")
            new_date_str = input("Введите новую дату рождения (YYYY-MM-DD): ")
            edit_birthday(name, new_date_str)
        case "next":
            upcoming = get_next_birthdays()
            if upcoming:
                next_birthday = upcoming[0]
                print(f"Следующий день рождения: {next_birthday['name']} - {next_birthday['date_str']}")
            else:
                raise ValueError("Нет предстоящих дней рождения.")
        case "check":
            background_check()
        case "remove":
            name = input("Введите имя для удаления: ")
            remove_birthday(name)
        case "add_to_autorun":
            confirm = input("Вы уверены, что хотите добавить программу в автозапуск? (y/n): ")
            if confirm.lower() == "y":
                add_to_autorun()
            else:
                print("Добавление в автозапуск отменено.")
        case "remove_from_autorun":
            confirm = input("Вы уверены, что хотите удалить программу из автозапуска? (y/n): ")
            if confirm.lower() == "y":
                remove_from_autorun()
            else:
                print("Удаление из автозапуска отменено.")
