FROM python:3.11-slim

# Define a pasta de trabalho dentro do container
WORKDIR /app

# Evita buffering nas saídas de log do Python
ENV PYTHONUNBUFFERED=1

# Instalar dependências básicas, curl e chaves
RUN apt-get update && apt-get install -y curl gnupg apt-transport-https unixodbc unixodbc-dev

# Adicionar repositório oficial da Microsoft e instalar o driver ODBC 18
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list | tee /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18

# Copia e instala as bibliotecas Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia os arquivos e módulos da aplicação
COPY . .

# Expõe a porta padrão do Streamlit
EXPOSE 8501

# Comando de inicialização do Streamlit
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]