"""
API REST para executar calculate_measurements de forma assíncrona
Permite iniciar processamento e consultar status via UUID
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import threading
import logging
import os
from api_client import custom_url
from enum import Enum
from engine_exec import EngineProcessor
from dotenv import load_dotenv

app = FastAPI(title="Engine Processor API", version="1.0.0")

# Enumeração de status das tarefas
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"

# Modelo de resposta da tarefa
class TaskInfo(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    measurement: Optional[str] = None
    use_cached_data: bool
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

# Modelo de resposta de logs
class LogEntry(BaseModel):
    timestamp: str
    level: str
    logger: str
    message: str

class LogResponse(BaseModel):
    task_id: str
    logs: List[str]
    total_lines: int

# Modelo de requisição para iniciar processamento
class ProcessRequest(BaseModel):
    measurement: Optional[str] = None
    use_cached_data: bool = True
    debug: bool = False

# Armazenamento em memória das tarefas (em produção, usar Redis ou DB)
tasks: Dict[str, TaskInfo] = {}
tasks_lock = threading.Lock()

# Armazenamento de logs por tarefa
task_logs: Dict[str, List[str]] = {}
task_logs_lock = threading.Lock()

class TaskLogHandler(logging.Handler):
    """Handler customizado para capturar logs por tarefa"""

    def __init__(self, task_id: str):
        super().__init__()
        self.task_id = task_id
        self.formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def emit(self, record):
        try:
            msg = self.format(record)
            with task_logs_lock:
                if self.task_id not in task_logs:
                    task_logs[self.task_id] = []
                task_logs[self.task_id].append(msg)
        except Exception:
            self.handleError(record)

def execute_calculation(task_id: str, measurement: Optional[str], use_cached_data: bool, debug: bool):
    """
    Executa calculate_measurements em background e atualiza o status da tarefa
    """
    # Configura handler de log para esta tarefa
    task_handler = TaskLogHandler(task_id)
    task_handler.setLevel(logging.DEBUG if debug else logging.INFO)

    # Adiciona o handler ao logger raiz para capturar todos os logs
    root_logger = logging.getLogger()
    root_logger.addHandler(task_handler)

    # Inicializa lista de logs para esta tarefa
    with task_logs_lock:
        task_logs[task_id] = []

    try:
        with tasks_lock:
            tasks[task_id].status = TaskStatus.RUNNING
            tasks[task_id].started_at = datetime.now()

        processor = EngineProcessor(debug=debug)
        processor.calculate_measurements(use_cached_data=use_cached_data, measurement=measurement)

        with tasks_lock:
            tasks[task_id].status = TaskStatus.COMPLETED
            tasks[task_id].completed_at = datetime.now()
            tasks[task_id].result = {"message": "Processamento concluído com sucesso"}

    except Exception as e:
        with tasks_lock:
            tasks[task_id].status = TaskStatus.ERROR
            tasks[task_id].completed_at = datetime.now()
            tasks[task_id].error = str(e)

    finally:

        # Monta o payload
        post_json = {
            "task_id": task_id,
            "error": tasks[task_id].error if tasks[task_id].error else ""
        }

        # Remove o handler após conclusão
        root_logger.removeHandler(task_handler)

        # Remove o handler após conclusão
        root_logger.removeHandler(task_handler)

        load_dotenv()

        # Obter variáveis de ambiente necessárias
        API_BASE_URL = os.getenv("ARTERIS_API_BASE_URL")
        API_TOKEN = os.getenv("ARTERIS_API_TOKEN")        

        # Envia registro de medição usando cliente de API
        _url = f"{API_BASE_URL}/method/arteris_app.api.support.taskcompleted"
        try:
            post_response = custom_url(
                api_base_url=_url,
                api_token=API_TOKEN,
                body=post_json,
                method="POST")
        except Exception as e:
            logging.error(f"Falha notificar conclusão: {e}")

@app.post("/calculate", status_code=200)
async def start_calculation(request: ProcessRequest, background_tasks: BackgroundTasks):
    """
    Inicia o processamento de calculate_measurements de forma assíncrona

    Parâmetros:
    - measurement: ID da medição específica (opcional)
    - use_cached_data: Usar dados em cache (padrão: True)
    - debug: Habilitar modo debug (padrão: False)

    Retorna:
    - UUID da tarefa para rastreamento do processamento
    """
    task_id = str(uuid.uuid4())

    task_info = TaskInfo(
        task_id=task_id,
        status=TaskStatus.PENDING,
        created_at=datetime.now(),
        measurement=request.measurement,
        use_cached_data=request.use_cached_data
    )

    with tasks_lock:
        tasks[task_id] = task_info

    # Inicia execução em background
    background_tasks.add_task(
        execute_calculation,
        task_id,
        request.measurement,
        request.use_cached_data,
        request.debug
    )

    return {"task_id": task_id}

@app.get("/status/{task_id}", response_model=TaskInfo)
async def get_task_status(task_id: str):
    """
    Consulta o status de uma tarefa pelo UUID

    Parâmetros:
    - task_id: UUID da tarefa

    Retorna:
    - TaskInfo com status atual da tarefa
    """
    with tasks_lock:
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        return tasks[task_id]

@app.get("/tasks", response_model=Dict[str, TaskInfo])
async def list_all_tasks():
    """
    Lista todas as tarefas registradas no sistema

    Retorna:
    - Dicionário com task_id como chave e TaskInfo como valor
    """
    with tasks_lock:
        return tasks.copy()

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """
    Remove uma tarefa do registro

    Parâmetros:
    - task_id: UUID da tarefa

    Retorna:
    - Mensagem de confirmação
    """
    with tasks_lock:
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        del tasks[task_id]
        return {"message": f"Tarefa {task_id} removida com sucesso"}

@app.get("/logs/{task_id}", response_model=LogResponse)
async def get_task_logs(
    task_id: str,
    offset: int = Query(0, ge=0, description="Número de linhas para pular"),
    limit: int = Query(100, ge=1, le=10000, description="Máximo de linhas para retornar")
):
    """
    Consulta os logs gerados por uma tarefa específica

    Parâmetros:
    - task_id: UUID da tarefa
    - offset: Número de linhas para pular (padrão: 0)
    - limit: Máximo de linhas para retornar (padrão: 100, máx: 10000)

    Retorna:
    - LogResponse com logs da tarefa
    """
    with tasks_lock:
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada")

    with task_logs_lock:
        if task_id not in task_logs:
            return LogResponse(task_id=task_id, logs=[], total_lines=0)

        all_logs = task_logs[task_id]
        total_lines = len(all_logs)
        logs_slice = all_logs[offset:offset + limit]

        return LogResponse(
            task_id=task_id,
            logs=logs_slice,
            total_lines=total_lines
        )

@app.delete("/logs/{task_id}")
async def delete_task_logs(task_id: str):
    """
    Remove os logs de uma tarefa específica

    Parâmetros:
    - task_id: UUID da tarefa

    Retorna:
    - Mensagem de confirmação
    """
    with task_logs_lock:
        if task_id not in task_logs:
            raise HTTPException(status_code=404, detail="Logs da tarefa não encontrados")
        del task_logs[task_id]
        return {"message": f"Logs da tarefa {task_id} removidos com sucesso"}

@app.get("/")
async def root():
    """
    Endpoint raiz com informações da API
    """
    return {
        "name": "Engine Processor API",
        "version": "1.0.0",
        "endpoints": {
            "POST /calculate": "Inicia processamento de medições",
            "GET /status/{task_id}": "Consulta status de uma tarefa",
            "GET /tasks": "Lista todas as tarefas",
            "GET /logs/{task_id}": "Consulta logs de uma tarefa",
            "DELETE /tasks/{task_id}": "Remove uma tarefa",
            "DELETE /logs/{task_id}": "Remove logs de uma tarefa"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8084)
