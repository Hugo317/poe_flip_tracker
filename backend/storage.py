import copy
import json
import os
import shutil
from datetime import datetime
from pathlib import Path


class Storage:
    def __init__(self, data_file, backup_file, default_data):
        self.data_file = Path(data_file)
        self.backup_file = Path(backup_file)
        self.default_data = default_data

    @staticmethod
    def now():
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    def load(self):
        if (
            not self.data_file.exists()
            or self.data_file.stat().st_size == 0
        ):
            return self._create_default_data()

        try:
            with self.data_file.open(
                "r",
                encoding="utf-8"
            ) as file:
                return json.load(file)

        except (json.JSONDecodeError, OSError) as error:
            print(f"Could not load data.json: {error}")

            if (
                self.backup_file.exists()
                and self.backup_file.stat().st_size > 0
            ):
                print("Trying backup...")

                with self.backup_file.open(
                    "r",
                    encoding="utf-8"
                ) as file:
                    data = json.load(file)

                print("Backup loaded successfully.")
                return data

            raise RuntimeError(
                "data.json is corrupted and "
                "no usable backup exists."
            )

    def _create_default_data(self):
        data = copy.deepcopy(self.default_data)

        now = self.now()

        data["settings"]["gold_rate"]["history"].append({
            "timestamp": now,
            "gold_amount": 1_000_000,
            "chaos_value": 200
        })

        data["settings"]["divine_rate"]["history"].append({
            "timestamp": now,
            "divine_amount": 1,
            "chaos_value": 180
        })

        self.save(data)

        return data

    def save(self, data):
        if self.data_file.exists():
            shutil.copy2(
                self.data_file,
                self.backup_file
            )

        temporary_file = self.data_file.with_suffix(".tmp")

        with temporary_file.open(
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                data,
                file,
                indent=2,
                ensure_ascii=False
            )
            file.write("\n")

        os.replace(
            temporary_file,
            self.data_file
        )

    def export_backup(self, data):
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        backup_file = self.data_file.with_name(
            f"poe_flip_tracker_backup_{timestamp}.json"
        )

        with backup_file.open(
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                data,
                file,
                indent=2,
                ensure_ascii=False
            )
            file.write("\n")

        return backup_file