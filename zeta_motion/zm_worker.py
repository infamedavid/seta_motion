# zm_worker.py — Zeta Motion
# Blender 4.5+ | Linux-only
# Asynchronous, non-blocking command executor for gphoto2.

import subprocess
import threading
from queue import Queue
import bpy # <-- Importante para agendar callbacks de forma segura

# --- Cola de Comandos: Único punto de entrada para la ejecución de comandos ---
camera_cmd_queue = Queue()

def safe_run(cmd, timeout=10):
    """
    Ejecuta un comando de forma segura usando subprocess.run.
    Retorna: (stdout, stderr, returncode)
    """
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return None, f"Comando excedió el timeout de {timeout}s", 124
    except Exception as e:
        return None, str(e), 1

def _camera_command_worker():
    """
    Hilo worker que procesa comandos de la cola secuencialmente.
    Ahora puede manejar callbacks para devolver resultados de forma asíncrona.
    """
    while True:
        item = camera_cmd_queue.get()
        if item is None:
            break
        
        # El item ahora puede ser (cmd, retries, callback)
        cmd, retries, callback = item if len(item) == 3 else (item[0], item[1], None)
        
        final_stdout = None
        final_stderr = None
        
        for attempt in range(retries):
            stdout, stderr, returncode = safe_run(cmd)
            if returncode == 0:
                print(f"✅ [Zeta Motion Worker] Comando exitoso: {cmd}")
                final_stdout = stdout
                break
            else:
                final_stderr = stderr
                print(f"❌ [Zeta Motion Worker] Intento {attempt + 1}/{retries} fallido para '{cmd}': {stderr}")
        
        # Si había un callback, lo agendamos para que se ejecute en el hilo principal de Blender
        if callback:
            # Usamos un lambda para pasar los argumentos al callback
            def schedule_callback(out, err):
                # bpy.app.timers.register asegura que esto se ejecute en el hilo principal
                bpy.app.timers.register(lambda: callback(out, err))

            schedule_callback(final_stdout, final_stderr)
            
        camera_cmd_queue.task_done()

def enqueue_command(cmd, retries=1, callback=None):
    """
    Función pública para añadir un comando a la cola del worker.
    Ahora acepta un callback opcional.
    """
    camera_cmd_queue.put((cmd, retries, callback))

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
    camera_cmd_queue.put(None)
    print("[Zeta Motion] Señal de apagado enviada al worker.")