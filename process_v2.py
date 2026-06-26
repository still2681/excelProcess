import os

from rule_selector import select_rules_and_process

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "package-simple.json")


if __name__ == "__main__":
    select_rules_and_process(CONFIG_FILE)
