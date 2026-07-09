#!/usr/bin/env python3
"""Script puntual para reparar gui/main_window.py.
Tres fixes:
  1. execute_restore (líneas 6351-6491): dos implementaciones superpuestas → versión limpia.
  2. Duplicate if __name__ (línea 7182): insertado en medio de execute_maintenance → eliminar.
  3. Extra ) en línea 7497 → eliminar.
"""

import sys

TARGET = "gui/main_window.py"

with open(TARGET, "r", encoding="utf-8") as fh:
    lines = fh.readlines()

total = len(lines)
print(f"Archivo leído: {total} líneas")

# ── helpers ────────────────────────────────────────────────────────────────────

def find_line(pattern, start=0, end=None):
    """Devuelve el índice 0-based de la primera línea que contiene pattern."""
    stop = end if end is not None else total
    for i in range(start, stop):
        if pattern in lines[i]:
            return i
    return -1

# ══════════════════════════════════════════════════════════════════════════════
# FIX 1 — execute_restore limpio
# ══════════════════════════════════════════════════════════════════════════════

er_start = find_line("    def execute_restore(self, backup_dir,")
mc_start = find_line("    def maintain_collections(self):", start=er_start + 1)

if er_start == -1 or mc_start == -1:
    print(f"ERROR fix1: execute_restore={er_start}, maintain_collections={mc_start}")
    sys.exit(1)

print(f"Fix 1: execute_restore líneas {er_start+1}–{mc_start} → reescritura limpia")

NEW_EXECUTE_RESTORE = '''\
    def execute_restore(self, backup_dir, metadata, is_full_restore, selected_collections,
                        conflict_mode, drop_first, dialog):
        """Ejecutar la restauración con las opciones configuradas."""
        try:
            all_collections = metadata.get("collections", [])

            if not is_full_restore and not selected_collections:
                QMessageBox.warning(
                    dialog, "Advertencia",
                    "Por favor, seleccione al menos una colección para restaurar"
                )
                return

            collections_to_restore = (
                all_collections if is_full_restore else selected_collections
            )
            is_compressed = metadata.get("compressed", False)
            total_cols = len(collections_to_restore)
            collections_dir = os.path.join(backup_dir, "collections")
            errors = []
            restored_collections = [0]

            progress_dialog = QProgressDialog(
                "Preparando restauración...", "Cancelar", 0, 100, dialog
            )
            progress_dialog.setWindowTitle("Restauración en progreso")
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setAutoClose(False)
            progress_dialog.setAutoReset(False)
            progress_dialog.setValue(0)

            def perform_restore():
                for i, collection_name in enumerate(collections_to_restore):
                    if progress_dialog.wasCanceled():
                        break

                    pct = 10 + int((i / total_cols) * 80)
                    progress_dialog.setValue(pct)
                    progress_dialog.setLabelText(
                        f"Restaurando colección: {collection_name}..."
                    )

                    try:
                        col_file = os.path.join(
                            collections_dir, f"{collection_name}.json"
                        )
                        col_gz = col_file + ".gz"

                        if not os.path.exists(col_file) and not os.path.exists(col_gz):
                            errors.append(
                                f"Archivo de colección '{collection_name}' no encontrado"
                            )
                            continue

                        if drop_first and collection_name in self.db.list_collection_names():
                            self.db.drop_collection(collection_name)

                        documents = []
                        if is_compressed and os.path.exists(col_gz):
                            with gzip.open(col_gz, "rt", encoding="utf-8") as f:
                                documents = json.load(f)
                        elif os.path.exists(col_file):
                            with open(col_file, "r", encoding="utf-8") as f:
                                documents = json.load(f)

                        if not documents:
                            errors.append(
                                f"No se encontraron documentos en '{collection_name}'"
                            )
                            continue

                        from bson.objectid import ObjectId

                        for doc in documents:
                            if (
                                "_id" in doc
                                and isinstance(doc["_id"], str)
                                and doc["_id"].startswith("ObjectId(")
                            ):
                                id_str = (
                                    doc["_id"]
                                    .replace("ObjectId('", "")
                                    .replace("')", "")
                                    .replace('"', "")
                                )
                                try:
                                    doc["_id"] = ObjectId(id_str)
                                except Exception:
                                    pass

                        col = self.db[collection_name]
                        if conflict_mode == 0:
                            existing = set(
                                d["_id"] for d in col.find({}, {"_id": 1})
                            )
                            to_rm = [d for d in documents if d["_id"] in existing]
                            if to_rm:
                                col.delete_many(
                                    {"_id": {"$in": [d["_id"] for d in to_rm]}}
                                )
                            col.insert_many(documents)
                        elif conflict_mode == 1:
                            existing = set(
                                d["_id"] for d in col.find({}, {"_id": 1})
                            )
                            to_ins = [d for d in documents if d["_id"] not in existing]
                            if to_ins:
                                col.insert_many(to_ins)
                        else:
                            existing = set(
                                d["_id"] for d in col.find({}, {"_id": 1})
                            )
                            to_ins = [d for d in documents if d["_id"] not in existing]
                            if to_ins:
                                col.insert_many(to_ins)

                        idx_file = os.path.join(
                            collections_dir, f"{collection_name}_indexes.json"
                        )
                        idx_gz = idx_file + ".gz"
                        indexes = []
                        if os.path.exists(idx_file):
                            with open(idx_file, "r", encoding="utf-8") as f_i:
                                indexes = json.load(f_i)
                        elif os.path.exists(idx_gz):
                            with gzip.open(idx_gz, "rt", encoding="utf-8") as f_i:
                                indexes = json.load(f_i)

                        for idx in indexes:
                            if idx.get("name") != "_id_":
                                try:
                                    col.create_index(
                                        idx["key"], name=idx.get("name")
                                    )
                                except Exception:
                                    pass

                        restored_collections[0] += 1

                    except Exception as e:
                        errors.append(
                            f"Error restaurando '{collection_name}': {e}"
                        )

                report_file = os.path.join(backup_dir, "restore_report.txt")
                try:
                    with open(report_file, "w", encoding="utf-8") as f:
                        f.write("Informe de restauración\n")
                        f.write(
                            f"Tipo: {'Completa' if is_full_restore else 'Selectiva'}\n"
                        )
                        f.write(
                            f"Colecciones restauradas: {restored_collections[0]}"
                            f" de {len(collections_to_restore)}\n"
                        )
                        if errors:
                            f.write("\nErrores durante la restauración:\n")
                            for err in errors:
                                f.write(f"  - {err}\n")
                except Exception:
                    pass

                progress_dialog.setValue(100)
                progress_dialog.setLabelText(
                    f"Restauración completada. "
                    f"{restored_collections[0]} colecciones restauradas."
                )

            restore_thread = threading.Thread(target=perform_restore)
            restore_thread.daemon = True
            restore_thread.start()

            while restore_thread.is_alive() and not progress_dialog.wasCanceled():
                QApplication.processEvents()

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Error durante la restauración: {str(e)}"
            )
            self.show_status_message(f"Error: {str(e)}", error=True)

'''

lines = lines[:er_start] + [NEW_EXECUTE_RESTORE] + lines[mc_start:]
total = len(lines)
print(f"  → archivo ahora tiene {total} líneas")

# ══════════════════════════════════════════════════════════════════════════════
# FIX 2 — duplicate if __name__ == '__main__': en medio de la clase
# ══════════════════════════════════════════════════════════════════════════════
# Buscamos TODOS los if __name__ a columna 0
ifmain_positions = [
    i for i, ln in enumerate(lines)
    if ln.strip() == "if __name__ == '__main__':"
]
print(f"Fix 2: if __name__ encontrado en líneas {[p+1 for p in ifmain_positions]}")

if len(ifmain_positions) >= 2:
    # El primero es el intruso (está en medio de la clase).
    # Eliminar las 5 líneas del bloque if __name__: (la declaración + 4 líneas de cuerpo)
    bad_pos = ifmain_positions[0]
    # Verificar que las 4 líneas siguientes forman el bloque de entrada
    block = "".join(lines[bad_pos:bad_pos+5])
    print(f"  Eliminando:\n{block}")
    lines = lines[:bad_pos] + lines[bad_pos + 5:]
    total = len(lines)
    print(f"  → archivo ahora tiene {total} líneas")
else:
    print("  Solo hay un if __name__, no se elimina nada.")

# ══════════════════════════════════════════════════════════════════════════════
# FIX 3 — paréntesis de cierre extra (línea original ~7497)
# ══════════════════════════════════════════════════════════════════════════════
# Buscamos el patrón: línea con strftime termina en ")  y la siguiente es "            )"
extra_paren_idx = -1
for i in range(len(lines) - 1):
    if (
        "strftime('%d/%m/%Y %H:%M')" in lines[i]
        and lines[i].rstrip().endswith('")')
        and lines[i + 1].strip() == ")"
    ):
        extra_paren_idx = i + 1
        break

if extra_paren_idx != -1:
    print(f"Fix 3: eliminando ) extra en línea {extra_paren_idx + 1}: {lines[extra_paren_idx].rstrip()!r}")
    lines = lines[:extra_paren_idx] + lines[extra_paren_idx + 1:]
    total = len(lines)
    print(f"  → archivo ahora tiene {total} líneas")
else:
    print("Fix 3: patrón de ) extra no encontrado (puede que ya esté corregido).")

# ══════════════════════════════════════════════════════════════════════════════
# Escribir resultado
# ══════════════════════════════════════════════════════════════════════════════
with open(TARGET, "w", encoding="utf-8") as fh:
    fh.writelines(lines)

print(f"\nArchivo guardado: {TARGET} ({total} líneas)")

# Verificar sintaxis
import py_compile, tempfile, shutil
tmp = tempfile.mktemp(suffix=".py")
shutil.copy(TARGET, tmp)
try:
    py_compile.compile(tmp, doraise=True)
    print("✅ SINTAXIS OK — el archivo parsea correctamente")
except py_compile.PyCompileError as e:
    print(f"❌ SINTAXIS ERROR: {e}")
finally:
    import os
    os.unlink(tmp)
