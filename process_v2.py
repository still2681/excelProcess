import os

from rule_selector import select_rules_and_process

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "package.json")


if __name__ == "__main__":
    select_rules_and_process(CONFIG_FILE)
