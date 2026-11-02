#!/usr/bin/env python3
from cpr import CEDARPointerRegistry

CEDAR_COMMANDS = [
    "CREATE FILE path WITH content",
    "UPDATE FILE path ... END UPDATE",
    "INSERT AT BEGINNING OF FILE path CONTENT content",
    "INSERT AT END OF FILE path CONTENT content",
    "INSERT AT LINE line OF FILE path CONTENT content",
    "DELETE FILE path",
    "MOVE FILE source_path TO destination_path",
    "CREATE FUNCTION name ... END FUNCTION",
    "UPDATE FUNCTION name ... END UPDATE",
    "INSERT BEFORE FUNCTION name CONTENT code",
    "INSERT AFTER FUNCTION name CONTENT code",
    "INSERT AT BEGINNING OF FUNCTION name CONTENT code",
    "INSERT AT END OF FUNCTION name CONTENT code",
    "INSERT AT LINE line OF FUNCTION name CONTENT code",
    "DELETE FUNCTION name",
    "MOVE FUNCTION name BEFORE FUNCTION target",
    "MOVE FUNCTION name AFTER FUNCTION target",
    "CREATE CLASS name ... END CLASS",
    "UPDATE CLASS name ... END UPDATE",
    "CREATE METHOD method_name IN CLASS class_name ... END METHOD",
    "UPDATE METHOD method_name IN CLASS class_name ... END UPDATE",
    "INSERT BEFORE METHOD method_name IN CLASS class_name CONTENT code",
    "INSERT AFTER METHOD method_name IN CLASS class_name CONTENT code",
    "DELETE METHOD method_name IN CLASS class_name",
    "MOVE METHOD method_name IN CLASS class_name BEFORE METHOD target",
    "SELECT LOCATION OF FUNCTION name",
    "SELECT LOCATION OF CLASS name",
    "SELECT LOCATION OF METHOD method_name IN CLASS class_name",
    "SELECT LOCATION OF IDENTIFIER name",
    "SELECT CALLS OF FUNCTION name",
    "SELECT REFERENCES OF IDENTIFIER name",
    "SELECT DEFINITION OF IDENTIFIER name",
    "SELECT ALL FUNCTIONS IN FILE file_path",
    "SELECT ALL CLASSES IN FILE file_path",
    "SELECT ALL METHODS IN CLASS class_name",
    "SELECT ALL VARIABLES IN FILE file_path",
    "SELECT ALL IMPORTS IN FILE file_path",
    "RENAME FUNCTION old_name TO new_name",
    "RENAME CLASS old_name TO new_name",
    "RENAME METHOD old_method TO new_method IN CLASS class_name",
    "RENAME VARIABLE old_name TO new_name IN SCOPE file",
    "EXTRACT CODE FROM line_start TO line_end INTO FUNCTION new_function_name",
    "INLINE FUNCTION call_site",
    "ADD PARAMETER param_name TO FUNCTION function_name",
    "REMOVE PARAMETER param_name FROM FUNCTION function_name",
]

if __name__ == "__main__":
    cpr = CEDARPointerRegistry()
    for cmd in CEDAR_COMMANDS:
        ptr = cpr.compress(cmd)
        print(f"{ptr} → {cmd}")
    print(f"\nRegistered {len(CEDAR_COMMANDS)} commands.")
    print(f"Registry file: {cpr.registry_file}")