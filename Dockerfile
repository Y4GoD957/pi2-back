# 1. Usa uma imagem oficial do Python 3.13 leve
FROM python:3.13-slim

# 2. Define a pasta de trabalho dentro do container
WORKDIR /code

# 3. Copia os ficheiros de dependências primeiro (para aproveitar o cache do Docker)
COPY ./pyproject.toml ./setup.py* ./requirements.txt* /code/

# 4. Instala as dependências (ajustado para o formato que o seu projeto usar)
# Se usar requirements.txt:
RUN pip install --no-cache-dir --upgrade pip && \
    if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Se o projeto usar a instalação editável original (pip install -e .):
COPY . /code/
RUN pip install -e .

# Expõe a porta que o seu backend usa (ex: 8000 para FastAPI)
EXPOSE 8000

# 5. Comando para iniciar o Uvicorn apontando para a rede do container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]