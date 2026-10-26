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

Menu-driven script:
  - Apply known function + RAM names
  - Trace callers / callees
  - XREFs to address / range
  - Rename, comments, bookmarks
  - Find important constants (0x258, 0x3C, ...)
"""

from ghidra.program.model.symbol import SourceType
from ghidra.program.model.listing import CodeUnit
from ghidra.util.exception import CancelledException
from java.util import ArrayList

# ---------------------------------------------------------------------------
# Py2 / Py3 compatibility (Jython 2.7 vs PyGhidra)
# ---------------------------------------------------------------------------
try:
    _string_types = (str, unicode)  # Jython / Py2
except NameError:
    _string_types = (str,)          # PyGhidra / Py3

def _fmt(s, *args):
    """Safe format that stringifies Address objects etc."""
    return s.format(*[str(a) for a in args])


# ==============================================================================
#  KNOWN SYMBOLS
# ==============================================================================

KNOWN_FUNCTIONS = {
    0x08001688: "early_init_clear_flag_46E",
    0x08002024: "process_params_and_state",
    0x08002cd6: "lowlevel_peripheral_write_A",
    0x08002cda: "lowlevel_peripheral_write_B",
    0x08003706: "timer_struct_init",
    0x08003b32: "timer_handler_CMP_0x3C",
    0x08003EF0: "buffer_table_ops_A",
    0x08003f88: "reset_state_caller",
    0x08004064: "buffer_table_ops_B",
    0x0800407E: "reset_state_clear_buffer",
    0x08005ed0: "motor_control_main",
    0x08006bc4: "lock_flag_chain_B",
    0x08006f72: "apply_saved_target_speed",
    0x08006faa: "lock_flag_chain_A",
    0x080073fc: "main_state_machine",
    0x08008040: "ptr_target_old",
    0x08008096: "ptr_target_new",
}

KNOWN_RAM = {
    0x20000035: "sec_counter_or_lock_timer",
    0x20000091: "motor_internal_counter",
    0x20000158: "traction_lock_flag",
    0x20000164: "cyclic_buffer_ptr",
    0x200003A0: "timer_struct_base",
    0x200003BC: "timer_bitmask_src",
    0x200003C8: "unlock_elapsed_counter",
    0x20000426: "state_counter_or_flag",
    0x20000444: "iot_timeout_multiplier",
    0x2000046E: "global_state_flag",
    0x20000472: "aux_flag_or_counter",
    0x20000477: "iot_active_flag",
    0x20000489: "cyclic_buf_index",
}

KEY_LOCATIONS = {
    0x080010A0: "PATCH_SITE_pointer_swap",
    0x08006098: "IOT_FLAG_LOAD_0x20000477",
    0x0800609a: "IOT_FLAG_ldrb",
    0x0800609c: "IOT_FLAG_cmp_1",
    0x0800609e: "IOT_FLAG_bne_GATE",
    0x08007922: "TIMER_cmp_0x258",
    0x08007fb4: "old_suspected_lock_flag_ptr",
}


# ==============================================================================
#  HELPERS
# ==============================================================================

def to_addr(x):
    """Accept int, string or Address → Address."""
    if x is None:
        return None
    if hasattr(x, "getOffset"):
        return x
    if isinstance(x, _string_types):
        s = x.strip().lower()
        if s.startswith("0x"):
            s = s[2:]
        return currentProgram.getAddressFactory().getAddress("0x" + s)
    # int / long
    return currentProgram.getAddressFactory().getAddress("0x%x" % int(x))


def jlist(py_list):
    """Python list → java.util.ArrayList (safer for askChoice on some builds)."""
    al = ArrayList()
    for item in py_list:
        al.add(item)
    return al


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
        f = createFunction(addr, new_name)
        if f is not None:
            println(_fmt("[+] Created function {} @ {}", new_name, addr))
            return True
        println(_fmt("[-] No function at {}", addr))
        return False
    old = f.getName()
    if old == new_name:
        return True
    try:
        f.setName(new_name, SourceType.USER_DEFINED)
        println(_fmt("[+] {}  →  {}   ({})", old, new_name, addr))
        return True
    except Exception as e:
        println(_fmt("[!] Rename failed {} → {}: {}", old, new_name, e))
        return False


def safe_create_label(addr, name, primary=True):
    addr = to_addr(addr)
    try:
        # FlatAPI: createLabel(Address, String, boolean)
        createLabel(addr, name, primary)
        println(_fmt("[+] Label {} @ {}", name, addr))
        return True
    except Exception as e:
        sym = getSymbolAt(addr)
        if sym is not None and sym.getName() == name:
            return True
        # try non-primary
        try:
            createLabel(addr, name, False)
            println(_fmt("[+] Label (non-primary) {} @ {}", name, addr))
            return True
        except Exception as e2:
            println(_fmt("[!] Label {} @ {} : {}", name, addr, e2))
            return False


def add_plate_comment(addr, text):
    addr = to_addr(addr)
    listing = currentProgram.getListing()
    cu = listing.getCodeUnitAt(addr)
    if cu is None:
        cu = listing.getInstructionAt(addr)
    if cu is not None:
        existing = cu.getComment(CodeUnit.PLATE_COMMENT)
        if existing is None:
            existing = ""
        if text not in existing:
            new = (existing + "\n" + text).strip() if existing else text
            cu.setComment(CodeUnit.PLATE_COMMENT, new)
            println(_fmt("[+] Plate comment @ {}", addr))
    else:
        println(_fmt("[-] No code unit @ {}", addr))


def add_eol_comment(addr, text):
    addr = to_addr(addr)
    listing = currentProgram.getListing()
    cu = listing.getCodeUnitAt(addr)
    if cu is None:
        cu = listing.getInstructionAt(addr)
    if cu is not None:
        cu.setComment(CodeUnit.EOL_COMMENT, text)
        println(_fmt("[+] EOL comment @ {}", addr))


# ==============================================================================
#  ACTIONS
# ==============================================================================

def action_apply_all_known_names():
    println("=" * 60)
    println("Applying known function names...")
    cnt = 0
    for addr, name in sorted(KNOWN_FUNCTIONS.items()):
        if safe_rename_function(addr, name):
            cnt += 1
    println(_fmt("Functions processed: {}", cnt))

    println("")
    println("Applying RAM labels...")
    cnt = 0
    for addr, name in sorted(KNOWN_RAM.items()):
        if safe_create_label(addr, name):
            cnt += 1
    println(_fmt("RAM labels: {}", cnt))

    println("")
    println("Adding key location labels + comments...")
    for addr, desc in sorted(KEY_LOCATIONS.items()):
        safe_create_label(addr, desc)
        add_plate_comment(addr, "KEY: " + desc)

    println("")
    println("Done.")
    println("=" * 60)


def action_trace_callers(addr=None):
    if addr is None:
        addr = askAddress("Trace Callers", "Enter address inside the target function:")
    addr = to_addr(addr)
    f = get_function_at_or_containing(addr)
    if f is None:
        println(_fmt("[-] No function containing {}", addr))
        return

    println(_fmt("=== Callers of {} @ {} ===", f.getName(), f.getEntryPoint()))
    refs = getReferencesTo(f.getEntryPoint())
    n = 0
    seen = {}
    for r in refs:
        rt = r.getReferenceType()
        if rt.isCall() or rt.isJump():
            from_addr = r.getFromAddress()
            caller_f = get_function_at_or_containing(from_addr)
            name = caller_f.getName() if caller_f is not None else "<no func>"
            key = str(from_addr)
            if key not in seen:
                seen[key] = True
                println(_fmt("  {}  →  {}   ({})", from_addr, name, rt))
                n += 1
    if n == 0:
        println("  (no call/jump references found)")
    else:
        println(_fmt("Total unique callers: {}", n))


def action_trace_callees(addr=None):
    if addr is None:
        addr = askAddress("Trace Callees", "Enter address inside the target function:")
    addr = to_addr(addr)
    f = get_function_at_or_containing(addr)
    if f is None:
        println(_fmt("[-] No function containing {}", addr))
        return

    println(_fmt("=== Callees of {} @ {} ===", f.getName(), f.getEntryPoint()))
    body = f.getBody()
    insns = currentProgram.getListing().getInstructions(body, True)
    n = 0
    seen = {}
    while insns.hasNext():
        insn = insns.next()
        refs = insn.getReferencesFrom()
        for r in refs:
            if r.getReferenceType().isCall():
                to_a = r.getToAddress()
                target_f = getFunctionAt(to_a)
                name = target_f.getName() if target_f is not None else str(to_a)
                key = str(to_a)
                if key not in seen:
                    seen[key] = True
                    println(_fmt("  {}  calls  {}  ({})", insn.getAddress(), name, to_a))
                    n += 1
    if n == 0:
        println("  (no call references found)")
    else:
        println(_fmt("Total unique callees: {}", n))


def action_xrefs_to_address(addr=None):
    if addr is None:
        addr = askAddress("XREFs to", "Enter target address:")
    addr = to_addr(addr)
    refs = getReferencesTo(addr)
    println(_fmt("=== References TO {} ===", addr))
    count = 0
    for r in refs:
        from_a = r.getFromAddress()
        f = get_function_at_or_containing(from_a)
        fname = f.getName() if f is not None else "-"
        println(_fmt("  {}  ({})  <-  {}   [{}]", from_a, fname, r.getReferenceType(), r.getSource()))
        count += 1
    println(_fmt("Total: {}", count))


def action_xrefs_in_range():
    start = askAddress("Range start", "Start address:")
    end = askAddress("Range end", "End address (inclusive):")
    start = to_addr(start)
    end = to_addr(end)

    # Guard against huge ranges
    size = end.subtract(start) + 1
    if size > 0x10000:
        ok = askYesNo("Large range",
                      _fmt("Range is {} bytes. This can be slow. Continue?", size))
        if not ok:
            return

    println(_fmt("=== References into range {} – {} ===", start, end))
    count = 0
    # Prefer walking references from the program rather than every byte
    refmgr = currentProgram.getReferenceManager()
    it = refmgr.getReferenceDestinationIterator(
        currentProgram.getAddressFactory().getAddressSet(start, end), True)
    while it.hasNext():
        dest = it.next()
        refs = getReferencesTo(dest)
        for r in refs:
            from_a = r.getFromAddress()
            f = get_function_at_or_containing(from_a)
            fname = f.getName() if f is not None else "-"
            println(_fmt("  {}  →  {}   (from {} / {})", from_a, dest, fname, r.getReferenceType()))
            count += 1
            if count >= 500:
                println("... truncated at 500 hits")
                println(_fmt("Total hits (truncated): {}", count))
                return
    println(_fmt("Total hits: {}", count))


def action_find_constant_xrefs():
    choices = jlist([
        "0x258 (60-sec timer)",
        "0x3C (60 / threshold)",
        "0x15", "0x3D", "0xC9", "0x12C", "0x3E9", "0x7D0",
        "Custom value..."
    ])
    choice = askChoice("Constant", "Which constant to search for?", choices, choices.get(0))

    if choice is not None and str(choice).startswith("Custom"):
        val_str = askString("Value", "Enter constant (hex or decimal):", "0x258")
        if val_str is None:
            return
        val_str = val_str.strip().lower()
        if val_str.startswith("0x"):
            val = int(val_str, 16)
        else:
            val = int(val_str)
    else:
        val = int(str(choice).split()[0], 16)

    println(_fmt("=== Searching for constant {} (0x{:X}) ===", val, val))
    listing = currentProgram.getListing()
    count = 0
    insns = listing.getInstructions(True)
    while insns.hasNext() and count < 300:
        insn = insns.next()
        num_ops = insn.getNumOperands()
        found = False
        for i in range(num_ops):
            objs = insn.getOpObjects(i)
            if objs is None:
                continue
            for o in objs:
                try:
                    if hasattr(o, "getValue") and int(o.getValue()) == val:
                        f = get_function_at_or_containing(insn.getAddress())
                        fname = f.getName() if f is not None else "-"
                        println(_fmt("  {}  [{}]  {}", insn.getAddress(), fname, insn))
                        count += 1
                        found = True
                        break
                except Exception:
                    pass
            if found:
                break
    println(_fmt("Found {} instruction(s) using immediate 0x{:X}", count, val))


def action_rename_at_address():
    addr = askAddress("Rename", "Address to rename:")
    name = askString("New name", "Enter new name:", "new_name")
    if name is None or name == "":
        return

    a = to_addr(addr)
    f = get_function_at_or_containing(a)
    if f is not None and f.getEntryPoint().equals(a):
        safe_rename_function(a, name)
    else:
        safe_create_label(a, name)
        if f is not None:
            if askYesNo("Also rename function?",
                        _fmt("Rename the containing function {} as well?", f.getName())):
                safe_rename_function(f.getEntryPoint(), name)


def action_add_comment():
    addr = askAddress("Comment", "Address for comment:")
    kinds = jlist(["Plate (above)", "EOL (end-of-line)"])
    kind = askChoice("Type", "Comment type:", kinds, kinds.get(0))
    text = askString("Text", "Comment text:")
    if text is None or text == "":
        return
    if str(kind).startswith("Plate"):
        add_plate_comment(addr, text)
    else:
        add_eol_comment(addr, text)


def action_dump_function_info(addr=None):
    if addr is None:
        addr = askAddress("Function info", "Address inside function:")
    addr = to_addr(addr)
    f = get_function_at_or_containing(addr)
    if f is None:
        println(_fmt("[-] No function at {}", addr))
        return

    println("=" * 60)
    println(_fmt("Function: {}", f.getName()))
    println(_fmt("Entry   : {}", f.getEntryPoint()))
    println(_fmt("Body size: {} addresses", f.getBody().getNumAddresses()))
    try:
        println(_fmt("Calling : {}", f.getCallingConventionName()))
    except Exception:
        pass
    try:
        println(_fmt("Signature: {}", f.getSignature()))
    except Exception:
        pass

    println("")
    println("--- Callers ---")
    action_trace_callers(f.getEntryPoint())
    println("")
    println("--- Callees ---")
    action_trace_callees(f.getEntryPoint())
    println("=" * 60)


def action_bookmark_key_sites():
    for addr, desc in KEY_LOCATIONS.items():
        a = to_addr(addr)
        createBookmark(a, "LimeRE", desc)
        println(_fmt("[+] Bookmark @ {}  {}", a, desc))
    println("Bookmarks created.  Window → Bookmarks")


def action_goto_known():
    items = []
    for a, n in sorted(KNOWN_FUNCTIONS.items()):
        items.append("F  0x%08X  %s" % (a, n))
    for a, n in sorted(KNOWN_RAM.items()):
        items.append("R  0x%08X  %s" % (a, n))
    for a, n in sorted(KEY_LOCATIONS.items()):
        items.append("K  0x%08X  %s" % (a, n))

    choices = jlist(items)
    choice = askChoice("Go to", "Select symbol:", choices, choices.get(0))
    if choice is None:
        return
    # format: "F  0x08005ED0  motor_control_main"
    parts = str(choice).split()
    addr_str = parts[1]
    addr = to_addr(addr_str)
    goTo(addr)
    println(_fmt("Navigated to {}", addr))


# ==============================================================================
#  MAIN MENU
# ==============================================================================

def run():
    menu_items = [
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
    menu = jlist(menu_items)

    while True:
        try:
            choice = askChoice("Lime RE Helper", "Choose action:", menu, menu.get(0))
        except CancelledException:
            println("Cancelled.")
            return
        except Exception as e:
            println(_fmt("[!] askChoice error: {}", e))
            return

        if choice is None:
            return

        c = str(choice)
        try:
            if c.startswith("0."):
                println("Bye.")
                return
            elif c.startswith("1."):
                action_apply_all_known_names()
            elif c.startswith("2."):
                action_trace_callers()
            elif c.startswith("3."):
                action_trace_callees()
            elif c.startswith("4."):
                action_xrefs_to_address()
            elif c.startswith("5."):
                action_xrefs_in_range()
            elif c.startswith("6."):
                action_find_constant_xrefs()
            elif c.startswith("7."):
                action_rename_at_address()
            elif c.startswith("8."):
                action_add_comment()
            elif c.startswith("9."):
                action_dump_function_info()
            elif c.startswith("10."):
                action_bookmark_key_sites()
            elif c.startswith("11."):
                action_goto_known()
            else:
                println("Unknown choice")
        except CancelledException:
            println("Action cancelled.")
        except Exception as e:
            println(_fmt("[!] Error in action: {}", e))
            import traceback
            traceback.print_exc()

        try:
            if not askYesNo("Continue?", "Run another action?"):
                break
        except CancelledException:
            break

    println("Lime RE Helper finished.")


# Ghidra executes the script file; always start the menu.
# (Do NOT rely on if __name__ == "__main__" — in Ghidra it is often not "__main__")
run()
