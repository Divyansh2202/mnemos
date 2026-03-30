from setuptools import setup, find_packages

setup(
    name="mnemos",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.115.0",
        "uvicorn>=0.30.0",
        "psycopg2-binary>=2.9.9",
        "pgvector>=0.3.0",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.7.0",
        "typer>=0.12.0",
        "rich>=13.7.0",
    ],
    entry_points={
        "console_scripts": [
            "mnemos=cli.main:app",
        ],
    },
)
