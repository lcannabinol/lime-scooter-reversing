# -*- coding: utf-8 -*-
# LimeRE_Helper.py
# Interactive Ghidra helper for Lime Gen3 Motor Controller reverse engineering.
#
# @author  lcannabinol + Grok
# @category Lime.RE
# @keybinding
# @menupath Tools.Lime RE Helper
# @toolbar

"""
Lime Gen3 Motor Controller — Interactive RE Helper

Main menu-driven script that:
  • Applies all known function + RAM names from the analysis
  • Traces callers / callees
  • Shows XREFs to any address / range
  • Renames functions / data
  • Adds plate / EOL comments
  • Finds references to constants (0x258, 0x3C, IoT flag, etc.)
  • Dumps function call graph snippet

All dialogs use the built-in Ghidra ask* API (works in both GUI and headless with .properties).
"""

from ghidra.program.model.symbol import SourceType, RefType
from ghidra.program.model.listing import CodeUnit, Function
from ghidra.program.model.address import AddressSet
from ghidra.util.exception import CancelledException
from ghidra.app.decompiler import DecompInterface
from java.util import ArrayList
import re

# ==============================================================================
#  KNOWN SYMBOLS  (from address book + README + Ghidra dump)
# ==============================================================================

# Flash functions  (entry point -> nice name)
KNOWN_FUNCTIONS = {
    0x08001688: "early_init_clear_flag_46E",
    0x08002024: "process_params_and_state",          # contains thresholds 0x15,0x3C,0x3D,0xC9...
    0x08002cd6: "lowlevel_peripheral_write_A",
    0x08002cda: "lowlevel_peripheral_write_B",      # candidate physical traction off
    0x08003706: "timer_struct_init",                # args 0x10/0x200/0x400/0x800
    0x08003b32: "timer_handler_CMP_0x3C",           # critical 60-sec compare
    0x08003EF0: "buffer_table_ops_A",
    0x08003f88: "reset_state_caller",
    0x08004064: "buffer_table_ops_B",
    0x0800407E: "reset_state_clear_buffer",
    0x08005ed0: "motor_control_main",               # REAL traction gate lives here
    0x08006bc4: "lock_flag_chain_B",
    0x08006f72: "apply_saved_target_speed",
    0x08006faa: "lock_flag_chain_A",
    0x080073fc: "main_state_machine",               # state 7 + traction disable calls
    0x08008040: "ptr_target_old",
    0x08008096: "ptr_target_new",                   # after the 0x080010A0 patch
}

# Important absolute RAM addresses
KNOWN_RAM = {
    0x20000035: "sec_counter_or_lock_timer",        # increases 0→0x1E→0x3E in dumps
    0x20000091: "motor_internal_counter",           # corrected from README
    0x20000158: "traction_lock_flag",               # 1 = locked
    0x20000164: "cyclic_buffer_ptr",
    0x200003A0: "timer_struct_base",
    0x200003BC: "timer_bitmask_src",
    0x200003C8: "unlock_elapsed_counter",           # ~10 ms ticks
    0x20000426: "state_counter_or_flag",            # often holds 0x258
    0x20000444: "iot_timeout_multiplier",           # 0x3C / 0x960
    0x2000046E: "global_state_flag",
    0x20000472: "aux_flag_or_counter",
    0x20000477: "iot_active_flag",                  # THE IoT flag (0/1)
    0x20000489: "cyclic_buf_index",
}

# Important constants that appear in code
IMPORTANT_CONSTANTS = {
    0x258:  "TIMER_600_TICKS_60SEC",
    0x3C:   "SECONDS_60_OR_THRESHOLD",
    0x15:   "THRESH_0x15",
    0x3D:   "THRESH_0x3D",
    0xC9:   "THRESH_0xC9",
    0x12C:  "THRESH_0x12C",
    0x3E9:  "THRESH_0x3E9",
    0x7D0:  "THRESH_0x7D0",
}

# Key code locations (for comments / bookmarks)
KEY_LOCATIONS = {
    0x080010A0: "PATCH_SITE_pointer_swap",
    0x08006098: "IOT_FLAG_LOAD_0x20000477",
    0x0800609a: "IOT_FLAG_ldrb",
    0x0800609c: "IOT_FLAG_cmp_#1",
    0x0800609e: "IOT_FLAG_bne_GATE",               # radical patch candidate
    0x08007922: "TIMER_cmp_#0x258",                 # safe patch candidate
    0x08007fb4: "old_suspected_lock_flag_ptr",
}

# ==============================================================================
#  HELPERS
# ==============================================================================

def to_addr(x):
    """Accept int, long, string or Address."""
    if hasattr(x, "getOffset"):
        return x
    if isinstance(x, (str, unicode)):
        x = x.strip().lower().replace("0x", "")
        return currentProgram.getAddressFactory().getAddress("0x" + x)
    return currentProgram.getAddressFactory().getAddress(hex(int(x)))


def get_function_at_or_containing(addr):
    fm = currentProgram.getFunctionManager()
    f = fm.getFunctionAt(addr)
    if f is None:
        f = fm.getFunctionContaining(addr)
    return f


def safe_rename_function(addr, new_name):
    addr = to_addr(addr)
    f = get_function_at_or_containing(addr)
    if f is None:
        # try to create
        f = createFunction(addr, new_name)
        if f:
            println("[+] Created function {} @ {}".format(new_name, addr))
            return True
        println("[-] No function at {}".format(addr))
        return False
    old = f.getName()
    if old == new_name:
        return True
    try:
        f.setName(new_name, SourceType.USER_DEFINED)
        println("[+] {}  →  {}   ({})".format(old, new_name, addr))
        return True
    except Exception as e:
        println("[!] Rename failed {} → {}: {}".format(old, new_name, e))
        return False


def safe_create_label(addr, name, primary=True):
    addr = to_addr(addr)
    try:
        createLabel(addr, name, primary)
        println("[+] Label {} @ {}".format(name, addr))
        return True
    except Exception as e:
        # already exists or conflict
        sym = getSymbolAt(addr)
        if sym and sym.getName() == name:
            return True
        println("[!] Label {} @ {} : {}".format(name, addr, e))
        return False


def add_plate_comment(addr, text):
    addr = to_addr(addr)
    listing = currentProgram.getListing()
    cu = listing.getCodeUnitAt(addr)
    if cu is None:
        # try instruction
        cu = listing.getInstructionAt(addr)
    if cu:
        existing = cu.getComment(CodeUnit.PLATE_COMMENT) or ""
        if text not in existing:
            new = (existing + "\n" + text).strip() if existing else text
            cu.setComment(CodeUnit.PLATE_COMMENT, new)
            println("[+] Plate comment @ {}".format(addr))
    else:
        println("[-] No code unit @ {}".format(addr))


def add_eol_comment(addr, text):
    addr = to_addr(addr)
    listing = currentProgram.getListing()
    cu = listing.getCodeUnitAt(addr)
    if cu is None:
        cu = listing.getInstructionAt(addr)
    if cu:
        cu.setComment(CodeUnit.EOL_COMMENT, text)
        println("[+] EOL comment @ {}".format(addr))


# ==============================================================================
#  ACTIONS
# ==============================================================================

def action_apply_all_known_names():
    """Apply every known function + RAM + key location name."""
    println("=" * 60)
    println("Applying known function names...")
    cnt = 0
    for addr, name in sorted(KNOWN_FUNCTIONS.items()):
        if safe_rename_function(addr, name):
            cnt += 1
    println("Functions processed: {}".format(cnt))

    println("\nApplying RAM labels...")
    cnt = 0
    for addr, name in sorted(KNOWN_RAM.items()):
        if safe_create_label(addr, name):
            cnt += 1
    println("RAM labels: {}".format(cnt))

    println("\nAdding key location comments / labels...")
    for addr, desc in sorted(KEY_LOCATIONS.items()):
        safe_create_label(addr, desc)
        add_plate_comment(addr, "KEY: " + desc)

    println("\nDone. Reload or refresh Listing to see changes.")
    println("=" * 60)


def action_trace_callers(addr=None):
    """Show all callers of the function that contains the given address."""
    if addr is None:
        addr = askAddress("Trace Callers", "Enter address inside the target function:")
    addr = to_addr(addr)
    f = get_function_at_or_containing(addr)
    if f is None:
        println("[-] No function containing {}".format(addr))
        return

    println("\n=== Callers of {} @ {} ===".format(f.getName(), f.getEntryPoint()))
    refs = getReferencesTo(f.getEntryPoint())
    callers = set()
    for r in refs:
        if r.getReferenceType().isCall() or r.getReferenceType().isJump():
            from_addr = r.getFromAddress()
            caller_f = get_function_at_or_containing(from_addr)
            name = caller_f.getName() if caller_f else "<no func>"
            callers.add((from_addr, name))
            println("  {}  →  {}   (from {})".format(from_addr, name, r.getReferenceType()))

    if not callers:
        println("  (no call/jump references found)")
    else:
        println("Total unique callers: {}".format(len(callers)))


def action_trace_callees(addr=None):
    """List all functions called from the given function."""
    if addr is None:
        addr = askAddress("Trace Callees", "Enter address inside the target function:")
    addr = to_addr(addr)
    f = get_function_at_or_containing(addr)
    if f is None:
        println("[-] No function containing {}".format(addr))
        return

    println("\n=== Callees of {} @ {} ===".format(f.getName(), f.getEntryPoint()))
    body = f.getBody()
    insns = currentProgram.getListing().getInstructions(body, True)
    callees = set()
    while insns.hasNext():
        insn = insns.next()
        for r in insn.getReferencesFrom():
            if r.getReferenceType().isCall():
                to_addr = r.getToAddress()
                target_f = getFunctionAt(to_addr)
                name = target_f.getName() if target_f else str(to_addr)
                callees.add((to_addr, name))
                println("  {}  calls  {}  ({})".format(insn.getAddress(), name, to_addr))

    if not callees:
        println("  (no call references found)")
    else:
        println("Total unique callees: {}".format(len(callees)))


def action_xrefs_to_address(addr=None):
    """Show all references to an address (or current location)."""
    if addr is None:
        addr = askAddress("XREFs to", "Enter target address:")
    addr = to_addr(addr)
    refs = getReferencesTo(addr)
    println("\n=== References TO {} ===".format(addr))
    count = 0
    for r in refs:
        from_a = r.getFromAddress()
        f = get_function_at_or_containing(from_a)
        fname = f.getName() if f else "-"
        println("  {}  ({})  ←  {}   [{}]".format(
            from_a, fname, r.getReferenceType(), r.getSource()))
        count += 1
    println("Total: {}".format(count))


def action_xrefs_in_range():
    """Find all references that land inside a given address range."""
    start = askAddress("Range start", "Start address:")
    end   = askAddress("Range end",   "End address (inclusive):")
    start = to_addr(start)
    end   = to_addr(end)

    println("\n=== References into range {} – {} ===".format(start, end))
    count = 0
    addr = start
    while addr.compareTo(end) <= 0:
        refs = getReferencesTo(addr)
        for r in refs:
            from_a = r.getFromAddress()
            f = get_function_at_or_containing(from_a)
            fname = f.getName() if f else "-"
            println("  {}  →  {}   (from {} / {})".format(
                from_a, addr, fname, r.getReferenceType()))
            count += 1
        addr = addr.add(1)
        if count > 500:
            println("... truncated at 500 hits")
            break
    println("Total hits: {}".format(count))


def action_find_constant_xrefs():
    """Search for references to important constants (0x258, 0x3C …)."""
    choices = ["0x258 (60-sec timer)", "0x3C (60 / threshold)",
               "0x15", "0x3D", "0xC9", "0x12C", "0x3E9", "0x7D0",
               "Custom value..."]
    choice = askChoice("Constant", "Which constant to search for?", choices, choices[0])

    if choice.startswith("Custom"):
        val_str = askString("Value", "Enter constant (hex or decimal):", "0x258")
        if val_str.lower().startswith("0x"):
            val = int(val_str, 16)
        else:
            val = int(val_str)
    else:
        val = int(choice.split()[0], 16)

    println("\n=== Searching for constant {} (0x{:X}) ===".format(val, val))
    # Simple scalar search via memory + instruction operands is heavy;
    # we use the ReferenceManager for existing value references first,
    # then fall back to a linear scan of instructions.
    listing = currentProgram.getListing()
    mem = currentProgram.getMemory()
    count = 0

    # 1. Existing data references that point to a location containing the value
    # 2. Linear scan of all instructions looking for the immediate
    insns = listing.getInstructions(True)
    while insns.hasNext() and count < 300:
        insn = insns.next()
        for i in range(insn.getNumOperands()):
            objs = insn.getOpObjects(i)
            for o in objs:
                try:
                    if hasattr(o, "getValue") and o.getValue() == val:
                        f = get_function_at_or_containing(insn.getAddress())
                        fname = f.getName() if f else "-"
                        println("  {}  [{}]  {}".format(insn.getAddress(), fname, insn))
                        count += 1
                        break
                except:
                    pass
    println("Found {} instruction(s) using immediate 0x{:X}".format(count, val))


def action_rename_at_address():
    """Rename function or create label at arbitrary address."""
    addr = askAddress("Rename", "Address to rename:")
    name = askString("New name", "Enter new name:", "new_name")
    if not name:
        return

    f = get_function_at_or_containing(to_addr(addr))
    if f and f.getEntryPoint().equals(to_addr(addr)):
        safe_rename_function(addr, name)
    else:
        safe_create_label(addr, name)
        # also try to rename containing function if user wants
        if f and askYesNo("Also rename function?", "Rename the containing function {} as well?".format(f.getName())):
            safe_rename_function(f.getEntryPoint(), name)


def action_add_comment():
    """Add plate or EOL comment at address."""
    addr = askAddress("Comment", "Address for comment:")
    kind = askChoice("Type", "Comment type:", ["Plate (above)", "EOL (end-of-line)"], "Plate (above)")
    text = askString("Text", "Comment text:")
    if not text:
        return
    if kind.startswith("Plate"):
        add_plate_comment(addr, text)
    else:
        add_eol_comment(addr, text)


def action_dump_function_info(addr=None):
    """Print detailed info about a function (size, params, callees, callers)."""
    if addr is None:
        addr = askAddress("Function info", "Address inside function:")
    addr = to_addr(addr)
    f = get_function_at_or_containing(addr)
    if f is None:
        println("[-] No function at {}".format(addr))
        return

    println("\n" + "=" * 60)
    println("Function: {}".format(f.getName()))
    println("Entry   : {}".format(f.getEntryPoint()))
    println("Body    : {}  ({} bytes)".format(f.getBody(), f.getBody().getNumAddresses()))
    println("Calling : {}".format(f.getCallingConventionName()))
    println("Signature: {}".format(f.getSignature()))

    println("\n--- Callers ---")
    action_trace_callers(f.getEntryPoint())
    println("\n--- Callees ---")
    action_trace_callees(f.getEntryPoint())
    println("=" * 60)


def action_bookmark_key_sites():
    """Create bookmarks for all KEY_LOCATIONS."""
    for addr, desc in KEY_LOCATIONS.items():
        a = to_addr(addr)
        createBookmark(a, "LimeRE", desc)
        println("[+] Bookmark @ {}  {}".format(a, desc))
    println("Bookmarks created. View → Bookmarks")


def action_goto_known():
    """Quick navigation menu to any known function / RAM / key site."""
    items = []
    for a, n in sorted(KNOWN_FUNCTIONS.items()):
        items.append("F  0x{:08X}  {}".format(a, n))
    for a, n in sorted(KNOWN_RAM.items()):
        items.append("R  0x{:08X}  {}".format(a, n))
    for a, n in sorted(KEY_LOCATIONS.items()):
        items.append("K  0x{:08X}  {}".format(a, n))

    choice = askChoice("Go to", "Select symbol:", items, items[0])
    addr_str = choice.split()[1]
    addr = to_addr(addr_str)
    goTo(addr)
    println("Navigated to {}".format(addr))


# ==============================================================================
#  MAIN MENU
# ==============================================================================

def run():
    menu = [
        "1. Apply ALL known names (functions + RAM + key sites)",
        "2. Trace CALLERS of a function",
        "3. Trace CALLEES of a function",
        "4. Show XREFs to an address",
        "5. Find XREFs into an address RANGE",
        "6. Find instructions using an important constant",
        "7. Rename function / label at address",
        "8. Add plate / EOL comment",
        "9. Dump detailed function info",
        "10. Bookmark all key sites",
        "11. Go to known symbol (navigation)",
        "0. Exit",
    ]

    while True:
        try:
            choice = askChoice("Lime RE Helper",
                               "Choose action:",
                               menu,
                               menu[0])
        except CancelledException:
            println("Cancelled.")
            return

        if choice.startswith("0.") or choice is None:
            println("Bye.")
            return
        elif choice.startswith("1."):
            action_apply_all_known_names()
        elif choice.startswith("2."):
            action_trace_callers()
        elif choice.startswith("3."):
            action_trace_callees()
        elif choice.startswith("4."):
            action_xrefs_to_address()
        elif choice.startswith("5."):
            action_xrefs_in_range()
        elif choice.startswith("6."):
            action_find_constant_xrefs()
        elif choice.startswith("7."):
            action_rename_at_address()
        elif choice.startswith("8."):
            action_add_comment()
        elif choice.startswith("9."):
            action_dump_function_info()
        elif choice.startswith("10."):
            action_bookmark_key_sites()
        elif choice.startswith("11."):
            action_goto_known()
        else:
            println("Unknown choice")

        # ask whether to continue
        try:
            if not askYesNo("Continue?", "Run another action?"):
                break
        except CancelledException:
            break

    println("Lime RE Helper finished.")


# Entry point for Ghidra
if __name__ == "__main__":
    run()
