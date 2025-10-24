# zm_worker.py — Zeta Motion
# Blender 4.5+ | Linux-only
# Asynchronous, non-blocking task executor for gphoto2 and other callables.

import subprocess
import threading
from queue import Queue
import bpy # <-- Importante para agendar callbacks de forma segura

# --- Cola de Tareas: Único punto de entrada para la ejecución de tareas ---
task_queue = Queue()

def _camera_command_worker():
    """
    Hilo worker que procesa tareas (funciones o comandos) de la cola secuencialmente.
    """
    while True:
        item = task_queue.get()
        if item is None:
            break

        func, tag, callback = item
        print(f"[worker:{tag}] task started")

        result = None
        error = None

        try:
            if callable(func):
                result = func()
            else:
                raise TypeError(f"Task must be a callable function, but got {type(func)}")

        except Exception as e:
            print(f"❌ [worker:{tag}] task failed: {e}")
            error = e

        if callback and error is None:
            try:
                bpy.app.timers.register(lambda: callback(result))
            except Exception as cb_err:
                print(f"❌ [worker:{tag}] callback scheduling failed: {cb_err}")

        task_queue.task_done()

def enqueue(func, tag="general", callback=None):
    """
    Añade una tarea (función callable) a la cola del worker.

    Parameters
    ----------
    func : callable
        La función que se ejecutará en el hilo del worker.
    tag : str, optional
        Una etiqueta para identificar la tarea en los logs.
    callback : callable, optional
        Una función que se llamará en el hilo principal de Blender cuando la
        tarea termine. Recibirá el valor de retorno de `func` como argumento.
    """
    if not callable(func):
        print(f"❌ [zm_worker] Error: la tarea encolada debe ser una función (callable), no {type(func)}.")
        return

    task_queue.put((func, tag, callback))


# --- Funciones para el ciclo de vida del addon ---
_worker_thread = None

def start_worker():
    """Inicia el hilo del worker. Se llama desde __init__.py en register()."""
    global _worker_thread
    if _worker_thread is None or not _worker_thread.is_alive():
        _worker_thread = threading.Thread(target=_camera_command_worker, daemon=True)
        _worker_thread.start()
        print("[Zeta Motion] Worker asíncrono iniciado.")

def stop_worker():
    """Envía la señal de apagado a la cola. Se llama desde __init__.py en unregister()."""
    task_queue.put(None)
    print("[Zeta Motion] Señal de apagado enviada al worker.")
