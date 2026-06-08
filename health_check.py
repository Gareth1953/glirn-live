import os
import json
import importlib.util


BASE_DIR = r"C:\ArbitrageEngineV1"

REQUIRED_PATHS = [
    r"C:\ArbitrageEngineV1\main.py",
    r"C:\ArbitrageEngineV1\dashboard.py",
    r"C:\ArbitrageEngineV1\config\providers.json",
    r"C:\ArbitrageEngineV1\core\providers.py",
    r"C:\ArbitrageEngineV1\core\router.py",
    r"C:\ArbitrageEngineV1\core\verifier.py",
    r"C:\ArbitrageEngineV1\core\logger.py",
    r"C:\ArbitrageEngineV1\logs",
    r"C:\ArbitrageEngineV1\scripts\run_engine.ps1"
]


def check_path(path):
    return os.path.exists(path)


def check_python_package(package_name):
    return importlib.util.find_spec(package_name) is not None


def check_config():
    config_path = r"C:\ArbitrageEngineV1\config\providers.json"

    try:
        with open(config_path, "r", encoding="utf-8") as file:
            config = json.load(file)

        if "providers" not in config:
            return False, "providers key missing"

        if len(config["providers"]) == 0:
            return False, "no providers configured"

        return True, "config valid"

    except Exception as error:
        return False, str(error)


def main():
    print("")
    print("ARBITRAGE ENGINE V1 — HEALTH CHECK")
    print("----------------------------------")

    all_ok = True

    print("")
    print("File and folder checks:")

    for path in REQUIRED_PATHS:
        ok = check_path(path)
        status = "OK" if ok else "MISSING"

        print(f"{status}: {path}")

        if not ok:
            all_ok = False

    print("")
    print("Python package checks:")

    for package in ["requests"]:
        ok = check_python_package(package)
        status = "OK" if ok else "MISSING"

        print(f"{status}: {package}")

        if not ok:
            all_ok = False

    print("")
    print("Config check:")

    config_ok, config_message = check_config()
    print(("OK" if config_ok else "FAILED") + f": {config_message}")

    if not config_ok:
        all_ok = False

    print("")
    if all_ok:
        print("SYSTEM STATUS: HEALTHY")
    else:
        print("SYSTEM STATUS: NEEDS ATTENTION")


if __name__ == "__main__":
    main()