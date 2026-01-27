"""
API REST para executar importação de dados (Kartado e Osiris) de forma assíncrona
Permite iniciar processamento e consultar status via UUID
"""

import logging
import threading
import uuid
import os
from api_client import custom_url
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from pydantic import BaseModel

from kartado import create_kartado_measurement_records
from osiris import create_osiris_measurement_records

# Configurar logger
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Import API", version="1.0.0")

# Enumeração de status das tarefas
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"

# Enumeração de sistemas de origem
class SourceSystem(str, Enum):
    KARTADO = "kartado"
    OSIRIS = "osiris"
    BOTH = "both"

# Modelo de resposta da tarefa
class TaskInfo(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    source_system: SourceSystem
    start_date: str
    end_date: str
    contract_code: Optional[str] = None
    ignore_check: bool
    ignore_images: bool
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

# Modelo de resposta simplificado para iniciar importação
class ImportDataResponse(BaseModel):
    task_id: str

# Modelo de requisição para iniciar processamento
class ImportDataRequest(BaseModel):
    start_date: str  # Formato: YYYY-MM-DD
    end_date: str  # Formato: YYYY-MM-DD
    contract_code: Optional[str] = None
    source_system: SourceSystem = SourceSystem.BOTH
    ignore_check: bool = False
    ignore_images: bool = False

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

def execute_import(
    task_id: str,
    start_date: str,
    end_date: str,
    contract_code: Optional[str],
    source_system: SourceSystem,
    ignore_check: bool,
    ignore_images: bool
):
    """
    Executa importação de dados em background e atualiza o status da tarefa
    """

    # Configura handler de log para esta tarefa
    task_handler = TaskLogHandler(task_id)
    task_handler.setLevel(logging.INFO)

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

        # Converter strings de data para datetime
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        # Executar importação baseada no sistema de origem
        results = {}

        if source_system in (SourceSystem.KARTADO, SourceSystem.BOTH):
            logger.info(f"Iniciando importação Kartado: {start_date} a {end_date}, contrato: {contract_code}")
            try:
                create_kartado_measurement_records(
                    start_date=start_dt,
                    end_date=end_dt,
                    contract_code=contract_code,
                    ignore_check=ignore_check,
                    ignore_images=ignore_images
                )
                results["kartado"] = "Concluído com sucesso"
            except Exception as e:
                logger.error(f"Erro na importação Kartado: {e}")
                results["kartado"] = f"Erro: {str(e)}"

        if source_system in (SourceSystem.OSIRIS, SourceSystem.BOTH):
            logger.info(f"Iniciando importação Osiris: {start_date} a {end_date}, contrato: {contract_code}")
            try:
                create_osiris_measurement_records(
                    start_date=start_dt,
                    end_date=end_dt,
                    contract_code=contract_code,
                    ignore_check=ignore_check,
                    ignore_images=ignore_images
                )
                results["osiris"] = "Concluído com sucesso"
            except Exception as e:
                logger.error(f"Erro na importação Osiris: {e}")
                results["osiris"] = f"Erro: {str(e)}"

        with tasks_lock:
            tasks[task_id].status = TaskStatus.COMPLETED
            tasks[task_id].completed_at = datetime.now()
            tasks[task_id].result = results

    except Exception as e:
        logger.error(f"Erro geral na importação: {e}")
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
            logger.error(f"Falha notificar conclusão: {e}")

@app.post("/import_data", response_model=ImportDataResponse, status_code=200)
async def import_data(request: ImportDataRequest, background_tasks: BackgroundTasks):
    """
    Inicia a importação de dados de forma assíncrona

    Parâmetros:
    - start_date: Data inicial no formato YYYY-MM-DD
    - end_date: Data final no formato YYYY-MM-DD
    - contract_code: Código do contrato (opcional)
    - source_system: Sistema de origem (kartado, osiris ou both) (padrão: both)
    - ignore_check: Ignorar verificação de dados nos contratos (padrão: False)
    - ignore_images: Ignorar processar imagens (padrão: False)

    Retorna:
    - UUID (task_id) para rastreamento do processamento
    """
    # Validar formato de data

    try:
        datetime.strptime(request.start_date, "%Y-%m-%d")
        datetime.strptime(request.end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de data inválido. Use YYYY-MM-DD"
        )

    task_id = str(uuid.uuid4())

    task_info = TaskInfo(
        task_id=task_id,
        status=TaskStatus.PENDING,
        created_at=datetime.now(),
        source_system=request.source_system,
        start_date=request.start_date,
        end_date=request.end_date,
        contract_code=request.contract_code,
        ignore_check=request.ignore_check,
        ignore_images=request.ignore_images
    )

    with tasks_lock:
        tasks[task_id] = task_info

    # Inicia execução em background
    background_tasks.add_task(
        execute_import,
        task_id,
        request.start_date,
        request.end_date,
        request.contract_code,
        request.source_system,
        request.ignore_check,
        request.ignore_images
    )

    # Retorna apenas o UUID para rastreamento
    return ImportDataResponse(task_id=task_id)

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
        "name": "Data Import API",
        "version": "1.0.0",
        "description": "API para importação assíncrona de dados do Kartado e Osiris",
        "endpoints": {
            "POST /import_data": "Inicia importação de dados",
            "GET /status/{task_id}": "Consulta status de uma tarefa",
            "GET /tasks": "Lista todas as tarefas",
            "GET /logs/{task_id}": "Consulta logs de uma tarefa",
            "DELETE /tasks/{task_id}": "Remove uma tarefa",
            "DELETE /logs/{task_id}": "Remove logs de uma tarefa"
        },
        "source_systems": {
            "kartado": "Importar apenas do Kartado",
            "osiris": "Importar apenas do Osiris",
            "both": "Importar de ambos os sistemas"
        }
    }

if __name__ == "__main__":
    import uvicorn

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    uvicorn.run(app, host="0.0.0.0", port=8085)
