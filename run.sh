#!/bin/bash

set -e

# Проверка наличия Python 3.12.7
PYTHON_VERSION=$(python3 --version 2>&1)
REQUIRED_VERSION="Python 3.12.7"

if [[ "$PYTHON_VERSION" != "$REQUIRED_VERSION" ]]; then
    echo "Требуется Python 3.12.7, найдено: $PYTHON_VERSION"
    echo "Убедитесь, что у вас установлен Python 3.12.7 и добавлен в PATH."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Создаю виртуальное окружение с Python 3.12.7..."
    python3.12 -m venv venv
fi

source venv/bin/activate

echo "Устанавливаю зависимости..."
pip install --upgrade pip
pip install -r requirements.txt

if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi


uvicorn main:app --host 0.0.0.0 --port 8000 --reload
